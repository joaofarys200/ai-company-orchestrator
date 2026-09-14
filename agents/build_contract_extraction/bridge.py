"""
JARVIS OS — Phase 49: Build Contract Extraction Bridge
Integrates build-time extraction and dynamic consumer resolution with Fases 39–48.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from agents.build_contract_extraction.cache import BuildContractCache
from agents.build_contract_extraction.dynamic_consumers import DynamicConsumerScanner
from agents.build_contract_extraction.graph import BuildContractGraphIntegrator
from agents.build_contract_extraction.metrics import BuildContractTelemetry
from agents.build_contract_extraction.models import (
    DynamicConsumerPattern,
    DynamicConsumerResolution,
    EvidenceState,
    ExtractedContractBundle,
    ResolutionStatus,
)
from agents.build_contract_extraction.openapi import OpenAPIExtractor
from agents.build_contract_extraction.provenance import ProvenanceTracker
from agents.build_contract_extraction.resolver import DynamicConsumerResolver
from agents.build_contract_extraction.security import BuildContractSecuritySentinel
from agents.contract_change_management.models import (
    ConsumerCategory,
    ConsumerPatternMatching,
    ContractConsumerTrace,
)
from agents.semantic_graph.graph import CrossLanguageSemanticGraph


class BuildContractExtractionBridge:
    """
    Central orchestration bridge for Phase 49.
    Executes build contract extraction, dynamic consumer scanning, resolution, and propagation.
    """

    def __init__(self) -> None:
        self.cache = BuildContractCache()
        self.telemetry = BuildContractTelemetry()

    def process_build_contracts(
        self,
        openapi_specs: Optional[list[dict[str, Any]]] = None,
        source_code_files: Optional[dict[str, str]] = None,
        known_literal_unions: Optional[dict[str, list[str]]] = None,
        semantic_graph: Optional[CrossLanguageSemanticGraph] = None,
        mission_id: str = "mission_live",
    ) -> ExtractedContractBundle:
        """
        Main pipeline:
        1. Extracts contracts from OpenAPI specs (with cache check)
        2. Scans source code for dynamic consumer patterns (getattr, obj[key], registries)
        3. Resolves dynamic consumers using build-extracted types & unions
        4. Propagates contract nodes and consumer edges into the Semantic Graph
        5. Emits auditable telemetry events
        """
        bundle = ExtractedContractBundle()
        unions = known_literal_unions or {}

        # 1. Process OpenAPI Specs
        if openapi_specs:
            for idx, spec in enumerate(openapi_specs):
                spec_hash = ProvenanceTracker.compute_content_hash(spec)
                art_path = spec.get("info", {}).get("title", f"openapi_spec_{idx}.json")

                # Cache check
                cached = self.cache.get(art_path, spec_hash)
                if cached:
                    bundle.endpoints.update(cached.endpoints)
                    bundle.types.update(cached.types)
                    bundle.versions.update(cached.versions)
                else:
                    eps, tps, vers = OpenAPIExtractor.extract_from_dict(spec, artifact_path=art_path)
                    bundle.endpoints.update(eps)
                    bundle.types.update(tps)
                    bundle.versions.update(vers)

                    # Store in cache
                    sub_bundle = ExtractedContractBundle(endpoints=eps, types=tps, versions=vers)
                    self.cache.put(art_path, spec_hash, sub_bundle)

                    self.telemetry.record_event(
                        event_type="contract_extracted",
                        mission_id=mission_id,
                        artifact=art_path,
                        source="GENERATED_OPENAPI",
                        details={"endpoints_count": len(eps), "types_count": len(tps)},
                    )

        # 2. Extract literal unions from bundle types to augment known_literal_unions
        for t_name, ctype in bundle.types.items():
            if ctype.enum_values:
                unions[t_name] = [str(x) for x in ctype.enum_values]
                # Also store lowercase and clean names
                unions[ctype.name] = [str(x) for x in ctype.enum_values]

        # 3. Scan Source Code for Dynamic Patterns
        detected_patterns: list[DynamicConsumerPattern] = []
        if source_code_files:
            for file_path, code_str in source_code_files.items():
                if file_path.endswith(".py"):
                    pats = DynamicConsumerScanner.scan_python_code(
                        code_str,
                        source_file=file_path,
                        known_literal_unions=unions,
                    )
                    detected_patterns.extend(pats)
                elif file_path.endswith((".ts", ".tsx", ".js")):
                    pats = DynamicConsumerScanner.scan_typescript_code(
                        code_str,
                        source_file=file_path,
                        known_literal_unions=unions,
                    )
                    detected_patterns.extend(pats)

            for p in detected_patterns:
                self.telemetry.record_event(
                    event_type="dynamic_consumer_detected",
                    mission_id=mission_id,
                    artifact=p.source_file,
                    source="DYNAMIC_SCANNER",
                    details={"pattern_type": p.pattern_type.value, "line": p.line_number, "key": p.key_expression},
                )

        # 4. Resolve Dynamic Consumer Patterns
        resolutions = DynamicConsumerResolver.resolve_multiple(detected_patterns, bundle)
        bundle.dynamic_resolutions = resolutions

        for r in resolutions:
            ev_type = (
                "dynamic_consumer_resolved"
                if r.resolution_status == ResolutionStatus.RESOLVED
                else "dynamic_consumer_uncertain"
            )
            self.telemetry.record_event(
                event_type=ev_type,
                mission_id=mission_id,
                artifact=r.pattern.source_file,
                source="DYNAMIC_RESOLVER",
                confidence=r.evidence_state.value,
                decision=r.resolution_status.value,
                details={
                    "consumer_id": r.consumer_id,
                    "resolved_contract": r.resolved_contract_id,
                    "uncertainty_reason": r.uncertainty_reason.value,
                },
            )

        # 5. Propagate into Semantic Graph if provided
        if semantic_graph is not None:
            BuildContractGraphIntegrator.integrate_bundle(bundle, semantic_graph)

        return bundle

    def convert_resolutions_to_phase48_traces(
        self,
        resolutions: list[DynamicConsumerResolution],
    ) -> list[ContractConsumerTrace]:
        """
        Converts Phase 49 DynamicConsumerResolutions into Phase 48 ContractConsumerTraces.
        Enables seamless injection into ContractChangeAnalyzer and Migration Plan DAGs.
        """
        traces = []
        for r in resolutions:
            category = (
                ConsumerCategory.DIRECT
                if r.resolution_status == ResolutionStatus.RESOLVED
                else ConsumerCategory.INDIRECT
            )
            pm = (
                ConsumerPatternMatching.OPEN_WITH_FALLBACK
                if r.pattern_matching == "OPEN_WITH_FALLBACK"
                else ConsumerPatternMatching.CLOSED_EXHAUSTIVE
            )
            traces.append(ContractConsumerTrace(
                consumer_id=r.consumer_id,
                name=r.consumer_name,
                file_path=r.pattern.source_file,
                category=category,
                pattern_matching=pm,
                impact_reason=r.impact_reason,
                required_action=r.required_action,
                language=r.pattern.language,
            ))
        return traces
