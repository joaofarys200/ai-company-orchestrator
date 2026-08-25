from __future__ import annotations

import logging
from typing import Any

from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from security.sentinel.watchdog import SentinelWatchdogService

logger = logging.getLogger("sentinel.websocket")

SENTINEL_HANDLERS = {
    "sentinel_get_status": "get_status",
    "sentinel_run_audit": "run_audit",
    "sentinel_get_baseline": "get_baseline",
    "sentinel_accept_known_good": "accept_known_good",
    "sentinel_get_actions": "get_actions",
    "sentinel_approve_action": "approve_action",
    "sentinel_reject_action": "reject_action",
    "sentinel_rollback_action": "rollback_action",
    "sentinel_submit_review": "submit_review",
    "sentinel_get_shadow_telemetry": "get_shadow_telemetry",
}


class SentinelWebSocketHandler:
    """Handler de WebSocket e IPC para o subsistema Security Sentinel (Fases S2 e S3)."""

    def __init__(
        self,
        watchdog: SentinelWatchdogService,
        connections: ConnectionManager,
    ) -> None:
        self.watchdog = watchdog
        self.connections = connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, SENTINEL_HANDLERS)

    async def get_status(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        status_payload = self.watchdog.get_status_dict()
        await self.connections.send(
            websocket,
            {
                "type": "sentinel_status",
                "data": status_payload,
            },
        )

    async def run_audit(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        logger.info("Manual audit requested via WebSocket/IPC")
        result = await self.watchdog.run_manual_audit()
        await self.connections.send(
            websocket,
            {
                "type": "sentinel_audit_completed",
                "data": result,
            },
        )
        # Broadcast updated status to all clients
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def get_baseline(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        baseline = self.watchdog.active_baseline
        if not baseline:
            baseline = self.watchdog.baseline_engine.get_active_baseline()

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_baseline",
                "data": baseline.to_dict() if baseline else None,
            },
        )

    async def accept_known_good(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        item_key = str(message.get("item_key", "")).strip()
        reason = str(message.get("reason", "Accepted by user")).strip()
        user = str(message.get("user", "local_user")).strip()

        if item_key:
            self.watchdog.accept_known_good(item_key, reason, user)
            logger.info("Item marked as Known Good: %s (reason: %s)", item_key, reason)

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_known_good_updated",
                "item_key": item_key,
                "status": "success",
            },
        )
        # Broadcast updated status
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def get_actions(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        actions = self.watchdog.get_actions()
        await self.connections.send(
            websocket,
            {
                "type": "sentinel_actions_list",
                "data": actions,
            },
        )

    async def approve_action(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        action_id = str(message.get("action_id", "")).strip()
        user = str(message.get("user", "human_operator")).strip()
        session_id = str(message.get("session_id", "web_session")).strip()
        incident_id = str(message.get("incident_id", "")).strip() or None

        success, action_dict, msg = await self.watchdog.approve_and_execute_action(
            action_id=action_id,
            user=user,
            session_id=session_id,
            incident_id=incident_id,
        )

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": success,
                "action": action_dict,
                "message": msg,
            },
        )
        # Broadcast updated actions and status
        await self.connections.broadcast({
            "type": "sentinel_actions_list",
            "data": self.watchdog.get_actions(),
        })
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def reject_action(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        action_id = str(message.get("action_id", "")).strip()
        user = str(message.get("user", "human_operator")).strip()
        reason = str(message.get("reason", "Rejeitado pelo utilizador")).strip()

        success, action_dict, msg = self.watchdog.reject_action(
            action_id=action_id,
            user=user,
            reason=reason,
        )

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": success,
                "action": action_dict,
                "message": msg,
            },
        )
        await self.connections.broadcast({
            "type": "sentinel_actions_list",
            "data": self.watchdog.get_actions(),
        })
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def rollback_action(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        action_id = str(message.get("action_id", "")).strip()
        user = str(message.get("user", "human_operator")).strip()
        session_id = str(message.get("session_id", "web_session")).strip()

        success, action_dict, msg = await self.watchdog.rollback_action(
            action_id=action_id,
            user=user,
            session_id=session_id,
        )

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": success,
                "action": action_dict,
                "message": msg,
            },
        )
        await self.connections.broadcast({
            "type": "sentinel_actions_list",
            "data": self.watchdog.get_actions(),
        })
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def submit_review(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        event_id = str(message.get("event_id", "")).strip()
        operator = str(message.get("operator", "human_operator")).strip()
        final_classification = str(message.get("final_classification", "BENIGN")).strip()
        reason = str(message.get("reason", "Revisão humana em Shadow Mode")).strip()

        review_dict = self.watchdog.submit_human_review(
            event_id=event_id,
            operator=operator,
            final_classification=final_classification,
            reason=reason,
        )

        await self.connections.send(
            websocket,
            {
                "type": "sentinel_review_result",
                "event_id": event_id,
                "success": review_dict is not None,
                "review": review_dict,
            },
        )
        await self.connections.broadcast({
            "type": "sentinel_status",
            "data": self.watchdog.get_status_dict(),
        })

    async def get_shadow_telemetry(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        telemetry = self.watchdog.get_shadow_telemetry()
        await self.connections.send(
            websocket,
            {
                "type": "sentinel_shadow_telemetry",
                "data": telemetry,
            },
        )

