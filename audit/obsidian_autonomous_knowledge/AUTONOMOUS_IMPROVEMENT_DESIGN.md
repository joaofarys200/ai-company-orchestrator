# ARQUITETURA DE EVOLUÇÃO AUTÓNOMA E NÃO-DESTRUTIVA
**JARVIS OS — FILA DE MELHORIA CONTÍNUA, GOVERNANÇA EPISTÉMICA & ROLLBACK SEGURO**  
*Data de Execução:* 05 de Novembro de 2026  
*Ambiente:* Produção Local JARVIS OS (Ollama `qwen3.5:9b`, PyMuPDF `1.28.2`, Python `3.14.7`)

---

## 1. PRINCÍPIOS FUNDAMENTAIS DA EVOLUÇÃO NÃO-DESTRUTIVA

A evolução de conhecimento no cofre Obsidian do JARVIS OS opera sob cinco restrições invioláveis:

1. **Invariância de Conteúdo Humano:** Nenhum parágrafo, reflexão, anotação ou diagrama inserido pelo utilizador é alguma vez apagado ou reescrito sem autorização.
2. **Snapshot Prévio Obrigatório:** Antes de qualquer alteração, o ficheiro original é copiado integralmente para `obsidian_vault/.history/<stem>_<timestamp>.md`.
3. **Isolamento de Adições Estruturadas:** Novas relações semânticas e metadados são inseridos exclusivamente em blocos dedicados (`--- YAML Frontmatter ---` e secção final `## 🔗 Grafo de Conhecimento & Relações Tipadas`), preservando 100% do corpo principal.
4. **Propostas Auditáveis:** Cada intervenção gera um registo JSON em `data/obsidian/proposals/<proposal_id>.json` contendo diff de comprimentos, justificação semântica e caminho de backup.
5. **Reversibilidade Determinística a 1 Clique:** Qualquer alteração pode ser revertida de forma imediata via comando ou clique na interface Spatial Board.

---

## 2. ARQUITETURA DA FILA DE MELHORIA (`data/obsidian/improvement_queue.json`)

A fila de evolução ordena as notas através de uma fórmula de **Prioridade Epistémica**:

$$\text{PriorityScore} = (100 - \text{Q-Score}) \times 0.7 + (\text{FindingsCount} \times 5.0)$$

### Ciclo de Vida de um Item na Fila:
```
  [ AUDITORIA 10-D ] 
          │
          ▼ (Score < 75.0 ou Findings > 0)
    ┌───────────┐
    │  PENDING  │  ◄── Adicionado à Fila Ordenada por Prioridade
    └─────┬─────┘
          │
          ▼ (Execução Local Ollama / Resolvedor Semântico)
    ┌───────────┐
    │ PROPOSED  │  ◄── Snapshot em .history/ e Proposta em data/obsidian/proposals/
    └─────┬─────┘
          │
     ┌────┴────────────┐
     ▼                 ▼
┌───────────┐    ┌───────────┐
│  APPLIED  │    │ REJECTED  │
└─────┬─────┘    └───────────┘
      │ (Se solicitado pelo utilizador)
      ▼
┌───────────┐
│ ROLLEDBACK│  ◄── Restauração fiel a partir de .history/
└───────────┘
```

---

## 3. MECANISMO DE ENRIQUECIMENTO SEGURO (SAFE ENRICHMENT)

O método `enrich_note_safely(rel_path, auto_apply)` do `ObsidianGraphEngine`:

1. **Resolução de Ficheiro:** Localiza a nota pelo título canónico, alias ou caminho relativo.
2. **Snapshot Timestamped:** Salva cópia fiel com timestamp UNIX em `.history/`.
3. **Injeção de Frontmatter:** Se a nota não possuir cabeçalho YAML, injeta metadados padronizados:
   ```yaml
   ---
   type: atomic_note
   domain: ai-llm
   status: verified
   provenance: JARVIS_INTERNAL
   confidence: high
   tags:
     - agent-systems
     - mcp-architecture
   ---
   ```
4. **Resolução de Relações Tipadas:** Analisa o corpo da nota contra o registo ontológico e títulos canónicos, inferindo até 4 relações tipadas com justificação semântica:
   ```markdown
   ## 🔗 Grafo de Conhecimento & Relações Tipadas
   - **APPLIES_TO** ➔ [[Model Context Protocol (MCP) and Capability Discovery Architecture]] — *Aplica padrões de descoberta e controlo de capacidades definidos na especificação MCP*
   - **EXTENDS** ➔ [[TypeScript AST Architecture]] — *Especializa o modelo de parsing para streaming em tempo real*
   ```
5. **Aplicação e Registo de Proposta:** Escreve as alterações no ficheiro apenas se `auto_apply=True` e regista o payload da proposta.

---

## 4. SISTEMA DE ROLLBACK DETERMINÍSTICO

O método `rollback_note(rel_path, backup_path)` garante que, caso o utilizador não aprove as adições semânticas:
- O ficheiro em `.history/` substitui o documento ativo.
- O ficheiro resultante é byte-a-byte idêntico ao estado pré-enriquecimento.
- Os testes automatizados em `tests/test_obsidian_graph_engine.py::test_05_safe_enrichment_and_rollback` comprovam que `restored_text == original_text`.

---

## 5. CONTROLO DE CONCORRÊNCIA & GOVERNANÇA NO SPATIAL BOARD

No Spatial Board (domínio Obsidian):
- O operador humano dispõe de um botão de alternância **"PAUSADA" / "EM EXECUÇÃO"** para a fila.
- Cada proposta de relação tipada pode ser inspecionada visualmente antes de ser consolidada.
- O botão de rollback com o ícone de reversão está acessível diretamente no cartão do inspetor de notas.
- Todas as operações são executadas localmente, sem dependência de serviços externos ou cloud.

