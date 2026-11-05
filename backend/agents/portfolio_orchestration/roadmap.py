"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: roadmap.py
Versioned engineering roadmap generation, milestone checkpointing, and decision rationale.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional

from .models import (
    EngineeringInitiative,
    ExecutionSchedule,
    MilestoneCheckpoint,
    PortfolioRoadmap,
)


class RoadmapGenerator:
    """
    Generates structured, versioned engineering roadmaps from evaluated and scheduled portfolios.
    """

    def generate_roadmap(
        self,
        portfolio_id: str,
        version: str,
        selected_initiatives: List[str],
        rejected_initiatives: List[str],
        schedule: ExecutionSchedule,
        initiatives: Dict[str, EngineeringInitiative],
        rationale: str = "",
    ) -> PortfolioRoadmap:
        """
        Assemble a versioned PortfolioRoadmap complete with milestone checkpoints.
        """
        # Create checkpoints at the boundary of each execution wave
        milestones: List[MilestoneCheckpoint] = []
        for wave_idx in range(schedule.total_waves):
            wave_inits = [
                item.initiative_id
                for item in schedule.items
                if item.wave_index == wave_idx
            ]
            req_verifs = [f"verify_invariants_{init_id}" for init_id in wave_inits]
            milestones.append(
                MilestoneCheckpoint(
                    checkpoint_id=f"chk_wave_{wave_idx}_{uuid.uuid4().hex[:6]}",
                    wave_index=wave_idx,
                    required_verifications=req_verifs,
                    passed=False,
                )
            )

        if not rationale:
            rationale = (
                f"Roadmap {version} selected {len(selected_initiatives)} initiatives "
                f"across {schedule.total_waves} waves, deferring {len(rejected_initiatives)} candidates "
                f"to respect budget and resource constraints."
            )

        return PortfolioRoadmap(
            roadmap_id=f"rdm_{uuid.uuid4().hex[:8]}",
            version=version,
            portfolio_id=portfolio_id,
            selected_initiatives=selected_initiatives,
            rejected_initiatives=rejected_initiatives,
            schedule=schedule,
            milestones=milestones,
            created_at=time.time(),
            status="ACTIVE",
            rationale=rationale,
        )

    def render_markdown_summary(
        self,
        roadmap: PortfolioRoadmap,
        initiatives: Dict[str, EngineeringInitiative],
    ) -> str:
        """Render a readable engineering roadmap report."""
        lines = [
            f"# Engineering Portfolio Roadmap — {roadmap.version}",
            f"**Roadmap ID**: `{roadmap.roadmap_id}` | **Portfolio ID**: `{roadmap.portfolio_id}`",
            f"**Status**: `{roadmap.status}` | **Total Waves**: {roadmap.schedule.total_waves}",
            "",
            "## 1. Executive Summary & Rationale",
            roadmap.rationale,
            "",
            "## 2. Selected Initiatives",
            "| Initiative ID | Title | Type | Effort | Cost ($) | Expected Benefit | Confidence |",
            "|---|---|---|---|---|---|---|",
        ]
        for s_id in roadmap.selected_initiatives:
            init = initiatives.get(s_id)
            if init:
                lines.append(
                    f"| `{init.id}` | {init.title} | `{init.initiative_type.value}` | "
                    f"{init.effort_units:.1f} | ${init.budget_cost:.1f} | {init.expected_benefit:.1f} | "
                    f"{init.confidence:.2f} |"
                )

        lines.extend([
            "",
            "## 3. Rejected or Deferred Candidates",
            "| Initiative ID | Title | Reason |",
            "|---|---|---|",
        ])
        for r_id in roadmap.rejected_initiatives:
            init = initiatives.get(r_id)
            title = init.title if init else "Unknown"
            lines.append(f"| `{r_id}` | {title} | Exceeded budget, lower synergy ROI, or mutual exclusion |")

        lines.extend([
            "",
            "## 4. Wave-by-Wave Execution Schedule",
            f"**Critical Path**: {' -> '.join(f'`{c}`' for c in roadmap.schedule.critical_path) or 'None'}",
            "",
        ])

        for wave_idx in range(roadmap.schedule.total_waves):
            wave_items = [item for item in roadmap.schedule.items if item.wave_index == wave_idx]
            lines.append(f"### Wave {wave_idx + 1}")
            for it in wave_items:
                init = initiatives.get(it.initiative_id)
                title = init.title if init else it.initiative_id
                lines.append(
                    f"- **`{it.initiative_id}`** ({title}) | Assigned: `{it.assigned_agent}` | "
                    f"Duration: {it.estimated_duration:.1f}s | Resources: {it.claimed_resources}"
                )
            lines.append(f"- *Checkpoint*: Wave {wave_idx + 1} invariant verification required before next wave.\n")

        return "\n".join(lines)
