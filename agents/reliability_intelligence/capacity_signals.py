"""
Phase 72 — Capacity Signals and Resource Pressure Monitoring
Detects CPU pressure, memory growth, restart growth, and request queue saturation.
Never assumes autoscaling or synthetic elastic resources when physical infrastructure is absent.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    CapacitySignal,
    CapacityStatus,
    ReliabilityWindow,
    TrendSignal,
    TrendStatus,
)


class CapacityMonitor:
    """Evaluates saturation and trajectory of system resources."""

    def __init__(
        self,
        cpu_pressure_threshold: float = 75.0,
        cpu_risk_threshold: float = 90.0,
        memory_pressure_threshold: float = 75.0,
        memory_risk_threshold: float = 88.0,
        restart_risk_count: int = 3,
    ):
        self.cpu_pressure = cpu_pressure_threshold
        self.cpu_risk = cpu_risk_threshold
        self.mem_pressure = memory_pressure_threshold
        self.mem_risk = memory_risk_threshold
        self.restart_risk = restart_risk_count

    def evaluate(
        self,
        window: ReliabilityWindow,
        trend: Optional[TrendSignal] = None,
    ) -> CapacitySignal:
        evidence_id = f"ev_cap_{uuid.uuid4().hex[:8]}"
        now = time.time()
        service = window.service
        metric = window.metric.lower()
        obs = window.observations

        if not obs:
            return CapacitySignal(
                signal_id=f"cap_{uuid.uuid4().hex[:6]}",
                service=service,
                resource_type=metric,
                status=CapacityStatus.UNKNOWN,
                utilization=0.0,
                rate_of_change=0.0,
                evidence_id=evidence_id,
                timestamp=now,
            )

        latest_val = obs[-1].value
        roc = trend.slope if trend else 0.0

        # 1. CPU
        if metric in ("cpu", "cpu_utilization", "cpu_percent"):
            if latest_val >= self.cpu_risk or (latest_val >= self.cpu_pressure and trend and trend.status == TrendStatus.DEGRADING):
                status = CapacityStatus.RISK
            elif latest_val >= self.cpu_pressure:
                status = CapacityStatus.PRESSURE
            else:
                status = CapacityStatus.SAFE

        # 2. Memory
        elif metric in ("memory", "memory_mb", "memory_percent"):
            if latest_val >= self.mem_risk or (latest_val >= self.mem_pressure and trend and trend.status == TrendStatus.DEGRADING):
                status = CapacityStatus.RISK
            elif latest_val >= self.mem_pressure:
                status = CapacityStatus.PRESSURE
            else:
                status = CapacityStatus.SAFE

        # 3. Restarts
        elif metric in ("restarts", "restart_count"):
            if latest_val >= self.restart_risk:
                status = CapacityStatus.RISK
            elif latest_val >= 1:
                status = CapacityStatus.PRESSURE
            else:
                status = CapacityStatus.SAFE

        # 4. Queue / Requests / Latency
        elif metric in ("queue_depth", "request_volume", "latency"):
            if trend and trend.status == TrendStatus.DEGRADING and trend.confidence > 0.7:
                status = CapacityStatus.RISK
            elif trend and trend.status == TrendStatus.DEGRADING:
                status = CapacityStatus.PRESSURE
            else:
                status = CapacityStatus.SAFE

        else:
            status = CapacityStatus.SAFE

        return CapacitySignal(
            signal_id=f"cap_{uuid.uuid4().hex[:6]}",
            service=service,
            resource_type=metric,
            status=status,
            utilization=round(latest_val, 2),
            rate_of_change=round(roc, 4),
            evidence_id=evidence_id,
            timestamp=now,
        )
