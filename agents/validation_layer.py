import os
import py_compile

class ValidationPipeline:
    """
    Validation Layer (Fase 3).
    Aplica testes e compilações a ficheiros isolados para garantir que não têm erros de sintaxe ou de build
    após edições do motor de Patch.
    """
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root

    def validate_python_syntax(self, rel_filepath: str) -> tuple[bool, str]:
        """
        Garante que o ficheiro corre sem syntax errors ou indentation errors.
        Retorna (sucesso: bool, erro_detalhado: str)
        """
        filepath = os.path.join(self.workspace_root, rel_filepath)
        
        if not os.path.exists(filepath):
            return False, f"Ficheiro não encontrado para validação: {filepath}"
            
        try:
            # O py_compile apenas compila, não executa o código. Ideal para encontrar erros críticos de sintaxe.
            py_compile.compile(filepath, doraise=True)
            return True, "Syntax OK"
        except py_compile.PyCompileError as e:
            # Capturamos o trace exatamente para poder dizer ao LLM o que é que ele partiu
            return False, f"SyntaxError Detetado:\n{e}"
        except Exception as e:
            return False, f"Erro genérico de validação:\n{str(e)}"
