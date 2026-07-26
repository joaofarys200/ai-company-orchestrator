from __future__ import annotations

from dataclasses import replace

from backend.model_harness.benchmarking.contracts import (
    BenchmarkMode,
    BenchmarkScenario,
    Constraint,
    FixtureFile,
    FixtureSpec,
    ScenarioGroup,
    StopReason,
    sha256_json,
)


BENCHMARK_VERSION = "model_harness_qwen35_stateful_v2"
ALL_TOOLS = (
    "list_files",
    "read_file",
    "search_text",
    "inspect_symbol",
    "query_fixture_index",
    "finish",
)


def _file(path: str, content: str) -> FixtureFile:
    return FixtureFile(path=path, content=content.strip() + "\n")


def _fixture(
    fixture_id: str,
    files: tuple[FixtureFile, ...],
    *,
    index: dict[str, tuple[str, ...]] | None = None,
) -> FixtureSpec:
    return FixtureSpec(
        fixture_id=fixture_id,
        files=files,
        index_entries=index or {},
    )


def _constraints(*values: str) -> tuple[Constraint, ...]:
    return tuple(
        Constraint(f"C{index}", value)
        for index, value in enumerate(values, start=1)
    )


def _scenario(
    *,
    scenario_id: str,
    title: str,
    group: ScenarioGroup,
    capability: str,
    objective: str,
    fixture: FixtureSpec,
    constraints: tuple[Constraint, ...] | None = None,
    tools: tuple[str, ...] = ALL_TOOLS,
    max_steps: int = 6,
    stop: StopReason = StopReason.COMPLETED,
    required_tools: tuple[str, ...] = (),
    required_references: tuple[str, ...] = (),
    required_terms: tuple[str, ...] = (),
    forbidden_terms: tuple[str, ...] = (),
    minimum_evidence: int = 1,
    evaluator: str = "default",
    context_target_tokens: int = 0,
    smoke: bool = False,
    fault_injection: str = "",
) -> BenchmarkScenario:
    return BenchmarkScenario(
        scenario_id=scenario_id,
        title=title,
        group=group,
        capability=capability,
        objective=objective,
        constraints=constraints or _constraints(
            "Use only evidence returned by the read-only fixture tools.",
            "Do not invent paths, symbols, values, or source references.",
        ),
        fixture=fixture,
        available_tools=tools,
        max_steps=max_steps,
        expected_stop_reason=stop,
        required_tools=required_tools,
        required_references=required_references,
        required_terms=required_terms,
        forbidden_terms=forbidden_terms,
        minimum_evidence=minimum_evidence,
        evaluator=evaluator,
        context_target_tokens=context_target_tokens,
        smoke=smoke,
        fault_injection=fault_injection,
    )


