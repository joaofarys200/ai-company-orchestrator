---
type: concept
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - coding-agents
  - patch-engine
  - diff
  - git
status: verified
---

# 🩹 Patch Generation and Safe Application

## 1. O Desafio de Modificação de Código por IA
Quando agentes de codificação modificam ficheiros no disco, reescrever ficheiros de 2000 linhas por completo causa:
1. **Desperdício Extremo de Tokens e Tempo** (reescrever 2000 linhas para alterar 2).
2. **Introdução Involuntária de Regressões** (o modelo esquece ou simplifica partes de código periféricas).
3. **Falhas por Truncamento de Buffer de Saída**.

A solução adotada no **JARVIS OS** é a geração e aplicação de **Patches Cirúrgicos** (Diffs Unificados ou Substituições por Blocos Delimitados).

---

## 2. Métodos de Aplicação de Patches

```
+-------------------------------------------------------------+
| Método A: Unified Diff (GNU patch / git apply)              |
|   - Requer contagem estrita de linhas (@@ -12,5 +12,6 @@)   |
|   - Frágil a pequenas variações de números de linha         |
+-------------------------------------------------------------+
| Método B: Search & Replace com Âncoras Únicas               |
|   - Identifica target_content e replacement_content         |
|   - Valida unicidade antes de aplicar                       |
+-------------------------------------------------------------+
| Método C: AST Subtree Replacement                           |
|   - Substitui nós gramaticais exatos no compilador          |
|   - Imune a formatação e espaçamentos vazios                |
+-------------------------------------------------------------+
```

---

## 3. Algoritmo de Aplicação Segura de Substituição com Validação

```python
import os

class SafePatcher:
    @staticmethod
    def apply_exact_block_replace(
        file_path: str,
        target_content: str,
        replacement_content: str
    ) -> bool:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Ficheiro {file_path} não existe.")

        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()

        # 1. Verificar contagem de ocorrências
        count = original.count(target_content)
        if count == 0:
            raise ValueError("O bloco 'target_content' não foi encontrado no ficheiro.")
        elif count > 1:
            raise ValueError(f"O bloco 'target_content' é ambíguo ({count} ocorrências). Forneça mais linhas de contexto.")

        # 2. Executar substituição atómica
        modified = original.replace(target_content, replacement_content, 1)

        # 3. Escrever em ficheiro temporário antes de substituir
        tmp_path = f"{file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(modified)

        os.replace(tmp_path, file_path)
        return True
```

---

## 4. Pipeline de Validação Pós-Patch
Após aplicar o patch:
1. **Linter & Syntax Check**: Executar `python -m py_compile <file>` ou `eslint <file>`. Se falhar $\rightarrow$ Reversão imediata.
2. **Testes Rápidos de Regressão**: Executar os testes unitários do módulo alterado.

---

## 5. Related Concepts
- [[AST-Based Refactoring vs Regex Replacement]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Safe Rollback and Git Transactional Strategies]]
- [[How to Safely Validate and Apply Code Patches]]

---

## 6. Sources
- *GNU Diffutils & Patch Documentation*: https://www.gnu.org/software/diffutils/manual/html_node/Unified-Format.html
- *Git SCM - git-apply Documentation*: https://git-scm.com/docs/git-apply
