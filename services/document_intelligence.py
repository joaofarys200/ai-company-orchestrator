"""
JARVIS OS - Document Intelligence (Fase 2)

Camada de compreensão estrutural de PDFs. Converte um PDF numa ``AcademicDocumentAST``:
uma representação estruturada, rastreável e reutilizável do documento original
(metadados, secções hierárquicas, parágrafos, tabelas, figuras, fórmulas e referências),
com página, coordenadas e método de extração em cada entidade.

Princípios:
- Sem modelo generativo: extração puramente determinística (PyMuPDF + pdfplumber + OCR local opcional).
- Sem limites globais de caracteres e sem cortes de texto: nada recuperável é descartado
  deliberadamente. Cabeçalhos/rodapés removidos do corpo são preservados em ``page_artifacts``.
- Honestidade: nada é inventado. Metadados ausentes ficam ``None``; tabelas que não puderam
  ser reconstruídas são assinaladas; figuras são apenas imagens extraídas (nunca "dados de gráfico").
- Rastreabilidade: SHA-256 do ficheiro, identificadores estáveis, página/secção/bbox/método por entidade.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:  # PyMuPDF moderno
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "2.0.0"


class DocumentExtractionError(Exception):
    """Falha irrecuperável de extração (PDF ilegível, protegido ou sem conteúdo recuperável)."""


# ---------------------------------------------------------------------------
# Modelo de dados (AcademicDocumentAST)
# ---------------------------------------------------------------------------

class ObservableASTNode:
    """Base mixin para nós da AST que notificam observadores quando atributos indexados são alterados."""

    def _set_observer(self, callback: Optional[Callable[[], None]]) -> None:
        object.__setattr__(self, "_observer", callback)

    def _notify_change(self) -> None:
        obs = getattr(self, "_observer", None)
        if obs is not None:
            obs()


def _from_dict(cls, data: Dict[str, Any]):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (data or {}).items() if k in known})


@dataclass
class PageInfo(ObservableASTNode):
    page_number: int
    width: float = 0.0
    height: float = 0.0
    rotation: int = 0
    text_source: str = "TEXT_LAYER"  # TEXT_LAYER | OCR_WINDOWS | NONE
    status: str = "OK"  # OK | OCR_RECOVERED | UNRECOVERED | EMPTY
    char_count: int = 0
    block_count: int = 0
    columns_detected: int = 1
    image_count: int = 0
    image_coverage: float = 0.0
    page_image_ref: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def __setattr__(self, name: str, value: Any) -> None:
        old_val = getattr(self, name, None) if hasattr(self, name) else None
        super().__setattr__(name, value)
        if name == "page_number" and old_val is not None and old_val != value:
            self._notify_change()


@dataclass
class ASTSection(ObservableASTNode):
    section_id: str
    title: str
    level: int = 1
    kind: str = "other"  # abstract | introduction | background | methodology | results | discussion | conclusion | references | appendix | front_matter | chapter | other
    kind_basis: str = "UNCLASSIFIED"  # TITLE_MATCH | UNCLASSIFIED | SYNTHETIC
    number: Optional[str] = None
    parent_id: Optional[str] = None
    page_start: int = 1
    page_end: int = 1
    detection: str = "TYPOGRAPHY"  # TYPOGRAPHY | PATTERN | SYNTHETIC_PREAMBLE | SYNTHETIC_DOCUMENT
    heading_bbox: Optional[List[float]] = None
    element_refs: List[Dict[str, str]] = field(default_factory=list)

    def __setattr__(self, name: str, value: Any) -> None:
        old_val = getattr(self, name, None) if hasattr(self, name) else None
        super().__setattr__(name, value)
        if name == "section_id" and old_val is not None and old_val != value:
            self._notify_change()


@dataclass
class ASTParagraph(ObservableASTNode):
    paragraph_id: str
    section_id: str
    text: str
    page_number: int
    page_end: int
    order: int
    content_type: str = "body"  # body | caption | front_matter | list_item | reference | ocr_body
    extraction_method: str = "PDF_TEXT_LAYER"  # PDF_TEXT_LAYER | OCR_WINDOWS
    extraction_status: str = "OK"  # OK | MERGED_ACROSS_PAGES | OCR_UNVERIFIED
    bbox: Optional[List[float]] = None
    bboxes: List[Dict[str, Any]] = field(default_factory=list)
    font_size: Optional[float] = None
    contains_math: bool = False
    normalizations: Dict[str, int] = field(default_factory=dict)
    sentence_spans: List[List[int]] = field(default_factory=list)
    linked_element_id: Optional[str] = None
    content_sha1: str = ""

    def __setattr__(self, name: str, value: Any) -> None:
        old_val = getattr(self, name, None) if hasattr(self, name) else None
        super().__setattr__(name, value)
        if name in ("paragraph_id", "section_id", "page_number") and old_val is not None and old_val != value:
            self._notify_change()


@dataclass
class ASTTable:
    table_id: str
    page_number: int
    section_id: str
    order: int
    caption: Optional[str] = None
    caption_paragraph_id: Optional[str] = None
    bbox: Optional[List[float]] = None
    rows: List[List[str]] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    header_row_index: Optional[int] = None
    header_status: str = "NONE"  # BOLD_FIRST_ROW | ASSUMED_FIRST_ROW | NONE
    structure_status: str = "CAPTION_ONLY"  # RECONSTRUCTED | PARTIAL | CAPTION_ONLY
    extraction_method: str = "NONE"  # PYMUPDF_LINES | PYMUPDF_TEXT | PDFPLUMBER_LINES | NONE
    limitations: List[str] = field(default_factory=list)


@dataclass
class ASTFigure:
    figure_id: str
    page_number: int
    section_id: str
    order: int
    element_kind: str = "RASTER_IMAGE"  # RASTER_IMAGE | VECTOR_GRAPHIC | CAPTION_ONLY
    caption: Optional[str] = None
    caption_paragraph_id: Optional[str] = None
    bbox: Optional[List[float]] = None
    asset_ref: Optional[str] = None
    asset_sha256: Optional[str] = None
    asset_status: str = "EXTRACTED"  # EXTRACTED | RENDERED_FROM_PAGE | EXTRACTION_FAILED | NOT_FOUND
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    effective_dpi: Optional[float] = None
    is_decorative_candidate: bool = False
    decorative_reason: Optional[str] = None
    embedded_text: str = ""
    # Estados de interpretação — a Fase 2 NUNCA interpreta gráficos.
    interpretation_status: str = "IMAGE_ONLY_NOT_INTERPRETED"
    chart_type: Optional[str] = None
    underlying_data_recovered: bool = False
    limitations: List[str] = field(default_factory=list)


@dataclass
class ASTFormula:
    formula_id: str
    page_number: int
    section_id: str
    order: int
    raw_text: str = ""
    equation_number: Optional[str] = None
    bbox: Optional[List[float]] = None
    display: bool = True
    representation: str = "RAW_TEXT_EXTRACTION"
    latex: Optional[str] = None
    structure_status: str = "UNPARSED"
    asset_ref: Optional[str] = None
    asset_sha256: Optional[str] = None
    limitations: List[str] = field(default_factory=list)


@dataclass
class ASTReference:
    reference_id: str
    raw: str
    section_id: str
    page_number: int
    marker: Optional[str] = None
    authors_raw: Optional[str] = None
    year: Optional[str] = None
    title: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    parse_status: str = "RAW_ONLY"  # PARSED_PARTIAL | RAW_ONLY
    paragraph_id: Optional[str] = None


@dataclass
class PageArtifact:
    page_number: int
    text: str
    reason: str  # RUNNING_HEADER_FOOTER | PAGE_NUMBER
    bbox: Optional[List[float]] = None


@dataclass
class DocumentMetadata:
    title: Optional[str] = None
    title_source: Optional[str] = None
    subtitle: Optional[str] = None
    subtitle_source: Optional[str] = None
    authors: List[Dict[str, Any]] = field(default_factory=list)
    authors_source: Optional[str] = None
    affiliations: List[Dict[str, Any]] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    publication_date: Optional[Dict[str, Any]] = None
    doi: Optional[str] = None
    doi_source: Optional[str] = None
    abstract: Optional[str] = None
    abstract_source: Optional[str] = None
    abstract_paragraph_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    keywords_source: Optional[str] = None
    page_count: int = 0
    filename: Optional[str] = None
    source_sha256: Optional[str] = None
    size_bytes: int = 0
    pdf_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionReport:
    status: str = "COMPLETED"  # COMPLETED | PARTIAL | FAILED
    total_pages: int = 0
    pages_with_text_layer: int = 0
    pages_ocr: int = 0
    pages_ocr_attempted: int = 0
    pages_unrecovered: List[int] = field(default_factory=list)
    pages_empty: List[int] = field(default_factory=list)
    multi_column_pages: List[int] = field(default_factory=list)
    sections_identified: int = 0
    paragraphs: int = 0
    tables_identified: int = 0
    tables_structure_reconstructed: int = 0
    tables_partial: int = 0
    tables_caption_only: int = 0
    images_found: int = 0
    figures_identified: int = 0
    figures_decorative_candidates: int = 0
    figures_interpreted: int = 0  # sempre 0 na Fase 2
    formulas_identified: int = 0
    formulas_converted: int = 0  # sempre 0 na Fase 2 (apenas texto bruto + recorte)
    references_identified: int = 0
    references_parsed_partial: int = 0
    page_artifacts_separated: int = 0
    text_accounting: Dict[str, Any] = field(default_factory=dict)
    not_interpreted: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    note: str = (
        "Contagens indicam elementos IDENTIFICADOS, não interpretados. 'text_accounting' mede captura do texto "
        "da camada PDF, não compreensão semântica."
    )


class VersionedList(list):
    """
    Subclasse de list com sinalização de mutação e observação atómica de nós AST.
    Cobre: append, extend, insert, remove, pop, clear, __setitem__, __delitem__,
    sort, reverse, __iadd__, __imul__, e slice assignments.
    Garante consistência automática com os índices secundários da AST sem custo O(N) nas leituras.
    """

    def __init__(self, iterable=None, on_mutation: Optional[Callable[[], None]] = None):
        super().__init__(iterable or [])
        self.version = 0
        self.on_mutation = on_mutation
        for item in self:
            self._hook_item(item)

    def _hook_item(self, item: Any) -> None:
        if hasattr(item, "_set_observer") and callable(getattr(item, "_set_observer")):
            item._set_observer(self._on_item_mutated)

    def _unhook_item(self, item: Any) -> None:
        if hasattr(item, "_set_observer") and callable(getattr(item, "_set_observer")):
            item._set_observer(None)

    def _on_item_mutated(self) -> None:
        self.version += 1
        if self.on_mutation is not None:
            self.on_mutation()

    def _notify(self) -> None:
        self.version += 1
        if self.on_mutation is not None:
            self.on_mutation()

    def append(self, item: Any) -> None:
        self._hook_item(item)
        super().append(item)
        self._notify()

    def extend(self, iterable: Any) -> None:
        items = list(iterable)
        for item in items:
            self._hook_item(item)
        super().extend(items)
        self._notify()

    def insert(self, index: int, item: Any) -> None:
        self._hook_item(item)
        super().insert(index, item)
        self._notify()

    def remove(self, item: Any) -> None:
        self._unhook_item(item)
        super().remove(item)
        self._notify()

    def pop(self, index: int = -1) -> Any:
        res = super().pop(index)
        self._unhook_item(res)
        self._notify()
        return res

    def clear(self) -> None:
        for item in self:
            self._unhook_item(item)
        super().clear()
        self._notify()

    def __setitem__(self, index: Any, item: Any) -> None:
        if isinstance(index, slice):
            old_items = self[index]
            for it in old_items:
                self._unhook_item(it)
            new_items = list(item)
            for it in new_items:
                self._hook_item(it)
            super().__setitem__(index, new_items)
        else:
            if 0 <= index < len(self) or (-len(self) <= index < 0):
                self._unhook_item(self[index])
            self._hook_item(item)
            super().__setitem__(index, item)
        self._notify()

    def __delitem__(self, index: Any) -> None:
        if isinstance(index, slice):
            old_items = self[index]
            for it in old_items:
                self._unhook_item(it)
        else:
            if 0 <= index < len(self) or (-len(self) <= index < 0):
                self._unhook_item(self[index])
        super().__delitem__(index)
        self._notify()

    def sort(self, *args: Any, **kwargs: Any) -> None:
        super().sort(*args, **kwargs)
        self._notify()

    def reverse(self) -> None:
        super().reverse()
        self._notify()

    def __iadd__(self, other: Any) -> "VersionedList":
        items = list(other)
        for item in items:
            self._hook_item(item)
        super().__iadd__(items)
        self._notify()
        return self

    def __imul__(self, n: int) -> "VersionedList":
        super().__imul__(n)
        for item in self:
            self._hook_item(item)
        self._notify()
        return self


@dataclass
class AcademicDocumentAST:
    document_id: str
    schema_version: str = SCHEMA_VERSION
    extractor_version: str = EXTRACTOR_VERSION
    source_sha256: str = ""
    filename: str = ""
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    pages: List[PageInfo] = field(default_factory=list)
    sections: List[ASTSection] = field(default_factory=list)
    paragraphs: List[ASTParagraph] = field(default_factory=list)
    tables: List[ASTTable] = field(default_factory=list)
    figures: List[ASTFigure] = field(default_factory=list)
    formulas: List[ASTFormula] = field(default_factory=list)
    references: List[ASTReference] = field(default_factory=list)
    page_artifacts: List[PageArtifact] = field(default_factory=list)
    report: ExtractionReport = field(default_factory=ExtractionReport)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_paragraphs_version", 0)
        object.__setattr__(self, "_sections_version", 0)
        object.__setattr__(self, "_pages_version", 0)
        if not isinstance(self.paragraphs, VersionedList):
            self.paragraphs = VersionedList(self.paragraphs, on_mutation=lambda: self._on_paragraphs_mutated())
        else:
            self.paragraphs.on_mutation = lambda: self._on_paragraphs_mutated()
        if not isinstance(self.sections, VersionedList):
            self.sections = VersionedList(self.sections, on_mutation=lambda: self._on_sections_mutated())
        else:
            self.sections.on_mutation = lambda: self._on_sections_mutated()
        if not isinstance(self.pages, VersionedList):
            self.pages = VersionedList(self.pages, on_mutation=lambda: self._on_pages_mutated())
        else:
            self.pages.on_mutation = lambda: self._on_pages_mutated()

    def _on_paragraphs_mutated(self) -> None:
        object.__setattr__(self, "_paragraphs_version", getattr(self, "_paragraphs_version", 0) + 1)
        self.invalidate_indices()

    def _on_sections_mutated(self) -> None:
        object.__setattr__(self, "_sections_version", getattr(self, "_sections_version", 0) + 1)
        self.invalidate_indices()

    def _on_pages_mutated(self) -> None:
        object.__setattr__(self, "_pages_version", getattr(self, "_pages_version", 0) + 1)
        self.invalidate_indices()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcademicDocumentAST":
        d = dict(data or {})
        return cls(
            document_id=d.get("document_id", ""),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            extractor_version=d.get("extractor_version", EXTRACTOR_VERSION),
            source_sha256=d.get("source_sha256", ""),
            filename=d.get("filename", ""),
            metadata=_from_dict(DocumentMetadata, d.get("metadata")),
            pages=[_from_dict(PageInfo, x) for x in d.get("pages", [])],
            sections=[_from_dict(ASTSection, x) for x in d.get("sections", [])],
            paragraphs=[_from_dict(ASTParagraph, x) for x in d.get("paragraphs", [])],
            tables=[_from_dict(ASTTable, x) for x in d.get("tables", [])],
            figures=[_from_dict(ASTFigure, x) for x in d.get("figures", [])],
            formulas=[_from_dict(ASTFormula, x) for x in d.get("formulas", [])],
            references=[_from_dict(ASTReference, x) for x in d.get("references", [])],
            page_artifacts=[_from_dict(PageArtifact, x) for x in d.get("page_artifacts", [])],
            report=_from_dict(ExtractionReport, d.get("report")),
        )

    # -- Projeções de compatibilidade e índices secundários O(1) consistentes --

    def _get_lock(self) -> threading.RLock:
        """Lock reentrante para operações thread-safe sobre a AST e os seus índices."""
        lock = getattr(self, "_lock", None)
        if lock is None:
            lock = threading.RLock()
            object.__setattr__(self, "_lock", lock)
        return lock

    @property
    def paragraphs_by_id(self) -> Dict[str, ASTParagraph]:
        """Índice secundário O(1) de parágrafos por paragraph_id (com invalidação automática por versionamento)."""
        with self._get_lock():
            cached = getattr(self, "_cached_paragraphs_by_id", None)
            cached_ver = getattr(self, "_cached_paras_ver", -1)
            cur_ver = getattr(self.paragraphs, "version", getattr(self, "_paragraphs_version", 0))
            if cached is None or cached_ver != cur_ver:
                cached = {p.paragraph_id: p for p in self.paragraphs}
                object.__setattr__(self, "_cached_paragraphs_by_id", cached)
                object.__setattr__(self, "_cached_paras_ver", cur_ver)
            return cached

    @property
    def sections_by_id(self) -> Dict[str, ASTSection]:
        """Índice secundário O(1) de secções por section_id."""
        with self._get_lock():
            cached = getattr(self, "_cached_sections_by_id", None)
            cached_ver = getattr(self, "_cached_sec_ver", -1)
            cur_ver = getattr(self.sections, "version", getattr(self, "_sections_version", 0))
            if cached is None or cached_ver != cur_ver:
                cached = {s.section_id: s for s in self.sections}
                object.__setattr__(self, "_cached_sections_by_id", cached)
                object.__setattr__(self, "_cached_sec_ver", cur_ver)
            return cached

    @property
    def paragraphs_by_section_id(self) -> Dict[str, List[ASTParagraph]]:
        """Índice secundário O(1) de agrupamento de parágrafos por section_id."""
        with self._get_lock():
            cached = getattr(self, "_cached_paragraphs_by_sec", None)
            cached_ver = getattr(self, "_cached_paras_sec_ver", -1)
            cur_ver = getattr(self.paragraphs, "version", getattr(self, "_paragraphs_version", 0))
            if cached is None or cached_ver != cur_ver:
                group: Dict[str, List[ASTParagraph]] = defaultdict(list)
                for p in self.paragraphs:
                    group[p.section_id].append(p)
                cached = dict(group)
                object.__setattr__(self, "_cached_paragraphs_by_sec", cached)
                object.__setattr__(self, "_cached_paras_sec_ver", cur_ver)
            return cached

    @property
    def pages_by_number(self) -> Dict[int, PageInfo]:
        """Índice secundário O(1) de páginas por page_number."""
        with self._get_lock():
            cached = getattr(self, "_cached_pages_by_number", None)
            cached_ver = getattr(self, "_cached_pages_ver", -1)
            cur_ver = getattr(self.pages, "version", getattr(self, "_pages_version", 0))
            if cached is None or cached_ver != cur_ver:
                cached = {pg.page_number: pg for pg in self.pages}
                object.__setattr__(self, "_cached_pages_by_number", cached)
                object.__setattr__(self, "_cached_pages_ver", cur_ver)
            return cached

    def get_paragraph(self, paragraph_id: str) -> Optional[ASTParagraph]:
        """Acesso O(1) a parágrafo por ID."""
        return self.paragraphs_by_id.get(paragraph_id)

    def get_section(self, section_id: str) -> Optional[ASTSection]:
        """Acesso O(1) a secção por ID."""
        return self.sections_by_id.get(section_id)

    def get_paragraphs_for_section(self, section_id: str) -> List[ASTParagraph]:
        """Acesso O(1) a lista de parágrafos de uma secção específica."""
        return self.paragraphs_by_section_id.get(section_id, [])

    def get_page(self, page_number: int) -> Optional[PageInfo]:
        """Acesso O(1) a página por número."""
        return self.pages_by_number.get(page_number)

    def invalidate_indices(self) -> None:
        """Invalida explicitamente os caches de índices após mutações diretas da AST."""
        with self._get_lock():
            object.__setattr__(self, "_cached_paras_ver", -1)
            object.__setattr__(self, "_cached_sec_ver", -1)
            object.__setattr__(self, "_cached_paras_sec_ver", -1)
            object.__setattr__(self, "_cached_pages_ver", -1)
            for attr in (
                "_cached_paragraphs_by_id",
                "_cached_sections_by_id",
                "_cached_paragraphs_by_sec",
                "_cached_pages_by_number",
            ):
                if hasattr(self, attr):
                    try:
                        delattr(self, attr)
                    except AttributeError:
                        pass

    # -- Métodos de mutação controlada com invalidação atómica de índices --------------

    def add_paragraph(self, paragraph: ASTParagraph) -> None:
        """Adiciona um parágrafo e invalida os índices afetados."""
        self.paragraphs.append(paragraph)

    def remove_paragraph(self, paragraph_id: str) -> bool:
        """Remove um parágrafo por ID e invalida os índices afetados."""
        idx = next((i for i, p in enumerate(self.paragraphs) if p.paragraph_id == paragraph_id), None)
        if idx is not None:
            self.paragraphs.pop(idx)
            return True
        return False

    def update_paragraph(self, target_paragraph_id: str, **kwargs: Any) -> Optional[ASTParagraph]:
        """Atualiza atributos de um parágrafo existente e invalida os índices."""
        p = self.get_paragraph(target_paragraph_id)
        if p is not None:
            for k, v in kwargs.items():
                if hasattr(p, k):
                    setattr(p, k, v)
            self._on_paragraphs_mutated()
            return p
        return None

    def add_section(self, section: ASTSection) -> None:
        """Adiciona uma secção e invalida os índices afetados."""
        self.sections.append(section)

    def remove_section(self, section_id: str) -> bool:
        """Remove uma secção por ID e invalida os índices afetados."""
        idx = next((i for i, s in enumerate(self.sections) if s.section_id == section_id), None)
        if idx is not None:
            self.sections.pop(idx)
            return True
        return False

    def update_section(self, target_section_id: str, **kwargs: Any) -> Optional[ASTSection]:
        """Atualiza atributos de uma secção existente e invalida os índices."""
        s = self.get_section(target_section_id)
        if s is not None:
            for k, v in kwargs.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            self._on_sections_mutated()
            return s
        return None

    def add_page(self, page: PageInfo) -> None:
        """Adiciona uma página e invalida os índices afetados."""
        self.pages.append(page)

    def update_page(self, target_page_number: int, **kwargs: Any) -> Optional[PageInfo]:
        """Atualiza atributos de uma página existente e invalida os índices."""
        pg = self.get_page(target_page_number)
        if pg is not None:
            for k, v in kwargs.items():
                if hasattr(pg, k):
                    setattr(pg, k, v)
            self._on_pages_mutated()
            return pg
        return None

    def to_legacy_sections(self) -> List[Dict[str, Any]]:
        """Projeção ``sections`` legada (section_id/title/level/page_start/page_end/paragraphs)."""
        by_sec = self.paragraphs_by_section_id
        out: List[Dict[str, Any]] = []
        for s in self.sections:
            paras = [p for p in by_sec.get(s.section_id, []) if p.content_type != "front_matter"]
            if not paras:
                continue
            out.append({
                "section_id": s.section_id,
                "title": s.title,
                "level": s.level,
                "kind": s.kind,
                "page_start": s.page_start,
                "page_end": s.page_end,
                "paragraphs": [
                    {
                        "paragraph_id": p.paragraph_id,
                        "text": p.text,
                        "page_number": p.page_number,
                        "section_id": p.section_id,
                        "order": p.order,
                        "content_type": p.content_type,
                        "bbox": p.bbox,
                    }
                    for p in sorted(paras, key=lambda x: x.order)
                ],
            })
        return out

    def to_legacy_media(self) -> List[Dict[str, Any]]:
        media: List[Dict[str, Any]] = []
        for t in self.tables:
            cap = t.caption or ""
            media.append({
                "media_id": t.table_id,
                "media_type": "table",
                "title": (cap[:60] if cap else f"Tabela (p. {t.page_number})"),
                "caption": cap or f"Tabela identificada na página {t.page_number}",
                "page_number": t.page_number,
                "data_ref": "",
                "evidence_status": "OBSERVED",
                "section_id": t.section_id,
                "bbox": t.bbox,
                "structure_status": t.structure_status,
                "n_rows": t.n_rows,
                "n_cols": t.n_cols,
            })
        for f in self.figures:
            if f.is_decorative_candidate and not f.caption:
                continue
            cap = f.caption or ""
            media.append({
                "media_id": f.figure_id,
                "media_type": "figure",
                "title": (cap[:60] if cap else f"Figura / imagem (p. {f.page_number})"),
                "caption": cap or f"Elemento visual extraído da página {f.page_number}",
                "page_number": f.page_number,
                "data_ref": f.asset_ref or "",
                "evidence_status": "OBSERVED",
                "section_id": f.section_id,
                "bbox": f.bbox,
                "element_kind": f.element_kind,
                "interpretation_status": f.interpretation_status,
            })
        return media

    def to_pages_text(self) -> List[str]:
        """Texto por página em ordem de leitura (sem cabeçalhos/rodapés repetidos)."""
        parts: Dict[int, List[Tuple[float, str]]] = defaultdict(list)
        first_order: Dict[str, float] = {}
        for p in self.paragraphs:
            first_order[p.section_id] = min(first_order.get(p.section_id, p.order), p.order)
            parts[p.page_number].append((float(p.order), p.text))
        for s in self.sections:
            if s.detection in ("TYPOGRAPHY", "PATTERN"):
                heading = f"{s.number} {s.title}" if s.number else s.title
                parts[s.page_start].append((first_order.get(s.section_id, 0.0) - 0.5, heading))
        for t in self.tables:
            if t.rows:
                parts[t.page_number].append((float(t.order), "\n".join(" | ".join(r) for r in t.rows)))
        for fm in self.formulas:
            if fm.raw_text:
                parts[fm.page_number].append((float(fm.order), fm.raw_text))
        if self.metadata.title and self.metadata.title_source == "LAYOUT_LARGEST_TEXT_PAGE1":
            parts[1].append((-1e9, self.metadata.title))
        n = max(self.metadata.page_count, len(self.pages))
        return ["\n\n".join(txt for _o, txt in sorted(parts.get(i, []), key=lambda x: x[0])) for i in range(1, n + 1)]


# ---------------------------------------------------------------------------
# Utilitários de texto
# ---------------------------------------------------------------------------

_ABBREVIATIONS = {
    "al", "e.g", "i.e", "eg", "ie", "fig", "figs", "eq", "eqs", "no", "nos", "vs", "cf", "dr", "mr", "mrs", "ms",
    "prof", "inc", "ltd", "co", "etc", "approx", "sec", "secs", "ref", "refs", "vol", "pp", "p", "ed", "eds", "resp",
    "viz", "ca", "st", "jr", "sr", "dept", "univ", "ch", "tab", "ex", "exa", "sra", "sr", "dra", "pág", "págs", "cap",
}

_SENT_BOUNDARY = re.compile(r"([.!?]+[\"”’')\]]*)(\s+)(?=[A-ZÀ-Ý0-9\"“‘(\[])")


def sentence_spans(text: str) -> List[List[int]]:
    """Segmenta em frases COMPLETAS devolvendo offsets [início, fim) sobre o texto original (sem cortar)."""
    if not text or not text.strip():
        return []
    spans: List[List[int]] = []
    start = 0
    for m in _SENT_BOUNDARY.finditer(text):
        punct_start = m.start(1)
        before = text[start:punct_start]
        tok_m = re.search(r"([^\s(\[\"“]+)$", before)
        token = tok_m.group(1) if tok_m else ""
        low = token.lower().rstrip(".")
        if m.group(1).startswith("."):
            if low in _ABBREVIATIONS:
                continue
            if len(token) == 1 and token.isalpha() and token.isupper():
                continue  # inicial de nome (J. Smith)
            if re.fullmatch(r"(?:[A-Za-z]\.){1,}[A-Za-z]?", token):
                continue  # e.g., U.S.
        end = m.end(1)
        if end > start and text[start:end].strip():
            spans.append([start, end])
        start = m.end(2)
    if text[start:].strip():
        spans.append([start, len(text.rstrip())])
    return spans


def _norm_ws(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\u00a0", " ").replace("\u2009", " ").replace("\u200b", "")
    return re.sub(r"[ \t\r\f\v]+", " ", s).strip()


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:16]


def _join_lines(texts: List[str]) -> Tuple[str, int]:
    """Junta linhas de um bloco, des-hifenizando quebras de linha (palavra- + minúscula)."""
    out = ""
    dehyph = 0
    for t in texts:
        t = _norm_ws(t)
        if not t:
            continue
        if not out:
            out = t
            continue
        if re.search(r"[A-Za-zÀ-ÿ]{2,}-$", out) and re.match(r"[a-zà-ÿ]", t):
            out = out[:-1] + t
            dehyph += 1
        else:
            out = out + " " + t
    return out, dehyph


def _round_bbox(b) -> List[float]:
    return [round(float(x), 1) for x in b]


def _bbox_area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection_area(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _overlap_frac(inner, outer) -> float:
    """Fração da área de ``inner`` contida em ``outer``."""
    a = _bbox_area(inner)
    return _intersection_area(inner, outer) / a if a > 0 else 0.0


def _h_overlap(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    base = max(1.0, min(a[2] - a[0], b[2] - b[0]))
    return max(0.0, w) / base


_MATH_FONT = re.compile(r"(cmmi|cmsy|cmex|cmmib|msbm|msam|stix|cambria\s?math|symbol|mathematica|mtmi|mtsy|mtex|mt-extra|euclid|mathjax|latinmodern-math|xits)", re.I)
_MATH_CHARS = set("∑∏∫∂√∞≤≥≈≠≡±×÷∈∉⊂⊆∪∩∀∃∇∝→←↔⇒⇔αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ")
_CAPTION_SEP = re.compile(
    r"^\s*(?P<label>(?P<kind>Table|Tab\.|TABLE|Tabela|TABELA|Figure|Fig\.|FIG\.|FIGURE|Figura|FIGURA|Chart|Exhibit)\s*[A-Z]?\d+(?:\.\d+)?[a-z]?)\s*(?P<sep>[.:\-–—|])\s*(?P<rest>.*)$",
    re.S,
)
_CAPTION_BOLD_LABEL = re.compile(r"^\s*(Table|Tab\.|TABLE|Tabela|Figure|Fig\.|FIGURE|Figura)\s*[A-Z]?\d+(?:\.\d+)?[a-z]?\b", re.I)
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+|p\.\s*|pág\.?\s+)?(?:\d{1,4}|[ivxlcdm]{1,6})(?:\s*(?:of|de|/)\s*\d{1,4})?\s*$", re.I)
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.I)


def _is_bold_font(font: str, flags: int) -> bool:
    f = (font or "").lower()
    if flags & 16:
        return True
    if any(t in f for t in ("bold", "black", "heavy", "semibold", "demi", "-bd", ",bold")):
        return True
    return bool(re.search(r"[.\-_,]b(?:ld|d)?$", f))


def _is_italic_font(font: str, flags: int) -> bool:
    f = (font or "").lower()
    return bool(flags & 2) or any(t in f for t in ("italic", "oblique")) or bool(re.search(r"[.\-_,]i(?:t)?$", f))


def classify_section_title(title: str) -> Tuple[str, str]:
    """Classifica o papel da secção SÓ pelo título (não assume estrutura de artigo científico)."""
    t = re.sub(r"^\s*(?:(?:chapter|capítulo|cap\.)\s+)?[\dIVXivx]+(?:\.\d+)*\.?\s*[-–—:]?\s*", "", title or "", flags=re.I)
    t = re.sub(r"\s+", " ", t).strip().lower().rstrip(":.")
    rules: List[Tuple[str, Tuple[str, ...]]] = [
        ("abstract", ("abstract", "resumo", "summary", "executive summary", "sumário executivo", "abstract article info", "abstract/introduction")),
        ("introduction", ("introduction", "introdução", "introducao", "overview", "enquadramento")),
        ("background", ("background", "literature review", "related work", "related literature", "theoretical background", "theoretical framework", "estado da arte", "revisão da literatura", "revisão de literatura", "enquadramento teórico", "hypotheses development", "research model", "conceptual framework")),
        ("methodology", ("methodology", "methods", "method", "materials and methods", "research design", "research method", "data and methods", "data and methodology", "metodologia", "métodos", "método", "approach", "experimental setup")),
        ("results", ("results", "findings", "results and analysis", "results and discussion", "resultados", "data analysis", "empirical results", "analysis and results", "evaluation", "experiments")),
        ("discussion", ("discussion", "discussão", "discussao", "implications", "theoretical implications")),
        ("limitations", ("limitations", "limitações", "limitations and future work", "limitations and future research")),
        ("conclusion", ("conclusion", "conclusions", "conclusão", "conclusões", "concluding remarks", "final remarks", "conclusion and future work", "conclusions and future work")),
        ("acknowledgements", ("acknowledgments", "acknowledgements", "acknowledgment", "agradecimentos")),
        ("references", ("references", "reference list", "bibliography", "referências", "referencias", "bibliografia", "works cited", "literature cited")),
        ("appendix", ("appendix", "appendices", "apêndice", "apêndices", "anexo", "anexos")),
    ]
    for kind, names in rules:
        for n in names:
            if t == n or (n in t and len(t) <= 35) or (t.startswith(n + " ") and kind in ("appendix", "abstract", "references")):
                return kind, "TITLE_MATCH"
    if re.match(r"^(?:chapter|capítulo)\s+[\dIVXivx]+", (title or "").strip(), flags=re.I):
        return "chapter", "TITLE_MATCH"
    return "other", "UNCLASSIFIED"


_HEADING_NUMBER = re.compile(r"^\s*(?P<num>(?:\d+|[IVX]+|[A-Z])(?:\.\d+)*)\s*[.)]?\s+(?P<title>\S.*)$")


# ---------------------------------------------------------------------------
# Leitura de blocos (camada de texto PDF)
# ---------------------------------------------------------------------------

def _read_blocks(page) -> List[Dict[str, Any]]:
    d = page.get_text("dict")
    out: List[Dict[str, Any]] = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        lines: List[Dict[str, Any]] = []
        for l in b.get("lines", []):
            spans = [s for s in l.get("spans", []) if s.get("text")]
            txt = "".join(s["text"] for s in spans)
            if not txt.strip():
                continue
            n_chars = sum(len(s["text"]) for s in spans) or 1
            size_w: Counter = Counter()
            bold_chars = italic_chars = math_font = math_char = 0
            for s in spans:
                L = len(s["text"])
                size_w[round(s["size"], 1)] += L
                if _is_bold_font(s.get("font", ""), s.get("flags", 0)):
                    bold_chars += L
                if _is_italic_font(s.get("font", ""), s.get("flags", 0)):
                    italic_chars += L
                if _MATH_FONT.search(s.get("font", "")):
                    math_font += L
                math_char += sum(1 for c in s["text"] if c in _MATH_CHARS)
            lines.append({
                "text": txt,
                "bbox": [float(x) for x in l["bbox"]],
                "size": size_w.most_common(1)[0][0],
                "bold": bold_chars / n_chars >= 0.6,
                "italic": italic_chars / n_chars >= 0.6,
                "math_font": math_font,
                "math_char": math_char,
                "n": n_chars,
            })
        if not lines:
            continue
        total = sum(l["n"] for l in lines) or 1
        size_w2: Counter = Counter()
        for l in lines:
            size_w2[l["size"]] += l["n"]
        text, dehyph = _join_lines([l["text"] for l in lines])
        out.append({
            "bbox": [float(x) for x in b["bbox"]],
            "lines": lines,
            "text": text,
            "dehyph": dehyph,
            "size": size_w2.most_common(1)[0][0],
            "bold": sum(l["n"] for l in lines if l["bold"]) / total >= 0.6,
            "italic": sum(l["n"] for l in lines if l["italic"]) / total >= 0.6,
            "math_font_frac": sum(l["math_font"] for l in lines) / total,
            "math_char_frac": sum(l["math_char"] for l in lines) / total,
            "raw_chars": sum(1 for l in lines for c in l["text"] if not c.isspace()),
            "role": "text",
        })
    return out


def _order_blocks(blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Ordem de leitura com suporte a várias colunas (bandas separadas por blocos de largura total)."""
    if not blocks:
        return [], 1
    x0 = min(b["bbox"][0] for b in blocks)
    x1 = max(b["bbox"][2] for b in blocks)
    cw = max(1.0, x1 - x0)
    full = [b for b in blocks if (b["bbox"][2] - b["bbox"][0]) >= 0.62 * cw]
    full_ids = {id(b) for b in full}
    ordered: List[Dict[str, Any]] = []
    max_cols = 1
    band: List[Dict[str, Any]] = []

    def flush_band():
        nonlocal band, max_cols
        if not band:
            return
        cols = _split_columns(band)
        if len(cols) > 1:
            max_cols = max(max_cols, len(cols))
            for c in cols:
                ordered.extend(sorted(c, key=lambda b: (b["bbox"][1], b["bbox"][0])))
        else:
            ordered.extend(sorted(band, key=lambda b: (b["bbox"][1], b["bbox"][0])))
        band = []

    for b in sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0])):
        if id(b) in full_ids:
            flush_band()
            ordered.append(b)
        else:
            band.append(b)
    flush_band()
    return ordered, max_cols