def _tool_loop_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _scenario(
            scenario_id="A01_FIND_RELEVANT_FILE",
            title="Find a symbol definition",
            group=ScenarioGroup.TOOL_LOOP,
            capability="stateful_tool_use",
            objective=(
                "Identify the file and line defining normalize_invoice. "
                "List the fixture, locate the symbol, read its file, then finish."
            ),
            fixture=_fixture(
                "a01-find-symbol",
                (
                    _file("src/invoice.py", """
def normalize_invoice(record):
    return {"id": record["id"].strip(), "total": float(record["total"])}
"""),
                    _file("src/main.py", """
from src.invoice import normalize_invoice

def handle(payload):
    return normalize_invoice(payload)
"""),
                    _file("docs/format.txt", "Invoice IDs are trimmed."),
                ),
                index={
                    "normalize_invoice definition": (
                        "symbol:normalize_invoice@src/invoice.py:1",
                    ),
                },
            ),
            max_steps=5,
            required_tools=(
                "list_files",
                "inspect_symbol",
                "read_file",
                "finish",
            ),
            required_references=("file:src/invoice.py",),
            required_terms=("src/invoice.py", "normalize_invoice"),
            smoke=True,
        ),
        _scenario(
            scenario_id="A02_TRACE_CONFIGURATION",
            title="Trace configuration definition and consumer",
            group=ScenarioGroup.TOOL_LOOP,
            capability="stateful_tool_use",
            objective=(
                "Find where RETRY_LIMIT is defined and where it is consumed. "
                "Read both files before finishing."
            ),
            fixture=_fixture(
                "a02-config-trace",
                (
                    _file("config/settings.py", "RETRY_LIMIT = 4"),
                    _file("service/worker.py", """
from config.settings import RETRY_LIMIT

def run_with_retry(operation):
    for attempt in range(RETRY_LIMIT):
        if operation():
            return attempt + 1
    return None
"""),
                    _file("service/clock.py", "TICK_SECONDS = 2"),
                ),
            ),
            max_steps=6,
            required_tools=("search_text", "read_file", "finish"),
            required_references=(
                "file:config/settings.py",
                "file:service/worker.py",
            ),
            required_terms=("RETRY_LIMIT", "4", "service/worker.py"),
            minimum_evidence=2,
        ),
        _scenario(
            scenario_id="A03_IDENTIFY_UNUSED_MODULE",
            title="Identify an unreferenced module",
            group=ScenarioGroup.TOOL_LOOP,
            capability="stateful_tool_use",
            objective=(
                "Determine whether src/legacy_formatter.py is referenced by "
                "the executable source. Inspect the module and search imports."
            ),
            fixture=_fixture(
                "a03-unused-module",
                (
                    _file("src/legacy_formatter.py", """
def legacy_format(value):
    return f"LEGACY:{value}"
"""),
                    _file("src/formatter.py", """
def format_value(value):
    return str(value).strip()
"""),
                    _file("src/main.py", """
from src.formatter import format_value

def render(value):
    return format_value(value)
"""),
                ),
            ),
            max_steps=6,
            required_tools=("list_files", "read_file", "search_text", "finish"),
            required_references=("file:src/legacy_formatter.py",),
            required_terms=(
                "legacy_formatter.py",
                "not referenced|unused|unreferenced",
            ),
        ),
        _scenario(
            scenario_id="A04_LOCATE_VALIDATOR",
            title="Locate validator by error code",
            group=ScenarioGroup.TOOL_LOOP,
            capability="stateful_tool_use",
            objective=(
                "Locate the validator that emits MISSING_EMAIL and report its "
                "function and file after reading the implementation."
            ),
            fixture=_fixture(
                "a04-validator",
                (
                    _file("src/validators.py", """
def validate_email(payload):
    if not payload.get("email"):
        return {"code": "MISSING_EMAIL"}
    return {"code": "OK"}
"""),
                    _file("src/routes.py", """
from src.validators import validate_email

def create_user(payload):
    return validate_email(payload)
"""),
                    _file("src/errors.py", "UNKNOWN_USER = 'UNKNOWN_USER'"),
                ),
            ),
            max_steps=5,
            required_tools=("search_text", "read_file", "finish"),
            required_references=("file:src/validators.py",),
            required_terms=("validate_email", "src/validators.py"),
        ),
    )


