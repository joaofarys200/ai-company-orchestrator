import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PROVIDER = Path(
    "backend/model_harness/providers/ollama.py"
)
OFFICIAL_PROVIDER_DIRECTORY = Path("backend/model_harness/providers")
EXCLUDED_PREFIXES = (
    Path("tests"),
    Path("scripts"),
    Path("diagnostics"),
    Path("workspace"),
    Path("backend/model_harness/benchmarking"),
    Path("venv"),
    Path(".venv"),
)
EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
}
FORBIDDEN_TRANSPORT_PATTERNS = {
    "ollama_base_url": re.compile(
        r"(?:localhost|127\.0\.0\.1):11434",
        re.IGNORECASE,
    ),
    "ollama_http_endpoint": re.compile(
        r"[\"']/api/(?:chat|generate)[\"']",
        re.IGNORECASE,
    ),
    "ollama_sdk_transport": re.compile(
        r"\bollama\.(?:chat|generate)\s*\(",
        re.IGNORECASE,
    ),
}
FORBIDDEN_MODEL_TRANSPORT_PATTERNS = {
    "gemini_http_endpoint": re.compile(
        r"generativelanguage\.googleapis\.com/.+/(?:chat|generate)",
        re.IGNORECASE,
    ),
    "anthropic_http_endpoint": re.compile(
        r"api\.anthropic\.com/(?:v1/)?messages",
        re.IGNORECASE,
    ),
    "anthropic_sdk_transport": re.compile(
        r"\banthropic\.Anthropic\s*\(",
        re.IGNORECASE,
    ),
}


def productive_python_files():
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative == OFFICIAL_PROVIDER:
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if any(
            relative == prefix or prefix in relative.parents
            for prefix in EXCLUDED_PREFIXES
        ):
            continue
        yield relative, path


class ModelTransportArchitectureTest(unittest.TestCase):
    def test_ollama_transport_exists_only_in_official_provider(self):
        violations = []
        for relative, path in productive_python_files():
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            for label, pattern in FORBIDDEN_TRANSPORT_PATTERNS.items():
                for match in pattern.finditer(source):
                    line = source.count("\n", 0, match.start()) + 1
                    violations.append(
                        f"{relative.as_posix()}:{line}: {label}"
                    )
        self.assertEqual(
            violations,
            [],
            "Transporte Ollama produtivo fora do provider oficial:\n"
            + "\n".join(violations),
        )

    def test_model_transports_exist_only_in_official_providers(self):
        violations = []
        for relative, path in productive_python_files():
            if (
                relative == OFFICIAL_PROVIDER_DIRECTORY
                or OFFICIAL_PROVIDER_DIRECTORY in relative.parents
            ):
                continue
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            for label, pattern in (
                FORBIDDEN_MODEL_TRANSPORT_PATTERNS.items()
            ):
                for match in pattern.finditer(source):
                    line = source.count("\n", 0, match.start()) + 1
                    violations.append(
                        f"{relative.as_posix()}:{line}: {label}"
                    )
        self.assertEqual(
            violations,
            [],
            "Transporte de modelo produtivo fora dos providers oficiais:\n"
            + "\n".join(violations),
        )

    def test_known_local_consumers_use_model_harness(self):
        expectations = {
            Path("server.py"): "ModelExecutionService",
            Path("agents/orchestrator/__init__.py"):
                "get_model_harness",
            Path("agents/orchestrator/project_builder.py"):
                "get_model_harness",
            Path("agents/providers/ollama.py"):
                "get_model_harness",
            Path("intelligence/coding_session.py"):
                "ModelHarnessPlanRequester",
        }
        for relative, boundary in expectations.items():
            with self.subTest(path=relative.as_posix()):
                source = (ROOT / relative).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertIn(boundary, source)


if __name__ == "__main__":
    unittest.main()
