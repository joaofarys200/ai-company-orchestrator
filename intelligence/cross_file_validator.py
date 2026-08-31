"""
JARVIS OS — Cross-File Contract Validator & Dependency Checker (Fase 10.1: Coding Agent 2.1)
Validador determinístico de integridade multi-ficheiro, contratos de API, TypeScript aliases e monorepos.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from intelligence.repository_graph import (
    ApiClientCall,
    ApiEndpoint,
    ModuleImport,
    RepositoryGraph,
    SymbolDefinition,
)


class ContractIssueType(str, Enum):
    MISSING_IMPORT = "MISSING_IMPORT"
    MISSING_EXPORT = "MISSING_EXPORT"
    BROKEN_SCRIPT_LINK = "BROKEN_SCRIPT_LINK"
    BROKEN_CSS_LINK = "BROKEN_CSS_LINK"
    API_CONTRACT_MISMATCH = "API_CONTRACT_MISMATCH"
    TEST_SYMBOL_MISMATCH = "TEST_SYMBOL_MISMATCH"
    STALE_REFERENCE = "STALE_REFERENCE"
    INVALID_PATH_ALIAS = "INVALID_PATH_ALIAS"
    MISSING_WORKSPACE_PACKAGE = "MISSING_WORKSPACE_PACKAGE"
    WRONG_PACKAGE_BOUNDARY = "WRONG_PACKAGE_BOUNDARY"
    STALE_BARREL_EXPORT = "STALE_BARREL_EXPORT"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"


@dataclass(slots=True)
class ContractValidationIssue:
    """Problema ou violação de integridade detetada entre múltiplos ficheiros."""
    issue_type: str
    source_file: str
    line_number: int
    target: str
    message: str
    severity: str = "ERROR"  # ERROR, WARNING
    suggested_fix: str = ""
    context_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationReport:
    """Relatório exaustivo de validação determinística de contratos."""
    is_valid: bool
    total_issues: int
    errors_count: int
    warnings_count: int
    issues: List[ContractValidationIssue]
    contract_mismatches: List[ContractValidationIssue]
    missing_imports: List[ContractValidationIssue]
    broken_links: List[ContractValidationIssue]
    circular_dependencies: List[ContractValidationIssue]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CrossFileValidator:
    """Validador determinístico de contratos entre ficheiros frontend, backend, TypeScript e testes."""

    def __init__(self, repo_graph: RepositoryGraph) -> None:
        self.graph = repo_graph

    def validate(self) -> ValidationReport:
        """Executa validação completa de integridade referencial, aliases e contratos no grafo."""
        issues: List[ContractValidationIssue] = []

        # 1. Validação de Imports, Exports e Aliases
        issues.extend(self._validate_imports_and_exports())

        # 2. Validação de Barrel Files e Re-exports
        issues.extend(self._validate_barrel_re_exports())

        # 3. Validação de Links em Ficheiros HTML
        issues.extend(self._validate_html_asset_links())

        # 4. Validação de Contratos de API (Frontend <-> Backend)
        issues.extend(self._validate_api_contracts())

        # 5. Validação de Referências de Testes
        issues.extend(self._validate_test_references())

        # 6. Validação de Dependências Circulares
        issues.extend(self._validate_circular_dependencies())

        errors = [i for i in issues if i.severity == "ERROR"]
        warnings = [i for i in issues if i.severity == "WARNING"]
        api_mismatches = [i for i in issues if i.issue_type == ContractIssueType.API_CONTRACT_MISMATCH.value]
        missing_imps = [i for i in issues if i.issue_type in (
            ContractIssueType.MISSING_IMPORT.value,
            ContractIssueType.MISSING_EXPORT.value,
            ContractIssueType.INVALID_PATH_ALIAS.value,
            ContractIssueType.MISSING_WORKSPACE_PACKAGE.value,
        )]
        broken_links = [i for i in issues if i.issue_type in (
            ContractIssueType.BROKEN_SCRIPT_LINK.value,
            ContractIssueType.BROKEN_CSS_LINK.value,
        )]
        circ_deps = [i for i in issues if i.issue_type == ContractIssueType.CIRCULAR_DEPENDENCY.value]

        return ValidationReport(
            is_valid=len(errors) == 0,
            total_issues=len(issues),
            errors_count=len(errors),
            warnings_count=len(warnings),
            issues=issues,
            contract_mismatches=api_mismatches,
            missing_imports=missing_imps,
            broken_links=broken_links,
            circular_dependencies=circ_deps,
        )

    def _validate_imports_and_exports(self) -> List[ContractValidationIssue]:
        issues: List[ContractValidationIssue] = []

        for src_file, imp_list in self.graph.imports.items():
            for imp in imp_list:
                # A. Import não resolvido
                if imp.resolved_target is None:
                    # Verifica se parece um alias de tsconfig (ex: '@/...' ou '@core/...')
                    if imp.module_name.startswith("@") or imp.module_name.startswith("~/"):
                        issues.append(ContractValidationIssue(
                            issue_type=ContractIssueType.INVALID_PATH_ALIAS.value,
                            source_file=src_file,
                            line_number=imp.line_number,
                            target=imp.module_name,
                            message=f"Path alias '{imp.module_name}' em '{src_file}' não pôde ser resolvido para nenhum ficheiro existente.",
                            severity="ERROR",
                            suggested_fix=f"Verificar se o ficheiro alvo existe ou corrigir o mapeamento em tsconfig.json paths.",
                        ))
                    elif imp.is_relative:
                        issues.append(ContractValidationIssue(
                            issue_type=ContractIssueType.MISSING_IMPORT.value,
                            source_file=src_file,
                            line_number=imp.line_number,
                            target=imp.module_name,
                            message=f"Módulo relativo '{imp.module_name}' importado em '{src_file}' não foi encontrado no projeto.",
                            severity="ERROR",
                            suggested_fix=f"Criar o ficheiro correspondente a '{imp.module_name}' ou corrigir o caminho de importação.",
                        ))
                    continue

                # B. Se o target existe, validar se os símbolos importados estão definidos nele
                if imp.resolved_target and imp.imported_symbols:
                    target_symbols = {s.name for s in self.graph.file_symbols.get(imp.resolved_target, [])}
                    for sym in imp.imported_symbols:
                        if sym in ("*", "default") or not sym:
                            continue
                        if target_symbols and sym not in target_symbols:
                            issues.append(ContractValidationIssue(
                                issue_type=ContractIssueType.MISSING_EXPORT.value,
                                source_file=src_file,
                                line_number=imp.line_number,
                                target=sym,
                                message=f"Símbolo '{sym}' importado de '{imp.resolved_target}' não está definido nem exportado.",
                                severity="ERROR",
                                suggested_fix=f"Definir '{sym}' em '{imp.resolved_target}' ou atualizar o import em '{src_file}'.",
                                context_data={"resolved_target": imp.resolved_target},
                            ))

        return issues

    def _validate_barrel_re_exports(self) -> List[ContractValidationIssue]:
        """Valida se as declarações export * from './...' em barrel files apontam para ficheiros válidos."""
        issues: List[ContractValidationIssue] = []

        for barrel_file, re_exports in self.graph.barrel_exports.items():
            for re_exp in re_exports:
                src_mod = re_exp["source"]
                target_file = self.graph._resolve_import_path(barrel_file, src_mod)
                if not target_file or target_file not in self.graph.files:
                    issues.append(ContractValidationIssue(
                        issue_type=ContractIssueType.STALE_BARREL_EXPORT.value,
                        source_file=barrel_file,
                        line_number=re_exp.get("line", 1),
                        target=src_mod,
                        message=f"Barrel file '{barrel_file}' tenta re-exportar '{src_mod}' que não existe.",
                        severity="ERROR",
                        suggested_fix=f"Criar o ficheiro '{src_mod}' ou remover a declaração de re-exportação.",
                    ))

        return issues

    def _validate_html_asset_links(self) -> List[ContractValidationIssue]:
        issues: List[ContractValidationIssue] = []

        for ref_type, ref_list in self.graph.references.items():
            if ref_type == "html:script":
                for r in ref_list:
                    if r.symbol_name.startswith("http://") or r.symbol_name.startswith("https://"):
                        continue
                    clean_path = r.symbol_name.lstrip("./").lstrip("/")
                    if clean_path not in self.graph.files and f"public/{clean_path}" not in self.graph.files and f"src/{clean_path}" not in self.graph.files:
                        issues.append(ContractValidationIssue(
                            issue_type=ContractIssueType.BROKEN_SCRIPT_LINK.value,
                            source_file=r.source_file,
                            line_number=r.line_number,
                            target=r.symbol_name,
                            message=f"Ficheiro de script '{r.symbol_name}' referenciado em '{r.source_file}' não existe no projeto.",
                            severity="ERROR",
                            suggested_fix=f"Criar o ficheiro '{clean_path}' ou corrigir o atributo src em '{r.source_file}'.",
                        ))
            elif ref_type == "html:stylesheet":
                for r in ref_list:
                    if r.symbol_name.startswith("http://") or r.symbol_name.startswith("https://"):
                        continue
                    clean_path = r.symbol_name.lstrip("./").lstrip("/")
                    if clean_path not in self.graph.files and f"public/{clean_path}" not in self.graph.files and f"src/{clean_path}" not in self.graph.files:
                        issues.append(ContractValidationIssue(
                            issue_type=ContractIssueType.BROKEN_CSS_LINK.value,
                            source_file=r.source_file,
                            line_number=r.line_number,
                            target=r.symbol_name,
                            message=f"Ficheiro CSS '{r.symbol_name}' referenciado em '{r.source_file}' não existe no projeto.",
                            severity="ERROR",
                            suggested_fix=f"Criar o ficheiro '{clean_path}' ou corrigir a tag link em '{r.source_file}'.",
                        ))

        return issues

    def _validate_api_contracts(self) -> List[ContractValidationIssue]:
        issues: List[ContractValidationIssue] = []

        if not self.graph.endpoints and not self.graph.api_calls:
            return issues

        backend_routes: Dict[str, List[ApiEndpoint]] = {}
        for ep in self.graph.endpoints:
            key = f"{ep.http_method}:{ep.route_path}"
            backend_routes.setdefault(key, []).append(ep)

        for call in self.graph.api_calls:
            call_key = f"{call.http_method}:{call.route_path}"
            if call_key in backend_routes:
                continue

            matching_method_routes = [ep for ep in self.graph.endpoints if ep.http_method == call.http_method]
            same_path_diff_method = [ep for ep in self.graph.endpoints if ep.route_path == call.route_path]

            if same_path_diff_method:
                valid_methods = ", ".join([ep.http_method for ep in same_path_diff_method])
                issues.append(ContractValidationIssue(
                    issue_type=ContractIssueType.API_CONTRACT_MISMATCH.value,
                    source_file=call.file_path,
                    line_number=call.line_number,
                    target=f"{call.http_method} {call.route_path}",
                    message=(
                        f"CONTRACT_MISMATCH: Chamada '{call.http_method} {call.route_path}' em '{call.file_path}' "
                        f"incompatível com o backend. O endpoint existe mas aceita apenas [{valid_methods}]."
                    ),
                    severity="ERROR",
                    suggested_fix=f"Alterar o método HTTP em '{call.file_path}' para um de [{valid_methods}] ou adicionar o handler no backend.",
                    context_data={"call": call.to_dict(), "candidates": [ep.to_dict() for ep in same_path_diff_method]},
                ))
            else:
                issues.append(ContractValidationIssue(
                    issue_type=ContractIssueType.API_CONTRACT_MISMATCH.value,
                    source_file=call.file_path,
                    line_number=call.line_number,
                    target=f"{call.http_method} {call.route_path}",
                    message=(
                        f"CONTRACT_MISMATCH: Chamada '{call.http_method} {call.route_path}' em '{call.file_path}' "
                        f"não possui nenhum endpoint correspondente registado no backend."
                    ),
                    severity="ERROR",
                    suggested_fix=f"Implementar o endpoint '{call.http_method} {call.route_path}' no backend ou corrigir o URL da chamada.",
                    context_data={"call": call.to_dict()},
                ))

        return issues

    def _validate_test_references(self) -> List[ContractValidationIssue]:
        issues: List[ContractValidationIssue] = []

        for test_file, impl_list in self.graph.test_mappings.items():
            imp_list = self.graph.imports.get(test_file, [])
            for imp in imp_list:
                if imp.resolved_target in impl_list:
                    target_symbols = {s.name for s in self.graph.file_symbols.get(imp.resolved_target, [])}
                    for sym in imp.imported_symbols:
                        if sym != "*" and sym and target_symbols and sym not in target_symbols:
                            issues.append(ContractValidationIssue(
                                issue_type=ContractIssueType.TEST_SYMBOL_MISMATCH.value,
                                source_file=test_file,
                                line_number=imp.line_number,
                                target=sym,
                                message=f"O teste '{test_file}' tenta testar o símbolo '{sym}', que não existe em '{imp.resolved_target}'.",
                                severity="ERROR",
                                suggested_fix=f"Implementar '{sym}' em '{imp.resolved_target}' ou atualizar os testes.",
                            ))

        return issues

    def _validate_circular_dependencies(self) -> List[ContractValidationIssue]:
        issues: List[ContractValidationIssue] = []

        for cycle in self.graph.circular_dependencies:
            cycle_str = " -> ".join(cycle)
            first_file = cycle[0]
            issues.append(ContractValidationIssue(
                issue_type=ContractIssueType.CIRCULAR_DEPENDENCY.value,
                source_file=first_file,
                line_number=1,
                target=cycle_str,
                message=f"CIRCULAR_DEPENDENCY: Ciclo de importação detetado: {cycle_str}",
                severity="WARNING",  # Warning defensivo: reporta sem aplicar mutação cega
                suggested_fix="Refatorar módulos para mover tipos ou funções partilhadas para um ficheiro comum.",
                context_data={"cycle": cycle},
            ))

        return issues
