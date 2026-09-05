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
*Quais são os limites mínimos teóricos e práticos de latência ponta a ponta (Glass-to-Ear / Mic-to-Speaker) alcançáveis em hardware local de consumo para conversação contínua por voz sem buffers de streaming audíveis?*

---

## Why It Matters
A percepção humana de conversa natural degrada quando a latência de resposta ultrapassa $300\text{ms}$. Para o JARVIS agir como um par de programação verdadeiramente fluido via voz, os tempos de captura, VAD, STT, inferência e TTS devem ser otimizados conjuntamente.

---

## What Is Known
- O processamento de VAD via WebRTC opera em blocos de $30\text{ms}$ ($480\text{ amostras}$ a $16\text{kHz}$).
- O Whisper `tiny` local requer cerca de $120 - 250\text{ms}$ em CPU moderna para frases curtas.

---

## What Is Unknown
- A variação de jitter introduzida pelos drivers WASAPI / ALSA em diferentes interfaces de áudio USB.
- O impacto do escalonamento de frequência de clock da GPU durante a alternância rápida entre STT e inferência de LLM.

---

## Evidence Required
Benchmarks empíricos gravados em hardware real medindo o tempo exato com osciloscópio ou loopback de áudio calibrado entre a última palavra falada pelo humano e o primeiro frame de áudio emitido pelo TTS.

---

## Potential Sources
- Especificações IETF WebRTC Data Channels and Audio Processing.
- Documentação da biblioteca `sounddevice` e do backend PortAudio.

---

## Implementation Status
`status: "knowledge_gap"` (Pesquisa em andamento; suporte experimental no `voice_service.py`).

---

## Priority
`P2 (Médio-Alto)`

