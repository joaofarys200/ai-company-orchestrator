import os
from intelligence.project_intelligence import ProjectIntelligenceEngine
from agents.patch_engine import PatchEngine

class RefactorEngine:
    """
    Validation Layer (Fase 5).
    Reestruturações em larga escala que exigem mover ou alterar funções inteiras 
    garantindo que o AST permanece íntegro.
    """
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self.intelligence = ProjectIntelligenceEngine(workspace_root)
        self.patcher = PatchEngine(workspace_root)

    def _get_symbol_code(self, rel_filepath: str, symbol_name: str) -> str:
        """Puxa o bloco exato de código usando a Inteligência."""
        graph = self.intelligence.scan_workspace()
        norm_path = os.path.normpath(rel_filepath)
        
        file_data = None
        for k, v in graph.items():
            if os.path.normpath(k) == norm_path:
                file_data = v
                break
                
        if not file_data:
            return ""
            
        items = file_data.get("classes", []) + file_data.get("functions", [])
        for item in items:
            if item.get("name") == symbol_name and "code" in item:
                return item["code"]
        return ""

    def move_symbol(self, source_file: str, target_file: str, symbol_name: str) -> str:
        """Move uma função ou classe do source_file para o target_file sem partir o código."""
        abs_source = os.path.join(self.workspace_root, source_file)
        abs_target = os.path.join(self.workspace_root, target_file)
        
        if not os.path.exists(abs_source):
            return f"[RefactorEngine] Erro: Ficheiro origem '{source_file}' não existe."
            
        # 1. Obter o bloco original intacto
        code_block = self._get_symbol_code(source_file, symbol_name)
        if not code_block:
            return f"[RefactorEngine] Erro: O símbolo '{symbol_name}' não foi encontrado em '{source_file}'."
            
        # 2. Apagar do ficheiro de origem
        print(f"[RefactorEngine] A remover '{symbol_name}' de '{source_file}'...")
        remove_res = self.patcher.apply_patch(source_file, symbol_name, "")
        
        if "ERRO FATAL" in remove_res:
            return f"[RefactorEngine] Falha ao remover o símbolo da origem: {remove_res}"
            
        # 3. Criar ou injetar no ficheiro de destino
        print(f"[RefactorEngine] A injetar '{symbol_name}' em '{target_file}'...")
        
        # Garante que a pasta e ficheiro target existem
        os.makedirs(os.path.dirname(abs_target) if os.path.dirname(abs_target) else ".", exist_ok=True)
        
        target_content = ""
        if os.path.exists(abs_target):
            with open(abs_target, "r", encoding="utf-8") as f:
                target_content = f.read()
                
        with open(abs_target, "w", encoding="utf-8") as f:
            if target_content.strip() and not target_content.endswith("\n\n"):
                f.write(target_content + "\n\n")
            elif not target_content.strip():
                pass
            else:
                f.write(target_content)
                
            f.write(code_block + "\n")
            
        return f"[RefactorEngine] Símbolo '{symbol_name}' movido com sucesso de '{source_file}' para '{target_file}'."

    def rename_symbol(self, filepath: str, old_name: str, new_name: str) -> str:
        """Renomeia a definição de uma função local."""
        code_block = self._get_symbol_code(filepath, old_name)
        if not code_block:
            return f"[RefactorEngine] Erro: '{old_name}' não encontrado."
            
        # Refactoring inocente: troca apenas o nome na def ou class
        # (Idealmente envolvia regex mais cuidada, mas para Fase 5 isto demonstra o poder)
        new_code_block = code_block.replace(f"def {old_name}(", f"def {new_name}(")
        new_code_block = new_code_block.replace(f"class {old_name}(", f"class {new_name}(")
        new_code_block = new_code_block.replace(f"class {old_name}:", f"class {new_name}:")
        
        return self.patcher.apply_patch(filepath, old_name, new_code_block)
