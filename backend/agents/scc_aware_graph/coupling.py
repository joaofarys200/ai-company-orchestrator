from __future__ import annotations

from typing import Any, Dict, List

from .models import SCCCouplingMetrics, StronglyConnectedComponent


class CouplingAnalyzer:
    """Computes transparent mathematical coupling metrics for strongly connected components."""

    W_DENSITY = 0.30
    W_SIZE = 0.25
    W_EXTERNAL = 0.25
    W_CROSS_SERVICE = 0.20

    @classmethod
    def analyze_scc(cls, scc: StronglyConnectedComponent) -> SCCCouplingMetrics:
        internal_count = len(scc.edges_internal)
        incoming_count = len(scc.incoming_edges)
        outgoing_count = len(scc.outgoing_edges)
        external_count = incoming_count + outgoing_count

        fan_in = incoming_count
        fan_out = outgoing_count

        # Count cross-service and cross-language edges
        cross_service = 0
        cross_lang = 0

        all_edges = scc.edges_internal + scc.incoming_edges + scc.outgoing_edges
        for e in all_edges:
            src = e.get("source") or e.get("src", "")
            tgt = e.get("target") or e.get("dst", "")
            if ("fe_" in src and "be_" in tgt) or ("backend" in src and "frontend" in tgt):
                cross_service += 1
            if ("ts" in src.lower() and "py" in tgt.lower()) or ("py" in src.lower() and "ts" in tgt.lower()):
                cross_lang += 1

        # Cycle depth estimation (size of SCC if cyclic, else 0)
        cycle_depth = scc.size if scc.is_cycle else 0

        # Transparent component breakdown
        norm_density = scc.density
        norm_size = min(1.0, scc.size / 10.0)
        norm_external = min(1.0, external_count / 20.0)
        norm_cross_service = min(1.0, cross_service / 5.0)

        score = (
            cls.W_DENSITY * norm_density
            + cls.W_SIZE * norm_size
            + cls.W_EXTERNAL * norm_external
            + cls.W_CROSS_SERVICE * norm_cross_service
        )
        score = round(min(1.0, score), 4)

        explanation = {
            "density_contribution": round(cls.W_DENSITY * norm_density, 4),
            "size_contribution": round(cls.W_SIZE * norm_size, 4),
            "external_edges_contribution": round(cls.W_EXTERNAL * norm_external, 4),
            "cross_service_contribution": round(cls.W_CROSS_SERVICE * norm_cross_service, 4),
            "raw_density": scc.density,
            "raw_size": scc.size,
            "raw_external_edges": external_count,
            "raw_cross_service_edges": cross_service,
        }

        return SCCCouplingMetrics(
            scc_id=scc.scc_id,
            size=scc.size,
            internal_edges_count=internal_count,
            external_edges_count=external_count,
            density=scc.density,
            fan_in=fan_in,
            fan_out=fan_out,
            cross_service_edges=cross_service,
            cross_language_edges=cross_lang,
            cycle_depth=cycle_depth,
            coupling_score=score,
            components_explanation=explanation,
        )
