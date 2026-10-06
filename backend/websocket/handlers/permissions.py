"""
JARVIS OS — Permission Gateway WebSocket Handler
Handles real-time Just-in-Time permission requests, user decisions,
and capability verification events over WebSocket / IPC.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from security.permission_gateway.dependency_governance import get_dependency_governor
from security.permission_gateway.gateway import (
    CrossProjectApprovalError,
    InvalidApprovalStateError,
    PermissionBlockedByPolicyError,
    PermissionExpiredError,
    PermissionGatewayService,
    PermissionNotFoundError,
    get_permission_gateway_service,
)

logger = logging.getLogger("permissions.websocket")

PERMISSION_HANDLERS = {
    "action_confirm_response": "handle_action_confirm_response",
    "permission_get_pending": "handle_get_pending",
    "permission_approve": "handle_approve",
    "permission_deny": "handle_deny",
    "permission_rollback": "handle_rollback",
    "permission_resolve_choice": "handle_resolve_choice",
}


class PermissionGatewayWebSocketHandler:
    """Handler de WebSocket e IPC para o Human-in-the-Loop Permission Gateway."""

    def __init__(
        self,
        gateway: PermissionGatewayService | None = None,
        connections: ConnectionManager | None = None,
    ) -> None:
        self.gateway = gateway or get_permission_gateway_service()
        self.connections = connections

        if self.connections:
            # Regista broadcast automático de eventos do gateway para os clientes WebSocket
            self.gateway.register_broadcast_callback(self._on_gateway_event)

    def _on_gateway_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.connections:
            return
        msg = {"type": event_type, **payload}
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.connections.broadcast(msg))
        except Exception as e:
            logger.debug(f"Não foi possível agendar broadcast de {event_type}: {e}")

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, PERMISSION_HANDLERS)

    async def handle_get_pending(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        pending = [r.to_dict() for r in self.gateway.get_pending_requests()]
        if self.connections:
            await self.connections.send(
                websocket,
                {
                    "type": "permission_pending_list",
                    "data": pending,
                },
            )

    async def handle_approve(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        request_id = str(message.get("request_id", "")).strip()
        user = str(message.get("user") or getattr(session, "user_id", None) or "human_operator").strip()
        session_id = str(message.get("session_id") or getattr(session, "session_id", None) or "web_session").strip()
        project_id = message.get("project_id") or getattr(session, "selected_project_id", None)
        mission_id = message.get("mission_id")

        try:
            req = self.gateway.approve_request(
                request_id=request_id,
                user=user,
                session_id=session_id,
                project_id=project_id,
                mission_id=mission_id,
            )
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_request_approved",
                        "request": req.to_dict(),
                        "success": True,
                    },
                )
        except (
            PermissionNotFoundError,
            PermissionExpiredError,
            PermissionBlockedByPolicyError,
            CrossProjectApprovalError,
            InvalidApprovalStateError,
        ) as err:
            logger.warning(f"Rejeição ao aprovar pedido '{request_id}': {err}")
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_request_approved",
                        "request_id": request_id,
                        "success": False,
                        "error": str(err),
                    },
                )

    async def handle_deny(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        request_id = str(message.get("request_id", "")).strip()
        reason = str(message.get("reason", "Recusado pelo utilizador")).strip()
        user = str(message.get("user") or getattr(session, "user_id", None) or "human_operator").strip()
        session_id = str(message.get("session_id") or getattr(session, "session_id", None) or "web_session").strip()
        project_id = message.get("project_id") or getattr(session, "selected_project_id", None)
        mission_id = message.get("mission_id")

        try:
            req = self.gateway.deny_request(
                request_id=request_id,
                user=user,
                session_id=session_id,
                reason=reason,
                project_id=project_id,
                mission_id=mission_id,
            )
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_request_denied",
                        "request": req.to_dict(),
                        "success": True,
                    },
                )
        except Exception as err:
            logger.warning(f"Erro ao rejeitar pedido '{request_id}': {err}")
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_request_denied",
                        "request_id": request_id,
                        "success": False,
                        "error": str(err),
                    },
                )

    async def handle_action_confirm_response(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        decision = str(message.get("decision", "")).strip().upper()
        if decision in {"APPROVE", "USER_APPROVED", "CONFIRM", "AUTHORIZED"}:
            await self.handle_approve(websocket, message, session)
        else:
            await self.handle_deny(websocket, message, session)

    async def handle_rollback(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        request_id = str(message.get("request_id", "")).strip()
        user = str(message.get("user") or getattr(session, "user_id", None) or "human_operator").strip()

        try:
            rec = self.gateway.rollback_request(request_id=request_id, user=user)
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_execution_result",
                        "request_id": request_id,
                        "rollback": rec.to_dict(),
                        "status": "ROLLED_BACK",
                    },
                )
        except Exception as err:
            logger.warning(f"Erro ao reverter '{request_id}': {err}")
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_execution_result",
                        "request_id": request_id,
                        "status": "FAILED",
                        "error": str(err),
                    },
                )

    async def handle_resolve_choice(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        request_id = str(message.get("request_id", "")).strip()
        action = str(message.get("action", "")).strip()
        user = str(message.get("user") or getattr(session, "user_id", None) or "human_operator").strip()
        governor = get_dependency_governor()

        try:
            result = governor.resolve_user_decision(request_id, action, user_id=user)
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_capability_result",
                        "request_id": request_id,
                        **result,
                    },
                )
        except Exception as err:
            logger.warning(f"Erro ao resolver decisão '{action}' para pedido '{request_id}': {err}")
            if self.connections:
                await self.connections.send(
                    websocket,
                    {
                        "type": "permission_capability_result",
                        "request_id": request_id,
                        "status": "ERROR",
                        "error": str(err),
                    },
                )
