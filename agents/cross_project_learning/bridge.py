"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: bridge.py
CrossProjectLearningBridge acts as the primary coordinator and singleton interface.
Governs knowledge ingestion, security quarantine, hybrid retrieval, applicability evaluation,
conflict resolution, transfer decisioning, and local validation closed loops.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .applicability import KnowledgeApplicabilityEngine
from .behavior import CrossProjectBehaviorAdapter
from .cache import DeterministicTransferCache
from .conflicts import ConflictDetector
from .contracts import CrossProjectContractAdapter
from .index import KnowledgeReverseIndex
from .knowledge import KnowledgeManager
from .metrics import CrossProjectLearningMetrics
from .models import (
    ApplicabilityResult,
    CandidateKnowledge,
    EngineeringKnowledgeItem,
    FeedbackOutcome,
    HarmEvent,
    KnowledgeCategory,
    KnowledgeProvenance,
    KnowledgeState,
    KnowledgeTransferDecision,
    LocalValidationResult,
    ProjectFingerprint,
    TransferDecisionState,
    TransferPolicyName,
)
from .persistence import CrossProjectLearningStore
from .policy import PolicyRegistry
from .provenance import ProvenanceTracker
from .retrieval import HybridKnowledgeRetriever
from .risk import CrossProjectRiskAnalyzer
from .security import CrossProjectSecurityFilter
from .tests import TestKnowledgeTransferEngine
from .transfer import TransferGovernanceEngine
from .validator import CrossProjectValidator
from .verification import VerificationKnowledgeTransferEngine


