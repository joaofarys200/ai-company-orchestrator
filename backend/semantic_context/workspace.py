from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.semantic_context.contracts import (
    BuilderConfiguration,
    DocumentContext,
    WorkspaceContext,
    WorkspaceFile,
    sha256_json,
)
from intelligence.project_intelligence import (
    GENERATED_SUFFIXES,
    IGNORED_DIRECTORIES,
)


READABLE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".htm",
    ".java",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mjs",
    ".cjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".htm",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".ts",
    ".tsx",
    ".vue",
}
BINARY_OR_DURABLE_SUFFIXES = {
    ".7z",
    ".bin",
    ".db",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".so",
    ".tar",
    ".wasm",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}
CONFIG_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "pytest.ini",
    "tsconfig.json",
    "vite.config.js",
    "vite.config.ts",
    "webpack.config.js",
    "eslint.config.js",
    ".eslintrc",
    ".eslintrc.json",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}
LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "poetry.lock": "Poetry",
    "uv.lock": "uv",
    "pipfile.lock": "Pipenv",
}
LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".css": "CSS",
    ".go": "Go",
    ".h": "C/C++",
    ".hpp": "C++",
    ".html": "HTML",
    ".htm": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript JSX",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sql": "SQL",
    ".ts": "TypeScript",
    ".tsx": "TypeScript TSX",
    ".vue": "Vue",
}
SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "secrets.json",
}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]{3,}")


class WorkspaceInspectionError(Exception):
    pass


@dataclass(frozen=True)
class InspectedContent:
    path: str
    category: str
    content: str
    observed_at: str
    priority: int
    content_sha256: str


@dataclass(frozen=True)
class WorkspaceInspection:
    workspace: WorkspaceContext
    documents: DocumentContext
    contents: tuple[InspectedContent, ...]
    rejected_reasons: tuple[tuple[str, str], ...]


