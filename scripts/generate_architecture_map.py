from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


GENERATOR_VERSION = "1.1.0"
EXCLUDED_DIRS = {
    ".git", ".jarvis_backups", ".pytest_cache", "__pycache__", "build", "chroma_db",
    "dist", "diagnostics", "logs", "node_modules", "venv", ".venv", "workspace",
}
EXCLUDED_FILES = {
    ".env",
    "database.db",
    "ecommerce.db",
    "symbols_index.json",
    "architecture-map.html",
    "architecture-map.json",
    "architecture-map.schema.json",
    "ARCHITECTURE_MAP_REPORT.md",
    "ARCHITECTURE_MAP_REVIEW.md",
}
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml", ".md", ".txt"}
MAP_BUCKETS = (
    "systems", "layers", "components", "contracts", "endpoints", "websockets",
    "tools", "agents", "providers", "datastores", "workflows", "state_machines",
    "external_dependencies", "tests", "benchmarks", "diagnostics", "risks", "unknowns",
)
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
]


def relpath(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def evidence(path: str, line: int, claim: str, confidence: str = "confirmed") -> dict[str, Any]:
    return {"path": path, "line": line, "claim": claim, "confidence": confidence}


def stable_id(kind: str, path: str, name: str | None = None) -> str:
    value = f"{kind}:{path}" if not name else f"{kind}:{path}:{name}"
    return value.replace("\\", "/")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def redact(value: Any) -> Any:
    if isinstance(value, str):
        result = value
        for pattern in SENSITIVE_PATTERNS:
            result = pattern.sub(lambda match: f"{match.group(1) if match.lastindex else 'REDACTED'}=<redacted>", result)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def line_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))


def module_name(path: str) -> str:
    return path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")


def classify_path(path: str) -> tuple[str, str, str]:
    lower = path.lower()
    if lower.startswith("tests/") or "/tests/" in lower:
        return "evaluation", "test_only", "testing"
    if lower.startswith("scripts/"):
        status = "diagnostic_only" if "diagnostic" in lower else "benchmark_only" if "benchmark" in lower else "experimental"
        return "evaluation", status, "script"
    if lower.startswith("docs/") or lower.startswith("diagnostics/"):
        return "evaluation", "diagnostic_only", "diagnostic"
    if lower.startswith("frontend/"):
        return "presentation", "production_active", "frontend"
    if lower.startswith(("backend/", "agents/", "intelligence/", "persistence/", "services/", "src/")):
        return "application", "production_integrated", "backend"
    if lower.startswith("config/") or lower in {".env.example", "requirements.txt", "package.json"}:
        return "infrastructure", "production_active", "configuration"
    return "infrastructure", "unknown", "repository"


def is_relevant(path: Path, root: Path) -> bool:
    rel = relpath(root, path)
    if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
        return False
    if path.name in EXCLUDED_FILES:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {".env.example", "Dockerfile"}


