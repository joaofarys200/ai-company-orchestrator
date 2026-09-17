from __future__ import annotations

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

import time
from typing import Any, Dict, List, Optional


class SymbolMetricsCollector:
    """Collects telemetry, precision gains, memory footprints, and benchmark statistics."""

    def __init__(self) -> None:
        if _HAS_PSUTIL:
            try:
                self.process = psutil.Process(os.getpid())
            except Exception:
                self.process = None
        else:
            self.process = None
        self.measurements: List[Dict[str, Any]] = []

    def measure_memory_mb(self) -> float:
        """Return current RSS memory usage in megabytes."""
        if self.process:
            try:
                return round(self.process.memory_info().rss / (1024 * 1024), 2)
            except Exception:
                pass
        return 0.0

    def record_precision_gain(
        self,
        file_scc_size: int,
        symbol_scc_size: int,
        file_impact: int,
        symbol_impact: int,
        context: str = "",
    ) -> Dict[str, Any]:
        """Compute and log precision gain and overapproximation reduction."""
        precision_gain = round(1.0 - (symbol_impact / file_impact), 4) if file_impact > 0 else 0.0
        overapprox_reduction = round((file_scc_size - symbol_scc_size) / file_scc_size, 4) if file_scc_size > 0 else 0.0

        record = {
            "timestamp": time.time(),
            "context": context,
            "file_scc_size": file_scc_size,
            "symbol_scc_size": symbol_scc_size,
            "file_impact": file_impact,
            "symbol_impact": symbol_impact,
            "precision_gain": max(precision_gain, 0.0),
            "overapproximation_reduction": max(overapprox_reduction, 0.0),
            "ram_mb": self.measure_memory_mb(),
        }
        self.measurements.append(record)
        return record

    def summarize(self) -> Dict[str, Any]:
        """Summarize telemetry across all measurements."""
        if not self.measurements:
            return {"count": 0, "avg_precision_gain": 0.0, "avg_overapprox_reduction": 0.0}

        avg_gain = sum(m["precision_gain"] for m in self.measurements) / len(self.measurements)
        avg_red = sum(m["overapproximation_reduction"] for m in self.measurements) / len(self.measurements)

        return {
            "measurement_count": len(self.measurements),
            "avg_precision_gain": round(avg_gain, 4),
            "avg_overapproximation_reduction": round(avg_red, 4),
            "peak_ram_mb": max(m["ram_mb"] for m in self.measurements),
        }
