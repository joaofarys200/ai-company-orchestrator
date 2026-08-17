---
type: concept
domain: jarvis
status: knowledge_gap
source_type: UNVERIFIED
confidence: low
freshness: evolving
difficulty: advanced
tags:
  - knowledge-gap
  - jarvis
  - webrtc
  - audio-latency
  - hardware
prerequisites:
  - "[[JARVIS Voice Service and Audio Streaming Architecture]]"
related:
  - "[[JARVIS Gemini Live Multimodal WebSocket Protocol]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[How to Detect and Break Agent Infinite Loops]]"
implementation:
  - "[[JARVIS Voice Service and Audio Streaming Architecture]]"
sources:
  - title: WebRTC Audio Processing Latency Standards (IETF)
    type: PRIMARY_SOURCE
    url: https://webrtc.org/
---

# â“ Gap - Real-Time WebRTC Audio Latency Bounds in Local Hardware

## Question
*Quais sÃ£o os limites mÃ­nimos teÃ³ricos e prÃ¡ticos de latÃªncia ponta a ponta (Glass-to-Ear / Mic-to-Speaker) alcanÃ§Ã¡veis em hardware local de consumo para conversaÃ§Ã£o contÃ­nua por voz sem buffers de streaming audÃ­veis?*

---

## Why It Matters
A percepÃ§Ã£o humana de conversa natural degrada quando a latÃªncia de resposta ultrapassa $300\text{ms}$. Para o JARVIS agir como um par de programaÃ§Ã£o verdadeiramente fluido via voz, os tempos de captura, VAD, STT, inferÃªncia e TTS devem ser otimizados conjuntamente.

---

## What Is Known
- O processamento de VAD via WebRTC opera em blocos de $30\text{ms}$ ($480\text{ amostras}$ a $16\text{kHz}$).
- O Whisper `tiny` local requer cerca de $120 - 250\text{ms}$ em CPU moderna para frases curtas.

---

## What Is Unknown
- A variaÃ§Ã£o de jitter introduzida pelos drivers WASAPI / ALSA em diferentes interfaces de Ã¡udio USB.
- O impacto do escalonamento de frequÃªncia de clock da GPU durante a alternÃ¢ncia rÃ¡pida entre STT e inferÃªncia de LLM.

---

## Evidence Required
Benchmarks empÃ­ricos gravados em hardware real medindo o tempo exato com osciloscÃ³pio ou loopback de Ã¡udio calibrado entre a Ãºltima palavra falada pelo humano e o primeiro frame de Ã¡udio emitido pelo TTS.

---

## Potential Sources
- EspecificaÃ§Ãµes IETF WebRTC Data Channels and Audio Processing.
- DocumentaÃ§Ã£o da biblioteca `sounddevice` e do backend PortAudio.

---

## Implementation Status
`status: "knowledge_gap"` (Pesquisa em andamento; suporte experimental no `voice_service.py`).

---

## Priority
`P2 (MÃ©dio-Alto)`

