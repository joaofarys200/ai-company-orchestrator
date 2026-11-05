# JARVIS OS — FASE 23.0: AUDITORIA FORENSE INTEGRAL
## INVENTÁRIO ARQUITETURAL COMPLETO DE COMPONENTES E CAPACIDADES
**Documento:** `JARVIS_CAPABILITY_INVENTORY.md`  
**Data:** 21 de Outubro de 2026  
**Auditor Forense:** Antigravity Forensic Engineering  
**Classificação:** Baseline Técnica Oficial — Fase 23.0  
**Diretório de Auditoria:** `audit/phase_23_forensic_audit_20261021/`

---

## 1. VISÃO GERAL DO INVENTÁRIO

Este inventário cataloga exaustivamente todos os subsistemas, módulos, agentes, ferramentas, orquestradores, pontos de persistência, motores de validação e interfaces do **JARVIS OS**. Cada componente foi inspecionado diretamente no código-fonte e classificado de acordo com os estados normativos da auditoria forense.

```
+-------------------------------------------------------------------------------+
|                        INVENTÁRIO ESTATÍSTICO DE MÓDULOS                      |
+--------------------------+---------------------+------------------------------+
| Categoria                | Qtd. Componentes    | Estado Predominante          |
+--------------------------+---------------------+------------------------------+
| Backend & Serviços       | 620 módulos         | IMPLEMENTED_AND_INTEGRATED   |
| Frontend & Interface     | 1 aplicação Vite/TS | IMPLEMENTED_AND_INTEGRATED   |
| Entrypoints & Runners    | 12 scripts/runners  | IMPLEMENTED_AND_INTEGRATED   |
| Orquestradores de Swarm  | 3 subsistemas       | HÍBRIDO (1 Ativo, 2 Isolados)|
| Perfis de Agente         | 28 personas         | IMPLEMENTED_AND_INTEGRATED   |
| Ferramentas Executáveis  | 30 ferramentas core | IMPLEMENTED_AND_INTEGRATED   |
| Motores de Planeamento   | 4 motores           | IMPLEMENTED_AND_INTEGRATED   |
| Execução de Código       | 6 subsistemas       | EXECUTION_VERIFIED           |
| Persistência e Memória   | 7 subsistemas       | PARCIALMENTE INTEGRADO       |
| Governança & Segurança   | 5 motores           | HÍBRIDO (1 Vulnerabilidade P0|
| Product Delivery Gate    | 8 validadores       | VALIDATION_VERIFIED          |
| Motor Documental Word    | 9 componentes       | EXECUTION_VERIFIED           |
+--------------------------+---------------------+------------------------------+
```

---

## 2. BACKEND E SERVIÇOS NATIVOS

### 2.1 Servidor FastAPI e Handlers WebSockets
- **Módulo Principal:** [backend/main.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/main.py)
  - **Responsabilidade:** Inicialização do FastAPI, CORS, middleware de telemetria, montagem de rotas REST e endpoints WebSocket (`/ws/chat`, `/ws/missions`, `/ws/telemetry`).
  - **Integração:** `IMPLEMENTED_AND_INTEGRATED`.
  - **Limitações:** Existem scripts alternativos em `scripts/` (e.g., `start_backend.py`, `start_complete_system.py`) que inicializam servidores Uvicorn em portas diferentes ou com subconjuntos de rotas.
- **WebSocket Chat Handler:** [backend/websocket/handlers/chat.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/websocket/handlers/chat.py)
  - **Responsabilidade:** Gestão do canal bidirecional de mensagens do utilizador, streaming de tokens de resposta do LLM, broadcasting de eventos de execução e tratamento de interrupções de chat.
  - **Integração:** `IMPLEMENTED_AND_INTEGRATED`.
