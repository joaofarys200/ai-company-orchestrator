---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - obsidian
  - rag
  - tools
  - memory
status: verified
---

# 📚 JARVIS Obsidian Tools and RAG System

## 1. O Papel do Obsidian Vault no JARVIS OS
O cofre local do Obsidian funciona como a **camada de memória externa e base de conhecimento desacoplada** do JARVIS OS. Em vez de injetar manuais extensos e tratados de centenas de páginas diretamente nos system prompts, os agentes recuperam dinamicamente apenas os fragmentos relevantes via a ferramenta `buscar_contexto_obsidian`.

---

## 2. Ferramentas Disponíveis em `agents/obsidian_tools.py`

| Função | Assinatura | Finalidade |
|---|---|---|
| **`buscar_contexto_obsidian`** | `(prompt: str) -> str` | RAG automático que pontua e injeta as 2 notas mais relevantes |
| **`safe_join_vault`** | `(vault_path: str, filename: str) -> str` | Validação de segurança contra Path Traversal fora do cofre |
| **`get_obsidian_vault_path`** | `() -> str` | Resolução do caminho físico configurado via `OBSIDIAN_VAULT_PATH` |

---

## 3. Segurança e Isolamento de Artefatos de Código
Para evitar que agentes guardem acidentalmente código gerado dentro do cofre em vez da sandbox do projeto, `agents/obsidian_tools.py` implementa `obsidian_path_looks_like_code_artifact()` para bloquear ficheiros `.py`, `.js`, `.ts`, `.sh` dentro de `obsidian_vault/`.

---

## 4. Related Concepts
- [[RAG Architecture and Retrieval Strategies]]
- [[Context Engineering and Compression]]
- [[OBSIDIAN_RAG_KNOWLEDGE_AUDIT]]
- [[JARVIS Component Architecture]]

---

## 5. Sources
- *JARVIS OS Codebase — `agents/obsidian_tools.py`*
