from __future__ import annotations

from typing import Any

from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import notes_from_output


KNOWLEDGE_HANDLERS = {
    "get_notes": "get_notes",
    "read_note": "read_note",
    "save_note": "save_note",
    "get_rules": "get_rules",
    "delete_rule": "delete_rule",
    "delete_architecture": "delete_architecture",
    "delete_decision": "delete_decision",
    "get_vault_diagnostics": "get_vault_diagnostics",
    "audit_note_quality": "audit_note_quality",
    "enrich_note": "enrich_note",
    "rollback_note": "rollback_note",
    "get_queue_status": "get_queue_status",
    "pause_queue_worker": "pause_queue_worker",
    "resume_queue_worker": "resume_queue_worker",
    "start_improvement_batch": "start_improvement_batch",
}


class KnowledgeWebSocketHandler:
    def __init__(
        self,
        agents: Any,
        database: Any,
        connections: ConnectionManager,
    ) -> None:
        self.agents = agents
        self.database = database
        self.connections = connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, KNOWLEDGE_HANDLERS)

    async def get_notes(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        notes = await self.agents.run_obsidian_list_notes()
        await self.connections.send(
            websocket,
            {
                "type": "notes_list",
                "notes": notes_from_output(notes),
            },
        )

    async def read_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        content = await self.agents.run_obsidian_read_note(
            filename
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_content",
                "filename": filename,
                "content": content,
            },
        )

    async def save_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        result = await self.agents.run_obsidian_write_note(
            filename,
            message.get("content"),
        )
        notes = await self.agents.run_obsidian_list_notes()
        await self.connections.broadcast(
            {
                "type": "notes_list",
                "notes": notes_from_output(notes),
            }
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_saved",
                "filename": filename,
                "result": result,
            },
        )

    async def get_rules(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "rules_list",
                "rules": (
                    self.database.get_compounding_rules()
                ),
            },
        )

    async def delete_rule(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_compounding_rule(
            message.get("key")
        )
        rules = self.database.get_compounding_rules()
        await self.connections.broadcast(
            {"type": "rules_list", "rules": rules}
        )
        await self.connections.broadcast(
            {"type": "rules_updated", "rules": rules}
        )

    async def delete_architecture(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_architecture_memory(
            message.get("module")
        )
        architecture = (
            self.database.get_architecture_memory()
        )
        await self.connections.broadcast(
            {
                "type": "architecture_updated",
                "architecture": architecture,
            }
        )

    async def delete_decision(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_engineering_decision(
            message.get("decision")
        )
        decisions = (
            self.database.get_engineering_decisions()
        )
        await self.connections.broadcast(
            {
                "type": "decisions_updated",
                "decisions": decisions,
            }
        )

    async def get_vault_diagnostics(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        diagnostics = engine.compute_graph_diagnostics()
        queue = engine.load_queue()
        await self.connections.send(
            websocket,
            {
                "type": "vault_diagnostics",
                "diagnostics": diagnostics,
                "queue": queue[:25],
            },
        )

    async def audit_note_quality(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename") or ""
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        audit_res = engine.audit_note_quality(filename)
        await self.connections.send(
            websocket,
            {
                "type": "note_quality_audit",
                "audit": audit_res,
            },
        )

    async def enrich_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename") or ""
        auto_apply = bool(message.get("auto_apply", True))
        from services.obsidian_graph_engine import (
            ObsidianGraphEngine,
            ObsidianSecurityError,
            ObsidianNotFoundError,
            ObsidianConcurrencyError,
        )
        engine = ObsidianGraphEngine()
        try:
            proposal = engine.enrich_note_safely(filename, auto_apply=auto_apply)
            await self.connections.send(
                websocket,
                {
                    "type": "note_enrichment_result",
                    "success": True,
                    "proposal": proposal,
                },
            )
        except ObsidianSecurityError as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_enrichment_result",
                    "success": False,
                    "error": str(err),
                    "code": "SECURITY_VIOLATION",
                },
            )
        except ObsidianNotFoundError as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_enrichment_result",
                    "success": False,
                    "error": str(err),
                    "code": "NOT_FOUND",
                },
            )
        except ObsidianConcurrencyError as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_enrichment_result",
                    "success": False,
                    "error": str(err),
                    "code": "CONCURRENCY_CONFLICT",
                },
            )
        except Exception as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_enrichment_result",
                    "success": False,
                    "error": str(err),
                    "code": "INTERNAL_ERROR",
                },
            )

    async def rollback_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename") or ""
        backup_path = message.get("backup_path") or ""
        from services.obsidian_graph_engine import (
            ObsidianGraphEngine,
            ObsidianSecurityError,
            ObsidianNotFoundError,
        )
        engine = ObsidianGraphEngine()
        try:
            success = engine.rollback_note(filename, backup_path)
            await self.connections.send(
                websocket,
                {
                    "type": "note_rollback_result",
                    "success": success,
                    "filename": filename,
                },
            )
        except ObsidianSecurityError as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_rollback_result",
                    "success": False,
                    "filename": filename,
                    "error": str(err),
                    "code": "SECURITY_VIOLATION",
                },
            )
        except ObsidianNotFoundError as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_rollback_result",
                    "success": False,
                    "filename": filename,
                    "error": str(err),
                    "code": "NOT_FOUND",
                },
            )
        except Exception as err:
            await self.connections.send(
                websocket,
                {
                    "type": "note_rollback_result",
                    "success": False,
                    "filename": filename,
                    "error": str(err),
                    "code": "INTERNAL_ERROR",
                },
            )

    async def get_queue_status(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        status = engine.get_worker_status()
        queue = engine.load_queue()
        await self.connections.send(
            websocket,
            {
                "type": "queue_worker_status",
                "worker_state": status,
                "queue": queue[:25],
            },
        )

    async def pause_queue_worker(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        engine.pause_queue_worker()
        status = engine.get_worker_status()
        await self.connections.send(
            websocket,
            {
                "type": "queue_worker_status",
                "worker_state": status,
                "action": "paused",
            },
        )

    async def resume_queue_worker(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        engine.resume_queue_worker()
        status = engine.get_worker_status()
        await self.connections.send(
            websocket,
            {
                "type": "queue_worker_status",
                "worker_state": status,
                "action": "resumed",
            },
        )

    async def start_improvement_batch(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        batch_size = int(message.get("batch_size", 1))
        from services.obsidian_graph_engine import ObsidianGraphEngine
        engine = ObsidianGraphEngine()
        proposals = await engine.run_bounded_improvement_batch(batch_size=batch_size)
        diagnostics = engine.compute_graph_diagnostics()
        await self.connections.send(
            websocket,
            {
                "type": "improvement_batch_result",
                "proposals": proposals,
                "count_processed": len(proposals),
                "diagnostics": diagnostics,
            },
        )

