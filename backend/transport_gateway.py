"""
JARVIS OS - Unified Stdio / Native IPC Transport Gateway
Permite que o Electron Main e processos locais comuniquem com o JARVIS via STDIO JSON-RPC,
eliminando a necessidade de sockets de rede ou portas TCP no modo Desktop.
"""

from __future__ import annotations

import sys
import json
import asyncio
from typing import Any, Callable, Optional, Dict, Awaitable
from dataclasses import dataclass, field

from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.message_protocol import (
    normalize_ws_message,
    system_message,
    validate_client_message,
)
from backend.websocket.context import (
    WebSocketSessionState,
    bind_response_request_id,
    current_response_request_id,
    reset_response_request_id,
    resolve_request_id,
)


class VirtualIPCClient:
    """Objeto virtual compatível com WebSocket para handlers existentes."""

    def __init__(self, gateway: "StdioTransportGateway"):
        self.gateway = gateway

    async def send(self, msg_str: str | dict):
        if isinstance(msg_str, str):
            try:
                msg_dict = json.loads(msg_str)
            except Exception:
                msg_dict = {"raw": msg_str}
        else:
            msg_dict = dict(msg_str)
        if isinstance(msg_dict, dict):
            if isinstance(msg_dict.get("type"), str):
                msg_dict = normalize_ws_message(msg_dict)
            active_req_id = current_response_request_id()
            if active_req_id and not msg_dict.get("request_id"):
                msg_dict["request_id"] = active_req_id
        await self.gateway.send_message(msg_dict)


class StdioTransportGateway:
    """Gateway de transporte baseado em STDIO line-delimited JSON."""

    def __init__(
        self,
        dispatcher: Any,
        logger: Any = None,
        on_connect: Optional[Callable[[Any, WebSocketSessionState], Awaitable[None]]] = None,
        on_broadcast: Optional[Callable[[Dict[str, Any]], None]] = None,
        validate_messages: Optional[bool] = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.logger = logger
        self.on_connect = on_connect
        self.on_broadcast = on_broadcast
        self.validate_messages = (
            validate_messages
            if validate_messages is not None
            else hasattr(dispatcher, "message_types")
        )
        self.session_state = WebSocketSessionState()
        self.virtual_client = VirtualIPCClient(self)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._write_lock = asyncio.Lock()

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Task:
        """Inicia a escuta contínua de mensagens no sys.stdin."""
        self._running = True
        self._loop = loop or asyncio.get_event_loop()
        return self._loop.create_task(self._listen_loop())

    def stop(self) -> None:
        """Encerra o gateway de transporte."""
        self._running = False

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Envia uma mensagem JSON formatada para o stdout."""
        async with self._write_lock:
            try:
                line = json.dumps(message, ensure_ascii=False)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.send_error", error=str(e))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Transmite mensagem para o cliente IPC nativo."""
        await self.send_message(message)
        if self.on_broadcast:
            try:
                self.on_broadcast(message)
            except Exception:
                pass

    async def _listen_loop(self) -> None:
        """Lê linhas do sys.stdin em background sem bloquear o event loop."""
        if sys.stdin is None or getattr(sys.stdin, "closed", True):
            return

        # Trigger on_connect initial sync if handler provided
        if self.on_connect:
            try:
                await self.on_connect(self.virtual_client, self.session_state)
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.initial_sync_error", error=str(e))

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        try:
            await self._loop.connect_read_pipe(lambda: protocol, sys.stdin)
        except Exception:
            # Fallback para ambientes onde connect_read_pipe não é suportado no Windows
            return await self._threaded_read_loop()

        while self._running:
            try:
                line_bytes = await reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    await self._handle_raw_line(line)
            except asyncio.CancelledError:
                break
            except (OSError, ValueError):
                break
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.read_error", error=str(e))
                break

    async def _threaded_read_loop(self) -> None:
        """Loop de leitura em thread separada com executor para Windows Proactor/Selector."""
        if sys.stdin is None or getattr(sys.stdin, "closed", True):
            return

        loop = self._loop or asyncio.get_running_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                cleaned_line = line.strip()
                if cleaned_line:
                    await self._handle_raw_line(cleaned_line)
            except asyncio.CancelledError:
                break
            except (OSError, ValueError):
                # Stdin desconectado ou inválido
                break
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.threaded_read_error", error=str(e))
                break

    async def _handle_raw_line(self, line: str) -> None:
        """Processa, valida minimamente e despacha a linha JSON recebida."""
        if not line.startswith("{") or not line.endswith("}"):
            return

        try:
            data = json.loads(line)
        except Exception as exc:
            await self.send_message({
                "type": "error",
                "message": f"Payload IPC JSON inválido: {exc}",
            })
            return

        if not isinstance(data, dict):
            await self.send_message({
                "type": "error",
                "message": "Payload IPC deve ser um objeto JSON.",
            })
            return

        msg_type = data.get("type")
        req_id = data.get("request_id")
        if not isinstance(msg_type, str) or not msg_type.strip():
            err_payload: Dict[str, Any] = {
                "type": "error",
                "message": "Campo 'type' obrigatório e em falta no payload IPC.",
            }
            if req_id is not None:
                err_payload["request_id"] = req_id
            await self.send_message(err_payload)
            return
        msg_type = msg_type.strip()
        request_token = None
        try:
            _, supplied_request_id = resolve_request_id(data)
            request_token = bind_response_request_id(supplied_request_id)
            payload = validate_client_message(data) if self.validate_messages else data
            # Despachar para o WebSocketDispatcher unificado
            if hasattr(self.dispatcher, "dispatch"):
                await self.dispatcher.dispatch(
                    websocket=self.virtual_client,
                    message=payload,
                    session=self.session_state,
                )
            elif hasattr(self.dispatcher, "handle"):
                await self.dispatcher.handle(self.virtual_client, payload)
        except Exception as e:
            if msg_type.startswith("study_"):
                err_msg: Dict[str, Any] = {
                    "type": "study_error",
                    "message": safe_user_error("Erro no processamento IPC de estudo", e),
                }
            else:
                err_msg = system_message(safe_user_error("Mensagem IPC invalida", e))
            if req_id is not None:
                err_msg["request_id"] = req_id
            await self.send_message(err_msg)
        finally:
            if request_token is not None:
                reset_response_request_id(request_token)
