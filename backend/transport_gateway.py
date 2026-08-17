"""
JARVIS OS - Unified Stdio / Native IPC Transport Gateway
Permite que o Electron Main e processos locais comuniquem com o JARVIS via STDIO JSON-RPC,
eliminando a necessidade de sockets de rede ou portas TCP no modo Desktop.
"""

from __future__ import annotations

import sys
import json
import asyncio
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass, field

from backend.websocket.context import WebSocketSessionState
from backend.logging_config import log_event


class StdioTransportGateway:
    """Gateway de transporte baseado em STDIO line-delimited JSON."""

    def __init__(
        self,
        dispatcher: Any,
        logger: Any = None,
        on_broadcast: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.logger = logger
        self.on_broadcast = on_broadcast
        self.session_state = WebSocketSessionState()
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
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.read_error", error=str(e))

    async def _threaded_read_loop(self) -> None:
        """Loop de leitura em thread separada com executor para Windows Proactor/Selector."""
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
            except Exception as e:
                if self.logger:
                    log_event(self.logger, "ipc.threaded_read_error", error=str(e))
                await asyncio.sleep(0.1)

    async def _handle_raw_line(self, line: str) -> None:
        """Processa e despacha a linha JSON recebida."""
        if not line.startswith("{") or not line.endswith("}"):
            return

        try:
            data = json.loads(line)
        except Exception:
            return

        if not isinstance(data, dict):
            return

        msg_type = data.get("type")
        if not msg_type:
            return

        # Objeto virtual de websocket para handlers existentes
        class VirtualIPCClient:
            def __init__(self, gateway: StdioTransportGateway):
                self.gateway = gateway

            async def send(self, msg_str: str | dict):
                if isinstance(msg_str, str):
                    try:
                        msg_dict = json.loads(msg_str)
                    except Exception:
                        msg_dict = {"raw": msg_str}
                else:
                    msg_dict = msg_str
                await self.gateway.send_message(msg_dict)

        virtual_client = VirtualIPCClient(self)

        try:
            # Despachar para o WebSocketDispatcher unificado
            if hasattr(self.dispatcher, "dispatch"):
                await self.dispatcher.dispatch(
                    websocket=virtual_client,
                    message=data,
                    session=self.session_state,
                )
            elif hasattr(self.dispatcher, "handle"):
                await self.dispatcher.handle(virtual_client, data)
        except Exception as e:
            await self.send_message({
                "type": "error",
                "message": f"Erro no processamento IPC: {e}",
            })
