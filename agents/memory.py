import os
import re
import asyncio
import json
import subprocess
import httpx
import base64
import io
import yaml
import datetime
from pathlib import Path
from PIL import ImageGrab
from sandbox import SANDBOX_DIR

try:
    from crewai import Agent, Task, Crew, LLM
    from crewai.tools import tool
except ImportError:
    pass

import agents.globals as glb
import agents.utils as utils
import agents.memory as memory
import agents.tools as ag_tools
import agents.obsidian_tools as obs_tools
import agents.swarm as swarm
import server


# --- save_session_memory ---
def save_session_memory(session_id: int, goal: str, files_created: list, key_decisions: list = None):
    """ECC Memory Hook — persists session summary to disk."""
    try:
        memory = {}
        if glb._MEMORY_PATH.exists():
            memory = json.loads(glb._MEMORY_PATH.read_text(encoding="utf-8"))
        memory[str(session_id)] = {
            "timestamp": datetime.datetime.now().isoformat(),
            "goal": goal,
            "files_created": files_created,
            "key_decisions": key_decisions or []
        }
        # Keep last 10 sessions only (token budget)
        keys = sorted(memory.keys())[-10:]
        memory = {k: memory[k] for k in keys}
        glb._MEMORY_PATH.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[ECC Memory] Erro ao guardar sessão: {e}")


# --- load_session_context ---
def load_session_context() -> str:
    """ECC Memory Hook — loads the last 3 sessions as context."""
    try:
        if not glb._MEMORY_PATH.exists():
            return ""
        memory = json.loads(glb._MEMORY_PATH.read_text(encoding="utf-8"))
        if not memory:
            return ""
        last_sessions = list(memory.values())[-3:]
        lines = ["## Contexto de Sessões Anteriores"]
        for s in last_sessions:
            ts = s.get("timestamp", "")[:10]
            goal = s.get("goal", "N/A")
            files = ", ".join(s.get("files_created", [])) or "nenhum"
            lines.append(f"- [{ts}] **Objetivo:** {goal} | **Ficheiros:** {files}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[ECC Memory] Erro ao carregar sessão: {e}")
        return ""


# --- save_loop_metrics ---
def save_loop_metrics(success: bool, steps_used: int, duration_secs: float, goal: str):
    """Loop Engineering — tracks performance metrics per loop run."""
    try:
        metrics = {"runs": []}
        if glb._METRICS_PATH.exists():
            metrics = json.loads(glb._METRICS_PATH.read_text(encoding="utf-8"))
        metrics["runs"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "goal": goal[:80],
            "success": success,
            "steps_used": steps_used,
            "duration_secs": round(duration_secs, 1)
        })
        # Keep last 50 runs
        metrics["runs"] = metrics["runs"][-50:]
        # Compute aggregate stats
        runs = metrics["runs"]
        metrics["stats"] = {
            "total_runs": len(runs),
            "success_rate": round(sum(1 for r in runs if r["success"]) / len(runs) * 100, 1),
            "avg_loop_time_secs": round(sum(r["duration_secs"] for r in runs) / len(runs), 1),
            "avg_steps": round(sum(r["steps_used"] for r in runs) / len(runs), 1)
        }
        glb._METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        return metrics["stats"]
    except Exception as e:
        print(f"[Loop Metrics] Erro ao guardar métricas: {e}")
        return {}


# --- load_loop_metrics_summary ---
def load_loop_metrics_summary() -> str:
    """Returns a formatted string with loop performance stats."""
    try:
        if not glb._METRICS_PATH.exists():
            return ""
        metrics = json.loads(glb._METRICS_PATH.read_text(encoding="utf-8"))
        stats = metrics.get("stats", {})
        if not stats:
            return ""
        sr = stats.get("success_rate", 0)
        avg_t = stats.get("avg_loop_time_secs", 0)
        avg_s = stats.get("avg_steps", 0)
        total = stats.get("total_runs", 0)
        mins = int(avg_t // 60)
        secs = int(avg_t % 60)
        return f"📊 **Loop Metrics** ({total} runs) — Success Rate: **{sr}%** | Avg Time: **{mins}m {secs}s** | Avg Steps: **{avg_s}**"
    except Exception:
        return ""


# --- load_compounding_memory_rules ---
def load_compounding_memory_rules() -> str:
    """Loads compounding memory rules from SQLite database."""
    try:
        import database
        rules = database.get_compounding_rules()
        if not rules:
            return ""
        lines = ["## Compounding Memory (Lições Aprendidas de Sessões Anteriores)"]
        for r in rules:
            lines.append(f"- **Regra ({r['rule_key']}):** {r['description']}\n  *Correção:* {r['correction']}")
        return "\n".join(lines)
    except Exception as e:
        print(f"Error loading compounding rules: {e}")
        return ""


# --- load_architecture_memory_summary ---
def load_architecture_memory_summary() -> str:
    """Loads architecture memory constraints from SQLite database."""
    try:
        import database
        arch = database.get_architecture_memory()
        if not arch:
            return ""
        lines = ["## Architecture Memory (Propósito e Restrições de Módulos)"]
        for a in arch:
            lines.append(
                f"- **Módulo ({a['module']}):** {a['purpose']}\n"
                f"  *Dependências:* {a['dependencies'] or 'Nenhum'}\n"
                f"  *Restrições/Constraints:* {a['constraints'] or 'Nenhum'}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"Error loading architecture memory: {e}")
        return ""


# --- load_engineering_decisions_summary ---
def load_engineering_decisions_summary() -> str:
    """Loads engineering decisions from SQLite database."""
    try:
        import database
        decisions = database.get_engineering_decisions()
        if not decisions:
            return ""
        lines = ["## Decision Memory (Registo de Decisões de Engenharia)"]
        for d in decisions:
            lines.append(
                f"- **Decisão:** {d['decision']}\n"
                f"  *Razão:* {d['reason']}\n"
                f"  *Impacto:* {d['impact'] or 'Nenhum'}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"Error loading engineering decisions: {e}")
        return ""



# --- HarnessContext ---
class HarnessContext:
    @staticmethod
    def get_current_sandbox_state() -> str:
        """Compiles the contents of MEMORY.md as agent context."""
        from sandbox import SANDBOX_DIR
        p = os.path.join(SANDBOX_DIR, "MEMORY.md")
        if not os.path.exists(p):
            p = os.path.join(glb.BASE_DIR, "MEMORY.md")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as file_obj:
                    content = file_obj.read()
                return f"\n\n## Memória de Progresso (MEMORY.md)\n```markdown\n{content}\n```"
            except Exception:
                pass
        return ""

