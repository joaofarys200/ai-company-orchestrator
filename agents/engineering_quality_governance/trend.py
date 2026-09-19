"""
JARVIS OS — Phase 68: Quality Trend Engine
Analyzes historical sequences of QualitySnapshots: T1, T2, ..., Tn.
Detects:
- IMPROVING
- STABLE
- DEGRADING
- VOLATILE
- INSUFFICIENT_DATA

Invariant:
Never make long-term forecasts without sufficient historical data (minimum 5 chronological snapshots).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import QualitySnapshot, QualityTrendDirection


class QualityTrendEngine:
    """
    Computes quality trends across chronological snapshots without over-extrapolating.
    """

    def __init__(self) -> None:
        pass

    def analyze_trend(
        self,
        snapshots: List[QualitySnapshot],
        dimension_name: Optional[str] = None,
    ) -> Tuple[QualityTrendDirection, Dict[str, Any]]:
        """
        Analyzes trend across snapshots.
        If snapshots < 2, returns INSUFFICIENT_DATA.
        If snapshots < 5, forecasts are explicitly flagged as unreliable.
        """
        if len(snapshots) < 2:
            return QualityTrendDirection.INSUFFICIENT_DATA, {
                "snapshot_count": len(snapshots),
                "reason": "At least 2 chronological snapshots are required to infer direction",
                "can_forecast_long_term": False,
            }

        # Extract metric trajectories across snapshots
        # Use healthy dimension counts or specific metric if requested
        trajectory = []
        for s in snapshots:
            if dimension_name:
                eval_dim = s.dimensions.get(dimension_name)
                val = 1.0 if eval_dim and eval_dim.status.value == "HEALTHY" else 0.0
            else:
                healthy_count = sum(1 for d in s.dimensions.values() if d.status.value == "HEALTHY")
                val = healthy_count / max(len(s.dimensions), 1)
            trajectory.append(val)

        # Check differences between consecutive points
        diffs = [trajectory[i] - trajectory[i - 1] for i in range(1, len(trajectory))]
        positive_moves = sum(1 for d in diffs if d > 0.05)
        negative_moves = sum(1 for d in diffs if d < -0.05)
        neutral_moves = sum(1 for d in diffs if abs(d) <= 0.05)

        can_forecast = len(snapshots) >= 5

        # Check volatility: alternating positive and negative moves
        is_volatile = positive_moves >= 2 and negative_moves >= 2

        if is_volatile:
            direction = QualityTrendDirection.VOLATILE
        elif negative_moves > positive_moves and negative_moves >= len(diffs) // 2:
            direction = QualityTrendDirection.DEGRADING
        elif positive_moves > negative_moves and positive_moves >= len(diffs) // 2:
            direction = QualityTrendDirection.IMPROVING
        else:
            direction = QualityTrendDirection.STABLE

        details = {
            "snapshot_count": len(snapshots),
            "trajectory": trajectory,
            "positive_moves": positive_moves,
            "negative_moves": negative_moves,
            "neutral_moves": neutral_moves,
            "can_forecast_long_term": can_forecast,
            "forecast_note": "Reliable long-term forecast available" if can_forecast else "Forecast constrained: < 5 snapshots",
        }

        return direction, details
