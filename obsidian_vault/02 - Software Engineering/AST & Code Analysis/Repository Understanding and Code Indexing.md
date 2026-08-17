---
type: concept
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - coding-agents
  - code-indexing
  - semantic-search
  - tree-sitter
status: verified
---

# 🗺️ Repository Understanding and Code Indexing

## 1. O Desafio de Compreensão de Repositórios
Grandes bases de código contêm centenas de ficheiros e milhões de linhas de código, ultrapassando a capacidade de qualquer janela de contexto de LLM.

Para que um agente como o **Devon** consiga resolver bugs ou implementar novas features de forma autónoma, ele necessita de um **Grafo de Símbolos do Repositório (Symbol Graph)** e de indexação em três camadas:
1. **Árvore de Ficheiros e Metadados** (File Map / Directory Layout).
2. **Grafo de Definições e Usos (Call Graph & Inheritance Hierarchy)**.
3. **Índice Semântico e Léxico (AST Chunks + Embeddings de Docstrings)**.

```
[ Workspace Root ]
       |
       +---> [ AST Scanner (Python, JS, TS, Rust) ]
       |           |
       |           v
       +---> [ Symbol Table & Reference Graph ]
       |     - Classes, Métodos, Interfaces, Imports
       |     - Exported Functions vs Private Helpers
       |
       +---> [ Inverted Index & Semantic Embeddings ]
                   |
                   v
       [ Consultas do Agente: "Onde o WebSocket é autenticado?" ]
                   |
                   v
       [ Retorna: backend/server.py:L142-L180 + interfaces ]
```

---

## 2. Estrutura do Grafo de Símbolos

Um nó no índice de código deve conter metadados semânticos precisos:

```json
{
  "symbol_name": "ModelHarness",
  "symbol_type": "class",
  "file_path": "backend/harness.py",
  "start_line": 25,
  "end_line": 140,
  "dependencies": ["BaseModel", "asyncio", "httpx"],
  "calls": ["execute_structured", "validate_schema"],
  "docstring": "Chassis de execução de modelos com circuit breaker e timeout."
}
```

---

## 3. Algoritmo de Pesquisa Relevante em Duas Fases

1. **Fase 1: Resolução de Símbolo Direto (Symbol Lookup)**:
   - Se a query do agente mencionar explicitamente um símbolo (ex: `buscar_contexto_obsidian`), o índice consulta a tabela de símbolos ($O(1)$) e retorna o bloco exato da função e as suas assinaturas dependentes.
2. **Fase 2: Expansão Contextual (Context Expansion)**:
   - Recupera os ficheiros que importam o símbolo (`references`) e os ficheiros importados por ele (`imports`) num raio de 1 salto (1-hop neighborhood), permitindo que o agente entenda o contrato de dados sem carregar todo o repositório.

---

## 4. Used When
- Na inicialização de missões de desenvolvimento para agentes de programação.
- Em tarefas de refatoração que requerem renomear funções ou alterar contratos de API em dezenas de ficheiros.

---

## 5. Common Failure Modes
- **Stale Index (Índice Desatualizado)**: Aplicar alterações em ficheiros sem atualizar o grafo de símbolos, levando o agente a basear-se em números de linha obsoletos.
- **Over-Expansion**: Puxar todas as referências de uma função utilitária comum (como `logger.info`), inundando a janela de contexto.

---

## 6. Related Concepts
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]
- [[Context Engineering and Compression]]
- [[Patch Generation and Safe Application]]

---

## 7. Sources
- *Language Server Protocol (LSP) Specification (Microsoft)*: https://microsoft.github.io/language-server-protocol/
- *SCIP: A better Code Intelligence Protocol (Sourcegraph)*: https://about.sourcegraph.com/blog/announcing-scip
