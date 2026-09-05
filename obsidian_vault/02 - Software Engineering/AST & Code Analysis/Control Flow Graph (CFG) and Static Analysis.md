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
  - cfg
  - static-analysis
  - dead-code
prerequisites:
  - "[[Abstract Syntax Tree (AST) Parsing and Manipulation]]"
related:
  - "[[LALR and Recursive Descent Parsing]]"
  - "[[Repository Understanding and Code Indexing]]"
used_by:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: Static Program Analysis (MÃ¸ller & Schwartzbach, Aarhus University)
    type: PRIMARY_SOURCE
    url: https://cs.au.dk/~amoeller/spa/spa.pdf
---

# 📊 Grafo de Fluxo de Controle CFG Analise Estatica e Deteccao de Dead Code

## 1. Pergunta Central
> *Como os analisadores estáticos e agentes de qualidade inspecionam o grafo de fluxo de controle (CFG) para análise estática e deteção de dead code e código inalcançável sem executar o código?*

---

## 2. Blocos Básicos e Arestas de Fluxo
Um **Control Flow Graph (CFG)** é um grafo dirigido $G = (V, E)$ onde:
- Cada vértice $v \in V$ é um **Bloco Básico (Basic Block)**: uma sequência linear de instruções com exatamente um ponto de entrada e um ponto de saída (sem bifurcações no meio).
- Cada aresta $(u, v) \in E$ representa uma transição de controlo (saltos condicionais `if`, laços `while`, `break`, `return`).

```
          [ Bloco 1: Entrada / Inicialização ]
                          |
                          v
         [ Bloco 2: Avaliação Condicional (x > 0) ]
                     /                 \
          (True)    /                   \ (False)
                   v                     v
       [ Bloco 3: Executa A ]    [ Bloco 4: Executa B ]
                   \                     /
                    \                   /
                     v                 v
                 [ Bloco 5: Retorno / Saída ]
```

---

## 3. Análise de Vivacidade de Variáveis e Código Morto (Dead Code)
- **Dead Code Detection**: Se um nó do grafo não tiver caminho direcionado a partir do nó de entrada inicial, o compilador sinaliza o bloco como inalcançável.
- **Def-Use Chains**: Rastreia onde cada variável foi definida e garante que toda a leitura seja precedida por uma definição válida.

---

## 4. Related Concepts
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Repository Understanding and Code Indexing]]
- [[Compiler Feedback and Test-Driven Self-Repair]]

## Query Relevance
Grafo de fluxo de controle cfg análise estática e deteção de dead code.

