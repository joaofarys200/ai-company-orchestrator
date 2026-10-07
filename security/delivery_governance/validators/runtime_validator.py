"""
Validador de Integridade em Runtime.
Executa quando possível:
- Teste de servidor / HTTP Health Check.
- Verificação se o servidor arranca sem exceção fatal.
- Deteção de portas em escuta ou falhas imediatas de execução (Exit Code != 0).
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


class RuntimeIntegrityValidator:
    """Valida o comportamento dinâmico e execução da aplicação em runtime."""

    @classmethod
    def check_http_endpoint(
        cls,
        url: str,
        timeout: float = 2.0,
        retries: int = 3,
        expected_status: Tuple[int, ...] = (200, 201, 204, 301, 302),
    ) -> Dict[str, Any]:
        """Efetua um health check HTTP a um endpoint ativo."""
        last_error = ""
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Jarvis-Runtime-Validator/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = response.status
                    if status in expected_status:
                        return {
                            "valid": True,
                            "url": url,
                            "status_code": status,
                            "attempt": attempt + 1,
                            "error": None,
                        }
                    else:
                        last_error = f"Status HTTP inesperado: {status}"
            except Exception as exc:
                last_error = str(exc)
                time.sleep(0.3)

        return {
            "valid": False,
            "url": url,
            "status_code": None,
            "error": last_error,
        }

    @classmethod
    def check_port_listening(cls, host: str = "127.0.0.1", port: int = 3000, timeout: float = 1.0) -> bool:
        """Verifica se uma porta de rede local está em escuta."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            return result == 0
        finally:
            sock.close()
