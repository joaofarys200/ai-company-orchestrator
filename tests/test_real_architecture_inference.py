"""
JARVIS OS - Testes de Inferência Arquitetural e Validação Anti-Template (Fase 9.2).

Verifica os requisitos fundamentais:
1. Anti-Template: A mesma capacidade FRONTEND produz artefactos diferentes em React, Next.js, Vue e Vanilla.
2. Anti-Template: Nunca exige index.html / styles.css / app.js como requisitos universais.
3. Project Edit: 'adiciona pesquisa' num projeto React edita componentes React e NUNCA cria search.js.
4. Project Edit: 'adiciona dashboard' num projeto Next.js usa estrutura Next e NUNCA cria index.html.
5. Novo Projeto: Decisão de arquitetura explícita (ArchitectureDecision) antes da criação de artefactos.
6. Mismatch: Deteta ARTIFACT_ARCHITECTURE_MISMATCH quando templates vanilla são propostos para React/Next.
7. Product Delivery Gate: Aceitação baseada em responsabilidade e evidência funcional, não em nomes fixos.
"""

import json
import pytest
from pathlib import Path

from intelligence.artifact_inference import (
    ArchitectureDecision,
    ArtifactInferenceEngine,
    Capability,
    CapabilityDetector,
    DeterministicRepairEngine,
    InferredArtifact,
    ProjectArchitecture,
    ProjectIntakeArchitectureDetector,
    detect_architecture_mismatch,
)
from security.delivery_governance import (
    DeliveryGateStatus,
    ProductDeliveryGate,
    RequirementStatus,
)


# ==============================================================================
# 1. TESTES ANTI-TEMPLATE (Capacidade FRONTEND -> Artefactos Diferentes)
# ==============================================================================

def test_anti_template_react_app(tmp_path):
    """
    Projeto React/Vite:
    A capacidade FRONTEND deve resultar em artefactos React (src/App.tsx, src/main.tsx, src/index.css).
    FALHA se o motor tentar exigir app.js ou styles.css vanilla.
    """
    p = tmp_path / "react_app"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "react-client",
        "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
        "devDependencies": {"vite": "^4.0.0"}
    }), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <h1>React</h1>; }", encoding="utf-8")
    (src / "main.tsx").write_text("import ReactDOM from 'react-dom/client'; import App from './App'; ReactDOM.createRoot(document.getElementById('root')!).render(<App />);", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; }", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="cria uma interface para o utilizador",
        project_root=str(p),
    )

    assert result.has_capability(Capability.FRONTEND)
    assert result.architecture is not None
    assert result.architecture.stack == "react_vite"
    assert result.architecture_decision.architecture == "react_vite"
    assert result.architecture_decision.detected is True

    paths = result.required_paths()
    # Artefactos React esperados
    assert any("App.tsx" in path for path in paths)
    assert any("main.tsx" in path for path in paths)
    assert any("index.css" in path for path in paths)

    # ANTI-TEMPLATE: Ficheiros de template vanilla estritamente PROIBIDOS como requisitos
    assert "app.js" not in paths
    assert "styles.css" not in paths


def test_anti_template_nextjs_app(tmp_path):
    """
    Projeto Next.js:
    A capacidade FRONTEND deve resultar em artefactos App Router (app/page.tsx, app/layout.tsx, app/globals.css).
    FALHA se o motor tentar exigir index.html ou app.js.
    """
    p = tmp_path / "next_app"
    p.mkdir()
    app_dir = p / "app"
    app_dir.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "next-app",
        "dependencies": {"next": "^14.0.0", "react": "^18.2.0"}
    }), encoding="utf-8")
    (p / "next.config.js").write_text("module.exports = {};", encoding="utf-8")
    (app_dir / "page.tsx").write_text("export default function Page() { return <h1>Next.js</h1>; }", encoding="utf-8")
    (app_dir / "layout.tsx").write_text("export default function RootLayout({ children }) { return <html><body>{children}</body></html>; }", encoding="utf-8")
    (app_dir / "globals.css").write_text("body { margin: 0; }", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="cria uma pagina moderna de apresentacao",
        project_root=str(p),
    )

    assert result.has_capability(Capability.FRONTEND)
    assert result.architecture.stack == "nextjs"
    assert result.architecture_decision.architecture == "nextjs"

    paths = result.required_paths()
    assert any("page.tsx" in path for path in paths)
    assert any("layout.tsx" in path for path in paths)
    assert any("globals.css" in path for path in paths)

    # ANTI-TEMPLATE: index.html e app.js PROIBIDOS
    assert "index.html" not in paths
    assert "app.js" not in paths


