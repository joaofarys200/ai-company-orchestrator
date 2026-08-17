---
type: concept
domain: software-engineering
difficulty: advanced
tags:
  - software-engineering
  - coding-agents
  - ast
  - compilers
  - python-ast
status: verified
---

# 🌳 Abstract Syntax Tree (AST) Parsing and Manipulation

## 1. Definição & Teoria Formal
Uma **Abstract Syntax Tree (AST)** (Árvore de Sintaxe Abstrata) é uma representação estruturada em árvore da estrutura sintática e gramatical de um código-fonte. Ao contrário de uma *Parse Tree* concreta, a AST omite detalhes triviais como parênteses redundantes, vírgulas e comentários, retendo a essência hierárquica das instruções (classes, métodos, variáveis, operações binárias e condicionais).

Em agentes de codificação como o **Devon (JARVIS OS)**, a manipulação de AST é o alicerce para refatorações cirúrgicas, deteção de dependências e transformações de código com garantia absoluta de preservação de validade sintática.

```
       [ Fonte: def add(x, y): return x + y ]
                          |
                          v
                    [ Module ]
                        |
                  [ FunctionDef: 'add' ]
                 /         |          \
            [args]      [returns]   [body]
            /    \                    |
      [arg: 'x'] [arg: 'y']     [ Return ]
                                      |
                                  [ BinOp: Add ]
                                  /            \
                           [Name: 'x']      [Name: 'y']
```

---

## 2. Padrão NodeVisitor e NodeTransformer em Python

O módulo padrão `ast` do Python fornece duas classes fundamentais baseadas no padrão de design *Visitor*:
1. `ast.NodeVisitor`: Percorre a árvore sem modificá-la para análise estática (extração de imports, lista de classes, cálculo de complexidade ciclomática).
2. `ast.NodeTransformer`: Percorre a árvore permitindo substituir, remover ou injetar novos nós gramaticais em tempo de execução.

### Exemplo: Extração Segura de Assinaturas de Funções

```python
import ast
from typing import List, Dict

class FunctionSignatureExtractor(ast.NodeVisitor):
    def __init__(self):
        self.functions: List[Dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        args = [arg.arg for arg in node.args.args]
        docstring = ast.get_docstring(node) or ""
        self.functions.append({
            "name": node.name,
            "args": args,
            "line_number": node.lineno,
            "docstring": docstring.strip()
        })
        self.generic_visit(node)

def inspect_python_signatures(source_code: str) -> List[Dict[str, Any]]:
    tree = ast.parse(source_code)
    extractor = FunctionSignatureExtractor()
    extractor.visit(tree)
    return extractor.functions
```

---

## 3. Modificação Cirúrgica de Código com `ast.unparse`

```python
class LoggingDecoratorInjector(ast.NodeTransformer):
    """
    Injeta automaticamente um decorator @audit_log em todas as funções públicas.
    """
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if not node.name.startswith("_"):
            decorator_node = ast.Name(id="audit_log", ctx=ast.Load())
            # Evitar duplicação se já existir
            if not any(getattr(d, "id", None) == "audit_log" for d in node.decorator_list):
                node.decorator_list.insert(0, decorator_node)
        return node

# Transformar código e regenerar texto limpo
# tree = ast.parse(code)
# transformer = LoggingDecoratorInjector()
# new_tree = ast.fix_missing_locations(transformer.visit(tree))
# modified_code = ast.unparse(new_tree)
```

---

## 4. Used When
- Na análise estática de repositórios para extração de símbolos e dependências sem carregar módulos no interpretador.
- Na refatoração automatizada de código onde substituição por regex geraria falsos positivos (ex: mudar o nome de uma variável sem alterar strings com o mesmo nome).

---

## 5. Common Failure Modes
- **Perda de Comentários e Formatação**: `ast.unparse` nativo do Python regenera o código sem os comentários originais. Para preservar formatação e comentários linha a linha, deve usar-se **RedBaron**, **LibCST** ou **Tree-sitter**.
- **Syntax Version Incompatibility**: Fazer parsing de código Python 3.12 (ex: novas sintaxes de type parameter) num interpretador mais antigo causará `SyntaxError`.

---

## 6. Related Concepts
- [[AST-Based Refactoring vs Regex Replacement]]
- [[Repository Understanding and Code Indexing]]
- [[Patch Generation and Safe Application]]
- [[Compiler Feedback and Test-Driven Self-Repair]]

---

## 7. Sources
- *Python Official Documentation - ast module*: https://docs.python.org/3/library/ast.html
- *Aho, Lam, Sethi, Ullman - Compilers: Principles, Techniques, and Tools (Dragon Book)*
- *Tree-sitter Language Parsing Infrastructure*: https://tree-sitter.github.io/tree-sitter/
