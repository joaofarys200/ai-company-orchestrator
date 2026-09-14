"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Python Preflight Analyzer: Executes py_compile and ast.parse to detect syntax errors
and undefined name issues before startup.
"""

from __future__ import annotations

import ast
import os
import py_compile
from typing import List, Optional

from agents.project_preflight.language import PYTHON_LEGITIMATE_BUILTINS
from agents.project_preflight.models import (
    IssueSeverity,
    PreflightIssue,
    ProjectRuntimeProfile,
)


class PythonPreflightAnalyzer:
    """
    Validates Python files using py_compile and safe AST walking.
    """

    def analyze_file(
        self, file_path: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []
        if not os.path.isfile(file_path):
            issues.append(
                PreflightIssue(
                    issue_id=f"missing_py_file_{os.path.basename(file_path)}",
                    severity=IssueSeverity.BLOCKER,
                    category="ENTRYPOINT_MISSING",
                    message=f"Ficheiro Python não encontrado: {file_path}",
                    file_path=file_path,
                )
            )
            return issues

        # 1. py_compile check
        compile_issue = self._run_py_compile(file_path)
        if compile_issue:
            issues.append(compile_issue)
            return issues

        # 2. AST parsing for syntax and unimported modules
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            issues.append(
                PreflightIssue(
                    issue_id=f"syntax_error_{os.path.basename(file_path)}",
                    severity=IssueSeverity.BLOCKER,
                    category="SYNTAX_ERROR",
                    message=f"Erro de sintaxe Python: {e.msg}",
                    file_path=file_path,
                    line=e.lineno,
                )
            )
            return issues
        except Exception:
            return issues

        # AST Inspection for common framework calls without declaration
        issues.extend(self._inspect_ast_calls(tree, file_path))
        return issues

    def _run_py_compile(self, file_path: str) -> Optional[PreflightIssue]:
        try:
            py_compile.compile(file_path, doraise=True)
        except py_compile.PyCompileError as e:
            return PreflightIssue(
                issue_id=f"py_compile_error_{os.path.basename(file_path)}",
                severity=IssueSeverity.BLOCKER,
                category="SYNTAX_ERROR",
                message=f"Erro de compilação Python: {e.msg}",
                file_path=file_path,
                suggested_action="Corrija o erro de compilação ou indentação do script Python.",
            )
        except Exception:
            pass
        return None

    def _inspect_ast_calls(self, tree: ast.AST, file_path: str) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []
        imported_names = set(PYTHON_LEGITIMATE_BUILTINS)
        defined_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.FunctionDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)

        # Look for calls to common web frameworks on undefined objects (e.g. app.route)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                obj_name = node.value.id
                if obj_name == "app" and node.attr in ("route", "get", "post", "run"):
                    if "app" not in defined_names and "app" not in imported_names:
                        issues.append(
                            PreflightIssue(
                                issue_id=f"undefined_py_app_{os.path.basename(file_path)}",
                                severity=IssueSeverity.BLOCKER,
                                category="NAME_ERROR",
                                message="O objeto 'app' é referenciado mas não foi instanciado (ex: app = FastAPI() ou app = Flask(__name__)).",
                                file_path=file_path,
                                line=getattr(node, "lineno", None),
                                symbol="app",
                                suggested_action="Instancie o objeto de aplicação web antes de registrar rotas.",
                            )
                        )
                        break

        return issues
