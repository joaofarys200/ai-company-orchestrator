from __future__ import annotations

import json

import pytest

from services.airllm_server.phase18_validation import (
    CHECKPOINT_REVISION,
    MODEL_ID,
    ORCHESTRATION_MISSION,
    ORCHESTRATOR_SYSTEM_PROMPT,
    Phase18ValidationError,
    classify_phase18,
    estimate_storage,
    evaluate_plan_text,
    orchestration_messages,
    parse_plan_json,
    safe_environment_summary,
    validate_phase18_environment,
)
from services.airllm_server.prompting import render_chat_prompt


def phase18_environment() -> dict[str, str]:
    return {
        "AIRLLM_MODEL": MODEL_ID,
        "AIRLLM_COMPRESSION": "4bit",
        "AIRLLM_MAX_NEW_TOKENS": "1024",
        "AIRLLM_TEMPERATURE": "0",
        "AIRLLM_DO_SAMPLE": "false",
        "AIRLLM_ENABLE_QWEN35_COMPAT_PATCH": "false",
    }


def valid_plan() -> dict[str, object]:
    return {
        "objective": "Planear o SaaS de inventário sem executar a implementação.",
        "assumptions": ["A aplicação será executada localmente."],
        "open_questions": ["Qual é a política de retenção do histórico?"],
        "workstreams": [
            {
                "id": "ws-product",
                "name": "Descoberta de produto e requisitos de negócio",
                "owner": "Alex",
                "objective": "Priorizar requisitos de produto e decisões de negócio.",
                "tasks": [
                    {
                        "id": "task-product",
                        "title": "Definir requisitos",
                        "description": (
                            "Cobrir produto, stock, entradas, saídas, alertas, "
                            "utilizadores, relatórios e histórico."
                        ),
                        "depends_on": [],
                        "deliverables": ["Backlog priorizado"],
                        "acceptance_criteria": ["Todos os requisitos têm prioridade."],
                    }
                ],
            },
            {
                "id": "ws-design",
                "name": "UX, UI, interface e sistema visual",
                "owner": "Clara",
                "objective": "Desenhar fluxos e dashboard acessíveis.",
                "tasks": [
                    {
                        "id": "task-design",
                        "title": "Desenhar os fluxos",
                        "description": "Criar os fluxos de interface e dashboard.",
                        "depends_on": ["task-product"],
                        "deliverables": ["Protótipo navegável"],
                        "acceptance_criteria": ["Fluxos validados com utilizadores."],
                    }
                ],
            },
            {
                "id": "ws-build",
                "name": "Arquitetura e implementação",
                "owner": "Devon",
                "objective": (
                    "Definir backend Python, API REST, base de dados relacional, "
                    "autenticação e Docker."
                ),
                "tasks": [
                    {
                        "id": "task-build",
                        "title": "Planear a implementação",
                        "description": "Planear arquitetura, integração e implementação.",
                        "depends_on": ["task-product", "task-design"],
                        "deliverables": ["Plano técnico"],
                        "acceptance_criteria": ["A API e os dados têm contratos verificáveis."],
                    }
                ],
            },
            {
                "id": "ws-quality",
                "name": "Testes, segurança e qualidade",
                "owner": "Quinn",
                "objective": "Planear testes automatizados, validação e segurança.",
                "tasks": [
                    {
                        "id": "task-quality",
                        "title": "Definir a validação",
                        "description": "Definir testes e critérios de aceitação.",
                        "depends_on": ["task-build"],
                        "deliverables": ["Estratégia de testes"],
                        "acceptance_criteria": ["Testes cobrem os fluxos críticos."],
                    }
                ],
            },
        ],
        "milestones": [
            {
                "id": "milestone-plan",
                "name": "Plano aprovado",
                "depends_on": ["task-quality"],
                "completion_criteria": ["Todas as validações estão definidas."],
            }
        ],
        "risks": [
            {
                "risk": "Requisitos de auditoria incompletos.",
                "impact": "high",
                "mitigation": "Validar retenção e permissões antes da implementação.",
                "owner": "Alex",
            }
        ],
    }


def test_checkpoint_identity_is_pinned_without_network_access():
    assert MODEL_ID == "Qwen/Qwen2.5-72B-Instruct"
    assert CHECKPOINT_REVISION == "495f39366efef23836d0cfae4fbe635880d2be31"


def test_phase18_environment_accepts_only_the_controlled_configuration():
    validate_phase18_environment(phase18_environment())

    invalid = phase18_environment()
    invalid["AIRLLM_DO_SAMPLE"] = "true"
    with pytest.raises(Phase18ValidationError, match="AIRLLM_DO_SAMPLE"):
        validate_phase18_environment(invalid)


def test_qwen35_patch_must_be_disabled():
    invalid = phase18_environment()
    invalid["AIRLLM_ENABLE_QWEN35_COMPAT_PATCH"] = "true"

    with pytest.raises(Phase18ValidationError, match="must remain disabled"):
        validate_phase18_environment(invalid)


