---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - software-engineering
  - compilers
  - lexer
  - tokenization
  - ast
prerequisites:
  - "[[Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores]]"
related:
  - "[[LALR and Recursive Descent Parsing.md]]"
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
used_by:
  - "[[Repository Understanding and Code Indexing]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: Compilers - Principles, Techniques, and Tools (Dragon Book, Chapter 3 - Lexical Analysis)
    type: PRIMARY_SOURCE
    url: https://en.wikipedia.org/wiki/Compilers:_Principles,_Techniques,_and_Tools
---

# 🔍 Lexical Analysis and Tokenization

## 1. Pergunta Central
> *Como é que um compilador converte um fluxo contínuo de caracteres de código-fonte num fluxo estruturado de unidades léxicas (tokens) com tipo, valor e posição exata?*

---

## 2. A Mecânica do Scanner / Lexer
A **Análise Léxica** é a primeira fase do pipeline de compilação. Ela lê os caracteres do arquivo-fonte e agrupa-os em **lexemas** baseados em regras descritas por Expressões Regulares e convertidas em Autômatos Finitos Determinísticos (**DFA**).

```
Source Code:  `total = price * 1.23`
                     |
                     v (Lexer / DFA)
Token Stream: [IDENTIFIER('total'), ASSIGN('='), IDENTIFIER('price'), OP_MUL('*'), FLOAT(1.23)]
```

---

## 3. Tokenização Nativa em Python

```python
import tokenize
import io

def inspect_python_tokens(source_code: str):
    tokens = tokenize.tokenize(io.BytesIO(source_code.encode("utf-8")).readline)
    for tok in tokens:
        if tok.type not in [tokenize.ENCODING, tokenize.ENDMARKER]:
            print(f"Linha {tok.start[0]}, Coluna {tok.start[1]}: {tokenize.tok_name[tok.type]} -> {tok.string!r}")
```

---

## 4. Related Concepts
- [[LALR and Recursive Descent Parsing]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores]]
