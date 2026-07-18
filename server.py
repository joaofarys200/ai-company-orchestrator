import os
import json
import asyncio
import websockets
import httpx
import base64
import re
import time
import unicodedata
import subprocess
import shutil
from backend.errors import safe_user_error
from backend.health import build_local_health_report
from backend.logging_config import get_logger, log_event
from backend.services.sandbox_service import start_frontend_http_server as start_frontend_http_server_service
from backend.services.voice_service import normalize_voice_prompt
from backend.startup import configure_runtime_environment
from backend.websocket_gateway import (
    extract_ws_token,
    get_ws_headers,
    get_ws_request_path,
    is_ws_authorized,
    reject_unauthorized_ws,
    resolve_under_base,
)
from backend.message_protocol import (
    chat_message,
    file_message,
    kanban_message,
    normalize_ws_message,
    state_message,
    system_message,
    validate_client_message,
)

configure_runtime_environment()

import database
import sandbox
import agents
from intelligence.project_context import ProjectContextError, ProjectContextService
from intelligence.coding_session import CodingSessionError, CodingSessionService
from agents.mission_state import MissionStateError
from agents.mission_executor import MissionExecutorService
from agents.planner_engine import PersistentPlanner
from voice_service import VoiceService

voice_service = None
conversation_history = []
pending_voice_directive = None
logger = get_logger(__name__)
project_context_service = ProjectContextService()
coding_session_service = CodingSessionService(project_context_service)
mission_planner = PersistentPlanner(os.path.dirname(os.path.abspath(__file__)))
mission_executor_service = MissionExecutorService(
    os.path.dirname(os.path.abspath(__file__)),
    mission_state=mission_planner.mission_state,
    coding_service=coding_session_service,
)

VOICE_CONFIRMATION_WORDS = {
    "confirma",
    "confirmo",
    "confirmar",
    "executa",
    "executar",
    "avanca",
    "arranca",
    "podes avancar",
    "sim confirma",
    "sim executa",
}
VOICE_CANCEL_WORDS = {
    "cancela",
    "cancelar",
    "anula",
    "para",
    "esquece",
    "ignora",
    "nao executes",
    "nao executar",
}

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed

def is_orchestration_result_error(result: str | None) -> bool:
    text = (result or "").lower()
    error_markers = [
        "fallback local interrompido",
        "limite de passos atingido",
        "erro:",
        "interrompido",
        "falhou",
        "falha",
        "recovery write_file falhou",
        "orquestracao interrompida",
        "orquestração interrompida",
        "erro controlado",
        "contrato operacional",
        "quality gate falhou",
    ]
    return any(marker in text for marker in error_markers)

def normalize_persistent_plan(plan_data):
    if not isinstance(plan_data, dict):
        return None
    status = str(plan_data.get("status") or "").upper()
    goal = str(plan_data.get("goal") or "").strip()
    steps = plan_data.get("steps")
    has_steps = isinstance(steps, list) and len(steps) > 0
    if status in {"NONE", "DONE", "COMPLETED"}:
        return None
    if not goal and not has_steps:
        return None
    return plan_data

def read_persistent_plan_state(path: str = ".jarvis_plan.json"):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return normalize_persistent_plan(json.load(f))
    except Exception as e:
        log_event(logger, "planner_state.read_error", level="error", error=str(e))
        return None

def voice_confirmation_enabled() -> bool:
    return env_bool("VOICE_CONFIRMATION_MODE", True)

def normalize_voice_command_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = without_accents.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()

LOCAL_APP_ACTION_WORDS = {
    "abre", "abrir", "abram", "abrir", "inicia", "iniciar", "executa", "executar",
    "corre", "correr", "lanca", "lancar", "arranca", "arrancar", "open", "start", "run",
}

LOCAL_APP_OPEN_ACTION_WORDS = {
    "abre", "abrir", "abram", "inicia", "iniciar", "lanca", "lancar",
    "arranca", "arrancar", "open", "start",
}

LOCAL_APP_FILLER_WORDS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
    "dos", "das", "no", "na", "nos", "nas", "por", "favor", "pf", "sff",
    "novamente", "outra", "vez", "app", "aplicacao", "programa",
}

LOCAL_APP_TARGETS = [
    {
        "id": "excel",
        "label": "Excel",
        "terms": ["excel", "microsoft excel", "folha de calculo", "folha calculo", "spreadsheet"],
        "command": "Start-Process -FilePath excel.exe",
    },
    {
        "id": "word",
        "label": "Word",
        "terms": ["word", "microsoft word"],
        "command": "Start-Process -FilePath winword.exe",
    },
    {
        "id": "powerpoint",
        "label": "PowerPoint",
        "terms": ["powerpoint", "power point", "microsoft powerpoint"],
        "command": "Start-Process -FilePath powerpnt.exe",
    },
    {
        "id": "outlook",
        "label": "Outlook",
        "terms": ["outlook", "microsoft outlook"],
        "command": "Start-Process -FilePath outlook.exe",
    },
    {
        "id": "notepad",
        "label": "Bloco de Notas",
        "terms": ["notepad", "bloco de notas", "bloco notas"],
        "command": "Start-Process -FilePath notepad.exe",
    },
    {
        "id": "calculator",
        "label": "Calculadora",
        "terms": ["calculadora", "calculator", "calc"],
        "command": "Start-Process -FilePath calc.exe",
    },
    {
        "id": "paint",
        "label": "Paint",
        "terms": ["paint", "mspaint"],
        "command": "Start-Process -FilePath mspaint.exe",
    },
    {
        "id": "explorer",
        "label": "Explorador de Ficheiros",
        "terms": ["explorador", "explorer", "ficheiros", "file explorer"],
        "command": "Start-Process -FilePath explorer.exe",
    },
    {
        "id": "chrome",
        "label": "Chrome",
        "terms": ["chrome", "google chrome"],
        "command": "Start-Process -FilePath chrome.exe",
    },
    {
        "id": "edge",
        "label": "Edge",
        "terms": ["edge", "microsoft edge"],
        "command": "Start-Process -FilePath msedge.exe",
    },
    {
        "id": "powershell",
        "label": "PowerShell",
        "terms": ["powershell", "power shell"],
        "command": "Start-Process -FilePath powershell.exe",
    },
    {
        "id": "cmd",
        "label": "Command Prompt",
        "terms": ["cmd", "command prompt", "linha de comandos"],
        "command": "Start-Process -FilePath cmd.exe",
    },
    {
        "id": "vscode",
        "label": "Visual Studio Code",
        "terms": ["visual studio code", "vs code", "vscode"],
        "command": "Start-Process -FilePath code",
    },
]

