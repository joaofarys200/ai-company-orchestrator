# JARVIS OS — Test & Evidence Register (`TEST_AND_EVIDENCE_REGISTER.md`)

**Data:** 2026-11-04  
**Ambiente Python:** `.\venv\Scripts\python.exe` (Python 3.14.7, `pytest-9.1.1`)  
**Ambiente Frontend:** Node.js / TypeScript (`tsc -b && vite build`)

---

## 1. Resumo Geral de Execução de Testes e Verificações

| Suite / Verificação | Comando Executado | Resultado | Tempo |
|---|---|---|---|
| **Suite Forense Obrigatória (25 Testes)** | `.\venv\Scripts\python.exe -m pytest tests/test_study_engine_forensic_qa.py -v` | **25 passed, 0 failed** | `1.05s` |
| **Suite Completa de Estudos (95 Testes)** | `.\venv\Scripts\python.exe -m pytest tests/test_study_engine_forensic_qa.py tests/test_study_grounded_summaries.py tests/test_study_reading_experience.py tests/test_study_folder_sync.py -q` | **95 passed, 0 failed** | `19.15s` |
| **Benchmark Live Ollama `qwen3.5:9b`** | `$env:STUDY_FORCE_LIVE_LLM="1"; .\venv\Scripts\python.exe audit/study_engine_quality/run_live_qwen_benchmark.py` | **COMPLETED (`LLM_GROUNDED` em PDF e VIDEO)** | `117.4s` (2 docs completos) |
| **Integridade de Dependências Python** | `.\venv\Scripts\python.exe -m pip check` | **No broken requirements found (Exit 0)** | `0.8s` |
| **Compilação TypeScript + Vite Build** | `npm --prefix frontend run build` | **✓ built in 3.96s (Exit 0)** | `3.96s` |

---

## 2. Registo Detalhado dos 25 Testes Obrigatórios (`tests/test_study_engine_forensic_qa.py`)

| # | Nome do Teste | Requisito Verificado | Estado |
|---|---|---|---|
| 1 | `test_01_txt_upload_produces_traceable_evidence_units` | Upload TXT produz unidades de evidência com `line_range` e `paragraph_id` | **PASSED** |
| 2 | `test_02_pdf_preserves_page_and_paragraph_coordinates` | PDF preserva `document_id + page_number + paragraph_id` | **PASSED** |
| 3 | `test_03_pptx_preserves_slide_number_and_text_element` | PPTX preserva `document_id + slide_number + text_element_id` e notas do orador | **PASSED** |
| 4 | `test_04_docx_preserves_section_and_paragraph_structure` | DOCX preserva `document_id + section_id + paragraph_id` | **PASSED** |
| 5 | `test_05_audio_produces_transcription_segments_with_timestamps` | Áudio produz segmentos com `start_timestamp`, `end_timestamp` e `transcription_segment_id` | **PASSED** |
| 6 | `test_06_video_associates_transcription_and_ocr_timestamps` | Vídeo associa transcrição ASR e OCR de slides com timestamps | **PASSED** |
| 7 | `test_07_silent_audio_reports_no_speech_detected` | Áudio silencioso comunica `NO_SPEECH_DETECTED` e `audio_analysis_incomplete=True` sem inventar texto | **PASSED** |
| 8 | `test_08_qwen35_9b_observable_telemetry_recorded` | Chamada ao `qwen3.5:9b` regista telemetria completa (`provider`, `model`, `generation_id`, tokens, `tokens_per_sec`, `status`) | **PASSED** |
| 9 | `test_09_invalid_llm_response_is_rejected` | Resposta inválida/malformada do modelo é rejeitada e registada em `validation_errors` | **PASSED** |
| 10 | `test_10_think_markers_are_stripped_cleanly` | Marcadores `<think>...</think>` são integralmente removidos antes da apresentação | **PASSED** |
| 11 | `test_11_ungrounded_claim_is_rejected_by_evidence_matcher` | Afirmação sem suporte no documento é rejeitada (`UNCONFIRMED`, `source_refs=[]`) | **PASSED** |
| 12 | `test_12_quick_summary_reflects_real_document_topic` | Quick Summary reflete o tema, objetivo, conceitos e conclusões reais do documento | **PASSED** |
| 13 | `test_13_study_summary_preserves_section_structure` | Study Summary preserva a divisão por secções e inclui `source_refs` | **PASSED** |
| 14 | `test_14_detailed_summary_has_greater_depth_than_quick_summary` | Detailed Summary aprofunda a matéria e não repete o Quick Summary | **PASSED** |
| 15 | `test_15_exam_summary_identifies_high_yield_concepts` | Exam Summary identifica conceitos fundamentais, definições e perguntas suportadas | **PASSED** |
| 16 | `test_16_cornell_notes_produces_grounded_cues_notes_and_summary` | Cornell Notes produz Cues, Notes e Summary com `source_refs` verificados | **PASSED** |
| 17 | `test_17_argument_map_distinguishes_descriptive_from_argumentative` | Argument Map distingue texto descritivo (`is_argumentative=False` + `argumentative_limitation`) de texto argumentativo | **PASSED** |
| 18 | `test_18_flashcards_and_quizzes_contain_zero_generic_filler` | Flashcards e Quizzes usam apenas factos do documento, sem perguntas genéricas pré-fabricadas | **PASSED** |
| 19 | `test_19_multi_document_synthesis_attributes_points_to_documents` | Síntese multi-documento atribui pontos, diferenças e conceitos a cada título de origem | **PASSED** |
| 20 | `test_20_extractive_fallback_is_explicitly_marked_extractive_grounded` | Fallback extrativo é marcado explicitamente como `EXTRACTIVE_GROUNDED` | **PASSED** |
| 21 | `test_21_model_failure_never_reports_llm_grounded_success` | Falha do modelo nunca comunica `LLM_GROUNDED` nem sucesso generativo | **PASSED** |
| 22 | `test_22_regeneration_replaces_stale_derived_artifacts_cleanly` | Regeneração substitui artefactos antigos, atualiza `extraction_version` e incrementa `regeneration_count` | **PASSED** |
| 23 | `test_23_save_to_vault_preserves_provenance_and_archives_existing_file` | `save_to_knowledge_vault` grava frontmatter completo e arquiva versão anterior em `.archive/` | **PASSED** |
| 24 | `test_24_websocket_preserves_request_id_and_supports_cancel` | WebSocket preserva `request_id` e suporta `study_cancel_generation` | **PASSED** |
| 25 | `test_25_frontend_distinguishes_llm_grounded_from_extractive_local` | Frontend (`StudySummaryView.tsx` / `StudyNotesView.tsx`) distingue `LLM_GROUNDED` (`qwen3.5:9b`) de `EXTRACTIVE_GROUNDED` | **PASSED** |

