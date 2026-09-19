"""
Phase 71 — Deterministic Healthcheck Engine
Tri-state health checking with explicit evidence collection. UNKNOWN is never converted to HEALTHY.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from .models import HealthCheckResult, HealthStatus


class HealthCheckEngine:
    """
    Executes and tracks deterministic multi-domain health checks.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._registered_checks: Dict[str, Callable[[], tuple[HealthStatus, str]]] = {}
        self._history: List[HealthCheckResult] = []

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], tuple[HealthStatus, str]],
    ) -> None:
        """Registers a named health check function returning (HealthStatus, details)."""
        self._registered_checks[name] = check_fn

    def execute_check(self, name: str) -> HealthCheckResult:
        """Executes a single registered check and records the outcome."""
        if name not in self._registered_checks:
            res = HealthCheckResult(
                check_name=name,
                service_id=self.service_id,
                status=HealthStatus.UNKNOWN,
                details=f"Check '{name}' is not registered.",
                duration_ms=0.0,
            )
            self._history.append(res)
            return res

        fn = self._registered_checks[name]
        start_t = time.perf_counter()
        try:
            status, details = fn()
        except Exception as exc:
            status = HealthStatus.UNHEALTHY
            details = f"Check raised exception: {type(exc).__name__}: {str(exc)}"
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        # Enforce invariant: UNKNOWN must never be promoted to HEALTHY
        if status == HealthStatus.UNKNOWN and "healthy" in details.lower():
            details += " [Note: status retained as UNKNOWN despite details text]"

        res = HealthCheckResult(
            check_name=name,
            service_id=self.service_id,
            status=status,
            details=details,
            duration_ms=round(duration_ms, 3),
        )
        self._history.append(res)
        return res

    def execute_all(self) -> List[HealthCheckResult]:
        """Executes all registered health checks in order."""
        return [self.execute_check(name) for name in self._registered_checks]

    def aggregate_status(self, results: Optional[List[HealthCheckResult]] = None) -> HealthStatus:
        """
        Aggregates multiple health check results:
        - If ANY is UNHEALTHY -> UNHEALTHY
        - If ANY is UNKNOWN (and none UNHEALTHY) -> UNKNOWN (never promote UNKNOWN to HEALTHY)
        - Only if ALL are HEALTHY -> HEALTHY
        - If empty -> UNKNOWN
        """
        if results is None:
            results = self.execute_all()

        if not results:
            return HealthStatus.UNKNOWN

        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY

        if any(r.status == HealthStatus.UNKNOWN for r in results):
            return HealthStatus.UNKNOWN

        return HealthStatus.HEALTHY

    def get_history(self) -> List[HealthCheckResult]:
        return list(self._history)


def create_standard_healthcheck_suite(
    service_id: str,
    process_checker: Optional[Callable[[], bool]] = None,
    http_checker: Optional[Callable[[], tuple[bool, int, str]]] = None,
    schema_checker: Optional[Callable[[], bool]] = None,
    dependency_checker: Optional[Callable[[], Dict[str, bool]]] = None,
    websocket_checker: Optional[Callable[[], bool]] = None,
    db_checker: Optional[Callable[[], bool]] = None,
) -> HealthCheckEngine:
    """Factory creating a standard 8-point production health check suite."""
    engine = HealthCheckEngine(service_id=service_id)

    # 1. Process alive
    def check_process() -> tuple[HealthStatus, str]:
        if process_checker is None:
            return HealthStatus.UNKNOWN, "Process checker not configured."
        alive = process_checker()
        return (HealthStatus.HEALTHY, "Process running normally.") if alive else (HealthStatus.UNHEALTHY, "Process not running.")

    # 2. HTTP reachable
    def check_http() -> tuple[HealthStatus, str]:
        if http_checker is None:
            return HealthStatus.UNKNOWN, "HTTP checker not configured."
        ok, status_code, msg = http_checker()
        if ok and 200 <= status_code < 400:
            return HealthStatus.HEALTHY, f"HTTP {status_code}: {msg}"
        return HealthStatus.UNHEALTHY, f"HTTP error {status_code}: {msg}"

    # 3. Endpoint response schema
    def check_schema() -> tuple[HealthStatus, str]:
        if schema_checker is None:
            return HealthStatus.UNKNOWN, "Response schema checker not configured."
        valid = schema_checker()
        return (HealthStatus.HEALTHY, "Endpoint payload conforms to contract.") if valid else (HealthStatus.UNHEALTHY, "Response schema violation.")

    # 4. Dependency availability
    def check_deps() -> tuple[HealthStatus, str]:
        if dependency_checker is None:
            return HealthStatus.UNKNOWN, "Dependency checker not configured."
        deps = dependency_checker()
        failed = [d for d, s in deps.items() if not s]
        if not failed:
            return HealthStatus.HEALTHY, f"All {len(deps)} dependencies available."
        return HealthStatus.UNHEALTHY, f"Dependencies failed: {', '.join(failed)}"

    # 5. WebSocket availability
    def check_ws() -> tuple[HealthStatus, str]:
        if websocket_checker is None:
            return HealthStatus.UNKNOWN, "WebSocket checker not configured."
        active = websocket_checker()
        return (HealthStatus.HEALTHY, "WebSocket channel responsive.") if active else (HealthStatus.UNHEALTHY, "WebSocket channel down.")

    # 6. Database connectivity
    def check_db() -> tuple[HealthStatus, str]:
        if db_checker is None:
            return HealthStatus.UNKNOWN, "Database checker not configured."
        connected = db_checker()
        return (HealthStatus.HEALTHY, "Database connection active.") if connected else (HealthStatus.UNHEALTHY, "Database connection failed.")

    engine.register_check("process_alive", check_process)
    engine.register_check("http_reachable", check_http)
    engine.register_check("response_schema", check_schema)
    engine.register_check("dependency_availability", check_deps)
    engine.register_check("websocket_availability", check_ws)
    engine.register_check("database_connectivity", check_db)

    return engine
