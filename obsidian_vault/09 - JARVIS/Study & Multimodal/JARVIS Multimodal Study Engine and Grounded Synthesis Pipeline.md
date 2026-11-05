---
type: architecture
domain: jarvis
difficulty: advanced
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
tags:
  - jarvis
  - study-engine
  - multimodal
  - ocr
  - asr
  - grounding
---

# 🎓 JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline

## 1. Separação Arquitetural de Responsabilidades
O subsistema de Estudos do **JARVIS OS** divide-se estritamente em dois módulos complementares:

1. **`services/study_service.py` (Catálogo, Estado e Persistência)**:
   - Gere o ciclo de vida da biblioteca (`data/study/documents.json`, `collections.json`, `quizzes.json`), sincronização de pastas locais, progresso de leitura, exportação para `obsidian_vault/` e ingestão de `PDF`, `DOCX`, `PPTX` (XML de slides + notas do orador), `MARKDOWN`, `TXT`, `IMAGE`, `VIDEO` e `AUDIO` / `LECTURE_AUDIO`.
2. **`services/study_ai_engine.py` (Motor Unificado de Síntese e Grounding Multimodal)**:
   - Motor *stateless* partilhado por documentos, vídeos e aulas que executa transcrição real, OCR nativo de fotogramas, síntese via `ModelExecutionService` (`LLM_GROUNDED`) e extração determinística TF-MMR (`EXTRACTIVE_GROUNDED`).

---

## 2. Pipeline Multimodal e Invariante Zero-Fabricação

```text
Upload (PDF/PPTX/DOCX/Audio/Video)
   ├── Texto/Slides ──> Segmentação PT/EN/Markdown/Slides + Excerto Representativo
   ├── Áudio/Vídeo  ──> FFmpeg 16kHz Mono ──> RMS Silence Gate ──> Faster-Whisper / Multimodal ASR
   └── Vídeo/Imagem ──> Keyframes ──> Windows.Media.Ocr (WinRT) ──> Desduplicação Jaccard
                                  │
                                  ▼
         generate_complete_study_bundle (max_output_tokens=8192, schema delimitado)
             ├── Sucesso LLM  ──> generation_mode = "LLM_GROUNDED"
             └── Offline/429  ──> build_extractive_study_bundle ──> "EXTRACTIVE_GROUNDED"
```

### Garantias de Qualidade Implementadas:
- **4 Modos de Resumo Coerentes**: `Quick` (pontos-chave), `Study` (síntese + conceitos por secção), `Detailed` (blocos analíticos aprofundados) e `Exam` (conceitos *high-yield* + perguntas prováveis com linha orientadora), gerados em conjunto com `Cornell Notes` e `Argument Map` (`structure`).
- **Auto-Cura de Cache Legado**: `is_prefabricated_artifact()` deteta marcadores legados pré-fabricados e força regeneração limpa (`force_regenerate=True`).
- **Protocolo WebSocket Completo**: `normalizeServerMessage` em `frontend/src/protocol/websocket.ts` preserva `study_summary_ready`, `study_synthesis_ready`, `study_knowledge_saved` e `study_error`.

---

## 3. Conceitos Relacionados & Fontes
- [[Multimodal Ingestion - Native Audio ASR, Vision Tokens and Document OCR]]
- [[Test-Time Compute Scaling and Reasoning Token Budgeting]]
- [[Agentic RAG, Query Decomposition and Cross-Encoder Reranking]]
- [[Runbook - How to Prevent Thinking-Token Starvation and Mid-JSON Truncation]]
- [[JARVIS Obsidian Tools and RAG System]]
- **Fontes**: Código-fonte do JARVIS OS — `services/study_ai_engine.py`, `services/study_service.py`, `services/video_intelligence_service.py`, `frontend/src/features/study/StudySummaryView.tsx`.

