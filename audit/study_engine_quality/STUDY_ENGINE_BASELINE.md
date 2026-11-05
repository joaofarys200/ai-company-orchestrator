# JARVIS OS — Study Engine Baseline (`STUDY_ENGINE_BASELINE.md`)

**Data de Fecho da Baseline:** 2026-11-04  
**Versão da Arquitetura de Extração e Grounding:** `3.0-grounded` (`EXTRACTION_VERSION`)  
**Modelo Local Oficial:** `ollama` / `qwen3.5:9b`

---

## 1. Resumo Executivo da Baseline Estabelecida

1. **Modelo Único e Soberania Local (`qwen3.5:9b`):**
   - Todas as sínteses do subsistema de Estudos e o modo predefinido do orquestrador (`ORCHESTRATOR_MODE=local`) executam localmente através do Ollama com `qwen3.5:9b`.
   - Zero chamadas a APIs pagas ou fornecedores cloud externos para síntese de estudo; zero fallbacks silenciosos.

2. **Arquitetura de Evidências Canónicas (`build_document_evidence_units`):**
   - Todos os formatos suportados (`PDF`, `PPTX`, `DOCX`, `TXT/MD`, `AUDIO`, `VIDEO`) produzem unidades de evidência rastreáveis com coordenadas específicas (página/parágrafo, slide/elemento, secção/parágrafo, linhas ou intervalo temporal ASR/OCR).
   - Nenhuma afirmação sem suporte factual recebe citação falsa (`match_claim_evidence_ids` devolve `[]` quando o estado é `UNCONFIRMED`).

3. **Distinção Rigorosa entre Geração e Extração:**
   - Modos explícitos (`LLM_GROUNDED`, `PARTIAL`, `EXTRACTIVE_GROUNDED`, `UNAVAILABLE`) propagados desde o backend (`services/study_ai_engine.py`, `services/study_service.py`) até ao frontend (`StudySummaryView.tsx`, `StudyNotesView.tsx`) e ao cofre Obsidian (`status: llm_grounded_verified` vs `status: extractive_unverified`).

4. **Desempenho Validado no `qwen3.5:9b`:**
   - Síntese completa (Quick, Study, Detailed, Exam, Cornell Notes e Argument Map) executada numa única chamada JSON compacta:
     - **PDF Científico (`doc_a3b336f4295d`):** `66.1s` (`20.32 tok/s`, `grounding_ratio = 82.4%`, Score Global `94.0/100`).
     - **Vídeo Multimodal (`doc_vid_f76259cd5c4e`):** `49.9s` (`32.61 tok/s`, `grounding_ratio = 95.2%`, Score Global `94.7/100`).

5. **Spatial Board HUD Integrado (`SpatialBoard.tsx` + `HologramCore.tsx`):**
   - Suporte completo por voz, texto e clique para abrir quadros modulares de **Estudos**, **Obsidian Vault**, **Projetos (`dina`)** e **Sentinel**, maximizar cartões em foco e recolher o quadro devolvendo o orbe holográfico ao centro.

---

## 2. Inventário dos 10 Entregáveis Documentais (`audit/study_engine_quality/`)

1. [`STUDY_ENGINE_FORENSIC_AUDIT.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/STUDY_ENGINE_FORENSIC_AUDIT.md)
2. [`MULTIMODAL_INGESTION_AUDIT.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/MULTIMODAL_INGESTION_AUDIT.md)
3. [`GROUNDED_GENERATION_DESIGN.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/GROUNDED_GENERATION_DESIGN.md)
4. [`EXTRACTION_VS_GENERATION_POLICY.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/EXTRACTION_VS_GENERATION_POLICY.md)
5. [`STUDY_QUALITY_BENCHMARK.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/STUDY_QUALITY_BENCHMARK.md)
6. [`OLLAMA_PERFORMANCE_REPORT.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/OLLAMA_PERFORMANCE_REPORT.md)
7. [`FRONTEND_STUDY_INTEGRITY.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/FRONTEND_STUDY_INTEGRITY.md)
8. [`OBSIDIAN_INTEGRATION_AUDIT.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/OBSIDIAN_INTEGRATION_AUDIT.md)
9. [`TEST_AND_EVIDENCE_REGISTER.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/TEST_AND_EVIDENCE_REGISTER.md)
10. [`STUDY_ENGINE_BASELINE.md`](file:///c:/Users/joaor/Desktop/JarvisOS/audit/study_engine_quality/STUDY_ENGINE_BASELINE.md)