def normalized_phrase_in_text(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_voice_command_text(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in f" {text} "

def extract_local_app_query(prompt: str) -> str:
    normalized = normalize_voice_command_text(prompt)
    if not normalized:
        return ""
    words = normalized.split()
    action_index = next(
        (index for index, word in enumerate(words) if word in LOCAL_APP_ACTION_WORDS),
        -1,
    )
    if action_index < 0:
        return ""
    target_words = words[action_index + 1:]
    while target_words and target_words[0] in LOCAL_APP_FILLER_WORDS:
        target_words.pop(0)
    while target_words and target_words[-1] in LOCAL_APP_FILLER_WORDS:
        target_words.pop()
    return " ".join(target_words).strip()

def local_app_start_menu_roots() -> list[str]:
    roots = []
    program_data = os.getenv("PROGRAMDATA")
    app_data = os.getenv("APPDATA")
    if program_data:
        roots.append(os.path.join(program_data, "Microsoft", "Windows", "Start Menu", "Programs"))
    if app_data:
        roots.append(os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs"))
    return roots

def find_start_menu_shortcut(query: str):
    normalized_query = normalize_voice_command_text(query)
    if not normalized_query:
        return None
    query_words = normalized_query.split()
    best_match = None
    best_score = 0
    for root in local_app_start_menu_roots():
        if not os.path.isdir(root):
            continue
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith((".lnk", ".url")):
                    continue
                label = os.path.splitext(filename)[0]
                normalized_label = normalize_voice_command_text(label)
                score = 0
                if normalized_label == normalized_query:
                    score = 100
                elif normalized_label.startswith(normalized_query):
                    score = 85
                elif normalized_phrase_in_text(normalized_label, normalized_query):
                    score = 75
                elif all(word in normalized_label for word in query_words):
                    score = 60 + len(query_words)

                if score > best_score:
                    best_score = score
                    best_match = {
                        "label": label,
                        "path": os.path.join(current_root, filename),
                    }
    if best_score < 60:
        return None
    return best_match

def find_path_executable(query: str):
    normalized_query = normalize_voice_command_text(query).replace(" ", "")
    if not re.fullmatch(r"[a-z0-9_.-]{2,64}", normalized_query or ""):
        return None
    for candidate in (normalized_query, f"{normalized_query}.exe", f"{normalized_query}.cmd"):
        found = shutil.which(candidate)
        if found:
            return {"label": query.strip(), "path": found}
    return None

def quote_powershell_single(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"

def find_local_app_request(prompt: str):
    normalized = normalize_voice_command_text(prompt)
    if not normalized:
        return None
    words = normalized.split()
    action_words = {word for word in words if word in LOCAL_APP_ACTION_WORDS}
    if not action_words:
        return None

    for app in LOCAL_APP_TARGETS:
        if any(normalized_phrase_in_text(normalized, term) for term in app["terms"]):
            return app

    query = extract_local_app_query(prompt)
    if not query:
        return None

    shortcut = find_start_menu_shortcut(query)
    if shortcut:
        return {
            "id": "start_menu_shortcut",
            "label": shortcut["label"],
            "path": shortcut["path"],
            "source": "start_menu",
        }

    if action_words & LOCAL_APP_OPEN_ACTION_WORDS:
        executable = find_path_executable(query)
        if executable:
            return {
                "id": "path_executable",
                "label": executable["label"],
                "path": executable["path"],
                "source": "path",
            }
    return None

async def open_local_application(app_request: dict) -> tuple[bool, str]:
    if "command" in app_request:
        command = app_request["command"]
    elif "path" in app_request:
        command = f"Start-Process -FilePath {quote_powershell_single(app_request['path'])}"
    else:
        return False, "Aplicacao local nao resolvida."
    loop = asyncio.get_running_loop()

    def run_cmd():
        try:
            process = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
                cwd=PROJECT_ROOT,
            )
            output = "\n".join(part for part in [process.stdout, process.stderr] if part).strip()
            if process.returncode == 0:
                return True, output
            return False, output or f"PowerShell terminou com codigo {process.returncode}."
        except subprocess.TimeoutExpired:
            return False, "O comando excedeu o tempo limite ao tentar abrir a aplicacao."
        except Exception as e:
            return False, str(e)

    return await loop.run_in_executor(None, run_cmd)

def is_voice_confirmation(text: str) -> bool:
    normalized = normalize_voice_command_text(text)
    return normalized in VOICE_CONFIRMATION_WORDS

def is_voice_cancel(text: str) -> bool:
    normalized = normalize_voice_command_text(text)
    return normalized in VOICE_CANCEL_WORDS

def init_voice_service():
    global voice_service
    
    voice_mode = os.getenv("VOICE_MODE", "none").lower()
    
    if voice_mode == "none":
        log_event(logger, "voice.disabled", mode=voice_mode)
        return
        
    if voice_mode == "gemini_live":
        from gemini_live import GeminiLiveService
        
        def on_state_change(state):
            # Map states to frontend voice_status
            run_in_main_loop(broadcast({"type": "voice_status", "status": state}))
            
        def on_message(text):
            # Broadcast text generated by Gemini Live to the UI chat log
            run_in_main_loop(broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": text
            }))
            # Append to conversation history
            conversation_history.append({"role": "assistant", "content": text})
            if len(conversation_history) > 100:
                conversation_history.pop(0)

        def on_voice_directive(prompt):
            normalized = normalize_voice_prompt(prompt)
            run_in_main_loop(handle_voice_directive_candidate(normalized, source="gemini_live"))

        def on_voice_confirm(spoken_confirmation):
            run_in_main_loop(confirm_pending_voice_directive(spoken_confirmation, source="gemini_live"))

        def on_voice_cancel(spoken_cancel):
            run_in_main_loop(cancel_pending_voice_directive(spoken_cancel, source="gemini_live"))
                
        api_key = os.getenv("GEMINI_API_KEY", "")
        voice_name = os.getenv("GEMINI_LIVE_VOICE", "Puck")
        voice_service = GeminiLiveService(
            api_key=api_key,
            voice_name=voice_name,
            on_state_change=on_state_change,
            on_message=on_message,
            on_voice_directive=on_voice_directive,
            on_voice_confirm=on_voice_confirm,
            on_voice_cancel=on_voice_cancel
        )
        log_event(logger, "voice.gemini_live.initialized", voice=voice_name)
    else:
        def on_speech_start():
            run_in_main_loop(broadcast({"type": "voice_status", "status": "listening"}))
            
        def on_speech_end():
            run_in_main_loop(broadcast({"type": "voice_status", "status": "idle"}))
            
        def on_transcribing():
            run_in_main_loop(broadcast({"type": "voice_status", "status": "transcribing"}))
            
        def on_transcription(text):
            normalized = normalize_voice_prompt(text)
            run_in_main_loop(broadcast({"type": "voice_status", "status": "transcribed", "text": normalized}))
            run_in_main_loop(handle_voice_directive_candidate(normalized, source="local"))
            
        model_name = os.getenv("VOICE_MODEL", "tiny")
        voice_service = VoiceService(
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
            on_transcribing=on_transcribing,
            on_transcription=on_transcription,
            model_name=model_name
        )
        log_event(logger, "voice.local.initialized", model=model_name)

async def start_directive_orchestration(prompt: str):
    prompt = prompt.strip()
    if not prompt:
        return
    conversation_history.append({"role": "user", "content": prompt})
    if len(conversation_history) > 100:
        conversation_history.pop(0)
    log_event(logger, "voice.directive.received", prompt_length=len(prompt))
    session = database.create_session(prompt)
    await broadcast_state("processing")
    await broadcast({"type": "system", "content": f"OrquestraÃ§Ã£o iniciada via Voz: {prompt}"})
    asyncio.create_task(run_orchestration_task(prompt, session.id))

def pending_voice_directive_expired() -> bool:
    if not pending_voice_directive:
        return False
    ttl_seconds = env_int("VOICE_CONFIRMATION_TTL_SECONDS", 600, 30, 3600)
    return (time.time() - pending_voice_directive.get("created_at", 0)) > ttl_seconds

async def clear_expired_voice_directive():
    global pending_voice_directive
    if pending_voice_directive_expired():
        expired_prompt = pending_voice_directive.get("prompt", "")
        pending_voice_directive = None
        await broadcast({"type": "voice_status", "status": "idle"})
        await broadcast({
            "type": "system",
            "content": f"Diretiva de voz expirada e descartada: {expired_prompt}"
        })

async def handle_voice_directive_candidate(prompt: str, source: str = "voice") -> str:
    global pending_voice_directive

    prompt = (prompt or "").strip()
    if not prompt:
        return "Sem texto de voz para processar."

    await clear_expired_voice_directive()

    if not voice_confirmation_enabled():
        await start_directive_orchestration(prompt)
        return "Orquestracao iniciada sem confirmacao."

    if is_voice_confirmation(prompt):
        return await confirm_pending_voice_directive(prompt, source=source)

    if is_voice_cancel(prompt):
        return await cancel_pending_voice_directive(prompt, source=source)

    pending_voice_directive = {
        "prompt": prompt,
        "source": source,
        "created_at": time.time(),
    }

    await broadcast({"type": "voice_status", "status": "pending_confirmation", "text": prompt})
    await broadcast({
        "type": "system",
        "content": (
            "Diretiva de voz preparada. Diz 'confirma' ou 'executa' para iniciar, "
            "ou 'cancela' para descartar."
        )
    })
    await broadcast({
        "type": "chat",
        "sender": "OPENCLAW",
        "role": "Voz",
        "content": f"Entendi esta tarefa: {prompt}"
    })
    log_event(logger, "voice.directive.pending", source=source, prompt_length=len(prompt))
    return "Diretiva preparada e a aguardar confirmacao."

async def confirm_pending_voice_directive(spoken_confirmation: str = "confirma", source: str = "voice") -> str:
    global pending_voice_directive

    await clear_expired_voice_directive()

    if not pending_voice_directive:
        await broadcast({"type": "system", "content": "Nao ha diretiva de voz pendente para confirmar."})
        return "Nao ha diretiva pendente."

    if voice_confirmation_enabled() and not is_voice_confirmation(spoken_confirmation):
        await broadcast({
            "type": "system",
            "content": "Confirmacao de voz ignorada porque nao foi uma frase explicita de confirmacao."
        })
        return "Confirmacao ignorada."

    prompt = pending_voice_directive["prompt"]
    pending_voice_directive = None
    await broadcast({"type": "voice_status", "status": "confirmed", "text": prompt})
    log_event(logger, "voice.directive.confirmed", source=source, prompt_length=len(prompt))
    await start_directive_orchestration(prompt)
    return "Diretiva confirmada e orquestracao iniciada."

async def cancel_pending_voice_directive(spoken_cancel: str = "cancela", source: str = "voice") -> str:
    global pending_voice_directive

    await clear_expired_voice_directive()

    if not pending_voice_directive:
        await broadcast({"type": "system", "content": "Nao ha diretiva de voz pendente para cancelar."})
        return "Nao ha diretiva pendente."

    if voice_confirmation_enabled() and not is_voice_cancel(spoken_cancel):
        await broadcast({
            "type": "system",
            "content": "Cancelamento de voz ignorado porque nao foi uma frase explicita de cancelamento."
        })
        return "Cancelamento ignorado."

    prompt = pending_voice_directive["prompt"]
    pending_voice_directive = None
    await broadcast({"type": "voice_status", "status": "cancelled", "text": prompt})
    await broadcast({"type": "system", "content": f"Diretiva de voz cancelada: {prompt}"})
    log_event(logger, "voice.directive.cancelled", source=source, prompt_length=len(prompt))
    return "Diretiva cancelada."

# Active WebSocket connections
active_connections = set()
PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
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

async def broadcast(message: dict):
    if not active_connections:
        return
        
    payload = json.dumps(normalize_ws_message(message))
    for conn in list(active_connections):
        try:
            await conn.send(payload)
        except Exception:
            try:
                active_connections.remove(conn)
            except KeyError:
                pass

async def send_ws(websocket, message: dict):
    await websocket.send(json.dumps(normalize_ws_message(message)))


async def send_project_context(websocket, project_id: str, reindex: bool = False):
    payload = await asyncio.to_thread(project_context_service.project_payload, project_id, reindex)
    await send_ws(websocket, {"type": "project_context", **payload})
    await send_ws(websocket, {"type": "ast_state", "data": payload.get("symbols") or None})


async def send_latest_coding_session(websocket, project_id: str):
    session = await asyncio.to_thread(coding_session_service.latest, project_id)
    await send_ws(websocket, {"type": "coding_session", "data": session.to_dict() if session else None})


async def send_mission_list(websocket, project_id: str):
    missions = await asyncio.to_thread(mission_planner.list_missions, project_id)
    await send_ws(websocket, {"type": "mission_list", "project_id": project_id, "missions": missions})


async def dispatch_mission_operation(websocket, msg: dict, selected_project_id: str | None) -> bool:
    operation = str(msg.get("type") or "")
    mission_operations = {
        "mission_list", "mission_create", "mission_get", "mission_update", "mission_set_status",
        "work_package_create", "work_package_update", "work_package_set_status", "work_package_add_dependency",
        "deliverable_create", "deliverable_update", "deliverable_set_status", "evidence_attach",
        "criterion_create", "criterion_set_status", "mission_resume_snapshot",
        "mission_execute_work_package", "mission_apply_execution", "mission_review_execution",
        "mission_retry_execution", "mission_cancel_execution", "mission_release_stale_lock",
    }
    if operation not in mission_operations:
        return False
    project_id = str(msg.get("project_id") or selected_project_id or "").strip()
    try:
        snapshot = None
        if operation == "mission_list":
            await send_mission_list(websocket, project_id)
            return True
        if operation == "mission_create":
            snapshot = await asyncio.to_thread(
                mission_planner.create_mission,
                project_id,
                msg.get("title"),
                msg.get("objective"),
                msg.get("description", ""),
                msg.get("current_phase", ""),
                msg.get("metadata"),
                msg.get("mission_id"),
            )
        elif operation in {"mission_get", "mission_resume_snapshot"}:
            snapshot = await asyncio.to_thread(mission_planner.load_mission, project_id, msg.get("mission_id"))
        elif operation == "mission_update":
            snapshot = await asyncio.to_thread(
                mission_planner.update_mission, project_id, msg.get("mission_id"), msg.get("expected_version"), msg.get("changes")
            )
        elif operation == "mission_set_status":
            snapshot = await asyncio.to_thread(
                mission_planner.set_mission_status,
                project_id,
                msg.get("mission_id"),
                msg.get("status"),
                msg.get("expected_version"),
            )
        elif operation == "work_package_create":
            snapshot = await asyncio.to_thread(
                mission_planner.create_work_package,
                project_id,
                msg.get("mission_id"),
                msg.get("title"),
                msg.get("description", ""),
                msg.get("work_package_type", "GENERIC"),
                msg.get("priority", 0),
                msg.get("dependencies"),
                msg.get("executor_kind", "MANUAL"),
                msg.get("executor_ref", ""),
                msg.get("metadata"),
                msg.get("required", True),
                msg.get("work_package_id"),
            )
        elif operation == "work_package_update":
            snapshot = await asyncio.to_thread(
                mission_planner.update_work_package,
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("expected_version"),
                msg.get("changes"),
            )
        elif operation == "work_package_set_status":
            snapshot = await asyncio.to_thread(
                mission_planner.set_work_package_status,
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("status"),
                msg.get("expected_version"),
                msg.get("blocked_reason", ""),
            )
        elif operation == "work_package_add_dependency":
            snapshot = await asyncio.to_thread(
                mission_planner.add_dependency,
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("dependency_id"),
                msg.get("expected_version"),
            )
        elif operation == "deliverable_create":
            snapshot = await asyncio.to_thread(
                mission_planner.create_deliverable,
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("name"),
                msg.get("kind", "GENERIC"),
                msg.get("description", ""),
                msg.get("artifact_refs"),
                msg.get("required", False),
                msg.get("expected_work_package_version"),
                msg.get("deliverable_id"),
            )
        elif operation == "deliverable_update":
            snapshot = await asyncio.to_thread(
                mission_planner.update_deliverable,
                project_id,
                msg.get("mission_id"),
                msg.get("deliverable_id"),
                msg.get("expected_version"),
                msg.get("changes"),
            )
        elif operation == "deliverable_set_status":
            snapshot = await asyncio.to_thread(
                mission_planner.set_deliverable_status,
                project_id,
                msg.get("mission_id"),
                msg.get("deliverable_id"),
                msg.get("status"),
                msg.get("expected_version"),
            )
        elif operation == "evidence_attach":
            snapshot = await asyncio.to_thread(
                mission_planner.attach_evidence,
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("kind"),
                msg.get("source_ref"),
                msg.get("description", ""),
                msg.get("deliverable_id"),
                msg.get("metadata"),
                msg.get("content_hash"),
                msg.get("evidence_id"),
            )
        elif operation == "criterion_create":
            snapshot = await asyncio.to_thread(
                mission_planner.create_criterion,
                project_id,
                msg.get("mission_id"),
                msg.get("owner_type"),
                msg.get("owner_id"),
                msg.get("description"),
                msg.get("required_evidence_kinds"),
                msg.get("required", True),
                msg.get("criterion_id"),
            )
        elif operation == "criterion_set_status":
            snapshot = await asyncio.to_thread(
                mission_planner.set_criterion_status,
                project_id,
                msg.get("mission_id"),
                msg.get("criterion_id"),
                msg.get("status"),
                msg.get("expected_version"),
                msg.get("evidence_refs"),
                msg.get("validation_note", ""),
            )
        elif operation == "mission_execute_work_package":
            snapshot = await mission_executor_service.execute_work_package(
                project_id,
                msg.get("mission_id"),
                msg.get("work_package_id"),
                msg.get("expected_mission_version"),
                msg.get("expected_work_package_version"),
            )
        elif operation == "mission_apply_execution":
            snapshot = await asyncio.to_thread(
                mission_executor_service.apply_execution,
                project_id,
                msg.get("mission_id"),
                msg.get("execution_id"),
                msg.get("expected_execution_version"),
                bool(msg.get("confirmed")),
            )
        elif operation == "mission_review_execution":
            snapshot = await asyncio.to_thread(
                mission_executor_service.review_execution,
                project_id,
                msg.get("mission_id"),
                msg.get("execution_id"),
                msg.get("decision"),
                msg.get("review_note", ""),
                msg.get("accepted_evidence_refs") or [],
                msg.get("expected_execution_version"),
                bool(msg.get("validation_failed", False)),
            )
        elif operation == "mission_retry_execution":
            snapshot = await mission_executor_service.retry_execution(
                project_id,
                msg.get("mission_id"),
                msg.get("execution_id"),
                msg.get("expected_execution_version"),
            )
        elif operation == "mission_cancel_execution":
            snapshot = await asyncio.to_thread(
                mission_executor_service.cancel_execution,
                project_id,
                msg.get("mission_id"),
                msg.get("execution_id"),
                msg.get("expected_execution_version"),
                bool(msg.get("confirmed")),
            )
        elif operation == "mission_release_stale_lock":
            snapshot = await asyncio.to_thread(
                mission_executor_service.release_stale_lock,
                project_id,
                msg.get("mission_id"),
                msg.get("execution_id"),
                msg.get("expected_execution_version"),
                bool(msg.get("confirmed")),
                msg.get("minimum_age_seconds"),
            )
        if snapshot is not None:
            active_mission_store = getattr(mission_planner, "mission_state", mission_planner)
            if mission_executor_service.mission_state is active_mission_store:
                snapshot = await asyncio.to_thread(
                    mission_executor_service.load_snapshot,
                    project_id,
                    snapshot["mission"]["mission_id"],
                )
            await send_ws(websocket, {"type": "mission_snapshot", "data": snapshot})
            await send_mission_list(websocket, project_id)
        return True
    except MissionStateError as mission_error:
        await send_ws(websocket, system_message(str(mission_error)))
        return True

async def broadcast_state(value: str):
    global voice_service
    if voice_service:
        voice_service.is_processing = (value == "processing")
    await broadcast(state_message(value))

# Callbacks
main_loop = None

def run_in_main_loop(coro):
    if main_loop and main_loop.is_running():
        main_loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
    else:
        try:
            coro.close()
        except RuntimeError:
            pass

def on_agent_message(sender: str, role: str, content: str):
    message = chat_message(sender.upper(), role, content)
    # Track agent message in casual chat history to keep Jarvis in the loop about agent debates
    conversation_history.append({"role": "assistant", "content": f"[{sender} - {role}]: {content}"})
    if len(conversation_history) > 30:
        conversation_history.pop(0)
        
    run_in_main_loop(broadcast(message))

def on_file_update(filename: str, content: str):
    message = file_message(filename, content)
    run_in_main_loop(broadcast(message))

def on_kanban_update(card_id: str, status: str):
    message = kanban_message(card_id, status)
    run_in_main_loop(broadcast(message))

def parse_file_context(prompt: str) -> str:
    """Scan the prompt for @filename mentions, read matching files from the
    sandbox or workspace root, and append their contents as context blocks."""
    import re
    mentions = re.findall(r'@([\w.\-/]+)', prompt)
    if not mentions:
        return prompt

    extra_context = []
    # Directories to search for mentioned files
    search_dirs = [
        PROJECT_ROOT,                        # project root
        sandbox.SANDBOX_DIR if hasattr(sandbox, 'SANDBOX_DIR') else ''
    ]

    for fname in dict.fromkeys(mentions):  # deduplicate preserving order
        found = False
        for directory in search_dirs:
            if not directory:
                continue
            candidate = _resolve_under_base(directory, fname)
            if not candidate:
                log_event(logger, "file_context.path_blocked", level="warning", filename=fname)
                continue
            if os.path.isfile(candidate):
                try:
                    with open(candidate, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    # Truncate very large files so as not to blow the context window
                    if len(content) > 8000:
                        content = content[:8000] + '\n... [truncado para 8000 caracteres] ...'
                    extra_context.append(
                        f'\n\n--- ConteÃºdo do ficheiro @{fname} ---\n```\n{content}\n```'
                    )
                    log_event(logger, "file_context.injected", filename=fname, content_length=len(content))
                    found = True
                    break
                except Exception as e:
                    log_event(logger, "file_context.read_error", level="error", filename=fname, error=str(e))
        if not found:
            log_event(logger, "file_context.not_found", level="warning", filename=fname)

    if extra_context:
        return prompt + ''.join(extra_context)
    return prompt

def get_template_suggestions(template_name: str) -> list:
    suggestions = {
        "builder_swarm": [
            {"prompt": "Criar Landing Page de PortefÃ³lio Moderno", "label": "Landing Page PortefÃ³lio", "icon": "layout"},
            {"prompt": "Desenvolver API FastAPI para Tarefas com SQLite", "label": "API FastAPI SQLite", "icon": "database"},
            {"prompt": "Escrever Script Python para Renomear Ficheiros em Massa", "label": "Script Renomear", "icon": "file-code"}
        ],
        "operator_swarm": [
            {"prompt": "Configurar CÃ³pia de SeguranÃ§a do Obsidian Vault", "label": "Backup Obsidian", "icon": "archive"},
            {"prompt": "Verificar Estado dos Contentores Docker no Windows", "label": "Estado Docker", "icon": "server"},
            {"prompt": "Organizar Ficheiros da Sandbox por ExtensÃ£o", "label": "Organizar Sandbox", "icon": "folder-plus"}
        ],
        "creator_swarm": [
            {"prompt": "Escrever Ebook de IntroduÃ§Ã£o a Agentes de IA em PDF", "label": "Ebook Agentes IA", "icon": "book-open"},
            {"prompt": "Criar GuiÃ£o e Copy para LanÃ§amento de Curso Online", "label": "Copy LanÃ§amento", "icon": "video"},
            {"prompt": "Projetar Mockup de Interface de Utilizador para App", "label": "Mockup App", "icon": "palette"}
        ],
        "growth_swarm": [
            {"prompt": "Pesquisa de Nichos de MonetizaÃ§Ã£o com IA para 500â‚¬/mÃªs", "label": "Nicho 500â‚¬/mÃªs", "icon": "dollar-sign"},
            {"prompt": "Delinear EstratÃ©gia de SEO para Blog de Tecnologia", "label": "EstratÃ©gia SEO", "icon": "trending-up"},
            {"prompt": "Criar Plano de LanÃ§amento de Produto Digital", "label": "Plano LanÃ§amento", "icon": "shopping-cart"}
        ],
        "research_swarm": [
            {"prompt": "Investigar TendÃªncias de Agentes Inteligentes em 2026", "label": "TendÃªncias IA 2026", "icon": "search"},
            {"prompt": "Organizar Notas do Obsidian e Atualizar SOPs", "label": "Organizar Vault", "icon": "book"},
            {"prompt": "Fazer SumÃ¡rio de DocumentaÃ§Ã£o sobre FastAPI", "label": "SumÃ¡rio FastAPI", "icon": "align-left"}
        ]
    }
    return suggestions.get(template_name, suggestions["builder_swarm"])


AVAILABLE_TEMPLATE_NAMES = {
    "builder_swarm",
    "operator_swarm",
    "creator_swarm",
    "growth_swarm",
    "research_swarm",
}

AGENT_ICON_MAP = {
    "dev_lead": "briefcase",
    "sys_admin": "briefcase",
    "market_analyst": "briefcase",
    "designer": "palette",
    "ops_specialist": "palette",
    "coder": "code",
    "copywriter": "code",
    "growth_lead": "code",
    "researcher": "code",
    "knowledge_manager": "code",
}

def normalize_template_name(template_name: str) -> str:
    if template_name in AVAILABLE_TEMPLATE_NAMES:
        return template_name
    return "builder_swarm"

def build_template_payload(template_name: str) -> dict:
    normalized_name = normalize_template_name(template_name)
    template_info = agents.get_active_template(normalized_name)
    agents_cfg = template_info.get("agents", {})
    tasks_cfg = template_info.get("tasks", {})

    return {
        "type": "template_changed",
        "template_name": normalized_name,
        "name": template_info.get("name", "Builder Swarm"),
        "description": template_info.get("description", ""),
        "agents": [
            {
                "id": name,
                "name": name.replace("_", " ").title(),
                "role": cfg.get("role", "Agente"),
                "icon": AGENT_ICON_MAP.get(name, "shield-check"),
            }
            for name, cfg in agents_cfg.items()
            if name != "jarvis"
        ],
        "tasks": [
            {
                "id": tid,
                "title": tcfg.get("title", tid.replace("task_", "").replace("_", " ").capitalize()),
                "agent": tcfg.get("agent"),
            }
            for tid, tcfg in tasks_cfg.items()
        ],
        "suggestions": get_template_suggestions(normalized_name),
    }

def markdown_to_html(text: str) -> str:
    import re
    lines = text.split("\n")
    html_lines = []
    in_list = False
    in_table = False
    in_code = False
    
    for line in lines:
        line_strip = line.strip()
        
        # Code block
        if line_strip.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue
            
        if in_code:
            html_lines.append(line)
            continue
            
        if not line_strip:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            continue
            
        # Headers
        if line_strip.startswith("# "):
            html_lines.append(f"<h1>{line_strip[2:]}</h1>")
        elif line_strip.startswith("## "):
            html_lines.append(f"<h2>{line_strip[3:]}</h2>")
        elif line_strip.startswith("### "):
            html_lines.append(f"<h3>{line_strip[4:]}</h3>")
        # List items
        elif line_strip.startswith("- ") or line_strip.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = line_strip[2:]
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            html_lines.append(f"<li>{content}</li>")
        # Table rows
        elif line_strip.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            parts = [p.strip() for p in line_strip.split("|")[1:-1]]
            if parts and all(re.match(r'^:?-+:?$', p) for p in parts):
                continue
            row_type = "th" if html_lines[-1] == "<table>" else "td"
            row_html = "<tr>" + "".join(f"<{row_type}>{p}</{row_type}>" for p in parts) + "</tr>"
            html_lines.append(row_html)
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            # Paragraph
            content = line_strip
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            html_lines.append(f"<p>{content}</p>")
            
    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</table>")
    if in_code:
        html_lines.append("</code></pre>")
        
    return "\n".join(html_lines)

async def query_model_for_arena(model_id: str, model_name: str, prompt: str):
    import time
    start_time = time.time()
    result_text = ""
    token_count = 0
    
    # Send initial status
    await broadcast({
        "type": "arena_update",
        "model_id": model_id,
        "status": "generating",
        "content": "",
        "time": 0,
        "tokens": 0
    })
    
    try:
        if model_id == "gemini":
            gemini_key = os.getenv("GEMINI_API_KEY")
            if gemini_key:
                url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                headers = {"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "gemini-2.5-flash",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 800
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    result_text = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    result_text = f"Erro Gemini (Status {res.status_code}): {res.text}"
            else:
                result_text = "SimulaÃ§Ã£o Gemini: " + prompt
                
        elif model_id == "qwen":
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 400}
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
            if res.status_code == 200:
                result_text = res.json().get("response", "")
            else:
                result_text = "SimulaÃ§Ã£o Qwen Local: " + prompt
        elif model_id == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "claude-3-5-haiku-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    result_text = res.json().get("content", [{}])[0].get("text", "")
            else:
                url = "http://localhost:11434/api/generate"
                payload = {
                        "model": os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 400}
                }
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        result_text = res.json().get("response", "")
                    else:
                        result_text = "Simulacao Claude (Sem chave Anthropic configurada): " + prompt
                except Exception:
                    result_text = "Simulacao Claude (Sem chave Anthropic configurada): " + prompt                    
    except Exception as e:
        result_text = safe_user_error(f"Erro ao chamar {model_name}", e)
        
    duration = time.time() - start_time
    token_count = len(result_text.split()) * 4 // 3
    
    await broadcast({
        "type": "arena_update",
        "model_id": model_id,
        "status": "complete",
        "content": result_text,
        "time": round(duration, 2),
        "tokens": token_count
    })

async def run_arena_comparison(prompt: str):
    await broadcast({"type": "system", "content": f"Arena Swarm iniciada para o prompt: '{prompt}'"})
    
    # Send disabled update for Groq
    await broadcast({
        "type": "arena_update",
        "model_id": "groq",
        "status": "disabled",
        "content": "Desativado (Groq API Key removida)",
        "time": "-",
        "tokens": "-"
    })
    
    await asyncio.gather(
        query_model_for_arena("gemini", "Gemini 3.5 Flash", prompt),
        query_model_for_arena("qwen", "Qwen 2.5 (Local)", prompt),
        query_model_for_arena("claude", "Claude 3.5 (Sonnet)", prompt)
    )
    
    await broadcast({"type": "system", "content": "Arena Swarm finalizada. Todos os modelos responderam!"})

async def handle_slash_command(command_str: str, websocket, session_id: int):
    parts = command_str.split(" ", 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    
    await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"ðŸ› ï¸ **Comando Executado:** `{command_str}`"})
    
    if cmd == "/review":
        await broadcast_state("processing")
        await broadcast({"type": "system", "content": "A iniciar auditoria QA automÃ¡tica nos ficheiros da sandbox..."})
        
        from sandbox import SANDBOX_DIR
        current_html = ""
        current_css = ""
        current_js = ""
        try:
            p_html = os.path.join(SANDBOX_DIR, "index.html")
            p_css = os.path.join(SANDBOX_DIR, "styles.css")
            p_js = os.path.join(SANDBOX_DIR, "app.js")
            if os.path.exists(p_html):
                with open(p_html, "r", encoding="utf-8") as f_obj:
                    current_html = f_obj.read()
            if os.path.exists(p_css):
                with open(p_css, "r", encoding="utf-8") as f_obj:
                    current_css = f_obj.read()
            if os.path.exists(p_js):
                with open(p_js, "r", encoding="utf-8") as f_obj:
                    current_js = f_obj.read()
        except Exception as e:
            log_event(logger, "sandbox_files.read_error", level="error", error=str(e))
            
        review_task = (
            "Analisa os ficheiros da sandbox:\n"
            f"HTML:\n{current_html}\n\nCSS:\n{current_css}\n\nJS:\n{current_js}\n\n"
            "Faz um relatÃ³rio detalhado de testes, indicando se existem erros de visualizaÃ§Ã£o, sintaxe ou de caminho de imagens. Termina com 'APROVAÃ‡ÃƒO: SIM' ou 'APROVAÃ‡ÃƒO: NÃƒO'."
        )
        
        qa_report = await agents.spawn_specialist_agent(
            nome="Quinn",
            especialidade="Auditor QA",
            backstory="Ã‰s o Quinn, o auditor de qualidade experiente da agÃªncia. Analisas cÃ³digo para garantir que tudo funciona.",
            tarefa=review_task,
            contexto_projeto="Auditoria de qualidade manual via slash command.",
            on_msg=on_agent_message
        )
        await broadcast({"type": "chat", "sender": "QUINN", "role": "QA Engineer (Slash Command)", "content": qa_report})
        await broadcast_state("idle")
        
    elif cmd == "/refactor":
        await broadcast_state("processing")
        await broadcast({"type": "system", "content": "ðŸ”„ A iniciar ciclo Self-Healing (Devon â†’ Quinn, atÃ© 3 tentativas)..."})

        import re
        from sandbox import SANDBOX_DIR

        def read_sandbox_files():
            html, css, js = "", "", ""
            try:
                p_html = os.path.join(SANDBOX_DIR, "index.html")
                p_css  = os.path.join(SANDBOX_DIR, "styles.css")
                p_js   = os.path.join(SANDBOX_DIR, "app.js")
                if os.path.exists(p_html):
                    with open(p_html, "r", encoding="utf-8") as f_obj: html = f_obj.read()
                if os.path.exists(p_css):
                    with open(p_css,  "r", encoding="utf-8") as f_obj: css  = f_obj.read()
                if os.path.exists(p_js):
                    with open(p_js,   "r", encoding="utf-8") as f_obj: js   = f_obj.read()
            except Exception as re_err:
                log_event(logger, "sandbox_files.read_error", level="error", error=str(re_err))
            return html, css, js

        def write_sandbox_files(html_match, css_match, js_match):
            refined = []
            if html_match:
                with open(os.path.join(SANDBOX_DIR, "index.html"), "w", encoding="utf-8") as f:
                    f.write(html_match.group(1).strip())
                on_file_update("index.html", html_match.group(1).strip())
                refined.append("index.html")
            if css_match:
                with open(os.path.join(SANDBOX_DIR, "styles.css"), "w", encoding="utf-8") as f:
                    f.write(css_match.group(1).strip())
                on_file_update("styles.css", css_match.group(1).strip())
                refined.append("styles.css")
            if js_match:
                with open(os.path.join(SANDBOX_DIR, "app.js"), "w", encoding="utf-8") as f:
                    f.write(js_match.group(1).strip())
                on_file_update("app.js", js_match.group(1).strip())
                refined.append("app.js")
            return refined

        MAX_HEALING_CYCLES = 3
        qa_feedback = ""  # feedback from Quinn to feed into Devon
        approved = False

        for cycle in range(1, MAX_HEALING_CYCLES + 1):
            await broadcast({"type": "system", "content": f"ðŸ”§ Ciclo {cycle}/{MAX_HEALING_CYCLES} â€” Devon a refatorar..."})

            current_html, current_css, current_js = read_sandbox_files()

            feedback_section = f"\n\nâš ï¸ Feedback do QA (ciclo anterior):\n{qa_feedback}" if qa_feedback else ""
            refactor_task = (
                f"Otimiza o cÃ³digo da sandbox para garantir mÃ¡xima performance e conformidade com as regras de visualizaÃ§Ã£o:{feedback_section}\n"
                f"HTML:\n{current_html}\n\nCSS:\n{current_css}\n\nJS:\n{current_js}\n\n"
                "Retorna as versÃµes completas otimizadas e limpas em blocos de cÃ³digo markdown: ```html ... ```, ```css ... ``` e ```javascript ... ```."
            )

            refactor_report = await agents.spawn_specialist_agent(
                nome="Devon",
                especialidade="Programador OtimizaÃ§Ã£o",
                backstory="Ã‰s o Devon, o programador core da agÃªncia. Refatoras cÃ³digo para garantir clareza, performance e beleza.",
                tarefa=refactor_task,
                contexto_projeto=f"Ciclo Self-Healing {cycle}/{MAX_HEALING_CYCLES}.",
                on_msg=on_agent_message
            )

            html_match = re.search(r"```html\n(.*?)\n```", refactor_report, re.DOTALL)
            css_match  = re.search(r"```css\n(.*?)\n```", refactor_report, re.DOTALL)
            js_match   = re.search(r"```(?:javascript|js)\n(.*?)\n```", refactor_report, re.DOTALL)

            refined_files = write_sandbox_files(html_match, css_match, js_match)

            if refined_files:
                await broadcast({"type": "chat", "sender": "DEVON", "role": f"Programador (Ciclo {cycle})",
                                 "content": f"âœ… CÃ³digo atualizado na sandbox: {', '.join(refined_files)}"})
            else:
                await broadcast({"type": "chat", "sender": "DEVON", "role": f"Programador (Ciclo {cycle})",
                                 "content": refactor_report})
                # No code blocks found â€” nothing to audit, break early
                break

            # â”€â”€ Quinn QA audit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            await broadcast({"type": "system", "content": f"ðŸ” Quinn a auditar cÃ³digo (ciclo {cycle})..."})
            new_html, new_css, new_js = read_sandbox_files()
            review_task = (
                f"Analisa os ficheiros da sandbox (ciclo Self-Healing {cycle}):\n"
                f"HTML:\n{new_html}\n\nCSS:\n{new_css}\n\nJS:\n{new_js}\n\n"
                "Faz um relatÃ³rio detalhado de testes, indicando se existem erros de visualizaÃ§Ã£o, sintaxe ou de caminho de imagens. Termina com 'APROVAÃ‡ÃƒO: SIM' ou 'APROVAÃ‡ÃƒO: NÃƒO'."
            )
            qa_report = await agents.spawn_specialist_agent(
                nome="Quinn",
                especialidade="Auditor QA",
                backstory="Ã‰s o Quinn, o auditor de qualidade experiente da agÃªncia. Analisas cÃ³digo para garantir que tudo funciona.",
                tarefa=review_task,
                contexto_projeto=f"Auto-auditoria Self-Healing ciclo {cycle}.",
                on_msg=on_agent_message
            )
            await broadcast({"type": "chat", "sender": "QUINN", "role": f"QA (Ciclo {cycle})", "content": qa_report})

            if "APROVAÃ‡ÃƒO: SIM" in qa_report.upper():
                await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador",
                                 "content": f"âœ… **Self-Healing concluÃ­do** em {cycle} ciclo(s). QA aprovou o cÃ³digo!"})
                approved = True
                break
            else:
                # Extract Quinn's feedback to pass to Devon on the next iteration
                qa_feedback = qa_report
                await broadcast({"type": "system",
                                 "content": f"âš ï¸ QA rejeitou (ciclo {cycle}). Devon irÃ¡ corrigir automaticamente..."})

        if not approved:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador",
                             "content": f"âš ï¸ **Self-Healing atingiu o limite de {MAX_HEALING_CYCLES} ciclos.** RevÃª o cÃ³digo manualmente."})

        await broadcast_state("idle")
        
    elif cmd == "/theme":
        theme = args.strip().lower()
        if theme in ["neon", "cyberpunk", "clean"]:
            await broadcast({"type": "ui_theme", "theme": theme})
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"ðŸŽ¨ Tema visual alterado para: **{theme.upper()}**"})
        else:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": "âš ï¸ Tema desconhecido. Temas vÃ¡lidos: `/theme neon`, `/theme cyberpunk`, `/theme clean`"})
            
    elif cmd == "/spawn":
        try:
            subparts = args.split("|")
            name = subparts[0].strip()
            specialty = subparts[1].strip()
            task = subparts[2].strip()
            
            await broadcast_state("processing")
            await broadcast({"type": "system", "content": f"A criar e executar subagente especialista {name}..."})
            
            res = await agents.spawn_specialist_agent(
                nome=name,
                especialidade=specialty,
                backstory=f"Ã‰s o subagente especialista {name}, focado em {specialty}.",
                tarefa=task,
                contexto_projeto="CriaÃ§Ã£o ad-hoc via comando de barra.",
                on_msg=on_agent_message
            )
            await broadcast({"type": "chat", "sender": name.upper(), "role": specialty, "content": res})
            await broadcast_state("idle")
        except Exception as e:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"âš ï¸ Formato invÃ¡lido. Uso: `/spawn Nome | Especialidade | Tarefa` (ex: `/spawn Marta | Dev SQL | Cria uma query para clientes`)"})
            
    elif cmd == "/arena":
        prompt_p = args.strip()
        if not prompt_p:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": "âš ï¸ Introduza um prompt para a Arena (ex: `/arena Criar um botÃ£o pulsante neon`)"})
            return
        
        await broadcast_state("processing")
        await broadcast({"type": "ui", "action": "show_arena_tab"})
        asyncio.create_task(run_arena_comparison(prompt_p))

    elif cmd == "/rules":
        rules = database.get_compounding_rules()
        if not rules:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": "ðŸ§  **Compounding Memory:** Nenhuma regra ou liÃ§Ã£o aprendida guardada no SQLite."})
        else:
            text = "ðŸ§  **Compounding Memory (Regras Ativas):**\n"
            for r in rules:
                text += f"- `{r['rule_key']}`: {r['description']} -> *{r['correction']}*\n"
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": text})

    elif cmd == "/learn":
        try:
            parts = args.split("|")
            key = parts[0].strip().replace(" ", "_").lower()
            desc = parts[1].strip()
            corr = parts[2].strip()
            database.add_compounding_rule(key, desc, corr)
            # Send updated rules list to client
            await broadcast({"type": "rules_list", "rules": database.get_compounding_rules()})
            await broadcast({"type": "rules_updated", "rules": database.get_compounding_rules()})
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"âœ… Nova regra de memÃ³ria `{key}` gravada com sucesso!"})
        except Exception:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": "âš ï¸ Formato invÃ¡lido. Uso: `/learn chave | descriÃ§Ã£o | correÃ§Ã£o` (ex: `/learn python_venv | O utilizador usa venv/Scripts/python | Sempre usar o caminho completo da venv`)"})

    elif cmd == "/forget":
        key = args.strip().lower()
        if not key:
            await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": "âš ï¸ Introduza a chave da regra a apagar (ex: `/forget python_venv`)"})
        else:
            deleted = database.delete_compounding_rule(key)
            if deleted:
                await broadcast({"type": "rules_list", "rules": database.get_compounding_rules()})
                await broadcast({"type": "rules_updated", "rules": database.get_compounding_rules()})
                await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"âœ… Regra `{key}` esquecida/apagada com sucesso!"})
            else:
                await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"âš ï¸ Regra `{key}` nÃ£o encontrada no SQLite."})
        
    elif cmd == "/help":
        help_text = (
            "ðŸ“– **Comandos de Barra DisponÃ­veis:**\n"
            "- `/review` : Audita o cÃ³digo na sandbox (QA Quinn)\n"
            "- `/refactor` : Otimiza e limpa o cÃ³digo sandbox (Devon)\n"
            "- `/theme [neon|cyberpunk|clean]` : Muda o tema visual da app\n"
            "- `/spawn Nome | Especialidade | Tarefa` : Cria e executa um subagente especialista ad-hoc\n"
            "- `/arena [prompt]` : Compara a velocidade e o cÃ³digo gerado por mÃºltiplos modelos na Swarm Arena\n"
            "- `/rules` : Lista as regras de compounding memory ativas no SQLite\n"
            "- `/learn chave | desc | corr` : Cria ou atualiza manualmente uma regra de memÃ³ria\n"
            "- `/forget chave` : Remove uma regra de memÃ³ria da base de dados\n"
            "- `/help` : Mostra esta ajuda"
        )
        await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": help_text})
    else:
        await broadcast({"type": "chat", "sender": "OPENCLAW", "role": "Orquestrador", "content": f"âš ï¸ Comando desconhecido: `{cmd}`. Digite `/help` para ajuda."})

