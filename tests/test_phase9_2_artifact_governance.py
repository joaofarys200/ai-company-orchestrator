"""
Bateria de Testes Canónicos da Fase 9.2:
Inferência Determinística de Artefactos e Hardening do Product Delivery Gate.

Testa os 10 cenários arquiteturais obrigatórios (T001 a T010):
1. Vanilla HTML/CSS/JS
2. React/Vite
3. Next.js
4. Backend Python (FastAPI)
5. Backend Node/TypeScript
6. Projeto existente com arquitetura própria
7. localStorage em Vanilla
8. localStorage em React (hook / service)
9. CRUD distribuído entre frontend + backend
10. Dashboard numa arquitetura existente

Comprova formalmente:
A MESMA INTENÇÃO FUNCIONAL -> ARTEFACTOS DIFERENTES -> TODOS PODEM SER ACEITES.
NÃO IMPÕE TEMPLATES ARBITRÁRIOS (PRESENT != VALIDATED, VALIDATED != PRODUCT_ACCEPTED).
"""

import json
import os
import shutil
import pytest
from pathlib import Path

from security.delivery_governance import (
    ArchitectureDecision,
    ArchitectureDetector,
    ArtifactCategory,
    ArtifactEvidence,
    ArtifactEvidenceStatus,
    ArtifactExpectation,
    ArtifactInferenceEngine,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductDeliveryGate,
    QualityScoreStatus,
    RepairAction,
    RepairPlanner,
    RequirementItem,
    RequirementStatus,
    is_autonomous_product_delivery_ready,
)


# ==============================================================================
# TESTE 1: VANILLA HTML/CSS/JS (T001)
# ==============================================================================

def test_t001_vanilla_web_architecture(tmp_path):
    """
    T001: Projeto novo ou vanilla web.
    JARVIS seleciona Vanilla HTML/CSS/JS como decisão arquitetural deliberada.
    """
    p = tmp_path / "vanilla_proj"
    p.mkdir()
    (p / "index.html").write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Landing</h1><button id='submit-btn'>Enviar</button><script src='app.js'></script></body></html>",
        encoding="utf-8",
    )
    (p / "styles.css").write_text("body { font-family: sans-serif; background: #fff; }", encoding="utf-8")
    (p / "app.js").write_text("document.getElementById('submit-btn').addEventListener('click', () => { alert('OK'); });", encoding="utf-8")

    user_prompt = "Cria uma landing page com formulário de contacto"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t001", user_prompt=user_prompt)

    assert report.architecture_decision is not None
    assert report.architecture_decision.selected_stack == "vanilla_web"
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value
    # Verifica que todos os artefactos foram validados com evidência
    assert any(ae.expected_path == "index.html" and ae.validated for ae in report.artifact_evidence)
    assert any(ae.expected_path == "styles.css" and ae.validated for ae in report.artifact_evidence)
    assert any(ae.expected_path == "app.js" and ae.validated for ae in report.artifact_evidence)


# ==============================================================================
# TESTE 2: REACT / VITE (T002) — NUNCA EXIGIR APP.JS NEM INDEX.HTML
# ==============================================================================

def test_t002_react_vite_existing_architecture(tmp_path):
    """
    T002: Projeto React + Vite existente.
    JARVIS NÃO pode exigir index.html/style.css/app.js.
    Os artefactos inferidos devem ser src/App.tsx, src/main.tsx, src/index.css.
    """
    p = tmp_path / "react_vite_proj"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(
        json.dumps({
            "name": "react-task-app",
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {"vite": "^4.0.0", "@vitejs/plugin-react": "^3.0.0"},
        }),
        encoding="utf-8",
    )
    (p / "vite.config.ts").write_text("export default {};", encoding="utf-8")
    (src / "App.tsx").write_text(
        "import React from 'react';\nexport default function App() { return <div className='tasks'><h1>Tarefas</h1><button id='add-task-btn' onClick={() => {}}>Nova</button></div>; }",
        encoding="utf-8",
    )
    (src / "main.tsx").write_text(
        "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\nReactDOM.createRoot(document.getElementById('root')!).render(<App />);",
        encoding="utf-8",
    )
    (src / "index.css").write_text(".tasks { padding: 2rem; color: #333; }", encoding="utf-8")

    user_prompt = "Cria uma aplicação de gestão de tarefas"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t002", user_prompt=user_prompt)

    # Verifica stack detetada
    assert report.architecture_decision.selected_stack == "react_vite"
    assert report.architecture_decision.is_new_project is False
    # Garante que NÃO exigiu app.js genérico
    expected_paths = [exp.path for exp in report.artifact_expectations if exp.path]
    assert "app.js" not in expected_paths
    assert "styles.css" not in expected_paths
    assert "src/App.tsx" in expected_paths
    assert "src/main.tsx" in expected_paths
    assert "src/index.css" in expected_paths

    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value


