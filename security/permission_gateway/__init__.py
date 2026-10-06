"""
JARVIS OS — Human-in-the-Loop (HITL) Permission Gateway Package
"""

from security.permission_gateway.capability_checker import CapabilityChecker
from security.permission_gateway.dependency_governance import (
    DependencyGovernanceError,
    DependencyGovernanceService,
    FallbackCriteriaViolationError,
    SilentDowngradePreventedError,
    get_dependency_governor,
    reset_dependency_governor,
)
from security.permission_gateway.gateway import (
    CrossProjectApprovalError,
    InvalidApprovalStateError,
    PermissionBlockedByPolicyError,
    PermissionExpiredError,
    PermissionGatewayError,
    PermissionGatewayService,
    PermissionNotFoundError,
    get_permission_gateway_service,
    reset_permission_gateway_service,
)
from security.permission_gateway.models import (
    ApprovalSemantics,
    AuditLogEntry,
    CapabilityStatus,
    DependencyClassification,
    DependencyRequirement,
    DependencyResolutionReport,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
    RollbackRecord,
)
from security.permission_gateway.policy_engine import PermissionPolicyEngine, PolicyDecision
from security.permission_gateway.supply_chain import SupplyChainValidator

__all__ = [
    "ApprovalSemantics",
    "AuditLogEntry",
    "CapabilityChecker",
    "CapabilityStatus",
    "CrossProjectApprovalError",
    "DependencyClassification",
    "DependencyGovernanceError",
    "DependencyGovernanceService",
    "DependencyRequirement",
    "DependencyResolutionReport",
    "FallbackCriteriaViolationError",
    "InvalidApprovalStateError",
    "PermissionBlockedByPolicyError",
    "PermissionExpiredError",
    "PermissionGatewayError",
    "PermissionGatewayService",
    "PermissionNotFoundError",
    "PermissionPolicyEngine",
    "PermissionRequest",
    "PermissionRequestStatus",
    "PermissionRiskLevel",
    "PolicyDecision",
    "RollbackRecord",
    "SilentDowngradePreventedError",
    "SupplyChainValidator",
    "get_dependency_governor",
    "get_permission_gateway_service",
    "reset_dependency_governor",
    "reset_permission_gateway_service",
]
