import os
import json
import asyncio
import websockets
from backend.health import build_local_health_report
from backend.logging_config import get_logger, log_event
from backend.services.sandbox_service import start_frontend_http_server as start_frontend_http_server_service
from backend.services.local_app_service import (
    extract_local_app_query,
    find_local_app_request,
    find_path_executable,
    find_start_menu_shortcut,
    local_app_start_menu_roots,
    normalize_voice_command_text,
    normalized_phrase_in_text,
    open_local_application as open_local_application_service,
    quote_powershell_single,
)
from backend.server_helpers import (
    build_template_payload as build_template_payload_helper,
    get_template_suggestions,
    is_orchestration_result_error,
    markdown_to_html,
    normalize_persistent_plan,
    normalize_template_name,
    parse_file_context as parse_file_context_helper,
    read_persistent_plan_state as read_persistent_plan_state_helper,
)
from backend.services.model_service import ModelExecutionService
from backend.services.orchestration_runtime import (
    OrchestrationCallbacks,
    OrchestrationService,
)
from backend.services.chat_command_service import (
    ChatCommandCallbacks,
    ChatCommandService,
)
from backend.services.voice_runtime import (
    VoiceDirectiveService,
    VoiceRuntimeCallbacks,
)
from backend.startup import configure_runtime_environment
from backend.application_lifecycle import ApplicationLifecycle
from backend.application_runtime import ApplicationRuntimeState
from backend.application_services import (
    ApplicationServices,
    create_application_services,
)
from backend.websocket.gateway import (
    ConnectionManager,
    WebSocketGateway,
    extract_ws_token,
    get_ws_headers,
    get_ws_request_path,
    is_ws_authorized,
    reject_unauthorized_ws,
    resolve_under_base,
)
from backend.websocket.context import WebSocketSessionState
from backend.websocket.handlers.common import (
    WebSocketResponder,
    WebSocketRuntimeCallbacks,
)
from backend.websocket.handlers.missions import MissionWebSocketHandler
from backend.websocket.registry import create_websocket_handlers
from backend.message_protocol import (
    chat_message,
    file_message,
    kanban_message,
    normalize_ws_message,
    state_message,
    system_message,
    validate_client_message,
)
from backend.model_harness import (
    ModelResponse,
    OutputFormat,
)

configure_runtime_environment()

import database
import sandbox
import agents

PROJECT_ROOT = os.path.realpath(
    os.path.abspath(os.path.dirname(__file__))
)
connection_manager = ConnectionManager()

from security.sentinel.watchdog import SentinelWatchdogService

sentinel_watchdog = SentinelWatchdogService(
    scan_interval_seconds=60,
    event_callback=lambda ev: connection_manager.broadcast({
        "type": "sentinel_event",
        "event": ev.to_dict(),
    }),
    status_callback=lambda st: connection_manager.broadcast({
        "type": "sentinel_status",
        "data": st,
    }),
)

application_services = create_application_services(
    PROJECT_ROOT,
    database_module=database,
    agents_module=agents,
    sandbox_module=sandbox,
    sentinel_watchdog=sentinel_watchdog,
)
runtime_state = ApplicationRuntimeState()
logger = get_logger(__name__)
project_context_service = application_services.project_context
coding_session_service = application_services.coding_sessions
mission_planner = application_services.mission_planner
mission_executor_service = application_services.mission_executor
mission_autonomy_controller = application_services.mission_autonomy
model_execution_service = ModelExecutionService(
    application_services.model_harness
)