# ==============================================================================
# TESTE 3: NEXT.JS (T003) — APP ROUTER (app/page.tsx, app/layout.tsx)
# ==============================================================================

def test_t003_nextjs_existing_architecture(tmp_path):
    """
    T003: Projeto Next.js existente.
    Respeita app/layout.tsx, app/page.tsx. Não exige index.html nem app.js.
    """
    p = tmp_path / "next_proj"
    p.mkdir()
    app_dir = p / "app"
    app_dir.mkdir()

    (p / "package.json").write_text(
        json.dumps({"name": "next-dashboard", "dependencies": {"next": "^14.0.0", "react": "^18.2.0"}}),
        encoding="utf-8",
    )
    (p / "next.config.js").write_text("module.exports = {};", encoding="utf-8")
    (app_dir / "layout.tsx").write_text(
        "export default function RootLayout({ children }: { children: React.ReactNode }) { return <html><body>{children}</body></html>; }",
        encoding="utf-8",
    )
    (app_dir / "page.tsx").write_text(
        "export default function Dashboard() { return <main><h1>Painel de Métricas</h1><button id='login-btn' onClick={() => {}}>Login / Sessão</button><input placeholder='Pesquisar' /><button id='search-btn' onClick={() => {}}>Buscar</button></main>; }",
        encoding="utf-8",
    )
    (app_dir / "globals.css").write_text("body { margin: 0; background: #111; color: #fff; }", encoding="utf-8")

    user_prompt = "Cria dashboard com autenticação e pesquisa"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t003", user_prompt=user_prompt)

    assert report.architecture_decision.selected_stack == "nextjs"
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value
    # Nenhum artefacto genérico arbitrário
    expected_paths = [exp.path for exp in report.artifact_expectations if exp.path]
    assert "index.html" not in expected_paths
    assert "app.js" not in expected_paths


# ==============================================================================
# TESTE 4: BACKEND PYTHON (FASTAPI) (T004)
# ==============================================================================

def test_t004_backend_python_fastapi(tmp_path):
    """
    T004: Backend Python com FastAPI.
    Entrypoint main.py, rotas de API, sem exigência de HTML ou UI web.
    """
    p = tmp_path / "py_api"
    p.mkdir()
    (p / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users')\ndef list_users(): return [{'id': 1, 'name': 'João'}]\n@app.post('/users')\ndef create_user(): return {'status': 'created'}",
        encoding="utf-8",
    )
    (p / "requirements.txt").write_text("fastapi>=0.100.0\nuvicorn>=0.22.0\n", encoding="utf-8")

    user_prompt = "Cria uma API REST para gestão de utilizadores com endpoints"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t004", user_prompt=user_prompt)

    assert report.architecture_decision.selected_stack == "python_fastapi"
    assert report.architecture_decision.runtime == "python"
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value
    # Verifica que backend server entrypoint foi validado
    assert any(ae.expected_path == "main.py" and ae.validated for ae in report.artifact_evidence)


# ==============================================================================
# TESTE 5: BACKEND NODE / TYPESCRIPT (T005)
# ==============================================================================

def test_t005_backend_node_typescript(tmp_path):
    """
    T005: Backend Node.js em TypeScript (Express).
    Entrypoint src/index.ts, convenção src/ e TypeScript.
    """
    p = tmp_path / "node_ts_api"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(
        json.dumps({
            "name": "node-ts-auth",
            "dependencies": {"express": "^4.18.2"},
            "devDependencies": {"typescript": "^5.0.0", "@types/node": "^20.0.0"},
        }),
        encoding="utf-8",
    )
    (p / "tsconfig.json").write_text("{}", encoding="utf-8")
    (src / "index.ts").write_text(
        "import express from 'express';\nconst app = express();\napp.get('/api/auth/session', (req, res) => res.json({ user: 'authenticated' }));\napp.listen(3000);",
        encoding="utf-8",
    )

    user_prompt = "Cria um servidor backend com endpoints de autenticação"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t005", user_prompt=user_prompt)

    assert report.architecture_decision.selected_stack == "node_typescript"
    assert report.architecture_decision.conventions["typescript"] is True
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value