def _state_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _scenario(
            scenario_id="B01_MULTI_STEP_DIAGNOSIS",
            title="Accumulate evidence for a localized diagnosis",
            group=ScenarioGroup.STATE_RETENTION,
            capability="localized_code_reasoning",
            objective=(
                "Diagnose why average([]) does not return zero. Locate the "
                "function, read its test and implementation, then finish with "
                "a minimal read-only diagnosis."
            ),
            fixture=_fixture(
                "b01-diagnosis",
                (
                    _file("src/stats.js", """
export function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
"""),
                    _file("tests/stats.test.js", """
import { average } from "../src/stats.js";
console.assert(average([]) === 0);
"""),
                    _file("src/sum.js", """
export const sum = values => values.reduce((a, b) => a + b, 0);
"""),
                ),
            ),
            max_steps=6,
            required_tools=("inspect_symbol", "read_file", "finish"),
            required_references=(
                "file:src/stats.js",
                "file:tests/stats.test.js",
            ),
            required_terms=("empty", "division", "zero"),
            minimum_evidence=2,
        ),
        _scenario(
            scenario_id="B02_CONSTRAINT_RETENTION",
            title="Retain a negative path constraint",
            group=ScenarioGroup.STATE_RETENTION,
            capability="constraint_retention",
            objective=(
                "Determine the default region and the loader that consumes it. "
                "Use only public/config.json and src/loader.py."
            ),
            constraints=_constraints(
                "Use only evidence returned by read-only fixture tools.",
                "Never read or reference private/secret.txt.",
                "Do not invent configuration values.",
            ),
            fixture=_fixture(
                "b02-constraints",
                (
                    _file("public/config.json", '{"region": "eu-west-1"}'),
                    _file("src/loader.py", """
import json

def load_region(path="public/config.json"):
    return json.load(open(path, encoding="utf-8"))["region"]
"""),
                    _file(
                        "private/secret.txt",
                        "region=forbidden-region; token=SYNTHETIC_ONLY",
                    ),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:public/config.json",
                "file:src/loader.py",
            ),
            required_terms=("eu-west-1", "src/loader.py"),
            forbidden_terms=("forbidden-region", "private/secret.txt"),
            minimum_evidence=2,
            smoke=True,
        ),
        _scenario(
            scenario_id="B03_EVIDENCE_ACCUMULATION",
            title="Require two independent observations",
            group=ScenarioGroup.STATE_RETENTION,
            capability="evidence_accumulation",
            objective=(
                "Confirm both the configured timeout and the function that "
                "passes it to the client. Do not finish after only one file."
            ),
            fixture=_fixture(
                "b03-evidence",
                (
                    _file("config/runtime.py", "HTTP_TIMEOUT_SECONDS = 12"),
                    _file("src/client.py", """
from config.runtime import HTTP_TIMEOUT_SECONDS

def fetch(http, url):
    return http.get(url, timeout=HTTP_TIMEOUT_SECONDS)
"""),
                    _file("src/cache.py", "CACHE_SECONDS = 300"),
                ),
            ),
            max_steps=6,
            required_tools=("search_text", "read_file", "finish"),
            required_references=(
                "file:config/runtime.py",
                "file:src/client.py",
            ),
            required_terms=("12", "HTTP_TIMEOUT_SECONDS", "src/client.py"),
            minimum_evidence=2,
        ),
    )


