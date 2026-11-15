"""
Reparador Determinístico e Planeador de Reparação de Artefactos do JARVIS.
Implementa o Princípio Arquitetural: ARCHITECTURE-AWARE REPAIR.

O reparador:
- NÃO cria index.html / style.css / app.js por defeito.
- Procura:
  1. artefacto equivalente existente
  2. convenção do projeto (TypeScript, src/, etc.)
  3. entrypoint conhecido
  4. arquitetura selecionada
- Só cria um novo ficheiro quando:
  - o artefacto é estritamente necessário
  - não existe equivalente funcional
  - a arquitetura suporta esse artefacto
  - a criação é 100% compatível com a stack do projeto
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from security.delivery_governance.architecture_detector import DetectedArchitecture
from security.delivery_governance.models import ArchitectureDecision, ArtifactCategory, ArtifactExpectation


@dataclass
class RepairAction:
    """Ação determinística de reparação de artefacto ausente."""
    action_type: str  # 'MAP_EXISTING_EQUIVALENT' ou 'CREATE_ARCHITECTURE_CONFORMING_FILE'
    file_path: str
    content: str
    rationale: str
    responsibility: str
    category: str


class RepairPlanner:
    """Planeador de reparação de integridade de produto com respeito estrito à stack."""

    @classmethod
    def plan_repairs(
        cls,
        missing_expectations: List[ArtifactExpectation],
        arch: DetectedArchitecture,
        decision: ArchitectureDecision,
        project_root: str,
    ) -> List[RepairAction]:
        """Gera ações de reparação sem impor templates genéricos incompatíveis."""
        actions: List[RepairAction] = []
        is_ts = arch.conventions.get("typescript", False)
        stack = decision.selected_stack or arch.stack

        for exp in missing_expectations:
            # 1. Procura equivalente existente no projeto
            equiv = cls._find_existing_equivalent(exp, arch, project_root)
            if equiv:
                actions.append(RepairAction(
                    action_type="MAP_EXISTING_EQUIVALENT",
                    file_path=equiv,
                    content="",
                    rationale=f"Reaproveitando ficheiro equivalente existente '{equiv}' para a responsabilidade '{exp.responsibility}'.",
                    responsibility=exp.responsibility,
                    category=exp.category,
                ))
                continue

            # 2. Se não existe equivalente, cria esqueleto compatível com a arquitetura
            target_path = exp.path or cls._derive_conventional_path(exp, arch, stack)
            content = cls._generate_conforming_skeleton(exp, stack, is_ts, target_path)

            actions.append(RepairAction(
                action_type="CREATE_ARCHITECTURE_CONFORMING_FILE",
                file_path=target_path,
                content=content,
                rationale=f"Criando artefacto mínimo conforme com a stack '{stack}' para satisfazer '{exp.responsibility}'.",
                responsibility=exp.responsibility,
                category=exp.category,
            ))

        return actions

    @classmethod
    def apply_repairs(cls, actions: List[RepairAction], project_root: str) -> List[str]:
        """Aplica com segurança as reparações no sistema de ficheiros."""
        applied: List[str] = []
        for act in actions:
            if act.action_type == "CREATE_ARCHITECTURE_CONFORMING_FILE":
                full_p = os.path.join(project_root, act.file_path)
                os.makedirs(os.path.dirname(full_p), exist_ok=True)
                if not os.path.exists(full_p) or os.path.getsize(full_p) == 0:
                    from backend.atomic_io import atomic_write_text

                    atomic_write_text(full_p, act.content, encoding="utf-8")
                    applied.append(act.file_path)
            elif act.action_type == "MAP_EXISTING_EQUIVALENT":
                applied.append(f"Mapped: {act.file_path}")
        return applied

    @classmethod
    def _find_existing_equivalent(
        cls,
        exp: ArtifactExpectation,
        arch: DetectedArchitecture,
        project_root: str,
    ) -> Optional[str]:
        """Verifica se já existe algum ficheiro que cumpra a responsabilidade."""
        for f in arch.existing_files:
            lower = f.lower()
            if exp.category == ArtifactCategory.FRONTEND.value:
                if any(x in lower for x in ["app.tsx", "app.jsx", "main.tsx", "main.jsx", "index.html", "page.tsx", "page.jsx"]):
                    return f
            elif exp.category == ArtifactCategory.STORAGE.value:
                if any(x in lower for x in ["storage", "localstorage", "store", "repo", "db"]):
                    return f
            elif exp.category == ArtifactCategory.BACKEND.value:
                if any(x in lower for x in ["main.py", "app.py", "server.py", "api.py", "server.ts", "index.ts"]):
                    return f
        return None

    @classmethod
    def _derive_conventional_path(
        cls,
        exp: ArtifactExpectation,
        arch: DetectedArchitecture,
        stack: str,
    ) -> str:
        """Deduz o caminho do ficheiro em harmonia com as convenções do projeto."""
        is_ts = arch.conventions.get("typescript", False)
        has_src = arch.conventions.get("has_src", False)

        if stack == "react_vite":
            ext = "tsx" if is_ts else "jsx"
            if exp.category == ArtifactCategory.FRONTEND.value:
                return f"src/App.{ext}"
            elif exp.category == ArtifactCategory.STORAGE.value:
                return f"src/services/storage.{'ts' if is_ts else 'js'}"
            return f"src/Component.{ext}"

        elif stack == "nextjs":
            ext = "tsx" if is_ts else "jsx"
            return f"app/page.{ext}"

        elif stack in {"python_fastapi", "python_flask", "python_backend"}:
            if exp.category == ArtifactCategory.STORAGE.value:
                return "repository.py"
            return "main.py"

        elif stack in {"node_express", "node_typescript"}:
            ext = "ts" if is_ts else "js"
            prefix = "src/" if has_src else ""
            return f"{prefix}server.{ext}"

        # Vanilla Web
        if exp.category == ArtifactCategory.FRONTEND.value:
            return "index.html"
        elif "style" in exp.responsibility.lower():
            return "styles.css"
        return "app.js"

    @classmethod
    def _generate_conforming_skeleton(
        cls,
        exp: ArtifactExpectation,
        stack: str,
        is_ts: bool,
        file_path: str,
    ) -> str:
        """Gera o código fonte do esqueleto mínimo apropriado para a stack."""
        if stack == "react_vite":
            if file_path.endswith((".tsx", ".jsx")):
                return (
                    "import React, { useState, useEffect } from 'react';\n\n"
                    "export default function App() {\n"
                    "  const [tasks, setTasks] = useState<any[]>(() => {\n"
                    "    try {\n"
                    "      return JSON.parse(localStorage.getItem('tasks') || '[]');\n"
                    "    } catch { return []; }\n"
                    "  });\n\n"
                    "  return (\n"
                    "    <main className=\"container\">\n"
                    "      <h1>Gestão de Tarefas</h1>\n"
                    "      <button id=\"add-task-btn\" onClick={() => setTasks([...tasks, { id: Date.now(), title: 'Nova Tarefa' }])}>\n"
                    "        Adicionar Tarefa\n"
                    "      </button>\n"
                    "      <ul id=\"task-list\">\n"
                    "        {tasks.map(t => <li key={t.id}>{t.title}</li>)}\n"
                    "      </ul>\n"
                    "    </main>\n"
                    "  );\n"
                    "}\n"
                )
            elif file_path.endswith((".ts", ".js")):
                return (
                    "// Persistence Service\n"
                    "export const storage = {\n"
                    "  load: (key: string) => JSON.parse(localStorage.getItem(key) || '[]'),\n"
                    "  save: (key: string, data: any) => localStorage.setItem(key, JSON.stringify(data)),\n"
                    "};\n"
                )
            elif file_path.endswith(".css"):
                return ":root { --primary: #3b82f6; }\nbody { font-family: system-ui, sans-serif; padding: 2rem; }\n"

        elif stack == "nextjs":
            return (
                "export default function Page() {\n"
                "  return (\n"
                "    <main>\n"
                "      <h1>Dashboard</h1>\n"
                "      <p>Aplicação Next.js verificada.</p>\n"
                "    </main>\n"
                "  );\n"
                "}\n"
            )

        elif stack in {"python_fastapi", "python_flask", "python_backend"}:
            if "fastapi" in stack:
                return (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title='JARVIS Inferred API')\n\n"
                    "@app.get('/health')\n"
                    "def health():\n"
                    "    return {'status': 'healthy', 'ready': True}\n\n"
                    "@app.get('/api/tasks')\n"
                    "def get_tasks():\n"
                    "    return [{'id': 1, 'title': 'Tarefa de Exemplo'}]\n"
                )
            else:
                return (
                    "from flask import Flask, jsonify\n\n"
                    "app = Flask(__name__)\n\n"
                    "@app.route('/health')\n"
                    "def health():\n"
                    "    return jsonify({'status': 'healthy'})\n\n"
                    "if __name__ == '__main__':\n"
                    "    app.run(port=8000)\n"
                )

        # Vanilla Web
        if file_path.endswith(".html"):
            return (
                "<!DOCTYPE html>\n"
                "<html lang=\"pt\">\n"
                "<head>\n"
                "  <meta charset=\"UTF-8\" />\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
                "  <title>JARVIS Product</title>\n"
                "  <link rel=\"stylesheet\" href=\"styles.css\" />\n"
                "</head>\n"
                "<body>\n"
                "  <div class=\"app-container\">\n"
                "    <h1>Aplicação Web</h1>\n"
                "    <button id=\"action-btn\">Executar</button>\n"
                "  </div>\n"
                "  <script src=\"app.js\"></script>\n"
                "</body>\n"
                "</html>\n"
            )
        elif file_path.endswith(".css"):
            return (
                ":root {\n"
                "  --bg: #0f172a;\n"
                "  --text: #f8fafc;\n"
                "  --primary: #3b82f6;\n"
                "}\n"
                "body {\n"
                "  background: var(--bg);\n"
                "  color: var(--text);\n"
                "  font-family: system-ui, sans-serif;\n"
                "  padding: 2rem;\n"
                "}\n"
            )
        elif file_path.endswith(".js"):
            return (
                "document.addEventListener('DOMContentLoaded', () => {\n"
                "  const btn = document.getElementById('action-btn');\n"
                "  if (btn) {\n"
                "    btn.addEventListener('click', () => {\n"
                "      console.log('Action executed');\n"
                "    });\n"
                "  }\n"
                "});\n"
            )

        return "// Minimum conforming artifact\n"