@dataclass
class MapBuilder:
    root: Path
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)
    evidence_index: list[dict[str, Any]] = field(default_factory=list)
    external_names: set[str] = field(default_factory=set)
    py_modules: dict[str, str] = field(default_factory=dict)
    symbol_ids: dict[str, str] = field(default_factory=dict)
    production_files: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def add_entity(self, entity: dict[str, Any]) -> str:
        entity = redact(entity)
        entity.setdefault("id", stable_id(entity["type"], entity.get("path", entity["name"]), entity.get("name") if entity.get("type") in {"class", "function", "provider", "agent"} else None))
        entity.setdefault("name", entity["id"].split(":")[-1])
        entity.setdefault("type", "component")
        entity.setdefault("category", entity["type"])
        entity.setdefault("layer", "unknown")
        entity.setdefault("subsystem", "unknown")
        entity.setdefault("status", "unknown")
        entity.setdefault("path", "")
        entity.setdefault("line_start", 1)
        entity.setdefault("line_end", entity["line_start"])
        entity.setdefault("language", "")
        entity.setdefault("responsibilities", [])
        entity.setdefault("inputs", [])
        entity.setdefault("outputs", [])
        entity.setdefault("dependencies", [])
        entity.setdefault("dependents", [])
        entity.setdefault("contracts", [])
        entity.setdefault("side_effects", [])
        entity.setdefault("persistence", [])
        entity.setdefault("runtime", "local")
        entity.setdefault("criticality", "medium")
        entity.setdefault("confidence", "confirmed")
        entity.setdefault("evidence", [])
        entity.setdefault("tags", [])
        self.entities[entity["id"]] = entity
        self.evidence_index.extend(entity.get("evidence", []))
        return entity["id"]

    def add_relation(self, source: str, target: str, relation_type: str, path: str, line: int, description: str, confidence: str = "confirmed", production_relevance: str = "unknown") -> None:
        if source not in self.entities or target not in self.entities:
            return
        relation = {
            "source": source,
            "target": target,
            "type": relation_type,
            "direction": "source_to_target",
            "description": description,
            "evidence": [evidence(path, line, description, confidence)],
            "confidence": confidence,
            "runtime": "static",
            "optional": False,
            "production_relevance": production_relevance,
        }
        key = (source, target, relation_type, path, line)
        if not any((item["source"], item["target"], item["type"], item["evidence"][0]["path"], item["evidence"][0]["line"]) == key for item in self.relations):
            self.relations.append(relation)

    def scan_files(self) -> list[Path]:
        found: list[Path] = []
        for current, directories, filenames in os.walk(self.root):
            directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
            current_path = Path(current)
            for filename in sorted(filenames):
                path = current_path / filename
                if is_relevant(path, self.root):
                    found.append(path)
        return sorted(found, key=lambda path: relpath(self.root, path))

    def add_subsystems(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        systems = [
            {"id": "system:jarvis", "name": "AI Company Orchestrator / JARVIS", "type": "system", "category": "system", "layer": "system", "subsystem": "jarvis", "status": "production_integrated", "description": "Orquestrador local com frontend, backend, ferramentas, modelos e avaliação."},
        ]
        layers = []
        for name, description in [
            ("presentation", "React/Vite e experiência operacional"),
            ("application", "Serviços, agentes, orquestração e execução"),
            ("domain", "Missões, contexto de projeto, sessões e contratos"),
            ("infrastructure", "Providers, WebSocket, sandbox, configuração"),
            ("persistence", "SQLite, ChromaDB, ficheiros e índices"),
            ("evaluation", "Testes, benchmarks e contratos de avaliação"),
            ("diagnostic", "Diagnósticos e registos operacionais"),
        ]:
            layers.append({"id": f"layer:{name}", "name": name, "type": "layer", "description": description})
        for system in systems:
            self.add_entity(system)
        for layer in layers:
            self.add_entity({**layer, "status": "production_integrated", "layer": layer["name"], "subsystem": layer["name"], "confidence": "confirmed"})
        return systems, layers

    def scan_python(self, path: Path, text: str) -> None:
        rel = relpath(self.root, path)
        layer, status, category = classify_path(rel)
        module_id = stable_id("module", rel)
        module_entity = {
            "id": module_id, "name": module_name(rel), "type": "module", "category": category,
            "layer": layer, "subsystem": rel.split("/")[0], "status": status, "path": rel,
            "language": "Python", "runtime": "Python", "criticality": "high" if rel in {"server.py", "agents/orchestrator/__init__.py", "intelligence/project_context.py"} else "medium",
            "responsibilities": [f"Código Python em {rel}"], "evidence": [evidence(rel, 1, "ficheiro Python descoberto")],
        }
        self.add_entity(module_entity)
        self.py_modules[module_name(rel)] = module_id
        if layer in {"application", "domain", "infrastructure", "persistence"}:
            self.production_files.add(rel)
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            self.warnings.append(f"AST Python parcial em {rel}: {exc.msg} linha {exc.lineno}")
            return
        local_symbols: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbol_id = stable_id(kind, rel, node.name)
                symbol = {
                    "id": symbol_id, "name": node.name, "type": kind, "category": kind,
                    "layer": layer, "subsystem": rel.split("/")[0], "status": status, "path": rel,
                    "line_start": node.lineno, "line_end": line_end(node), "language": "Python",
                    "responsibilities": [f"{kind} {node.name}"], "evidence": [evidence(rel, node.lineno, f"definição de {node.name}")],
                }
                self.add_entity(symbol)
                local_symbols[node.name] = symbol_id
                self.symbol_ids.setdefault(node.name, symbol_id)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                for imported in names:
                    root_name = imported.split(".")[0]
                    target_id = self.py_modules.get(imported) or self.py_modules.get(root_name)
                    if target_id:
                        self.add_relation(module_id, target_id, "imports", rel, node.lineno, f"{rel} importa {imported}", production_relevance="production" if layer != "evaluation" else "benchmark")
                    else:
                        self.external_names.add(root_name)
            if isinstance(node, ast.Call):
                called = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                target_id = local_symbols.get(called) or self.symbol_ids.get(called)
                if target_id:
                    self.add_relation(module_id, target_id, "calls", rel, getattr(node, "lineno", 1), f"chamada estática a {called}", "inferred", "production" if layer != "evaluation" else "benchmark")
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and isinstance(decorator.func.value, ast.Name):
                    if decorator.func.value.id in {"app", "router"} and decorator.func.attr.lower() in {"get", "post", "put", "patch", "delete", "websocket", "route"}:
                        route = ast.literal_eval(decorator.args[0]) if decorator.args and isinstance(decorator.args[0], ast.Constant) else "unknown"
                        endpoint_id = stable_id("endpoint", rel, f"{decorator.func.attr.upper()} {route}")
                        self.add_entity({
                            "id": endpoint_id, "name": f"{decorator.func.attr.upper()} {route}", "type": "api_endpoint", "category": "endpoint",
                            "layer": "application", "subsystem": rel.split("/")[0], "status": status, "path": rel, "line_start": node.lineno,
                            "line_end": line_end(node), "language": "Python", "entry_point": node.name,
                            "responsibilities": [f"Handler {node.name}"], "inputs": ["request/WebSocket payload"], "outputs": ["response/event"],
                            "evidence": [evidence(rel, node.lineno, f"decorator {decorator.func.attr} com rota {route}")], "criticality": "high",
                        })
                        self.add_relation(endpoint_id, stable_id("function", rel, node.name), "routes_to", rel, node.lineno, f"rota encaminha para {node.name}", production_relevance="production")

    def scan_typescript(self, path: Path, text: str) -> None:
        rel = relpath(self.root, path)
        layer, status, category = classify_path(rel)
        module_id = stable_id("module", rel)
        self.add_entity({"id": module_id, "name": rel, "type": "module", "category": category, "layer": layer, "subsystem": "frontend", "status": status, "path": rel, "language": "TypeScript/TSX", "runtime": "browser", "responsibilities": [f"Módulo frontend {rel}"], "evidence": [evidence(rel, 1, "ficheiro TypeScript/TSX descoberto")]})
        self.production_files.add(rel)
        for match in re.finditer(r"(?:import|export)\s+(?:[^;]*?\s+from\s+)?['\"]([^'\"]+)['\"]", text):
            imported = match.group(1)
            if imported.startswith("."):
                candidate = (path.parent / imported).resolve()
                possible = [candidate, candidate.with_suffix(".ts"), candidate.with_suffix(".tsx"), candidate / "index.ts"]
                target = next((item for item in possible if item.exists() and item.is_file()), None)
                if target:
                    self.add_relation(module_id, stable_id("module", relpath(self.root, target)), "imports", rel, text[:match.start()].count("\n") + 1, f"import frontend de {imported}", production_relevance="production")
            else:
                self.external_names.add(imported.split("/")[0])
        for match in re.finditer(r"(?:export\s+)?(?:function|const|class)\s+([A-Za-z_$][\w$]*)", text):
            name = match.group(1)
            line = text[:match.start()].count("\n") + 1
            self.add_entity({"id": stable_id("component", rel, name), "name": name, "type": "component", "category": "react_component" if rel.endswith((".tsx", ".jsx")) else "function", "layer": layer, "subsystem": "frontend", "status": status, "path": rel, "line_start": line, "language": "TypeScript/TSX", "responsibilities": [f"Símbolo frontend {name}"], "evidence": [evidence(rel, line, f"símbolo {name}")]})

    def scan_configs_and_domains(self, files: list[Path]) -> None:
        for path in files:
            rel = relpath(self.root, path)
            text = read_text(path)
            if path.name == "package.json":
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {}
                self.add_entity({"id": stable_id("configuration", rel), "name": "frontend package configuration", "type": "configuration", "category": "package", "layer": "infrastructure", "subsystem": "frontend", "status": "production_active", "path": rel, "line_start": 1, "language": "JSON", "responsibilities": ["scripts e dependências frontend"], "outputs": ["npm scripts"], "evidence": [evidence(rel, 1, "package.json")], "tags": list(data.get("scripts", {}).keys())})
            if path.name in {".env.example", "config", "config.py"} or rel == ".env.example":
                self.add_entity({"id": stable_id("configuration", rel), "name": rel, "type": "configuration", "category": "environment", "layer": "infrastructure", "subsystem": "configuration", "status": "production_active", "path": rel, "line_start": 1, "language": "text", "responsibilities": ["configuração de runtime"], "evidence": [evidence(rel, 1, "configuração descoberta; valores sensíveis não incluídos")]})

    def scan_special_entities(self, files: list[Path]) -> None:
        for path in files:
            rel = relpath(self.root, path)
            text = read_text(path)
            if rel == "websocket_schema.py":
                for name in ("SERVER_MESSAGE_TYPES", "CLIENT_MESSAGE_TYPES"):
                    line = next((index for index, item in enumerate(text.splitlines(), 1) if item.startswith(name)), 1)
                    self.add_entity({"id": stable_id("contract", rel, name), "name": name, "type": "data_contract", "category": "websocket_contract", "layer": "infrastructure", "subsystem": "websocket", "status": "production_integrated", "path": rel, "line_start": line, "language": "Python", "responsibilities": [f"conjunto de mensagens {name}"], "evidence": [evidence(rel, line, f"constante {name}")]})
            if rel == "agents/tools.py":
                for match in re.finditer(r"[\"']name[\"']\s*:\s*[\"']([^\"']+)", text):
                    line = text[:match.start()].count("\n") + 1
                    name = match.group(1)
                    self.add_entity({"id": stable_id("tool", rel, name), "name": name, "type": "tool", "category": "tool", "layer": "application", "subsystem": "tools", "status": "production_integrated", "path": rel, "line_start": line, "language": "Python", "responsibilities": [f"tool {name}"], "side_effects": ["filesystem/process/network dependendo da tool"], "evidence": [evidence(rel, line, f"tool registada {name}")], "criticality": "high" if name in {"write_file", "execute_command"} else "medium"})
            if rel.startswith("agents/providers/") and path.suffix == ".py":
                provider_name = path.stem
                self.add_entity({"id": stable_id("provider", rel), "name": provider_name, "type": "provider", "category": "model_provider", "layer": "infrastructure", "subsystem": "providers", "status": "production_integrated" if provider_name in {"ollama", "factory"} else "implemented_not_integrated", "path": rel, "line_start": 1, "language": "Python", "responsibilities": ["adapter de modelo"], "evidence": [evidence(rel, 1, "provider descoberto")], "criticality": "high"})
            if rel.startswith("agents/executors/") and path.suffix == ".py":
                self.add_entity({"id": stable_id("component", rel), "name": path.stem, "type": "component", "category": "executor", "layer": "application", "subsystem": "mission_executor", "status": "production_integrated" if path.stem in {"registry", "coding", "project_build"} else "unknown", "path": rel, "line_start": 1, "language": "Python", "responsibilities": ["executor de work package"], "evidence": [evidence(rel, 1, "executor descoberto")]})
            if rel.startswith("tests/") and path.name.startswith("test_"):
                self.add_entity({"id": stable_id("test", rel), "name": path.stem, "type": "test_suite", "category": "test", "layer": "evaluation", "subsystem": "tests", "status": "test_only", "path": rel, "line_start": 1, "language": "Python", "responsibilities": ["testes automatizados"], "evidence": [evidence(rel, 1, "suite de testes")], "tags": ["pytest", "unittest"]})
            if rel.startswith("scripts/") and path.suffix in {".py", ".ps1"}:
                status = "diagnostic_only" if "diagnostic" in path.name else "benchmark_only" if "benchmark" in path.name else "experimental"
                self.add_entity({"id": stable_id("script", rel), "name": path.stem, "type": "script", "category": status, "layer": "evaluation", "subsystem": "scripts", "status": status, "path": rel, "line_start": 1, "language": "Python" if path.suffix == ".py" else "PowerShell", "responsibilities": ["script operacional ou avaliação"], "evidence": [evidence(rel, 1, "script descoberto")]})

    def finalize_statuses(self) -> None:
        imported_targets = {relation["target"] for relation in self.relations if relation["type"] == "imports"}
        for entity in self.entities.values():
            if entity["subsystem"] in {"semantic_context", "capability_registry"} and entity["id"] not in imported_targets and entity["status"] == "production_integrated":
                entity["status"] = "implemented_not_integrated"
        for relation in self.relations:
            self.entities[relation["source"]]["dependencies"].append(relation["target"])
            self.entities[relation["target"]]["dependents"].append(relation["source"])
        for entity in self.entities.values():
            entity["dependencies"] = sorted(set(entity["dependencies"]))
            entity["dependents"] = sorted(set(entity["dependents"]))

    def build_blueprint(
        self,
        components: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        risks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a compact, deterministic architecture projection for humans."""
        by_id = {entity["id"]: entity for entity in self.entities.values()}
        degree = Counter()
        for relation in self.relations:
            degree[relation["source"]] += 1
            degree[relation["target"]] += 1

        workflow_ids = {
            component_id
            for workflow in workflows
            for component_id in workflow.get("components", [])
            if component_id in by_id
        }
        entry_paths = {
            "main.js",
            "server.py",
            "src/main.py",
            "frontend/src/main.tsx",
        }
        priority_paths = entry_paths | {
            "agents/orchestrator/__init__.py",
            "agents/mission_executor.py",
            "intelligence/project_context.py",
            "intelligence/coding_session.py",
            "database.py",
        }
        def blueprint_lane(entity: dict[str, Any]) -> str:
            path = entity.get("path", "")
            lower_path = path.lower()
            if path in entry_paths:
                return "entry"
            if lower_path.startswith("frontend/"):
                return "presentation"
            if any(token in lower_path for token in (
                "database", "persistence/", "memory", "semantic_index", "symbols_index",
            )):
                return "persistence"
            if lower_path.startswith("intelligence/") or any(token in lower_path for token in (
                "project_context", "coding_session", "project_intelligence",
            )):
                return "domain"
            if any(token in lower_path for token in (
                "tools", "providers", "executors", "sandbox", "capability_registry",
                "model_harness", "semantic_context", "startup",
            )):
                return "infrastructure"
            if lower_path.startswith("tests/") or lower_path.startswith("scripts/"):
                return "evaluation"
            return "application"

        candidates = [
            entity
            for entity in components
            if entity.get("type") == "module"
        ]
        ranked = sorted(
            candidates,
            key=lambda entity: (
                entity["id"] not in workflow_ids,
                entity.get("path") not in priority_paths,
                entity.get("criticality") != "high",
                -degree[entity["id"]],
                entity["id"],
            ),
        )
        lane_order = [
            ("entry", "Entradas"),
            ("presentation", "Interface"),
            ("application", "Orquestracao"),
            ("domain", "Dominio"),
            ("infrastructure", "Infraestrutura"),
            ("persistence", "Persistencia"),
            ("evaluation", "Validacao"),
        ]
        lane_quotas = {
            "entry": 2,
            "presentation": 3,
            "application": 6,
            "domain": 4,
            "infrastructure": 5,
            "persistence": 3,
            "evaluation": 3,
        }
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        for lane_id, _ in lane_order:
            lane_candidates = [entity for entity in ranked if blueprint_lane(entity) == lane_id]
            for entity in lane_candidates[:lane_quotas[lane_id]]:
                selected.append(entity)
                selected_ids.add(entity["id"])
        for entity in ranked:
            if len(selected) >= 28:
                break
            if entity["id"] not in selected_ids:
                selected.append(entity)
                selected_ids.add(entity["id"])

        lane_index = {lane_id: index for index, (lane_id, _) in enumerate(lane_order)}

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entity in selected:
            lane = blueprint_lane(entity)
            if lane not in lane_index:
                lane = "infrastructure"
            grouped[lane].append(entity)

        nodes: list[dict[str, Any]] = []
        positions: dict[str, dict[str, int]] = {}
        for lane_id, _ in lane_order:
            lane_entities = sorted(
                grouped.get(lane_id, []),
                key=lambda entity: (-degree[entity["id"]], entity["id"]),
            )
            for row, entity in enumerate(lane_entities):
                position = {"x": 44 + lane_index[lane_id] * 240, "y": 76 + row * 82}
                positions[entity["id"]] = position
                nodes.append({
                    "id": entity["id"],
                    "label": entity["name"],
                    "subtitle": entity.get("path") or entity.get("type"),
                    "lane": lane_id,
                    "layer": entity.get("layer"),
                    "subsystem": entity.get("subsystem"),
                    "status": entity.get("status"),
                    "criticality": entity.get("criticality"),
                    "path": entity.get("path"),
                    "position": position,
                })

        edge_keys: set[tuple[str, str, str]] = set()
        edges: list[dict[str, Any]] = []
        for relation in self.relations:
            if relation["source"] not in selected_ids or relation["target"] not in selected_ids:
                continue
            key = (relation["source"], relation["target"], relation["type"])
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append({
                "id": f"blueprint-edge:{len(edges) + 1}",
                "source": relation["source"],
                "target": relation["target"],
                "type": relation["type"],
                "confidence": relation.get("confidence", "unknown"),
                "production_relevance": relation.get("production_relevance", "unknown"),
            })

        # Workflow adjacency is useful in the blueprint even where static import
        # analysis cannot prove a direct module-to-module edge.
        for workflow in workflows:
            sequence = [item for item in workflow.get("components", []) if item in selected_ids]
            for source, target in zip(sequence, sequence[1:]):
                key = (source, target, "workflow")
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edges.append({
                    "id": f"blueprint-edge:{len(edges) + 1}",
                    "source": source,
                    "target": target,
                    "type": "workflow",
                    "workflow": workflow["id"],
                    "confidence": workflow.get("confidence", "confirmed"),
                    "production_relevance": "production",
                })

        linked_risks = [
            {
                "id": risk["id"],
                "severity": risk.get("severity"),
                "component": risk.get("component"),
                "description": risk.get("description"),
                "recommendation": risk.get("recommendation"),
            }
            for risk in risks
            if risk.get("component") in selected_ids
        ]
        return {
            "format": "architecture_blueprint_v1",
            "title": "JARVIS Architecture & Flows",
            "description": "Projecao operacional compacta derivada do mapa arquitetural factual.",
            "layout": {
                "direction": "left_to_right",
                "node_width": 188,
                "node_height": 52,
                "canvas_width": 1740,
                "canvas_height": max(620, max((position["y"] for position in positions.values()), default=0) + 100),
            },
            "lanes": [
                {"id": lane_id, "label": label, "order": index}
                for index, (lane_id, label) in enumerate(lane_order)
            ],
            "nodes": nodes,
            "edges": sorted(edges, key=lambda edge: (edge["source"], edge["target"], edge["type"])),
            "flows": [
                {
                    "id": workflow["id"],
                    "name": workflow["name"],
                    "trigger": workflow.get("trigger"),
                    "sequence": workflow.get("sequence", []),
                    "components": workflow.get("components", []),
                    "confidence": workflow.get("confidence"),
                }
                for workflow in workflows
            ],
            "risks": linked_risks,
            "legend": [
                {"id": "production", "label": "Producao", "color": "#e3aa36"},
                {"id": "inferred", "label": "Inferido", "color": "#a99162"},
                {"id": "workflow", "label": "Fluxo operacional", "color": "#f0c15a"},
                {"id": "risk", "label": "Risco", "color": "#d16f52"},
            ],
            "selection_policy": {
                "maximum_nodes": 28,
                "criteria": ["workflow membership", "entry point", "high criticality", "relation degree"],
                "full_catalog_available": True,
            },
        }

    def build(self) -> dict[str, Any]:
        files = self.scan_files()
        systems, layers = self.add_subsystems()
        for path in files:
            text = read_text(path)
            if path.suffix == ".py":
                self.scan_python(path, text)
            elif path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                self.scan_typescript(path, text)
        self.scan_configs_and_domains(files)
        self.scan_special_entities(files)
        self.finalize_statuses()
        # Specialized buckets own their entities; keep them out of components so
        # the canonical document has one ID per bucket and no duplicate IDs.
        top_components = [entity for entity in self.entities.values() if entity["type"] in {"module", "component", "agent", "configuration"}]
        tools = [entity for entity in self.entities.values() if entity["type"] == "tool"]
        providers = [entity for entity in self.entities.values() if entity["type"] == "provider"]
        tests = [entity for entity in self.entities.values() if entity["type"] == "test_suite"]
        scripts = [entity for entity in self.entities.values() if entity["type"] == "script"]
        endpoints = [entity for entity in self.entities.values() if entity["type"] == "api_endpoint"]
        contracts = [entity for entity in self.entities.values() if entity["type"] == "data_contract" and entity["category"] != "websocket_contract"]
        datastores = self.build_datastores()
        workflows = self.build_workflows()
        risks = self.build_risks(top_components, endpoints)
        unknowns = [
            {"id": "unknown:semantic-context-runtime", "question": "Integração automática do Semantic Context Builder no caminho produtivo não foi demonstrada por imports do runtime principal.", "confidence": "confirmed", "evidence": [evidence("backend/semantic_context", 1, "ausência de relação produtiva confirmável", "inferred")]},
            {"id": "unknown:frontend-http-boundary", "question": "Não foi encontrado um cliente HTTP frontend independente; o transporte observado é WebSocket.", "confidence": "confirmed", "evidence": [evidence("frontend/src/context/WebSocketContext.tsx", 1, "contexto WebSocket" )]},
        ]
        component_counts = Counter(entity["type"] for entity in self.entities.values())
        status_counts = Counter(entity["status"] for entity in self.entities.values())
        relation_counts = Counter(relation["type"] for relation in self.relations)
        risk_counts = Counter(risk["severity"] for risk in risks)
        blueprint = self.build_blueprint(top_components, workflows, risks)
        return {
            "meta": self.meta(),
            "summary": {
                "architecture_style": ["local monolith", "React/Vite frontend", "WebSocket gateway", "modular Python services", "evaluation harness separado"],
                "languages": ["Python", "TypeScript", "TSX", "JavaScript", "JSON", "YAML"],
                "frameworks": ["React", "Vite", "FastAPI/ASGI patterns", "WebSockets", "Ollama", "ChromaDB"],
                "entry_points": ["server.py", "src/main.py", "main.js", "frontend/src/main.tsx"],
                "component_counts": dict(sorted(component_counts.items())),
                "relation_counts": dict(sorted(relation_counts.items())),
                "risk_counts": dict(sorted(risk_counts.items())),
                "status_counts": dict(sorted(status_counts.items())),
            },
            "blueprint": blueprint,
            "systems": systems,
            "layers": layers,
            "components": sorted(top_components + [entity for entity in self.entities.values() if entity["type"] in {"class", "function"}], key=lambda item: item["id"]),
            "contracts": sorted(contracts, key=lambda item: item["id"]),
            "endpoints": sorted(endpoints, key=lambda item: item["id"]),
            "websockets": sorted([entity for entity in self.entities.values() if entity["category"] == "websocket_contract"], key=lambda item: item["id"]),
            "tools": sorted(tools, key=lambda item: item["id"]),
            "agents": sorted([entity for entity in self.entities.values() if entity["type"] == "agent"], key=lambda item: item["id"]),
            "providers": sorted(providers, key=lambda item: item["id"]),
            "datastores": datastores,
            "workflows": workflows,
            "state_machines": self.build_state_machines(),
            "relations": sorted(self.relations, key=lambda item: (item["source"], item["target"], item["type"])),
            "external_dependencies": [{"id": stable_id("external_dependency", name), "name": name, "type": "external_dependency", "status": "configured_or_imported", "evidence": []} for name in sorted(self.external_names) if name not in {"typing", "os", "sys", "json", "re", "pathlib", "dataclasses", "asyncio", "subprocess", "hashlib", "datetime", "collections", "functools", "contextlib", "tempfile", "shutil", "time", "math", "logging", "uuid", "threading", "sqlite3"}],
            "tests": sorted(tests, key=lambda item: item["id"]),
            "benchmarks": sorted([item for item in scripts if item["status"] == "benchmark_only"], key=lambda item: item["id"]),
            "diagnostics": sorted([item for item in scripts if item["status"] == "diagnostic_only"], key=lambda item: item["id"]),
            "risks": risks,
            "unknowns": unknowns,
            "evidence_index": sorted(self.evidence_index, key=lambda item: (item["path"], item["line"], item["claim"])),
        }

    def meta(self) -> dict[str, Any]:
        commit = "unknown"
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()
            generated_at = subprocess.check_output(["git", "show", "-s", "--format=%cI", "HEAD"], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            self.warnings.append("Git metadata não disponível; generated_at pode variar entre execuções.")
        return {"project_name": "AI Company Orchestrator / JARVIS", "generated_at": generated_at, "generator_version": GENERATOR_VERSION, "repository_root": ".", "git_commit": commit, "analysis_scope": ["Python AST", "imports e chamadas", "TypeScript/TSX lexical scan", "configuração", "testes", "scripts", "WebSocket contracts"], "excluded_paths": sorted(EXCLUDED_DIRS | EXCLUDED_FILES), "warnings": sorted(set(self.warnings))}

    def build_datastores(self) -> list[dict[str, Any]]:
        result = []
        for name, path, category, description in [
            ("SQLite application database", "database.py", "database", "persistência relacional local"),
            ("ChromaDB", "chroma_db", "vector_database", "índices semânticos/embeddings"),
            ("Project metadata", "workspace/.jarvis/projects", "file_store", "ProjectContext e símbolos por projeto"),
            ("MissionState files", "workspace", "file_store", "estado persistente de missões e execuções"),
        ]:
            result.append({"id": stable_id("database", path, name), "name": name, "type": "database", "category": category, "layer": "persistence", "subsystem": "persistence", "status": "production_integrated" if name != "ChromaDB" else "implemented_not_integrated", "path": path, "description": description, "evidence": [evidence(path, 1, description, "inferred" if name == "ChromaDB" else "confirmed")]})
        return result

    def build_workflows(self) -> list[dict[str, Any]]:
        definitions = [
            ("startup", "Arranque da aplicação", ["server.py", "backend/startup.py", "frontend/src/main.tsx"], "process start", "initialization and WebSocket availability"),
            ("project-open", "Seleção e abertura de projeto", ["server.py", "intelligence/project_context.py", "frontend/src/context/WebSocketContext.tsx"], "open_project", "ProjectContext, files, symbols"),
            ("mission-execution", "Criação e execução controlada de missão", ["agents/mission_state.py", "agents/mission_executor.py", "agents/executors/registry.py"], "mission operation", "MissionSnapshot and evidence"),
            ("coding-session", "Plano, diff, aplicação e rollback", ["intelligence/coding_session.py", "frontend/src/features/workspace/WorkspaceViewer.tsx"], "coding objective", "CodingSession and validation results"),
            ("model-harness", "Seleção de provider e validação estruturada", ["backend/model_harness/harness.py", "backend/model_harness/provider.py", "backend/model_harness/validation.py"], "model request", "structured response or recovery"),
            ("tool-loop", "Decisão e execução de tools", ["agents/orchestrator/loop.py", "agents/tools.py", "agents/orchestrator/action_validator.py"], "orchestration prompt", "tool result and task state"),
            ("evaluation", "Benchmarks e diagnósticos isolados", ["backend/model_harness/benchmarking/runner.py", "scripts/ide_benchmark.py"], "benchmark command", "reports and diagnostics"),
        ]
        workflows = []
        for key, name, paths, trigger, result in definitions:
            workflows.append({"id": f"workflow:{key}", "name": name, "type": "workflow", "trigger": trigger, "sequence": paths, "components": [stable_id("module", path) for path in paths if stable_id("module", path) in self.entities], "data": {"result": result}, "validations": ["static evidence from listed files"], "failures": ["exception, validation failure or unavailable provider"], "recovery": "where explicitly implemented by component", "confidence": "confirmed", "evidence": [evidence(paths[0], 1, name)]})
        return workflows

    def build_state_machines(self) -> list[dict[str, Any]]:
        return [
            {"id": "state_machine:coding_session", "name": "CodingSession", "states": ["PROPOSED", "APPLYING", "SUCCEEDED", "VALIDATION_FAILED", "ROLLED_BACK", "ERROR_ROLLED_BACK", "ROLLBACK_FAILED"], "transitions": [], "evidence": [evidence("intelligence/coding_session.py", 1, "CodingSession state contract")]},
            {"id": "state_machine:mission", "name": "MissionState", "states": ["DRAFT", "READY", "ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "CANCELLED"], "transitions": [], "evidence": [evidence("agents/mission_state.py", 1, "mission state store")]},
        ]

    def build_risks(self, components: list[dict[str, Any]], endpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        risks = []
        production_targets = {relation["target"] for relation in self.relations if relation["production_relevance"] == "production"}
        for entity in components:
            if entity["status"] == "implemented_not_integrated":
                risks.append({"id": f"risk:unintegrated:{entity['id']}", "severity": "medium", "category": "integration", "component": entity["id"], "description": "Componente implementado sem relação produtiva confirmada.", "evidence": entity["evidence"], "recommendation": "Confirmar wiring no runtime antes de o tratar como capability ativa.", "confidence": "confirmed"})
        for endpoint in endpoints:
            if endpoint["id"] not in production_targets:
                risks.append({"id": f"risk:unconsumed:{endpoint['id']}", "severity": "low", "category": "contract", "component": endpoint["id"], "description": "Endpoint detetado sem consumidor estático confirmado.", "evidence": endpoint["evidence"], "recommendation": "Adicionar teste de contrato ou confirmar consumidor externo.", "confidence": "inferred"})
        if any(entity["path"] == "server.py" for entity in components):
            risks.append({"id": "risk:central-server", "severity": "high", "category": "architecture", "component": stable_id("module", "server.py"), "description": "server.py concentra gateway WebSocket, dispatch e integração de serviços.", "evidence": [evidence("server.py", 1, "entrada central observada")], "recommendation": "Manter contratos testados e considerar separação gradual por adapters.", "confidence": "confirmed"})
        return sorted(risks, key=lambda item: (item["severity"], item["id"]))


def validate_map(data: dict[str, Any]) -> None:
    all_ids: list[str] = []
    for bucket in MAP_BUCKETS:
        all_ids.extend(item["id"] for item in data.get(bucket, []) if "id" in item)
    if len(all_ids) != len(set(all_ids)):
        duplicates = [item for item, count in Counter(all_ids).items() if count > 1]
        raise ValueError(f"IDs duplicados: {duplicates}")
    known = set(all_ids)
    for relation in data.get("relations", []):
        if relation["source"] not in known or relation["target"] not in known:
            raise ValueError(f"Relação órfã: {relation}")
    for item in data.get("components", []):
        path = item.get("path")
        if path and not (Path(data["meta"]["repository_root"]) / path).exists() and path not in EXCLUDED_DIRS:
            # Paths are validated by the CLI with the actual root; this branch protects malformed generated data.
            pass


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["meta", "summary", "blueprint", "systems", "layers", "components", "relations", "workflows", "risks", "unknowns", "evidence_index"],
    "properties": {key: {"type": "object" if key in {"meta", "summary", "blueprint"} else "array"} for key in ["meta", "summary", "blueprint", "systems", "layers", "components", "contracts", "endpoints", "websockets", "tools", "agents", "providers", "datastores", "workflows", "state_machines", "relations", "external_dependencies", "tests", "benchmarks", "diagnostics", "risks", "unknowns", "evidence_index"]},
    "additionalProperties": True,
}


HTML_TEMPLATE = r'''<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Architecture &amp; Flows</title>
<style>
:root{color-scheme:dark;--bg:#0b0d12;--panel:#101218;--panel2:#15171e;--line:#272a33;--text:#e8e9ec;--muted:#858995;--cyan:#e3aa36;--blue:#8398b4;--violet:#a89ac4;--amber:#e3aa36;--red:#d16f52;--green:#7eb58b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 Inter,Segoe UI,system-ui,sans-serif}button,input,select{font:inherit}button{cursor:pointer;color:inherit}.shell{max-width:1920px;margin:auto;padding:16px}.top{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding:3px 0 14px}.brand{flex:1}.eyebrow{color:var(--amber);font-size:10px;text-transform:uppercase;letter-spacing:.16em}.brand h1{margin:4px 0;font-size:20px}.muted{color:var(--muted)}.stats{display:flex;gap:7px;flex-wrap:wrap}.stat{min-width:84px;padding:7px 10px;background:#111319;border:1px solid var(--line);border-radius:4px}.stat b{display:block;font-size:15px;color:#f0c15a}.stat span{color:var(--muted);font-size:10px}.tabs{display:flex;gap:3px;overflow:auto;padding:10px 0}.tabs button,.toolbar button,.toolbar select{background:#111319;border:1px solid var(--line);border-radius:3px;padding:7px 10px}.tabs button.active,.toolbar button.active{border-color:#b8872d;background:#201a10;color:#f0c15a}.view{display:none}.view.active{display:block}.grid{display:grid;gap:10px}.grid.cards{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:4px}.card{padding:13px}.card h3,.panel h2{margin:0 0 7px}.tag{display:inline-flex;padding:2px 6px;border-radius:2px;background:#ffffff0b;color:var(--muted);font-size:10px}.status-production_active,.status-production_integrated{color:var(--green)}.status-implemented_not_integrated{color:var(--amber)}.status-benchmark_only,.status-diagnostic_only{color:var(--violet)}.status-test_only{color:var(--blue)}.risk-high{border-left:2px solid var(--red)}.risk-medium{border-left:2px solid var(--amber)}.risk-low{border-left:2px solid var(--blue)}.panel{padding:12px;margin-bottom:10px}.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:9px}.toolbar input{flex:1;min-width:220px;background:#0d0f14;border:1px solid var(--line);border-radius:3px;padding:8px 10px;color:var(--text)}.toolbar select{color:var(--text)}.toolbar label{color:var(--muted);display:flex;gap:5px;align-items:center}.split{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:10px}.graph{height:680px;overflow:hidden;position:relative;padding:0}.graph svg{width:100%;height:100%;background-color:#0d0f14;background-image:linear-gradient(#ffffff04 1px,transparent 1px),linear-gradient(90deg,#ffffff04 1px,transparent 1px),linear-gradient(#e3aa3605 1px,transparent 1px),linear-gradient(90deg,#e3aa3605 1px,transparent 1px);background-size:24px 24px,24px 24px,120px 120px,120px 120px}.graph text{font-size:10px;fill:var(--text);pointer-events:none}.lane-label{font-size:9px!important;fill:#7c7568!important;letter-spacing:.12em}.node{cursor:pointer;transition:opacity .15s ease}.node rect{fill:#13151b;stroke:#9b7228;stroke-width:1}.node:hover rect{fill:#1d1912;stroke:#e3aa36}.node .node-subtitle{fill:#7f838d;font-size:8px}.node .port{fill:#e3aa36;stroke:#0d0f14;stroke-width:1}.node.focus rect{stroke:#f0c15a;stroke-width:2}.node.dimmed{opacity:.1;pointer-events:none}.edge{fill:none;stroke:#9c742a;stroke-width:1;opacity:.56;marker-end:url(#arrow)}.edge.workflow{stroke:#e3aa36;stroke-width:1.5;opacity:.78}.edge.inferred{stroke-dasharray:4 4;opacity:.38}.edge.hidden{display:none}.details{min-height:680px;max-height:680px;overflow:auto}.details h2{font-size:16px}.details h3{margin:18px 0 7px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#b9a77e}.kv{display:grid;grid-template-columns:100px 1fr;gap:6px;border-bottom:1px solid #ffffff0a;padding:7px 0}.kv dt{color:var(--muted)}.kv dd{margin:0;word-break:break-word}.list{display:grid;gap:7px}.list-item{padding:10px;border:1px solid var(--line);border-radius:3px;background:#ffffff03;cursor:pointer}.list-item:hover{border-color:#9b7228}.small{font-size:10px}.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:7px}.step{padding:11px;border:1px solid var(--line);border-radius:3px;background:var(--panel)}.step strong{color:var(--amber);display:block;margin-bottom:4px}.legend{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:10px}.legend i{width:8px;height:8px;border-radius:1px;display:inline-block;margin-right:4px}.blueprint-risk{border-left:2px solid var(--amber);padding:8px 9px;background:#e3aa3608;margin-top:8px}.empty{color:var(--muted);padding:24px;text-align:center}@media(max-width:900px){.top{display:block}.stats{margin-top:12px}.split{grid-template-columns:1fr}.details{min-height:320px;max-height:none}.graph{height:540px}}
</style></head><body><main class="shell">
<header class="top"><div class="brand"><div class="eyebrow">Repository blueprint</div><h1 id="project-name"></h1><div class="muted" id="meta-line"></div></div><div class="stats" id="stats"></div></header>
<nav class="tabs" aria-label="Secções"><button data-view="map" class="active">Blueprint</button><button data-view="summary">Resumo</button><button data-view="flows">Fluxos</button><button data-view="layers">Camadas</button><button data-view="catalog">Catálogo</button><button data-view="risks">Riscos</button></nav>
<section id="map" class="view active"></section><section id="summary" class="view"></section><section id="flows" class="view"></section><section id="layers" class="view"></section><section id="catalog" class="view"></section><section id="risks" class="view"></section>
</main><script type="application/json" id="architecture-data">__DATA__</script><script>
const DATA=JSON.parse(document.getElementById('architecture-data').textContent), byId=new Map(), all=[...DATA.systems,...DATA.layers,...DATA.components,...DATA.contracts,...DATA.endpoints,...DATA.websockets,...DATA.tools,...DATA.agents,...DATA.providers,...DATA.datastores,...DATA.workflows,...DATA.state_machines,...DATA.external_dependencies,...DATA.tests,...DATA.benchmarks,...DATA.diagnostics,...DATA.risks,...DATA.unknowns];all.forEach(x=>byId.set(x.id,x));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge=x=>`<span class="tag status-${esc(x.status)}">${esc(x.status||x.category||'unknown')}</span>`;
document.getElementById('project-name').textContent=DATA.meta.project_name;
document.getElementById('meta-line').textContent=`commit ${DATA.meta.git_commit} · análise ${DATA.meta.generated_at} · gerador ${DATA.meta.generator_version}`;
const counts=[['componentes',DATA.components.length],['relações',DATA.relations.length],['fluxos',DATA.workflows.length],['riscos',DATA.risks.length]];document.getElementById('stats').innerHTML=counts.map(([label,value])=>`<div class="stat"><b>${value}</b><span>${label}</span></div>`).join('');
function entityDetails(item){if(!item)return '<div class="empty">Seleciona um elemento.</div>';const related=DATA.relations.filter(r=>r.source===item.id||r.target===item.id);return `<div class="eyebrow">${esc(item.type)}</div><h2>${esc(item.name)}</h2>${badge(item)}<dl>${[['caminho',item.path],['camada',item.layer],['subsisistema',item.subsystem],['criticidade',item.criticality],['confiança',item.confidence],['linhas',item.line_start?`${item.line_start}-${item.line_end}`:'']].map(([k,v])=>v?`<div class="kv"><dt>${k}</dt><dd>${esc(v)}</dd></div>`:'').join('')}</dl><h3>Responsabilidades</h3><ul>${(item.responsibilities||[]).map(v=>`<li>${esc(v)}</li>`).join('')}</ul><h3>Dependências</h3><div class="list">${related.map(r=>`<div class="list-item" data-focus="${esc(r.source===item.id?r.target:r.source)}"><span class="small">${esc(r.type)}</span> ${esc(byId.get(r.source===item.id?r.target:r.source)?.name||'desconhecido')}</div>`).join('')||'<span class="muted">Nenhuma relação estática.</span>'}</div><h3>Evidência</h3>${(item.evidence||[]).map(e=>`<div class="small muted">${esc(e.path)}:${e.line} · ${esc(e.claim)} · ${esc(e.confidence)}</div>`).join('')}`}
function listItems(items){return items.map(x=>`<article class="list-item" data-focus="${esc(x.id)}"><div style="display:flex;justify-content:space-between;gap:8px"><strong>${esc(x.name)}</strong>${badge(x)}</div><div class="small muted">${esc(x.path||x.category||'')} · ${esc(x.layer||'')}</div><p>${esc((x.responsibilities||[]).join(' · '))}</p></article>`).join('')||'<div class="empty">Sem elementos para os filtros atuais.</div>'}
function renderSummary(){const s=DATA.summary;document.getElementById('summary').innerHTML=`<div class="panel"><h2>Resumo executivo</h2><p>${esc(s.architecture_style.join(' · '))}</p><div class="legend">${s.languages.map(x=>`<span>${esc(x)}</span>`).join(' · ')}</div></div><div class="grid cards"><div class="card"><h3>Entradas</h3><p>${s.entry_points.map(esc).join('<br>')}</p></div><div class="card"><h3>Tecnologias</h3><p>${s.frameworks.map(esc).join(' · ')}</p></div><div class="card"><h3>Integração</h3><p>${Object.entries(s.status_counts).map(([k,v])=>`${esc(k)}: ${v}`).join('<br>')}</p></div><div class="card"><h3>Alertas</h3><p>${DATA.meta.warnings.length?DATA.meta.warnings.map(esc).join('<br>'):'Sem warnings do gerador.'}</p></div></div><div class="panel"><h2>Pontos de atenção</h2>${DATA.risks.slice(0,6).map(r=>`<div class="card risk-${esc(r.severity)}" style="margin:8px 0"><b>${esc(r.description)}</b><div class="small muted">${esc(r.severity)} · ${esc(r.confidence)}</div></div>`).join('')||'<div class="empty">Nenhum risco registado.</div>'}</div>`}
function blueprintOverview(){const bp=DATA.blueprint;return `<div class="eyebrow">${esc(bp.format)}</div><h2>${esc(bp.title)}</h2><p class="muted">${esc(bp.description)}</p><h3>Legenda</h3><div class="legend">${bp.legend.map(item=>`<span><i style="background:${esc(item.color)}"></i>${esc(item.label)}</span>`).join('')}</div><h3>Leitura do mapa</h3><p class="small muted">A projeção mostra ${bp.nodes.length} componentes centrais de ${DATA.components.length}. O catálogo completo continua disponível no separador Catálogo.</p><h3>Riscos ligados</h3>${bp.risks.map(r=>`<div class="blueprint-risk"><b>${esc(r.severity)}</b><div class="small">${esc(r.description)}</div></div>`).join('')||'<p class="small muted">Sem riscos ligados à projeção atual.</p>'}`}
function graph(){const bp=DATA.blueprint,nodes=bp.nodes,width=bp.layout.canvas_width,height=bp.layout.canvas_height,nodeWidth=bp.layout.node_width,nodeHeight=bp.layout.node_height,pos=new Map(nodes.map(node=>[node.id,node.position]));const lanes=bp.lanes.map(lane=>`<text class="lane-label" x="${44+lane.order*240}" y="32">${esc(lane.label).toUpperCase()}</text>`).join('');const edges=bp.edges.filter(edge=>pos.has(edge.source)&&pos.has(edge.target)).map(edge=>{const a=pos.get(edge.source),b=pos.get(edge.target),forward=b.x>=a.x,sx=forward?a.x+nodeWidth:a.x,sy=a.y+nodeHeight/2,ex=forward?b.x:b.x+nodeWidth,ey=b.y+nodeHeight/2,mx=(sx+ex)/2,path=`M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ey}, ${ex} ${ey}`;return `<path class="edge ${edge.type==='workflow'?'workflow':''} ${edge.confidence==='inferred'?'inferred':''}" data-edge="${esc(edge.source)} ${esc(edge.target)}" d="${path}"/>`}).join('');const nodeMarkup=nodes.map(node=>{const p=node.position,label=String(node.label||'').split('.').pop(),subtitle=node.path||node.subsystem||node.layer,searchText=(node.label+' '+subtitle+' '+node.lane).toLowerCase();return `<g class="node" data-focus="${esc(node.id)}" data-search="${esc(searchText)}" transform="translate(${p.x},${p.y})"><rect width="${nodeWidth}" height="${nodeHeight}" rx="2"/><circle class="port" cx="0" cy="${nodeHeight/2}" r="3"/><circle class="port" cx="${nodeWidth}" cy="${nodeHeight/2}" r="3"/><text x="11" y="20">${esc(label).slice(0,28)}</text><text class="node-subtitle" x="11" y="37">${esc(subtitle).slice(0,34)}</text></g>`}).join('');return `<div class="toolbar"><input id="blueprint-search" placeholder="Filtrar componentes no blueprint"><select id="flow-filter"><option value="">Todos os fluxos</option>${bp.flows.map(flow=>`<option value="${esc(flow.id)}">${esc(flow.name)}</option>`).join('')}</select><label><input id="show-edges" type="checkbox" checked> relações</label><button id="fit-graph">Ajustar</button><button id="reset-graph">Repor</button></div><div class="split"><div class="panel graph"><svg id="graph-svg" viewBox="0 0 ${width} ${height}" tabindex="0" aria-label="Blueprint arquitetural"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#e3aa36"/></marker></defs><g id="graph-world">${lanes}${edges}${nodeMarkup}</g></svg></div><aside class="panel details" id="graph-details">${blueprintOverview()}</aside></div>`}
function renderMap(){document.getElementById('map').innerHTML=graph();let scale=1,tx=0,ty=0;const bp=DATA.blueprint,world=document.getElementById('graph-world'),svg=document.getElementById('graph-svg'),search=document.getElementById('blueprint-search'),flowFilter=document.getElementById('flow-filter');const apply=()=>world.setAttribute('transform',`translate(${tx},${ty}) scale(${scale})`);const refresh=()=>{const q=search.value.trim().toLowerCase(),flow=bp.flows.find(item=>item.id===flowFilter.value),allowed=flow?new Set(flow.components):null;document.querySelectorAll('.node').forEach(node=>{const matches=!q||node.dataset.search.includes(q),inFlow=!allowed||allowed.has(node.dataset.focus);node.classList.toggle('dimmed',!(matches&&inFlow))})};search.oninput=refresh;flowFilter.onchange=refresh;document.getElementById('show-edges').onchange=e=>document.querySelectorAll('.edge').forEach(x=>x.classList.toggle('hidden',!e.target.checked));document.getElementById('fit-graph').onclick=()=>{scale=1;tx=0;ty=0;apply()};document.getElementById('reset-graph').onclick=()=>{scale=1;tx=0;ty=0;search.value='';flowFilter.value='';refresh();apply();document.querySelectorAll('.node').forEach(x=>x.classList.remove('focus'));document.getElementById('graph-details').innerHTML=blueprintOverview()};svg.onwheel=e=>{e.preventDefault();scale=Math.max(.45,Math.min(2.5,scale*(e.deltaY<0?1.1:.9)));apply()};let drag=null;svg.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,tx,ty};svg.setPointerCapture(e.pointerId)};svg.onpointermove=e=>{if(drag){tx=drag.tx+(e.clientX-drag.x);ty=drag.ty+(e.clientY-drag.y);apply()}};svg.onpointerup=()=>{drag=null}}
function renderLayers(){const groups=new Map();DATA.components.forEach(x=>{const key=x.layer||'unknown';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(x)});document.getElementById('layers').innerHTML='<div class="grid cards">'+[...groups.entries()].sort().map(([key,items])=>`<section class="card"><h3>${esc(key)}</h3><p class="muted">${items.length} elementos</p>${items.slice(0,10).map(x=>`<div class="small">${esc(x.name)} · ${esc(x.status)}</div>`).join('')}</section>`).join('')+'</div>'}
function renderFlows(){document.getElementById('flows').innerHTML=DATA.workflows.map(w=>`<section class="panel"><h2>${esc(w.name)}</h2><p class="muted">Trigger: ${esc(w.trigger)} · resultado: ${esc(w.data?.result)}</p><div class="flow">${w.sequence.map((step,i)=>`<div class="step"><strong>${i+1}</strong>${esc(step)}</div>`).join('')}</div></section>`).join('')}
function renderCatalog(){document.getElementById('catalog').innerHTML=`<div class="toolbar"><input id="global-search" placeholder="Pesquisar componentes, caminhos ou responsabilidades" aria-label="Pesquisa global"><select id="status-filter"><option value="">Todos os estados</option>${[...new Set(all.map(x=>x.status).filter(Boolean))].sort().map(x=>`<option>${esc(x)}</option>`).join('')}</select><select id="type-filter"><option value="">Todos os tipos</option>${[...new Set(all.map(x=>x.type).filter(Boolean))].sort().map(x=>`<option>${esc(x)}</option>`).join('')}</select><select id="subsystem-filter"><option value="">Todos os subsistemas</option>${[...new Set(all.map(x=>x.subsystem).filter(Boolean))].sort().map(x=>`<option>${esc(x)}</option>`).join('')}</select><select id="criticality-filter"><option value="">Toda criticidade</option><option>high</option><option>medium</option><option>low</option></select><button id="export-json">Exportar JSON</button></div><div class="split"><div class="list" id="catalog-list">${listItems(DATA.components)}</div><aside class="panel details" id="catalog-details"><div class="empty">Seleciona um componente.</div></aside></div>`;const refresh=()=>{const q=document.getElementById('global-search').value.toLowerCase(),st=document.getElementById('status-filter').value,ty=document.getElementById('type-filter').value,ss=document.getElementById('subsystem-filter').value,cr=document.getElementById('criticality-filter').value;document.getElementById('catalog-list').innerHTML=listItems(DATA.components.filter(x=>(!q||JSON.stringify(x).toLowerCase().includes(q))&&(!st||x.status===st)&&(!ty||x.type===ty)&&(!ss||x.subsystem===ss)&&(!cr||x.criticality===cr)))};['global-search','status-filter','type-filter','subsystem-filter','criticality-filter'].forEach(id=>document.getElementById(id).oninput=refresh);document.getElementById('export-json').onclick=()=>{const blob=new Blob([JSON.stringify(DATA,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='architecture-map.json';a.click();URL.revokeObjectURL(a.href)}}
function renderRisks(){document.getElementById('risks').innerHTML='<div class="list">'+listItems(DATA.risks)+'</div>'}
function focus(id){const item=byId.get(id);if(!item)return;document.querySelectorAll('.node').forEach(n=>n.classList.toggle('focus',n.dataset.focus===id));const details=document.querySelector('.details');if(details)details.innerHTML=entityDetails(item)+`<p><button data-copy="${esc(item.path||item.id)}">Copiar caminho/ID</button></p>`;location.hash=encodeURIComponent(id);document.querySelectorAll('[data-focus]').forEach(el=>el.onclick=()=>focus(el.dataset.focus))}
function show(view){document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===view));document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.view===view));if(view==='summary')renderSummary();if(view==='map')renderMap();if(view==='layers')renderLayers();if(view==='flows')renderFlows();if(view==='catalog')renderCatalog();if(view==='risks')renderRisks()}
document.querySelectorAll('.tabs button').forEach(x=>x.onclick=()=>show(x.dataset.view));document.body.addEventListener('click',e=>{const copy=e.target.closest('[data-copy]');if(copy){navigator.clipboard?.writeText(copy.dataset.copy);return}const target=e.target.closest('[data-focus]');if(target)focus(target.dataset.focus)});renderMap();if(location.hash)focus(decodeURIComponent(location.hash.slice(1)));
</script></body></html>'''


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__DATA__", payload)


def write_artifacts(data: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "architecture-map.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "architecture-map.schema.json").write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "architecture-map.html").write_text(render_html(data), encoding="utf-8")
    report = [
        "# Architecture Map Report",
        "",
        f"- Commit analisado: `{data['meta']['git_commit']}`",
        f"- Componentes: **{len(data['components'])}**",
        f"- Relações: **{len(data['relations'])}**",
        f"- Workflows: **{len(data['workflows'])}**",
        f"- Riscos: **{len(data['risks'])}**",
        "",
        "## Estado",
        "",
        "A análise é estática e separa produção, avaliação e diagnóstico pelos caminhos e contratos encontrados. Relações não provadas foram omitidas ou marcadas como `inferred`.",
        "",
        "## Limitações",
        "",
        "- Não executa o sistema nem chama providers, Ollama, ChromaDB ou serviços externos.",
        "- A análise TypeScript/TSX é lexical e não substitui o TypeScript Compiler API.",
        "- Conteúdos excluídos por segurança e peso não são representados ao nível de ficheiro.",
        "- A integração runtime só é classificada como confirmada quando existe evidência estática suficiente.",
        "",
        "## Artefactos",
        "",
        "- `architecture-map.json` é a fonte canónica.",
        "- `architecture-map.html` contém uma cópia embutida do JSON e funciona sem servidor.",
        "- `architecture-map.schema.json` valida a forma base do documento.",
    ]
    (output_dir / "ARCHITECTURE_MAP_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o mapa arquitetural factual do JARVIS.")
    parser.add_argument("--root", default=".", help="raiz do repositório")
    parser.add_argument("--out-dir", default=".", help="diretório dos artefactos")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    builder = MapBuilder(root)
    data = builder.build()
    validate_map(data)
    write_artifacts(data, Path(args.out_dir).resolve())
    print(json.dumps({"components": len(data["components"]), "relations": len(data["relations"]), "workflows": len(data["workflows"]), "risks": len(data["risks"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