async def handle_client(websocket, *args):
    if not _is_ws_authorized(websocket, args):
        log_event(logger, "websocket.auth.rejected", level="warning")
        await _reject_unauthorized_ws(websocket)
        return

    active_connections.add(websocket)
    selected_project_id = None
    log_event(logger, "websocket.client.connected", active_connections=len(active_connections))
    
    try:
        await send_ws(websocket, system_message("Conectado ao servidor Jarvis WebSocket na porta 8001!"))
        
        # Send current template state immediately to sync frontend
        template_name = normalize_template_name(getattr(agents, "active_template_name", "builder_swarm"))
        agents.active_template_name = template_name
        await send_ws(websocket, build_template_payload(template_name))

        # Send initial compounding rules, architecture memory, engineering decisions and obsidian notes list to sync frontend tabs
        rules = database.get_compounding_rules()
        await send_ws(websocket, {
            "type": "rules_list",
            "rules": rules
        })
        
        architecture = database.get_architecture_memory()
        await send_ws(websocket, {
            "type": "architecture_list",
            "architecture": architecture
        })
        
        decisions = database.get_engineering_decisions()
        await send_ws(websocket, {
            "type": "decisions_list",
            "decisions": decisions
        })
        
        notes_str = await agents.run_obsidian_list_notes()
        notes_list = [n.strip() for n in notes_str.split("\n") if n.strip() and not n.startswith("(Nenhuma")]
        await send_ws(websocket, {
            "type": "notes_list",
            "notes": notes_list
        })

        projects = project_context_service.list_projects()
        await send_ws(websocket, {"type": "projects_list", "projects": projects})
        if projects:
            project_ids = [project["project_id"] for project in projects]
            selected_project_id = "task-app" if "task-app" in project_ids else project_ids[0]
            try:
                await send_project_context(websocket, selected_project_id)
                await send_latest_coding_session(websocket, selected_project_id)
                await send_mission_list(websocket, selected_project_id)
            except ProjectContextError as project_error:
                log_event(logger, "project_context.initial_error", level="warning", error=str(project_error))
        
        async for message_str in websocket:
            try:
                msg = validate_client_message(json.loads(message_str))
                if msg.get("type") == "directive":
                    prompt = msg.get("text", "").strip()
                    if not prompt:
                        continue
                    prompt = normalize_voice_prompt(prompt)
                    
                    if prompt.startswith("/"):
                        await handle_slash_command(prompt, websocket, 1) # Fallback to session 1 or fetch active session
                        continue

                    # Inject @file context before handing off to agents
                    prompt_with_context = parse_file_context(prompt)
                    if prompt_with_context != prompt:
                        mentions_count = prompt_with_context.count('--- ConteÃºdo do ficheiro @')
                        await websocket.send(json.dumps({
                            "type": "system",
                            "content": f"ðŸ“Ž {mentions_count} ficheiro(s) injetados como contexto via @mention."
                        }))

                    conversation_history.append({"role": "user", "content": prompt_with_context})
                    if len(conversation_history) > 100:
                        conversation_history.pop(0)
                    log_event(logger, "websocket.directive.received", prompt_length=len(prompt))
                    session = database.create_session(prompt)
                    
                    await broadcast_state("processing")
                    await broadcast({"type": "system", "content": f"OrquestraÃ§Ã£o iniciada: {prompt}"})
                    
                    asyncio.create_task(run_orchestration_task(prompt_with_context, session.id))

                elif msg.get("type") == "select_template":
                    requested_template = msg.get("template", "builder_swarm")
                    template_name = normalize_template_name(requested_template)
                    agents.active_template_name = template_name
                    if requested_template != template_name:
                        await websocket.send(json.dumps({
                            "type": "system",
                            "content": f"Template desconhecido '{requested_template}'. A usar Builder Swarm."
                        }))
                    await broadcast(build_template_payload(template_name))
                elif msg.get("type") == "toggle_voice":
                    active = msg.get("active", False)
                    if active:
                        try:
                            if voice_service:
                                voice_service.start()
                                await websocket.send(json.dumps({
                                    "type": "system",
                                    "content": "Reconhecimento de Voz Jarvis OS (VAD Python) ativado no Servidor."
                                }))
                                await broadcast({"type": "voice_status", "status": "idle"})
                            else:
                                await websocket.send(json.dumps({
                                    "type": "system",
                                    "content": "Reconhecimento de Voz estÃ¡ desativado no .env (VOICE_MODE=none)."
                                }))
                        except Exception as e:
                            await websocket.send(json.dumps({
                                "type": "system",
                                "content": safe_user_error("Erro ao ativar voz", e)
                             }))
                    else:
                        if voice_service:
                            voice_service.stop()
                        await websocket.send(json.dumps({
                            "type": "system",
                            "content": "Reconhecimento de Voz Jarvis OS (VAD Python) desativado."
                        }))
                        await broadcast({"type": "voice_status", "status": "offline"})
                elif msg.get("type") == "run_project":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    if not requested_project_id:
                        await send_ws(websocket, system_message("Selecione um projeto antes de iniciar o preview."))
                        continue
                    await send_ws(websocket, {
                        "type": "project_output",
                        "content": f"[Project] A preparar preview de {requested_project_id}...\n"
                    })

                    def on_sandbox_output(content: str):
                        run_in_main_loop(broadcast({
                            "type": "project_output",
                            "content": content
                        }))

                    try:
                        project_run = project_context_service.preview_project(requested_project_id, on_sandbox_output)
                        selected_project_id = requested_project_id
                    except ProjectContextError as project_error:
                        await send_ws(websocket, system_message(str(project_error)))
                        await send_ws(websocket, {"type": "project_status", "running": False, "preview_url": ""})
                        continue
                    if isinstance(project_run, dict):
                        project_running = bool(project_run.get("running"))
                        preview_url = project_run.get("preview_url")
                    else:
                        project_running = bool(project_run)
                        preview_url = None
                    await send_ws(websocket, {
                        "type": "project_status",
                        "running": project_running,
                        "preview_url": preview_url
                    })

                elif msg.get("type") == "stop_project":
                    sandbox.stop_custom_project()
                    await send_ws(websocket, {
                        "type": "project_status",
                        "running": False
                    })
                    await send_ws(websocket, {
                        "type": "project_output",
                        "content": "[Sandbox] ExecuÃ§Ã£o interrompida.\n"
                    })

                elif msg.get("type") == "get_notes":
                    notes_str = await agents.run_obsidian_list_notes()
                    notes_list = [n.strip() for n in notes_str.split("\n") if n.strip() and not n.startswith("(Nenhuma")]
                    await send_ws(websocket, {
                        "type": "notes_list",
                        "notes": notes_list
                    })

                elif msg.get("type") == "read_note":
                    filename = msg.get("filename")
                    content = await agents.run_obsidian_read_note(filename)
                    await send_ws(websocket, {
                        "type": "note_content",
                        "filename": filename,
                        "content": content
                    })

                elif msg.get("type") == "save_note":
                    filename = msg.get("filename")
                    content = msg.get("content")
                    result = await agents.run_obsidian_write_note(filename, content)
                    notes_str = await agents.run_obsidian_list_notes()
                    notes_list = [n.strip() for n in notes_str.split("\n") if n.strip() and not n.startswith("(Nenhuma")]
                    await broadcast({
                        "type": "notes_list",
                        "notes": notes_list
                    })
                    await send_ws(websocket, {
                        "type": "note_saved",
                        "filename": filename,
                        "result": result
                    })

                elif msg.get("type") == "get_rules":
                    rules = database.get_compounding_rules()
                    await send_ws(websocket, {
                        "type": "rules_list",
                        "rules": rules
                    })

                elif await dispatch_mission_operation(websocket, msg, selected_project_id):
                    pass

                elif msg.get("type") == "get_planner_state":
                    plan_data = read_persistent_plan_state()
                    await send_ws(websocket, {
                        "type": "planner_state",
                        "data": plan_data
                    })

                elif msg.get("type") == "get_ast_state":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    ast_data = project_context_service.load_index(requested_project_id) if requested_project_id else {}
                    await send_ws(websocket, {"type": "ast_state", "data": ast_data or None})

                elif msg.get("type") == "list_projects":
                    await send_ws(websocket, {"type": "projects_list", "projects": project_context_service.list_projects()})

                elif msg.get("type") == "open_project":
                    requested_project_id = msg.get("project_id")
                    try:
                        await send_project_context(websocket, requested_project_id)
                        await send_latest_coding_session(websocket, requested_project_id)
                        await send_mission_list(websocket, requested_project_id)
                        selected_project_id = requested_project_id
                    except ProjectContextError as project_error:
                        await send_ws(websocket, system_message(str(project_error)))

                elif msg.get("type") == "index_project":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    if not requested_project_id:
                        await send_ws(websocket, system_message("Selecione um projeto antes de reindexar."))
                        continue
                    try:
                        await send_project_context(websocket, requested_project_id, reindex=True)
                        selected_project_id = requested_project_id
                    except ProjectContextError as project_error:
                        await send_ws(websocket, system_message(str(project_error)))

                elif msg.get("type") == "find_references":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    try:
                        reference_data = await asyncio.to_thread(
                            project_context_service.find_references,
                            requested_project_id,
                            msg.get("symbol", ""),
                        )
                        await send_ws(websocket, {"type": "project_references", "data": reference_data})
                    except ProjectContextError as project_error:
                        await send_ws(websocket, system_message(str(project_error)))

                elif msg.get("type") == "semantic_search":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    query = str(msg.get("query") or "").strip()
                    if not requested_project_id or not query:
                        await send_ws(websocket, system_message("Selecione um projeto e indique uma pesquisa."))
                        continue
                    try:
                        results = await asyncio.to_thread(project_context_service.semantic_search, requested_project_id, query)
                        await send_ws(websocket, {"type": "semantic_results", "query": query, "content": results})
                    except Exception as search_error:
                        log_event(logger, "project.semantic_search_error", level="warning", error=str(search_error))
                        await send_ws(websocket, system_message(safe_user_error("Pesquisa semantica indisponivel", search_error)))

                elif msg.get("type") == "create_coding_session":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    objective = str(msg.get("objective") or "").strip()
                    if not requested_project_id or not objective:
                        await send_ws(websocket, system_message("Selecione um projeto e indique o objetivo da alteracao."))
                        continue
                    try:
                        coding_session = await coding_session_service.create_assisted_session(requested_project_id, objective)
                        selected_project_id = requested_project_id
                        await send_ws(websocket, {"type": "coding_session", "data": coding_session.to_dict()})
                    except (CodingSessionError, ProjectContextError) as coding_error:
                        await send_ws(websocket, system_message(str(coding_error)))

                elif msg.get("type") == "apply_coding_session":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    try:
                        coding_session = await asyncio.to_thread(
                            coding_session_service.apply_session,
                            requested_project_id,
                            msg.get("session_id"),
                        )
                        await send_ws(websocket, {"type": "coding_session", "data": coding_session.to_dict()})
                        await send_project_context(websocket, requested_project_id)
                    except (CodingSessionError, ProjectContextError) as coding_error:
                        await send_ws(websocket, system_message(str(coding_error)))

                elif msg.get("type") == "rollback_coding_session":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    try:
                        coding_session = await asyncio.to_thread(
                            coding_session_service.rollback_session,
                            requested_project_id,
                            msg.get("session_id"),
                            bool(msg.get("confirmed")),
                        )
                        await send_ws(websocket, {"type": "coding_session", "data": coding_session.to_dict()})
                        await send_project_context(websocket, requested_project_id)
                    except (CodingSessionError, ProjectContextError) as coding_error:
                        await send_ws(websocket, system_message(str(coding_error)))

                elif msg.get("type") == "get_coding_session":
                    requested_project_id = msg.get("project_id") or selected_project_id
                    if requested_project_id:
                        await send_latest_coding_session(websocket, requested_project_id)

                elif msg.get("type") == "delete_rule":
                    key = msg.get("key")
                    database.delete_compounding_rule(key)
                    rules = database.get_compounding_rules()
                    await broadcast({
                        "type": "rules_list",
                        "rules": rules
                    })
                    await broadcast({
                        "type": "rules_updated",
                        "rules": rules
                    })

                elif msg.get("type") == "delete_architecture":
                    module = msg.get("module")
                    database.delete_architecture_memory(module)
                    arch = database.get_architecture_memory()
                    await broadcast({
                        "type": "architecture_updated",
                        "architecture": arch
                    })

                elif msg.get("type") == "delete_decision":
                    decision = msg.get("decision")
                    database.delete_engineering_decision(decision)
                    decisions = database.get_engineering_decisions()
                    await broadcast({
                        "type": "decisions_updated",
                        "decisions": decisions
                    })

            except Exception as parse_err:
                log_event(logger, "websocket.message.parse_error", level="error", error=str(parse_err))
                await send_ws(websocket, system_message(safe_user_error("Mensagem WebSocket invalida", parse_err)))
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        try:
            active_connections.remove(websocket)
        except KeyError:
            pass
        log_event(logger, "websocket.client.disconnected", active_connections=len(active_connections))

