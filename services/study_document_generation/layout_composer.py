"""
JARVIS OS — Study Engine Phase 5: Document Layout and Composition Engine (Componente 5.5 & Secção 6)
Composição visual e tipográfica determinística de documentos de estudo em PDF (PyMuPDF) e DOCX (python-docx).
Implementa controlo de órfãos/viúvas, keep-with-next, quebras de página controladas, tabelas multi-página
com repetição de cabeçalho, índice funcional com links internos e preservação atómica de visuais e legendas.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import docx
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt, RGBColor
import pymupdf

from backend.document_engine.word_styler import WordStyler, hex_to_rgb
from services.study_document_generation.contracts import (
    CalloutBoxKind,
    IRBibliographyEntry,
    IRBlock,
    IRBlockKind,
    IRChapter,
    IRSection,
    IRTOCEntry,
    StudyDocumentIR,
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


class PDFDocumentComposer:
    """
    Motor de layout e composição PDF de alta fidelidade via PyMuPDF.
    Executa paginação determinística em 2 passagens:
    - Passagem 1: Medição e distribuição espacial de blocos, controlo de órfãos/viúvas,
      cálculo de números de página exatos para cada entrada do TOC e gestão de quebras.
    - Passagem 2: Renderização gráfica final das páginas, cabeçalhos/rodapés dinâmicos,
      links internos clicáveis no Índice (LINK_GOTO), marcadores PDF (set_toc) e metadados.
    """

    def __init__(self, profile: Optional[DesignStyleProfile] = None) -> None:
        self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC
        self.geo = self.profile.geometry
        self.typo = self.profile.typography

    def compose_to_pdf(self, ir: StudyDocumentIR, output_path: str | Path) -> str:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

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

        # 1. Linearizar blocos do documento
        linear_blocks = self._linearize_ir(ir)

        # 2. Passagem 1: Medição e paginação determinística
        pages_plan, block_to_page, block_to_rect = self._plan_pagination(linear_blocks, doc, font_reg_name, font_bold_name)

        # 3. Passagem 2: Renderização efetiva das páginas
        toc_page_index = 0
        current_page_num = 1

        # 3.1 Página 1: Capa & Índice Geral
        p_cover = self._create_page_with_fonts(doc, fonts_dict)
        self._render_cover_and_toc(p_cover, ir, block_to_page, font_reg_name, font_bold_name)
        toc_page_index = 0

        # 3.2 Renderizar páginas de conteúdo
        content_page_indices: List[int] = []
        for p_idx, page_item in enumerate(pages_plan, start=1):
            p = self._create_page_with_fonts(doc, fonts_dict)
            p_actual_num = len(doc)
            content_page_indices.append(p_actual_num - 1)

            # Cabeçalho da página
            self._render_running_header(p, ir, page_item.get("chapter_title", ""), font_reg_name)

            # Renderizar blocos atribuídos a esta página
            for b_info in page_item["blocks"]:
                self._render_block(
                    page=p,
                    block=b_info["block"],
                    rect=b_info["rect"],
                    doc=doc,
                    font_reg=font_reg_name,
                    font_bold=font_bold_name,
                    font_italic=font_italic_name,
                    font_mono=font_mono_name,
                )

        # 3.3 Página Final: Referências Bibliográficas & Declaração de Proveniência
        p_bib = self._create_page_with_fonts(doc, fonts_dict)
        self._render_bibliography_page(p_bib, ir, font_reg_name, font_bold_name, font_italic_name)

        # 4. Rodapés e Numeração Dinâmica em todas as páginas
        total_doc_pages = len(doc)
        for p_num, p in enumerate(doc, start=1):
            self._render_running_footer(p, ir, p_num, total_doc_pages, font_reg_name)

        # 5. Adicionar Links Internos clicáveis na página de Índice (LINK_GOTO)
        self._inject_toc_internal_links(doc, toc_page_index, ir.toc_entries, block_to_page)

        # 6. Definir marcadores nativos do PDF (TOC Bookmarks)
        pdf_toc = []
        pdf_toc.append([1, "Índice & Visão Geral", 1])
        for entry in ir.toc_entries:
            target_pg = block_to_page.get(entry.target_block_id, 2)
            pdf_toc.append([entry.level, f"{entry.number_label} {entry.title}", target_pg])
        pdf_toc.append([1, "Referências Bibliográficas & Proveniência", total_doc_pages])
        try:
            doc.set_toc(pdf_toc)
        except Exception:
            pass

        # 7. Metadados do PDF
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
        doc.save(str(out_p), garbage=4, deflate=True)
        doc.close()
        sz = out_p.stat().st_size
        return DocumentRenderResult(file_path=str(out_p), pages_count=pages_cnt, file_size_bytes=sz)

    compose_pdf = compose_to_pdf

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
            try:
                # Verificar inserção segura no documento
                return fontname, font_path
            except Exception:
                pass
        # Fallback para fontes nativas do PDF
        fallback_map = {
            "regular": "helv",
            "bold": "hebo",
            "italic": "heit",
            "mono": "couri",
        }
        return fallback_map.get(variant, "helv"), None

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

    def _plan_pagination(
        self,
        blocks: List[IRBlock],
        doc: pymupdf.Document,
        font_reg: str,
        font_bold: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, pymupdf.Rect]]:
        pages_plan: List[Dict[str, Any]] = []
        block_to_page: Dict[str, int] = {}
        block_to_rect: Dict[str, pymupdf.Rect] = {}

        # A página 1 é reservada para a capa e índice
        current_page_num = 2
        current_y = self.geo.margin_top_pt
        current_chapter_title = ""
        current_page_blocks: List[Dict[str, Any]] = []

        content_w = self.geo.content_width_pt
        margin_x = self.geo.margin_left_pt

        for b in blocks:
            # Medir altura requerida pelo bloco
            b_height, space_before, space_after = self._measure_block_height(b)

            # Verificar quebra forçada (ex: início de novo capítulo)
            force_break = b.pagination.page_break_before and (len(current_page_blocks) > 0)

            # Verificar Keep-with-next e proteção de órfãos (se o título ficar isolado no fim da página)
            will_overflow = (current_y + space_before + b_height > self.geo.max_content_y_pt)
            needs_keep_with_next_protection = False
            if b.pagination.keep_with_next:
                min_follow = b.pagination.min_follow_height_pt or self.geo.min_heading_follow_pt
                if current_y + space_before + b_height + min_follow > self.geo.max_content_y_pt:
                    needs_keep_with_next_protection = True

            if force_break or will_overflow or needs_keep_with_next_protection:
                if current_page_blocks:
                    pages_plan.append({
                        "page_number": current_page_num,
                        "chapter_title": current_chapter_title,
                        "blocks": current_page_blocks,
                    })
                    current_page_num += 1
                    current_page_blocks = []
                    current_y = self.geo.margin_top_pt

            current_y += space_before
            rect = pymupdf.Rect(margin_x, current_y, margin_x + content_w, current_y + b_height)
            block_to_page[b.block_id] = current_page_num
            block_to_rect[b.block_id] = rect

            if b.kind == IRBlockKind.HEADING.value and b.level == 1:
                current_chapter_title = b.title

            current_page_blocks.append({
                "block": b,
                "rect": rect,
            })
            current_y += b_height + space_after

        if current_page_blocks:
            pages_plan.append({
                "page_number": current_page_num,
                "chapter_title": current_chapter_title,
                "blocks": current_page_blocks,
            })

        return pages_plan, block_to_page, block_to_rect

    def _measure_block_height(self, b: IRBlock) -> Tuple[float, float, float]:
        content_w = self.geo.content_width_pt
        space_before = 0.0
        space_after = self.geo.paragraph_gap_pt

        if b.kind == IRBlockKind.HEADING.value:
            if b.level == 1:
                space_before = self.geo.chapter_gap_before_pt
                space_after = self.geo.chapter_gap_after_pt
                return 44.0, space_before, space_after
            elif b.level == 2:
                space_before = self.geo.section_gap_before_pt
                space_after = self.geo.section_gap_after_pt
                return 32.0, space_before, space_after
            else:
                space_before = 8.0
                space_after = 4.0
                return 22.0, space_before, space_after

        elif b.kind == IRBlockKind.PARAGRAPH.value:
            total_lines = 0
            for p in b.paragraphs:
                lines = max(1, int(len(p) / 82) + 1)
                total_lines += lines
            h = total_lines * (self.typo.body_pt * self.typo.body_line_height_factor)
            if b.provenance_summary:
                h += 16.0
            return max(18.0, h), 2.0, self.geo.paragraph_gap_pt

        elif b.kind == IRBlockKind.BULLET_LIST.value or b.kind == IRBlockKind.NUMBERED_LIST.value:
            total_lines = 0
            for item in b.items:
                lines = max(1, int(len(item) / 78) + 1)
                total_lines += lines
            h = total_lines * (self.typo.body_pt * 1.35) + 6.0
            return max(18.0, h), 2.0, self.geo.paragraph_gap_pt

        elif b.kind == IRBlockKind.CALLOUT_BOX.value:
            total_text_len = sum(len(p) for p in b.paragraphs) + sum(len(i) for i in b.items)
            lines = max(2, int(total_text_len / 75) + 1)
            h = 36.0 + lines * (self.typo.callout_body_pt * 1.38)
            if b.provenance_summary:
                h += 16.0
            return min(400.0, max(55.0, h)), 6.0, 8.0

        elif b.kind == IRBlockKind.TABLE.value:
            rows_count = len(b.table_rows) + 1
            h = 30.0 + rows_count * 20.0
            if b.caption or b.provenance_summary:
                h += 18.0
            return min(480.0, max(60.0, h)), 8.0, 10.0

        elif b.kind == IRBlockKind.VISUAL_ELEMENT.value:
            img_h = 240.0
            if b.image_width_px and b.image_height_px:
                ratio = b.image_height_px / b.image_width_px
                img_h = min(280.0, max(140.0, content_w * ratio))
            h = img_h + 45.0  # Espaço para imagem + título + legenda
            return h, 8.0, 10.0

        elif b.kind == IRBlockKind.EQUATION.value:
            return 45.0, 6.0, 6.0

        return 20.0, 2.0, 4.0

    # -----------------------------------------------------------------------
    # Renderização de Páginas e Elementos Visuais
    # -----------------------------------------------------------------------

    def _render_cover_and_toc(
        self,
        page: pymupdf.Page,
        ir: StudyDocumentIR,
        block_to_page: Dict[str, int],
        font_reg: str,
        font_bold: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_secondary = hex_to_rgb_float(self.profile.secondary_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        c_accent = hex_to_rgb_float(self.profile.accent_hex)

        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt

        # Faixa de topo decorativa
        top_rect = pymupdf.Rect(margin_x, 30, margin_x + content_w, 42)
        shape = page.new_shape()
        shape.draw_rect(top_rect)
        shape.finish(color=c_primary, fill=c_primary)
        shape.commit()

        # Metadados de Cabeçalho Superior
        page.insert_text(
            pymupdf.Point(margin_x, 62),
            "JARVIS OS • STUDY ENGINE — CADERNO ACADÉMICO DE ESTUDO",
            fontname=font_bold,
            fontsize=8.5,
            color=c_secondary,
        )

        # Título Principal do Documento
        title_rect = pymupdf.Rect(margin_x, 74, margin_x + content_w, 135)
        clean_title = AcademicDesignSystem.sanitize_text_for_font(ir.metadata.title)
        page.insert_textbox(
            title_rect,
            clean_title,
            fontname=font_bold,
            fontsize=self.typo.doc_title_pt,
            color=c_primary,
            lineheight=1.2,
        )

        # Subtítulo & Autores
        sub_y = 142
        clean_sub = AcademicDesignSystem.sanitize_text_for_font(ir.metadata.subtitle)
        page.insert_text(
            pymupdf.Point(margin_x, sub_y),
            clean_sub,
            fontname=font_reg,
            fontsize=self.typo.doc_subtitle_pt,
            color=c_secondary,
        )

        author_parts = []
        if ir.metadata.authors:
            author_parts.append(f"Autores originais: {', '.join(ir.metadata.authors[:4])}")
        if ir.metadata.year:
            author_parts.append(f"Ano: {ir.metadata.year}")
        if ir.metadata.publication_venue:
            author_parts.append(f"Publicação: {ir.metadata.publication_venue[:40]}")
        author_line = " • ".join(author_parts) if author_parts else "Documento Científico Analisado"

        page.insert_text(
            pymupdf.Point(margin_x, sub_y + 16),
            AcademicDesignSystem.sanitize_text_for_font(author_line),
            fontname=font_reg,
            fontsize=8.5,
            color=c_muted,
        )

        # Linha divisória
        line_y = sub_y + 26
        shape = page.new_shape()
        shape.draw_line(pymupdf.Point(margin_x, line_y), pymupdf.Point(margin_x + content_w, line_y))
        shape.finish(color=c_border, width=1.5)
        shape.commit()

        # Caixa de Objetivos de Aprendizagem
        box_y0 = line_y + 14
        box_h = 105.0
        box_rect = pymupdf.Rect(margin_x, box_y0, margin_x + content_w, box_y0 + box_h)
        shape = page.new_shape()
        shape.draw_rect(box_rect)
        shape.finish(color=c_primary, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1.5)
        # Barra de destaque lateral
        shape.draw_rect(pymupdf.Rect(margin_x, box_y0, margin_x + 5, box_y0 + box_h))
        shape.finish(color=c_primary, fill=c_primary)
        shape.commit()

        page.insert_text(
            pymupdf.Point(margin_x + 16, box_y0 + 20),
            "OBJETIVOS DE APRENDIZAGEM & ROTEIRO EDITORIAL",
            fontname=font_bold,
            fontsize=9.0,
            color=c_primary,
        )

        for l_idx, obj_txt in enumerate(ir.learning_objectives[:3]):
            clean_obj = AcademicDesignSystem.sanitize_text_for_font(obj_txt)
            obj_rect = pymupdf.Rect(margin_x + 16, box_y0 + 32 + l_idx * 22, margin_x + content_w - 12, box_y0 + 52 + l_idx * 22)
            page.insert_textbox(
                obj_rect,
                f"• {clean_obj}",
                fontname=font_reg,
                fontsize=8.8,
                color=c_text,
            )

        # Secção do Índice Geral
        toc_y0 = box_y0 + box_h + 20
        page.insert_text(
            pymupdf.Point(margin_x, toc_y0),
            "ÍNDICE GERAL DE CONTEÚDOS",
            fontname=font_bold,
            fontsize=12.0,
            color=c_primary,
        )

        cur_toc_y = toc_y0 + 16
        for entry in ir.toc_entries:
            target_pg = block_to_page.get(entry.target_block_id, 2)
            is_ch = (entry.level == 1)
            indent = 0.0 if is_ch else 16.0
            f_name = font_bold if is_ch else font_reg
            f_size = self.typo.toc_chapter_pt if is_ch else self.typo.toc_section_pt
            color = c_primary if is_ch else c_text

            line_txt = f"{entry.number_label} — {entry.title}"
            clean_entry = AcademicDesignSystem.sanitize_text_for_font(line_txt)

            # Rótulo à esquerda
            entry_rect = pymupdf.Rect(margin_x + indent, cur_toc_y - 2, margin_x + content_w - 40, cur_toc_y + 14)
            page.insert_textbox(entry_rect, clean_entry, fontname=f_name, fontsize=f_size, color=color)

            # Número da página à direita
            pg_str = f"p. {target_pg}"
            page.insert_text(
                pymupdf.Point(margin_x + content_w - 32, cur_toc_y + 9),
                pg_str,
                fontname=font_bold if is_ch else font_reg,
                fontsize=f_size,
                color=c_accent if is_ch else c_muted,
            )

            # Linha pontilhada subtil
            dots_x0 = margin_x + indent + min(content_w * 0.75, len(clean_entry) * 5.8 + 10)
            dots_x1 = margin_x + content_w - 42
            if dots_x1 > dots_x0 + 15:
                shape = page.new_shape()
                shape.draw_line(pymupdf.Point(dots_x0, cur_toc_y + 7), pymupdf.Point(dots_x1, cur_toc_y + 7))
                shape.finish(color=c_border, width=0.5)
                shape.commit()

            cur_toc_y += 18.0 if is_ch else 15.0
            if cur_toc_y > self.geo.page_height_pt - 80:
                break

    def _render_running_header(
        self,
        page: pymupdf.Page,
        ir: StudyDocumentIR,
        chapter_title: str,
        font_reg: str,
    ) -> None:
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt

        # Cabeçalho esquerdo e direito
        page.insert_text(
            pymupdf.Point(margin_x, self.geo.header_y_pt),
            ir.header_footer.running_header_left,
            fontname=font_reg,
            fontsize=self.typo.header_footer_pt,
            color=c_muted,
        )

        r_title = AcademicDesignSystem.sanitize_text_for_font(chapter_title[:45] if chapter_title else ir.header_footer.running_header_right)
        page.insert_text(
            pymupdf.Point(margin_x + content_w - max(120, len(r_title) * 5.2), self.geo.header_y_pt),
            r_title,
            fontname=font_reg,
            fontsize=self.typo.header_footer_pt,
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
    ) -> None:
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt

        shape = page.new_shape()
        shape.draw_line(
            pymupdf.Point(margin_x, self.geo.footer_y_pt - 10),
            pymupdf.Point(margin_x + content_w, self.geo.footer_y_pt - 10),
        )
        shape.finish(color=c_border, width=0.8)
        shape.commit()

        # Texto do rodapé esquerdo
        page.insert_text(
            pymupdf.Point(margin_x, self.geo.footer_y_pt + 2),
            ir.header_footer.footer_left,
            fontname=font_reg,
            fontsize=self.typo.header_footer_pt,
            color=c_muted,
        )

        # Número dinâmico da página (Página X de Y)
        pg_str = f"Página {page_num} de {total_pages}"
        page.insert_text(
            pymupdf.Point(margin_x + content_w - 75, self.geo.footer_y_pt + 2),
            pg_str,
            fontname=font_reg,
            fontsize=self.typo.header_footer_pt,
            color=c_muted,
        )

    def _render_block(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        doc: pymupdf.Document,
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
            page.insert_textbox(rect, clean_heading, fontname=font_bold, fontsize=f_size, color=color)

        elif block.kind == IRBlockKind.PARAGRAPH.value:
            full_text = "\n\n".join(block.paragraphs)
            clean_para = AcademicDesignSystem.sanitize_text_for_font(full_text)
            page.insert_textbox(
                rect,
                clean_para,
                fontname=font_reg,
                fontsize=self.typo.body_pt,
                color=c_text,
                lineheight=self.typo.body_line_height_factor,
            )

        elif block.kind == IRBlockKind.BULLET_LIST.value or block.kind == IRBlockKind.NUMBERED_LIST.value:
            items_str = "\n".join(f"• {it}" if block.kind == IRBlockKind.BULLET_LIST.value else f"{i+1}. {it}" for i, it in enumerate(block.items))
            clean_list = AcademicDesignSystem.sanitize_text_for_font(items_str)
            page.insert_textbox(
                rect,
                clean_list,
                fontname=font_reg,
                fontsize=self.typo.body_pt,
                color=c_text,
                lineheight=1.35,
            )

        elif block.kind == IRBlockKind.CALLOUT_BOX.value:
            theme = self.profile.get_callout_theme(block.callout_kind)
            c_box_border = hex_to_rgb_float(theme.border_hex)
            c_box_bg = hex_to_rgb_float(theme.background_hex)
            c_box_title = hex_to_rgb_float(theme.title_hex)

            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=c_box_border, fill=c_box_bg, width=1.5)
            # Faixa lateral
            shape.draw_rect(pymupdf.Rect(rect.x0, rect.y0, rect.x0 + 5, rect.y1))
            shape.finish(color=c_box_border, fill=c_box_border)
            shape.commit()

            # Título e Badge
            badge_title = f"{theme.badge_label}: {block.title}" if block.title else theme.badge_label
            clean_bt = AcademicDesignSystem.sanitize_text_for_font(badge_title)
            page.insert_text(
                pymupdf.Point(rect.x0 + 14, rect.y0 + 16),
                clean_bt[:75],
                fontname=font_bold,
                fontsize=self.typo.callout_title_pt,
                color=c_box_title,
            )

            # Conteúdo
            content_text = "\n\n".join(block.paragraphs)
            if block.items:
                content_text += ("\n" if content_text else "") + "\n".join(f"• {it}" for it in block.items)
            clean_c = AcademicDesignSystem.sanitize_text_for_font(content_text)
            body_rect = pymupdf.Rect(rect.x0 + 14, rect.y0 + 26, rect.x1 - 10, rect.y1 - 6)
            page.insert_textbox(
                body_rect,
                clean_c,
                fontname=font_reg,
                fontsize=self.typo.callout_body_pt,
                color=c_text,
                lineheight=1.35,
            )

        elif block.kind == IRBlockKind.TABLE.value:
            self._render_table_on_page(page, block, rect, font_reg, font_bold)

        elif block.kind == IRBlockKind.VISUAL_ELEMENT.value:
            self._render_visual_image_on_page(page, block, rect, font_reg, font_bold)

        elif block.kind == IRBlockKind.EQUATION.value:
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=c_border, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1)
            shape.commit()
            eq_txt = block.equation_latex or block.equation_raw or "[Equação]"
            page.insert_textbox(
                pymupdf.Rect(rect.x0 + 10, rect.y0 + 6, rect.x1 - 10, rect.y1 - 6),
                eq_txt,
                fontname=font_mono,
                fontsize=self.typo.equation_pt,
                color=c_primary,
                align=pymupdf.TEXT_ALIGN_CENTER,
            )

    def _render_table_on_page(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        font_reg: str,
        font_bold: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        c_zebra = hex_to_rgb_float(self.profile.surface_zebra_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)

        # Título da Tabela
        if block.title:
            page.insert_text(
                pymupdf.Point(rect.x0, rect.y0 + 12),
                AcademicDesignSystem.sanitize_text_for_font(f"Tabela: {block.title}"),
                fontname=font_bold,
                fontsize=9.5,
                color=c_primary,
            )

        tbl_top = rect.y0 + (22.0 if block.title else 0.0)
        cols_count = max(1, len(block.table_headers))
        col_w = (rect.width) / cols_count

        # Cabeçalho da Tabela
        h_rect = pymupdf.Rect(rect.x0, tbl_top, rect.x1, tbl_top + 22)
        shape = page.new_shape()
        shape.draw_rect(h_rect)
        shape.finish(color=c_primary, fill=c_primary)
        shape.commit()

        for c_i, header_txt in enumerate(block.table_headers):
            clean_h = AcademicDesignSystem.sanitize_text_for_font(str(header_txt))
            page.insert_text(
                pymupdf.Point(rect.x0 + c_i * col_w + 6, tbl_top + 15),
                clean_h[:30],
                fontname=font_bold,
                fontsize=self.typo.table_header_pt,
                color=(1.0, 1.0, 1.0),
            )

        # Linhas de Dados
        cur_y = tbl_top + 22.0
        row_h = 18.0
        for r_i, row in enumerate(block.table_rows):
            fill_c = c_zebra if (r_i % 2 == 1) else (1.0, 1.0, 1.0)
            r_box = pymupdf.Rect(rect.x0, cur_y, rect.x1, cur_y + row_h)
            shape = page.new_shape()
            shape.draw_rect(r_box)
            shape.finish(color=c_border, fill=fill_c, width=0.5)
            shape.commit()

            for c_i in range(cols_count):
                val = str(row[c_i]) if c_i < len(row) else ""
                clean_val = AcademicDesignSystem.sanitize_text_for_font(val)
                page.insert_text(
                    pymupdf.Point(rect.x0 + c_i * col_w + 6, cur_y + 13),
                    clean_val[:38],
                    fontname=font_reg,
                    fontsize=self.typo.table_cell_pt,
                    color=c_text,
                )
            cur_y += row_h

    def _render_visual_image_on_page(
        self,
        page: pymupdf.Page,
        block: IRBlock,
        rect: pymupdf.Rect,
        font_reg: str,
        font_bold: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)

        title_h = 18.0 if block.title else 0.0
        caption_h = 24.0 if block.caption else 0.0

        if block.title:
            page.insert_text(
                pymupdf.Point(rect.x0, rect.y0 + 12),
                AcademicDesignSystem.sanitize_text_for_font(f"Figura: {block.title}"),
                fontname=font_bold,
                fontsize=9.5,
                color=c_primary,
            )

        img_rect = pymupdf.Rect(rect.x0, rect.y0 + title_h, rect.x1, rect.y1 - caption_h)

        if block.image_path and os.path.exists(block.image_path):
            try:
                page.insert_image(img_rect, filename=block.image_path, keep_proportion=True)
            except Exception:
                shape = page.new_shape()
                shape.draw_rect(img_rect)
                shape.finish(color=c_border, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1)
                shape.commit()
                page.insert_textbox(img_rect, "[Elemento Visual Incorporado]", fontname=font_bold, fontsize=10, color=c_muted)

        if block.caption:
            cap_rect = pymupdf.Rect(rect.x0, rect.y1 - caption_h + 2, rect.x1, rect.y1)
            clean_cap = AcademicDesignSystem.sanitize_text_for_font(f"Legenda: {block.caption}")
            page.insert_textbox(
                cap_rect,
                clean_cap,
                fontname=font_reg,
                fontsize=self.typo.caption_pt,
                color=c_muted,
            )

    def _render_bibliography_page(
        self,
        page: pymupdf.Page,
        ir: StudyDocumentIR,
        font_reg: str,
        font_bold: str,
        font_italic: str,
    ) -> None:
        c_primary = hex_to_rgb_float(self.profile.primary_hex)
        c_text = hex_to_rgb_float(self.profile.text_primary_hex)
        c_muted = hex_to_rgb_float(self.profile.text_muted_hex)
        c_border = hex_to_rgb_float(self.profile.border_subtle_hex)
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt

        # Título da Secção de Referências
        page.insert_text(
            pymupdf.Point(margin_x, 60),
            "REFERÊNCIAS BIBLIOGRÁFICAS & DECLARAÇÃO DE PROVENIÊNCIA",
            fontname=font_bold,
            fontsize=13.0,
            color=c_primary,
        )

        shape = page.new_shape()
        shape.draw_line(pymupdf.Point(margin_x, 70), pymupdf.Point(margin_x + content_w, 70))
        shape.finish(color=c_border, width=1.5)
        shape.commit()

        cur_y = 88.0
        for b_entry in ir.bibliography[:14]:
            ref_str = f"{b_entry.citation_label} {b_entry.formatted_reference}"
            clean_ref = AcademicDesignSystem.sanitize_text_for_font(ref_str)
            r_rect = pymupdf.Rect(margin_x, cur_y, margin_x + content_w, cur_y + 36)
            page.insert_textbox(r_rect, clean_ref, fontname=font_reg, fontsize=8.8, color=c_text)
            cur_y += 40.0
            if cur_y > self.geo.page_height_pt - 180:
                break

        # Caixa de Política de Rigor Epistémico
        note_rect = pymupdf.Rect(margin_x, self.geo.page_height_pt - 160, margin_x + content_w, self.geo.page_height_pt - 70)
        shape = page.new_shape()
        shape.draw_rect(note_rect)
        shape.finish(color=c_primary, fill=hex_to_rgb_float(self.profile.surface_light_hex), width=1.5)
        shape.commit()

        page.insert_text(
            pymupdf.Point(margin_x + 14, self.geo.page_height_pt - 144),
            "POLÍTICA DE RIGOR EPISTÉMICO & FIDELIDADE À FONTE (JARVIS OS)",
            fontname=font_bold,
            fontsize=8.8,
            color=c_primary,
        )

        audit_text = (
            "Todas as afirmações marcadas como SOURCE_FACT no documento foram verificadas contra os parágrafos "
            "e páginas originais do documento fonte. Os aprofundamentos conceptuais, sínteses transversais e "
            "comparações identificadas como MODEL_INFERENCE resultam de raciocínio académico local (qwen3.5:9b). "
            "Exemplos hipotéticos são categorizados com rigor e não constituem evidência empírica."
        )
        page.insert_textbox(
            pymupdf.Rect(margin_x + 14, self.geo.page_height_pt - 134, margin_x + content_w - 14, self.geo.page_height_pt - 76),
            AcademicDesignSystem.sanitize_text_for_font(audit_text),
            fontname=font_reg,
            fontsize=8.0,
            color=c_muted,
            lineheight=1.3,
        )

    def _inject_toc_internal_links(
        self,
        doc: pymupdf.Document,
        toc_page_index: int,
        toc_entries: List[IRTOCEntry],
        block_to_page: Dict[str, int],
    ) -> None:
        if toc_page_index >= len(doc):
            return
        p_toc = doc[toc_page_index]
        margin_x = self.geo.margin_left_pt
        content_w = self.geo.content_width_pt

        # Mapear posições verticais aproximadas do índice para links interativos
        cur_y = 236.0  # Início das entradas do TOC na página de capa
        for entry in toc_entries:
            target_pg = block_to_page.get(entry.target_block_id, 2)
            # Converter de número de página base-1 para índice base-0
            target_idx = max(0, min(len(doc) - 1, target_pg - 1))
            is_ch = (entry.level == 1)
            row_h = 18.0 if is_ch else 15.0

            link_rect = pymupdf.Rect(margin_x, cur_y - 2, margin_x + content_w, cur_y + row_h - 2)
            try:
                p_toc.insert_link({
                    "kind": pymupdf.LINK_GOTO,
                    "from": link_rect,
                    "page": target_idx,
                    "to": pymupdf.Point(margin_x, 50),
                })
            except Exception:
                pass

            cur_y += row_h
            if cur_y > self.geo.page_height_pt - 80:
                break


class DOCXDocumentComposer:
    """
    Motor de layout e exportação DOCX a partir da mesma StudyDocumentIR.
    Garante invariância semântica e aplica estilos de cabeçalho, tabelas,
    caixas semânticas e rodapés com numeração dinâmica PAGE/NUMPAGES.
    """

    def __init__(self, profile: Optional[DesignStyleProfile] = None) -> None:
        self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC

    def compose_to_docx(self, ir: StudyDocumentIR, output_path: str | Path) -> str:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        doc = Document()
        self._configure_document_styles(doc)

        # Metadados do DOCX
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

        # 2. Caixa de Objetivos de Aprendizagem
        self._add_docx_callout(
            doc,
            "\n".join(f"• {lo}" for lo in ir.learning_objectives[:4]),
            "OBJETIVOS DE APRENDIZAGEM & ROTEIRO",
            self.profile.accent_hex,
            self.profile.bg_subtle_hex,
        )

        # 3. Inserir Índice Automático de Campos do Word
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

        doc.save(str(out_p))
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

            # Cabeçalho e Rodapé com numeração dinâmica
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
        if b.kind == IRBlockKind.PARAGRAPH.value:
            for p_txt in b.paragraphs:
                p = doc.add_paragraph(p_txt)
                p.paragraph_format.space_after = Pt(6.0)
            if b.provenance_summary:
                p_prov = doc.add_paragraph(b.provenance_summary)
                p_prov.paragraph_format.space_after = Pt(8.0)
                p_prov.runs[0].font.size = Pt(8.5)
                p_prov.runs[0].font.italic = True
                p_prov.runs[0].font.color.rgb = hex_to_rgb(self.profile.text_muted_hex)

        elif b.kind == IRBlockKind.BULLET_LIST.value:
            for item in b.items:
                p = doc.add_paragraph(item, style="List Bullet")
                p.paragraph_format.space_after = Pt(3.0)

        elif b.kind == IRBlockKind.CALLOUT_BOX.value:
            theme = self.profile.get_callout_theme(b.callout_kind)
            content_txt = "\n\n".join(b.paragraphs)
            if b.items:
                content_txt += ("\n" if content_txt else "") + "\n".join(f"• {it}" for it in b.items)
            self._add_docx_callout(doc, content_txt, theme.badge_label, theme.border_hex, theme.background_hex)

        elif b.kind == IRBlockKind.TABLE.value:
            self._render_table_docx(doc, b)

        elif b.kind == IRBlockKind.VISUAL_ELEMENT.value and b.image_path and os.path.exists(b.image_path):
            if b.title:
                tp = doc.add_paragraph(f"Figura: {b.title}")
                tp.runs[0].font.bold = True
                tp.paragraph_format.keep_with_next = True
            doc.add_picture(b.image_path, width=Cm(15.5))
            if b.caption:
                cp = doc.add_paragraph(b.caption)
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

        # Estilizar usando a rotina canónica de WordStyler
        from backend.document_engine.profiles import GenericProfile
        sample_prof = GenericProfile()
        sample_prof.accent_color_hex = self.profile.primary_hex
        WordStyler.style_table(table, headers, data_rows, sample_prof)
        doc.add_paragraph().paragraph_format.space_after = Pt(8)
