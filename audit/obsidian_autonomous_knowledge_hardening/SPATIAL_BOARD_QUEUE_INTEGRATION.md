# INTEGRAÇÃO DO SPATIAL BOARD COM A FILA AUTÓNOMA
## JARVIS OS — Domínio Obsidian no HUD Espacial

### 1. Resumo da Implementação
O domínio **Obsidian Vault** no Spatial Board HUD (`frontend/src/features/board/SpatialBoard.tsx`) foi completamente articulado com o backend hardened do `ObsidianGraphEngine`. Toda a telemetria decorre de mensagens dinâmicas por WebSocket, permitindo controlo operacional bidirecional em tempo real.

---

### 2. Cartões Funcionais do Domínio Obsidian

#### Card 1: Telemetria do Grafo & Conectividade (`card_vault_metrics`)
- **Métricas Vivas:**
  - `Notas Canónicas`: Apresenta dinamicamente `vaultDiagnostics.total_notes` (261 notas).
  - `Média de Qualidade`: Apresenta `vaultDiagnostics.quality_average` (77.4/100).
  - `Órfãos Genuínos`: Lê `vaultDiagnostics.genuine_orphans` (0 órfãos absolutos).
  - `Links Quebrados`: Lê `vaultDiagnostics.broken_links` (23 links mapeados).
- **Distribuição de Qualidade Dinâmica:**
  - O gráfico de barras ponderadas calcula em tempo de execução as percentagens das 4 faixas a partir de `vaultDiagnostics.quality_distribution`:
    - $\ge 80$ (Excelente)
    - $70-79$ (Adequado)
    - $60-69$ (Melhorável)
    - $< 60$ (Prioridade Fila)
- **Callout Explicativo para o Utilizador:**
  - Mantém o painel informativo detalhado sobre nós MOC-only e variações de nomenclatura.

#### Card 2: Auditor de Qualidade em 10 Dimensões (`card_vault_inspector`)
- **Seleção Interativa de Notas:** Dropdown dinâmico com todas as notas canónicas do cofre.
- **Visualização das 10 Dimensões:** Barras de progresso individuais (0 a 100) com codificação por cores (verde $\ge 80$, ciano $\ge 60$, âmbar $< 60$).
- **Identificação de Oportunidades de Melhoria (Findings):** Lista estruturada de cada défice epistémico identificado, explicitando *o que falta*, *por que importa* e a *recomendação de melhoria*.
- **Enriquecimento com Relações Tipadas:** Botão com um clique para injetar relações seguras.
- **Rollback Instantâneo:** Botão de reversão histórica com restauro atómico e verificação de integridade.

#### Card 3: Fila de Evolução Autónoma (`card_vault_relationships`)
- **Botão de Alternância de Estado (PAUSADA / EM EXECUÇÃO):**
  - Conectado diretamente aos comandos WebSocket `pause_queue_worker` e `resume_queue_worker`.
  - Reflete o estado factual persistido no backend (`data/obsidian/worker_state.json`).
- **Botão de Execução Delimitada ("+1 Ciclo"):**
  - Envia a mensagem `{ type: "start_improvement_batch", batch_size: 1 }` ao servidor.
  - Processa o próximo item de prioridade máxima na fila usando o Ollama local (`qwen3.5:9b`), gera a proposta, executa o CAS atómico e atualiza os diagnósticos.
- **Pré-visualização da Fila Ordenada por Défice Epistémico:**
  - Lista os itens em espera com respetivo *score*, défice e estado (`PENDING`, `APPLIED`).
  - Ao clicar em qualquer item da fila, o Card 2 inspeciona de imediato a respetiva nota.

---

### 3. Validação do Protocolo de WebSocket

O ficheiro `frontend/src/protocol/websocket.ts` e o contexto `frontend/src/context/WebSocketContext.tsx` foram estendidos com os seguintes contratos:
- **Mensagens de Cliente:**
  - `get_vault_diagnostics`
  - `audit_note_quality`
  - `enrich_note`
  - `rollback_note`
  - `get_queue_status`
  - `pause_queue_worker`
  - `resume_queue_worker`
  - `start_improvement_batch`
- **Mensagens de Servidor:**
  - `vault_diagnostics`
  - `note_quality_audit`
  - `note_enrichment_result`
  - `note_rollback_result`
  - `queue_worker_status`
  - `improvement_batch_result`
