import json
import unittest
from dataclasses import replace

from backend.model_harness import (
    CallableModelProvider,
    ContextBuildRequest,
    ContextBuilder,
    ContextCandidate,
    DuplicateProviderError,
    EnumConstraint,
    ExecutionConstraints,
    ExpectedOutput,
    ModelHarness,
    ModelPreferences,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    ModelRoute,
    ModelUsage,
    ModelValidationPipeline,
    OutputFormat,
    ProgressCondition,
    ProgressTracker,
    ProviderRegistry,
    ProviderResult,
    RecoveryAction,
    RecoveryCoordinator,
    RecoveryRecord,
    ReferenceConstraint,
    TaskProfileRegistry,
    UnsafeRecoveryError,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    ValidationStage,
    ValidationStatus,
    create_default_task_profile_registry,
)


def request(
    *,
    user_prompt="extract",
    expected=None,
    constraints=None,
    metadata=None,
):
    return ModelRequest(
        task_profile="STRUCTURED_EXTRACTION",
        system_prompt="Return the requested result.",
        user_prompt=user_prompt,
        expected_output=expected or ExpectedOutput(
            format=OutputFormat.JSON,
        ),
        model_preferences=ModelPreferences(
            providers=("test",),
            models=("test-model",),
        ),
        execution_constraints=constraints or ExecutionConstraints(),
        metadata=metadata or {},
    )


def route():
    return ModelRoute(
        provider="test",
        model="test-model",
        mode="chat",
        streaming=False,
        thinking=False,
    )


class ModelHarnessContractsTest(unittest.TestCase):
    def test_request_has_stable_content_fingerprint(self):
        first = request(user_prompt="same")
        second = replace(first, request_id="different")
        changed = replace(first, user_prompt="changed")

        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertNotEqual(first.fingerprint(), changed.fingerprint())
        self.assertNotIn("same", first.fingerprint())

    def test_response_serialization_omits_provider_exception(self):
        response = ModelResponse(
            request_id="r",
            status=ModelResponseStatus.PROVIDER_FAILED,
            provider_exception=RuntimeError("private exception"),
        )

        payload = response.to_dict()

        self.assertNotIn("provider_exception", payload)
        self.assertEqual(payload["status"], "PROVIDER_FAILED")

    def test_default_registry_contains_all_initial_profiles(self):
        registry = create_default_task_profile_registry()

        self.assertEqual(
            set(registry.describe()),
            {
                "LOCAL_CHOICE",
                "STRUCTURED_EXTRACTION",
                "TOOL_SELECTION",
                "CODE_REASONING",
                "MISSION_PLANNING",
                "RESEARCH",
                "ACADEMIC_RESEARCH",
                "DOCUMENT",
                "DOCUMENT_GENERATION",
                "DOCUMENT_REVIEW",
            },
        )
        for profile in registry.describe().values():
            self.assertGreater(profile["max_context_tokens"], 0)
            self.assertGreater(profile["max_output_tokens"], 0)
            self.assertTrue(profile["validation_pipeline"])
            self.assertTrue(profile["recovery_policy"])


class ContextBuilderTest(unittest.TestCase):
    def test_selects_relevant_context_and_justifies_every_decision(self):
        context = ContextBuilder().build(ContextBuildRequest(
            task_summary="focused task",
            candidates=(
                ContextCandidate(
                    source="symbol:a",
                    kind="symbol",
                    content="def a(): pass",
                    relevance_score=0.9,
                ),
                ContextCandidate(
                    source="history",
                    kind="full_history",
                    content="all prior messages",
                    relevance_score=1.0,
                ),
                ContextCandidate(
                    source="secret",
                    kind="evidence",
                    content="api_key=secret",
                    sensitive=True,
                ),
            ),
            allowed_kinds=("symbol", "full_history", "evidence"),
            max_items=2,
            max_chars=1_000,
        ))

        self.assertEqual(
            [item.source for item in context.items],
            ["symbol:a"],
        )
        self.assertEqual(len(context.decisions), 3)
        decisions = {item.source: item for item in context.decisions}
        self.assertEqual(
            decisions["history"].reason,
            "bulk_context_requires_explicit_request",
        )
        self.assertEqual(
            decisions["secret"].reason,
            "sensitive_context_not_authorized",
        )
        self.assertTrue(
            context.items[0].inclusion_reason.startswith(
                "relevance_score="
            )
        )

    def test_explicit_bulk_context_still_obeys_budget(self):
        context = ContextBuilder().build(ContextBuildRequest(
            task_summary="explicit",
            candidates=(ContextCandidate(
                source="mission",
                kind="full_mission",
                content="123456",
                explicitly_requested=True,
            ),),
            allowed_kinds=("full_mission",),
            max_chars=3,
        ))

        self.assertFalse(context.items)
        self.assertEqual(
            context.decisions[0].reason,
            "character_budget_exceeded",
        )


class ProviderAndRouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_registry_and_router_use_explicit_provider_and_model(self):
        captured = {}

        async def callback(model_request, model_route, _progress):
            captured["request"] = model_request
            captured["route"] = model_route
            return ProviderResult(raw_text="{}")

        provider = CallableModelProvider(
            "test",
            "fallback-model",
            callback,
        )
        providers = ProviderRegistry([provider])
        harness = ModelHarness(providers)
        response = await harness.execute(request())

        self.assertEqual(response.status, ModelResponseStatus.SUCCEEDED)
        self.assertEqual(captured["route"].provider, "test")
        self.assertEqual(captured["route"].model, "test-model")
        self.assertEqual(captured["request"].temperature, 0.0)
        self.assertEqual(
            captured["request"].max_output_tokens,
            16_384,
        )

    def test_registry_rejects_duplicate_provider(self):
        provider = CallableModelProvider(
            "test",
            "model",
            lambda *_args: "{}",
        )
        registry = ProviderRegistry([provider])

        with self.assertRaises(DuplicateProviderError):
            registry.register(provider)


class ModelValidationPipelineTest(unittest.TestCase):
    def test_layered_validation_passes_schema_enums_references_and_rule(self):
        expected = ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            schema={
                "type": "object",
                "required": ["status", "source"],
                "properties": {
                    "status": {"type": "string"},
                    "source": {"type": "string"},
                },
            },
            enum_constraints=(
                EnumConstraint("$.status", ("READY",)),
            ),
            reference_constraints=(
                ReferenceConstraint("$.source", ("file:a.py",)),
            ),
        )
        pipeline = ModelValidationPipeline([
            ValidationRule(
                stage=ValidationStage.ACCEPTANCE_CRITERIA,
                code="STATUS_REQUIRED",
                callback=lambda data, *_args: (
                    data["status"] == "READY",
                    "status must be READY",
                ),
            ),
        ])

        result = pipeline.validate(
            request(expected=expected),
            route(),
            ProviderResult(
                raw_text='{"status":"READY","source":"file:a.py"}'
            ),
            create_default_task_profile_registry().get(
                "STRUCTURED_EXTRACTION"
            ).validation_pipeline,
            expected,
        )

        self.assertEqual(result.status, ValidationStatus.PASSED)
        self.assertEqual(result.structured_output["status"], "READY")
        self.assertEqual(
            result.completed_stages[-1],
            ValidationStage.ACCEPTANCE_CRITERIA,
        )

    def test_parse_failure_reports_stage_reason_and_recoverability(self):
        expected = ExpectedOutput(format=OutputFormat.JSON)

        result = ModelValidationPipeline().validate(
            request(expected=expected),
            route(),
            ProviderResult(raw_text="{broken"),
            ("PARSING", "SCHEMA"),
            expected,
        )

        self.assertEqual(result.status, ValidationStatus.FAILED)
        self.assertEqual(
            result.issues[0].stage,
            ValidationStage.PARSING,
        )
        self.assertEqual(result.issues[0].code, "JSON_PARSE_FAILED")
        self.assertTrue(result.issues[0].recoverable)

    def test_deferred_validation_names_the_existing_owner(self):
        expected = ExpectedOutput(
            format=OutputFormat.JSON_SCHEMA,
            defer_validation=True,
            validation_owner="ProjectBuilder",
        )

        result = ModelValidationPipeline().validate(
            request(expected=expected),
            route(),
            ProviderResult(raw_text="not parsed here"),
            ("PARSING",),
            expected,
        )

        self.assertEqual(result.status, ValidationStatus.DEFERRED)
        self.assertEqual(result.delegated_to, "ProjectBuilder")