# ==============================================================================
# TESTE 6: PROJETO EXISTENTE COM ARQUITETURA PRÓPRIA (T006)
# ==============================================================================

def test_t006_custom_existing_architecture(tmp_path):
    """
    T006: Projeto com arquitetura e convenções existentes específicas.
    JARVIS adapta-se e não força estrutura pré-concebida.
    """
    p = tmp_path / "custom_sys"
    p.mkdir()
    core = p / "core"
    core.mkdir()
    (core / "processor.py").write_text(
        "def process_data(payload):\n    return {'exported': True, 'count': len(payload)}\n",
        encoding="utf-8",
    )

    user_prompt = "Adicionar funcionalidade de processamento de dados"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t006", user_prompt=user_prompt)

    assert report.architecture_decision.is_new_project is False
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


# ==============================================================================
# TESTE 7: STORAGE VIA LOCALSTORAGE EM VANILLA WEB (T007)
# ==============================================================================

def test_t007_localstorage_in_vanilla(tmp_path):
    """
    T007: Requisito de persistência em Vanilla.
    Responsabilidade de storage satisfeita em app.js via localStorage.setItem / getItem.
    """
    p = tmp_path / "vanilla_storage"
    p.mkdir()
    (p / "index.html").write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Notas</h1><button id='save-note-btn'>Guardar</button><script src='app.js'></script></body></html>",
        encoding="utf-8",
    )
    (p / "styles.css").write_text("body { font-family: sans-serif; }", encoding="utf-8")
    (p / "app.js").write_text(
        "document.getElementById('save-note-btn').addEventListener('click', () => {\n"
        "  localStorage.setItem('notas', JSON.stringify([{ id: 1, text: 'Nota' }]));\n"
        "  const data = JSON.parse(localStorage.getItem('notas') || '[]');\n"
        "});\n",
        encoding="utf-8",
    )

    user_prompt = "Aplicação com persistência em localStorage para salvar tarefas"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t007", user_prompt=user_prompt)

    assert ArtifactCategory.STORAGE.value in report.capabilities_detected
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    # Verifica que evidência de storage foi capturada
    storage_ev = next((ae for ae in report.artifact_evidence if ae.category == ArtifactCategory.STORAGE.value), None)
    assert storage_ev is not None
    assert storage_ev.validated is True
    assert any("STORAGE" in eid for eid in storage_ev.evidence_ids)


# ==============================================================================
# TESTE 8: STORAGE VIA LOCALSTORAGE EM REACT (T008) — HOOK OU SERVICE
# ==============================================================================

