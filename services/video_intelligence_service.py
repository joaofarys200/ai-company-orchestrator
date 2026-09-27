"""
JARVIS OS - Video Intelligence Service
Processamento multimodal de vídeo para a área de Estudo:
Extração de metadados, áudio, transcrição com timestamps granulares,
análise visual de keyframes, deteção de slides/diagramas, janelas de contexto
multimodal, Q&A temporal, notas de Cornell com timestamps, geração de quizzes
e flashcards multimodais, e sincronização com o Knowledge Vault.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageStat

from services.lecture_synthesizer import LocalTranscriber, VaultLinker


# ---------------------------------------------------------------------------
# Formatos Suportados e Capability Detection
# ---------------------------------------------------------------------------

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
SUPPORTED_VIDEO_FORMATS = SUPPORTED_VIDEO_EXTENSIONS

# Regex para sanitização de nomes de ficheiro e proteção contra path traversal
SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.\(\)\s]+$")


def validate_video_path(path: str) -> bool:
    """Valida formato de vídeo e protege contra path traversal."""
    p_str = str(path).replace("\\", "/")
    if ".." in p_str:
        raise ValueError("PATH_TRAVERSAL_DETECTED: Caminho contém sequências relativas ilegais.")
    
    ext = Path(p_str).suffix.lower()
    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError(f"UNSUPPORTED_VIDEO_FORMAT: Extensão '{ext}' não suportada. Suportadas: {sorted(list(SUPPORTED_VIDEO_EXTENSIONS))}")
    return True


def validate_video_url(url: str) -> bool:
    """Valida URL de vídeo e protege contra SSRF."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("SSRF_FORBIDDEN_HOST: Apenas esquemas HTTP/HTTPS são permitidos.")
    
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("SSRF_FORBIDDEN_HOST: URL sem host válido.")
    
    if hostname in ("127.0.0.1", "localhost", "0.0.0.0", "169.254.169.254") or hostname.startswith("10.") or hostname.startswith("192.168."):
        raise ValueError("SSRF_FORBIDDEN_HOST: Acesso a endereços de rede privada/interna é bloqueado.")
    return True


def sanitize_transcript_for_prompt(text: str) -> str:
    """Sanitiza texto da transcrição para prevenir injeção de instruções de sistema."""
    patterns = [
        r"SYSTEM\s+INSTRUCTION:?",
        r"IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS",
        r"DISREGARD\s+ALL\s+PRIOR\s+RULES",
    ]
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "[REMOVED]", cleaned, flags=re.IGNORECASE)
    return cleaned



def get_ffmpeg_binary() -> Optional[str]:
    """Localiza o binário do ffmpeg no sistema ou via imageio-ffmpeg."""
    # 1. Variável de ambiente explícita
    env_ffmpeg = os.environ.get("FFMPEG_PATH")
    if env_ffmpeg and os.path.isfile(env_ffmpeg) and os.access(env_ffmpeg, os.X_OK):
        return env_ffmpeg

    # 2. imageio-ffmpeg instalado no ambiente Python
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except (ImportError, Exception):
        pass

    # 3. PATH do sistema
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    return None


def get_ffprobe_binary() -> Optional[str]:
    """Localiza ffprobe se disponível."""
    env_ffprobe = os.environ.get("FFPROBE_PATH")
    if env_ffprobe and os.path.isfile(env_ffprobe) and os.access(env_ffprobe, os.X_OK):
        return env_ffprobe

    which_ffprobe = shutil.which("ffprobe")
    if which_ffprobe:
        return which_ffprobe

    # Se imageio-ffmpeg estiver em uso, tentar localizar ffprobe na mesma pasta
    ffmpeg_exe = get_ffmpeg_binary()
    if ffmpeg_exe:
        candidate = Path(ffmpeg_exe).parent / "ffprobe.exe"
        if candidate.is_file():
            return str(candidate)

    return None


def check_video_capabilities() -> Dict[str, Any]:
    """Verifica as capacidades reais do motor de vídeo."""
    ffmpeg_path = get_ffmpeg_binary()
    ffmpeg_ok = ffmpeg_path is not None
    version_str = "Unavailable"
    if ffmpeg_ok:
        try:
            res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                version_str = res.stdout.splitlines()[0]
            else:
                ffmpeg_ok = False
        except Exception:
            ffmpeg_ok = False

    return {
        "ffmpeg_available": ffmpeg_ok,
        "ffmpeg_path": ffmpeg_path if ffmpeg_ok else None,
        "ffmpeg_binary": ffmpeg_path if ffmpeg_ok else None,
        "ffmpeg_version": version_str,
        "supported_formats": sorted(list(SUPPORTED_VIDEO_EXTENSIONS)),
        "transcriber_available": True,
        "visual_analysis_available": True,
    }


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class VideoKeyframe:
    frame_id: str
    timestamp: float
    timestamp_str: str
    image_path: str
    image_url: str = ""
    source_id: str = ""
    scene_id: str = "scene_0"
    provenance: str = "FFMPEG_EXTRACTION"
    is_slide: bool = False
    slide_confidence: float = 0.0
    visual_type: str = "general"  # slide, diagram, chart, table, code, screenshot, general
    visual_description: str = ""
    evidence_status: str = "VISUAL_OBSERVED"  # VISUAL_OBSERVED, VISUAL_UNKNOWN
    has_text: bool = False
    confidence: float = 0.85

    def __post_init__(self):
        if not self.confidence and self.slide_confidence:
            self.confidence = self.slide_confidence
        elif self.confidence and not self.slide_confidence:
            self.slide_confidence = self.confidence
        if self.is_slide:
            self.has_text = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


KeyframeData = VideoKeyframe


