"""
JARVIS OS — Study Engine Phase 7: Integration Contracts
Contratos tipados para pedidos, respostas, contexto conversacional, navegação
e operações assíncronas entre a orquestração JARVIS e o Study Engine (Fases 2–6).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


UNSCOPED_CHAT_SESSION_IDS = frozenset({
    "global",
    "default",
    "default_study_chat",
    "none",
    "null",
})


def normalize_chat_session_id(chat_session_id: Any) -> Optional[str]:
    """Normaliza um ID canónico de conversa sem fabricar identificadores nem mapear para 'global'."""
    if chat_session_id is None or isinstance(chat_session_id, bool):
        return None
    raw = str(chat_session_id).strip()
    if not raw or raw.lower() in UNSCOPED_CHAT_SESSION_IDS:
        return None
    return raw


class StudyCapabilityType(str, Enum):
    LIST_DOCUMENTS = "LIST_DOCUMENTS"
    GET_DOCUMENT_STATUS = "GET_DOCUMENT_STATUS"
    INGEST_DOCUMENT = "INGEST_DOCUMENT"
    OPEN_STUDY_WORKSPACE = "OPEN_STUDY_WORKSPACE"
    ANALYSE_DOCUMENT = "ANALYSE_DOCUMENT"
    PREPARE_STUDY_MATERIAL = "PREPARE_STUDY_MATERIAL"
    GENERATE_STUDY_DOCUMENT = "GENERATE_STUDY_DOCUMENT"
    EXPLAIN_CONCEPT_OR_CHAPTER = "EXPLAIN_CONCEPT_OR_CHAPTER"
    COMPARE_CONCEPTS = "COMPARE_CONCEPTS"
    GENERATE_FLASHCARDS = "GENERATE_FLASHCARDS"
    GENERATE_CORNELL_NOTES = "GENERATE_CORNELL_NOTES"
    CREATE_ASSESSMENT = "CREATE_ASSESSMENT"
    START_ACTIVE_RECALL = "START_ACTIVE_RECALL"
    SUBMIT_ACTIVE_RECALL = "SUBMIT_ACTIVE_RECALL"
    START_DAILY_REVIEW = "START_DAILY_REVIEW"
    GET_LEARNING_PROGRESS = "GET_LEARNING_PROGRESS"
    GET_KNOWLEDGE_GAPS = "GET_KNOWLEDGE_GAPS"
    MANAGE_STUDY_SESSION = "MANAGE_STUDY_SESSION"
    CANCEL_STUDY_OPERATION = "CANCEL_STUDY_OPERATION"


ASYNC_HEAVY_CAPABILITIES = frozenset({
    StudyCapabilityType.ANALYSE_DOCUMENT,
    StudyCapabilityType.PREPARE_STUDY_MATERIAL,
    StudyCapabilityType.GENERATE_STUDY_DOCUMENT,
    StudyCapabilityType.GENERATE_FLASHCARDS,
    StudyCapabilityType.GENERATE_CORNELL_NOTES,
    StudyCapabilityType.CREATE_ASSESSMENT,
})

VALID_DIFFICULTIES = frozenset({"EASY", "MEDIUM", "HARD"})
VALID_STUDY_TABS = frozenset({
    "library",
    "reader",
    "summary",
    "notes",
    "flashcards",
    "active_recall",
    "quiz",
    "adaptive",
    "knowledge",
})
VALID_SESSION_ACTIONS = frozenset({"start", "resume", "pause", "complete", "list"})


class StudyOperationState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


@dataclass
class StudyNavigationTarget:
    target: str = "study"
    document_id: Optional[str] = None
    tab: str = "library"
    chapter_id: Optional[str] = None
    section_id: Optional[str] = None
    assessment_id: Optional[str] = None
    session_id: Optional[str] = None
    topic: Optional[str] = None
    label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "target": self.target,
            "tab": self.tab if self.tab in VALID_STUDY_TABS else "library",
        }
        if self.document_id:
            payload["document_id"] = self.document_id
        if self.chapter_id:
            payload["chapter_id"] = self.chapter_id
        if self.section_id:
            payload["section_id"] = self.section_id
        if self.assessment_id:
            payload["assessment_id"] = self.assessment_id
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.topic:
            payload["topic"] = self.topic
        if self.label:
            payload["label"] = self.label
        return payload


@dataclass
class StudyConversationContext:
    chat_session_id: str
    active_document_id: Optional[str] = None
    active_document_title: Optional[str] = None
    active_collection_id: Optional[str] = None
    active_chapter_id: Optional[str] = None
    active_section_id: Optional[str] = None
    active_activity: Optional[str] = None
    active_study_session_id: Optional[str] = None
    last_assessment_id: Optional[str] = None
    last_active_recall_prompt_id: Optional[str] = None
    last_operation_id: Optional[str] = None
    last_operation_type: Optional[str] = None
    last_topic: Optional[str] = None
    last_difficulty: Optional[str] = None
    last_question_count: Optional[int] = None
    recent_concepts: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyConversationContext":
        return cls(
            chat_session_id=normalize_chat_session_id(data.get("chat_session_id")) or "",
            active_document_id=data.get("active_document_id"),
            active_document_title=data.get("active_document_title"),
            active_collection_id=data.get("active_collection_id"),
            active_chapter_id=data.get("active_chapter_id"),
            active_section_id=data.get("active_section_id"),
            active_activity=data.get("active_activity"),
            active_study_session_id=data.get("active_study_session_id"),
            last_assessment_id=data.get("last_assessment_id"),
            last_active_recall_prompt_id=data.get("last_active_recall_prompt_id"),
            last_operation_id=data.get("last_operation_id"),
            last_operation_type=data.get("last_operation_type"),
            last_topic=data.get("last_topic"),
            last_difficulty=data.get("last_difficulty"),
            last_question_count=data.get("last_question_count"),
            recent_concepts=list(data.get("recent_concepts") or [])[:12],
            updated_at=str(data.get("updated_at") or _utc_now_iso()),
        )


@dataclass
class StudyCapabilityRequest:
    capability: StudyCapabilityType
    operation_id: str = field(default_factory=lambda: f"op_{uuid.uuid4().hex[:12]}")
    correlation_id: str = ""
    chat_session_id: Optional[str] = None
    document_id: Optional[str] = None
    document_query: Optional[str] = None
    secondary_document_ids: List[str] = field(default_factory=list)
    collection_id: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_ref: Optional[str] = None
    section_id: Optional[str] = None
    section_ref: Optional[str] = None
    topic: Optional[str] = None
    question: Optional[str] = None
    concept_a: Optional[str] = None
    concept_b: Optional[str] = None
    study_session_id: Optional[str] = None
    session_action: Optional[str] = None
    difficulty: Optional[str] = None
    question_count: Optional[int] = None
    card_count: Optional[int] = None
    answer_text: Optional[str] = None
    prompt_id: Optional[str] = None
    file_path: Optional[str] = None
    video_url: Optional[str] = None
    target_tab: Optional[str] = None
    target_operation_id: Optional[str] = None
    force_recompute: bool = False
    reveal_answer: bool = False
    confirm_destructive: bool = False
    raw_prompt: str = ""

    def validate_bounds(self) -> None:
        if self.difficulty is not None:
            diff_up = str(self.difficulty).strip().upper()
            if diff_up not in VALID_DIFFICULTIES:
                raise ValueError(
                    f"Dificuldade inválida '{self.difficulty}'. Valores aceites: {', '.join(sorted(VALID_DIFFICULTIES))}."
                )
            self.difficulty = diff_up

        if self.question_count is not None:
            if isinstance(self.question_count, bool) or not isinstance(self.question_count, int):
                raise ValueError("question_count deve ser um inteiro.")
            if self.question_count < 1 or self.question_count > 30:
                raise ValueError("question_count deve estar entre 1 e 30.")

        if self.card_count is not None:
            if isinstance(self.card_count, bool) or not isinstance(self.card_count, int):
                raise ValueError("card_count deve ser um inteiro.")
            if self.card_count < 1 or self.card_count > 50:
                raise ValueError("card_count deve estar entre 1 e 50.")

        if self.target_tab is not None:
            tab = str(self.target_tab).strip().lower()
            if tab not in VALID_STUDY_TABS:
                raise ValueError(f"Separador de estudo inválido '{self.target_tab}'.")
            self.target_tab = tab

        if self.session_action is not None:
            act = str(self.session_action).strip().lower()
            if act not in VALID_SESSION_ACTIONS:
                raise ValueError(f"Ação de sessão inválida '{self.session_action}'.")
            self.session_action = act


@dataclass
class StudyCapabilityResult:
    operation_id: str
    capability: str
    status: str  # COMPLETED | RUNNING | NEEDS_CLARIFICATION | NEEDS_CONFIRMATION | FAILED | CANCELLED
    summary_markdown: str
    document_id: Optional[str] = None
    document_title: Optional[str] = None
    chapter_id: Optional[str] = None
    section_id: Optional[str] = None
    study_session_id: Optional[str] = None
    result_ref: Dict[str, Any] = field(default_factory=dict)
    epistemic_breakdown: Optional[Dict[str, Any]] = None
    citations: List[str] = field(default_factory=list)
    navigation: Optional[StudyNavigationTarget] = None
    navigation_actions: List[StudyNavigationTarget] = field(default_factory=list)
    auto_navigate: bool = False
    progress: Optional[Dict[str, Any]] = None
    clarification_options: List[Dict[str, Any]] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    question_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "operation_id": self.operation_id,
            "capability": self.capability,
            "status": self.status,
            "summary_markdown": self.summary_markdown,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "chapter_id": self.chapter_id,
            "section_id": self.section_id,
            "study_session_id": self.study_session_id,
            "result_ref": dict(self.result_ref or {}),
            "citations": list(self.citations or []),
            "auto_navigate": self.auto_navigate,
        }
        if self.epistemic_breakdown:
            payload["epistemic_breakdown"] = dict(self.epistemic_breakdown)
        if self.navigation:
            payload["navigation"] = self.navigation.to_dict()
        if self.navigation_actions:
            payload["navigation_actions"] = [a.to_dict() for a in self.navigation_actions]
        if self.progress:
            payload["progress"] = dict(self.progress)
        if self.clarification_options:
            payload["clarification_options"] = list(self.clarification_options)
        if self.error_code:
            payload["error_code"] = self.error_code
        if self.error_message:
            payload["error_message"] = self.error_message
        return payload

    def to_study_card(self) -> Dict[str, Any]:
        """Serialização compacta para apresentação conversacional em ChatPanel."""
        actions = [a.to_dict() for a in self.navigation_actions]
        if self.navigation and not any(
            a.get("tab") == self.navigation.tab and a.get("document_id") == self.navigation.document_id
            for a in actions
        ):
            actions.insert(0, self.navigation.to_dict())
        card: Dict[str, Any] = {
            "operation_id": self.operation_id,
            "capability": self.capability,
            "status": self.status,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "study_session_id": self.study_session_id,
            "summary": self.summary_markdown,
            "result_ref": dict(self.result_ref or {}),
            "citations": list(self.citations or [])[:8],
            "actions": actions[:4],
        }
        if self.epistemic_breakdown:
            card["epistemic_breakdown"] = dict(self.epistemic_breakdown)
        if self.progress:
            card["progress"] = dict(self.progress)
        if self.error_code:
            card["error_code"] = self.error_code
        if self.error_message:
            card["error_message"] = self.error_message
        return card


@dataclass
class StudyOperationRecord:
    operation_id: str
    correlation_id: str
    chat_session_id: str
    capability: str
    document_id: Optional[str]
    status: str = StudyOperationState.QUEUED.value
    stage: str = "QUEUED"
    progress_percent: Optional[float] = None
    message: str = ""
    dedup_key: str = ""
    result_summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StudyOperationRecord":
        return cls(
            operation_id=str(data.get("operation_id") or ""),
            correlation_id=str(data.get("correlation_id") or ""),
            chat_session_id=normalize_chat_session_id(data.get("chat_session_id")) or "",
            capability=str(data.get("capability") or ""),
            document_id=data.get("document_id"),
            status=str(data.get("status") or StudyOperationState.INTERRUPTED.value),
            stage=str(data.get("stage") or "INTERRUPTED"),
            progress_percent=data.get("progress_percent"),
            message=str(data.get("message") or ""),
            dedup_key=str(data.get("dedup_key") or ""),
            result_summary=dict(data.get("result_summary") or {}),
            error=data.get("error"),
            started_at=str(data.get("started_at") or _utc_now_iso()),
            updated_at=str(data.get("updated_at") or _utc_now_iso()),
        )