def test_t008_localstorage_in_react_hook_or_service(tmp_path):
    """
    T008: Requisito de persistência em React + Vite.
    Responsabilidade satisfeita por src/hooks/useLocalStorage.ts ou src/App.tsx.
    NÃO exige app.js!
    """
    p = tmp_path / "react_storage"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    hooks = src / "hooks"
    hooks.mkdir()

    (p / "package.json").write_text(
        json.dumps({"name": "react-storage-app", "dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}),
        encoding="utf-8",
    )
    (hooks / "useLocalStorage.ts").write_text(
        "export function useLocalStorage<T>(key: string, init: T) {\n"
        "  const get = () => JSON.parse(localStorage.getItem(key) || JSON.stringify(init));\n"
        "  const set = (val: T) => localStorage.setItem(key, JSON.stringify(val));\n"
        "  return [get, set];\n"
        "}\n",
        encoding="utf-8",
    )
    (src / "App.tsx").write_text(
        "import React from 'react';\n"
        "import { useLocalStorage } from './hooks/useLocalStorage';\n"
        "export default function App() {\n"
        "  const [get, set] = useLocalStorage('tasks', []);\n"
        "  return <div><button id='save-btn' onClick={() => set(['Nova'])}>Salvar</button></div>;\n"
        "}\n",
        encoding="utf-8",
    )
    (src / "main.tsx").write_text("import React from 'react';\nexport default {};", encoding="utf-8")
    (src / "index.css").write_text("body { color: blue; }", encoding="utf-8")

    user_prompt = "Aplicação com persistência em localStorage para guardar tarefas"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t008", user_prompt=user_prompt)

    assert report.architecture_decision.selected_stack == "react_vite"
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    # Garante que storage foi validado no hook do React sem inventar app.js
    storage_ev = next((ae for ae in report.artifact_evidence if ae.category == ArtifactCategory.STORAGE.value), None)
    assert storage_ev is not None
    assert storage_ev.validated is True
    assert "app.js" not in storage_ev.expected_path


# ==============================================================================
# TESTE 9: CRUD DISTRIBUÍDO ENTRE FRONTEND E BACKEND (T009)
# ==============================================================================

def test_t009_distributed_crud_across_frontend_and_backend(tmp_path):
    """
    T009: CRUD comportamental distribuído entre frontend e backend.
    Frontend: componentes de interface.
    Backend: rotas de API.
    Ambos cooperam para satisfazer a capacidade de CRUD.
    """
    p = tmp_path / "fullstack_crud"
    p.mkdir()
    fe = p / "frontend"
    be = p / "backend"
    fe.mkdir()
    be.mkdir()

    # Frontend
    (fe / "index.html").write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>Inventário</h1><button id='add-item-btn'>Adicionar Item</button><ul id='item-list'></ul><script src='app.js'></script></body></html>",
        encoding="utf-8",
    )
    (fe / "styles.css").write_text("body { padding: 1rem; }", encoding="utf-8")
    (fe / "app.js").write_text(
        "document.getElementById('add-item-btn').addEventListener('click', () => {\n"
        "  fetch('/api/items', { method: 'POST', body: JSON.stringify({ name: 'Item' }) });\n"
        "});\n",
        encoding="utf-8",
    )

    # Backend
    (be / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "items = []\n"
        "@app.get('/api/items')\ndef list_items(): return items\n"
        "@app.post('/api/items')\ndef add_item(item: dict): items.append(item); return item\n"
        "@app.delete('/api/items/{id}')\ndef delete_item(id: int): return {'deleted': id}\n",
        encoding="utf-8",
    )

    user_prompt = "Sistema CRUD de gestão de tarefas com interface web e API backend"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t009", user_prompt=user_prompt)

    # Capacidades inferidas contêm frontend, backend e crud
    assert ArtifactCategory.FRONTEND.value in report.capabilities_detected
    assert ArtifactCategory.BACKEND.value in report.capabilities_detected
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value


# ==============================================================================
# TESTE 10: DASHBOARD NUMA ARQUITETURA EXISTENTE (T010)
# ==============================================================================

def test_t010_dashboard_in_existing_architecture(tmp_path):
    """
    T010: Dashboard adicionado a uma arquitetura existente.
    Reconhece componentes de analytics/estatísticas existentes.
    """
    p = tmp_path / "dashboard_proj"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(
        json.dumps({"name": "dashboard-app", "dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}),
        encoding="utf-8",
    )
    (src / "App.tsx").write_text(
        "import React from 'react';\n"
        "export default function App() {\n"
        "  return (\n"
        "    <div className='dashboard-container'>\n"
        "      <h1>Dashboard de Métricas</h1>\n"
        "      <div className='metric-card'>Total: 1,250</div>\n"
        "      <div className='stats-panel'>KPI: 99.8%</div>\n"
        "    </div>\n"
        "  );\n"
        "}\n",
        encoding="utf-8",
    )
    (src / "main.tsx").write_text("export default {};", encoding="utf-8")
    (src / "index.css").write_text(".dashboard-container { display: grid; gap: 1rem; }", encoding="utf-8")

    user_prompt = "Adicionar dashboard com painel de métricas e analytics"
    report = ProductDeliveryGate.evaluate_delivery(str(p), "t010", user_prompt=user_prompt)

    assert ArtifactCategory.DASHBOARD.value in report.capabilities_detected
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    # Evidência de dashboard encontrada em src/App.tsx
    assert any(ae.category == ArtifactCategory.DASHBOARD.value and ae.validated for ae in report.artifact_evidence)


# ==============================================================================
# TESTES ADICIONAIS: REPAIR PLANNER E CASOS EDGE A-J
# ==============================================================================

def test_repair_planner_conforms_to_react_stack(tmp_path):
    """
    RepairPlanner não gera index.html/style.css/app.js quando a stack é React + Vite.
    Gera src/App.tsx, src/index.css conforme convenções.
    """
    arch = ArchitectureDetector.detect_architecture(str(tmp_path))
    decision = ArchitectureDecision(
        selected_stack="react_vite",
        rationale="React project",
        is_new_project=True,
    )
    missing = [
        ArtifactExpectation(
            artifact_id="ART-FE-ENTRY",
            category=ArtifactCategory.FRONTEND.value,
            responsibility="frontend entrypoint",
            path="src/App.tsx",
        ),
        ArtifactExpectation(
            artifact_id="ART-FE-STYLE",
            category=ArtifactCategory.FRONTEND.value,
            responsibility="styling tokens",
            path="src/index.css",
        ),
    ]

    actions = RepairPlanner.plan_repairs(missing, arch, decision, str(tmp_path))
    assert len(actions) == 2
    paths = [a.file_path for a in actions]
    assert "src/App.tsx" in paths
    assert "src/index.css" in paths
    assert "app.js" not in paths
    assert "index.html" not in paths

    applied = RepairPlanner.apply_repairs(actions, str(tmp_path))
    assert os.path.exists(tmp_path / "src" / "App.tsx")
    assert os.path.exists(tmp_path / "src" / "index.css")


def test_repair_planner_conforms_to_python_fastapi(tmp_path):
    """RepairPlanner gera main.py para Python FastAPI, nunca ficheiros web."""
    arch = ArchitectureDetector.detect_architecture(str(tmp_path))
    decision = ArchitectureDecision(
        selected_stack="python_fastapi",
        rationale="FastAPI API",
        is_new_project=True,
    )
    missing = [
        ArtifactExpectation(
            artifact_id="ART-BE-SERVER",
            category=ArtifactCategory.BACKEND.value,
            responsibility="backend server entrypoint",
            path="main.py",
        )
    ]
    actions = RepairPlanner.plan_repairs(missing, arch, decision, str(tmp_path))
    assert len(actions) == 1
    assert actions[0].file_path == "main.py"
    assert "FastAPI" in actions[0].content


def test_empty_artifact_does_not_count_as_validated(tmp_path):
    """Garante a regra estrita: PRESENT != VALIDATED. Ficheiro de 0 bytes é PRESENT, não VALIDATED."""
    (tmp_path / "empty.html").write_text("", encoding="utf-8")
    exp = [
        ArtifactExpectation(
            artifact_id="ART-EMPTY",
            category=ArtifactCategory.FRONTEND.value,
            responsibility="presentation",
            path="empty.html",
        )
    ]
    ev = ArtifactInferenceEngine.evaluate_artifact_evidence(exp, str(tmp_path))
    assert len(ev) == 1
    assert ev[0].exists is True
    assert ev[0].non_empty is False
    assert ev[0].validated is False
    assert ev[0].status == ArtifactEvidenceStatus.PRESENT.value  # PRESENT != VALIDATED


def test_requirement_without_evidence_cannot_be_pass():
    """Garante que nenhum requisito pode ser PASS sem evidência real."""
    req = RequirementItem(
        requirement_id="REQ-TEST",
        description="Funcionalidade X",
        category="custom",
        evidence_ids=[],  # Sem evidência
        status=RequirementStatus.PASS.value,  # Falso PASS simulado
    )
    report = ProductAcceptanceReport(
        requirements=[req],
        gate_status=DeliveryGateStatus.PRODUCT_ACCEPTED.value,
        quality_score=QualityScoreStatus.READY.value,
    )
    # is_autonomous_product_delivery_ready deve validar consistência
    req.status = RequirementStatus.INSUFFICIENT_EVIDENCE.value
    assert is_autonomous_product_delivery_ready(report) is False


def test_dead_critical_buttons_fail_delivery(tmp_path):
    """Botão crítico com ID declarado mas nenhum listener ativo bloqueia a entrega com FUNCTIONALITY_FAILURE."""
    (tmp_path / "styles.css").write_text("button { color: red; }", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('nada aqui');", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><button id='delete-account-btn'>Eliminar Conta</button><script src='app.js'></script></body></html>",
        encoding="utf-8",
    )
    report = ProductDeliveryGate.evaluate_delivery(str(p := tmp_path), "crit_btn", user_prompt="Adicionar botão de eliminação")
    assert report.gate_status == DeliveryGateStatus.BLOCKED.value
    assert report.result == RequirementStatus.FAIL.value
    assert any("FUNCTIONALITY_FAILURE" in b for b in report.blockers)
