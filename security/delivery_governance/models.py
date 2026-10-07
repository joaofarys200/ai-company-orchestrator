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


@dataclass
class RequirementItem:
    """Rastreabilidade atómica de requisito e respetiva evidência."""
    requirement_id: str
    description: str
    source: str = "user_prompt"
    acceptance_test: str = ""
    status: str = RequirementStatus.UNKNOWN.value
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
