from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from typing import Any

from backend.events.bus import Event, get_event_bus
from workspace.infra_monitor.anomaly_detector import AnomalyAlert, MetricSample, SlidingWindowAnomalyDetector


class InfraMonitoringServer:
    """Enterprise Infrastructure Monitoring & Real-Time Alert Server."""

    def __init__(self, window_size: int = 30):
        self.detector = SlidingWindowAnomalyDetector(window_size=window_size)
        self.bus = get_event_bus()
        self.incidents_history: list[dict[str, Any]] = []
        self.active_nodes: set[str] = set()

    async def ingest_metric(self, node_id: str, metric_name: str, value: float) -> dict[str, Any]:
        """Ingests a metric sample, triggers anomaly detector, and publishes Pub/Sub events if alert raised."""
        sample = MetricSample(
            node_id=node_id,
            metric_name=metric_name,
            value=value,
            timestamp=time.time(),
        )
        self.active_nodes.add(node_id)

        alert = self.detector.process_sample(sample)
        result: dict[str, Any] = {
            "status": "ingested",
            "node_id": node_id,
            "metric_name": metric_name,
            "value": value,
            "alert": None,
        }

        if alert is not None:
            alert_dict = asdict(alert)
            self.incidents_history.append(alert_dict)
            result["alert"] = alert_dict

            # Publish event to AsyncEventBus Pub/Sub Control Plane
            await self.bus.publish(
                "infra.anomaly_detected",
                alert_dict,
            )

        return result

    def get_health_summary(self) -> dict[str, Any]:
        """Returns health summary of infrastructure nodes and recent incidents."""
        return {
            "active_nodes_count": len(self.active_nodes),
            "total_incidents_logged": len(self.incidents_history),
            "recent_incidents": self.incidents_history[-10:],
        }


__all__ = ["InfraMonitoringServer"]
