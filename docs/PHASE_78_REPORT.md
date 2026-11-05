# Phase 78 Completion Report: Autonomous Causal Diagnosis & Root-Cause Analysis

**Phase**: 78  
**Title**: Autonomous Causal Diagnosis & Root-Cause Analysis  
**Status**: COMPLETE  
**Auditor/Author**: Antigravity Assistant (Google DeepMind)  
**Date**: 2026-10-25  
**Target Repository**: `JARVIS OS`  

---

## Executive Summary

Phase 78 establishes the **Autonomous Causal Diagnosis & Root-Cause Analysis (RCA) Engine** for JARVIS OS. Prior to Phase 78, JARVIS OS relied on reactive string-matching heuristics (`RootCauseDiagnostician` in Phase 71) and static category correlation dictionaries (`KNOWN_CAUSAL_CHAINS`). It was unable to formulate competing root-cause hypotheses, construct directed acyclic causal graphs (DAGs), distinguish temporal precedence or correlation from true causation, evaluate evidence through Phase 77 governance, plan safe diagnostic experiments, calculate calibrated confidence, or reconcile post-remediation outcomes.

Phase 78 implements the full 11-stage closed-loop causal diagnosis lifecycle:
$$\text{INCIDENT INTAKE} \rightarrow \text{CONTEXT RECONSTRUCTION} \rightarrow \text{TIMELINE} \rightarrow \text{HYPOTHESES} \rightarrow \text{CAUSAL DAG} \rightarrow \text{EVIDENCE ASSESSMENT} \rightarrow \text{DISCRIMINATION} \rightarrow \text{CONFIDENCE} \rightarrow \text{ROOT-CAUSE ASSESSMENT} \rightarrow \text{RECOMMENDATIONS} \rightarrow \text{OUTCOME RECONCILIATION}$$

The system demonstrates:
1. **Multi-Hypothesis Competition**: Concurrently evaluates competing explanations ($K \ge 2$) rather than locking prematurely into the first hypothesis.
2. **Causal Graph Modeling**: Constructs DAGs linking root causes to terminal symptoms through intermediate states, strictly enforcing absence of causal cycles.
3. **Correlation vs Causation Distinction**: Coincidental events and correlation edges are explicitly penalized and prevented from being confirmed as root causes without causal mechanism evidence.
4. **Safe Hypothesis Discrimination**: Formulates targeted, read-only diagnostic checks to distinguish competing hypotheses while blocking destructive operations.
5. **Calibrated Confidence**: Computes mathematically derived confidence with explicit uncertainty bounds and Laplace/Bayesian evidence scaling.
6. **Post-Remediation Reconciliation**: Compares post-action telemetry with predicted effects to verify that the upstream root cause was genuinely resolved.

---

## 1. Verified Capability Gap & Audit Findings

The pre-implementation audit ([`docs/AUDIT_PHASE_78_CAPABILITY_GAP.md`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/AUDIT_PHASE_78_CAPABILITY_GAP.md)) inspected Phases 65 through 77 and established that:
- **Heuristic String Matching**: Phase 71's `RootCauseDiagnostician` matched keywords (`"exit_code"`, `"oom"`) in unverified strings and assigned hardcoded floats (`0.95`, `0.92`).
- **Absence of Causal DAGs**: Causal chains were not modeled as graphs; cascading failures could only be grouped if they matched a hardcoded static dictionary within a 60-second window.
- **Conflation of Root Causes and Symptoms**: Downstream symptoms (e.g. queue saturation, 504 timeouts) were frequently categorized as root causes.
- **No Safe Experimentation**: No capability existed to formulate or run non-destructive diagnostic experiments to differentiate competing explanations.
- **No Outcome Reconciliation**: No closed loop existed to verify that remediation actions actually cleared the diagnosed cause.

---

## 2. Core Implementation Architecture

Implemented with 1:1 structural parity across [`backend/agents/causal_diagnosis/`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/) and [`agents/causal_diagnosis/`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/causal_diagnosis/):

