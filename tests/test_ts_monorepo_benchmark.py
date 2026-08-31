"""
JARVIS OS — Test Suite: TypeScript Path, Monorepo & Real Repository Benchmark (Fase 10.1)
Validação controlada (TSA-01 a TSA-10) e benchmark em 5 repositórios/estruturas representativas.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from intelligence.ast_repair_v2 import ASTRepairEngineV2
from intelligence.autonomous_repair_loop import AutonomousRepairLoop
from intelligence.cross_file_validator import ContractIssueType, CrossFileValidator
from intelligence.repository_graph import RepositoryGraph
from intelligence.tsconfig_resolver import MonorepoResolver, TSConfigResolver


class TestTSMonorepoBenchmark(unittest.IsolatedAsyncioTestCase):
    """Suíte oficial de testes para TypeScript Path Aliases, Monorepos e Barrel Files."""

    def setUp(self) -> None:
        self.test_root = tempfile.mkdtemp(prefix="jarvis_ts_bench_")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> str:
        abs_p = os.path.join(self.test_root, rel_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_p

    # =========================================================================
    # 1. CONTROLLED BENCHMARK: TSA-01 to TSA-10
    # =========================================================================

    async def test_tsa01_single_package_alias(self) -> None:
        """TSA-01: Resolução de alias único '@/components/*' mapeado para 'src/components/*'."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@/*": ["src/*"]
                }
            }
        }))
        self._create_file("src/components/Button.tsx", "export function Button() { return <button>Click</button>; }\n")
        self._create_file("src/views/Home.tsx", "import { Button } from '@/components/Button';\nexport function Home() { return <Button />; }\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertIn("src/views/Home.tsx", graph.files)
        
        # Verifica se o import foi resolvido
        imports = graph.imports.get("src/views/Home.tsx", [])
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].resolved_target, "src/components/Button.tsx")

        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)

    async def test_tsa02_multiple_aliases(self) -> None:
        """TSA-02: Resolução com múltiplos aliases configurados (@core/*, @ui/*, @api/*)."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": "./src",
                "paths": {
                    "@core/*": ["core/*"],
                    "@ui/*": ["components/*"],
                    "@api/*": ["services/*"]
                }
            }
        }))
        self._create_file("src/core/auth.ts", "export function getAuthToken(): string { return 'token-123'; }\n")
        self._create_file("src/components/Header.tsx", "export function Header() { return <header /> }\n")
        self._create_file("src/services/userApi.ts", "export function fetchUser() { return { name: 'Alice' }; }\n")
        self._create_file("src/App.tsx", """
import { getAuthToken } from '@core/auth';
import { Header } from '@ui/Header';
import { fetchUser } from '@api/userApi';