def _split_columns(band: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    if len(band) < 2:
        return [band]
    intervals = sorted([(b["bbox"][0], b["bbox"][2]) for b in band])
    merged: List[List[float]] = []
    for a, c in intervals:
        if merged and a <= merged[-1][1] + 5.0:
            merged[-1][1] = max(merged[-1][1], c)
        else:
            merged.append([a, c])
    if len(merged) < 2:
        return [band]
    cols: List[List[Dict[str, Any]]] = [[] for _ in merged]
    for b in band:
        cx = (b["bbox"][0] + b["bbox"][2]) / 2
        for i, (a, c) in enumerate(merged):
            if a - 1 <= cx <= c + 1:
                cols[i].append(b)
                break
    cols = [c for c in cols if c]
    return cols if len(cols) > 1 else [band]


# ---------------------------------------------------------------------------
# OCR (opcional) — reutiliza o OCR offline do projeto (Windows.Media.Ocr)
# ---------------------------------------------------------------------------

def _default_ocr(image_paths: List[str]) -> Tuple[Dict[str, str], str]:
    from services.study_ai_engine import extract_keyframes_ocr_windows_with_status
    return extract_keyframes_ocr_windows_with_status(image_paths)


def _text_layer_reliable(blocks: List[Dict[str, Any]]) -> Tuple[bool, str]:
    text = " ".join(b["text"] for b in blocks)
    visible = [c for c in text if not c.isspace()]
    bad = text.count("\ufffd") + text.count("(cid:") * 6
    if visible and bad / len(visible) > 0.04:
        return False, "camada de texto corrompida (caracteres de substituição / cid)"
    if len(visible) < 25:
        return False, "sem texto selecionável suficiente"
    return True, ""


# ---------------------------------------------------------------------------
# Extrator principal
# ---------------------------------------------------------------------------

class DocumentIntelligenceExtractor:
    def __init__(
        self,
        *,
        ocr_enabled: bool = True,
        ocr_fn: Optional[Callable[[List[str]], Tuple[Dict[str, str], str]]] = None,
        assets_dir: Optional[str | Path] = None,
        ocr_dpi: int = 200,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.ocr_fn = ocr_fn or _default_ocr
        self.assets_dir = Path(assets_dir) if assets_dir else None
        self.ocr_dpi = ocr_dpi

    # ------------------------------------------------------------------ public

    def extract(
        self,
        pdf_path: str | Path,
        document_id: str,
        *,
        filename: Optional[str] = None,
        source_hash: Optional[str] = None,
    ) -> AcademicDocumentAST:
        if pymupdf is None:
            raise DocumentExtractionError("PyMuPDF não está instalado; não é possível extrair PDFs.")
        t0 = time.perf_counter()
        pdf_path = Path(pdf_path)
        max_bytes = int(os.environ.get("STUDY_MAX_PDF_BYTES", str(256 * 1024 * 1024)) or (256 * 1024 * 1024))
        max_pages = int(os.environ.get("STUDY_MAX_PDF_PAGES", "1500") or 1500)
        try:
            file_size = pdf_path.stat().st_size
            if file_size > max_bytes:
                raise DocumentExtractionError(
                    f"PDF excede o limite de tamanho configurado ({file_size} > {max_bytes} bytes)."
                )
            raw_bytes = pdf_path.read_bytes()
        except OSError as e:
            raise DocumentExtractionError(f"Não foi possível ler o ficheiro: {e}") from e
        sha = source_hash or hashlib.sha256(raw_bytes).hexdigest()
        try:
            pdf = pymupdf.open(stream=raw_bytes, filetype="pdf")
        except Exception as e:
            raise DocumentExtractionError(f"PDF ilegível ou corrompido: {e}") from e
        try:
            if pdf.needs_pass:
                raise DocumentExtractionError("PDF protegido por palavra-passe.")
            if pdf.page_count == 0:
                raise DocumentExtractionError("PDF sem páginas.")
            if pdf.page_count > max_pages:
                raise DocumentExtractionError(
                    f"PDF excede o limite de páginas configurado ({pdf.page_count} > {max_pages})."
                )
            return self._extract(pdf, pdf_path, document_id, filename or pdf_path.name, sha, len(raw_bytes), t0)
        finally:
            pdf.close()

    # ---------------------------------------------------------------- pipeline

    def _extract(self, pdf, pdf_path: Path, document_id: str, filename: str, sha: str, size: int, t0: float) -> AcademicDocumentAST:
        n_pages = pdf.page_count
        ast = AcademicDocumentAST(document_id=document_id, source_sha256=sha, filename=filename)
        rep = ast.report
        rep.total_pages = n_pages
        asset_cache: Dict[int, Tuple[str, str]] = {}

        page_blocks: Dict[int, List[Dict[str, Any]]] = {}
        page_infos: Dict[int, PageInfo] = {}

        # 1) Ler blocos de texto de todas as páginas
        for i in range(n_pages):
            page = pdf[i]
            pn = i + 1
            info = PageInfo(page_number=pn, width=round(page.rect.width, 1), height=round(page.rect.height, 1), rotation=page.rotation)
            try:
                blocks = _read_blocks(page)
            except Exception as e:  # página isolada falhada não derruba o documento
                blocks = []
                rep.errors.append(f"Página {pn}: erro na leitura do texto ({e})")
            info.block_count = len(blocks)
            info.char_count = sum(b["raw_chars"] for b in blocks)
            page_blocks[pn] = blocks
            page_infos[pn] = info

        # 2) Decidir quais páginas precisam de OCR e executá-lo
        ocr_pages: Dict[int, List[str]] = {}
        self._run_ocr(pdf, page_blocks, page_infos, rep, ocr_pages)

        # 3) Cabeçalhos/rodapés repetidos e números de página (documento inteiro)
        self._separate_artifacts(ast, page_blocks, page_infos)

        # 4) Elementos não textuais, tabelas, figuras e fórmulas por página
        items: List[Dict[str, Any]] = []
        figure_xref_pages: Dict[int, set] = defaultdict(set)
        for pn in range(1, n_pages + 1):
            page = pdf[pn - 1]
            info = page_infos[pn]
            blocks = [b for b in page_blocks[pn] if b["role"] == "text"]
            if info.text_source == "OCR_WINDOWS":
                for para in ocr_pages.get(pn, []):
                    items.append({"type": "ocr_block", "page": pn, "text": para, "y": 0.0})
                continue
            try:
                page_items, ncols = self._process_page(pdf, page, pn, blocks, info, rep, asset_cache, figure_xref_pages)
            except Exception as e:
                rep.errors.append(f"Página {pn}: erro na análise estrutural ({e}); texto preservado como blocos simples")
                ordered, ncols = _order_blocks(blocks)
                page_items = [{"type": "block", "page": pn, "block": b} for b in ordered]
            info.columns_detected = ncols
            if ncols > 1:
                rep.multi_column_pages.append(pn)
            items.extend(page_items)

        # 5) Estrutura: título, secções, parágrafos, referências
        self._build_structure(ast, pdf, items, page_infos)

        # 6) Metadados
        self._build_metadata(ast, pdf, items, size)

        # 7) Relatório
        ast.pages = [page_infos[i] for i in range(1, n_pages + 1)]
        self._finalize_report(ast, page_blocks, t0)
        return ast

    # --------------------------------------------------------------------- OCR

    def _run_ocr(self, pdf, page_blocks, page_infos, rep: ExtractionReport, ocr_pages: Dict[int, List[str]]) -> None:
        need: List[int] = []
        corrupted_pages: set = set()
        for pn, blocks in page_blocks.items():
            ok, why = _text_layer_reliable(blocks)
            info = page_infos[pn]
            if ok:
                info.text_source = "TEXT_LAYER"
                continue
            page = pdf[pn - 1]
            try:
                imgs = page.get_image_info()
                cover = sum(_bbox_area(im["bbox"]) for im in imgs) / max(1.0, page.rect.width * page.rect.height)
            except Exception:
                cover = 0.0
            info.image_coverage = round(min(cover, 1.0), 3)
            corrupted = why.startswith("camada de texto corrompida")
            if not corrupted and cover < 0.25:
                # página genuinamente esparsa (divisória, título, quase em branco): o texto existente é fiável
                if blocks:
                    info.text_source = "TEXT_LAYER"
                else:
                    info.text_source = "NONE"
                    info.status = "EMPTY"
                    info.warnings.append("página sem texto nem imagem relevante (possivelmente em branco)")
                    rep.pages_empty.append(pn)
                continue
            if corrupted:
                corrupted_pages.add(pn)
            info.warnings.append(f"camada de texto não utilizável: {why}")
            need.append(pn)

        if not need:
            return
        if not self.ocr_enabled:
            for pn in need:
                self._mark_unrecovered(page_infos[pn], page_blocks, rep, pn, "OCR desativado e camada de texto não utilizável", pn in corrupted_pages)
            return

        tmpdir = Path(tempfile.mkdtemp(prefix="jarvis_ocr_"))
        try:
            paths: Dict[int, str] = {}
            for pn in need:
                page = pdf[pn - 1]
                png = tmpdir / f"page_{pn:04d}.png"
                pix = page.get_pixmap(dpi=self.ocr_dpi)
                pix.save(str(png))
                paths[pn] = str(png.resolve())
                if self.assets_dir is not None:
                    self.assets_dir.mkdir(parents=True, exist_ok=True)
                    keep = self.assets_dir / f"page_{pn:04d}.png"
                    shutil.copyfile(png, keep)
                    page_infos[pn].page_image_ref = f"assets/{keep.name}"
            rep.pages_ocr_attempted += len(need)
            results: Dict[str, str] = {}
            unavailable = True
            plist = [paths[p] for p in need]
            for k in range(0, len(plist), 5):
                try:
                    res, st = self.ocr_fn(plist[k:k + 5])
                    results.update({os.path.abspath(a): b for a, b in (res or {}).items()})
                    if st != "OCR_UNAVAILABLE":
                        unavailable = False
                except Exception as e:
                    rep.warnings.append(f"OCR falhou num lote de páginas: {e}")
            for pn in need:
                txt = (results.get(os.path.abspath(paths[pn])) or "").strip()
                info = page_infos[pn]
                if txt:
                    info.text_source = "OCR_WINDOWS"
                    info.status = "OCR_RECOVERED"
                    info.char_count = sum(1 for c in txt if not c.isspace())
                    ocr_pages[pn] = _segment_ocr_text(txt)
                    page_blocks[pn] = []  # a camada de texto inutilizável não é usada
                else:
                    self._mark_unrecovered(
                        info, page_blocks, rep, pn,
                        "OCR indisponível neste sistema" if unavailable else "OCR não reconheceu texto",
                        pn in corrupted_pages,
                    )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _mark_unrecovered(info: PageInfo, page_blocks, rep: ExtractionReport, pn: int, reason: str, discard_text: bool) -> None:
        """Página sem camada de texto utilizável e sem OCR: limitação explícita (nunca silenciosa)."""
        info.status = "UNRECOVERED"
        info.warnings.append(reason)
        rep.pages_unrecovered.append(pn)
        rep.not_interpreted.append({"page": pn, "kind": "PAGE", "reason": reason})
        if discard_text:
            page_blocks[pn] = []  # texto corrompido (cid/U+FFFD) não é aproveitável; descarte reportado acima
            info.text_source = "NONE"
        else:
            info.text_source = "TEXT_LAYER" if page_blocks[pn] else "NONE"

    # --------------------------------------------------------------- artefactos

    def _separate_artifacts(self, ast: AcademicDocumentAST, page_blocks, page_infos) -> None:
        n = len(page_blocks)
        keyed: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
        for pn, blocks in page_blocks.items():
            H = page_infos[pn].height or 1.0
            for b in blocks:
                y0, y1 = b["bbox"][1], b["bbox"][3]
                in_margin = y1 <= 0.095 * H or y0 >= 0.905 * H
                b["in_margin"] = in_margin
                if not in_margin:
                    continue
                key = re.sub(r"\d+", "#", re.sub(r"\s+", " ", b["text"].lower())).strip()
                if key:
                    keyed[key].append((pn, b))
        min_pages = 2 if n == 2 else max(2, math.ceil(0.3 * n))
        for key, occ in keyed.items():
            pages_hit = {p for p, _ in occ}
            for pn, b in occ:
                reason = None
                if _PAGE_NUMBER.match(b["text"]):
                    reason = "PAGE_NUMBER"
                elif n >= 2 and len(pages_hit) >= min_pages and (n >= 3 or len(pages_hit) == n):
                    reason = "RUNNING_HEADER_FOOTER"
                if reason:
                    b["role"] = "artifact"
                    ast.page_artifacts.append(PageArtifact(pn, b["text"], reason, _round_bbox(b["bbox"])))

    # ----------------------------------------------------------- análise de página

    def _process_page(self, pdf, page, pn, blocks, info, rep, asset_cache, figure_xref_pages):
        H, W = info.height, info.width
        page_area = max(1.0, W * H)
        captions = self._find_captions(blocks)
        for b in blocks:
            b["caption"] = None
        for cap in captions:
            cap["block"]["caption"] = cap

        # --- imagens raster
        figures: List[Dict[str, Any]] = []
        try:
            infos = page.get_image_info(xrefs=True)
        except Exception:
            infos = []
        info.image_count = len(infos)
        rep.images_found += len(infos)
        info.image_coverage = round(min(1.0, sum(_bbox_area(im["bbox"]) for im in infos) / page_area), 3)
        for im in infos:
            bbox = [float(x) for x in im["bbox"]]
            if _bbox_area(bbox) <= 4:
                continue
            xref = int(im.get("xref") or 0)
            if xref:
                figure_xref_pages[xref].add(pn)
            deco, why = False, None
            if _bbox_area(bbox) / page_area < 0.012 or min(im.get("width", 0), im.get("height", 0)) < 48:
                deco, why = True, "imagem pequena (ícone/logótipo provável)"
            figures.append({
                "kind": "RASTER_IMAGE", "bbox": bbox, "xref": xref, "w": im.get("width"), "h": im.get("height"),
                "deco": deco, "why": why,
            })

        # --- gráficos vetoriais
        try:
            clusters = page.cluster_drawings()
        except Exception:
            clusters = []
        for r in clusters:
            bbox = [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if w < 60 or h < 40 or _bbox_area(bbox) / page_area < 0.02:
                continue
            if any(_overlap_frac(bbox, f["bbox"]) > 0.6 for f in figures if f["kind"] == "RASTER_IMAGE"):
                continue
            near_caption = any(
                c["kind"] == "figure" and _h_overlap(bbox, c["block"]["bbox"]) > 0.2
                and (-8 <= c["block"]["bbox"][1] - bbox[3] <= 60 or -8 <= bbox[1] - c["block"]["bbox"][3] <= 60)
                for c in captions
            )
            if near_caption:
                figures.append({"kind": "VECTOR_GRAPHIC", "bbox": bbox, "xref": 0, "w": None, "h": None, "deco": False, "why": None})

        # --- tabelas
        tables = self._find_tables(page, pn, blocks, captions, figures, rep)

        # --- consumo de blocos por tabelas / figuras
        for t in tables:
            if t["bbox"]:
                for b in blocks:
                    if b["role"] == "text" and _overlap_frac(b["bbox"], t["bbox"]) >= 0.6 and not b["caption"]:
                        b["role"] = "table_text"
        for f in figures:
            if f["deco"]:
                f["embedded"] = ""
                continue
            inside = [b for b in blocks if b["role"] == "text" and not b["caption"] and _overlap_frac(b["bbox"], f["bbox"]) >= 0.8]
            f["embedded"] = "\n".join(b["text"] for b in inside)
            for b in inside:
                b["role"] = "figure_text"

        # --- fórmulas (display)
        formulas: List[Dict[str, Any]] = []
        for b in blocks:
            if b["role"] == "text" and not b["caption"] and self._is_display_formula(b):
                m = re.search(r"\(\s*(\d+(?:\.\d+)?[a-z]?)\s*\)\s*$", b["text"])
                formulas.append({"block": b, "number": m.group(1) if m else None})
                b["role"] = "formula"

        remaining = [b for b in blocks if b["role"] in ("text", "formula")]
        ordered, ncols = _order_blocks(remaining)

        # --- associar legendas a tabelas/figuras
        for f in figures:
            f["caption_block"] = None if f["deco"] else self._nearest_caption(f["bbox"], captions, "figure", prefer="below")
        for t in tables:
            t["caption_block"] = t.get("caption_block") or (self._nearest_caption(t["bbox"], captions, "table", prefer="above") if t["bbox"] else None)
        used_caps = {id(f["caption_block"]["block"]) for f in figures if f.get("caption_block") and not f["deco"]}
        used_caps |= {id(t["caption_block"]["block"]) for t in tables if t.get("caption_block")}

        # legendas sem elemento visual/tabela detetado → entidade "CAPTION_ONLY"
        for c in captions:
            if id(c["block"]) in used_caps:
                continue
            if c["kind"] == "table":
                tables.append({"bbox": None, "rows": [], "method": "NONE", "caption_block": c, "status": "CAPTION_ONLY",
                               "limitations": ["legenda encontrada mas a estrutura da tabela não foi detetada"]})
            else:
                figures.append({"kind": "CAPTION_ONLY", "bbox": None, "xref": 0, "w": None, "h": None, "deco": False,
                                "why": None, "embedded": "", "caption_block": c})

        # --- guardar recursos (imagens extraídas / recortes)
        for f in figures:
            self._save_figure_asset(pdf, page, pn, f, asset_cache, rep)
        for fm in formulas:
            self._save_formula_crop(page, pn, fm)
            fm["block"]["asset_ref"], fm["block"]["asset_sha"] = fm["asset_ref"], fm["asset_sha"]

        # --- sequência final em ordem de leitura: elementos entram junto da sua legenda (ou do bloco mais próximo)
        def anchor_pos(bbox, cap_block=None, before=False) -> int:
            """Posição de inserção (0..len(ordered)): o elemento fica ANTES de ordered[pos]."""
            if cap_block is not None:
                for i, ob in enumerate(ordered):
                    if ob is cap_block:
                        return i if before else i + 1
            if not ordered:
                return 0
            cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
            best, best_d = 0, 1e18
            for i, ob in enumerate(ordered):
                bb = ob["bbox"]
                d = abs((bb[1] + bb[3]) / 2 - cy) + 0.2 * abs((bb[0] + bb[2]) / 2 - cx)
                if d < best_d:
                    best, best_d = i, d
            return best + (1 if ordered[best]["bbox"][1] <= bbox[1] else 0)

        inserts: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for f in figures:
            cap = f.get("caption_block")
            if f["bbox"] is None:
                pos = anchor_pos([0, 0, 1, 1], cap["block"], False) if cap else len(ordered)
            else:
                above = bool(cap) and f["bbox"][3] <= cap["block"]["bbox"][1] + 6
                pos = anchor_pos(f["bbox"], cap["block"] if cap else None, before=above)
            inserts[pos].append({"type": "figure", "page": pn, "data": f})
        for t in tables:
            cap = t.get("caption_block")
            if t["bbox"] is None:
                pos = anchor_pos([0, 0, 1, 1], cap["block"], False) if cap else len(ordered)
            else:
                below = bool(cap) and t["bbox"][1] >= cap["block"]["bbox"][3] - 6
                pos = anchor_pos(t["bbox"], cap["block"] if cap else None, before=not below)
            inserts[pos].append({"type": "table", "page": pn, "data": t})

        seq: List[Dict[str, Any]] = []
        for pos in range(len(ordered) + 1):
            seq.extend(inserts.get(pos, []))
            if pos < len(ordered):
                seq.append({"type": "block", "page": pn, "block": ordered[pos]})
        return seq, ncols

    # ---------------------------------------------------------------- legendas

    @staticmethod
    def _find_captions(blocks) -> List[Dict[str, Any]]:
        caps = []
        for b in blocks:
            if b["role"] != "text":
                continue
            text = b["text"]
            m = _CAPTION_SEP.match(text)
            is_cap = False
            if m:
                rest = (m.group("rest") or "").strip()
                is_cap = bool(rest) and not rest[0].islower() or (len(b["lines"]) <= 6 and b["lines"][0]["bold"])
            elif _CAPTION_BOLD_LABEL.match(text) and len(b["lines"]) <= 6 and b["lines"][0]["bold"] and len(text) < 600:
                m2 = _CAPTION_BOLD_LABEL.match(text)
                is_cap = True
                m = m2
            if not is_cap:
                continue
            label = (m.group("label") if "label" in (m.re.groupindex or {}) else m.group(0)).strip()
            kind = "table" if re.match(r"(?i)tab", label) else "figure"
            caps.append({"block": b, "kind": kind, "label": label, "text": text})
        return caps

    @staticmethod
    def _nearest_caption(bbox, captions, kind, prefer="below") -> Optional[Dict[str, Any]]:
        best, best_score = None, 1e18
        for c in captions:
            if c["kind"] != kind or c.get("claimed"):
                continue
            cb = c["block"]["bbox"]
            if _h_overlap(bbox, cb) < 0.25:
                continue
            below_gap = cb[1] - bbox[3]
            above_gap = bbox[1] - cb[3]
            if below_gap >= -10:
                gap, side = below_gap, "below"
            elif above_gap >= -10:
                gap, side = above_gap, "above"
            else:
                continue
            if gap > 120:
                continue
            score = gap + (0 if side == prefer else 25)
            if score < best_score:
                best, best_score = c, score
        if best is not None:
            best["claimed"] = True
        return best

    # ----------------------------------------------------------------- tabelas

    @staticmethod
    def _has_table_grid_drawings(page) -> bool:
        """Verifica rapidamente se a página tem traços ortogonais mínimos para tabelas com linhas."""
        try:
            drawings = page.get_cdrawings()
        except Exception:
            return True
        if not drawings:
            return False
        horiz = 0
        vert = 0
        for d in drawings:
            for item in d.get("items") or ():
                if not item:
                    continue
                kind = item[0]
                if kind in ("re", "qu"):
                    if kind == "re" and len(item) >= 2:
                        r = item[1]
                        if isinstance(r, (tuple, list)):
                            x0, y0, x1, y1 = float(r[0]), float(r[1]), float(r[2]), float(r[3])
                        else:
                            x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
                        w = abs(x1 - x0)
                        h = abs(y1 - y0)
                        if h <= 3.5 and w >= 8.0:
                            horiz += 1
                        elif w <= 3.5 and h >= 8.0:
                            vert += 1
                        else:
                            horiz += 2
                            vert += 2
                    else:
                        horiz += 2
                        vert += 2
                elif kind == "l" and len(item) >= 3:
                    p1, p2 = item[1], item[2]
                    x1, y1 = (float(p1[0]), float(p1[1])) if isinstance(p1, (tuple, list)) else (float(p1.x), float(p1.y))
                    x2, y2 = (float(p2[0]), float(p2[1])) if isinstance(p2, (tuple, list)) else (float(p2.x), float(p2.y))
                    dx = abs(x2 - x1)
                    dy = abs(y2 - y1)
                    if dy <= 2.5 and dx >= 8.0:
                        horiz += 1
                    elif dx <= 2.5 and dy >= 8.0:
                        vert += 1
                # Tabelas académicas (ex.: Elsevier/APA) podem usar apenas linhas horizontais (toprule/midrule/bottomrule)
                if horiz >= 2 or (horiz >= 1 and vert >= 1):
                    return True
        return False

    def _find_tables(self, page, pn, blocks, captions, figures, rep) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        table_caps = [c for c in captions if c["kind"] == "table"]
        candidates: List[Dict[str, Any]] = []
        if self._has_table_grid_drawings(page):
            try:
                for t in page.find_tables(strategy="lines").tables:
                    rows = _clean_rows(t.extract())
                    if self._table_acceptable(rows, [float(x) for x in t.bbox], table_caps, figures):
                        candidates.append({"bbox": [float(x) for x in t.bbox], "rows": rows, "method": "PYMUPDF_LINES"})
            except Exception:
                pass
        if not candidates and pdfplumber is not None and table_caps:
            try:
                with pdfplumber.open(page.parent.name) as _p:  # pragma: no cover - raramente usado
                    pass
            except Exception:
                pass

        claimed_bboxes = [c["bbox"] for c in candidates]
        for cap in table_caps:
            cb = cap["block"]["bbox"]
            if any(self._near(cb, bb) for bb in claimed_bboxes):
                continue
            tb = self._text_strategy_table(page, cb, blocks, captions)
            if tb:
                candidates.append(tb)
                claimed_bboxes.append(tb["bbox"])

        for c in candidates:
            rows, status, lim = self._grade_table(c["rows"], blocks, c["bbox"])
            c["rows"] = rows
            c["status"] = status
            c["limitations"] = lim
            result.append(c)
        return result

    @staticmethod
    def _near(cap_bbox, tbl_bbox) -> bool:
        return _h_overlap(cap_bbox, tbl_bbox) > 0.25 and (
            -10 <= tbl_bbox[1] - cap_bbox[3] <= 90 or -10 <= cap_bbox[1] - tbl_bbox[3] <= 90
        )

    def _table_acceptable(self, rows, bbox, table_caps, figures) -> bool:
        if len(rows) < 2 or not rows or len(rows[0]) < 2:
            return False
        cells = [c for r in rows for c in r]
        nonempty = sum(1 for c in cells if c.strip())
        if nonempty < 4 or nonempty / max(1, len(cells)) < 0.35:
            return False
        has_cap = any(self._near(c["block"]["bbox"], bbox) for c in table_caps)
        if not has_cap and nonempty / max(1, len(cells)) < 0.6:
            return False
        if not has_cap and any(_overlap_frac(bbox, f["bbox"]) > 0.5 for f in figures if f["bbox"]):
            return False
        return True

    def _text_strategy_table(self, page, cap_bbox, blocks, captions) -> Optional[Dict[str, Any]]:
        W, H = page.rect.width, page.rect.height
        x0 = min((b["bbox"][0] for b in blocks), default=0) - 2
        x1 = max((b["bbox"][2] for b in blocks), default=W) + 2
        # coluna da legenda (tabelas em duas colunas) ou largura total
        if (cap_bbox[2] - cap_bbox[0]) < 0.62 * (x1 - x0):
            mid = (x0 + x1) / 2
            x0, x1 = (x0, mid + 4) if cap_bbox[2] <= mid + 8 else (mid - 4, x1)
        regions = [pymupdf.Rect(x0, cap_bbox[3] + 1, x1, H * 0.94)]
        for clip in regions:
            try:
                tabs = page.find_tables(clip=clip, strategy="text", min_words_vertical=2, min_words_horizontal=1).tables
            except Exception:
                continue
            for t in tabs:
                rows = _clean_rows(t.extract())
                bbox = [float(v) for v in t.bbox]
                if bbox[1] - cap_bbox[3] > 40:
                    continue
                rows = _trim_prose_rows(rows)
                if len(rows) < 2 or len(rows[0]) < 2:
                    continue
                n_cols_used = max(sum(1 for c in r if c.strip()) for r in rows)
                if n_cols_used < 2:
                    continue
                # bbox efetiva = união das linhas mantidas
                kept_h = bbox[3] - bbox[1]
                if len(_clean_rows(t.extract())) != len(rows):
                    frac = len(rows) / max(1, len(_clean_rows(t.extract())))
                    bbox[3] = bbox[1] + kept_h * frac
                return {"bbox": bbox, "rows": rows, "method": "PYMUPDF_TEXT", "caption_block": None}
        return None

    @staticmethod
    def _grade_table(rows: List[List[str]], blocks, bbox) -> Tuple[List[List[str]], str, List[str]]:
        lim: List[str] = []
        if not rows:
            return rows, "CAPTION_ONLY", ["estrutura não detetada"]
        n_cols = max(len(r) for r in rows)
        rows = [r + [""] * (n_cols - len(r)) for r in rows]
        cells = [c for r in rows for c in r]
        empty_ratio = sum(1 for c in cells if not c.strip()) / max(1, len(cells))
        status = "RECONSTRUCTED"
        if empty_ratio > 0.5:
            status = "PARTIAL"
            lim.append(f"{round(empty_ratio * 100)}% das células vazias; possíveis células fundidas ou colunas mal separadas")
        if n_cols > 14:
            status = "PARTIAL"
            lim.append("número invulgar de colunas; estrutura pode estar fragmentada")
        if any(len(c) > 160 for c in cells):
            status = "PARTIAL"
            lim.append("células com texto longo; pode incluir texto corrido adjacente")
        if status == "PARTIAL":
            lim.append("estrutura não validada; usar apenas como informação bruta")
        return rows, status, lim

    # ---------------------------------------------------------------- figuras

    def _next_asset_seq(self, pn: int, prefix: str, glob_pattern: str) -> int:
        counters = getattr(self, "_page_asset_counters", None)
        if counters is None:
            counters = {}
            self._page_asset_counters = counters
        key = (str(self.assets_dir or ""), pn, prefix)
        cur = counters.get(key)
        if cur is None and self.assets_dir is not None:
            cur = len(list(self.assets_dir.glob(glob_pattern)))
        nxt = (cur or 0) + 1
        counters[key] = nxt
        return nxt

    def _save_figure_asset(self, pdf, page, pn, f: Dict[str, Any], cache: Dict[int, Tuple[str, str]], rep) -> None:
        f["asset_ref"], f["asset_sha"], f["asset_status"] = None, None, "NOT_FOUND"
        if f["kind"] == "CAPTION_ONLY":
            return
        if self.assets_dir is None:
            f["asset_status"] = "NOT_PERSISTED"
            return
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        pix = None
        try:
            if f["kind"] == "RASTER_IMAGE" and f["xref"]:
                if f["xref"] in cache:
                    f["asset_ref"], f["asset_sha"] = cache[f["xref"]]
                    f["asset_status"] = "EXTRACTED"
                    return
                pix = pymupdf.Pixmap(pdf, f["xref"])
                if pix.n - pix.alpha > 3:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                if pix.alpha:
                    pix = pymupdf.Pixmap(pix, 0)
                name = f"fig_p{pn:03d}_x{f['xref']}.png"
                path = self.assets_dir / name
                png_bytes = pix.tobytes("png")
                sha = hashlib.sha256(png_bytes).hexdigest()
                path.write_bytes(png_bytes)
                f["asset_ref"], f["asset_sha"], f["asset_status"] = f"assets/{name}", sha, "EXTRACTED"
                f["w"], f["h"] = pix.width, pix.height
                cache[f["xref"]] = (f["asset_ref"], sha)
                return
            # gráficos vetoriais / imagens inline: recorte renderizado da página
            clip = pymupdf.Rect(*f["bbox"])
            dpi = 150
            longest = max(clip.width, clip.height) / 72 * dpi
            if longest > 3200:
                dpi = int(dpi * 3200 / longest)
            pix = page.get_pixmap(clip=clip, dpi=max(dpi, 60))
            idx = self._next_asset_seq(pn, "fig_r", f"fig_p{pn:03d}_r*.png")
            name = f"fig_p{pn:03d}_r{idx}.png"
            path = self.assets_dir / name
            png_bytes = pix.tobytes("png")
            sha = hashlib.sha256(png_bytes).hexdigest()
            path.write_bytes(png_bytes)
            f["asset_ref"] = f"assets/{name}"
            f["asset_sha"] = sha
            f["asset_status"] = "RENDERED_FROM_PAGE"
            f["w"], f["h"] = pix.width, pix.height
        except Exception as e:
            f["asset_status"] = "EXTRACTION_FAILED"
            f["error"] = str(e)
            rep.warnings.append(f"Página {pn}: falha ao guardar imagem ({e})")
        finally:
            pix = None

    def _save_formula_crop(self, page, pn, fm: Dict[str, Any]) -> None:
        fm["asset_ref"], fm["asset_sha"] = None, None
        if self.assets_dir is None:
            return
        pix = None
        try:
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            b = fm["block"]["bbox"]
            clip = pymupdf.Rect(b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2)
            pix = page.get_pixmap(clip=clip, dpi=200)
            idx = self._next_asset_seq(pn, "eq", f"eq_p{pn:03d}_*.png")
            name = f"eq_p{pn:03d}_{idx}.png"
            path = self.assets_dir / name
            png_bytes = pix.tobytes("png")
            sha = hashlib.sha256(png_bytes).hexdigest()
            path.write_bytes(png_bytes)
            fm["asset_ref"] = f"assets/{name}"
            fm["asset_sha"] = sha
        except Exception:
            pass
        finally:
            pix = None

    # ---------------------------------------------------------------- fórmulas

    @staticmethod
    def _is_display_formula(b: Dict[str, Any]) -> bool:
        text = b["text"]
        if len(text) > 260 or len(text) < 3:
            return False
        score = 0
        if b["math_font_frac"] >= 0.3:
            score += 2
        if b["math_char_frac"] >= 0.12:
            score += 1
        has_eq_num = bool(re.search(r"\(\s*\d+(?:\.\d+)?[a-z]?\s*\)\s*$", text))
        if has_eq_num:
            score += 1
        if "=" in text or "<=" in text or ">=" in text:
            score += 1
            if has_eq_num:
                score += 1  # Equação numerada com igualdade é sinal quase definitivo
        if any(sym in text for sym in ("^", "_", "||", "\\sum", "\\int", "\\lambda", "\\theta", "sum_", "int_")):
            score += 1
        words = re.findall(r"[^\W\d_]{4,}", text)
        tokens = text.split()
        if tokens and len(words) / len(tokens) < 0.5:
            score += 1
        if re.search(r"[.!?]\s+[A-Z]", text) and len(words) >= 6:
            score -= 3  # prosa
        return score >= 3

    # -------------------------------------------------------------- estrutura

    def _build_structure(self, ast: AcademicDocumentAST, pdf, items: List[Dict[str, Any]], page_infos) -> None:
        text_blocks = [it["block"] for it in items if it["type"] == "block" and it["block"]["role"] in ("text",)]
        size_w: Counter = Counter()
        for b in text_blocks:
            if len(b["text"]) >= 40:
                size_w[b["size"]] += b["raw_chars"]
        if not size_w:
            for b in text_blocks:
                size_w[b["size"]] += b["raw_chars"]
        body_size = size_w.most_common(1)[0][0] if size_w else 10.0

        title_blocks = self._detect_title_blocks(items, body_size, pdf.metadata if hasattr(pdf, 'metadata') else None)
        title_ids = {id(b) for b in title_blocks}
        ast.metadata.title = _norm_ws(" ".join(b["text"] for b in title_blocks)) or None
        ast.metadata.title_source = "LAYOUT_TITLE_PAGE1" if title_blocks else None

        heading_sizes = sorted({
            b["size"] for b in text_blocks
            if id(b) not in title_ids and self._is_heading_candidate(b, body_size) and b["size"] >= body_size * 1.08
        }, reverse=True)

        sections: List[ASTSection] = []
        paragraphs: List[ASTParagraph] = []
        order = 0
        counters = {"sec": 0, "p": 0, "tbl": 0, "fig": 0, "eq": 0}
        stack: List[ASTSection] = []
        cur: Optional[ASTSection] = None
        last_para: Optional[ASTParagraph] = None
        ref_lines: List[Dict[str, Any]] = []
        ref_section: Optional[ASTSection] = None
        pending_caption_target: Dict[int, Tuple[str, Any]] = {}
        refs_out: List[ASTReference] = []

        def new_section(title: str, level: int, page: int, detection: str, bbox=None, kind=None, basis=None, number=None) -> ASTSection:
            nonlocal cur, last_para
            sid = f"sec_{counters['sec']}"
            counters["sec"] += 1
            k, kb = classify_section_title(title)
            if kind:
                k, kb = kind, basis or "SYNTHETIC"
            s = ASTSection(section_id=sid, title=title, level=level, kind=k, kind_basis=kb, number=number,
                           page_start=page, page_end=page, detection=detection, heading_bbox=bbox)
            while stack and stack[-1].level >= level:
                stack.pop()
            s.parent_id = stack[-1].section_id if stack else None
            stack.append(s)
            sections.append(s)
            cur = s
            last_para = None
            return s

        def ensure_section(page: int) -> ASTSection:
            if cur is None:
                return new_section("Início do documento", 1, page, "SYNTHETIC_PREAMBLE", kind="front_matter", basis="SYNTHETIC")
            return cur

        def add_para(text: str, page: int, block: Optional[Dict[str, Any]], ctype: str, method="PDF_TEXT_LAYER", merge=True) -> ASTParagraph:
            nonlocal order, last_para
            sec = ensure_section(page)
            text = text.strip()
            if (merge and last_para is not None and last_para.section_id == sec.section_id
                    and last_para.content_type == ctype and ctype in ("body", "ocr_body", "front_matter")
                    and _is_continuation(last_para.text, text)):
                joined, dh = _join_lines([last_para.text, text])
                last_para.text = joined
                last_para.page_end = max(last_para.page_end, page)
                if page != last_para.page_number:
                    last_para.extraction_status = "MERGED_ACROSS_PAGES"
                if block is not None:
                    last_para.bboxes.append({"page": page, "bbox": _round_bbox(block["bbox"])})
                if dh + (block["dehyph"] if block else 0):
                    last_para.normalizations["dehyphenated_line_breaks"] = last_para.normalizations.get("dehyphenated_line_breaks", 0) + dh + (block["dehyph"] if block else 0)
                last_para.sentence_spans = sentence_spans(last_para.text)
                last_para.content_sha1 = _sha1(last_para.text)
                sec.page_end = max(sec.page_end, page)
                return last_para
            counters["p"] += 1
            order += 1
            p = ASTParagraph(
                paragraph_id=f"p_{counters['p']}", section_id=sec.section_id, text=text, page_number=page, page_end=page,
                order=order, content_type=ctype, extraction_method=method,
                extraction_status="OCR_UNVERIFIED" if method == "OCR_WINDOWS" else "OK",
                bbox=_round_bbox(block["bbox"]) if block else None,
                bboxes=[{"page": page, "bbox": _round_bbox(block["bbox"])}] if block else [],
                font_size=block["size"] if block else None,
                contains_math=bool(block and (block["math_font_frac"] > 0.02 or block["math_char_frac"] > 0.02)),
                normalizations={"dehyphenated_line_breaks": block["dehyph"]} if block and block["dehyph"] else {},
                sentence_spans=sentence_spans(text), content_sha1=_sha1(text),
            )
            paragraphs.append(p)
            sec.element_refs.append({"type": "paragraph", "id": p.paragraph_id})
            sec.page_end = max(sec.page_end, page)
            last_para = p
            return p

        def flush_references():
            nonlocal ref_lines, ref_section
            if not ref_lines or ref_section is None:
                ref_lines = []
                return
            entries = _split_reference_entries(ref_lines)
            for ent in entries:
                raw, page = ent["text"], ent["page"]
                counters["p"] += 1
                nonlocal order
                order += 1
                p = ASTParagraph(
                    paragraph_id=f"p_{counters['p']}", section_id=ref_section.section_id, text=raw, page_number=page,
                    page_end=page, order=order, content_type="reference", bbox=_round_bbox(ent["bbox"]) if ent.get("bbox") else None,
                    bboxes=[{"page": page, "bbox": _round_bbox(ent["bbox"])}] if ent.get("bbox") else [],
                    sentence_spans=sentence_spans(raw), content_sha1=_sha1(raw),
                )
                paragraphs.append(p)
                ref_section.element_refs.append({"type": "paragraph", "id": p.paragraph_id})
                parsed = parse_reference(raw)
                ref = ASTReference(reference_id=f"ref_{len(refs_out) + 1}", raw=raw, section_id=ref_section.section_id,
                                   page_number=page, paragraph_id=p.paragraph_id, **parsed)
                refs_out.append(ref)
                ref_section.page_end = max(ref_section.page_end, page)
            ref_lines = []

        for it in items:
            typ = it["type"]
            page = it["page"]
            if typ == "ocr_block":
                add_para(it["text"], page, None, "ocr_body", method="OCR_WINDOWS")
                continue
            if typ == "block":
                b = it["block"]
                if id(b) in title_ids:
                    continue
                if b["role"] == "formula":
                    sec = ensure_section(page)
                    counters["eq"] += 1
                    order += 1
                    fm = next((x for x in it.get("formula_data", [])), None)
                    num = None
                    m = re.search(r"\(\s*(\d+(?:\.\d+)?[a-z]?)\s*\)\s*$", b["text"])
                    if m:
                        num = m.group(1)
                    ast.formulas.append(ASTFormula(
                        formula_id=f"eq_{counters['eq']}", page_number=page, section_id=sec.section_id, order=order,
                        raw_text=b["text"], equation_number=num, bbox=_round_bbox(b["bbox"]),
                        asset_ref=b.get("asset_ref"), asset_sha256=b.get("asset_sha"),
                        limitations=["texto extraído da camada PDF; a ordem dos símbolos pode estar incorreta; sem conversão para LaTeX"],
                    ))
                    sec.element_refs.append({"type": "formula", "id": f"eq_{counters['eq']}"})
                    sec.page_end = max(sec.page_end, page)
                    last_para = None
                    continue
                cap = b.get("caption")
                in_refs = cur is not None and cur.kind == "references"
                if cap is None and self._heading_decision(b, body_size, heading_sizes, page=page):
                    flush_references()
                    h_text = _normalize_heading_text(b["text"])
                    m = _HEADING_NUMBER.match(h_text)
                    number, clean_title, level = None, h_text, None
                    if m and (re.match(r"\d", m.group("num")) or len(m.group("num")) <= 3):
                        number = m.group("num")
                        clean_title = m.group("title").strip() if re.match(r"\d", m.group("num")) else h_text
                        if re.match(r"\d", m.group("num")):
                            level = number.count(".") + 1
                    if level is None:
                        level = (heading_sizes.index(b["size"]) + 1) if b["size"] in heading_sizes else 2
                    level = max(1, min(level, 6))
                    k_guess, _ = classify_section_title(clean_title)
                    if k_guess == "abstract":
                        clean_title = "Abstract" if "abstract" in clean_title.lower() else "Resumo"
                    sec = new_section(clean_title, level, page, "TYPOGRAPHY" if b["size"] >= body_size * 1.08 or b["bold"] else "PATTERN",
                                      _round_bbox(b["bbox"]), number=number)
                    if sec.kind == "references":
                        ref_section = sec
                    continue
                if in_refs and cap is None:
                    for ln in b["lines"]:
                        ref_lines.append({"text": ln["text"], "x0": ln["bbox"][0], "page": page, "bbox": ln["bbox"], "block_start": ln is b["lines"][0]})
                    continue
                if cap is not None:
                    p = add_para(b["text"], page, b, "caption", merge=False)
                    pending_caption_target[id(b)] = ("paragraph", p.paragraph_id)
                    continue
                ctype = "list_item" if re.match(r"^\s*(?:[•▪●◦\-–—*]|\(?[a-z0-9]{1,2}[.)])\s+\S", b["text"]) else "body"
                if cur is not None and cur.kind == "front_matter" or (cur is None and page == 1):
                    ctype = "front_matter" if _is_front_matter_metadata(b, ast) and ctype == "body" else ctype
                add_para(b["text"], page, b, ctype, merge=(ctype == "body"))
            elif typ == "table":
                t = it["data"]
                sec = ensure_section(page)
                counters["tbl"] += 1
                order += 1
                tid = f"tbl_{counters['tbl']}"
                cap_block = t.get("caption_block")
                cap_text = _clean_caption(cap_block["text"]) if cap_block else None
                rows = t.get("rows") or []
                n_cols = max((len(r) for r in rows), default=0)
                hdr_idx, hdr_status = (None, "NONE")
                if rows and t.get("status") != "CAPTION_ONLY":
                    hdr_idx, hdr_status = 0, "ASSUMED_FIRST_ROW"
                ast.tables.append(ASTTable(
                    table_id=tid, page_number=page, section_id=sec.section_id, order=order, caption=cap_text,
                    bbox=_round_bbox(t["bbox"]) if t.get("bbox") else None, rows=rows, n_rows=len(rows), n_cols=n_cols,
                    header_row_index=hdr_idx, header_status=hdr_status, structure_status=t.get("status", "CAPTION_ONLY"),
                    extraction_method=t.get("method", "NONE"), limitations=t.get("limitations", []),
                ))
                sec.element_refs.append({"type": "table", "id": tid})
                sec.page_end = max(sec.page_end, page)
                if cap_block:
                    t["_id"] = tid
                    pending_caption_target[id(cap_block["block"])] = ("table", tid)
                last_para = None
            elif typ == "figure":
                f = it["data"]
                sec = ensure_section(page)
                counters["fig"] += 1
                order += 1
                fid = f"fig_{counters['fig']}"
                cap_block = f.get("caption_block")
                cap_text = _clean_caption(cap_block["text"]) if cap_block else None
                lim: List[str] = []
                if f["kind"] == "CAPTION_ONLY":
                    lim.append("legenda encontrada mas nenhum elemento visual correspondente foi detetado nesta página")
                if f["kind"] == "VECTOR_GRAPHIC":
                    lim.append("gráfico vetorial renderizado como imagem; dados subjacentes não recuperados")
                if f["kind"] == "RASTER_IMAGE":
                    lim.append("imagem extraída sem interpretação; conteúdo/dados do gráfico não recuperados")
                w, h = f.get("w"), f.get("h")
                dpi = None
                if w and f.get("bbox") and f["kind"] == "RASTER_IMAGE":
                    bw = max(1.0, f["bbox"][2] - f["bbox"][0])
                    dpi = round(w / (bw / 72.0), 1)
                ast.figures.append(ASTFigure(
                    figure_id=fid, page_number=page, section_id=sec.section_id, order=order, element_kind=f["kind"],
                    caption=cap_text, bbox=_round_bbox(f["bbox"]) if f.get("bbox") else None,
                    asset_ref=f.get("asset_ref"), asset_sha256=f.get("asset_sha"), asset_status=f.get("asset_status", "NOT_FOUND"),
                    width_px=int(w) if w else None, height_px=int(h) if h else None, effective_dpi=dpi,
                    is_decorative_candidate=bool(f.get("deco")), decorative_reason=f.get("why"),
                    embedded_text=f.get("embedded", ""), limitations=lim,
                ))
                sec.element_refs.append({"type": "figure", "id": fid})
                sec.page_end = max(sec.page_end, page)
                if cap_block:
                    pending_caption_target[id(cap_block["block"])] = ("figure", fid)
                last_para = None

        flush_references()

        # ligar legendas (parágrafos) às suas tabelas/figuras
        para_by_id = {p.paragraph_id: p for p in paragraphs}
        tbl_by_id = {t.table_id: t for t in ast.tables}
        fig_by_id = {f.figure_id: f for f in ast.figures}
        cap_para_of_block: Dict[int, str] = {k: v[1] for k, v in pending_caption_target.items() if v[0] == "paragraph"}
        for key, (kind, ref_id) in pending_caption_target.items():
            if kind == "paragraph":
                continue
            pid = cap_para_of_block.get(key)
            if not pid:
                continue
            para_by_id[pid].linked_element_id = ref_id
            if kind == "table":
                tbl_by_id[ref_id].caption_paragraph_id = pid
            else:
                fig_by_id[ref_id].caption_paragraph_id = pid

        # secções sem conteúdo (apenas título) mantêm-se, pois podem ter filhos
        ast.sections = sections
        ast.paragraphs = paragraphs
        ast.references = refs_out
        if not sections:
            ast.sections = [ASTSection(section_id="sec_0", title="Documento completo", level=1, kind="other",
                                       kind_basis="SYNTHETIC", detection="SYNTHETIC_DOCUMENT", page_start=1, page_end=len(page_infos))]

    @staticmethod
    def _is_heading_candidate(b: Dict[str, Any], body_size: float) -> bool:
        text = b["text"]
        if b.get("caption") or len(b["lines"]) > 3 or len(text) > 170 or len(text) < 2:
            return False
        if _PAGE_NUMBER.match(text):
            return False
        if text.rstrip().endswith((",", ";")):
            return False
        alpha = sum(1 for c in text if c.isalpha())
        return alpha / max(1, len(text)) >= 0.45

    def _heading_decision(self, b: Dict[str, Any], body_size: float, heading_sizes: List[float], page: int = 1) -> bool:
        if not self._is_heading_candidate(b, body_size):
            return False
        text = _normalize_heading_text(b["text"])
        
        # Na página 1 antes das secções principais, linhas de autores ou afiliações não são títulos de secções
        if page == 1 and b["bbox"][1] < 380:
            if _parse_author_line(b["text"]) or _is_front_matter_metadata(b, None):
                return False

        larger = b["size"] >= body_size * 1.12
        numbered = bool(re.match(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[^\W\d_]", text))
        kind, basis = classify_section_title(text)
        canonical = basis == "TITLE_MATCH" and len(text) <= 60
        single_line = len(b["lines"]) == 1
        ends_period = text.rstrip().endswith(".") and not numbered
        if larger and not ends_period:
            return True
        if b["bold"] and (numbered or canonical) and not ends_period:
            return True
        if b["bold"] and single_line and len(text) <= 80 and not ends_period and b["size"] >= body_size * 0.95 and b.get("lead_in") is None:
            # título em negrito isolado numa linha (sem pontuação final)
            words = text.split()
            return 1 <= len(words) <= 12 and not text.endswith(":") or canonical
        # sem pistas tipográficas: só padrões fortes
        if single_line and canonical and (text.isupper() or numbered):
            return True
        if single_line and numbered and len(text) <= 70 and not ends_period and text[0].isdigit() is True and text.split(" ", 1)[1][:1].isupper() and len(text.split()) <= 9:
            return b["bold"] or larger
        if single_line and text.isupper() and 3 <= len(text) <= 60 and sum(c.isalpha() for c in text) >= 4:
            return True
        return False

    @staticmethod
    def _detect_title_blocks(items, body_size, pdf_metadata=None) -> List[Dict[str, Any]]:
        first_page = [it["block"] for it in items if it["type"] == "block" and it["page"] == 1 and it["block"]["role"] == "text"]
        if not first_page:
            return []
        
        # 1. Se os metadados do PDF tiverem título substantivo, procurar bloco correspondente
        if pdf_metadata and pdf_metadata.get("title"):
            m_title = _norm_ws(pdf_metadata["title"]).lower()
            if len(m_title) >= 10 and not re.match(r"(?i)^(microsoft word|untitled|document\d*|.*\.(docx?|pdf|tex|indd)$)", m_title):
                for b in first_page:
                    b_norm = _norm_ws(b["text"]).lower()
                    if (b_norm in m_title or m_title in b_norm) and len(b_norm) >= 15:
                        return [b]

        # 2. Filtrar banners de publicadores e jornais
        journal_banner = re.compile(
            r"(?i)\b(journal homepage|contents lists available|sciencedirect|elsevier|springer|ieee|acm|wiley|proceedings of|published by|vol(?:ume)?\.?\s*\d+|issn)\b"
        )
        H_guess = max(b["bbox"][3] for b in first_page) or 1.0
        cands = [
            b for b in first_page
            if b["bbox"][1] <= 0.55 * H_guess + 80
            and len(b["text"]) >= 6
            and not b.get("caption")
            and not journal_banner.search(b["text"])
        ]
        if not cands:
            return []
        max_size = max(b["size"] for b in cands)
        if max_size < body_size * 1.2:
            return []
        group: List[Dict[str, Any]] = []
        for b in cands:
            if abs(b["size"] - max_size) <= 0.6 and len(b["lines"]) <= 4:
                if group and b["bbox"][1] - group[-1]["bbox"][3] > max_size * 2.2:
                    break
                group.append(b)
            elif group:
                break
        return group

    # -------------------------------------------------------------- metadados

    def _build_metadata(self, ast: AcademicDocumentAST, pdf, items, size: int) -> None:
        md = ast.metadata
        md.page_count = pdf.page_count
        md.filename = ast.filename
        md.source_sha256 = ast.source_sha256
        md.size_bytes = size
        raw_meta = {k: v for k, v in (pdf.metadata or {}).items() if v}
        md.pdf_metadata = {k: raw_meta[k] for k in ("title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate", "format") if k in raw_meta}

        pdf_title = (raw_meta.get("title") or "").strip()
        if not md.title and pdf_title and len(pdf_title) >= 6 and not re.match(r"(?i)^(microsoft word|untitled|document\d*|.*\.(docx?|pdf|tex|indd)$)", pdf_title):
            md.title, md.title_source = pdf_title, "PDF_METADATA"

        page1 = [it["block"] for it in items if it["type"] == "block" and it["page"] == 1 and it["block"]["role"] in ("text",)]
        page12_text = "\n".join(
            it["block"]["text"] for it in items if it["type"] == "block" and it["page"] <= 2 and it["block"]["role"] in ("text",)
        )
        # Subtítulo: bloco imediatamente a seguir ao título, claramente maior que o corpo mas menor que o título
        if md.title and md.title_source == "LAYOUT_LARGEST_TEXT_PAGE1":
            tsizes = [b["size"] for b in page1 if _norm_ws(b["text"]) and b["text"] in md.title]
            tsize = max(tsizes) if tsizes else None
            if tsize:
                seen_title = False
                for b in page1:
                    if b["text"] in md.title:
                        seen_title = True
                        continue
                    if seen_title:
                        if 0.78 * tsize >= b["size"] >= 1.15 * min(x["size"] for x in page1) and len(b["text"]) <= 200 \
                                and not re.search(r"@|university|universidade|department", b["text"], re.I) and len(b["text"].split()) >= 3 \
                                and b["size"] >= tsize * 0.6:
                            md.subtitle, md.subtitle_source = _norm_ws(b["text"]), "LAYOUT_BLOCK_AFTER_TITLE"
                        break

        # DOI
        for src_name, hay in (("PDF_METADATA", " ".join(str(v) for v in raw_meta.values())), ("LAYOUT_PAGES_1_2", page12_text)):
            m = _DOI.search(hay)
            if m:
                md.doi = m.group(0).rstrip(".,;:)]}")
                md.doi_source = src_name
                break

        # E-mails
        md.emails = sorted(set(re.findall(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", page12_text)))

        # Afiliações e autores (heurístico, página 1, antes da primeira secção)
        fm_blocks = []
        for b in page1:
            if re.match(r"(?i)^\s*(a\s?b\s?s\s?t\s?r\s?a\s?c\s?t|abstract|resumo|1\.?\s+introduction|introduction)\b", b["text"]):
                break
            if md.title and b["text"] in md.title:
                fm_blocks = []
                continue
            fm_blocks.append(b)
        aff_kw = re.compile(r"(?i)\b(universit|institut|department|dept\.|school of|college|laborator|faculty|faculdade|universidade|centre|center|hospital|company|inc\.|ltd|gmbh|corp)")
        for b in fm_blocks:
            for ln in b["lines"]:
                t = _norm_ws(ln["text"])
                if aff_kw.search(t) or "@" in t:
                    m = re.match(r"^([a-z0-9⁎*†‡])\s+(?=[A-Z])", t)
                    md.affiliations.append({"marker": m.group(1) if m else None, "text": t[m.end():] if m else t})
        authors: List[Dict[str, Any]] = []
        for b in fm_blocks:
            if len(b["lines"]) > 3 or aff_kw.search(b["text"]) or "@" in b["text"] or b["size"] < 6.0:
                continue
            if re.search(r"\d{4}|\bdoi\b|http|www\.", b["text"], re.I):
                continue
            names = _parse_author_line(b["text"])
            if names:
                authors.extend(names)
            if authors:
                break
        if authors:
            md.authors, md.authors_source = authors, "LAYOUT_HEURISTIC"
        elif raw_meta.get("author"):
            md.authors = [{"name": n.strip(), "raw": n.strip(), "markers": []} for n in re.split(r";|\band\b|&", raw_meta["author"]) if n.strip()]
            md.authors_source = "PDF_METADATA"

        # Data de publicação (apenas padrões explícitos; nunca a data de criação do PDF)
        pd = None
        for kind, pat in (
            ("published", r"(?i)\b(?:published(?:\s+online)?|publicado)\s*[:\-]?\s*([^\n]{0,40}?((?:19|20)\d{2}))"),
            ("available_online", r"(?i)\bavailable online\s*[:\-]?\s*([^\n]{0,40}?((?:19|20)\d{2}))"),
            ("accepted", r"(?i)\baccepted\s*[:\-]?\s*([^\n]{0,40}?((?:19|20)\d{2}))"),
            ("received", r"(?i)\breceived\s*[:\-]?\s*([^\n]{0,40}?((?:19|20)\d{2}))"),
            ("copyright_year", r"(?:©|\(c\)|copyright)\s*((?:19|20)\d{2})"),
        ):
            m = re.search(pat, page12_text)
            if m:
                year = m.group(m.lastindex)
                pd = {"kind": kind, "year": year, "text": _norm_ws(m.group(0)), "source": "LAYOUT_PATTERN"}
                break
        md.publication_date = pd

        # Abstract
        abs_sec = next((s for s in ast.sections if s.kind == "abstract"), None)
        paras_by_sec = defaultdict(list)
        for p in ast.paragraphs:
            paras_by_sec[p.section_id].append(p)
        if abs_sec:
            cand = [p for p in paras_by_sec[abs_sec.section_id] if p.content_type == "body" and len(p.text.split()) >= 25]
            if cand:
                md.abstract = "\n\n".join(p.text for p in cand)
                md.abstract_source = "SECTION_ABSTRACT"
                md.abstract_paragraph_ids = [p.paragraph_id for p in cand]
        if not md.abstract:
            for p in ast.paragraphs:
                if p.page_number > 2:
                    break
                m = re.match(r"(?is)^\s*(?:abstract|resumo|summary)\s*[:.\-–—]\s*(.{80,})$", p.text)
                if m:
                    md.abstract, md.abstract_source, md.abstract_paragraph_ids = m.group(1).strip(), "LEAD_IN_PARAGRAPH", [p.paragraph_id]
                    break

        # Palavras-chave
        for p in ast.paragraphs:
            if p.page_number > 2:
                break
            m = re.match(r"(?is)^\s*(?:key\s?words?|index terms|palavras[\s\-]chave)\s*[:\-–—]\s*(.+)$", p.text)
            if m:
                kws = [k.strip(" .") for k in re.split(r"[;,·•|]", m.group(1)) if k.strip(" .")]
                if kws:
                    md.keywords, md.keywords_source = kws, "LAYOUT_PARAGRAPH"
                    break
        if not md.keywords and raw_meta.get("keywords"):
            kws = [k.strip(" .") for k in re.split(r"[;,]", raw_meta["keywords"]) if k.strip(" .")]
            if kws:
                md.keywords, md.keywords_source = kws, "PDF_METADATA"

    # -------------------------------------------------------------- relatório

    def _finalize_report(self, ast: AcademicDocumentAST, page_blocks, t0: float) -> None:
        rep = ast.report
        infos = ast.pages
        rep.pages_with_text_layer = sum(1 for p in infos if p.text_source == "TEXT_LAYER" and p.char_count > 0)
        rep.pages_ocr = sum(1 for p in infos if p.text_source == "OCR_WINDOWS")
        rep.sections_identified = len([s for s in ast.sections if s.detection in ("TYPOGRAPHY", "PATTERN")])
        rep.paragraphs = len(ast.paragraphs)
        rep.tables_identified = len(ast.tables)
        rep.tables_structure_reconstructed = sum(1 for t in ast.tables if t.structure_status == "RECONSTRUCTED")
        rep.tables_partial = sum(1 for t in ast.tables if t.structure_status == "PARTIAL")
        rep.tables_caption_only = sum(1 for t in ast.tables if t.structure_status == "CAPTION_ONLY")
        rep.figures_identified = len([f for f in ast.figures if not f.is_decorative_candidate])
        rep.figures_decorative_candidates = len([f for f in ast.figures if f.is_decorative_candidate])
        rep.formulas_identified = len(ast.formulas)
        rep.references_identified = len(ast.references)
        rep.references_parsed_partial = sum(1 for r in ast.references if r.parse_status == "PARSED_PARTIAL")
        rep.page_artifacts_separated = len(ast.page_artifacts)

        for t in ast.tables:
            if t.structure_status != "RECONSTRUCTED":
                rep.not_interpreted.append({"kind": "TABLE", "id": t.table_id, "page": t.page_number, "reason": t.structure_status, "detail": t.limitations})
        for f in ast.figures:
            if not f.is_decorative_candidate:
                rep.not_interpreted.append({"kind": "FIGURE", "id": f.figure_id, "page": f.page_number, "reason": f.interpretation_status})
        for fm in ast.formulas:
            rep.not_interpreted.append({"kind": "FORMULA", "id": fm.formula_id, "page": fm.page_number, "reason": "RAW_TEXT_ONLY_NO_LATEX"})

        # contabilização de texto da camada PDF: tudo o que foi lido tem de estar algures
        captured = sum(sum(1 for c in p.text if not c.isspace()) for p in ast.paragraphs if p.extraction_method == "PDF_TEXT_LAYER")
        captured += sum(sum(1 for c in s.title if not c.isspace()) for s in ast.sections if s.detection in ("TYPOGRAPHY", "PATTERN"))
        captured += sum(sum(1 for c in (ast.metadata.title or "") if not c.isspace()) for _ in [0]) if ast.metadata.title_source == "LAYOUT_LARGEST_TEXT_PAGE1" else 0
        captured += sum(sum(1 for r in t.rows for c in "".join(r) if not c.isspace()) for t in ast.tables)
        captured += sum(sum(1 for c in f.embedded_text if not c.isspace()) for f in ast.figures)
        captured += sum(sum(1 for c in fm.raw_text if not c.isspace()) for fm in ast.formulas)
        artifacts = sum(sum(1 for c in a.text if not c.isspace()) for a in ast.page_artifacts)
        raw_total = sum(p.char_count for p in infos if p.text_source == "TEXT_LAYER")
        accounted = captured + artifacts
        rep.text_accounting = {
            "text_layer_chars_read": raw_total,
            "captured_in_ast": captured,
            "separated_header_footer_chars": artifacts,
            "difference": raw_total - accounted,
            "difference_ratio": round((raw_total - accounted) / raw_total, 4) if raw_total else 0.0,
            "meaning": "Medida de captura de caracteres da camada de texto PDF (não é cobertura semântica nem prova de compreensão).",
        }
        if infos and all(p.status in ("UNRECOVERED", "EMPTY") for p in infos):
            rep.status = "FAILED"
            rep.errors.append("Nenhuma página com conteúdo recuperável.")
        elif rep.pages_unrecovered or rep.errors:
            rep.status = "PARTIAL"
            if rep.pages_unrecovered:
                rep.warnings.append(f"Páginas sem conteúdo recuperável: {rep.pages_unrecovered}")
        rep.duration_ms = round((time.perf_counter() - t0) * 1000, 1)


# ---------------------------------------------------------------------------
# Funções auxiliares da estrutura
# ---------------------------------------------------------------------------

def _clean_rows(rows) -> List[List[str]]:
    out: List[List[str]] = []
    for r in rows or []:
        cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in r]
        if any(cells):
            out.append(cells)
    return out


def _trim_prose_rows(rows: List[List[str]]) -> List[List[str]]:
    kept: List[List[str]] = []
    for r in rows:
        filled = [c for c in r if c]
        if len(filled) == 1 and len(filled[0]) > 90 and kept:
            break  # linha de texto corrido: fim da tabela
        if filled and max(len(c) for c in filled) > 200 and kept:
            break
        kept.append(r)
    return kept


def _normalize_heading_text(text: str) -> str:
    lines = (text or "").splitlines() or [text or ""]
    despaced_lines = []
    for l in lines:
        dl = re.sub(r"(?<=\b[A-Za-z])\s+(?=[A-Za-z]\b)", "", l)
        despaced_lines.append(dl)
    t = _norm_ws(" ".join(despaced_lines))
    return t


def _is_continuation(prev: str, nxt: str) -> bool:
    prev, nxt = prev.rstrip(), nxt.lstrip()
    if not prev or not nxt:
        return False
    if re.search(r"[.!?:][\"”’')\]]*$", prev):
        return False
    return bool(re.match(r"[a-zà-ÿ,;)\]]", nxt)) or prev.endswith("-")


def _is_front_matter_metadata(b: Dict[str, Any], ast: AcademicDocumentAST) -> bool:
    t = _norm_ws(b["text"])
    # Títulos e secções canónicas nunca são metadados de front matter
    k_guess, basis = classify_section_title(t)
    if basis == "TITLE_MATCH" or re.match(r"^\d+(?:\.\d+)*\.?\s+[A-Z]", t):
        return False
    words = len(t.split())
    if re.search(r"@|\buniversit|\binstitut|\bdepartment\b|\bcollege\b|\blaborator|\bfaculty\b|\bdoi\b|https?://|©|all rights reserved|contents lists available|journal homepage|article history|received|accepted|available online", t, re.I):
        return True
    return len(b["lines"]) <= 3 and words < 14 and b["bbox"][1] < 330 and not t.lower().startswith(("abstract", "resumo", "introduction", "introdução"))


def _clean_caption(text: str) -> str:
    return _norm_ws(text)


def _parse_author_line(text: str) -> List[Dict[str, Any]]:
    t = _norm_ws(text)
    parts = re.split(r",\s*(?:and\s+)?|\s+and\s+|\s*&\s*|;|·|•", t)
    names: List[Dict[str, Any]] = []
    particles = {"de", "da", "do", "dos", "das", "van", "von", "der", "den", "del", "di", "la", "le", "bin", "al"}
    for raw in parts:
        raw = raw.strip()
        if not raw:
            continue
        markers = re.findall(r"[⁎*†‡§¶]|(?<=\s)[a-z0-9](?=\s*$)|[⁰¹²³⁴⁵⁶⁷⁸⁹]", raw)
        name = re.sub(r"[⁎*†‡§¶⁰¹²³⁴⁵⁶⁷⁸⁹]+", "", raw)
        name = re.sub(r"\s+[a-z0-9]$", "", name).strip(" ,")
        name = re.sub(r"\d+$", "", name).strip()
        toks = name.split()
        if not (2 <= len(toks) <= 5):
            return [] if not names else names
        ok = all(
            (tk[0].isupper() and re.fullmatch(r"[^\W\d_][\w.'’\-]*", tk, re.UNICODE)) or tk.lower() in particles
            for tk in toks
        )
        if not ok:
            return [] if not names else names
        names.append({"name": name, "raw": raw, "markers": markers})
    return names


_REF_MARKER = re.compile(r"^\s*(\[\d+\]|\(\d+\)|\d{1,3}[.)])\s+")
_REF_AUTHOR_START = re.compile(r"^[A-ZÀ-Ý][\w'’\-]+(?:\s[\w'’\-]+)?,\s+(?:[A-Z]\.|[A-Z][a-z]+)")


def _split_reference_entries(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    x0s = sorted({round(l["x0"]) for l in lines})
    min_x0 = min(l["x0"] for l in lines)
    hanging = len([l for l in lines if l["x0"] - min_x0 >= 6]) >= max(2, len(lines) // 4)
    entries: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for ln in lines:
        t = _norm_ws(ln["text"])
        if not t:
            continue
        starts = False
        if cur is None:
            starts = True
        elif _REF_MARKER.match(t):
            starts = True
        elif hanging and ln["x0"] - min_x0 <= 2.5 and ln["block_start"] is not None:
            starts = ln["x0"] - min_x0 <= 2.5 and (cur["last_x0"] - min_x0 >= 4 or re.search(r"[.)\]]$|\d$", cur["text"]) is not None) and bool(_REF_AUTHOR_START.match(t) or True)
        elif ln.get("block_start") and re.search(r"[.)\]]\s*$|\bdoi\b.*\S$|https?://\S+$", cur["text"], re.I):
            starts = True
        elif _REF_AUTHOR_START.match(t) and re.search(r"[.]\s*$|\d\s*$", cur["text"]):
            starts = True
        if starts:
            if cur:
                entries.append(cur)
            cur = {"text": t, "page": ln["page"], "bbox": list(ln["bbox"]), "last_x0": ln["x0"]}
        else:
            joined, _ = _join_lines([cur["text"], t])
            cur["text"] = joined
            cur["last_x0"] = ln["x0"]
            bb = cur["bbox"]
            cur["bbox"] = [min(bb[0], ln["bbox"][0]), min(bb[1], ln["bbox"][1]), max(bb[2], ln["bbox"][2]), max(bb[3], ln["bbox"][3])] if ln["page"] == cur["page"] else bb
    if cur:
        entries.append(cur)
    return entries


def parse_reference(raw: str) -> Dict[str, Any]:
    """Separa campos de uma referência só quando o padrão é inequívoco; nunca inventa dados."""
    text = raw
    marker = None
    m = _REF_MARKER.match(text)
    if m:
        marker = m.group(1)
        text = text[m.end():]
    doi_m = _DOI.search(text)
    doi = doi_m.group(0).rstrip(".,;:)]}") if doi_m else None
    result: Dict[str, Any] = {"marker": marker, "doi": doi, "authors_raw": None, "year": None, "title": None, "venue": None, "parse_status": "RAW_ONLY"}
    apa = re.match(r"^(?P<authors>.+?)\s*\((?P<year>(?:19|20)\d{2}[a-z]?)\)\s*[.,]?\s*(?P<title>[^.?!]+[.?!]?)\s*(?P<venue>.*)$", text)
    if apa and len(apa.group("authors")) < 300:
        result.update({
            "authors_raw": apa.group("authors").strip(" ."),
            "year": apa.group("year"),
            "title": apa.group("title").strip().rstrip("."),
            "venue": (apa.group("venue") or "").strip() or None,
            "parse_status": "PARSED_PARTIAL",
        })
        return result
    ym = re.search(r"\b((?:19|20)\d{2}[a-z]?)\b", text)
    if ym:
        result["year"] = ym.group(1)
        result["parse_status"] = "PARSED_PARTIAL" if doi or ym else "RAW_ONLY"
    return result


def _segment_ocr_text(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    lens = sorted(len(l) for l in lines)
    median = lens[len(lens) // 2]
    paras: List[List[str]] = [[]]
    for l in lines:
        if paras[-1]:
            prev = paras[-1][-1]
            if re.search(r"[.!?:][\"”’')\]]*$", prev) and len(prev) < 0.72 * max(median, 1) and l[:1].isupper():
                paras.append([])
        paras[-1].append(l)
    return [_join_lines(p)[0] for p in paras if p]