| Module | Core Responsibility |
|---|---|
| [`models.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/models.py) | Normalized domain models (`CausalNodeType`, `CausalEdgeType`, `HypothesisStatus`, `DiagnosticOutcome`, `TimelineEvent`, `CausalNode`, `CausalEdge`, `CausalHypothesis`, `DiagnosticExperiment`, `CorrectiveAction`, `DiagnosisReport`). |
| [`timeline.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/timeline.py) | `TimelineReconstructor`: Ingests and orders heterogeneous events chronologically; identifies missing timestamps and temporal skews. |
| [`graph.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/graph.py) | `CausalGraphBuilder`: Causal DAG construction, DFS cycle detection, topological sorting, path tracing, and candidate root-cause isolation. |
| [`confidence.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/confidence.py) | `ConfidenceCalculator`: Computes calibrated confidence via Bayesian evidence volume scaling, contradiction penalties, and explicit uncertainty intervals. |
| [`hypothesizer.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/hypothesizer.py) | `HypothesisGenerator`: Extracts candidate causal paths, attributes supporting and contradicting evidence, applies correlation penalties, and ranks competing hypotheses. |
| [`experiments.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/experiments.py) | `DiagnosticExperimentPlanner`: Formulates read-only discriminating experiments; blocks destructive commands; evaluates observation branches. |
| [`recommender.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/recommender.py) | `CorrectiveActionRecommender`: Formulates targeted remediation recommendations linked directly to confirmed root causes. |
| [`reconciliation.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/reconciliation.py) | `OutcomeReconciler`: Compares post-action telemetry with predicted effects to close the feedback loop. |
| [`persistence.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/persistence.py) | `CausalDiagnosisStore`: Atomic persistence in `.jarvis/causal_diagnosis/`, crash recovery, and audit ledgers. |
| [`adapters.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/adapters.py) | Subsystem adapters for Phase 71 (incidents), Phase 72 (reliability signals), Phase 73 (refactoring step failures), and Phase 77 (evidence governance). |
| [`bridge.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/bridge.py) | `CausalDiagnosisBridge`: Master 11-stage lifecycle orchestrator. |

---

## 3. Existing Subsystems Reused

Phase 78 does not introduce duplicate telemetry, test runners, or persistence databases:
- **Phase 77 Evidence Governance**: Verifies evidence authenticity, provenance, and freshness. Invalidation in Phase 77 directly degrades hypothesis status in Phase 78.
- **Phase 71 Production Operations**: Reuses incident categorization, telemetry contracts, and severity levels.
- **Phase 72 Reliability Intelligence**: Ingests anomaly and capacity signals as environmental context.
- **Phase 73 Macro-Refactoring Engine**: Ingests migration step failures into causal DAGs.
- **Phase 76 Predictive Calibration**: Bounded uncertainty intervals and drift tracking.
- **Phase 65 Safe Self-Modification**: Enforces execution boundaries and authorization tokens for diagnostic and corrective actions.

---

## 4. Test Suite Verification (35/35 Passed)

Automated tests in [`tests/test_causal_diagnosis.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_causal_diagnosis.py) verify all 35 scenarios mandated by Section 8:

| # | Scenario | Status |
|---|---|---|
| 1 | Correct reconstruction of a known causal chain | **PASS** |
| 2 | Distinguishing a symptom from its upstream cause | **PASS** |
| 3 | Multiple competing root-cause hypotheses | **PASS** |
| 4 | Correlation without sufficient causal evidence | **PASS** |
| 5 | Missing timestamps triggering uncertainty penalty | **PASS** |
| 6 | Contradictory evidence rejecting hypothesis | **PASS** |
| 7 | Missing evidence keeping diagnosis inconclusive | **PASS** |
| 8 | Synthetic evidence receiving uncertainty penalty | **PASS** |
| 9 | Cycle detection in causal DAG | **PASS** |
| 10 | Multiple interacting causes | **PASS** |
| 11 | Misleading hypothesis outranked by solid evidence | **PASS** |
| 12 | Insufficient evidence returning inconclusive | **PASS** |
| 13 | Deterministic confidence calculation | **PASS** |
| 14 | Plan discriminating diagnostic experiment | **PASS** |
| 15 | Diagnostic experiment execution and outcome evaluation | **PASS** |
| 16 | Prevention of destructive experiments | **PASS** |
| 17 | Experiment requiring authorization blocked without token | **PASS** |
| 18 | Experiment with valid authorization token succeeding | **PASS** |
| 19 | Outcome reconciliation success | **PASS** |
| 20 | Outcome reconciliation detecting failure | **PASS** |
| 21 | Integration with Phase 71 incident ingestion | **PASS** |
| 22 | Integration with Phase 72 reliability signals | **PASS** |
| 23 | Integration with Phase 73 refactoring step failure | **PASS** |
| 24 | Persistence and crash recovery | **PASS** |
| 25 | Topological sort enforcing causal order | **PASS** |
| 26 | Graceful handling of empty graph | **PASS** |
| 27 | Isolated symptom returning inconclusive | **PASS** |
| 28 | Rejecting edge between non-existent nodes | **PASS** |
| 29 | Complex diamond causal graph traversal | **PASS** |
| 30 | Ambiguous experiment observation handling | **PASS** |
| 31 | Audit trail recorded on every diagnosis | **PASS** |
| 32 | Recovery from clean store | **PASS** |
| 33 | Contributing factor not mislabeled as root cause | **PASS** |
| 34 | Unverified edge confidence propagation | **PASS** |
| 35 | Reconciling multiple corrective actions | **PASS** |

