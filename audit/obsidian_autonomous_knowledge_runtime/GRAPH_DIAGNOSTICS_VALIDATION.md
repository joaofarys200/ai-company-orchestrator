# 7. GRAPH DIAGNOSTICS VALIDATION

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  

---

## 7.1 Algoritmo de Adjacência em Duas Fases (Two-Pass Adjacency)

A versão anterior classificava nós como órfãos durante a iteração enquanto o mapa de in-degree ainda estava a ser construído, gerando falsos positivos.

**Nova Implementação:**
- **Fase 1 (Extração de Arestas e Mapeamento Completo):**
  - Inventaria as 257 notas canónicas únicas (excluindo `.history` e `.obsidian`).
  - Extrai wikilinks ignorando blocos de código e comentários.
  - Resolve destinos através de nomes canónicos, caminhos relativos e mapa de aliases YAML.
  - Constrói o mapa bidirecional completo de `outgoing_map` e `incoming_map`.
- **Fase 2 (Classificação Topológica e Diagnóstico):**
  - Calcula graus de entrada e saída exatos.
  - Identifica órfãos genuínos: nós com 0 arestas de entrada e 0 arestas de saída.
  - Identifica nós MOC-only: nós conectados unicamente a índices/MOCs e sem ligações entre pares.
  - Identifica hubs: nós com grau total superior a 15.
  - Contabiliza propostas reais a partir dos ficheiros em `data/obsidian/proposals/` (`APPLIED`, `REJECTED`, `AWAITING_REVIEW`).
