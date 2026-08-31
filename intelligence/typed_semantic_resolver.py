"""
JARVIS OS — Typed Semantic Resolution & Deep Property Impact Analysis (Fase 10.4)
Motor de inferência de propriedades aninhadas, Type Graph e cálculo de Property Blast Radius.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from enum import IntEnum
import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple


class SourcePriority(IntEnum):
    """Prioridade estrita de fontes para resolução semântica e de tipos."""
    EXPLICIT_TYPE = 1       # TypeScript interface / type alias
    PYDANTIC_MODEL = 2      # Pydantic BaseModel
    DATACLASS = 3           # Python @dataclass
    TYPED_DICT = 4          # Python TypedDict
    JSON_SCHEMA = 5         # JSON Schema formal
    OPENAPI_SPEC = 6        # OpenAPI / Swagger specs
    INFERRED_SCHEMA = 7     # Schema conservador inferido por usos
    AST_USAGE = 8           # Análise de padrões de AST
    LSP_FALLBACK = 9        # Language Server Protocol (tsserver/pyright)
    LLM_SEMANTIC = 10       # Inferência semântica LLM (último recurso)


@dataclass(slots=True)
class PropertyNode:
    """Nó de propriedade no Type Graph com suporte a aninhamento recursivo."""
    name: str
    type_annotation: str = "any"
    is_optional: bool = False
    parent_type: Optional[str] = None
    nested_properties: Dict[str, PropertyNode] = field(default_factory=dict)
    resolution_source: str = "EXPLICIT_TYPE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_annotation": self.type_annotation,
            "is_optional": self.is_optional,
            "parent_type": self.parent_type,
            "resolution_source": self.resolution_source,
            "nested_properties": {k: v.to_dict() for k, v in self.nested_properties.items()},
        }


@dataclass(slots=True)
class PropertyUsage:
    """Registo de uso de uma propriedade no código."""
    file_path: str
    line_number: int
    access_path: List[str]  # ex: ["user", "profile", "settings", "theme"]
    usage_type: str  # PRODUCER, CONSUMER, TEST, API_CONTRACT, SERIALIZATION
    raw_expression: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TypeNode:
    """Nó de tipo registrado no Type Graph."""
    name: str
    kind: str  # INTERFACE, TYPE_ALIAS, PYDANTIC, DATACLASS, TYPED_DICT, INFERRED_SCHEMA
    file_path: str
    line_number: int
    properties: Dict[str, PropertyNode] = field(default_factory=dict)
    resolution_source: str = "EXPLICIT_TYPE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "resolution_source": self.resolution_source,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
        }


@dataclass(slots=True)
class PropertyBlastRadius:
    """Raio de impacto profundo decorrente da modificação de uma propriedade."""
    target_property_path: str
    declarations: List[Dict[str, Any]] = field(default_factory=list)
    producers: List[PropertyUsage] = field(default_factory=list)
    consumers: List[PropertyUsage] = field(default_factory=list)
    tests: List[PropertyUsage] = field(default_factory=list)
    api_contracts: List[PropertyUsage] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    confidence_level: str = "HIGH"  # HIGH, MEDIUM, LOW, UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_property_path": self.target_property_path,
            "declarations": self.declarations,
            "producers": [p.to_dict() for p in self.producers],
            "consumers": [c.to_dict() for c in self.consumers],
            "tests": [t.to_dict() for t in self.tests],
            "api_contracts": [a.to_dict() for a in self.api_contracts],
            "affected_files": self.affected_files,
            "confidence_level": self.confidence_level,
        }


class TypedSemanticResolver:
    """Resolvedor semântico de propriedades aninhadas e analisador de impacto profundo."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.types: Dict[str, TypeNode] = {}
        self.usages: List[PropertyUsage] = []
        self.lsp_available: Dict[str, bool] = self._detect_lsp_tools()

    def _detect_lsp_tools(self) -> Dict[str, bool]:
        """Deteta se servidores LSP (tsserver, pyright) estão disponíveis no sistema."""
        return {
            "tsserver": shutil.which("tsserver") is not None or shutil.which("typescript-language-server") is not None,
            "pyright": shutil.which("pyright") is not None or shutil.which("pyright-langserver") is not None,
        }

    def scan(self) -> TypedSemanticResolver:
        """Examina todo o repositório e constrói o Type Graph e mapa de acessos a propriedades."""
        self.types.clear()
        self.usages.clear()

        for root, _, files in os.walk(self.workspace_root):
            if any(p in root for p in (".git", "node_modules", "__pycache__", "venv", ".pytest_cache")):
                continue
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace(os.sep, "/")
                lower = file.lower()

                if lower.endswith(".py"):
                    self._parse_python_file(abs_path, rel_path)
                elif lower.endswith((".ts", ".tsx", ".js", ".jsx")):
                    self._parse_typescript_file(abs_path, rel_path)
                elif lower.endswith(".json") and "schema" in lower:
                    self._parse_json_schema_file(abs_path, rel_path)

        # Inferência de schemas para objetos sem tipo explícito
        self._infer_missing_schemas()
        return self

    def _parse_python_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._extract_python_class_types(node, rel_path)
            elif isinstance(node, ast.Subscript):
                self._extract_python_subscript_usage(node, rel_path)
            elif isinstance(node, ast.Call):
                self._extract_python_call_usage(node, rel_path)

    def _extract_python_class_types(self, node: ast.ClassDef, rel_path: str) -> None:
        kind = "CLASS"
        source = SourcePriority.DATACLASS.name

        base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
        dec_names = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]

        if "BaseModel" in base_names or any("BaseModel" in getattr(b, "attr", "") for b in node.bases):
            kind = "PYDANTIC"
            source = SourcePriority.PYDANTIC_MODEL.name
        elif "TypedDict" in base_names:
            kind = "TYPED_DICT"
            source = SourcePriority.TYPED_DICT.name
        elif "dataclass" in dec_names:
            kind = "DATACLASS"
            source = SourcePriority.DATACLASS.name

        type_node = TypeNode(
            name=node.name,
            kind=kind,
            file_path=rel_path,
            line_number=node.lineno,
            resolution_source=source,
        )

        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                p_name = item.target.id
                p_type = ast.unparse(item.annotation) if hasattr(ast, "unparse") else "any"
                type_node.properties[p_name] = PropertyNode(
                    name=p_name,
                    type_annotation=p_type,
                    parent_type=node.name,
                    resolution_source=source,
                )
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        type_node.properties[target.id] = PropertyNode(
                            name=target.id,
                            parent_type=node.name,
                            resolution_source=source,
                        )

        self.types[node.name] = type_node

    def _extract_python_subscript_usage(self, node: ast.Subscript, rel_path: str) -> None:
        """Extrai acessos aninhados do tipo data['user']['profile']['settings']."""
        chain = []
        curr = node
        while isinstance(curr, ast.Subscript):
            if isinstance(curr.slice, ast.Constant) and isinstance(curr.slice.value, str):
                chain.append(curr.slice.value)
            curr = curr.value

        if isinstance(curr, ast.Name) and chain:
            chain.append(curr.id)
            chain.reverse()
            usage_type = "TEST" if "test" in rel_path.lower() else "CONSUMER"
            self.usages.append(PropertyUsage(
                file_path=rel_path,
                line_number=node.lineno,
                access_path=chain,
                usage_type=usage_type,
                raw_expression=f"{curr.id}[...]",
            ))

    def _extract_python_call_usage(self, node: ast.Call, rel_path: str) -> None:
        """Extrai chained .get() do tipo data.get('user', {}).get('profile')."""
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            chain = []
            curr = node
            while isinstance(curr, ast.Call) and isinstance(curr.func, ast.Attribute) and curr.func.attr == "get":
                if curr.args and isinstance(curr.args[0], ast.Constant) and isinstance(curr.args[0].value, str):
                    chain.append(curr.args[0].value)
                curr = curr.func.value

            if isinstance(curr, ast.Name) and chain:
                chain.append(curr.id)
                chain.reverse()
                usage_type = "TEST" if "test" in rel_path.lower() else "CONSUMER"
                self.usages.append(PropertyUsage(
                    file_path=rel_path,
                    line_number=node.lineno,
                    access_path=chain,
                    usage_type=usage_type,
                    raw_expression=f"{curr.id}.get(...)",
                ))

    def _parse_typescript_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return

        lines = content.splitlines()

        # 1. Interface e Type Alias TS
        interface_pattern = re.compile(r"(?:export\s+)?interface\s+([a-zA-Z0-9_$]+)\s*\{([^}]+)\}")
        type_pattern = re.compile(r"(?:export\s+)?type\s+([a-zA-Z0-9_$]+)\s*=\s*\{([^}]+)\}")

        for match in interface_pattern.finditer(content):
            name, body = match.group(1), match.group(2)
            self._register_ts_type(name, body, "INTERFACE", rel_path, match.start())

        for match in type_pattern.finditer(content):
            name, body = match.group(1), match.group(2)
            self._register_ts_type(name, body, "TYPE_ALIAS", rel_path, match.start())

        # 2. Destructuring: const { a: { b: { c } } } = obj
        destruct_pattern = re.compile(r"(?:const|let|var)\s+(\{.+?\})\s*=\s*([a-zA-Z0-9_$]+)")
        for idx, line in enumerate(lines, start=1):
            d_match = destruct_pattern.search(line)
            if d_match:
                body = d_match.group(1)
                root_var = d_match.group(2)
                idents = re.findall(r"[a-zA-Z0-9_$]+", body)
                for id_name in idents:
                    self.usages.append(PropertyUsage(
                        file_path=rel_path,
                        line_number=idx,
                        access_path=[root_var, id_name],
                        usage_type="CONSUMER",
                        raw_expression=line.strip(),
                    ))

        # 3. Dot and bracket access: obj.a.b.c / obj["a"]["b"]
        dot_pattern = re.compile(r"([a-zA-Z0-9_$]+(?:\.[a-zA-Z0-9_$]+){2,})")
        for idx, line in enumerate(lines, start=1):
            for m in dot_pattern.finditer(line):
                expr = m.group(1)
                parts = expr.split(".")
                usage_type = "TEST" if "test" in rel_path.lower() else "CONSUMER"
                self.usages.append(PropertyUsage(
                    file_path=rel_path,
                    line_number=idx,
                    access_path=parts,
                    usage_type=usage_type,
                    raw_expression=expr,
                ))

    def _register_ts_type(self, name: str, body: str, kind: str, rel_path: str, offset: int) -> None:
        type_node = TypeNode(
            name=name,
            kind=kind,
            file_path=rel_path,
            line_number=1,
            resolution_source=SourcePriority.EXPLICIT_TYPE.name,
        )
        prop_pattern = re.compile(r"([a-zA-Z0-9_$]+)(\?)?:\s*([^;,\n]+)")
        for p_match in prop_pattern.finditer(body):
            p_name = p_match.group(1)
            is_opt = p_match.group(2) is not None
            p_type = p_match.group(3).strip()
            type_node.properties[p_name] = PropertyNode(
                name=p_name,
                type_annotation=p_type,
                is_optional=is_opt,
                parent_type=name,
                resolution_source=SourcePriority.EXPLICIT_TYPE.name,
            )
        self.types[name] = type_node

    def _parse_json_schema_file(self, abs_path: str, rel_path: str) -> None:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", os.path.splitext(os.path.basename(rel_path))[0])
            type_node = TypeNode(
                name=title,
                kind="JSON_SCHEMA",
                file_path=rel_path,
                line_number=1,
                resolution_source=SourcePriority.JSON_SCHEMA.name,
            )
            for p_name, p_def in data.get("properties", {}).items():
                type_node.properties[p_name] = PropertyNode(
                    name=p_name,
                    type_annotation=p_def.get("type", "any"),
                    parent_type=title,
                    resolution_source=SourcePriority.JSON_SCHEMA.name,
                )
            self.types[title] = type_node
        except Exception:
            pass

    def _infer_missing_schemas(self) -> None:
        """Sintetiza schemas conservadores a partir de múltiplos acessos consistentes."""
        grouped: Dict[str, Dict[str, Set[str]]] = {}
        for usage in self.usages:
            if len(usage.access_path) >= 2:
                root = usage.access_path[0]
                prop = usage.access_path[1]
                sub = usage.access_path[2] if len(usage.access_path) >= 3 else None
                if root not in self.types:
                    grouped.setdefault(root, {}).setdefault(prop, set())
                    if sub:
                        grouped[root][prop].add(sub)

        for root_name, prop_map in grouped.items():
            if len(prop_map) >= 1:
                inferred_type = TypeNode(
                    name=f"Inferred_{root_name.capitalize()}",
                    kind="INFERRED_SCHEMA",
                    file_path="inferred",
                    line_number=1,
                    resolution_source=SourcePriority.INFERRED_SCHEMA.name,
                )
                for p_name, subs in prop_map.items():
                    nested_dict = {}
                    for sub_name in subs:
                        nested_dict[sub_name] = PropertyNode(
                            name=sub_name,
                            parent_type=p_name,
                            resolution_source=SourcePriority.INFERRED_SCHEMA.name,
                        )
                    inferred_type.properties[p_name] = PropertyNode(
                        name=p_name,
                        parent_type=inferred_type.name,
                        nested_properties=nested_dict,
                        resolution_source=SourcePriority.INFERRED_SCHEMA.name,
                    )
                self.types[inferred_type.name] = inferred_type

    def resolve_property_path(self, type_or_obj_name: str, property_path: List[str]) -> Tuple[str, Optional[PropertyNode]]:
        """Resolve o caminho de propriedades (ex: ['User', 'profile', 'settings', 'theme'])."""
        if not property_path:
            return "UNKNOWN", None

        # 1. Procura em tipos explícitos registrados
        target_type = self.types.get(type_or_obj_name) or self.types.get(f"Inferred_{type_or_obj_name.capitalize()}")
        if not target_type:
            # Fallback por correspondência de nome
            for t_node in self.types.values():
                if t_node.name.lower() == type_or_obj_name.lower():
                    target_type = t_node
                    break

        if not target_type:
            return "UNKNOWN", None

        curr_props = target_type.properties
        last_node: Optional[PropertyNode] = None

        for idx, prop_segment in enumerate(property_path):
            if prop_segment in curr_props:
                last_node = curr_props[prop_segment]
                # Se o tipo da propriedade for outro tipo registado, transita para esse tipo
                nested_type = self.types.get(last_node.type_annotation)
                if nested_type:
                    curr_props = nested_type.properties
                else:
                    curr_props = last_node.nested_properties
            else:
                if idx == 0 and prop_segment == type_or_obj_name:
                    continue
                return "PARTIAL_RESOLUTION" if last_node else "UNKNOWN", last_node

        return "RESOLVED", last_node

    def compute_property_blast_radius(self, target_property_name: str) -> PropertyBlastRadius:
        """Calcula o raio de impacto profundo completo de uma propriedade."""
        declarations = []
        producers = []
        consumers = []
        tests = []
        api_contracts = []
        affected_files: Set[str] = set()

        # 1. Localiza declarações
        for t_name, t_node in self.types.items():
            if target_property_name in t_node.properties:
                p_node = t_node.properties[target_property_name]
                declarations.append({
                    "type_name": t_name,
                    "kind": t_node.kind,
                    "file_path": t_node.file_path,
                    "line_number": t_node.line_number,
                    "source": p_node.resolution_source,
                })
                affected_files.add(t_node.file_path)

        # 2. Localiza usos
        for usage in self.usages:
            if target_property_name in usage.access_path:
                affected_files.add(usage.file_path)
                if usage.usage_type == "TEST":
                    tests.append(usage)
                elif usage.usage_type == "API_CONTRACT":
                    api_contracts.append(usage)
                elif usage.usage_type == "PRODUCER":
                    producers.append(usage)
                else:
                    consumers.append(usage)

        conf = "HIGH" if declarations else ("MEDIUM" if (consumers or tests) else "LOW")
        if not declarations and not consumers and not tests:
            conf = "UNKNOWN"

        return PropertyBlastRadius(
            target_property_path=target_property_name,
            declarations=declarations,
            producers=producers,
            consumers=consumers,
            tests=tests,
            api_contracts=api_contracts,
            affected_files=sorted(affected_files),
            confidence_level=conf,
        )
