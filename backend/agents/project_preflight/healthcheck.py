"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Healthcheck Engine: Probes startup health, open sockets, HTTP status, and latency.
Never conflates 'process alive' with 'application healthy'.
"""

from __future__ import annotations

import http.client
import socket
import subprocess
import time
from typing import Optional

from agents.project_preflight.models import StartupHealthResult


class HealthcheckEngine:
    """
    Probes running project instances to determine real functional readiness.
    """

    def probe_health(
        self,
        port: int,
        path: str = "/",
        process: Optional[subprocess.Popen] = None,
        timeout_seconds: float = 5.0,
    ) -> StartupHealthResult:
        t_start = time.perf_counter()
        deadline = time.time() + timeout_seconds

        # 1. First check if process is alive (if provided)
        if process and process.poll() is not None:
            return StartupHealthResult(
                started=False,
                ready=False,
                port=port,
                failure_reason=f"Process exited immediately with returncode {process.returncode}.",
                latency_ms=(time.perf_counter() - t_start) * 1000.0,
            )

        # 2. Wait for port to open
        port_open = False
        while time.time() < deadline:
            if self._is_socket_open(port):
                port_open = True
                break
            # If process dies while waiting
            if process and process.poll() is not None:
                return StartupHealthResult(
                    started=True,
                    ready=False,
                    port=port,
                    failure_reason=f"Process terminated during socket startup (exit {process.returncode}).",
                    latency_ms=(time.perf_counter() - t_start) * 1000.0,
                )
            time.sleep(0.1)

        if not port_open:
            return StartupHealthResult(
                started=process is None or process.poll() is None,
                ready=False,
                port=port,
                failure_reason=f"Timeout waiting for port {port} to open within {timeout_seconds}s.",
                latency_ms=(time.perf_counter() - t_start) * 1000.0,
            )

        # 3. Probe HTTP endpoint
        status_code = None
        http_ok = False
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
            conn.request("GET", path if path.startswith("/") else f"/{path}")
            resp = conn.getresponse()
            status_code = resp.status
            # Any HTTP response code (including 200, 301, 404, etc.) proves the HTTP server is serving!
            if status_code < 500:
                http_ok = True
            conn.close()
        except Exception as e:
            return StartupHealthResult(
                started=True,
                ready=False,
                port=port,
                failure_reason=f"Socket open but HTTP probe failed: {e}",
                latency_ms=(time.perf_counter() - t_start) * 1000.0,
            )

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        return StartupHealthResult(
            started=True,
            ready=http_ok,
            port=port,
            status_code=status_code,
            latency_ms=latency_ms,
            preview_url=f"http://127.0.0.1:{port}{path}",
            failure_reason=None if http_ok else f"Server returned 5xx status code {status_code}.",
        )

    def _is_socket_open(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            return False
