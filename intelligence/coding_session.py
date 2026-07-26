from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

import sandbox
from intelligence.project_context import ProjectContextError, ProjectContextService
from workspace_policy import validate_local_command


EDITABLE_SUFFIXES = {".css", ".html", ".htm", ".js", ".jsx", ".json", ".mjs", ".cjs", ".py", ".ts", ".tsx"}
MAX_CHANGE_BYTES = 500_000
PlanRequester = Callable[[dict[str, Any], str | None], Awaitable[str | dict[str, Any]] | str | dict[str, Any]]


class CodingSessionError(Exception):
    pass


def resolve_project_git_context(project_root: str) -> dict[str, Any]:
    canonical_root = os.path.realpath(project_root)
    context: dict[str, Any] = {
        "is_git_repository": False,
        "git_toplevel": None,
        "project_relative_to_toplevel": None,
        "checkpoint_strategy": "file_backup",
        "reason": "git_unavailable",
    }
    if not shutil.which("git"):
        return context
    try:
        result = subprocess.run(
            ["git", "-C", canonical_root, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        context["reason"] = f"git_probe_failed:{type(exc).__name__}"
        return context
    if result.returncode != 0 or not result.stdout.strip():
        context["reason"] = "not_a_git_repository"
        return context

    git_toplevel = os.path.realpath(result.stdout.strip())
    context["is_git_repository"] = True
    context["git_toplevel"] = git_toplevel
    try:
        relative = os.path.relpath(canonical_root, git_toplevel).replace(os.sep, "/")
        common = os.path.commonpath([canonical_root, git_toplevel])
    except ValueError:
        context["reason"] = "git_toplevel_not_ancestor"
        return context
    context["project_relative_to_toplevel"] = relative

    same_root = os.path.normcase(canonical_root) == os.path.normcase(git_toplevel)
    if same_root:
        context["checkpoint_strategy"] = "git_blob"
        context["reason"] = "project_root_is_git_toplevel"
    elif os.path.normcase(common) == os.path.normcase(git_toplevel):
        context["reason"] = "nested_project_uses_file_backup"
    else:
        context["reason"] = "git_toplevel_not_ancestor"
    return context


@dataclass
class CodingSession:
    session_id: str
    project_id: str
    objective: str
    project_context_snapshot: dict[str, Any]
    affected_files: list[str]
    proposed_changes: list[dict[str, Any]]
    applied_changes: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    status: str = "PROPOSED"
    errors: list[str] = field(default_factory=list)
    primary_error: dict[str, str] | None = None
    rollback_error: dict[str, str] | None = None
    checkpoint_created: bool = False
    writes_started: bool = False
    rollback_attempted: bool = False
    rollback_succeeded: bool = False
    change_plan: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodingSessionService:
    def __init__(
        self,
        project_service: ProjectContextService | None = None,
        new_file_writer: Callable[[str, str], str] | None = None,
    ):
        self.projects = project_service or ProjectContextService()
        self.new_file_writer = new_file_writer

    def create_session(
        self,
        project_id: str,
        objective: str,
        changes: list[dict[str, Any]],
        risks: list[str] | None = None,
    ) -> CodingSession:
        clean_objective = str(objective or "").strip()
        if not clean_objective:
            raise CodingSessionError("O objetivo da alteracao e obrigatorio.")
        if not isinstance(changes, list) or not changes:
            raise CodingSessionError("O plano nao contem alteracoes.")

        context = self.projects.open_project(project_id)
        graph = self.projects.load_index(project_id)
        prepared = [self._prepare_change(context.root_path, graph, item) for item in changes]
        affected_files = list(dict.fromkeys(item["file"] for item in prepared))
        self._assert_index_current(context.to_dict(), context.root_path, prepared)
        validations = self._select_validations(context.to_dict(), prepared)
        if not any(item.get("required") for item in validations):
            raise CodingSessionError("O projeto nao tem uma validacao obrigatoria segura. Reconfigure o ProjectContext antes de editar.")

        plan = {
            "objective": clean_objective,
            "affected_files": affected_files,
            "affected_symbols": list(dict.fromkeys(item["symbol"] for item in prepared if item.get("symbol"))),
            "intended_changes": [
                {"file": item["file"], "symbol": item.get("symbol"), "change": item["reason"]}
                for item in prepared
            ],
            "risks": [str(risk) for risk in (risks or []) if str(risk).strip()],
            "validations": validations,
        }
        session = CodingSession(
            session_id=uuid.uuid4().hex,
            project_id=context.project_id,
            objective=clean_objective,
            project_context_snapshot=context.to_dict(),
            affected_files=affected_files,
            proposed_changes=prepared,
            change_plan=plan,
        )
        self._save(session)
        return session

    async def create_assisted_session(
        self,
        project_id: str,
        objective: str,
        requester: PlanRequester | None = None,
    ) -> CodingSession:
        context = self.projects.open_project(project_id)
        graph = self.projects.load_index(project_id)
        if not graph or not context.last_indexed_at:
            raise CodingSessionError("O projeto deve ser reindexado antes de criar uma alteracao.")
        request_payload = {
            "objective": objective,
            "project_context": context.to_dict(),
            "symbols": graph,
            "files": self._limited_files(self.projects.read_project_files(project_id)),
        }
        selected_requester = requester or request_edit_plan_from_ollama
        first_raw = await _maybe_await(selected_requester, request_payload, None)
        try:
            plan_data = _extract_json(first_raw)
            changes, risks = self._validate_llm_plan(plan_data)
        except Exception as first_error:
            corrected_raw = await _maybe_await(selected_requester, request_payload, str(first_error))
            try:
                plan_data = _extract_json(corrected_raw)
                changes, risks = self._validate_llm_plan(plan_data)
            except Exception as second_error:
                raise CodingSessionError(
                    f"Plano de alteracao invalido depois de uma correcao: {second_error}"
                ) from second_error
        return self.create_session(project_id, objective, changes, risks)

    def apply_session(self, project_id: str, session_id: str) -> CodingSession:
        session = self.load(project_id, session_id)
        if session.status != "PROPOSED":
            raise CodingSessionError(f"A sessao nao pode ser aplicada no estado {session.status}.")
        root = self.projects.project_root(project_id)
        self._assert_index_current(session.project_context_snapshot, root, session.proposed_changes)
        self._assert_proposals_still_match(root, session.proposed_changes)
        session.status = "APPLYING"
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(session)

        try:
            session.checkpoint = self._create_checkpoint(session, root)
            session.checkpoint_created = True
            self._save(session)
            for change in session.proposed_changes:
                session.writes_started = True
                self._apply_change(session, root, change)
            self._verify_applied_changes(root, session.proposed_changes)
        except Exception as exc:
            session.primary_error = self._exception_details(exc)
            session.errors.append(str(exc))
            if not session.checkpoint_created or not session.writes_started:
                session.status = "ERROR"
            else:
                session.rollback_attempted = True
                try:
                    self._restore_checkpoint(session, root)
                    session.rollback_succeeded = True
                    session.status = "ERROR_ROLLED_BACK"
                except Exception as rollback_error:
                    session.rollback_error = self._exception_details(rollback_error)
                    session.errors.append(f"Rollback automatico falhou: {rollback_error}")
                    session.status = "ROLLBACK_FAILED"
            session.updated_at = datetime.now(timezone.utc).isoformat()
            self._save(session)
            return session

        session.validation_results = self._run_validations(session, root)
        mandatory_failed = any(result["required"] and result["exit_code"] != 0 for result in session.validation_results)
        if mandatory_failed:
            session.status = "VALIDATION_FAILED"
            session.errors.append("Uma ou mais validacoes obrigatorias falharam. O rollback esta disponivel.")
        else:
            session.status = "SUCCEEDED"
            self.projects.index_project(project_id)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(session)
        return session

    def rollback_session(self, project_id: str, session_id: str, confirmed: bool = False) -> CodingSession:
        if not confirmed:
            raise CodingSessionError("O rollback requer confirmacao explicita.")
        session = self.load(project_id, session_id)
        if not session.checkpoint:
            raise CodingSessionError("A sessao ainda nao tem checkpoint.")
        if session.status in {"ROLLED_BACK", "ERROR_ROLLED_BACK"}:
            return session
        root = self.projects.project_root(project_id)
        session.rollback_attempted = True
        try:
            self._restore_checkpoint(session, root)
        except Exception as exc:
            session.rollback_error = self._exception_details(exc)
            session.rollback_succeeded = False
            session.errors.append(f"Rollback explicito falhou: {exc}")
            session.status = "ROLLBACK_FAILED"
            self._save(session)
            raise
        session.rollback_succeeded = True
        session.rollback_error = None
        session.status = "ROLLED_BACK"
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self.projects.index_project(project_id)
        self._save(session)
        return session

    def load(self, project_id: str, session_id: str) -> CodingSession:
        if not re.fullmatch(r"[a-f0-9]{32}", str(session_id or "")):
            raise CodingSessionError("session_id invalido.")
        path = self._session_path(project_id, session_id)
        if not os.path.isfile(path):
            raise CodingSessionError("CodingSession nao encontrada.")
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return CodingSession(**data)
        except (OSError, ValueError, TypeError) as exc:
            raise CodingSessionError(f"CodingSession invalida: {exc}") from exc

    def latest(self, project_id: str) -> CodingSession | None:
        sessions_dir = Path(self.projects.metadata_dir(project_id), "coding_sessions")
        if not sessions_dir.is_dir():
            return None
        candidates = sorted(sessions_dir.glob("*/session.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        data = json.loads(candidates[0].read_text(encoding="utf-8"))
        return CodingSession(**data)

    def _prepare_change(self, root: str, graph: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise CodingSessionError("Cada alteracao deve ser um objeto.")
        relative_path, absolute_path = self._safe_project_path(root, raw.get("file") or raw.get("path"))
        suffix = Path(relative_path).suffix.lower()
        if suffix not in EDITABLE_SUFFIXES:
            raise CodingSessionError(f"Tipo de ficheiro nao permitido para edicao: {relative_path}")
        exists = os.path.isfile(absolute_path)
        operation = str(raw.get("operation") or ("replace_symbol" if raw.get("symbol") else "replace_text" if exists else "create_file"))
        if operation in {"delete", "delete_file", "remove"}:
            raise CodingSessionError("A eliminacao de ficheiros nao e permitida nesta fase.")
        if operation not in {"replace_symbol", "replace_text", "create_file"}:
            raise CodingSessionError(f"Operacao de alteracao desconhecida: {operation}")
        if operation == "create_file" and exists:
            raise CodingSessionError(f"O ficheiro {relative_path} ja existe; create_file foi recusado.")
        if operation != "create_file" and not exists:
            raise CodingSessionError(f"O ficheiro {relative_path} nao existe.")

        new_text = raw.get("new_code", raw.get("new_text", raw.get("content")))
        if not isinstance(new_text, str) or not new_text:
            raise CodingSessionError(f"A alteracao de {relative_path} nao tem conteudo proposto.")
        if len(new_text.encode("utf-8")) > MAX_CHANGE_BYTES:
            raise CodingSessionError(f"A alteracao de {relative_path} excede o limite permitido.")
        new_text = new_text.replace("\r\n", "\n")
        symbol = str(raw.get("symbol") or "").strip() or None
        current_content = Path(absolute_path).read_text(encoding="utf-8") if exists else ""

        if operation == "replace_symbol":
            if not symbol:
                raise CodingSessionError("replace_symbol requer um simbolo.")
            old_text = self._symbol_code(graph, relative_path, symbol)
            if old_text is None:
                raise CodingSessionError(f"O simbolo {symbol} nao existe no indice de {relative_path}.")
            old_text = old_text.replace("\r\n", "\n")
        elif operation == "replace_text":
            old_text = raw.get("old_text")
            if not isinstance(old_text, str) or not old_text:
                raise CodingSessionError("replace_text requer old_text explicito.")
            old_text = old_text.replace("\r\n", "\n")
        else:
            old_text = ""

        proposed_content = self._replace_once(current_content, old_text, new_text, relative_path) if exists else new_text
        if proposed_content == current_content:
            raise CodingSessionError(f"A alteracao de {relative_path} nao muda o ficheiro.")
        reason = str(raw.get("reason") or "Alteracao solicitada pelo utilizador.").strip()
        return {
            "file": relative_path,
            "operation": operation,
            "symbol": symbol,
            "previous_excerpt": old_text,
            "proposed_excerpt": new_text,
            "reason": reason,
            "unified_diff": self._unified_diff(relative_path, current_content, proposed_content),
            "before_hash": self._content_hash(current_content) if exists else None,
            "after_hash": self._content_hash(proposed_content),
            "existed": exists,
        }

    def _select_validations(self, context: dict[str, Any], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        validations = []
        for item in context.get("suggested_commands", []):
            command = str(item.get("command") or "").strip()
            if not command:
                continue
            validations.append({
                "kind": str(item.get("kind") or "check"),
                "command": command,
                "source": str(item.get("source") or "ProjectContext"),
                "required": True,
            })
        existing_commands = {item["command"] for item in validations}
        python_executable = context.get("python_executable")
        for change in changes:
            suffix = Path(change["file"]).suffix.lower()
            command = None
            if suffix == ".py" and python_executable:
                command = ProjectContextService.python_module_command(
                    python_executable,
                    "py_compile",
                    [change["file"]],
                )
            elif suffix in {".js", ".mjs", ".cjs"} and shutil.which("node"):
                command = f'node --check "{change["file"]}"'
            if command and command not in existing_commands:
                validations.append({
                    "kind": "syntax",
                    "command": command,
                    "source": "CodingSession affected file",
                    "required": True,
                })
                existing_commands.add(command)
        if "HTML/JavaScript" in context.get("stack", []) and "Node" not in context.get("stack", []):
            validations.append({
                "kind": "preview",
                "command": "__jarvis_static_preview__",
                "source": "ProjectContext preview",
                "required": not any(item["required"] for item in validations),
            })
        return validations

    def _create_checkpoint(self, session: CodingSession, root: str) -> dict[str, Any]:
        git_context = resolve_project_git_context(root)
        use_git = git_context["checkpoint_strategy"] == "git_blob"
        checkpoint = {
            "type": "git_blob" if use_git else "file_backup",
            "strategy": git_context["checkpoint_strategy"],
            "reason": git_context["reason"],
            "git_context": git_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }
        checkpoint_dir = Path(self._session_dir(session.project_id, session.session_id), "checkpoint")
        if not use_git:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

        for relative_path in session.affected_files:
            _, absolute_path = self._safe_project_path(root, relative_path)
            exists = os.path.isfile(absolute_path)
            record: dict[str, Any] = {
                "relative_path": relative_path,
                "checkpoint_method": "git_blob" if use_git else "file_backup",
                "git_blob_oid": None,
                "original_sha256": None,
                "size_bytes": 0,
                "existed_before": exists,
                # Compatibility aliases for sessions created before Fase 13.1A.
                "existed": exists,
                "before_hash": None,
            }
            if exists:
                original_sha256, size_bytes = self._sha256_file_bytes(absolute_path)
                record["original_sha256"] = original_sha256
                record["size_bytes"] = size_bytes
                record["before_hash"] = original_sha256
                if use_git:
                    with open(absolute_path, "rb") as handle:
                        original_bytes = handle.read()
                    result = subprocess.run(
                        ["git", "-C", root, "hash-object", "-w", "--stdin"],
                        input=original_bytes,
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        raise CodingSessionError(f"Falha ao criar blob Git para {relative_path}.")
                    blob_oid = result.stdout.decode("ascii", errors="ignore").strip()
                    record["git_blob_oid"] = blob_oid
                    record["blob"] = blob_oid
                else:
                    backup_path = checkpoint_dir / relative_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(absolute_path, backup_path)
                    record["backup_path"] = str(backup_path)
                    record["backup"] = str(backup_path)
            else:
                record["checkpoint_method"] = "absent_before"
            checkpoint["files"][relative_path] = record
        return checkpoint

    def _apply_change(self, session: CodingSession, root: str, change: dict[str, Any]) -> None:
        relative_path, absolute_path = self._safe_project_path(root, change["file"])
        write_metadata: dict[str, Any] = {}
        if change["operation"] == "create_file":
            if self.new_file_writer:
                result = self.new_file_writer(absolute_path, change["proposed_excerpt"])
            else:
                workspace_relative = os.path.relpath(absolute_path, self.projects.workspace_root).replace(os.sep, "/")
                from agents import tools as agent_tools

                result = agent_tools.write_file_sync(workspace_relative, change["proposed_excerpt"])
            if result.lower().startswith("erro"):
                raise CodingSessionError(result)
            resulting_sha256, resulting_size = self._sha256_file_bytes(absolute_path)
            write_metadata = {
                "physical_write_strategy": "write_file",
                "original_size": 0,
                "resulting_size": resulting_size,
                "original_sha256": None,
                "resulting_sha256": resulting_sha256,
                "full_file_logical_rewrite": True,
                "full_file_physical_write": True,
            }
        elif relative_path.endswith(".py") and change["operation"] == "replace_symbol":
            from agents.patch_engine import PatchEngine

            patcher = PatchEngine(root, create_backups=False, validate_python=False)
            result = patcher.apply_patch(relative_path, change["symbol"], change["proposed_excerpt"])
            if "Sucesso" not in result:
                raise CodingSessionError(result)
            write_metadata = {
                "physical_write_strategy": "patch_engine",
                "full_file_logical_rewrite": False,
                "full_file_physical_write": None,
            }
        else:
            write_metadata = self._apply_atomic_text_patch(absolute_path, relative_path, change)

        current_content = Path(absolute_path).read_text(encoding="utf-8")
        applied_change = {
            "file": relative_path,
            "after_hash": self._content_hash(current_content),
            "unified_diff": change["unified_diff"],
        }
        applied_change.update(write_metadata)
        session.applied_changes.append(applied_change)
        self._save(session)

    def _apply_atomic_text_patch(
        self,
        absolute_path: str,
        relative_path: str,
        change: dict[str, Any],
    ) -> dict[str, Any]:
        original_bytes = Path(absolute_path).read_bytes()
        has_utf8_bom = original_bytes.startswith(b"\xef\xbb\xbf")
        payload = original_bytes[3:] if has_utf8_bom else original_bytes
        try:
            original_text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CodingSessionError(f"Encoding UTF-8 invalido em {relative_path}.") from exc

        normalized_text, boundaries = self._normalize_newlines_with_boundaries(original_text)
        old_text = str(change["previous_excerpt"]).replace("\r\n", "\n").replace("\r", "\n")
        new_text = str(change["proposed_excerpt"]).replace("\r\n", "\n").replace("\r", "\n")
        occurrences = normalized_text.count(old_text)
        if occurrences != 1:
            raise CodingSessionError(
                f"Patch controlado recusado em {relative_path}: trecho anterior ocorre {occurrences} vezes."
            )
        normalized_start = normalized_text.index(old_text)
        normalized_end = normalized_start + len(old_text)
        raw_start = boundaries[normalized_start]
        raw_end = boundaries[normalized_end]
        replaced_raw_text = original_text[raw_start:raw_end]
        newline = self._preferred_newline(original_text, replaced_raw_text)
        rendered_new_text = new_text.replace("\n", newline)
        resulting_text = original_text[:raw_start] + rendered_new_text + original_text[raw_end:]
        resulting_text = self._preserve_final_newline(original_text, resulting_text, newline)
        resulting_payload = resulting_text.encode("utf-8")
        resulting_bytes = (b"\xef\xbb\xbf" if has_utf8_bom else b"") + resulting_payload

        normalized_result = resulting_text.replace("\r\n", "\n").replace("\r", "\n")
        logical_scope = self._logical_edit_scope(normalized_text, normalized_result)
        original_sha256 = hashlib.sha256(original_bytes).hexdigest()
        resulting_sha256 = hashlib.sha256(resulting_bytes).hexdigest()
        self._atomic_replace_bytes(absolute_path, resulting_bytes)
        return {
            "logical_edit_scope": logical_scope,
            "physical_write_strategy": "atomic_full_file_replace",
            "full_file_logical_rewrite": old_text == normalized_text,
            "full_file_physical_write": True,
            "original_size": len(original_bytes),
            "resulting_size": len(resulting_bytes),
            "original_sha256": original_sha256,
            "resulting_sha256": resulting_sha256,
            "changed_line_count": logical_scope["changed_line_count"],
            "total_line_count": logical_scope["total_line_count"],
            "logical_change_ratio": logical_scope["logical_change_ratio"],
            "encoding": "utf-8-sig" if has_utf8_bom else "utf-8",
            "newline": "crlf" if newline == "\r\n" else "lf",
            "final_newline": resulting_text.endswith(("\n", "\r")),
        }

    @staticmethod
    def _normalize_newlines_with_boundaries(text: str) -> tuple[str, list[int]]:
        normalized: list[str] = []
        boundaries = [0]
        index = 0
        while index < len(text):
            if text.startswith("\r\n", index):
                normalized.append("\n")
                index += 2
            elif text[index] == "\r":
                normalized.append("\n")
                index += 1
            else:
                normalized.append(text[index])
                index += 1
            boundaries.append(index)
        return "".join(normalized), boundaries

    @staticmethod
    def _preferred_newline(text: str, replaced_text: str) -> str:
        replaced_crlf = replaced_text.count("\r\n")
        replaced_lf = replaced_text.count("\n") - replaced_crlf
        if replaced_crlf and not replaced_lf:
            return "\r\n"
        if replaced_lf and not replaced_crlf:
            return "\n"
        crlf = text.count("\r\n")
        lf = text.count("\n") - crlf
        return "\r\n" if crlf > lf else "\n"

    @staticmethod
    def _preserve_final_newline(original: str, resulting: str, newline: str) -> str:
        original_has_final = original.endswith(("\n", "\r"))
        resulting_has_final = resulting.endswith(("\n", "\r"))
        if original_has_final and not resulting_has_final:
            return resulting + newline
        if not original_has_final and resulting_has_final:
            return resulting.rstrip("\r\n")
        return resulting

    @staticmethod
    def _logical_edit_scope(original: str, resulting: str) -> dict[str, Any]:
        original_lines = original.splitlines()
        resulting_lines = resulting.splitlines()
        total_line_count = max(len(original_lines), len(resulting_lines), 1)
        if original == resulting:
            return {
                "changed_line_count": 0,
                "changed_region_count": 0,
                "total_line_count": total_line_count,
                "logical_change_ratio": 0.0,
            }

        prefix = 0
        while (
            prefix < len(original_lines)
            and prefix < len(resulting_lines)
            and original_lines[prefix] == resulting_lines[prefix]
        ):
            prefix += 1

        original_end = len(original_lines)
        resulting_end = len(resulting_lines)
        suffix = 0
        while (
            original_end - suffix > prefix
            and resulting_end - suffix > prefix
            and original_lines[original_end - suffix - 1] == resulting_lines[resulting_end - suffix - 1]
        ):
            suffix += 1

        original_core = original_lines[prefix : original_end - suffix]
        resulting_core = resulting_lines[prefix : resulting_end - suffix]

        # A controlled textual patch has one logical region. Avoid quadratic
        # SequenceMatcher work when a large file contains repeated lines.
        if len(original_core) * len(resulting_core) > 4_000_000:
            changed_line_count = max(len(original_core), len(resulting_core), 1)
            return {
                "changed_line_count": changed_line_count,
                "changed_region_count": 1,
                "total_line_count": total_line_count,
                "logical_change_ratio": changed_line_count / total_line_count,
            }

        matcher = difflib.SequenceMatcher(a=original_core, b=resulting_core, autojunk=False)
        changed_line_count = 0
        changed_region_count = 0
        for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            changed_region_count += 1
            changed_line_count += max(old_end - old_start, new_end - new_start)
        return {
            "changed_line_count": changed_line_count,
            "changed_region_count": changed_region_count,
            "total_line_count": total_line_count,
            "logical_change_ratio": changed_line_count / total_line_count,
        }

    @staticmethod
    def _atomic_replace_bytes(path: str, content: bytes) -> None:
        directory = os.path.dirname(path)
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{Path(path).name}.",
            suffix=".jarvis-tmp",
            dir=directory,
        )
        try:
            original_mode = os.stat(path).st_mode
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, original_mode)
            os.replace(temporary_path, path)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            raise

    def _run_validations(self, session: CodingSession, root: str) -> list[dict[str, Any]]:
        current_context = self.projects.open_project(session.project_id).to_dict()
        allowed_commands = {item.get("command") for item in current_context.get("suggested_commands", [])}
        results = []
        for validation in session.change_plan.get("validations", []):
            started = time.perf_counter()
            command = validation["command"]
            if command == "__jarvis_static_preview__":
                exit_code, stdout, stderr = self._run_preview_validation(session.project_id)
            elif command not in allowed_commands and not self._affected_syntax_command(
                command,
                session.proposed_changes,
                current_context,
            ):
                exit_code, stdout, stderr = 126, "", "Comando deixou de estar autorizado pelo ProjectContext."
            else:
                resolved_python_command = self._is_resolved_python_command(command, current_context)
                allowed, reason = (True, "") if resolved_python_command else validate_local_command(command)
                if not allowed or "obsidian" in command.lower():
                    exit_code, stdout, stderr = 126, "", reason or "Comando bloqueado."
                else:
                    exit_code, stdout, stderr = self._execute_validation_command(command, root)
            results.append({
                "kind": validation["kind"],
                "command": command,
                "required": bool(validation.get("required")),
                "exit_code": exit_code,
                "stdout": stdout[-8000:],
                "stderr": stderr[-8000:],
                "duration_seconds": round(time.perf_counter() - started, 3),
            })
        return results

    @staticmethod
    def _affected_syntax_command(
        command: str,
        changes: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> bool:
        allowed = set()
        python_executable = context.get("python_executable")
        for change in changes:
            suffix = Path(change["file"]).suffix.lower()
            if suffix == ".py" and python_executable:
                allowed.add(ProjectContextService.python_module_command(
                    python_executable,
                    "py_compile",
                    [change["file"]],
                ))
            elif suffix in {".js", ".mjs", ".cjs"}:
                allowed.add(f'node --check "{change["file"]}"')
        return command in allowed

    @staticmethod
    def _is_resolved_python_command(command: str, context: dict[str, Any]) -> bool:
        executable = context.get("python_executable")
        if not executable:
            return False
        if os.name == "nt":
            prefix = f'& "{str(executable).replace(chr(34), "`" + chr(34))}" -m '
        else:
            import shlex

            prefix = f"{shlex.quote(str(executable))} -m "
        return command.startswith(prefix)

    def _run_preview_validation(self, project_id: str) -> tuple[int, str, str]:
        logs: list[str] = []
        try:
            preview = self.projects.preview_project(project_id, logs.append)
            url = preview.get("preview_url")
            if not url:
                return 1, "".join(logs), "Preview nao produziu URL."
            last_error = ""
            for _ in range(10):
                try:
                    with urllib.request.urlopen(url, timeout=2) as response:
                        if 200 <= response.status < 400:
                            return 0, f"Preview respondeu em {url}", ""
                except Exception as exc:
                    last_error = str(exc)
                    time.sleep(0.2)
            return 1, "".join(logs), last_error or "Preview indisponivel."
        finally:
            sandbox.stop_custom_project()

    @staticmethod
    def _execute_validation_command(command: str, root: str) -> tuple[int, str, str]:
        try:
            if os.name == "nt":
                args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
            else:
                args = ["sh", "-c", command]
            result = subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=180)
            return result.returncode, result.stdout or "", result.stderr or ""
        except subprocess.TimeoutExpired as exc:
            return 124, exc.stdout or "", "Validacao excedeu 180 segundos."
        except OSError as exc:
            return 127, "", str(exc)

    def _restore_checkpoint(self, session: CodingSession, root: str) -> None:
        checkpoint_type = session.checkpoint.get("type")
        for relative_path, record in session.checkpoint.get("files", {}).items():
            _, absolute_path = self._safe_project_path(root, relative_path)
            existed_before = record.get("existed_before", record.get("existed", False))
            if not existed_before:
                if os.path.exists(absolute_path):
                    os.remove(absolute_path)
                continue
            if checkpoint_type == "git_blob":
                blob_oid = record.get("git_blob_oid") or record.get("blob")
                result = subprocess.run(
                    ["git", "-C", root, "cat-file", "blob", blob_oid],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    raise CodingSessionError(f"Nao foi possivel restaurar {relative_path} pelo Git.")
                Path(absolute_path).parent.mkdir(parents=True, exist_ok=True)
                Path(absolute_path).write_bytes(result.stdout)
            else:
                backup_path = record.get("backup_path") or record.get("backup")
                if not backup_path or not os.path.isfile(backup_path):
                    raise CodingSessionError(f"Backup de {relative_path} nao encontrado.")
                Path(absolute_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, absolute_path)
            restored_hash, restored_size = self._sha256_file_bytes(absolute_path)
            expected_hash = record.get("original_sha256") or record.get("before_hash")
            expected_size = record.get("size_bytes")
            if restored_hash != expected_hash or (expected_size is not None and restored_size != expected_size):
                raise CodingSessionError(
                    f"A restauracao binaria de {relative_path} nao corresponde ao checkpoint: "
                    f"sha256 esperado={expected_hash}, obtido={restored_hash}, "
                    f"bytes esperados={expected_size}, obtidos={restored_size}."
                )

    @staticmethod
    def _sha256_file_bytes(path: str) -> tuple[str, int]:
        digest = hashlib.sha256()
        size_bytes = 0
        with open(path, "rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
        return digest.hexdigest(), size_bytes

    def _assert_index_current(self, context: dict[str, Any], root: str, changes: list[dict[str, Any]]) -> None:
        ast_index = context.get("ast_index") or {}
        source_hashes = ast_index.get("source_hashes") or {}
        file_metadata = ast_index.get("files") or {}
        if not context.get("last_indexed_at"):
            raise CodingSessionError("O indice esta ausente ou desatualizado. Reindexe o projeto.")
        for change in changes:
            if not change.get("existed"):
                continue
            relative_path, absolute_path = self._safe_project_path(root, change["file"])
            metadata = file_metadata.get(relative_path) or {}
            if not metadata.get("hash_available"):
                reason = metadata.get("reason") or "hash_unavailable"
                if reason == "transaction_limit_exceeded":
                    limit = ast_index.get("transaction_limit_bytes")
                    raise CodingSessionError(
                        f"{relative_path} excede o limite transacional de {limit} bytes."
                    )
                raise CodingSessionError(
                    f"Integridade transacional indisponivel para {relative_path}: {reason}."
                )
            current_record = self.projects.file_integrity_record(
                absolute_path,
                content_indexed=bool(metadata.get("content_indexed")),
            )
            current_hash = current_record.get("source_hash")
            if source_hashes.get(relative_path) != current_hash:
                raise CodingSessionError(f"O indice esta desatualizado para {relative_path}. Reindexe antes de aplicar.")

    def _assert_proposals_still_match(self, root: str, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            _, absolute_path = self._safe_project_path(root, change["file"])
            if change.get("existed"):
                current = Path(absolute_path).read_text(encoding="utf-8")
                if self._content_hash(current) != change.get("before_hash"):
                    raise CodingSessionError(f"{change['file']} mudou depois da proposta; a aplicacao foi bloqueada.")
            elif os.path.exists(absolute_path):
                raise CodingSessionError(f"{change['file']} foi criado depois da proposta; a aplicacao foi bloqueada.")

    def _verify_applied_changes(self, root: str, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            _, absolute_path = self._safe_project_path(root, change["file"])
            if not os.path.isfile(absolute_path):
                raise CodingSessionError(f"Ficheiro esperado nao foi alterado: {change['file']}")
            current = Path(absolute_path).read_text(encoding="utf-8")
            if self._content_hash(current) != change["after_hash"]:
                raise CodingSessionError(f"O diff final de {change['file']} nao corresponde ao plano.")

    def _safe_project_path(self, root: str, path_value: Any) -> tuple[str, str]:
        raw = str(path_value or "").strip().replace("\\", "/")
        if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
            raise CodingSessionError("Path de alteracao invalido.")
        if any(part in {"", ".", ".."} for part in raw.split("/")):
            raise CodingSessionError("Path de alteracao invalido ou fora do projeto.")
        if "obsidian" in raw.lower():
            raise CodingSessionError("Obsidian nao pode ser alterado por uma CodingSession.")
        absolute = os.path.realpath(os.path.abspath(os.path.join(root, raw)))
        project_root = os.path.realpath(os.path.abspath(root))
        try:
            if os.path.commonpath([project_root, absolute]) != project_root:
                raise CodingSessionError("Tentativa de alterar ficheiro fora do projeto.")
        except ValueError as exc:
            raise CodingSessionError("Tentativa de alterar ficheiro fora do projeto.") from exc
        return raw, absolute

    @staticmethod
    def _symbol_code(graph: dict[str, Any], relative_path: str, symbol_name: str) -> str | None:
        data = graph.get(relative_path) or {}
        for item in data.get("classes", []) + data.get("functions", []):
            if item.get("name") == symbol_name and isinstance(item.get("code"), str):
                return item["code"]
        return None

    @staticmethod
    def _replace_once(content: str, old_text: str, new_text: str, relative_path: str) -> str:
        if not old_text:
            return new_text
        occurrences = content.count(old_text)
        if occurrences != 1:
            raise CodingSessionError(
                f"Patch controlado recusado em {relative_path}: trecho anterior ocorre {occurrences} vezes."
            )
        return content.replace(old_text, new_text, 1)

    @staticmethod
    def _unified_diff(relative_path: str, old_content: str, new_content: str) -> str:
        return "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        ))

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _exception_details(exc: Exception) -> dict[str, str]:
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        }

    @staticmethod
    def _limited_files(files: dict[str, str], limit: int = 60_000) -> dict[str, str]:
        selected: dict[str, str] = {}
        used = 0
        for path, content in files.items():
            remaining = limit - used
            if remaining <= 0:
                break
            selected[path] = content[:remaining]
            used += len(selected[path])
        return selected

    @staticmethod
    def _validate_llm_plan(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        changes = data.get("changes")
        if not isinstance(changes, list) or not changes:
            raise CodingSessionError("O JSON nao contem changes.")
        risks = data.get("risks") if isinstance(data.get("risks"), list) else []
        return changes, [str(item) for item in risks]

    def _session_dir(self, project_id: str, session_id: str) -> str:
        return os.path.join(self.projects.metadata_dir(project_id), "coding_sessions", session_id)

    def _session_path(self, project_id: str, session_id: str) -> str:
        return os.path.join(self._session_dir(project_id, session_id), "session.json")

    def _save(self, session: CodingSession) -> None:
        session.updated_at = datetime.now(timezone.utc).isoformat()
        path = Path(self._session_path(session.project_id, session.session_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


async def request_edit_plan_from_ollama(payload: dict[str, Any], correction: str | None = None) -> str:
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    correction_text = f"\nCorrige este erro da resposta anterior: {correction}" if correction else ""
    system = (
        "Es um planeador de alteracoes de codigo. Responde apenas JSON valido. Nao chames tools. "
        "Nao uses Obsidian, nao apagues ficheiros e nao inventes paths. Usa apenas ficheiros, simbolos e conteudo fornecidos."
    )
    user = (
        "Produz JSON com {\"changes\":[{\"file\":\"...\",\"operation\":\"replace_symbol|replace_text|create_file\","
        "\"symbol\":\"opcional\",\"old_text\":\"obrigatorio para replace_text\",\"new_code\":\"...\","
        "\"reason\":\"...\"}],\"risks\":[\"...\"]}. "
        "Para funcoes/classes usa replace_symbol e devolve o bloco completo do simbolo. "
        f"Dados reais do projeto: {json.dumps(payload, ensure_ascii=False)}{correction_text}"
    )
    request = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "top_p": 0.8},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post("http://localhost:11434/api/chat", json=request)
        response.raise_for_status()
        data = response.json()
    return str((data.get("message") or {}).get("content") or "")


async def _maybe_await(requester: PlanRequester, payload: dict[str, Any], correction: str | None):
    result = requester(payload, correction)
    if asyncio.iscoroutine(result):
        return await result
    return result


def _extract_json(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise CodingSessionError("A resposta nao contem um objeto JSON valido.")
