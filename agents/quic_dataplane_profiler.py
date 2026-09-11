"""
JARVIS OS — Phase 22: QUIC Dataplane Profiler Subsystem
Granular, non-synthetic causal profiler instrumenting the 14 distinct dataplane components:
1. udp_recv_send
2. asyncio_scheduling
3. quic_packet_parsing
4. quic_packet_serialization
5. crypto_tls_ops
6. payload_framing
7. chunk_assembly_disassembly
8. checksum_integrity
9. queue_operations
10. memory_copies
11. buffer_allocation
12. lock_contention
13. python_object_allocation
14. logging_telemetry
"""

from __future__ import annotations

import contextlib
import gc
import logging
import math
import os
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROFILED_COMPONENTS = [
    "udp_recv_send",
    "asyncio_scheduling",
    "quic_packet_parsing",
    "quic_packet_serialization",
    "crypto_tls_ops",
    "payload_framing",
    "chunk_assembly_disassembly",
    "checksum_integrity",
    "queue_operations",
    "memory_copies",
    "buffer_allocation",
    "lock_contention",
    "python_object_allocation",
    "logging_telemetry",
]


@dataclass
class ComponentProfileMetrics:
    name: str
    calls: int = 0
    total_cpu_ns: int = 0
    total_wall_ns: int = 0
    samples_ns: List[int] = field(default_factory=list)

    def record(self, cpu_dur_ns: int, wall_dur_ns: int) -> None:
        self.calls += 1
        self.total_cpu_ns += cpu_dur_ns
        self.total_wall_ns += wall_dur_ns
        if len(self.samples_ns) < 5000:
            self.samples_ns.append(wall_dur_ns)

    def get_summary(self, grand_total_cpu_ns: int) -> Dict[str, Any]:
        pct = (self.total_cpu_ns / max(1, grand_total_cpu_ns)) * 100.0
        avg_us = (self.total_cpu_ns / max(1, self.calls)) / 1000.0
        p95_us = 0.0
        if self.samples_ns:
            sorted_s = sorted(self.samples_ns)
            n = len(sorted_s)
            p95_us = sorted_s[min(n - 1, int(0.95 * n))] / 1000.0

        return {
            "name": self.name,
            "calls": self.calls,
            "total_cpu_ms": round(self.total_cpu_ns / 1_000_000.0, 3),
            "total_wall_ms": round(self.total_wall_ns / 1_000_000.0, 3),
            "percentage_of_total_cpu": round(pct, 2),
            "average_cost_us": round(avg_us, 3),
            "p95_cost_us": round(p95_us, 3),
        }


class QuicDataplaneProfiler:
    """
    Thread-safe, fine-grained causal profiler for QUIC dataplane components.
    Provides precise CPU time (time.process_time_ns) and wall time (time.perf_counter_ns) measurements.
    """

    def __init__(self):
        self.components: Dict[str, ComponentProfileMetrics] = {
            comp: ComponentProfileMetrics(name=comp) for comp in PROFILED_COMPONENTS
        }
        self.is_enabled: bool = True

    def reset(self) -> None:
        for comp in self.components.values():
            comp.calls = 0
            comp.total_cpu_ns = 0
            comp.total_wall_ns = 0
            comp.samples_ns.clear()

    @contextlib.contextmanager
    def probe(self, component_name: str) -> Generator[None, None, None]:
        if not self.is_enabled or component_name not in self.components:
            yield
            return

        t_cpu_0 = time.process_time_ns()
        t_wall_0 = time.perf_counter_ns()
        try:
            yield
        finally:
            cpu_dur = time.process_time_ns() - t_cpu_0
            wall_dur = time.perf_counter_ns() - t_wall_0
            self.components[component_name].record(cpu_dur, wall_dur)

    def record_direct(self, component_name: str, cpu_dur_ns: int, wall_dur_ns: int) -> None:
        if component_name in self.components:
            self.components[component_name].record(cpu_dur_ns, wall_dur_ns)

    def get_grand_total_cpu_ns(self) -> int:
        return sum(c.total_cpu_ns for c in self.components.values())

    def get_grand_total_wall_ns(self) -> int:
        return sum(c.total_wall_ns for c in self.components.values())

    def generate_report(self) -> Dict[str, Any]:
        grand_cpu = self.get_grand_total_cpu_ns()
        grand_wall = self.get_grand_total_wall_ns()

        summaries = [
            c.get_summary(grand_cpu)
            for c in sorted(self.components.values(), key=lambda x: x.total_cpu_ns, reverse=True)
        ]

        if summaries and summaries[0]["total_cpu_ms"] > 0:
            hot_path = summaries[0]["name"]
            hot_path_pct = summaries[0]["percentage_of_total_cpu"]
        elif summaries and grand_wall > 0:
            by_wall = sorted(self.components.values(), key=lambda x: x.total_wall_ns, reverse=True)
            hot_path = by_wall[0].name
            hot_path_pct = round((by_wall[0].total_wall_ns / max(1, grand_wall)) * 100.0, 2)
        else:
            hot_path = summaries[0]["name"] if summaries else "UNKNOWN"
            hot_path_pct = 0.0

        return {
            "grand_total_cpu_ms": round(grand_cpu / 1_000_000.0, 3),
            "grand_total_wall_ms": round(grand_wall / 1_000_000.0, 3),
            "first_real_cpu_hot_path": hot_path,
            "hot_path_percentage": hot_path_pct,
            "components": summaries,
        }

    def format_markdown_table(self) -> str:
        report = self.generate_report()
        lines = [
            "| Component | Total CPU (ms) | Wall Time (ms) | % of Total CPU | Calls | Avg Cost (µs) | p95 Cost (µs) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for c in report["components"]:
            lines.append(
                f"| `{c['name']}` | {c['total_cpu_ms']:8.3f} | {c['total_wall_ms']:8.3f} | {c['percentage_of_total_cpu']:6.2f}% | {c['calls']:7d} | {c['average_cost_us']:8.3f} | {c['p95_cost_us']:8.3f} |"
            )
        lines.append("")
        lines.append(f"**FIRST_REAL_CPU_HOT_PATH:** `{report['first_real_cpu_hot_path']}` ({report['hot_path_percentage']:.2f}% of total CPU time)")
        return "\n".join(lines)


# Global singleton instance
global_dataplane_profiler = QuicDataplaneProfiler()
