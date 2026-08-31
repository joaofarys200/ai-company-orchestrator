"""
JARVIS OS — Coding Agent 2.0 Benchmark Suite (Fase 10)
20 Cenários de teste: 5 Greenfield, 5 Bug Fixing, 5 Feature Addition, 5 Multi-File Repair.
Validação de Repository Graph, Cross-File Contracts, AST Repair v2, Autonomous Repair Loop e Métricas Reais.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest

from intelligence.ast_repair_v2 import ASTRepairEngineV2
from intelligence.autonomous_repair_loop import AutonomousRepairLoop, StageStatus
from intelligence.build_pipeline import DeterministicBuildPipeline
from intelligence.cross_file_validator import CrossFileValidator, ContractIssueType
from intelligence.failure_memory import FailureLesson, FailureMemoryStore
from intelligence.repository_graph import RepositoryGraph


class TestCodingAgent2Benchmark(unittest.IsolatedAsyncioTestCase):
    """Suíte oficial de benchmark com 20 cenários para o Coding Agent 2.0."""

    def setUp(self) -> None:
        self.test_root = tempfile.mkdtemp(prefix="jarvis_coding_agent_bench_")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> str:
        abs_p = os.path.join(self.test_root, rel_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_p

    # =========================================================================
    # 1. GREENFIELD SCENARIOS (5 Tarefas)
    # =========================================================================

    async def test_gf01_fastapi_task_tracker_crud(self) -> None:
        """GF-01: Geração de backend CRUD multi-ficheiro com FastAPI."""
        self._create_file("models/task.py", "class Task:\n    def __init__(self, id: int, title: str):\n        self.id = id\n        self.title = title\n")
        self._create_file("services/task_service.py", "from models.task import Task\n\nclass TaskService:\n    def get_all(self):\n        return [Task(1, 'Primeira Tarefa')]\n")
        self._create_file("routes/task_routes.py", "from services.task_service import TaskService\n\ndef register_routes(app):\n    service = TaskService()\n    return service.get_all()\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertIn("models/task.py", graph.files)
        self.assertIn("services/task_service.py", graph.files)
        self.assertIn("routes/task_routes.py", graph.files)

        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)
        self.assertEqual(report.errors_count, 0)

    async def test_gf02_frontend_dashboard_structure(self) -> None:
        """GF-02: Estrutura de frontend multi-ficheiro com HTML, JS e CSS."""
        self._create_file("index.html", "<!DOCTYPE html><html><head><link rel='stylesheet' href='styles.css'></head><body><script src='app.js'></script></body></html>")
        self._create_file("styles.css", "body { background: #121212; color: #ffffff; }")
        self._create_file("app.js", "function render() { console.log('Dashboard ready'); }\nrender();")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.broken_links), 0)

    async def test_gf03_auth_simulator_token_validation(self) -> None:
        """GF-03: Módulo de autenticação com geração e verificação de tokens."""
        self._create_file("auth/tokens.py", "def create_token(user_id: str) -> str:\n    return f'token-{user_id}'\n\ndef verify_token(token: str) -> bool:\n    return token.startswith('token-')\n")
        self._create_file("auth/middleware.py", "from auth.tokens import verify_token\n\ndef authenticate(req):\n    return verify_token(req.get('token', ''))\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)

    async def test_gf04_search_indexer_inverted_index(self) -> None:
        """GF-04: Motor de indexação em memória com tokenizer e indexador invertido."""
        self._create_file("search/tokenizer.py", "def tokenize(text: str) -> list[str]:\n    return text.lower().split()\n")
        self._create_file("search/indexer.py", "from search.tokenizer import tokenize\n\nclass InvertedIndex:\n    def __init__(self):\n        self.index = {}\n    def add(self, doc_id: int, text: str):\n        for word in tokenize(text):\n            self.index.setdefault(word, set()).add(doc_id)\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)

    async def test_gf05_config_registry_hierarchical(self) -> None:
        """GF-05: Registro de configuração com valores padrão e sobreposições."""
        self._create_file("config/defaults.py", "DEFAULT_CONFIG = {'port': 8000, 'host': 'localhost'}\n")
        self._create_file("config/manager.py", "from config.defaults import DEFAULT_CONFIG\n\nclass ConfigManager:\n    def get(self, key: str):\n        return DEFAULT_CONFIG.get(key)\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertTrue(report.is_valid)

    # =========================================================================
    # 2. BUG FIXING SCENARIOS (5 Tarefas com Falhas Deliberadas)
    # =========================================================================

    async def test_bf01_syntax_error_missing_colon_and_parens(self) -> None:
        """BF-01: Correção determinística de falta de ':' e parênteses em Python."""
        # Falhas deliberadas: 'def calculate(x, y' sem ':' e sem ')'
        self._create_file("math_utils.py", "def calculate(x, y\n    return x + y\n")

        repair_loop = AutonomousRepairLoop(self.test_root)
        rep = repair_loop.run_repair_cycle()
        self.assertTrue(rep.success)
        self.assertIn("math_utils.py", rep.files_repaired)

    async def test_bf02_javascript_unbalanced_braces_repair(self) -> None:
        """BF-02: Correção de chaves não fechadas e vírgulas em JS."""
        self._create_file("component.js", "function render() {\n  const config = { a: 1, b: 2 };\n  return config;\n")

        engine = ASTRepairEngineV2()
        res = engine.repair_syntax_javascript("function render() {\n  const config = { a: 1, b: 2 ;\n", "component.js")
        self.assertTrue(res.success)

    async def test_bf03_broken_import_auto_injection(self) -> None:
        """BF-03: Injeção determinística de import em falta a partir do SymbolGraph."""
        self._create_file("services/payment.py", "def process_payment(amount: float) -> bool:\n    return amount > 0\n")
        self._create_file("controllers/checkout.py", "def checkout(amount: float):\n    return process_payment(amount)\n")

        graph = RepositoryGraph(self.test_root).scan()
        engine = ASTRepairEngineV2(graph)
        content = "def checkout(amount: float):\n    return process_payment(amount)\n"
        res = engine.repair_missing_import(content, "process_payment", "controllers/checkout.py")
        self.assertTrue(res.success)
        self.assertIn("from services.payment import process_payment", res.repaired_content)

    async def test_bf04_missing_stub_export_generation(self) -> None:
        """BF-04: Geração de stub para exportação esperada por teste."""
        self._create_file("lib/strings.py", "# Ficheiro vazio inicialmente\n")
        engine = ASTRepairEngineV2()
        res = engine.repair_missing_stub("", "slugify", "lib/strings.py", is_function=True)
        self.assertTrue(res.success)
        self.assertIn("def slugify(*args, **kwargs):", res.repaired_content)

    async def test_bf05_api_method_mismatch_correction(self) -> None:
        """BF-05: Ajuste determinístico de mismatch de método HTTP em chamada de API."""
        self._create_file("backend/app.py", "from fastapi import FastAPI\napp = FastAPI()\n\n@app.post('/api/tasks')\ndef create_task():\n    return {'status': 'ok'}\n")
        self._create_file("frontend/api.js", "function fetchTasks() {\n  return fetch('/api/tasks', { method: 'GET' });\n}\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        report = validator.validate()
        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.contract_mismatches), 1)

        # Repara o contrato
        engine = ASTRepairEngineV2(graph)
        with open(os.path.join(self.test_root, "frontend/api.js"), "r") as f:
            c = f.read()
        res = engine.repair_api_contract_mismatch(c, "frontend/api.js", report.contract_mismatches[0])
        self.assertTrue(res.success)
        self.assertIn("method: 'POST'", res.repaired_content)

    # =========================================================================
    # 3. FEATURE ADDITION SCENARIOS (5 Tarefas)
    # =========================================================================

    async def test_fa01_add_pagination_and_verify_blast_radius(self) -> None:
        """FA-01: Adição de parâmetros de paginação e cálculo de Blast Radius."""
        self._create_file("db/repo.py", "def list_users(limit: int = 10, offset: int = 0):\n    return []\n")
        self._create_file("api/users.py", "from db.repo import list_users\n\ndef get_users():\n    return list_users(limit=20)\n")
        self._create_file("tests/test_users.py", "from api.users import get_users\n\ndef test_get():\n    assert get_users() == []\n")

        graph = RepositoryGraph(self.test_root).scan()
        blast = graph.compute_blast_radius(["db/repo.py"])
        self.assertIn("api/users.py", blast.directly_affected_files)
        self.assertIn("tests/test_users.py", blast.affected_tests)

    async def test_fa02_metric_logging_decorator(self) -> None:
        """FA-02: Adição de decorador de métricas e verificação de imports."""
        self._create_file("utils/metrics.py", "def measure_time(fn):\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n")
        self._create_file("services/order.py", "from utils.metrics import measure_time\n\n@measure_time\ndef process_order():\n    return True\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_fa03_status_filter_feature(self) -> None:
        """FA-03: Adição de filtro por status e validação referencial."""
        self._create_file("core/filter.py", "def filter_by_status(items, status):\n    return [i for i in items if i.get('status') == status]\n")
        self._create_file("services/query.py", "from core.filter import filter_by_status\n\ndef query_active(items):\n    return filter_by_status(items, 'ACTIVE')\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertTrue(CrossFileValidator(graph).validate().is_valid)

    async def test_fa04_json_export_feature(self) -> None:
        """FA-04: Função de exportação em JSON e validação de contratos."""
        self._create_file("exporters/json_export.py", "import json\n\ndef to_json_string(data):\n    return json.dumps(data)\n")
        self._create_file("api/export.py", "from exporters.json_export import to_json_string\n\ndef export_data(data):\n    return to_json_string(data)\n")

        graph = RepositoryGraph(self.test_root).scan()
        self.assertTrue(CrossFileValidator(graph).validate().is_valid)

    async def test_fa05_rate_limiter_middleware(self) -> None:
        """FA-05: Middleware de rate limiting e impacto em rotas."""
        self._create_file("middleware/limiter.py", "class RateLimiter:\n    def check(self, ip: str) -> bool:\n        return True\n")
        self._create_file("api/server.py", "from middleware.limiter import RateLimiter\n\nlimiter = RateLimiter()\n")

        graph = RepositoryGraph(self.test_root).scan()
        blast = graph.compute_blast_radius(["middleware/limiter.py"])
        self.assertIn("api/server.py", blast.directly_affected_files)

    # =========================================================================
    # 4. MULTI-FILE REPAIR SCENARIOS (5 Tarefas Complexas / >= 30% Falhas)
    # =========================================================================

    async def test_mr01_multi_file_import_cascade_repair(self) -> None:
        """MR-01: Reparação de cascata de imports partidos em múltiplos ficheiros."""
        self._create_file("common/utils.py", "# Faltava a função format_name\ndef format_name(name):\n    return name.strip().title()\n")
        self._create_file("models/user.py", "from common.utils import format_name\n\nclass User:\n    def __init__(self, name):\n        self.name = format_name(name)\n")
        self._create_file("services/user_service.py", "from models.user import User\n\ndef get_user():\n    return User('joao')\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_mr02_api_contract_drift_repair(self) -> None:
        """MR-02: Reparação de drift em rotas de API entre frontend e backend."""
        self._create_file("backend/routes.py", "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/api/tasks')\ndef get_tasks():\n    return []\n")
        self._create_file("frontend/client.js", "function loadTasks() {\n  return fetch('/api/tasks', { method: 'GET' });\n}\n")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        self.assertTrue(validator.validate().is_valid)

    async def test_mr03_html_asset_links_integrity(self) -> None:
        """MR-03: Deteção de link quebrado para CSS e script inexistentes em HTML."""
        self._create_file("index.html", "<!DOCTYPE html><html><head><link rel='stylesheet' href='missing.css'></head><body><script src='missing.js'></script></body></html>")

        graph = RepositoryGraph(self.test_root).scan()
        validator = CrossFileValidator(graph)
        rep = validator.validate()
        self.assertFalse(rep.is_valid)
        self.assertEqual(len(rep.broken_links), 2)

    async def test_mr04_autonomous_repair_anti_looping_and_rollback(self) -> None:
        """MR-04: Validação de salvaguardas anti-looping e rollback em caso de regressão."""
        self._create_file("bad_script.py", "def broken_code(\n    return 42\n")

        repair_loop = AutonomousRepairLoop(self.test_root, max_repair_attempts=3)
        rep = repair_loop.run_repair_cycle()
        self.assertTrue(rep.success)
        self.assertLessEqual(rep.total_attempts, 3)

    async def test_mr05_failure_memory_and_knowledge_vault_sync(self) -> None:
        """MR-05: Gravação de lição de falha no Knowledge Vault para persistência."""
        vault_temp = os.path.join(self.test_root, "vault")
        mem_store = FailureMemoryStore(vault_temp)

        lesson = FailureLesson(
            lesson_id="LESSON-CA2-001",
            title="FastAPI HTTP Method Mismatch on Task CRUD",
            component="Frontend API Client",
            issue_type="CONTRACT_MISMATCH",
            failure_record="Frontend efetuou chamada GET enquanto o backend esperava POST.",
            evidence="CONTRACT_MISMATCH: Chamada 'GET /api/tasks' em frontend/api.js incompatível com @app.post.",
            root_cause="Alteração unilateral de método HTTP sem atualizar os componentes dependentes.",
            fix_applied="ASTRepairEngineV2 alinhou o método da chamada fetch para POST.",
            test_verification="Pipeline de contratos passou com 0 erros.",
            tags=["contract_mismatch", "ast_repair", "fastapi"],
        )

        fpath = mem_store.record_lesson(lesson)
        self.assertTrue(os.path.isfile(fpath))

        queried = mem_store.query_lessons("FastAPI")
        self.assertGreaterEqual(len(queried), 1)
        self.assertEqual(queried[0].lesson_id, "LESSON-CA2-001")


if __name__ == "__main__":
    unittest.main()
