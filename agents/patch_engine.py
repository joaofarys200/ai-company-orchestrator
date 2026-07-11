import os
import shutil
from intelligence.project_intelligence import ProjectIntelligenceEngine

class PatchEngine:
    """
    Motor de Patching Baseado em AST.
    Modifica cirurgicamente blocos de código sem fazer overwrite completo aos ficheiros.
    """
    def __init__(
        self,
        workspace_root: str = ".",
        backup_dir: str | None = None,
        create_backups: bool = True,
        validate_python: bool = True,
    ):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.create_backups = create_backups
        self.validate_python = validate_python
        # Diretório onde guardamos backups rápidos para a "Validation Layer" conseguir fazer Undo
        self.backup_dir = backup_dir or os.path.join(self.workspace_root, ".jarvis_backups")
        if self.create_backups:
            os.makedirs(self.backup_dir, exist_ok=True)
        self.intelligence = ProjectIntelligenceEngine(self.workspace_root)

    def _backup_file(self, filepath: str) -> str:
        """Cria um snapshot do ficheiro antes da alteração."""
        if not self.create_backups or not os.path.exists(filepath):
            return ""
        backup_path = os.path.join(self.backup_dir, os.path.basename(filepath) + ".bak")
        shutil.copy2(filepath, backup_path)
        return backup_path

    def restore_backup(self, filepath: str) -> bool:
        """Restaura o último backup se o patch correr mal."""
        backup_path = os.path.join(self.backup_dir, os.path.basename(filepath) + ".bak")
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, filepath)
            return True
        return False

    def apply_patch(self, rel_filepath: str, symbol_name: str, new_code: str) -> str:
        """
        Recebe um filepath relativo, o nome da função ou classe a editar, e o código final.
        Devolve uma string descrevendo o resultado da operação.
        """
        filepath = os.path.realpath(os.path.abspath(os.path.join(self.workspace_root, rel_filepath)))
        try:
            if os.path.commonpath([self.workspace_root, filepath]) != self.workspace_root:
                return "[PatchEngine] Erro de seguranca: path fora do projeto."
        except ValueError:
            return "[PatchEngine] Erro de seguranca: path fora do projeto."
        if not os.path.exists(filepath):
            return f"[PatchEngine] Erro: Ficheiro '{rel_filepath}' não encontrado."

        # 1. Faz scan fresco para apanhar o AST do ficheiro alvo
        graph = self.intelligence.scan_workspace()
        
        # O graph indexa por relative paths no Windows (pode usar \ ou / dependendo do os.walk)
        # Vamos normalizar as paths para o lookup
        norm_rel_filepath = os.path.normpath(rel_filepath)
        
        file_data = None
        for k, v in graph.items():
            if os.path.normpath(k) == norm_rel_filepath:
                file_data = v
                break
                
        if not file_data:
            return f"[PatchEngine] Erro: O ficheiro '{rel_filepath}' não foi indexado na AST."

        # 2. Procurar o símbolo exato
        old_code = None
        items = file_data.get("classes", []) + file_data.get("functions", [])
        for item in items:
            if item.get("name") == symbol_name and "code" in item:
                old_code = item["code"]
                break
                
        if not old_code:
            return f"[PatchEngine] Erro: Símbolo '{symbol_name}' não encontrado em '{rel_filepath}'."

        # 3. Ler o ficheiro real
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 4. Validar se o bloco antigo ainda existe intacto no ficheiro
        if old_code not in content:
            # Fallback para diferenças de encoding/newlines
            old_code_normalized = old_code.replace("\r\n", "\n")
            content_normalized = content.replace("\r\n", "\n")
            if old_code_normalized not in content_normalized:
                return f"[PatchEngine] Erro Fatal: O código original de '{symbol_name}' foi modificado recentemente e a AST está dessincronizada."
            
            # Faz o replace na versão normalizada
            new_content = content_normalized.replace(old_code_normalized, new_code)
        else:
            # 5. Aplicar o patch
            new_content = content.replace(old_code, new_code)

        # 6. Gravar backup e gravar novo ficheiro
        self._backup_file(filepath)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        # 7. Validar o ficheiro modificado (Fase 3)
        if self.validate_python and filepath.endswith(".py"):
            from agents.validation_layer import ValidationPipeline
            vp = ValidationPipeline(self.workspace_root)
            is_valid, err_msg = vp.validate_python_syntax(rel_filepath)
            
            if not is_valid:
                # O Cinto de Segurança!
                self.restore_backup(filepath)
                return f"[PatchEngine] ERRO FATAL: O teu patch introduziu um erro de sintaxe no código!\n\nDetalhes:\n{err_msg}\n\nO ficheiro sofreu Rollback para segurança e voltou ao estado anterior. Verifica os parênteses, indentações e blocos, e aplica de novo!"

        return f"[PatchEngine] Sucesso: O símbolo '{symbol_name}' em '{rel_filepath}' foi atualizado de forma cirúrgica."
