from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import pymupdf  # PyMuPDF

from backend.document_engine.word_ast import extract_ast_from_docx


class RenderEngineType(str, Enum):
    REAL_OFFICE_RENDER = "REAL_OFFICE_RENDER"
    SYNTHETIC_RENDER = "SYNTHETIC_RENDER"
    RENDER_UNAVAILABLE = "RENDER_UNAVAILABLE"


@dataclass(frozen=True)
class RenderResult:
    engine_type: RenderEngineType
    engine_name: str
    engine_version: str
    pdf_path: str
    page_images: tuple[str, ...]
    total_pages: int
    fields_updated: bool
    toc_updated: bool
    is_real_office: bool
    limitations: tuple[str, ...]
    docx_input_sha256: str
    docx_output_sha256: Optional[str]
    pdf_sha256: str
    duration_ms: float = 0.0


class RenderEngineManager:
    """
    Explicit abstraction and orchestrator for document rendering engines.
    Determines available engines (Microsoft Word COM, LibreOffice, or PyMuPDF Synthetic)
    and enforces strict separation between real Office pagination and synthetic simulation.
    """

    _cached_word_com_version: Optional[str] = None
    _cached_word_com_checked: bool = False

    @classmethod
    def detect_available_engines(cls) -> dict[str, Any]:
        """Probes the host environment for available Office and rendering engines."""
        engines: dict[str, Any] = {
            "word_com": {"available": False, "version": None},
            "libreoffice": {"available": False, "path": None},
            "synthetic_pymupdf": {"available": True, "version": pymupdf.__version__},
        }

        # Check Microsoft Word COM on Windows
        if os.name == "nt":
            v = cls._probe_word_com()
            if v:
                engines["word_com"] = {"available": True, "version": v}

        # Check LibreOffice
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            engines["libreoffice"] = {"available": True, "path": soffice}

        return engines

    @classmethod
    def _probe_word_com(cls) -> Optional[str]:
        if cls._cached_word_com_checked:
            return cls._cached_word_com_version

        cls._cached_word_com_checked = True
        probe_script = (
            "try {\n"
            "    $w = New-Object -ComObject Word.Application\n"
            "    $v = $w.Version\n"
            "    $w.Quit()\n"
            "    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($w) | Out-Null\n"
            "    Write-Host \"WORD_VERSION:$v\"\n"
            "} catch {\n"
            "    Write-Host \"WORD_UNAVAILABLE\"\n"
            "}\n"
        )
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as tf:
                tf.write(probe_script)
                tf_path = tf.name

            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tf_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            try:
                os.remove(tf_path)
            except Exception:
                pass

            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("WORD_VERSION:"):
                        ver = line.split(":", 1)[1].strip()
                        cls._cached_word_com_version = ver
                        return ver
        except Exception:
            pass

        return None

    @classmethod
    def render(
        cls,
        docx_path: str | Path,
        output_dir: Optional[str | Path] = None,
        *,
        prefer_real_office: bool = True,
        update_fields: bool = True,
        require_real_office: bool = False,
        dpi: int = 150,
    ) -> RenderResult:
        """
        Renders a DOCX file to PDF and page-by-page PNG images.
        Strictly records whether REAL_OFFICE_RENDER or SYNTHETIC_RENDER was executed.
        """
        import time
        start_time = time.time()

        in_docx = Path(docx_path).resolve()
        if not in_docx.exists():
            raise FileNotFoundError(f"Documento DOCX não encontrado: {in_docx}")

        out_dir = Path(output_dir).resolve() if output_dir else in_docx.parent / f"{in_docx.stem}_render"
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_target = out_dir / f"{in_docx.stem}.pdf"

        in_bytes = in_docx.read_bytes()
        in_sha = hashlib.sha256(in_bytes).hexdigest()

        engines = cls.detect_available_engines()
        limitations: List[str] = []
        is_real = False
        fields_upd = False
        toc_upd = False
        engine_type = RenderEngineType.RENDER_UNAVAILABLE
        engine_name = "Nenhum"
        engine_ver = "N/A"
        docx_out_sha = None

        # 1. Attempt Word COM
        if prefer_real_office and engines["word_com"]["available"]:
            try:
                res_code, out_pdf_p, updated_sha = cls._convert_via_word_com(
                    in_docx,
                    pdf_target,
                    update_fields=update_fields,
                )
                if res_code == 0 and os.path.exists(out_pdf_p) and os.path.getsize(out_pdf_p) > 0:
                    is_real = True
                    fields_upd = update_fields
                    toc_upd = update_fields
                    engine_type = RenderEngineType.REAL_OFFICE_RENDER
                    engine_name = "Microsoft Word COM Automation"
                    engine_ver = str(engines["word_com"]["version"])
                    docx_out_sha = updated_sha
            except Exception as e:
                limitations.append(f"Falha na conversão via Microsoft Word COM: {e}")

        # 2. Attempt LibreOffice if Word COM didn't run and LibreOffice is present
        if not is_real and prefer_real_office and engines["libreoffice"]["available"]:
            try:
                res_code, out_pdf_p = cls._convert_via_libreoffice(in_docx, out_dir)
                if res_code == 0 and os.path.exists(out_pdf_p) and os.path.getsize(out_pdf_p) > 0:
                    is_real = True
                    engine_type = RenderEngineType.REAL_OFFICE_RENDER
                    engine_name = "LibreOffice Headless"
                    engine_ver = "Headless CLI"
            except Exception as e:
                limitations.append(f"Falha na conversão via LibreOffice: {e}")

        # 3. If real Office was required but unavailable, fail controlled
        if require_real_office and not is_real:
            raise RuntimeError(
                f"Motor Office real obrigatório não disponível no ambiente para renderização de alta fidelidade. "
                f"Limitações: {limitations}"
            )

        # 4. Fallback to Synthetic Render if Real Office was not executed
        if not is_real:
            engine_type = RenderEngineType.SYNTHETIC_RENDER
            engine_name = "PyMuPDF Synthetic Layout Synthesizer"
            engine_ver = pymupdf.__version__
            limitations.append(
                "PDF sintético gerado via PyMuPDF a partir da AST. "
                "AVISO: Não constitui prova de fidelidade visual nem de paginação do Microsoft Word."
            )
            cls._synthesize_pdf_from_docx(in_docx, pdf_target)

        # 5. Extract PDF bytes and hash
        pdf_bytes = pdf_target.read_bytes()
        pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

        # 6. Rasterize pages to PNG
        page_images = cls._render_pdf_pages_to_png(pdf_target, out_dir, dpi=dpi)

        duration = (time.time() - start_time) * 1000.0

        return RenderResult(
            engine_type=engine_type,
            engine_name=engine_name,
            engine_version=engine_ver,
            pdf_path=str(pdf_target),
            page_images=tuple(page_images),
            total_pages=len(page_images),
            fields_updated=fields_upd,
            toc_updated=toc_upd,
            is_real_office=is_real,
            limitations=tuple(limitations),
            docx_input_sha256=in_sha,
            docx_output_sha256=docx_out_sha or in_sha,
            pdf_sha256=pdf_sha,
            duration_ms=duration,
        )

    @classmethod
    def _convert_via_word_com(
        cls,
        docx_path: Path,
        pdf_path: Path,
        *,
        update_fields: bool = True,
    ) -> Tuple[int, str, Optional[str]]:
        """
        Executes robust Word COM conversion via isolated PowerShell script.
        Updates Fields and Tables of Contents, saves the updated DOCX, and exports to PDF.
        """
        update_snippet = ""
        if update_fields:
            update_snippet = """
    Write-Host "UPDATING_FIELDS"
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
        Write-Host "TOC_UPDATED"
    }
    $doc.Save()
"""

        ps_script = f"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
    $doc = $word.Documents.Open('{str(docx_path)}')
    {update_snippet}
    # 17 = wdFormatPDF
    $doc.SaveAs([ref]'{str(pdf_path)}', [ref]17)
    $doc.Close()
    Write-Host "WORD_CONVERSION_SUCCESS"
}} catch {{
    Write-Host "WORD_CONVERSION_ERROR: $($_.Exception.Message)"
}} finally {{
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as tf:
            tf.write(ps_script)
            script_path = tf.name

        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
                capture_output=True,
                text=True,
                timeout=45,
            )
        finally:
            try:
                os.remove(script_path)
            except Exception:
                pass

        if "WORD_CONVERSION_SUCCESS" in res.stdout and pdf_path.exists() and pdf_path.stat().st_size > 0:
            out_sha = hashlib.sha256(docx_path.read_bytes()).hexdigest()
            return 0, str(pdf_path), out_sha

        return 1, str(pdf_path), None

    @classmethod
    def _convert_via_libreoffice(cls, docx_path: Path, out_dir: Path) -> Tuple[int, str]:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            return 1, ""
        res = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", str(docx_path), "--outdir", str(out_dir)],
            capture_output=True,
            text=True,
            timeout=40,
        )
        pdf_path = out_dir / f"{docx_path.stem}.pdf"
        if res.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            return 0, str(pdf_path)
        return res.returncode, str(pdf_path)

    @classmethod
    def _synthesize_pdf_from_docx(cls, docx_path: Path, output_pdf: Path) -> None:
        """Pure-Python fallback PDF synthesizer using PyMuPDF for offline/isolated execution."""
        ast = extract_ast_from_docx(docx_path)
        doc = pymupdf.open()

        page_w, page_h = 595.3, 841.9  # A4 pt
        margin_x = 56.7  # 2.0 cm
        margin_y = 56.7  # 2.0 cm
        max_y = page_h - margin_y - 30

        curr_page = doc.new_page(width=page_w, height=page_h)
        y = margin_y

        # Watermark/Banner explicitly documenting synthetic nature
        banner_rect = pymupdf.Rect(margin_x, 15, page_w - margin_x, 35)
        curr_page.insert_textbox(
            banner_rect,
            "[SIMULAÇÃO SINTÉTICA PYMUPDF — NÃO CONSTITUI PROVA DE PAGINAÇÃO WORD]",
            fontsize=7,
            fontname="helv",
            color=(0.7, 0.2, 0.2),
        )

        if ast.title:
            rect = pymupdf.Rect(margin_x, y, page_w - margin_x, y + 30)
            curr_page.insert_textbox(rect, ast.title, fontsize=18, fontname="helv", color=(0.1, 0.2, 0.4))
            y += 40

        for elem in ast.ordered_elements:
            if y >= max_y:
                curr_page = doc.new_page(width=page_w, height=page_h)
                y = margin_y

            if hasattr(elem, "level") and hasattr(elem, "text"):
                lvl = elem.level
                font_size = 15 if lvl == 1 else (12 if lvl == 2 else 10)
                space_before = 14 if lvl == 1 else 8

                if y + space_before + 40 > max_y:
                    curr_page = doc.new_page(width=page_w, height=page_h)
                    y = margin_y
                else:
                    y += space_before

                rect = pymupdf.Rect(margin_x, y, page_w - margin_x, y + font_size + 8)
                curr_page.insert_textbox(
                    rect,
                    elem.text,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0.1, 0.2, 0.4) if lvl == 1 else (0.2, 0.3, 0.5),
                )
                y += font_size + 10

            elif hasattr(elem, "is_bullet") and hasattr(elem, "text"):
                text = elem.text.strip()
                if not text:
                    continue
                lines_est = max(1, len(text) // 70 + 1)
                box_h = lines_est * 13 + 5

                if y + box_h > max_y:
                    curr_page = doc.new_page(width=page_w, height=page_h)
                    y = margin_y

                prefix = "• " if elem.is_bullet else ""
                rect = pymupdf.Rect(margin_x + (15 if elem.is_bullet else 0), y, page_w - margin_x, y + box_h)
                curr_page.insert_textbox(rect, prefix + text, fontsize=9.5, fontname="helv", color=(0.15, 0.15, 0.15))
                y += box_h + 3

            elif hasattr(elem, "headers") and hasattr(elem, "rows"):
                rows_count = len(elem.rows) + (1 if elem.headers else 0)
                tbl_h = rows_count * 18 + 10

                if y + tbl_h > max_y:
                    curr_page = doc.new_page(width=page_w, height=page_h)
                    y = margin_y

                rect = pymupdf.Rect(margin_x, y, page_w - margin_x, y + tbl_h)
                table_text = " | ".join(elem.headers) + "\n" + "\n".join(" | ".join(r) for r in elem.rows)
                curr_page.draw_rect(rect, color=(0.8, 0.8, 0.8), fill=(0.96, 0.97, 0.99))
                curr_page.insert_textbox(rect, table_text, fontsize=8.5, fontname="helv")
                y += tbl_h + 10

        doc.save(str(output_pdf))
        doc.close()

    @classmethod
    def _render_pdf_pages_to_png(cls, pdf_path: Path, out_dir: Path, dpi: int = 150) -> List[str]:
        pages_dir = out_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        doc = pymupdf.open(str(pdf_path))
        images: List[str] = []

        for p_idx, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            img_path = pages_dir / f"page_{p_idx:02d}.png"
            pix.save(str(img_path))
            images.append(str(img_path))

        doc.close()
        return images
