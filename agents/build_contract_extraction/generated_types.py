"""
JARVIS OS — Phase 49: Generated Types Extractor
Parses generated TypeScript interfaces/types/enums and Python TypedDicts/Pydantic models/dataclasses.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.build_contract_extraction.models import (
    ArtifactProvenance,
    ContractField,
    ContractType,
    ContractVariant,
    SourceType,
    TypeKind,
)
from agents.build_contract_extraction.provenance import ProvenanceTracker


class GeneratedTypesExtractor:
    """
    Extracts canonical ContractType definitions from generated TypeScript and Python code artifacts.
    Supports interfaces, type aliases, union types, enums, TypedDicts, dataclasses, and Pydantic models.
    """

    # -------------------------------------------------------------
    # TypeScript Type Extraction
    # -------------------------------------------------------------
    @classmethod
    def extract_typescript_types(
        cls,
        code_content: str,
        artifact_path: str = "generated_types.ts",
    ) -> dict[str, ContractType]:
        """Parses TypeScript code to extract interfaces, type unions, and enums."""
        types: dict[str, ContractType] = {}
        prov_base = ProvenanceTracker.create_provenance(
            source_type=SourceType.GENERATED_TYPESCRIPT,
            artifact_path=artifact_path,
            json_pointer="#",
            content=code_content,
        )

        # 1. Extract interfaces: interface UserProfile { id: string; name?: string; ... }
        interface_pattern = re.compile(
            r"export\s+interface\s+(\w+)(?:\s+extends\s+[\w,\s]+)?\s*\{([^}]+)\}",
            re.MULTILINE | re.DOTALL,
        )
        for match in interface_pattern.finditer(code_content):
            name = match.group(1)
            body = match.group(2)
            props = cls._parse_ts_interface_body(body, artifact_path, name)
            types[name] = ContractType(
                type_id=f"ts_{name}",
                name=name,
                kind=TypeKind.OBJECT,
                properties=props,
                language="TypeScript",
                provenance=prov_base,
            )

        # 2. Extract string literal union types: export type EventType = "user.created" | "user.updated" | ...;
        union_pattern = re.compile(
            r"export\s+type\s+(\w+)\s*=\s*([^;]+);",
            re.MULTILINE,
        )
        for match in union_pattern.finditer(code_content):
            name = match.group(1)
            raw_union = match.group(2).strip()
            # Extract string literal members: "val1" | "val2"
            literals = re.findall(r"['\"]([^'\"]+)['\"]", raw_union)
            if literals:
                variants = [
                    ContractVariant(
                        variant_id=f"var_{name}_{lit.replace('.', '_')}",
                        discriminator_value=lit,
                        schema={"type": "string", "enum": [lit]},
                        provenance=prov_base,
                    )
                    for lit in literals
                ]
                types[name] = ContractType(
                    type_id=f"ts_{name}",
                    name=name,
                    kind=TypeKind.UNION,
                    enum_values=literals,
                    variants=variants,
                    language="TypeScript",
                    provenance=prov_base,
                )

        # 3. Extract TypeScript Enums: export enum Status { PENDING = "pending", ACTIVE = "active" }
        enum_pattern = re.compile(
            r"export\s+enum\s+(\w+)\s*\{([^}]+)\}",
            re.MULTILINE | re.DOTALL,
        )
        for match in enum_pattern.finditer(code_content):
            name = match.group(1)
            body = match.group(2)
            enum_vals = []
            for line in body.split(","):
                line = line.strip()
                if "=" in line:
                    val_match = re.search(r"=\s*['\"]?([^'\",\s]+)['\"]?", line)
                    if val_match:
                        enum_vals.append(val_match.group(1))
                elif line:
                    enum_vals.append(line)
            types[name] = ContractType(
                type_id=f"ts_enum_{name}",
                name=name,
                kind=TypeKind.ENUM,
                enum_values=enum_vals,
                language="TypeScript",
                provenance=prov_base,
            )

        return types

    @classmethod
    def _parse_ts_interface_body(
        cls,
        body: str,
        artifact_path: str,
        type_name: str,
    ) -> dict[str, ContractField]:
        """Parses fields from an interface body string."""
        fields: dict[str, ContractField] = {}
        for line in body.strip().split("\n"):
            line = line.strip().rstrip(";,")
            if not line or line.startswith("//") or line.startswith("/*"):
                continue
            # Match: fieldName?: string or fieldName: number
            m = re.match(r"^(\w+)(\?)?\s*:\s*([^;]+)$", line)
            if m:
                fname = m.group(1)
                is_optional = bool(m.group(2))
                ftype = m.group(3).strip()
                f_prov = ProvenanceTracker.create_provenance(
                    source_type=SourceType.GENERATED_TYPESCRIPT,
                    artifact_path=artifact_path,
                    json_pointer=f"#{type_name}/{fname}",
                    content=line,
                )
                fields[fname] = ContractField(
                    field_name=fname,
                    field_type=ftype,
                    required=not is_optional,
                    nullable="null" in ftype.lower() or is_optional,
                    provenance=f_prov,
                )
        return fields

    # -------------------------------------------------------------
    # Python Type Extraction
    # -------------------------------------------------------------
    @classmethod
    def extract_python_types(
        cls,
        code_content: str,
        artifact_path: str = "generated_models.py",
    ) -> dict[str, ContractType]:
        """Parses Python source code AST to extract TypedDicts, Pydantic BaseModels, and dataclasses."""
        types: dict[str, ContractType] = {}
        prov_base = ProvenanceTracker.create_provenance(
            source_type=SourceType.PYTHON_MODEL,
            artifact_path=artifact_path,
            json_pointer="#",
            content=code_content,
        )

        try:
            tree = ast.parse(code_content, filename=artifact_path)
        except SyntaxError:
            return types

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                name = node.name
                base_names = [cls._get_name(b) for b in node.bases]
                is_typed_dict = any("TypedDict" in b for b in base_names)
                is_pydantic = any("BaseModel" in b for b in base_names)
                is_enum = any("Enum" in b for b in base_names)

                if is_enum:
                    enum_vals = []
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    enum_vals.append(target.id)
                    types[name] = ContractType(
                        type_id=f"py_enum_{name}",
                        name=name,
                        kind=TypeKind.ENUM,
                        enum_values=enum_vals,
                        language="Python",
                        provenance=prov_base,
                    )
                elif is_typed_dict or is_pydantic or any(d.id == "dataclass" for d in node.decorator_list if isinstance(d, ast.Name)):
                    props = {}
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            fname = item.target.id
                            ftype = cls._annotation_to_str(item.annotation)
                            is_opt = "Optional" in ftype or item.value is not None
                            f_prov = ProvenanceTracker.create_provenance(
                                source_type=SourceType.PYTHON_MODEL,
                                artifact_path=artifact_path,
                                json_pointer=f"#{name}/{fname}",
                                content=ast.unparse(item) if hasattr(ast, "unparse") else fname,
                            )
                            props[fname] = ContractField(
                                field_name=fname,
                                field_type=ftype,
                                required=not is_opt,
                                nullable="None" in ftype or is_opt,
                                provenance=f_prov,
                            )
                    types[name] = ContractType(
                        type_id=f"py_{name}",
                        name=name,
                        kind=TypeKind.OBJECT,
                        properties=props,
                        language="Python",
                        provenance=prov_base,
                    )

        return types

    @classmethod
    def _get_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{cls._get_name(node.value)}.{node.attr}"
        return ""

    @classmethod
    def _annotation_to_str(cls, node: Optional[ast.AST]) -> str:
        if node is None:
            return "Any"
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
        if isinstance(node, ast.Name):
            return node.id
        return "Any"
