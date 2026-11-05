# FOLDER SYNCHRONIZATION AND RECOVERY ENGINE
## Detailed Engine Design, Debouncing, and Resilience Specification

**Module:** JARVIS OS Study Area Evolution  
**Date:** 2026-10-21  

---

### 1. Overview

The folder synchronization engine (`services/folder_sync_service.py` & `services/study_service.py`) provides real-time, bidirectional-aware background ingestion of local study directories into JARVIS OS courses. It is engineered with four primary pillars:
1. **Thread-Safe File Watching & Write Debouncing**
2. **Deterministic In-Place Modification Tracking**
3. **Rename & Relocation Detection via Content Hashes**
4. **Startup Offline Reconciliation**
5. **Zero Data Loss Invariance**

---

### 2. File Discovery and Extension Filtering

The discovery scanner (`FolderSyncManager.scan_folder`) walks linked directories with strict filtering rules:

#### Whitelisted Extensions
- **Text & Academic Documents:** `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, `.markdown`
- **Video Lectures:** `.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`
- **Audio Lectures & Podcasts:** `.mp3`, `.wav`, `.m4a`, `.ogg`
- **Visuals & Diagrams:** `.png`, `.jpg`, `.jpeg`, `.webp`

#### Ignored Patterns & Directories
To prevent thrashing and performance degradation, the following directories and file patterns are excluded automatically:
- Version control & editor metadata: `.git`, `.idea`, `.vscode`, `node_modules`
- Obsidian vault internals: `.obsidian`, `.trash`
- System & temporary files: `.DS_Store`, `Thumbs.db`, temporary office locks (`~$*`), hidden files (`.*`)

---

### 3. Change Detection & In-Place Modification

When a file inside a linked directory is modified on disk:
1. The watcher captures `FileModifiedEvent`.
2. The path and collection mapping are fed into the debounce coordinator.
3. Once the settling window expires, `sync_collection_folder` evaluates the file's current size, modification timestamp (`mtime`), and SHA-256 digest.
4. **Duplicate Prevention:**
   The service queries existing documents by matching `linked_folder_path` and `rel_path` or `source_path`.
   If a matching record exists and its SHA-256 matches the stored hash, the event is discarded as a no-op.
   If the SHA-256 has changed, the existing document is updated **in-place**:
   - The same `document_id` is retained.
   - User highlights, bookmarks, and Cornell notes linked to this document are preserved.
   - Multimodal re-ingestion regenerates text chunks, summary, and citations.
   - Provenance metadata (`last_modified`, `sha256`, `size_bytes`) is updated.

---

### 4. Rename & Relocation Tracking

When files are renamed or moved within the linked folder:
1. Standard filesystem watchers emit two separate events: a delete for the old path and a create for the new path.
2. In naive systems, this causes the document to be deleted (destroying user notes and study metrics) and re-ingested as a brand-new entity.
3. **JARVIS OS Solution:**
   Before executing the deletion pass, `sync_collection_folder` computes SHA-256 hashes of all newly discovered, unindexed files.
   It compares these hashes against missing documents that belonged to the linked folder.
   If a match is found:
   - The operation is classified as a **Rename / Relocation**.
   - The existing `document_id` is preserved.
   - The document's `title` is updated to reflect the new filename.
   - The document's `provenance["rel_path"]` and `source_path` are updated to point to the new location.
   - The document ID is added to `renamed_doc_ids`, explicitly exempting it from the deletion pass.
   - The user's study progress, quiz scores, and flashcard schedules remain 100% intact.

---

### 5. Write Debouncing Architecture

When large files (such as 2 GB video lectures or high-resolution slide decks) are copied into a folder, the operating system triggers a continuous stream of modification events as sequential blocks are written.

To prevent premature ingestion of half-written files:
- `FolderSyncManager` implements a `_DebouncedFileWatcher` utilizing a `threading.Timer` with a **1.5-second settling window**.
- Every incoming event for a folder resets the timer.
- Only when the folder has been quiet for 1.5 continuous seconds does the synchronization callback fire.
- File handles are opened in read mode with exception handling: if a file is still locked by an external write process, the scanner marks it as pending and schedules an automatic retry.

---

### 6. Startup & Offline Reconciliation

When JARVIS OS is closed, users may freely add, modify, or remove files in their course folders.

Upon service initialization (`StudyService.__init__`):
1. All persisted `StudyCollection` entities are loaded from `collections.json`.
2. For each collection with `sync_preferences.get("auto_sync", True)`:
   - Each registered folder in `linked_folders` is inspected on the local disk.
   - If the folder exists, `FolderSyncManager.register_folder` restarts the active watcher.
   - `sync_collection_folder` is invoked immediately to reconcile offline changes.
   - Files added while JARVIS OS was closed are ingested.
   - Files deleted while JARVIS OS was closed have their index entries cleaned up.
   - Files modified while JARVIS OS was closed are re-processed.

---

### 7. Thread Safety & Safe Teardown Guards

1. **Reentrant Lock Protection:**
   Internal data structures (`self.collections`, `self.documents`, `self.links`) are accessed with thread-safe guards to avoid race conditions between background watcher callbacks and frontend WebSocket requests.
2. **Teardown Protection:**
   In `StudyService._on_folder_change_detected`, the callback verifies that `self.storage_dir` and `self.workspace_root` still exist before initiating any file operations. If the application is shutting down or a temporary test fixture is being torn down, background worker threads safely abort without raising unhandled exceptions or crashing the process.

---

### 8. Proof of Zero Data Loss Guarantee

The platform guarantees that **JARVIS OS will never delete or modify the user's actual files on disk**:

```python
# From StudyService.unlink_folder_from_collection:
def unlink_folder_from_collection(self, collection_id: str, folder_path: str, remove_materials: bool = False):
    ...
    # Unregister from watcher
    self.folder_sync_manager.unregister_folder(collection_id, norm_str)
    
    # Remove link from collection
    col.linked_folders = [lnk for lnk in col.linked_folders if lnk.get("folder_path") != norm_str]
    
    if remove_materials:
        # Only remove documents from internal memory index:
        # os.remove() is NEVER called on the source disk files!
        for doc_id in docs_to_remove:
            self.documents.pop(doc_id, None)
```

In addition:
- Removing a material from a course removes its index entry and extracted text chunks from JARVIS OS internal state, leaving the original file on disk untouched.
- Deleting an entire course removes the collection grouping, leaving all source files on the user's hard drive intact.