export function App() {
  return <Header />;
}
""")
        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)
        self.assertEqual(report.errors_count, 0)

    async def test_tsa03_tsconfig_extends_inheritance(self) -> None:
        """TSA-03: Herança de aliases através de 'extends' em tsconfig base."""
        self._create_file("tsconfig.base.json", json.dumps({
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@shared/*": ["packages/shared/src/*"]
                }
            }
        }))
        self._create_file("apps/web/tsconfig.json", json.dumps({
            "extends": "../../tsconfig.base.json",
            "compilerOptions": {
                "paths": {
                    "@/*": ["src/*"]
                }
            }
        }))
        self._create_file("packages/shared/src/utils.ts", "export function format(): string { return 'formatted'; }\n")
        self._create_file("apps/web/src/main.ts", "import { format } from '@shared/utils';\nconsole.log(format());\n")

        graph = RepositoryGraph(self.test_root).scan()
        imports = graph.imports.get("apps/web/src/main.ts", [])
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].resolved_target, "packages/shared/src/utils.ts")

    async def test_tsa04_workspace_package_resolution(self) -> None:
        """TSA-04: Resolução de pacote NPM Workspace em monorepo (@myorg/ui -> packages/ui)."""
        self._create_file("package.json", json.dumps({
            "name": "monorepo-root",
            "workspaces": ["packages/*", "apps/*"]
        }))
        self._create_file("packages/ui/package.json", json.dumps({
            "name": "@myorg/ui",
            "main": "src/index.ts"
        }))
        self._create_file("packages/ui/src/index.ts", "export function Card() { return 'Card'; }\n")
        self._create_file("apps/web/package.json", json.dumps({
            "name": "web-app"
        }))
        self._create_file("apps/web/src/index.ts", "import { Card } from '@myorg/ui';\nconsole.log(Card());\n")

        graph = RepositoryGraph(self.test_root).scan()
        imports = graph.imports.get("apps/web/src/index.ts", [])
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].resolved_target, "packages/ui/src/index.ts")

    async def test_tsa05_barrel_exports_propagation(self) -> None:
        """TSA-05: Rastreamento transparente através de index.ts com export * from './Component'."""
        self._create_file("src/components/Button.tsx", "export function Button() { return '<button />'; }\n")
        self._create_file("src/components/Modal.tsx", "export function Modal() { return '<dialog />'; }\n")
        self._create_file("src/components/index.ts", "export * from './Button';\nexport * from './Modal';\n")
        self._create_file("src/App.tsx", "import { Button, Modal } from './components';\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)

    async def test_tsa06_package_subpath_exports(self) -> None:
        """TSA-06: Resolução de subpath exports definidos no campo 'exports' do package.json."""
        self._create_file("packages/core/package.json", json.dumps({
            "name": "@acme/core",
            "exports": {
                "./logger": "./src/logger.ts",
                "./math": "./src/math.ts"
            }
        }))
        self._create_file("packages/core/src/logger.ts", "export function log(msg: string) { console.log(msg); }\n")
        self._create_file("apps/server/src/app.ts", "import { log } from '@acme/core/logger';\nlog('App started');\n")

        graph = RepositoryGraph(self.test_root).scan()
        imports = graph.imports.get("apps/server/src/app.ts", [])
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].resolved_target, "packages/core/src/logger.ts")

    async def test_tsa07_project_references_discovery(self) -> None:
        """TSA-07: Descoberta de referências de projeto TypeScript (tsconfig references)."""
        self._create_file("packages/shared/tsconfig.json", json.dumps({
            "compilerOptions": { "composite": True }
        }))
        self._create_file("apps/client/tsconfig.json", json.dumps({
            "references": [{ "path": "../../packages/shared" }]
        }))

        graph = RepositoryGraph(self.test_root).scan()
        client_ts = graph.tsconfigs.get("apps/client/tsconfig.json")
        self.assertIsNotNone(client_ts)
        self.assertIn("../../packages/shared", client_ts.references)

    async def test_tsa08_circular_dependency_detection(self) -> None:
        """TSA-08: Deteção determinística de dependências circulares A -> B -> C -> A."""
        self._create_file("src/moduleA.ts", "import { bFunc } from './moduleB';\nexport function aFunc() { return bFunc(); }\n")
        self._create_file("src/moduleB.ts", "import { cFunc } from './moduleC';\nexport function bFunc() { return cFunc(); }\n")
        self._create_file("src/moduleC.ts", "import { aFunc } from './moduleA';\nexport function cFunc() { return aFunc(); }\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertGreater(len(graph.circular_dependencies), 0)

        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertGreater(len(report.circular_dependencies), 0)
        self.assertEqual(report.circular_dependencies[0].issue_type, ContractIssueType.CIRCULAR_DEPENDENCY.value)

    async def test_tsa09_invalid_path_alias_detection_and_repair(self) -> None:
        """TSA-09: Deteção de alias inválido e reparação determinística via ASTRepairEngineV2."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@/*": ["src/*"]
                }
            }
        }))
        self._create_file("src/components/Badge.tsx", "export function Badge() { return 'badge'; }\n")
        # Alias inválido: '@components/Badge' em vez de '@/components/Badge'
        self._create_file("src/views/Profile.tsx", "import { Badge } from '@components/Badge';\nexport function Profile() { return <Badge />; }\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertFalse(report.is_valid)

        # Reparação
        engine = ASTRepairEngineV2(graph)
        with open(os.path.join(self.test_root, "src/views/Profile.tsx"), "r") as f:
            content = f.read()
        res = engine.repair_invalid_path_alias(content, "@components/Badge", "src/views/Profile.tsx")
        self.assertTrue(res.success)
        self.assertIn("from '@/components/Badge'", res.repaired_content)

    async def test_tsa10_multi_package_monorepo_repair(self) -> None:
        """TSA-10: Reparação autónoma multi-pacote em monorepo com import quebrado."""
        self._create_file("package.json", json.dumps({ "workspaces": ["packages/*", "apps/*"] }))
        self._create_file("packages/data/package.json", json.dumps({ "name": "@acme/data", "main": "src/index.ts" }))
        self._create_file("packages/data/src/index.ts", "export function queryDatabase(): string[] { return ['item1']; }\n")
        self._create_file("apps/api/package.json", json.dumps({ "name": "api-app" }))
        self._create_file("apps/api/src/server.ts", "import { queryDatabase } from '@acme/data';\nconsole.log(queryDatabase());\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    # =========================================================================
    # 2. REAL REPOSITORY BENCHMARK (5 Repositórios / Estruturas Representativas)
    # =========================================================================

    async def test_rr01_nextjs_app_router_discovery_and_feature_add(self) -> None:
        """RR-01: Repositório estilo Next.js App Router com @/* aliases e rotas de API."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": ".",
                "paths": { "@/*": ["*"] }
            }
        }))
        self._create_file("app/api/tasks/route.ts", "export async function GET() { return []; }\n")
        self._create_file("components/TaskList.tsx", "import { useEffect } from 'react';\nexport function TaskList() { return <div>Tasks</div>; }\n")
        self._create_file("app/page.tsx", "import { TaskList } from '@/components/TaskList';\nexport default function Page() { return <TaskList />; }\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)
        self.assertEqual(len(graph.endpoints), 1)

    async def test_rr02_turborepo_workspace_full_resolution(self) -> None:
        """RR-02: Estrutura Turborepo com apps/web, packages/ui e packages/config."""
        self._create_file("package.json", json.dumps({ "workspaces": ["apps/*", "packages/*"] }))
        self._create_file("packages/ui/package.json", json.dumps({ "name": "@repo/ui", "main": "src/index.tsx" }))
        self._create_file("packages/ui/src/index.tsx", "export function Button() { return 'Button'; }\n")
        self._create_file("apps/web/package.json", json.dumps({ "name": "web" }))
        self._create_file("apps/web/src/App.tsx", "import { Button } from '@repo/ui';\nexport function App() { return <Button />; }\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertIn("@repo/ui", graph.monorepo_packages)
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_rr03_component_library_with_deep_barrel_files(self) -> None:
        """RR-03: Biblioteca de componentes com múltiplos níveis de barrel files."""
        self._create_file("src/primitives/Button.tsx", "export function Button() { return null; }\n")
        self._create_file("src/primitives/Input.tsx", "export function Input() { return null; }\n")
        self._create_file("src/primitives/index.ts", "export * from './Button';\nexport * from './Input';\n")
        self._create_file("src/index.ts", "export * from './primitives';\n")
        self._create_file("src/demo.ts", "import { Button, Input } from './index';\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_rr04_nestjs_backend_modules_and_dtos(self) -> None:
        """RR-04: Estrutura backend estilo NestJS com aliases @modules/* e @common/*."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": "./src",
                "paths": {
                    "@modules/*": ["modules/*"],
                    "@common/*": ["common/*"]
                }
            }
        }))
        self._create_file("src/common/dto/create-user.dto.ts", "export class CreateUserDto { name: string = ''; }\n")
        self._create_file("src/modules/users/users.service.ts", "import { CreateUserDto } from '@common/dto/create-user.dto';\nexport class UsersService { create(dto: CreateUserDto) {} }\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_rr05_fullstack_shared_contracts_resolution(self) -> None:
        """RR-05: Aplicação Fullstack com contratos de tipos partilhados entre backend e frontend."""
        self._create_file("tsconfig.json", json.dumps({
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@shared/*": ["shared/*"]
                }
            }
        }))
        self._create_file("shared/contracts/user.ts", "export interface UserContract { id: string; email: string; }\n")
        self._create_file("backend/api.ts", "import { UserContract } from '@shared/contracts/user';\nexport function getUser(): UserContract { return { id: '1', email: 'a@b.com' }; }\n")
        self._create_file("frontend/client.ts", "import { UserContract } from '@shared/contracts/user';\nexport function renderUser(u: UserContract) {}\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)


if __name__ == "__main__":
    unittest.main()