class WorkspaceInspector:
    """Bounded metadata traversal plus selective UTF-8 content reads."""

    def inspect(
        self,
        configuration: BuilderConfiguration,
        *,
        mission_terms: tuple[str, ...] = (),
    ) -> WorkspaceInspection:
        workspace_root = Path(configuration.workspace_root).resolve()
        projects_root = (workspace_root / "workspace" / "projects").resolve()
        project_root = (projects_root / configuration.project_id).resolve()
        if not project_root.is_dir():
            raise WorkspaceInspectionError(
                f"Project root does not exist: {configuration.project_id}"
            )
        try:
            project_root.relative_to(projects_root)
        except ValueError as exc:
            raise WorkspaceInspectionError(
                "Project root is outside workspace/projects."
            ) from exc

        records, rejected, truncated = self._scan_metadata(
            project_root,
            configuration,
        )
        package_path = self._select_package_json(records)
        package_data, cached = self._load_structured_file(
            project_root,
            package_path,
            configuration.max_file_bytes,
        )
        metadata_by_path = {item.path: item for item in records}
        entrypoints = self._entrypoints(records, package_path, package_data)
        stack = self._stack(records, package_data)
        dependency_markers, dependency_cache = self._dependency_markers(
            project_root,
            metadata_by_path,
            package_data,
            configuration.max_file_bytes,
        )
        cached.update(dependency_cache)
        frameworks = self._frameworks(package_data, dependency_markers)
        managers = self._package_managers(records, package_data)
        dependencies = self._dependencies(package_data, dependency_markers)
        source_roots = self._source_roots(records, entrypoints)
        configurations = tuple(
            item.path for item in records if item.category == "configuration"
        )
        tests = tuple(item.path for item in records if item.category == "test")
        latest_changes = tuple(
            item.path
            for item in sorted(
                records,
                key=lambda value: (-value.modified_ns, value.path),
            )[:20]
        )
        languages = tuple(sorted({
            item.language for item in records if item.language
        }))
        selected_records = self._select_content_candidates(
            records,
            entrypoints=entrypoints,
            relevant_paths=configuration.relevant_paths,
            mission_terms=mission_terms,
            limit=configuration.max_content_files,
        )
        contents, content_records, content_rejected = self._read_selected(
            project_root,
            selected_records,
            configuration,
            cached,
        )
        rejected.extend(content_rejected)
        content_by_path = {item.path: item for item in content_records}
        final_records = tuple(
            content_by_path.get(item.path, item)
            for item in records
        )
        relevant_files = tuple(
            content_by_path[item.path]
            for item in selected_records
            if item.path in content_by_path
        )
        document_records = tuple(
            item
            for item in relevant_files
            if item.category == "document"
        )
        observed_at = _latest_timestamp(final_records)
        workspace_payload = {
            "project_id": configuration.project_id,
            "root_path": (
                f"workspace/projects/{configuration.project_id}"
            ),
            "stack": stack,
            "frameworks": frameworks,
            "package_managers": managers,
            "entrypoints": entrypoints,
            "source_roots": source_roots,
            "languages": languages,
            "dependencies": dependencies,
            "configurations": configurations,
            "tests": tests,
            "latest_changes": latest_changes,
            "file_tree": final_records,
            "relevant_files": relevant_files,
            "traversal_truncated": truncated,
        }
        workspace_context = WorkspaceContext(
            project_id=configuration.project_id,
            root_path=f"workspace/projects/{configuration.project_id}",
            project_name=project_root.name,
            stack=stack,
            frameworks=frameworks,
            package_managers=managers,
            entrypoints=entrypoints,
            source_roots=source_roots,
            languages=languages,
            dependencies=dependencies,
            configurations=configurations,
            tests=tests,
            latest_changes=latest_changes,
            file_tree=final_records,
            relevant_files=relevant_files,
            files_considered=len(records),
            files_rejected=len(rejected),
            traversal_truncated=truncated,
            observed_at=observed_at,
            source_sha256=sha256_json(workspace_payload),
        )
        document_context = DocumentContext(
            documents=document_records,
            source_sha256=sha256_json(document_records),
        )
        return WorkspaceInspection(
            workspace=workspace_context,
            documents=document_context,
            contents=contents,
            rejected_reasons=tuple(sorted(rejected)),
        )

    def _scan_metadata(
        self,
        project_root: Path,
        configuration: BuilderConfiguration,
    ) -> tuple[list[WorkspaceFile], list[tuple[str, str]], bool]:
        records: list[WorkspaceFile] = []
        rejected: list[tuple[str, str]] = []
        truncated = False

        def visit(directory: Path, depth: int) -> None:
            nonlocal truncated
            if truncated:
                return
            if depth > configuration.max_workspace_depth:
                rejected.append((
                    directory.relative_to(project_root).as_posix(),
                    "depth_limit",
                ))
                return
            try:
                entries = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError:
                rejected.append((
                    directory.relative_to(project_root).as_posix() or ".",
                    "directory_unreadable",
                ))
                return
            for entry in entries:
                if len(records) >= configuration.max_workspace_files:
                    truncated = True
                    return
                relative = Path(entry.path).relative_to(project_root).as_posix()
                if entry.is_symlink():
                    rejected.append((relative, "symlink_excluded"))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() in {
                        item.lower() for item in IGNORED_DIRECTORIES
                    }:
                        rejected.append((relative, "directory_excluded"))
                        continue
                    visit(Path(entry.path), depth + 1)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    rejected.append((relative, "non_regular_file"))
                    continue
                reason = _file_exclusion_reason(Path(entry.path))
                if reason:
                    rejected.append((relative, reason))
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    rejected.append((relative, "stat_failed"))
                    continue
                category = _category(relative)
                records.append(
                    WorkspaceFile(
                        path=relative,
                        size_bytes=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                        category=category,
                        language=LANGUAGE_BY_SUFFIX.get(
                            Path(relative).suffix.lower(),
                            "",
                        ),
                    )
                )

        visit(project_root, 0)
        records.sort(key=lambda item: item.path)
        return records, rejected, truncated

    @staticmethod
    def _select_package_json(
        records: list[WorkspaceFile],
    ) -> str | None:
        paths = [
            item.path
            for item in records
            if Path(item.path).name.lower() == "package.json"
        ]
        return min(paths, key=lambda value: (value.count("/"), value)) if paths else None

    @staticmethod
    def _load_structured_file(
        root: Path,
        relative_path: str | None,
        max_bytes: int,
    ) -> tuple[dict[str, Any], dict[str, tuple[str, str]]]:
        if not relative_path:
            return {}, {}
        path = root / relative_path
        try:
            if path.stat().st_size > max_bytes:
                return {}, {}
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            value = json.loads(text)
        except (OSError, UnicodeDecodeError, ValueError):
            return {}, {}
        return (
            value if isinstance(value, dict) else {},
            {relative_path: (text, _sha256_bytes(raw))},
        )

    @staticmethod
    def _entrypoints(
        records: list[WorkspaceFile],
        package_path: str | None,
        package_data: dict[str, Any],
    ) -> tuple[str, ...]:
        paths = {item.path for item in records}
        entries: list[str] = []
        preferred = (
            "frontend/index.html",
            "public/index.html",
            "client/index.html",
            "index.html",
            "backend/server.py",
            "backend/app.py",
            "backend/main.py",
            "server.py",
            "app.py",
            "main.py",
            "src/main.tsx",
            "src/main.ts",
            "src/main.jsx",
            "src/main.js",
            "src/index.tsx",
            "src/index.js",
            "app.js",
        )
        entries.extend(item for item in preferred if item in paths)
        package_main = package_data.get("main")
        if isinstance(package_main, str) and package_main.strip():
            package_dir = (
                Path(package_path).parent
                if package_path
                else Path(".")
            )
            candidate = (package_dir / package_main).as_posix()
            if candidate.startswith("./"):
                candidate = candidate[2:]
            if candidate in paths:
                entries.append(candidate)
        return tuple(dict.fromkeys(entries))

    @staticmethod
    def _stack(
        records: list[WorkspaceFile],
        package_data: dict[str, Any],
    ) -> tuple[str, ...]:
        paths = {item.path for item in records}
        suffixes = {Path(item.path).suffix.lower() for item in records}
        stack: list[str] = []
        if any(path.endswith((".html", ".htm")) for path in paths):
            stack.append("HTML/JavaScript")
        if package_data:
            stack.append("Node")
        if ".py" in suffixes:
            stack.append("Python")
        return tuple(stack or ["Unknown"])

    @staticmethod
    def _dependency_markers(
        root: Path,
        records: dict[str, WorkspaceFile],
        package_data: dict[str, Any],
        max_bytes: int,
    ) -> tuple[tuple[str, ...], dict[str, tuple[str, str]]]:
        del package_data
        markers: list[str] = []
        cached: dict[str, tuple[str, str]] = {}
        for name in ("requirements.txt", "pyproject.toml"):
            item = records.get(name)
            if item is None or item.size_bytes > max_bytes:
                continue
            try:
                raw = (root / name).read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            cached[name] = (text, _sha256_bytes(raw))
            if name == "requirements.txt":
                markers.extend(
                    line.strip()
                    for line in text.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                continue
            try:
                parsed = tomllib.loads(text)
            except (tomllib.TOMLDecodeError, ValueError):
                continue
            project = parsed.get("project")
            if isinstance(project, dict):
                markers.extend(
                    str(item)
                    for item in project.get("dependencies") or ()
                )
        return tuple(sorted(set(markers))), cached

    @staticmethod
    def _frameworks(
        package_data: dict[str, Any],
        dependency_markers: tuple[str, ...],
    ) -> tuple[str, ...]:
        dependencies: dict[str, Any] = {}
        for key in ("dependencies", "devDependencies"):
            if isinstance(package_data.get(key), dict):
                dependencies.update(package_data[key])
        package_frameworks = {
            "react": "React",
            "next": "Next.js",
            "vue": "Vue",
            "@angular/core": "Angular",
            "svelte": "Svelte",
            "vite": "Vite",
            "express": "Express",
        }
        frameworks = {
            label
            for package, label in package_frameworks.items()
            if package in dependencies
        }
        python_text = "\n".join(dependency_markers).lower()
        for marker, label in (
            ("django", "Django"),
            ("fastapi", "FastAPI"),
            ("flask", "Flask"),
        ):
            if marker in python_text:
                frameworks.add(label)
        return tuple(sorted(frameworks))

    @staticmethod
    def _package_managers(
        records: list[WorkspaceFile],
        package_data: dict[str, Any],
    ) -> tuple[str, ...]:
        names = {Path(item.path).name.lower() for item in records}
        managers = {
            manager
            for filename, manager in LOCKFILE_MANAGERS.items()
            if filename in names
        }
        if package_data and not managers.intersection({"npm", "pnpm", "yarn"}):
            managers.add("npm")
        if "requirements.txt" in names:
            managers.add("pip")
        return tuple(sorted(managers))

    @staticmethod
    def _dependencies(
        package_data: dict[str, Any],
        dependency_markers: tuple[str, ...],
    ) -> tuple[str, ...]:
        values = set(dependency_markers)
        for key in ("dependencies", "devDependencies"):
            entries = package_data.get(key)
            if not isinstance(entries, dict):
                continue
            values.update(
                f"{name}@{version}"
                for name, version in entries.items()
            )
        return tuple(sorted(values))

    @staticmethod
    def _source_roots(
        records: list[WorkspaceFile],
        entrypoints: tuple[str, ...],
    ) -> tuple[str, ...]:
        first_segments = {
            item.path.split("/", 1)[0]
            for item in records
            if "/" in item.path
        }
        roots = [
            item
            for item in (
                "src",
                "app",
                "api",
                "backend",
                "frontend",
                "server",
                "client",
                "lib",
            )
            if item in first_segments
        ]
        if any("/" not in item for item in entrypoints):
            roots.insert(0, ".")
        return tuple(dict.fromkeys(roots or ["."]))

    @staticmethod
    def _select_content_candidates(
        records: list[WorkspaceFile],
        *,
        entrypoints: tuple[str, ...],
        relevant_paths: tuple[str, ...],
        mission_terms: tuple[str, ...],
        limit: int,
    ) -> list[WorkspaceFile]:
        entry_set = set(entrypoints)
        relevant_set = set(relevant_paths)
        mission_tokens = {
            token.lower()
            for value in mission_terms
            for token in TOKEN_PATTERN.findall(value)
        }

        def score(item: WorkspaceFile) -> tuple[int, str]:
            value = 0
            if item.path in relevant_set:
                value += 100
            if item.path in entry_set:
                value += 90
            if Path(item.path).name.lower().startswith("readme"):
                value += 85
            value += {
                "configuration": 75,
                "test": 65,
                "document": 60,
                "source": 45,
                "other": 0,
            }.get(item.category, 0)
            path_tokens = {
                token.lower()
                for token in TOKEN_PATTERN.findall(item.path)
            }
            value += min(20, len(path_tokens & mission_tokens) * 5)
            return (-value, item.path)

        candidates = [
            item
            for item in records
            if item.category in {
                "configuration",
                "document",
                "source",
                "test",
            }
        ]
        return sorted(candidates, key=score)[:limit]

    @staticmethod
    def _read_selected(
        root: Path,
        records: list[WorkspaceFile],
        configuration: BuilderConfiguration,
        cache: dict[str, tuple[str, str]],
    ) -> tuple[
        tuple[InspectedContent, ...],
        tuple[WorkspaceFile, ...],
        list[tuple[str, str]],
    ]:
        contents: list[InspectedContent] = []
        updated: list[WorkspaceFile] = []
        rejected: list[tuple[str, str]] = []
        total_bytes = 0
        for item in records:
            if item.size_bytes > configuration.max_file_bytes:
                rejected.append((item.path, "file_content_limit"))
                continue
            if total_bytes + item.size_bytes > configuration.max_total_file_bytes:
                rejected.append((item.path, "total_content_limit"))
                continue
            if item.path in cache:
                text, content_hash = cache[item.path]
            else:
                try:
                    raw = (root / item.path).read_bytes()
                except OSError:
                    rejected.append((item.path, "file_unreadable"))
                    continue
                if b"\x00" in raw:
                    rejected.append((item.path, "binary_content"))
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    rejected.append((item.path, "non_utf8_content"))
                    continue
                content_hash = _sha256_bytes(raw)
            total_bytes += item.size_bytes
            record = replace(
                item,
                content_available=True,
                content_sha256=content_hash,
            )
            updated.append(record)
            contents.append(
                InspectedContent(
                    path=item.path,
                    category=item.category,
                    content=text,
                    observed_at=_timestamp_from_ns(item.modified_ns),
                    priority=_category_priority(item.category),
                    content_sha256=content_hash,
                )
            )
        return tuple(contents), tuple(updated), rejected


def _file_exclusion_reason(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in SECRET_NAMES or name.startswith(".env."):
        return "sensitive_file"
    if suffix in BINARY_OR_DURABLE_SUFFIXES:
        return "binary_or_durable_file"
    if name.endswith(GENERATED_SUFFIXES):
        return "generated_file"
    if suffix and suffix not in READABLE_SUFFIXES and name not in CONFIG_NAMES:
        return "unsupported_file"
    return ""


def _category(relative_path: str) -> str:
    path = Path(relative_path)
    name = path.name.lower()
    parts = {item.lower() for item in path.parts}
    suffix = path.suffix.lower()
    if (
        "test" in parts
        or "tests" in parts
        or name.startswith("test_")
        or name.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    ):
        return "test"
    if name in CONFIG_NAMES or name in LOCKFILE_MANAGERS:
        return "configuration"
    if name.startswith("readme") or "docs" in parts or suffix in {".md", ".rst"}:
        return "document"
    if suffix in SOURCE_SUFFIXES:
        return "source"
    return "other"


def _category_priority(category: str) -> int:
    return {
        "configuration": 75,
        "test": 70,
        "document": 65,
        "source": 55,
    }.get(category, 0)


def _timestamp_from_ns(value: int) -> str:
    return datetime.fromtimestamp(
        value / 1_000_000_000,
        tz=timezone.utc,
    ).isoformat()


def _latest_timestamp(records: tuple[WorkspaceFile, ...]) -> str:
    if not records:
        return "1970-01-01T00:00:00+00:00"
    return _timestamp_from_ns(max(item.modified_ns for item in records))


def _sha256_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()
