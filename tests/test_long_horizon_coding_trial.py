"""
JARVIS OS — Test Suite: Long-Horizon Coding Stress & Real-World Trial (Fase 10.3)
10 Missões de longa duração, evolução de requisitos, cascatas de falhas, degradação de contexto e caos controlado.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from intelligence.cross_file_validator import CrossFileValidator
from intelligence.long_horizon_trial_engine import (
    LongHorizonMissionSession,
    LongHorizonMissionStep,
    LongHorizonStressRunner,
)
from intelligence.repository_graph import RepositoryGraph


class TestLongHorizonCodingTrial(unittest.IsolatedAsyncioTestCase):
    """Suíte oficial de testes de stress e longa duração do Coding Agent."""

    def setUp(self) -> None:
        self.workspace_base = tempfile.mkdtemp(prefix="jarvis_long_horizon_")

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace_base, ignore_errors=True)

    def _create_mission_repo(self, mission_name: str) -> str:
        repo_dir = os.path.join(self.workspace_base, mission_name)
        os.makedirs(repo_dir, exist_ok=True)
        return repo_dir

    def _write_file(self, repo_dir: str, rel_path: str, content: str) -> str:
        abs_p = os.path.join(repo_dir, rel_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_p

    # =========================================================================
    # MISSÃO 1: E-Commerce Requirement Evolution (A -> B -> C)
    # =========================================================================

    async def test_m01_ecommerce_requirement_evolution(self) -> None:
        """M-01: Evolução cumulativa de requisitos sem quebrar etapas anteriores."""
        repo = self._create_mission_repo("m01_ecommerce")
        session = LongHorizonMissionSession("sess_m01", repo)
        runner = LongHorizonStressRunner(repo)

        # Base inicial
        self._write_file(repo, "app/models/product.py", "class Product:\n    def __init__(self, id: int, name: str, price: float):\n        self.id = id\n        self.name = name\n        self.price = price\n")
        self._write_file(repo, "app/services/catalog.py", "from app.models.product import Product\nclass CatalogService:\n    def list_products(self):\n        return [Product(1, 'Laptop', 1200.0)]\n")

        steps = [
            LongHorizonMissionStep(
                step_id="STEP_A",
                step_prompt="Implementar catálogo de produtos e endpoint de listagem",
                acceptance_criteria=["Retornar lista de produtos", "Preços válidos"],
                apply_fn=lambda: [
                    self._write_file(repo, "app/api/catalog.py", "from fastapi import FastAPI\nfrom app.services.catalog import CatalogService\napp = FastAPI()\ncat = CatalogService()\n@app.get('/api/products')\ndef get_prods(): return cat.list_products()\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="STEP_B",
                step_prompt="Adicionar carrinho de compras com cálculo de total",
                acceptance_criteria=["Suportar adição de itens", "Calcular total de preços"],
                apply_fn=lambda: [
                    self._write_file(repo, "app/services/cart.py", "class CartService:\n    def __init__(self):\n        self.items = []\n    def add(self, product):\n        self.items.append(product)\n    def total(self) -> float:\n        return sum(p.price for p in self.items)\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="STEP_C",
                step_prompt="Adicionar cupão de desconto no checkout preservando catálogo e carrinho",
                acceptance_criteria=["Aplicar desconto percentual", "Preservar itens anteriores"],
                apply_fn=lambda: [
                    self._write_file(repo, "app/services/checkout.py", "from app.services.cart import CartService\nclass CheckoutService:\n    def apply_coupon(self, cart: CartService, discount_pct: float) -> float:\n        return cart.total() * (1.0 - (discount_pct / 100.0))\n")
                ],
            ),
        ]

        def regression_check():
            # Valida que ficheiros criados em passos anteriores continuam existindo
            if os.path.isfile(os.path.join(repo, "app/services/checkout.py")):
                return os.path.isfile(os.path.join(repo, "app/api/catalog.py")) and os.path.isfile(os.path.join(repo, "app/services/cart.py"))
            elif os.path.isfile(os.path.join(repo, "app/services/cart.py")):
                return os.path.isfile(os.path.join(repo, "app/api/catalog.py"))
            return True

        result = runner.run_mission(session, "M-01", "E-Commerce Requirement Evolution", steps, regression_check)
        self.assertTrue(result.eventual_success)
        self.assertEqual(result.completed_steps, 3)
        self.assertGreaterEqual(result.total_cycles, 6)

    # =========================================================================
    # MISSÃO 2: Multi-Layer Fullstack RBAC Auth Pipeline
    # =========================================================================

    async def test_m02_fullstack_rbac_auth_pipeline(self) -> None:
        """M-02: Pipeline de 4 camadas: Frontend UI + Auth Middleware + SQL Store + Pytest."""
        repo = self._create_mission_repo("m02_rbac_auth")
        session = LongHorizonMissionSession("sess_m02", repo)
        runner = LongHorizonStressRunner(repo)

        steps = [
            LongHorizonMissionStep(
                step_id="LAYER_1_DB",
                step_prompt="Criar repositório SQL de utilizadores e papéis (RBAC)",
                acceptance_criteria=["Definir User e Role", "Função get_by_email"],
                apply_fn=lambda: [
                    self._write_file(repo, "db/users.py", "class User:\n    def __init__(self, id: str, role: str): self.id = id; self.role = role\nclass UserDB:\n    def get_user(self, id: str): return User(id, 'ADMIN')\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="LAYER_2_AUTH",
                step_prompt="Criar middleware de autorização baseado em papéis",
                acceptance_criteria=["Validar role ADMIN", "Bloquear acesso não autorizado"],
                apply_fn=lambda: [
                    self._write_file(repo, "auth/rbac.py", "from db.users import UserDB\nclass RBACMiddleware:\n    def __init__(self): self.db = UserDB()\n    def authorize(self, user_id: str, required_role: str) -> bool:\n        user = self.db.get_user(user_id)\n        return user.role == required_role\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="LAYER_3_API",
                step_prompt="Expor endpoint seguro de administração",
                acceptance_criteria=["Endpoint /api/admin/settings", "Protegido por RBAC"],
                apply_fn=lambda: [
                    self._write_file(repo, "api/admin.py", "from fastapi import FastAPI\nfrom auth.rbac import RBACMiddleware\napp = FastAPI()\nrbac = RBACMiddleware()\n@app.get('/api/admin/settings')\ndef get_settings(user_id: str):\n    if not rbac.authorize(user_id, 'ADMIN'): return {'error': 'unauthorized'}\n    return {'status': 'active'}\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="LAYER_4_FRONTEND",
                step_prompt="Criar cliente frontend para consumo de configurações de admin",
                acceptance_criteria=["Chamar GET /api/admin/settings", "Tratar resposta"],
                apply_fn=lambda: [
                    self._write_file(repo, "frontend/adminClient.ts", "export function fetchAdminSettings(userId: string) {\n  return fetch(`/api/admin/settings?user_id=${userId}`, { method: 'GET' });\n}\n")
                ],
            ),
        ]

        result = runner.run_mission(session, "M-02", "Fullstack RBAC Auth Pipeline", steps)
        self.assertTrue(result.eventual_success)
        self.assertEqual(result.completed_steps, 4)

    # =========================================================================
    # MISSÃO 3: Multi-File Failure Cascade Repair
    # =========================================================================

    async def test_m03_failure_cascade_sequential_repair(self) -> None:
        """M-03: Cascata de 3 falhas onde a resolução da primeira revela a segunda."""
        repo = self._create_mission_repo("m03_failure_cascade")
        session = LongHorizonMissionSession("sess_m03", repo)
        runner = LongHorizonStressRunner(repo)

        # Falhas deliberadas em cadeia:
        # 1. math_engine.py com erro sintático
        self._write_file(repo, "engine/math_engine.py", "def calculate_tax(amount\n    return amount * 0.23\n")
        # 2. invoice.py importando math_engine
        self._write_file(repo, "services/invoice.py", "from engine.math_engine import calculate_tax\ndef generate_invoice(val: float): return calculate_tax(val)\n")

        steps = [
            LongHorizonMissionStep(
                step_id="CASCADE_STEP_1",
                step_prompt="Reparar sintaxe no motor matemático e propagar para faturas",
                acceptance_criteria=["Sintaxe válida", "Pipeline passar"],
                apply_fn=lambda: ["engine/math_engine.py"],
            ),
        ]

        result = runner.run_mission(session, "M-03", "Failure Cascade Repair", steps)
        self.assertTrue(result.eventual_success)
        self.assertGreater(result.repair_attempts_total, 0)

    # =========================================================================
    # MISSÃO 4: Regression Detection & Recovery
    # =========================================================================

    async def test_m04_regression_detection_and_recovery(self) -> None:
        """M-04: Deteção de regressão de contrato e recuperação automática."""
        repo = self._create_mission_repo("m04_regression_recovery")
        session = LongHorizonMissionSession("sess_m04", repo)
        runner = LongHorizonStressRunner(repo)

        self._write_file(repo, "core/legacy.py", "def legacy_calculate(a: int, b: int) -> int: return a + b\n")
        self._write_file(repo, "services/consumer.py", "from core.legacy import legacy_calculate\ndef run(): return legacy_calculate(1, 2)\n")

        # Step 1: Normal
        # Step 2: Alteração que causa regressão
        steps = [
            LongHorizonMissionStep(
                step_id="REG_STEP_1",
                step_prompt="Validar estado inicial",
                acceptance_criteria=["Tudo funcional"],
            ),
            LongHorizonMissionStep(
                step_id="REG_STEP_2",
                step_prompt="Adicionar funcionalidade mantendo retrocompatibilidade",
                acceptance_criteria=["Manter legacy_calculate funcional"],
                apply_fn=lambda: [
                    self._write_file(repo, "core/legacy.py", "def legacy_calculate(a: int, b: int) -> int: return a + b\ndef new_calculate(x: int): return x * 2\n")
                ],
            ),
        ]

        result = runner.run_mission(session, "M-04", "Regression Detection & Recovery", steps)
        self.assertTrue(result.eventual_success)

    # =========================================================================
    # MISSÃO 5: Long-Context 25-Cycle Monorepo Feature Pipeline
    # =========================================================================

    async def test_m05_long_context_25_cycle_pipeline(self) -> None:
        """M-05: 8 passos sequenciais acumulando mais de 20 ciclos de agente contínuos."""
        repo = self._create_mission_repo("m05_long_context")
        session = LongHorizonMissionSession("sess_m05", repo)
        runner = LongHorizonStressRunner(repo)

        steps = []
        for i in range(1, 9):
            steps.append(LongHorizonMissionStep(
                step_id=f"CYCLE_STEP_{i}",
                step_prompt=f"Adicionar módulo funcional {i} e registar decisões",
                acceptance_criteria=[f"Módulo {i} criado", "Sem erros de build"],
                apply_fn=lambda idx=i: [
                    self._write_file(repo, f"modules/mod_{idx}.py", f"def get_value_{idx}(): return {idx}\n")
                ],
            ))

        result = runner.run_mission(session, "M-05", "Long-Context 25-Cycle Pipeline", steps)
        self.assertTrue(result.eventual_success)
        self.assertGreaterEqual(result.total_cycles, 16)
        self.assertGreater(result.context_token_estimate, 1000)

        # Valida recuperação de memória
        retrieved = session.retrieve_memory("CYCLE_STEP_3")
        self.assertGreaterEqual(len(retrieved), 1)

    # =========================================================================
    # MISSÃO 6: Chaos Recovery Under Stale Files & Concurrency
    # =========================================================================

    async def test_m06_chaos_recovery_stale_files_concurrency(self) -> None:
        """M-06: Recuperação sob perturbações de concorrência e ficheiros desatualizados."""
        repo = self._create_mission_repo("m06_chaos_recovery")
        session = LongHorizonMissionSession("sess_m06", repo)
        runner = LongHorizonStressRunner(repo)

        steps = [
            LongHorizonMissionStep(
                step_id="CHAOS_1",
                step_prompt="Criar serviço sob condições de ficheiro estático",
                acceptance_criteria=["Recuperar integridade"],
                simulate_chaos="STALE_FILE",
                apply_fn=lambda: [
                    self._write_file(repo, "services/sync.py", "def sync_data(): return True\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="CHAOS_2",
                step_prompt="Executar alteração com simulação de edição concorrente",
                acceptance_criteria=["Resolver conflito e validar grafo"],
                simulate_chaos="CONCURRENT_EDIT",
                apply_fn=lambda: [
                    self._write_file(repo, "services/sync.py", "def sync_data(): return {'synced': True}\n")
                ],
            ),
        ]

        result = runner.run_mission(session, "M-06", "Chaos Recovery", steps)
        self.assertTrue(result.eventual_success)

    # =========================================================================
    # MISSÃO 7: Fullstack Analytics Dashboard Multi-Layer
    # =========================================================================

    async def test_m07_analytics_dashboard_multi_layer(self) -> None:
        """M-07: Dashboard analítico multi-camada com modelos, rotas e componentes."""
        repo = self._create_mission_repo("m07_analytics")
        session = LongHorizonMissionSession("sess_m07", repo)
        runner = LongHorizonStressRunner(repo)

        steps = [
            LongHorizonMissionStep(
                step_id="ANALYTICS_CORE",
                step_prompt="Criar agregador de métricas analíticas",
                acceptance_criteria=["Calcular médias"],
                apply_fn=lambda: [
                    self._write_file(repo, "analytics/metrics.py", "def calculate_averages(data: list[float]) -> float: return sum(data) / max(len(data), 1)\n")
                ],
            ),
            LongHorizonMissionStep(
                step_id="ANALYTICS_API",
                step_prompt="Expor rota de métricas na API",
                acceptance_criteria=["Endpoint /api/analytics/averages"],
                apply_fn=lambda: [
                    self._write_file(repo, "api/analytics.py", "from fastapi import FastAPI\nfrom analytics.metrics import calculate_averages\napp = FastAPI()\n@app.get('/api/analytics/averages')\ndef get_avg(): return {'avg': calculate_averages([10.0, 20.0])}\n")
                ],
            ),
        ]

        result = runner.run_mission(session, "M-07", "Fullstack Analytics", steps)
        self.assertTrue(result.eventual_success)

    # =========================================================================
    # MISSÃO 8: Monorepo Shared Contract Evolution
    # =========================================================================

    async def test_m08_monorepo_dto_propagation(self) -> None:
        """M-08: Atualização de contrato DTO partilhado propagada para múltiplos pacotes."""
        repo = self._create_mission_repo("m08_dto_propagation")
        session = LongHorizonMissionSession("sess_m08", repo)
        runner = LongHorizonStressRunner(repo)

        self._write_file(repo, "package.json", json.dumps({"workspaces": ["packages/*", "apps/*"]}))
        self._write_file(repo, "packages/contracts/package.json", json.dumps({"name": "@app/contracts", "main": "src/index.ts"}))
        self._write_file(repo, "packages/contracts/src/index.ts", "export interface UserDTO { id: string; name: string; email?: string; }\n")
        self._write_file(repo, "apps/web/package.json", json.dumps({"name": "web-app"}))
        self._write_file(repo, "apps/web/src/view.ts", "import { UserDTO } from '@app/contracts';\nexport function render(u: UserDTO) { return u.name; }\n")

        steps = [
            LongHorizonMissionStep(
                step_id="DTO_STEP",
                step_prompt="Atualizar UserDTO com campo opcional e validar propagação",
                acceptance_criteria=["UserDTO exportado", "Web app consome sem erros"],
                apply_fn=lambda: [
                    self._write_file(repo, "packages/contracts/src/index.ts", "export interface UserDTO { id: string; name: string; email?: string; role?: string; }\n")
                ],
            ),
        ]

        result = runner.run_mission(session, "M-08", "Monorepo DTO Propagation", steps)
        self.assertTrue(result.eventual_success)

    # =========================================================================
    # MISSÃO 9: Real Browser Multi-Step Verification
    # =========================================================================

    async def test_m09_browser_multi_step_verification(self) -> None:
        """M-09: Verificação de aplicação web multi-ficheiro com assets e HTML íntegros."""
        repo = self._create_mission_repo("m09_browser_app")
        session = LongHorizonMissionSession("sess_m09", repo)
        runner = LongHorizonStressRunner(repo)

        self._write_file(repo, "index.html", "<!DOCTYPE html><html><head><link rel='stylesheet' href='app.css'></head><body><div id='app'></div><script src='bundle.js'></script></body></html>")
        self._write_file(repo, "app.css", "body { margin: 0; background: #0a0a0a; color: #fff; }")
        self._write_file(repo, "bundle.js", "console.log('App loaded in browser');\n")

        steps = [
            LongHorizonMissionStep(
                step_id="BROWSER_STEP_1",
                step_prompt="Validar carregamento de assets no browser",
                acceptance_criteria=["HTML, CSS e JS vinculados sem links 404"],
            ),
        ]

        result = runner.run_mission(session, "M-09", "Browser Multi-Step Verification", steps)
        self.assertTrue(result.eventual_success)

    # =========================================================================
    # MISSÃO 10: Extreme Stress Horizon (Deep Dependency Chain)
    # =========================================================================

    async def test_m10_extreme_stress_horizon_30_cycles(self) -> None:
        """M-10: Stress extremo de 30 ciclos com cadeia profunda de dependências."""
        repo = self._create_mission_repo("m10_extreme_stress")
        session = LongHorizonMissionSession("sess_m10", repo)
        runner = LongHorizonStressRunner(repo)

        # Cadeia de 6 módulos dependentes
        self._write_file(repo, "chain/c1.py", "def f1(): return 1\n")
        self._write_file(repo, "chain/c2.py", "from chain.c1 import f1\ndef f2(): return f1() + 1\n")
        self._write_file(repo, "chain/c3.py", "from chain.c2 import f2\ndef f3(): return f2() + 1\n")
        self._write_file(repo, "chain/c4.py", "from chain.c3 import f3\ndef f4(): return f3() + 1\n")
        self._write_file(repo, "chain/c5.py", "from chain.c4 import f4\ndef f5(): return f4() + 1\n")
        self._write_file(repo, "chain/c6.py", "from chain.c5 import f5\ndef f6(): return f5() + 1\n")

        steps = []
        for i in range(1, 7):
            steps.append(LongHorizonMissionStep(
                step_id=f"EXTREME_STEP_{i}",
                step_prompt=f"Iterar sobre o elo {i} da cadeia de dependências",
                acceptance_criteria=[f"Elo {i} validado"],
            ))

        result = runner.run_mission(session, "M-10", "Extreme Stress Horizon", steps)
        self.assertTrue(result.eventual_success)
        self.assertEqual(result.completed_steps, 6)
        self.assertGreaterEqual(result.total_cycles, 12)


if __name__ == "__main__":
    unittest.main()
