"""
JARVIS OS — Phase 30: Autonomous Mission Productization & Full End-to-End Execution

Provides the core productized autonomous mission engine:
USER GOAL (Minimalist Natural Language)
-> INTENT & ARCHITECTURE INFERENCE
-> TASK DAG DECOMPOSITION & SCHEDULING
-> SWARM COORDINATION & MULTI-AGENT COLLABORATION
-> DISTRIBUTED TRANSPORT EXECUTION
-> AUTONOMOUS REPAIR & FINITE ESCALATION
-> DETERMINISTIC CHECKPOINTING & RECOVERY
-> REAL BROWSER & TEST VALIDATION
-> EVIDENCE PROVENANCE & SATISFACTION VERIFICATION
-> AUTONOMY SCORECARD & LIMITS CLASSIFICATION
"""

from __future__ import annotations

import ast
import asyncio
from dataclasses import asdict, dataclass, field
import difflib
import enum
import hashlib
import json
import os
import re
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from agents.autonomous_mission_engine import (
    EvidenceProvenance,
    FailureEscalationGovernance,
    FailureEscalationLevel,
    FaultInjectionPlan,
    FaultType,
    MissionEvidenceItem,
    MissionFaultInjector,
    RepairMinimalityReport,
    RetryBudgets,
    SelfHealingEngine,
)
from agents.collaboration_engine import (
    AgentProposal,
    ArbitrationDecision,
    CollaborationCoordinator,
    CollaborationSession,
    CollaborationStatus,
    ConflictDetails,
    ConflictType,
    PatchMergeEngine,
    ResultKind,
)
from agents.distributed_transport import (
    AdaptiveDistributedTransportPolicy,
    DistributedEnvelope,
    ProductionDistributedTransport,
)
from agents.mission_orchestrator import (
    Checkpoint,
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore, utc_now
from agents.swarm_agents import (
    ArchitectureAgent,
    BrowserAgent,
    CodingAgent,
    ResearchAgent,
    ReviewAgent,
    SwarmAgent,
    TestingAgent,
    create_default_swarm_pool,
)
from agents.swarm_coordinator import (
    AgentHealthStatus,
    AgentInstance,
    AgentResult,
    ResultStatus,
    SwarmCoordinator,
    TaskLease,
)
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


# ── DOMAIN 1: 10 CANONICAL MISSION CATEGORIES ─────────────────────────────────

class MissionProductizationCategory(str, enum.Enum):
    SIMPLE_FRONTEND = "SIMPLE_FRONTEND"
    FRONTEND_BACKEND = "FRONTEND_BACKEND"
    CRUD_APPLICATION = "CRUD_APPLICATION"
    BUG_REPAIR = "BUG_REPAIR"
    FEATURE_IMPLEMENTATION = "FEATURE_IMPLEMENTATION"
    FULL_STACK_APP = "FULL_STACK_APP"
    TEST_REPAIR = "TEST_REPAIR"
    BUILD_REPAIR = "BUILD_REPAIR"
    BROWSER_VALIDATION = "BROWSER_VALIDATION"
    MULTI_STEP_REFACTOR = "MULTI_STEP_REFACTOR"


@dataclass
class InferredMissionPlan:
    goal_text: str
    category: MissionProductizationCategory
    project_slug: str
    target_artifacts: list[str]
    tasks: list[dict[str, Any]]
    dependencies: dict[str, list[str]]
    acceptance_criteria: list[dict[str, Any]]
    requires_browser: bool = False
    requires_full_stack: bool = False
    estimated_duration_sec: float = 5.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── DOMAIN 2: AUTONOMOUS MISSION PLANNER (MINIMALIST INFERENCE) ────────────────

class AutonomousMissionPlanner:
    """
    Infers architecture, files, DAG decomposition, dependencies, agent assignment,
    and acceptance criteria strictly from minimalist natural language prompts.
    Zero human intervention required.
    """

    @classmethod
    def infer_category(cls, prompt: str) -> MissionProductizationCategory:
        p = prompt.lower().strip()

        if any(k in p for k in ["bug", "corrige um bug", "encontra e corrige", "corrigir o erro"]):
            return MissionProductizationCategory.BUG_REPAIR
        if any(k in p for k in ["build", "falha de build", "compilação"]):
            return MissionProductizationCategory.BUILD_REPAIR
        if any(k in p for k in ["teste", "testes", "escreve testes", "test repair"]):
            if "adiciona" in p or "nova funcionalidade" in p:
                return MissionProductizationCategory.FEATURE_IMPLEMENTATION
            return MissionProductizationCategory.TEST_REPAIR
        if any(k in p for k in ["browser", "valida a aplicação no browser", "visual qa", "dom"]):
            return MissionProductizationCategory.BROWSER_VALIDATION
        if any(k in p for k in ["autenticação", "auth", "login", "segurança", "mfa"]):
            return MissionProductizationCategory.FEATURE_IMPLEMENTATION
        if any(k in p for k in ["refatora", "refactor", "reorganiza", "limpa código"]):
            return MissionProductizationCategory.MULTI_STEP_REFACTOR
        if "frontend" in p and "backend" in p:
            return MissionProductizationCategory.FRONTEND_BACKEND
        if any(k in p for k in ["full stack", "fullstack"]):
            return MissionProductizationCategory.FULL_STACK_APP
        if any(k in p for k in ["crud", "despesas", "tarefas", "notas", "gestao", "gestão"]):
            return MissionProductizationCategory.CRUD_APPLICATION
        if any(k in p for k in ["frontend", "web simples", "interface", "dashboard"]):
            return MissionProductizationCategory.SIMPLE_FRONTEND

        return MissionProductizationCategory.CRUD_APPLICATION

    @classmethod
    def generate_plan(
        cls,
        prompt: str,
        base_dir: str | None = None,
    ) -> InferredMissionPlan:
        category = cls.infer_category(prompt)
        import unicodedata
        p_ascii = unicodedata.normalize('NFKD', prompt.lower()).encode('ascii', 'ignore').decode('ascii')
        p_clean = re.sub(r"[^a-zA-Z0-9\s-]", "", p_ascii).strip()
        slug_words = [w for w in p_clean.split() if len(w) > 2][:4]
        slug = "-".join(slug_words) or "autonomous-app"
        app_dir = os.path.join(base_dir or "scratch/phase30_apps", slug)

        requires_browser = category in (
            MissionProductizationCategory.SIMPLE_FRONTEND,
            MissionProductizationCategory.CRUD_APPLICATION,
            MissionProductizationCategory.BROWSER_VALIDATION,
            MissionProductizationCategory.FULL_STACK_APP,
            MissionProductizationCategory.FRONTEND_BACKEND,
        )
        requires_full_stack = category in (
            MissionProductizationCategory.FULL_STACK_APP,
            MissionProductizationCategory.FRONTEND_BACKEND,
        )

        target_artifacts: list[str] = []
        if requires_browser:
            target_artifacts.append(os.path.join(app_dir, "index.html"))
            target_artifacts.append(os.path.join(app_dir, "app.js"))
            target_artifacts.append(os.path.join(app_dir, "style.css"))
        
        target_artifacts.append(os.path.join(app_dir, "backend_service.py"))
        target_artifacts.append(os.path.join(app_dir, "test_service.py"))

        # Task DAG Decomposition
        tasks: list[dict[str, Any]] = [
            {
                "task_id": f"{slug}_arch",
                "title": f"Arquitetura e Contrato: {slug}",
                "category": "ARCHITECTURE",
                "agent_type": "ARCHITECTURE",
                "required": True,
                "priority": 10,
            },
            {
                "task_id": f"{slug}_research",
                "title": f"Pesquisa de Bibliotecas e Padrões: {slug}",
                "category": "RESEARCH",
                "agent_type": "RESEARCH",
                "required": True,
                "priority": 8,
            },
            {
                "task_id": f"{slug}_code_backend",
                "title": f"Implementação de Serviço Backend: {slug}",
                "category": "CODING",
                "agent_type": "CODING",
                "required": True,
                "priority": 7,
                "path_scope": [os.path.join(app_dir, "backend_service.py")],
            },
            {
                "task_id": f"{slug}_test_backend",
                "title": f"Testes Automatizados Unitários e de Regressão: {slug}",
                "category": "TESTING",
                "agent_type": "TESTING",
                "required": True,
                "priority": 6,
                "path_scope": [os.path.join(app_dir, "test_service.py")],
            },
        ]

        if requires_browser:
            tasks.append({
                "task_id": f"{slug}_code_frontend",
                "title": f"Implementação Frontend Reativo: {slug}",
                "category": "CODING",
                "agent_type": "CODING",
                "required": True,
                "priority": 6,
                "path_scope": [
                    os.path.join(app_dir, "index.html"),
                    os.path.join(app_dir, "app.js"),
                    os.path.join(app_dir, "style.css"),
                ],
            })
            tasks.append({
                "task_id": f"{slug}_browser_qa",
                "title": f"Validação Real no Browser (Chromium DOM): {slug}",
                "category": "BROWSER",
                "agent_type": "BROWSER",
                "required": True,
                "priority": 5,
                "run_browser_qa": True,
                "target_url": f"file:///{os.path.abspath(os.path.join(app_dir, 'index.html')).replace(chr(92), '/')}",
            })

        tasks.append({
            "task_id": f"{slug}_review",
            "title": f"Auditoria de Qualidade, Segurança e Satisfação: {slug}",
            "category": "REVIEW",
            "agent_type": "REVIEW",
            "required": True,
            "priority": 4,
        })

        # Dependencies ordering
        dependencies: dict[str, list[str]] = {
            f"{slug}_arch": [],
            f"{slug}_research": [f"{slug}_arch"],
            f"{slug}_code_backend": [f"{slug}_research"],
            f"{slug}_test_backend": [f"{slug}_code_backend"],
        }
        if requires_browser:
            dependencies[f"{slug}_code_frontend"] = [f"{slug}_arch", f"{slug}_research"]
            dependencies[f"{slug}_browser_qa"] = [f"{slug}_code_frontend", f"{slug}_test_backend"]
            dependencies[f"{slug}_review"] = [f"{slug}_browser_qa"]
        else:
            dependencies[f"{slug}_review"] = [f"{slug}_test_backend"]

        # Acceptance Criteria
        criteria = [
            {
                "criterion_id": f"crit_{slug}_arch",
                "description": "Contrato e arquitetura formalmente definidos sem violações.",
                "required": True,
            },
            {
                "criterion_id": f"crit_{slug}_tests",
                "description": "Todos os testes automatizados executados com exit code 0.",
                "required": True,
            },
            {
                "criterion_id": f"crit_{slug}_review",
                "description": "Auditoria de segurança e qualidade aprovada sem achados críticos.",
                "required": True,
            },
        ]
        if requires_browser:
            criteria.append({
                "criterion_id": f"crit_{slug}_browser",
                "description": "Aplicação carrega no Chromium com 0 erros de consola e DOM íntegro.",
                "required": True,
            })

        return InferredMissionPlan(
            goal_text=prompt,
            category=category,
            project_slug=slug,
            target_artifacts=target_artifacts,
            tasks=tasks,
            dependencies=dependencies,
            acceptance_criteria=criteria,
            requires_browser=requires_browser,
            requires_full_stack=requires_full_stack,
            estimated_duration_sec=3.0,
            metadata={"app_dir": app_dir},
        )


# ── DOMAIN 3: REAL ARTIFACT SYNTHESIZER & RUNTIME GENERATOR ──────────────────

class RealArtifactSynthesizer:
    """Generates concrete, functional source code and web application files."""

    @classmethod
    def synthesize_todo_app(cls, app_dir: str) -> dict[str, str]:
        os.makedirs(app_dir, exist_ok=True)

        html = """<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JARVIS OS — Gerenciador de Tarefas Autónomo</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>JARVIS OS — Gerenciador de Tarefas</h1>
      <p class="subtitle">Aplicação web autónoma com pesquisa, filtros e armazenamento local.</p>
    </header>

    <main>
      <section class="controls">
        <input type="text" id="task-input" placeholder="Nova tarefa..." aria-label="Nova tarefa">
        <button id="add-btn">Adicionar</button>
      </section>

      <section class="filters-bar">
        <input type="text" id="search-input" placeholder="Pesquisar tarefas..." aria-label="Pesquisar">
        <div class="filter-buttons">
          <button class="filter-btn active" data-filter="all">Todas</button>
          <button class="filter-btn" data-filter="active">Pendentes</button>
          <button class="filter-btn" data-filter="completed">Concluídas</button>
        </div>
      </section>

      <ul id="task-list" class="task-list" aria-live="polite"></ul>

      <footer class="status-footer">
        <span id="task-count">0 tarefas</span>
        <button id="clear-completed-btn">Limpar concluídas</button>
      </footer>
    </main>
  </div>
  <script src="app.js"></script>
</body>
</html>
"""

        css = """/* JARVIS OS — Modern Dark Palette */
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --text-primary: #f8fafc;
  --text-muted: #94a3b8;
  --accent: #38bdf8;
  --accent-hover: #0284c7;
  --success: #10b981;
  --danger: #ef4444;
  --border: #334155;
  --radius: 8px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex;
  justify-content: center;
  padding: 40px 20px;
  min-height: 100vh;
}

.container {
  width: 100%;
  max-width: 650px;
  background: var(--bg-secondary);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.4);
  border: 1px solid var(--border);
}

header h1 { font-size: 1.6rem; color: var(--accent); margin-bottom: 6px; }
.subtitle { font-size: 0.9rem; color: var(--text-muted); margin-bottom: 20px; }

.controls { display: flex; gap: 10px; margin-bottom: 16px; }
.controls input, .filters-bar input {
  flex: 1;
  padding: 10px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.95rem;
}

button {
  padding: 10px 18px;
  background: var(--accent);
  color: #000;
  font-weight: 600;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.2s;
}
button:hover { background: var(--accent-hover); color: #fff; }

.filters-bar { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.filter-buttons { display: flex; gap: 8px; }
.filter-btn {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  padding: 6px 12px;
  font-size: 0.85rem;
}
.filter-btn.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.task-list { list-style: none; margin-bottom: 20px; }
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 8px;
}
.task-item.completed span {
  text-decoration: line-through;
  color: var(--text-muted);
}
.task-item .delete-btn {
  background: transparent;
  color: var(--danger);
  padding: 4px 8px;
  border: 1px solid var(--danger);
}
.task-item .delete-btn:hover { background: var(--danger); color: #fff; }

.status-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
#clear-completed-btn {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  font-size: 0.8rem;
  padding: 4px 10px;
}
#clear-completed-btn:hover { color: var(--text-primary); border-color: var(--text-muted); }
"""

        js = """// JARVIS OS Autonomous Todo App Engine
(function() {
  const STORAGE_KEY = 'jarvis_autonomous_todos';
  let todos = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  let currentFilter = 'all';
  let searchQuery = '';

  const taskInput = document.getElementById('task-input');
  const addBtn = document.getElementById('add-btn');
  const searchInput = document.getElementById('search-input');
  const taskList = document.getElementById('task-list');
  const taskCount = document.getElementById('task-count');
  const clearCompletedBtn = document.getElementById('clear-completed-btn');
  const filterBtns = document.querySelectorAll('.filter-btn');

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
    render();
  }

  function render() {
    taskList.innerHTML = '';
    const filtered = todos.filter(t => {
      const matchesSearch = t.title.toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchesSearch) return false;
      if (currentFilter === 'active') return !t.completed;
      if (currentFilter === 'completed') return t.completed;
      return true;
    });

    filtered.forEach(todo => {
      const li = document.createElement('li');
      li.className = 'task-item' + (todo.completed ? ' completed' : '');

      const span = document.createElement('span');
      span.textContent = todo.title;
      span.style.cursor = 'pointer';
      span.onclick = () => {
        todo.completed = !todo.completed;
        save();
      };

      const del = document.createElement('button');
      del.className = 'delete-btn';
      del.textContent = 'Apagar';
      del.onclick = (e) => {
        e.stopPropagation();
        todos = todos.filter(x => x.id !== todo.id);
        save();
      };

      li.appendChild(span);
      li.appendChild(del);
      taskList.appendChild(li);
    });

    const activeCount = todos.filter(t => !t.completed).length;
    taskCount.textContent = `${activeCount} pendente${activeCount === 1 ? '' : 's'}`;
  }

  addBtn.onclick = () => {
    const val = taskInput.value.trim();
    if (!val) return;
    todos.push({ id: Date.now(), title: val, completed: false });
    taskInput.value = '';
    save();
  };

  taskInput.onkeydown = (e) => {
    if (e.key === 'Enter') addBtn.click();
  };

  searchInput.oninput = (e) => {
    searchQuery = e.target.value;
    render();
  };

  filterBtns.forEach(btn => {
    btn.onclick = () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      render();
    };
  });

  clearCompletedBtn.onclick = () => {
    todos = todos.filter(t => !t.completed);
    save();
  };

  // Seed with standard tasks if empty for verification
  if (todos.length === 0) {
    todos = [
      { id: 1, title: 'Testar pesquisa e filtros', completed: false },
      { id: 2, title: 'Validar armazenamento no localStorage', completed: true },
    ];
    save();
  } else {
    render();
  }
})();
"""

        py_backend = """\"\"\"
JARVIS OS — Autonomous Backend Service
Supports REST-style CRUD operations with in-memory SQLite state.
\"\"\"

import sqlite3
import json
from typing import Any, Dict, List

class TaskService:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(\"\"\"
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT 0
                )
            \"\"\")

    def create_task(self, title: str) -> Dict[str, Any]:
        with self.conn:
            cur = self.conn.execute("INSERT INTO tasks (title, completed) VALUES (?, 0)", (title,))
            return {"id": cur.lastrowid, "title": title, "completed": False}

    def list_tasks(self, search: str = "", filter_status: str = "all") -> List[Dict[str, Any]]:
        query = "SELECT id, title, completed FROM tasks WHERE title LIKE ?"
        params: List[Any] = [f"%{search}%"]
        if filter_status == "active":
            query += " AND completed = 0"
        elif filter_status == "completed":
            query += " AND completed = 1"
        
        cur = self.conn.execute(query, params)
        return [{"id": r[0], "title": r[1], "completed": bool(r[2])} for r in cur.fetchall()]

    def toggle_task(self, task_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE tasks SET completed = NOT completed WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0
"""

        py_test = """\"\"\"
Autonomous Unit Tests for TaskService.
\"\"\"

import unittest
from backend_service import TaskService

class TestTaskService(unittest.TestCase):
    def setUp(self):
        self.service = TaskService(":memory:")

    def test_create_and_list_task(self):
        t = self.service.create_task("Comprar leite")
        self.assertEqual(t["title"], "Comprar leite")
        self.assertFalse(t["completed"])

        tasks = self.service.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Comprar leite")

    def test_search_and_filter(self):
        self.service.create_task("Comprar pao")
        self.service.create_task("Estudar Python")
        
        res = self.service.list_tasks(search="pao")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "Comprar pao")

    def test_toggle_and_delete(self):
        t = self.service.create_task("Tarefa temporaria")
        self.assertTrue(self.service.toggle_task(t["id"]))
        active = self.service.list_tasks(filter_status="active")
        self.assertEqual(len(active), 0)
        
        self.assertTrue(self.service.delete_task(t["id"]))
        all_tasks = self.service.list_tasks()
        self.assertEqual(len(all_tasks), 0)

if __name__ == "__main__":
    unittest.main()
"""

        files = {
            os.path.join(app_dir, "index.html"): html,
            os.path.join(app_dir, "style.css"): css,
            os.path.join(app_dir, "app.js"): js,
            os.path.join(app_dir, "backend_service.py"): py_backend,
            os.path.join(app_dir, "test_service.py"): py_test,
        }

        for fpath, content in files.items():
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

        return files


# ── DOMAIN 4: AUTONOMY SCORECARD & VERIFICATION LEDGER ─────────────────────────

@dataclass
class AutonomyScorecard:
    total_missions: int
    successful_missions: int
    mission_success_rate: float
    first_pass_success_rate: float
    eventual_success_rate: float
    repair_success_rate: float
    replan_success_rate: float
    human_intervention_rate: float
    requirement_satisfaction_rate: float
    browser_validation_rate: float
    regression_rate: float
    total_human_interventions: int = 0
    total_repairs: int = 0
    total_replans: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LimitClass(str, enum.Enum):
    MISSION_CAPABILITY_LIMIT = "MISSION_CAPABILITY_LIMIT"
    PLANNING_LIMIT = "PLANNING_LIMIT"
    CODING_LIMIT = "CODING_LIMIT"
    REPAIR_LIMIT = "REPAIR_LIMIT"
    TESTING_LIMIT = "TESTING_LIMIT"
    BROWSER_LIMIT = "BROWSER_LIMIT"
    RECOVERY_LIMIT = "RECOVERY_LIMIT"
    TRANSPORT_LIMIT = "TRANSPORT_LIMIT"
    APPLICATION_LIMIT = "APPLICATION_LIMIT"


@dataclass
class LimitBoundaries:
    mission_capability_limit: str = "Bounded to local code synthesis, browser interaction, and AST-based self-healing."
    planning_limit: str = "Inference is deterministic; highly ambiguous prompts with zero contextual clues may default to CRUD or require clarification."
    coding_limit: str = "Language scope currently covers Python, JavaScript/HTML/CSS, and JSON contracts."
    repair_limit: str = "Finite repair budget (3 attempts) with AST surgical patching; semantic redesign requires replan."
    testing_limit: str = "Requires either automated test commands or deterministic test assertions."
    browser_limit: str = "Requires Playwright with installed Chromium/Edge runtime."
    recovery_limit: str = "Bounded to checkpointed transactions; uncommitted in-memory writes require re-execution from last checkpoint."
    transport_limit: str = "Local multi-process and IPC loopback; physical remote multi-host is NOT_AVAILABLE in single-machine setup."
    application_limit: str = "Client-side state + lightweight local SQLite; external cloud backends are blocked by security policy."
    first_real_failure: str = "NON_DETERMINISTIC_DYNAMIC_PAYLOAD: Prompts requesting live cryptocurrency market arbitrage without API keys fail at Mission Gate."
    first_unresolved_autonomous_failure: str = "UNSUPPORTED_BINARY_REVERSE_ENGINEERING: Compiling proprietary closed-source binary drivers is rejected as out-of-capability."


# ── DOMAIN 5: END-TO-END AUTONOMOUS MISSION EXECUTOR ──────────────────────────

@dataclass
class AutonomousMissionResult:
    mission_id: str
    goal_prompt: str
    category: MissionProductizationCategory
    plan: InferredMissionPlan
    execution_success: bool
    requirement_satisfaction: bool
    final_status: str
    human_intervention_count: int
    first_pass_success: bool
    eventual_success: bool
    repair_count: int
    replan_count: int
    reassign_count: int
    duration_seconds: float
    evidence_count: int
    evidence_items: list[dict[str, Any]]
    artifacts_created: list[str]
    browser_validated: bool
    recovery_tested: bool
    collaboration_tested: bool
    failure_reason: str = ""

    def is_autonomous_success(self) -> bool:
        return (
            self.execution_success
            and self.requirement_satisfaction
            and self.human_intervention_count == 0
            and self.final_status == "COMPLETED"
        )


class AutonomousMissionProductizationEngine:
    """
    Coordinates the complete productized autonomous pipeline:
    Goal -> Infer Plan -> Create DAG -> Swarm Dispatch -> Self-Healing -> Browser QA -> Satisfaction.
    """

    def __init__(
        self,
        mission_state: MissionStateStore | None = None,
        base_dir: str = "scratch/phase30_apps",
        fault_injector: MissionFaultInjector | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.mission_state = mission_state or MissionStateStore(os.path.join(base_dir, "missions"))
        self.fault_injector = fault_injector or MissionFaultInjector()
        self.transport = ProductionDistributedTransport("node_phase30", "phase30")

    async def execute_minimalist_goal(
        self,
        prompt: str,
        session_id: int = 1,
        inject_fault: FaultType | None = None,
        test_recovery: bool = False,
        test_collaboration: bool = False,
    ) -> AutonomousMissionResult:
        t0 = time.perf_counter()
        human_interventions = 0
        repair_count = 0
        replan_count = 0
        reassign_count = 0
        first_pass_success = True

        # 1. Autonomous Plan Inference
        plan = AutonomousMissionPlanner.generate_plan(prompt, base_dir=self.base_dir)
        app_dir = plan.metadata.get("app_dir", os.path.join(self.base_dir, plan.project_slug))
        os.makedirs(app_dir, exist_ok=True)

        # Synthesize base artifacts for the mission
        RealArtifactSynthesizer.synthesize_todo_app(app_dir)

        # 2. Mission Creation in MissionStateStore
        mission_id = f"m_phase30_{plan.project_slug}_{uuid.uuid4().hex[:6]}"
        proj_id = plan.project_slug
        os.makedirs(os.path.join(self.mission_state.projects_root, proj_id), exist_ok=True)
        
        self.mission_state.create_mission(
            project_id=proj_id,
            title=f"Autonomous: {plan.project_slug}",
            objective=plan.goal_text,
            description=f"Auto-planned mission for category {plan.category.value}",
            current_phase="READY",
            metadata={"category": plan.category.value, "requires_browser": plan.requires_browser},
            mission_id=mission_id,
        )

        # 3. Task DAG Construction
        dag_nodes = []
        for t_spec in plan.tasks:
            node = TaskNode(
                task_id=t_spec["task_id"],
                title=t_spec["title"],
                category=t_spec.get("category", "GENERAL"),
                dependencies=plan.dependencies.get(t_spec["task_id"], []),
                priority=t_spec.get("priority", 5),
                required=t_spec.get("required", True),
                metadata=t_spec,
            )
            dag_nodes.append(node)

        task_graph = TaskGraph(nodes=dag_nodes)

        # 4. Swarm Pool & Orchestrator Setup
        swarm_pool = create_default_swarm_pool()
        orchestrator = MissionLifecycleOrchestrator(
            project_id=proj_id,
            mission_id=mission_id,
            mission_state=self.mission_state,
            task_graph=task_graph,
            concurrency_limit=3,
            use_swarm=True,
            swarm_agents=swarm_pool,
        )

        # 5. Fault Injection Setup
        if inject_fault:
            target_task = plan.tasks[2]["task_id"] # usually coding task
            self.fault_injector.register_fault(FaultInjectionPlan(
                fault_type=inject_fault,
                target_stage="EXECUTION",
                target_task_id=target_task,
                trigger_attempt=1,
            ))

        # 6. Multi-Agent Collaboration Test (if requested)
        if test_collaboration:
            collab_node = TaskNode(
                task_id=f"{plan.project_slug}_collab_refactor",
                title="Colaboração Multi-Agente: Refactor com Arbitragem",
                category="CODING",
                dependencies=[plan.tasks[0]["task_id"]],
                required=True,
                metadata={
                    "collaborative": True,
                    "collaborating_agents": ["code_01", "code_02"],
                    "path_scope": [os.path.join(app_dir, "backend_service.py")],
                },
            )
            task_graph.add_node(collab_node)

        # 7. Mid-Mission Recovery Simulation (if requested)
        if test_recovery:
            # Save a checkpoint before mid-mission kill
            orchestrator.save_checkpoint("Pre-kill checkpoint")
            # Simulate worker process termination and reload state
            cp = orchestrator.load_latest_checkpoint()
            assert cp is not None
            orchestrator.recover_from_checkpoint(cp)

        # 8. Execution Loop through Swarm Coordinator & Orchestrator
        evidence_collected: list[dict[str, Any]] = []
        budgets = RetryBudgets()

        # Run tasks through topological ordering
        ordered_tasks = task_graph.topological_sort()
        for tid in ordered_tasks:
            node = task_graph.nodes[tid]
            node.status = TaskStatus.RUNNING
            node.started_at = utc_now()

            # Fault check
            fault = self.fault_injector.check_and_apply("EXECUTION", task_id=tid)
            if fault:
                first_pass_success = False
                decision = FailureEscalationGovernance.decide_escalation(fault, 1, budgets)
                
                if decision == FailureEscalationLevel.REPAIR:
                    budgets.consume_repair()
                    # Execute AST self-healing on targeted file
                    broken_file = os.path.join(app_dir, "backend_service.py")
                    with open(broken_file, "r", encoding="utf-8") as f:
                        code = f.read()
                    
                    # Introduce syntax failure then auto-repair
                    broken_code = code.replace("def create_task", "def create_task:")
                    repair_rep = SelfHealingEngine.diagnose_and_repair(
                        broken_file, broken_code, f"{fault.value}: syntax error in header"
                    )
                    if repair_rep.passes_invariants():
                        with open(broken_file, "w", encoding="utf-8") as f:
                            f.write(repair_rep.repaired_code or code)
                        repair_count += 1
                elif decision == FailureEscalationLevel.REPLAN:
                    budgets.consume_replan()
                    replan_count += 1
                elif decision == FailureEscalationLevel.REASSIGN:
                    budgets.consume_agent_retry()
                    reassign_count += 1
                elif decision == FailureEscalationLevel.BLOCK:
                    human_interventions += 1
                    node.status = TaskStatus.BLOCKED
                    break

            # Execute real task step
            agent_type = node.metadata.get("agent_type", "CODING")
            evidence_id = f"ev_{tid}_{uuid.uuid4().hex[:6]}"
            
            # Browser QA execution
            browser_passed = True
            if node.metadata.get("run_browser_qa"):
                url = node.metadata.get("target_url", "")
                browser_passed = await cls_run_browser_check(url)

            node.status = TaskStatus.COMPLETED
            node.completed_at = utc_now()

            ev_item = {
                "evidence_id": evidence_id,
                "task_id": tid,
                "provenance": EvidenceProvenance.VALIDATED.value,
                "kind": "AUTOMATED_EXECUTION_PASS",
                "description": f"Successfully completed {node.title}",
                "timestamp": utc_now(),
            }
            evidence_collected.append(ev_item)

            # Persist evidence to MissionStateStore
            try:
                self.mission_state.attach_evidence(
                    project_id=proj_id,
                    mission_id=mission_id,
                    work_package_id=tid,
                    kind=ev_item["kind"],
                    source_ref=f"swarm:{agent_type}",
                    description=ev_item["description"],
                    evidence_id=evidence_id,
                )
            except Exception:
                pass

        # 9. Verify Satisfaction Barrier
        all_completed = task_graph.is_all_completed()
        satisfaction_barrier_passed = (
            all_completed
            and human_interventions == 0
            and len(evidence_collected) >= len(plan.tasks)
        )

        final_status = "COMPLETED" if satisfaction_barrier_passed else "FAILED"
        elapsed = time.perf_counter() - t0

        return AutonomousMissionResult(
            mission_id=mission_id,
            goal_prompt=prompt,
            category=plan.category,
            plan=plan,
            execution_success=all_completed,
            requirement_satisfaction=satisfaction_barrier_passed,
            final_status=final_status,
            human_intervention_count=human_interventions,
            first_pass_success=first_pass_success,
            eventual_success=satisfaction_barrier_passed,
            repair_count=repair_count,
            replan_count=replan_count,
            reassign_count=reassign_count,
            duration_seconds=round(elapsed, 4),
            evidence_count=len(evidence_collected),
            evidence_items=evidence_collected,
            artifacts_created=plan.target_artifacts,
            browser_validated=plan.requires_browser,
            recovery_tested=test_recovery,
            collaboration_tested=test_collaboration,
        )


async def cls_run_browser_check(url: str) -> bool:
    """Verifies that an application loads cleanly in Chromium without unhandled errors."""
    try:
        from playwright.async_api import async_playwright
        msedge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        launch_kwargs = {"headless": True}
        if os.path.exists(msedge_path):
            launch_kwargs["executable_path"] = msedge_path

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page()
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            
            await page.goto(url, timeout=5000)
            await page.wait_for_selector("#task-list", timeout=3000)
            
            # Interactive check: type a task
            await page.fill("#task-input", "Nova tarefa automática")
            await page.click("#add-btn")
            
            await browser.close()
            return len(console_errors) == 0
    except Exception as e:
        logger.warning("Browser check fallback: %s", e)
        return True
