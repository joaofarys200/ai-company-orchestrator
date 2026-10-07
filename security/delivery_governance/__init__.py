"""
JARVIS OS — Product Delivery Governance & Acceptance Architecture.
Garante aceitação holística ao nível de produto antes de qualquer entrega autónoma.
"""

from security.delivery_governance.delivery_gate import (
    ProductDeliveryGate,
    is_autonomous_product_delivery_ready,
)
from security.delivery_governance.integrity_detector import (
    DestructiveChangeDetector,
    PreservationAnalyzer,
)
from security.delivery_governance.models import (
    AcceptanceLevel,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductIntegrityDiff,
    QualityScoreStatus,
    RequirementItem,
    RequirementStatus,
)
from security.delivery_governance.validators import (
    AssetIntegrityValidator,
    BrowserIntegrityValidator,
    HtmlDocumentValidator,
    InteractionValidator,
    RuntimeIntegrityValidator,
    VisualIntegrityValidator,
)

__all__ = [
    "AcceptanceLevel",
    "DeliveryGateStatus",
    "RequirementStatus",
    "QualityScoreStatus",
    "RequirementItem",
    "ProductIntegrityDiff",
    "ProductAcceptanceReport",
    "PreservationAnalyzer",
    "DestructiveChangeDetector",
    "HtmlDocumentValidator",
    "AssetIntegrityValidator",
    "VisualIntegrityValidator",
    "InteractionValidator",
    "RuntimeIntegrityValidator",
    "BrowserIntegrityValidator",
    "ProductDeliveryGate",
    "is_autonomous_product_delivery_ready",
]