def test_anti_template_vue_app(tmp_path):
    """
    Projeto Vue 3:
    A capacidade FRONTEND deve resultar em src/App.vue e src/main.js.
    """
    p = tmp_path / "vue_app"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "vue-app",
        "dependencies": {"vue": "^3.3.0"},
        "devDependencies": {"vite": "^4.0.0"}
    }), encoding="utf-8")
    (src / "App.vue").write_text("<template><h1>Vue</h1></template><script setup></script>", encoding="utf-8")
    (src / "main.js").write_text("import { createApp } from 'vue'; import App from './App.vue'; createApp(App).mount('#app');", encoding="utf-8")
    (src / "style.css").write_text("body { margin: 0; }", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="cria uma aplicacao frontend",
        project_root=str(p),
    )

    assert result.has_capability(Capability.FRONTEND)
    assert result.architecture.stack == "vue_vite"
    paths = result.required_paths()
    assert any("App.vue" in path for path in paths)
    assert any("main.js" in path for path in paths)
    assert "app.js" not in paths


def test_anti_template_vanilla_app(tmp_path):
    """
    Projeto Vanilla:
    Deve inferir index.html, styles.css, app.js como resultado de DECISÃO ARQUITETURAL,
    e não de imposição cega de template.
    """
    p = tmp_path / "vanilla_app"
    p.mkdir()
    (p / "index.html").write_text("<!DOCTYPE html><html><body><h1>Vanilla</h1></body></html>", encoding="utf-8")
    (p / "styles.css").write_text("body { background: #fff; }", encoding="utf-8")
    (p / "app.js").write_text("console.log('vanilla');", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="cria uma aplicacao web",
        project_root=str(p),
    )

    assert result.has_capability(Capability.FRONTEND)
    assert result.architecture.stack == "vanilla_web"
    paths = result.required_paths()
    assert "index.html" in paths
    assert "styles.css" in paths
    assert "app.js" in paths


def test_same_capability_different_artifacts(tmp_path):
    """
    Prova formal: A MESMA capability FRONTEND para 4 stacks diferentes
    gera 4 conjuntos de artefactos disjuntos.
    """
    engine = ArtifactInferenceEngine()

    res_react = engine.infer("cria aplicacao", planned_files={"src/App.tsx": "", "src/main.tsx": ""})
    res_next = engine.infer("cria aplicacao", planned_files={"app/page.tsx": "", "app/layout.tsx": ""})
    res_vue = engine.infer("cria aplicacao", planned_files={"src/App.vue": "", "src/main.js": ""})
    res_vanilla = engine.infer("cria aplicacao", planned_files={"index.html": "", "styles.css": ""})

    paths_react = set(res_react.required_paths())
    paths_next = set(res_next.required_paths())
    paths_vue = set(res_vue.required_paths())
    paths_vanilla = set(res_vanilla.required_paths())

    # Devem ser conjuntos estruturalmente distintos
    assert paths_react != paths_next
    assert paths_react != paths_vanilla
    assert paths_next != paths_vanilla
    assert paths_vue != paths_react


# ==============================================================================
# 2. TESTES DE PROJECT EDIT (EXISTING VS NEW ARTIFACT)
# ==============================================================================

def test_project_edit_react_add_search(tmp_path):
    """
    Projeto React existente + 'adiciona pesquisa'.
    O sistema deve resolver SearchBar.tsx e App.tsx.
    NUNCA deve criar search.js.
    """
    p = tmp_path / "react_search"
    p.mkdir()
    src = p / "src"
    src.mkdir()
    components = src / "components"
    components.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "react-search-app",
        "dependencies": {"react": "^18.2.0"}
    }), encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <div>App</div>; }", encoding="utf-8")
    (components / "SearchBar.tsx").write_text("export function SearchBar() { return <input />; }", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="adiciona pesquisa à lista de tarefas",
        project_root=str(p),
    )

    search_artifacts = [a for a in result.required_artifacts if a.category == "search" or "search" in a.artifact_id]
    assert len(search_artifacts) > 0
    search_art = search_artifacts[0]

    # Deve resolver o componente TSX existente
    assert search_art.existing is True
    assert search_art.relative_path in ("src/components/SearchBar.tsx", "src/App.tsx")
    assert search_art.architecture == "react_vite"

    # NUNCA search.js
    assert not any(a.relative_path == "search.js" for a in result.required_artifacts)


def test_project_edit_nextjs_add_dashboard(tmp_path):
    """
    Projeto Next.js existente + 'adiciona dashboard'.
    O sistema deve resolver rotas/componentes Next.js (app/dashboard/page.tsx ou app/page.tsx).
    NUNCA deve criar index.html.
    """
    p = tmp_path / "next_dashboard"
    p.mkdir()
    app_dir = p / "app"
    app_dir.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "next-dash",
        "dependencies": {"next": "^14.0.0"}
    }), encoding="utf-8")
    (app_dir / "page.tsx").write_text("export default function Page() { return <div>Home</div>; }", encoding="utf-8")

    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="adiciona dashboard com estatisticas e kpis",
        project_root=str(p),
    )

    dash_artifacts = [a for a in result.required_artifacts if a.category == "dashboard" or "dashboard" in a.artifact_id]
    assert len(dash_artifacts) > 0
    dash_art = dash_artifacts[0]

    assert dash_art.architecture == "nextjs"
    assert "app/" in dash_art.relative_path
    assert not any(a.relative_path == "index.html" for a in result.required_artifacts)


