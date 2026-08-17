---
type: comparison
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - refactoring
  - ast
  - regex
  - comparison
status: verified
---

# ⚖️ AST-Based Refactoring vs Regex Replacement

## 1. Tabela Comparativa

| Dimensão | Refatoração Baseada em AST | Substituição por Expressão Regular (Regex) |
|---|---|---|
| **Compreensão de Escopo** | Total. Distingue variáveis locais, parâmetros e globais | Nenhuma. Trata o código estritamente como texto plano |
| **Segurança Sintática** | 100% garantida pelo parser da linguagem | Frágil; pode quebrar parênteses, aspas ou indentação |
| **Imunidade a Comentários/Strings** | Ignora ocorrências dentro de strings ou comentários | Altera acidentalmente textos dentro de strings e docstrings |
| **Performance de Execução** | Mais lenta (requer parse completo da árvore sintática) | Quase instantânea ($O(N)$ em bytes de texto) |
| **Flexibilidade Multi-linguagem** | Requer parser específico por linguagem (Tree-sitter/ast) | Agnóstico de linguagem; funciona em qualquer ficheiro |
| **Preservação de Formatação** | Requer CST (Concrete Syntax Tree) para não perder layout | Preserva exatamente todo o texto envolvente não alterado |

---

## 2. Exemplos de Falha de Regex que o AST Previne

### Cenário: Renomear a variável `user` para `account_owner`

#### Código Original:
```python
def process_data(user: str):
    # Enviar notificação para o user cadastrado
    log_msg = f"Processando o user {user}"
    user_data = get_user(user)
    return user_data
```

#### Resultado com Regex Ingênuo (`s/\buser\b/account_owner/g`):
```python
def process_data(account_owner: str):
    # Enviar notificação para o account_owner cadastrado  <-- Comentário alterado
    log_msg = f"Processando o account_owner {account_owner}"  <-- String de log alterada!
    account_owner_data = get_account_owner(account_owner)     <-- Função errada get_account_owner!
```

#### Resultado com AST:
O AST identifica que apenas o parâmetro `user` e a variável no corpo `get_user(user)` pertencem ao símbolo local, preservando comentários, strings e a função `get_user`.

---

## 3. Matriz de Decisão: Quando Usar Cada Abordagem

1. **Usar AST / CST**:
   - Renomeação de símbolos, métodos e classes;
   - Injeção de decorators, parâmetros ou middlewares;
   - Análise estática de segurança e conformidade de regras.
2. **Usar Regex / Exact Block Replace**:
   - Edição de ficheiros de configuração (`.yaml`, `.toml`, `.json`, `.env`, `.md`);
   - Correção de linhas pontuais com âncoras de contexto únicas.

---

## 4. Related Concepts
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Patch Generation and Safe Application]]
- [[Repository Understanding and Code Indexing]]

---

## 5. Sources
- *Fowler, Martin - Refactoring: Improving the Design of Existing Code*
- *LibCST Documentation (Instagram Engineering)*: https://libcst.readthedocs.io/