class RecoveryAndProgressTest(unittest.IsolatedAsyncioTestCase):
    def test_recovery_classifies_parse_mechanical_semantic_and_stop(self):
        coordinator = RecoveryCoordinator()
        progress = ProgressTracker().snapshot()

        def response(issue):
            return ModelResponse(
                request_id="r",
                status=ModelResponseStatus.VALIDATION_FAILED,
                validation=ValidationResult(
                    status=ValidationStatus.FAILED,
                    issues=(issue,),
                ),
            )

        parse = coordinator.decide(
            "STRUCTURED_CONSERVATIVE",
            response(ValidationIssue(
                ValidationStage.PARSING,
                "JSON_PARSE_FAILED",
                "$",
                "bad json",
                True,
            )),
            progress,
        )
        mechanical = coordinator.decide(
            "STRUCTURED_CONSERVATIVE",
            response(ValidationIssue(
                ValidationStage.PARSING,
                "OUTPUT_TRUNCATED",
                "$",
                "truncated",
                True,
            )),
            progress,
        )
        semantic = coordinator.decide(
            "STRUCTURED_CONSERVATIVE",
            response(ValidationIssue(
                ValidationStage.SCHEMA,
                "JSON_SCHEMA_FAILED",
                "$.x",
                "missing",
                True,
            )),
            progress,
        )
        stop = coordinator.decide(
            "STRUCTURED_CONSERVATIVE",
            response(ValidationIssue(
                ValidationStage.COMPATIBILITY,
                "UNSAFE",
                "$",
                "unsafe",
                False,
            )),
            progress,
        )

        self.assertEqual(parse.action, RecoveryAction.PARSE_RECOVERY)
        self.assertEqual(
            mechanical.action,
            RecoveryAction.MECHANICAL_COMPLETION,
        )
        self.assertEqual(semantic.action, RecoveryAction.SEMANTIC_RETRY)
        self.assertEqual(stop.action, RecoveryAction.STOP)

    def test_none_policy_never_requests_recovery(self):
        response = ModelResponse(
            request_id="r",
            status=ModelResponseStatus.VALIDATION_FAILED,
        )

        decision = RecoveryCoordinator().decide(
            "NONE",
            response,
            ProgressTracker().snapshot(),
        )

        self.assertEqual(decision.action, RecoveryAction.STOP)
        self.assertFalse(decision.retry_requested)

    async def test_recovery_rejects_an_identical_prompt(self):
        original = request()
        response = ModelResponse(
            request_id=original.request_id,
            status=ModelResponseStatus.VALIDATION_FAILED,
        )
        decision = RecoveryRecord(
            action=RecoveryAction.SEMANTIC_RETRY,
            reason="schema",
            recoverable=True,
            retry_requested=True,
        )
        coordinator = RecoveryCoordinator(
            transformer=lambda current, *_args: replace(
                current,
                request_id="new-id",
            )
        )

        with self.assertRaises(UnsafeRecoveryError):
            await coordinator.transform(original, response, decision)

    def test_progress_detects_repeated_outputs_tools_and_failures(self):
        tracker = ProgressTracker()
        tracker.record_input("same")
        tracker.record_output("same output")
        tracker.record_tool_call("read", {"path": "a"})
        tracker.record_failure("E")
        tracker.record_input("same")
        tracker.record_output("same output")
        tracker.record_tool_call("read", {"path": "a"})
        snapshot = tracker.record_failure("E")

        self.assertIn(
            ProgressCondition.NO_PROGRESS,
            snapshot.conditions,
        )
        self.assertIn(
            ProgressCondition.REPEATED_REASONING,
            snapshot.conditions,
        )
        self.assertIn(
            ProgressCondition.REPEATED_TOOL_CALLS,
            snapshot.conditions,
        )
        self.assertIn(
            ProgressCondition.REPEATED_FAILURES,
            snapshot.conditions,
        )


class ModelHarnessExecutionTest(unittest.IsolatedAsyncioTestCase):
    async def test_provider_failure_is_normalized_and_telemetry_has_no_prompt(self):
        secret = "SECRET_PROMPT_VALUE"

        async def fail(*_args):
            raise RuntimeError(secret)

        harness = ModelHarness(ProviderRegistry([
            CallableModelProvider("test", "test-model", fail)
        ]))
        model_request = request(
            user_prompt=secret,
            metadata={
                "consumer": "test",
                "secret": "do-not-log",
            },
        )
        response = await harness.execute(model_request)

        self.assertEqual(
            response.status,
            ModelResponseStatus.PROVIDER_FAILED,
        )
        self.assertIsInstance(
            response.provider_exception,
            RuntimeError,
        )
        serialized = json.dumps(
            harness.telemetry.snapshot(),
            ensure_ascii=False,
        )
        self.assertNotIn(secret, serialized)
        self.assertNotIn("do-not-log", serialized)
        self.assertIn(model_request.fingerprint(), serialized)

    async def test_changed_recovery_request_can_run_once(self):
        calls = 0

        async def callback(*_args):
            nonlocal calls
            calls += 1
            return "{broken" if calls == 1 else '{"ok": true}'

        async def transform_request(current, *_args):
            return replace(
                current,
                user_prompt=current.user_prompt + "\nReturn complete JSON.",
            )

        harness = ModelHarness(
            ProviderRegistry([
                CallableModelProvider(
                    "test",
                    "test-model",
                    callback,
                )
            ]),
            recovery=RecoveryCoordinator(
                transformer=transform_request
            ),
        )
        response = await harness.execute(request(
            constraints=ExecutionConstraints(
                max_attempts=2,
                allow_recovery=True,
            )
        ))

        self.assertEqual(calls, 2)
        self.assertEqual(
            response.status,
            ModelResponseStatus.SUCCEEDED,
        )
        self.assertTrue(response.recovery[0].input_changed)

    async def test_repeated_success_is_observed_as_no_progress_and_stopped(self):
        harness = ModelHarness(ProviderRegistry([
            CallableModelProvider(
                "test",
                "test-model",
                lambda *_args: "{}",
            )
        ]))
        metadata = {"progress_key": "same-operation"}

        first = await harness.execute(request(metadata=metadata))
        second = await harness.execute(request(metadata=metadata))

        self.assertEqual(first.status, ModelResponseStatus.SUCCEEDED)
        self.assertEqual(second.status, ModelResponseStatus.STOPPED)


if __name__ == "__main__":
    unittest.main()