# ==============================================================================
# 3. TESTE DE NOVO PROJETO (ARCHITECTURE DECISION EXPLICITA)
# ==============================================================================

def test_new_empty_project_explicit_architecture_decision():
    """
    Projeto vazio + 'cria uma aplicacao web simples'.
    Deve produzir uma ArchitectureDecision formal e explícita antes de gerar qualquer artefacto.
    """
    engine = ArtifactInferenceEngine()
    result = engine.infer(
        prompt="cria uma aplicacao web simples de tarefas",
        project_name="my-clean-app",
        planned_files={},
    )

    decision = result.architecture_decision
    assert decision is not None
    assert decision.detected is False
    assert decision.source == "default_architecture"
    assert decision.confidence > 0.8
    assert len(decision.evidence) > 0
    assert decision.architecture in ("vanilla_web", "react_vite")


# ==============================================================================
# 4. TESTE DE DETEÇÃO DE ARTIFACT_ARCHITECTURE_MISMATCH
# ==============================================================================

def test_detect_artifact_architecture_mismatch():
    """
    Verifica que propor app.js num projeto React/Vite despoleta ARTIFACT_ARCHITECTURE_MISMATCH.
    """
    arch = ProjectArchitecture(
        architecture_id="react_vite",
        stack="react_vite",
        framework="React",
        bundler="vite",
        runtime="browser",
        frontend_entrypoints=["src/App.tsx", "src/main.tsx"],
    )

    planned_files = {
        "src/App.tsx": "export default function App() { return <h1>OK</h1>; }",
        "app.js": "document.addEventListener('DOMContentLoaded', () => {});",
        "styles.css": "body { margin: 0; }",
    }

    mismatches = detect_architecture_mismatch(planned_files, arch)
    assert len(mismatches) > 0
    assert any("ARTIFACT_ARCHITECTURE_MISMATCH" in m and "app.js" in m for m in mismatches)


def test_repair_engine_removes_architecture_mismatch():
    """
    O DeterministicRepairEngine deve remover ficheiros template estranhos (app.js)
    de planos de projetos React/Vite.
    """
    repair_engine = DeterministicRepairEngine()
    planned_files = {
        "src/App.tsx": "export default function App() { return <h1>OK</h1>; }",
        "src/main.tsx": "import ReactDOM from 'react-dom/client'; import App from './App'; ReactDOM.createRoot(document.getElementById('root')!).render(<App />);",
        "app.js": "console.log('running');",  # Mismatch template
    }

    result = repair_engine.repair_plan(
        prompt="atualiza a aplicacao react",
        planned_files=planned_files,
        project_name="react-fix",
    )

    assert result.repaired is True
    # O ficheiro app.js foi removido da lista de ficheiros reparados
    assert "app.js" not in result.repaired_files
    assert any(a.action_type == "REMOVE_MISMATCH" and a.relative_path == "app.js" for a in result.actions)


# ==============================================================================
# 5. TESTE DE INTEGRAÇÃO COM PRODUCT DELIVERY GATE
# ==============================================================================

def test_product_delivery_gate_accepts_react_entrypoint_by_responsibility(tmp_path):
    """
    O ProductDeliveryGate deve aceitar src/App.tsx e src/main.tsx como satisfação
    da responsabilidade 'frontend application entrypoint', sem exigir index.html vanilla.
    """
    p = tmp_path / "react_gate"
    p.mkdir()
    src = p / "src"
    src.mkdir()

    (p / "package.json").write_text(json.dumps({
        "name": "react-gate-app",
        "dependencies": {"react": "^18.2.0"},
        "devDependencies": {"vite": "^4.0.0"}
    }), encoding="utf-8")
    (p / "vite.config.ts").write_text("export default {};", encoding="utf-8")
    (src / "App.tsx").write_text("export default function App() { return <div><h1>Painel</h1><button id='action-btn'>OK</button></div>; }", encoding="utf-8")
    (src / "main.tsx").write_text("import ReactDOM from 'react-dom/client'; import App from './App'; ReactDOM.createRoot(document.getElementById('root')!).render(<App />);", encoding="utf-8")
    (src / "index.css").write_text("body { margin: 0; background: #000; }", encoding="utf-8")

    report = ProductDeliveryGate.evaluate_delivery(
        project_root=str(p),
        project_id="gate-react-01",
        user_prompt="Cria painel de gestao em react",
    )

    assert report.architecture_decision.selected_stack == "react_vite"
    assert report.gate_status == DeliveryGateStatus.PRODUCT_ACCEPTED.value
    assert report.result == RequirementStatus.PASS.value
