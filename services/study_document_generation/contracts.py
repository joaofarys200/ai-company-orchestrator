"""
JARVIS OS — Study Engine Phase 5: Document Generation Engine & Academic Document Composition
Contratos de Dados, Representação Intermédia Semântica (IR), Elementos Visuais e Relatórios de QA.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Dict, List, Optional

from services.editorial_intelligence_engine import EditorialEvidenceRef, EditorialStudyPlan

if not hasattr(EditorialEvidenceRef, "from_dict"):
    @classmethod
    def _ev_from_dict(cls, d: Dict[str, Any]):
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in known})
    setattr(EditorialEvidenceRef, "from_dict", _ev_from_dict)


class DocumentGenerationState(str, Enum):
    """Estados canónicos da geração documental (Fase 5)."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ContentBlockType(str, Enum):
    """Tipos de blocos de enriquecimento e explicação académica (Componentes 5.1 e 5.2)."""
    EXPLANATORY_PARAGRAPH = "EXPLANATORY_PARAGRAPH"
    DEVELOPED_DEFINITION = "DEVELOPED_DEFINITION"
    STEP_BY_STEP_MECHANISM = "STEP_BY_STEP_MECHANISM"
    THEORETICAL_CONTEXT = "THEORETICAL_CONTEXT"
    CONCEPT_COMPARISON = "CONCEPT_COMPARISON"
    CAUSE_EFFECT_ANALYSIS = "CAUSE_EFFECT_ANALYSIS"
    RESULTS_INTERPRETATION = "RESULTS_INTERPRETATION"
    METHODOLOGY_EXPLANATION = "METHODOLOGY_EXPLANATION"
    LIMITATIONS_DISCUSSION = "LIMITATIONS_DISCUSSION"
    HYPOTHETICAL_EXAMPLE = "HYPOTHETICAL_EXAMPLE"
    CALLOUT_BOX = "CALLOUT_BOX"
    SECTION_SYNTHESIS = "SECTION_SYNTHESIS"
    CHAPTER_SYNTHESIS = "CHAPTER_SYNTHESIS"


class IRBlockKind(str, Enum):
    """Tipos de blocos semânticos na Representação Intermédia (Componente 5.3)."""
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    BULLET_LIST = "BULLET_LIST"
    NUMBERED_LIST = "NUMBERED_LIST"
    CALLOUT_BOX = "CALLOUT_BOX"
    TABLE = "TABLE"
    EQUATION = "EQUATION"
    VISUAL_ELEMENT = "VISUAL_ELEMENT"
    PROVENANCE_NOTE = "PROVENANCE_NOTE"
    DIVIDER = "DIVIDER"


class CalloutBoxKind(str, Enum):
    """Tipos de caixas pedagógicas do Sistema de Design Documental (Componente 5.6)."""
    CONCEPT_BOX = "CONCEPT_BOX"
    MECHANISM_BOX = "MECHANISM_BOX"
    ATTENTION_BOX = "ATTENTION_BOX"
    HYPOTHETICAL_EXAMPLE_BOX = "HYPOTHETICAL_EXAMPLE_BOX"
    LIMITATION_BOX = "LIMITATION_BOX"
    SYNTHESIS_BOX = "SYNTHESIS_BOX"


class VisualRenderStatus(str, Enum):
    """Estado de produção efetiva de cada elemento visual planeado (Componente 5.4)."""
    RENDERED = "RENDERED"
    RENDERED_AS_TABLE = "RENDERED_AS_TABLE"
    OMITTED_INSUFFICIENT_DATA = "OMITTED_INSUFFICIENT_DATA"
    OMITTED_REDUNDANT = "OMITTED_REDUNDANT"
    FAILED = "FAILED"


class QAAxis(str, Enum):
    """Quatro eixos obrigatórios de auditoria do documento final (Componente 5.8)."""
    CONTENT_INTEGRITY = "CONTENT_INTEGRITY"
    VISUAL_INTEGRITY = "VISUAL_INTEGRITY"
    DOCUMENT_INTEGRITY = "DOCUMENT_INTEGRITY"
    PEDAGOGICAL_QUALITY = "PEDAGOGICAL_QUALITY"


class QASeverity(str, Enum):
    """Níveis de severidade da validação documental (Componente 5.8)."""
    BLOCKING_ERROR = "BLOCKING_ERROR"
    WARNING = "WARNING"
    RECOMMENDATION = "RECOMMENDATION"


