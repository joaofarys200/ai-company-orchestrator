---
type: concept
domain: ai-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - ai-engineering
  - mcp
  - agents
  - tool-calling
  - json-rpc
  - security
---

# 🔌 Model Context Protocol (MCP) and Capability Discovery Architecture

## 1. Definição & Topologia do Protocolo
O **Model Context Protocol (MCP)** é um protocolo aberto baseado em **JSON-RPC 2.0** que padroniza a ligação entre aplicações agênticas (*MCP Hosts/Clients*) e fontes externas de ferramentas e contexto (*MCP Servers*), eliminando conectores $M \times N$ ad-hoc.

```text
+-----------------------+       JSON-RPC 2.0        +----------------------+
|   MCP Host / Agent    | <=======================> |      MCP Server      |
| (Client + Capability  |   stdio | Streamable HTTP | (Tools / Resources / |
|  Router + Policy Gate)|                           |  Prompts)            |
+-----------------------+                           +----------------------+
```

### Primitivas Centrais Negociadas no `initialize`:
1. **Tools (`tools/list`, `tools/call`)**: Funções executáveis pelo modelo com *inputSchema* JSON Schema estrito e anotações de efeitos colaterais (`readOnlyHint`, `destructiveHint`).
2. **Resources (`resources/list`, `resources/read`)**: Dados endereçáveis por URI (ficheiros, esquemas SQL, logs) injetados sob controlo da aplicação/utilizador.
3. **Prompts (`prompts/list`, `prompts/get`)**: Templates parametrizados reutilizáveis expostos pelo servidor.

---

## 2. Transportes e Isolamento Operacional

| Transporte | Mecanismo | Latência | Modelo de Segurança |
|---|---|---|---|
| **`stdio`** | Subprocesso local via `stdin`/`stdout` (`\n`-delimited JSON-RPC) | $< 1\text{ ms}$ | Herda ambiente se não filtrado; exige whitelist de variáveis e path jail |
| **Streamable HTTP** | `POST`/`GET` HTTP com streaming SSE opcional e `Mcp-Session-Id` | Rede/TLS | OAuth 2.1 + PKCE, tokens de curta duração e validação de `Origin` (anti-DNS rebinding) |

---

## 3. Vetores de Ameaça Específicos do MCP e Mitigações

1. **Tool Poisoning & Rug Pulls**: Descrições de ferramentas (`description`) contendo instruções ocultas de injeção de prompt ou alteradas dinamicamente após aprovação.
   - *Mitigação*: Fixar hash criptográfico do manifesto `tools/list` aprovado e higienizar descrições externas.
2. **Confused Deputy / Cross-Server Exfiltration**: Um documento lido no Servidor A induz o modelo a invocar uma ferramenta de envio externo no Servidor B.
   - *Mitigação*: Isolamento epistêmico de resultados (`Tool-Result Isolation`) + confirmação humana obrigatória para qualquer `tool` com efeito externo/mutável.
3. **Context Bloat por Catálogos Grandes**: Dezenas de servidores MCP esgotam a janela de contexto só com definições JSON Schema.
   - *Mitigação*: Descoberta progressiva (*lazy capability loading*) filtrada por intenção da tarefa.

---

## 4. Conceitos Relacionados & Fontes
- [[Tool Calling Protocols and Structured Invocation]]
- [[Tool-Result Isolation and Epistemic Separation]]
- [[Prompt Injection Defense in Autonomous Agents]]
- [[OAuth 2.1, PKCE and Short-Lived Capability Tokens for Agents]]
- **Fontes**: Model Context Protocol Specification (2025–2026, `modelcontextprotocol.io`); JSON-RPC 2.0 Specification; OWASP Top 10 for LLM Applications (LLM01 / LLM07).

