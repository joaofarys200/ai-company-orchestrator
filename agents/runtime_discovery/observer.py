"""
JARVIS OS — Phase 45: Runtime Contract Observer
Passively monitors and ingests runtime HTTP traffic from Browser QA, backend middleware,
test runners, and proxies, with automatic credential redaction and route normalization.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agents.runtime_discovery.models import (
    ObservationSourceType,
    RuntimeObservation,
)
from agents.runtime_discovery.security import RuntimeDiscoverySecurity


class RuntimeContractObserver:
    """Passively collects, redacts, parameterizes, and indexes runtime network observations."""

    # Dynamic route parameter pattern matchers (integer ID, UUID, hex hash)
    UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
    INT_ID_REGEX = re.compile(r"^\d+$")
    HEX_ID_REGEX = re.compile(r"^[0-9a-f]{24,32}$", re.IGNORECASE)

    def __init__(self) -> None:
        # Index: (METHOD, PARAMETERIZED_ROUTE) -> list[RuntimeObservation]
        self._observations_by_route: dict[tuple[str, str], list[RuntimeObservation]] = {}
        self._all_observations: list[RuntimeObservation] = []
        self._redacted_fields_count: int = 0
        self._security_alerts_count: int = 0

    @property
    def total_observations(self) -> int:
        return len(self._all_observations)

    @property
    def redacted_fields_count(self) -> int:
        return self._redacted_fields_count

    @property
    def security_alerts_count(self) -> int:
        return self._security_alerts_count

    @classmethod
    def parameterize_route(cls, raw_path: str) -> str:
        """Normalizes dynamic IDs in route path to parameterized templates.
        
        Examples:
        /api/v1/users/42 -> /api/v1/users/{id}
        /orders/550e8400-e29b-41d4-a716-446655440000/items -> /orders/{id}/items
        """
        # Strip query params from path if present
        clean_path = raw_path.split("?")[0].strip()
        segments = clean_path.split("/")
        parameterized_segments = []

        for seg in segments:
            if not seg:
                parameterized_segments.append(seg)
                continue
            if cls.INT_ID_REGEX.match(seg) or cls.UUID_REGEX.match(seg) or cls.HEX_ID_REGEX.match(seg):
                parameterized_segments.append("{id}")
            else:
                parameterized_segments.append(seg)

        return "/".join(parameterized_segments)

    def observe(
        self,
        method: str,
        route: str,
        status_code: int,
        request_headers: Optional[dict[str, str]] = None,
        request_payload: Any = None,
        response_payload: Any = None,
        content_type: str = "application/json",
        source_type: ObservationSourceType = ObservationSourceType.BROWSER_NETWORK,
        response_time_ms: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RuntimeObservation:
        """Ingests, redacts, parameterizes, and indexes an observed runtime exchange."""
        norm_method = method.upper().strip()
        param_route = self.parameterize_route(route)

        # 1. Redact headers
        clean_headers, hdr_redactions = RuntimeDiscoverySecurity.redact_headers(request_headers or {})

        # 2. Redact request payload
        clean_req, req_redactions, req_alerts = RuntimeDiscoverySecurity.redact_payload(request_payload, "request")

        # 3. Redact response payload
        clean_res, res_redactions, res_alerts = RuntimeDiscoverySecurity.redact_payload(response_payload, "response")

        self._redacted_fields_count += (hdr_redactions + req_redactions + res_redactions)
        self._security_alerts_count += (len(req_alerts) + len(res_alerts))

        obs = RuntimeObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:8]}",
            source_type=source_type,
            method=norm_method,
            route=param_route,
            status_code=status_code,
            request_headers=clean_headers,
            request_payload=clean_req,
            response_payload=clean_res,
            content_type=content_type,
            response_time_ms=response_time_ms,
            timestamp=time.time(),
            metadata={
                **(metadata or {}),
                "original_route": route,
                "redactions_applied": hdr_redactions + req_redactions + res_redactions,
                "security_alerts": req_alerts + res_alerts,
            },
        )

        key = (norm_method, param_route)
        if key not in self._observations_by_route:
            self._observations_by_route[key] = []
        self._observations_by_route[key].append(obs)
        self._all_observations.append(obs)

        return obs

    def observe_interaction(
        self,
        source_type: ObservationSourceType = ObservationSourceType.BROWSER_NETWORK,
        method: str = "GET",
        route: str = "/",
        status_code: int = 200,
        request_headers: Optional[dict[str, str]] = None,
        response_headers: Optional[dict[str, str]] = None,
        query_params: Optional[dict[str, Any]] = None,
        request_body: Any = None,
        response_body: Any = None,
        duration_ms: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RuntimeObservation:
        """Alias for observe matching test signatures."""
        merged_meta = dict(metadata or {})
        if query_params:
            merged_meta["query_params"] = query_params
        if response_headers:
            merged_meta["response_headers"] = response_headers

        return self.observe(
            method=method,
            route=route,
            status_code=status_code,
            request_headers=request_headers,
            request_payload=request_body,
            response_payload=response_body,
            source_type=source_type,
            response_time_ms=duration_ms,
            metadata=merged_meta,
        )

    def get_observations(self, method: Optional[str] = None, route: Optional[str] = None) -> list[RuntimeObservation]:
        if method is None and route is None:
            return list(self._all_observations)
        norm_method = (method or "GET").upper().strip()
        param_route = self.parameterize_route(route or "/")
        return list(self._observations_by_route.get((norm_method, param_route), []))

    def get_observations_for_endpoint(self, method: str, route: str) -> list[RuntimeObservation]:
        return self.get_observations(method, route)

    def list_observed_routes(self) -> list[tuple[str, str, int]]:
        """Returns list of (method, route, sample_count)."""
        return [(m, r, len(samples)) for (m, r), samples in self._observations_by_route.items()]

    def clear(self) -> None:
        self._observations_by_route.clear()
        self._all_observations.clear()
        self._redacted_fields_count = 0
        self._security_alerts_count = 0

