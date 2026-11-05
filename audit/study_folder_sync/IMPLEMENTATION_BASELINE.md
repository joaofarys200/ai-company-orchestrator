# IMPLEMENTATION BASELINE — STUDY AREA FOLDER SYNCHRONIZATION
## Complete File Catalog & Architecture Baseline

**Module:** JARVIS OS Study Area Evolution  
**Date:** 2026-10-21  

---

### 1. File Inventory & Responsibilities

The following files constitute the implementation baseline for the Study Area Evolution:

| File Path | Type | Role & Responsibilities |
|:---|:---:|:---|
| `services/folder_sync_service.py` | **NEW** | Core folder sync engine: path normalization and traversal protection (`validate_and_normalize_folder_path`), extension whitelists, `FolderSyncReport` & `StudyFolderLink` dataclasses, and thread-safe `FolderSyncManager` with debounced watchdog observation. |
| `services/study_service.py` | **MODIFIED** | Integrates folder sync into Study domain: collection linking/unlinking, startup reconciliation, in-place SHA-256 change detection, rename tracking without data loss, safe teardown guards, and course-scoped Q&A retrieval with citations. |
| `backend/websocket/contracts.py` | **MODIFIED** | Defines message type contracts (`study_link_folder`, `study_unlink_folder`, `study_sync_folder`, `study_ask_course`, `study_get_course_details`, `study_retry_document`). |
| `backend/websocket/handlers/study.py` | **MODIFIED** | WebSocket handlers dispatching incoming client messages to `StudyService` asynchronously, broadcasting updates to connected clients. |
| `electron/preload.js` | **MODIFIED** | Exposes `window.electronAPI.selectFolder()` and `window.electronAPI.openPath()` across the Electron context isolation bridge. |
| `electron/main.js` | **MODIFIED** | Implements Electron IPC handlers for `dialog:selectFolder` (`dialog.showOpenDialog`) and `shell:openPath` (`shell.openPath`). |
| `frontend/src/features/study/types.ts` | **MODIFIED** | TypeScript definitions for `StudyFolderLink`, `StudyCollection`, and extended `StudyDocument` provenance fields (`source_origin`, `linked_folder_path`, `rel_path`, `sync_status`). |
| `frontend/src/protocol/websocket.ts` | **MODIFIED** | WebSocket client request payloads, server response types, and message parser mappings for study folder events. |
| `frontend/src/context/WebSocketContext.tsx` | **MODIFIED** | React context state and action handlers (`studyCollections`, `listStudyCollections`, `createStudyCollection`, `linkStudyFolder`, `unlinkStudyFolder`, `syncStudyFolder`, `askStudyCourse`, `retryStudyDocument`). |
| `frontend/src/features/workspace/WorkspaceViewer.tsx` | **MODIFIED** | Workspace router wiring: passes collection state and synchronization callbacks down to `StudyContainer`. |
| `frontend/src/features/study/StudyContainer.tsx` | **MODIFIED** | Intermediate view container: delegates collection, folder link, and course query methods to `StudyLibraryView`. |
| `frontend/src/features/study/StudyLibraryView.tsx` | **MODIFIED** | Comprehensive UI implementation: Course tab navigation, "+ Nova Disciplina" modal, Linked Folders toolbar with sync badges, native Electron folder picker with manual fallback, Zero Data Loss confirmation dialogs, "Perguntar à Disciplina" modal with citations, and document origin badges. |
| `websocket_schema.py` | **MODIFIED** | Canonical schema registry: added study folder sync and course message types to `CLIENT_MESSAGE_TYPES` and `SERVER_MESSAGE_TYPES`, ensuring zero protocol divergence at startup. |
| `tests/test_study_folder_sync.py` | **NEW** | Exhaustive automated test suite covering all 14 requirement scenarios (A through N) plus end-to-end WebSocket integration. |

---

### 2. Architectural Boundaries & Constraints

1. **Isolation to Study Area:**
   All folder synchronization logic is self-contained within `services/folder_sync_service.py`, `services/study_service.py`, and `frontend/src/features/study/*`. No modifications were made to the general Knowledge base (`services/knowledge_service.py`) or the Obsidian vault exporter.

2. **Zero Data Loss Guarantee:**
   Unlinking a folder, deleting a collection, or removing an item from the study library only cleanses the internal in-memory and database indexes of JARVIS OS. No `os.remove()`, `os.unlink()`, or `shutil.rmtree()` is ever executed on the user's disk files.

3. **Local-First & Offline:**
   All document parsing (PyMuPDF, docx, pptx) and audio/video processing (local Whisper, OpenCV keyframes) operate entirely on local compute without reliance on third-party cloud APIs.
