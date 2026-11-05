from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import docx
from docx.document import Document as _DocxDocument
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.table import Table as _DocxTable
from docx.text.paragraph import Paragraph as _DocxParagraph


@dataclass(frozen=True)
class RunNode:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    color_rgb: Optional[str] = None
    style_name: Optional[str] = None


@dataclass(frozen=True)
class HeadingNode:
    text: str
    level: int  # 1 to 6
    style_name: str
    index: int
    runs: tuple[RunNode, ...] = ()


@dataclass(frozen=True)
class ParagraphNode:
    text: str
    style_name: str
    index: int
    runs: tuple[RunNode, ...] = ()
    is_bullet: bool = False
    is_numbered: bool = False
    list_level: int = 0


@dataclass(frozen=True)
class TableCellNode:
    text: str
    row_idx: int
    col_idx: int
    runs: tuple[RunNode, ...] = ()


@dataclass(frozen=True)
class TableNode:
    index: int
    rows_count: int
    cols_count: int
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    has_header_row: bool = True
    cells: tuple[TableCellNode, ...] = ()


@dataclass(frozen=True)
class ImageNode:
    image_id: str
    relationship_id: str
    filename: str
    caption: str = ""
    width_pt: Optional[float] = None
    height_pt: Optional[float] = None
    content_sha256: str = ""
    content_bytes: bytes = b""


@dataclass(frozen=True)
class SectionNode:
    section_index: int
    orientation: str  # PORTRAIT or LANDSCAPE
    page_width_pt: float
    page_height_pt: float
    top_margin_pt: float
    bottom_margin_pt: float
    left_margin_pt: float
    right_margin_pt: float
    header_text: str = ""
    footer_text: str = ""


@dataclass(frozen=True)
class HyperlinkNode:
    text: str
    url: str
    paragraph_index: int


@dataclass(frozen=True)
class FieldNode:
    field_type: str  # PAGE, NUMPAGES, TOC, DATE, etc.
    text: str = ""


@dataclass(frozen=True)
class UnparsedElementNode:
    tag: str
    description: str
    xml_snippet: str = ""


@dataclass(frozen=True)
class WordDocumentMetadata:
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    created: str = ""
    modified: str = ""
    revision: int = 1
    total_words: int = 0
    total_paragraphs: int = 0


@dataclass
class WordDocumentAST:
    title: str
    metadata: WordDocumentMetadata
    sections: List[SectionNode] = field(default_factory=list)
    headings: List[HeadingNode] = field(default_factory=list)
    paragraphs: List[ParagraphNode] = field(default_factory=list)
    tables: List[TableNode] = field(default_factory=list)
    images: List[ImageNode] = field(default_factory=list)
    hyperlinks: List[HyperlinkNode] = field(default_factory=list)
    fields: List[FieldNode] = field(default_factory=list)
    unparsed_elements: List[UnparsedElementNode] = field(default_factory=list)
    ordered_elements: List[Any] = field(default_factory=list)
    raw_text: str = ""

    def get_outline(self) -> List[Tuple[int, str]]:
        """Returns hierarchy outline [(level, heading_text), ...]."""
        return [(h.level, h.text) for h in self.headings]

    def find_heading(self, pattern: str) -> Optional[HeadingNode]:
        """Finds heading matching regex pattern."""
        regex = re.compile(pattern, re.IGNORECASE)
        for h in self.headings:
            if regex.search(h.text):
                return h
        return None

    def get_section_text(self, heading_text: str) -> str:
        """Returns body text under a specific heading until the next heading of equal or higher level."""
        target_idx = -1
        target_level = 1
        for i, h in enumerate(self.headings):
            if heading_text.lower() in h.text.lower():
                target_idx = h.index
                target_level = h.level
                break

        if target_idx == -1:
            return ""

        collected = []
        for elem in self.ordered_elements:
            if isinstance(elem, HeadingNode):
                if elem.index > target_idx and elem.level <= target_level:
                    break
            elif isinstance(elem, ParagraphNode):
                if elem.index > target_idx:
                    collected.append(elem.text)
        return "\n\n".join(collected)

    def to_markdown(self) -> str:
        """Converts AST to structured Markdown representation."""
        lines: List[str] = []
        if self.title:
            lines.append(f"# {self.title}\n")

        for elem in self.ordered_elements:
            if isinstance(elem, HeadingNode):
                prefix = "#" * max(1, min(6, elem.level))
                lines.append(f"\n{prefix} {elem.text}\n")
            elif isinstance(elem, ParagraphNode):
                if elem.is_bullet:
                    indent = "  " * elem.list_level
                    lines.append(f"{indent}- {elem.text}")
                elif elem.is_numbered:
                    indent = "  " * elem.list_level
                    lines.append(f"{indent}1. {elem.text}")
                else:
                    lines.append(f"\n{elem.text}\n")
            elif isinstance(elem, TableNode):
                lines.append("")
                if elem.headers:
                    lines.append("| " + " | ".join(elem.headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(elem.headers)) + " |")
                for row in elem.rows:
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("")
            elif isinstance(elem, ImageNode):
                lines.append(f"\n![{elem.caption or elem.filename}](image:{elem.image_id})\n")

        return "\n".join(lines).strip()

    def to_dict(self) -> dict[str, Any]:
        """Serializes AST to JSON-friendly dictionary."""
        return {
            "title": self.title,
            "metadata": {
                "title": self.metadata.title,
                "author": self.metadata.author,
                "subject": self.metadata.subject,
                "keywords": self.metadata.keywords,
                "created": self.metadata.created,
                "modified": self.metadata.modified,
                "revision": self.metadata.revision,
                "total_words": self.metadata.total_words,
                "total_paragraphs": self.metadata.total_paragraphs,
            },
            "outline": self.get_outline(),
            "sections_count": len(self.sections),
            "headings_count": len(self.headings),
            "paragraphs_count": len(self.paragraphs),
            "tables_count": len(self.tables),
            "images_count": len(self.images),
            "hyperlinks_count": len(self.hyperlinks),
            "unparsed_count": len(self.unparsed_elements),
            "tables": [
                {
                    "index": t.index,
                    "rows": t.rows_count,
                    "cols": t.cols_count,
                    "headers": list(t.headers),
                }
                for t in self.tables
            ],
            "images": [
                {
                    "id": img.image_id,
                    "filename": img.filename,
                    "caption": img.caption,
                    "sha256": img.content_sha256,
                }
                for img in self.images
            ],
        }


