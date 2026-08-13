from __future__ import annotations

from backend.gateway.deployment_gateway import WebDeploymentGateway
from backend.gateway.evidence_gateway import EvidenceGateway
from backend.gateway.lead_gateway import LeadCaptureGateway
from backend.gateway.monetization_gateway import MonetizationGateway
from backend.gateway.verification_gate import (
    EvidenceLevel,
    ExternalVerificationGate,
    FabricationAttemptError,
)


class EconomicExecutionGateway:
    """Unified Gateway coordinating verified external interactions, lead capture, deployments, and monetization events."""

    def __init__(
        self,
        lead_gateway: LeadCaptureGateway | None = None,
        deployment_gateway: WebDeploymentGateway | None = None,
        monetization_gateway: MonetizationGateway | None = None,
        evidence_gateway: EvidenceGateway | None = None,
        verification_gate: ExternalVerificationGate | None = None,
    ):
        self.verification = verification_gate or ExternalVerificationGate()
        self.leads = lead_gateway or LeadCaptureGateway(verification_gate=self.verification)
        self.deployment = deployment_gateway or WebDeploymentGateway()
        self.monetization = monetization_gateway or MonetizationGateway(verification_gate=self.verification)
        self.evidence = evidence_gateway or EvidenceGateway()


__all__ = [
    "EvidenceLevel",
    "FabricationAttemptError",
    "ExternalVerificationGate",
    "LeadCaptureGateway",
    "WebDeploymentGateway",
    "MonetizationGateway",
    "EvidenceGateway",
    "EconomicExecutionGateway",
]