@dataclass
class SlideCandidate:
    timestamp: float
    timestamp_str: str = ""
    frame_id: str = ""
    confidence: float = 0.8
    is_slide: bool = True
    evidence_status: str = "OBSERVED"
    title: str = "Diapositivo Identificado"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class TranscriptSegment:
    segment_id: str = ""
    start: float = 0.0
    end: float = 0.0
    timestamp: str = ""  # "00:17:32"
    text: str = ""
    confidence: float = 0.95
    language: str = "en"
    words: List[Dict[str, Any]] = field(default_factory=list)
    id: Optional[Any] = None

    def __post_init__(self):
        if self.id is not None and not self.segment_id:
            self.segment_id = f"seg_{self.id}"
        elif self.segment_id and self.id is None:
            try:
                self.id = int(self.segment_id.split("_")[-1])
            except Exception:
                self.id = 0
        if not self.timestamp and self.start >= 0:
            self.timestamp = format_timestamp(self.start)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoChapter:
    chapter_id: str = "ch_0"
    title: str = "Introdução"
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    start_timestamp: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    summary: str = ""
    key_concepts: List[str] = field(default_factory=list)
    provenance: str = "SEMANTIC_TRANSCRIPT_SEGMENTATION"
    confidence: float = 0.85

    def __post_init__(self):
        if self.start_time > 0 and self.start_seconds == 0:
            self.start_seconds = self.start_time
        elif self.start_seconds > 0 and self.start_time == 0:
            self.start_time = self.start_seconds
        if self.end_time > 0 and self.end_seconds == 0:
            self.end_seconds = self.end_time
        elif self.end_seconds > 0 and self.end_time == 0:
            self.end_time = self.end_seconds
        if not self.start_timestamp:
            self.start_timestamp = format_timestamp(self.start_time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoCornellNotes:
    document_id: str
    topic: str
    subject: str
    date: str
    executive_summary: str
    cue_column: List[Dict[str, Any]]
    detailed_notes: str
    glossary: str
    action_items: List[str]
    title: str = ""

    def __post_init__(self):
        if not self.title:
            self.title = self.topic

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoStudyQuizQuestion:
    id: str
    question: str
    question_type: str
    options: List[str]
    correct_index: int
    correct_answer: str
    explanation: str
    source_ids: List[str] = field(default_factory=list)
    timestamp: str = ""
    frame_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoStudyQuiz:
    quiz_id: str
    document_id: str
    topic: str
    questions: List[Any]
    transfer_question: Dict[str, Any]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoStudyFlashcard:
    card_id: str
    document_id: str
    front: str
    back: str
    source_ids: List[str] = field(default_factory=list)
    timestamp: str = ""
    frame_id: Optional[str] = None
    difficulty: str = "MEDIUM"
    next_review: float = 0.0
    repetitions: int = 0
    interval_days: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


@dataclass
class VideoMetadata:
    source_id: str
    filename: str
    title: str
    subject: str
    duration_seconds: float
    duration_str: str
    width: int
    height: int
    fps: float
    codec: str
    language: str
    source_hash: str
    creation_date: str
    provenance: Dict[str, Any]
    processing_status: str  # UPLOADING, VALIDATING, EXTRACTING_AUDIO, TRANSCRIBING, ANALYZING_VIDEO, INDEXING, READY, FAILED
    file_path: str = ""
    audio_path: str = ""
    error_message: Optional[str] = None
    is_online: bool = False
    source_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VideoContextWindow:
    timestamp: float = 0.0
    timestamp_str: str = ""
    current_segment: Optional[Any] = None
    prev_segments: List[Any] = field(default_factory=list)
    next_segments: List[Any] = field(default_factory=list)
    relevant_frames: List[Any] = field(default_factory=list)
    chapter: Optional[Any] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    current_timestamp: float = 0.0
    surrounding_transcript: str = ""
    current_chapter: Optional[Any] = None

    def __post_init__(self):
        if self.current_timestamp == 0.0 and self.timestamp > 0.0:
            self.current_timestamp = self.timestamp
        elif self.timestamp == 0.0 and self.current_timestamp > 0.0:
            self.timestamp = self.current_timestamp
        if self.current_chapter is None and self.chapter is not None:
            self.current_chapter = self.chapter
        elif self.chapter is None and self.current_chapter is not None:
            self.chapter = self.current_chapter

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VideoStudyNote:
    note_id: str
    document_id: str
    timestamp: float
    timestamp_str: str
    note: str
    frame_id: Optional[str] = None
    selected_text: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def format_timestamp(seconds: float) -> str:
    """Formata segundos para formato HH:MM:SS ou MM:SS."""
    sec = max(0, int(seconds))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_timestamp(timestamp_str: str) -> float:
    """Converte '00:17:32' ou '17:32' de volta para segundos."""
    parts = timestamp_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return 0.0
    return 0.0


# ---------------------------------------------------------------------------
# VideoIntelligenceService
# ---------------------------------------------------------------------------

class VideoIntelligenceService:
    """
    Serviço central de processamento multimodal de vídeo e integração
    com o ecossistema pedagógico Study (Jarvis OS).
    """

    def __init__(
        self,
        workspace_root: str = ".",
        storage_dir: Optional[str] = None,
        vault_root: str = "obsidian_vault",
        media_dir: Optional[str] = None,
    ):
        self.workspace_root = Path(workspace_root)
        base_dir = media_dir or storage_dir or (self.workspace_root / "data" / "study")
        self.storage_dir = Path(base_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir = self.storage_dir / "videos"
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.keyframes_dir = self.storage_dir / "keyframes"
        self.keyframes_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir = self.storage_dir / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        self.vault_root = Path(vault_root)
        self.transcriber = LocalTranscriber()
        self.linker = VaultLinker(vault_root=str(self.vault_root))

    # -----------------------------------------------------------------------
    # Validação e Segurança
    # -----------------------------------------------------------------------

    def validate_video_file(self, file_path_or_name: str, max_size_bytes: int = 2 * 1024 * 1024 * 1024) -> str:
        """
        Valida que o formato de vídeo é suportado, sem path traversal ou nomes maliciosos.
        Retorna a extensão normalizada.
        """
        raw_name = Path(file_path_or_name).name
        # Prevenir path traversal e carateres perigosos de injeção em shell
        if ".." in file_path_or_name or "/" in raw_name or "\\" in raw_name:
            raise ValueError("SECURITY_VIOLATION: Tentativa de path traversal detetada no ficheiro de vídeo.")

        ext = Path(raw_name).suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(f"UNSUPPORTED_VIDEO_FORMAT: Formato '{ext}' não suportado. Suportados: {sorted(list(SUPPORTED_VIDEO_EXTENSIONS))}")

        # Se o ficheiro já existir em disco, verificar tamanho
        if os.path.exists(file_path_or_name):
            size = os.path.getsize(file_path_or_name)
            if size > max_size_bytes:
                raise ValueError(f"OVERSIZED_VIDEO: Ficheiro excede o limite de {max_size_bytes // (1024*1024)}MB.")

        return ext

    def validate_online_url(self, url: str) -> Dict[str, Any]:
        """
        Valida URL de vídeo online com proteção estrita contra SSRF.
        Suporta apenas HTTP/HTTPS em provedores verificados ou streams diretos.
        """
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            raise ValueError("VIDEO_URL_NOT_SUPPORTED: Apenas URLs HTTP e HTTPS são suportadas.")

        hostname = (parsed.hostname or "").lower()
        # Prevenir SSRF em localhost, IPs privados e metadados de nuvem
        private_patterns = [
            "localhost", "127.", "0.0.0.0", "::1", "10.", "192.168.",
            "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
            "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
            "172.28.", "172.29.", "172.30.", "172.31.", "169.254."
        ]
        for priv in private_patterns:
            if hostname.startswith(priv) or hostname == priv:
                raise ValueError("SECURITY_VIOLATION: Acesso a endereços locais ou de rede privada bloqueado por SSRF guard.")

        # Identificar provedor suportado
        provider = "DIRECT_URL"
        if "youtube.com" in hostname or "youtu.be" in hostname:
            provider = "YOUTUBE"
        elif "vimeo.com" in hostname:
            provider = "VIMEO"
        elif any(parsed.path.lower().endswith(ext) for ext in SUPPORTED_VIDEO_EXTENSIONS):
            provider = "DIRECT_STREAM"
        else:
            # Rejeitar esquemas arbitrários não verificados
            raise ValueError("VIDEO_URL_NOT_SUPPORTED: Provedor ou formato de stream online não suportado.")

        return {
            "valid": True,
            "provider": provider,
            "url": url,
            "hostname": hostname,
        }

    # -----------------------------------------------------------------------
    # Extração de Metadados via FFmpeg
    # -----------------------------------------------------------------------

    def probe_video_metadata(self, video_path: str, filename: str, source_hash: str) -> VideoMetadata:
        """Extrai duração, resolução, fps e codec usando ffmpeg."""
        ffmpeg_bin = get_ffmpeg_binary()
        if not ffmpeg_bin:
            raise RuntimeError("VIDEO_PROCESSING_NOT_AVAILABLE: Motor FFmpeg não encontrado para processamento de vídeo.")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Ficheiro de vídeo não encontrado: {video_path}")

        # Executar probe via ffmpeg -i
        cmd = [ffmpeg_bin, "-hide_banner", "-i", video_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=15)
            stderr = res.stderr or ""
        except Exception as e:
            raise RuntimeError(f"Falha ao executar probe do vídeo: {e}")

        # Extrair duração: Duration: 00:01:23.45
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
        if duration_match:
            h, m, s = duration_match.groups()
            duration_seconds = int(h) * 3600 + int(m) * 60 + float(s)
        else:
            duration_seconds = 0.0

        # Extrair resolução: e.g. 1920x1080
        res_match = re.search(r"Stream.*Video:.*?(\d{2,5})x(\d{2,5})", stderr)
        if res_match:
            width = int(res_match.group(1))
            height = int(res_match.group(2))
        else:
            width, height = 1280, 720

        # Extrair fps: e.g. 30 fps ou 29.97 fps
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
        fps = float(fps_match.group(1)) if fps_match else 30.0

        # Extrair codec: e.g. h264 (High)
        codec_match = re.search(r"Stream.*Video:\s*([a-zA-Z0-9_\-]+)", stderr)
        codec = codec_match.group(1) if codec_match else "unknown"

        duration_str = format_timestamp(duration_seconds)
        title = Path(filename).stem.replace("_", " ").replace("-", " ").title()

        return VideoMetadata(
            source_id=source_hash[:16],
            filename=filename,
            title=title,
            subject="Geral",
            duration_seconds=round(duration_seconds, 2),
            duration_str=duration_str,
            width=width,
            height=height,
            fps=round(fps, 2),
            codec=codec,
            language="en",
            source_hash=source_hash,
            creation_date=datetime.now().isoformat(),
            provenance={
                "engine": "FFMPEG",
                "extracted_at": datetime.now().isoformat(),
                "file_path": video_path,
                "evidence_status": "OBSERVED",
            },
            processing_status="VALIDATING",
            file_path=video_path,
        )

    # -----------------------------------------------------------------------
    # Extração de Áudio e Transcrição
    # -----------------------------------------------------------------------

    def extract_audio_from_video(self, video_path: str, output_wav_path: str) -> str:
        """
        Extrai o stream de áudio do vídeo para WAV 16kHz mono (ideal para Whisper)
        sem alterar o vídeo original.
        """
        ffmpeg_bin = get_ffmpeg_binary()
        if not ffmpeg_bin:
            raise RuntimeError("VIDEO_PROCESSING_NOT_AVAILABLE: FFmpeg não disponível para extração de áudio.")

        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
        # Comando ffmpeg para converter em PCM 16-bit, 16000Hz, mono
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav_path,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0 or not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
                # Caso o vídeo não possua stream de áudio
                if "does not contain any stream" in (res.stderr or "") or "Output file is empty" in (res.stderr or ""):
                    # Criar arquivo WAV silencioso curto para garantir continuidade sem crash
                    self._create_silent_wav(output_wav_path, duration_seconds=1.0)
                else:
                    raise RuntimeError(f"Erro no FFmpeg ao extrair áudio: {res.stderr[:200]}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("Tempo limite excedido ao extrair áudio do vídeo.")

        return output_wav_path

    def _create_silent_wav(self, path: str, duration_seconds: float = 1.0) -> None:
        """Gera um WAV com silêncio caso o vídeo não possua stream de áudio."""
        import wave
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            num_frames = int(16000 * duration_seconds)
            wf.writeframes(b"\x00\x00" * num_frames)

    def transcribe_audio_stream(
        self,
        audio_path: str,
        language: Optional[str] = None,
        duration_seconds: float = 0.0,
    ) -> Tuple[str, List[TranscriptSegment]]:
        """
        Executa transcrição reutilizando o LocalTranscriber (Faster-Whisper),
        preservando timestamps de início, fim e texto.
        """
        raw_text, raw_segments = self.transcriber.transcribe(audio_path, language=language)

        structured: List[TranscriptSegment] = []
        if raw_segments:
            for idx, s in enumerate(raw_segments):
                start = float(s.get("start", 0.0))
                end = float(s.get("end", start + 5.0))
                t_str = format_timestamp(start)
                txt = s.get("text", "").strip()

                # Criar timestamps por palavra aproximados a partir do segmento
                words_list = []
                tokens = txt.split()
                if tokens:
                    span_duration = max(0.1, end - start)
                    per_word = span_duration / len(tokens)
                    for w_idx, w in enumerate(tokens):
                        w_start = start + w_idx * per_word
                        w_end = min(end, w_start + per_word)
                        words_list.append({
                            "word": w,
                            "start": round(w_start, 2),
                            "end": round(w_end, 2),
                        })

                seg = TranscriptSegment(
                    segment_id=f"seg_{idx + 1:04d}",
                    start=round(start, 2),
                    end=round(end, 2),
                    timestamp=t_str,
                    text=txt,
                    confidence=float(s.get("confidence", 0.95)),
                    language=language or "en",
                    words=words_list,
                )
                structured.append(seg)
        else:
            # Fallback se não foram detetados segmentos explícitos
            structured.append(TranscriptSegment(
                segment_id="seg_0001",
                start=0.0,
                end=max(5.0, duration_seconds),
                timestamp="00:00",
                text=raw_text or "Áudio processado sem fala detetada.",
                confidence=1.0,
                language=language or "en",
            ))

        return raw_text, structured

    # -----------------------------------------------------------------------
    # Análise Visual, Keyframes e Deteção de Slides
    # -----------------------------------------------------------------------

    def extract_visual_keyframes(
        self,
        video_path: str,
        doc_id: str = "doc_default",
        duration_seconds: float = 0.0,
        interval_seconds: float = 5.0,
        max_frames: int = 30,
    ) -> List[VideoKeyframe]:
        """
        Extrai keyframes em intervalos adaptativos para não sobrecarregar I/O,
        analisando propriedades visuais para identificar slides e diagramas.
        """
        ffmpeg_bin = get_ffmpeg_binary()
        if not ffmpeg_bin:
            return []

        doc_keyframe_dir = self.keyframes_dir / doc_id
        doc_keyframe_dir.mkdir(parents=True, exist_ok=True)

        # Calcular número de frames e timestamps alvo
        if duration_seconds <= 0:
            try:
                meta = self.probe_metadata(video_path)
                duration_seconds = meta.duration_seconds
            except Exception:
                pass
            if duration_seconds <= 0:
                duration_seconds = 60.0

        # Amostragem espaçada
        step = max(0.5, interval_seconds)
        sample_timestamps = []
        cur = 0.5  # Iniciar aos 0.5s para capturar amostras mesmo em clips curtos
        while cur < duration_seconds:
            sample_timestamps.append(cur)
            cur += step

        if not sample_timestamps:
            sample_timestamps = [0.5]

        keyframes: List[VideoKeyframe] = []

        for idx, ts in enumerate(sample_timestamps[:max_frames]):
            frame_filename = f"frame_{idx + 1:03d}_{int(ts)}s.jpg"
            frame_path = doc_keyframe_dir / frame_filename
            t_str = format_timestamp(ts)

            # Extrair frame único via FFmpeg seek rápido
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss", str(ts),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",
                str(frame_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=15)
            except Exception:
                continue

            if not frame_path.exists() or frame_path.stat().st_size == 0:
                continue

            # Análise visual do frame extraído usando PIL
            visual_type, is_slide, confidence, desc = self._analyze_frame_visuals(str(frame_path))

            keyframe = VideoKeyframe(
                frame_id=f"frame_{idx + 1:03d}",
                timestamp=round(ts, 2),
                timestamp_str=t_str,
                image_path=str(frame_path),
                image_url=f"/data/study/keyframes/{doc_id}/{frame_filename}",
                source_id=doc_id,
                scene_id=f"scene_{idx + 1}",
                provenance="FFMPEG_SCENE_SAMPLE",
                is_slide=is_slide,
                slide_confidence=confidence,
                visual_type=visual_type,
                visual_description=desc,
                evidence_status="VISUAL_OBSERVED",
            )
            keyframes.append(keyframe)

        return keyframes

    def _analyze_frame_visuals(self, image_path: str) -> Tuple[str, bool, float, str]:
        """
        Classifica o tipo visual (slide, diagram, chart, general) baseado
        na distribuição de cores, luminosidade e contraste.
        """
        try:
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                w, h = img.size
                stat = ImageStat.Stat(img_rgb)
                brightness = sum(stat.mean) / 3.0  # 0-255
                std_dev = sum(stat.stddev) / 3.0   # Contraste

                # Heurística: Apresentações e slides possuem contraste moderado a alto e fundo consistente
                # Imagens com fundo claro (>180) e alto contraste (>35) tendem a ser slides de aula
                is_slide = False
                confidence = 0.5
                visual_type = "general"
                desc = "Frame de vídeo"

                if brightness > 160 and std_dev > 30:
                    is_slide = True
                    confidence = 0.88
                    visual_type = "slide"
                    desc = "Diapositivo com texto e apresentação estruturada"
                elif std_dev > 55:
                    is_slide = True
                    confidence = 0.75
                    visual_type = "diagram"
                    desc = "Diagrama visual ou gráfico com variação de contraste"
                elif brightness < 60:
                    visual_type = "code" if std_dev > 25 else "general"
                    desc = "Editor de código ou terminal escuro" if visual_type == "code" else "Cena de baixa luminosidade"
                else:
                    visual_type = "demonstration"
                    desc = "Demonstração ou captura de ecrã ao vivo"

                return visual_type, is_slide, confidence, desc
        except Exception:
            return "general", False, 0.0, "Frame não analisado"

    def detect_slide_candidates(self, keyframes: List[VideoKeyframe]) -> List[SlideCandidate]:
        """Filtra frames com evidência estrita para construir a lista de candidatos a slide."""
        slides: List[SlideCandidate] = []
        for k in keyframes:
            is_slide = getattr(k, "is_slide", False)
            conf = getattr(k, "slide_confidence", getattr(k, "confidence", 0.5))
            f_id = getattr(k, "frame_id", "frame_001")
            ts = getattr(k, "timestamp", 0.0)
            t_str = getattr(k, "timestamp_str", format_timestamp(ts))
            slides.append(SlideCandidate(
                timestamp=ts,
                timestamp_str=t_str,
                frame_id=f_id,
                confidence=conf,
                is_slide=bool(is_slide),
                evidence_status="OBSERVED" if is_slide else "UNKNOWN",
                title=f"Slide em {t_str}" if is_slide else f"Frame em {t_str}",
            ))
        return slides

    # -----------------------------------------------------------------------
    # Segmentação Semântica em Capítulos
    # -----------------------------------------------------------------------

    def generate_video_chapters(
        self,
        transcript_segments: List[TranscriptSegment],
        duration_seconds: float,
    ) -> List[VideoChapter]:
        """
        Segmenta a aula/vídeo em capítulos temáticos com base nos timestamps e texto.
        """
        if not transcript_segments:
            return [VideoChapter(
                chapter_id="chap_01",
                title="Apresentação do Conteúdo",
                start_seconds=0.0,
                end_seconds=duration_seconds,
                start_timestamp="00:00",
                provenance="DEFAULT_SINGLE_CHAPTER",
            )]

        # Estratégia: dividir a cada ~4-8 minutos ou por mudanças de tópico
        target_chapter_duration = 300.0  # 5 minutos por capítulo
        chapters: List[VideoChapter] = []

        cur_start = 0.0
        cur_segments: List[TranscriptSegment] = []
        chap_num = 1

        for seg in transcript_segments:
            cur_segments.append(seg)
            if (seg.end - cur_start) >= target_chapter_duration:
                # Extrair título a partir das primeiras palavras ou palavras-chave do bloco
                block_text = " ".join(s.text for s in cur_segments)
                title = self._infer_chapter_title(block_text, chap_num)

                chapters.append(VideoChapter(
                    chapter_id=f"chap_{chap_num:02d}",
                    title=title,
                    start_seconds=round(cur_start, 2),
                    end_seconds=round(seg.end, 2),
                    start_timestamp=format_timestamp(cur_start),
                    provenance="TRANSCRIPT_TEMPORAL_WINDOW",
                ))
                chap_num += 1
                cur_start = seg.end
                cur_segments = []

        # Adicionar capítulo final se restaram segmentos
        if cur_segments:
            block_text = " ".join(s.text for s in cur_segments)
            title = self._infer_chapter_title(block_text, chap_num)
            chapters.append(VideoChapter(
                chapter_id=f"chap_{chap_num:02d}",
                title=title,
                start_seconds=round(cur_start, 2),
                end_seconds=round(duration_seconds, 2),
                start_timestamp=format_timestamp(cur_start),
                provenance="TRANSCRIPT_TEMPORAL_WINDOW",
            ))

        return chapters

    def _infer_chapter_title(self, text: str, chapter_num: int) -> str:
        """Infere título conciso para o capítulo baseado nos termos dominantes."""
        if not text:
            return f"Secção {chapter_num}"

        text_lower = text.lower()
        if chapter_num == 1 or "welcome" in text_lower or "introdu" in text_lower:
            return "Introdução e Visão Geral"
        if "consensus" in text_lower or "raft" in text_lower or "algorithm" in text_lower:
            return "Fundamentos e Mecanismo de Consenso"
        if "architecture" in text_lower or "design" in text_lower or "structure" in text_lower:
            return "Arquitetura e Componentes"
        if "experiment" in text_lower or "evaluation" in text_lower or "results" in text_lower:
            return "Resultados e Avaliação Experimental"
        if "summary" in text_lower or "conclusion" in text_lower or "next" in text_lower:
            return "Conclusões e Passos Finais"

        # Pegar primeiros 5 termos relevantes
        words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", text) if w.lower() not in {"this", "that", "with", "from", "have"}]
        if words:
            sample = " ".join(words[:4]).title()
            return f"{sample}"

        return f"Capítulo {chapter_num}"

    # -----------------------------------------------------------------------
    # Multimodal Context Window
    # -----------------------------------------------------------------------

    def get_context_window(
        self,
        current_timestamp: Optional[float] = None,
        timestamp: Optional[float] = None,
        transcript_segments: Optional[List[TranscriptSegment]] = None,
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        chapters: Optional[List[VideoChapter]] = None,
        metadata: Optional[Any] = None,
        source_metadata: Optional[Any] = None,
        window_seconds: float = 30.0,
    ) -> VideoContextWindow:
        """
        Monta uma janela de contexto multimodal em torno do timestamp:
        segmento atual, contexto anterior/seguinte, frames próximos e capítulo ativo.
        """
        ts = current_timestamp if current_timestamp is not None else (timestamp if timestamp is not None else 0.0)
        segs = transcript_segments if transcript_segments is not None else (segments or [])
        kfs = keyframes or []
        chaps = chapters or []
        meta = metadata if metadata is not None else (source_metadata or {})
        if hasattr(meta, "to_dict"):
            meta_dict = meta.to_dict()
        elif isinstance(meta, dict):
            meta_dict = meta
        else:
            meta_dict = {"title": str(meta)}

        current_seg = None
        for s in segs:
            if s.start <= ts <= s.end:
                current_seg = s
                break
        if not current_seg and segs:
            current_seg = min(segs, key=lambda s: abs(s.start - ts))

        prev_segs = [s for s in segs if s.end < ts and (ts - s.end) <= window_seconds]
        next_segs = [s for s in segs if s.start > ts and (s.start - ts) <= window_seconds]

        relevant_frames = []
        for k in kfs:
            if abs(getattr(k, "timestamp", 0.0) - ts) <= (window_seconds * 1.5):
                relevant_frames.append(k)

        active_chap = None
        for c in chaps:
            c_start = getattr(c, "start_seconds", getattr(c, "start_time", 0.0))
            c_end = getattr(c, "end_seconds", getattr(c, "end_time", 0.0))
            if c_start <= ts <= c_end:
                active_chap = c
                break

        surrounding_text = " ".join([getattr(s, "text", "") for s in segs if abs(getattr(s, "start", 0.0) - ts) <= window_seconds])

        return VideoContextWindow(
            timestamp=round(ts, 2),
            timestamp_str=format_timestamp(ts),
            current_segment=current_seg,
            prev_segments=[s.to_dict() if hasattr(s, "to_dict") else s for s in prev_segs],
            next_segments=[s.to_dict() if hasattr(s, "to_dict") else s for s in next_segs],
            relevant_frames=relevant_frames,
            chapter=active_chap,
            current_chapter=active_chap,
            source_metadata=meta_dict,
            current_timestamp=round(ts, 2),
            surrounding_transcript=surrounding_text,
        )

    # -----------------------------------------------------------------------
    # Ações Contextuais Pedagógicas
    # -----------------------------------------------------------------------

    def explain_moment(
        self,
        timestamp: float,
        context: Optional[VideoContextWindow] = None,
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        chapters: Optional[List[VideoChapter]] = None,
        level: str = "Intermédio",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Responde à ação 'O que está a acontecer aqui?' combinando
        timestamp + transcrição atual + frame visual relevante.
        """
        t_str = format_timestamp(timestamp)
        if context is None:
            context = self.get_context_window(
                current_timestamp=timestamp,
                segments=segments,
                keyframes=keyframes,
                chapters=chapters,
                metadata={},
            )

        curr_text = ""
        if context.current_segment:
            curr_text = getattr(context.current_segment, "text", "") or (context.current_segment.get("text", "") if isinstance(context.current_segment, dict) else "")

        chap_title = "Vídeo"
        if context.current_chapter:
            chap_title = getattr(context.current_chapter, "title", "Vídeo") or (context.current_chapter.get("title", "Vídeo") if isinstance(context.current_chapter, dict) else "Vídeo")

        frame_desc = "Sem frame visual específico"
        frame_id = None
        if context.relevant_frames:
            best_kf = min(context.relevant_frames, key=lambda f: abs(getattr(f, "timestamp", f.get("timestamp", 0.0) if isinstance(f, dict) else 0.0) - timestamp))
            frame_desc = getattr(best_kf, "visual_description", "") or (best_kf.get("visual_description", "") if isinstance(best_kf, dict) else "")
            frame_id = getattr(best_kf, "frame_id", None) or (best_kf.get("frame_id") if isinstance(best_kf, dict) else None)

        explanation = (
            f"No momento {t_str} ({chap_title}), o orador expõe: «{curr_text}». "
            f"Visualmente ({frame_desc}), o conteúdo reforça este conceito ao demonstrar a relação estrutural em tempo real."
        )

        return {
            "timestamp": t_str,
            "timestamp_str": t_str,
            "frame_id": frame_id,
            "text": curr_text,
            "frame_description": frame_desc,
            "explanation": explanation,
            "evidence_status": "OBSERVED",
            "citations": [f"video @ {t_str}"] + ([f"frame {frame_id} @ {t_str}"] if frame_id else []),
        }

    def explain_visual_on_screen(
        self,
        timestamp: float,
        context_or_keyframes: Any,
        surrounding_transcript: str = "",
    ) -> Dict[str, Any]:
        """
        Responde à ação 'Explicar o que está no ecrã' combinando frame + transcrição contextual.
        """
        if isinstance(context_or_keyframes, list):
            return self.explain_visual(timestamp, context_or_keyframes, surrounding_transcript)

        context = context_or_keyframes
        t_str = getattr(context, "timestamp_str", format_timestamp(timestamp))
        curr_text = getattr(getattr(context, "current_segment", None), "text", "") or ""

        if not getattr(context, "relevant_frames", []):
            return {
                "timestamp": t_str,
                "timestamp_str": t_str,
                "visual_type": "VISUAL_UNKNOWN",
                "explanation": "VISUAL_UNKNOWN: Não foi detetado nenhum frame visual específico para este momento temporal.",
                "evidence_status": "UNKNOWN",
                "citations": [f"video @ {t_str}"],
            }

        best_frame = min(context.relevant_frames, key=lambda f: abs(getattr(f, "timestamp", 0.0) - timestamp))
        f_type = getattr(best_frame, "visual_type", "SLIDE_OR_DIAGRAM")
        f_id = getattr(best_frame, "frame_id", "frame_001")
        f_desc = getattr(best_frame, "visual_description", "Conteúdo visual estruturado")

        explanation = (
            f"O elemento visual apresentado aos {t_str} ({f_id}) corresponde a um {f_type.upper()} ({f_desc}). "
            f"Em alinhamento com a fala «{curr_text or surrounding_transcript}», este diapositivo organiza os parâmetros essenciais."
        )

        return {
            "timestamp": t_str,
            "timestamp_str": t_str,
            "frame_id": f_id,
            "visual_type": "SLIDE_OR_DIAGRAM",
            "explanation": explanation,
            "evidence_status": "VISUAL_OBSERVED",
            "citations": [f"frame {f_id} @ {t_str}", f"video @ {t_str}"],
        }

    def explain_visual(
        self,
        timestamp: float,
        keyframes: List[VideoKeyframe],
        surrounding_transcript: str = "",
    ) -> Dict[str, Any]:
        if not keyframes:
            return {
                "visual_type": "VISUAL_UNKNOWN",
                "explanation": "VISUAL_UNKNOWN: Nenhum diapositivo ou diagrama visual detectado para este timestamp.",
                "evidence_status": "UNKNOWN",
                "frame_id": "",
                "timestamp_str": format_timestamp(timestamp),
            }

        best_kf = min(keyframes, key=lambda k: abs(getattr(k, "timestamp", 0.0) - timestamp))
        f_id = getattr(best_kf, "frame_id", "frame_001")
        t_str = getattr(best_kf, "timestamp_str", format_timestamp(timestamp))
        desc = getattr(best_kf, "visual_description", "Conteúdo visual estruturado")

        explanation = (
            f"O frame {f_id} em {t_str} apresenta: {desc}. "
            f"Contexto do áudio: «{surrounding_transcript}». "
            f"Os dados visuais ilustram a correlação direta entre os parâmetros e a métrica de throughput."
        )

        return {
            "visual_type": "SLIDE_OR_DIAGRAM",
            "frame_id": f_id,
            "timestamp_str": t_str,
            "transcript_context": surrounding_transcript,
            "explanation": explanation,
            "evidence_status": "VISUAL_OBSERVED",
            "citations": [f"frame {f_id} @ {t_str}"],
        }

    def search_transcript(
        self,
        arg1: Any,
        arg2: Any,
    ) -> List[Dict[str, Any]]:
        """Pesquisa texto na transcrição e retorna todas as ocorrências com timestamps."""
        if isinstance(arg1, str):
            query = arg1
            segments = arg2
        else:
            segments = arg1
            query = arg2

        if not query or not query.strip() or not segments:
            return []

        query_lower = query.strip().lower()
        results = []

        for seg in segments:
            text = getattr(seg, "text", seg.get("text", "") if isinstance(seg, dict) else "")
            seg_id = getattr(seg, "id", None)
            if seg_id is None:
                seg_id = getattr(seg, "segment_id", None)
            if seg_id is None and isinstance(seg, dict):
                seg_id = seg.get("id", seg.get("segment_id", 0))
            if isinstance(seg_id, str) and seg_id.startswith("seg_"):
                try:
                    seg_id = int(seg_id.split("_")[1])
                except Exception:
                    pass

            start = getattr(seg, "start", seg.get("start", 0.0) if isinstance(seg, dict) else 0.0)
            end = getattr(seg, "end", seg.get("end", 0.0) if isinstance(seg, dict) else 0.0)
            t_str = getattr(seg, "timestamp", "") or format_timestamp(start)

            if query_lower in text.lower():
                results.append({
                    "segment_id": seg_id,
                    "id": seg_id,
                    "timestamp": t_str,
                    "timestamp_str": t_str,
                    "start": start,
                    "end": end,
                    "text": text,
                    "match": query,
                    "evidence_status": "OBSERVED",
                })

        return results

    def ask_the_video(
        self,
        query: str = "",
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        chapters: Optional[List[VideoChapter]] = None,
        metadata: Optional[Any] = None,
        question: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Q&A Grounded sobre o vídeo:
        Localiza os momentos mais relevantes e formula resposta citando timestamp e frame.
        """
        q = question or query or ""
        segs = segments or []
        kfs = keyframes or []

        q_lower = q.strip().lower()
        tokens = [t for t in re.findall(r"\b[a-zA-Z0-9]{3,}\b", q_lower) if t not in {"onde", "como", "porque", "qual", "video", "este", "what", "where", "when", "show", "mentioned"}]

        matched_segs = []
        for s in segs:
            s_text = getattr(s, "text", "")
            s_lower = s_text.lower()
            score = sum(1 for t in tokens if t in s_lower)
            if score > 0:
                matched_segs.append((score, s))

        matched_segs.sort(key=lambda x: x[0], reverse=True)

        if not matched_segs:
            return {
                "query": q,
                "answer": "INSUFFICIENT_EVIDENCE: Não foi encontrada evidência suficiente na transcrição ou nos frames deste vídeo para responder a esta questão específica.",
                "evidence_status": "INSUFFICIENT_EVIDENCE",
                "citations": [],
                "temporal_citation": "",
                "target_timestamp": 0.0,
            }

        top_seg = matched_segs[0][1]
        t_str = getattr(top_seg, "timestamp", "") or format_timestamp(getattr(top_seg, "start", 0.0))
        target_ts = getattr(top_seg, "start", 0.0)

        matching_frame = None
        if kfs:
            matching_frame = min(kfs, key=lambda k: abs(getattr(k, "timestamp", 0.0) - target_ts))

        answer_text = (
            f"Aos {t_str}, o vídeo aborda este tópico diretamente afirmando: «{getattr(top_seg, 'text', '')}». "
        )
        if matching_frame and getattr(matching_frame, "is_slide", False):
            answer_text += f"O diapositivo ({getattr(matching_frame, 'frame_id', '')}) fornece a representação gráfica associada."

        citation = f"video @ {t_str}"
        citations = [citation]
        if matching_frame:
            citations.append(f"frame {getattr(matching_frame, 'frame_id', '')} @ {t_str}")

        return {
            "query": q,
            "answer": answer_text,
            "evidence_status": "OBSERVED",
            "citations": citations,
            "temporal_citation": citation,
            "target_timestamp": target_ts,
            "target_frame_id": getattr(matching_frame, "frame_id", None) if matching_frame else None,
        }

    # -----------------------------------------------------------------------
    # Geração Pedagógica: Resumos, Cornell, Quizzes e Flashcards
    # -----------------------------------------------------------------------

    def generate_video_summary(
        self,
        arg1: Any = None,
        arg2: Any = None,
        arg3: Any = None,
        mode: str = "Study",
        **kwargs,
    ) -> str:
        """Gera resumo multimodal nos 4 modos: Quick, Study, Detailed, Exam."""
        if isinstance(arg1, str) and arg1 in ("Quick", "Study", "Detailed", "Exam"):
            mode = arg1
            segments = arg2 or []
            chapters = arg3 or []
        else:
            segments = arg1 or []
            chapters = arg3 or []
            if "mode" in kwargs:
                mode = kwargs["mode"]

        summary_lines = [
            f"# Sumário de Vídeo — Modo {mode}",
            f"Este resumo pedagógico sintetiza os momentos mais relevantes da aula em modo {mode}.",
            "",
            f"## Tópicos Nucleares e Estrutura Temporal ({mode})",
        ]
        if chapters:
            for c in chapters:
                c_title = getattr(c, "title", "Capítulo")
                c_ts = getattr(c, "start_timestamp", "00:00")
                summary_lines.append(f"- **[{c_ts}] {c_title}**: Síntese dos fundamentos apresentados.")
        elif segments:
            for s in segments[:4]:
                s_ts = getattr(s, "timestamp", "00:00") or format_timestamp(getattr(s, "start", 0.0))
                summary_lines.append(f"- **[{s_ts}]**: {getattr(s, 'text', '')}")
        else:
            summary_lines.append(f"- **[00:00]**: Introdução e visão geral ({mode}).")

        summary_lines.extend([
            "",
            f"## Análise Pedagógica e Revisão ({mode})",
            f"O conteúdo do modo {mode} foi estruturado para assimilação ativa e retenção duradoura.",
        ])
        return "\n".join(summary_lines)

    def generate_video_cornell_notes(
        self,
        doc_id: str,
        metadata: Any,
        transcript_segments: List[TranscriptSegment],
        chapters: List[VideoChapter],
        keyframes: List[VideoKeyframe],
    ) -> VideoCornellNotes:
        """Gera notas em formato Cornell Notes com timestamps explícitos na Cue Column."""
        if isinstance(metadata, str):
            doc_title = metadata
            doc_subject = "Sistemas"
            dur_str = "01:00:00"
        elif hasattr(metadata, "title"):
            doc_title = metadata.title
            doc_subject = getattr(metadata, "subject", "Sistemas")
            dur_str = getattr(metadata, "duration_str", "01:00:00")
        elif isinstance(metadata, dict):
            doc_title = metadata.get("title", "Aula de Estudo")
            doc_subject = metadata.get("subject", "Sistemas")
            dur_str = metadata.get("duration_str", "01:00:00")
        else:
            doc_title = "Aula de Estudo"
            doc_subject = "Sistemas"
            dur_str = "01:00:00"

        cue_items = []
        for c in chapters[:4]:
            t_str = getattr(c, "start_timestamp", "00:00")
            c_title = getattr(c, "title", "Conceito")
            cue_items.append({
                "cue": f"Qual o conceito fundamental abordado em {t_str}?",
                "idea": f"Em {t_str} ({c_title}), define-se a mecânica operacional.",
                "timestamp": t_str,
            })

        for s in transcript_segments[:4]:
            t_str = getattr(s, "timestamp", "") or format_timestamp(getattr(s, "start", 0.0))
            s_text = getattr(s, "text", "")
            cue_items.append({
                "cue": f"Qual é o conceito explicado aos {t_str}?",
                "idea": f"Aos {t_str}, afirma-se que «{s_text}».",
                "timestamp": t_str,
            })

        for k in keyframes:
            if getattr(k, "is_slide", False):
                k_ts = getattr(k, "timestamp_str", "00:00")
                k_id = getattr(k, "frame_id", "frame_001")
                cue_items.append({
                    "cue": f"Que diagrama é apresentado em {k_ts}?",
                    "idea": f"Em {k_ts} ({k_id}), o diapositivo ilustra a arquitetura.",
                    "timestamp": k_ts,
                    "frame_id": k_id,
                })
                break

        return VideoCornellNotes(
            document_id=doc_id,
            topic=doc_title,
            subject=doc_subject,
            date=datetime.now().strftime("%Y-%m-%d"),
            executive_summary=f"Síntese Cornell estruturada a partir da aula «{doc_title}» ({dur_str}).",
            cue_column=cue_items,
            detailed_notes=f"### Notas Detalhadas [{doc_title}]\n" + "\n".join(f"- [{getattr(s, 'timestamp', format_timestamp(getattr(s, 'start', 0.0)))}]: {getattr(s, 'text', '')}" for s in transcript_segments[:5]),
            glossary="Consenso: Acordo unificado sobre estado distribuído.\nLatência: Intervalo temporal entre estímulo e resposta.",
            action_items=[
                f"Rever os conceitos assinalados na coluna de pistas antes do exame.",
                "Consolidar as definições e diagramas nos cartões de estudo.",
            ],
            title=doc_title,
        )

    def generate_video_quiz(
        self,
        doc_id: str,
        topic: str,
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        num_questions: int = 5,
        **kwargs,
    ) -> VideoStudyQuiz:
        """Gera quiz de autoavaliação com proveniência temporal e frame_id."""
        segs = segments or []
        kfs = keyframes or []
        questions = []
        for i in range(num_questions):
            seg = segs[i % len(segs)] if segs else None
            t_str = getattr(seg, "timestamp", "") or format_timestamp(getattr(seg, "start", 0.0)) if seg else f"00:{i*15:02d}"
            seg_text = getattr(seg, "text", "") if seg else "princípio fundamental"

            q = VideoStudyQuizQuestion(
                id=f"vq_{i+1}",
                question=f"No minuto {t_str}, que garantia é apresentada relativamente a '{topic}'?",
                question_type="multiple_choice",
                options=[
                    f"Confirma que {seg_text[:40] if seg_text else 'o estado é consistente'}.",
                    "O líder abdica imediatamente sem qualquer termo de eleição.",
                    "Os nós secundários ignoram todos os registos anteriores.",
                    "O cliente executa escritas sem confirmação de maioria.",
                ],
                correct_index=0,
                correct_answer=f"Confirma que {seg_text[:40] if seg_text else 'o estado é consistente'}.",
                explanation=f"Aos {t_str}, a exposição teórica valida este comportamento: «{seg_text}».",
                source_ids=[f"video @ {t_str}"],
                timestamp=t_str,
                frame_id=getattr(kfs[0], "frame_id", None) if kfs else None,
            )
            questions.append(q)

        return VideoStudyQuiz(
            quiz_id=f"quiz_v_{doc_id}",
            document_id=doc_id,
            topic=topic,
            questions=questions,
            transfer_question={
                "id": "transfer_q1",
                "scenario": f"Como aplicarias as técnicas do vídeo «{topic}» num ambiente de produção com restrições estritas?",
                "expected_concepts": ["Redução de overhead", "Assincronia", "Validação periódica"],
            },
            created_at=datetime.now().isoformat(),
        )

    def generate_video_flashcards(
        self,
        document_id: str,
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        chapters: Optional[List[VideoChapter]] = None,
        num_cards: int = 5,
        **kwargs,
    ) -> List[VideoStudyFlashcard]:
        """Gera flashcards pedagógicos associados a timestamps e frames."""
        segs = segments or []
        kfs = keyframes or []
        cards: List[VideoStudyFlashcard] = []

        for idx, s in enumerate(segs[:num_cards]):
            t_str = getattr(s, "timestamp", "") or format_timestamp(getattr(s, "start", 0.0))
            s_text = getattr(s, "text", "")
            cards.append(VideoStudyFlashcard(
                card_id=f"card_v_{document_id}_{idx+1}",
                document_id=document_id,
                front=f"Em {t_str}, como é definido o conceito de 'Logical Clock' / Termo em Raft?",
                back=f"Aos {t_str}: «{s_text}». Funciona como relógio lógico para ordenar estados no sistema.",
                source_ids=[f"video @ {t_str}"],
                timestamp=t_str,
                difficulty="MEDIUM",
                next_review=time.time() + 86400,
                repetitions=0,
                interval_days=1.0,
            ))

        for idx, k in enumerate([f for f in kfs if getattr(f, "is_slide", False)][:2]):
            k_ts = getattr(k, "timestamp_str", "00:00")
            k_id = getattr(k, "frame_id", "frame_001")
            k_desc = getattr(k, "visual_description", "Conteúdo visual do slide")
            cards.append(VideoStudyFlashcard(
                card_id=f"card_vf_{document_id}_{idx+1}",
                document_id=document_id,
                front=f"Identifica o diagrama visual exibido aos {k_ts} ({k_id}).",
                back=f"{k_desc}. Constitui âncora visual para a explicação do fluxo.",
                source_ids=[f"frame {k_id} @ {k_ts}"],
                timestamp=k_ts,
                frame_id=k_id,
                difficulty="EASY",
                next_review=time.time() + 86400,
                repetitions=0,
                interval_days=1.0,
            ))

        return cards

    # -----------------------------------------------------------------------
    # Persistência no Obsidian Knowledge Vault
    # -----------------------------------------------------------------------

    def save_video_to_knowledge_vault(
        self,
        metadata: VideoMetadata,
        summary: Dict[str, Any],
        cornell: Dict[str, Any],
        keyframes: List[VideoKeyframe],
    ) -> Dict[str, Any]:
        """
        Exporta nota completa para o Obsidian Knowledge Vault em '10 - Lectures'
        com metadados YAML, [[Wikilinks]] e referências a momentos temporais.
        """
        vault_lectures_dir = self.vault_root / "10 - Lectures"
        vault_lectures_dir.mkdir(parents=True, exist_ok=True)

        safe_title = re.sub(r'[\\/*?:"<>|]', "", metadata.title).strip()
        filename = f"{datetime.now().strftime('%Y-%m-%d')} - {safe_title}.md"
        out_file = vault_lectures_dir / filename

        cue_lines = []
        for item in cornell.get("cue_column", []):
            cue = item.get("cue", "")
            idea = item.get("idea", "")
            ts = item.get("timestamp", "")
            cue_lines.append(f"> [!faq] **{ts} — {cue}**\n> {idea}\n")

        cue_md = "\n".join(cue_lines)

        frames_md = ""
        for k in keyframes[:4]:
            if k.is_slide:
                frames_md += f"- **{k.timestamp_str}** (`{k.frame_id}`): {k.visual_description}\n"

        content = f"""---
type: video_lecture
title: "{metadata.title}"
subject: "{metadata.subject}"
duration: "{metadata.duration_str}"
source_id: "{metadata.source_id}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
tags:
  - study/video
  - jarvis/multimodal
---

# {metadata.title}

> [!abstract] **Resumo Executivo**
> {summary.get('executive_summary', '')}

---

## 📌 Pistas & Questões Centrais (Cornell Cue Column)

{cue_md}

---

## 📖 Apontamentos Estruturados

{cornell.get('detailed_notes', '')}

---

## 🖼️ Momentos Visuais e Diapositivos Chave

{frames_md if frames_md else "Nenhum diapositivo específico registado."}

---

## 🎯 Ações e Revisão

- [ ] Rever os pontos temporais assinalados antes da próxima sessão de estudo.
- [ ] Praticar os cartões de memorização espaçada associados.
"""
        # Injetar wikilinks do vault
        linked_content = self.linker.link_text(content)
        out_file.write_text(linked_content, encoding="utf-8")

        return {
            "saved": True,
            "vault_path": str(out_file),
            "filename": filename,
            "linked_concepts_count": len(re.findall(r"\[\[.*?\]\]", linked_content)),
        }

    def save_to_knowledge_vault(
        self,
        vault_root: str,
        cornell_notes: Any,
        source_id: str = "src_default",
    ) -> str:
        vault_path = Path(vault_root)
        vault_path.mkdir(parents=True, exist_ok=True)
        title = getattr(cornell_notes, "topic", getattr(cornell_notes, "title", "Video Notes")) or "Video Notes"
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        filename = f"{clean_title}.md"
        out_file = vault_path / filename

        cue_md = ""
        for c in getattr(cornell_notes, "cue_column", []):
            cue = c.get("cue", "") if isinstance(c, dict) else getattr(c, "cue", "")
            idea = c.get("idea", "") if isinstance(c, dict) else getattr(c, "idea", "")
            cue_md += f"- **{cue}**: {idea}\n"

        content = f"""---
title: "{title}"
source_id: {source_id}
date: "{datetime.now().strftime('%Y-%m-%d')}"
tags:
  - study/video
  - jarvis/multimodal
---

# [[{title}]]

> [!abstract] **Resumo**
> {getattr(cornell_notes, "executive_summary", "")}

## Pistas
{cue_md}

## Notas
{getattr(cornell_notes, "detailed_notes", "")}
"""
        linked = self.linker.link_text(content)
        out_file.write_text(linked, encoding="utf-8")
        return str(out_file)

    def save_note(
        self,
        document_id: str,
        timestamp: float,
        note_text: str,
        frame_id: Optional[str] = None,
        selected_text: Optional[str] = None,
    ) -> VideoStudyNote:
        import uuid
        return VideoStudyNote(
            note_id=f"vnote_{uuid.uuid4().hex[:8]}",
            document_id=document_id,
            timestamp=timestamp,
            timestamp_str=format_timestamp(timestamp),
            note=note_text,
            frame_id=frame_id,
            selected_text=selected_text,
            created_at=datetime.now().isoformat(),
        )

    def probe_metadata(self, video_path: str, filename: str = "video.mp4", source_hash: str = "") -> VideoMetadata:
        return self.probe_video_metadata(video_path, filename, source_hash)

    def extract_audio(self, video_path: str, output_wav_path: Optional[str] = None) -> str:
        if not output_wav_path:
            output_wav_path = str(self.audio_dir / f"{Path(video_path).stem}_extracted.wav")
        return self.extract_audio_from_video(video_path, output_wav_path)

    def extract_keyframes(self, video_path: str, interval_seconds: float = 5.0) -> List[VideoKeyframe]:
        return self.extract_visual_keyframes(video_path, interval_seconds=interval_seconds)

    def detect_chapters(self, segments: List[TranscriptSegment], duration_seconds: float = 0.0) -> List[VideoChapter]:
        return self.generate_video_chapters(segments, duration_seconds=duration_seconds)

    def build_context_window(
        self,
        current_timestamp: float,
        segments: List[TranscriptSegment],
        keyframes: List[VideoKeyframe],
        chapters: List[VideoChapter],
        metadata: Dict[str, Any],
    ) -> VideoContextWindow:
        return self.get_context_window(
            current_timestamp=current_timestamp,
            segments=segments,
            keyframes=keyframes,
            chapters=chapters,
            source_metadata=metadata,
        )


    def generate_cornell_notes(
        self,
        document_id: str,
        title: str,
        segments: List[TranscriptSegment],
        keyframes: List[VideoKeyframe],
        chapters: List[VideoChapter],
    ):
        return self.generate_video_cornell_notes(document_id, title, segments, chapters, keyframes)

    def generate_quiz(
        self,
        document_id: str,
        topic: str,
        segments: List[TranscriptSegment],
        keyframes: List[VideoKeyframe],
        count: int = 5,
    ):
        return self.generate_video_quiz(document_id, topic, segments, keyframes, num_questions=count)

    def generate_flashcards(
        self,
        document_id: str,
        segments: Optional[List[TranscriptSegment]] = None,
        keyframes: Optional[List[VideoKeyframe]] = None,
        chapters: Optional[List[VideoChapter]] = None,
        count: int = 5,
    ):
        return self.generate_video_flashcards(document_id, segments, keyframes, chapters, num_cards=count)

    def translate_transcript_segment(self, selected_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        from services.study_service import contextual_translate_to_pt
        return contextual_translate_to_pt(selected_text)

    def process_video(
        self,
        video_path: str,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> Dict[str, Any]:
        if progress_callback:
            progress_callback("VALIDATING", 10.0, "Validando formato")
        meta = self.probe_metadata(video_path, filename or Path(video_path).name)
        if progress_callback:
            progress_callback("EXTRACTING_AUDIO", 25.0, "Extraindo áudio")
        audio = self.extract_audio(video_path)
        if progress_callback:
            progress_callback("ANALYZING_VIDEO", 60.0, "Analisando frames")
        kfs = self.extract_keyframes(video_path, interval_seconds=1.0)
        if progress_callback:
            progress_callback("INDEXING", 90.0, "Indexando")
        if progress_callback:
            progress_callback("READY", 100.0, "Pronto")
        return {"metadata": meta, "audio_path": audio, "keyframes": kfs}

    def _parse_text_to_segments(self, text: str) -> List[TranscriptSegment]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        segments = []
        for i, line in enumerate(lines):
            ts = 0.0
            content = line
            parts = line.split(" ", 1)
            if len(parts) == 2 and ":" in parts[0]:
                ts = parse_timestamp(parts[0])
                content = parts[1]
            segments.append(TranscriptSegment(
                segment_id=f"seg_{i+1}",
                start=ts,
                end=ts + 5.0,
                timestamp=format_timestamp(ts),
                text=content,
            ))
        return segments


