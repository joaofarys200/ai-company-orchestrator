"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
JavaScript Preflight Analyzer: Performs node --check and safe AST token analysis
for missing declarations, undeclared Express app instances, and unimported libraries.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import List, Optional

from agents.project_preflight.language import (
    BROWSER_LEGITIMATE_GLOBALS,
    NODE_LEGITIMATE_GLOBALS,
)
from agents.project_preflight.models import (
    IssueSeverity,
    PreflightIssue,
    ProjectRuntimeProfile,
    RuntimeType,
)


class JavaScriptPreflightAnalyzer:
    """
    Analyzes JavaScript files (CommonJS and ESM) for syntax errors and missing declarations.
    Respects runtime profile globals to prevent false positives.
    """

    def analyze_file(
        self, file_path: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []
        if not os.path.isfile(file_path):
            issues.append(
                PreflightIssue(
                    issue_id=f"missing_file_{os.path.basename(file_path)}",
                    severity=IssueSeverity.BLOCKER,
                    category="ENTRYPOINT_MISSING",
                    message=f"Ficheiro de entrada não encontrado: {file_path}",
                    file_path=file_path,
                )
            )
            return issues

        # 1. Node Syntax Check via node --check
        syntax_issue = self._run_node_syntax_check(file_path)
        if syntax_issue:
            issues.append(syntax_issue)
            # If syntax itself is invalid, AST token analysis will be inaccurate
            return issues

        # 2. Semantic AST Token Analysis
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            code = "".join(lines)
        except Exception as e:
            issues.append(
                PreflightIssue(
                    issue_id="file_read_error",
                    severity=IssueSeverity.BLOCKER,
                    category="FILE_IO_ERROR",
                    message=f"Não foi possível ler o ficheiro: {e}",
                    file_path=file_path,
                )
            )
            return issues

        # Run semantic token checks
        issues.extend(self._check_undeclared_express_app(lines, code, file_path))
        issues.extend(self._check_unimported_libraries(lines, code, file_path, profile))

        return issues

    def _run_node_syntax_check(self, file_path: str) -> Optional[PreflightIssue]:
        try:
            proc = subprocess.run(
                ["node", "--check", os.path.basename(file_path)],
                cwd=os.path.dirname(file_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                stderr = proc.stderr.strip()
                # Parse line number if present
                line_match = re.search(r":(\d+)\r?\n", stderr)
                line_num = int(line_match.group(1)) if line_match else None
                return PreflightIssue(
                    issue_id=f"syntax_error_{os.path.basename(file_path)}",
                    severity=IssueSeverity.BLOCKER,
                    category="SYNTAX_ERROR",
                    message=f"Erro de sintaxe detetado pelo Node.js: {stderr.splitlines()[0] if stderr else 'SyntaxError'}",
                    file_path=file_path,
                    line=line_num,
                    suggested_action="Corrija o erro de sintaxe no arquivo antes da execução.",
                )
        except Exception:
            pass
        return None

    def _check_undeclared_express_app(
        self, lines: List[str], code: str, file_path: str
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        # Detect app method invocations
        app_usage = re.search(r'\bapp\.(get|post|put|delete|patch|use|listen|all)\s*\(', code)
        if not app_usage:
            return issues

        # Check if app is declared or assigned in the file
        has_decl = (
            re.search(r'\b(const|let|var)\s+app\b', code)
            or re.search(r'\bfunction\s+app\b', code)
            or re.search(r'\b(class|import)\s+app\b', code)
            or re.search(r'^\s*app\s*=\s*', code, re.MULTILINE)
        )

        if not has_decl:
            # Find the line where app is first called
            first_line = 1
            for idx, line in enumerate(lines, 1):
                if re.search(r'\bapp\.(get|post|put|delete|patch|use|listen|all)\s*\(', line):
                    first_line = idx
                    break

            issues.append(
                PreflightIssue(
                    issue_id=f"undeclared_app_{os.path.basename(file_path)}",
                    severity=IssueSeverity.BLOCKER,
                    category="REFERENCE_ERROR",
                    message="O objeto 'app' é invocado mas não foi declarado ou instanciado com Express.",
                    file_path=file_path,
                    line=first_line,
                    symbol="app",
                    suggested_action="Adicione 'const express = require(\"express\"); const app = express();' antes de utilizar o app.",
                )
            )

        return issues

    def _check_unimported_libraries(
        self, lines: List[str], code: str, file_path: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        common_libraries = [
            ("axios", r'\baxios(\.|\s*\()', 'const axios = require("axios");'),
            ("path", r'\bpath\.(join|resolve|basename|dirname|extname)\s*\(', 'const path = require("path");'),
            ("fs", r'\bfs\.(readFile|writeFile|existsSync|stat|promises)\b', 'const fs = require("fs");'),
        ]

        for lib_name, usage_pattern, fix_snippet in common_libraries:
            if re.search(usage_pattern, code):
                has_import = (
                    re.search(rf'\b(const|let|var)\s+.*?\b{lib_name}\b.*?require\s*\(', code)
                    or re.search(rf'\bimport\s+.*?\b{lib_name}\b', code)
                )
                if not has_import:
                    first_line = 1
                    for idx, line in enumerate(lines, 1):
                        if re.search(usage_pattern, line):
                            first_line = idx
                            break
                    issues.append(
                        PreflightIssue(
                            issue_id=f"unimported_{lib_name}_{os.path.basename(file_path)}",
                            severity=IssueSeverity.WARNING,
                            category="IMPORT_MISSING",
                            message=f"O módulo '{lib_name}' é utilizado mas não foi explicitamente importado ou requerido.",
                            file_path=file_path,
                            line=first_line,
                            symbol=lib_name,
                            suggested_action=f"Adicione '{fix_snippet}' no topo do ficheiro.",
                        )
                    )

        return issues
