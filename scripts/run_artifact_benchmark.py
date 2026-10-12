"""
Script de Execução e Geração de Relatório do Benchmark T001 a T010.
Executa os 10 cenários arquiteturais da Fase 9.2 e valida os critérios de aceitação holísticos.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.delivery_governance import (
    DeliveryGateStatus,
    ProductDeliveryGate,
    RequirementStatus,
    is_autonomous_product_delivery_ready,
)


def run_benchmark() -> List[Dict[str, Any]]:
    benchmark_results: List[Dict[str, Any]] = []

    # T001: Vanilla Web
    with tempfile.TemporaryDirectory() as p:
        Path(p, "index.html").write_text(
            "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Landing</h1><button id='submit-btn'>Enviar</button><script src='app.js'></script></body></html>",
            encoding="utf-8",
        )
        Path(p, "styles.css").write_text("body { font-family: sans-serif; background: #fff; }", encoding="utf-8")
        Path(p, "app.js").write_text("document.getElementById('submit-btn').addEventListener('click', () => { alert('OK'); });", encoding="utf-8")

        prompt = "Cria uma landing page com formulário de contacto"
        r = ProductDeliveryGate.evaluate_delivery(p, "T001", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T001",
            "name": "Vanilla HTML/CSS/JS",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Vanilla Web (autónomo sem bundler)",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T002: React / Vite
    with tempfile.TemporaryDirectory() as p:
        src = Path(p, "src")
        src.mkdir()
        Path(p, "package.json").write_text(
            json.dumps({"name": "react-app", "dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}),
            encoding="utf-8",
        )
        Path(src, "App.tsx").write_text(
            "import React from 'react';\nexport default function App() { return <div className='tasks'><h1>Tarefas</h1><button id='add-task-btn' onClick={() => {}}>Nova</button></div>; }",
            encoding="utf-8",
        )
        Path(src, "main.tsx").write_text("import React from 'react';\nexport default {};", encoding="utf-8")
        Path(src, "index.css").write_text(".tasks { padding: 2rem; }", encoding="utf-8")

        prompt = "Cria uma aplicação de gestão de tarefas"
        r = ProductDeliveryGate.evaluate_delivery(p, "T002", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T002",
            "name": "React + Vite",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "React 18 + Vite (TypeScript, src/ convention)",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T003: Next.js
    with tempfile.TemporaryDirectory() as p:
        app_dir = Path(p, "app")
        app_dir.mkdir()
        Path(p, "package.json").write_text(json.dumps({"name": "next-app", "dependencies": {"next": "^14.0.0", "react": "^18.2.0"}}), encoding="utf-8")
        Path(p, "next.config.js").write_text("module.exports = {};", encoding="utf-8")
        Path(app_dir, "layout.tsx").write_text("export default function Layout({children}: any) { return <html><body>{children}</body></html>; }", encoding="utf-8")
        Path(app_dir, "page.tsx").write_text("export default function Dashboard() { return <main><h1>Painel de Métricas</h1><button id='login-btn' onClick={() => {}}>Login / Sessão</button><input placeholder='Pesquisar' /><button id='search-btn' onClick={() => {}}>Buscar</button></main>; }", encoding="utf-8")
        Path(app_dir, "globals.css").write_text("body { background: #000; }", encoding="utf-8")

        prompt = "Cria dashboard com autenticação e pesquisa"
        r = ProductDeliveryGate.evaluate_delivery(p, "T003", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T003",
            "name": "Next.js App Router",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Next.js 14 (App Router, app/ directory)",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T004: Python FastAPI
    with tempfile.TemporaryDirectory() as p:
        Path(p, "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users')\ndef list_users(): return [{'id': 1}]\n@app.post('/users')\ndef create_user(): return {'status': 'created'}",
            encoding="utf-8",
        )
        Path(p, "requirements.txt").write_text("fastapi>=0.100.0\n", encoding="utf-8")

        prompt = "Cria uma API REST para gestão de utilizadores com endpoints"
        r = ProductDeliveryGate.evaluate_delivery(p, "T004", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T004",
            "name": "Python FastAPI",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Python 3 + FastAPI REST Service",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T005: Node / TypeScript
    with tempfile.TemporaryDirectory() as p:
        src = Path(p, "src")
        src.mkdir()
        Path(p, "package.json").write_text(
            json.dumps({"name": "node-ts-app", "dependencies": {"express": "^4.18.2"}, "devDependencies": {"typescript": "^5.0.0"}}),
            encoding="utf-8",
        )
        Path(src, "index.ts").write_text(
            "import express from 'express';\nconst app = express();\napp.get('/api/auth', (req, res) => res.json({ ok: true }));",
            encoding="utf-8",
        )

        prompt = "Cria um servidor backend com endpoints de autenticação"
        r = ProductDeliveryGate.evaluate_delivery(p, "T005", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T005",
            "name": "Node.js Express + TypeScript",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Node.js TypeScript API (Express)",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T006: Custom Existing Architecture
    with tempfile.TemporaryDirectory() as p:
        core = Path(p, "core")
        core.mkdir()
        Path(core, "processor.py").write_text("def process_data(d): return {'ok': True}", encoding="utf-8")

        prompt = "Adicionar funcionalidade de processamento de dados"
        r = ProductDeliveryGate.evaluate_delivery(p, "T006", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T006",
            "name": "Custom Existing Architecture",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Custom Proprietary Repository Structure",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T007: localStorage in Vanilla Web
    with tempfile.TemporaryDirectory() as p:
        Path(p, "index.html").write_text(
            "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Tarefas</h1><button id='save-btn'>Salvar</button><script src='app.js'></script></body></html>",
            encoding="utf-8",
        )
        Path(p, "styles.css").write_text("body { font-family: sans-serif; }", encoding="utf-8")
        Path(p, "app.js").write_text(
            "document.getElementById('save-btn').addEventListener('click', () => { localStorage.setItem('tasks', '[]'); });",
            encoding="utf-8",
        )

        prompt = "Aplicação com persistência em localStorage para salvar tarefas"
        r = ProductDeliveryGate.evaluate_delivery(p, "T007", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T007",
            "name": "localStorage in Vanilla Web",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Vanilla Web com Storage em app.js",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T008: localStorage in React Hook/Service
    with tempfile.TemporaryDirectory() as p:
        src = Path(p, "src")
        hooks = src / "hooks"
        hooks.mkdir(parents=True)
        Path(p, "package.json").write_text(json.dumps({"name": "react-storage", "dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}), encoding="utf-8")
        Path(hooks, "useLocalStorage.ts").write_text(
            "export const useLocalStorage = (k: string) => [() => localStorage.getItem(k), (v: any) => localStorage.setItem(k, JSON.stringify(v))];",
            encoding="utf-8",
        )
        Path(src, "App.tsx").write_text(
            "import React from 'react';\nimport { useLocalStorage } from './hooks/useLocalStorage';\nexport default function App() { const [g, s] = useLocalStorage('tasks'); return <button id='save-btn' onClick={() => s([])}>Salvar</button>; }",
            encoding="utf-8",
        )
        Path(src, "main.tsx").write_text("export default {};", encoding="utf-8")
        Path(src, "index.css").write_text("body { color: blue; }", encoding="utf-8")

        prompt = "Aplicação com persistência em localStorage para guardar tarefas"
        r = ProductDeliveryGate.evaluate_delivery(p, "T008", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T008",
            "name": "localStorage in React (Hook/Service)",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "React + Vite com hook customizado de storage",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T009: Distributed CRUD Frontend + Backend
    with tempfile.TemporaryDirectory() as p:
        fe = Path(p, "frontend")
        be = Path(p, "backend")
        fe.mkdir()
        be.mkdir()
        Path(fe, "index.html").write_text("<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><button id='add-btn'>Add</button><script src='app.js'></script></body></html>", encoding="utf-8")
        Path(fe, "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
        Path(fe, "app.js").write_text("document.getElementById('add-btn').addEventListener('click', () => { fetch('/api/tasks'); });", encoding="utf-8")
        Path(be, "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api/tasks')\ndef list_tasks(): return []\n@app.post('/api/tasks')\ndef add_task(): return {'ok': True}\n@app.delete('/api/tasks/{id}')\ndef del_task(id: int): return {'deleted': id}",
            encoding="utf-8",
        )

        prompt = "Sistema CRUD de gestão de tarefas com interface web e API backend"
        r = ProductDeliveryGate.evaluate_delivery(p, "T009", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T009",
            "name": "Distributed CRUD Frontend + Backend",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "Monorepo Fullstack (Frontend estático + FastAPI)",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    # T010: Dashboard in Existing Architecture
    with tempfile.TemporaryDirectory() as p:
        src = Path(p, "src")
        src.mkdir()
        Path(p, "package.json").write_text(json.dumps({"name": "dashboard-app", "dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}), encoding="utf-8")
        Path(src, "App.tsx").write_text(
            "import React from 'react';\nexport default function App() { return <div className='dashboard'><h1>Dashboard</h1><div className='metric-card'>Total: 100</div></div>; }",
            encoding="utf-8",
        )
        Path(src, "main.tsx").write_text("export default {};", encoding="utf-8")
        Path(src, "index.css").write_text(".dashboard { padding: 1rem; }", encoding="utf-8")

        prompt = "Adicionar dashboard com painel de métricas e analytics"
        r = ProductDeliveryGate.evaluate_delivery(p, "T010", user_prompt=prompt)
        benchmark_results.append({
            "test_id": "T010",
            "name": "Dashboard in Existing React Architecture",
            "prompt": prompt,
            "detected_stack": r.architecture_decision.selected_stack if r.architecture_decision else "unknown",
            "detected_architecture": "React + Vite com componente de métricas",
            "inferred_capabilities": r.capabilities_detected,
            "inferred_artifacts": [f"{e.expected_path} [{e.responsibility}]" for e in r.artifact_evidence],
            "acceptance_tests": [rq.acceptance_test for rq in r.requirements],
            "evidence": [eid for ae in r.artifact_evidence for eid in ae.evidence_ids],
            "result": r.result,
            "gate_status": r.gate_status,
        })

    return benchmark_results


if __name__ == "__main__":
    results = run_benchmark()
    print("=" * 80)
    print("JARVIS PHASE 9.2 ARTIFACT INFERENCE BENCHMARK (T001 - T010)")
    print("=" * 80)
    for r in results:
        print(f"[{r['test_id']}] {r['name']}: {r['result']} ({r['gate_status']})")
        print(f"  • Stack: {r['detected_stack']}")
        print(f"  • Inferred Capabilities: {', '.join(r['inferred_capabilities'])}")
        print(f"  • Inferred Artifacts: {', '.join(r['inferred_artifacts'])}")
        print(f"  • Evidence: {len(r['evidence'])} verified tokens")
        print()
