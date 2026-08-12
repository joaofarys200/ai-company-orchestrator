import sys, os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import unittest
from backend.events.bus import Event, get_event_bus
from workspace.infra_monitor.anomaly_detector import MetricSample, SlidingWindowAnomalyDetector
from workspace.infra_monitor.server import InfraMonitoringServer


class TestInfraMonitor(unittest.IsolatedAsyncioTestCase):
    def test_anomaly_detector_z_score_trigger(self):
        detector = SlidingWindowAnomalyDetector(window_size=10, z_threshold_warning=2.0, z_threshold_critical=3.0)

        # Feed 10 baseline samples around 50.0 CPU usage
        for i in range(10):
            sample = MetricSample(node_id="node_1", metric_name="cpu_usage", value=50.0 + (i % 2), timestamp=1000 + i)
            alert = detector.process_sample(sample)
            self.assertIsNone(alert)

        # Inject massive CPU spike (99.0%)
        spike_sample = MetricSample(node_id="node_1", metric_name="cpu_usage", value=99.0, timestamp=1011)
        alert = detector.process_sample(spike_sample)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.node_id, "node_1")
        self.assertEqual(alert.metric_name, "cpu_usage")
        self.assertIn(alert.severity, ("WARNING", "CRITICAL"))
        self.assertGreater(alert.z_score, 2.0)

    async def test_infra_server_pub_sub_broadcasting(self):
        server = InfraMonitoringServer(window_size=10)
        bus = get_event_bus()

        broadcasted_alerts: list[Event] = []

        async def alert_handler(evt: Event):
            broadcasted_alerts.append(evt)

        await bus.subscribe("infra.anomaly_detected", alert_handler)

        # Feed 10 baseline metrics
        for i in range(10):
            await server.ingest_metric("node_2", "memory_usage", 40.0)

        # Spike memory to 95.0%
        result = await server.ingest_metric("node_2", "memory_usage", 95.0)

        self.assertIsNotNone(result["alert"])
        self.assertEqual(len(broadcasted_alerts), 1)
        self.assertEqual(broadcasted_alerts[0].data["node_id"], "node_2")
        self.assertEqual(broadcasted_alerts[0].data["severity"], "CRITICAL")

        summary = server.get_health_summary()
        self.assertEqual(summary["active_nodes_count"], 1)
        self.assertEqual(summary["total_incidents_logged"], 1)


if __name__ == "__main__":
    unittest.main()