def compute_plan_fingerprint(plan: EditorialStudyPlan) -> str:
    """Calcula impressão digital determinística do EditorialStudyPlan para controlo de sincronização."""
    payload = {
        "document_id": plan.metadata.document_id,
        "plan_id": plan.metadata.plan_id,
        "plan_version": plan.metadata.plan_version,
        "dossier_fingerprint": plan.metadata.dossier_fingerprint,
        "status": plan.metadata.status,
        "chapters": [
            {
                "chapter_id": c.chapter_id,
                "title": c.title,
                "order": c.order,
                "sections": [s.section_id for s in c.sections],
            }
            for c in plan.chapters
        ],
        "visuals": [v.visual_id for v in plan.visual_plans],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# 1. Modelos de Conteúdo Académico Desenvolvido (Componentes 5.1 e 5.2)
# ---------------------------------------------------------------------------

@dataclass
class DevelopedConceptDefinition:
    concept_id: str
    term: str
    developed_definition: str
    theoretical_context: str = ""
    relationships_explained: str = ""
    epistemic_status: str = "SOURCE_FACT"
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedConceptDefinition":
        return cls(
            concept_id=str(data.get("concept_id", "")),
            term=str(data.get("term", "")),
            developed_definition=str(data.get("developed_definition", "")),
            theoretical_context=str(data.get("theoretical_context", "")),
            relationships_explained=str(data.get("relationships_explained", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
        )


@dataclass
class DevelopedComparisonItem:
    dimension: str
    item_a_label: str
    item_a_description: str
    item_b_label: str
    item_b_description: str
    synthesis_note: str = ""
    epistemic_status: str = "SOURCE_FACT"
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedComparisonItem":
        return cls(
            dimension=str(data.get("dimension", "")),
            item_a_label=str(data.get("item_a_label", "")),
            item_a_description=str(data.get("item_a_description", "")),
            item_b_label=str(data.get("item_b_label", "")),
            item_b_description=str(data.get("item_b_description", "")),
            synthesis_note=str(data.get("synthesis_note", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
        )


@dataclass
class DevelopedContentBlock:
    block_id: str
    block_type: str  # ContentBlockType
    title: str
    body_paragraphs: List[str] = field(default_factory=list)
    bullet_points: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    is_hypothetical_example: bool = False
    epistemic_status: str = "SOURCE_FACT"
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)
    source_table_refs: List[str] = field(default_factory=list)
    source_figure_refs: List[str] = field(default_factory=list)
    source_formula_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedContentBlock":
        return cls(
            block_id=str(data.get("block_id", "")),
            block_type=str(data.get("block_type", ContentBlockType.EXPLANATORY_PARAGRAPH.value)),
            title=str(data.get("title", "")),
            body_paragraphs=[str(x) for x in (data.get("body_paragraphs") or []) if str(x).strip()],
            bullet_points=[str(x) for x in (data.get("bullet_points") or []) if str(x).strip()],
            steps=[str(x) for x in (data.get("steps") or []) if str(x).strip()],
            is_hypothetical_example=bool(data.get("is_hypothetical_example", False)),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
            source_table_refs=[str(x) for x in (data.get("source_table_refs") or []) if str(x).strip()],
            source_figure_refs=[str(x) for x in (data.get("source_figure_refs") or []) if str(x).strip()],
            source_formula_refs=[str(x) for x in (data.get("source_formula_refs") or []) if str(x).strip()],
        )


@dataclass
class DevelopedSectionContent:
    section_id: str
    chapter_id: str
    title: str
    order: int
    level: int = 2
    pedagogical_objective: str = ""
    content_role: str = ""
    explanation_strategy: str = ""
    opening_contextualization: str = ""
    content_blocks: List[DevelopedContentBlock] = field(default_factory=list)
    concept_definitions: List[DevelopedConceptDefinition] = field(default_factory=list)
    comparisons: List[DevelopedComparisonItem] = field(default_factory=list)
    limitations_and_caveats: List[str] = field(default_factory=list)
    section_synthesis: str = ""
    epistemic_status: str = "SOURCE_FACT"
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)
    generation_status: str = "COMPLETED"  # COMPLETED, PARTIAL, FALLBACK_GROUNDED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedSectionContent":
        return cls(
            section_id=str(data.get("section_id", "")),
            chapter_id=str(data.get("chapter_id", "")),
            title=str(data.get("title", "")),
            order=int(data.get("order", 1)),
            level=int(data.get("level", 2)),
            pedagogical_objective=str(data.get("pedagogical_objective", "")),
            content_role=str(data.get("content_role", "")),
            explanation_strategy=str(data.get("explanation_strategy", "")),
            opening_contextualization=str(data.get("opening_contextualization", "")),
            content_blocks=[
                DevelopedContentBlock.from_dict(b)
                for b in (data.get("content_blocks") or [])
                if isinstance(b, dict)
            ],
            concept_definitions=[
                DevelopedConceptDefinition.from_dict(c)
                for c in (data.get("concept_definitions") or [])
                if isinstance(c, dict)
            ],
            comparisons=[
                DevelopedComparisonItem.from_dict(c)
                for c in (data.get("comparisons") or [])
                if isinstance(c, dict)
            ],
            limitations_and_caveats=[
                str(x) for x in (data.get("limitations_and_caveats") or []) if str(x).strip()
            ],
            section_synthesis=str(data.get("section_synthesis", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
            generation_status=str(data.get("generation_status", "COMPLETED")),
        )

    @property
    def paragraphs(self) -> List[str]:
        res: List[str] = []
        if self.opening_contextualization:
            res.append(self.opening_contextualization)
        for b in self.content_blocks:
            res.extend(b.body_paragraphs)
        if self.section_synthesis:
            res.append(self.section_synthesis)
        return res

    @property
    def callout_boxes(self) -> List[Any]:
        return [b for b in self.content_blocks if "BOX" in b.block_type or "CALLOUT" in b.block_type or b.is_hypothetical_example]


@dataclass
class DevelopedChapterContent:
    chapter_id: str
    title: str
    order: int
    pedagogical_objective: str
    role_in_progression: str = ""
    chapter_introduction: str = ""
    sections: List[DevelopedSectionContent] = field(default_factory=list)
    chapter_synthesis: str = ""
    key_takeaways: List[str] = field(default_factory=list)
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedChapterContent":
        return cls(
            chapter_id=str(data.get("chapter_id", "")),
            title=str(data.get("title", "")),
            order=int(data.get("order", 1)),
            pedagogical_objective=str(data.get("pedagogical_objective", "")),
            role_in_progression=str(data.get("role_in_progression", "")),
            chapter_introduction=str(data.get("chapter_introduction", "")),
            sections=[
                DevelopedSectionContent.from_dict(s)
                for s in (data.get("sections") or [])
                if isinstance(s, dict)
            ],
            chapter_synthesis=str(data.get("chapter_synthesis", "")),
            key_takeaways=[str(x) for x in (data.get("key_takeaways") or []) if str(x).strip()],
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
        )


@dataclass
class DevelopedStudyDocumentContent:
    document_id: str
    plan_id: str
    plan_version: int = 1
    dossier_fingerprint: str = ""
    plan_fingerprint: str = ""
    document_title: str = ""
    document_subtitle: str = ""
    executive_study_overview: str = ""
    chapters: List[DevelopedChapterContent] = field(default_factory=list)
    global_integrative_synthesis: str = ""
    created_at: str = ""
    model_name: str = "qwen3.5:9b"
    generation_status: str = "COMPLETED"
    schema_version: str = "5.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopedStudyDocumentContent":
        return cls(
            document_id=str(data.get("document_id", "")),
            plan_id=str(data.get("plan_id", "")),
            plan_version=int(data.get("plan_version", 1)),
            dossier_fingerprint=str(data.get("dossier_fingerprint", "")),
            plan_fingerprint=str(data.get("plan_fingerprint", "")),
            document_title=str(data.get("document_title", "")),
            document_subtitle=str(data.get("document_subtitle", "")),
            executive_study_overview=str(data.get("executive_study_overview", "")),
            chapters=[
                DevelopedChapterContent.from_dict(c)
                for c in (data.get("chapters") or [])
                if isinstance(c, dict)
            ],
            global_integrative_synthesis=str(data.get("global_integrative_synthesis", "")),
            created_at=str(data.get("created_at", "")),
            model_name=str(data.get("model_name", "qwen3.5:9b")),
            generation_status=str(data.get("generation_status", "COMPLETED")),
            schema_version=str(data.get("schema_version", "5.0.0")),
        )


# ---------------------------------------------------------------------------
# 2. Modelos de Geração Visual Fundamentada (Componente 5.4)
# ---------------------------------------------------------------------------

@dataclass
class VisualNode:
    node_id: str
    label: str
    subtitle: str = ""
    epistemic_status: str = "SOURCE_FACT"  # SOURCE_FACT | MODEL_INFERENCE
    category: str = "core"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualNode":
        return cls(
            node_id=str(data.get("node_id", "")),
            label=str(data.get("label", "")),
            subtitle=str(data.get("subtitle", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            category=str(data.get("category", "core")),
        )


@dataclass
class VisualEdge:
    source_id: str
    target_id: str
    label: str = ""
    epistemic_status: str = "SOURCE_FACT"  # SOURCE_FACT | MODEL_INFERENCE
    is_directed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualEdge":
        return cls(
            source_id=str(data.get("source_id", "")),
            target_id=str(data.get("target_id", "")),
            label=str(data.get("label", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            is_directed=bool(data.get("is_directed", True)),
        )


@dataclass
class VisualDataSeries:
    series_name: str
    categories: List[str] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    unit: str = ""
    source_ref: str = ""
    epistemic_status: str = "SOURCE_FACT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualDataSeries":
        return cls(
            series_name=str(data.get("series_name", "")),
            categories=[str(c) for c in (data.get("categories") or [])],
            values=[float(v) for v in (data.get("values") or []) if isinstance(v, (int, float))],
            unit=str(data.get("unit", "")),
            source_ref=str(data.get("source_ref", "")),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
        )


@dataclass
class GeneratedVisualAsset:
    visual_id: str
    target_chapter_id: str
    target_section_id: str
    visual_type: str
    title: str
    caption: str
    pedagogical_objective: str
    render_status: str = VisualRenderStatus.RENDERED.value
    image_path: Optional[str] = None
    width_px: int = 0
    height_px: int = 0
    nodes: List[VisualNode] = field(default_factory=list)
    edges: List[VisualEdge] = field(default_factory=list)
    data_series: List[VisualDataSeries] = field(default_factory=list)
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[List[str]] = field(default_factory=list)
    epistemic_status: str = "SOURCE_FACT"
    provenance_label: str = ""
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)
    omission_or_fallback_reason: Optional[str] = None
    dpi: int = 220

    @property
    def is_grounded_in_source(self) -> bool:
        return (
            bool(self.evidence_refs or self.data_series or self.table_headers or self.nodes)
            and self.epistemic_status in ("SOURCE_FACT", "MODEL_INFERENCE")
            and not (self.render_status or "").startswith("OMITTED")
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_grounded_in_source"] = self.is_grounded_in_source
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedVisualAsset":
        return cls(
            visual_id=str(data.get("visual_id", "")),
            target_chapter_id=str(data.get("target_chapter_id", "")),
            target_section_id=str(data.get("target_section_id", "")),
            visual_type=str(data.get("visual_type", "")),
            title=str(data.get("title", "")),
            caption=str(data.get("caption", "")),
            pedagogical_objective=str(data.get("pedagogical_objective", "")),
            render_status=str(data.get("render_status", VisualRenderStatus.RENDERED.value)),
            image_path=data.get("image_path"),
            width_px=int(data.get("width_px", 0)),
            height_px=int(data.get("height_px", 0)),
            nodes=[VisualNode.from_dict(n) for n in (data.get("nodes") or []) if isinstance(n, dict)],
            edges=[VisualEdge.from_dict(e) for e in (data.get("edges") or []) if isinstance(e, dict)],
            data_series=[
                VisualDataSeries.from_dict(s) for s in (data.get("data_series") or []) if isinstance(s, dict)
            ],
            table_headers=[str(h) for h in (data.get("table_headers") or [])],
            table_rows=[[str(c) for c in row] for row in (data.get("table_rows") or []) if isinstance(row, list)],
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            provenance_label=str(data.get("provenance_label", "")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
            omission_or_fallback_reason=data.get("omission_or_fallback_reason"),
            dpi=int(data.get("dpi", 220)),
        )


# ---------------------------------------------------------------------------
# 3. Representação Intermédia Semântica — StudyDocumentIR (Componente 5.3)
# ---------------------------------------------------------------------------

@dataclass
class IRDocumentMetadata:
    document_id: str
    ir_id: str
    title: str
    subtitle: str
    original_filename: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[str] = None
    publication_venue: Optional[str] = None
    subject: str = "Estudo Académico"
    language: str = "pt-PT"
    design_profile_id: str = "ACADEMIC_EDITORIAL_CLASSIC"
    plan_id: str = ""
    plan_version: int = 1
    dossier_fingerprint: str = ""
    plan_fingerprint: str = ""
    created_at: str = ""
    model_name: str = "qwen3.5:9b"
    ir_version: str = "5.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRDocumentMetadata":
        return cls(
            document_id=str(data.get("document_id", "")),
            ir_id=str(data.get("ir_id", "")),
            title=str(data.get("title", "")),
            subtitle=str(data.get("subtitle", "")),
            original_filename=str(data.get("original_filename", "")),
            authors=[str(a) for a in (data.get("authors") or []) if str(a).strip()],
            year=str(data["year"]) if data.get("year") else None,
            publication_venue=str(data["publication_venue"]) if data.get("publication_venue") else None,
            subject=str(data.get("subject", "Estudo Académico")),
            language=str(data.get("language", "pt-PT")),
            design_profile_id=str(data.get("design_profile_id", "ACADEMIC_EDITORIAL_CLASSIC")),
            plan_id=str(data.get("plan_id", "")),
            plan_version=int(data.get("plan_version", 1)),
            dossier_fingerprint=str(data.get("dossier_fingerprint", "")),
            plan_fingerprint=str(data.get("plan_fingerprint", "")),
            created_at=str(data.get("created_at", "")),
            model_name=str(data.get("model_name", "qwen3.5:9b")),
            ir_version=str(data.get("ir_version", "5.0.0")),
        )


@dataclass
class IRTOCEntry:
    entry_id: str
    level: int  # 1 = Chapter, 2 = Section, 3 = Subsection
    number_label: str
    title: str
    target_block_id: str
    page_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRTOCEntry":
        return cls(
            entry_id=str(data.get("entry_id", "")),
            level=int(data.get("level", 1)),
            number_label=str(data.get("number_label", "")),
            title=str(data.get("title", "")),
            target_block_id=str(data.get("target_block_id", "")),
            page_number=int(data.get("page_number", 0)),
        )


@dataclass
class IRPaginationHint:
    keep_with_next: bool = False
    keep_together: bool = False
    page_break_before: bool = False
    prevent_widow_orphan: bool = True
    min_follow_height_pt: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRPaginationHint":
        return cls(
            keep_with_next=bool(data.get("keep_with_next", False)),
            keep_together=bool(data.get("keep_together", False)),
            page_break_before=bool(data.get("page_break_before", False)),
            prevent_widow_orphan=bool(data.get("prevent_widow_orphan", True)),
            min_follow_height_pt=float(data.get("min_follow_height_pt", 0.0)),
        )


@dataclass
class IRBlock:
    block_id: str
    kind: str  # IRBlockKind
    chapter_id: str = ""
    section_id: str = ""
    level: int = 0
    number_label: str = ""
    title: str = ""
    text: str = ""
    paragraphs: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    callout_kind: Optional[str] = None
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[List[str]] = field(default_factory=list)
    caption: str = ""
    equation_raw: str = ""
    equation_latex: str = ""
    visual_id: Optional[str] = None
    image_path: Optional[str] = None
    image_width_px: int = 0
    image_height_px: int = 0
    epistemic_status: str = "SOURCE_FACT"
    is_hypothetical_example: bool = False
    provenance_summary: str = ""
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)
    pagination: IRPaginationHint = field(default_factory=IRPaginationHint)

    @property
    def block_kind(self) -> str:
        return self.kind

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRBlock":
        return cls(
            block_id=str(data.get("block_id", "")),
            kind=str(data.get("kind", IRBlockKind.PARAGRAPH.value)),
            chapter_id=str(data.get("chapter_id", "")),
            section_id=str(data.get("section_id", "")),
            level=int(data.get("level", 0)),
            number_label=str(data.get("number_label", "")),
            title=str(data.get("title", "")),
            text=str(data.get("text", "")),
            paragraphs=[str(p) for p in (data.get("paragraphs") or []) if str(p).strip()],
            items=[str(i) for i in (data.get("items") or []) if str(i).strip()],
            callout_kind=data.get("callout_kind"),
            table_headers=[str(h) for h in (data.get("table_headers") or [])],
            table_rows=[[str(c) for c in row] for row in (data.get("table_rows") or []) if isinstance(row, list)],
            caption=str(data.get("caption", "")),
            equation_raw=str(data.get("equation_raw", "")),
            equation_latex=str(data.get("equation_latex", "")),
            visual_id=data.get("visual_id"),
            image_path=data.get("image_path"),
            image_width_px=int(data.get("image_width_px", 0)),
            image_height_px=int(data.get("image_height_px", 0)),
            epistemic_status=str(data.get("epistemic_status", "SOURCE_FACT")),
            is_hypothetical_example=bool(data.get("is_hypothetical_example", False)),
            provenance_summary=str(data.get("provenance_summary", "")),
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
            pagination=IRPaginationHint.from_dict(data.get("pagination") or {}),
        )


@dataclass
class IRSection:
    section_id: str
    chapter_id: str
    number_label: str
    title: str
    level: int
    order: int
    pedagogical_objective: str = ""
    content_role: str = ""
    blocks: List[IRBlock] = field(default_factory=list)
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRSection":
        return cls(
            section_id=str(data.get("section_id", "")),
            chapter_id=str(data.get("chapter_id", "")),
            number_label=str(data.get("number_label", "")),
            title=str(data.get("title", "")),
            level=int(data.get("level", 2)),
            order=int(data.get("order", 1)),
            pedagogical_objective=str(data.get("pedagogical_objective", "")),
            content_role=str(data.get("content_role", "")),
            blocks=[IRBlock.from_dict(b) for b in (data.get("blocks") or []) if isinstance(b, dict)],
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
        )


@dataclass
class IRChapter:
    chapter_id: str
    number_label: str
    title: str
    order: int
    pedagogical_objective: str = ""
    role_in_progression: str = ""
    intro_blocks: List[IRBlock] = field(default_factory=list)
    sections: List[IRSection] = field(default_factory=list)
    synthesis_blocks: List[IRBlock] = field(default_factory=list)
    evidence_refs: List[EditorialEvidenceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRChapter":
        return cls(
            chapter_id=str(data.get("chapter_id", "")),
            number_label=str(data.get("number_label", "")),
            title=str(data.get("title", "")),
            order=int(data.get("order", 1)),
            pedagogical_objective=str(data.get("pedagogical_objective", "")),
            role_in_progression=str(data.get("role_in_progression", "")),
            intro_blocks=[IRBlock.from_dict(b) for b in (data.get("intro_blocks") or []) if isinstance(b, dict)],
            sections=[IRSection.from_dict(s) for s in (data.get("sections") or []) if isinstance(s, dict)],
            synthesis_blocks=[
                IRBlock.from_dict(b) for b in (data.get("synthesis_blocks") or []) if isinstance(b, dict)
            ],
            evidence_refs=[
                EditorialEvidenceRef.from_dict(r)
                for r in (data.get("evidence_refs") or [])
                if isinstance(r, dict)
            ],
        )


@dataclass
class IRBibliographyEntry:
    ref_id: str
    citation_label: str
    formatted_reference: str
    authors: List[str] = field(default_factory=list)
    year: Optional[str] = None
    title: Optional[str] = None
    venue: Optional[str] = None
    doi_or_url: Optional[str] = None
    is_metadata_complete: bool = True
    metadata_limitation_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRBibliographyEntry":
        return cls(
            ref_id=str(data.get("ref_id", "")),
            citation_label=str(data.get("citation_label", "")),
            formatted_reference=str(data.get("formatted_reference", "")),
            authors=[str(a) for a in (data.get("authors") or []) if str(a).strip()],
            year=str(data["year"]) if data.get("year") else None,
            title=str(data["title"]) if data.get("title") else None,
            venue=str(data["venue"]) if data.get("venue") else None,
            doi_or_url=str(data["doi_or_url"]) if data.get("doi_or_url") else None,
            is_metadata_complete=bool(data.get("is_metadata_complete", True)),
            metadata_limitation_note=data.get("metadata_limitation_note"),
        )


@dataclass
class IRHeaderFooterSpec:
    running_header_left: str
    running_header_right: str
    footer_left: str
    footer_center: str = ""
    show_page_numbers: bool = True
    show_epistemic_notice: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IRHeaderFooterSpec":
        return cls(
            running_header_left=str(data.get("running_header_left", "")),
            running_header_right=str(data.get("running_header_right", "")),
            footer_left=str(data.get("footer_left", "")),
            footer_center=str(data.get("footer_center", "")),
            show_page_numbers=bool(data.get("show_page_numbers", True)),
            show_epistemic_notice=bool(data.get("show_epistemic_notice", True)),
        )


@dataclass
class StudyDocumentIR:
    metadata: IRDocumentMetadata
    executive_overview_blocks: List[IRBlock] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)
    toc_entries: List[IRTOCEntry] = field(default_factory=list)
    chapters: List[IRChapter] = field(default_factory=list)
    global_synthesis_blocks: List[IRBlock] = field(default_factory=list)
    bibliography: List[IRBibliographyEntry] = field(default_factory=list)
    provenance_summary_notes: List[str] = field(default_factory=list)
    header_footer: IRHeaderFooterSpec = field(
        default_factory=lambda: IRHeaderFooterSpec(
            running_header_left="JARVIS OS • Caderno Académico de Estudo",
            running_header_right="",
            footer_left="Proveniência auditada • Inferência local",
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDocumentIR":
        return cls(
            metadata=IRDocumentMetadata.from_dict(data.get("metadata") or {}),
            executive_overview_blocks=[
                IRBlock.from_dict(b) for b in (data.get("executive_overview_blocks") or []) if isinstance(b, dict)
            ],
            learning_objectives=[str(x) for x in (data.get("learning_objectives") or []) if str(x).strip()],
            toc_entries=[IRTOCEntry.from_dict(t) for t in (data.get("toc_entries") or []) if isinstance(t, dict)],
            chapters=[IRChapter.from_dict(c) for c in (data.get("chapters") or []) if isinstance(c, dict)],
            global_synthesis_blocks=[
                IRBlock.from_dict(b) for b in (data.get("global_synthesis_blocks") or []) if isinstance(b, dict)
            ],
            bibliography=[
                IRBibliographyEntry.from_dict(r) for r in (data.get("bibliography") or []) if isinstance(r, dict)
            ],
            provenance_summary_notes=[str(n) for n in (data.get("provenance_summary_notes") or []) if str(n).strip()],
            header_footer=IRHeaderFooterSpec.from_dict(data.get("header_footer") or {}),
        )


# ---------------------------------------------------------------------------
# 4. Modelos de Quality Assurance Documental (Componente 5.8)
# ---------------------------------------------------------------------------

@dataclass
class StudyDocumentQAFinding:
    finding_id: str
    axis: str  # QAAxis
    code: str
    severity: str  # QASeverity: BLOCKING_ERROR | WARNING | RECOMMENDATION
    message: str
    affected_elements: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDocumentQAFinding":
        return cls(
            finding_id=str(data.get("finding_id", "")),
            axis=str(data.get("axis", QAAxis.CONTENT_INTEGRITY.value)),
            code=str(data.get("code", "")),
            severity=str(data.get("severity", QASeverity.WARNING.value)),
            message=str(data.get("message", "")),
            affected_elements=[str(x) for x in (data.get("affected_elements") or [])],
            page_numbers=[int(p) for p in (data.get("page_numbers") or []) if isinstance(p, (int, float))],
            recommendation=str(data.get("recommendation", "")),
        )


@dataclass
class StudyDocumentQAReport:
    validation_status: str  # VALID | VALID_WITH_WARNINGS | INVALID_BLOCKING
    is_valid: bool
    blocking_errors_count: int = 0
    warnings_count: int = 0
    recommendations_count: int = 0
    chapter_coverage_pct: float = 100.0
    section_coverage_pct: float = 100.0
    visual_integrity_score: float = 100.0
    total_pages_inspected: int = 0
    selectable_text_verified: bool = False
    toc_verified: bool = False
    no_blank_pages_verified: bool = False
    no_orphan_headings_verified: bool = False
    no_text_clipping_verified: bool = False
    docx_verified: bool = False
    axis_summaries: Dict[str, str] = field(default_factory=dict)
    findings: List[StudyDocumentQAFinding] = field(default_factory=list)

    @property
    def blocking_count(self) -> int:
        return self.blocking_errors_count

    @property
    def overall_score(self) -> float:
        if self.blocking_errors_count > 0:
            return 0.0
        scores = [
            self.chapter_coverage_pct / 100.0,
            self.section_coverage_pct / 100.0,
            self.visual_integrity_score / 100.0,
            1.0 if self.selectable_text_verified else 0.8,
            1.0 if self.toc_verified else 0.8,
            1.0 if self.no_blank_pages_verified else 0.8,
        ]
        return max(0.0, min(1.0, sum(scores) / len(scores)))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDocumentQAReport":
        return cls(
            validation_status=str(data.get("validation_status", "VALID")),
            is_valid=bool(data.get("is_valid", True)),
            blocking_errors_count=int(data.get("blocking_errors_count", 0)),
            warnings_count=int(data.get("warnings_count", 0)),
            recommendations_count=int(data.get("recommendations_count", 0)),
            chapter_coverage_pct=float(data.get("chapter_coverage_pct", 100.0)),
            section_coverage_pct=float(data.get("section_coverage_pct", 100.0)),
            visual_integrity_score=float(data.get("visual_integrity_score", 100.0)),
            total_pages_inspected=int(data.get("total_pages_inspected", 0)),
            selectable_text_verified=bool(data.get("selectable_text_verified", False)),
            toc_verified=bool(data.get("toc_verified", False)),
            no_blank_pages_verified=bool(data.get("no_blank_pages_verified", False)),
            no_orphan_headings_verified=bool(data.get("no_orphan_headings_verified", False)),
            no_text_clipping_verified=bool(data.get("no_text_clipping_verified", False)),
            docx_verified=bool(data.get("docx_verified", False)),
            axis_summaries=dict(data.get("axis_summaries") or {}),
            findings=[
                StudyDocumentQAFinding.from_dict(f)
                for f in (data.get("findings") or [])
                if isinstance(f, dict)
            ],
        )


# ---------------------------------------------------------------------------
# 5. Telemetria, Histórico de Versões e Resultado Final
# ---------------------------------------------------------------------------

@dataclass
class DocumentGenerationTelemetry:
    total_duration_ms: float = 0.0
    llm_calls_count: int = 0
    llm_retries_count: int = 0
    prompt_tokens_total: int = 0
    completion_tokens_total: int = 0
    chapters_processed: int = 0
    sections_processed: int = 0
    visuals_rendered: int = 0
    visuals_omitted: int = 0
    pdf_pages_count: int = 0
    pdf_size_bytes: int = 0
    docx_size_bytes: int = 0
    stage_timings_ms: Dict[str, float] = field(default_factory=dict)
    prompt_versions: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentGenerationTelemetry":
        return cls(
            total_duration_ms=float(data.get("total_duration_ms", 0.0)),
            llm_calls_count=int(data.get("llm_calls_count", 0)),
            llm_retries_count=int(data.get("llm_retries_count", 0)),
            prompt_tokens_total=int(data.get("prompt_tokens_total", 0)),
            completion_tokens_total=int(data.get("completion_tokens_total", 0)),
            chapters_processed=int(data.get("chapters_processed", 0)),
            sections_processed=int(data.get("sections_processed", 0)),
            visuals_rendered=int(data.get("visuals_rendered", 0)),
            visuals_omitted=int(data.get("visuals_omitted", 0)),
            pdf_pages_count=int(data.get("pdf_pages_count", 0)),
            pdf_size_bytes=int(data.get("pdf_size_bytes", 0)),
            docx_size_bytes=int(data.get("docx_size_bytes", 0)),
            stage_timings_ms={str(k): float(v) for k, v in (data.get("stage_timings_ms") or {}).items()},
            prompt_versions={str(k): str(v) for k, v in (data.get("prompt_versions") or {}).items()},
        )


@dataclass
class StudyDocumentVersionRecord:
    version: int
    created_at: str
    status: str  # COMPLETED | PARTIAL | FAILED
    design_profile: str
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_sha256: Optional[str] = None
    docx_sha256: Optional[str] = None
    total_pages: int = 0
    qa_validation_status: str = "VALID"
    plan_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDocumentVersionRecord":
        return cls(
            version=int(data.get("version", 1)),
            created_at=str(data.get("created_at", "")),
            status=str(data.get("status", "COMPLETED")),
            design_profile=str(data.get("design_profile", "ACADEMIC_EDITORIAL_CLASSIC")),
            pdf_path=data.get("pdf_path"),
            docx_path=data.get("docx_path"),
            pdf_sha256=data.get("pdf_sha256"),
            docx_sha256=data.get("docx_sha256"),
            total_pages=int(data.get("total_pages", 0)),
            qa_validation_status=str(data.get("qa_validation_status", "VALID")),
            plan_version=int(data.get("plan_version", 1)),
        )


@dataclass
class StudyDocumentGenerationResult:
    document_id: str
    version: int
    status: str  # DocumentGenerationState
    design_profile: str
    pdf_path: Optional[str]
    docx_path: Optional[str]
    pdf_sha256: Optional[str]
    docx_sha256: Optional[str]
    ir_path: Optional[str]
    developed_content_path: Optional[str]
    qa_report_path: Optional[str]
    qa_report: StudyDocumentQAReport
    plan_fingerprint: str = ""
    dossier_fingerprint: str = ""
    telemetry: DocumentGenerationTelemetry = field(default_factory=DocumentGenerationTelemetry)
    visual_assets: List[GeneratedVisualAsset] = field(default_factory=list)
    versions_history: List[StudyDocumentVersionRecord] = field(default_factory=list)
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    schema_version: str = "5.0.0"
    engine_version: str = "5.0.0-docgen"

    @property
    def source_plan_fingerprint(self) -> str:
        return self.plan_fingerprint

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source_plan_fingerprint"] = self.source_plan_fingerprint
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDocumentGenerationResult":
        return cls(
            document_id=str(data.get("document_id", "")),
            version=int(data.get("version", 1)),
            status=str(data.get("status", DocumentGenerationState.COMPLETED.value)),
            design_profile=str(data.get("design_profile", "ACADEMIC_EDITORIAL_CLASSIC")),
            pdf_path=data.get("pdf_path"),
            docx_path=data.get("docx_path"),
            pdf_sha256=data.get("pdf_sha256"),
            docx_sha256=data.get("docx_sha256"),
            ir_path=data.get("ir_path"),
            developed_content_path=data.get("developed_content_path"),
            qa_report_path=data.get("qa_report_path"),
            qa_report=StudyDocumentQAReport.from_dict(data.get("qa_report") or {}),
            plan_fingerprint=str(data.get("plan_fingerprint") or data.get("source_plan_fingerprint") or ""),
            dossier_fingerprint=str(data.get("dossier_fingerprint") or ""),
            telemetry=DocumentGenerationTelemetry.from_dict(data.get("telemetry") or {}),
            visual_assets=[
                GeneratedVisualAsset.from_dict(v)
                for v in (data.get("visual_assets") or [])
                if isinstance(v, dict)
            ],
            versions_history=[
                StudyDocumentVersionRecord.from_dict(vh)
                for vh in (data.get("versions_history") or [])
                if isinstance(vh, dict)
            ],
            failed_operations=list(data.get("failed_operations") or []),
            created_at=str(data.get("created_at", "")),
            schema_version=str(data.get("schema_version", "5.0.0")),
            engine_version=str(data.get("engine_version", "5.0.0-docgen")),
        )