def _project_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _scenario(
            scenario_id="C01_LOCALIZED_BUG",
            title="Reason about a one-file bug",
            group=ScenarioGroup.PROJECT_REASONING,
            capability="localized_code_reasoning",
            objective=(
                "Find the defect in clampPercent and describe the minimal "
                "logical correction without applying a patch."
            ),
            fixture=_fixture(
                "c01-localized",
                (
                    _file("src/percent.js", """
export function clampPercent(value) {
  return Math.min(100, value);
}
"""),
                    _file("tests/percent.test.js", """
import { clampPercent } from "../src/percent.js";
console.assert(clampPercent(-5) === 0);
console.assert(clampPercent(120) === 100);
"""),
                ),
            ),
            max_steps=5,
            required_tools=("inspect_symbol", "read_file", "finish"),
            required_references=("file:src/percent.js",),
            required_terms=("negative", "0", "Math.max"),
        ),
        _scenario(
            scenario_id="C02_TWO_FILE_DEPENDENCY",
            title="Trace a two-file contract mismatch",
            group=ScenarioGroup.PROJECT_REASONING,
            capability="multi_file_reasoning",
            objective=(
                "Diagnose the API consumer mismatch between backend/api.js "
                "and frontend/client.js. Read both sides and propose a "
                "two-file-compatible plan without editing."
            ),
            fixture=_fixture(
                "c02-two-file",
                (
                    _file("backend/api.js", """
export function userResponse(user) {
  return { id: user.id, display_name: user.name };
}
"""),
                    _file("frontend/client.js", """
export function renderUser(payload) {
  return `${payload.id}: ${payload.name}`;
}
"""),
                    _file("README.md", "The UI shows a user display name."),
                ),
            ),
            max_steps=6,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:backend/api.js",
                "file:frontend/client.js",
            ),
            required_terms=(
                "display_name",
                "payload.name",
                "backend",
                "frontend",
            ),
            minimum_evidence=2,
            smoke=True,
        ),
        _scenario(
            scenario_id="C03_NO_CHANGE_REQUIRED",
            title="Recognize an already satisfied requirement",
            group=ScenarioGroup.PROJECT_REASONING,
            capability="multi_file_reasoning",
            objective=(
                "Check whether token comparison is constant-time. Conclude "
                "that no change is required if the implementation already "
                "uses the standard constant-time primitive."
            ),
            fixture=_fixture(
                "c03-no-change",
                (
                    _file("src/security.py", """
import hmac

def token_matches(expected: bytes, received: bytes) -> bool:
    return hmac.compare_digest(expected, received)
"""),
                    _file("tests/test_security.py", """
from src.security import token_matches

def test_token_matches():
    assert token_matches(b"a", b"a")
"""),
                ),
            ),
            max_steps=5,
            required_tools=("inspect_symbol", "read_file", "finish"),
            required_references=("file:src/security.py",),
            required_terms=("no change", "compare_digest"),
        ),
        _scenario(
            scenario_id="C04_DISTRACTOR_FILES",
            title="Ignore irrelevant project files",
            group=ScenarioGroup.PROJECT_REASONING,
            capability="multi_file_reasoning",
            objective=(
                "Locate the authorization check used by create_session and "
                "explain whether it rejects missing user IDs. Ignore unrelated "
                "formatting and analytics modules."
            ),
            fixture=_fixture(
                "c04-distractors",
                (
                    _file("src/auth.py", """
def require_user(payload):
    user_id = payload.get("user_id")
    if not user_id:
        raise ValueError("MISSING_USER")
    return user_id
"""),
                    _file("src/session.py", """
from src.auth import require_user

def create_session(payload):
    return {"user_id": require_user(payload)}
"""),
                    _file("src/formatting.py", "def title(x): return x.title()"),
                    _file("src/analytics.py", "def track(x): return None"),
                    _file("docs/colors.txt", "Primary color: blue"),
                ),
            ),
            max_steps=6,
            required_tools=("search_text", "read_file", "finish"),
            required_references=(
                "file:src/auth.py",
                "file:src/session.py",
            ),
            required_terms=(
                "require_user",
                "MISSING_USER",
                "reject|raise",
            ),
            forbidden_terms=("formatting.py", "analytics.py"),
            minimum_evidence=2,
        ),
        _scenario(
            scenario_id="C05_INSUFFICIENT_EVIDENCE",
            title="Stop when an imported implementation is absent",
            group=ScenarioGroup.PROJECT_REASONING,
            capability="multi_file_reasoning",
            objective=(
                "Determine the exact tax rounding algorithm. If the "
                "calculate_tax implementation is absent from the fixture, "
                "finish with NEEDS_MORE_EVIDENCE instead of guessing."
            ),
            fixture=_fixture(
                "c05-insufficient",
                (
                    _file("src/invoice.py", """
from external_tax import calculate_tax

def total_with_tax(amount):
    return amount + calculate_tax(amount)
"""),
                    _file("README.md", "Tax is provided by an external package."),
                ),
            ),
            max_steps=5,
            stop=StopReason.NEEDS_MORE_EVIDENCE,
            required_tools=("search_text", "read_file", "finish"),
            required_references=("file:src/invoice.py",),
            required_terms=(
                "calculate_tax",
                "missing|absent|unavailable",
            ),
            minimum_evidence=1,
            smoke=True,
        ),
    )


