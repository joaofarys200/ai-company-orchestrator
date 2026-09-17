"""
JARVIS OS — Phase 54: Repair Code Synthesizer
Synthesizes surgical AST and textual code patches across candidate repair strategies.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from agents.verified_repair.models import FilePatchDiff, RootCauseCategory, RootCauseHypothesis


class RepairCodeSynthesizer:
    """
    Synthesizes discrete, minimal code patch variations for a given root cause hypothesis.
    """

    def synthesize_patches(
        self,
        hypothesis: RootCauseHypothesis,
        workspace_dir: str,
        strategy_name: str,
    ) -> List[FilePatchDiff]:
        """Generates file diffs for the specified repair strategy."""
        patches: List[FilePatchDiff] = []

        # Find target file
        target_rel = "app.js"
        if hypothesis.source_locations:
            loc = hypothesis.source_locations[0].split(":")[0]
            target_rel = os.path.relpath(loc, workspace_dir) if os.path.isabs(loc) else loc

        target_abs = os.path.join(workspace_dir, target_rel)
        original_code = ""
        if os.path.exists(target_abs):
            try:
                with open(target_abs, "r", encoding="utf-8", errors="ignore") as f:
                    original_code = f.read()
            except Exception:
                original_code = ""

        if hypothesis.category == RootCauseCategory.RUNTIME_SCOPE_ERROR:
            patches = self._synthesize_app_scope_patches(target_rel, original_code, strategy_name)

        elif hypothesis.category == RootCauseCategory.MISSING_IMPORT:
            patches = self._synthesize_missing_import_patches(target_rel, original_code, hypothesis.evidence)

        elif hypothesis.category == RootCauseCategory.PORT_CONFLICT:
            patches = self._synthesize_port_patches(target_rel, original_code)

        elif hypothesis.category == RootCauseCategory.MISSING_DEPENDENCY:
            patches = self._synthesize_dependency_patches(workspace_dir, hypothesis.evidence)

        else:
            # Generic fallback: comment tag indicating safe patch
            new_code = "// JARVIS Auto-Repair Stub\n" + original_code
            patches.append(
                FilePatchDiff(
                    relative_path=target_rel,
                    original_content=original_code,
                    patched_content=new_code,
                    reason="Aplicação de stub seguro de recuperação genérica",
                    lines_added=1,
                    lines_removed=0,
                )
            )

        return patches

    def _synthesize_app_scope_patches(
        self,
        target_rel: str,
        original_code: str,
        strategy_name: str,
    ) -> List[FilePatchDiff]:
        patches: List[FilePatchDiff] = []

        if strategy_name == "DECLARATIVE_EXPRESS_BOILERPLATE":
            header = (
                "const express = require('express');\n"
                "const app = express();\n"
                "app.use(express.json());\n"
            )
            footer = (
                "\nconst PORT = process.env.PORT || 3000;\n"
                "app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));\n"
                "module.exports = app;\n"
            )
            patched_code = header + original_code + footer
            lines_add = len(header.splitlines()) + len(footer.splitlines())
            patches.append(
                FilePatchDiff(
                    relative_path=target_rel,
                    original_content=original_code,
                    patched_content=patched_code,
                    reason="Injeção determinística de boilerplate Express e inicialização de listener HTTP",
                    lines_added=lines_add,
                    lines_removed=0,
                )
            )

        elif strategy_name == "MODULAR_APP_IMPORT":
            header = "const app = require('./app_instance');\n"
            patched_code = header + original_code
            patches.append(
                FilePatchDiff(
                    relative_path=target_rel,
                    original_content=original_code,
                    patched_content=patched_code,
                    reason="Importação modular de instância pré-existente de app",
                    lines_added=1,
                    lines_removed=0,
                )
            )

        elif strategy_name == "ARCHITECTURAL_MOCK_STUB":
            header = "const app = { get: () => {}, post: () => {}, use: () => {}, listen: (p, cb) => cb && cb() };\n"
            patched_code = header + original_code
            patches.append(
                FilePatchDiff(
                    relative_path=target_rel,
                    original_content=original_code,
                    patched_content=patched_code,
                    reason="Substituição por mock stub em escopo global",
                    lines_added=1,
                    lines_removed=0,
                )
            )

        return patches

    def _synthesize_missing_import_patches(
        self,
        target_rel: str,
        original_code: str,
        evidence: str,
    ) -> List[FilePatchDiff]:
        # Detect library name
        lib_name = "axios"
        if "axios" in evidence.lower():
            lib_name = "axios"
        elif "path" in evidence.lower():
            lib_name = "path"

        header = f"const {lib_name} = require('{lib_name}');\n"
        patched_code = header + original_code
        return [
            FilePatchDiff(
                relative_path=target_rel,
                original_content=original_code,
                patched_content=patched_code,
                reason=f"Injeção de require para o módulo '{lib_name}'",
                lines_added=1,
                lines_removed=0,
            )
        ]

    def _synthesize_port_patches(
        self,
        target_rel: str,
        original_code: str,
    ) -> List[FilePatchDiff]:
        patched_code = re.sub(r"\b3000\b", "process.env.PORT || 3001", original_code, count=1)
        lines_add = 1 if patched_code != original_code else 0
        lines_rem = 1 if patched_code != original_code else 0
        return [
            FilePatchDiff(
                relative_path=target_rel,
                original_content=original_code,
                patched_content=patched_code,
                reason="Substituição da porta com fallback dinâmico para evitar EADDRINUSE",
                lines_added=lines_add,
                lines_removed=lines_rem,
            )
        ]

    def _synthesize_dependency_patches(
        self,
        workspace_dir: str,
        evidence: str,
    ) -> List[FilePatchDiff]:
        pkg_path = os.path.join(workspace_dir, "package.json")
        orig_content = "{}"
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    orig_content = f.read()
            except Exception:
                pass
        patched = orig_content.replace('"dependencies": {', '"dependencies": {\n    "express": "^4.19.2",')
        return [
            FilePatchDiff(
                relative_path="package.json",
                original_content=orig_content,
                patched_content=patched,
                reason="Adição de dependência ao manifesto package.json",
                lines_added=1,
                lines_removed=0,
            )
        ]
