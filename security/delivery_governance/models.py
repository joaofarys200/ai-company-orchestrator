"""
Modelos Formais de Aceitação de Produto e Governança de Entrega do JARVIS.
Formaliza:
- Separação estrita: SYNTAX_VALID != BUILD_VALID != RUNTIME_VALID != FUNCTIONALLY_VALID != PRODUCT_ACCEPTED.
- Rastreabilidade de requisitos (RequirementItem).
- Auditoria de preservação e deteção destrutiva (ProductIntegrityDiff).
- Relatório holístico de aceitação (ProductAcceptanceReport).
- Ciclo de estados formal de entrega autónoma.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AcceptanceLevel(str, Enum):
    """Níveis explícitos de validação sem inferência automática transitiva."""
    SYNTAX_VALID = "SYNTAX_VALID"
    TYPE_VALID = "TYPE_VALID"
    BUILD_VALID = "BUILD_VALID"
    RUNTIME_VALID = "RUNTIME_VALID"
    FUNCTIONALLY_VALID = "FUNCTIONALLY_VALID"
    VISUALLY_VALID = "VISUALLY_VALID"
    PRODUCT_ACCEPTED = "PRODUCT_ACCEPTED"
    USER_ACCEPTED = "USER_ACCEPTED"


class DeliveryGateStatus(str, Enum):
    """Máquina de estados de governança de entrega autónoma do JARVIS."""
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    IMPLEMENTING = "IMPLEMENTING"
    PREFLIGHT = "PREFLIGHT"
    TECHNICALLY_VALIDATED = "TECHNICALLY_VALIDATED"
    FUNCTIONALLY_VALIDATED = "FUNCTIONALLY_VALIDATED"
    VISUALLY_VALIDATED = "VISUALLY_VALIDATED"
    ACCEPTANCE_PENDING = "ACCEPTANCE_PENDING"
    PRODUCT_ACCEPTED = "PRODUCT_ACCEPTED"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RequirementStatus(str, Enum):
    """Estado de satisfação de um critério de aceitação de produto."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class QualityScoreStatus(str, Enum):
    """Classificação qualitativa do produto para entrega autónoma."""
    READY = "READY"
    NOT_READY = "NOT_READY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ArtifactCategory(str, Enum):
    """Categorias funcionais de capacidades suportadas."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    STORAGE = "storage"
    AUTH = "auth"
    CRUD = "crud"
    DASHBOARD = "dashboard"
    SEARCH = "search"
    PREVIEW = "preview"


class ArtifactEvidenceStatus(str, Enum):
    """Estado de evidência do artefacto no projeto."""
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"
    PRESENT = "PRESENT"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


@dataclass
class ArtifactExpectation:
    """
    Especificação formal de um artefacto baseado em capacidade e responsabilidade,
    não em convenções arbitrárias de nomes fixos.
    """
    artifact_id: str
    category: str
    responsibility: str
    path: Optional[str] = None
    path_pattern: Optional[str] = None
    required: bool = True
    architecture_source: str = "INFERRED_BY_PROJECT"  # INFERRED_BY_PROJECT ou INFERRED_BY_DEFAULT_ARCHITECTURE
    evidence_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactEvidence:
    """Evidência de verificação de um artefacto no contexto do projeto."""
    artifact_id: str
    expected_path: str
    responsibility: str = ""
    category: str = ""
    exists: bool = False
    non_empty: bool = False
    validated: bool = False
    evidence_ids: List[str] = field(default_factory=list)
    status: str = ArtifactEvidenceStatus.UNKNOWN.value
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectArchitecture:
    """Modelo explícito da arquitetura técnica do projeto."""
    architecture_id: str
    stack: str
    framework: str = "none"
    bundler: str = "none"
    runtime: str = "unknown"
    package_manager: str = "npm"
    frontend_entrypoints: List[str] = field(default_factory=list)
    backend_entrypoints: List[str] = field(default_factory=list)
    style_system: str = "none"
    source_root: str = "."
    app_root: str = "."
    conventions: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    is_existing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureDecision:
    """Registo formal da decisão de arquitetura para o projeto."""
    selected_stack: str = ""
    rationale: str = ""
    inferred_artifacts: List[str] = field(default_factory=list)
    expected_capabilities: List[str] = field(default_factory=list)
    is_new_project: bool = False
    framework: str = ""
    bundler: str = ""
    runtime: str = "unknown"
    entrypoints: Dict[str, List[str]] = field(default_factory=dict)
    conventions: Dict[str, Any] = field(default_factory=dict)
    detected: bool = False
    architecture: str = ""
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    source: str = "default_architecture"

    def __post_init__(self):
        if not self.selected_stack and self.architecture:
            self.selected_stack = self.architecture
        elif not self.architecture and self.selected_stack:
            self.architecture = self.selected_stack

        if not self.is_new_project or self.detected or self.source == "existing_project":
            self.source = "existing_project"
            self.detected = True
            self.is_new_project = False
        else:
            self.source = "default_architecture"
            self.detected = False
            self.is_new_project = True

        if not self.rationale:
            self.rationale = f"Decisão arquitetural: {self.architecture} ({self.source}, confiança: {self.confidence:.2f})"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RequirementItem:
    """Rastreabilidade atómica de requisito e respetiva evidência."""
    requirement_id: str
    description: str
    category: str = "functional"
    source: str = "user_prompt"
    acceptance_test: str = ""
    acceptance_tests: List[str] = field(default_factory=list)
    required_artifacts: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    status: str = RequirementStatus.UNKNOWN.value
    blocking: bool = True
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductIntegrityDiff:
    """Análise de preservação de capacidades existentes e deteção de alterações destrutivas."""
    project_id: str
    removed_scripts: List[str] = field(default_factory=list)
    removed_stylesheets: List[str] = field(default_factory=list)
    missing_html_roots: List[str] = field(default_factory=list)
    removed_endpoints: List[str] = field(default_factory=list)
    removed_event_listeners: List[str] = field(default_factory=list)
    missing_imports: List[str] = field(default_factory=list)
    broken_routes: List[str] = field(default_factory=list)
    deleted_existing_features: List[str] = field(default_factory=list)
    destructive_file_replacements: List[Dict[str, Any]] = field(default_factory=list)
    has_critical_regression: bool = False
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductAcceptanceReport:
    """Relatório canónico de aceitação holística do produto antes de entrega autónoma."""
    mission_id: str = ""
    project_id: str = ""
    change_id: str = ""
    requirements: List[RequirementItem] = field(default_factory=list)
    artifact_expectations: List[ArtifactExpectation] = field(default_factory=list)
    artifact_evidence: List[ArtifactEvidence] = field(default_factory=list)
    architecture_decision: Optional[ArchitectureDecision] = None
    capabilities_detected: List[str] = field(default_factory=list)
    preserved_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    functional_checks: List[Dict[str, Any]] = field(default_factory=list)
    runtime_checks: List[Dict[str, Any]] = field(default_factory=list)
    visual_checks: List[Dict[str, Any]] = field(default_factory=list)
    regression_checks: List[Dict[str, Any]] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    result: str = RequirementStatus.INSUFFICIENT_EVIDENCE.value
    quality_score: str = QualityScoreStatus.INSUFFICIENT_EVIDENCE.value
    gate_status: str = DeliveryGateStatus.CREATED.value
    user_summary: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
