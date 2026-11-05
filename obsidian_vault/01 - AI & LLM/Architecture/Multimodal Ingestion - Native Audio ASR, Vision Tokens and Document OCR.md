---
type: concept
domain: ai-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - ai-engineering
  - multimodal
  - asr
  - whisper
  - ocr
  - vision-language
---

# 🎙️ Multimodal Ingestion - Native Audio ASR, Vision Tokens and Document OCR

## 1. Arquitetura de Ingestão Multimodal Fundamentada
Pipelines multimodais de produção convertem sinais contínuos heterogéneos (áudio, vídeo, slides, PDFs digitalizados) numa representação textual e temporal ancorada em evidências, evitando qualquer geração especulativa quando um canal está silencioso ou ilegível.

1. **Canal Acústico (ASR / Audio Encoders)**:
   - O áudio é reamostrado para PCM linear `16 kHz` mono (`s16le`) via `ffmpeg`.
   - Antes da inferência, calcula-se a energia **RMS** (*Root Mean Square*):
     $$\text{RMS} = \sqrt{\frac{1}{N}\sum_{i=1}^{N} x_i^2}$$
     Se $\text{RMS} < \tau_{\text{silence}}$, o ficheiro é classificado deterministicamente como `SILENT_AUDIO`, prevenindo alucinações típicas de modelos encoder-decoder (ex.: frases fantasma do Whisper em silêncio).
   - Segmentos longos são processados com VAD (*Voice Activity Detection*) ou janelas temporais `[t_start, t_end]` preservando timestamps ao segundo.
2. **Canal Visual (Keyframes, ViT Patches & OCR Nativo)**:
   - Em vídeos de aulas/apresentações, grande parte da densidade técnica reside nos slides projetados e não na fala.
   - A amostragem de keyframes combinada com **OCR nativo local** (ex.: `Windows.Media.Ocr` / Tesseract / VLM tiling) extrai texto visual, aplicando desduplicação por similaridade de Jaccard entre fotogramas consecutivos ($J(A,B) = \frac{|A \cap B|}{|A \cup B|} > 0.72$).

---

## 2. Matriz de Decisão: OCR Dedicado vs Vision-Language Model (VLM)

| Critério | OCR Local (WinRT / PaddleOCR) | VLM Nativo (ViT Tokens) | Abordagem Híbrida Recomendada |
|---|---|---|---|
| **Custo & Latência** | Sub-100ms/frame em CPU, custo zero | $256\text{–}1500+$ tokens visuais/imagem | OCR local em todos os frames + VLM só em diagramas |
| **Fidelidade Lexical** | Alta para texto tipográfico nítido | Forte em equações, gráficos e layout complexo | Fusão temporal `[MM:SS]` fala + `[Ecrã]` OCR |
| **Modo de Falha** | Ruído em baixo contraste/manuscrito | Alucinação de rótulos pequenos sem tiling | Descarte abaixo de limiar mínimo de caracteres/confiança |

---

## 3. Invariantes Anti-Fabricação em Pipelines Multimodais
- **Separação de Proveniência**: Distinguir explicitamente transcrição falada (`[02:15] ...`) de texto visual extraído por OCR (`[02:15] [Ecrã] ...`).
- **Degradação Honesta**: Se nem ASR nem OCR extraírem conteúdo válido, registar diagnóstico técnico explícito (`NO_SPEECH_OR_TEXT_DETECTED`) — **nunca** injetar transcrições de exemplo ou resumos genéricos.

---

## 4. Conceitos Relacionados & Fontes
- [[Hallucination Mitigation Techniques]]
- [[RAG Architecture and Retrieval Strategies]]
- [[JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline]]
- [[JARVIS Voice Service and Audio Streaming Architecture]]
- **Fontes**: Radford et al. (2023), *Robust Speech Recognition via Large-Scale Weak Supervision (Whisper)*; Dosovitskiy et al. (2021), *An Image is Worth 16x16 Words (ViT)*; Microsoft WinRT `Windows.Media.Ocr` API Specification.

