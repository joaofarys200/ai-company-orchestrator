---
type: index
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - coding-agents
  - ast
  - compilers
  - architecture
  - tree-sitter
  - tla-plus
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 💻 Software Engineering & Coding Agents Index

Este MOC organiza os padrões fundamentais de engenharia de software, técnicas de compilação, parsing de AST, Tree-sitter, verificação formal com TLA+, topologias de repositório e matrizes de recuperação para agentes de código.

---

## 🏛️ Architecture, Formal Methods & Topologies
- [[Clean Architecture and Hexagonal Ports]] — Separação estrita do domínio de negócio de adaptadores de I/O externos.
- [[Domain-Driven Design Tactical Patterns]] — Entidades, Agregados, Value Objects e Repositórios.
- [[SOLID Principles and Clean Code Metrics]] — Princípios SOLID e cálculo de Complexidade Ciclomática de McCabe.
- [[TLA+ Formal Verification for Mission State Invariants]] — Model checking com TLC para máquinas de estados sem deadlocks.
- [[Git Monorepos, Subtrees and Boundary Topologies]] — Comparativo entre Monorepo, Git Subtrees e Submodules.
- [[IEEE SWEBOK Software Lifecycle Disciplines]] — Disciplinas formais do ciclo de vida de software IEEE SWEBOK v4.
- [[Idempotency in Software Systems]] — Garantia de que operações repetidas não provocam efeitos colaterais duplicados.
- [[DDD_Domain_Driven_Design_and_Enterprise_Patterns]] — Monografia sobre Domain-Driven Design estratégico e tático.
- [[Engenharia_de_Software_e_Arquitetura_Clean_Code]] — Monografia sobre Clean Code, SOLID e refatoração.
- [[SWEBOK_Software_Engineering_Body_of_Knowledge]] — IEEE Software Engineering Body of Knowledge v4.

## 🤖 Coding Agents & Self-Repair
- [[Compiler Feedback and Test-Driven Self-Repair]] — Ciclo fechado de auto-correção guiado por linters e asserções de testes.
- [[Coding Agent Failure Mode and Recovery Matrix]] — Matriz formal de deteção, prevenção e recuperação de falhas de agentes de código.

## 🌳 AST, Tree-sitter & Symbol Graphs
- [[Tree-sitter Incremental Parsing in Massive Repositories]] — Parsing incremental em C e consultas S-Expressions em tempo real.
- [[Symbol Dependency Graphs and Call Graph Indexing]] — Grafos de dependência de símbolos e cálculo de blast radius.
- [[Comparison - AST vs Tree-sitter for Multi-Language Analysis]] — Comparativo entre Python `ast` nativo e Tree-sitter poliglota.
- [[Lexical Analysis and Tokenization]] — Conversão de código fonte bruto em fluxo de tokens via DFA.
- [[LALR and Recursive Descent Parsing]] — Validação gramatical e construção de árvores sintáticas.
- [[Control Flow Graph (CFG) and Static Analysis]] — Análise de vivacidade, blocos básicos e deteção de código morto.
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]] — Inspeção e transformação estruturada de código sem quebra sintática.
- [[Repository Understanding and Code Indexing]] — Grafos de símbolos, call graphs e busca semântica em repositórios.
- [[AST-Based Refactoring vs Regex Replacement]] — Comparativo formal entre manipulação gramatical e substituição por expressões regulares.
- [[Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores]] — Monografia sobre compiladores, CFG e AST.

## 🧪 Testing & Validation
- [[Unit Tests vs End-to-End Tests in Agent Validation]] — Pirâmide de testes para validação rápida de agentes autónomos.

## 🩹 Patching & Refactoring
- [[Patch Generation and Safe Application]] — Aplicação atómica de diffs unificados e substituição de blocos com âncoras.

## 🔄 Recovery & Transactions
- [[Safe Rollback and Git Transactional Strategies]] — Transações de workspace com Git e reversão atómica pós-falha.

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/Coding
- [[How to Safely Validate and Apply Code Patches]] — Checklist de validação de patches gerados por IA.
- [[How to Diagnose Python Import and Module Resolution Failures]] — Análise de `sys.path` e dependências circulares.
- [[How to Safely Rollback Failed Code Changes]] — Procedimento de emergência para restaurar o repositório.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - Regex Refactoring Syntax Corruption]] — Corrupção sintática provocada por refatoração ingênua com regex.
- [[Lesson - Unescaped Wikilink Parsing Collisions in Markdown]] — Colisões entre caminhos físicos de código e nós do grafo.
