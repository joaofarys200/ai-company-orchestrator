from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from jsonschema import Draft202012Validator

from backend.model_harness.benchmarking.contracts import (
    FixtureSpec,
    ToolDefinition,
    ToolObservation,
    ToolRequest,
    ToolStatus,
    sha256_json,
)


class BenchmarkToolError(RuntimeError):
    pass


class BenchmarkPathError(BenchmarkToolError):
    pass


class BenchmarkToolTimeout(BenchmarkToolError):
    pass


ToolExecutor = Callable[
    ["FixtureSandbox", Mapping[str, Any]],
    Mapping[str, Any],
]


class FixtureSandbox:
    """Temporary, text-only fixture root with strict path containment."""

    def __init__(self, fixture: FixtureSpec):
        self.fixture = fixture
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.root: Path | None = None

    def __enter__(self) -> FixtureSandbox:
        self._temporary = tempfile.TemporaryDirectory(
            prefix=f"model-harness-{self.fixture.fixture_id}-"
        )
        self.root = Path(self._temporary.name).resolve()
        for fixture_file in self.fixture.files:
            target = self.resolve_path(
                fixture_file.path,
                must_exist=False,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                fixture_file.content,
                encoding="utf-8",
                newline="",
            )
        return self

    def __exit__(self, *_args: object) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None
        self.root = None

    def resolve_path(
        self,
        value: str | None,
        *,
        must_exist: bool = True,
        allow_directory: bool = True,
    ) -> Path:
        if self.root is None:
            raise BenchmarkToolError("FixtureSandbox ainda nao foi aberto.")
        normalized = self.normalize_relative_path(value)
        candidate = (self.root / normalized).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise BenchmarkPathError(
                "Path fora da fixture foi bloqueado."
            ) from exc
        current = self.root
        for part in normalized.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise BenchmarkPathError(
                    "Symlinks nao sao permitidos na fixture."
                )
        if must_exist and not candidate.exists():
            raise BenchmarkPathError(
                f"Path inexistente na fixture: {normalized.as_posix()}."
            )
        if (
            must_exist
            and not allow_directory
            and not candidate.is_file()
        ):
            raise BenchmarkPathError(
                f"O path nao e um ficheiro: {normalized.as_posix()}."
            )
        return candidate

    @staticmethod
    def normalize_relative_path(value: str | None) -> PurePosixPath:
        raw = str(value or ".").strip().replace("\\", "/")
        if "\x00" in raw:
            raise BenchmarkPathError("Path contem byte nulo.")
        windows = PureWindowsPath(raw)
        posix = PurePosixPath(raw)
        if (
            windows.is_absolute()
            or windows.drive
            or posix.is_absolute()
            or raw.startswith(("//", "\\\\"))
        ):
            raise BenchmarkPathError("Paths absolutos nao sao permitidos.")
        if any(part == ".." for part in posix.parts):
            raise BenchmarkPathError("Path traversal foi bloqueado.")
        cleaned = PurePosixPath(*(
            part for part in posix.parts if part not in ("", ".")
        ))
        return cleaned if cleaned.parts else PurePosixPath(".")

    def relative(self, path: Path) -> str:
        if self.root is None:
            raise BenchmarkToolError("FixtureSandbox ainda nao foi aberto.")
        return path.resolve().relative_to(self.root).as_posix()