def test_sensitive_environment_values_are_redacted():
    summary = safe_environment_summary(
        {"HF_TOKEN": "never-print", "api_secret": "hidden", "model": MODEL_ID}
    )

    assert summary == {
        "HF_TOKEN": "<redacted>",
        "api_secret": "<redacted>",
        "model": MODEL_ID,
    }
    assert "never-print" not in repr(summary)


def test_storage_estimate_includes_checkpoint_shards_temporary_and_margin():
    estimate = estimate_storage(
        1000,
        6000,
        quantized_ratio=0.3,
        airllm_guard_ratio=0.25,
        temporary_bytes=100,
        safety_bytes=200,
    )

    assert estimate.quantized_shards_bytes == 300
    assert estimate.airllm_guard_bytes == 4000
    assert estimate.physical_required_bytes == 1600
    assert estimate.required_bytes == 5300
    assert estimate.enough_space is True
    assert estimate_storage(
        1000,
        5299,
        quantized_ratio=0.3,
        airllm_guard_ratio=0.25,
        temporary_bytes=100,
        safety_bytes=200,
    ).enough_space is False


def test_real_checkpoint_is_rejected_by_the_official_airllm_space_guard():
    estimate = estimate_storage(
        checkpoint_bytes=145_412_407_296,
        free_bytes=571_503_427_584,
    )

    assert estimate.physical_required_bytes < estimate.free_bytes
    assert estimate.airllm_guard_bytes > estimate.free_bytes - estimate.checkpoint_bytes
    assert estimate.enough_space is False


def test_system_prompt_mission_and_messages_preserve_the_agent_contract():
    messages = orchestration_messages()

    assert messages[0]["content"] == ORCHESTRATOR_SYSTEM_PROMPT
    assert messages[1]["content"] == ORCHESTRATION_MISSION
    assert all(owner in ORCHESTRATOR_SYSTEM_PROMPT for owner in ("Alex", "Clara", "Devon", "Quinn"))
    assert "Responde exclusivamente em JSON válido" in ORCHESTRATOR_SYSTEM_PROMPT


def test_official_chat_template_is_applied_to_orchestration_messages():
    class FakeTokenizer:
        chat_template = "official-template"

        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            assert messages == orchestration_messages()
            assert tokenize is False
            assert add_generation_prompt is True
            return "<official-qwen-chat>"

    assert render_chat_prompt(FakeTokenizer(), orchestration_messages()) == "<official-qwen-chat>"


def test_json_parser_rejects_markdown_and_external_text():
    payload = valid_plan()
    assert parse_plan_json(json.dumps(payload)) == payload

    for invalid in (f"```json\n{json.dumps(payload)}\n```", f"Plano:\n{json.dumps(payload)}"):
        with pytest.raises(Phase18ValidationError, match="outside"):
            parse_plan_json(invalid)


def test_complete_plan_scores_100():
    evaluation = evaluate_plan_text(json.dumps(valid_plan(), ensure_ascii=False))

    assert evaluation.parsed is True
    assert evaluation.total == 100
    assert all(score > 0 for score in evaluation.category_scores.values())
    assert evaluation.violations == ()


def test_schema_and_owner_violations_are_detected():
    payload = valid_plan()
    del payload["milestones"]
    payload["workstreams"][0]["owner"] = "Miguel"

    evaluation = evaluate_plan_text(json.dumps(payload, ensure_ascii=False))

    assert any("missing_root:milestones" in item for item in evaluation.violations)
    assert any("invalid_owner_Miguel" in item for item in evaluation.violations)
    assert evaluation.total < 85


def test_duplicate_unknown_and_self_dependencies_are_detected():
    payload = valid_plan()
    payload["workstreams"][1]["tasks"][0]["id"] = "task-product"
    payload["workstreams"][2]["tasks"][0]["depends_on"] = ["missing-task"]
    payload["workstreams"][3]["tasks"][0]["depends_on"] = ["task-quality"]

    violations = evaluate_plan_text(json.dumps(payload, ensure_ascii=False)).violations

    assert any("duplicate_ids" in item for item in violations)
    assert any("unknown" in item for item in violations)
    assert any("self:task-quality" in item for item in violations)


def test_dependency_cycle_is_detected():
    payload = valid_plan()
    payload["workstreams"][0]["tasks"][0]["depends_on"] = ["task-design"]

    violations = evaluate_plan_text(json.dumps(payload, ensure_ascii=False)).violations

    assert "dependencies:cycle" in violations


@pytest.mark.parametrize(
    ("technical", "operational", "score", "baseline", "focal", "adversarial", "expected"),
    [
        (False, True, 100, 80, False, 3, "C"),
        (True, False, 100, 80, False, 3, "B"),
        (True, True, 84, 70, False, 3, "B"),
        (True, True, 90, 81, False, 3, "B"),
        (True, True, 90, 75, True, 3, "B"),
        (True, True, 90, 75, False, 1, "B"),
        (True, True, 90, 75, False, 2, "A"),
    ],
)
def test_phase_classification_is_deterministic(
    technical, operational, score, baseline, focal, adversarial, expected
):
    assert classify_phase18(
        technical_compatible=technical,
        operationally_viable=operational,
        qwen25_score=score,
        baseline_score=baseline,
        focal_correction_needed=focal,
        adversarial_passes=adversarial,
    ) == expected
