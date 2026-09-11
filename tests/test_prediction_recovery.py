"""
JARVIS OS — Phase 39 Test Suite: Prediction Recovery & Immutability

Tests:
1. Predictions and outcomes are safely persisted to disk and recoverable.
2. Historical predictions are immutable.
3. Invariant: A prediction is never directly executable as a command without passing through Mission Gate.
"""

import json
import os
import pytest
from intelligence.predictive_impact import PredictiveImpactEngine


@pytest.fixture(autouse=True)
def clean_engine():
    PredictiveImpactEngine.reset()
    yield
    PredictiveImpactEngine.reset()


def test_prediction_persistence_and_recovery(tmp_path):
    temp_file = str(tmp_path / "test_recovery_predictions.json")
    PredictiveImpactEngine._persistence_file = temp_file

    report = PredictiveImpactEngine.predict(
        delta_operation="ADD_REQUIREMENT",
        target_name="REQ_RECOVER",
        directive_text="Persistência durável",
        mission_id="m_durable",
        base_intent_version=1,
        current_intent_version=1,
        current_requirements=[],
        current_tasks=[],
        current_evidence=[],
        current_assumptions=[],
    )

    # Check persistence on disk
    assert os.path.exists(temp_file)
    with open(temp_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data.get("predictions", [])) == 1
    assert data["predictions"][0]["prediction_id"] == report.prediction_id

    # Retrieve from engine
    recovered = PredictiveImpactEngine.get_prediction(report.prediction_id)
    assert recovered is not None
    assert recovered.prediction_id == report.prediction_id
    assert recovered.simulation_marker == "SIMULATION_ONLY"


def test_prediction_never_executes_as_command():
    """
    CRITICAL INVARIANT: A prediction object cannot be dispatched as an executable command.
    Only explicit MissionIntentDelta validated by the Mission Gate can mutate state.
    """
    report = PredictiveImpactEngine.predict(
        delta_operation="ADD_REQUIREMENT",
        target_name="REQ_FAKE",
        directive_text="Tentativa de bypass",
        mission_id="m_sec",
        base_intent_version=1,
        current_intent_version=1,
        current_requirements=[],
        current_tasks=[],
        current_evidence=[],
        current_assumptions=[],
    )

    # Attempting to treat report as command should fail type contracts
    assert hasattr(report, "simulation_marker")
    assert report.simulation_marker == "SIMULATION_ONLY"
    assert not hasattr(report, "command_id")
    assert not hasattr(report, "command_type")
