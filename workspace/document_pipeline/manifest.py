from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DocumentProvenanceManifest:
    """Cryptographically verifiable provenance manifest for audit-grade technical and economic documents."""

    document_id: str
    document_title: str
    target_format: str  # markdown, pdf, docx, html
    revision: int = 1
    generated_by: str = "JARVIS OS Document Pipeline"
    sources: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    validation: dict[str, bool] = field(
        default_factory=lambda: {
            "sources_checked": False,
            "claims_checked": False,
            "completeness_checked": False,
            "formatting_checked": False,
            "technical_review_passed": False,
        }
    )
    sha256_fingerprint: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_fingerprint(self, content: str | bytes) -> str:
        """Computes SHA-256 of the exported document content."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.sha256_fingerprint = hashlib.sha256(data).hexdigest()
        return self.sha256_fingerprint

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


__all__ = ["DocumentProvenanceManifest"]
