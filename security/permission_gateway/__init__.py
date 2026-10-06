"""
JARVIS OS — Human-in-the-Loop (HITL) Permission Gateway Package
"""

from security.permission_gateway.capability_checker import CapabilityChecker
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
    AuditLogEntry,
    CapabilityStatus,
    DependencyRequirement,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
    RollbackRecord,
)
from security.permission_gateway.policy_engine import PermissionPolicyEngine, PolicyDecision
from security.permission_gateway.supply_chain import SupplyChainValidator

__all__ = [
    "AuditLogEntry",
    "CapabilityChecker",
    "CapabilityStatus",
    "CrossProjectApprovalError",
    "DependencyRequirement",
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
    "SupplyChainValidator",
    "get_permission_gateway_service",
    "reset_permission_gateway_service",
]
