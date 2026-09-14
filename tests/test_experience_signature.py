"""
JARVIS OS — Phase 42: Intent Normalization & Signature Extraction Tests
"""

from agents.experience_memory.signature import (
    ExperienceSignatureExtractor,
    IntentNormalizer,
)


def test_intent_normalizer_categories():
    cat1, tags1 = IntentNormalizer.normalize_intent("Permitir ao utilizador pesquisar e filtrar despesas")
    assert cat1 == "SEARCH_AND_FILTER"
    assert "search" in tags1 or "filtering" in tags1

    cat2, tags2 = IntentNormalizer.normalize_intent("Implementar autenticação segura com tokens JWT")
    assert cat2 == "AUTHENTICATION_AND_AUTH"
    assert "auth" in tags2

    cat3, tags3 = IntentNormalizer.normalize_intent("Calcular totais de gastos e despesas mensais")
    assert cat3 == "FINANCIAL_LEDGER"
    assert "financial" in tags3

    cat4, tags4 = IntentNormalizer.normalize_intent("Detetar oscilação repetida de planos A e B")
    assert cat4 == "OSCILLATION_DEFENSE"

    cat5, tags5 = IntentNormalizer.normalize_intent("Corrigir erro de sintaxe e compilar AST")
    assert cat5 == "CODE_REPAIR"


def test_signature_extraction_full_context():
    sig = ExperienceSignatureExtractor.extract_signature(
        intent_text="Adicionar pesquisa instantânea na interface web",
        requirements=[
            {"id": "REQ_01", "source": "USER_REQUIREMENT"},
            {"id": "REQ_02", "source": "SYSTEM_INFERRED"},
        ],
        tasks=[
            {"id": "TSK_01", "action": "CREATE_FILE"},
            {"id": "TSK_02", "action": "MODIFY_FILE"},
        ],
        observation={"failure_class": "CLEAN_BUILD"},
        decision="CONTINUE",
        technology=["vanilla_ts", "html5", "css3"],
        environment="LOCAL",
        affected_architecture=["frontend"],
    )

    assert sig.intent_category == "SEARCH_AND_FILTER"
    assert "USER_REQUIREMENT" in sig.requirement_types
    assert "SYSTEM_INFERRED" in sig.requirement_types
    assert "CREATE_FILE" in sig.task_categories
    assert "MODIFY_FILE" in sig.task_categories
    assert "vanilla_ts" in sig.technology
    assert sig.environment == "LOCAL"
    assert sig.decision == "CONTINUE"
