# JARVIS OS — Third-Party Software Notices & Licensing Evaluation

This document records the licensing terms, attribution notices, and redistribution obligations for the third-party binaries and Python libraries bundled inside JARVIS OS Windows installers (MSI / NSIS) and `src-tauri/py-runtime/runtime-bundle.zip`.

---

## 1. FFmpeg (`ffmpeg-win-x86_64-v7.1.exe` via `imageio-ffmpeg==0.6.0`)

- **License:** **GNU General Public License v3.0 (GPLv3)** (`--enable-gpl --enable-version3 --enable-static`, build `7.1-essentials_build-www.gyan.dev`).
- **Wrapper Package (`imageio-ffmpeg`):** `BSD-2-Clause`.
- **Technical Evaluation (Why GPLv3 instead of an LGPL build):**
  - JARVIS OS invokes `ffmpeg` strictly out-of-process as a standalone CLI subprocess (`services/video_intelligence_service.py` and `services/study_ai_engine.py`).
  - `services/video_intelligence_service.py` (`ensure_playable_mp4`) transcodes non-web containers (`.wmv`, `.mkv`, `.avi`) to H.264/AAC MP4 using `-c:v libx264`. Standard LGPL FFmpeg builds omit `libx264` (which is GPL-licensed). Replacing `ffmpeg-win-x86_64-v7.1.exe` with an LGPL-only build would drop `libx264` transcoding unless the video encoder pipeline were re-engineered around `libopenh264` or OS hardware encoders.
- **Redistribution Obligations (GPLv3 Section 6):**
  - Any external distribution of the MSI/NSIS installers containing `ffmpeg-win-x86_64-v7.1.exe` must:
    1. Retain copyright and GPLv3 notices (Full text: https://www.gnu.org/licenses/gpl-3.0.txt).
    2. Provide access or a written offer for the corresponding FFmpeg and x264 source code used in the Gyan.dev static build:
       - Upstream FFmpeg source: https://git.ffmpeg.org/ffmpeg.git
       - Gyan.dev Windows build scripts & source manifests: https://www.gyan.dev/ffmpeg/builds/

---

## 2. PyMuPDF (`pymupdf==1.28.2`)

- **License:** Dual-licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)** or a **Commercial Artifex Software License**.
- **Technical Evaluation (Why preserved alongside `pypdfium2==5.13.0`):**
  - `pypdfium2` (`Apache-2.0` / `BSD-3-Clause`) is also present in the bundle, but does not provide PyMuPDF's programmatic PDF authoring, typography, vector graphics, and XRef extraction APIs (`pymupdf.Font`, `Shape.draw_line`, `Shape.draw_rect`, `insert_textbox`, `insert_link`, `Pixmap(pdf, xref)`), which are required by:
    - `services/study_document_generation/layout_composer.py`
    - `services/study_document_generation/orchestrator.py` & `qa_engine.py`
    - `services/document_intelligence.py`
    - `backend/document_engine/render_engine.py` & `visual_inspector.py`
    - `services/study_service.py`
  - Retaining `pymupdf==1.28.2` preserves 100% of PDF reading, layout inspection, and study document generation capabilities without regression.
- **Redistribution Obligations:**
  - Public/networked or binary distribution must either comply with **AGPL-3.0** (https://www.gnu.org/licenses/agpl-3.0.txt) or hold a commercial license from Artifex Software, Inc.

---

## 3. Permissive & Standard Components Bundled in `runtime-bundle.zip`

| Component | Version | License | Architecture |
| :--- | :--- | :--- | :--- |
| **CPython** | `3.14.7` | Python Software Foundation License v2 (`PSFL-2.0`) | `AMD64` (`x86_64`) |
| **NumPy** (+ bundled OpenBLAS) | `2.5.2` | `BSD-3-Clause` | `AMD64` (`x86_64`) |
| **pypdfium2** (+ PDFium) | `5.13.0` | `Apache-2.0` / `BSD-3-Clause` | `AMD64` (`x86_64`) |
| **pdfplumber** | `0.11.10` | `MIT` | Pure Python |
| **sounddevice** (+ PortAudio) | `0.5.6` | `MIT` | `AMD64` (`libportaudio64bit.dll`) |
| **Pillow** | `12.3.0` | `MIT-CMU` (`HPND`) | `AMD64` (`x86_64`) |
| **python-docx** | `1.2.0` | `MIT` | Pure Python |
| **cryptography** | `50.0.0` | `Apache-2.0` / `BSD-3-Clause` | `AMD64` (`x86_64`) |
| **psutil** | `7.2.2` | `BSD-3-Clause` | `AMD64` (`x86_64`) |
| **tree-sitter** & grammars | `0.26.0` / `0.25.0` | `MIT` | `AMD64` (`x86_64`) |
| **requests** / **httpx** / **websockets** | `2.34.2` / `0.28.1` / `17.0.1` | `Apache-2.0` / `BSD-3-Clause` | Pure Python |
| **Microsoft VC++ CRT** (`vcruntime140*.dll`, `msvcp140*.dll`) | MSVC 14.x | Microsoft Runtime Redistributable DLLs | `AMD64` (`x86_64`) |
