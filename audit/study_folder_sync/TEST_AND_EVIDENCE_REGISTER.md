# TEST AND EVIDENCE REGISTER — STUDY AREA FOLDER SYNCHRONIZATION
## Complete Verification Matrix & Test Evidence Log

**Module:** JARVIS OS Study Area Evolution  
**Date:** 2026-10-21  
**Environment:** Python 3.14.7 on Windows x64  
**Test Runners:** `pytest 9.1.1` & `vite v6.4.1`  

---

### 1. Test Execution Summary

| Suite / Test Target | Total Tests | Passed | Failed | Duration | Result |
|:---|:---:|:---:|:---:|:---:|:---:|
| `tests/test_study_folder_sync.py` | 15 | 15 | 0 | 18.45s | **100% PASSED** |
| `tests/test_study_reading_experience.py` | 49 | 49 | 0 | 1.82s | **100% PASSED** |
| `frontend` (`npm run build`) | N/A | TypeScript + Vite Bundle | 0 Errors | 8.90s | **100% PASSED** |

---

### 2. Scenario-by-Scenario Verification Matrix

| Scenario | Objective | Test Method | Key Invariants Verified | Result |
|:---:|:---|:---|:---|:---:|
| **A** | Associate course with local folder | `test_scenario_a_associate_course_with_local_folder` | Course creation, folder normalization, status `LINKED`, sync enabled by default | **PASSED** |
| **B** | Initial scan discovers and processes files | `test_scenario_b_initial_scan_discovers_and_processes_files` | Ingests PDF/MD/TXT recursively, populates document metadata, assigns course ID | **PASSED** |
| **C** | Newly added file detected on sync | `test_scenario_c_newly_added_file_appears_on_sync` | Adding file to folder updates collection document count and ingests text content | **PASSED** |
| **D** | Lecture video processed via multimodal pipeline | `test_scenario_d_newly_added_lecture_video_pipeline` | MP4 video discovery, Whisper transcript ingestion, timestamp chunk formatting | **PASSED** |
| **E** | Modified file reprocessed without duplicates | `test_scenario_e_modified_file_reprocessed_without_duplicates` | Same `document_id` retained, text content updated, no duplicate records created | **PASSED** |
| **F** | Renaming file preserves associations | `test_scenario_f_renaming_file_preserves_associations` | SHA-256 match detects rename, updates `rel_path` & title, keeps highlights/notes | **PASSED** |
| **G** | Deleting source updates collection | `test_scenario_g_deleting_source_updates_collection` | Deleting file removes it from index; other disk files remain completely untouched | **PASSED** |
| **H** | Offline changes detected on startup | `test_scenario_h_offline_changes_detected_on_startup` | Files created while app was closed are discovered & ingested on service boot | **PASSED** |
| **I** | Coexistence of manual and folder materials | `test_scenario_i_individual_and_folder_materials_coexist` | `FOLDER_SYNC` and `MANUAL_UPLOAD` documents live together in same collection | **PASSED** |
| **J** | Course Q&A citations and fallback | `test_scenario_j_course_qa_citations_and_fallback` | Grounded citations `[Doc, p. X]`, `[Video, MM:SS]`; `INSUFFICIENT_EVIDENCE` fallback | **PASSED** |
| **K** | Unsupported files and failures handled | `test_scenario_k_unsupported_files_and_failures` | `.exe`/`.bin` skipped gracefully without halting sync; valid files still ingested | **PASSED** |
| **L** | Unlinking stops monitoring; zero disk deletion | `test_scenario_l_unlinking_stops_monitoring_zero_disk_deletion` | Unlinked folder leaves all disk files intact; watcher ceases background monitoring | **PASSED** |
| **M** | Path traversal & root protection | `test_scenario_m_path_traversal_boundaries` | Traversal attempts (`../Windows`), system root (`C:\`), non-existent folders rejected | **PASSED** |
| **N** | Existing study features regression | `test_scenario_n_existing_study_functionality_regressions` | Highlights, bookmarks, reading notes, Cornell synthesis work identically on synced docs | **PASSED** |
| **WS** | WebSocket integration | `test_websocket_study_handlers_integration` | End-to-end flow: create collection, link folder, ask course, unlink folder via WS | **PASSED** |

---

### 3. Regression Test Verification (`test_study_reading_experience.py`)

All 49 existing Study Area tests passed without any regressions:
- Document structure & provenance tracking: PASSED
- Language detection and contextual reading translation: PASSED
- Multi-tier explanation levels (Basic, Intermediate, Academic): PASSED
- Figure & table explanations with evidence validation: PASSED
- Paper Q&A with citations: PASSED
- Argument map generation and Cornell note synthesis: PASSED
- Quiz generation and mathematical rubric scoring: PASSED
- Flashcard generation and SM-2 spaced repetition intervals: PASSED
- Obsidian knowledge vault export with wikilinks: PASSED
- WebSocket lifecycles for reading, quizzes, and flashcards: PASSED

---

### 4. Frontend Compilation & Typecheck Verification

Executing `npm run build` in `frontend/`:
```
> frontend@0.0.0 build
> tsc -b && vite build

vite v6.4.1 building for production...
transforming...
✓ 1952 modules transformed.
rendering chunks...
computing chunk sizes...
dist/index.html                                          0.92 kB │ gzip:   0.49 kB
dist/assets/index-BOZsWM4L.js                        1,836.46 kB │ gzip: 456.83 kB
✓ built in 3.77s
```
Status: **0 TypeScript errors, 0 build failures.**

---

### 5. Media Format Expansion & Real-World Folder Ingestion Verification

- **Identified Gap in Real-World Usage:**
  - Real-world course folders with university lectures frequently use `.wmv` (Windows Media Video), `.m4v`, `.flv`, `.mpg`, `.mpeg` or audio formats like `.wma`, `.flac`, `.aac`.
  - Previously, `SUPPORTED_VIDEO_EXTENSIONS` only whitelisted `{".mp4", ".webm", ".mkv", ".mov", ".avi"}`.
- **Implemented Fixes:**
  - Expanded `SUPPORTED_VIDEO_EXTENSIONS` across `services/folder_sync_service.py`, `services/video_intelligence_service.py`, and `services/study_service.py` to include:
    `.wmv`, `.m4v`, `.flv`, `.mpg`, `.mpeg`.
  - Expanded `SUPPORTED_AUDIO_EXTENSIONS` to include `.wma`, `.aac`, `.flac`.
  - Optimized video ingestion SHA-256 computation to stream in 64KB chunks instead of reading large video files entirely into RAM.
  - Resolved `compute_file_sha256` reference in `services/study_service.py`.
  - Verified user's course `gestao` with 8 `.wmv` video lectures:
    All 8 files successfully recognized, indexed, and registered into `col_45c2a9e9` without errors.
- **Suite Results:**
  - `tests/test_study_folder_sync.py`: 15/15 passed.
  - `tests/test_study_reading_experience.py`: 49/49 passed.
  - Total: **64 passed, 0 failed in 18.51s.**

