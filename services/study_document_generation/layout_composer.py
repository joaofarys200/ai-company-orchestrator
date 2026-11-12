"""
JARVIS OS — Study Engine Phase 5: Document Layout and Composition Engine (Componente 5.5 & Secção 6)
Composição visual e tipográfica determinística de documentos de estudo em PDF (PyMuPDF) e DOCX (python-docx).
Implementa medição tipográfica real, fragmentação controlada de blocos extensos sem truncagem silenciosa,
paginação multi-página de Objetivos/Índice/Bibliografia, verificação explícita de `insert_textbox()`,
controlo de órfãos/viúvas, keep-with-next, tabelas multi-página com repetição de cabeçalho e
preservação atómica de elementos visuais com legenda.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt
import pymupdf

from backend.document_engine.word_styler import WordStyler, hex_to_rgb
from services.study_document_generation.contracts import (
    IRBlock,
    IRBlockKind,
    IRPaginationHint,
    IRTOCEntry,
    StudyDocumentIR,
    normalize_epistemic_status,
)
from services.study_document_generation.design_system import (
    ACADEMIC_EDITORIAL_CLASSIC,
    AcademicDesignSystem,
    DesignStyleProfile,
    hex_to_rgb_float,
)


@dataclass
class DocumentRenderResult:
    file_path: str
    pages_count: int = 1
    file_size_bytes: int = 0
    frontmatter_pages: int = 1
    backmatter_pages: int = 1
    render_overflow_errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def pdf_path(self) -> str:
        return self.file_path

    @property
    def docx_path(self) -> str:
        return self.file_path

    def __str__(self) -> str:
        return self.file_path

    def __fspath__(self) -> str:
        return self.file_path


class _TypographicMetrics:
    """Medidor tipográfico real baseado em fontes TrueType/PyMuPDF e página de sondagem."""

    def __init__(self, fonts_dict: Dict[str, Optional[str]]) -> None:
        self.fonts_dict = fonts_dict
        self.font_objs: Dict[str, pymupdf.Font] = {}
        for fname, fpath in fonts_dict.items():
            if fpath and os.path.exists(fpath):
                try:
                    self.font_objs[fname] = pymupdf.Font(fontfile=fpath)
                    continue
                except Exception:
                    pass
            base_name = fname if fname in ("helv", "hebo", "heit", "cour", "times", "tiro", "tibo", "tiit") else "helv"
            try:
                self.font_objs[fname] = pymupdf.Font(base_name)
            except Exception:
                self.font_objs[fname] = pymupdf.Font("helv")

        self._probe_doc: Optional[pymupdf.Document] = None
        self._probe_page: Optional[pymupdf.Page] = None
        self._probe_ops = 0
        # Caches tipográficos em memória por compilação de PDF (eliminam O(W^2) em wrap_text_lines)
        self._unit_width_cache: Dict[Tuple[str, str], float] = {}
        self._space_unit_widths: Dict[str, float] = {}
        self._wrap_cache: Dict[Tuple[str, str, float, float], Tuple[str, ...]] = {}

    def _new_probe_page(self) -> pymupdf.Page:
        if self._probe_doc is None:
            self._probe_doc = pymupdf.open()
        p = self._probe_doc.new_page(width=595.28, height=4000.0)
        for fname, fpath in self.fonts_dict.items():
            if fpath and os.path.exists(fpath):
                try:
                    p.insert_font(fontname=fname, fontfile=fpath)
                except Exception:
                    pass
        return p

    def get_font(self, fontname: str) -> pymupdf.Font:
        if fontname in self.font_objs:
            return self.font_objs[fontname]
        return next(iter(self.font_objs.values()))

    def _unit_width(self, fontname: str, text: str) -> float:
        if not text:
            return 0.0
        key = (fontname, text)
        cached = self._unit_width_cache.get(key)
        if cached is not None:
            return cached
        f = self.get_font(fontname)
        w = float(f.text_length(text, fontsize=1.0))
        if len(self._unit_width_cache) >= 8192:
            self._unit_width_cache.clear()
        self._unit_width_cache[key] = w
        return w

    def _space_width(self, fontname: str, fontsize: float) -> float:
        uw = self._space_unit_widths.get(fontname)
        if uw is None:
            uw = float(self.get_font(fontname).text_length(" ", fontsize=1.0))
            self._space_unit_widths[fontname] = uw
        return uw * fontsize

    def text_width(self, text: str, fontname: str, fontsize: float) -> float:
        if not text or fontsize <= 0.0:
            return 0.0
        if len(text) <= 240:
            return self._unit_width(fontname, text) * fontsize
        f = self.get_font(fontname)
        return float(f.text_length(text, fontsize=fontsize))

    def wrap_text_lines(self, text: str, fontname: str, fontsize: float, max_width: float) -> List[str]:
        """Quebra texto em linhas visuais segundo a largura real dos glifos da fonte ativa."""
        if not text:
            return []
        cache_key = (text, fontname, round(float(fontsize), 4), round(float(max_width), 4))
        cached_wrap = self._wrap_cache.get(cache_key)
        if cached_wrap is not None:
            return list(cached_wrap)

        safe_w = max(24.0, max_width - 2.0)
        f = self.get_font(fontname)
        space_w = self._space_width(fontname, fontsize)
        # Banda de tolerância para confirmar kerning exato apenas na vizinhança de `safe_w`
        tol = max(1.5, fontsize * 0.25)
        out_lines: List[str] = []

        for raw_para in text.split("\n"):
            if not raw_para.strip():
                out_lines.append("")
                continue
            words = raw_para.split(" ")
            cur_line = ""
            cur_w = 0.0
            for word in words:
                word_w = self._unit_width(fontname, word) * fontsize if word else 0.0
                # Se uma palavra única exceder a largura útil, partir por caracteres
                if word and word_w > (safe_w - tol) and f.text_length(word, fontsize=fontsize) > safe_w:
                    if cur_line:
                        out_lines.append(cur_line)
                        cur_line = ""
                        cur_w = 0.0
                    chunk = ""
                    chunk_w = 0.0
                    for ch in word:
                        ch_w = self._unit_width(fontname, ch) * fontsize
                        next_w = chunk_w + ch_w
                        if chunk and next_w > (safe_w - tol) and f.text_length(chunk + ch, fontsize=fontsize) > safe_w:
                            out_lines.append(chunk)
                            chunk = ch
                            chunk_w = ch_w
                        else:
                            chunk += ch
                            chunk_w = next_w
                    cur_line = chunk
                    cur_w = float(f.text_length(cur_line, fontsize=fontsize)) if cur_line else 0.0
                    continue

                if not cur_line:
                    cur_line = word
                    cur_w = word_w
                    continue

                cand_w = cur_w + space_w + word_w
                if cand_w <= (safe_w - tol):
                    cur_line = f"{cur_line} {word}"
                    cur_w = cand_w
                elif cand_w > (safe_w + tol):
                    out_lines.append(cur_line)
                    cur_line = word
                    cur_w = word_w
                else:
                    cand = f"{cur_line} {word}"
                    exact_w = float(f.text_length(cand, fontsize=fontsize))
                    if exact_w <= safe_w:
                        cur_line = cand
                        cur_w = exact_w
                    else:
                        out_lines.append(cur_line)
                        cur_line = word
                        cur_w = word_w
            if cur_line:
                out_lines.append(cur_line)

        if len(self._wrap_cache) >= 4096:
            self._wrap_cache.clear()
        self._wrap_cache[cache_key] = tuple(out_lines)
        return out_lines

    def measure_text_height(
        self,
        text: str,
        *,
        fontname: str,
        fontsize: float,
        lineheight: float,
        max_width: float,
    ) -> float:
        """Mede a altura vertical exata exigida por `insert_textbox` usando largura real de glifos e métricas da fonte."""
        if not text or not text.strip():
            return 0.0
        f = self.get_font(fontname)
        wrapped = self.wrap_text_lines(text, fontname, fontsize, max_width)
        n_lines = max(1, len(wrapped))
        asc_desc = max(lineheight, (f.ascender - f.descender) + 0.30)
        exact_h = ((n_lines - 1) * (fontsize * lineheight)) + (fontsize * asc_desc) + 3.0
        return max(exact_h, fontsize * 1.35)

    def close(self) -> None:
        try:
            if self._probe_doc is not None:
                self._probe_doc.close()
                self._probe_doc = None
        except Exception:
            pass
        self._unit_width_cache.clear()
        self._wrap_cache.clear()


class PDFDocumentComposer:
    """
    Motor de layout e composição PDF de alta fidelidade via PyMuPDF.
    Executa paginação determinística em 2 passagens com medição real e fragmentação controlada:
    - Frontmatter multi-página (Capa, TODOS os Objetivos de Aprendizagem, TODO o Índice).
    - Passagem 1: Medição tipográfica real com fontes carregadas, fragmentação de blocos extensos
      (parágrafos, listas, caixas pedagógicas, tabelas com repetição de cabeçalho), controlo de
      órfãos/viúvas e proteção atómica de visuais e legendas.
    - Passagem 2: Renderização gráfica, verificação de todos os códigos de retorno de `insert_textbox()`,
      cabeçalhos/rodapés dinâmicos com largura medida, marcadores PDF (set_toc), links clicáveis
      no Índice em todas as páginas de TOC e Bibliografia completa multi-página.
    """

    def __init__(self, profile: Optional[DesignStyleProfile] = None) -> None:
        self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC
        self.geo = self.profile.geometry
        self.typo = self.profile.typography

    def compose_to_pdf(self, ir: StudyDocumentIR, output_path: str | Path) -> DocumentRenderResult:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        self._render_overflow_errors: List[Dict[str, Any]] = []
        doc = pymupdf.open()

        # Carregar fontes TrueType do sistema
        font_reg_name, font_reg_file = self._register_system_font(doc, "F_Reg", "regular")
        font_bold_name, font_bold_file = self._register_system_font(doc, "F_Bold", "bold")
        font_italic_name, font_italic_file = self._register_system_font(doc, "F_Italic", "italic")
        font_mono_name, font_mono_file = self._register_system_font(doc, "F_Mono", "mono")

        fonts_dict = {
            font_reg_name: font_reg_file,
            font_bold_name: font_bold_file,
            font_italic_name: font_italic_file,
            font_mono_name: font_mono_file,
        }

        metrics = _TypographicMetrics(fonts_dict)
        try:
            # 1. Linearizar blocos do documento
            linear_blocks = self._linearize_ir(ir)

            # 2. Calcular número de páginas de Frontmatter (Capa + Objetivos + TOC multi-página)
            fm_probe = self._render_frontmatter_pages(
                doc=None,
                fonts_dict=fonts_dict,
                metrics=metrics,
                ir=ir,
                block_to_page={},
                font_reg=font_reg_name,
                font_bold=font_bold_name,
                dry_run=True,
            )
            frontmatter_pages_cnt = fm_probe["pages_count"]

            # 3. Passagem 1: Medição real e fragmentação controlada a partir da página (frontmatter + 1)
            pages_plan, block_to_page, block_to_rect = self._plan_pagination(
                blocks=linear_blocks,
                metrics=metrics,
                start_page_num=frontmatter_pages_cnt + 1,
                font_reg=font_reg_name,
                font_bold=font_bold_name,
                font_italic=font_italic_name,
                font_mono=font_mono_name,
            )

            # 4. Passagem 2: Renderização efetiva do Frontmatter (com números de página reais!)
            fm_res = self._render_frontmatter_pages(
                doc=doc,
                fonts_dict=fonts_dict,
                metrics=metrics,
                ir=ir,
                block_to_page=block_to_page,
                font_reg=font_reg_name,
                font_bold=font_bold_name,
                dry_run=False,
            )
            toc_link_specs: List[Tuple[int, pymupdf.Rect, str]] = fm_res["toc_links"]

            # 5. Renderizar páginas de conteúdo
            for page_item in pages_plan:
                p = self._create_page_with_fonts(doc, fonts_dict)
                self._render_running_header(p, ir, page_item.get("chapter_title", ""), font_reg_name, metrics)
                for b_info in page_item["blocks"]:
                    self._render_block(
                        page=p,
                        block=b_info["block"],
                        rect=b_info["rect"],
                        metrics=metrics,
                        font_reg=font_reg_name,
                        font_bold=font_bold_name,
                        font_italic=font_italic_name,
                        font_mono=font_mono_name,
                    )

            # 6. Páginas Finais: Bibliografia & Proveniência (multi-página sem truncagem)
            bib_start_page = len(doc) + 1
            backmatter_pages_cnt = self._render_bibliography_pages(
                doc=doc,
                fonts_dict=fonts_dict,
                metrics=metrics,
                ir=ir,
                font_reg=font_reg_name,
                font_bold=font_bold_name,
                font_italic=font_italic_name,
            )

            # 7. Rodapés e Numeração Dinâmica em todas as páginas
            total_doc_pages = len(doc)
            for p_num, p in enumerate(doc, start=1):
                self._render_running_footer(p, ir, p_num, total_doc_pages, font_reg_name, metrics)

            # 8. Injetar Links Internos clicáveis em TODAS as páginas do Índice (LINK_GOTO)
            self._inject_toc_internal_links(doc, toc_link_specs, block_to_page)

            # 9. Definir marcadores nativos do PDF (TOC Bookmarks)
            pdf_toc = [[1, "Índice & Visão Geral", 1]]
            for entry in ir.toc_entries:
                target_pg = block_to_page.get(entry.target_block_id, frontmatter_pages_cnt + 1)
                target_pg = max(1, min(total_doc_pages, target_pg))
                pdf_toc.append([entry.level, f"{entry.number_label} {entry.title}", target_pg])
            pdf_toc.append([1, "Referências Bibliográficas & Proveniência", min(total_doc_pages, bib_start_page)])
            try:
                doc.set_toc(pdf_toc)
            except Exception:
                pass

            # 10. Metadados do PDF
            meta = ir.metadata
            doc.set_metadata({
                "title": meta.title,
                "author": ", ".join(meta.authors) if meta.authors else "JARVIS OS • Study Engine",
                "subject": meta.subtitle,
                "keywords": f"Study Engine, {meta.subject}, {self.profile.display_name}, QA Validated",
                "creator": f"JARVIS OS (v{meta.ir_version})",
                "producer": "PyMuPDF Deterministic Academic Composer",
            })

            pages_cnt = len(doc)
            tmp_out = out_p.with_suffix(".pdf.tmp")
            doc.save(str(tmp_out), garbage=4, deflate=True)
            doc.close()
            os.replace(tmp_out, out_p)
            sz = out_p.stat().st_size
            return DocumentRenderResult(
                file_path=str(out_p),
                pages_count=pages_cnt,
                file_size_bytes=sz,
                frontmatter_pages=frontmatter_pages_cnt,
                backmatter_pages=backmatter_pages_cnt,
                render_overflow_errors=list(self._render_overflow_errors),
            )
        finally:
            metrics.close()

    compose_pdf = compose_to_pdf

    # -----------------------------------------------------------------------
    # Registo de Fontes e Utilitários de Caixa
    # -----------------------------------------------------------------------

    def _create_page_with_fonts(
        self,
        doc: pymupdf.Document,
        fonts_dict: Dict[str, Optional[str]],
    ) -> pymupdf.Page:
        p = doc.new_page(width=self.geo.page_width_pt, height=self.geo.page_height_pt)
        for fname, fpath in fonts_dict.items():
            if fpath and os.path.exists(fpath):
                try:
                    p.insert_font(fontname=fname, fontfile=fpath)
                except Exception:
                    pass
        return p

    def _register_system_font(
        self,
        doc: pymupdf.Document,
        fontname: str,
        variant: str,
    ) -> Tuple[str, Optional[str]]:
        font_path = self.profile.resolve_font_path(variant)
        if font_path and os.path.exists(font_path):
            return fontname, font_path
        fallback_map = {
            "regular": "helv",
            "bold": "hebo",
            "italic": "heit",
            "mono": "cour",
        }
        return fallback_map.get(variant, "helv"), None

    def _safe_insert_textbox(
        self,
        page: pymupdf.Page,
        rect: pymupdf.Rect,
        text: str,
        *,
        fontname: str,
        fontsize: float,
        color: Tuple[float, float, float],
        lineheight: float = 1.35,
        align: int = pymupdf.TEXT_ALIGN_LEFT,
        metrics: Optional[_TypographicMetrics] = None,
        block_id: str = "",
        context: str = "",
    ) -> float:
        """
        Executa `insert_textbox` validando o valor de retorno `rc`.
        Se ocorrer overflow (`rc < 0`), tenta envolvimento explícito linha a linha ou ajuste controlado
        até à área útil máxima; se persistir texto não inserido, regista em `_render_overflow_errors`.
        """
        if not text:
            return 0.0

        wrapped = text
        if metrics is not None:
            wrapped = "\n".join(metrics.wrap_text_lines(text, fontname, fontsize, rect.width))

        rc = page.insert_textbox(
            rect,
            wrapped,
            fontname=fontname,
            fontsize=fontsize,
            color=color,
            lineheight=lineheight,
            align=align,
        )
        if rc < 0:
            # Tentar expansão controlada dentro da margem inferior útil da página antes de acusar erro
            max_y = self.geo.max_content_y_pt
            if rect.y1 < max_y:
                expanded = pymupdf.Rect(rect.x0, rect.y0, rect.x1, min(max_y, rect.y1 + 24.0))
                rc_retry = page.insert_textbox(
                    expanded,
                    wrapped,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                    lineheight=lineheight,
                    align=align,
                )
                if rc_retry >= 0:
                    return rc_retry
                rc = rc_retry

            self._render_overflow_errors.append({
                "block_id": block_id,
                "context": context,
                "overflow_rc": float(rc),
                "rect": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                "text_preview": text[:120],
            })
        return rc

    def _linearize_ir(self, ir: StudyDocumentIR) -> List[IRBlock]:
        blocks: List[IRBlock] = []
        for b in ir.executive_overview_blocks:
            blocks.append(b)
        for ch in ir.chapters:
            for b in ch.intro_blocks:
                blocks.append(b)
            for sec in ch.sections:
                for b in sec.blocks:
                    blocks.append(b)
            for b in ch.synthesis_blocks:
                blocks.append(b)
        for b in ir.global_synthesis_blocks:
            blocks.append(b)
        return blocks

    # -----------------------------------------------------------------------
    # Medição Tipográfica Real & Fragmentação Controlada (Passagem 1)
    # -----------------------------------------------------------------------

    def _full_content_height(self) -> float:
        return self.geo.max_content_y_pt - self.geo.margin_top_pt

    def _measure_block_height(
        self,
        b: IRBlock,
        metrics: Optional[_TypographicMetrics] = None,
        font_reg: str = "F_Reg",
        font_bold: str = "F_Bold",
        font_italic: str = "F_Italic",
        font_mono: str = "F_Mono",
    ) -> Tuple[float, float, float]:
        content_w = self.geo.content_width_pt

        if b.kind == IRBlockKind.HEADING.value:
            f_size = self.typo.chapter_title_pt if b.level == 1 else (
                self.typo.section_title_pt if b.level == 2 else self.typo.subsection_title_pt
            )
            clean_h = AcademicDesignSystem.sanitize_text_for_font(b.title)
            if metrics is not None:
                h = metrics.measure_text_height(
                    clean_h,
                    fontname=font_bold,
                    fontsize=f_size,
                    lineheight=1.22,
                    max_width=content_w,
                ) + 6.0
            else:
                h = 44.0 if b.level == 1 else (32.0 if b.level == 2 else 22.0)

            if b.level == 1:
                return max(34.0, h), self.geo.chapter_gap_before_pt, self.geo.chapter_gap_after_pt
            elif b.level == 2:
                return max(26.0, h), self.geo.section_gap_before_pt, self.geo.section_gap_after_pt
            else:
                return max(18.0, h), 8.0, 4.0

        elif b.kind == IRBlockKind.PARAGRAPH.value:
            full_text = "\n\n".join(b.paragraphs)
            clean_p = AcademicDesignSystem.sanitize_text_for_font(full_text)
            if metrics is not None:
                h = metrics.measure_text_height(
                    clean_p,
                    fontname=font_reg,
                    fontsize=self.typo.body_pt,
                    lineheight=self.typo.body_line_height_factor,
                    max_width=content_w,
                )
            else:
                lines = sum(max(1, int(len(p) / 78) + 1) for p in b.paragraphs)
                h = lines * (self.typo.body_pt * self.typo.body_line_height_factor)
            prov_h = self._measure_provenance_footer_height(b, metrics, font_reg, content_w)
            return max(18.0, h + prov_h), 2.0, self.geo.paragraph_gap_pt

        elif b.kind in (IRBlockKind.BULLET_LIST.value, IRBlockKind.NUMBERED_LIST.value):
            list_start = int(getattr(b, "level", 0) or 1) if b.kind == IRBlockKind.NUMBERED_LIST.value else 1
            items_str = "\n".join(
                f"• {it}" if b.kind == IRBlockKind.BULLET_LIST.value else f"{list_start + i}. {it}"
                for i, it in enumerate(b.items)
            )
            clean_l = AcademicDesignSystem.sanitize_text_for_font(items_str)
            if metrics is not None:
                h = metrics.measure_text_height(
                    clean_l,
                    fontname=font_reg,
                    fontsize=self.typo.body_pt,
                    lineheight=1.36,
                    max_width=content_w - 8.0,
                ) + 4.0
            else:
                lines = sum(max(1, int(len(it) / 72) + 1) for it in b.items)
                h = lines * (self.typo.body_pt * 1.36) + 6.0
            prov_h = self._measure_provenance_footer_height(b, metrics, font_reg, content_w)
            return max(18.0, h + prov_h), 2.0, self.geo.paragraph_gap_pt

        elif b.kind == IRBlockKind.CALLOUT_BOX.value:
            inner_w = content_w - 24.0
            header_txt = self._callout_header_text(b)
            clean_bt = AcademicDesignSystem.sanitize_text_for_font(header_txt)
            body_txt = "\n\n".join(b.paragraphs)
            if b.items:
                body_txt += ("\n" if body_txt else "") + "\n".join(f"• {it}" for it in b.items)
            clean_c = AcademicDesignSystem.sanitize_text_for_font(body_txt)

            if metrics is not None:
                title_h = metrics.measure_text_height(
                    clean_bt, fontname=font_bold, fontsize=self.typo.callout_title_pt, lineheight=1.22, max_width=inner_w
                )
                body_h = metrics.measure_text_height(
                    clean_c, fontname=font_reg, fontsize=self.typo.callout_body_pt, lineheight=1.35, max_width=inner_w
                )
                prov_h = self._measure_provenance_footer_height(b, metrics, font_reg, inner_w)
                total_h = 12.0 + title_h + 6.0 + body_h + (prov_h + 4.0 if prov_h else 0.0) + 10.0
            else:
                lines = max(2, int((len(clean_c)) / 72) + 1)
                total_h = 44.0 + lines * (self.typo.callout_body_pt * 1.38) + (20.0 if b.provenance_summary else 0.0)
            return max(52.0, total_h), 6.0, 8.0

        elif b.kind == IRBlockKind.TABLE.value:
            total_h = self._measure_table_total_height(b, content_w, metrics, font_reg, font_bold)
            return max(58.0, total_h), 8.0, 10.0

        elif b.kind == IRBlockKind.VISUAL_ELEMENT.value:
            title_h = (
                metrics.measure_text_height(
                    AcademicDesignSystem.sanitize_text_for_font(f"Figura: {b.title}"),
                    fontname=font_bold,
                    fontsize=9.5,
                    lineheight=1.2,
                    max_width=content_w,
                ) + 4.0
                if (b.title and metrics) else (18.0 if b.title else 0.0)
            )
            caption_h = (
                metrics.measure_text_height(
                    AcademicDesignSystem.sanitize_text_for_font(f"Legenda: {b.caption}"),
                    fontname=font_reg,
                    fontsize=self.typo.caption_pt,
                    lineheight=1.25,
                    max_width=content_w,
                ) + 4.0
                if (b.caption and metrics) else (26.0 if b.caption else 0.0)
            )
            prov_h = self._measure_provenance_footer_height(b, metrics, font_reg, content_w)
            max_allowed = self._full_content_height() - 4.0
            raw_img_h = 240.0
            if b.image_width_px and b.image_height_px:
                ratio = b.image_height_px / max(1, b.image_width_px)
                raw_img_h = max(130.0, content_w * ratio)
            img_h = min(280.0, raw_img_h, max(90.0, max_allowed - title_h - caption_h - prov_h - 6.0))
            return title_h + img_h + caption_h + prov_h + 6.0, 8.0, 10.0

        elif b.kind == IRBlockKind.EQUATION.value:
            eq_txt = b.equation_latex or b.equation_raw or "[Equação]"
            if metrics is not None:
                h = metrics.measure_text_height(
                    eq_txt, fontname=font_mono, fontsize=self.typo.equation_pt, lineheight=1.3, max_width=content_w - 20.0
                ) + 16.0
            else:
                h = 45.0
            return max(36.0, h), 6.0, 6.0

        return 22.0, 2.0, 4.0

    def _provenance_display_text(self, b: IRBlock) -> str:
        """Constrói o rótulo de estado epistémico + proveniência a exibir no PDF."""
        if "__frag" in b.block_id:
            return ""
        if not b.provenance_summary and b.kind not in (
            IRBlockKind.PARAGRAPH.value,
            IRBlockKind.BULLET_LIST.value,
            IRBlockKind.NUMBERED_LIST.value,
            IRBlockKind.CALLOUT_BOX.value,
            IRBlockKind.TABLE.value,
        ):
            return ""
        if b.provenance_summary:
            return AcademicDesignSystem.sanitize_text_for_font(b.provenance_summary)
        # Se não houver texto completo de provenance_summary num bloco com estado definido
        if b.chapter_id or b.section_id:
            badge, _, _ = self.profile.get_epistemic_style(b.epistemic_status, b.is_hypothetical_example)
            return AcademicDesignSystem.sanitize_text_for_font(f"Classificação: {badge}")
        return ""

    def _measure_provenance_footer_height(
        self,
        b: IRBlock,
        metrics: Optional[_TypographicMetrics],
        font_reg: str,
        width: float,
    ) -> float:
        prov_txt = self._provenance_display_text(b)
        if not prov_txt:
            return 0.0
        if metrics is not None:
            return metrics.measure_text_height(
                prov_txt, fontname=font_reg, fontsize=self.typo.provenance_pt, lineheight=1.22, max_width=width
            ) + 5.0
        return 16.0

    def _callout_header_text(self, b: IRBlock) -> str:
        theme = self.profile.get_callout_theme(b.callout_kind)
        ep_st = normalize_epistemic_status(b.epistemic_status, default="UNVERIFIED")
        ep_tag = "[EXEMPLO HIPOTÉTICO • MODEL_INFERENCE]" if b.is_hypothetical_example else f"[{ep_st}]"
        base_lbl = theme.badge_label
        if f"[{ep_st}]" not in base_lbl and f"({ep_st})" not in base_lbl:
            prefix = f"{base_lbl} {ep_tag}"
        else:
            prefix = base_lbl
        return f"{prefix}: {b.title}" if b.title else prefix

    def _measure_table_layout(
        self,
        b: IRBlock,
        content_w: float,
        metrics: Optional[_TypographicMetrics],
        font_reg: str,
        font_bold: str,
    ) -> Tuple[float, float, List[float], float, float]:
        """Devolve (title_h, header_h, row_heights, caption_prov_h, col_w)."""
        cols_count = max(1, len(b.table_headers) or (len(b.table_rows[0]) if b.table_rows else 1))
        col_w = content_w / cols_count
        cell_inner_w = max(24.0, col_w - 10.0)

        title_h = 0.0
        if b.title:
            t_str = AcademicDesignSystem.sanitize_text_for_font(f"Tabela: {b.title}")
            title_h = (
                metrics.measure_text_height(t_str, fontname=font_bold, fontsize=9.5, lineheight=1.22, max_width=content_w) + 5.0
                if metrics else 22.0
            )

        hdr_h = 24.0
        if b.table_headers:
            max_hh = 18.0
            for h_txt in b.table_headers:
                ch = AcademicDesignSystem.sanitize_text_for_font(str(h_txt))
                hh = (
                    metrics.measure_text_height(
                        ch, fontname=font_bold, fontsize=self.typo.table_header_pt, lineheight=1.22, max_width=cell_inner_w
                    ) + 8.0
                    if metrics else 22.0
                )
                if hh > max_hh:
                    max_hh = hh
            hdr_h = max_hh

        row_heights: List[float] = []
        for row in b.table_rows:
            max_rh = 18.0
            for c_i in range(cols_count):
                val = str(row[c_i]) if c_i < len(row) else ""
                clean_val = AcademicDesignSystem.sanitize_text_for_font(val)
                rh = (
                    metrics.measure_text_height(
                        clean_val, fontname=font_reg, fontsize=self.typo.table_cell_pt, lineheight=1.25, max_width=cell_inner_w
                    ) + 8.0
                    if (metrics and clean_val) else 20.0
                )
                if rh > max_rh:
                    max_rh = rh
            row_heights.append(max_rh)

        cap_h = 0.0
        cap_parts: List[str] = []
        if b.caption:
            cap_parts.append(AcademicDesignSystem.sanitize_text_for_font(b.caption))
        prov_txt = self._provenance_display_text(b)
        if prov_txt:
            cap_parts.append(prov_txt)
        if cap_parts:
            cap_full = "\n".join(cap_parts)
            cap_h = (
                metrics.measure_text_height(
                    cap_full, fontname=font_reg, fontsize=self.typo.caption_pt, lineheight=1.22, max_width=content_w
                ) + 6.0
                if metrics else 20.0
            )

        return title_h, hdr_h, row_heights, cap_h, col_w

    def _measure_table_total_height(
        self,
        b: IRBlock,
        content_w: float,
        metrics: Optional[_TypographicMetrics],
        font_reg: str,
        font_bold: str,
    ) -> float:
        title_h, hdr_h, row_heights, cap_h, _ = self._measure_table_layout(
            b, content_w, metrics, font_reg, font_bold
        )
        return title_h + hdr_h + sum(row_heights) + cap_h + 4.0

    # -----------------------------------------------------------------------
    # Fragmentação Controlada de Blocos Extensos (Secção 3.2)
    # -----------------------------------------------------------------------

    def _split_block_for_space(
        self,
        b: IRBlock,
        avail_h: float,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> Tuple[Optional[IRBlock], Optional[IRBlock]]:
        """
        Divide um bloco extenso quando não cabe no espaço restante (`avail_h`).
        Devolve `(head_fragment, tail_fragment)`:
        - `(None, b)` se não houver espaço mínimo útil e convier quebrar para nova página.
        - `(b, None)` se couber integralmente.
        - `(head, tail)` se o bloco foi dividido exatamente sem perda de conteúdo.
        """
        content_w = self.geo.content_width_pt

        if b.kind == IRBlockKind.PARAGRAPH.value:
            return self._split_paragraph_block(b, avail_h, content_w, metrics, font_reg)

        if b.kind in (IRBlockKind.BULLET_LIST.value, IRBlockKind.NUMBERED_LIST.value):
            return self._split_list_block(b, avail_h, content_w, metrics, font_reg)

        if b.kind == IRBlockKind.CALLOUT_BOX.value:
            return self._split_callout_block(b, avail_h, content_w, metrics, font_reg, font_bold)

        if b.kind == IRBlockKind.TABLE.value:
            return self._split_table_block(b, avail_h, content_w, metrics, font_reg, font_bold)

        return None, b

    def _split_paragraph_block(
        self,
        b: IRBlock,
        avail_h: float,
        content_w: float,
        metrics: _TypographicMetrics,
        font_reg: str,
    ) -> Tuple[Optional[IRBlock], Optional[IRBlock]]:
        if avail_h < 34.0:
            return None, b

        fs = self.typo.body_pt
        lh = self.typo.body_line_height_factor
        line_step = fs * lh
        safe_budget = avail_h - 4.0

        head_paras: List[str] = []
        tail_paras: List[str] = []

        paras = list(b.paragraphs)
        for idx, para_txt in enumerate(paras):
            cand_joined = AcademicDesignSystem.sanitize_text_for_font("\n\n".join(head_paras + [para_txt]))
            cand_h = metrics.measure_text_height(
                cand_joined, fontname=font_reg, fontsize=fs, lineheight=lh, max_width=content_w
            )
            if cand_h <= safe_budget:
                head_paras.append(para_txt)
            else:
                base_h = (
                    metrics.measure_text_height(
                        AcademicDesignSystem.sanitize_text_for_font("\n\n".join(head_paras)),
                        fontname=font_reg, fontsize=fs, lineheight=lh, max_width=content_w,
                    )
                    if head_paras else 0.0
                )
                rem_h = safe_budget - base_h - (fs * lh if head_paras else 0.0)
                if rem_h >= line_step * 2:
                    clean_p = AcademicDesignSystem.sanitize_text_for_font(para_txt)
                    lines = metrics.wrap_text_lines(clean_p, font_reg, fs, content_w)
                    fit_lines_cnt = max(1, min(len(lines) - 1, int(rem_h / line_step)))
                    while fit_lines_cnt > 0:
                        chunk_cand = " ".join(ln for ln in lines[:fit_lines_cnt] if ln).strip()
                        test_joined = AcademicDesignSystem.sanitize_text_for_font("\n\n".join(head_paras + [chunk_cand]))
                        test_h = metrics.measure_text_height(
                            test_joined, fontname=font_reg, fontsize=fs, lineheight=lh, max_width=content_w
                        )
                        if test_h <= safe_budget:
                            break
                        fit_lines_cnt -= 1

                    if 1 <= fit_lines_cnt < len(lines):
                        head_chunk = " ".join(ln for ln in lines[:fit_lines_cnt] if ln).strip()
                        tail_chunk = " ".join(ln for ln in lines[fit_lines_cnt:] if ln).strip()
                        if head_chunk and tail_chunk:
                            head_paras.append(head_chunk)
                            tail_paras.append(tail_chunk)
                            tail_paras.extend(paras[idx + 1:])
                            break
                tail_paras.extend(paras[idx:])
                break

        if not head_paras:
            return None, b
        if not tail_paras:
            return b, None

        base_id = b.block_id.split("__frag")[0]
        frag_num = b.block_id.count("__frag") + 1
        head_blk = replace(
            b,
            block_id=f"{base_id}__frag{frag_num}",
            paragraphs=head_paras,
            provenance_summary="",
        )
        tail_blk = replace(
            b,
            block_id=f"{base_id}__fragcont{frag_num}",
            paragraphs=tail_paras,
            pagination=replace(b.pagination, page_break_before=False),
        )
        return head_blk, tail_blk

    def _split_list_block(
        self,
        b: IRBlock,
        avail_h: float,
        content_w: float,
        metrics: _TypographicMetrics,
        font_reg: str,
    ) -> Tuple[Optional[IRBlock], Optional[IRBlock]]:
        if avail_h < 34.0:
            return None, b

        fs = self.typo.body_pt
        lh = 1.36
        list_w = content_w - 8.0
        start_num = int(getattr(b, "level", 0) or 1)
        is_bullet = (b.kind == IRBlockKind.BULLET_LIST.value)
        safe_budget = avail_h - 6.0

        head_items: List[str] = []
        tail_items: List[str] = []

        def _fmt_list(its: List[str]) -> str:
            return AcademicDesignSystem.sanitize_text_for_font(
                "\n".join(f"• {it}" if is_bullet else f"{start_num + k}. {it}" for k, it in enumerate(its))
            )

        for i, item in enumerate(b.items):
            cand_h = metrics.measure_text_height(
                _fmt_list(head_items + [item]), fontname=font_reg, fontsize=fs, lineheight=lh, max_width=list_w
            ) + 4.0
            if cand_h <= safe_budget:
                head_items.append(item)
            else:
                if not head_items and avail_h >= self._full_content_height() * 0.85:
                    prefix = "• " if is_bullet else f"{start_num + i}. "
                    lines = metrics.wrap_text_lines(AcademicDesignSystem.sanitize_text_for_font(item), font_reg, fs, list_w - 14.0)
                    line_step = fs * lh
                    fit_cnt = max(1, min(len(lines) - 1, int((safe_budget - 8.0) / line_step)))
                    while fit_cnt > 1:
                        cand_txt = f"{prefix}" + " ".join(lines[:fit_cnt])
                        c_h = metrics.measure_text_height(
                            cand_txt, fontname=font_reg, fontsize=fs, lineheight=lh, max_width=list_w
                        ) + 4.0
                        if c_h <= safe_budget:
                            break
                        fit_cnt -= 1
                    if 1 <= fit_cnt < len(lines):
                        head_items.append(" ".join(lines[:fit_cnt]))
                        tail_items.append(" ".join(lines[fit_cnt:]))
                        tail_items.extend(b.items[i + 1:])
                        break
                tail_items.extend(b.items[i:])
                break

        if not head_items:
            return None, b
        if not tail_items:
            return b, None

        base_id = b.block_id.split("__frag")[0]
        frag_num = b.block_id.count("__frag") + 1
        head_blk = replace(
            b,
            block_id=f"{base_id}__frag{frag_num}",
            items=head_items,
            provenance_summary="",
        )
        tail_blk = replace(
            b,
            block_id=f"{base_id}__fragcont{frag_num}",
            level=start_num + len(head_items) if not is_bullet else b.level,
            items=tail_items,
            pagination=replace(b.pagination, page_break_before=False),
        )
        return head_blk, tail_blk

    def _split_callout_block(
        self,
        b: IRBlock,
        avail_h: float,
        content_w: float,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> Tuple[Optional[IRBlock], Optional[IRBlock]]:
        full_h = self._full_content_height()
        total_h, _, _ = self._measure_block_height(b, metrics, font_reg, font_bold)

        # Regra keep-together: se a caixa cabe numa página inteira e não cabe no espaço atual -> mover inteira
        if total_h <= full_h and avail_h < total_h:
            return None, b

        if avail_h < 80.0:
            return None, b

        # Caixa superior a uma página inteira -> fragmentar de forma controlada mantendo título & estilo
        inner_w = content_w - 24.0
        header_txt = self._callout_header_text(b)
        title_h = metrics.measure_text_height(
            AcademicDesignSystem.sanitize_text_for_font(header_txt),
            fontname=font_bold,
            fontsize=self.typo.callout_title_pt,
            lineheight=1.22,
            max_width=inner_w,
        )
        overhead = 12.0 + title_h + 6.0 + 14.0
        body_budget = avail_h - overhead
        if body_budget < 28.0:
            return None, b

        fs = self.typo.callout_body_pt
        lh = 1.35

        def _measure_box_body(p_list: List[str], i_list: List[str]) -> float:
            body_txt = "\n\n".join(p_list)
            if i_list:
                body_txt += ("\n" if body_txt else "") + "\n".join(f"• {it}" for it in i_list)
            return metrics.measure_text_height(
                AcademicDesignSystem.sanitize_text_for_font(body_txt),
                fontname=font_reg, fontsize=fs, lineheight=lh, max_width=inner_w,
            )

        head_paras: List[str] = []
        tail_paras: List[str] = []
        head_items: List[str] = []
        tail_items: List[str] = []

        paras = list(b.paragraphs)
        items = list(b.items)

        # 1. Distribuir parágrafos da caixa
        broke_in_paras = False
        for idx, p in enumerate(paras):
            if _measure_box_body(head_paras + [p], []) <= body_budget:
                head_paras.append(p)
            else:
                used_so_far = _measure_box_body(head_paras, []) if head_paras else 0.0
                rem = body_budget - used_so_far - (fs * lh if head_paras else 0.0)
                if rem >= fs * lh * 1.8:
                    clean_p = AcademicDesignSystem.sanitize_text_for_font(p)
                    lines = metrics.wrap_text_lines(clean_p, font_reg, fs, inner_w)
                    fit_c = max(1, min(len(lines) - 1, int(rem / (fs * lh))))
                    while fit_c > 0:
                        chunk_cand = " ".join(ln for ln in lines[:fit_c] if ln).strip()
                        if _measure_box_body(head_paras + [chunk_cand], []) <= body_budget:
                            break
                        fit_c -= 1
                    if 1 <= fit_c < len(lines):
                        head_paras.append(" ".join(lines[:fit_c]).strip())
                        tail_paras.append(" ".join(lines[fit_c:]).strip())
                        tail_paras.extend(paras[idx + 1:])
                        tail_items.extend(items)
                        broke_in_paras = True
                        break
                tail_paras.extend(paras[idx:])
                tail_items.extend(items)
                broke_in_paras = True
                break

        # 2. Se todos os parágrafos couberam, distribuir itens da caixa
        if not broke_in_paras and items:
            for idx, it in enumerate(items):
                if _measure_box_body(head_paras, head_items + [it]) <= body_budget:
                    head_items.append(it)
                else:
                    tail_items.extend(items[idx:])
                    break

        if not head_paras and not head_items:
            return None, b
        if not tail_paras and not tail_items:
            return b, None

        base_id = b.block_id.split("__frag")[0]
        frag_num = b.block_id.count("__frag") + 1
        head_title = b.title or ""
        tail_title = f"{head_title} (Continuação)" if head_title and "(Continuação)" not in head_title else (head_title or "Continuação")
        head_blk = replace(
            b,
            block_id=f"{base_id}__frag{frag_num}",
            paragraphs=head_paras,
            items=head_items,
            provenance_summary="",
        )
        tail_blk = replace(
            b,
            block_id=f"{base_id}__fragcont{frag_num}",
            title=tail_title,
            paragraphs=tail_paras,
            items=tail_items,
            pagination=replace(b.pagination, page_break_before=False),
        )
        return head_blk, tail_blk

    def _split_table_block(
        self,
        b: IRBlock,
        avail_h: float,
        content_w: float,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> Tuple[Optional[IRBlock], Optional[IRBlock]]:
        title_h, hdr_h, row_heights, cap_h, _ = self._measure_table_layout(
            b, content_w, metrics, font_reg, font_bold
        )
        min_needed = title_h + hdr_h + (row_heights[0] if row_heights else 20.0) + 8.0
        if avail_h < min_needed:
            return None, b

        used = title_h + hdr_h + 6.0
        split_idx = 0
        for r_h in row_heights:
            if used + r_h <= avail_h - 4.0:
                used += r_h
                split_idx += 1
            else:
                break

        base_id = b.block_id.split("__frag")[0]
        frag_num = b.block_id.count("__frag") + 1

        if split_idx == 0:
            if avail_h >= self._full_content_height() * 0.85 and b.table_rows:
                row0 = list(b.table_rows[0])
                max_cell_chars = max((len(str(c)) for c in row0), default=0)
                if max_cell_chars > 120:
                    head_r = [str(c)[: len(str(c)) // 2] for c in row0]
                    tail_r = [str(c)[len(str(c)) // 2 :] for c in row0]
                    head_blk = replace(
                        b,
                        block_id=f"{base_id}__frag{frag_num}",
                        table_rows=[head_r],
                        caption="",
                        provenance_summary="",
                    )
                    tail_title = f"{b.title} (Continuação)" if b.title and "(Continuação)" not in b.title else b.title
                    tail_blk = replace(
                        b,
                        block_id=f"{base_id}__fragcont{frag_num}",
                        title=tail_title,
                        table_rows=[tail_r] + list(b.table_rows[1:]),
                    )
                    return head_blk, tail_blk
            return None, b

        if split_idx >= len(b.table_rows):
            if used + cap_h <= avail_h:
                return b, None
            if len(b.table_rows) > 1:
                split_idx = len(b.table_rows) - 1
            else:
                return None, b

        head_blk = replace(
            b,
            block_id=f"{base_id}__frag{frag_num}",
            table_rows=list(b.table_rows[:split_idx]),
            caption="",
            provenance_summary="",
        )
        tail_title = (
            f"{b.title} (Continuação)" if b.title and "(Continuação)" not in b.title else b.title
        )
        tail_blk = replace(
            b,
            block_id=f"{base_id}__fragcont{frag_num}",
            title=tail_title,
            table_rows=list(b.table_rows[split_idx:]),
            pagination=replace(b.pagination, page_break_before=False),
        )
        return head_blk, tail_blk

    # -----------------------------------------------------------------------
    # Planeamento de Paginação em Duas Passagens (Passagem 1)
    # -----------------------------------------------------------------------

    def _plan_pagination(
        self,
        blocks: List[IRBlock],
        metrics: _TypographicMetrics,
        start_page_num: int,
        font_reg: str,
        font_bold: str,
        font_italic: str,
        font_mono: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, pymupdf.Rect]]:
        pages_plan: List[Dict[str, Any]] = []
        block_to_page: Dict[str, int] = {}
        block_to_rect: Dict[str, pymupdf.Rect] = {}

        current_page_num = start_page_num
        current_y = self.geo.margin_top_pt
        current_chapter_title = ""
        current_page_blocks: List[Dict[str, Any]] = []

        content_w = self.geo.content_width_pt
        margin_x = self.geo.margin_left_pt
        full_h = self._full_content_height()

        queue: List[IRBlock] = list(blocks)
        safety_iters = max(2000, len(queue) * 60)
        iter_count = 0

        def _flush_page() -> None:
            nonlocal current_page_num, current_page_blocks, current_y
            if current_page_blocks:
                pages_plan.append({
                    "page_number": current_page_num,
                    "chapter_title": current_chapter_title,
                    "blocks": current_page_blocks,
                })
                current_page_num += 1
                current_page_blocks = []
                current_y = self.geo.margin_top_pt

        while queue and iter_count < safety_iters:
            iter_count += 1
            b = queue.pop(0)

            b_height, space_before, space_after = self._measure_block_height(
                b, metrics, font_reg, font_bold, font_italic, font_mono
            )

            force_break = b.pagination.page_break_before and (len(current_page_blocks) > 0)
            if force_break:
                _flush_page()

            # Controlo de órfãs para títulos (`keep_with_next`)
            if b.pagination.keep_with_next and current_page_blocks:
                min_follow = b.pagination.min_follow_height_pt or self.geo.min_heading_follow_pt
                if current_y + space_before + b_height + min_follow > self.geo.max_content_y_pt:
                    _flush_page()

            avail_h = self.geo.max_content_y_pt - (current_y + space_before)

            # Verificar se bloco cabe no espaço restante da página
            if b_height > avail_h:
                is_divisible = b.kind in (
                    IRBlockKind.PARAGRAPH.value,
                    IRBlockKind.BULLET_LIST.value,
                    IRBlockKind.NUMBERED_LIST.value,
                    IRBlockKind.CALLOUT_BOX.value,
                    IRBlockKind.TABLE.value,
                )

                if is_divisible:
                    head_b, tail_b = self._split_block_for_space(b, avail_h, metrics, font_reg, font_bold)
                    if head_b is None:
                        # Não coube neste resto de página -> abrir nova página se esta já tem blocos
                        if current_page_blocks:
                            _flush_page()
                            queue.insert(0, b)
                            continue
                        # Já estamos numa página vazia e bloco excede `full_h`: tentar dividir na página cheia
                        head_b, tail_b = self._split_block_for_space(b, full_h, metrics, font_reg, font_bold)
                    if head_b is not None:
                        b = head_b
                        if tail_b is not None:
                            queue.insert(0, tail_b)
                        b_height, space_before, space_after = self._measure_block_height(
                            b, metrics, font_reg, font_bold, font_italic, font_mono
                        )
                else:
                    # Bloco indivisível (heading curto, visual+legenda, equação)
                    if current_page_blocks:
                        _flush_page()
                        queue.insert(0, b)
                        continue
                    # Mesmo numa página vazia: garantir que altura alocada nunca excede `full_h`
                    b_height = min(b_height, full_h)

            if current_page_blocks and (current_y + space_before + b_height > self.geo.max_content_y_pt):
                _flush_page()

            current_y += space_before
            # Clamp final estrito à área útil (com fragmentação prévia garante-se não haver perda)
            alloc_h = min(b_height, max(16.0, self.geo.max_content_y_pt - current_y))
            rect = pymupdf.Rect(margin_x, current_y, margin_x + content_w, current_y + alloc_h)

            base_id = b.block_id.split("__frag")[0]
            if base_id not in block_to_page:
                block_to_page[base_id] = current_page_num
                block_to_rect[base_id] = rect
            if b.block_id not in block_to_page:
                block_to_page[b.block_id] = current_page_num
                block_to_rect[b.block_id] = rect

            if b.kind == IRBlockKind.HEADING.value and b.level == 1:
                current_chapter_title = b.title

            current_page_blocks.append({
                "block": b,
                "rect": rect,
            })
            current_y += alloc_h + space_after

        if current_page_blocks:
            _flush_page()

        return pages_plan, block_to_page, block_to_rect

    # -----------------------------------------------------------------------
    # Frontmatter Multi-Página (Capa + Todos Objetivos + Todo Índice)
    # -----------------------------------------------------------------------

    def _render_frontmatter_pages(
        self,
        *,
        doc: Optional[pymupdf.Document],
        fonts_dict: Dict[str, Optional[str]],
        metrics: _TypographicMetrics,
        ir: StudyDocumentIR,
        block_to_page: Dict[str, int],
        font_reg: str,
        font_bold: str,
        dry_run: bool,
    ) -> Dict[str, Any]:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_secondary = hex_to_rgb_float(self.profile.secondary_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        c_accent = hex_to_rgb_float(self.profile.accent_hex)

        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt
        max_y = self.geo.max_content_y_pt - 6.0

        pages_count = 1
        toc_links: List[Tuple[int, pymupdf.Rect, str]] = []
        current_page: Optional[pymupdf.Page] = None
        if not dry_run and doc is not None:
            current_page = self._create_page_with_fonts(doc, fonts_dict)

        def _new_fm_page() -> None:
            nonlocal pages_count, current_page
            pages_count += 1
            if not dry_run and doc is not None:
                current_page = self._create_page_with_fonts(doc, fonts_dict)
                self._render_running_header(current_page, ir, "Índice & Objetivos", font_reg, metrics)

        # --- 1. Cabeçalho da Capa ---
        if current_page is not None:
            top_rect = pymupdf.Rect(margin_x, 30, margin_x + content_w, 42)
            shape = current_page.new_shape()
            shape.draw_rect(top_rect)
            shape.finish(color=c_primary, fill=c_primary)
            shape.commit()
            current_page.insert_text(
                pymupdf.Point(margin_x, 60),
                "JARVIS OS • STUDY ENGINE — CADERNO ACADÉMICO DE ESTUDO",
                fontname=font_bold,
                fontsize=8.5,
                color=c_secondary,
            )

        clean_title = AcademicDesignSystem.sanitize_text_for_font(ir.metadata.title)
        title_h = metrics.measure_text_height(
            clean_title, fontname=font_bold, fontsize=self.typo.doc_title_pt, lineheight=1.2, max_width=content_w
        )
        title_y0 = 72.0
        title_rect = pymupdf.Rect(margin_x, title_y0, margin_x + content_w, title_y0 + title_h + 2.0)
        if current_page is not None:
            self._safe_insert_textbox(
                current_page, title_rect, clean_title,
                fontname=font_bold, fontsize=self.typo.doc_title_pt, color=c_primary,
                lineheight=1.2, metrics=metrics, block_id="cover_title",
            )

        sub_y0 = title_rect.y1 + 4.0
        clean_sub = AcademicDesignSystem.sanitize_text_for_font(ir.metadata.subtitle)
        sub_h = metrics.measure_text_height(
            clean_sub, fontname=font_reg, fontsize=self.typo.doc_subtitle_pt, lineheight=1.22, max_width=content_w
        )
        sub_rect = pymupdf.Rect(margin_x, sub_y0, margin_x + content_w, sub_y0 + sub_h + 2.0)
        if current_page is not None and clean_sub:
            self._safe_insert_textbox(
                current_page, sub_rect, clean_sub,
                fontname=font_reg, fontsize=self.typo.doc_subtitle_pt, color=c_secondary,
                lineheight=1.22, metrics=metrics, block_id="cover_subtitle",
            )

        # Autores e Metadados completos (sem [:4] ou [:40])
        author_parts = []
        if ir.metadata.authors:
            author_parts.append(f"Autores originais: {', '.join(ir.metadata.authors)}")
        if ir.metadata.year:
            author_parts.append(f"Ano: {ir.metadata.year}")
        if ir.metadata.publication_venue:
            author_parts.append(f"Publicação: {ir.metadata.publication_venue}")
        author_line = " • ".join(author_parts) if author_parts else "Documento Científico Analisado"
        clean_auth = AcademicDesignSystem.sanitize_text_for_font(author_line)
        auth_h = metrics.measure_text_height(
            clean_auth, fontname=font_reg, fontsize=8.5, lineheight=1.25, max_width=content_w
        )
        auth_y0 = sub_rect.y1 + 2.0
        auth_rect = pymupdf.Rect(margin_x, auth_y0, margin_x + content_w, auth_y0 + auth_h + 2.0)
        if current_page is not None:
            self._safe_insert_textbox(
                current_page, auth_rect, clean_auth,
                fontname=font_reg, fontsize=8.5, color=c_muted,
                lineheight=1.25, metrics=metrics, block_id="cover_authors",
            )

        line_y = auth_rect.y1 + 6.0
        if current_page is not None:
            shape = current_page.new_shape()
            shape.draw_line(pymupdf.Point(margin_x, line_y), pymupdf.Point(margin_x + content_w, line_y))
            shape.finish(color=c_border, width=1.5)
            shape.commit()

        # --- 2. TODOS os Objetivos de Aprendizagem (multi-página se necessário) ---
        cur_y = line_y + 12.0
        objs = list(ir.learning_objectives or [])
        if objs:
            inner_w = content_w - 28.0
            obj_heights = [
                metrics.measure_text_height(
                    AcademicDesignSystem.sanitize_text_for_font(f"• {obj_txt}"),
                    fontname=font_reg,
                    fontsize=8.8,
                    lineheight=1.3,
                    max_width=inner_w,
                ) + 4.0
                for obj_txt in objs
            ]

            idx = 0
            chunk_num = 1
            while idx < len(objs):
                header_title = (
                    "OBJETIVOS DE APRENDIZAGEM & ROTEIRO EDITORIAL"
                    if chunk_num == 1
                    else "OBJETIVOS DE APRENDIZAGEM (Continuação)"
                )
                header_h = 26.0
                if cur_y + header_h + obj_heights[idx] + 10.0 > max_y:
                    _new_fm_page()
                    cur_y = self.geo.margin_top_pt

                avail_for_items = max_y - cur_y - header_h - 10.0
                acc_h = 0.0
                chunk_indices: List[int] = []
                while idx < len(objs) and (acc_h + obj_heights[idx] <= avail_for_items or not chunk_indices):
                    chunk_indices.append(idx)
                    acc_h += obj_heights[idx]
                    idx += 1

                box_h = min(max_y - cur_y, header_h + acc_h + 10.0)
                if current_page is not None:
                    box_rect = pymupdf.Rect(margin_x, cur_y, margin_x + content_w, cur_y + box_h)
                    shape = current_page.new_shape()
                    shape.draw_rect(box_rect)
                    shape.finish(color=c_primary, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1.5)
                    shape.draw_rect(pymupdf.Rect(margin_x, cur_y, margin_x + 5, cur_y + box_h))
                    shape.finish(color=c_primary, fill=c_primary)
                    shape.commit()

                    current_page.insert_text(
                        pymupdf.Point(margin_x + 16, cur_y + 18),
                        header_title,
                        fontname=font_bold,
                        fontsize=9.0,
                        color=c_primary,
                    )
                    o_y = cur_y + 28.0
                    for oi in chunk_indices:
                        clean_obj = AcademicDesignSystem.sanitize_text_for_font(f"• {objs[oi]}")
                        oh = obj_heights[oi]
                        o_rect = pymupdf.Rect(margin_x + 16, o_y, margin_x + content_w - 12, o_y + oh)
                        self._safe_insert_textbox(
                            current_page, o_rect, clean_obj,
                            fontname=font_reg, fontsize=8.8, color=c_text,
                            lineheight=1.3, metrics=metrics, block_id=f"cover_obj_{oi}",
                        )
                        o_y += oh

                cur_y += box_h + 16.0
                chunk_num += 1

        # --- 3. TODO o Índice Geral (multi-página se necessário) ---
        if cur_y + 52.0 > max_y:
            _new_fm_page()
            cur_y = self.geo.margin_top_pt

        if current_page is not None:
            current_page.insert_text(
                pymupdf.Point(margin_x, cur_y + 12),
                "ÍNDICE GERAL DE CONTEÚDOS",
                fontname=font_bold,
                fontsize=12.0,
                color=c_primary,
            )
        cur_y += 24.0

        for e_idx, entry in enumerate(ir.toc_entries):
            is_ch = (entry.level == 1)
            indent = 0.0 if is_ch else 16.0
            f_name = font_bold if is_ch else font_reg
            f_size = self.typo.toc_chapter_pt if is_ch else self.typo.toc_section_pt
            color = c_primary if is_ch else c_text

            line_txt = f"{entry.number_label} — {entry.title}"
            clean_entry = AcademicDesignSystem.sanitize_text_for_font(line_txt)
            label_w = max(80.0, content_w - indent - 46.0)
            entry_h = max(
                15.0 if not is_ch else 17.0,
                metrics.measure_text_height(
                    clean_entry, fontname=f_name, fontsize=f_size, lineheight=1.22, max_width=label_w
                ) + 2.0,
            )

            if cur_y + entry_h > max_y:
                _new_fm_page()
                cur_y = self.geo.margin_top_pt
                if current_page is not None:
                    current_page.insert_text(
                        pymupdf.Point(margin_x, cur_y + 10),
                        "ÍNDICE GERAL DE CONTEÚDOS (Continuação)",
                        fontname=font_bold,
                        fontsize=11.0,
                        color=c_primary,
                    )
                cur_y += 22.0

            if current_page is not None:
                entry_rect = pymupdf.Rect(margin_x + indent, cur_y, margin_x + indent + label_w, cur_y + entry_h)
                self._safe_insert_textbox(
                    current_page, entry_rect, clean_entry,
                    fontname=f_name, fontsize=f_size, color=color,
                    lineheight=1.22, metrics=metrics, block_id=f"toc_{entry.entry_id}",
                )

                target_pg = block_to_page.get(entry.target_block_id, pages_count + 1)
                pg_str = f"p. {target_pg}"
                pg_w = metrics.text_width(pg_str, font_bold if is_ch else font_reg, f_size)
                pg_x = margin_x + content_w - pg_w - 2.0
                current_page.insert_text(
                    pymupdf.Point(pg_x, cur_y + f_size),
                    pg_str,
                    fontname=font_bold if is_ch else font_reg,
                    fontsize=f_size,
                    color=c_accent if is_ch else c_muted,
                )

                first_line = metrics.wrap_text_lines(clean_entry, f_name, f_size, label_w)[0]
                first_w = metrics.text_width(first_line, f_name, f_size)
                dots_x0 = margin_x + indent + first_w + 8.0
                dots_x1 = pg_x - 8.0
                if dots_x1 > dots_x0 + 12.0:
                    shape = current_page.new_shape()
                    shape.draw_line(pymupdf.Point(dots_x0, cur_y + f_size * 0.8), pymupdf.Point(dots_x1, cur_y + f_size * 0.8))
                    shape.finish(color=c_border, width=0.5)
                    shape.commit()

                link_rect = pymupdf.Rect(margin_x, cur_y, margin_x + content_w, cur_y + entry_h)
                toc_links.append((pages_count - 1, link_rect, entry.target_block_id))

            cur_y += entry_h + (2.0 if is_ch else 1.0)

        return {"pages_count": pages_count, "toc_links": toc_links}

    # -----------------------------------------------------------------------
    # Cabeçalhos, Rodapés & Blocos de Conteúdo
    # -----------------------------------------------------------------------

    def _render_running_header(
        self,
        page: pymupdf.Page,
        ir: StudyDocumentIR,
        chapter_title: str,
        font_reg: str,
        metrics: Optional[_TypographicMetrics] = None,
    ) -> None:
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt
        fs = self.typo.header_footer_pt

        left_txt = AcademicDesignSystem.sanitize_text_for_font(ir.header_footer.running_header_left)
        page.insert_text(
            pymupdf.Point(margin_x, self.geo.header_y_pt),
            left_txt,
            fontname=font_reg,
            fontsize=fs,
            color=c_muted,
        )

        r_raw = AcademicDesignSystem.sanitize_text_for_font(
            chapter_title if chapter_title else ir.header_footer.running_header_right
        )
        max_r_w = content_w * 0.55
        if metrics is not None:
            while r_raw and metrics.text_width(r_raw, font_reg, fs) > max_r_w:
                r_raw = r_raw[:-4].rstrip() + "..."
            r_w = metrics.text_width(r_raw, font_reg, fs)
        else:
            r_raw = r_raw[:45]
            r_w = len(r_raw) * 4.5
        r_x = max(margin_x + content_w * 0.42, margin_x + content_w - r_w)
        page.insert_text(
            pymupdf.Point(r_x, self.geo.header_y_pt),
            r_raw,
            fontname=font_reg,
            fontsize=fs,
            color=c_muted,
        )

        shape = page.new_shape()
        shape.draw_line(
            pymupdf.Point(margin_x, self.geo.header_y_pt + 6),
            pymupdf.Point(margin_x + content_w, self.geo.header_y_pt + 6),
        )
        shape.finish(color=c_border, width=0.8)
        shape.commit()

    def _render_running_footer(
        self,
        page: pymupdf.Page,
        ir: StudyDocumentIR,
        page_num: int,
        total_pages: int,
        font_reg: str,
        metrics: Optional[_TypographicMetrics] = None,
    ) -> None:
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt
        fs = self.typo.header_footer_pt

        shape = page.new_shape()
        shape.draw_line(
            pymupdf.Point(margin_x, self.geo.footer_y_pt - 10),
            pymupdf.Point(margin_x + content_w, self.geo.footer_y_pt - 10),
        )
        shape.finish(color=c_border, width=0.8)
        shape.commit()

        page.insert_text(
            pymupdf.Point(margin_x, self.geo.footer_y_pt + 2),
            AcademicDesignSystem.sanitize_text_for_font(ir.header_footer.footer_left),
            fontname=font_reg,
            fontsize=fs,
            color=c_muted,
        )

        pg_str = f"Página {page_num} de {total_pages}"
        pg_w = metrics.text_width(pg_str, font_reg, fs) if metrics else 72.0
        page.insert_text(
            pymupdf.Point(margin_x + content_w - pg_w - 2.0, self.geo.footer_y_pt + 2),
            pg_str,
            fontname=font_reg,
            fontsize=fs,
            color=c_muted,
        )

    def _render_block(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
        font_italic: str,
        font_mono: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_secondary = hex_to_rgb_float(self.profile.secondary_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)

        if block.kind == IRBlockKind.HEADING.value:
            f_size = self.typo.chapter_title_pt if block.level == 1 else (
                self.typo.section_title_pt if block.level == 2 else self.typo.subsection_title_pt
            )
            color = c_primary if block.level == 1 else c_secondary
            clean_heading = AcademicDesignSystem.sanitize_text_for_font(block.title)
            self._safe_insert_textbox(
                page, rect, clean_heading,
                fontname=font_bold, fontsize=f_size, color=color,
                lineheight=1.22, metrics=metrics, block_id=block.block_id, context="heading",
            )

        elif block.kind == IRBlockKind.PARAGRAPH.value:
            prov_h = self._measure_provenance_footer_height(block, metrics, font_reg, rect.width)
            body_rect = pymupdf.Rect(rect.x0, rect.y0, rect.x1, max(rect.y0 + 14.0, rect.y1 - prov_h))
            full_text = "\n\n".join(block.paragraphs)
            clean_para = AcademicDesignSystem.sanitize_text_for_font(full_text)
            self._safe_insert_textbox(
                page, body_rect, clean_para,
                fontname=font_reg, fontsize=self.typo.body_pt, color=c_text,
                lineheight=self.typo.body_line_height_factor, metrics=metrics,
                block_id=block.block_id, context="paragraph",
            )
            if prov_h > 0:
                self._render_provenance_footer_line(page, block, rect.x0, rect.y1 - prov_h + 1.0, rect.width, font_reg, metrics)

        elif block.kind in (IRBlockKind.BULLET_LIST.value, IRBlockKind.NUMBERED_LIST.value):
            prov_h = self._measure_provenance_footer_height(block, metrics, font_reg, rect.width)
            list_rect = pymupdf.Rect(rect.x0 + 6.0, rect.y0, rect.x1 - 2.0, max(rect.y0 + 14.0, rect.y1 - prov_h))
            start_num = int(getattr(block, "level", 0) or 1) if block.kind == IRBlockKind.NUMBERED_LIST.value else 1
            items_str = "\n".join(
                f"• {it}" if block.kind == IRBlockKind.BULLET_LIST.value else f"{start_num + i}. {it}"
                for i, it in enumerate(block.items)
            )
            clean_list = AcademicDesignSystem.sanitize_text_for_font(items_str)
            self._safe_insert_textbox(
                page, list_rect, clean_list,
                fontname=font_reg, fontsize=self.typo.body_pt, color=c_text,
                lineheight=1.36, metrics=metrics, block_id=block.block_id, context="list",
            )
            if prov_h > 0:
                self._render_provenance_footer_line(page, block, rect.x0, rect.y1 - prov_h + 1.0, rect.width, font_reg, metrics)

        elif block.kind == IRBlockKind.CALLOUT_BOX.value:
            self._render_callout_box(page, block, rect, metrics, font_reg, font_bold)

        elif block.kind == IRBlockKind.TABLE.value:
            self._render_table_on_page(page, block, rect, metrics, font_reg, font_bold)

        elif block.kind == IRBlockKind.VISUAL_ELEMENT.value:
            self._render_visual_image_on_page(page, block, rect, metrics, font_reg, font_bold)

        elif block.kind == IRBlockKind.EQUATION.value:
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=c_border, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1)
            shape.commit()
            eq_txt = block.equation_latex or block.equation_raw or "[Equação]"
            self._safe_insert_textbox(
                page,
                pymupdf.Rect(rect.x0 + 10, rect.y0 + 6, rect.x1 - 10, rect.y1 - 6),
                eq_txt,
                fontname=font_mono,
                fontsize=self.typo.equation_pt,
                color=c_primary,
                align=pymupdf.TEXT_ALIGN_CENTER,
                metrics=metrics,
                block_id=block.block_id,
                context="equation",
            )

    def _render_provenance_footer_line(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        x0: float,
        y0: float,
        width: float,
        font_reg: str,
        metrics: _TypographicMetrics,
    ) -> None:
        prov_txt = self._provenance_display_text(block)
        if not prov_txt:
            return
        _, ep_accent_hex, _ = self.profile.get_epistemic_style(
            block.epistemic_status, block.is_hypothetical_example
        )
        c_ep = hex_to_rgb_float(ep_accent_hex)
        h = metrics.measure_text_height(
            prov_txt, fontname=font_reg, fontsize=self.typo.provenance_pt, lineheight=1.22, max_width=width
        ) + 2.0
        p_rect = pymupdf.Rect(x0, y0, x0 + width, min(self.geo.max_content_y_pt, y0 + h))
        self._safe_insert_textbox(
            page, p_rect, prov_txt,
            fontname=font_reg, fontsize=self.typo.provenance_pt, color=c_ep,
            lineheight=1.22, metrics=metrics, block_id=block.block_id, context="provenance",
        )

    def _render_callout_box(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> None:
        theme = self.profile.get_callout_theme(block.callout_kind)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        # Se a caixa for INFERÊNCIA / UNVERIFIED, nunca usar bordadura verde factual
        ep_st = normalize_epistemic_status(block.epistemic_status, default="UNVERIFIED")
        _, ep_accent_hex, ep_bg_hex = self.profile.get_epistemic_style(ep_st, block.is_hypothetical_example)

        if block.is_hypothetical_example or ep_st in ("UNVERIFIED", "NOT_FOUND"):
            c_box_border = hex_to_rgb_float(ep_accent_hex)
            c_box_bg = hex_to_rgb_float(ep_bg_hex)
            c_box_title = hex_to_rgb_float(ep_accent_hex)
        elif ep_st == "MODEL_INFERENCE":
            c_box_border = hex_to_rgb_float(theme.border_hex if theme.border_hex != self.profile.fact_accent_hex else ep_accent_hex)
            c_box_bg = hex_to_rgb_float(theme.background_hex if theme.background_hex != self.profile.fact_bg_hex else ep_bg_hex)
            c_box_title = hex_to_rgb_float(theme.title_hex if theme.title_hex != self.profile.fact_accent_hex else ep_accent_hex)
        else:
            c_box_border = hex_to_rgb_float(theme.border_hex)
            c_box_bg = hex_to_rgb_float(theme.background_hex)
            c_box_title = hex_to_rgb_float(theme.title_hex)

        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=c_box_border, fill=c_box_bg, width=1.5)
        shape.draw_rect(pymupdf.Rect(rect.x0, rect.y0, rect.x0 + 5, rect.y1))
        shape.finish(color=c_box_border, fill=c_box_border)
        shape.commit()

        inner_w = max(40.0, rect.width - 24.0)
        header_txt = AcademicDesignSystem.sanitize_text_for_font(self._callout_header_text(block))
        title_h = metrics.measure_text_height(
            header_txt, fontname=font_bold, fontsize=self.typo.callout_title_pt, lineheight=1.22, max_width=inner_w
        )
        title_rect = pymupdf.Rect(rect.x0 + 14, rect.y0 + 8, rect.x1 - 10, rect.y0 + 10 + title_h)
        self._safe_insert_textbox(
            page, title_rect, header_txt,
            fontname=font_bold, fontsize=self.typo.callout_title_pt, color=c_box_title,
            lineheight=1.22, metrics=metrics, block_id=block.block_id, context="callout_title",
        )

        prov_h = self._measure_provenance_footer_height(block, metrics, font_reg, inner_w)
        body_y0 = title_rect.y1 + 4.0
        body_y1 = max(body_y0 + 14.0, rect.y1 - (prov_h + 6.0 if prov_h else 6.0))

        content_text = "\n\n".join(block.paragraphs)
        if block.items:
            content_text += ("\n" if content_text else "") + "\n".join(f"• {it}" for it in block.items)
        clean_c = AcademicDesignSystem.sanitize_text_for_font(content_text)
        body_rect = pymupdf.Rect(rect.x0 + 14, body_y0, rect.x1 - 10, body_y1)
        self._safe_insert_textbox(
            page, body_rect, clean_c,
            fontname=font_reg, fontsize=self.typo.callout_body_pt, color=c_text,
            lineheight=1.35, metrics=metrics, block_id=block.block_id, context="callout_body",
        )

        if prov_h > 0:
            self._render_provenance_footer_line(page, block, rect.x0 + 14, body_y1 + 2.0, inner_w, font_reg, metrics)

    def _render_table_on_page(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        c_zebra = hex_to_rgb_float(self.profile.surface_zebra_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)

        title_h, hdr_h, row_heights, cap_h, col_w = self._measure_table_layout(
            block, rect.width, metrics, font_reg, font_bold
        )
        cols_count = max(1, len(block.table_headers) or (len(block.table_rows[0]) if block.table_rows else 1))

        cur_y = rect.y0
        if block.title:
            t_str = AcademicDesignSystem.sanitize_text_for_font(f"Tabela: {block.title}")
            t_rect = pymupdf.Rect(rect.x0, cur_y, rect.x1, cur_y + title_h)
            self._safe_insert_textbox(
                page, t_rect, t_str,
                fontname=font_bold, fontsize=9.5, color=c_primary,
                lineheight=1.22, metrics=metrics, block_id=block.block_id, context="table_title",
            )
            cur_y += title_h

        # Cabeçalho da Tabela (sem truncagem `[:30]`)
        if block.table_headers:
            h_rect = pymupdf.Rect(rect.x0, cur_y, rect.x1, cur_y + hdr_h)
            shape = page.new_shape()
            shape.draw_rect(h_rect)
            shape.finish(color=c_primary, fill=c_primary)
            shape.commit()

            for c_i, header_txt in enumerate(block.table_headers):
                clean_h = AcademicDesignSystem.sanitize_text_for_font(str(header_txt))
                cell_rect = pymupdf.Rect(
                    rect.x0 + c_i * col_w + 5.0,
                    cur_y + 4.0,
                    rect.x0 + (c_i + 1) * col_w - 5.0,
                    cur_y + hdr_h - 2.0,
                )
                self._safe_insert_textbox(
                    page, cell_rect, clean_h,
                    fontname=font_bold, fontsize=self.typo.table_header_pt, color=(1.0, 1.0, 1.0),
                    lineheight=1.22, metrics=metrics, block_id=block.block_id, context="table_header",
                )
            cur_y += hdr_h

        # Linhas de Dados com envolvimento automático (sem `[:38]`)
        for r_i, row in enumerate(block.table_rows):
            r_h = row_heights[r_i]
            fill_c = c_zebra if (r_i % 2 == 1) else (1.0, 1.0, 1.0)
            r_box = pymupdf.Rect(rect.x0, cur_y, rect.x1, cur_y + r_h)
            shape = page.new_shape()
            shape.draw_rect(r_box)
            shape.finish(color=c_border, fill=fill_c, width=0.5)
            shape.commit()

            for c_i in range(cols_count):
                val = str(row[c_i]) if c_i < len(row) else ""
                clean_val = AcademicDesignSystem.sanitize_text_for_font(val)
                if clean_val:
                    cell_rect = pymupdf.Rect(
                        rect.x0 + c_i * col_w + 5.0,
                        cur_y + 4.0,
                        rect.x0 + (c_i + 1) * col_w - 5.0,
                        cur_y + r_h - 2.0,
                    )
                    self._safe_insert_textbox(
                        page, cell_rect, clean_val,
                        fontname=font_reg, fontsize=self.typo.table_cell_pt, color=c_text,
                        lineheight=1.25, metrics=metrics, block_id=block.block_id, context=f"table_row_{r_i}",
                    )
            cur_y += r_h

        # Legenda e Proveniência
        cap_parts: List[str] = []
        if block.caption:
            cap_parts.append(AcademicDesignSystem.sanitize_text_for_font(block.caption))
        prov_txt = self._provenance_display_text(block)
        if prov_txt:
            cap_parts.append(prov_txt)
        if cap_parts:
            cap_rect = pymupdf.Rect(rect.x0, cur_y + 2.0, rect.x1, min(self.geo.max_content_y_pt, cur_y + cap_h + 4.0))
            _, ep_accent_hex, _ = self.profile.get_epistemic_style(block.epistemic_status, block.is_hypothetical_example)
            self._safe_insert_textbox(
                page, cap_rect, "\n".join(cap_parts),
                fontname=font_reg, fontsize=self.typo.caption_pt,
                color=hex_to_rgb_float(ep_accent_hex) if prov_txt else c_muted,
                lineheight=1.22, metrics=metrics, block_id=block.block_id, context="table_caption",
            )

    def _render_visual_image_on_page(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        metrics: _TypographicMetrics,
        font_reg: str,
        font_bold: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)

        title_h = 0.0
        if block.title:
            t_str = AcademicDesignSystem.sanitize_text_for_font(f"Figura: {block.title}")
            title_h = metrics.measure_text_height(
                t_str, fontname=font_bold, fontsize=9.5, lineheight=1.2, max_width=rect.width
            ) + 4.0
            self._safe_insert_textbox(
                page, pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + title_h), t_str,
                fontname=font_bold, fontsize=9.5, color=c_primary,
                lineheight=1.2, metrics=metrics, block_id=block.block_id, context="visual_title",
            )

        prov_h = self._measure_provenance_footer_height(block, metrics, font_reg, rect.width)
        caption_h = 0.0
        if block.caption:
            clean_cap = AcademicDesignSystem.sanitize_text_for_font(f"Legenda: {block.caption}")
            caption_h = metrics.measure_text_height(
                clean_cap, fontname=font_reg, fontsize=self.typo.caption_pt, lineheight=1.25, max_width=rect.width
            ) + 4.0

        img_y0 = rect.y0 + title_h
        img_y1 = max(img_y0 + 40.0, rect.y1 - caption_h - prov_h)
        img_rect = pymupdf.Rect(rect.x0, img_y0, rect.x1, img_y1)

        if block.image_path and os.path.exists(block.image_path):
            try:
                page.insert_image(img_rect, filename=block.image_path, keep_proportion=True)
            except Exception:
                shape = page.new_shape()
                shape.draw_rect(img_rect)
                shape.finish(color=c_border, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1)
                shape.commit()
                self._safe_insert_textbox(
                    page, img_rect, "[Elemento Visual Incorporado]",
                    fontname=font_bold, fontsize=10, color=c_muted,
                    metrics=metrics, block_id=block.block_id, context="visual_fallback",
                )

        if block.caption:
            cap_rect = pymupdf.Rect(rect.x0, img_y1 + 2.0, rect.x1, img_y1 + caption_h + 2.0)
            clean_cap = AcademicDesignSystem.sanitize_text_for_font(f"Legenda: {block.caption}")
            self._safe_insert_textbox(
                page, cap_rect, clean_cap,
                fontname=font_reg, fontsize=self.typo.caption_pt, color=c_muted,
                lineheight=1.25, metrics=metrics, block_id=block.block_id, context="visual_caption",
            )

        if prov_h > 0:
            self._render_provenance_footer_line(
                page, block, rect.x0, img_y1 + caption_h + 2.0, rect.width, font_reg, metrics
            )

    # -----------------------------------------------------------------------
    # Backmatter Multi-Página: Bibliografia & Declaração de Proveniência
    # -----------------------------------------------------------------------

    def _render_bibliography_pages(
        self,
        *,
        doc: pymupdf.Document,
        fonts_dict: Dict[str, Optional[str]],
        metrics: _TypographicMetrics,
        ir: StudyDocumentIR,
        font_reg: str,
        font_bold: str,
        font_italic: str,
    ) -> int:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt
        max_y = self.geo.max_content_y_pt - 4.0

        pages_added = 0

        def _open_bib_page(is_first: bool) -> Tuple[pymupdf.Page, float]:
            nonlocal pages_added
            pages_added += 1
            p = self._create_page_with_fonts(doc, fonts_dict)
            self._render_running_header(p, ir, "Referências Bibliográficas & Proveniência", font_reg, metrics)
            title = (
                "REFERÊNCIAS BIBLIOGRÁFICAS & DECLARAÇÃO DE PROVENIÊNCIA"
                if is_first
                else "REFERÊNCIAS BIBLIOGRÁFICAS (Continuação)"
            )
            p.insert_text(pymupdf.Point(margin_x, self.geo.margin_top_pt + 10), title, fontname=font_bold, fontsize=12.5, color=c_primary)
            shape = p.new_shape()
            shape.draw_line(
                pymupdf.Point(margin_x, self.geo.margin_top_pt + 18),
                pymupdf.Point(margin_x + content_w, self.geo.margin_top_pt + 18),
            )
            shape.finish(color=c_border, width=1.5)
            shape.commit()
            return p, self.geo.margin_top_pt + 30.0

        page, cur_y = _open_bib_page(is_first=True)

        # Renderizar TODAS as referências bibliográficas sem limite `[:14]`
        for b_idx, b_entry in enumerate(ir.bibliography):
            ref_str = f"{b_entry.citation_label} {b_entry.formatted_reference}"
            if b_entry.metadata_limitation_note:
                ref_str += f" — {b_entry.metadata_limitation_note}"
            clean_ref = AcademicDesignSystem.sanitize_text_for_font(ref_str)
            r_h = metrics.measure_text_height(
                clean_ref, fontname=font_reg, fontsize=8.8, lineheight=1.28, max_width=content_w
            ) + 4.0
            if cur_y + r_h > max_y:
                page, cur_y = _open_bib_page(is_first=False)

            r_rect = pymupdf.Rect(margin_x, cur_y, margin_x + content_w, cur_y + r_h)
            self._safe_insert_textbox(
                page, r_rect, clean_ref,
                fontname=font_reg, fontsize=8.8, color=c_text,
                lineheight=1.28, metrics=metrics, block_id=f"bib_{b_idx}", context="bibliography",
            )
            cur_y += r_h + 4.0

        # Notas de proveniência adicionais da IR
        for n_idx, note_txt in enumerate(ir.provenance_summary_notes):
            clean_n = AcademicDesignSystem.sanitize_text_for_font(f"• {note_txt}")
            n_h = metrics.measure_text_height(
                clean_n, fontname=font_reg, fontsize=8.4, lineheight=1.25, max_width=content_w
            ) + 3.0
            if cur_y + n_h > max_y:
                page, cur_y = _open_bib_page(is_first=False)
            n_rect = pymupdf.Rect(margin_x, cur_y, margin_x + content_w, cur_y + n_h)
            self._safe_insert_textbox(
                page, n_rect, clean_n,
                fontname=font_reg, fontsize=8.4, color=c_muted,
                lineheight=1.25, metrics=metrics, block_id=f"prov_note_{n_idx}", context="prov_note",
            )
            cur_y += n_h + 3.0

        # Caixa de Política de Rigor Epistémico sem sobrepor texto
        audit_text = AcademicDesignSystem.sanitize_text_for_font(
            "Todas as afirmações marcadas como SOURCE_FACT no documento foram validadas contra os parágrafos "
            "e páginas originais do documento fonte. As explicações pedagógicas, interpretações e comparações "
            "identificadas como MODEL_INFERENCE resultam de elaboração académica local (qwen3.5:9b). "
            "Afirmações sem suporte factual direto confirmado são mantidas como UNVERIFIED. Exemplos hipotéticos "
            "não constituem evidência empírica."
        )
        inner_w = content_w - 28.0
        audit_h = metrics.measure_text_height(
            audit_text, fontname=font_reg, fontsize=8.0, lineheight=1.3, max_width=inner_w
        )
        policy_box_h = 34.0 + audit_h + 10.0

        if cur_y + 10.0 + policy_box_h > max_y:
            page, cur_y = _open_bib_page(is_first=False)

        box_y0 = max(cur_y + 8.0, self.geo.max_content_y_pt - policy_box_h - 4.0)
        note_rect = pymupdf.Rect(margin_x, box_y0, margin_x + content_w, box_y0 + policy_box_h)
        shape = page.new_shape()
        shape.draw_rect(note_rect)
        shape.finish(color=c_primary, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1.5)
        shape.commit()

        page.insert_text(
            pymupdf.Point(margin_x + 14, box_y0 + 18),
            "POLÍTICA DE RIGOR EPISTÉMICO & FIDELIDADE À FONTE (JARVIS OS)",
            fontname=font_bold,
            fontsize=8.8,
            color=c_primary,
        )
        self._safe_insert_textbox(
            page,
            pymupdf.Rect(margin_x + 14, box_y0 + 26, margin_x + content_w - 14, box_y0 + policy_box_h - 6),
            audit_text,
            fontname=font_reg,
            fontsize=8.0,
            color=c_muted,
            lineheight=1.3,
            metrics=metrics,
            block_id="epistemic_policy_box",
            context="policy_box",
        )

        return pages_added

    def _inject_toc_internal_links(
        self,
        doc: pymupdf.Document,
        toc_link_specs: List[Tuple[int, pymupdf.Rect, str]],
        block_to_page: Dict[str, int],
    ) -> None:
        for toc_pg_idx, link_rect, target_block_id in toc_link_specs:
            if toc_pg_idx >= len(doc):
                continue
            p_toc = doc[toc_pg_idx]
            target_pg = block_to_page.get(target_block_id, 2)
            target_idx = max(0, min(len(doc) - 1, target_pg - 1))
            try:
                p_toc.insert_link({
                    "kind": pymupdf.LINK_GOTO,
                    "from": link_rect,
                    "page": target_idx,
                    "to": pymupdf.Point(self.geo.margin_left_pt, self.geo.margin_top_pt),
                })
            except Exception:
                pass


class DOCXDocumentComposer:
    """
    Motor de layout e exportação DOCX a partir da mesma StudyDocumentIR.
    Garante invariância semântica e preserva integralmente classificações epistémicas,
    objetivos de aprendizagem e referências bibliográficas.
    """

    def __init__(self, profile: Optional[DesignStyleProfile] = None) -> None:
        self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC

    def compose_to_docx(self, ir: StudyDocumentIR, output_path: str | Path) -> DocumentRenderResult:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        doc = Document()
        self._configure_document_styles(doc)

        props = doc.core_properties
        props.title = ir.metadata.title
        props.author = ", ".join(ir.metadata.authors) if ir.metadata.authors else "JARVIS OS"
        props.subject = ir.metadata.subtitle
        props.keywords = f"Study Engine, {ir.metadata.subject}, QA Validated"

        # 1. Título e Subtítulo
        title_p = doc.add_paragraph(ir.metadata.title, style="Title")
        title_p.paragraph_format.space_after = Pt(6)

        sub_p = doc.add_paragraph(f"{ir.metadata.subtitle} • {ir.header_footer.running_header_left}")
        sub_p.paragraph_format.space_after = Pt(16)

        # 2. Caixa de TODOS os Objetivos de Aprendizagem (sem truncagem)
        self._add_docx_callout(
            doc,
            "\n".join(f"• {lo}" for lo in ir.learning_objectives),
            "OBJETIVOS DE APRENDIZAGEM & ROTEIRO EDITORIAL",
            self.profile.accent_hex,
            self.profile.bg_subtle_hex,
        )

        # 3. Índice Automático de Campos do Word
        WordStyler.add_table_of_contents(doc, title="Índice")

        # 4. Capítulos e Secções
        for ch in ir.chapters:
            doc.add_page_break()
            ch_p = doc.add_paragraph(f"{ch.number_label} — {ch.title}", style="Heading 1")
            ch_p.paragraph_format.keep_with_next = True

            for b in ch.intro_blocks:
                if b.kind != IRBlockKind.HEADING.value:
                    self._render_block_docx(doc, b)

            for sec in ch.sections:
                sec_p = doc.add_paragraph(f"{sec.number_label} — {sec.title}", style="Heading 2")
                sec_p.paragraph_format.keep_with_next = True

                for b in sec.blocks:
                    if b.kind != IRBlockKind.HEADING.value:
                        self._render_block_docx(doc, b)

            for b in ch.synthesis_blocks:
                self._render_block_docx(doc, b)

        # 5. Síntese Global
        if ir.global_synthesis_blocks:
            doc.add_page_break()
            gs_p = doc.add_paragraph("Síntese Global & Integração Transversal", style="Heading 1")
            gs_p.paragraph_format.keep_with_next = True
            for b in ir.global_synthesis_blocks:
                if b.kind != IRBlockKind.HEADING.value:
                    self._render_block_docx(doc, b)

        # 6. Referências Bibliográficas
        doc.add_page_break()
        ref_p = doc.add_paragraph("Referências Bibliográficas & Proveniência", style="Heading 1")
        ref_p.paragraph_format.keep_with_next = True

        for ref_item in ir.bibliography:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            r_bold = p.add_run(f"{ref_item.citation_label} ")
            r_bold.font.bold = True
            p.add_run(ref_item.formatted_reference)

        tmp_out = out_p.with_suffix(".docx.tmp")
        doc.save(str(tmp_out))
        os.replace(tmp_out, out_p)
        sz = out_p.stat().st_size
        return DocumentRenderResult(file_path=str(out_p), pages_count=max(1, len(ir.chapters) + 2), file_size_bytes=sz)

    compose_docx = compose_to_docx

    def _configure_document_styles(self, doc: Document) -> None:
        primary_rgb = hex_to_rgb(self.profile.primary_hex)
        secondary_rgb = hex_to_rgb(self.profile.secondary_hex)
        text_rgb = hex_to_rgb(self.profile.text_primary_hex)

        for sec in doc.sections:
            sec.top_margin = Cm(2.2)
            sec.bottom_margin = Cm(2.2)
            sec.left_margin = Cm(2.2)
            sec.right_margin = Cm(2.0)
            sec.page_width = Cm(21.0)
            sec.page_height = Cm(29.7)

            header = sec.header
            header.is_linked_to_previous = False
            hp = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            hp.text = f"JARVIS OS • {self.profile.display_name}"
            hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            hp.runs[0].font.size = Pt(8.5)
            hp.runs[0].font.color.rgb = secondary_rgb

            footer = sec.footer
            footer.is_linked_to_previous = False
            fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            fp.text = ""
            fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            l_run = fp.add_run("Página ")
            l_run.font.size = Pt(9.0)
            p_run = fp.add_run()
            p_run.font.bold = True
            WordStyler.add_page_number_to_run(p_run)
            of_run = fp.add_run(" de ")
            of_run.font.size = Pt(9.0)
            tot_run = fp.add_run()
            WordStyler.add_num_pages_to_run(tot_run)

        styles = doc.styles
        if "Normal" in styles:
            n = styles["Normal"]
            n.font.name = self.profile.docx_font_body
            n.font.size = Pt(11.0)
            n.font.color.rgb = text_rgb
            n.paragraph_format.line_spacing = 1.2
            n.paragraph_format.space_after = Pt(6.0)

        if "Heading 1" in styles:
            h1 = styles["Heading 1"]
            h1.font.name = self.profile.docx_font_headings
            h1.font.size = Pt(16.0)
            h1.font.bold = True
            h1.font.color.rgb = primary_rgb
            h1.paragraph_format.space_before = Pt(14.0)
            h1.paragraph_format.space_after = Pt(6.0)
            h1.paragraph_format.keep_with_next = True

        if "Heading 2" in styles:
            h2 = styles["Heading 2"]
            h2.font.name = self.profile.docx_font_headings
            h2.font.size = Pt(13.0)
            h2.font.bold = True
            h2.font.color.rgb = secondary_rgb
            h2.paragraph_format.space_before = Pt(10.0)
            h2.paragraph_format.space_after = Pt(4.0)
            h2.paragraph_format.keep_with_next = True

    def _render_block_docx(self, doc: Document, b: IRBlock) -> None:
        ep_st = normalize_epistemic_status(b.epistemic_status, default="UNVERIFIED")
        ep_label, ep_accent_hex, ep_bg_hex = self.profile.get_epistemic_style(ep_st, b.is_hypothetical_example)

        if b.kind == IRBlockKind.PARAGRAPH.value:
            for p_txt in b.paragraphs:
                p = doc.add_paragraph(p_txt)
                p.paragraph_format.space_after = Pt(6.0)
            prov_str = b.provenance_summary or ep_label
            p_prov = doc.add_paragraph(prov_str)
            p_prov.paragraph_format.space_after = Pt(8.0)
            p_prov.runs[0].font.size = Pt(8.5)
            p_prov.runs[0].font.italic = True
            p_prov.runs[0].font.color.rgb = hex_to_rgb(ep_accent_hex)

        elif b.kind in (IRBlockKind.BULLET_LIST.value, IRBlockKind.NUMBERED_LIST.value):
            style = "List Bullet" if b.kind == IRBlockKind.BULLET_LIST.value else "List Number"
            for item in b.items:
                p = doc.add_paragraph(item, style=style)
                p.paragraph_format.space_after = Pt(3.0)
            if b.provenance_summary:
                p_prov = doc.add_paragraph(b.provenance_summary)
                p_prov.paragraph_format.space_after = Pt(8.0)
                p_prov.runs[0].font.size = Pt(8.5)
                p_prov.runs[0].font.italic = True
                p_prov.runs[0].font.color.rgb = hex_to_rgb(ep_accent_hex)

        elif b.kind == IRBlockKind.CALLOUT_BOX.value:
            theme = self.profile.get_callout_theme(b.callout_kind)
            border_h = ep_accent_hex if (b.is_hypothetical_example or ep_st in ("UNVERIFIED", "NOT_FOUND")) else theme.border_hex
            bg_h = ep_bg_hex if (b.is_hypothetical_example or ep_st in ("UNVERIFIED", "NOT_FOUND")) else theme.background_hex
            content_txt = "\n\n".join(b.paragraphs)
            if b.items:
                content_txt += ("\n" if content_txt else "") + "\n".join(f"• {it}" for it in b.items)
            if b.provenance_summary:
                content_txt += f"\n\n[{b.provenance_summary}]"
            box_title = f"{theme.badge_label} [{ep_st}]: {b.title}" if b.title else f"{theme.badge_label} [{ep_st}]"
            self._add_docx_callout(doc, content_txt, box_title, border_h, bg_h)

        elif b.kind == IRBlockKind.TABLE.value:
            self._render_table_docx(doc, b)

        elif b.kind == IRBlockKind.VISUAL_ELEMENT.value and b.image_path and os.path.exists(b.image_path):
            if b.title:
                tp = doc.add_paragraph(f"Figura: {b.title}")
                tp.runs[0].font.bold = True
                tp.paragraph_format.keep_with_next = True
            doc.add_picture(b.image_path, width=Cm(15.5))
            if b.caption or b.provenance_summary:
                cap = "\n".join(x for x in (b.caption, b.provenance_summary) if x)
                cp = doc.add_paragraph(cap)
                cp.runs[0].font.size = Pt(9.0)
                cp.runs[0].font.italic = True

    def _add_docx_callout(
        self,
        doc: Document,
        text: str,
        title: str,
        border_hex: str,
        bg_hex: str,
    ) -> None:
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        clean_b_hex = border_hex.lstrip("#")
        clean_bg_hex = bg_hex.lstrip("#")

        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{clean_bg_hex}"/>'))
        borders_xml = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'  <w:top w:val="none"/>'
            f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{clean_b_hex}"/>'
            f'  <w:bottom w:val="none"/>'
            f'  <w:right w:val="none"/>'
            f"</w:tcBorders>"
        )
        tcPr.append(borders_xml)

        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(2)
        r_title = p.add_run(f"📌 {title}\n")
        r_title.font.bold = True
        r_title.font.size = Pt(10)
        r_title.font.color.rgb = hex_to_rgb(border_hex)

        r_body = p.add_run(text)
        r_body.font.size = Pt(9.5)
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def _render_table_docx(self, doc: Document, b: IRBlock) -> None:
        if b.title:
            tp = doc.add_paragraph(f"Tabela: {b.title}")
            tp.runs[0].font.bold = True
            tp.paragraph_format.keep_with_next = True

        data_rows = b.table_rows
        headers = b.table_headers
        cols_count = max(1, len(headers))
        table = doc.add_table(rows=len(data_rows) + 1, cols=cols_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        import dataclasses
        from backend.document_engine.profiles import DocumentProfile, GenericProfile

        prof_kwargs = dataclasses.asdict(GenericProfile())
        prof_kwargs["accent_color_hex"] = self.profile.primary_hex
        sample_prof = DocumentProfile(**prof_kwargs)
        WordStyler.style_table(table, headers, data_rows, sample_prof)
        if b.provenance_summary:
            p_prov = doc.add_paragraph(b.provenance_summary)
            p_prov.paragraph_format.space_after = Pt(6.0)
            p_prov.runs[0].font.size = Pt(8.5)
            p_prov.runs[0].font.italic = True
        else:
            doc.add_paragraph().paragraph_format.space_after = Pt(8)