async def auto_extract_correction(prompt: str, history: list):
    clean = prompt.lower().strip(" .?!,")
    correction_signals = ["nÃ£o", "no", "errado", "corrige", "correÃ§Ã£o", "correcao", "prefiro", "deves", "deves usar", "esquece", "tenta outra vez", "tenta de novo", "muda"]
    if not any(clean.startswith(s) for s in correction_signals):
        return
    
    # We need history to understand what is being corrected
    if not history or len(history) < 2:
        return
        
    last_assistant_msg = ""
    for msg in reversed(history):
        if msg["role"] == "assistant" and msg.get("content"):
            last_assistant_msg = msg["content"]
            break
            
    if not last_assistant_msg:
        return
        
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    
    extracted_rule = None
    
    system_instruction = (
        "EstÃ¡s a monitorizar a conversa entre o utilizador (CEO) e o Jarvis/OpenClaw (orquestrador de IA). "
        "O CEO acabou de fazer uma correÃ§Ã£o ou expressar uma preferÃªncia sobre a resposta anterior do Jarvis.\n"
        "A tua tarefa Ã© extrair uma REGRA DE COMPORTAMENTO/PROGRAMAÃ‡ÃƒO concreta a partir desta correÃ§Ã£o para evitar que o Jarvis cometa o mesmo erro no futuro.\n"
        "Responde EXCLUSIVAMENTE em formato JSON com trÃªs chaves:\n"
        "1. 'rule_key': Uma palavra-chave Ãºnica (slug, sem espaÃ§os, minÃºscula, ex: 'neon_theme_default', 'venv_python_path').\n"
        "2. 'description': Resumo de 1 frase do erro ou contexto detetado (ex: 'Jarvis usou tema cyberpunk mas o utilizador corrigiu que prefere neon.').\n"
        "3. 'correction': InstruÃ§Ã£o corretiva clara em portuguÃªs de Portugal (ex: 'Sempre que o tema visual for solicitado ou alterado, usar neon por defeito, a menos que o utilizador especifique o contrÃ¡rio.').\n"
        "Se o input nÃ£o for realmente uma correÃ§Ã£o de comportamento tÃ©cnica relevante, responde apenas '{}'."
    )
    
    user_context = (
        f"Resposta Anterior do Jarvis:\n{last_assistant_msg}\n\n"
        f"CorreÃ§Ã£o/Feedback do CEO:\n{prompt}"
    )
    
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": ollama_model,
            "prompt": f"<|im_start|>system\n{system_instruction}<|im_end|>\n<|im_start|>user\n{user_context}<|im_end|>\n<|im_start|>assistant\n",
            "stream": False,
            "options": {"num_predict": 300}
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                extracted_rule = res.json().get("response", "")
                    
        if extracted_rule:
            rule_data = json.loads(extracted_rule)
            if rule_data and "rule_key" in rule_data and "correction" in rule_data:
                key = rule_data["rule_key"].strip().lower()
                desc = rule_data.get("description", "Auto-extraÃ­do via feedback")
                corr = rule_data["correction"]
                database.add_compounding_rule(key, desc, corr)
                log_event(logger, "auto_learning.rule_saved", rule_key=key)
                await broadcast({
                    "type": "chat",
                    "sender": "SISTEMA",
                    "role": "System",
                    "content": f"ðŸ§  *Auto-Aprendizagem:* Nova regra `{key}` gravada na minha Compounding Memory com base no seu feedback."
                })
                await broadcast({"type": "rules_list", "rules": database.get_compounding_rules()})
                await broadcast({"type": "rules_updated", "rules": database.get_compounding_rules()})
    except Exception as e:
        log_event(logger, "auto_learning.rule_extract_error", level="error", error=str(e))

