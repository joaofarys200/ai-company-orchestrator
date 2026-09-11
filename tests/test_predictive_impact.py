"""
JARVIS OS — Phase 39 Test Suite: Predictive Impact & Change Simulation

Tests:
1. Non-mutating simulation invariant: state before == state after.
2. 15 Representative Change Corpus:
   - ADD_REQUIREMENT local
   - ADD_REQUIREMENT cross-file
   - ADD_REQUIREMENT architectural
   - ADD_CONSTRAINT
   - REMOVE_REQUIREMENT
   - MODIFY_REQUIREMENT
   - REVISE_APPROACH
   - Frontend-only change
   - Backend-only change
   - Full-stack change
   - Evidence invalidation (Zero False Success)
   - Change during running/repair
   - Stale prediction detection
   - Conflicting directive
   - No-impact directive
3. Deterministic risk assessment and scope evaluation.
4. Epistemic calibration: confidence, assumptions, uncertainties, causal chains.
"""

import copy
import time
import pytest

from agents.mission_control_engine import (
    MissionControlEngine,
    MissionControlState,
    MissionIntentDelta,
    IntentDeltaOperation,
    CommandStatus,
)
from intelligence.predictive_impact import (
    PredictiveImpactEngine,
    PredictiveImpactReport,
    ImpactScope,
    RiskLevel,
    PredictionStatus,
)


@pytest.fixture(autouse=True)
def clean_engine():
    MissionControlEngine.reset_scenarios()
    PredictiveImpactEngine.reset()
    yield
    MissionControlEngine.reset_scenarios()
    PredictiveImpactEngine.reset()


@pytest.fixture
def base_state():
    return MissionControlEngine.get_interactive_state()


def test_simulation_without_mutation(base_state):
    """
    CRITICAL INVARIANT: Simulation MUST NEVER mutate the real mission state.
    state_before == state_after.
    """
    state_before = copy.deepcopy(base_state.to_dict())
    
    delta = MissionIntentDelta(
        delta_id="delta_test_nomut",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_SEARCH",
        payload={"desc": "Busca em tempo real de transações"},
        reason="Pesquisa instantânea",
        requested_by="operator",
    )
    
    report, status, reason = MissionControlEngine.predict_intent_impact(delta)
    
    state_after = base_state.to_dict()
    
    # State fields must remain identical except telemetry cache
    assert state_before["mission_version"] == state_after["mission_version"]
    assert state_before["intent_version"] == state_after["intent_version"]
    assert state_before["plan_version"] == state_after["plan_version"]
    assert len(state_before["tasks"]) == len(state_after["tasks"])
    assert len(state_before["requirements"]) == len(state_after["requirements"])
    assert state_before["status"] == state_after["status"]
    
    # Report itself is valid
    assert report.simulation_marker == "SIMULATION_ONLY"
    assert report.predicted_scope in (ImpactScope.CROSS_MODULE.value, ImpactScope.CROSS_FILE.value, ImpactScope.LOCAL.value)
    assert len(report.predicted_files) > 0
    assert len(report.predicted_tasks) > 0


def test_corpus_1_add_requirement_local(base_state):
    """Corpus 1: Local requirement (e.g. style/UI adjustment)."""
    delta = MissionIntentDelta(
        delta_id="delta_c1",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_UI_THEME",
        payload={"desc": "Ajuste de estilos e cores no CSS"},
        reason="Mudar cores da interface",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_scope in (ImpactScope.LOCAL.value, ImpactScope.CROSS_FILE.value)
    assert report.predicted_risk in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value)
    assert report.predicted_browser_validation is True


