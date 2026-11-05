# INGESTION AND RETRIEVAL INTEGRATION
## Multimodal Pipelines, Course-Scoped Retrieval & Citation Enforcement

**Module:** JARVIS OS Study Area Evolution  
**Date:** 2026-10-21  

---

### 1. Ingestion Pipelines Overview

The Study Area integrates multimodal files discovered in linked folders into a single pedagogical representation:

```
                      +-----------------------------+
                      |   Discovered Course File    |
                      +--------------+--------------+
                                     |
               +---------------------+---------------------+
               |                                           |
               v                                           v
     [Academic Documents]                        [Audio / Video Lectures]
   (.pdf, .docx, .pptx, .txt, .md)              (.mp4, .webm, .mkv, .mp3, .wav)
               |                                           |
               v                                           v
     +-------------------+                       +-------------------+
     | PyMuPDF / docx    |                       | Local Whisper     |
     | Text Extraction   |                       | Speech-to-Text    |
     +---------+---------+                       +---------+---------+
               |                                           |
               v                                           v
     +-------------------+                       +-------------------+
     | Page Chunking     |                       | Timestamp Chunks  |
     | (Page 1, 2, ...)  |                       | (MM:SS offsets)   |
     +---------+---------+                       +---------+---------+
               |                                           |
               +---------------------+---------------------+
                                     |
                                     v
                       +-----------------------------+
                       |    Standard StudyDocument   |
                       |  - text_content             |
                       |  - chunks with page/time    |
                       |  - provenance metadata      |
                       +-----------------------------+
```

---

### 2. Document Pipeline Integration

Documents discovered in linked folders pass through `StudyService.ingest_document`:
- **PDF Documents:** Analyzed using PyMuPDF (`fitz`), extracting per-page text, embedded figures, tables, and section hierarchies.
- **Office Documents (`.docx`, `.pptx`):** Extracted using `python-docx` and `python-pptx`, preserving headers, bullet lists, and presentation slide boundaries.
- **Markdown and Plain Text (`.md`, `.txt`):** Parsed with native UTF-8 decoders, preserving code blocks, markdown headings, and mathematical formulas.

Every document chunk records its exact source page:
```python
chunk = {
    "chunk_id": f"{doc_id}_chunk_{idx}",
    "text": chunk_text,
    "page_number": page_idx + 1,
    "source_type": "PDF",
}
```

---

### 3. Audio & Video Lecture Pipeline Integration

Video and audio lectures discovered in linked folders are processed via `StudyService.ingest_video`:
- **Audio Extraction:** High-efficiency extraction using ffmpeg into 16 kHz mono WAV streams.
- **Local Speech-to-Text:** Transcribed using local Whisper models (running completely offline on user hardware, with no paid cloud APIs).
- **Keyframe Extraction:** Key visual slide transitions are sampled at scene changes using OpenCV or ffmpeg, generating thumbnail previews for visual context.
- **Timestamp Segmentation:** Transcription is divided into temporal chunks corresponding to timestamp windows (e.g., `04:15 - 04:45`).

Every video chunk records its playback start and end times in seconds:
```python
chunk = {
    "chunk_id": f"{video_id}_seg_{idx}",
    "text": segment_text,
    "start_time": start_secs,
    "end_time": end_secs,
    "timestamp_str": f"{int(start_secs//60):02d}:{int(start_secs%60):02d}",
    "source_type": "VIDEO",
}
```

---

### 4. Provenance and Lineage Tracking

Every ingested material is tagged with comprehensive provenance metadata:
```json
{
  "document_id": "doc_ab83910c",
  "title": "aula02_arquitetura.pdf",
  "source_origin": "FOLDER_SYNC",
  "linked_folder_path": "C:\\Users\\aluno\\Documents\\EngenhariaSoftware",
  "rel_path": "Aulas\\aula02_arquitetura.pdf",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 1459203,
  "sync_status": "READY"
}
```
If a document is uploaded via drag-and-drop or file upload modal rather than folder synchronization, its `source_origin` is set to `"MANUAL_UPLOAD"` and `linked_folder_path` is `None`. Both origins coexist harmoniously within any course collection.

---

### 5. Course-Scoped Contextual Retrieval & Grounded Q&A

Students can execute natural-language queries across an entire course's corpus:
1. `StudyService.ask_course(collection_id, question)` identifies all documents linked to the specified `collection_id`.
2. Queries the internal semantic index only across chunks that belong to those documents.
3. Relevant evidence chunks are collected and ranked by cosine similarity.

#### Citation Formatting
All generated answers include explicit citation markers:
- For text documents: `[NomeDoFicheiro.pdf, p. 12]`
- For video lectures: `[Aula01_Gravada.mp4, 14:32]`

These citations are provided in two formats:
1. Embedded naturally inside the LLM answer text.
2. Returned as structured objects in the `citations` list for interactive UI badge rendering.

#### Insufficient Evidence Fallback
If the course materials do not contain sufficient information to answer the question, the system strictly refuses to hallucinate:
```json
{
  "answer": "INSUFFICIENT_EVIDENCE: Os materiais vinculados a esta disciplina não contêm informações suficientes sobre o tópico consultado.",
  "citations": [],
  "sources": []
}
```
The frontend detects this state and renders an amber advisory card prompting the student to add the relevant lecture slides or notes to their linked course folder.
