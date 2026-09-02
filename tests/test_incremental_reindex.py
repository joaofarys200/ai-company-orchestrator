"""
JARVIS OS — Test Suite: Incremental Reindex & Coding Flow Integration (Fase 10.5)
Verifica a reindexação por blast radius, auto-refresh em coding sessions e seleção de contexto relevante.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import time

from intelligence.project_intake import (
    ProjectIntakeService,
    StalenessStatus,
)


@pytest.fixture
def intake_service(tmp_path: Path) -> ProjectIntakeService:
    from intelligence.project_context import ProjectContextService
    ctx_service = ProjectContextService(workspace_root=str(tmp_path))
    return ProjectIntakeService(project_context_service=ctx_service, workspace_root=str(tmp_path))


def test_incremental_reindex_blast_radius(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a reindexação incremental rápida atualizando símbolos e mantendo o snapshot fresco."""
    proj_dir = tmp_path / "workspace" / "projects" / "incremental-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "user_service.py").write_text("class UserService:\n    def get_user(self): return 'Alice'\n", encoding="utf-8")
    (proj_dir / "auth_service.py").write_text("from user_service import UserService\nclass AuthService:\n    pass\n", encoding="utf-8")
    (proj_dir / "app.py").write_text("from auth_service import AuthService\n", encoding="utf-8")

    initial_snapshot = intake_service.build_snapshot("incremental-app")
    assert initial_snapshot.symbols["total_count"] >= 2

    # Modificar user_service.py adicionando novo método
    (proj_dir / "user_service.py").write_text(
        "class UserService:\n    def get_user(self): return 'Alice'\n    def delete_user(self): pass\n",
        encoding="utf-8"
    )

    # Reindexar incrementalmente
    updated_snapshot = intake_service.reindex_incremental("incremental-app", ["user_service.py"])
    
    assert updated_snapshot.staleness == StalenessStatus.FRESH.value
    assert updated_snapshot.snapshot_hash != initial_snapshot.snapshot_hash
    
    # Verificar se o novo método foi capturado nos símbolos
    key_symbols = [s["name"] for s in updated_snapshot.symbols["key_symbols"]]
    assert "delete_user" in key_symbols or any("UserService.delete_user" in s for s in key_symbols)

    # Testar que agora está FRESH
    check = intake_service.check_staleness("incremental-app")
    assert check.status == StalenessStatus.FRESH.value


def test_ensure_fresh_snapshot_flow(tmp_path: Path, intake_service: ProjectIntakeService):
    """Verifica que ensure_fresh_snapshot lida de forma transparente com projetos novos, intocados e modificados."""
    proj_dir = tmp_path / "workspace" / "projects" / "auto-refresh-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "main.py").write_text("print('hello')", encoding="utf-8")

    # 1. Primeira chamada em projeto sem snapshot -> cria snapshot
    s1 = intake_service.ensure_fresh_snapshot("auto-refresh-app")
    assert s1 is not None
    assert s1.project["project_id"] == "auto-refresh-app"

    # 2. Segunda chamada sem alterações -> retorna snapshot cached
    s2 = intake_service.ensure_fresh_snapshot("auto-refresh-app")
    assert s2.snapshot_hash == s1.snapshot_hash

    # 3. Pequena alteração -> executa incremental e retorna fresco
    (proj_dir / "main.py").write_text("print('hello world')", encoding="utf-8")
    s3 = intake_service.ensure_fresh_snapshot("auto-refresh-app")
    assert s3.snapshot_hash != s1.snapshot_hash
    assert s3.staleness == StalenessStatus.FRESH.value


def test_get_relevant_context_selection(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a seleção inteligente de contexto relevante para o prompt do modelo."""
    proj_dir = tmp_path / "workspace" / "projects" / "context-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "auth.py").write_text("class AuthManager:\n    def login(self): pass\n", encoding="utf-8")
    (proj_dir / "billing.py").write_text("class StripeBilling:\n    def charge(self): pass\n", encoding="utf-8")
    (proj_dir / "database.py").write_text("class DatabaseConnection:\n    pass\n", encoding="utf-8")

    intake_service.build_snapshot("context-app")

    # Pedir contexto para tarefa de autenticação
    auth_ctx = intake_service.get_relevant_context("context-app", "Implementar renovação de token no login de autenticação")
    
    assert "auth.py" in auth_ctx["relevant_files"]
    auth_syms = [s["name"] for s in auth_ctx["relevant_symbols"]]
    assert any("AuthManager" in s or "login" in s for s in auth_syms)

    # Pedir contexto para tarefa de faturação
    bill_ctx = intake_service.get_relevant_context("context-app", "Adicionar suporte a pagamentos com cartão no Stripe")
    assert "billing.py" in bill_ctx["relevant_files"]