class CrossProjectLearningBridge:
    """Singleton facade managing cross-project learning, transfer governance, and validation."""

    _instance: Optional[CrossProjectLearningBridge] = None

    def __init__(self, db_path: str = ":memory:") -> None:
        self.store = CrossProjectLearningStore(db_path=db_path)
        self.km = KnowledgeManager()
        self.retriever = HybridKnowledgeRetriever(self.km)
        self.conflict_detector = ConflictDetector()
        self.index = KnowledgeReverseIndex()
        self.cache = DeterministicTransferCache()
        self.metrics = CrossProjectLearningMetrics()
        self.provenance = ProvenanceTracker()
        self.fingerprints: Dict[str, ProjectFingerprint] = {}

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> CrossProjectLearningBridge:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register_fingerprint(self, fp: ProjectFingerprint) -> None:
        """Register and persist project structural fingerprint."""
        is_valid, errors = CrossProjectValidator.validate_fingerprint(fp)
        if not is_valid:
            raise ValueError(f"Invalid ProjectFingerprint: {errors}")
        self.fingerprints[fp.project_id] = fp
        self.store.save_fingerprint(fp)

    def ingest_knowledge(
        self,
        source_project_id: str,
        category: KnowledgeCategory,
        pattern: Dict[str, Any],
        context: Dict[str, Any],
        preconditions: List[str],
        observed_effect: Dict[str, Any],
        evidence_scope: Dict[str, Any],
        confidence: float = 0.85,
        source_file: str = "",
        auto_validate: bool = False,
        qualify_transferable: bool = False,
    ) -> EngineeringKnowledgeItem:
        """
        Ingest a knowledge pattern from a project.
        Passes through the security filter before indexing and persistence.
        """
        fp = self.fingerprints.get(source_project_id)
        fp_hash = fp.fingerprint_hash if fp else "fp_unknown"

        k_id = f"k_{category.value.lower()[:4]}_{uuid.uuid4().hex[:8]}"

        # 1. Provenance record
        prov = self.provenance.record_origin(
            knowledge_id=k_id,
            source_project_id=source_project_id,
            source_file=source_file,
        )

        # 2. Create item in OBSERVED state
        item = self.km.create_observed_item(
            source_project_id=source_project_id,
            source_project_fingerprint=fp_hash,
            category=category,
            pattern=pattern,
            context=context,
            preconditions=preconditions,
            observed_effect=observed_effect,
            evidence_scope=evidence_scope,
            confidence=confidence,
            provenance=prov,
            item_id=k_id,
        )

        # 3. Security Quarantine
        is_clean, reason = CrossProjectSecurityFilter.sanitize_item(item)
        if not is_clean:
            item.state = KnowledgeState.REJECTED
            item.context["security_rejection"] = reason
            self.store.save_knowledge_item(item)
            raise PermissionError(f"Security sentinel blocked knowledge ingestion: {reason}")

        # 3. Provenance record
        self.provenance.record_origin(
            knowledge_id=item.knowledge_id,
            source_project_id=source_project_id,
            source_file=source_file,
        )

        # 4. Optional promotion if source evidence verified
        if auto_validate:
            self.km.promote_to_validated(item.knowledge_id, {"source_verified": True})
            if qualify_transferable:
                self.km.qualify_for_transfer(item.knowledge_id, min_confidence=0.50)

        # 5. Index and persist
        self.index.index_item(item)
        self.store.save_knowledge_item(item)
        self.metrics.real_repository.items_indexed += 1
        return item

    def transfer_knowledge(
        self,
        target_project_id: str,
        query_intent: str = "",
        category: Optional[KnowledgeCategory] = None,
        policy: TransferPolicyName = TransferPolicyName.STANDARD,
        context_label: str = "real_repository",
    ) -> List[Tuple[KnowledgeTransferDecision, CandidateKnowledge]]:
        """
        Main query and transfer pipeline:
        Retrieval -> Applicability -> Conflict Check -> Transfer Governance -> Persistence.
        """
        t0 = time.perf_counter()
        target_fp = self.fingerprints.get(target_project_id)
        if not target_fp:
            raise KeyError(f"Target project fingerprint not registered: {target_project_id}")

        policy_profile = PolicyRegistry.get_policy(policy)
        bucket = self.metrics.get_bucket(context_label)
        bucket.queries_executed += 1

        # 1. Hybrid Retrieval
        candidates = self.retriever.retrieve(
            target_fingerprint=target_fp,
            category=category,
            query_intent=query_intent,
            min_score=policy_profile.min_retrieval_score,
            limit=policy_profile.max_transfers_per_cycle,
        )
        bucket.candidates_retrieved += len(candidates)

        decisions: List[Tuple[KnowledgeTransferDecision, CandidateKnowledge]] = []

        for cand in candidates:
            item = cand.item

            # 2. Check Cache
            cache_key = DeterministicTransferCache.compute_cache_key(
                source_knowledge_hash=item.knowledge_id,
                target_fingerprint_hash=target_fp.fingerprint_hash,
                policy_name=policy.value,
            )
            cached_dec = self.cache.get(cache_key)
            if cached_dec:
                bucket.cache_hits += 1
                decisions.append((cached_dec, cand))
                continue
            bucket.cache_misses += 1

            # 3. Applicability Evaluation
            applicability = KnowledgeApplicabilityEngine.evaluate_applicability(
                candidate=cand,
                target_fingerprint=target_fp,
            )

            # 4. Conflict Check against currently transferable items
            for other in self.km.list_items():
                if other.knowledge_id != item.knowledge_id:
                    conf = self.conflict_detector.check_conflict(item, other)
                    if conf:
                        self.store.save_conflict(conf)
                        bucket.conflicts_detected += 1

            if item.state == KnowledgeState.CONFLICTED:
                # Mark as rejected transfer due to open conflict
                dec = KnowledgeTransferDecision(
                    decision_id=f"dec_conf_{uuid.uuid4().hex[:6]}",
                    state=TransferDecisionState.REJECT_TRANSFER,
                    target_project_id=target_project_id,
                    item_id=item.knowledge_id,
                    category=item.category,
                    rationale=f"Transfer rejected: pattern is in conflict with existing knowledge item",
                    local_validation_plan={},
                    requires_human_review=False,
                    confidence=0.0,
                    timestamp=time.time(),
                )
                self.store.save_transfer_decision(dec)
                bucket.transfers_rejected += 1
                decisions.append((dec, cand))
                continue

            # 5. Formulate Governance Transfer Decision
            dec = TransferGovernanceEngine.decide_transfer(
                candidate=cand,
                applicability=applicability,
                target_fingerprint=target_fp,
                policy=policy,
            )

            # 6. Validate Decision Invariants
            is_valid, errors = CrossProjectValidator.validate_transfer_decision(dec)
            if not is_valid:
                raise ValueError(f"Transfer decision violated invariants: {errors}")

            # 7. Record provenance transformation
            self.provenance.record_transformation(
                knowledge_id=item.knowledge_id,
                provenance=item.provenance,
                transformation_description=f"Transferred to {target_project_id} under {policy.value}",
            )

            # 8. Cache, Persist & Telemetry
            self.cache.put(cache_key, dec, target_fingerprint_hash=target_fp.fingerprint_hash)
            self.store.save_transfer_decision(dec)

            if dec.state in (TransferDecisionState.REJECT_TRANSFER, TransferDecisionState.HUMAN_REVIEW):
                bucket.transfers_rejected += 1
            else:
                bucket.transfers_accepted += 1

            decisions.append((dec, cand))

        total_ms = (time.perf_counter() - t0) * 1000.0
        bucket.total_cpu_time_ms += total_ms
        return decisions

    def execute_local_validation(
        self,
        decision: KnowledgeTransferDecision,
        should_fail: bool = False,
        induces_harm: bool = False,
        context_label: str = "real_repository",
    ) -> LocalValidationResult:
        """
        Execute the mandatory local validation cycle for a transferred decision.
        Updates confidence, records harm events, and persists evidence.
        """
        target_fp = self.fingerprints.get(decision.target_project_id)
        if not target_fp:
            raise KeyError(f"Project not found: {decision.target_project_id}")

        item = self.km.get_item(decision.item_id)
        if not item:
            raise KeyError(f"Knowledge item not found: {decision.item_id}")

        # Execute synthesized test or local invariant verification
        val_result = TestKnowledgeTransferEngine.simulate_or_execute_local_validation(
            transfer_decision_id=decision.decision_id,
            test_item=item,
            target_fingerprint=target_fp,
            should_fail=should_fail,
            induces_harm=induces_harm,
        )

        # Validate evidence
        is_valid, errors = CrossProjectValidator.validate_local_evidence(val_result)
        if not is_valid:
            raise ValueError(f"Invalid validation result: {errors}")

        # Harm Telemetry and Feedback update
        bucket = self.metrics.get_bucket(context_label)
        if induces_harm:
            harm_event = HarmEvent(
                harm_id=f"harm_{uuid.uuid4().hex[:6]}",
                knowledge_id=item.knowledge_id,
                target_project_id=target_fp.project_id,
                harm_type="PERFORMANCE_DEGRADATION",
                details=val_result.harm_details or "Observed test instability or coverage degradation",
                penalty_applied=0.20,
            )
            self.store.save_harm_event(harm_event)
            self.km.register_feedback(item.knowledge_id, is_success=False, is_harm=True, penalty=0.20)
            bucket.harm_events_detected += 1
            bucket.local_validations_failed += 1
        elif val_result.validated:
            self.km.register_feedback(item.knowledge_id, is_success=True, is_harm=False, bonus=0.05)
            bucket.local_validations_passed += 1
        else:
            self.km.register_feedback(item.knowledge_id, is_success=False, is_harm=False)
            bucket.local_validations_failed += 1

        # Link validation to provenance ledger
        self.provenance.record_local_validation(
            knowledge_id=item.knowledge_id,
            provenance=item.provenance,
            validation_id=val_result.validation_id,
            validation_hash=val_result.evidence.get("local_hash", "hash_val"),
        )

        self.store.save_validation_result(val_result)
        return val_result
