from __future__ import annotations

from backend.gateway.deployment_gateway import WebDeploymentGateway
from backend.gateway.evidence_gateway import EvidenceGateway
from backend.gateway.lead_gateway import LeadCaptureGateway
from backend.gateway.monetization_gateway import MonetizationGateway


class EconomicExecutionGateway:
    """Unified Gateway coordinating real external interactions, lead capture, deployments, and monetization events."""

    def __init__(
        self,
        lead_gateway: LeadCaptureGateway | None = None,
        deployment_gateway: WebDeploymentGateway | None = None,
        monetization_gateway: MonetizationGateway | None = None,
        evidence_gateway: EvidenceGateway | None = None,
    ):
        self.leads = lead_gateway or LeadCaptureGateway()
        self.deployment = deployment_gateway or WebDeploymentGateway()
        self.monetization = monetization_gateway or MonetizationGateway()
        self.evidence = evidence_gateway or EvidenceGateway()


__all__ = [
    "LeadCaptureGateway",
    "WebDeploymentGateway",
    "MonetizationGateway",
    "EvidenceGateway",
    "EconomicExecutionGateway",
]
