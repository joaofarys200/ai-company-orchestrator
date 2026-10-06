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
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CAPABILITY_CHECKING = "CAPABILITY_CHECKING"
    AVAILABLE = "AVAILABLE"
    INSTALLATION_REQUIRED = "INSTALLATION_REQUIRED"
    ADMIN_PRIVILEGE_REQUIRED = "ADMIN_PRIVILEGE_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
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


@dataclass(slots=True)
class DependencyRequirement:
    """Requisito formal de dependência externa emitido pelo agente ou sessão."""
    tool_name: str
    package_name: Optional[str] = None
    version_constraint: Optional[str] = None
    registry: Optional[str] = None
    reason: str = ""
    risk_level: str = PermissionRiskLevel.LOW_RISK_MUTATION.value
    required_privileges: str = "Userland"
    fallback_description: Optional[str] = None
    license: Optional[str] = None
    target_command: Optional[str] = None

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


@dataclass(slots=True)
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
        )
