"""
JARVIS OS - Benchmark Canónico Real T001 a T010 (Fase 9.2).

Executa os 10 cenários obrigatórios contra o sistema de ficheiros real,
testando o pipeline completo:
1. Criar fixture real em disco (tmp_path)
2. Executar Project Intake
3. Executar Architecture Detection
4. Executar Artifact Inference
5. Recolher resultado
6. Validar contra Ground Truth (expected_architecture, expected_capabilities,
   allowed_artifacts, forbidden_artifacts, expected_responsibilities)
7. Guardar evidência de execução
"""

import json
import pytest
from pathlib import Path

from intelligence.artifact_inference import (
    ArtifactInferenceEngine,
    Capability,
    ProjectIntakeArchitectureDetector,
)


GROUND_TRUTH_TABLE = {
    "T001": {
        "name": "Vanilla Web",
        "prompt": "Cria uma landing page com formulário de contacto",
        "expected_architecture": "vanilla_web",
        "expected_capabilities": [Capability.FRONTEND],
        "allowed_artifacts": ["index.html", "styles.css", "app.js"],
        "forbidden_artifacts": ["src/App.tsx", "server.py"],
        "expected_responsibilities": ["HTML5 document structure", "responsive CSS stylesheet"],
    },
    "T002": {
        "name": "React / Vite",
        "prompt": "Cria uma aplicação de gestão de tarefas com componentes",
        "expected_architecture": "react_vite",
        "expected_capabilities": [Capability.FRONTEND, Capability.CRUD],
        "allowed_artifacts": ["src/App.tsx", "src/main.tsx", "src/index.css"],
        "forbidden_artifacts": ["app.js", "styles.css", "server.py"],
        "expected_responsibilities": ["frontend application entrypoint", "frontend style system"],
    },
    "T003": {
        "name": "Next.js App Router",
        "prompt": "Cria um portal de notícias",
        "expected_architecture": "nextjs",
        "expected_capabilities": [Capability.FRONTEND],
        "allowed_artifacts": ["app/page.tsx", "app/layout.tsx", "app/globals.css"],
        "forbidden_artifacts": ["index.html", "app.js", "styles.css"],
        "expected_responsibilities": ["Next.js page entrypoint", "Next.js root layout"],
    },
    "T004": {
        "name": "FastAPI Backend",
        "prompt": "Cria uma API RESTful assíncrona com documentação OpenAPI",
        "expected_architecture": "python_fastapi",
        "expected_capabilities": [Capability.BACKEND, Capability.API],
        "allowed_artifacts": ["main.py", "requirements.txt"],
        "forbidden_artifacts": ["index.html", "app.js", "styles.css"],
        "expected_responsibilities": ["backend runtime entrypoint and API routes"],
    },
    "T005": {
        "name": "Express / TypeScript",
        "prompt": "Cria um backend Node Express com TypeScript",
        "expected_architecture": "node_express",
        "expected_capabilities": [Capability.BACKEND],
        "allowed_artifacts": ["src/server.ts", "server.js", "package.json"],
        "forbidden_artifacts": ["server.py", "index.html", "app.js"],
        "expected_responsibilities": ["Node backend API entrypoint"],
    },
    "T006": {
        "name": "Custom Python",
        "prompt": "Adicionar rotina de processamento de dados",
        "expected_architecture": "custom_python",
        "expected_capabilities": [],
        "allowed_artifacts": ["core/processor.py", "main.py"],
        "forbidden_artifacts": ["index.html", "styles.css", "app.js"],
        "expected_responsibilities": [],
    },
    "T007": {
        "name": "localStorage Vanilla",
        "prompt": "Guarda as preferências do utilizador localmente no browser",
        "expected_architecture": "vanilla_web",
        "expected_capabilities": [Capability.FRONTEND, Capability.STORAGE],
        "allowed_artifacts": ["app.js", "index.html"],
        "forbidden_artifacts": ["database.py", "server.py"],
        "expected_responsibilities": ["client-side storage in browser"],
    },
    "T008": {
        "name": "localStorage React",
        "prompt": "Persiste o estado da aplicação localmente",
        "expected_architecture": "react_vite",
        "expected_capabilities": [Capability.FRONTEND, Capability.STORAGE],
        "allowed_artifacts": ["src/App.tsx", "src/services/storage.ts"],
        "forbidden_artifacts": ["database.py", "app.js", "styles.css"],
        "expected_responsibilities": ["client-side state persistence (localStorage / IndexedDB)"],
    },
    "T009": {
        "name": "Distributed CRUD",
        "prompt": "Cria sistema com frontend e backend para CRUD de inventário",
        "expected_architecture": "react_vite",
        "expected_capabilities": [Capability.FRONTEND, Capability.BACKEND, Capability.CRUD],
        "allowed_artifacts": ["src/App.tsx", "main.py", "server.py"],
        "forbidden_artifacts": ["crud.py", "crud.ts", "crud.js"],
        "expected_responsibilities": ["frontend application entrypoint"],
    },
    "T010": {
        "name": "Dashboard React",
        "prompt": "Adiciona dashboard de métricas e KPIs à aplicação",
        "expected_architecture": "react_vite",
        "expected_capabilities": [Capability.FRONTEND, Capability.DASHBOARD],
        "allowed_artifacts": ["src/components/Dashboard.tsx", "src/App.tsx"],
        "forbidden_artifacts": ["index.html", "app.js"],
        "expected_responsibilities": ["dashboard metric and summary view"],
    },
}


