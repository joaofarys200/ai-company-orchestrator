"""
JARVIS OS — Product Delivery Governance & Acceptance Architecture.
Garante aceitação holística ao nível de produto antes de qualquer entrega autónoma.
"""

from security.delivery_governance.architecture_detector import (
    ArchitectureDetector,
    DetectedArchitecture,
)
from security.delivery_governance.artifact_inference import (
    ArtifactInferenceEngine,
)
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
    ArchitectureDecision,
    ProjectArchitecture,
    ArtifactCategory,
    ArtifactEvidence,
    ArtifactEvidenceStatus,
    ArtifactExpectation,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductIntegrityDiff,
    QualityScoreStatus,
    RequirementItem,
    RequirementStatus,
)
from security.delivery_governance.repair_planner import (
    RepairAction,
    RepairPlanner,
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
    "ArtifactCategory",
    "ArtifactEvidenceStatus",
    "ArtifactExpectation",
    "ArtifactEvidence",
    "ArchitectureDecision",
    "DetectedArchitecture",
    "ArchitectureDetector",
    "ArtifactInferenceEngine",
    "RepairAction",
    "RepairPlanner",
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
