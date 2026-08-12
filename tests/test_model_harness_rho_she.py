import os
import unittest
from pathlib import Path

from backend.model_harness import (
    ExecutionConstraints,
    ModelHarness,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    ProviderRegistry,
    RetrospectiveEngine,
    SHERuleBank,
    SafetyRule,
)
from backend.model_harness.contracts import ProviderResult, ToolCall
from backend.model_harness.provider import ModelProvider


TEST_DB_PATH = Path("sandbox_dir/test_rho_she.db")


class MockPassProvider(ModelProvider):
    def __init__(self, name: str = "mock_pass"):
        self.name = name
        self.default_model = "mock-model"

    async def generate(self, request, route, progress_tracker):
        return ProviderResult(
            raw_text='[{"name": "list_files", "arguments": {"path": "."}}]',
            tool_calls=(ToolCall(name="list_files", arguments={"path": "."}),),
        )


class TestRHOSHEEngines(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except Exception:
                pass

    def tearDown(self):
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except Exception:
                pass

    def test_she_rule_bank_assembly(self):
        bank = SHERuleBank()
        rules = bank.assemble_dynamic_rules("Por favor salva o ficheiro no computador", task_profile="DOCUMENT_GENERATION")
        self.assertIn("DIRECTIVAS E REGRAS DE SEGURANCA", rules)
        self.assertIn("FILE_SYSTEM", rules)

    async def test_rho_engine_trajectory_recording(self):
        rho = RetrospectiveEngine(db_path=TEST_DB_PATH)
        she = SHERuleBank()
        providers = ProviderRegistry([MockPassProvider()])
        harness = ModelHarness(providers, rho=rho, she=she)

        request = ModelRequest(
            task_profile="TOOL_SELECTION",
            system_prompt="System base",
            user_prompt="Salva o ficheiro de teste",
            allowed_tools=("list_files",),
            execution_constraints=ExecutionConstraints(max_attempts=1),
        )

        response = await harness.execute(request)
        self.assertEqual(response.status, ModelResponseStatus.SUCCEEDED)
        rules = rho.get_compounding_rules("TOOL_SELECTION")
        self.assertIsInstance(rules, list)


if __name__ == "__main__":
    unittest.main()