- **WebSocket Missions Handler:** [backend/websocket/handlers/missions.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/websocket/handlers/missions.py)
  - **Responsabilidade:** Subscrição em tempo real aos estados das missões, broadcast de transições de estado (`DRAFT` -> `ACTIVE` -> `COMPLETED`), e exposição do estado da federação.
  - **Integração:** `INTEGRATION_BROKEN`. A rota `/ws/missions` tenta aceder à propriedade `orch.swarm_federation` que está permanentemente a `None` no ciclo de vida de produção.

### 2.2 Serviços de Domínio e Orquestração
- **ChatMissionBridge:** [backend/services/chat_mission_bridge.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/chat_mission_bridge.py)
  - **Responsabilidade:** Converte mensagens do utilizador classificadas como tarefas de execução em missões formais, grava o registo de estado em `MissionStateStore`, e aciona a execução.
  - **Integração:** `IMPLEMENTED_AND_INTEGRATED`.
  - **Limitação:** Não encaminha para `MissionLifecycleOrchestrator.run()`; desvia para `OrchestrationService._run_agent_orchestration()` ou `ProjectBuilder`.
- **OrchestrationService:** [backend/services/orchestration_service.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/orchestration_service.py)
  - **Responsabilidade:** Execução do loop de personas (Architect, Coder, Tester, Reviewer), gestão de prompts de equipa e consolidação de saídas de código.
  - **Integração:** `IMPLEMENTED_AND_INTEGRATED`.
- **ProjectIntakeService:** [backend/services/project_intake_service.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/project_intake_service.py)
  - **Responsabilidade:** Ingestão de projetos existentes ou novos, leitura de metadados, identificação de linguagens e geração de snapshots estruturais.
  - **Integração:** `IMPLEMENTED_AND_INTEGRATED`.

---

## 3. FRONTEND E INTERFACE DO UTILIZADOR

- **Localização:** `frontend/`
- **Stack:** React 18, Vite, TypeScript, TailwindCSS, Lucide React, Radix UI.
- **Componentes Principais:**
  - `frontend/src/components/chat/ChatContainer.tsx`: Interface principal de chat, histórico e streaming de texto.
  - `frontend/src/components/missions/MissionBoard.tsx`: Painel Kanban de visualização de missões, work packages e evidências de entrega.
  - `frontend/src/components/projects/ProjectExplorer.tsx`: Árvore de navegação e visualizador de ficheiros do projeto ativo.
  - `frontend/src/components/telemetry/TelemetryDashboard.tsx`: Gráficos de uso de CPU, memória e tokens.
- **Estado de Integração:** `IMPLEMENTED_AND_INTEGRATED`.
- **Evidências:** O frontend comunica via WebSockets com o backend nas portas 8000/8001. Contudo, cards de Swarm Federation mostram dados estáticos ou ficam cinzentos devido à inatividade da federação no backend.

---

## 4. ENTRYPOINTS E PONTOS DE ARRANQUE

A auditoria identificou uma pluralidade de scripts de entrada com responsabilidades sobrepostas:

1. [backend/main.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/main.py): Ponto de entrada padrão da API FastAPI (uvicorn).
2. [scripts/start_backend.py](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/start_backend.py): Wrapper de inicialização com verificação de ambiente prévia.
3. [scripts/start_complete_system.py](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/start_complete_system.py): Inicia simultaneamente o backend FastAPI e o frontend Vite via subprocessos.
4. [scripts/run_production_gate.py](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_production_gate.py): Runner isolado para validação do Product Delivery Gate.
5. [scripts/run_swarm_benchmark.py](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_swarm_benchmark.py): Runner de benchmark sintético de swarm e workers.
6. [scripts/run_word_engine_demo.py](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_word_engine_demo.py): Runner de demonstração de geração e revisão de documentos Word.

---

## 5. FERRAMENTAS EXECUTÁVEIS (TOOL REGISTRY)

Todas as ferramentas operacionais do JARVIS OS estão concentradas e registadas em [agents/tools.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/tools.py). A tabela seguinte cataloga as **30 ferramentas nativas**:

