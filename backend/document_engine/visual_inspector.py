from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import pymupdf  # PyMuPDF official modern API

from backend.document_engine.render_engine import (
    RenderEngineManager,
    RenderEngineType,
    RenderResult,
)


@dataclass(frozen=True)
class LayoutFlaw:
    flaw_type: str  # "BLANK_PAGE", "ORPHAN_TITLE", "TABLE_OVERFLOW", "TEXT_CLIPPING", "MARGIN_VIOLATION"
    severity: str  # "ERROR", "WARNING"
    page_number: int
    description: str
    element_text: str = ""


@dataclass(frozen=True)
class VisualInspectionResult:
    docx_path: str
    pdf_path: str
    page_images: tuple[str, ...]
    total_pages: int
    flaws: tuple[LayoutFlaw, ...]
    render_engine_type: RenderEngineType
    engine_name: str
    is_real_office: bool
    visual_fidelity_verified: bool
    passed: bool
    summary: str
    limitations: tuple[str, ...] = ()

    def has_errors(self) -> bool:
        return any(f.severity == "ERROR" for f in self.flaws)


class VisualInspector:
    """
    Renders Word DOCX documents and performs automated geometrical and visual layout inspection.
    Enforces the strict distinction between REAL_OFFICE_RENDER and SYNTHETIC_RENDER.
    """

    @classmethod
    def convert_docx_to_pdf(
        cls,
        docx_path: str | Path,
        pdf_path: Optional[str | Path] = None,
        prefer_real_office: bool = True,
        update_fields: bool = True,
    ) -> str:
        """Converts DOCX to PDF using RenderEngineManager."""
        out_dir = Path(pdf_path).parent if pdf_path else None
        res = RenderEngineManager.render(
            docx_path,
            output_dir=out_dir,
            prefer_real_office=prefer_real_office,
            update_fields=update_fields,
        )
        if pdf_path and Path(res.pdf_path).resolve() != Path(pdf_path).resolve():
            shutil_dest = Path(pdf_path).resolve()
            shutil_dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(res.pdf_path, shutil_dest)
            return str(shutil_dest)
        return res.pdf_path

    @classmethod
    def render_pdf_to_images(
        cls,
        pdf_path: str | Path,
        output_dir: Optional[str | Path] = None,
        dpi: int = 150,
    ) -> List[str]:
        """Renders each page of a PDF document to a PNG image file."""
        return RenderEngineManager._render_pdf_pages_to_png(Path(pdf_path), Path(output_dir or Path(pdf_path).parent), dpi=dpi)

    @classmethod
    def inspect_visual_layout(
        cls,
        docx_path: str | Path,
        pdf_path: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        *,
        prefer_real_office: bool = True,
        update_fields: bool = True,
        require_real_office: bool = False,
    ) -> VisualInspectionResult:
        """
        Executes full visual inspection pipeline:
        1. Explicit render dispatch via RenderEngineManager (Real Office or Synthetic).
        2. Geometrical analysis of the resulting PDF pages.
        3. Automated defect detection (blank pages, orphan headings, clipping).
        4. Strict visual fidelity decision.
        """
        out_dir = Path(output_dir).resolve() if output_dir else Path(docx_path).parent / f"{Path(docx_path).stem}_render"
        render_res: RenderResult = RenderEngineManager.render(
            docx_path,
            output_dir=out_dir,
            prefer_real_office=prefer_real_office,
            update_fields=update_fields,
            require_real_office=require_real_office,
        )

        flaws: List[LayoutFlaw] = []
        doc = pymupdf.open(render_res.pdf_path)
        total_pages = len(doc)

        for p_idx, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            page_rect = page.rect
            p_height = page_rect.height
            p_width = page_rect.width

            # 1. Blank page detection
            # Note: ignore synthetic watermark text when evaluating content
            content_text = text.replace("[SIMULAÇÃO SINTÉTICA PYMUPDF — NÃO CONSTITUI PROVA DE PAGINAÇÃO WORD]", "").strip()
            if not content_text or len(content_text.replace("\n", "").strip()) == 0:
                flaws.append(
                    LayoutFlaw(
                        flaw_type="BLANK_PAGE",
                        severity="ERROR" if p_idx < total_pages else "WARNING",
                        page_number=p_idx,
                        description=f"Página {p_idx} está completamente em branco.",
                    )
                )
                continue

            # 2. Orphan title / heading near bottom detection
            blocks = page.get_text("blocks")
            text_blocks = [b for b in blocks if len(b) >= 5 and b[4].strip()]
            # Filter watermark block
            filtered_blocks = [
                b for b in text_blocks if "SIMULAÇÃO SINTÉTICA" not in b[4]
            ]

            if filtered_blocks:
                last_block = filtered_blocks[-1]
                b_y0 = last_block[1]
                b_text = last_block[4].strip()

                # If last block is in the bottom 12% of the page and looks like a heading
                if b_y0 > (p_height * 0.88):
                    is_heading_like = (
                        len(b_text) < 80
                        and (b_text.isupper() or b_text[0].isdigit() or "título" in b_text.lower() or "heading" in b_text.lower())
                    )
                    if is_heading_like:
                        flaws.append(
                            LayoutFlaw(
                                flaw_type="ORPHAN_TITLE",
                                severity="WARNING",
                                page_number=p_idx,
                                description=f"Título isolado (órfão) detectado no fim da página {p_idx}.",
                                element_text=b_text,
                            )
                        )

            # 3. Horizontal clipping / overflow check
            for b in filtered_blocks:
                b_x1 = b[2]
                if b_x1 > (p_width - 12.0):
                    flaws.append(
                        LayoutFlaw(
                            flaw_type="TEXT_CLIPPING",
                            severity="WARNING",
                            page_number=p_idx,
                            description=f"Texto excede a margem direita na página {p_idx} (x={b_x1:.1f}pt, largura={p_width:.1f}pt).",
                            element_text=b[4][:50],
                        )
                    )

        doc.close()

        errors = sum(1 for f in flaws if f.severity == "ERROR")
        warnings = sum(1 for f in flaws if f.severity == "WARNING")
        passed = errors == 0

        # Visual fidelity can ONLY be claimed if rendered on a REAL Office engine!
        fidelity_verified = render_res.is_real_office and passed

        summary = (
            f"Inspeção Visual [{render_res.engine_type.value} - {render_res.engine_name}]: "
            f"{'CONFORME' if passed else 'FALHA'}. "
            f"Fidelidade Real Verificada: {'SIM' if fidelity_verified else 'NÃO (Simulação Limitada)'}. "
            f"Total Páginas: {total_pages}. "
            f"Erros de Layout: {errors}, Avisos: {warnings}."
        )

        return VisualInspectionResult(
            docx_path=str(docx_path),
            pdf_path=render_res.pdf_path,
            page_images=render_res.page_images,
            total_pages=total_pages,
            flaws=tuple(flaws),
            render_engine_type=render_res.engine_type,
            engine_name=render_res.engine_name,
            is_real_office=render_res.is_real_office,
            visual_fidelity_verified=fidelity_verified,
            passed=passed,
            summary=summary,
            limitations=render_res.limitations,
        )
