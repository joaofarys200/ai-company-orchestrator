---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: advanced
tags:
  - jarvis
  - voice-service
  - audio-streaming
  - webrtc-vad
  - stt
  - tts
prerequisites:
  - "[[FastAPI and WebSocket Lifecycle Management]]"
related:
  - "[[JARVIS Gemini Live Multimodal WebSocket Protocol]]"
  - "[[JARVIS Component Architecture]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - voice_service.py
    type: JARVIS_INTERNAL
    url: internal://voice_service.py
---

# 🎙️ JARVIS Voice Service and Audio Streaming Architecture

## 1. Purpose
O `VoiceService` implementa a camada de processamento de áudio local do JARVIS OS, fornecendo deteção contínua de atividade de voz (VAD via WebRTC), transcrição de fala para texto (STT local com Whisper) e síntese de voz (TTS) para interação mãos-livres com o utilizador.

---

## 2. Responsibilities
- Capturar fluxo contínuo de áudio do microfone em blocos de 30ms (480 amostras a 16kHz em formato PCM int16).
- Filtrar ruído de fundo e detetar início e fim de fala com `webrtcvad.Vad(mode=sensitivity)`.
- Gerir buffers de pré-fala (300ms) e pós-fala (600ms) para evitar cortes no início e no final das frases.
- Executar inferência local de STT usando modelos quantizados do Whisper (`tiny`, `base` ou `small`).
- Disparar callbacks assíncronos (`on_speech_start`, `on_speech_end`, `on_transcribing`, `on_transcription`).

---

## 3. Inputs & Outputs
- **Inputs**: Fluxo contínuo de áudio PCM mono (16000Hz, 16-bit) via `sounddevice.InputStream`.
- **Outputs**: Strings de texto transcritas emitidas para o despachante de comandos e telemetria WebSocket.

---

## 4. State Management & Invariants
- `VoiceService` mantém internamente uma fila `audio_queue` thread-safe.
- A flag `self.is_recording` é atomicamente alternada para evitar processamento concorrente de transcrições sobrepostas.

---

## 5. Dependencies
- [`voice_service.py`](file:///c:/Users/joaor/Desktop/JarvisOS/voice_service.py)
- Bibliotecas: `webrtcvad`, `sounddevice`, `numpy`, `faster-whisper`, `edge-tts` / `pyttsx3`.

---

## 6. Execution Flow
```
[ Microfone: sounddevice ] -> Bloco PCM (30ms / 480 bytes) -> [ WebRTC VAD ]
                                                                     |
                     +-----------------------------------------------+
                     | (Voz Detectada: Fala Iniciou)
                     v
             [ Acumulador de Ring Buffer ]
                     | (Silêncio > 600ms: Fala Concluiu)
                     v
             [ Worker Thread: Whisper Transcribe ]
                     |
                     v
             [ Callback: on_transcription(text) ] -> [ Despachante JARVIS ]
```

---

## 7. Failure Modes & Recovery
- **Failure**: Dispositivo de áudio desconectado ou taxa de amostragem incompatível.
- **Recovery**: Captura de exceção em `sd.InputStream`, log com fallback para índice de dispositivo padrão `VOICE_DEVICE_INDEX`.

---

## 8. Security Boundaries
- O áudio bruto permanece em memória volátil e é descartado imediatamente após a transcrição, sem gravação não-autorizada em disco.

---

## 9. Evidence Produced & Tests
- **Evidence**: Eventos de telemetria `VOICE_INPUT_DETECTED` no log.
- **Tests**: `tests/test_voice_service.py`.

---

## 10. Configuration & Performance Constraints
- `VOICE_VAD_SENSITIVITY`: Valor de 0 a 3 (padrão 3 para rejeição estrita de ruído).
- `VOICE_SAMPLE_RATE`: Fixo em 16000 Hz.
- Latência de transcrição alvo: $< 350\text{ms}$ para modelo `tiny.en` em CPU.

---

## 11. Related Components
- [[JARVIS Gemini Live Multimodal WebSocket Protocol]]
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]]
- [[JARVIS Component Architecture]]