| Nome da Ferramenta | Função / Capacidade | Dependências | Estado Operacional |
| :--- | :--- | :--- | :--- |
| `read_file` | Lê ficheiro em UTF-8 com limite de linhas | Sistema de Ficheiros | `IMPLEMENTED_AND_INTEGRATED` |
| `write_file` | Cria ou substitui ficheiro no workspace | Sistema de Ficheiros | `IMPLEMENTED_AND_INTEGRATED` |
| `edit_file` | Substituição exata de blocos de texto | Sistema de Ficheiros | `IMPLEMENTED_AND_INTEGRATED` |
| `list_directory` | Lista diretórios e metadados de ficheiros | Sistema de Ficheiros | `IMPLEMENTED_AND_INTEGRATED` |
| `search_code` | Pesquisa textual ou regex em diretórios | Python `re` / `os.walk` | `IMPLEMENTED_AND_INTEGRATED` |
| `execute_command` | Executa comandos shell no workspace | Subprocesso PowerShell | `IMPLEMENTED_AND_INTEGRATED` |
| `git_status` | Obtém branch, ficheiros modificados e staged | Binário `git` no PATH | `IMPLEMENTED_AND_INTEGRATED` |
| `git_diff` | Gera diffs de alterações locais | Binário `git` no PATH | `IMPLEMENTED_AND_INTEGRATED` |
| `git_commit` | Cria commits Git com mensagem | Binário `git` no PATH | `IMPLEMENTED_AND_INTEGRATED` |
| `run_tests` | Executa pytest com captura de exitcode | `pytest` no venv | `IMPLEMENTED_AND_INTEGRATED` |
| `run_linter` | Executa flake8/ruff para validação estática | Linters instalados | `IMPLEMENTED_AND_INTEGRATED` |
| `install_package` | Instala dependências via pip/npm | `pip` / `npm` no PATH | `IMPLEMENTED_AND_INTEGRATED` |
| `project_structure` | Retorna árvore estrutural do projeto | Sistema de Ficheiros | `IMPLEMENTED_AND_INTEGRATED` |
| `browser_navigate` | Abre URL em browser headless | Playwright | `PARTIALLY_IMPLEMENTED` |
| `browser_screenshot` | Captura screenshot da página | Playwright | `PARTIALLY_IMPLEMENTED` |
| `browser_click` | Clica em seletores CSS na página | Playwright | `PARTIALLY_IMPLEMENTED` |
| `browser_fill` | Preenche campos de formulário web | Playwright | `PARTIALLY_IMPLEMENTED` |
| `firecrawl_scrape` | Extração profunda de páginas web | `FIRECRAWL_API_KEY` | `BLOCKED_BY_ENVIRONMENT` |
| `apify_scrape` | Scraping avançado via atores Apify | `APIFY_API_TOKEN` | `BLOCKED_BY_ENVIRONMENT` |
| `web_search` | Pesquisa DuckDuckGo / Tavily | `tavily` / requests | `PARTIALLY_IMPLEMENTED` |
| `document_create` | Cria documento Word/Markdown/PDF | Document Engine | `IMPLEMENTED_AND_INTEGRATED` |
| `document_inspect` | Extrai AST estrutural de DOCX | `python-docx` / AST | `IMPLEMENTED_AND_INTEGRATED` |
| `document_revise` | Aplica revisão cirúrgica a DOCX | `SurgicalRevisor` | `IMPLEMENTED_AND_INTEGRATED` |
| `docker_ps` | Lista contentores Docker ativos | Docker Desktop | `BLOCKED_BY_ENVIRONMENT` |
| `docker_build` | Constrói imagem Dockerfile | Docker Desktop | `BLOCKED_BY_ENVIRONMENT` |
| `process_list` | Lista processos locais e consumo | `psutil` | `IMPLEMENTED_AND_INTEGRATED` |
| `process_kill` | Termina processo pelo PID | `psutil` / Windows API | `IMPLEMENTED_AND_INTEGRATED` |
| `db_query` | Executa consultas SQL em base de dados | SQLite local | `IMPLEMENTED_AND_INTEGRATED` |
| `workspace_snapshot` | Cria arquivo ZIP de backup do projeto | Python `zipfile` | `IMPLEMENTED_AND_INTEGRATED` |
| `gate_verify` | Executa pipeline do ProductDeliveryGate | Delivery Gate | `IMPLEMENTED_AND_INTEGRATED` |

