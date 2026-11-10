"""
JARVIS OS — Study Engine Phase 5: Document Generation Engine Facade
Fachada pública do motor de geração documental e composição académica.
Expõe a interface unificada para consumo pelo StudyService, testes e subsistemas integrados.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ContextBudgetManager,
)
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_document_generation.contracts import (
    DevelopedChapterContent,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    DocumentGenerationState,
    DocumentGenerationTelemetry,
    GeneratedVisualAsset,
    StudyDocumentGenerationResult,
    StudyDocumentIR,
    StudyDocumentQAReport,
    StudyDocumentVersionRecord,
    compute_plan_fingerprint,
)
from services.study_document_generation.design_system import (
    ACADEMIC_EDITORIAL_CLASSIC,
    TECHNICAL_SCIENTIFIC_MODERN,
    AcademicDesignSystem,
    DesignStyleProfile,
)
from services.study_document_generation.orchestrator import DocumentGenerationOrchestrator


class DocumentGenerationEngine:
    """
    Fachada pública do Motor de Geração Documental (Fase 5).
    Coordena a transformação do EditorialStudyPlan em documentos finais (PDF e DOCX),
    através da geração de conteúdo desenvolvido, síntese visual fundamentada,
    compilação da representação intermediária e layout determinístico.
    """

    def __init__(
        self,
        storage_dir: str | Path,
        *,
        llm_caller: Optional[Callable] = None,
        budget_manager: Optional[ContextBudgetManager] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.llm_caller = llm_caller
        self.budget_manager = budget_manager or ContextBudgetManager()
        self.orchestrator = DocumentGenerationOrchestrator(
            storage_dir=self.storage_dir,
            llm_caller=self.llm_caller,
            budget_manager=self.budget_manager,
        )

    def generate_study_document(
        self,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST] = None,
        *,
        design_profile_id: str = "ACADEMIC_EDITORIAL_CLASSIC",
        export_docx: bool = True,
        force_recompute: bool = False,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> StudyDocumentGenerationResult:
        """
        Gera o documento de estudo completo (PDF e DOCX) a partir do plano editorial,
        dossier de raciocínio e AST opcional.
        """
        return self.orchestrator.generate_document(
            plan=plan,
            dossier=dossier,
            ast=ast,
            design_profile_id=design_profile_id,
            export_docx=export_docx,
            force_recompute=force_recompute,
            on_progress=on_progress,
            cancellation_check=cancellation_check,
        )

    def get_document_generation_status(self, document_id: str) -> Dict[str, Any]:
        """Consulta o estado da geração documental, ficheiros e versão ativa."""
        return self.orchestrator.get_document_generation_status(document_id)

    def is_document_up_to_date(self, document_id: str, plan: EditorialStudyPlan) -> Tuple[bool, str]:
        """Verifica se o documento gerado em disco está sincronizado com o plano editorial atual."""
        status = self.get_document_generation_status(document_id)
        if not status.get("has_pdf"):
            return False, "DOCUMENT_NOT_FOUND"

        doc_dir = self.storage_dir / "documents" / document_id
        meta_res_path = doc_dir / "document_generation_result.json"
        if not meta_res_path.exists():
            return False, "METADATA_NOT_FOUND"

        try:
            raw = json.loads(meta_res_path.read_text(encoding="utf-8"))
            res = StudyDocumentGenerationResult.from_dict(raw)
            current_fp = compute_plan_fingerprint(plan)
            if res.source_plan_fingerprint != current_fp:
                return False, "PLAN_FINGERPRINT_MISMATCH"
            return True, "UP_TO_DATE"
        except Exception as e:
            return False, f"VERIFICATION_ERROR: {e}"


__all__ = [
    "DocumentGenerationEngine",
    "DocumentGenerationOrchestrator",
    "StudyDocumentGenerationResult",
    "StudyDocumentQAReport",
    "StudyDocumentIR",
    "DevelopedStudyDocumentContent",
    "DevelopedChapterContent",
    "DevelopedSectionContent",
    "GeneratedVisualAsset",
    "DocumentGenerationState",
    "DocumentGenerationTelemetry",
    "StudyDocumentVersionRecord",
    "AcademicDesignSystem",
    "DesignStyleProfile",
    "ACADEMIC_EDITORIAL_CLASSIC",
    "TECHNICAL_SCIENTIFIC_MODERN",
    "compute_plan_fingerprint",
]

