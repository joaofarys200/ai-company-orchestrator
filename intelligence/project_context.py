from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import sandbox
from intelligence.project_intelligence import GENERATED_SUFFIXES, IGNORED_DIRECTORIES, ProjectIntelligenceEngine
from workspace_policy import WORKSPACE_ROOT, resolve_workspace_path


PROJECTS_ROOT_REL = "workspace/projects"
PROJECT_METADATA_ROOT_REL = "workspace/.jarvis/projects"
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TEXT_FILE_SUFFIXES = {
    ".css", ".html", ".htm", ".js", ".jsx", ".json", ".md", ".mjs", ".cjs",
    ".py", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
MAX_VIEW_FILE_BYTES = 500_000
# Integrity is intentionally independent from UI/AST limits. The default protects
# transactional source files up to 50 MiB without loading them fully into memory.
DEFAULT_MAX_TRANSACTION_FILE_BYTES = 50 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
TRANSACTIONAL_FILE_SUFFIXES = {
    ".css", ".html", ".htm", ".js", ".jsx", ".json", ".mjs", ".cjs",
    ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml",
}


class ProjectContextError(Exception):
    pass


@dataclass
class ProjectContext:
    project_id: str
    root_path: str
    project_name: str
    python_executable: str | None = None
    runtime_source: str = "unavailable"
    runtime_version: str | None = None
    stack: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    source_roots: list[str] = field(default_factory=list)
    package_scripts: dict[str, str] = field(default_factory=dict)
    suggested_commands: list[dict[str, str]] = field(default_factory=list)
    git_state: dict[str, Any] = field(default_factory=dict)
    ast_index: dict[str, Any] = field(default_factory=dict)
    last_indexed_at: str | None = None
    diagnostics: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectContextService:
    def __init__(
        self,
        workspace_root: str = WORKSPACE_ROOT,
        projects_root_rel: str = PROJECTS_ROOT_REL,
        metadata_root_rel: str = PROJECT_METADATA_ROOT_REL,
        path_resolver: Callable[[str], str] | None = None,
        process_python_executable: str | None = sys.executable,
        max_transaction_file_bytes: int | None = None,
    ):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.projects_root_rel = projects_root_rel.replace("\\", "/").strip("/")
        self.metadata_root_rel = metadata_root_rel.replace("\\", "/").strip("/")
        self.path_resolver = path_resolver or (resolve_workspace_path if self.workspace_root == WORKSPACE_ROOT else self._resolve_for_custom_root)
        self.process_python_executable = process_python_executable
        configured_limit = max_transaction_file_bytes
        if configured_limit is None:
            try:
                configured_limit = int(os.getenv("JARVIS_MAX_TRANSACTION_FILE_BYTES", str(DEFAULT_MAX_TRANSACTION_FILE_BYTES)))
            except ValueError:
                configured_limit = DEFAULT_MAX_TRANSACTION_FILE_BYTES
        self.max_transaction_file_bytes = max(int(configured_limit), MAX_VIEW_FILE_BYTES + 1)

    def _resolve_for_custom_root(self, relative_path: str) -> str:
        candidate = os.path.realpath(os.path.abspath(os.path.join(self.workspace_root, relative_path)))
        try:
            if os.path.commonpath([self.workspace_root, candidate]) != self.workspace_root:
                raise ProjectContextError("Acesso fora do workspace nao permitido.")
        except ValueError as exc:
            raise ProjectContextError("Acesso fora do workspace nao permitido.") from exc
        return candidate

    @staticmethod
    def _validate_project_id(project_id: str) -> str:
        clean_id = str(project_id or "").strip()
        if not PROJECT_ID_PATTERN.fullmatch(clean_id):
            raise ProjectContextError("project_id invalido.")
        if "obsidian" in clean_id.lower() or clean_id.lower() in {"sandbox", "sandbox_dir"}:
            raise ProjectContextError("Este diretorio nao pode ser usado como projeto IDE.")
        return clean_id

    def project_root(self, project_id: str) -> str:
        clean_id = self._validate_project_id(project_id)
        project_root = self.path_resolver(f"{self.projects_root_rel}/{clean_id}")
        projects_root = self.path_resolver(self.projects_root_rel)
        try:
            if os.path.commonpath([projects_root, project_root]) != projects_root:
                raise ProjectContextError("Projeto fora de workspace/projects.")
        except ValueError as exc:
            raise ProjectContextError("Projeto fora de workspace/projects.") from exc
        if not os.path.isdir(project_root):
            raise ProjectContextError(f"Projeto '{clean_id}' nao existe.")
        return project_root

    def metadata_dir(self, project_id: str) -> str:
        clean_id = self._validate_project_id(project_id)
        return self.path_resolver(f"{self.metadata_root_rel}/{clean_id}")

    def context_path(self, project_id: str) -> str:
        return os.path.join(self.metadata_dir(project_id), "project_context.json")

    def index_path(self, project_id: str) -> str:
        return os.path.join(self.metadata_dir(project_id), "symbols_index.json")

    def list_projects(self) -> list[dict[str, str]]:
        projects_root = self.path_resolver(self.projects_root_rel)
        if not os.path.isdir(projects_root):
            return []
        projects = []
        for entry in sorted(os.scandir(projects_root), key=lambda item: item.name.lower()):
            if not entry.is_dir() or not PROJECT_ID_PATTERN.fullmatch(entry.name):
                continue
            if "obsidian" in entry.name.lower() or entry.name.lower() == "sandbox_dir":
                continue
            projects.append({"project_id": entry.name, "project_name": entry.name, "root_path": os.path.realpath(entry.path)})
        return projects

    def open_project(self, project_id: str) -> ProjectContext:
        clean_id = self._validate_project_id(project_id)
        root = self.project_root(clean_id)
        layout = sandbox.inspect_project_layout(root)
        package_data, package_rel_dir = self._read_package_json(layout.get("package_dir"), root)
        stack = self._detect_stack(root, layout, package_data)
        frameworks = self._detect_frameworks(root, package_data)
        package_managers = self._detect_package_managers(root, package_data)
        entrypoints = self._entrypoints(root, layout, package_data, package_rel_dir)
        source_roots = self._source_roots(root, entrypoints)
        package_scripts = self._package_scripts(package_data, package_rel_dir)
        runtime = self._detect_python_runtime(root) if "Python" in stack else {
            "python_executable": None,
            "runtime_source": "unavailable",
            "runtime_version": None,
        }
        diagnostics: list[dict[str, str]] = []
        existing = self._load_context(clean_id)
        if existing:
            diagnostics.extend(existing.get("diagnostics", []))
        ast_index = dict(existing.get("ast_index") or {}) if existing else {}
        indexed_hashes = ast_index.get("source_hashes") or {}
        if indexed_hashes:
            indexed_paths = {
                path for path, metadata in (ast_index.get("files") or {}).items()
                if metadata.get("content_indexed")
            }
            current_manifest = self.build_integrity_manifest(root, indexed_paths)
            current_hashes = {
                path: metadata["source_hash"] for path, metadata in current_manifest.items()
                if metadata.get("hash_available")
            }
            if current_hashes != indexed_hashes:
                ast_index["status"] = "stale"

        context = ProjectContext(
            project_id=clean_id,
            root_path=root,
            project_name=str(package_data.get("name") or clean_id),
            python_executable=runtime["python_executable"],
            runtime_source=runtime["runtime_source"],
            runtime_version=runtime["runtime_version"],
            stack=stack,
            frameworks=frameworks,
            package_managers=package_managers,
            entrypoints=entrypoints,
            source_roots=source_roots,
            package_scripts=package_scripts,
            suggested_commands=self.suggest_diagnostics(root, stack, entrypoints, package_data, package_rel_dir, runtime),
            git_state=self._git_state(root),
            ast_index=ast_index,
            last_indexed_at=existing.get("last_indexed_at") if existing else None,
            diagnostics=diagnostics,
        )
        self._persist_context(context)
        return context

    def index_project(self, project_id: str) -> ProjectContext:
        context = self.open_project(project_id)
        engine = ProjectIntelligenceEngine(context.root_path)
        graph = engine.scan_workspace()
        index_path = self.index_path(context.project_id)
        engine.save_index(index_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        symbol_count = sum(
            len(file_data.get("classes", [])) + len(file_data.get("functions", []))
            for file_data in graph.values()
        )
        file_manifest = self.build_integrity_manifest(context.root_path, set(graph))
        source_hashes = {
            relative_path: metadata["source_hash"]
            for relative_path, metadata in file_manifest.items()
            if metadata.get("hash_available")
        }
        context.ast_index = {
            "path": os.path.relpath(index_path, self.workspace_root).replace(os.sep, "/"),
            "file_count": len(graph),
            "symbol_count": symbol_count,
            "error_count": len(engine.errors),
            "status": "ready" if not engine.errors else "partial",
            "source_hashes": source_hashes,
            "files": file_manifest,
            "transaction_limit_bytes": self.max_transaction_file_bytes,
        }
        context.last_indexed_at = timestamp
        context.diagnostics = [item for item in context.diagnostics if item.get("source") != "indexer"]
        context.diagnostics.extend(
            {"source": "indexer", "file": error["file"], "message": error["error"]}
            for error in engine.errors
        )
        self._persist_context(context)
        return context

    def load_index(self, project_id: str) -> dict[str, dict[str, Any]]:
        self.project_root(project_id)
        path = self.index_path(project_id)
        if not os.path.isfile(path):
            return {}
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProjectContextError(f"Indice do projeto invalido: {exc}") from exc
        return data if isinstance(data, dict) else {}

    def locate_symbol(self, project_id: str, symbol_name: str) -> list[dict[str, Any]]:
        clean_name = str(symbol_name or "").strip()
        if not clean_name:
            return []
        definitions = []
        for filepath, data in self.load_index(project_id).items():
            for kind in ("classes", "functions"):
                for symbol in data.get(kind, []):
                    if symbol.get("name") == clean_name:
                        definitions.append({
                            "kind": "definition",
                            "symbol_kind": kind[:-2] if kind.endswith("es") else kind[:-1],
                            "file": filepath,
                            "line": symbol.get("line", 0),
                            "confirmed": True,
                            "text": clean_name,
                        })
        return definitions

    def find_references(self, project_id: str, symbol_name: str) -> dict[str, Any]:
        clean_name = str(symbol_name or "").strip()
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", clean_name):
            raise ProjectContextError("Nome de simbolo invalido.")
        root = self.project_root(project_id)
        definitions = self.locate_symbol(project_id, clean_name)
        definition_locations = {(item["file"], item["line"]) for item in definitions}
        engine = ProjectIntelligenceEngine(root)
        references: list[dict[str, Any]] = []
        pattern = re.compile(rf"\b{re.escape(clean_name)}\b")

        for absolute_path, relative_path in self._iter_reference_files(root):
            try:
                lines = Path(absolute_path).read_text(encoding="utf-8", errors="replace").splitlines()
                confirmed_lines = engine.identifier_lines(absolute_path, clean_name)
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if not pattern.search(line) or (relative_path, line_number) in definition_locations:
                    continue
                confirmed = line_number in confirmed_lines
                references.append({
                    "kind": "reference" if confirmed else "textual_match",
                    "file": relative_path,
                    "line": line_number,
                    "confirmed": confirmed,
                    "text": line.strip()[:240],
                })
        return {"symbol": clean_name, "definitions": definitions, "references": references}

    def read_project_files(self, project_id: str) -> dict[str, str]:
        root = self.project_root(project_id)
        files: dict[str, str] = {}
        for current_root, dirs, filenames in os.walk(root):
            dirs[:] = sorted(directory for directory in dirs if directory not in IGNORED_DIRECTORIES)
            for filename in sorted(filenames):
                path = os.path.join(current_root, filename)
                if Path(filename).suffix.lower() not in TEXT_FILE_SUFFIXES:
                    continue
                try:
                    if os.path.getsize(path) > MAX_VIEW_FILE_BYTES:
                        continue
                    relative_path = os.path.relpath(path, root).replace(os.sep, "/")
                    raw = Path(path).read_bytes()
                    if raw.startswith(b"\xef\xbb\xbf"):
                        raw = raw[3:]
                    files[relative_path] = raw.decode("utf-8", errors="replace")
                except OSError:
                    continue
        return files

    @staticmethod
    def _hash_file(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(HASH_CHUNK_BYTES):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _preserve_line_endings(original: bytes, content: str) -> str:
        crlf_count = original.count(b"\r\n")
        lf_count = original.count(b"\n") - crlf_count
        cr_count = original.count(b"\r") - crlf_count
        if crlf_count and not lf_count and not cr_count:
            newline = "\r\n"
        elif lf_count and not crlf_count and not cr_count:
            newline = "\n"
        elif cr_count and not crlf_count and not lf_count:
            newline = "\r"
        else:
            return content
        return content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)

    @staticmethod
    def _resolve_existing_project_file(root: str, relative_path: str) -> str:
        normalized = str(relative_path or "").replace("\\", "/").strip("/")
        if not normalized or os.path.isabs(normalized) or normalized.startswith("../") or "/../" in normalized:
            raise ProjectContextError("Caminho de ficheiro invalido.")
        ignored = {item.lower() for item in IGNORED_DIRECTORIES}
        if any(part.lower() in ignored for part in normalized.split("/")[:-1]):
            raise ProjectContextError("Edicao de diretorios gerados ou dependencias nao permitida.")
        if Path(normalized).suffix.lower() not in TEXT_FILE_SUFFIXES:
            raise ProjectContextError("O editor apenas permite ficheiros de texto suportados.")
        target = os.path.realpath(os.path.abspath(os.path.join(root, normalized)))
        try:
            if os.path.commonpath([root, target]) != root:
                raise ProjectContextError("Acesso fora do projeto nao permitido.")
        except ValueError as exc:
            raise ProjectContextError("Acesso fora do projeto nao permitido.") from exc
        source_path = os.path.abspath(os.path.join(root, normalized))
        if os.path.islink(source_path):
            raise ProjectContextError("Edicao de links simbolicos nao permitida.")
        if not os.path.isfile(target):
            raise ProjectContextError("O ficheiro selecionado nao existe.")
        return target

    def project_file_hashes(self, project_id: str, filenames: set[str]) -> dict[str, str]:
        root = self.project_root(project_id)
        hashes: dict[str, str] = {}
        for relative_path in filenames:
            try:
                target = self._resolve_existing_project_file(root, relative_path)
                hashes[relative_path] = self._hash_file(target)
            except ProjectContextError:
                continue
        return hashes

    def save_project_file(
        self,
        project_id: str,
        relative_path: str,
        content: str,
        expected_sha256: str,
    ) -> dict[str, Any]:
        root = self.project_root(project_id)
        target = self._resolve_existing_project_file(root, relative_path)
        expected_hash = str(expected_sha256 or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
            raise ProjectContextError("Hash original do ficheiro em falta ou invalido.")
        if not isinstance(content, str) or "\x00" in content:
            raise ProjectContextError("O editor apenas permite guardar ficheiros de texto.")

        current_bytes = Path(target).read_bytes()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        if current_hash != expected_hash:
            raise ProjectContextError(
                "O ficheiro mudou no disco desde que foi aberto. Reabra o projeto antes de guardar."
            )

        has_bom = current_bytes.startswith(b"\xef\xbb\xbf")
        original_body = current_bytes[3:] if has_bom else current_bytes
        normalized_content = self._preserve_line_endings(original_body, content)
        resulting_bytes = normalized_content.encode("utf-8")
        if has_bom:
            resulting_bytes = b"\xef\xbb\xbf" + resulting_bytes
        if len(resulting_bytes) > MAX_VIEW_FILE_BYTES:
            raise ProjectContextError(
                f"O ficheiro excede o limite de edicao manual de {MAX_VIEW_FILE_BYTES} bytes."
            )

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{Path(target).name}.",
            suffix=".jarvis-editor-tmp",
            dir=os.path.dirname(target),
        )
        try:
            original_mode = os.stat(target).st_mode
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(resulting_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, original_mode)
            os.replace(temporary_path, target)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            raise

        resulting_hash = hashlib.sha256(resulting_bytes).hexdigest()
        return {
            "project_id": self._validate_project_id(project_id),
            "filename": relative_path.replace("\\", "/"),
            "sha256": resulting_hash,
            "size_bytes": len(resulting_bytes),
        }

    def project_payload(self, project_id: str, reindex: bool = False) -> dict[str, Any]:
        context = self.index_project(project_id) if reindex else self.open_project(project_id)
        files = self.read_project_files(project_id)
        return {
            "context": context.to_dict(),
            "files": files,
            "file_hashes": self.project_file_hashes(project_id, set(files)),
            "symbols": self.load_index(project_id),
        }

    def preview_project(self, project_id: str, on_output_callback) -> dict[str, Any]:
        root = self.project_root(project_id)
        return sandbox.run_custom_project(
            on_output_callback,
            root_dir=root,
            allow_dependency_install=False,
        )

    def semantic_search(self, project_id: str, query: str, n_results: int = 5) -> str:
        from intelligence.semantic_index import SemanticCodeIndex

        context = self.open_project(project_id)
        db_path = os.path.join(self.metadata_dir(project_id), "semantic_index")
        index = SemanticCodeIndex(context.root_path, db_path=db_path, collection_name="project_code")
        graph = self.load_index(project_id)
        if not graph:
            context = self.index_project(project_id)
            graph = self.load_index(context.project_id)
        index.build_index(graph=graph)
        return index.search(query, n_results=n_results)

    def suggest_diagnostics(
        self,
        root: str,
        stack: list[str],
        entrypoints: list[str],
        package_data: dict[str, Any],
        package_rel_dir: str,
        runtime: dict[str, str | None],
    ) -> list[dict[str, str]]:
        commands: list[dict[str, str]] = []
        python_executable = runtime.get("python_executable")
        if "Python" in stack and python_executable:
            for entrypoint in entrypoints:
                if entrypoint.endswith(".py"):
                    commands.append({
                        "kind": "syntax",
                        "command": self.python_module_command(python_executable, "py_compile", [entrypoint]),
                        "source": f"python entrypoint ({runtime.get('runtime_source')})",
                    })
            if self._pytest_configured(root) and self._runtime_has_module(python_executable, "pytest"):
                commands.append({
                    "kind": "test",
                    "command": self.python_module_command(python_executable, "pytest"),
                    "source": f"pytest configuration ({runtime.get('runtime_source')})",
                })
            if self._tool_configured(root, "ruff") and self._runtime_has_module(python_executable, "ruff"):
                commands.append({
                    "kind": "lint",
                    "command": self.python_module_command(python_executable, "ruff", ["check", "."]),
                    "source": f"ruff configuration ({runtime.get('runtime_source')})",
                })
            if self._tool_configured(root, "mypy") and self._runtime_has_module(python_executable, "mypy"):
                commands.append({
                    "kind": "typecheck",
                    "command": self.python_module_command(python_executable, "mypy", ["."]),
                    "source": f"mypy configuration ({runtime.get('runtime_source')})",
                })

        scripts = package_data.get("scripts") if isinstance(package_data.get("scripts"), dict) else {}
        prefix = f'cd "{package_rel_dir}"; ' if package_rel_dir and package_rel_dir != "." else ""
        for script_name in ("lint", "build", "test", "typecheck", "check"):
            if isinstance(scripts.get(script_name), str):
                commands.append({"kind": script_name, "command": f"{prefix}npm run {script_name}", "source": "package.json"})

        if "HTML/JavaScript" in stack and "Node" not in stack and shutil.which("node"):
            for entrypoint in entrypoints:
                if entrypoint.endswith((".js", ".mjs", ".cjs")):
                    commands.append({"kind": "syntax", "command": f'node --check "{entrypoint}"', "source": "javascript entrypoint"})
        return commands

    def _detect_python_runtime(self, root: str) -> dict[str, str | None]:
        candidate_names = (
            ("venv", "project_venv"),
            (".venv", "project_.venv"),
        )
        for directory, source in candidate_names:
            for relative_executable in (("Scripts", "python.exe"), ("bin", "python")):
                candidate = os.path.realpath(os.path.join(root, directory, *relative_executable))
                version = self._probe_python_runtime(candidate)
                if version:
                    return {
                        "python_executable": candidate,
                        "runtime_source": source,
                        "runtime_version": version,
                    }

        process_candidate = os.path.realpath(self.process_python_executable) if self.process_python_executable else ""
        version = self._probe_python_runtime(process_candidate)
        if version:
            return {
                "python_executable": process_candidate,
                "runtime_source": "jarvis_process",
                "runtime_version": version,
            }
        return {
            "python_executable": None,
            "runtime_source": "unavailable",
            "runtime_version": None,
        }

    @staticmethod
    def _probe_python_runtime(executable: str) -> str | None:
        if not executable or not os.path.isfile(executable):
            return None
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return (result.stdout or result.stderr or "").strip() or None

    @staticmethod
    def _runtime_has_module(executable: str, module: str) -> bool:
        try:
            result = subprocess.run(
                [
                    executable,
                    "-c",
                    f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({module!r}) else 1)",
                ],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def python_module_command(executable: str, module: str, arguments: list[str] | None = None) -> str:
        arguments = arguments or []
        if os.name == "nt":
            quoted_executable = '"' + executable.replace('"', '`"') + '"'
            quoted_arguments = " ".join('"' + item.replace('"', '`"') + '"' for item in arguments)
            return f"& {quoted_executable} -m {module}" + (f" {quoted_arguments}" if quoted_arguments else "")
        command = f"{shlex.quote(executable)} -m {shlex.quote(module)}"
        if arguments:
            command += " " + " ".join(shlex.quote(item) for item in arguments)
        return command

    def build_integrity_manifest(self, root: str, indexed_paths: set[str] | None = None) -> dict[str, dict[str, Any]]:
        indexed_paths = indexed_paths or set()
        manifest: dict[str, dict[str, Any]] = {}
        for current_root, dirs, filenames in os.walk(root):
            dirs[:] = sorted(directory for directory in dirs if directory not in IGNORED_DIRECTORIES)
            for filename in sorted(filenames):
                lower_name = filename.lower()
                suffix = Path(filename).suffix.lower()
                if suffix not in TRANSACTIONAL_FILE_SUFFIXES or lower_name.endswith(GENERATED_SUFFIXES):
                    continue
                absolute_path = os.path.join(current_root, filename)
                relative_path = os.path.relpath(absolute_path, root).replace(os.sep, "/")
                manifest[relative_path] = self.file_integrity_record(
                    absolute_path,
                    content_indexed=relative_path in indexed_paths,
                )
        return manifest

    def file_integrity_record(self, absolute_path: str, content_indexed: bool = False) -> dict[str, Any]:
        try:
            size_bytes = os.path.getsize(absolute_path)
        except OSError as exc:
            return {
                "size_bytes": 0,
                "content_indexed": content_indexed,
                "hash_available": False,
                "source_hash": None,
                "reason": f"stat_error: {exc}",
            }
        record: dict[str, Any] = {
            "size_bytes": size_bytes,
            "content_indexed": content_indexed,
            "hash_available": False,
            "source_hash": None,
        }
        if size_bytes > self.max_transaction_file_bytes:
            record["reason"] = "transaction_limit_exceeded"
            return record

        digest = hashlib.sha256()
        try:
            with open(absolute_path, "rb") as handle:
                while chunk := handle.read(HASH_CHUNK_BYTES):
                    if b"\x00" in chunk:
                        record["reason"] = "binary_content"
                        return record
                    digest.update(chunk)
        except OSError as exc:
            record["reason"] = f"hash_error: {exc}"
            return record
        record["hash_available"] = True
        record["source_hash"] = digest.hexdigest()
        return record

    @staticmethod
    def _read_package_json(package_dir: str | None, root: str) -> tuple[dict[str, Any], str]:
        if not package_dir:
            return {}, "."
        try:
            data = json.loads(Path(package_dir, "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}, os.path.relpath(package_dir, root).replace(os.sep, "/")
        return (data if isinstance(data, dict) else {}), os.path.relpath(package_dir, root).replace(os.sep, "/")

    @staticmethod
    def _detect_stack(root: str, layout: dict[str, Any], package_data: dict[str, Any]) -> list[str]:
        stack: list[str] = []
        if layout.get("preview_index"):
            stack.append("HTML/JavaScript")
        if package_data:
            stack.append("Node")
        if layout.get("python_entry") or ProjectContextService._contains_suffix(root, ".py"):
            stack.append("Python")
        return stack or ["Unknown"]

    @staticmethod
    def _detect_frameworks(root: str, package_data: dict[str, Any]) -> list[str]:
        dependencies = {}
        for key in ("dependencies", "devDependencies"):
            if isinstance(package_data.get(key), dict):
                dependencies.update(package_data[key])
        framework_packages = {
            "react": "React", "next": "Next.js", "vue": "Vue", "@angular/core": "Angular",
            "svelte": "Svelte", "vite": "Vite", "express": "Express",
        }
        frameworks = [label for package, label in framework_packages.items() if package in dependencies]
        requirements = ""
        for filename in ("requirements.txt", "pyproject.toml"):
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                requirements += Path(path).read_text(encoding="utf-8", errors="ignore").lower()
        for marker, label in (("django", "Django"), ("fastapi", "FastAPI"), ("flask", "Flask")):
            if marker in requirements:
                frameworks.append(label)
        return sorted(set(frameworks))

    @staticmethod
    def _detect_package_managers(root: str, package_data: dict[str, Any]) -> list[str]:
        managers = []
        lockfiles = {"package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "poetry.lock": "Poetry", "uv.lock": "uv", "Pipfile.lock": "Pipenv"}
        for filename, manager in lockfiles.items():
            if ProjectContextService._contains_filename(root, filename):
                managers.append(manager)
        if package_data and not any(item in managers for item in ("npm", "pnpm", "yarn")):
            managers.append("npm")
        if os.path.isfile(os.path.join(root, "requirements.txt")):
            managers.append("pip")
        return sorted(set(managers))

    @staticmethod
    def _entrypoints(root: str, layout: dict[str, Any], package_data: dict[str, Any], package_rel_dir: str) -> list[str]:
        entries = []
        for key in ("preview_index", "python_entry"):
            path = layout.get(key)
            if path:
                entries.append(os.path.relpath(path, root).replace(os.sep, "/"))
        main_value = package_data.get("main")
        if isinstance(main_value, str) and main_value.strip():
            prefix = "" if package_rel_dir in {"", "."} else f"{package_rel_dir}/"
            entries.append(f"{prefix}{main_value}".replace("\\", "/"))
        for candidate in ("app.js", "main.js", "src/main.js", "src/main.ts", "src/main.tsx", "src/index.js", "src/index.tsx"):
            if os.path.isfile(os.path.join(root, candidate)):
                entries.append(candidate)
        return list(dict.fromkeys(entries))

    @staticmethod
    def _source_roots(root: str, entrypoints: list[str]) -> list[str]:
        roots = []
        for dirname in ("src", "app", "api", "backend", "frontend", "server", "client", "lib"):
            if os.path.isdir(os.path.join(root, dirname)):
                roots.append(dirname)
        if any("/" not in entry for entry in entrypoints):
            roots.insert(0, ".")
        return list(dict.fromkeys(roots or ["."]))

    @staticmethod
    def _package_scripts(package_data: dict[str, Any], package_rel_dir: str) -> dict[str, str]:
        scripts = package_data.get("scripts") if isinstance(package_data.get("scripts"), dict) else {}
        prefix = "" if package_rel_dir in {"", "."} else f"{package_rel_dir}:"
        return {f"{prefix}{name}": value for name, value in scripts.items() if isinstance(value, str)}

    @staticmethod
    def _pytest_configured(root: str) -> bool:
        return any(os.path.exists(os.path.join(root, name)) for name in ("pytest.ini", "conftest.py", "tests")) or ProjectContextService._tool_configured(root, "pytest")

    @staticmethod
    def _tool_configured(root: str, tool_name: str) -> bool:
        for filename in ("pyproject.toml", "setup.cfg", f".{tool_name}.ini", f"{tool_name}.ini"):
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            content = Path(path).read_text(encoding="utf-8", errors="ignore").lower()
            if tool_name.lower() in content:
                return True
        return False

    @staticmethod
    def _git_state(root: str) -> dict[str, Any]:
        if not shutil.which("git"):
            return {"available": False, "error": "git nao esta disponivel no ambiente"}
        try:
            probe = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
            if probe.returncode != 0:
                return {"available": False, "error": (probe.stderr or "nao e um repositorio Git").strip()}
            repository_root = os.path.realpath(probe.stdout.strip())
            status = subprocess.run(["git", "-C", root, "status", "--porcelain", "--branch"], capture_output=True, text=True, timeout=5)
            lines = status.stdout.splitlines()
            return {
                "available": status.returncode == 0,
                "repository_root": repository_root,
                "branch": lines[0][3:] if lines and lines[0].startswith("## ") else "",
                "dirty": len(lines) > 1,
                "changed_files": lines[1:101],
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"available": False, "error": str(exc)}

    @staticmethod
    def _iter_reference_files(root: str):
        supported = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm"}
        for current_root, dirs, filenames in os.walk(root):
            dirs[:] = sorted(directory for directory in dirs if directory not in IGNORED_DIRECTORIES)
            for filename in sorted(filenames):
                if Path(filename).suffix.lower() not in supported:
                    continue
                absolute_path = os.path.join(current_root, filename)
                relative_path = os.path.relpath(absolute_path, root).replace(os.sep, "/")
                yield absolute_path, relative_path

    @staticmethod
    def _contains_filename(root: str, target_filename: str) -> bool:
        for _current_root, dirs, filenames in os.walk(root):
            dirs[:] = [directory for directory in dirs if directory not in IGNORED_DIRECTORIES]
            if target_filename in filenames:
                return True
        return False

    @staticmethod
    def _contains_suffix(root: str, suffix: str) -> bool:
        for _current_root, dirs, filenames in os.walk(root):
            dirs[:] = [directory for directory in dirs if directory not in IGNORED_DIRECTORIES]
            if any(filename.lower().endswith(suffix.lower()) for filename in filenames):
                return True
        return False

    def _load_context(self, project_id: str) -> dict[str, Any] | None:
        path = self.context_path(project_id)
        if not os.path.isfile(path):
            return None
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _persist_context(self, context: ProjectContext) -> None:
        path = Path(self.context_path(context.project_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(context.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def index_project(project_id: str) -> ProjectContext:
    return ProjectContextService().index_project(project_id)
