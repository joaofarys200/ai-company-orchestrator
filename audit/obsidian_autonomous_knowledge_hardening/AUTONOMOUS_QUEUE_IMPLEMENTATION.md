# IMPLEMENTAÇÃO DA FILA DE EVOLUÇÃO AUTÓNOMA
## JARVIS OS — Motor de Melhoria Incremental e Controlo de Operador

### 1. Visão Geral da Arquitetura
A melhoria autónoma do cofre Obsidian não deve executar mutações em massa nem bloquear o sistema. Por essa razão, foi implementada uma **Fila de Melhoria Incremental Delimitada** (*Bounded Autonomous Improvement Queue*), persistida em disco e dotada de controlos de pausa/retoma para supervisão humana.

---

### 2. Algoritmo de Priorização por Défice Epistémico

A ordenação da fila é puramente determinística. Notas com maior défice conceptual, menor fundamentação ou isoladas no grafo sobem ao topo da fila através da seguinte métrica calibrada:

$$\text{Priority Deficit} = (100 - \text{Overall Score}) \times 0.40 + (100 - \text{Evidence Quality}) \times 0.35 + (100 - \text{Graph Quality}) \times 0.25$$

Notas que acumulam pontuação de prioridade mais elevada são processadas em primeiro lugar.

---

### 3. Fila Persistida e Máquina de Estados

#### 3.1 Estrutura do Item de Fila (`improvement_queue.json`)
```json
{
  "item_id": "queue_b4a1c2e3",
  "note_path": "10 - Lectures/Lecture - RAG and Agents.md",
  "stem": "Lecture - RAG and Agents",
  "priority_score": 68.4,
  "overall_score": 42.0,
  "epistemic_classification": "UNVERIFIED_HEURISTIC",
  "findings": [
    {
      "category": "Evidence Quality",
      "dimension": "Provenance",
      "what_is_missing": "Proveniência de fonte não identificada nos metadados",
      "why_it_matters": "Não é possível rastrear a origem do conteúdo",
      "evidence_supporting_finding": "Frontmatter não declara 'source_type' nem 'provenance'",
      "recommended_improvement": "Adicionar proveniência ou ligar a documento fonte"
    }
  ],
  "status": "PENDING",
  "retry_count": 0,
  "created_at": "2026-11-05T01:00:00.000000",
  "updated_at": "2026-11-05T01:00:00.000000"
}
```

#### 3.2 Transição de Estados
- `PENDING`: O item aguarda processamento pelo motor autónomo.
- `AWAITING_REVIEW` / `PROPOSAL_CREATED`: Foi gerada uma proposta de enriquecimento (`data/obsidian/proposals/prop_*.json`).
- `APPLIED`: A melhoria foi aplicada de forma segura através de escrita atómica CAS com backup histórico criado.
- `REJECTED`: A sugestão foi descartada pelo operador.

---

### 4. Persistência de Estado do Worker e Controlo do Operador

O ficheiro `data/obsidian/worker_state.json` regista o ciclo de vida do worker autónomo:
```json
{
  "is_paused": false,
  "is_running": false,
  "active_item_id": null,
  "items_processed": 18,
  "last_run_timestamp": "2026-11-05T01:14:00.000000",
  "updated_at": "2026-11-05T01:14:00.000000"
}
```

#### 4.1 Métodos de Controlo no `ObsidianGraphEngine`
- `pause_queue_worker()`: Marca `is_paused = true`. Impede qualquer execução subsequente de lotes.
- `resume_queue_worker()`: Marca `is_paused = false`. Reativa o processamento de itens da fila.
- `get_worker_status()`: Devolve a telemetria do worker (número de pendentes, aplicados, propostas, etc.).
- `run_bounded_improvement_batch(batch_size=1)`: Executa um lote limitado a `batch_size` itens pendentes. Se o worker estiver pausado, retorna imediatamente lista vazia sem mutações.

---

### 5. Integração com Ollama Local (`qwen3.5:9b`)
O processamento autónomo de notas que requerem enriquecimento generativo recorre unicamente à instância local Ollama via `ModelExecutionService` com o modelo `qwen3.5:9b`. Não existem chamadas a APIs cloud nem dependências pagas.

