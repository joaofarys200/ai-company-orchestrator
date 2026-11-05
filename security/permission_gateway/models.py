"""
JARVIS OS — Human-in-the-Loop (HITL) Permission Gateway Models
Defines immutable contracts, risk levels, lifecycle states, and audit models.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PermissionRiskLevel(str, Enum):
    """Níveis rigorosos de risco da política de segurança."""
    READ_ONLY = "READ_ONLY"
    LOW_RISK_MUTATION = "LOW_RISK_MUTATION"
    HIGH_RISK_MUTATION = "HIGH_RISK_MUTATION"
    CRITICAL_MUTATION = "CRITICAL_MUTATION"


class PermissionRequestStatus(str, Enum):
    """Ciclo de vida explícito de uma requisição de permissão humana."""
    REQUESTED = "REQUESTED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CAPABILITY_CHECKING = "CAPABILITY_CHECKING"
    AVAILABLE = "AVAILABLE"
    INSTALLATION_REQUIRED = "INSTALLATION_REQUIRED"
    ADMIN_PRIVILEGE_REQUIRED = "ADMIN_PRIVILEGE_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    BLOCKED_REQUIRED_CAPABILITY = "BLOCKED_REQUIRED_CAPABILITY"
    WAITING_FOR_CAPABILITY = "WAITING_FOR_CAPABILITY"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    EXECUTION_READY = "EXECUTION_READY"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class CapabilityStatus(str, Enum):
    """Resultado da verificação técnica de capacidade no sistema anfitrião."""
    AVAILABLE = "AVAILABLE"
    ADMIN_PRIVILEGE_REQUIRED = "ADMIN_PRIVILEGE_REQUIRED"
    INSTALLATION_REQUIRED = "INSTALLATION_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"


class DependencyClassification(str, Enum):
    """Classificação rigorosa de necessidade de dependência externa."""
    REQUIRED = "REQUIRED"        # A solução não cumpre completamente o objetivo sem esta dependência
    OPTIONAL = "OPTIONAL"        # A solução continua a cumprir o objetivo sem esta ferramenta
    ALTERNATIVE = "ALTERNATIVE"  # Existe outra implementação equivalente que cumpre os mesmos critérios


class ApprovalSemantics(str, Enum):
    """Semântica explícita de autorização humana."""
    AUTHORIZE_USE = "AUTHORIZE_USE"
    AUTHORIZE_INSTALLATION = "AUTHORIZE_INSTALLATION"
    USE_LIMITED_FALLBACK = "USE_LIMITED_FALLBACK"
    CANCEL = "CANCEL"


@dataclass
class DependencyRequirement:
    """Requisito formal de dependência externa emitido pelo agente ou sessão."""
    tool_name: str
    dependency_id: str = field(default_factory=lambda: f"dep-{uuid.uuid4().hex[:8]}")
    package_name: Optional[str] = None
    version_constraint: Optional[str] = None
    registry: Optional[str] = None
    reason: str = ""
    required_for: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    classification: str = DependencyClassification.REQUIRED.value
    risk_level: str = PermissionRiskLevel.LOW_RISK_MUTATION.value
    required_privileges: str = "Userland"
    fallback: Optional[str] = None
    fallback_description: Optional[str] = None
    fallback_capability: Optional[str] = None
    fallback_satisfies_acceptance_criteria: bool = False
    fallback_limitations: Optional[str] = None
    license: Optional[str] = None
    target_command: Optional[str] = None
    components: List[str] = field(default_factory=list)
    installer_source: Optional[str] = None
    installer_version: Optional[str] = None
    installer_checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyResolutionReport:
    """Relatório estruturado de análise e rastreabilidade de dependências."""
    required_dependencies: List[DependencyRequirement] = field(default_factory=list)
    optional_dependencies: List[DependencyRequirement] = field(default_factory=list)
    alternatives: List[DependencyRequirement] = field(default_factory=list)
    unavailable_required: List[DependencyRequirement] = field(default_factory=list)
    approval_requests: List[str] = field(default_factory=list)
    fallback_decisions: Dict[str, Any] = field(default_factory=dict)
    can_execute_immediately: bool = True
    blocked_reason: Optional[str] = None
    status: str = "READY_TO_EXECUTE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AuditLogEntry:
    """Registo de auditoria assinado e cronológico de cada transição de estado."""
    audit_id: str
    request_id: str
    event_type: str
    timestamp: float
    user_decision: Optional[str] = None
    risk_level: str = PermissionRiskLevel.LOW_RISK_MUTATION.value
    tool_name: str = ""
    mission_id: Optional[str] = None
    project_id: Optional[str] = None
    execution_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        return self.event_type

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuditLogEntry:
        return cls(
            audit_id=str(data["audit_id"]),
            request_id=str(data["request_id"]),
            event_type=str(data["event_type"]),
            timestamp=float(data.get("timestamp", time.time())),
            user_decision=data.get("user_decision"),
            risk_level=str(data.get("risk_level", PermissionRiskLevel.LOW_RISK_MUTATION.value)),
            tool_name=str(data.get("tool_name", "")),
            mission_id=data.get("mission_id"),
            project_id=data.get("project_id"),
            execution_id=data.get("execution_id"),
            details=dict(data.get("details", {})),
        )


@dataclass(slots=True)
class RollbackRecord:
    """Metadados de reversão segura de instalações ou mutações autorizadas."""
    rollback_id: str
    request_id: str
    tool_name: str
    installer: Optional[str]
    version: Optional[str]
    checksum: Optional[str]
    pre_install_state: Dict[str, Any] = field(default_factory=dict)
    post_install_state: Dict[str, Any] = field(default_factory=dict)
    is_reversible: bool = True
    executed: bool = False
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RollbackRecord:
        return cls(
            rollback_id=str(data["rollback_id"]),
            request_id=str(data["request_id"]),
            tool_name=str(data.get("tool_name", "")),
            installer=data.get("installer"),
            version=data.get("version"),
            checksum=data.get("checksum"),
            pre_install_state=dict(data.get("pre_install_state", {})),
            post_install_state=dict(data.get("post_install_state", {})),
            is_reversible=bool(data.get("is_reversible", True)),
            executed=bool(data.get("executed", False)),
            result=dict(data.get("result", {})),
            timestamp=float(data.get("timestamp", time.time())),
        )


@dataclass
class PermissionRequest:
    """
    Registo canónico de autorização Just-In-Time com separação estrita entre:
    REQUEST, APPROVAL, CAPABILITY e EXECUTION.
    """
    request_id: str
    tool_name: str
    requested_operation: str
    reason: str
    risk_level: str  # PermissionRiskLevel value
    required_privileges: str
    affected_resources: List[str]
    mission_id: Optional[str] = None
    project_id: Optional[str] = None
    execution_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_type: str = "binary"  # binary, package, driver, system_privilege, network_capability
    installation_required: bool = False
    installer_source: Optional[str] = None
    installer_version: Optional[str] = None
    installer_checksum: Optional[str] = None
    alternative_available: bool = False
    fallback_description: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)  # Default 5 min TTL
    status: str = PermissionRequestStatus.REQUESTED.value
    decision_evidence: Dict[str, Any] = field(default_factory=dict)
    policy_reason: Optional[str] = None
    user_decision: Optional[str] = None
    decided_at: Optional[float] = None
    decided_by: Optional[str] = None
    session_id: Optional[str] = None
    rollback_available: bool = False
    rollback_plan: Optional[str] = None
    capability_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    # Requirement Traceability & Governance Fields
    dependency_id: Optional[str] = None
    classification: str = DependencyClassification.REQUIRED.value
    required_for: Optional[str] = None
    acceptance_criteria: List[str] = field(default_factory=list)
    fallback_capability: Optional[str] = None
    fallback_satisfies_acceptance_criteria: bool = False
    fallback_limitations: Optional[str] = None
    components: List[str] = field(default_factory=list)
    approval_semantic: str = ApprovalSemantics.AUTHORIZE_USE.value
    capability_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        tool_name: str,
        requested_operation: str,
        reason: str,
        risk_level: str,
        required_privileges: str,
        affected_resources: List[str],
        mission_id: Optional[str] = None,
        project_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tool_type: str = "binary",
        installation_required: bool = False,
        installer_source: Optional[str] = None,
        installer_version: Optional[str] = None,
        installer_checksum: Optional[str] = None,
        alternative_available: bool = False,
        fallback_description: Optional[str] = None,
        ttl_seconds: float = 300.0,
        rollback_available: bool = False,
        rollback_plan: Optional[str] = None,
        dependency_id: Optional[str] = None,
        classification: str = DependencyClassification.REQUIRED.value,
        required_for: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        fallback_capability: Optional[str] = None,
        fallback_satisfies_acceptance_criteria: bool = False,
        fallback_limitations: Optional[str] = None,
        components: Optional[List[str]] = None,
        approval_semantic: str = ApprovalSemantics.AUTHORIZE_USE.value,
    ) -> PermissionRequest:
        now = time.time()
        return cls(
            request_id=f"perm-{uuid.uuid4().hex[:12]}",
            tool_name=tool_name,
            requested_operation=requested_operation,
            reason=reason,
            risk_level=risk_level,
            required_privileges=required_privileges,
            affected_resources=affected_resources,
            mission_id=mission_id,
            project_id=project_id,
            execution_id=execution_id,
            agent_id=agent_id,
            tool_type=tool_type,
            installation_required=installation_required,
            installer_source=installer_source,
            installer_version=installer_version,
            installer_checksum=installer_checksum,
            alternative_available=alternative_available,
            fallback_description=fallback_description,
            created_at=now,
            expires_at=now + ttl_seconds,
            status=PermissionRequestStatus.REQUESTED.value,
            rollback_available=rollback_available,
            rollback_plan=rollback_plan,
            dependency_id=dependency_id,
            classification=classification,
            required_for=required_for,
            acceptance_criteria=acceptance_criteria or [],
            fallback_capability=fallback_capability,
            fallback_satisfies_acceptance_criteria=fallback_satisfies_acceptance_criteria,
            fallback_limitations=fallback_limitations,
            components=components or [],
            approval_semantic=approval_semantic,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PermissionRequest:
        req = cls(
            request_id=str(data["request_id"]),
            tool_name=str(data["tool_name"]),
            requested_operation=str(data["requested_operation"]),
            reason=str(data.get("reason", "")),
            risk_level=str(data.get("risk_level", PermissionRiskLevel.LOW_RISK_MUTATION.value)),
            required_privileges=str(data.get("required_privileges", "")),
            affected_resources=list(data.get("affected_resources", [])),
            mission_id=data.get("mission_id"),
            project_id=data.get("project_id"),
            execution_id=data.get("execution_id"),
            agent_id=data.get("agent_id"),
            tool_type=str(data.get("tool_type", "binary")),
            installation_required=bool(data.get("installation_required", False)),
            installer_source=data.get("installer_source"),
            installer_version=data.get("installer_version"),
            installer_checksum=data.get("installer_checksum"),
            alternative_available=bool(data.get("alternative_available", False)),
            fallback_description=data.get("fallback_description"),
            created_at=float(data.get("created_at", time.time())),
            expires_at=float(data.get("expires_at", time.time() + 300.0)),
            status=str(data.get("status", PermissionRequestStatus.REQUESTED.value)),
            decision_evidence=dict(data.get("decision_evidence", {})),
            policy_reason=data.get("policy_reason"),
            user_decision=data.get("user_decision"),
            decided_at=data.get("decided_at"),
            decided_by=data.get("decided_by"),
            session_id=data.get("session_id"),
            rollback_available=bool(data.get("rollback_available", False)),
            rollback_plan=data.get("rollback_plan"),
            capability_result=data.get("capability_result"),
            execution_result=data.get("execution_result"),
            dependency_id=data.get("dependency_id"),
            classification=str(data.get("classification", DependencyClassification.REQUIRED.value)),
            required_for=data.get("required_for"),
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            fallback_capability=data.get("fallback_capability"),
            fallback_satisfies_acceptance_criteria=bool(data.get("fallback_satisfies_acceptance_criteria", False)),
            fallback_limitations=data.get("fallback_limitations"),
            components=list(data.get("components", [])),
            approval_semantic=str(data.get("approval_semantic", ApprovalSemantics.AUTHORIZE_USE.value)),
            capability_status=data.get("capability_status"),
        )
        return req
