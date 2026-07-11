from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agents.orchestrator.task_state import TaskState

@dataclass
class OrchestrationTrace:
    prompt: str
    model: str
    intent: str = "TASK"
    enabled: bool = False
    started_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    plan: dict | None = None
    events: list[dict] = field(default_factory=list)
    stop_reason: str = ""
    success: bool = False
    output_path: str = ""

    def record(self, event: str, **details) -> None:
        if not self.enabled:
            return
        self.events.append({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": event,
            **details,
        })

    def save(self, state: TaskState | None = None) -> str:
        if not self.enabled:
            return ""
        log_dir = Path("logs") / "orchestration_runs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = log_dir / f"{stamp}.json"
        payload = asdict(self)
        if state is not None:
            payload["final_task_state"] = asdict(state)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.output_path = str(path)
        return self.output_path
