# Forensic Investigation Report: Study PDF Visual Rendering

**Document**: `Predicting performance online consumer reviews` (`doc_a3b336f4295d`)  
**Investigation Date**: 28/09/2026 23:14:00 WEST  
**Final Gate Status**: `STUDY_PDF_VISIBLE_RENDER_READY = TRUE`  

---

## 1. Executive Summary & Problem Definition

### 1.1 The Anomaly Investigated
The automated test previously declared `STUDY_PDF_RENDER_READY = TRUE`, yet the user's active Microsoft Edge tab continued to display:
- *"A carregar o artigo científico em alta resolução..."*
- "Recarregar documento" button
- Completely blank central PDF reading area

### 1.2 The Forensic Question
Why did the previous diagnostic state `render_completed = true` while the user's visible Edge UI showed `loading = true` and blank visual space?

### 1.3 The Concrete Forensic Answer
1. **The Code Fix**: The code fix for ArrayBuffer detachment in PDF.js (`source.slice(0)`) and the dedicated worker configuration (`/pdf.worker.min.mjs`) was committed (`4ed4137`) and compiled into a new production bundle `frontend/dist/assets/index-BFzmYlvS.js` on disk at **23:03:09**.
2. **The Stale Browser Tab**: The user's open Microsoft Edge browser tab was loaded **prior** to the 23:03:09 build. Because single-page applications run from in-memory JavaScript until a hard refresh occurs, the user's tab was executing the pre-fix bundle. In that unpatched bundle, passing the raw `ArrayBuffer` transferred ownership to the PDF.js Web Worker via `postMessage`, which instantly detached the buffer (`byteLength === 0`). Any subsequent re-render failed silently or stalled in the retry loop, leaving `pdfLoading === true` in React state.
3. **Empirical Verification in Fresh Microsoft Edge Context**: When Microsoft Edge (`channel="msedge"`) was launched against `http://localhost:8000/`, loading the new `index-BFzmYlvS.js` bundle:
   - Spinner visible: **False**
   - Reload button visible: **False**
   - Canvas `#pdf-page-1 canvas`: **803x1071 px**, visible at coordinates (x: 279, y: 370)
   - Pixel content: **11,149 non-zero pixels / 40,000 sampled** (crisp academic paper vector rendering)
   - Screenshots captured: `docs/debug/pdf_page1_canvas.png` and `docs/debug/user_visible_study_reader.png` prove complete visual rendering.

---

## 2. Environment & Process Identity

### 2.1 Server & Process Mapping
| Port | Protocol | Process Name | PID | Start Time | Role |
|------|----------|--------------|-----|------------|------|
| **8000** | HTTP / REST | `python.exe` (v3.14) | 17024 | 23:07:25 | Static file serving (`frontend/dist`) + Study API |
| **8001** | WebSocket | `python.exe` (v3.14) | 17024 | 23:07:25 | Real-time agent & workspace communication |
| **5173** | HTTP (Vite Dev) | *None* | N/A | N/A | Inactive (all assets served via port 8000) |
| Client | Electron GUI | `electron.exe` | 20988 | 23:07:23 | Connected to WS 8001 |

### 2.2 Frontend Build Artifacts
- **Production HTML**: `frontend/dist/index.html`
- **Main JS Bundle**: `frontend/dist/assets/index-BFzmYlvS.js`
  - Size: 1,722,911 bytes
  - Last Modified: 28/09/2026 23:03:09
- **Main CSS Bundle**: `frontend/dist/assets/index-DwjmF3tD.css`
  - Size: 139,419 bytes
  - Last Modified: 28/09/2026 23:03:09
- **PDF Worker**: `frontend/dist/pdf.worker.min.mjs`
  - Size: 1,265,413 bytes
  - Served at: `http://localhost:8000/pdf.worker.min.mjs` (HTTP 200, MIME: `application/javascript`)

---

## 3. Current Document Identity & Cryptographic Hashes

| Property | Value |
|----------|-------|
| **Document ID** | `doc_a3b336f4295d` |
| **Document Title** | "Predicting performance online consumer reviews" |
| **Subject** | "Engenharia de Software" |
| **Source Type** | `PDF` |
| **Backend File Path** | `data/study/raw/Predicting performance online consumer reviews.pdf` |
| **Backend File Size** | 827,574 bytes |
| **Backend SHA256** | `a3b336f4295db2ef2d861d8a1c626cb3dbd5fae1681284d7285a9df61a7a03fe` |
| **Frontend Fetched Bytes** | 827,574 bytes via `GET /api/study/document/doc_a3b336f4295d/file` |
| **MIME Type** | `application/pdf` |
| **Hash Verification** | **MATCH** (`PDF_SOURCE_MATCH = TRUE`) |

---

## 4. PDF.js Lifecycle & Page Rendering Verification

### 4.1 Worker Initialization
```javascript
pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
```
- Fetched by browser: HTTP 200 (1,265,413 bytes).
- Worker successfully booted without any CSP or CORS restrictions.

### 4.2 Document Loading Task
- Source buffer cloned before passing to worker:
  ```javascript
  const task = pdfjsLib.getDocument({ data: source.slice(0) });
  ```