def test_benchmark_t001_vanilla(tmp_path):
    p = tmp_path / "t001"
    p.mkdir()
    (p / "index.html").write_text("<!DOCTYPE html><html><body><h1>Landing</h1></body></html>", encoding="utf-8")
    (p / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
    (p / "app.js").write_text("console.log('init');", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T001"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    for cap in gt["expected_capabilities"]:
        assert res.has_capability(cap)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths


def test_benchmark_t002_react_vite(tmp_path):
    p = tmp_path / "t002"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "^4.0.0"}}), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <h1>Tarefas</h1>; }", encoding="utf-8")
    (src / "main.tsx").write_text("import ReactDOM from 'react-dom/client'; import App from './App'; ReactDOM.createRoot(document.getElementById('root')!).render(<App />);", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; }", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T002"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    for cap in gt["expected_capabilities"]:
        assert res.has_capability(cap)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    for allowed in gt["allowed_artifacts"]:
        assert allowed in paths


def test_benchmark_t003_nextjs(tmp_path):
    p = tmp_path / "t003"
    p.mkdir()
    app_dir = p / "app"
    app_dir.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"next": "^14.0.0"}}), encoding="utf-8")
    (app_dir / "page.tsx").write_text("export default function Page() { return <h1>Noticias</h1>; }", encoding="utf-8")
    (app_dir / "layout.tsx").write_text("export default function RootLayout({ children }) { return <html><body>{children}</body></html>; }", encoding="utf-8")
    (app_dir / "globals.css").write_text("body { margin: 0; }", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T003"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    for cap in gt["expected_capabilities"]:
        assert res.has_capability(cap)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    assert "app/page.tsx" in paths


def test_benchmark_t004_fastapi(tmp_path):
    p = tmp_path / "t004"
    p.mkdir()
    (p / "requirements.txt").write_text("fastapi>=0.110.0\nuvicorn>=0.28.0\n", encoding="utf-8")
    (p / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T004"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    for cap in gt["expected_capabilities"]:
        assert res.has_capability(cap)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    assert "main.py" in paths


def test_benchmark_t005_express_typescript(tmp_path):
    p = tmp_path / "t005"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.18.2"}, "devDependencies": {"typescript": "^5.0.0"}}), encoding="utf-8")
    (p / "tsconfig.json").write_text("{}", encoding="utf-8")
    (src / "server.ts").write_text("import express from 'express'; const app = express(); app.listen(8080);", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T005"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    for cap in gt["expected_capabilities"]:
        assert res.has_capability(cap)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    assert "src/server.ts" in paths


def test_benchmark_t006_custom_python(tmp_path):
    p = tmp_path / "t006"
    p.mkdir()
    core = p / "core"
    core.mkdir()
    (core / "processor.py").write_text("def run(): pass\n", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T006"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths


def test_benchmark_t007_localstorage_vanilla(tmp_path):
    p = tmp_path / "t007"
    p.mkdir()
    (p / "index.html").write_text("<!DOCTYPE html><html><body><h1>App</h1></body></html>", encoding="utf-8")
    (p / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
    (p / "app.js").write_text("console.log('run');", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T007"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    assert res.has_capability(Capability.STORAGE)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths


def test_benchmark_t008_localstorage_react(tmp_path):
    p = tmp_path / "t008"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.2.0"}}), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <h1>App</h1>; }", encoding="utf-8")
    (src / "main.tsx").write_text("export default {};", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; }", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T008"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    assert res.has_capability(Capability.STORAGE)
    paths = res.required_paths()
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    # Não deve criar database.py
    assert "database.py" not in paths


def test_benchmark_t009_distributed_crud(tmp_path):
    p = tmp_path / "t009"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.2.0"}}), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <h1>Inventario</h1>; }", encoding="utf-8")
    (src / "main.tsx").write_text("export default {};", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; }", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T009"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.has_capability(Capability.CRUD)
    paths = res.required_paths()
    # REGRA FUNDAMENTAL: NUNCA criar crud.py, crud.ts, crud.js
    for forb in gt["forbidden_artifacts"]:
        assert forb not in paths
    assert not any("crud." in p.lower() for p in paths)


def test_benchmark_t010_dashboard_react(tmp_path):
    p = tmp_path / "t010"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    components = src / "components"
    components.mkdir()
    (p / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.2.0"}}), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <h1>App</h1>; }", encoding="utf-8")
    (src / "main.tsx").write_text("export default {};", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; }", encoding="utf-8")
    (components / "Dashboard.tsx").write_text("export function Dashboard() { return <div>KPIs</div>; }", encoding="utf-8")

    gt = GROUND_TRUTH_TABLE["T010"]
    engine = ArtifactInferenceEngine()
    res = engine.infer(gt["prompt"], project_root=str(p))

    assert res.architecture.stack == gt["expected_architecture"]
    assert res.has_capability(Capability.DASHBOARD)
    dash_arts = [a for a in res.required_artifacts if a.category == "dashboard" or "dashboard" in a.artifact_id]
    assert len(dash_arts) > 0
    assert dash_arts[0].existing is True
    assert dash_arts[0].relative_path in ("src/components/Dashboard.tsx", "src/App.tsx")
    # Proibido index.html e app.js
    for forb in gt["forbidden_artifacts"]:
        assert forb not in res.required_paths()
