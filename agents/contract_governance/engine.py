"""
JARVIS OS — Phase 46: Contract Drift Engine
Compares verified immutable contract baselines against runtime observation windows,
detects discrepancies across 15 drift types, performs deterministic breakage classification,
separates noise from systematic drift, and determines recommended governance actions.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.contract_governance.consumers import ContractConsumerRegistry
from agents.contract_governance.models import (
    ConsumerImpact,
    ContractBaseline,
    ContractDriftReport,
    ContractDriftStatus,
    DriftChange,
    DriftClassification,
    DriftPolicyAction,
    DriftType,
    ObservationWindow,
    TemporalStatus,
    VariationType,
)
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.models import RuntimeObservation


class ContractDriftEngine:
    """Core analytical engine for continuous contract governance and drift detection."""

    def __init__(self, consumer_registry: Optional[ContractConsumerRegistry] = None) -> None:
        self.consumer_registry = consumer_registry or ContractConsumerRegistry()

    def detect_drift(
        self,
        baseline: ContractBaseline,
        window: ObservationWindow,
        stale_threshold_seconds: float = 86400.0 * 2,  # 48h
    ) -> ContractDriftReport:
        """Analyzes all observations in the window against the immutable baseline."""
        drift_id = f"drift_{uuid.uuid4().hex[:10]}"
        now = time.time()

        # Step 1: Check Temporal Status (Aging / Stale)
        sample_count = window.sample_count
        if sample_count == 0:
            time_since_validation = now - baseline.validated_at
            temp_status = TemporalStatus.STALE if time_since_validation > stale_threshold_seconds else TemporalStatus.AGING
            return ContractDriftReport(
                drift_id=drift_id,
                contract_id=baseline.contract_id,
                baseline_version=baseline.version,
                observed_version=f"{baseline.version}-no_traffic",
                changes=[],
                classification=DriftClassification.NON_BREAKING,
                status=ContractDriftStatus.IN_SYNC if temp_status == TemporalStatus.AGING else ContractDriftStatus.UNCERTAIN_DRIFT,
                variation_type=VariationType.ONE_OFF_VARIATION,
                evidence_refs=[],
                sample_count=0,
                confidence=0.5,
                affected_consumers=[],
                affected_tasks=[],
                affected_graph_nodes=[],
                recommended_action=DriftPolicyAction.MONITOR if temp_status == TemporalStatus.AGING else DriftPolicyAction.REQUEST_VALIDATION,
                environment=window.environment.value,
                temporal_status=temp_status,
                timestamp=now,
                notes=f"No traffic observed in window. Temporal status: {temp_status.value}",
            )

        # Step 2: Extract observations matching this endpoint
        matching_obs: List[RuntimeObservation] = []
        for obs in window.observations:
            if obs.method.upper() == baseline.method.upper():
                # Normalized route matching
                if self._routes_match(obs.route, baseline.route):
                    matching_obs.append(obs)

        if not matching_obs:
            return ContractDriftReport(
                drift_id=drift_id,
                contract_id=baseline.contract_id,
                baseline_version=baseline.version,
                observed_version=f"{baseline.version}-unobserved",
                changes=[],
                classification=DriftClassification.NON_BREAKING,
                status=ContractDriftStatus.IN_SYNC,
                variation_type=VariationType.ONE_OFF_VARIATION,
                sample_count=0,
                confidence=0.5,
                environment=window.environment.value,
                temporal_status=TemporalStatus.AGING,
                timestamp=now,
                notes="Endpoint not invoked in observation window.",
            )

        # Step 3: Infer active schema from runtime traffic
        inferred_request, inferred_response, _ = SchemaInferenceEngine.infer_from_observations(matching_obs)

        # Step 4: Compare Baseline Schemas against Observed Schemas
        changes: List[DriftChange] = []
        evidence_refs = [obs.observation_id for obs in matching_obs[:10]]

        # Compare Responses
        self._compare_schema_properties(
            baseline_schema=baseline.response_schema or {},
            observed_schema=inferred_response.to_dict() if inferred_response else {},
            changes=changes,
            is_request=False,
            total_samples=len(matching_obs),
        )

        # Compare Requests only if request payloads were actually observed in runtime traffic
        has_req_payloads = any(obs.request_payload is not None for obs in matching_obs)
        if has_req_payloads:
            self._compare_schema_properties(
                baseline_schema=baseline.request_schema or {},
                observed_schema=inferred_request.to_dict() if inferred_request else {},
                changes=changes,
                is_request=True,
                total_samples=len(matching_obs),
            )

        # Step 5: Check Status Codes & Error Contracts
        self._compare_status_and_errors(
            baseline=baseline,
            observations=matching_obs,
            changes=changes,
        )

        # Step 6: Check Auth Headers & Credentials
        self._compare_auth_contract(
            baseline=baseline,
            observations=matching_obs,
            changes=changes,
        )

        # Step 7: Determine Variation Type (One-Off Noise vs Systematic Drift)
        variation_type = self._determine_variation_type(changes, len(matching_obs))

        # Filter out negligible one-off noise if sample size is large and frequency is miniscule
        active_changes = [
            c for c in changes
            if not (len(matching_obs) >= 10 and c.observed_frequency < 0.05 and c.classification == DriftClassification.NON_BREAKING)
        ]

        # Step 8: Classify Overall Drift Severity
        overall_classification = self._determine_overall_classification(active_changes)

        # Step 9: Downstream Consumer Impact Discovery
        affected_consumers = self.consumer_registry.get_consumers(baseline.contract_id)
        affected_tasks: List[str] = []
        affected_graph_nodes: List[str] = []

        for c in affected_consumers:
            if c.consumer_type == "TASK":
                affected_tasks.append(c.consumer_id)
            else:
                affected_graph_nodes.append(c.consumer_id)

        # Adjust breaking severity based on consumer presence
        if overall_classification == DriftClassification.BREAKING and not affected_consumers:
            # Still breaking from interface standpoint, but no active consumer will fail
            pass

        # Step 10: Map Status and Recommended Action
        if not active_changes:
            drift_status = ContractDriftStatus.IN_SYNC
            policy_action = DriftPolicyAction.MONITOR
        elif overall_classification == DriftClassification.NON_BREAKING:
            drift_status = ContractDriftStatus.NON_BREAKING_DRIFT
            policy_action = DriftPolicyAction.MONITOR
        elif overall_classification == DriftClassification.POTENTIALLY_BREAKING:
            drift_status = ContractDriftStatus.POTENTIALLY_BREAKING_DRIFT
            policy_action = DriftPolicyAction.REQUEST_VALIDATION
        elif overall_classification == DriftClassification.BREAKING:
            drift_status = ContractDriftStatus.BREAKING_DRIFT
            # Check if auth change or critical
            has_auth_break = any(c.is_auth for c in active_changes)
            policy_action = DriftPolicyAction.BLOCK if has_auth_break else DriftPolicyAction.REQUEST_HUMAN
        else:
            drift_status = ContractDriftStatus.UNCERTAIN_DRIFT
            policy_action = DriftPolicyAction.REQUEST_VALIDATION

        confidence = self._compute_confidence(len(matching_obs), active_changes)

        return ContractDriftReport(
            drift_id=drift_id,
            contract_id=baseline.contract_id,
            baseline_version=baseline.version,
            observed_version=f"{baseline.version}-observed_rev",
            changes=active_changes,
            classification=overall_classification,
            status=drift_status,
            variation_type=variation_type,
            evidence_refs=evidence_refs,
            sample_count=len(matching_obs),
            confidence=confidence,
            affected_consumers=affected_consumers,
            affected_tasks=affected_tasks,
            affected_graph_nodes=affected_graph_nodes,
            recommended_action=policy_action,
            environment=window.environment.value,
            temporal_status=TemporalStatus.DRIFTING if active_changes else TemporalStatus.CURRENT,
            timestamp=now,
            notes=f"Evaluated {len(matching_obs)} observations in {window.environment.value}. Detected {len(active_changes)} change(s).",
        )

    def _routes_match(self, obs_route: str, baseline_route: str) -> bool:
        """Checks if a concrete observation route matches a parameter-templated route."""
        r1 = obs_route.strip("/").split("/")
        r2 = baseline_route.strip("/").split("/")
        if len(r1) != len(r2):
            return False
        for p1, p2 in zip(r1, r2):
            if p2.startswith("{") and p2.endswith("}"):
                continue
            if p1 != p2:
                return False
        return True

    def _extract_properties(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts schema properties/fields without falling back to metadata attributes."""
        if not isinstance(schema, dict):
            return {}
        if "properties" in schema and isinstance(schema["properties"], dict):
            return schema["properties"]
        if "fields" in schema and isinstance(schema["fields"], dict):
            return schema["fields"]
        metadata_keys = {
            "schema_name", "properties", "fields", "required_fields",
            "nullable_fields", "enum_candidates", "sample_count",
            "error_contracts", "required", "type", "$schema", "title", "description"
        }
        return {k: v for k, v in schema.items() if k not in metadata_keys}

    def _compare_schema_properties(
        self,
        baseline_schema: Dict[str, Any],
        observed_schema: Dict[str, Any],
        changes: List[DriftChange],
        is_request: bool,
        total_samples: int,
    ) -> None:
        """Compares properties of baseline vs observed schema."""
        base_props = self._extract_properties(baseline_schema)
        obs_props = self._extract_properties(observed_schema)

        base_required = set(baseline_schema.get("required") or baseline_schema.get("required_fields") or [])
        obs_required = set(observed_schema.get("required") or observed_schema.get("required_fields") or [])

        # 1. Added fields in observed traffic
        for field_name, obs_field_def in obs_props.items():
            if field_name in ("properties", "fields", "required", "type", "$schema"):
                continue

            obs_type = obs_field_def.get("type", "any") if isinstance(obs_field_def, dict) else str(obs_field_def)
            obs_presence = obs_field_def.get("presence_ratio", 1.0) if isinstance(obs_field_def, dict) else 1.0

            if field_name not in base_props:
                # Field added!
                if is_request:
                    is_req = field_name in obs_required
                    severity = DriftClassification.BREAKING if is_req else DriftClassification.NON_BREAKING
                    dt = DriftType.REQUIREDNESS_CHANGED if is_req else DriftType.FIELD_ADDED
                    msg = f"New required field '{field_name}' added to request" if is_req else f"New optional field '{field_name}' observed in request"
                else:
                    # Added response field is generally non-breaking for tolerant consumers
                    severity = DriftClassification.NON_BREAKING
                    dt = DriftType.FIELD_ADDED
                    msg = f"New response field '{field_name}' ({obs_type}) observed in runtime"

                changes.append(
                    DriftChange(
                        field_path=f"{'request' if is_request else 'response'}.{field_name}",
                        drift_type=dt,
                        classification=severity,
                        baseline_value=None,
                        observed_value=obs_type,
                        observed_frequency=obs_presence,
                        baseline_frequency=0.0,
                        sample_count=total_samples,
                        message=msg,
                        is_request=is_request,
                    )
                )

        # 2. Existing baseline fields compared against observed
        for field_name, base_field_def in base_props.items():
            if field_name in ("properties", "fields", "required", "type", "$schema"):
                continue

            base_type = base_field_def.get("type", "any") if isinstance(base_field_def, dict) else str(base_field_def)
            is_base_required = field_name in base_required or (isinstance(base_field_def, dict) and base_field_def.get("is_required"))

            if field_name not in obs_props:
                # Field missing from observed traffic
                if is_request:
                    severity = DriftClassification.NON_BREAKING
                    msg = f"Field '{field_name}' not present in observed request traffic"
                else:
                    # Missing from response: breaking if consumer expected it
                    severity = DriftClassification.BREAKING if is_base_required else DriftClassification.POTENTIALLY_BREAKING
                    msg = f"Response field '{field_name}' missing from observed runtime responses"

                changes.append(
                    DriftChange(
                        field_path=f"{'request' if is_request else 'response'}.{field_name}",
                        drift_type=DriftType.FIELD_REMOVED,
                        classification=severity,
                        baseline_value=base_type,
                        observed_value="MISSING",
                        observed_frequency=0.0,
                        baseline_frequency=1.0,
                        sample_count=total_samples,
                        message=msg,
                        is_request=is_request,
                    )
                )
                continue

            # Field present in both: compare types
            obs_field_def = obs_props[field_name]
            obs_type = obs_field_def.get("type", "any") if isinstance(obs_field_def, dict) else str(obs_field_def)

            if base_type.lower() != "any" and obs_type.lower() != "any" and base_type.lower() != obs_type.lower():
                # Canonical normalization check
                if not (base_type.lower() in ("integer", "number", "float") and obs_type.lower() in ("integer", "number", "float")):
                    changes.append(
                        DriftChange(
                            field_path=f"{'request' if is_request else 'response'}.{field_name}",
                            drift_type=DriftType.TYPE_CHANGED,
                            classification=DriftClassification.BREAKING,
                            baseline_value=base_type,
                            observed_value=obs_type,
                            observed_frequency=1.0,
                            baseline_frequency=1.0,
                            sample_count=total_samples,
                            message=f"Type conflict on '{field_name}': baseline specifies '{base_type}', but runtime returns '{obs_type}'",
                            is_request=is_request,
                        )
                    )

            # Compare nullability
            base_nullable = base_field_def.get("is_nullable", False) if isinstance(base_field_def, dict) else False
            obs_nullable = obs_field_def.get("is_nullable", False) if isinstance(obs_field_def, dict) else False
            if obs_nullable and not base_nullable:
                changes.append(
                    DriftChange(
                        field_path=f"{'request' if is_request else 'response'}.{field_name}",
                        drift_type=DriftType.NULLABILITY_CHANGED,
                        classification=DriftClassification.BREAKING if not is_request else DriftClassification.NON_BREAKING,
                        baseline_value="NOT_NULL",
                        observed_value="NULLABLE",
                        observed_frequency=1.0,
                        baseline_frequency=1.0,
                        sample_count=total_samples,
                        message=f"Field '{field_name}' observed as null, but baseline specifies non-nullable",
                        is_request=is_request,
                    )
                )

    def _compare_status_and_errors(
        self,
        baseline: ContractBaseline,
        observations: List[RuntimeObservation],
        changes: List[DriftChange],
    ) -> None:
        """Detects unexpected status codes or deviations in error contracts."""
        observed_statuses = set(obs.status_code for obs in observations)
        expected_status = baseline.metadata.get("expected_status", 200)

        for status in observed_statuses:
            if status >= 500:
                # 5xx is an application failure / crash, not necessarily formal contract drift
                pass
            elif status >= 400:
                # Check if this 4xx status is documented in baseline error_contract
                error_spec = baseline.error_contract.get(str(status)) or baseline.error_contract.get(status)
                if not error_spec and status not in (400, 401, 403, 404, 422):
                    changes.append(
                        DriftChange(
                            field_path="status_code",
                            drift_type=DriftType.ERROR_CONTRACT_CHANGED,
                            classification=DriftClassification.POTENTIALLY_BREAKING,
                            baseline_value=expected_status,
                            observed_value=status,
                            observed_frequency=sum(1 for obs in observations if obs.status_code == status) / len(observations),
                            baseline_frequency=1.0,
                            sample_count=len(observations),
                            message=f"Unexpected error status code {status} observed in runtime",
                            is_error=True,
                        )
                    )

    def _compare_auth_contract(
        self,
        baseline: ContractBaseline,
        observations: List[RuntimeObservation],
        changes: List[DriftChange],
    ) -> None:
        """Detects auth contract shifts (e.g. endpoint unexpectedly requiring/missing auth)."""
        baseline_requires_auth = baseline.metadata.get("requires_auth", False)
        
        # Check observations for authorization header presence or 401/403 responses
        auth_obs_count = 0
        unauthorized_count = 0

        for obs in observations:
            headers = {k.lower(): v for k, v in (obs.request_headers or {}).items()}
            if "authorization" in headers or "cookie" in headers:
                auth_obs_count += 1
            if obs.status_code in (401, 403):
                unauthorized_count += 1

        total = len(observations)
        if total == 0:
            return

        if not baseline_requires_auth and unauthorized_count >= 1:
            changes.append(
                DriftChange(
                    field_path="security.auth",
                    drift_type=DriftType.AUTH_CONTRACT_CHANGED,
                    classification=DriftClassification.BREAKING,
                    baseline_value="PUBLIC",
                    observed_value="REQUIRES_AUTH",
                    observed_frequency=unauthorized_count / total,
                    baseline_frequency=0.0,
                    sample_count=total,
                    message=f"Endpoint is documented as public, but {unauthorized_count}/{total} requests returned 401/403 Unauthorized",
                    is_auth=True,
                )
            )

    def _determine_variation_type(self, changes: List[DriftChange], sample_count: int) -> VariationType:
        """Distinguishes one-off variations/noise from systematic drift."""
        if not changes:
            return VariationType.ONE_OFF_VARIATION
        
        if sample_count < 3:
            return VariationType.ONE_OFF_VARIATION

        high_freq_changes = [c for c in changes if c.observed_frequency >= 0.75]
        if len(high_freq_changes) == len(changes) and sample_count >= 5:
            return VariationType.CONTRACT_CHANGE
        elif high_freq_changes:
            return VariationType.SYSTEMATIC_DRIFT
        else:
            return VariationType.ONE_OFF_VARIATION

    def _determine_overall_classification(self, changes: List[DriftChange]) -> DriftClassification:
        """Classifies highest severity from all atomic changes."""
        if not changes:
            return DriftClassification.NON_BREAKING

        severities = [c.classification for c in changes]
        if DriftClassification.BREAKING in severities:
            return DriftClassification.BREAKING
        if DriftClassification.POTENTIALLY_BREAKING in severities:
            return DriftClassification.POTENTIALLY_BREAKING
        if DriftClassification.UNCERTAIN in severities:
            return DriftClassification.UNCERTAIN
        return DriftClassification.NON_BREAKING

    def _compute_confidence(self, sample_count: int, changes: List[DriftChange]) -> float:
        """Computes statistical confidence based on sample count and frequency consistency."""
        if sample_count == 0:
            return 0.5
        if sample_count == 1:
            return 0.6
        if sample_count == 2:
            return 0.75

        base_conf = min(0.98, 0.80 + (sample_count * 0.015))
        if changes:
            freq_avg = sum(c.observed_frequency for c in changes) / len(changes)
            return round(base_conf * freq_avg, 4)
        return round(base_conf, 4)