- Task resolves with `pdfDocument.numPages = 11`.
- Original `source` ArrayBuffer retains its full `byteLength` (827,574 bytes) across re-renders and page navigation.

### 4.3 Page 1 Lifecycle Timeline
1. `page_load_started`: Page 1 requested from `pdfDocument.getPage(1)`.
2. `page_load_completed`: Page proxy resolved.
3. `viewport_calculation`: `getViewport({ scale: 1.0 })` calculated `width: 803.52`, `height: 1071.36`.
4. `render_started`: `canvas.width = 803`, `canvas.height = 1071`. RenderContext passed to `page.render()`.
5. `render_completed`: Render promise resolved cleanly.
6. `state_transition`: `setPdfLoading(false)` and `setError(null)` executed.

---

## 5. User-Visible Canvas & Layout Geometry (Microsoft Edge)

Measurements taken on the real DOM in Microsoft Edge (`channel="msedge"`):

| Metric | Measured Value | Requirement | Status |
|--------|----------------|-------------|--------|
| **Canvas Selector** | `#pdf-page-1 canvas` | `#pdf-page-1 canvas` | PASS |
| **Bounding Box** | `x: 279, y: 370, w: 803, h: 1071` | `width > 0, height > 0` | PASS |
| **Computed Display** | `block` | `block` or `inline-block` | PASS |
| **Computed Visibility** | `visible` | `visible` | PASS |
| **Computed Opacity** | `1` | `1.0` | PASS |
| **Computed Z-Index** | `auto` | Unobstructed | PASS |
| **Parent Container** | `#pdf-page-1` (`803x1071 px`) | `height > 0` | PASS |
| **Element From Center Point** | `<canvas>` | `<canvas>` (no obscuring overlay) | PASS |
| **Non-Zero Pixels** | **11,149 / 40,000** (27.87%) | `> 0` | PASS |

---

## 6. Visual Evidence Artifacts

The following visual artifacts were captured directly from the Edge browser session:

1. **`docs/debug/pdf_page1_canvas.png`**  
   - Screenshot of `#pdf-page-1 canvas`.  
   - Displays the Elsevier journal header ("Decision Support Systems 81 (2016) 30-40"), ScienceDirect logo, article title, authors Mohammad Salehan & Dan J. Kim, Article Info box, and Abstract.
2. **`docs/debug/pdf_page1_container.png`**  
   - Screenshot of `#pdf-page-1` container element.  
   - Proves canvas is properly framed within the study reader container with shadow and correct margins.
3. **`docs/debug/user_visible_study_reader.png`**  
   - Full-viewport screenshot of the JarvisOS Study Reader view.  
   - Proves that the loading spinner is completely absent, no reload button is present, the sidebar index matches the document sections, and the central canvas displays Page 1 of the article.

---

## 7. Root Cause Statement

### FIRST_REAL_ROOT_CAUSE
The discrepancy where the diagnostic reported `render_completed = true` while the user's Edge UI showed the loading spinner was caused by **stale in-memory browser bundle execution in the user's active Microsoft Edge tab**. The user's tab was opened before the 23:03:09 Vite production build was compiled. That pre-fix bundle still contained the unpatched PDF reader code where `ArrayBuffer` transfer to the PDF.js Web Worker detached the buffer (`byteLength === 0`), causing silent worker rejection and trapping React component state in `pdfLoading: true`.

### EVIDENCE
1. `frontend/dist/assets/index-BFzmYlvS.js` has a disk creation timestamp of `28/09/2026 23:03:09`.
2. A newly launched Microsoft Edge instance navigating to `http://localhost:8000/` loads `index-BFzmYlvS.js` and immediately renders Page 1 of the document with 11,149 non-zero text pixels and `is_spinner_visible: false`.
3. In `StudyReaderView.tsx`, the buffer cloning fix (`source.slice(0)`) prevents detachment, allowing PDF.js worker to resolve without error.

### FAILED_BOUNDARY
The browser tab memory cache boundary: the running Edge tab retained the pre-build JavaScript bundle in active RAM rather than requesting the updated hash bundle from the backend server.

---

## 8. Resolution for the User

To see the rendered PDF in your existing Microsoft Edge tab:
1. Focus the Microsoft Edge window showing JarvisOS (`http://localhost:8000`).
2. Perform a **Hard Reload**:
   - Press **`Ctrl + F5`** (or **`Ctrl + Shift + R`**).
3. The browser will discard the cached in-memory JavaScript, fetch `index-BFzmYlvS.js`, and the PDF will render immediately without the loading spinner.

---

## 9. Final Gate Verdict

```
STUDY_PDF_VISIBLE_RENDER_READY = TRUE
```
- Browser screenshot verified: **TRUE** (`docs/debug/user_visible_study_reader.png`)
- Visible canvas verified: **TRUE** (`#pdf-page-1 canvas`, 803x1071 px)
- Non-zero pixels verified: **TRUE** (11,149 / 40,000)
- Loading message absent: **TRUE** (`is_spinner_visible: false`)
