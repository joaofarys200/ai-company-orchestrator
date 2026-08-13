from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from workspace.document_pipeline.manifest import DocumentProvenanceManifest


@dataclass
class DocumentQualityScore:
    """Detailed multidimensional quality score for audit-grade technical and business documents."""

    document_id: str
    requirement_coverage_pct: float = 100.0
    factuality_pct: float = 100.0
    citations_count: int = 0
    tables_count: int = 0
    contradictions_count: int = 0
    structural_integrity_score: float = 10.0  # Out of 10.0
    overall_quality_grade: str = "A+"
    details: dict[str, Any] = field(default_factory=dict)


class DocumentQualityEvaluator:
    """Evaluates generated documents across factual, structural, and citation axes."""

    @classmethod
    def evaluate_document(
        cls,
        content: str,
        manifest: DocumentProvenanceManifest,
        required_sections: list[str] | None = None,
    ) -> DocumentQualityScore:
        reqs = required_sections or [
            "Executive Summary",
            "Technical Architecture",
            "Market Analysis",
            "Risk Assessment",
            "Conclusion",
        ]

        # Check section coverage
        matched_sections = [s for s in reqs if re.search(rf"#+\s+{re.escape(s)}", content, re.IGNORECASE)]
        coverage_pct = round((len(matched_sections) / len(reqs)) * 100.0, 2) if reqs else 100.0

        # Check citations
        citations = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        citations_count = len(citations)

        # Check tables
        tables = re.findall(r"\|.+\|", content)
        tables_count = len(tables) // 2 if tables else 0

        # Check contradictions (placeholder for semantic checks)
        contradictions = 0

        # Factuality score based on validated claims
        valid_claims = sum(1 for c in manifest.claims if c.get("verified", False))
        total_claims = len(manifest.claims)
        factuality_pct = round((valid_claims / total_claims) * 100.0, 2) if total_claims else 100.0

        score = DocumentQualityScore(
            document_id=manifest.document_id,
            requirement_coverage_pct=coverage_pct,
            factuality_pct=factuality_pct,
            citations_count=citations_count,
            tables_count=tables_count,
            contradictions_count=contradictions,
            structural_integrity_score=9.5 if coverage_pct >= 80 else 7.0,
            overall_quality_grade="A+" if (coverage_pct >= 90 and factuality_pct >= 90) else "B",
            details={
                "matched_sections": matched_sections,
                "missing_sections": [s for s in reqs if s not in matched_sections],
            },
        )
        return score


__all__ = ["DocumentQualityEvaluator", "DocumentQualityScore"]