async def classify_intent(prompt: str, history: list = None) -> str:
    clean = prompt.lower().strip(" .?!,")
    # Instant filters to bypass model queries for common greetings
    greetings = ["olÃ¡", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem", "como estÃ¡s", "olÃ¡ jarvis", "como vais", "tavas ai", "estÃ¡s bem"]
    if clean in greetings:
        return "CHAT"
    
    # --- CRITICAL FIX: Short affirmative follow-ups must route as TASK when history has task context ---
    # Words like 'sim', 'comeÃ§a', 'avanÃ§a', 'ok', 'vai', 'continua', 'trata disso' are ALWAYS TASK
    # when there's conversation history (user confirming something the agent said it would do)
    task_confirmations = [
        "sim", "ok", "claro", "avanÃ§a", "comeÃ§a", "comeÃ§a entÃ£o", "comeÃ§a jÃ¡", "vai", "vai em frente",
        "pode avanÃ§ar", "pode comeÃ§ar", "pode ir", "trata disso", "trata de tudo", "trata tu",
        "continua", "segue", "segue em frente", "procede", "faz isso", "faz", "faz tu",
        "eu quero que trates de tudo", "quero que trates de tudo", "faz tudo tu",
        "eu vou sair do pc", "quando chegar quero tudo pronto", "avisa quando estiver pronto",
        "tudo pronto", "quando estiver pronto", "deixa correr", "pode ser", "Ã³ptimo", "Ã³timo"
    ]
    if any(clean == c or clean.startswith(c) for c in task_confirmations):
        if history and len(history) >= 2:  # Only TASK if there's prior context
            return "TASK"
        
    # Check if the prompt is a question (should be handled via CHAT unless classified by LLM)
    is_question = prompt.strip().endswith("?") or any(clean.startswith(q) for q in ["como", "o que", "o quÃª", "porque", "porquÃª", "quais", "qual", "onde", "quando", "quanto", "quem", "serÃ¡", "explica", "imagina", "consegues", "sabes", "poderias", "gostarias", "se eu", "conseguirias"])
    
    # --- GUARD: Exploratory / meta questions must always be CHAT ---
    # "da-me ideias", "que fazes", "mostra-me os agentes", "o que consegues", etc.
    exploratory_patterns = [
        "que fazes", "o que fazes", "o que Ã© que fazes", "o que podes fazer",
        "o que consegues", "o que consegues fazer", "o que Ã© que consegues",
        "da-me ideias", "dÃ¡-me ideias", "dÃ¡ ideias", "dÃ¡-me sugestÃµes",
        "mostra-me os agentes", "mostra os agentes", "quais sÃ£o os agentes",
        "quais sÃ£o as funcionalidades", "quais sÃ£o as tuas capacidades",
        "apresenta-te", "apresenta te", "descreve-te", "fala sobre ti",
        "o que Ã©s", "quem Ã©s", "quem es tu", "o que sabes fazer",
        "dÃ¡-me exemplos", "da-me exemplos", "dÃ¡ exemplos",
        "tens ideias", "dÃ¡-me uma ideia", "sugere algo", "sugere alguma coisa",
        "para testar-te", "para te testar", "como podes ajudar",
    ]
    if any(ep in clean for ep in exploratory_patterns):
        return "CHAT"

    if not is_question:
        # Check template suggestions directly to force TASK
        known_suggestions = [
            "pomodoro timer minimalista", "landing page para cafÃ© de especialidade", "app de lista de tarefas futurista",
            "campanha de lanÃ§amento de curso de ia", "estratÃ©gia de conteÃºdo para linkedin de startup", "artigos sobre produtividade com agentes autÃ³nomos",
            "estudo de viabilidade para central de energia solar", "plano de investimento em e-commerce", "anÃ¡lise de risco de abertura de novo ginÃ¡sio",
            "ticket: cliente reclama de atraso de 10 dias na entrega", "ticket: dificuldade em recuperar password de administrador", "ticket: dÃºvida sobre polÃ­tica de reembolso de software"
        ]
        if clean in known_suggestions or any(s in clean for s in known_suggestions):
            return "TASK"
            
        # Common direct task actions and task-centric nouns
        # NOTE: 'faz' is ONLY a task trigger if there is a concrete object after it
        # e.g. 'faz uma landing page' YES, but 'que fazes' NO (caught above)
        task_keywords = ["pomodoro", "timer", "landing page", "website", "site", "criar", "cria", "desenvolve", "desenvolver", "fazer", "desenha", "desenhar", "gera", "gerar", "constrÃ³i", "construir", "programa", "programar", "executa", "executar", "corre", "correr", "escreve", "escrever", "esqueleto", "projeto", "dashboard", "elabora", "elaborar", "planeia", "planejar", "estratÃ©gia", "estrategia", "analisa", "analisar", "anÃ¡lise", "estudo", "relatÃ³rio", "relatorio", "campanha", "investimento", "viabilidade", "negÃ³cio", "negocio"]
        if any(w in clean for w in task_keywords):
            return "TASK"
            

    # Direct shortcut for opening/running apps/commands to avoid LLM misclassification
    if find_local_app_request(prompt):
        return "TASK"

    action_verbs = ["abre", "abrir", "abro", "abras", "inicia", "iniciar", "executa", "executar", "corre", "correr", "lanÃ§a", "lanÃ§ar", "start", "open", "run"]
    targets = [
        "whatsapp", "chrome", "edge", "browser", "navegador", "bloco", "notepad",
        "calculadora", "calc", "paint", "explorador", "explorer", "terminal", "cmd",
        "powershell", "excel", "word", "powerpoint", "outlook", "office",
        "folha de calculo", "spreadsheet", "app", "programa", "jogo", "game",
        "site", "website", "google", "youtube",
    ]
    
    words = clean.split()
    has_action = any(v in words or clean.startswith(v) for v in action_verbs)
    has_target = any(t in clean for t in targets)
    
    if has_action and has_target:
        return "TASK"

    mode = os.getenv("ORCHESTRATOR_MODE", "local").lower()

    if mode == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                
                # Format history for Claude classification
                claude_messages = []
                if history:
                    for msg in history[:-1]:
                        claude_messages.append({"role": msg["role"], "content": msg["content"]})
                claude_messages.append({"role": "user", "content": prompt})
                
                res = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: client.messages.create(
                        model="claude-3-5-haiku-latest",
                        max_tokens=10,
                        system="Classifica o Ãºltimo input do utilizador. Usa o histÃ³rico de conversa para contexto. Se for um pedido ou ordem para realizar uma aÃ§Ã£o, comando de terminal, criar ficheiro, website, tirar screenshot, ver janelas, ou uma resposta afirmativa/instruÃ§Ã£o de seguimento para realizar uma tarefa, responde apenas 'TASK'. Se for conversa casual, saudaÃ§Ã£o, agradecimento ou ruÃ­do/texto sem sentido, responde apenas 'CHAT'.",
                        messages=claude_messages
                    )
                )
                val = res.content[0].text.strip().upper()
                if "TASK" in val:
                    return "TASK"
                return "CHAT"
            except Exception:
                pass

    # Local Ollama classification
    try:
        url = "http://localhost:11434/api/generate"
        
        # Format history string
        history_str = ""
        if history:
            for msg in history[:-1]:
                role_name = "Utilizador" if msg["role"] == "user" else "Jarvis"
                history_str += f"{role_name}: {msg['content']}\n"
                
        payload = {
            "model": os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
            "prompt": (
                "HistÃ³rico de conversa:\n"
                f"{history_str}"
                f"Ãšltimo input do utilizador: '{prompt}'\n\n"
                "Classifica o Ãºltimo input do utilizador. Se for um pedido ou ordem para realizar uma aÃ§Ã£o, comando de terminal, criar ficheiro, website, screenshot, listar pasta, ou uma resposta afirmativa/instruÃ§Ã£o de seguimento para realizar uma tarefa, responde apenas com a palavra 'TASK'.\n"
                "Se for conversa casual, saudaÃ§Ã£o, agradecimento ou texto sem sentido/ruÃ­do de transcriÃ§Ã£o, responde apenas com a palavra 'CHAT'.\n"
                "Resposta (apenas TASK ou CHAT):"
            ),
            "stream": False,
            "options": {"temperature": 0.0}
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                res_text = response.json().get("response", "").strip().upper()
                if "TASK" in res_text:
                    return "TASK"
        return "CHAT"
    except Exception as e:
        log_event(logger, "intent.classification_error", level="error", error=str(e))
        return "CHAT"

async def run_casual_chat(prompt: str):
    mode = os.getenv("ORCHESTRATOR_MODE", "local").lower()
    response_text = ""

    if not response_text and mode == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                
                # Format conversation history for Claude
                claude_messages = []
                for msg in conversation_history:
                    claude_messages.append({"role": msg["role"], "content": msg["content"]})
                if not claude_messages or claude_messages[-1]["content"] != prompt:
                    claude_messages.append({"role": "user", "content": prompt})
                    
                res = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: client.messages.create(
                        model="claude-3-5-sonnet-latest",
                        max_tokens=500,
                        system=(
                            "Ã‰s o OpenClaw, o assistente central, COO e orquestrador avanÃ§ado de IA da agÃªncia. "
                            "O utilizador Ã© o CEO da agÃªncia (podes tratÃ¡-lo ocasionalmente por 'CEO' ou 'Sir' de forma moderada, respeitosa e discreta, sem repetir em todas as frases!). "
                            "Tu ficas a um nÃ­vel abaixo do CEO, coordenas a tua equipa de agentes especialistas (Alex - Produto, Clara - Designer, Devon - Programador, Quinn - QA) e reportas diretamente ao CEO. "
                            "CONCISÃƒO ABSOLUTA: Responde sempre em portuguÃªs de Portugal de forma extremamente curta (1 ou 2 frases no mÃ¡ximo), natural, elegante e fluida. Nunca faÃ§as listas das tarefas ou expliques o que os agentes fazem, a menos que seja explicitamente solicitado. Se o CEO pedir para criar ou fazer algo, diz apenas que vais tratar do assunto e avanÃ§a."
                            "Tens acesso ao histÃ³rico recente da conversa (incluindo as mensagens de debate dos teus agentes) e lembras-te perfeitamente de tudo o que foi dito ou feito nesta sessÃ£o. "
                            "Nunca digas que Ã©s um modelo de linguagem ou que nÃ£o tens memÃ³ria. Age sempre como um assistente consciente e integrado no sistema."
                        ),
                        messages=claude_messages
                    )
                )
                response_text = res.content[0].text
            except Exception as e:
                response_text = safe_user_error("Erro ao comunicar com a Claude API", e)
    
    if not response_text:
        try:
            url = "http://localhost:11434/api/chat"
            
            # Format conversation history for local Ollama
            ollama_messages = [
                {"role": "system", "content": (
                    "Ã‰s o OpenClaw, o assistente central, COO e orquestrador avanÃ§ado de IA da agÃªncia. "
                    "O utilizador Ã© o CEO da agÃªncia (podes tratÃ¡-lo ocasionalmente por 'CEO' ou 'Sir' de forma moderada, respeitosa e discreta, sem repetir em todas as frases!). "
                    "Tu ficas a um nÃ­vel abaixo do CEO, coordenas a tua equipa de agentes especialistas (Alex - Produto, Clara - Designer, Devon - Programador, Quinn - QA) e reportas diretamente ao CEO. "
                    "CONCISÃƒO ABSOLUTA: Responde sempre em portuguÃªs de Portugal de forma extremamente curta (1 ou 2 frases no mÃ¡ximo), natural, elegante e fluida. Nunca faÃ§as listas das tarefas ou expliques o que os agentes fazem, a menos que seja explicitamente solicitado. Se o CEO pedir para criar ou fazer algo, diz apenas que vais tratar do assunto e avanÃ§a."
                    "Tens acesso ao histÃ³rico recente da conversa (incluindo as mensagens de debate dos teus agentes) e lembras-te perfeitamente de tudo o que foi dito ou feito nesta sessÃ£o. "
                    "Nunca digas que Ã©s um modelo de linguagem ou que nÃ£o tens memÃ³ria. Age sempre como um assistente consciente e integrado no sistema."
                )}
            ]
            for msg in conversation_history:
                ollama_messages.append({"role": msg["role"], "content": msg["content"]})
            if not conversation_history or conversation_history[-1]["content"] != prompt:
                ollama_messages.append({"role": "user", "content": prompt})
                
            payload = {
                "model": os.getenv("OLLAMA_MODEL", "qwen2.5:14b"),
                "messages": ollama_messages,
                "stream": False
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                response_text = res.json().get("message", {}).get("content", "")
        except Exception as e:
            response_text = safe_user_error("Erro ao comunicar com o Ollama local", e)
            
    await broadcast({
        "type": "chat",
        "sender": "OPENCLAW",
        "role": "Orquestrador",
        "content": response_text
    })
    
    # Append assistant response to history
    conversation_history.append({"role": "assistant", "content": response_text})
    if len(conversation_history) > 100:
        conversation_history.pop(0)

async def run_orchestration_task(prompt: str, session_id: int):
    try:
        # Check for UI-specific commands to bypass LLM and prevent running command line tools
        clean_prompt = prompt.lower().strip(" .?!,")
        
        dashboard_keywords = ["abre a dashboard", "abrir a dashboard", "mostra a dashboard", "mostrar a dashboard", "ver a dashboard", "dashboard", "abrir painel", "mostrar painel", "abre o painel", "mostra o painel", "abrir dashboard", "mostrar dashboard", "mostra-me a dashboard", "mostra-me o painel", "exibe a dashboard", "exibir a dashboard"]
        main_screen_keywords = ["volta ao ecra principal", "volta ao ecrÃ£ principal", "ecra principal", "ecrÃ£ principal", "volta para o inicio", "volta para o inÃ­cio", "volta ao inicio", "volta ao inÃ­cio", "limpa o ecra", "limpa o ecrÃ£", "clean", "clean hud", "ja nao preciso de nada", "jÃ¡ nÃ£o preciso de nada", "modo clean", "oculta a dashboard", "fecha a dashboard", "minimiza a dashboard", "ocultar dashboard", "fechar dashboard", "voltar ao ecrÃ£ principal", "voltar ao ecra principal", "voltar ao inÃ­cio", "voltar ao inicio", "volta ao menu principal", "voltar ao menu principal", "ja nao preciso de ajuda", "jÃ¡ nÃ£o preciso de ajuda"]
        
        open_chat_keywords = ["abre o chat", "abrir o chat", "mostra o chat", "mostrar o chat", "chat", "abre a conversa", "abrir conversa", "mostra a conversa", "exibe o chat", "spawna o chat", "spawna a janela de chat", "abre janela de chat", "quero o chat", "mostra chat", "exibir chat"]
        close_chat_keywords = ["fecha o chat", "fechar o chat", "oculta o chat", "ocultar o chat", "minimiza o chat", "esconde o chat", "esconder o chat", "fecha a conversa", "fechar conversa", "ocultar conversa", "fechar janela de chat"]
        open_dev_keywords = ["abre o painel dev", "abrir o painel dev", "mostra o painel dev", "mostrar o painel dev", "painel dev", "abre painel de desenvolvimento", "mostra painel dev", "abre o dev panel", "mostra dev panel", "abre a consola dev", "mostrar consola dev", "abrir dev", "abrir consola de desenvolvimento", "mostra o painel de desenvolvimento", "abre painel de controlo", "abre painel de controle"]
        close_dev_keywords = ["fecha o painel dev", "fechar o painel dev", "oculta o painel dev", "ocultar o painel dev", "minimiza o painel dev", "fecha dev", "fechar dev", "esconde dev", "esconder dev", "fecha o dev panel", "fechar dev panel"]

        if clean_prompt in open_chat_keywords or any(k in clean_prompt for k in ["abre o chat", "mostra o chat", "abre a conversa"]):
            await broadcast({"type": "ui_action", "action": "open_chat"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Janela de conversa aberta, Sir."
            })
            return

        if clean_prompt in close_chat_keywords or any(k in clean_prompt for k in ["fecha o chat", "oculta o chat", "fecha a conversa"]):
            await broadcast({"type": "ui_action", "action": "close_chat"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Ocultei a janela de conversa."
            })
            return

        if clean_prompt in open_dev_keywords or any(k in clean_prompt for k in ["abre o painel dev", "mostra o painel dev", "abre o dev panel"]):
            await broadcast({"type": "ui_action", "action": "open_dev"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Painel de desenvolvimento expandido."
            })
            return

        if clean_prompt in close_dev_keywords or any(k in clean_prompt for k in ["fecha o painel dev", "oculta o painel dev", "fecha o dev panel"]):
            await broadcast({"type": "ui_action", "action": "close_dev"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Painel de desenvolvimento ocultado."
            })
            return

        if clean_prompt in dashboard_keywords or any(k in clean_prompt for k in ["abre a dashboard", "mostra a dashboard", "mostra-me a dashboard", "abrir a dashboard", "abrir o painel"]):
            await broadcast({"type": "ui", "action": "show_dashboard"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Painel de trabalho e dashboard expandidos, Sir."
            })
            return
            
        if clean_prompt in main_screen_keywords or any(k in clean_prompt for k in ["volta ao ecra principal", "volta ao ecrÃ£ principal", "volta para o inicio", "volta para o inÃ­cio", "ja nao preciso de nada", "jÃ¡ nÃ£o preciso de nada", "modo clean"]):
            await broadcast({"type": "ui", "action": "show_main_screen"})
            await broadcast_state("idle")
            await broadcast({
                "type": "chat",
                "sender": "OPENCLAW",
                "role": "Orquestrador",
                "content": "Voltando ao ecrÃ£ principal e ativando o modo clean, Sir."
            })
            return

        local_app = find_local_app_request(prompt)
        if local_app:
            ok, details = await open_local_application(local_app)
            await broadcast_state("idle")
            if ok:
                log_event(logger, "local_app.opened", app=local_app["id"])
                await broadcast({
                    "type": "chat",
                    "sender": "OPENCLAW",
                    "role": "Orquestrador",
                    "content": f"Abri o {local_app['label']}."
                })
            else:
                log_event(logger, "local_app.open_error", level="error", app=local_app["id"], error=details)
                await broadcast({
                    "type": "chat",
                    "sender": "OPENCLAW",
                    "role": "Orquestrador",
                    "content": f"Tentei abrir o {local_app['label']}, mas o Windows devolveu erro: {details}"
                })
            return
        # Rota de execuÃ§Ã£o de tarefas baseadas em objetivos
        pass

        # Optional auto-learning is useful, but it costs an extra model call per prompt.
        if env_bool("ORCHESTRATOR_AUTO_LEARN", False):
            asyncio.create_task(auto_extract_correction(prompt, conversation_history))

        # 1. Classify intent to separate chat/noise from actionable developer tasks
        intent = await classify_intent(prompt, conversation_history)
        log_event(logger, "orchestration.intent_classified", intent=intent, prompt_length=len(prompt))
        
        if intent == "CHAT":
            await run_casual_chat(prompt)
            await broadcast_state("idle")
            return

        from agents.orchestrator.project_builder import (
            ProjectBuilderError,
            build_project,
            is_project_creation_request,
        )

        if is_project_creation_request(prompt):
            await broadcast({
                "type": "project_output",
                "content": "[ProjectBuilder] A gerar plano JSON e criar projeto isolado...\n",
            })

            def on_project_log(content: str):
                run_in_main_loop(broadcast({
                    "type": "project_output",
                    "content": content,
                }))

            try:
                project_result = await build_project(
                    prompt,
                    on_file=on_file_update,
                    on_log=on_project_log,
                )
                report = project_result.report()
                conversation_history.append({"role": "assistant", "content": report})
                if len(conversation_history) > 100:
                    conversation_history.pop(0)
                await broadcast({
                    "type": "project_output",
                    "content": report + "\n",
                })
                await broadcast({
                    "type": "project_status",
                    "running": project_result.preview_started,
                    "preview_url": project_result.preview_url or None,
                })
                created_project_id = os.path.basename(project_result.project_dir)
                project_payload = await asyncio.to_thread(
                    project_context_service.project_payload,
                    created_project_id,
                    True,
                )
                await broadcast({"type": "projects_list", "projects": project_context_service.list_projects()})
                await broadcast({"type": "project_context", **project_payload})
                await broadcast({
                    "type": "chat",
                    "sender": "OPENCLAW",
                    "role": "Project Builder",
                    "content": report,
                })
                await broadcast_state("idle")
                await broadcast({"type": "complete", "result": report})
                return
            except ProjectBuilderError as e:
                error_report = f"Project Builder falhou: {e}"
                conversation_history.append({"role": "assistant", "content": error_report})
                await broadcast({
                    "type": "chat",
                    "sender": "OPENCLAW",
                    "role": "Project Builder",
                    "content": error_report,
                })
                await broadcast({
                    "type": "project_output",
                    "content": error_report + "\n",
                })
                await broadcast_state("idle")
                await broadcast({"type": "complete", "result": error_report})
                return
            
        async def on_template_change(new_template_name: str):
            normalized_name = normalize_template_name(new_template_name)
            agents.active_template_name = normalized_name
            await broadcast(build_template_payload(normalized_name))

        # 2. Run the unified ReAct tool-driven orchestrator
        # Automatic template detection: route research/informational tasks to research_swarm
        template_name = getattr(agents, "active_template_name", "builder_swarm")
        clean_prompt = prompt.lower().strip(" .?!,")
        
        coding_keywords = ["criar website", "criar site", "criar landing page", "desenvolver app", "desenvolver website", 
                           "programar", "cria um site", "cria uma app", "cria um jogo", "code a", "build a website", 
                           "write code", "escrever cÃ³digo", "criar api", "criar base de dados"]
                           
        research_keywords = ["pesquisa", "procura", "vaga", "vagas", "emprego", "analisa", "lÃª o", "ler o", "resume", 
                             "sugestÃµes", "melhorar", "cv", "currÃ­culo", "curriculo", "informaÃ§Ã£o", "investiga", 
                             "sugere", "explica", "dÃ¡ ideias", "ideias para"]
                             
        if any(rk in clean_prompt for rk in research_keywords) and not any(ck in clean_prompt for ck in coding_keywords):
            if template_name != "research_swarm":
                template_name = "research_swarm"
                agents.active_template_name = "research_swarm"
                await on_template_change("research_swarm")
                
        result = await agents.run_jarvis_orchestration(
            prompt,
            session_id,
            on_agent_message,
            on_file_update,
            on_kanban_update,
            history=conversation_history,
            template_name=template_name,
            on_template_change=on_template_change
        )
        
        # Append assistant response to history
        conversation_history.append({"role": "assistant", "content": result})
        if len(conversation_history) > 100:
            conversation_history.pop(0)
                
        html = ""
        css = ""
        js = ""
        try:
            sandbox_dir = sandbox.SANDBOX_DIR
            index_p = os.path.join(sandbox_dir, "index.html")
            style_p = os.path.join(sandbox_dir, "styles.css")
            app_p = os.path.join(sandbox_dir, "app.js")
            
            if os.path.exists(index_p):
                with open(index_p, "r", encoding="utf-8") as f:
                    html = f.read()
            if os.path.exists(style_p):
                with open(style_p, "r", encoding="utf-8") as f:
                    css = f.read()
            if os.path.exists(app_p):
                with open(app_p, "r", encoding="utf-8") as f:
                    js = f.read()
                    
            if html or css or js:
                database.save_project(session_id, "Projeto Gerado", prompt, html, css, js)
        except Exception as file_err:
            log_event(logger, "project.persist_error", level="error", error=str(file_err))
            
        await broadcast_state("idle")
        if is_orchestration_result_error(result):
            await broadcast({"type": "system", "content": "OrquestraÃ§Ã£o terminou com erro/aviso. Ver detalhes na mensagem final."})
        else:
            await broadcast({"type": "system", "content": "OrquestraÃ§Ã£o concluÃ­da com sucesso!"})
        await broadcast({"type": "complete", "result": result})
        
    except Exception as e:
        log_event(logger, "orchestration.task_error", level="error", error=str(e))
        await broadcast_state("idle")
        await broadcast({"type": "system", "content": safe_user_error("Erro na orquestracao", e)})

def start_frontend_http_server():
    start_frontend_http_server_service(os.path.dirname(__file__), port=8000)

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    database.init_db()
    
    # Initialize voice service
    init_voice_service()
    
    # Start Frontend File Server on port 8000
    start_frontend_http_server()

    # Start Sandbox Preview Server on port 8080
    sandbox.start_docker_sandbox()
    
    # Start WebSocket Server on port 8001
    log_event(logger, "runtime.health", health=build_runtime_health())
    log_event(logger, "websocket.server.starting", host=WS_HOST, port=8001)
    async with websockets.serve(handle_client, WS_HOST, 8001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_event(logger, "server.shutdown")

