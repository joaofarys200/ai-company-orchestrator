"""
JARVIS OS — AST Repair Engine v2 (Fase 10: Coding Agent 2.0)
Motor determinístico e semântico de reparação de sintaxe, imports partidos, contratos e assinaturas.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from enum import Enum
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from intelligence.cross_file_validator import ContractValidationIssue, ContractIssueType
from intelligence.repository_graph import RepositoryGraph


class RepairStrategy(str, Enum):
    DETERMINISTIC_SYNTAX = "DETERMINISTIC_SYNTAX"
    DETERMINISTIC_IMPORT = "DETERMINISTIC_IMPORT"
    DETERMINISTIC_CONTRACT = "DETERMINISTIC_CONTRACT"
    DETERMINISTIC_STUB = "DETERMINISTIC_STUB"
    SEMANTIC_LLM = "SEMANTIC_LLM"


@dataclass(slots=True)
class RepairResult:
    """Resultado da aplicação de uma reparação de código."""
    file_path: str
    original_content: str
    repaired_content: str
    strategy: str
    issue_type: str
    applied_changes: List[str]
    success: bool
    diagnostics: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ASTRepairEngineV2:
    """Motor de reparação de código AST com prioridade determinística."""

    def __init__(self, repo_graph: Optional[RepositoryGraph] = None) -> None:
        self.graph = repo_graph

    def repair_syntax_python(self, content: str, file_path: str = "") -> RepairResult:
        """Tenta corrigir deterministicamente erros sintáticos comuns em Python."""
        original = content
        changes: List[str] = []
        lines = content.splitlines()

        # 1. Correção de delimitadores e falta de ':' linha a linha
        repaired_lines = []
        statement_keywords = ("def ", "async def ", "class ", "if ", "elif ", "else", "for ", "while ", "with ", "try:", "except", "finally:", "return", "import ", "from ", "raise ")

        for idx, line in enumerate(lines):
            stripped = line.strip()
            # Ignora linhas comentadas ou vazias
            if not stripped or stripped.startswith("#"):
                repaired_lines.append(line)
                continue

            # Verifica se a próxima linha não-vazia inicia um novo statement
            next_is_boundary = True
            for next_idx in range(idx + 1, len(lines)):
                next_str = lines[next_idx].strip()
                if next_str and not next_str.startswith("#"):
                    next_is_boundary = any(next_str.startswith(k) for k in statement_keywords)
                    break

            # Se for cabeçalho de bloco
            is_header = any(stripped.startswith(k) for k in ("def ", "async def ", "class ", "if ", "elif ", "else", "for ", "while ", "with ", "try:", "except", "finally:"))
            if is_header:
                line_open_parens = line.count("(") - line.count(")")
                if line_open_parens > 0:
                    line = line + (")" * line_open_parens)
                    changes.append(f"Fechados {line_open_parens} parênteses no cabeçalho: '{line.strip()}'")

                line_open_brackets = line.count("[") - line.count("]")
                if line_open_brackets > 0:
                    line = line + ("]" * line_open_brackets)

                stripped = line.strip()
                if not stripped.endswith(":") and not stripped.endswith("\\"):
                    line = line + ":"
                    changes.append(f"Adicionado ':' ao final da instrução: '{line.strip()}'")

            elif next_is_boundary:
                # Fecha colchetes ou parênteses que ficaram abertos na linha de atribuição/expressão
                line_open_brackets = line.count("[") - line.count("]")
                if line_open_brackets > 0:
                    line = line + ("]" * line_open_brackets)
                    changes.append(f"Fechados {line_open_brackets} colchetes na expressão: '{line.strip()}'")

                line_open_parens = line.count("(") - line.count(")")
                if line_open_parens > 0:
                    line = line + (")" * line_open_parens)
                    changes.append(f"Fechados {line_open_parens} parênteses na expressão: '{line.strip()}'")

            repaired_lines.append(line)

        content = "\n".join(repaired_lines)

        # 2. Correção de Parênteses, Colchetes e Chaves pendentes no final do ficheiro
        open_parens = content.count("(") - content.count(")")
        open_brackets = content.count("[") - content.count("]")
        open_braces = content.count("{") - content.count("}")

        if open_parens > 0:
            content += ")" * open_parens
            changes.append(f"Fechados {open_parens} parênteses pendentes no final do ficheiro.")
        if open_brackets > 0:
            content += "]" * open_brackets
            changes.append(f"Fechados {open_brackets} colchetes pendentes no final do ficheiro.")
        if open_braces > 0:
            content += "}" * open_braces
            changes.append(f"Fechadas {open_braces} chavetas pendentes no final do ficheiro.")

        # Valida se agora compila via ast.parse
        success = False
        diagnostic = None
        try:
            ast.parse(content)
            success = True
        except SyntaxError as e:
            diagnostic = f"SyntaxError em linha {e.lineno}: {e.msg}"

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_SYNTAX.value,
            issue_type="SYNTAX_ERROR",
            applied_changes=changes,
            success=success,
            diagnostics=diagnostic,
        )

    def repair_syntax_javascript(
        self,
        content: str,
        file_path: str = "",
        diagnostics: Optional[str] = None,
    ) -> RepairResult:
        """Tenta corrigir deterministicamente erros sintáticos comuns em JS/TS."""
        original = content
        changes: List[str] = []

        # 0. Se existirem diagnósticos do compilador/Node.js, analisa a linha do erro
        error_line_num: Optional[int] = None
        if diagnostics:
            line_match = re.search(r':(\d+)(?::\d+)?(?:\r?\n|\s)', diagnostics)
            if line_match:
                try:
                    error_line_num = int(line_match.group(1))
                except ValueError:
                    pass

        # 1. Tratar erro específico: "Unexpected token '}'" ou excesso de chavetas/parênteses (open_braces < 0)
        lines = content.splitlines()
        if error_line_num and 1 <= error_line_num <= len(lines):
            target_line = lines[error_line_num - 1].strip()
            if diagnostics and "Unexpected token '}'" in diagnostics:
                if target_line in ("});", "}", "};", "});\n"):
                    lines.pop(error_line_num - 1)
                    content = "\n".join(lines)
                    changes.append(f"Removido token inesperado '{target_line}' na linha {error_line_num}.")
            elif diagnostics and "Unexpected token ')'" in diagnostics:
                if target_line in (");", ")", ");\n"):
                    lines.pop(error_line_num - 1)
                    content = "\n".join(lines)
                    changes.append(f"Removido parêntese inesperado '{target_line}' na linha {error_line_num}.")

        # 2. Fechar ou remover chaves/parênteses/colchetes desbalanceados
        open_braces = content.count("{") - content.count("}")
        open_parens = content.count("(") - content.count(")")
        open_brackets = content.count("[") - content.count("]")

        if open_braces < 0:
            # Excesso de chavetas de fecho: remover fechos órfãos no final do ficheiro
            lines = content.splitlines()
            removed_count = 0
            while lines and lines[-1].strip() in ("});", "}", "};", ");") and open_braces < 0:
                discarded = lines.pop()
                if "}" in discarded:
                    open_braces += discarded.count("}")
                if ")" in discarded:
                    open_parens += discarded.count(")")
                removed_count += 1
            if removed_count > 0:
                content = "\n".join(lines)
                changes.append(f"Removidas {removed_count} chavetas de fecho órfãs no final do ficheiro JS.")

        if open_parens > 0:
            content += ")" * open_parens
            changes.append(f"Fechados {open_parens} parênteses no final do código JS.")
        if open_brackets > 0:
            content += "]" * open_brackets
            changes.append(f"Fechados {open_brackets} colchetes no final do código JS.")
        if open_braces > 0:
            content += "\n" + ("}" * open_braces)
            changes.append(f"Fechadas {open_braces} chavetas no final do ficheiro JS.")

        # 3. Tratar erro específico: "await is only valid in async functions"
        if diagnostics and "await is only valid in async functions" in diagnostics:
            lines = content.splitlines()
            # Se sabemos a linha do await com erro
            if error_line_num and 1 <= error_line_num <= len(lines):
                # Verificar se houve um fecho prematuro (ex: '});') pouco antes da linha do erro
                premature_idx = None
                for i in range(error_line_num - 2, max(-1, error_line_num - 35), -1):
                    if lines[i].strip() in ("});", "}", "};"):
                        premature_idx = i
                        break
                if premature_idx is not None:
                    removed_delimiter = lines.pop(premature_idx)
                    content = "\n".join(lines)
                    changes.append(f"Removido fecho prematuro '{removed_delimiter.strip()}' na linha {premature_idx + 1} que isolava a chamada 'await'.")
                else:
                    # Verificar se a função anterior não tem a palavra-chave async
                    for i in range(error_line_num - 1, -1, -1):
                        cur_line = lines[i]
                        if re.search(r'(?:function|\(.*?\)\s*=>|\bpost\(|\bget\(|\bput\()', cur_line) and "async" not in cur_line:
                            lines[i] = re.sub(r'(\bfunction\b|\(.*?\)\s*=>|\b(?:post|get|put)\s*\()', r'async \1', cur_line, count=1)
                            content = "\n".join(lines)
                            changes.append(f"Adicionada palavra-chave 'async' na definição da função na linha {i + 1}.")
                            break

        # 4. Tratar blocos duplicados acidentais no final do ficheiro
        lines = content.splitlines()
        half = len(lines) // 2
        for block_size in range(10, min(100, half)):
            if lines[-block_size:] == lines[-2*block_size:-block_size]:
                lines = lines[:-block_size]
                content = "\n".join(lines)
                changes.append(f"Removido bloco de código duplicado de {block_size} linhas no final do ficheiro.")
                break

        # 5. Corrigir vírgulas duplas ou trailing commas malformadas
        fixed_commas = re.sub(r",\s*,", ", ", content)
        if fixed_commas != content:
            content = fixed_commas
            changes.append("Removidas vírgulas consecutivas malformadas.")

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_SYNTAX.value,
            issue_type="SYNTAX_ERROR",
            applied_changes=changes,
            success=len(changes) > 0,
            diagnostics=diagnostics,
        )

    def repair_missing_import(
        self,
        content: str,
        missing_symbol: str,
        file_path: str,
    ) -> RepairResult:
        """Adiciona automaticamente o import em falta com base no SymbolGraph."""
        original = content
        changes: List[str] = []

        if not self.graph:
            return RepairResult(
                file_path=file_path,
                original_content=original,
                repaired_content=content,
                strategy=RepairStrategy.DETERMINISTIC_IMPORT.value,
                issue_type="MISSING_IMPORT",
                applied_changes=[],
                success=False,
                diagnostics="SymbolGraph indisponível para resolução de imports",
            )

        sym_def = self.graph.find_definition(missing_symbol)
        if not sym_def:
            return RepairResult(
                file_path=file_path,
                original_content=original,
                repaired_content=content,
                strategy=RepairStrategy.DETERMINISTIC_IMPORT.value,
                issue_type="MISSING_IMPORT",
                applied_changes=[],
                success=False,
                diagnostics=f"Definição do símbolo '{missing_symbol}' não encontrada no grafo",
            )

        # Determina o caminho de importação relativo
        src_dir = os.path.dirname(file_path)
        target_file = sym_def.file_path

        if file_path.endswith(".py"):
            target_mod = os.path.splitext(target_file)[0].replace("/", ".").replace("\\", ".")
            import_line = f"from {target_mod} import {missing_symbol}\n"
            content = import_line + content
            changes.append(f"Injetado import: '{import_line.strip()}'")
        else:
            rel_path = os.path.relpath(target_file, src_dir).replace(os.sep, "/")
            if not rel_path.startswith("."):
                rel_path = "./" + rel_path
            rel_path = os.path.splitext(rel_path)[0]
            import_line = f"import {{ {missing_symbol} }} from '{rel_path}';\n"
            content = import_line + content
            changes.append(f"Injetado import JS/TS: '{import_line.strip()}'")

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_IMPORT.value,
            issue_type="MISSING_IMPORT",
            applied_changes=changes,
            success=True,
        )

    def repair_missing_stub(
        self,
        content: str,
        missing_symbol: str,
        file_path: str,
        is_function: bool = True,
    ) -> RepairResult:
        """Gera um stub determinístico para símbolos em falta importados por testes ou outros ficheiros."""
        original = content
        changes: List[str] = []

        if file_path.endswith(".py"):
            if is_function:
                stub = f"\n\ndef {missing_symbol}(*args, **kwargs):\n    \"\"\"Auto-generated stub.\"\"\"\n    pass\n"
            else:
                stub = f"\n\nclass {missing_symbol}:\n    \"\"\"Auto-generated stub class.\"\"\"\n    pass\n"
            content = content.rstrip() + stub
            changes.append(f"Adicionado stub Python para '{missing_symbol}'")
        else:
            if is_function:
                stub = f"\nexport function {missing_symbol}(...args: any[]): any {{\n  // Auto-generated stub\n  return null;\n}}\n"
            else:
                stub = f"\nexport class {missing_symbol} {{\n  // Auto-generated stub\n}}\n"
            content = content.rstrip() + stub
            changes.append(f"Adicionado stub JS/TS para '{missing_symbol}'")

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_STUB.value,
            issue_type="MISSING_EXPORT",
            applied_changes=changes,
            success=True,
        )

    def repair_api_contract_mismatch(
        self,
        content: str,
        file_path: str,
        issue: ContractValidationIssue,
    ) -> RepairResult:
        """Corrige desalinhamentos de rotas ou métodos HTTP entre frontend e backend."""
        original = content
        changes: List[str] = []
        candidates = issue.context_data.get("candidates", [])

        if candidates:
            # Endpoint existe com outro método (ex: backend tem POST e frontend fez GET)
            valid_method = candidates[0].get("http_method", "GET")
            call_data = issue.context_data.get("call", {})
            old_method = call_data.get("http_method", "GET")
            route_path = call_data.get("route_path", "")

            # Substitui método na chamada
            if "axios." in content:
                content = content.replace(f"axios.{old_method.lower()}(", f"axios.{valid_method.lower()}(")
                changes.append(f"Atualizado método axios de '{old_method}' para '{valid_method}'")
            elif "fetch(" in content:
                content = re.sub(
                    rf"fetch\(\s*(['\"`]{re.escape(route_path)}['\"`])\s*,\s*\{{[^}}]*method\s*:\s*['\"][A-Z]+['\"]",
                    f"fetch(\\1, {{ method: '{valid_method}'",
                    content,
                )
                changes.append(f"Atualizado método fetch para '{valid_method}'")

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_CONTRACT.value,
            issue_type="API_CONTRACT_MISMATCH",
            applied_changes=changes,
            success=len(changes) > 0,
        )

    def repair_invalid_path_alias(
        self,
        content: str,
        invalid_alias: str,
        file_path: str,
    ) -> RepairResult:
        """Corrige um path alias inválido substituindo-o pelo alias correto resolvido via SymbolGraph."""
        original = content
        changes: List[str] = []

        if not self.graph:
            return RepairResult(
                file_path=file_path,
                original_content=original,
                repaired_content=content,
                strategy=RepairStrategy.DETERMINISTIC_IMPORT.value,
                issue_type="INVALID_PATH_ALIAS",
                applied_changes=[],
                success=False,
            )

        # Extrai símbolos importados na linha com o alias inválido
        import_match = re.search(rf"import\s+\{{([^}}]+)\}}\s+from\s+['\"]{re.escape(invalid_alias)}['\"]", content)
        if import_match:
            syms = [s.strip().split(" as ")[0] for s in import_match.group(1).split(",") if s.strip()]
            if syms:
                target_sym = syms[0]
                sym_def = self.graph.find_definition(target_sym)
                if sym_def:
                    # Encontra o alias mais adequado a partir do tsconfig
                    active_tsconfig = self.graph._find_matching_tsconfig(file_path)
                    correct_specifier = None
                    if active_tsconfig and active_tsconfig.paths:
                        # Mapeia caminho do ficheiro alvo de volta para um alias
                        for alias_pat, target_pats in active_tsconfig.paths.items():
                            for target_pat in target_pats:
                                t_base = target_pat.rstrip("*").rstrip("/")
                                a_base = alias_pat.rstrip("*").rstrip("/")
                                rel_target = os.path.relpath(
                                    os.path.join(self.graph.workspace_root, sym_def.file_path),
                                    os.path.join(active_tsconfig.base_dir, active_tsconfig.base_url),
                                ).replace(os.sep, "/")
                                if rel_target.startswith(t_base):
                                    sub = rel_target[len(t_base):].lstrip("/")
                                    sub = os.path.splitext(sub)[0]
                                    correct_specifier = f"{a_base}/{sub}" if a_base else sub
                                    break
                            if correct_specifier:
                                break

                    if not correct_specifier:
                        # Fallback relativo
                        src_dir = os.path.dirname(file_path)
                        rel_p = os.path.relpath(sym_def.file_path, src_dir).replace(os.sep, "/")
                        if not rel_p.startswith("."):
                            rel_p = "./" + rel_p
                        correct_specifier = os.path.splitext(rel_p)[0]

                    if correct_specifier and correct_specifier != invalid_alias:
                        content = content.replace(f"from '{invalid_alias}'", f"from '{correct_specifier}'")
                        content = content.replace(f'from "{invalid_alias}"', f'from "{correct_specifier}"')
                        changes.append(f"Corrigido path alias de '{invalid_alias}' para '{correct_specifier}'")

        return RepairResult(
            file_path=file_path,
            original_content=original,
            repaired_content=content,
            strategy=RepairStrategy.DETERMINISTIC_IMPORT.value,
            issue_type="INVALID_PATH_ALIAS",
            applied_changes=changes,
            success=len(changes) > 0,
        )

