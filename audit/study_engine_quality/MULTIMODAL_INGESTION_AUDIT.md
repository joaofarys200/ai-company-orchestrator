# JARVIS OS — Multimodal Ingestion Audit (`MULTIMODAL_INGESTION_AUDIT.md`)

**Data:** 2026-11-04  
**Âmbito:** Ingestão, extração estrutural, transcrição ASR (`Faster-Whisper`) e OCR visual de diapositivos para TXT/MD, PDF, PPTX, DOCX, Áudio e Vídeo.

---

## 1. Coordenadas Canónicas de Evidência por Tipo de Fonte

Todas as fontes ingeridas são convertidas por [`build_document_evidence_units()`](file:///c:/Users/joaor/Desktop/JarvisOS/services/study_ai_engine.py) em unidades de evidência normalizadas com `evidence_id` determinístico e coordenadas auditáveis:

| Formato | Formato do `evidence_id` | Coordenadas Preservadas em Cada Unidade | Função de Extração |
|---|---|---|---|
| **PDF** | `{document_id}:p{page_number}:par{paragraph_idx}` | `document_id`, `page_number`, `paragraph_id`, `section_id`, `section_title`, `confidence` | `StudyService._extract_pdf_sections_and_media()` (PyMuPDF `fitz`) |
| **PPTX** | `{document_id}:slide{slide_number}:el{element_idx}` | `document_id`, `slide_number`, `text_element_id`, `speaker_notes`, `section_title` | `StudyService._extract_pptx_sections()` (`python-pptx`, incluindo notas do orador) |
| **DOCX** | `{document_id}:sec{section_idx}:par{paragraph_idx}` | `document_id`, `section_id`, `paragraph_id`, `section_title` | `StudyService._extract_docx_sections()` (`python-docx`) |
| **TXT / MD** | `{document_id}:L{line_start}-{line_end}:par{paragraph_idx}` | `document_id`, `line_range` (`Lstart-Lend`), `paragraph_id`, `section_id` | `StudyService._extract_text_sections()` |
| **AUDIO** | `{document_id}:t{start_ms}-{end_ms}:seg{segment_id}` | `document_id`, `start_timestamp`, `end_timestamp`, `transcription_segment_id`, `confidence` | `StudyService.ingest_audio()` + `LocalTranscriber` (`Faster-Whisper`) |
| **VIDEO** | `{document_id}:t{start_ms}-{end_ms}:{source_subtype}:{idx}` | `document_id`, `start_timestamp`, `end_timestamp`, `source_type` (`ASR_SPEECH` ou `SLIDE_OCR`), `frame_id`, `confidence` | `StudyService.ingest_video()` + `VideoIntelligenceService` |

---

## 2. Estados Explícitos do Pipeline Multimodal (Áudio e Vídeo)

Para eliminar qualquer ambiguidade entre um ficheiro com fala real, um ficheiro silencioso ou uma falha de ferramentas locais, o sistema regista estados padronizados em `doc.metadata`:

### Estados de Transcrição (`transcription_status`)
- `TRANSCRIPTION_COMPLETED`: Fala extraída com segmentos temporais reais via `Faster-Whisper`.
- `TRANSCRIPTION_PARTIAL`: Transcrição obtida parcialmente com avisos de confiança ou segmentos incompletos.
- `NO_SPEECH_DETECTED`: Áudio silencioso (`rms < 1e-4`) ou sem discurso inteligível detetado.
- `TRANSCRIPTION_FAILED`: Erro de descodificação de áudio ou indisponibilidade do motor ASR.

### Estados de OCR Visual em Vídeo (`ocr_status`)
- `OCR_COMPLETED`: Texto legível extraído e deduplicado de keyframes/diapositivos (`deduplicate_slide_ocr_entries`).
- `OCR_PARTIAL`: Keyframes extraídos mas sem texto de slide denso detetado.
- `OCR_UNAVAILABLE`: Sem keyframes visuais ou motor OCR indisponível.

### Flag de Integridade de Áudio (`audio_analysis_incomplete`)
- Sempre que `transcription_status` é `NO_SPEECH_DETECTED` ou `TRANSCRIPTION_FAILED`, `doc.metadata["audio_analysis_incomplete"] = True`.
- Em vídeos onde apenas os diapositivos (OCR) produziram texto e a pista de voz falhou ou está silenciosa, o documento regista:
  - `transcription_status = "NO_SPEECH_DETECTED"` (ou `"TRANSCRIPTION_FAILED"`)
  - `ocr_status = "OCR_COMPLETED"`
  - `audio_analysis_incomplete = True`
  - `transcription_warning = "Análise do áudio incompleta (...); conteúdo extraído exclusivamente via OCR local dos diapositivos (...)."`

---

## 3. Proibição de Fabrico em Multimédia

- Se um ficheiro de áudio ou vídeo não produzir discurso nem texto OCR (`full_video_corpus == ""` / `raw_transcript == ""`), `generate_complete_study_bundle()` define `generation_mode = "UNAVAILABLE"` e devolve `unavailable_generative_features = ["QuickSummary", "StudySummary", "DetailedSummary", "ExamSummary", "CornellNotes", "ArgumentMap"]`, sem inventar conteúdo a partir do nome do ficheiro.
- Validado pelos testes `test_05_audio_produces_transcription_segments_with_timestamps`, `test_06_video_associates_transcription_and_ocr_timestamps` e `test_07_silent_audio_reports_no_speech_detected`.