def _extract_runs(paragraph: _DocxParagraph) -> tuple[RunNode, ...]:
    nodes: List[RunNode] = []
    for r in paragraph.runs:
        if not r.text:
            continue
        font_size = None
        if r.font and r.font.size:
            font_size = r.font.size.pt
        font_name = r.font.name if r.font else None
        color_rgb = None
        if r.font and r.font.color and r.font.color.rgb:
            color_rgb = f"#{r.font.color.rgb}"
        nodes.append(
            RunNode(
                text=r.text,
                bold=bool(r.bold),
                italic=bool(r.italic),
                underline=bool(r.underline),
                font_name=font_name,
                font_size_pt=font_size,
                color_rgb=color_rgb,
                style_name=r.style.name if r.style else None,
            )
        )
    return tuple(nodes)


def _detect_heading_level(paragraph: _DocxParagraph) -> Optional[int]:
    """Detects heading level 1-6 from style or XML outline."""
    style_name = (paragraph.style.name if paragraph.style else "").lower()
    if "heading 1" in style_name or "título 1" in style_name:
        return 1
    if "heading 2" in style_name or "título 2" in style_name:
        return 2
    if "heading 3" in style_name or "título 3" in style_name:
        return 3
    if "heading 4" in style_name or "título 4" in style_name:
        return 4
    if "heading 5" in style_name or "título 5" in style_name:
        return 5
    if "heading 6" in style_name or "título 6" in style_name:
        return 6

    # Note: 'Title' and 'Subtitle' styles represent the document title/cover,
    # not a numbered/hierarchical section heading.

    # Check w:outlineLvl in paragraph properties
    pPr = paragraph._p.pPr
    if pPr is not None:
        outlineLvl = pPr.find(qn("w:outlineLvl"))
        if outlineLvl is not None:
            try:
                val = int(outlineLvl.get(qn("w:val"), "0"))
                return min(6, max(1, val + 1))
            except Exception:
                pass
    return None