**Execution Summary**: `35 passed in 0.16s` (exit code 0).

---

## 5. Continuous Regression Suite Results (Phases 40–78)

Executed via continuous regression runner [`scripts/run_regression_phases_40_78.py`](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_regression_phases_40_78.py) across all 39 active phases:

- **Computed Total**: 611 tests passed
- **Reported Total**: 611 tests passed
- **Failed Total**: 0
- **Arithmetic Delta ($\Delta$)**: 0
- **Execution Time**: 25.57 seconds
- **Reconciliation Ledger**: [`docs/phase78_regression_reconciliation.json`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/phase78_regression_reconciliation.json)

Zero regressions observed across all prior phases (F40–F77).

---

## 6. Empirical Validation Evidence

Executed via [`scripts/empirical_validation_phase_78.py`](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/empirical_validation_phase_78.py); evidence recorded in [`docs/phase78_empirical_validation_evidence.json`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/phase78_empirical_validation_evidence.json):

1. **Root-Cause Classification Accuracy**: **100.0%** across all ground-truth scenarios.
2. **False Positive Causal Claim Rate**: **0.0%** (Zero unsupported or coincidental events were confirmed as root causes).
3. **Correlation vs Causation**: A coincident scheduled cron job was successfully separated from the true unindexed SQL query.
4. **Hypothesis Discrimination**: In a scenario with two competing explanations (JVM Full GC pause vs network switch packet drop), a read-only diagnostic check inspecting GC logs decisively confirmed the GC pause and rejected the network drop.
5. **Fresh Evidence Invalidation**: When contradictory evidence was introduced proving DB uptime was uninterrupted, a previously confirmed DB crash hypothesis was automatically invalidated to `CONTRADICTED_BY_EVIDENCE`.
6. **Crash Recovery & Reconciliation**: A persisted diagnosis was recovered from disk across process boundaries, and a post-remediation telemetry reconciliation confirmed that the root cause was eliminated.

---

## 7. Security, Authorization & Safety Safeguards

1. **Non-Destructive by Default**: Diagnostic experiments default to `READ_ONLY_INSPECTION`.
2. **Destructive Keyword Guard**: Commands containing destructive patterns (`rm `, `drop `, `delete `, `kill `, `format `) are automatically blocked with `UnauthorizedDiagnosticActionError`.
3. **Tier 4 Authorization Gate**: Privileged network or process inspections require an authentic human authorization token.
4. **No Premature Causal Promotion**: No hypothesis is promoted to `CONFIRMED` without verified supporting evidence and an absence of unexamined contradictions.

---

## 8. Deliverables Index

- Audit Gap Report: [`docs/AUDIT_PHASE_78_CAPABILITY_GAP.md`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/AUDIT_PHASE_78_CAPABILITY_GAP.md)
- Architecture & System Design: [`docs/DESIGN_PHASE_78_CAUSAL_DIAGNOSIS.md`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/DESIGN_PHASE_78_CAUSAL_DIAGNOSIS.md)
- Full Completion Report: [`docs/PHASE_78_REPORT.md`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/PHASE_78_REPORT.md)
- Primary Subsystem: [`backend/agents/causal_diagnosis/`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/agents/causal_diagnosis/)
- 1:1 Mirror: [`agents/causal_diagnosis/`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/causal_diagnosis/)
- Focused Test Suite (35 Tests): [`tests/test_causal_diagnosis.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_causal_diagnosis.py)
- Regression Suite Runner (Phases 40–78): [`scripts/run_regression_phases_40_78.py`](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_regression_phases_40_78.py)
- Regression Ledger: [`docs/phase78_regression_reconciliation.json`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/phase78_regression_reconciliation.json)
- Empirical Validation Script: [`scripts/empirical_validation_phase_78.py`](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/empirical_validation_phase_78.py)
- Empirical Validation Evidence: [`docs/phase78_empirical_validation_evidence.json`](file:///c:/Users/joaor/Desktop/JarvisOS/docs/phase78_empirical_validation_evidence.json)

---

## 9. Exact Reproduction Commands

```powershell
# 1. Run the focused Phase 78 test suite (35 tests)
.\venv\Scripts\python -m pytest tests/test_causal_diagnosis.py -v

# 2. Run the continuous regression suite (Phases 40-78, 611 tests)
.\venv\Scripts\python scripts/run_regression_phases_40_78.py

# 3. Run the empirical causal diagnosis validation experiment
.\venv\Scripts\python scripts/empirical_validation_phase_78.py
```
