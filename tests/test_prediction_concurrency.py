"""
JARVIS OS — Phase 39 Test Suite: Prediction Concurrency & Stale Protection

Tests:
1. Prediction created on Intent v1 becomes STALE if Intent transitions to v2 before Apply.
2. Applying an intent delta with a stale base version is strictly rejected with STALE_INTENT_DELTA / STALE_PREDICTION.
3. Concurrent predictions for independent missions remain properly isolated.
"""

import pytest
from agents.mission_control_engine import (
    CommandStatus,
    IntentDeltaOperation,
    MissionControlEngine,
    MissionIntentDelta,
)
from intelligence.predictive_impact import PredictiveImpactEngine, PredictionStatus


@pytest.fixture(autouse=True)
def clean_engine():
    MissionControlEngine.reset_scenarios()
    PredictiveImpactEngine.reset()
    yield
    MissionControlEngine.reset_scenarios()
    PredictiveImpactEngine.reset()


def test_stale_prediction_after_intent_increment():
    state = MissionControlEngine.get_interactive_state()
    initial_version = state.intent_version  # 1

    # 1. Create Prediction P1 on base version 1
    delta_p1 = MissionIntentDelta(
        delta_id="delta_p1",
        mission_id=state.mission_id,
        base_intent_version=initial_version,
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_SEARCH",
        payload={"desc": "Busca"},
        reason="Pesquisa",
    )
    report_p1, status_p1, _ = MissionControlEngine.predict_intent_impact(delta_p1)
    assert report_p1.status == PredictionStatus.GENERATED.value
    assert status_p1 == CommandStatus.ACCEPTED

    # 2. Another operator applies a change (Intent v1 -> Intent v2)
    delta_applied = MissionIntentDelta(
        delta_id="delta_other",
        mission_id=state.mission_id,
        base_intent_version=initial_version,
        operation=IntentDeltaOperation.ADD_CONSTRAINT,
        target="CST_FAST",
        payload={"desc": "Tempo de resposta < 100ms"},
        reason="Latência estrita",
    )
    cmd_res, updated_state = MissionControlEngine.apply_intent_delta(delta_applied, pre_approved=True)
    assert cmd_res.status == CommandStatus.ACCEPTED
    assert updated_state.intent_version == 2

    # 3. Now attempt to predict or apply using the old base_version=1
    delta_stale = MissionIntentDelta(
        delta_id="delta_stale_attempt",
        mission_id=state.mission_id,
        base_intent_version=initial_version,  # 1 != current 2
        operation=IntentDeltaOperation.ADD_REQUIREMENT,
        target="REQ_SEARCH",
        payload={"desc": "Busca"},
        reason="Pesquisa antiga",
    )
    report_stale, status_stale, reason_stale = MissionControlEngine.predict_intent_impact(delta_stale)
    assert status_stale == CommandStatus.STALE
    assert report_stale.status == PredictionStatus.STALE.value

    # 4. Applying stale delta directly is blocked
    cmd_stale, _ = MissionControlEngine.apply_intent_delta(delta_stale, pre_approved=True)
    assert cmd_stale.status == CommandStatus.STALE
    assert "STALE" in cmd_stale.reason


def test_independent_mission_predictions_isolated():
    """Predictions for different missions do not cross-contaminate."""
    p_a = PredictiveImpactEngine.predict(
        delta_operation="ADD_REQUIREMENT",
        target_name="REQ_A",
        directive_text="Alpha feature",
        mission_id="m_alpha",
        base_intent_version=1,
        current_intent_version=1,
        current_requirements=[],
        current_tasks=[],
        current_evidence=[],
        current_assumptions=[],
    )

    p_b = PredictiveImpactEngine.predict(
        delta_operation="ADD_REQUIREMENT",
        target_name="REQ_B",
        directive_text="Beta feature",
        mission_id="m_beta",
        base_intent_version=1,
        current_intent_version=1,
        current_requirements=[],
        current_tasks=[],
        current_evidence=[],
        current_assumptions=[],
    )

    alpha_list = PredictiveImpactEngine.get_mission_predictions("m_alpha")
    beta_list = PredictiveImpactEngine.get_mission_predictions("m_beta")

    assert len(alpha_list) == 1
    assert len(beta_list) == 1
    assert alpha_list[0].prediction_id == p_a.prediction_id
    assert beta_list[0].prediction_id == p_b.prediction_id