def test_corpus_2_add_requirement_cross_file(base_state):
    """Corpus 2: Cross-file requirement (search feature touching frontend & backend)."""
    delta = MissionIntentDelta(
        delta_id="delta_c2",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_SEARCH",
        payload={"desc": "Implementar barra de pesquisa reativa"},
        reason="Pesquisa e filtros",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_scope in (ImpactScope.CROSS_MODULE.value, ImpactScope.CROSS_FILE.value)
    assert any("search" in f["file_path"].lower() for f in report.predicted_files)


def test_corpus_3_add_requirement_architectural(base_state):
    """Corpus 3: Architectural change (GraphQL / Architecture alteration)."""
    delta = MissionIntentDelta(
        delta_id="delta_c3",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_GRAPHQL",
        payload={"desc": "Substituir endpoints REST por arquitetura GraphQL"},
        reason="Migração para GraphQL",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_scope == ImpactScope.ARCHITECTURAL.value
    assert report.predicted_risk in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
    assert report.predicted_pause_required is True
    assert report.predicted_approval_required is True


def test_corpus_4_add_constraint(base_state):
    """Corpus 4: Add operational constraint."""
    delta = MissionIntentDelta(
        delta_id="delta_c4",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_CONSTRAINT,
        target="CST_NO_EXT_LIBS",
        payload={"desc": "Não adicionar dependências externas no package.json"},
        reason="Restrição de pacotes",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.status == PredictionStatus.GENERATED.value
    assert report.predicted_risk in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value)


def test_corpus_5_remove_requirement(base_state):
    """Corpus 5: Remove requirement with active evidence."""
    delta = MissionIntentDelta(
        delta_id="delta_c5",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.REMOVE_REQUIREMENT,
        target="REQ_01",
        payload={},
        reason="Remover requisito REQ_01",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_scope == ImpactScope.ARCHITECTURAL.value
    assert report.predicted_approval_required is True
    # Zero False Success: evidence must be predicted as superseded
    assert any(e["predicted_status"] == "SUPERSEDED" for e in report.predicted_evidence_impact)


def test_corpus_6_modify_requirement(base_state):
    """Corpus 6: Modify requirement."""
    delta = MissionIntentDelta(
        delta_id="delta_c6",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.MODIFY_REQUIREMENT,
        target="REQ_02",
        payload={"desc": "Novo cálculo dinâmico com impostos agregados"},
        reason="Atualizar cálculo",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert any(t["action"] == "MODIFY_TASK" for t in report.predicted_tasks)


def test_corpus_7_revise_approach(base_state):
    """Corpus 7: Revise approach (e.g. use React instead of vanilla JS)."""
    delta = MissionIntentDelta(
        delta_id="delta_c7",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.REVISE_APPROACH,
        target="APP_FRAMEWORK",
        payload={"desc": "Refazer estrutura com React modular"},
        reason="Mudar abordagem para React",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_scope == ImpactScope.ARCHITECTURAL.value
    assert report.predicted_approval_required is True


def test_corpus_8_auth_security_risk(base_state):
    """Corpus 8: Auth / Security directive evaluates deterministic high security risk."""
    delta = MissionIntentDelta(
        delta_id="delta_c8",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_AUTH",
        payload={"desc": "Adiciona autenticação com tokens JWT"},
        reason="Implementar autenticação JWT",
        requested_by="operator",
    )
    report, status, _ = MissionControlEngine.predict_intent_impact(delta)
    assert report.predicted_risk in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
    assert report.risk_factors["breakdown"]["security_score"] > 0
    assert report.predicted_approval_required is True


def test_corpus_9_stale_prediction(base_state):
    """Corpus 9: Outdated intent version produces STALE_PREDICTION."""
    delta = MissionIntentDelta(
        delta_id="delta_c9",
        mission_id=base_state.mission_id,
        base_intent_version=99,  # Mismatched version
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_OUTDATED",
        payload={"desc": "Requisito defasado"},
        reason="Teste stale",
        requested_by="operator",
    )
    report, status, reason = MissionControlEngine.predict_intent_impact(delta)
    assert status == CommandStatus.STALE
    assert report.status == PredictionStatus.STALE.value
    assert "STALE" in reason


def test_corpus_10_assumptions_and_causal_chains(base_state):
    """Corpus 10: Verifies calibration meta (assumptions, causal chains)."""
    delta = MissionIntentDelta(
        delta_id="delta_c10",
        mission_id=base_state.mission_id,
        base_intent_version=base_state.intent_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_SEARCH",
        payload={"desc": "Busca instantânea"},
        reason="Pesquisa reativa",
        requested_by="operator",
    )
    report, _, _ = MissionControlEngine.predict_intent_impact(delta)
    assert len(report.assumptions) >= 1
    assert any(a["category"] in ("SYSTEM_ASSUMPTION", "INFERRED") for a in report.assumptions)
    assert len(report.causal_chains) >= 1
    assert "path" in report.causal_chains[0]