def extract_ast_from_docx(file_path_or_bytes: str | Path | bytes) -> WordDocumentAST:
    """
    Parses a Microsoft Word (.docx) document into a strongly-typed WordDocumentAST.
    Faithfully interprets headings, paragraphs, lists, tables, images, hyperlinks,
    headers/footers, and captures unparsed XML elements without silent deletion.
    """
    if isinstance(file_path_or_bytes, bytes):
        source_stream = io.BytesIO(file_path_or_bytes)
        doc = docx.Document(source_stream)
    else:
        path_str = str(file_path_or_bytes)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"Documento DOCX não encontrado: {path_str}")
        doc = docx.Document(path_str)

    # Core properties / metadata
    props = doc.core_properties
    meta = WordDocumentMetadata(
        title=props.title or "",
        author=props.author or "",
        subject=props.subject or "",
        keywords=props.keywords or "",
        created=str(props.created or ""),
        modified=str(props.modified or ""),
        revision=int(props.revision or 1),
    )

    # Sections extraction
    sections_list: List[SectionNode] = []
    for s_idx, sec in enumerate(doc.sections):
        orient = "LANDSCAPE" if sec.orientation == WD_ORIENT.LANDSCAPE else "PORTRAIT"
        w_pt = sec.page_width.pt if sec.page_width else 595.3  # A4 default pt
        h_pt = sec.page_height.pt if sec.page_height else 841.9
        top_m = sec.top_margin.pt if sec.top_margin else 72.0
        bot_m = sec.bottom_margin.pt if sec.bottom_margin else 72.0
        left_m = sec.left_margin.pt if sec.left_margin else 72.0
        right_m = sec.right_margin.pt if sec.right_margin else 72.0

        header_txt = ""
        footer_txt = ""
        try:
            if sec.header and sec.header.paragraphs:
                header_txt = " ".join(p.text for p in sec.header.paragraphs if p.text).strip()
            if sec.footer and sec.footer.paragraphs:
                footer_txt = " ".join(p.text for p in sec.footer.paragraphs if p.text).strip()
        except Exception:
            pass

        sections_list.append(
            SectionNode(
                section_index=s_idx,
                orientation=orient,
                page_width_pt=w_pt,
                page_height_pt=h_pt,
                top_margin_pt=top_m,
                bottom_margin_pt=bot_m,
                left_margin_pt=left_m,
                right_margin_pt=right_m,
                header_text=header_txt,
                footer_text=footer_txt,
            )
        )

    # Extract images from relationships
    images_list: List[ImageNode] = []
    image_rel_map: dict[str, ImageNode] = {}
    try:
        for r_id, rel in doc.part.rels.items():
            if "image" in rel.target_ref.lower():
                try:
                    img_part = rel.target_part
                    img_bytes = img_part.blob
                    img_sha = hashlib.sha256(img_bytes).hexdigest()
                    filename = Path(rel.target_ref).name
                    img_node = ImageNode(
                        image_id=f"img_{img_sha[:10]}",
                        relationship_id=r_id,
                        filename=filename,
                        content_sha256=img_sha,
                        content_bytes=img_bytes,
                    )
                    images_list.append(img_node)
                    image_rel_map[r_id] = img_node
                except Exception:
                    pass
    except Exception:
        pass

    headings_list: List[HeadingNode] = []
    paragraphs_list: List[ParagraphNode] = []
    tables_list: List[TableNode] = []
    hyperlinks_list: List[HyperlinkNode] = []
    fields_list: List[FieldNode] = []
    unparsed_list: List[UnparsedElementNode] = []
    ordered_elements: List[Any] = []
    all_text_chunks: List[str] = []

    doc_title = meta.title or ""

    # Iterate over document body child elements in document flow order
    # (p: w:p, tbl: w:tbl, sdt: w:sdt, etc.)
    p_counter = 0
    t_counter = 0

    for child in doc.element.body:
        tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag_name == "p":
            p = _DocxParagraph(child, doc)
            text = p.text.strip()
            runs = _extract_runs(p)
            style_name = p.style.name if p.style else "Normal"
            p_counter += 1

            if not doc_title and style_name.lower() in {"title", "título"} and text:
                doc_title = text

            # Detect hyperlinks
            for hyper in child.findall(qn("w:hyperlink")):
                try:
                    r_id = hyper.get(qn("r:id"))
                    target_url = ""
                    if r_id and r_id in doc.part.rels:
                        target_url = doc.part.rels[r_id].target_ref
                    h_text = "".join(t.text for t in hyper.findall(".//" + qn("w:t")) if t.text)
                    if h_text:
                        hyperlinks_list.append(
                            HyperlinkNode(
                                text=h_text,
                                url=target_url,
                                paragraph_index=p_counter,
                            )
                        )
                except Exception:
                    pass

            # Detect fields (PAGE, NUMPAGES, TOC)
            for fld in child.findall(".//" + qn("w:fldSimple")):
                instr = fld.get(qn("w:instr"), "").strip()
                if instr:
                    fields_list.append(FieldNode(field_type=instr.split()[0], text=instr))

            heading_level = _detect_heading_level(p)
            if heading_level is not None and text:
                if not doc_title and heading_level == 1 and p_counter <= 2:
                    doc_title = text
                h_node = HeadingNode(
                    text=text,
                    level=heading_level,
                    style_name=style_name,
                    index=p_counter,
                    runs=runs,
                )
                headings_list.append(h_node)
                ordered_elements.append(h_node)
                all_text_chunks.append(text)
            elif text:
                # Check for bullet or numbered list
                is_bullet = False
                is_numbered = False
                list_lvl = 0
                numPr = child.find(".//" + qn("w:numPr"))
                if numPr is not None or "list" in style_name.lower():
                    if "bullet" in style_name.lower():
                        is_bullet = True
                    else:
                        is_numbered = True
                    ilvl = child.find(".//" + qn("w:ilvl"))
                    if ilvl is not None:
                        try:
                            list_lvl = int(ilvl.get(qn("w:val"), "0"))
                        except Exception:
                            list_lvl = 0

                p_node = ParagraphNode(
                    text=text,
                    style_name=style_name,
                    index=p_counter,
                    runs=runs,
                    is_bullet=is_bullet,
                    is_numbered=is_numbered,
                    list_level=list_lvl,
                )
                paragraphs_list.append(p_node)
                ordered_elements.append(p_node)
                all_text_chunks.append(text)

            # Check if this paragraph contains an image drawing
            for blip in child.findall(".//" + qn("a:blip")):
                r_id = blip.get(qn("r:embed"))
                if r_id and r_id in image_rel_map:
                    img_node = image_rel_map[r_id]
                    if img_node not in ordered_elements:
                        ordered_elements.append(img_node)

        elif tag_name == "tbl":
            table = _DocxTable(child, doc)
            t_counter += 1
            rows_data: List[tuple[str, ...]] = []
            cells_nodes: List[TableCellNode] = []
            headers: tuple[str, ...] = ()

            for r_idx, row in enumerate(table.rows):
                row_vals = []
                for c_idx, cell in enumerate(row.cells):
                    c_text = cell.text.strip()
                    row_vals.append(c_text)
                    cells_nodes.append(
                        TableCellNode(
                            text=c_text,
                            row_idx=r_idx,
                            col_idx=c_idx,
                        )
                    )
                if r_idx == 0:
                    headers = tuple(row_vals)
                else:
                    rows_data.append(tuple(row_vals))

            t_node = TableNode(
                index=t_counter,
                rows_count=len(table.rows),
                cols_count=len(table.columns),
                headers=headers,
                rows=tuple(rows_data),
                has_header_row=bool(headers),
                cells=tuple(cells_nodes),
            )
            tables_list.append(t_node)
            ordered_elements.append(t_node)
            # Add table text to all_text_chunks
            table_flat = " | ".join(headers) + "\n" + "\n".join(" | ".join(r) for r in rows_data)
            all_text_chunks.append(table_flat)

        elif tag_name == "sdt":
            # Structured Document Tag (e.g. Table of Contents or Content Control)
            fields_list.append(FieldNode(field_type="TOC", text="Table of Contents block"))
        elif tag_name not in {"sectPr"}:
            unparsed_list.append(
                UnparsedElementNode(
                    tag=tag_name,
                    description=f"Elemento XML de corpo {tag_name} preservado",
                )
            )

    full_text = "\n\n".join(all_text_chunks)
    total_words = len(full_text.split())
    meta = WordDocumentMetadata(
        title=doc_title or meta.title,
        author=meta.author,
        subject=meta.subject,
        keywords=meta.keywords,
        created=meta.created,
        modified=meta.modified,
        revision=meta.revision,
        total_words=total_words,
        total_paragraphs=len(paragraphs_list) + len(headings_list),
    )

    return WordDocumentAST(
        title=doc_title or "Documento Word",
        metadata=meta,
        sections=sections_list,
        headings=headings_list,
        paragraphs=paragraphs_list,
        tables=tables_list,
        images=images_list,
        hyperlinks=hyperlinks_list,
        fields=fields_list,
        unparsed_elements=unparsed_list,
        ordered_elements=ordered_elements,
        raw_text=full_text,
    )
