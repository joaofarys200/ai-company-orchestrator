---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - software-engineering
  - compilers
  - parsing
  - lalr
  - recursive-descent
prerequisites:
  - "[[Lexical Analysis and Tokenization]]"
related:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
  - "[[Control Flow Graph (CFG) and Static Analysis]]"
used_by:
  - "[[Patch Generation and Safe Application]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: Crafting Interpreters - Parsing Expressions (Robert Nystrom)
    type: PRIMARY_SOURCE
    url: https://craftinginterpreters.com/parsing-expressions.html
---

# 🌳 LALR and Recursive Descent Parsing

## 1. Pergunta Central
> *Como é que um parser valida se um fluxo de tokens respeita a Gramática Livre de Contexto (CFG) e constrói hierarquicamente a Árvore de Sintaxe Abstrata (AST)?*

---

## 2. Paradigmas de Parsing

### 2.1. Top-Down: Descendente Recursivo (Recursive Descent / PEG)
- Cada regra da gramática é mapeada diretamente para uma função no código do compilador.
- Fácil de implementar manualmente e de depurar com mensagens de erro precisas (adotado pelo CPython moderno com parser PEG e pelo Rust).

### 2.2. Bottom-Up: LALR(1) (Look-Ahead LR)
- Constrói a árvore de baixo para cima a partir das folhas, executando operações de **Shift** (empilhar token) e **Reduce** (reduzir tokens a uma regra não-terminal) através de uma tabela de estados gerada por ferramentas como Yacc, Bison ou Tree-sitter.

---

## 3. Implementação Simplificada de Parser Descendente Recursivo

```python
class SimpleMathParser:
    """Parser para expressões matemáticas simples: Factor ((+ | -) Factor)*"""
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        result = self.factor()
        while self.pos < len(self.tokens) and self.tokens[self.pos] in ("+", "-"):
            op = self.tokens[self.pos]
            self.pos += 1
            right = self.factor()
            result = ("BINOP", op, result, right)
        return result

    def factor(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return ("NUMBER", tok)
```

---

## 4. Related Concepts
- [[Lexical Analysis and Tokenization]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Control Flow Graph (CFG) and Static Analysis]]
