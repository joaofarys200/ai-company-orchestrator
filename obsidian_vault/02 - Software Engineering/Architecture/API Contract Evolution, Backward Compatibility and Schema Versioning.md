---
type: concept
domain: software-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - software-engineering
  - api-design
  - backward-compatibility
  - schema-evolution
  - websockets
  - contracts
---

# 📜 API Contract Evolution, Backward Compatibility and Schema Versioning

## 1. Semântica Formal de Compatibilidade de Contratos
Em sistemas onde produtores (backend Python/FastAPI) e consumidores (frontend TypeScript/Electron, workers persistidos ou agentes MCP) evoluem ao longo do tempo, quebrar contratos provoca falhas silenciosas ou perda de mensagens.

- **Backward Compatibility (Leitura de dados antigos)**: Código novo $V_{n+1}$ processa corretamente payloads/estados persistidos por $V_n$.
- **Forward Compatibility (Tolerância a extensões futuras)**: Código $V_n$ ignora campos desconhecidos adicionados por $V_{n+1}$ sem descartar a mensagem inteira.

> **Armadilha de Normalizadores Estritos**: Um switch `normalizeServerMessage(msg)` que converte qualquer `type` novo não listado num `{ type: 'unknown' }` destrói a compatibilidade *forward* em protocolos WebSocket full-duplex. Todo novo evento no servidor exige registo atómico na união discriminada do cliente e teste de contrato.

---

## 2. Matriz de Alterações Seguras vs Breaking Changes

| Operação no Esquema (JSON / REST / WS) | Classificação | Estratégia Segura de Evolução |
|---|---|---|
| Adicionar campo opcional no *response* | ✅ **Aditiva (Segura)** | Consumidor aplica *default* defensivo se ausente |
| Adicionar campo obrigatório no *request* | ❌ **Breaking Change** | Tornar opcional com *default* no servidor |
| Renomear ou mudar tipo de um campo (ex.: `str` $\to$ `list`) | ❌ **Breaking Change** | Padrão **Expand-and-Contract** + normalizador dual |
| Remover variante de `enum` ou `message.type` | ❌ **Breaking Change** | Manter alias deprecado com telemetria até uso $= 0$ |

---

## 3. Padrão Expand-and-Contract (Parallel Change em 3 Fases)

1. **Expand**: O produtor aceita/emite simultaneamente o formato antigo e o novo (ou o consumidor normaliza ambos: ex. `detailed: string | Array<{title, text}>`).
2. **Migrate**: Todos os clientes, filas e documentos persistidos (`documents.json` / SQLite) são migrados ou reidratados sob demanda.
3. **Contract**: Apenas após telemetria confirmar zero leituras/escritas no formato legado, remove-se o ramo de compatibilidade.

---

## 4. Conceitos Relacionados & Fontes
- [[Clean Architecture and Hexagonal Ports]]
- [[Structured Outputs and Schema Validation]]
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Progressive Delivery - Canary Analysis, Blue-Green and Feature Flag Governance]]
- **Fontes**: Kleppmann (2017), *Designing Data-Intensive Applications* (Cap. 4: *Encoding and Evolution*); Fowler (2014), *Parallel Change (Expand and Contract)*; RFC 9413 (*Maintaining Robust Protocols*).

