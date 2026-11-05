# REGISTO DE TESTES & EVIDÊNCIAS DE EXECUÇÃO
**JARVIS OS — VERIFICAÇÃO AUTOMATIZADA, CONTRATOS & DESEMPENHO**  
*Data de Execução:* 05 de Novembro de 2026  
*Ambiente:* Produção Local JARVIS OS (Ollama `qwen3.5:9b`, PyMuPDF `1.28.2`, Python `3.14.7`)

---

## 1. MATRIZ DE TESTES AUTOMATIZADOS

A integridade do motor de grafos, migração do PyMuPDF, contratos WebSocket e frontend foi verificada através de suites de teste automatizadas reais:

| Suite de Teste | Ficheiro / Comando | Testes Executados | Duração | Resultado | Evidência / Âncora |
|---|---|---|---|---|---|
| **Motor de Grafos Obsidian** | `python -m pytest tests/test_obsidian_graph_engine.py` | 6 testes | 0.16s | **PASS (100%)** | `tests/test_obsidian_graph_engine.py` |
| **Contratos WebSocket** | `.\venv\Scripts\python.exe -m pytest tests/test_websocket_dispatcher_contract.py` | 9 testes (230 subtestes) | 0.64s | **PASS (100%)** | `tests/test_websocket_dispatcher_contract.py` |
| **Caracterização do Servidor** | `.\venv\Scripts\python.exe -m pytest tests/test_server_websocket_characterization.py` | 8 testes | 4.81s | **PASS (100%)** | `tests/test_server_websocket_characterization.py` |
| **Migração PyMuPDF** | `StudyService._parse_pdf` via `scripts/test_pymupdf_clean.py` | 1 execução | 0.12s | **PASS (0 Warnings)** | `audit/obsidian_autonomous_knowledge/PYMuPDF_MIGRATION_REPORT.md` |
| **Compilação Frontend & Tipos** | `npm run build --prefix frontend` | 3506 módulos | 3.34s | **PASS (Código 0)** | `dist/index.html` (Vite 8) |
| **Inventário Forense do Cofre** | `scripts/vault_forensic_inventory.py` | 256 notas | 0.42s | **PASS (100% SHA-256)** | `data/obsidian/vault_graph_snapshot.json` |

---

## 2. DETALHE DOS TESTES UNITÁRIOS DO MOTOR DE GRAFOS (`test_obsidian_graph_engine.py`)

1. **`test_01_vault_initialization_and_canonical_map` (PASS):** Valida a deteção de ficheiros `.md`, ignorando diretórios de sistema (`.obsidian`, `.history`), e mapeia chaves canónicas e aliases YAML.
2. **`test_02_layered_concept_link_resolution` (PASS):** Testa o resolvedor em 6 camadas: correspondência canónica, resolução por sinónimo técnico (`mcp` ➔ `Model Context Protocol...`), rejeição de stopwords comuns e prevenção de ligações circulares.
3. **`test_03_note_quality_assessment_10_dimensions` (PASS):** Valida o cálculo calibrado nas 10 dimensões objetivas, geração de findings explicativos e pontuação global rigorosa.
4. **`test_04_improvement_queue_generation` (PASS):** Verifica o cálculo da fórmula de prioridade epistémica e a persistência do ficheiro JSON da fila.
5. **`test_05_safe_enrichment_and_rollback` (PASS):** Testa o ciclo completo de salvaguarda de snapshot em `.history/`, injeção de frontmatter e relações tipadas, seguido de rollback determinístico restaurando o ficheiro original byte-a-byte.
6. **`test_06_bridge_note_generation` (PASS):** Valida a escrita de notas de síntese transversal em `09 - JARVIS/Bridge Notes/` com metadados YAML e referências bidirecionais.

---

## 3. VERIFICAÇÃO DE AUSÊNCIA DE DEPRECATION WARNINGS (PYMuPDF)

- **Ficheiros Atualizados:**
  - `services/study_service.py` (linhas 25-30 e 1870-1880)
  - `scripts/pdftotext.py` (linhas 15-20)
  - `backend/document_engine/visual_inspector.py` (linhas 10-15)
- **Verificação no Runtime:**
  ```
  DeprecationWarning: The `fitz` API is deprecated and will be removed in future.
  => 0 ocorrências emitidas durante a execução de StudyService e pdftotext.
  ```

---

## 4. REGISTO DE ARTEFACTOS PRODUZIDOS

Todos os artefactos produzidos nesta fase cumprem o modelo de dados local e encontram-se persistidos no repositório:
- `data/obsidian/vault_graph_snapshot.json` (SHA-256 de 256 notas)
- `data/obsidian/improvement_queue.json` (Fila de melhoria contínua ordenada)
- `data/obsidian/proposals/` (Registo estruturado de propostas aplicadas)
- `obsidian_vault/.history/` (Diretório de snapshots históricos timestamped)
- `obsidian_vault/09 - JARVIS/Bridge Notes/Bridge - MCP Capability Discovery and Hierarchical Agent Governance.md` (Demonstração de síntese transversal)

