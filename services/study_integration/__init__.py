"""
JARVIS OS — Study Engine Phase 7: Full JARVIS Integration Package
"""

from services.study_integration.context_manager import StudyContextManager
from services.study_integration.contracts import (
    StudyCapabilityRequest,
    StudyCapabilityResult,
    StudyCapabilityType,
    StudyConversationContext,
    StudyNavigationTarget,
    StudyOperationRecord,
    StudyOperationState,
)
from services.study_integration.coordinator import StudyOrchestrationCoordinator
from services.study_integration.explainer import OllamaUnavailableError, StudyAcademicExplainer
from services.study_integration.operation_manager import StudyOperationManager
from services.study_integration.router import StudyCapabilityRouter


def get_study_coordinator(study_service, *, model_service=None):
    """Obtém ou inicializa de forma partilhada o StudyOrchestrationCoordinator ligado ao StudyService."""
    if study_service is None:
        return None
    existing = getattr(study_service, "_study_coordinator", None)
    if existing is None:
        existing = StudyOrchestrationCoordinator(study_service, model_service=model_service)
        setattr(study_service, "_study_coordinator", existing)
    elif model_service is not None and existing.model_service is None:
        existing.model_service = model_service
        existing.router.explainer.model_service = model_service
    return existing


__all__ = [
    "OllamaUnavailableError",
    "StudyAcademicExplainer",
    "StudyCapabilityRequest",
    "StudyCapabilityResult",
    "StudyCapabilityRouter",
    "StudyCapabilityType",
    "StudyContextManager",
    "StudyConversationContext",
    "StudyNavigationTarget",
    "StudyOperationManager",
    "StudyOperationRecord",
    "StudyOperationState",
    "StudyOrchestrationCoordinator",
    "get_study_coordinator",
]