---

## 6. SISTEMAS DE PLANEAMENTO E COORDENAÇÃO

1. **HierarchicalPlanner ([agents/hierarchical_planner.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/hierarchical_planner.py)):**
   - Decompõe pedidos complexos de utilizador em Epics, Features, WorkPackages e Tasks atómicas.
   - Atribui critérios de aceitação e estimativas de risco.
   - Estado: `IMPLEMENTED_AND_INTEGRATED`.
2. **TaskGraph ([agents/task_graph.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/task_graph.py)):**
   - Modela dependências entre tarefas através de um grafo acíclico dirigido (DAG).
   - Suporta deteção de ciclos, nós paralelos e bloqueios de dependência.
   - Estado: `IMPLEMENTED_AND_INTEGRATED` (usado nos testes e orquestrador formal, contornado pelo chat linear).
3. **ActionTargetEvaluator ([security/action_target_evaluator.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/action_target_evaluator.py)):**
   - Analisa se uma mensagem do utilizador se refere ao próprio JARVIS, ao workspace ativo ou a um caminho externo.
   - Previne modificações acidentais fora do workspace.
   - Estado: `EXECUTION_VERIFIED`.

---

## 7. ENGENHARIA DE SOFTWARE AUTÓNOMA E EXECUÇÃO DE CÓDIGO

- **ProjectBuilder ([agents/project_builder.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/project_builder.py)):**
  - Motor central de construção e modificação de software. Coordena planeamento, geração de ficheiros, compilação de testes e execução do Delivery Gate.
  - Estado: `EXECUTION_VERIFIED`.
- **PatchEngine ([agents/patch_engine.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/patch_engine.py)):**
  - Aplica alterações cirúrgicas em ficheiros de código existentes sem reescrever o ficheiro completo. Resolve conflitos de linha e calcula diffs unificados.
  - Estado: `EXECUTION_VERIFIED`.
- **WorkspaceContext ([agents/workspace_context.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/workspace_context.py)):**
  - Indexa a estrutura de ficheiros do projeto, classes, funções e dependências de importação.
  - Fornece contexto relevante ao LLM durante a fase de geração de código.
  - Estado: `IMPLEMENTED_AND_INTEGRATED`.

---

## 8. MOTOR DOCUMENTAL (WORD & ARTEFACTOS)

O motor documental é um dos subsistemas mais avançados do repositório, com arquitetura em camadas completas em `backend/document_engine/`:

1. **WordDocumentAST ([backend/document_engine/word_document_ast.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_document_ast.py)):**
   - Modela o documento Word como uma árvore estrutural independente de nós (Headings, Paragraphs, Tables, Images, Sections, Footnotes, Lists).
2. **WordEngine ([backend/document_engine/word_engine.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_engine.py)):**
   - Interface de alto nível para criação, leitura, montagem e serialização de documentos `.docx`.
3. **WordStyler ([backend/document_engine/word_styler.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_styler.py)):**
   - Aplica perfis tipográficos profissionais (Executive, Academic, TechModern, Legal) com esquemas de cores e estilos de tabela.
4. **SurgicalRevisor ([backend/document_engine/surgical_revisor.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/surgical_revisor.py)):**
   - Realiza edições cirúrgicas em documentos existentes preservando cabeçalhos, imagens e estilos originais.
5. **VisualInspector ([backend/document_engine/visual_inspector.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/visual_inspector.py)):**
   - Renderiza páginas do documento para imagem e analisa anomalias de paginação, linhas orfãs e corte de tabelas.
