"""
JARVIS OS — Study Engine Phase 6: Study Modes, Active Recall & Adaptive Learning
Contratos estruturados, enums, normalizadores epistémicos e modelos persistíveis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from services.academic_reasoning_engine import EvidenceRef
from services.study_document_generation.contracts import (
    VALID_EPISTEMIC_STATUSES,
    normalize_epistemic_status,
)


SCHEMA_VERSION_PHASE6 = "6.0.0"
ENGINE_VERSION_PHASE6 = "6.0.0-study-modes"
SRS_ALGORITHM_VERSION = "sm2-v6.0"

PROMPT_VERSIONS_PHASE6: Dict[str, str] = {
    "flashcards_generation": "v6.0.0-fc",
    "cornell_notes_generation": "v6.0.0-cornell",
    "assessment_generation": "v6.0.0-quiz",
    "open_answer_evaluation": "v6.0.0-eval",
    "active_recall_generation": "v6.0.0-recall",
}


# ---------------------------------------------------------------------------
# Enumerações de Domínio
# ---------------------------------------------------------------------------

class ContentDifficulty(str, Enum):
    FOUNDATIONAL = "FOUNDATIONAL"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class QuestionDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class FlashcardType(str, Enum):
    DEFINITION = "DEFINITION"
    CONCEPTUAL_UNDERSTANDING = "CONCEPTUAL_UNDERSTANDING"
    RELATIONSHIP = "RELATIONSHIP"
    METHODOLOGY = "METHODOLOGY"
    RESULTS_CONCLUSIONS = "RESULTS_CONCLUSIONS"
    APPLICATION = "APPLICATION"
    ANALYTICAL = "ANALYTICAL"


class FlashcardReviewStatus(str, Enum):
    NEW = "NEW"
    LEARNING = "LEARNING"
    MASTERED = "MASTERED"
    EDITED = "EDITED"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    CONCEPT_EXPLANATION = "CONCEPT_EXPLANATION"
    COMPARISON = "COMPARISON"
    APPLICATION_SCENARIO = "APPLICATION_SCENARIO"
    ANALYTICAL = "ANALYTICAL"


class AssessmentFeedbackMode(str, Enum):
    IMMEDIATE = "IMMEDIATE"  # Practice mode
    DEFERRED = "DEFERRED"    # Assessment/Exam mode


class AssessmentSessionMode(str, Enum):
    PRACTICE = "PRACTICE"
    ASSESSMENT = "ASSESSMENT"


class OpenAnswerVerdict(str, Enum):
    CORRECT = "CORRECT"
    PARTIAL = "PARTIAL"
    INCOMPLETE_EXPLANATION = "INCOMPLETE_EXPLANATION"
    FACTUAL_ERROR = "FACTUAL_ERROR"
    AMBIGUOUS = "AMBIGUOUS"
    UNANSWERED = "UNANSWERED"


class ActiveRecallPromptType(str, Enum):
    CONCEPT_EXPLANATION = "CONCEPT_EXPLANATION"
    ARGUMENT_RECONSTRUCTION = "ARGUMENT_RECONSTRUCTION"
    METHODOLOGY_STEPS = "METHODOLOGY_STEPS"
    CONCEPT_RELATIONSHIPS = "CONCEPT_RELATIONSHIPS"
    RESULT_SIGNIFICANCE = "RESULT_SIGNIFICANCE"
    CHAPTER_STRUCTURE = "CHAPTER_STRUCTURE"


class ReviewLearningState(str, Enum):
    NEW = "NEW"
    LEARNING = "LEARNING"
    DUE = "DUE"
    LAPSED = "LAPSED"
    MATURE = "MATURE"
    SUSPENDED = "SUSPENDED"


class MasteryLevel(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EMERGING = "EMERGING"
    DEVELOPING = "DEVELOPING"
    PROFICIENT = "PROFICIENT"


class KnowledgeGapType(str, Enum):
    REPEATED_CONCEPT_MISS = "REPEATED_CONCEPT_MISS"
    CONCEPT_CONFUSION = "CONCEPT_CONFUSION"
    METHODOLOGY_RECALL_FAILURE = "METHODOLOGY_RECALL_FAILURE"
    RELATIONSHIP_MISUNDERSTANDING = "RELATIONSHIP_MISUNDERSTANDING"
    FACTUAL_ACCURACY_DEFICIT = "FACTUAL_ACCURACY_DEFICIT"
    CHAPTER_STRUGGLE = "CHAPTER_STRUGGLE"


class StudySessionMode(str, Enum):
    FLASHCARD_REVIEW = "FLASHCARD_REVIEW"
    ACTIVE_RECALL = "ACTIVE_RECALL"
    ASSESSMENT = "ASSESSMENT"
    CORNELL_STUDY = "CORNELL_STUDY"
    DAILY_REVIEW = "DAILY_REVIEW"


class StudySessionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class StudyModeReadinessStatus(str, Enum):
    READY = "READY"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    MISSING_AST = "MISSING_AST"
    MISSING_DOSSIER = "MISSING_DOSSIER"
    MISSING_PLAN = "MISSING_PLAN"
    INVALID_UPSTREAM_ARTIFACT = "INVALID_UPSTREAM_ARTIFACT"
    STALE_SOURCE_ARTIFACTS = "STALE_SOURCE_ARTIFACTS"


# ---------------------------------------------------------------------------
# Helpers Comuns
# ---------------------------------------------------------------------------

def _deserialize_refs(raw: Any) -> List[EvidenceRef]:
    out: List[EvidenceRef] = []
    if not isinstance(raw, list):
        return out
    known = set(EvidenceRef.__dataclass_fields__.keys())
    for item in raw:
        if isinstance(item, EvidenceRef):
            out.append(item)
        elif isinstance(item, dict):
            payload = {k: v for k, v in item.items() if k in known}
            payload["status"] = normalize_epistemic_status(payload.get("status"), default="UNVERIFIED")
            out.append(EvidenceRef(**payload))
    return out


@dataclass
class SourceLocation:
    """Referência estruturada à origem académica de uma atividade de estudo."""
    document_id: str
    chapter_id: str = ""
    section_id: str = ""
    original_section_id: str = ""
    paragraph_ids: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    concept_ids: List[str] = field(default_factory=list)
    learning_objective_id: str = ""
    learning_objective_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceLocation":
        d = data or {}
        return cls(
            document_id=str(d.get("document_id", "")),
            chapter_id=str(d.get("chapter_id", "")),
            section_id=str(d.get("section_id", "")),
            original_section_id=str(d.get("original_section_id", "")),
            paragraph_ids=[str(x) for x in (d.get("paragraph_ids") or []) if str(x).strip()],
            page_numbers=[int(p) for p in (d.get("page_numbers") or []) if isinstance(p, (int, float)) and int(p) > 0],
            concept_ids=[str(x) for x in (d.get("concept_ids") or []) if str(x).strip()],
            learning_objective_id=str(d.get("learning_objective_id", "")),
            learning_objective_text=str(d.get("learning_objective_text", "")),
        )


@dataclass
class SourceFingerprintSnapshot:
    """Impressão digital dos artefactos das Fases 2–5 usados para deteção de obsolescência."""
    document_id: str
    ast_fingerprint: str = ""
    dossier_fingerprint: str = ""
    plan_fingerprint: str = ""
    plan_version: int = 1
    model_name: str = "qwen3.5:9b"
    prompt_versions: Dict[str, str] = field(default_factory=lambda: dict(PROMPT_VERSIONS_PHASE6))
    captured_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceFingerprintSnapshot":
        d = data or {}
        return cls(
            document_id=str(d.get("document_id", "")),
            ast_fingerprint=str(d.get("ast_fingerprint", "")),
            dossier_fingerprint=str(d.get("dossier_fingerprint", "")),
            plan_fingerprint=str(d.get("plan_fingerprint", "")),
            plan_version=int(d.get("plan_version", 1)),
            model_name=str(d.get("model_name", "qwen3.5:9b")),
            prompt_versions={str(k): str(v) for k, v in (d.get("prompt_versions") or {}).items()},
            captured_at=str(d.get("captured_at", "")),
        )


# ---------------------------------------------------------------------------
# 1. Flashcards Inteligentes
# ---------------------------------------------------------------------------

@dataclass
class AdaptiveFlashcard:
    card_id: str
    document_id: str
    front: str
    back: str
    card_type: str = FlashcardType.CONCEPTUAL_UNDERSTANDING.value
    content_difficulty: str = ContentDifficulty.INTERMEDIATE.value
    question_difficulty: str = QuestionDifficulty.MEDIUM.value
    chapter_id: str = ""
    chapter_title: str = ""
    section_id: str = ""
    section_title: str = ""
    topic: str = ""
    learning_objective_id: str = ""
    learning_objective_text: str = ""
    concept_ids: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    epistemic_status: str = "MODEL_INFERENCE"
    is_hypothetical_scenario: bool = False
    generation_mode: str = "LLM_GROUNDED"  # LLM_GROUNDED | DETERMINISTIC_GROUNDED | USER_CREATED
    generation_metadata: Dict[str, Any] = field(default_factory=dict)
    review_status: str = FlashcardReviewStatus.NEW.value
    user_edited: bool = False
    edited_at: Optional[str] = None
    is_deleted: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdaptiveFlashcard":
        d = data or {}
        return cls(
            card_id=str(d.get("card_id", "")),
            document_id=str(d.get("document_id", "")),
            front=str(d.get("front", "")),
            back=str(d.get("back", "")),
            card_type=str(d.get("card_type", FlashcardType.CONCEPTUAL_UNDERSTANDING.value)),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            chapter_id=str(d.get("chapter_id", "")),
            chapter_title=str(d.get("chapter_title", "")),
            section_id=str(d.get("section_id", "")),
            section_title=str(d.get("section_title", "")),
            topic=str(d.get("topic", "")),
            learning_objective_id=str(d.get("learning_objective_id", "")),
            learning_objective_text=str(d.get("learning_objective_text", "")),
            concept_ids=[str(x) for x in (d.get("concept_ids") or []) if str(x).strip()],
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            source_pages=[int(p) for p in (d.get("source_pages") or []) if isinstance(p, (int, float)) and int(p) > 0],
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
            is_hypothetical_scenario=bool(d.get("is_hypothetical_scenario", False)),
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
            generation_metadata=dict(d.get("generation_metadata") or {}),
            review_status=str(d.get("review_status", FlashcardReviewStatus.NEW.value)),
            user_edited=bool(d.get("user_edited", False)),
            edited_at=d.get("edited_at"),
            is_deleted=bool(d.get("is_deleted", False)),
            created_at=str(d.get("created_at", "")),
        )


@dataclass
class StudyDeck:
    deck_id: str
    document_id: str
    title: str
    document_nature: str = ""
    cards: List[AdaptiveFlashcard] = field(default_factory=list)
    fingerprints: Optional[SourceFingerprintSnapshot] = None
    generation_mode: str = "LLM_GROUNDED"
    status: str = "COMPLETED"
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: str = SCHEMA_VERSION_PHASE6

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyDeck":
        d = data or {}
        fp = d.get("fingerprints")
        return cls(
            deck_id=str(d.get("deck_id", "")),
            document_id=str(d.get("document_id", "")),
            title=str(d.get("title", "")),
            document_nature=str(d.get("document_nature", "")),
            cards=[AdaptiveFlashcard.from_dict(c) for c in (d.get("cards") or []) if isinstance(c, dict)],
            fingerprints=SourceFingerprintSnapshot.from_dict(fp) if isinstance(fp, dict) else None,
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
            status=str(d.get("status", "COMPLETED")),
            failed_operations=list(d.get("failed_operations") or []),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            schema_version=str(d.get("schema_version", SCHEMA_VERSION_PHASE6)),
        )


# ---------------------------------------------------------------------------
# 2. Cornell Notes Estruturadas
# ---------------------------------------------------------------------------

@dataclass
class CornellCueItem:
    cue_id: str
    cue_prompt: str
    cue_type: str = "QUESTION"  # QUESTION | KEYWORD | CONCEPT | RECALL_PROMPT | CONNECTION
    answer_hint: str = ""
    epistemic_status: str = "MODEL_INFERENCE"
    concept_ids: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    is_important: bool = False
    user_edited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CornellCueItem":
        d = data or {}
        return cls(
            cue_id=str(d.get("cue_id", "")),
            cue_prompt=str(d.get("cue_prompt", "")),
            cue_type=str(d.get("cue_type", "QUESTION")),
            answer_hint=str(d.get("answer_hint", "")),
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
            concept_ids=[str(x) for x in (d.get("concept_ids") or []) if str(x).strip()],
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            is_important=bool(d.get("is_important", False)),
            user_edited=bool(d.get("user_edited", False)),
        )


@dataclass
class CornellPersonalNote:
    note_id: str
    section_id: str
    content: str
    is_important: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CornellPersonalNote":
        d = data or {}
        return cls(
            note_id=str(d.get("note_id", "")),
            section_id=str(d.get("section_id", "")),
            content=str(d.get("content", "")),
            is_important=bool(d.get("is_important", False)),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )


@dataclass
class CornellNoteEntry:
    entry_id: str
    chapter_id: str
    chapter_title: str
    section_id: str
    section_title: str
    sufficient_evidence: bool = True
    insufficiency_reason: str = ""
    main_concepts: List[Dict[str, Any]] = field(default_factory=list)
    explanations: List[str] = field(default_factory=list)
    supporting_details: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    concept_relationships: List[str] = field(default_factory=list)
    methodology_notes: str = ""
    results_and_conclusions_notes: str = ""
    cue_column: List[CornellCueItem] = field(default_factory=list)
    summary_section: str = ""
    source_pages: List[int] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    epistemic_status: str = "MODEL_INFERENCE"
    is_important: bool = False
    personal_notes: List[CornellPersonalNote] = field(default_factory=list)
    user_edited: bool = False
    edited_fields: List[str] = field(default_factory=list)
    generation_mode: str = "LLM_GROUNDED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CornellNoteEntry":
        d = data or {}
        return cls(
            entry_id=str(d.get("entry_id", "")),
            chapter_id=str(d.get("chapter_id", "")),
            chapter_title=str(d.get("chapter_title", "")),
            section_id=str(d.get("section_id", "")),
            section_title=str(d.get("section_title", "")),
            sufficient_evidence=bool(d.get("sufficient_evidence", True)),
            insufficiency_reason=str(d.get("insufficiency_reason", "")),
            main_concepts=[dict(x) for x in (d.get("main_concepts") or []) if isinstance(x, dict)],
            explanations=[str(x) for x in (d.get("explanations") or []) if str(x).strip()],
            supporting_details=[str(x) for x in (d.get("supporting_details") or []) if str(x).strip()],
            examples=[str(x) for x in (d.get("examples") or []) if str(x).strip()],
            concept_relationships=[str(x) for x in (d.get("concept_relationships") or []) if str(x).strip()],
            methodology_notes=str(d.get("methodology_notes", "")),
            results_and_conclusions_notes=str(d.get("results_and_conclusions_notes", "")),
            cue_column=[CornellCueItem.from_dict(c) for c in (d.get("cue_column") or []) if isinstance(c, dict)],
            summary_section=str(d.get("summary_section", "")),
            source_pages=[int(p) for p in (d.get("source_pages") or []) if isinstance(p, (int, float)) and int(p) > 0],
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
            is_important=bool(d.get("is_important", False)),
            personal_notes=[
                CornellPersonalNote.from_dict(n)
                for n in (d.get("personal_notes") or [])
                if isinstance(n, dict)
            ],
            user_edited=bool(d.get("user_edited", False)),
            edited_fields=[str(x) for x in (d.get("edited_fields") or []) if str(x).strip()],
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
        )


@dataclass
class CornellStudyDocument:
    cornell_id: str
    document_id: str
    title: str
    subject: str = "Geral"
    global_summary: str = ""
    entries: List[CornellNoteEntry] = field(default_factory=list)
    fingerprints: Optional[SourceFingerprintSnapshot] = None
    generation_mode: str = "LLM_GROUNDED"
    status: str = "COMPLETED"
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: str = SCHEMA_VERSION_PHASE6

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CornellStudyDocument":
        d = data or {}
        fp = d.get("fingerprints")
        return cls(
            cornell_id=str(d.get("cornell_id", "")),
            document_id=str(d.get("document_id", "")),
            title=str(d.get("title", "")),
            subject=str(d.get("subject", "Geral")),
            global_summary=str(d.get("global_summary", "")),
            entries=[CornellNoteEntry.from_dict(e) for e in (d.get("entries") or []) if isinstance(e, dict)],
            fingerprints=SourceFingerprintSnapshot.from_dict(fp) if isinstance(fp, dict) else None,
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
            status=str(d.get("status", "COMPLETED")),
            failed_operations=list(d.get("failed_operations") or []),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            schema_version=str(d.get("schema_version", SCHEMA_VERSION_PHASE6)),
        )


# ---------------------------------------------------------------------------
# 3. Avaliações & Quizzes Pedagógicos
# ---------------------------------------------------------------------------

@dataclass
class ScoringCriterion:
    criterion_id: str
    description: str
    weight: float = 1.0
    required_concepts: List[str] = field(default_factory=list)
    factual_anchors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringCriterion":
        d = data or {}
        return cls(
            criterion_id=str(d.get("criterion_id", "")),
            description=str(d.get("description", "")),
            weight=float(d.get("weight", 1.0)),
            required_concepts=[str(x) for x in (d.get("required_concepts") or []) if str(x).strip()],
            factual_anchors=[str(x) for x in (d.get("factual_anchors") or []) if str(x).strip()],
        )


@dataclass
class AssessmentQuestion:
    question_id: str
    document_id: str
    question_text: str
    question_type: str = QuestionType.MULTIPLE_CHOICE.value
    content_difficulty: str = ContentDifficulty.INTERMEDIATE.value
    question_difficulty: str = QuestionDifficulty.MEDIUM.value
    options: List[str] = field(default_factory=list)
    correct_index: Optional[int] = None
    correct_answer: str = ""
    explanation: str = ""
    topic: str = ""
    chapter_id: str = ""
    section_id: str = ""
    learning_objective_id: str = ""
    learning_objective_text: str = ""
    related_concept_ids: List[str] = field(default_factory=list)
    related_concept_names: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    source_location: Optional[SourceLocation] = None
    epistemic_status: str = "SOURCE_FACT"
    is_hypothetical_scenario: bool = False
    scoring_criteria: List[ScoringCriterion] = field(default_factory=list)
    generation_mode: str = "LLM_GROUNDED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssessmentQuestion":
        d = data or {}
        sl = d.get("source_location")
        ci = d.get("correct_index")
        return cls(
            question_id=str(d.get("question_id", "")),
            document_id=str(d.get("document_id", "")),
            question_text=str(d.get("question_text", "")),
            question_type=str(d.get("question_type", QuestionType.MULTIPLE_CHOICE.value)),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            options=[str(o) for o in (d.get("options") or [])],
            correct_index=int(ci) if isinstance(ci, (int, float)) and ci is not None else None,
            correct_answer=str(d.get("correct_answer", "")),
            explanation=str(d.get("explanation", "")),
            topic=str(d.get("topic", "")),
            chapter_id=str(d.get("chapter_id", "")),
            section_id=str(d.get("section_id", "")),
            learning_objective_id=str(d.get("learning_objective_id", "")),
            learning_objective_text=str(d.get("learning_objective_text", "")),
            related_concept_ids=[str(x) for x in (d.get("related_concept_ids") or []) if str(x).strip()],
            related_concept_names=[str(x) for x in (d.get("related_concept_names") or []) if str(x).strip()],
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            source_location=SourceLocation.from_dict(sl) if isinstance(sl, dict) else None,
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
            is_hypothetical_scenario=bool(d.get("is_hypothetical_scenario", False)),
            scoring_criteria=[
                ScoringCriterion.from_dict(c) for c in (d.get("scoring_criteria") or []) if isinstance(c, dict)
            ],
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
        )


@dataclass
class AssessmentConfig:
    question_count: int = 8
    chapter_ids: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    difficulty: str = "MIXED"  # EASY | MEDIUM | HARD | MIXED
    question_types: List[str] = field(default_factory=list)
    session_mode: str = AssessmentSessionMode.PRACTICE.value
    feedback_mode: str = AssessmentFeedbackMode.IMMEDIATE.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssessmentConfig":
        d = data or {}
        return cls(
            question_count=max(1, int(d.get("question_count", 8))),
            chapter_ids=[str(x) for x in (d.get("chapter_ids") or []) if str(x).strip()],
            topics=[str(x) for x in (d.get("topics") or []) if str(x).strip()],
            difficulty=str(d.get("difficulty", "MIXED")),
            question_types=[str(x) for x in (d.get("question_types") or []) if str(x).strip()],
            session_mode=str(d.get("session_mode", AssessmentSessionMode.PRACTICE.value)),
            feedback_mode=str(d.get("feedback_mode", AssessmentFeedbackMode.IMMEDIATE.value)),
        )


@dataclass
class StudyAssessment:
    assessment_id: str
    document_id: str
    title: str
    config: AssessmentConfig = field(default_factory=AssessmentConfig)
    questions: List[AssessmentQuestion] = field(default_factory=list)
    fingerprints: Optional[SourceFingerprintSnapshot] = None
    generation_mode: str = "LLM_GROUNDED"
    status: str = "COMPLETED"
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyAssessment":
        d = data or {}
        fp = d.get("fingerprints")
        return cls(
            assessment_id=str(d.get("assessment_id", "")),
            document_id=str(d.get("document_id", "")),
            title=str(d.get("title", "")),
            config=AssessmentConfig.from_dict(d.get("config") or {}),
            questions=[
                AssessmentQuestion.from_dict(q) for q in (d.get("questions") or []) if isinstance(q, dict)
            ],
            fingerprints=SourceFingerprintSnapshot.from_dict(fp) if isinstance(fp, dict) else None,
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
            status=str(d.get("status", "COMPLETED")),
            failed_operations=list(d.get("failed_operations") or []),
            created_at=str(d.get("created_at", "")),
        )


@dataclass
class OpenAnswerEvaluation:
    question_id: str
    student_answer: str
    verdict: str = OpenAnswerVerdict.INCOMPLETE_EXPLANATION.value
    score_ratio: float = 0.0  # 0.0..1.0
    is_correct: bool = False
    is_uncertain: bool = False
    factual_errors: List[str] = field(default_factory=list)
    missing_points: List[str] = field(default_factory=list)
    covered_points: List[str] = field(default_factory=list)
    criteria_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    evaluation_mode: str = "DETERMINISTIC_RUBRIC"  # DETERMINISTIC_RUBRIC | LLM_RUBRIC_GUIDED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenAnswerEvaluation":
        d = data or {}
        return cls(
            question_id=str(d.get("question_id", "")),
            student_answer=str(d.get("student_answer", "")),
            verdict=str(d.get("verdict", OpenAnswerVerdict.INCOMPLETE_EXPLANATION.value)),
            score_ratio=float(d.get("score_ratio", 0.0)),
            is_correct=bool(d.get("is_correct", False)),
            is_uncertain=bool(d.get("is_uncertain", False)),
            factual_errors=[str(x) for x in (d.get("factual_errors") or [])],
            missing_points=[str(x) for x in (d.get("missing_points") or [])],
            covered_points=[str(x) for x in (d.get("covered_points") or [])],
            criteria_breakdown=[dict(x) for x in (d.get("criteria_breakdown") or []) if isinstance(x, dict)],
            reasoning=str(d.get("reasoning", "")),
            evaluation_mode=str(d.get("evaluation_mode", "DETERMINISTIC_RUBRIC")),
        )


@dataclass
class QuestionAttemptOutcome:
    question_id: str
    question_type: str
    topic: str
    chapter_id: str
    section_id: str
    question_difficulty: str
    content_difficulty: str
    related_concept_ids: List[str] = field(default_factory=list)
    learning_objective_id: str = ""
    student_answer: Any = None
    correct_answer: str = ""
    is_correct: bool = False
    score_ratio: float = 0.0
    verdict: str = OpenAnswerVerdict.UNANSWERED.value
    explanation: str = ""
    open_evaluation: Optional[OpenAnswerEvaluation] = None
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    epistemic_status: str = "MODEL_INFERENCE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuestionAttemptOutcome":
        d = data or {}
        oe = d.get("open_evaluation")
        return cls(
            question_id=str(d.get("question_id", "")),
            question_type=str(d.get("question_type", "")),
            topic=str(d.get("topic", "")),
            chapter_id=str(d.get("chapter_id", "")),
            section_id=str(d.get("section_id", "")),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            related_concept_ids=[str(x) for x in (d.get("related_concept_ids") or [])],
            learning_objective_id=str(d.get("learning_objective_id", "")),
            student_answer=d.get("student_answer"),
            correct_answer=str(d.get("correct_answer", "")),
            is_correct=bool(d.get("is_correct", False)),
            score_ratio=float(d.get("score_ratio", 0.0)),
            verdict=str(d.get("verdict", OpenAnswerVerdict.UNANSWERED.value)),
            explanation=str(d.get("explanation", "")),
            open_evaluation=OpenAnswerEvaluation.from_dict(oe) if isinstance(oe, dict) else None,
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
        )


@dataclass
class AssessmentAttempt:
    attempt_id: str
    assessment_id: str
    document_id: str
    session_mode: str = AssessmentSessionMode.PRACTICE.value
    feedback_mode: str = AssessmentFeedbackMode.IMMEDIATE.value
    total_questions: int = 0
    answered_count: int = 0
    correct_count: int = 0
    partial_count: int = 0
    incorrect_count: int = 0
    unanswered_count: int = 0
    score_pct: float = 0.0
    passed: bool = False
    outcomes: List[QuestionAttemptOutcome] = field(default_factory=list)
    by_topic: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_difficulty: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    incorrect_question_ids: List[str] = field(default_factory=list)
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssessmentAttempt":
        d = data or {}
        return cls(
            attempt_id=str(d.get("attempt_id", "")),
            assessment_id=str(d.get("assessment_id", "")),
            document_id=str(d.get("document_id", "")),
            session_mode=str(d.get("session_mode", AssessmentSessionMode.PRACTICE.value)),
            feedback_mode=str(d.get("feedback_mode", AssessmentFeedbackMode.IMMEDIATE.value)),
            total_questions=int(d.get("total_questions", 0)),
            answered_count=int(d.get("answered_count", 0)),
            correct_count=int(d.get("correct_count", 0)),
            partial_count=int(d.get("partial_count", 0)),
            incorrect_count=int(d.get("incorrect_count", 0)),
            unanswered_count=int(d.get("unanswered_count", 0)),
            score_pct=float(d.get("score_pct", 0.0)),
            passed=bool(d.get("passed", False)),
            outcomes=[QuestionAttemptOutcome.from_dict(o) for o in (d.get("outcomes") or []) if isinstance(o, dict)],
            by_topic=dict(d.get("by_topic") or {}),
            by_difficulty=dict(d.get("by_difficulty") or {}),
            incorrect_question_ids=[str(x) for x in (d.get("incorrect_question_ids") or [])],
            submitted_at=str(d.get("submitted_at", "")),
        )


# ---------------------------------------------------------------------------
# 4. Active Recall (Recuperação Ativa Estruturada)
# ---------------------------------------------------------------------------

@dataclass
class ActiveRecallPrompt:
    prompt_id: str
    document_id: str
    prompt_text: str
    prompt_type: str = ActiveRecallPromptType.CONCEPT_EXPLANATION.value
    content_difficulty: str = ContentDifficulty.INTERMEDIATE.value
    question_difficulty: str = QuestionDifficulty.MEDIUM.value
    chapter_id: str = ""
    chapter_title: str = ""
    section_id: str = ""
    section_title: str = ""
    topic: str = ""
    learning_objective_id: str = ""
    learning_objective_text: str = ""
    concept_ids: List[str] = field(default_factory=list)
    optional_outline: List[str] = field(default_factory=list)
    key_points_expected: List[str] = field(default_factory=list)
    grounded_reference_answer: str = ""
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    epistemic_status: str = "MODEL_INFERENCE"
    generation_mode: str = "LLM_GROUNDED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveRecallPrompt":
        d = data or {}
        return cls(
            prompt_id=str(d.get("prompt_id", "")),
            document_id=str(d.get("document_id", "")),
            prompt_text=str(d.get("prompt_text", "")),
            prompt_type=str(d.get("prompt_type", ActiveRecallPromptType.CONCEPT_EXPLANATION.value)),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            chapter_id=str(d.get("chapter_id", "")),
            chapter_title=str(d.get("chapter_title", "")),
            section_id=str(d.get("section_id", "")),
            section_title=str(d.get("section_title", "")),
            topic=str(d.get("topic", "")),
            learning_objective_id=str(d.get("learning_objective_id", "")),
            learning_objective_text=str(d.get("learning_objective_text", "")),
            concept_ids=[str(x) for x in (d.get("concept_ids") or []) if str(x).strip()],
            optional_outline=[str(x) for x in (d.get("optional_outline") or []) if str(x).strip()],
            key_points_expected=[str(x) for x in (d.get("key_points_expected") or []) if str(x).strip()],
            grounded_reference_answer=str(d.get("grounded_reference_answer", "")),
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            source_pages=[int(p) for p in (d.get("source_pages") or []) if isinstance(p, (int, float)) and int(p) > 0],
            epistemic_status=normalize_epistemic_status(d.get("epistemic_status"), default="MODEL_INFERENCE"),
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
        )


@dataclass
class ActiveRecallAttempt:
    attempt_id: str
    prompt_id: str
    document_id: str
    student_response: str
    self_confidence: int = 3  # 1..5
    self_rating: str = "PARTIAL"  # MISSED | PARTIAL | RECALLED
    outline_used: bool = False
    evaluation: Optional[OpenAnswerEvaluation] = None
    score_ratio: float = 0.0
    revealed_reference: str = ""
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    identified_gap_triggered: bool = False
    scheduled_next_review_ts: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveRecallAttempt":
        d = data or {}
        ev = d.get("evaluation")
        return cls(
            attempt_id=str(d.get("attempt_id", "")),
            prompt_id=str(d.get("prompt_id", "")),
            document_id=str(d.get("document_id", "")),
            student_response=str(d.get("student_response", "")),
            self_confidence=max(1, min(5, int(d.get("self_confidence", 3)))),
            self_rating=str(d.get("self_rating", "PARTIAL")),
            outline_used=bool(d.get("outline_used", False)),
            evaluation=OpenAnswerEvaluation.from_dict(ev) if isinstance(ev, dict) else None,
            score_ratio=float(d.get("score_ratio", 0.0)),
            revealed_reference=str(d.get("revealed_reference", "")),
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            identified_gap_triggered=bool(d.get("identified_gap_triggered", False)),
            scheduled_next_review_ts=float(d.get("scheduled_next_review_ts", 0.0)),
            created_at=str(d.get("created_at", "")),
        )


@dataclass
class ActiveRecallDeck:
    document_id: str
    prompts: List[ActiveRecallPrompt] = field(default_factory=list)
    fingerprints: Optional[SourceFingerprintSnapshot] = None
    generation_mode: str = "LLM_GROUNDED"
    status: str = "COMPLETED"
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveRecallDeck":
        d = data or {}
        fp = d.get("fingerprints")
        return cls(
            document_id=str(d.get("document_id", "")),
            prompts=[ActiveRecallPrompt.from_dict(p) for p in (d.get("prompts") or []) if isinstance(p, dict)],
            fingerprints=SourceFingerprintSnapshot.from_dict(fp) if isinstance(fp, dict) else None,
            generation_mode=str(d.get("generation_mode", "LLM_GROUNDED")),
            status=str(d.get("status", "COMPLETED")),
            failed_operations=list(d.get("failed_operations") or []),
            created_at=str(d.get("created_at", "")),
        )


# ---------------------------------------------------------------------------
# 5. Spaced Repetition Engine (SM-2 Adaptativo)
# ---------------------------------------------------------------------------

@dataclass
class ReviewSchedulingState:
    item_id: str
    item_type: str  # "flashcard" | "active_recall" | "assessment_question"
    document_id: str
    chapter_id: str = ""
    section_id: str = ""
    topic: str = ""
    concept_ids: List[str] = field(default_factory=list)
    learning_objective_id: str = ""
    content_difficulty: str = ContentDifficulty.INTERMEDIATE.value
    question_difficulty: str = QuestionDifficulty.MEDIUM.value
    last_reviewed_ts: float = 0.0
    next_review_ts: float = 0.0
    reviews_count: int = 0
    successful_recalls: int = 0
    failed_recalls: int = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_confidence: int = 3
    last_performance_quality: int = 0  # SM-2 0..5
    learning_state: str = ReviewLearningState.NEW.value
    interval_days: float = 0.0
    ease_factor: float = 2.5
    scheduling_params: Dict[str, Any] = field(default_factory=dict)
    algorithm_version: str = SRS_ALGORITHM_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewSchedulingState":
        d = data or {}
        return cls(
            item_id=str(d.get("item_id", "")),
            item_type=str(d.get("item_type", "flashcard")),
            document_id=str(d.get("document_id", "")),
            chapter_id=str(d.get("chapter_id", "")),
            section_id=str(d.get("section_id", "")),
            topic=str(d.get("topic", "")),
            concept_ids=[str(x) for x in (d.get("concept_ids") or [])],
            learning_objective_id=str(d.get("learning_objective_id", "")),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            last_reviewed_ts=float(d.get("last_reviewed_ts", 0.0)),
            next_review_ts=float(d.get("next_review_ts", 0.0)),
            reviews_count=int(d.get("reviews_count", 0)),
            successful_recalls=int(d.get("successful_recalls", 0)),
            failed_recalls=int(d.get("failed_recalls", 0)),
            consecutive_successes=int(d.get("consecutive_successes", 0)),
            consecutive_failures=int(d.get("consecutive_failures", 0)),
            last_confidence=int(d.get("last_confidence", 3)),
            last_performance_quality=int(d.get("last_performance_quality", 0)),
            learning_state=str(d.get("learning_state", ReviewLearningState.NEW.value)),
            interval_days=float(d.get("interval_days", 0.0)),
            ease_factor=float(d.get("ease_factor", 2.5)),
            scheduling_params=dict(d.get("scheduling_params") or {}),
            algorithm_version=str(d.get("algorithm_version", SRS_ALGORITHM_VERSION)),
        )


@dataclass
class ReviewHistoryEntry:
    event_id: str
    item_id: str
    item_type: str
    document_id: str
    timestamp: float
    rating: str  # Again | Hard | Good | Easy | RecallMiss | RecallPass
    quality_score: int  # 0..5
    confidence: int  # 1..5
    content_difficulty: str
    question_difficulty: str
    previous_interval_days: float
    new_interval_days: float
    previous_ease_factor: float
    new_ease_factor: float
    previous_state: str
    new_state: str
    algorithm_version: str = SRS_ALGORITHM_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewHistoryEntry":
        d = data or {}
        return cls(
            event_id=str(d.get("event_id", "")),
            item_id=str(d.get("item_id", "")),
            item_type=str(d.get("item_type", "flashcard")),
            document_id=str(d.get("document_id", "")),
            timestamp=float(d.get("timestamp", 0.0)),
            rating=str(d.get("rating", "")),
            quality_score=int(d.get("quality_score", 0)),
            confidence=int(d.get("confidence", 3)),
            content_difficulty=str(d.get("content_difficulty", ContentDifficulty.INTERMEDIATE.value)),
            question_difficulty=str(d.get("question_difficulty", QuestionDifficulty.MEDIUM.value)),
            previous_interval_days=float(d.get("previous_interval_days", 0.0)),
            new_interval_days=float(d.get("new_interval_days", 0.0)),
            previous_ease_factor=float(d.get("previous_ease_factor", 2.5)),
            new_ease_factor=float(d.get("new_ease_factor", 2.5)),
            previous_state=str(d.get("previous_state", "")),
            new_state=str(d.get("new_state", "")),
            algorithm_version=str(d.get("algorithm_version", SRS_ALGORITHM_VERSION)),
        )


@dataclass
class DailyReviewQueue:
    document_id: str
    generated_at: str
    daily_new_limit: int = 10
    daily_review_limit: int = 30
    due_items: List[Dict[str, Any]] = field(default_factory=list)
    lapsed_items: List[Dict[str, Any]] = field(default_factory=list)
    low_confidence_items: List[Dict[str, Any]] = field(default_factory=list)
    new_items: List[Dict[str, Any]] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)
    total_queue_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 6. Learning Progress & Knowledge Gaps
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeGap:
    gap_id: str
    document_id: str
    gap_type: str = KnowledgeGapType.REPEATED_CONCEPT_MISS.value
    concept_id: str = ""
    concept_name: str = ""
    confused_with_concept_id: str = ""
    learning_objective_id: str = ""
    learning_objective_text: str = ""
    chapter_id: str = ""
    section_id: str = ""
    section_title: str = ""
    severity: str = "MEDIUM"  # LOW | MEDIUM | HIGH
    failure_count: int = 0
    attempts_count: int = 0
    avg_confidence: float = 0.0
    description: str = ""
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    suggested_activities: List[Dict[str, Any]] = field(default_factory=list)
    resolved: bool = False
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGap":
        d = data or {}
        return cls(
            gap_id=str(d.get("gap_id", "")),
            document_id=str(d.get("document_id", "")),
            gap_type=str(d.get("gap_type", KnowledgeGapType.REPEATED_CONCEPT_MISS.value)),
            concept_id=str(d.get("concept_id", "")),
            concept_name=str(d.get("concept_name", "")),
            confused_with_concept_id=str(d.get("confused_with_concept_id", "")),
            learning_objective_id=str(d.get("learning_objective_id", "")),
            learning_objective_text=str(d.get("learning_objective_text", "")),
            chapter_id=str(d.get("chapter_id", "")),
            section_id=str(d.get("section_id", "")),
            section_title=str(d.get("section_title", "")),
            severity=str(d.get("severity", "MEDIUM")),
            failure_count=int(d.get("failure_count", 0)),
            attempts_count=int(d.get("attempts_count", 0)),
            avg_confidence=float(d.get("avg_confidence", 0.0)),
            description=str(d.get("description", "")),
            evidence_refs=_deserialize_refs(d.get("evidence_refs")),
            suggested_activities=[dict(x) for x in (d.get("suggested_activities") or []) if isinstance(x, dict)],
            resolved=bool(d.get("resolved", False)),
            detected_at=str(d.get("detected_at", "")),
        )


@dataclass
class LearningProgressSnapshot:
    document_id: str
    questions_answered: int = 0
    correct_answers: int = 0
    partial_answers: int = 0
    incorrect_answers: int = 0
    flashcard_reviews_total: int = 0
    active_recall_attempts_total: int = 0
    overall_accuracy_pct: Optional[float] = None
    avg_recall_confidence: Optional[float] = None
    mastery_level: str = MasteryLevel.INSUFFICIENT_EVIDENCE.value
    by_chapter: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_section: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_concept: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_objective: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_topic: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    repeatedly_missed_concepts: List[str] = field(default_factory=list)
    consistently_recalled_concepts: List[str] = field(default_factory=list)
    insufficient_evidence_objectives: List[str] = field(default_factory=list)
    knowledge_gaps: List[KnowledgeGap] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningProgressSnapshot":
        d = data or {}
        return cls(
            document_id=str(d.get("document_id", "")),
            questions_answered=int(d.get("questions_answered", 0)),
            correct_answers=int(d.get("correct_answers", 0)),
            partial_answers=int(d.get("partial_answers", 0)),
            incorrect_answers=int(d.get("incorrect_answers", 0)),
            flashcard_reviews_total=int(d.get("flashcard_reviews_total", 0)),
            active_recall_attempts_total=int(d.get("active_recall_attempts_total", 0)),
            overall_accuracy_pct=float(d["overall_accuracy_pct"]) if d.get("overall_accuracy_pct") is not None else None,
            avg_recall_confidence=float(d["avg_recall_confidence"]) if d.get("avg_recall_confidence") is not None else None,
            mastery_level=str(d.get("mastery_level", MasteryLevel.INSUFFICIENT_EVIDENCE.value)),
            by_chapter=dict(d.get("by_chapter") or {}),
            by_section=dict(d.get("by_section") or {}),
            by_concept=dict(d.get("by_concept") or {}),
            by_objective=dict(d.get("by_objective") or {}),
            by_topic=dict(d.get("by_topic") or {}),
            repeatedly_missed_concepts=[str(x) for x in (d.get("repeatedly_missed_concepts") or [])],
            consistently_recalled_concepts=[str(x) for x in (d.get("consistently_recalled_concepts") or [])],
            insufficient_evidence_objectives=[str(x) for x in (d.get("insufficient_evidence_objectives") or [])],
            knowledge_gaps=[KnowledgeGap.from_dict(g) for g in (d.get("knowledge_gaps") or []) if isinstance(g, dict)],
            updated_at=str(d.get("updated_at", "")),
        )


# ---------------------------------------------------------------------------
# 7. Gestor de Sessões de Estudo & QA
# ---------------------------------------------------------------------------

@dataclass
class StudySessionState:
    session_id: str
    document_id: str
    mode: str = StudySessionMode.FLASHCARD_REVIEW.value
    status: str = StudySessionStatus.IN_PROGRESS.value
    title: str = ""
    item_ids: List[str] = field(default_factory=list)
    current_index: int = 0
    completed_item_ids: List[str] = field(default_factory=list)
    partial_responses: Dict[str, Any] = field(default_factory=dict)
    item_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    summary_stats: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now().isoformat())
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudySessionState":
        d = data or {}
        return cls(
            session_id=str(d.get("session_id", "")),
            document_id=str(d.get("document_id", "")),
            mode=str(d.get("mode", StudySessionMode.FLASHCARD_REVIEW.value)),
            status=str(d.get("status", StudySessionStatus.IN_PROGRESS.value)),
            title=str(d.get("title", "")),
            item_ids=[str(x) for x in (d.get("item_ids") or [])],
            current_index=int(d.get("current_index", 0)),
            completed_item_ids=[str(x) for x in (d.get("completed_item_ids") or [])],
            partial_responses=dict(d.get("partial_responses") or {}),
            item_outcomes=[dict(x) for x in (d.get("item_outcomes") or []) if isinstance(x, dict)],
            config=dict(d.get("config") or {}),
            summary_stats=dict(d.get("summary_stats") or {}),
            started_at=str(d.get("started_at", "")),
            last_activity_at=str(d.get("last_activity_at", "")),
            paused_at=d.get("paused_at"),
            completed_at=d.get("completed_at"),
        )


@dataclass
class StudyModeQAFinding:
    code: str
    severity: str  # BLOCKING | WARNING
    message: str
    item_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StudyModeQAReport:
    is_valid: bool = True
    items_checked: int = 0
    items_accepted: int = 0
    items_rejected: int = 0
    duplicates_removed: int = 0
    findings: List[StudyModeQAFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StudyModeReadiness:
    document_id: str
    status: str  # StudyModeReadinessStatus
    is_ready: bool
    has_ast: bool = False
    has_dossier: bool = False
    has_plan: bool = False
    has_study_document: bool = False
    is_stale: bool = False
    stale_reasons: List[str] = field(default_factory=list)
    missing_artifacts: List[str] = field(default_factory=list)
    actionable_message: str = ""
    current_fingerprints: Optional[SourceFingerprintSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