async def execute_model(
    *,
    provider: str,
    model: str,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    conversation_messages: list[dict] | None = None,
    output_format: OutputFormat = OutputFormat.TEXT,
    temperature: float = 0.0,
    max_output_tokens: int = 512,
    timeout_seconds: float = 30.0,
) -> ModelResponse:
    return await model_execution_service.execute(
        provider=provider,
        model=model,
        operation=operation,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        conversation_messages=conversation_messages,
        output_format=output_format,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


async def execute_local_model(
    *,
    operation: str,
    system_prompt: str,
    user_prompt: str,
    conversation_messages: list[dict] | None = None,
    output_format: OutputFormat = OutputFormat.TEXT,
    temperature: float = 0.0,
    max_output_tokens: int = 512,
    timeout_seconds: float = 30.0,
) -> ModelResponse:
    return await model_execution_service.execute_local(
        operation=operation,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        conversation_messages=conversation_messages,
        output_format=output_format,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )

def read_persistent_plan_state(path: str = ".jarvis_plan.json"):
    return read_persistent_plan_state_helper(
        path,
        logger=logger,
    )


def voice_confirmation_enabled() -> bool:
    return voice_runtime.confirmation_enabled()


async def open_local_application(app_request: dict) -> tuple[bool, str]:
    return await open_local_application_service(
        app_request,
        working_directory=PROJECT_ROOT,
    )


def is_voice_confirmation(text: str) -> bool:
    return voice_runtime.is_confirmation(text)


def is_voice_cancel(text: str) -> bool:
    return voice_runtime.is_cancel(text)


def is_voice_read_only_request(text: str) -> bool:
    return voice_runtime.is_read_only_request(text)


def init_voice_service():
    return voice_runtime.initialize()


async def start_directive_orchestration(prompt: str):
    await voice_runtime.start_orchestration(prompt)


def pending_voice_directive_expired() -> bool:
    return voice_runtime.pending_expired()


async def clear_expired_voice_directive():
    await voice_runtime.clear_expired()


async def handle_voice_directive_candidate(prompt: str, source: str = "voice") -> str:
    return await voice_runtime.handle_candidate(
        prompt,
        source=source,
    )


async def confirm_pending_voice_directive(spoken_confirmation: str = "confirma", source: str = "voice") -> str:
    return await voice_runtime.confirm(
        spoken_confirmation,
        source=source,
    )


async def cancel_pending_voice_directive(spoken_cancel: str = "cancela", source: str = "voice") -> str:
    return await voice_runtime.cancel(
        spoken_cancel,
        source=source,
    )

# Active WebSocket connections
active_connections = connection_manager.connections
WS_HOST = "127.0.0.1"
WS_AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN") or os.getenv("WS_AUTH_TOKEN") or "local-dev-token"


def build_runtime_health() -> dict:
    return build_local_health_report(
        project_root=PROJECT_ROOT,
        websocket_host=WS_HOST,
        websocket_port=8001,
        active_connections_count=len(active_connections),
        sandbox_dir=sandbox.SANDBOX_DIR,
        sandbox_port=sandbox.PORT,
        frontend_port=8000,
    )

def _resolve_under_base(base_dir: str, requested_path: str):
    return resolve_under_base(base_dir, requested_path)

def _get_ws_request_path(websocket, args) -> str:
    return get_ws_request_path(websocket, args)

def _get_ws_headers(websocket):
    return get_ws_headers(websocket)

def _extract_ws_token(websocket, args) -> str:
    return extract_ws_token(websocket, args)

def _is_ws_authorized(websocket, args) -> bool:
    return is_ws_authorized(websocket, args, WS_AUTH_TOKEN)

async def _reject_unauthorized_ws(websocket):
    await reject_unauthorized_ws(websocket)

def _current_application_services() -> ApplicationServices:
    """Return the shared runtime services with test-time aliases applied."""

    return application_services.with_overrides(
        database=database,
        agents=agents,
        sandbox=sandbox,
        project_context=project_context_service,
        coding_sessions=coding_session_service,
        mission_planner=mission_planner,
        mission_executor=mission_executor_service,
        mission_autonomy=mission_autonomy_controller,
    )


def _websocket_callbacks() -> WebSocketRuntimeCallbacks:
    return WebSocketRuntimeCallbacks(
        handle_slash_command=handle_slash_command,
        parse_file_context=parse_file_context,
        run_orchestration_task=run_orchestration_task,
        broadcast_state=broadcast_state,
        run_in_main_loop=run_in_main_loop,
        normalize_template_name=normalize_template_name,
        build_template_payload=build_template_payload,
        read_persistent_plan_state=read_persistent_plan_state,
        get_voice_service=lambda: voice_runtime.voice_service,
        conversation_history=runtime_state.conversation_history,
    )


async def broadcast(message: dict):
    await connection_manager.broadcast(message)

async def send_ws(websocket, message: dict):
    await connection_manager.send(websocket, message)


async def send_project_context(websocket, project_id: str, reindex: bool = False):
    services = _current_application_services()
    responder = WebSocketResponder(
        services.project_context,
        services.coding_sessions,
        services.mission_planner,
        connection_manager,
    )
    await responder.send_project_context(
        websocket,
        project_id,
        reindex=reindex,
    )


async def send_latest_coding_session(websocket, project_id: str):
    services = _current_application_services()
    responder = WebSocketResponder(
        services.project_context,
        services.coding_sessions,
        services.mission_planner,
        connection_manager,
    )
    await responder.send_latest_coding_session(
        websocket,
        project_id,
    )


async def send_mission_list(websocket, project_id: str):
    services = _current_application_services()
    responder = WebSocketResponder(
        services.project_context,
        services.coding_sessions,
        services.mission_planner,
        connection_manager,
    )
    await responder.send_mission_list(websocket, project_id)


async def dispatch_mission_operation(websocket, msg: dict, selected_project_id: str | None) -> bool:
    operation = str(msg.get("type") or "")
    if operation not in MissionWebSocketHandler.OPERATIONS:
        return False
    services = _current_application_services()
    responder = WebSocketResponder(
        services.project_context,
        services.coding_sessions,
        services.mission_planner,
        connection_manager,
    )
    handler = MissionWebSocketHandler(
        services.mission_planner,
        services.mission_executor,
        services.mission_autonomy,
        responder,
    )
    await handler.handle(
        websocket,
        msg,
        WebSocketSessionState(selected_project_id),
    )
    return True

async def broadcast_state(value: str):
    service = voice_runtime.voice_service
    if service:
        service.is_processing = (value == "processing")
    await broadcast(state_message(value))

def run_in_main_loop(coro):
    loop = runtime_state.main_loop
    if loop and loop.is_running():
        loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
    else:
        try:
            coro.close()
        except RuntimeError:
            pass

def on_agent_message(sender: str, role: str, content: str):
    message = chat_message(sender.upper(), role, content)
    # Track agent message in casual chat history to keep Jarvis in the loop about agent debates
    history = runtime_state.conversation_history
    history.append(
        {
            "role": "assistant",
            "content": f"[{sender} - {role}]: {content}",
        }
    )
    if len(history) > 30:
        history.pop(0)
        
    run_in_main_loop(broadcast(message))

def on_file_update(filename: str, content: str):
    message = file_message(filename, content)
    run_in_main_loop(broadcast(message))

def on_kanban_update(card_id: str, status: str):
    message = kanban_message(card_id, status)
    run_in_main_loop(broadcast(message))

def parse_file_context(prompt: str) -> str:
    return parse_file_context_helper(
        prompt,
        project_root=PROJECT_ROOT,
        sandbox_root=getattr(sandbox, "SANDBOX_DIR", ""),
        logger=logger,
    )

def build_template_payload(template_name: str) -> dict:
    return build_template_payload_helper(
        template_name,
        agents_module=agents,
    )


def _current_chat_command_service() -> ChatCommandService:
    return ChatCommandService(
        services=_current_application_services(),
        models=model_execution_service,
        connections=connection_manager,
        callbacks=ChatCommandCallbacks(
            broadcast_state=broadcast_state,
            on_agent_message=on_agent_message,
            on_file_update=on_file_update,
        ),
        logger=logger,
    )


async def query_model_for_arena(model_id: str, model_name: str, prompt: str):
    await _current_chat_command_service().query_arena_model(
        model_id,
        model_name,
        prompt,
    )

async def run_arena_comparison(prompt: str):
    await _current_chat_command_service().run_arena(prompt)

async def handle_slash_command(command_str: str, websocket, session_id: int):
    await _current_chat_command_service().handle(
        command_str,
        websocket,
        session_id,
    )

async def handle_client(websocket, *args):
    await websocket_gateway.handle_client(websocket, *args)


from backend.transport_gateway import StdioTransportGateway

_global_dispatcher = None
_global_initial_sync = None
stdio_transport_gateway: Optional[StdioTransportGateway] = None

def _create_websocket_gateway() -> WebSocketGateway:
    global _global_dispatcher, _global_initial_sync, stdio_transport_gateway
    _global_dispatcher, _global_initial_sync = create_websocket_handlers(
        services=_current_application_services(),
        connections=connection_manager,
        callbacks=_websocket_callbacks(),
        logger=logger,
    )
    stdio_transport_gateway = StdioTransportGateway(
        dispatcher=_global_dispatcher,
        logger=logger,
        on_connect=_global_initial_sync.handle,
        on_broadcast=lambda msg: connection_manager.broadcast(msg),
    )
    connection_manager.add_broadcast_hook(stdio_transport_gateway.send_message)
    return WebSocketGateway(
        auth_token=WS_AUTH_TOKEN,
        connections=connection_manager,
        dispatcher=_global_dispatcher,
        on_connect=_global_initial_sync.handle,
        logger=logger,
    )


def _current_orchestration_service() -> OrchestrationService:
    return OrchestrationService(
        services=_current_application_services(),
        models=model_execution_service,
        connections=connection_manager,
        callbacks=OrchestrationCallbacks(
            broadcast_state=broadcast_state,
            open_local_application=open_local_application,
            run_in_main_loop=run_in_main_loop,
            on_agent_message=on_agent_message,
            on_file_update=on_file_update,
            on_kanban_update=on_kanban_update,
            build_template_payload=build_template_payload,
        ),
        conversation_history=runtime_state.conversation_history,
        logger=logger,
    )


async def auto_extract_correction(prompt: str, history: list):
    await _current_orchestration_service().auto_extract_correction(
        prompt,
        history,
    )

async def classify_intent(prompt: str, history: list = None) -> str:
    return await _current_orchestration_service().classify_intent(
        prompt,
        history,
    )

async def run_casual_chat(prompt: str):
    await _current_orchestration_service().run_casual_chat(
        prompt
    )

async def run_orchestration_task(prompt: str, session_id: int):
    await _current_orchestration_service().run_task(
        prompt,
        session_id,
    )


def _create_voice_runtime() -> VoiceDirectiveService:
    return VoiceDirectiveService(
        services=_current_application_services(),
        connections=connection_manager,
        callbacks=VoiceRuntimeCallbacks(
            run_in_main_loop=lambda coro: run_in_main_loop(coro),
            broadcast_state=lambda value: broadcast_state(value),
            run_orchestration_task=(
                lambda prompt, session_id: run_orchestration_task(
                    prompt,
                    session_id,
                )
            ),
            open_local_application=(
                lambda app_request: open_local_application(
                    app_request
                )
            ),
        ),
        conversation_history=runtime_state.conversation_history,
        logger=logger,
    )


voice_runtime = _create_voice_runtime()
websocket_gateway = _create_websocket_gateway()


def start_frontend_http_server():
    return start_frontend_http_server_service(
        os.path.dirname(__file__),
        port=8000,
    )

def _free_port_if_locked(port: int = 8001) -> None:
    """Closes any orphaned background processes holding the port before binding."""
    try:
        if os.name == "nt":
            cmd = f'cmd.exe /c "for /f \\"tokens=5\\" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /f /pid %a"'
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


async def main():
    runtime_state.main_loop = asyncio.get_running_loop()
    lifecycle = ApplicationLifecycle(
        services=_current_application_services(),
        initialize_voice=init_voice_service,
        get_voice_service=lambda: voice_runtime.voice_service,
        start_frontend=start_frontend_http_server,
    )
    lifecycle.startup()

    # Trigger proactive background warmup for local Ollama inference model
    async def _async_warmup():
        try:
            harness = _current_application_services().model_harness
            provider = harness.registry.get("ollama")
            if provider and hasattr(provider, "warmup"):
                warmed = await provider.warmup()
                if warmed:
                    log_event(logger, "model_harness.ollama.warmup_succeeded")
        except Exception:
            pass

    asyncio.create_task(_async_warmup())

    # Start Native Stdio Transport Gateway for Electron desktop IPC
    stdio_task = None
    if stdio_transport_gateway is not None:
        stdio_task = stdio_transport_gateway.start(runtime_state.main_loop)
        log_event(logger, "stdio_ipc.gateway.started")

    # Start Sentinel continuous background watchdog
    try:
        await sentinel_watchdog.start()
        log_event(logger, "sentinel.watchdog.started", status=sentinel_watchdog.get_status_dict())
    except Exception as e:
        log_event(logger, "sentinel.watchdog.start_failed", error=str(e))

    log_event(logger, "runtime.health", health=build_runtime_health())
    log_event(logger, "websocket.server.starting", host=WS_HOST, port=8001)
    
    try:
        async with websockets.serve(handle_client, WS_HOST, 8001):
            await asyncio.Future()
    except OSError as exc:
        if exc.errno in (10048, 98):  # Address already in use
            _free_port_if_locked(8001)
            await asyncio.sleep(0.5)
            async with websockets.serve(handle_client, WS_HOST, 8001):
                await asyncio.Future()
        else:
            raise
    finally:
        try:
            await sentinel_watchdog.stop()
        except Exception:
            pass
        if stdio_transport_gateway is not None:
            stdio_transport_gateway.stop()
        lifecycle.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_event(logger, "server.shutdown")

