from __future__ import annotations

from typing import Any

from backend.application_services import ApplicationServices
from backend.message_protocol import CLIENT_MESSAGE_TYPES
from backend.websocket.contracts import EXPECTED_MESSAGE_TYPES
from backend.websocket.dispatcher import WebSocketDispatcher
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers.chat import ChatWebSocketHandler
from backend.websocket.handlers.coding import (
    CodingSessionWebSocketHandler,
)
from backend.websocket.handlers.common import (
    InitialSyncHandler,
    WebSocketResponder,
    WebSocketRuntimeCallbacks,
)
from backend.websocket.handlers.knowledge import (
    KnowledgeWebSocketHandler,
)
from backend.websocket.handlers.lectures import LectureWebSocketHandler
from backend.websocket.handlers.missions import (
    MissionWebSocketHandler,
)
from backend.websocket.handlers.projects import ProjectWebSocketHandler
from backend.websocket.handlers.sentinel import SentinelWebSocketHandler
from backend.websocket.handlers.system import SystemWebSocketHandler
from backend.websocket.handlers.voice import VoiceWebSocketHandler
from security.sentinel.watchdog import SentinelWatchdogService


def create_websocket_handlers(
    *,
    services: ApplicationServices,
    connections: ConnectionManager,
    callbacks: WebSocketRuntimeCallbacks,
    logger: Any,
) -> tuple[WebSocketDispatcher, InitialSyncHandler]:
    responder = WebSocketResponder(
        services.project_context,
        services.coding_sessions,
        services.mission_planner,
        connections,
    )
    dispatcher = WebSocketDispatcher(
        services=services,
        result_sender=connections.send,
        result_broadcaster=connections.broadcast,
    )
    watchdog = services.sentinel_watchdog or SentinelWatchdogService()

    domains = {
        "chat": ChatWebSocketHandler(
            services.agents,
            services.database,
            connections,
            callbacks,
            logger,
        ).routes(),
        "voice": VoiceWebSocketHandler(
            connections,
            callbacks,
        ).routes(),
        "project": ProjectWebSocketHandler(
            services.project_context,
            services.sandbox,
            responder,
            callbacks,
            logger,
        ).routes(),
        "coding": CodingSessionWebSocketHandler(
            services.coding_sessions,
            responder,
        ).routes(),
        "knowledge": KnowledgeWebSocketHandler(
            services.agents,
            services.database,
            connections,
        ).routes(),
        "system": SystemWebSocketHandler(
            services.project_context,
            connections,
            callbacks,
        ).routes(),
        "mission": MissionWebSocketHandler(
            services.mission_planner,
            services.mission_executor,
            services.mission_autonomy,
            responder,
        ).routes(),
        "lecture": LectureWebSocketHandler(
            connections=connections,
            logger=logger,
        ).routes(),
        "sentinel": SentinelWebSocketHandler(
            watchdog=watchdog,
            connections=connections,
        ).routes(),
    }
    for domain, routes in domains.items():
        dispatcher.register_many(routes, domain=domain)

    protocol_types = frozenset(CLIENT_MESSAGE_TYPES)
    if protocol_types != EXPECTED_MESSAGE_TYPES:
        raise RuntimeError(
            "Canonical WebSocket message types diverge from protocol: "
            f"missing={sorted(protocol_types - EXPECTED_MESSAGE_TYPES)}, "
            f"extra={sorted(EXPECTED_MESSAGE_TYPES - protocol_types)}"
        )

    missing = EXPECTED_MESSAGE_TYPES - dispatcher.message_types
    extra = dispatcher.message_types - EXPECTED_MESSAGE_TYPES
    if missing or extra:
        raise RuntimeError(
            "WebSocket handler registry diverges from protocol: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    initial_sync = InitialSyncHandler(
        services.agents,
        services.database,
        services.project_context,
        responder,
        callbacks,
        logger,
    )
    return dispatcher, initial_sync


__all__ = [
    "InitialSyncHandler",
    "WebSocketResponder",
    "WebSocketRuntimeCallbacks",
    "create_websocket_handlers",
]
