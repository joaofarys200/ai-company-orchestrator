"""
JARVIS OS — Study Engine Phase 6: Public Facade (StudyModesEngine)
Exporta a API canónica dos modos de estudo, repetição espaçada, Active Recall,
progresso e sessões persistentes para consumo pelo StudyService e WebSocketHandler.
"""

from __future__ import annotations

from services.study_modes.active_recall_engine import ActiveRecallEngine
from services.study_modes.assessment_engine import AssessmentEngine
from services.study_modes.contracts import (
    ActiveRecallAttempt,
    ActiveRecallDeck,
    ActiveRecallPrompt,
    ActiveRecallPromptType,
    AssessmentAttempt,
    AssessmentConfig,
    AssessmentFeedbackMode,
    AssessmentQuestion,
    AssessmentSessionMode,
    AdaptiveFlashcard,
    ContentDifficulty,
    CornellCueItem,
    CornellNoteEntry,
    CornellPersonalNote,
    CornellStudyDocument,
    DailyReviewQueue,
    FlashcardReviewStatus,
    FlashcardType,
    KnowledgeGap,
    KnowledgeGapType,
    LearningProgressSnapshot,
    MasteryLevel,
    OpenAnswerEvaluation,
    OpenAnswerVerdict,
    PROMPT_VERSIONS_PHASE6,
    QuestionAttemptOutcome,
    QuestionDifficulty,
    QuestionType,
    ReviewHistoryEntry,
    ReviewLearningState,
    ReviewSchedulingState,
    SRS_ALGORITHM_VERSION,
    ScoringCriterion,
    SourceFingerprintSnapshot,
    SourceLocation,
    StudyAssessment,
    StudyDeck,
    StudyModeQAFinding,
    StudyModeQAReport,
    StudyModeReadiness,
    StudyModeReadinessStatus,
    StudySessionItemRef,
    StudySessionMode,
    StudySessionState,
    StudySessionStatus,
)
from services.study_modes.cornell_notes_engine import CornellNotesEngine
from services.study_modes.flashcards_engine import FlashcardEngine
from services.study_modes.grounding import (
    Phase6GroundingHelper,
    compute_source_fingerprints,
    fingerprints_match,
)
from services.study_modes.learning_progress_engine import LearningProgressEngine
from services.study_modes.orchestrator import StudyModeOrchestrator
from services.study_modes.persistence import StudyModePersistence
from services.study_modes.qa_engine import StudyModeQA
from services.study_modes.session_manager import StudySessionManager
from services.study_modes.spaced_repetition_engine import SpacedRepetitionEngine

StudyModesEngine = StudyModeOrchestrator

__all__ = [
    "StudyModesEngine",
    "StudyModeOrchestrator",
    "StudyModePersistence",
    "Phase6GroundingHelper",
    "FlashcardEngine",
    "CornellNotesEngine",
    "AssessmentEngine",
    "ActiveRecallEngine",
    "SpacedRepetitionEngine",
    "LearningProgressEngine",
    "StudySessionManager",
    "StudyModeQA",
    "compute_source_fingerprints",
    "fingerprints_match",
    "StudySessionItemRef",
    "StudyDeck",
    "AdaptiveFlashcard",
    "FlashcardType",
    "FlashcardReviewStatus",
    "CornellStudyDocument",
    "CornellNoteEntry",
    "CornellCueItem",
    "CornellPersonalNote",
    "StudyAssessment",
    "AssessmentConfig",
    "AssessmentQuestion",
    "QuestionType",
    "AssessmentFeedbackMode",
    "AssessmentSessionMode",
    "AssessmentAttempt",
    "QuestionAttemptOutcome",
    "OpenAnswerEvaluation",
    "OpenAnswerVerdict",
    "ScoringCriterion",
    "ActiveRecallDeck",
    "ActiveRecallPrompt",
    "ActiveRecallPromptType",
    "ActiveRecallAttempt",
    "ReviewSchedulingState",
    "ReviewHistoryEntry",
    "ReviewLearningState",
    "DailyReviewQueue",
    "LearningProgressSnapshot",
    "KnowledgeGap",
    "KnowledgeGapType",
    "MasteryLevel",
    "StudySessionState",
    "StudySessionMode",
    "StudySessionStatus",
    "StudyModeReadiness",
    "StudyModeReadinessStatus",
    "StudyModeQAReport",
    "StudyModeQAFinding",
    "SourceFingerprintSnapshot",
    "SourceLocation",
    "ContentDifficulty",
    "QuestionDifficulty",
    "SRS_ALGORITHM_VERSION",
    "PROMPT_VERSIONS_PHASE6",
]

