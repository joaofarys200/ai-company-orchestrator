# ARCHITECTURE AND DATA FLOW — STUDY AREA FOLDER SYNCHRONIZATION
## Technical Specifications & Architecture Blueprint

**Module:** JARVIS OS Study Area Evolution  
**Date:** 2026-10-21  

---

### 1. High-Level System Architecture

The Study folder synchronization system bridges the desktop filesystem, the Python backend service layer, the WebSocket gateway, and the React frontend.

```
+-----------------------------------------------------------------------------------------+
|                                    REACT FRONTEND                                       |
|  [StudyLibraryView] <---> [WebSocketContext] <---> [Electron Bridge (window.electronAPI)]|
+------------------------------------+-----------------------------------+----------------+
                                     |                                   |
                         WebSocket   |                       Native IPC  |
                       (JSON Event)  |                      (Select Dir) |
                                     v                                   v
+------------------------------------+---------------+       +-----------+----------------+
|                   PYTHON BACKEND GATEWAY           |       |      ELECTRON MAIN PROCESS |
|     backend/websocket/handlers/study.py            |       |     electron/main.js       |
|     backend/websocket/contracts.py                 |       |  (dialog.showOpenDialog)   |
+------------------------------------+---------------+       +----------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------------------+
|                                 SERVICES LAYER                                          |
|                                                                                         |
|   +------------------------------------+      +-------------------------------------+   |
|   |         StudyService               | <--> |          FolderSyncManager          |   |
|   |   (collections, documents, RAG)    |      | (watchdog, debouncing, scan, hash)  |   |
|   +-----------------+------------------+      +------------------+------------------+   |
|                     |                                            |                      |
|                     v                                            v                      |
|   +-----------------+------------------+      +------------------+------------------+   |
|   |       Multimodal Ingestion         |      |       Filesystem Watcher            |   |
|   |  PyMuPDF / python-docx / Whisper   |      |  Thread-safe recursive Observer     |   |
|   +------------------------------------+      +-------------------------------------+   |
+-----------------------------------------------------------------------------------------+
```

---

### 2. Sequence Diagrams

#### Diagram 1: User Links Folder via Native Electron Dialog

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant View as StudyLibraryView.tsx
    participant IPC as Electron Bridge (preload.js)
    participant Main as Electron Main (main.js)
    participant WS as WebSocket Gateway (study.py)
    participant Svc as StudyService (study_service.py)
    participant Sync as FolderSyncManager (folder_sync_service.py)

    User->>View: Clicks "+ Vincular Pasta"
    alt Electron Runtime
        View->>IPC: window.electronAPI.selectFolder()
        IPC->>Main: ipcRenderer.invoke('dialog:selectFolder')
        Main-->>IPC: Returns selected folder path
        IPC-->>View: folderPath string
    else Browser Fallback
        View->>User: Prompts window.prompt("Caminho absoluto da pasta:")
        User-->>View: Returns folderPath
    end

    View->>WS: send({ type: "study_link_folder", collection_id, folder_path })
    WS->>Svc: link_folder_to_collection(collection_id, folder_path)
    Svc->>Sync: validate_and_normalize_folder_path(folder_path)
    Sync-->>Svc: normalized Path (traversal-safe)
    Svc->>Sync: register_folder(collection_id, folder_path, callback)
    Svc->>Sync: sync_collection_folder(collection_id, folder_path)
    Sync->>Svc: Ingests all valid files (.pdf, .docx, .txt, .md, .mp4, etc.)
    Svc->>Svc: _save_collections() & _save_documents()
    Svc-->>WS: Return { status: "LINKED", sync_report, total_files, ... }
    WS-->>View: Broadcast "study_folder_linked", "study_collections_list", "study_documents_list"
    View->>User: Displays Linked Folder badge, sync count, and ingested materials
