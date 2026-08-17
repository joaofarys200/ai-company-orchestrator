"""
JARVIS OS - Lecture Recorder Service
Captura áudio contínuo de microfone físico em streaming para disco,
gerencia sessões de gravação de aulas e emite métricas de status em tempo real.
"""

from __future__ import annotations

import os
import time
import uuid
import wave
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any

import math

try:
    import numpy as np
except ImportError:
    np = None

try:
    import sounddevice as sd
except ImportError:
    sd = None


@dataclass
class LectureSession:
    session_id: str
    subject: str
    title: str
    professor: str = ""
    audio_path: str = ""
    status: str = "IDLE"  # IDLE, RECORDING, TRANSCRIBING, SYNTHESIZING, COMPLETED, FAILED
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: float = 0.0
    markdown_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LectureRecorderService:
    def __init__(
        self,
        output_dir: str = "temp_audio",
        sample_rate: int = 16000,
        channels: int = 1,
        on_audio_level: Optional[Callable[[float], None]] = None,
        on_status_change: Optional[Callable[[LectureSession], None]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_audio_level = on_audio_level
        self.on_status_change = on_status_change

        self._current_session: Optional[LectureSession] = None
        self._is_recording = False
        self._audio_stream: Optional[Any] = None
        self._wave_file: Optional[wave.Wave_write] = None
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._current_level: float = 0.0
        self._history: Dict[str, LectureSession] = {}

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def current_session(self) -> Optional[LectureSession]:
        with self._lock:
            return self._current_session

    def start_recording(
        self,
        subject: str,
        title: str,
        professor: str = "",
        device_index: Optional[int] = None,
    ) -> LectureSession:
        """Inicia a gravação de uma nova aula."""
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Já existe uma gravação de aula em andamento.")

            session_id = f"lec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            audio_filename = f"{session_id}.wav"
            audio_path = str(self.output_dir / audio_filename)

            # Inicializar arquivo WAV
            self._wave_file = wave.open(audio_path, "wb")
            self._wave_file.setnchannels(self.channels)
            self._wave_file.setsampwidth(2)  # 16-bit PCM = 2 bytes
            self._wave_file.setframerate(self.sample_rate)

            now_iso = datetime.now().isoformat()
            self._current_session = LectureSession(
                session_id=session_id,
                subject=subject.strip() or "Geral",
                title=title.strip() or f"Aula de {datetime.now().strftime('%d/%m/%Y')}",
                professor=professor.strip(),
                audio_path=audio_path,
                status="RECORDING",
                started_at=now_iso,
            )

            self._is_recording = True
            self._start_time = time.time()

            # Iniciar stream de captura
            if sd is not None:
                try:
                    self._audio_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=self.channels,
                        dtype="int16",
                        callback=self._audio_callback,
                        device=device_index,
                        blocksize=int(self.sample_rate * 0.1),  # blocos de 100ms
                    )
                    self._audio_stream.start()
                except Exception as e:
                    self._is_recording = False
                    self._wave_file.close()
                    self._current_session.status = "FAILED"
                    self._current_session.error_message = f"Falha ao abrir dispositivo de áudio: {e}"
                    raise RuntimeError(f"Erro ao inicializar microfone: {e}") from e

            self._history[session_id] = self._current_session

            if self.on_status_change:
                self.on_status_change(self._current_session)

            return self._current_session

    def stop_recording(self) -> LectureSession:
        """Encerra a gravação da aula e fecha o arquivo de áudio."""
        with self._lock:
            if not self._is_recording or self._current_session is None:
                raise RuntimeError("Nenhuma gravação de aula ativa para encerrar.")

            self._is_recording = False
            duration = max(0.0, time.time() - self._start_time)

            if self._audio_stream is not None:
                try:
                    self._audio_stream.stop()
                    self._audio_stream.close()
                except Exception:
                    pass
                self._audio_stream = None

            if self._wave_file is not None:
                try:
                    self._wave_file.close()
                except Exception:
                    pass
                self._wave_file = None

            self._current_session.ended_at = datetime.now().isoformat()
            self._current_session.duration_seconds = round(duration, 2)
            self._current_session.status = "TRANSCRIBING"

            session_copy = self._current_session
            self._history[session_copy.session_id] = session_copy

            if self.on_status_change:
                self.on_status_change(session_copy)

            return session_copy

    def _audio_callback(self, indata: Any, frames: int, time_info: Any, status: Any) -> None:
        """Callback executado pelo sounddevice a cada bloco de áudio."""
        if not self._is_recording or self._wave_file is None:
            return

        try:
            # Escrever bytes diretamente no arquivo WAV
            raw_bytes = indata.tobytes() if hasattr(indata, "tobytes") else bytes(indata)
            self._wave_file.writeframes(raw_bytes)

            # Calcular nível de volume RMS
            if np is not None and isinstance(indata, np.ndarray):
                samples = indata.astype(np.float32)
                rms = float(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0.0
                level = float(np.clip(rms / 10000.0, 0.0, 1.0))
            else:
                level = 0.5 if len(raw_bytes) > 0 else 0.0

            self._current_level = level

            if self.on_audio_level:
                self.on_audio_level(level)
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """Retorna o estado operacional e métricas em tempo real."""
        with self._lock:
            if not self._is_recording or self._current_session is None:
                return {
                    "is_recording": False,
                    "status": "IDLE",
                    "current_level": 0.0,
                    "current_session": None,
                }

            current_duration = round(time.time() - self._start_time, 1)
            session_data = self._current_session.to_dict()
            session_data["duration_seconds"] = current_duration

            return {
                "is_recording": True,
                "status": self._current_session.status,
                "current_level": self._current_level,
                "duration_seconds": current_duration,
                "current_session": session_data,
            }

    def list_history(self) -> list[Dict[str, Any]]:
        """Lista histórico de sessões gravadas."""
        with self._lock:
            return [s.to_dict() for s in self._history.values()]
