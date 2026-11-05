from __future__ import annotations

import os
from typing import Any, List, Optional, Sequence, Tuple

import docx
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Inches, Pt, RGBColor

from backend.document_engine.profiles import DocumentProfile, DocumentProfileType, get_profile


def hex_to_rgb(hex_str: str) -> RGBColor:
    """Converts hex color string (e.g. '1B365D' or '#1B365D') to RGBColor."""
    clean = hex_str.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "1B365D"
    r = int(clean[0:2], 16)
    g = int(clean[2:4], 16)
    b = int(clean[4:6], 16)
    return RGBColor(r, g, b)


class WordStyler:
    """Applies semantic Word styles, professional typography, tables, and page layout."""

    @classmethod
    def apply_profile_to_document(
        cls,
        doc: Document,
        profile: DocumentProfile,
    ) -> None:
        """Configures document-wide styles, margins, and typography according to profile."""
        primary_rgb = hex_to_rgb(profile.accent_color_hex)
        secondary_rgb = hex_to_rgb(profile.secondary_color_hex)
        text_rgb = hex_to_rgb(profile.text_color_hex)

        # 1. Page Margins on all sections
        for section in doc.sections:
            section.top_margin = Cm(profile.top_margin_cm)
            section.bottom_margin = Cm(profile.bottom_margin_cm)
            section.left_margin = Cm(profile.left_margin_cm)
            section.right_margin = Cm(profile.right_margin_cm)
            section.page_width = Cm(21.0)  # A4 width
            section.page_height = Cm(29.7)  # A4 height

        # 2. Configure 'Normal' style
        styles = doc.styles
        if "Normal" in styles:
            normal_style = styles["Normal"]
            normal_style.font.name = profile.font_primary
            normal_style.font.size = Pt(11) if profile.profile_type != DocumentProfileType.ACADEMIC else Pt(12)
            normal_style.font.color.rgb = text_rgb
            normal_style.paragraph_format.line_spacing = profile.line_spacing
            normal_style.paragraph_format.space_after = Pt(profile.paragraph_space_after_pt)
            normal_style.paragraph_format.space_before = Pt(profile.paragraph_space_before_pt)

        # 3. Heading 1
        if "Heading 1" in styles:
            h1 = styles["Heading 1"]
            h1.font.name = profile.font_headings
            h1.font.size = Pt(18)
            h1.font.bold = True
            h1.font.color.rgb = primary_rgb
            h1.paragraph_format.space_before = Pt(16)
            h1.paragraph_format.space_after = Pt(6)
            h1.paragraph_format.keep_with_next = True

        # 4. Heading 2
        if "Heading 2" in styles:
            h2 = styles["Heading 2"]
            h2.font.name = profile.font_headings
            h2.font.size = Pt(14)
            h2.font.bold = True
            h2.font.color.rgb = secondary_rgb
            h2.paragraph_format.space_before = Pt(12)
            h2.paragraph_format.space_after = Pt(4)
            h2.paragraph_format.keep_with_next = True

        # 5. Heading 3
        if "Heading 3" in styles:
            h3 = styles["Heading 3"]
            h3.font.name = profile.font_headings
            h3.font.size = Pt(12)
            h3.font.bold = True
            h3.font.italic = True
            h3.font.color.rgb = secondary_rgb
            h3.paragraph_format.space_before = Pt(8)
            h3.paragraph_format.space_after = Pt(3)
            h3.paragraph_format.keep_with_next = True

        # 6. Title style
        if "Title" in styles:
            title_style = styles["Title"]
            title_style.font.name = profile.font_headings
            title_style.font.size = Pt(24)
            title_style.font.bold = True
            title_style.font.color.rgb = primary_rgb
            title_style.paragraph_format.space_before = Pt(12)
            title_style.paragraph_format.space_after = Pt(12)
            title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if profile.profile_type == DocumentProfileType.ACADEMIC else WD_ALIGN_PARAGRAPH.LEFT

    @classmethod
    def add_page_number_to_run(cls, run: Any) -> None:
        """Appends dynamic PAGE field to run."""
        fld_xml = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls("w"))
        run._r.append(fld_xml)

    @classmethod
    def add_num_pages_to_run(cls, run: Any) -> None:
        """Appends dynamic NUMPAGES field to run."""
        fld_xml = parse_xml(r'<w:fldSimple %s w:instr="NUMPAGES"/>' % nsdecls("w"))
        run._r.append(fld_xml)

    @classmethod
    def configure_headers_and_footers(
        cls,
        doc: Document,
        document_title: str,
        profile: DocumentProfile,
    ) -> None:
        """Configures clean headers and footers with dynamic page numbering (Página X de Y)."""
        secondary_rgb = hex_to_rgb(profile.secondary_color_hex)
        for s_idx, section in enumerate(doc.sections):
            # Header
            header = section.header
            header.is_linked_to_previous = False
            hp = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            hp.text = ""
            hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            hrun = hp.add_run(document_title[:60])
            hrun.font.name = profile.font_headings
            hrun.font.size = Pt(8.5)
            hrun.font.color.rgb = secondary_rgb

            # Footer
            footer = section.footer
            footer.is_linked_to_previous = False
            fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            fp.text = ""
            fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT

            label_run = fp.add_run("Página ")
            label_run.font.name = profile.font_primary
            label_run.font.size = Pt(9)
            label_run.font.color.rgb = secondary_rgb

            p_run = fp.add_run()
            p_run.font.name = profile.font_primary
            p_run.font.size = Pt(9)
            p_run.font.bold = True
            p_run.font.color.rgb = secondary_rgb
            cls.add_page_number_to_run(p_run)

            of_run = fp.add_run(" de ")
            of_run.font.name = profile.font_primary
            of_run.font.size = Pt(9)
            of_run.font.color.rgb = secondary_rgb

            tot_run = fp.add_run()
            tot_run.font.name = profile.font_primary
            tot_run.font.size = Pt(9)
            tot_run.font.color.rgb = secondary_rgb
            cls.add_num_pages_to_run(tot_run)

    @classmethod
    def add_table_of_contents(cls, doc: Document, title: str = "Índice") -> None:
        """Inserts an automated Table of Contents field into the document."""
        h = doc.add_paragraph(title, style="Heading 1")
        h.paragraph_format.keep_with_next = True
        p = doc.add_paragraph()
        run = p.add_run()
        fld_char_begin = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls("w"))
        instr_text = parse_xml(r'<w:instrText %s xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText>' % nsdecls("w"))
        fld_char_sep = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls("w"))
        fld_char_end = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls("w"))
        run._r.append(fld_char_begin)
        run._r.append(instr_text)
        run._r.append(fld_char_sep)
        run._r.append(fld_char_end)
        doc.add_page_break()

    @classmethod
    def style_table(
        cls,
        table: Any,
        headers: Sequence[str],
        data_rows: Sequence[Sequence[str]],
        profile: DocumentProfile,
        col_widths_cm: Optional[Sequence[float]] = None,
    ) -> None:
        """Applies professional styling: accented header row, zebra shading, cell padding and borders."""
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        accent_hex = profile.accent_color_hex.lstrip("#")
        zebra_hex = "F8FAFC"
        border_hex = "CBD5E1"

        # Apply XML borders
        tblPr = table._tbl.tblPr
        borders_xml = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="{border_hex}"/>'
            f'  <w:left w:val="none"/>'
            f'  <w:bottom w:val="single" w:sz="8" w:space="0" w:color="{accent_hex}"/>'
            f'  <w:right w:val="none"/>'
            f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{border_hex}"/>'
            f'  <w:insideV w:val="none"/>'
            f"</w:tblBorders>"
        )
        tblPr.append(borders_xml)

        # Style Header Row
        if headers and len(table.rows) > 0:
            header_row = table.rows[0]
            header_tr = header_row._tr.get_or_add_trPr()
            header_tr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))

            for c_idx, cell in enumerate(header_row.cells):
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                tcPr = cell._tc.get_or_add_tcPr()
                tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{accent_hex}"/>'))
                # Cell margins (padding)
                tcMar = parse_xml(
                    f'<w:tcMar {nsdecls("w")}>'
                    f'  <w:top w:w="140" w:type="dxa"/>'
                    f'  <w:bottom w:w="140" w:type="dxa"/>'
                    f'  <w:left w:w="160" w:type="dxa"/>'
                    f'  <w:right w:w="160" w:type="dxa"/>'
                    f"</w:tcMar>"
                )
                tcPr.append(tcMar)

                # Set cell text with white bold font
                p = cell.paragraphs[0]
                p.text = ""
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(headers[c_idx] if c_idx < len(headers) else "")
                run.font.name = profile.font_headings
                run.font.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)

        # Style Data Rows
        for r_idx, row in enumerate(table.rows[1:], start=1):
            is_zebra = r_idx % 2 == 0
            row_fill = zebra_hex if is_zebra else "FFFFFF"
            data_row = data_rows[r_idx - 1] if (r_idx - 1) < len(data_rows) else ()

            for c_idx, cell in enumerate(row.cells):
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                tcPr = cell._tc.get_or_add_tcPr()
                if is_zebra:
                    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{row_fill}"/>'))
                tcMar = parse_xml(
                    f'<w:tcMar {nsdecls("w")}>'
                    f'  <w:top w:w="100" w:type="dxa"/>'
                    f'  <w:bottom w:w="100" w:type="dxa"/>'
                    f'  <w:left w:w="160" w:type="dxa"/>'
                    f'  <w:right w:w="160" w:type="dxa"/>'
                    f"</w:tcMar>"
                )
                tcPr.append(tcMar)

                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)

                # Set cell text from data_rows if cell is currently empty
                cell_val = str(data_row[c_idx]) if c_idx < len(data_row) else ""
                if cell_val and not p.text.strip():
                    p.text = ""
                    run = p.add_run(cell_val)
                    run.font.name = profile.font_primary
                    run.font.size = Pt(9.5)
                else:
                    for r in p.runs:
                        r.font.name = profile.font_primary
                        r.font.size = Pt(9.5)

        # Set Column widths if specified
        if col_widths_cm:
            for row in table.rows:
                for c_idx, width_cm in enumerate(col_widths_cm):
                    if c_idx < len(row.cells):
                        row.cells[c_idx].width = Cm(width_cm)

    @classmethod
    def add_callout(
        cls,
        doc: Document,
        text: str,
        profile: DocumentProfile,
        title: str = "NOTA RELEVANTE",
    ) -> None:
        """Adds a shaded callout box with an accent left border."""
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        accent_hex = profile.accent_color_hex.lstrip("#")

        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>'))
        borders_xml = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'  <w:top w:val="none"/>'
            f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{accent_hex}"/>'
            f'  <w:bottom w:val="none"/>'
            f'  <w:right w:val="none"/>'
            f"</w:tcBorders>"
        )
        tcPr.append(borders_xml)
        tcMar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>'
            f'  <w:top w:w="140" w:type="dxa"/>'
            f'  <w:bottom w:w="140" w:type="dxa"/>'
            f'  <w:left w:w="200" w:type="dxa"/>'
            f'  <w:right w:w="160" w:type="dxa"/>'
            f"</w:tcMar>"
        )
        tcPr.append(tcMar)

        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        r_title = p.add_run(f"📌 {title}\n")
        r_title.font.name = profile.font_headings
        r_title.font.bold = True
        r_title.font.size = Pt(10)
        r_title.font.color.rgb = hex_to_rgb(profile.accent_color_hex)

        r_body = p.add_run(text)
        r_body.font.name = profile.font_primary
        r_body.font.size = Pt(10)
        r_body.font.italic = True
