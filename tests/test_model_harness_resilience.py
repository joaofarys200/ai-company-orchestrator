import unittest
from dataclasses import replace

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelHarness,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    OutputFormat,
    ProviderRegistry,
    create_default_task_profile_registry,
)
from backend.model_harness.contracts import (
    ProviderResult,
    ToolCall,
    ValidationIssue,
    ValidationResult,
    ValidationStage,
    ValidationStatus,
)
from backend.model_harness.provider import ModelProvider
from backend.model_harness.recovery import default_recovery_transformer


class MockFailingProvider(ModelProvider):
    def __init__(self, name: str, should_fail: bool = True):
        self.name = name
        self.should_fail = should_fail
        self.default_model = f"{name}-model"

    async def generate(self, request, route, progress_tracker):
        if self.should_fail:
            raise RuntimeError(f"{self.name} provider simulation error")
        return ProviderResult(
            raw_text='[{"name": "list_files", "arguments": {"path": "."}}]',
            tool_calls=(ToolCall(name="list_files", arguments={"path": "."}),),
        )


class TestModelHarnessResilience(unittest.IsolatedAsyncioTestCase):
    def test_academic_research_profile_registration(self):
        registry = create_default_task_profile_registry()
        profile = registry.get("ACADEMIC_RESEARCH")
        self.assertEqual(profile.name, "ACADEMIC_RESEARCH")
        self.assertIn("search_arxiv", profile.allowed_tools)
        self.assertIn("read_pdf", profile.allowed_tools)

    def test_document_generation_profile_registration(self):
        registry = create_default_task_profile_registry()
        profile = registry.get("DOCUMENT_GENERATION")
        self.assertEqual(profile.name, "DOCUMENT_GENERATION")
        self.assertIn("write_file", profile.allowed_tools)

    def test_default_recovery_transformer_injects_vigil_repair(self):
        request = ModelRequest(
            task_profile="TOOL_SELECTION",
            system_prompt="System prompt",
            user_prompt="Original prompt",
        )
        response = ModelResponse(
            request_id=request.request_id,
            status=ModelResponseStatus.VALIDATION_FAILED,
            validation=ValidationResult(
                status=ValidationStatus.FAILED,
                issues=(
                    ValidationIssue(
                        stage=ValidationStage.SCHEMA,
                        code="MISSING_ARG",
                        message="Missing required field 'filename'",
                        location="user_prompt",
                        recoverable=True,
                    ),
                ),
            ),
        )
        transformed = default_recovery_transformer(request, response, None)
        self.assertIsNotNone(transformed)
        self.assertIn("[CORRECAO AUTONOMA - VIGIL ENGINE]", transformed.user_prompt)
        self.assertIn("Missing required field 'filename'", transformed.user_prompt)

    async def test_provider_failover_chain_from_gemini_to_ollama(self):
        gemini = MockFailingProvider("gemini", should_fail=True)
        ollama = MockFailingProvider("ollama", should_fail=False)
        providers = ProviderRegistry([gemini, ollama])
        harness = ModelHarness(providers)

        request = ModelRequest(
            task_profile="TOOL_SELECTION",
            system_prompt="System prompt",
            user_prompt="Run query",
            allowed_tools=("list_files",),
            execution_constraints=ExecutionConstraints(max_attempts=2, allow_recovery=True),
        )
        response = await harness.execute(request)
        self.assertEqual(response.status, ModelResponseStatus.SUCCEEDED)
        self.assertEqual(response.provider, "ollama")


if __name__ == "__main__":
    unittest.main()