```

#### Diagram 2: Background Change Detection & In-Place Re-ingestion

```mermaid
sequenceDiagram
    autonumber
    actor OS as Local Operating System
    participant Watch as Watchdog Observer (Background Thread)
    participant Debounce as Debounce Queue (threading.Timer)
    participant Svc as StudyService
    participant WS as WebSocket Broadcast
    participant UI as React Study UI

    OS->>Watch: File Modified Event (e.g., lecture_notes.md)
    Watch->>Debounce: push(folder_path, file_path)
    Note over Debounce: Resets 1.5s timer.<br/>Ignores rapid burst writes until settling.
    Debounce->>Svc: Trigger callback: _on_folder_change_detected(col_id, folder_path)
    Svc->>Svc: Compute SHA-256 of modified file
    alt File SHA-256 unchanged
        Svc->>Svc: Skip (no-op)
    else File SHA-256 changed
        Svc->>Svc: Re-ingest file in-place using existing doc_id
        Svc->>Svc: Update provenance (mtime, size, sha256)
        Svc->>WS: Broadcast "study_documents_list"
        WS-->>UI: Live update document list (Zero duplicate records)
    end
```

#### Diagram 3: Course-Scoped Contextual Q&A

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant UI as StudyLibraryView (Q&A Modal)
    participant WS as WebSocket Gateway
    participant Svc as StudyService
    participant RAG as Multimodal Semantic Retrieval

    Student->>UI: Enters question for course (e.g. "O que é polimorfismo?")
    UI->>WS: send({ type: "study_ask_course", collection_id, question })
    WS->>Svc: ask_course(collection_id, question)
    Svc->>Svc: Filter documents belonging strictly to collection_id
    Svc->>RAG: Retrieve relevant chunks across collection documents and video transcripts
    alt Chunks found above similarity threshold
        RAG-->>Svc: Top chunks with page/time metadata
        Svc->>Svc: Synthesize answer with citations [Doc, p. X], [Video, MM:SS]
        Svc-->>WS: Return { answer, citations: [...], sources: [...] }
    else Insufficient Evidence
        Svc-->>WS: Return { answer: "INSUFFICIENT_EVIDENCE: ...", citations: [] }
    end
    WS-->>UI: "study_ask_course_result"
    UI->>Student: Displays formatted answer with clickable citation tags
```

---

### 3. Electron IPC Bridge Specification

In `electron/preload.js`:
```javascript
contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:selectFolder'),
  openPath: (targetPath) => ipcRenderer.invoke('shell:openPath', targetPath),
});
```

In `electron/main.js`:
```javascript
ipcMain.handle('dialog:selectFolder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory']
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

ipcMain.handle('shell:openPath', async (event, targetPath) => {
  if (!targetPath) return { error: 'Invalid path' };
  return await shell.openPath(targetPath);
});
```

---

### 4. WebSocket Contracts

| Client Message | Parameters | Server Response | Action |
|:---|:---|:---|:---|
| `study_create_collection` | `name`, `subject`, `document_ids?`, `request_id?` | `study_collection_created`, `study_collections_list` | Creates a new discipline / course |
| `study_link_folder` | `collection_id`, `folder_path`, `recursive?`, `sync_enabled?` | `study_folder_linked`, `study_documents_list`, `study_collections_list` | Binds folder, registers watcher, runs initial sync |
| `study_unlink_folder` | `collection_id`, `folder_path`, `remove_materials?` | `study_folder_unlinked`, `study_documents_list`, `study_collections_list` | Unlinks folder without disk deletion |
| `study_sync_folder` | `collection_id`, `folder_path?` | `study_folder_synced`, `study_documents_list`, `study_collections_list` | Manually triggers full synchronization |
| `study_ask_course` | `collection_id`, `question`, `request_id?` | `study_ask_course_result` | Course-scoped RAG query with citations |
| `study_get_course_details` | `collection_id`, `request_id?` | `study_course_details` | Returns course stats, folder links, and materials |
| `study_retry_document` | `document_id`, `request_id?` | `study_document_retried` | Retries ingestion for failed or pending file |