class BenchmarkToolRegistry:
    def __init__(self):
        self._definitions: dict[str, ToolDefinition] = {}
        self._executors: dict[str, ToolExecutor] = {}

    def register(
        self,
        definition: ToolDefinition,
        executor: ToolExecutor,
    ) -> None:
        if definition.name in self._definitions:
            raise ValueError(
                f"Tool duplicada no benchmark: {definition.name}."
            )
        if not definition.read_only:
            raise ValueError("Benchmark aceita apenas tools read-only.")
        self._definitions[definition.name] = definition
        self._executors[definition.name] = executor

    def definition(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise BenchmarkToolError(
                f"Tool nao registada: {name}."
            ) from exc

    def definitions(
        self,
        allowed: tuple[str, ...] | None = None,
    ) -> tuple[ToolDefinition, ...]:
        names = allowed or tuple(self._definitions)
        return tuple(self.definition(name) for name in names)

    def names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def execute(
        self,
        sandbox: FixtureSandbox,
        request: ToolRequest,
        *,
        injected_fault: str = "",
    ) -> ToolObservation:
        if request.name not in self._definitions:
            return self._error_observation(
                request.name,
                ToolStatus.BLOCKED,
                "TOOL_UNAVAILABLE",
                "Tool fora do registry read-only.",
            )
        definition = self._definitions[request.name]
        errors = sorted(
            Draft202012Validator(
                dict(definition.input_schema)
            ).iter_errors(dict(request.arguments)),
            key=lambda item: tuple(str(part) for part in item.path),
        )
        if errors:
            return self._error_observation(
                request.name,
                ToolStatus.BLOCKED,
                "TOOL_ARGUMENT_INVALID",
                errors[0].message,
            )
        if injected_fault == "timeout":
            return self._error_observation(
                request.name,
                ToolStatus.TIMED_OUT,
                "TOOL_TIMEOUT",
                "Timeout deterministico injetado.",
            )
        try:
            raw = dict(
                self._executors[request.name](
                    sandbox,
                    dict(request.arguments),
                )
            )
        except BenchmarkPathError as exc:
            return self._error_observation(
                request.name,
                ToolStatus.BLOCKED,
                "PATH_BLOCKED",
                str(exc),
            )
        except BenchmarkToolTimeout as exc:
            return self._error_observation(
                request.name,
                ToolStatus.TIMED_OUT,
                "TOOL_TIMEOUT",
                str(exc),
            )
        except Exception as exc:
            return self._error_observation(
                request.name,
                ToolStatus.FAILED,
                type(exc).__name__,
                str(exc),
            )
        if injected_fault == "empty":
            raw = {"matches": [], "files": [], "injected": True}
        references = _references(raw)
        status = (
            ToolStatus.EMPTY if _is_empty_result(raw) else ToolStatus.SUCCEEDED
        )
        raw_context = json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ToolObservation(
            tool_name=request.name,
            status=status,
            result=_report_projection(raw),
            references=references,
            result_sha256=hashlib.sha256(
                raw_context.encode("utf-8")
            ).hexdigest(),
            summary=_summary(request.name, raw, status),
            raw_context=raw_context,
        )

    @staticmethod
    def _error_observation(
        tool_name: str,
        status: ToolStatus,
        code: str,
        message: str,
    ) -> ToolObservation:
        raw = {"error_code": code, "message": message}
        return ToolObservation(
            tool_name=tool_name,
            status=status,
            result=raw,
            references=(),
            result_sha256=sha256_json(raw),
            summary=f"{code}: {message}",
            error_code=code,
            raw_context=json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )


def create_read_only_tool_registry() -> BenchmarkToolRegistry:
    registry = BenchmarkToolRegistry()
    registry.register(
        ToolDefinition(
            name="list_files",
            description=(
                "List relative fixture files below an optional relative path."
            ),
            input_schema=_object_schema({
                "path": {"type": "string"},
            }),
        ),
        _list_files,
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description=(
                "Read one UTF-8 text file from the fixture. Paths are relative."
            ),
            input_schema=_object_schema(
                {
                    "path": {"type": "string", "minLength": 1},
                    "max_chars": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 250_000,
                    },
                },
                required=("path",),
            ),
        ),
        _read_file,
    )
    registry.register(
        ToolDefinition(
            name="search_text",
            description=(
                "Search literal text in fixture files and return paths and lines."
            ),
            input_schema=_object_schema(
                {
                    "query": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                required=("query",),
            ),
        ),
        _search_text,
    )
    registry.register(
        ToolDefinition(
            name="inspect_symbol",
            description=(
                "Locate a Python or JavaScript symbol definition in fixture files."
            ),
            input_schema=_object_schema(
                {
                    "symbol": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                },
                required=("symbol",),
            ),
        ),
        _inspect_symbol,
    )
    registry.register(
        ToolDefinition(
            name="query_fixture_index",
            description=(
                "Query the closed fixture index for known source references."
            ),
            input_schema=_object_schema(
                {"query": {"type": "string", "minLength": 1}},
                required=("query",),
            ),
        ),
        _query_fixture_index,
    )
    registry.register(
        ToolDefinition(
            name="finish",
            description=(
                "Finish with a supported conclusion and explicit stop reason."
            ),
            input_schema=_object_schema(
                {
                    "conclusion": {"type": "string"},
                    "stop_reason": {
                        "type": "string",
                        "enum": [
                            "COMPLETED",
                            "NEEDS_MORE_EVIDENCE",
                            "UNSUPPORTED_CONCLUSION",
                        ],
                    },
                },
                required=("conclusion", "stop_reason"),
            ),
        ),
        _finish,
    )
    return registry


def _object_schema(
    properties: Mapping[str, Any],
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def _list_files(
    sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    base = sandbox.resolve_path(
        str(arguments.get("path") or "."),
        allow_directory=True,
    )
    paths = (
        [sandbox.relative(base)]
        if base.is_file()
        else sorted(
            sandbox.relative(item)
            for item in base.rglob("*")
            if item.is_file() and not item.is_symlink()
        )
    )
    return {"files": paths, "count": len(paths)}


def _read_file(
    sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    path = sandbox.resolve_path(
        str(arguments["path"]),
        allow_directory=False,
    )
    max_chars = int(arguments.get("max_chars") or 250_000)
    content = path.read_text(encoding="utf-8")
    truncated = len(content) > max_chars
    selected = content[:max_chars]
    return {
        "path": sandbox.relative(path),
        "content": selected,
        "size_chars": len(content),
        "line_count": content.count("\n") + 1,
        "truncated": truncated,
        "content_sha256": hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
    }


def _search_text(
    sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    query = str(arguments["query"])
    max_results = int(arguments.get("max_results") or 20)
    base = sandbox.resolve_path(
        str(arguments.get("path") or "."),
        allow_directory=True,
    )
    candidates = [base] if base.is_file() else sorted(base.rglob("*"))
    matches: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if query.casefold() in line.casefold():
                matches.append({
                    "reference": (
                        f"file:{sandbox.relative(path)}:{line_number}"
                    ),
                    "path": sandbox.relative(path),
                    "line": line_number,
                    "text": line[:500],
                })
                if len(matches) >= max_results:
                    return {
                        "query": query,
                        "matches": matches,
                        "truncated": True,
                    }
    return {"query": query, "matches": matches, "truncated": False}


def _inspect_symbol(
    sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    symbol = str(arguments["symbol"])
    base = sandbox.resolve_path(
        str(arguments.get("path") or "."),
        allow_directory=True,
    )
    candidates = [base] if base.is_file() else sorted(base.rglob("*"))
    escaped = re.escape(symbol)
    patterns = (
        ("function", re.compile(
            rf"^\s*(?:async\s+)?(?:def|function)\s+{escaped}\b"
        )),
        ("class", re.compile(rf"^\s*class\s+{escaped}\b")),
        ("binding", re.compile(
            rf"^\s*(?:const|let|var)\s+{escaped}\b"
        )),
    )
    matches: list[dict[str, Any]] = []
    for path in candidates:
        if (
            not path.is_file()
            or path.is_symlink()
            or path.suffix.lower() not in {
                ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx"
            }
        ):
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            kind = next(
                (name for name, pattern in patterns if pattern.search(line)),
                "",
            )
            if kind:
                matches.append({
                    "reference": (
                        f"symbol:{symbol}@{sandbox.relative(path)}:{line_number}"
                    ),
                    "path": sandbox.relative(path),
                    "line": line_number,
                    "kind": kind,
                    "text": line[:500],
                })
    return {"symbol": symbol, "matches": matches}


def _query_fixture_index(
    sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    query = str(arguments["query"]).casefold()
    matches: list[dict[str, Any]] = []
    for key, references in sorted(sandbox.fixture.index_entries.items()):
        if query in key.casefold():
            matches.append({
                "key": key,
                "references": list(references),
            })
    return {"query": arguments["query"], "matches": matches}


def _finish(
    _sandbox: FixtureSandbox,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "accepted": True,
        "conclusion_sha256": hashlib.sha256(
            str(arguments["conclusion"]).encode("utf-8")
        ).hexdigest(),
        "stop_reason": arguments["stop_reason"],
    }


def _references(raw: Mapping[str, Any]) -> tuple[str, ...]:
    found: list[str] = []
    path = raw.get("path")
    if isinstance(path, str) and path:
        found.append(f"file:{path}")
    for path_value in raw.get("files") or ():
        if isinstance(path_value, str):
            found.append(f"file:{path_value}")
    for match in raw.get("matches") or ():
        if not isinstance(match, Mapping):
            continue
        reference = match.get("reference")
        if isinstance(reference, str):
            found.append(reference)
        for nested in match.get("references") or ():
            if isinstance(nested, str):
                found.append(nested)
    return tuple(dict.fromkeys(found))


def _is_empty_result(raw: Mapping[str, Any]) -> bool:
    if "content" in raw:
        return not bool(raw.get("content"))
    for key in ("matches", "files"):
        if key in raw:
            return not bool(raw.get(key))
    return False


def _report_projection(raw: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "accepted",
        "content_sha256",
        "conclusion_sha256",
        "count",
        "injected",
        "line_count",
        "path",
        "query",
        "size_chars",
        "stop_reason",
        "symbol",
        "truncated",
    }
    result = {
        key: value
        for key, value in raw.items()
        if key in allowed
    }
    if "files" in raw:
        result["file_count"] = len(raw.get("files") or ())
    if "matches" in raw:
        result["match_count"] = len(raw.get("matches") or ())
    return result


def _summary(
    tool_name: str,
    raw: Mapping[str, Any],
    status: ToolStatus,
) -> str:
    if status == ToolStatus.EMPTY:
        return f"{tool_name} returned no evidence."
    if tool_name == "read_file":
        return (
            f"Read {raw.get('path')} ({raw.get('size_chars')} chars, "
            f"truncated={raw.get('truncated')})."
        )
    if tool_name == "list_files":
        return f"Listed {len(raw.get('files') or ())} files."
    if tool_name in {
        "search_text",
        "inspect_symbol",
        "query_fixture_index",
    }:
        return f"{tool_name} returned {len(raw.get('matches') or ())} matches."
    return f"{tool_name} completed."