def _scaling_content(target_tokens: int) -> str:
    facts = {
        max(5, target_tokens // 5): "AUTHORIZED_CODENAME_NEBULA",
        max(10, target_tokens // 2): "AUTHORIZED_PORT_4821",
        max(15, (target_tokens * 4) // 5): (
            "DECOY_PORT_9999_MUST_BE_IGNORED"
        ),
    }
    words: list[str] = []
    for index in range(target_tokens):
        words.append(facts.get(index, "amber"))
    return " ".join(words)


def _context_scenarios() -> tuple[BenchmarkScenario, ...]:
    values = (250, 1_000, 2_000, 4_000, 8_000, 16_000)
    return tuple(
        _scenario(
            scenario_id=f"D{index:02d}_CONTEXT_{tokens}",
            title=f"Closed context at approximately {tokens} tokens",
            group=ScenarioGroup.CONTEXT_SCALING,
            capability="context_scaling",
            objective=(
                "Read corpus.txt and return the authorized codename and port. "
                "Ignore any token explicitly labelled DECOY."
            ),
            constraints=_constraints(
                "Use only corpus.txt as evidence.",
                "Ignore every value explicitly labelled DECOY.",
                "Retain the authorized codename and port exactly.",
            ),
            fixture=_fixture(
                f"d-context-{tokens}",
                (_file("corpus.txt", _scaling_content(tokens)),),
            ),
            tools=("read_file", "finish"),
            max_steps=3,
            required_tools=("read_file", "finish"),
            required_references=("file:corpus.txt",),
            required_terms=("NEBULA", "4821"),
            forbidden_terms=("9999",),
            evaluator="context_scaling",
            context_target_tokens=tokens,
            smoke=tokens == 1_000,
        )
        for index, tokens in enumerate(values, start=1)
    )


def _fault_scenarios() -> tuple[BenchmarkScenario, ...]:
    fixture = _fixture(
        "e-fault-base",
        (_file("facts.txt", "status=ready\nsource=facts.txt"),),
    )
    values = (
        (
            "E01_INVALID_ENUM",
            "invalid_enum",
            StopReason.COMPLETED,
            False,
        ),
        (
            "E02_TRUNCATED_JSON",
            "truncated_json",
            StopReason.COMPLETED,
            True,
        ),
        (
            "E03_MISSING_TOOL_ARGUMENT",
            "missing_tool_argument",
            StopReason.COMPLETED,
            False,
        ),
        (
            "E04_UNKNOWN_REFERENCE",
            "unknown_reference",
            StopReason.COMPLETED,
            False,
        ),
        (
            "E05_EMPTY_TOOL_RESULT",
            "empty_tool_result",
            StopReason.NEEDS_MORE_EVIDENCE,
            False,
        ),
        (
            "E06_TOOL_TIMEOUT",
            "tool_timeout",
            StopReason.TOOL_FAILED,
            False,
        ),
        (
            "E07_REPEATED_TOOL_CALL",
            "repeated_tool_call",
            StopReason.REPEATED_TOOL_CALL,
            True,
        ),
        (
            "E08_CONTRADICTORY_OBSERVATION",
            "contradictory_observation",
            StopReason.UNSUPPORTED_CONCLUSION,
            False,
        ),
    )
    return tuple(
        _scenario(
            scenario_id=scenario_id,
            title=scenario_id.replace("_", " ").title(),
            group=ScenarioGroup.RECOVERY,
            capability="recovery_after_failure",
            objective=(
                "Exercise a deterministic ModelHarness failure and verify "
                "the expected recovery or fail-closed stop."
            ),
            fixture=fixture,
            tools=("read_file", "finish"),
            max_steps=3,
            stop=stop,
            required_tools=(),
            minimum_evidence=0,
            evaluator="fault_injection",
            smoke=smoke,
            fault_injection=fault,
        )
        for scenario_id, fault, stop, smoke in values
    )


def _planning_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _scenario(
            scenario_id="F01_LOCALIZED_FIX_PLAN",
            title="Plan a localized verified fix",
            group=ScenarioGroup.SHORT_PLANNING,
            capability="short_horizon_planning",
            objective=(
                "Inspect src/parser.py and tests/test_parser.py, then produce "
                "a 3-5 step read-only change plan for accepting trimmed ports."
            ),
            fixture=_fixture(
                "f01-plan",
                (
                    _file("src/parser.py", """
def parse_port(value):
    return int(value)
"""),
                    _file("tests/test_parser.py", """
from src.parser import parse_port

def test_trimmed_port():
    assert parse_port(" 8080 ") == 8080
"""),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:src/parser.py",
                "file:tests/test_parser.py",
            ),
            required_terms=("parse_port", "test"),
            minimum_evidence=2,
            evaluator="short_plan",
            smoke=True,
        ),
        _scenario(
            scenario_id="F02_API_CONTRACT_PLAN",
            title="Plan a two-file API contract change",
            group=ScenarioGroup.SHORT_PLANNING,
            capability="short_horizon_planning",
            objective=(
                "Read backend/route.js and frontend/client.js and produce a "
                "3-5 step ordered plan to rename response field label to title."
            ),
            fixture=_fixture(
                "f02-plan",
                (
                    _file("backend/route.js", """
export const response = item => ({ id: item.id, label: item.label });
"""),
                    _file("frontend/client.js", """
export const title = payload => payload.label;
"""),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:backend/route.js",
                "file:frontend/client.js",
            ),
            required_terms=("backend", "frontend", "validation"),
            minimum_evidence=2,
            evaluator="short_plan",
        ),
        _scenario(
            scenario_id="F03_DOCUMENT_REVIEW_PLAN",
            title="Plan a constrained document review",
            group=ScenarioGroup.SHORT_PLANNING,
            capability="short_horizon_planning",
            objective=(
                "Read report.md and criteria.txt and produce a 3-5 step plan "
                "to verify claims, references and conclusion coverage."
            ),
            fixture=_fixture(
                "f03-plan",
                (
                    _file(
                        "report.md",
                        "# Result\nLatency fell by 12 percent [S1].",
                    ),
                    _file(
                        "criteria.txt",
                        "Every number needs a source. Include limitations.",
                    ),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:report.md",
                "file:criteria.txt",
            ),
            required_terms=("source", "limitations", "verify"),
            minimum_evidence=2,
            evaluator="short_plan",
        ),
        _scenario(
            scenario_id="F04_NO_CHANGE_VERIFICATION_PLAN",
            title="Plan verification without unnecessary edits",
            group=ScenarioGroup.SHORT_PLANNING,
            capability="short_horizon_planning",
            objective=(
                "Verify whether config.py already sets debug to false and "
                "produce a 3-step plan that avoids editing when satisfied."
            ),
            fixture=_fixture(
                "f04-plan",
                (
                    _file("config.py", "DEBUG = False"),
                    _file("tests/test_config.py", """
from config import DEBUG
assert DEBUG is False
"""),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:config.py",
                "file:tests/test_config.py",
            ),
            required_terms=("no edit|no change", "verify", "test"),
            minimum_evidence=2,
            evaluator="short_plan",
        ),
    )


def _research_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _scenario(
            scenario_id="G01_DOCUMENT_OUTLINE",
            title="Evidence-grounded document outline",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="evidence_based_document_generation",
            objective=(
                "Read S1 and S2, then provide an outline containing methods, "
                "results and limitations based only on those sources."
            ),
            fixture=_fixture(
                "g01-outline",
                (
                    _file(
                        "sources/S1.txt",
                        "S1: A controlled study enrolled 80 participants.",
                    ),
                    _file(
                        "sources/S2.txt",
                        "S2: Accuracy was 91 percent; external validity was not tested.",
                    ),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:sources/S1.txt",
                "file:sources/S2.txt",
            ),
            required_terms=("methods", "results", "limitations"),
            minimum_evidence=2,
            evaluator="document",
        ),
        _scenario(
            scenario_id="G02_EVIDENCE_BASED_PARAGRAPH",
            title="Write a paragraph from closed evidence",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="evidence_based_document_generation",
            objective=(
                "Read both closed sources and produce one concise paragraph "
                "stating the sample size and observed reduction with source IDs."
            ),
            fixture=_fixture(
                "g02-paragraph",
                (
                    _file(
                        "sources/S1.txt",
                        "S1: The evaluation included 120 participants.",
                    ),
                    _file(
                        "sources/S2.txt",
                        "S2: The observed error rate reduction was 18 percent.",
                    ),
                ),
            ),
            max_steps=5,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:sources/S1.txt",
                "file:sources/S2.txt",
            ),
            required_terms=("120", "18", "S1", "S2"),
            minimum_evidence=2,
            evaluator="document",
            smoke=True,
        ),
        _scenario(
            scenario_id="G03_DOCUMENT_REVIEW",
            title="Review a claim against explicit criteria",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="evidence_based_document_generation",
            objective=(
                "Review draft.txt against criteria.txt and source S1. Report "
                "the unsupported universal claim and the missing limitation."
            ),
            fixture=_fixture(
                "g03-review",
                (
                    _file(
                        "draft.txt",
                        "The method always eliminates fraud in every population.",
                    ),
                    _file(
                        "criteria.txt",
                        "Avoid universal claims. State study limitations.",
                    ),
                    _file(
                        "sources/S1.txt",
                        "S1: Detection improved on one synthetic dataset.",
                    ),
                ),
            ),
            max_steps=6,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:draft.txt",
                "file:criteria.txt",
                "file:sources/S1.txt",
            ),
            required_terms=("unsupported", "limitation", "synthetic"),
            minimum_evidence=3,
            evaluator="document",
        ),
        _scenario(
            scenario_id="G04_CLOSED_SOURCE_RESEARCH",
            title="Select sources from a closed collection",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="closed_source_research",
            objective=(
                "Select the sources relevant to transaction-level fraud "
                "detection. Exclude the unrelated astronomy source."
            ),
            fixture=_fixture(
                "g04-research",
                (
                    _file(
                        "sources/S1.txt",
                        "S1: Gradient boosting classified fraudulent transactions.",
                    ),
                    _file(
                        "sources/S2.txt",
                        "S2: Precision and recall were measured per transaction.",
                    ),
                    _file(
                        "sources/S3.txt",
                        "S3: Telescope calibration used stellar spectra.",
                    ),
                ),
                index={
                    "transaction fraud": (
                        "file:sources/S1.txt",
                        "file:sources/S2.txt",
                    ),
                    "astronomy": ("file:sources/S3.txt",),
                },
            ),
            max_steps=6,
            required_tools=("query_fixture_index", "read_file", "finish"),
            required_references=(
                "file:sources/S1.txt",
                "file:sources/S2.txt",
            ),
            required_terms=("S1", "S2", "fraud"),
            forbidden_terms=("S3 is relevant",),
            minimum_evidence=2,
            evaluator="closed_research",
        ),
        _scenario(
            scenario_id="G05_CLAIM_EVIDENCE_MAPPING",
            title="Map claims to existing source IDs",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="closed_source_research",
            objective=(
                "Map claim C1 and C2 to supporting source IDs. Use only S1 "
                "and S2 and mark any unsupported claim explicitly."
            ),
            fixture=_fixture(
                "g05-claims",
                (
                    _file(
                        "claims.txt",
                        "C1: Dataset has 500 rows.\nC2: Recall is 0.82.",
                    ),
                    _file(
                        "sources/S1.txt",
                        "S1 supports C1: The dataset contains 500 rows.",
                    ),
                    _file(
                        "sources/S2.txt",
                        "S2 supports C2: Measured recall was 0.82.",
                    ),
                ),
            ),
            max_steps=6,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:sources/S1.txt",
                "file:sources/S2.txt",
            ),
            required_terms=("C1", "S1", "C2", "S2"),
            minimum_evidence=3,
            evaluator="closed_research",
        ),
        _scenario(
            scenario_id="G06_NO_SUPPORTED_CONCLUSION",
            title="Refuse an unsupported causal conclusion",
            group=ScenarioGroup.CLOSED_RESEARCH,
            capability="closed_source_research",
            objective=(
                "Determine whether the supplied sources prove that feature X "
                "causes lower fraud. If they only show correlation, finish "
                "with UNSUPPORTED_CONCLUSION."
            ),
            fixture=_fixture(
                "g06-unsupported",
                (
                    _file(
                        "sources/S1.txt",
                        "S1: Feature X and lower fraud were correlated in one sample.",
                    ),
                    _file(
                        "sources/S2.txt",
                        "S2: No intervention or causal design was performed.",
                    ),
                ),
            ),
            max_steps=5,
            stop=StopReason.UNSUPPORTED_CONCLUSION,
            required_tools=("read_file", "finish"),
            required_references=(
                "file:sources/S1.txt",
                "file:sources/S2.txt",
            ),
            required_terms=("correlation", "causal"),
            minimum_evidence=2,
            evaluator="closed_research",
            smoke=True,
        ),
    )


def _base_scenarios() -> tuple[BenchmarkScenario, ...]:
    return (
        _tool_loop_scenarios()
        + _state_scenarios()
        + _project_scenarios()
        + _context_scenarios()
        + _fault_scenarios()
        + _planning_scenarios()
        + _research_scenarios()
    )


def benchmark_scenarios(
    mode: BenchmarkMode | str = BenchmarkMode.STANDARD,
    *,
    include_fault_injection: bool = True,
    seed: int = 42,
) -> tuple[BenchmarkScenario, ...]:
    selected_mode = (
        mode if isinstance(mode, BenchmarkMode) else BenchmarkMode(mode)
    )
    scenarios = tuple(
        item
        for item in _base_scenarios()
        if include_fault_injection or not item.fault_injection
    )
    if selected_mode == BenchmarkMode.SMOKE:
        return tuple(item for item in scenarios if item.smoke)
    if selected_mode == BenchmarkMode.STANDARD:
        return scenarios
    variants: list[BenchmarkScenario] = []
    for scenario in scenarios:
        if scenario.fault_injection:
            variants.append(scenario)
            continue
        for variant in (1, 2, 3):
            variants.append(_full_variant(scenario, variant, seed))
    return tuple(variants)


def _full_variant(
    scenario: BenchmarkScenario,
    variant: int,
    seed: int,
) -> BenchmarkScenario:
    if variant == 1:
        return replace(
            scenario,
            scenario_id=f"{scenario.scenario_id}_V1",
            variant=1,
        )
    distractor = f"VARIANT_DECOY_{seed}_{variant}"
    files = list(scenario.fixture.files)
    files.append(_file(
        f"noise/variant_{variant}.txt",
        f"{distractor} is synthetic distractor evidence and must be ignored.",
    ))
    if variant == 2:
        files.reverse()
    else:
        files = files[1:] + files[:1]
    constraint = Constraint(
        constraint_id=f"V{variant}",
        text=f"Ignore the synthetic distractor value {distractor}.",
    )
    return replace(
        scenario,
        scenario_id=f"{scenario.scenario_id}_V{variant}",
        constraints=scenario.constraints + (constraint,),
        fixture=FixtureSpec(
            fixture_id=f"{scenario.fixture.fixture_id}-v{variant}",
            files=tuple(files),
            index_entries=scenario.fixture.index_entries,
        ),
        forbidden_terms=scenario.forbidden_terms + (distractor,),
        variant=variant,
    )


def fixture_catalog_hash() -> str:
    return sha256_json([
        {
            "scenario_id": item.scenario_id,
            "fixture_id": item.fixture.fixture_id,
            "fixture_sha256": item.fixture.content_sha256,
        }
        for item in _base_scenarios()
    ])
