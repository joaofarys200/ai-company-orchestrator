"""
JARVIS OS — Document Engine Package.
Unified document intelligence and Microsoft Word (.docx) authoring & revision system.
"""

from backend.document_engine.contracts import (
    DocumentFormat,
    DocumentMetrics,
    DocumentProject,
    DocumentReview,
    DocumentSection,
    DocumentSnapshot,
    DocumentTelemetry,
    DocumentTemplate,
    Evidence,
    EvidenceGraph,
    EvidenceSource,
    EvidenceSourceKind,
    ExportResult,
    FactEntity,
    FactRelationship,
    GeneratedDocument,
    KnowledgeGraph,
    KnowledgeNode,
    KnowledgeRelation,
)
from backend.document_engine.editorial_planner import (
    EditorialFinding,
    EditorialPlan,
    EditorialPlanSection,
    EditorialPlanner,
    EditorialReviewReport,
    ReviewFindingSeverity,
)
from backend.document_engine.profiles import (
    AcademicProfile,
    BusinessProposalProfile,
    DocumentProfile,
    DocumentProfileType,
    ExecutiveMemoProfile,
    GenericProfile,
    TechnicalSpecProfile,
    get_profile,
)
from backend.document_engine.surgical_revisor import (
    RevisionDirective,
    RevisionSummary,
    SurgicalRevisor,
)
from backend.document_engine.visual_inspector import (
    LayoutFlaw,
    VisualInspectionResult,
    VisualInspector,
)
from backend.document_engine.word_ast import (
    FieldNode,
    HeadingNode,
    HyperlinkNode,
    ImageNode,
    ParagraphNode,
    RunNode,
    SectionNode,
    TableCellNode,
    TableNode,
    UnparsedElementNode,
    WordDocumentAST,
    WordDocumentMetadata,
    extract_ast_from_docx,
)
from backend.document_engine.word_engine import (
    DocumentCreationRequest,
    DocumentEngineResult,
    ValidationReport,
    WordDocumentEngine,
)
from backend.document_engine.word_styler import WordStyler

__all__ = [
    # Canonical Engine & Requests
    "WordDocumentEngine",
    "DocumentCreationRequest",
    "DocumentEngineResult",
    "ValidationReport",
    "WordStyler",
    # AST
    "WordDocumentAST",
    "WordDocumentMetadata",
    "HeadingNode",
    "ParagraphNode",
    "RunNode",
    "TableNode",
    "TableCellNode",
    "ImageNode",
    "SectionNode",
    "HyperlinkNode",
    "FieldNode",
    "UnparsedElementNode",
    "extract_ast_from_docx",
    # Editorial Planning & Review
    "EditorialPlanner",
    "EditorialPlan",
    "EditorialPlanSection",
    "EditorialReviewReport",
    "EditorialFinding",
    "ReviewFindingSeverity",
    # Profiles
    "DocumentProfile",
    "DocumentProfileType",
    "AcademicProfile",
    "TechnicalSpecProfile",
    "BusinessProposalProfile",
    "ExecutiveMemoProfile",
    "GenericProfile",
    "get_profile",
    # Revision
    "SurgicalRevisor",
    "RevisionDirective",
    "RevisionSummary",
    # Visual Inspection & Rendering
    "VisualInspector",
    "VisualInspectionResult",
    "LayoutFlaw",
    # Architecture contracts
    "DocumentFormat",
    "ExportResult",
    "GeneratedDocument",
    "DocumentReview",
    "DocumentSection",
    "DocumentSnapshot",
    "DocumentMetrics",
    "DocumentTelemetry",
    "DocumentProject",
    "DocumentTemplate",
    "Evidence",
    "EvidenceGraph",
    "EvidenceSource",
    "EvidenceSourceKind",
    "FactEntity",
    "FactRelationship",
    "KnowledgeGraph",
    "KnowledgeNode",
    "KnowledgeRelation",
]