6. **Automação Word COM ([backend/document_engine/word_com_automation.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_com_automation.py)):**
   - Interage diretamente com a aplicação nativa `WINWORD.EXE` no Windows via OLE/COM (`win32com.client`).
   - Atualiza campos complexos (TOC - Tabela de Conteúdos, números de página, numeração de figuras) e exporta para PDF fiel.
   - **Estado:** `EXECUTION_VERIFIED` (25/25 testes de integração com o Word real executados com sucesso).

---

## 9. PRODUCT DELIVERY GATE E VALIDAÇÃO DE QUALIDADE

O pipeline de aceitação em [security/delivery_governance/](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/) assegura que nenhum trabalho é declarado como concluído sem validação rigorosa:

- **ProductDeliveryGate ([security/delivery_governance/product_delivery_gate.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/product_delivery_gate.py)):** Orquestrador de validação em estágios (`LINT`, `BUILD`, `RUNTIME`, `INTEGRITY`, `CONTRACT`, `BROWSER`).
- **RuntimeTracker ([security/delivery_governance/runtime_tracker.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/runtime_tracker.py)):** Monitoriza o arranque de servidores locais e verifica se a porta responde a HTTP GET sem crash.
- **ServedAssetIntegrityValidator ([security/delivery_governance/served_asset_integrity_validator.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/served_asset_integrity_validator.py)):** Valida se ficheiros CSS/JS servidos não estão truncados, vazios ou corrompidos.
- **ContractValidator ([security/delivery_governance/contract_validator.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/contract_validator.py)):** Valida se os endpoints da API cumprem os contratos JSON Schema especificados.
- **RealBrowserQAValidator ([security/delivery_governance/real_browser_qa_validator.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/real_browser_qa_validator.py)):** Executa testes em browser real capturando erros na consola e screenshots.

---

## 10. SEGURANÇA, POLÍTICAS E AUTORIZAÇÃO

- **DecisionEngine ([security/decision_engine.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/decision_engine.py)):** Avalia o risco da operação solicitada e determina se requer confirmação do utilizador.
- **SafetyClassifier ([security/safety_classifier.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/safety_classifier.py)):**
  - Classifica intenções perigosas (malware, ddos, ataques, exfiltração).
  - **Estado:** `INTEGRATION_BROKEN / P0 DEFECT`.
  - Falha crítica confirmada: regex restrito ao infinitivo permite bypass imediato com verbos imperativos (*"executa ataque..."*).
- **ExecutionTruthEnforcer ([security/execution_truth_enforcer.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/execution_truth_enforcer.py)):**
  - Impede "teatro de IA", verificando se a resposta gerada alega ter modificado ficheiros ou corrido comandos sem haver registo de chamada de ferramenta correspondente.
  - Estado: `EXECUTION_VERIFIED`.

---

## 11. PERSISTÊNCIA E MEMÓRIA

- **SQLite Database (`database.db`):**
  - Armazena 1.477 trajetórias de inferência (`model_trajectories`), 366 regras heurísticas (`rho_compounding_rules`), 311 sessões (`sessions`) e 66 projetos (`projects`).
  - As tabelas `messages`, `compounding_memory`, `strategic_goals`, `engineering_decisions` e `event_sourcing_log` contêm 0 registos.
- **MissionStateStore ([agents/mission_state_store.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_state_store.py)):**
  - Fonte da verdade real das missões. Guarda ficheiros JSON em `.jarvis/projects/<project_id>/missions/<mission_id>.json`.
  - Suporta transições de estado idempotentes e checkpoints atómicos.
  - Estado: `IMPLEMENTED_AND_INTEGRATED`.
- **Módulos em `persistence/`:**
  - 8 ficheiros Python contendo 57 linhas no total. Interfaces abstratas sem implementação de repositório ativa. Estado: `IMPLEMENTED_BUT_UNREACHABLE`.
