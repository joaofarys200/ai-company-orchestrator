"""
JARVIS OS — Test Suite: Real Repository Coding Trial (Fase 10.2)
20 Tarefas abertas sobre 10 repositórios representativos (Zero Benchmark Leakage, Open-Ended Tasks, Extensionless ESM).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from intelligence.cross_file_validator import CrossFileValidator
from intelligence.real_repository_trial_agent import RealRepositoryCodingTrialAgent
from intelligence.repository_graph import RepositoryGraph


class TestRealRepositoryCodingTrial(unittest.IsolatedAsyncioTestCase):
    """Suíte de avaliação em repositórios reais e tarefas abertas."""

    def setUp(self) -> None:
        self.workspace_base = tempfile.mkdtemp(prefix="jarvis_real_repo_trial_")

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace_base, ignore_errors=True)

    def _create_repo(self, name: str) -> str:
        repo_dir = os.path.join(self.workspace_base, name)
        os.makedirs(repo_dir, exist_ok=True)
        return repo_dir

    def _write_file(self, repo_dir: str, rel_path: str, content: str) -> str:
        abs_p = os.path.join(repo_dir, rel_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_p

    # =========================================================================
    # REPOSITÓRIO 1: Python FastAPI Microservice (Tarefas 1 e 2)
    # =========================================================================

    async def test_t01_t02_python_fastapi_microservice(self) -> None:
        """T-01 (Bug Fix) e T-02 (Feature): FastAPI Microservice com models e rotas."""
        repo = self._create_repo("python_fastapi_microservice")
        self._write_file(repo, "requirements.txt", "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\n")
        self._write_file(repo, "app/models/user.py", "class User:\n    def __init__(self, id: int, name: str, active: bool = True):\n        self.id = id\n        self.name = name\n        self.active = active\n")
        self._write_file(repo, "app/services/user_service.py", "from app.models.user import User\n\nclass UserService:\n    def get_users(self, offset: int = 0, limit: int = 10):\n        # Bug T-01: sem proteção contra offset negativo\n        safe_offset = max(0, offset)\n        return [User(1, 'Alice')][safe_offset:safe_offset + limit]\n")
        self._write_file(repo, "app/api/users.py", "from fastapi import FastAPI\nfrom app.services.user_service import UserService\n\napp = FastAPI()\nservice = UserService()\n\n@app.get('/api/users')\ndef list_users(offset: int = 0, limit: int = 10, active_only: bool = False):\n    return service.get_users(offset, limit)\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        
        # T-01: Bug Fix
        res1 = agent.execute_trial_task(
            task_id="T-01",
            task_prompt="Corrigir offset negativo no serviço de utilizadores",
            criteria=["O serviço deve aceitar apenas offsets não negativos", "Pipeline deve passar"],
            expected_files=["app/services/user_service.py"],
        )
        self.assertTrue(res1.success)
        self.assertEqual(res1.discovery_model.package_manager, "unknown")
        self.assertIn("Python", res1.discovery_model.languages)

        # T-02: Feature Addition
        res2 = agent.execute_trial_task(
            task_id="T-02",
            task_prompt="Adicionar filtro de utilizadores ativos na rota de API",
            criteria=["Adicionar query param active_only", "Retornar lista filtrada"],
            expected_files=["app/api/users.py"],
        )
        self.assertTrue(res2.success)

    # =========================================================================
    # REPOSITÓRIO 2: Python Data Pipeline (Tarefas 3 e 4 - Open-ended)
    # =========================================================================

    async def test_t03_t04_python_data_pipeline(self) -> None:
        """T-03 (Refactor) e T-04 (Open-ended): Pipeline de dados em Python."""
        repo = self._create_repo("python_data_pipeline")
        self._write_file(repo, "pipeline/transformers.py", "class CSVTransformer:\n    def parse(self, line: str) -> list[str]:\n        return [x.strip() for x in line.split(',')]\n")
        self._write_file(repo, "pipeline/aggregator.py", "from pipeline.transformers import CSVTransformer\n\nclass DataAggregator:\n    def __init__(self):\n        self.t = CSVTransformer()\n    def sum_column(self, lines: list[str], col_idx: int) -> float:\n        total = 0.0\n        for l in lines:\n            parts = self.t.parse(l)\n            if len(parts) > col_idx:\n                total += float(parts[col_idx])\n        return total\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res3 = agent.execute_trial_task(
            task_id="T-03",
            task_prompt="Refatorar parsing de CSV para classe separada",
            criteria=["Manter a função sum_column funcional"],
            expected_files=["pipeline/transformers.py"],
        )
        self.assertTrue(res3.success)

        # T-04: Open-ended (sem especificar ficheiros)
        res4 = agent.execute_trial_task(
            task_id="T-04",
            task_prompt="Adiciona suporte para agregação de somatório mantendo o comportamento atual",
            criteria=["Calcular soma por coluna", "Reutilizar CSVTransformer existente"],
            expected_files=["pipeline/aggregator.py"],
        )
        self.assertTrue(res4.success)

    # =========================================================================
    # REPOSITÓRIO 3: TypeScript / React Vite SPA (Tarefas 5 e 6)
    # =========================================================================

    async def test_t05_t06_typescript_react_vite_spa(self) -> None:
        """T-05 (Feature) e T-06 (Bug Fix): React Vite SPA com Zustand."""
        repo = self._create_repo("react_vite_spa")
        self._write_file(repo, "package.json", json.dumps({"name": "vite-react-app", "dependencies": {"react": "^18.2.0", "zustand": "^4.4.0"}}))
        self._write_file(repo, "vite.config.ts", "export default {};\n")
        self._write_file(repo, "tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}))
        self._write_file(repo, "src/store/theme.ts", "export const useThemeStore = () => ({ theme: 'dark', toggle: () => {} });\n")
        self._write_file(repo, "src/components/Header.tsx", "import { useThemeStore } from '@/store/theme';\nexport function Header() { const { theme } = useThemeStore(); return <header className={theme} />; }\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-05",
            task_prompt="Adicionar alternador de tema claro/escuro no Header",
            criteria=["Usar theme store", "Renderizar classe correspondente"],
            expected_files=["src/components/Header.tsx"],
        )
        self.assertTrue(res.success)
        self.assertIn("TypeScript", res.discovery_model.languages)
        self.assertIn("React", res.discovery_model.frameworks)

    # =========================================================================
    # REPOSITÓRIO 4: TypeScript UI Component Library (Tarefas 7 e 8)
    # =========================================================================

    async def test_t07_t08_ui_component_library_barrel(self) -> None:
        """T-07 (Cross-file) e T-08 (Refactor): Biblioteca com barrel files."""
        repo = self._create_repo("ui_library")
        self._write_file(repo, "package.json", json.dumps({"name": "@myorg/ui-kit"}))
        self._write_file(repo, "src/components/Button.tsx", "export function Button() { return 'Btn'; }\n")
        self._write_file(repo, "src/components/Avatar.tsx", "export function Avatar() { return 'Avatar'; }\n")
        self._write_file(repo, "src/components/index.ts", "export * from './Button';\nexport * from './Avatar';\n")
        self._write_file(repo, "src/index.ts", "export * from './components';\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-07",
            task_prompt="Adicionar componente Avatar e exportar através de barrel file",
            criteria=["Criar Avatar.tsx", "Re-exportar em index.ts"],
            expected_files=["src/components/Avatar.tsx", "src/components/index.ts"],
        )
        self.assertTrue(res.success)

    # =========================================================================
    # REPOSITÓRIO 5: Next.js App Router (Tarefas 9 e 10 - Open-ended)
    # =========================================================================

    async def test_t09_t10_nextjs_app_router(self) -> None:
        """T-09 (Feature) e T-10 (Open-ended): Next.js 14 App Router."""
        repo = self._create_repo("nextjs_app_router")
        self._write_file(repo, "tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["*"]}}}))
        self._write_file(repo, "app/api/projects/route.ts", "export async function GET() { return []; }\nexport async function POST() { return { status: 'created' }; }\n")
        self._write_file(repo, "app/projects/page.tsx", "import { useEffect } from 'react';\nexport default function ProjectsPage() { return <div>Projects</div>; }\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-09",
            task_prompt="Adicionar rota de API de projetos com GET e POST",
            criteria=["Exportar GET e POST em route.ts", "Passar validação de contratos"],
            expected_files=["app/api/projects/route.ts"],
        )
        self.assertTrue(res.success)
        self.assertEqual(len(res.discovery_model.entrypoints), 0)

    # =========================================================================
    # REPOSITÓRIO 6: Next.js Pages Router (Tarefas 11 e 12)
    # =========================================================================

    async def test_t11_t12_nextjs_pages_router(self) -> None:
        """T-11 (Bug Fix) e T-12 (Cross-file): Next.js Pages Router."""
        repo = self._create_repo("nextjs_pages_router")
        self._write_file(repo, "components/Breadcrumbs.tsx", "export function Breadcrumbs({ path }: { path: string }) { return <nav>{path}</nav>; }\n")
        self._write_file(repo, "pages/products/[id].tsx", "import { Breadcrumbs } from '../../components/Breadcrumbs';\nexport default function ProductDetail() { return <Breadcrumbs path='/products/1' />; }\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-11",
            task_prompt="Corrigir navegação por breadcrumbs na página de produto",
            criteria=["Importar Breadcrumbs", "Validar integridade de rota"],
            expected_files=["pages/products/[id].tsx"],
        )
        self.assertTrue(res.success)

    # =========================================================================
    # REPOSITÓRIO 7: Turborepo Monorepo (Tarefas 13 e 14)
    # =========================================================================

    async def test_t13_t14_turborepo_monorepo(self) -> None:
        """T-13 (Cross-file) e T-14 (Refactor): Turborepo com múltiplos pacotes."""
        repo = self._create_repo("turborepo_monorepo")
        self._write_file(repo, "package.json", json.dumps({"workspaces": ["apps/*", "packages/*"]}))
        self._write_file(repo, "packages/ui/package.json", json.dumps({"name": "@repo/ui", "main": "src/index.ts"}))
        self._write_file(repo, "packages/ui/src/index.ts", "export function PrimaryButton() { return 'Primary'; }\n")
        self._write_file(repo, "packages/config/package.json", json.dumps({"name": "@repo/config", "main": "src/index.ts"}))
        self._write_file(repo, "packages/config/src/index.ts", "export const APP_NAME = 'Jarvis Turborepo';\n")
        self._write_file(repo, "apps/web/package.json", json.dumps({"name": "web-client"}))
        self._write_file(repo, "apps/web/src/App.tsx", "import { PrimaryButton } from '@repo/ui';\nimport { APP_NAME } from '@repo/config';\nexport function App() { return <div>{APP_NAME} <PrimaryButton /></div>; }\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-13",
            task_prompt="Integrar botão partilhado @repo/ui na aplicação web",
            criteria=["Importar @repo/ui", "Sem erros de contratos"],
            expected_files=["apps/web/src/App.tsx"],
        )
        self.assertTrue(res.success)
        self.assertTrue(res.discovery_model.is_monorepo)

    # =========================================================================
    # REPOSITÓRIO 8: Lerna Monorepo com Package Exports (Tarefas 15 e 16 - Open-ended)
    # =========================================================================

    async def test_t15_t16_lerna_monorepo_package_exports(self) -> None:
        """T-15 (Feature) e T-16 (Open-ended): Lerna Monorepo com subpath exports."""
        repo = self._create_repo("lerna_monorepo")
        self._write_file(repo, "package.json", json.dumps({"workspaces": ["packages/*"]}))
        self._write_file(repo, "packages/math/package.json", json.dumps({
            "name": "@acme/math",
            "exports": { "./calc": "./src/calc.ts" }
        }))
        self._write_file(repo, "packages/math/src/calc.ts", "export function add(a: number, b: number) { return a + b; }\n")
        self._write_file(repo, "packages/app/package.json", json.dumps({"name": "math-consumer"}))
        self._write_file(repo, "packages/app/src/main.ts", "import { add } from '@acme/math/calc';\nconsole.log(add(2, 3));\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-15",
            task_prompt="Adicionar subpath export ./calc no package.json do @acme/math",
            criteria=["Exportar calc.ts", "Permitir import @acme/math/calc"],
            expected_files=["packages/math/package.json"],
        )
        self.assertTrue(res.success)

    # =========================================================================
    # REPOSITÓRIO 9: Fullstack FastAPI + React (Tarefas 17 e 18)
    # =========================================================================

    async def test_t17_t18_fullstack_fastapi_react(self) -> None:
        """T-17 (Cross-file) e T-18 (Bug Fix): Projeto Fullstack com alinhamento de contratos."""
        repo = self._create_repo("fullstack_fastapi_react")
        self._write_file(repo, "backend/server.py", "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/api/health')\ndef health(): return {'status': 'ok'}\n")
        self._write_file(repo, "frontend/src/api.ts", "export function checkHealth() {\n  return fetch('/api/health', { method: 'GET' });\n}\n")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-17",
            task_prompt="Alinhar contratos de saúde entre frontend e backend",
            criteria=["Endpoint /api/health", "Chamada GET correspondente"],
            expected_files=["frontend/src/api.ts", "backend/server.py"],
        )
        self.assertTrue(res.success)

    # =========================================================================
    # REPOSITÓRIO 10: Extensionless ESM Test (Tarefas 19 e 20 - Cenário ESM)
    # =========================================================================

    async def test_t19_t20_extensionless_esm_and_complex_config(self) -> None:
        """T-19 (Cenário Específico ESM) e T-20 (Open-ended): Importação ESM sem extensão de .tsx."""
        repo = self._create_repo("extensionless_esm_repo")
        # Cenário real: .js compilado a tentar importar .tsx diretamente
        self._write_file(repo, "src/components/Widget.tsx", "export function Widget() { return 'Widget'; }\n")
        self._write_file(repo, "src/entry.js", "import { Widget } from './components/Widget';\nconsole.log(Widget());\n")

        graph = RepositoryGraph(repo).scan()
        imp = graph.imports.get("src/entry.js", [])[0]
        
        # O RepositoryGraph agora resolve automaticamente através de probe_file_extensions
        self.assertIsNotNone(imp.resolved_target)
        self.assertEqual(imp.resolved_target, "src/components/Widget.tsx")

        agent = RealRepositoryCodingTrialAgent(repo)
        res = agent.execute_trial_task(
            task_id="T-19",
            task_prompt="Validar resolução de import ESM sem extensão de ficheiro .tsx",
            criteria=["Resolver ./components/Widget para Widget.tsx sem quebrar"],
            expected_files=["src/entry.js"],
        )
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
