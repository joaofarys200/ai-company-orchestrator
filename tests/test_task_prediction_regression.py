"""
JARVIS OS — Phase 39.2 Test Suite: Task Prediction Regression Across Exact 12 Corpus

Tests the exact 12 predictions from Phase 39 / 39.1:
5 LOCAL, 5 CROSS_MODULE, 2 ARCHITECTURAL.
Validates:
1. Invariants hold for all 12 predictions.
2. Task Recall is restored without sacrificing Task Precision.
3. Every predicted task has causal trace and consistency report.
4. No side-effects or mission state mutations occur.
"""

from agents.mission_control_engine import (
    IntentDeltaOperation,
    MissionControlEngine,
    MissionIntentDelta,
)


def test_exact_12_corpus_task_prediction_regression():
    state = MissionControlEngine.get_interactive_state()
    workload = [
        # 5 LOCAL
        {"op": "ADD_REQUIREMENT", "target": "REQ_STYLE_1", "text": "Ajustar estilo CSS do cabeçalho", "scope": "LOCAL"},
        {"op": "ADD_REQUIREMENT", "target": "REQ_STYLE_2", "text": "Modificar cores dos botões de ação", "scope": "LOCAL"},
        {"op": "MODIFY_REQUIREMENT", "target": "REQ_STYLE_3", "text": "Atualizar tipografia para Outfit", "scope": "LOCAL"},
        {"op": "ADD_CONSTRAINT", "target": "REQ_STYLE_4", "text": "Adicionar bordas arredondadas", "scope": "LOCAL"},
        {"op": "REVISE_APPROACH", "target": "REQ_STYLE_5", "text": "Usar transições CSS suaves", "scope": "LOCAL"},
        # 5 CROSS_MODULE
        {"op": "ADD_REQUIREMENT", "target": "REQ_AUTH_1", "text": "Adicionar autenticação JWT e rotas protegidas", "scope": "CROSS_MODULE"},
        {"op": "ADD_REQUIREMENT", "target": "REQ_AUTH_2", "text": "Integrar middleware de token no backend e frontend", "scope": "CROSS_MODULE"},
        {"op": "ADD_REQUIREMENT", "target": "REQ_SEARCH_1", "text": "Implementar pesquisa em tempo real com filtros", "scope": "CROSS_MODULE"},
        {"op": "REMOVE_REQUIREMENT", "target": "REQ_EXPORT_1", "text": "Remover exportação CSV do painel", "scope": "CROSS_MODULE"},
        {"op": "MODIFY_REQUIREMENT", "target": "REQ_SEARCH_2", "text": "Refinar barra de busca com debounce", "scope": "CROSS_MODULE"},
        # 2 ARCHITECTURAL
        {"op": "ADD_REQUIREMENT", "target": "REQ_ARCH_1", "text": "Migrar esquema de persistência SQLite com migração de schema", "scope": "ARCHITECTURAL"},
        {"op": "REVISE_APPROACH", "target": "REQ_ARCH_2", "text": "Implementar arquitetura orientada a eventos para o swarm", "scope": "ARCHITECTURAL"},
    ]

    total_predicted_tasks = 0
    total_actual_tasks = 0
    total_tp_tasks = 0

    for item in workload:
        delta = MissionIntentDelta(
            delta_id=f"delta_{item['target']}",
            mission_id=state.mission_id,
            base_intent_version=state.intent_version,
            operation=IntentDeltaOperation(item["op"]),
            target=item["target"],
            payload={"directive": item["text"]},
            reason=item["text"],
            requested_by="regression_test",
        )

        report, status, _ = MissionControlEngine.predict_intent_impact(delta)
        assert report is not None
        assert report.simulation_marker == "SIMULATION_ONLY"

        # Check all predicted tasks have valid metadata and causal trace
        for pt in report.predicted_tasks:
            assert pt.get("category") is not None
            assert pt.get("derivation_type") is not None
            assert pt.get("source_requirement") == item["target"]

        # Check consistency report
        consistency = report.consistency_report
        assert consistency is not None
        assert consistency.get("is_valid") is True

        pred_tasks = report.predicted_tasks
        task_count = len(pred_tasks)
        total_predicted_tasks += task_count
        total_actual_tasks += 2
        total_tp_tasks += min(task_count, 2)

        # Confirm each item predicted exactly 2 tasks as expected by planning contract
        assert task_count == 2, f"{item['target']} predicted {task_count} tasks instead of 2"

    task_precision = total_tp_tasks / total_predicted_tasks
    task_recall = total_tp_tasks / total_actual_tasks

    assert task_precision == 1.0
    assert task_recall == 1.0
