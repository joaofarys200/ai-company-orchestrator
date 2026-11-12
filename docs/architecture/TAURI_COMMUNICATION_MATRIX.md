# JARVIS OS — Matriz Completa de Comunicação e Mapeamento Tauri 2

**Baseline analisada:** `main` @ `fb1aeeda10652ed1662e7e5c24ed381d7635f8d0`  
**Fontes verificadas no código:** `websocket_schema.py` (263 `CLIENT_MESSAGE_TYPES`, 272 `SERVER_MESSAGE_TYPES`), `main.js`, `preload.js`, `server.py`, `backend/transport_gateway.py`, `backend/services/sandbox_service.py`, `backend/websocket/handlers/*.py`, `backend/model_harness/providers/ollama.py`, `sandbox.py`, `frontend/src/context/WebSocketContext.tsx`, `frontend/src/protocol/websocket.ts`, `frontend/src/features/study/StudyVideoReaderView.tsx`.

---

## 1. Taxonomia dos Mecanismos Alvo em Tauri 2

| Mecanismo Alvo | Papel na Arquitetura Tauri 2 | Quando Usar |
|---|---|---|
| **Tauri `Command` (`invoke`)** | RPC síncrono/assíncrono Request → Response correlacionado por Promise nativa | Pedidos iniciados pela UI com resposta determinística (CRUD, leitura, ações, início/cancelamento de jobs) |
| **Tauri `Event` (`app.emit`)** | Push assíncrono Rust Core → WebView (1-para-N janelas) | Mudanças de estado de sistema, notificações de aprovação HITL, conclusões em background, alertas Sentinel |
| **Tauri `Channel<T>`** | Stream ordenado ponto-a-ponto ligado a um `invoke` ativo | Streaming de tokens LLM, níveis de áudio, progresso de ingestão/geração de estudos, logs contínuos de build/execução |
| **Loopback HTTP (`127.0.0.1:0`)** | Servidor HTTP nativo em Rust em porta efémera com `Range: bytes=...` (`206 Partial Content`) | Leitura direta de PDF (`pdfjs-dist`), MP4 (`<video>`), frames/miniaturas (`<img>`) e Preview IDE isolado sem `jarvis-media://` (instável no WebView2 para Range 206 / Web Workers) |
| **Worker NDJSON (`stdin`/`stdout`)** | Barramento interno `Rust Core ↔ Python Specialized Worker` + **Reverse RPC** | Execução isolada de tarefas IA/Study/Knowledge e pedidos síncronos de aprovação HITL (`reverse_request`) |
| **Barramento Interno Rust (`tokio::sync`)** | Canais `mpsc` / `broadcast` intra-processo | Coordenação entre `AppState`, `PermissionGate`, `LoopbackHTTP`, `Sentinel` e `WorkerPool` |
| **WebSocket / HTTP Externo ou Loopback Isolado** | Sockets mantidos fora do IPC | Ollama HTTP `127.0.0.1:11434` (via Python `ModelExecutionService`); Gemini Live WSS (`gemini_live.py`) |

---

## 2. Anomalias e Assimetrias de Protocolo Validadas Empiricamente [Confirmado no código]

Antes da migração de transporte, foram confirmadas 6 anomalias reais e quantificadas no protocolo atual através de inspeção exaustiva do código-fonte:

1. **`StdioTransportGateway` sem validação de schema**: `backend/websocket/gateway.py` invoca `validate_client_message()`, enquanto `backend/transport_gateway.py` (`StdioTransportGateway`) encaminha JSON bruto sem qualquer validação.
2. **33 operações no-op em `MISSION_HANDLERS`**: em `backend/websocket/handlers/missions.py`, 33 chaves registadas no dicionário `MISSION_HANDLERS` não possuem ramo `elif` correspondente no método de despacho `handle()`, resultando em descarte silencioso da mensagem.
3. **14 ramos mortos inalcançáveis em `missions.py`**: existem 14 blocos `elif msg_type == ...` no dispatcher `handle()` que comparam strings de tipo que **não constam em `CLIENT_MESSAGE_TYPES`**, sendo sumariamente rejeitados pela validação do gateway antes de chegarem ao handler.
4. **57 eventos emitidos pelo servidor ausentes de `SERVER_MESSAGE_TYPES`**: a auditoria identificou exatamente 57 tipos de mensagens disparados em runtime pelo backend Python (incluindo `architecture_snapshot`, `coding_session_error`, `safety_refusal`, `lecture_error`, `project_intake_status`, `sentinel_review_result`, `sentinel_shadow_telemetry`, `study_document_deleted`, `error` e 32 variantes dinâmicas de resposta de missões e impactos) que não estão declarados no schema formal `websocket_schema.py`.
5. **144 mensagens do servidor sem consumidor na UI**: das 272 mensagens em `SERVER_MESSAGE_TYPES`, exatamente 144 tipos não possuem qualquer bloco `case` no `switch` de processamento de eventos do `WebSocketContext.tsx` (incluindo `note_saved`, `sentinel_action_result`, etc.), sendo silenciosamente ignorados pelo frontend.
6. **20 mensagens de cliente ausentes da união TypeScript**: o frontend despacha 101 tipos distintos de mensagens, mas exatamente 20 mensagens emitidas por componentes React (incluindo `study_update_video_progress` e `study_save_video_note` em `StudyVideoReaderView.tsx`) estão ausentes da definição de união `ClientMessage` em `frontend/src/protocol/websocket.ts`, causando quebras de tipagem estrita no TypeScript.

### Tabela de Auditoria de Paridade de Mensagens
| Métrica de Comunicação | Quantidade Verificada | Estado no Código Atual | Resolução em Tauri 2 |
|---|---|---|---|
| **Mensagens Cliente Declaradas (`CLIENT_MESSAGE_TYPES`)** | 263 | Validado em `websocket_schema.py` | Substituído por `tauri::command` tipados |
| **Mensagens Cliente Despachadas pela UI** | 101 | Identificadas em `WebSocketContext.tsx` e views | Mapeadas para comandos e channels |
| **Mensagens Cliente Faltando na União TS (`ClientMessage`)** | **20** | Ausentes em `frontend/src/protocol/websocket.ts` | Adicionadas ao contrato `JarvisTransport` |
| **Mensagens Servidor Declaradas (`SERVER_MESSAGE_TYPES`)** | 272 | Validado em `websocket_schema.py` | Mapeadas para `tauri::event` / `Channel` |
| **Mensagens Servidor Emitidas sem Declaração no Schema** | **57** | Disparadas dinamicamente no backend | Formalizadas ou podadas no contrato |
| **Mensagens Servidor sem Handler no Frontend (`switch`)** | **144** | Ignoradas silenciosamente em `WebSocketContext` | Podadas ou tratadas no `TransportAdapter` |
| **Handlers Registados sem Ramo de Execução (`missions.py`)** | **33** | Presentes em `MISSION_HANDLERS`, sem `elif` | Auditados e podados na Etapa 1 |
| **Ramos Mortos Inalcançáveis (`missions.py`)** | **14** | `elif` presente mas rejeitado no gateway | Removidos na consolidação da Etapa 1 |

### Detalhe e Classificação Forense das Discrepâncias
1. **Os 14 Ramos Mortos Inalcançáveis (`missions.py:1456-1716`):**
   - *Causa-Raiz:* O gateway `backend/websocket/gateway.py:108` valida mensagens contra `CLIENT_MESSAGE_TYPES`. Como nenhum destes 14 tipos consta na lista, são rejeitados antes de alcançar o router.
   - *Classificação:* **Código Morto / Inalcançável** (`mission_task_completion_run`, `mission_task_completion_status`, `mission_massive_project_state_status`, `mission_massive_project_state_plan_change`, `mission_scc_graph_status`, `mission_scc_graph_query_impact`, `mission_symbol_graph_status`, `mission_symbol_graph_query_impact`, `mission_test_synthesis_status`, `mission_test_synthesis_generate`, `mission_continuous_verification_status`, `mission_continuous_verification_run`, `mission_cross_project_learning_status`, `mission_cross_project_learning_transfer`).
2. **As 33 Operações No-Op em `MISSION_HANDLERS` (`missions.py:68-120`):**
   - *Causa-Raiz:* Chaves registadas no dicionário mas sem ramo `elif operation == "..."` no método `handle()`, caindo no default que apenas reenvia `mission_list`.
   - *Classificação:* **Defeito Confirmado / Handler Ausente** (inclui `mission_loop_status`, `mission_loop_step`, `mission_loop_run`, `mission_loop_respond_human`, `mission_semantic_graph_status`, `mission_contract_*`, `mission_polymorphic_*`, `mission_long_horizon_*`, `mission_quality_governance_*`).
3. **As 57 Mensagens Emitidas em Runtime sem Declaração no Schema:**
   - *Classificação:* **9 Defeitos Confirmados da UI** (`architecture_snapshot`, `safety_refusal`, `coding_session_error`, `lecture_error`, `project_intake_status`, `sentinel_review_result`, `sentinel_shadow_telemetry`, `study_document_deleted`, `mission_understanding`); **11 Eventos de Simulação Interna** (`TASK_*`, `IMPACT_*`); e **37 Respostas de Missão** (`mission_*_result`, `mission_*_response`).
4. **As 20 Mensagens Despachadas na UI em Falta na União TypeScript (`ClientMessage`):**
   - *Classificação:* **Defeitos Confirmados de Tipagem** (`study_update_video_progress`, `study_save_video_note`, `mission_control_command`, `mission_control_get`, `mission_intent_preview`, `mission_intent_change`, `mission_resume_snapshot`, `mission_delete`, `mission_cancel_execution`, `action_confirm_response`, etc.).
5. **As 144 Mensagens de Servidor sem Switch Handler na UI:**
   - *Classificação:* **57 Eventos de Telemetria Multi-Host / Cluster** (código dormente); **66 Benchmarks de Governança de Missões** (CLI-only); **13 Eventos de Experiência de Estudo** (defeitos confirmados que descartam notas de vídeo e momentos explicados: `study_explain_video_moment_result`, `study_video_note_saved`, etc.); **1 Conhecimento** (`note_saved`); e **7 Eventos de Aulas** (`lecture_audio_level`, `lecture_session_update`, etc.).

---

## 3. Matriz Principal de Comunicação (Electron, HTTP, WebSocket & Serviços)

### 3.1 IPC Nativo Electron (`main.js` / `preload.js`) & Transporte HTTP Local

| Evento / Operação | Origem | Destino | Payload | Utilização | Frequência | Substituição Proposta (Tauri 2) |
|---|---|---|---|---|---|---|
| `window.jarvisIPC.send` | Frontend (`WebSocketContext.tsx`) | Electron `main.js` → `server.py` `stdin` | JSON serializado (32 tipos dedup 1500ms) | Canal alternativo/primário de comandos | Média (interação UI) | **Tauri `Command` (`invoke`)** tipado por domínio; remove dedup 1500ms ad-hoc |
| `window.jarvisIPC.onMessage` | `server.py` `stdout` → Electron `main.js` | Frontend (`WebSocketContext.tsx`) | NDJSON broadcast/resposta | Receção de respostas e eventos via stdio | Alta | **Tauri `Event` (`listen`)** + **`Channel<T>`** |
| `window.jarvisIPC.selectFolder` | `StudyLibraryView.tsx` | Electron `dialog.showOpenDialog` | `{ canceled, path }` | Selecionar pasta de estudos local | Baixa (sob ação) | **`tauri-plugin-dialog`** (`open({ directory: true })`) |
| `window.jarvisIPC.openPath` | `StudyContainer.tsx`, `StudyLibraryView.tsx` | Electron `shell.openPath` | `targetPath` (validado contra allowlist) | Abrir PDF/DOCX/pasta no SO | Baixa (sob ação) | **Tauri `Command` `system_open_path`** + Path Jail + `tauri-plugin-opener` |
| `window.jarvisIPC.getPathForFile` | `StudyLibraryView.tsx` | Electron `webUtils.getPathForFile` | `File` DOM → path absoluto | Drag-and-drop de materiais de estudo | Baixa | **Tauri Drag-and-Drop event** (`tauri://drag-drop` fornece `paths[]` nativos) |
| `ws://127.0.0.1:8001/?token=...` | Frontend `WebSocketContext.tsx` | `server.py` (`websockets==16.0`) | Envelope JSON `{ type, ... }` (`max_size=32MiB`) | Barramento bidirecional de 263 req / 272+ evt | Muito alta | **Eliminado em produção**; substituído por **Tauri `invoke` + `emit` + `Channel<T>`** (mantido apenas em ponte temporária de migração) |
| `GET /healthz`, `/health.json` | Dev/Playwright/Probe | `sandbox_service.py` (`:8000`) | JSON `{ status, ... }` | Health check HTTP local | Baixa | **Tauri `Command` `system_health`** (ou loopback dev opcional) |
| `GET /api/study/documents` | Frontend/Testes | `sandbox_service.py` (`:8000`) | Lista JSON metadados estudo | Listagem HTTP alternativa ao WS | Baixa | **Tauri `Command` `study_list_documents`** |
| `HEAD/GET /api/study/document/{id}/file` | `StudyReaderView.tsx` (`pdfjs-dist`) | `sandbox_service.py` (`:8000`) + `X-Jarvis-Token` | Bytes PDF + `Range` (`206 Partial Content`) | Leitura e paginação de PDFs | Alta (leitura ativa) | **Rust Loopback HTTP `http://127.0.0.1:<port>/study/{id}/file`** (Range 206 nativo) |
| `HEAD/GET /api/study/document/{id}/video` | `StudyVideoReaderView.tsx` (`<video>`) | `sandbox_service.py` (`:8000`) + `?token=` | Stream MP4 + `Range` (`206 Partial Content`) | Reprodução e seek de vídeos de aula | Alta (vídeo ativo) | **Rust Loopback HTTP `http://127.0.0.1:<port>/study/{id}/video`** (Range 206 nativo) |
| `GET /api/study/document/{id}/media/{frame_id}` | `StudyVideoReaderView.tsx` (`<img>`) | `sandbox_service.py` (`:8000`) + `?token=` | Imagem PNG/JPG frame extraído | Visualização de slides/frames chave | Média | **Rust Loopback HTTP `http://127.0.0.1:<port>/study/{id}/media/{frame_id}`** |
| `GET /data/study/{subpath}` & SPA static | Frontend/WebView | `sandbox_service.py` (`:8000`) | Ficheiros estáticos Study / `dist/` | Acesso direto a artefactos & build estático | Média | **Rust Loopback HTTP (`127.0.0.1:0`)** (artefactos) + bundling nativo `frontendDist` do Tauri |
| Preview Server `TCPServer(("", 8080))` | `WorkspaceViewer.tsx` (`<iframe>`) | `sandbox.py` (`0.0.0.0:8080`) | HTML/JS/CSS do projeto gerado | Pré-visualização live de projetos IDE | Média (IDE ativo) | **Rust `PreviewServer` em `127.0.0.1:0` (porta efémera)** dentro de janela/CSP isolada |
| `http://127.0.0.1:11434/api/{chat,generate,tags,ps}` | `backend/model_harness/providers/ollama.py` | Daemon Ollama local | NDJSON prompts/tokens/modelos | Inferência local, warmup, inspeção VRAM | Alta | **Python `ModelExecutionService` (Abordagem C)** + **Rust Event Fanout `Channel<TokenDelta>`** |
| WSS Gemini Live (`gemini_live.py`) | `services/gemini_live.py` | Google Gemini Live API (Cloud) | Frames PCM áudio 16kHz + texto/controlo | Conversação voz em tempo real | Contínua (quando ativo) | **Retido em Python `voice_swarm_worker`** (áudio HW + WSS externo) durante transição; notificações UI via `Channel<AudioEvent>` |

---

### 3.2 Operações de Cliente por Domínio (Total: 263 `CLIENT_MESSAGE_TYPES`)

Todas as 263 mensagens declaradas em `websocket_schema.py` agrupadas por domínio funcional, destino atual e substituição proposta:

#### A. Chat, Sistema e Voz (`chat`: 2, `system`: 2, `voice`: 1 — Total: 5)
| Evento / Operação (Cliente → Servidor) | Origem | Destino Atual | Payload Resumido | Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| `directive`, `start_improvement_batch` | `Chat` / `SpatialBoard` | `agents/orchestrator/` | `{ text, mode, conversation_id, attachments }` | Prompt principal do assistente & melhoria contínua | Alta / Baixa | **Tauri `Command` `chat_send_directive(channel)`** (Rust Orchestrator + Ollama / Worker legado) + **`Command` `system_start_improvement_batch`** |
| `get_queue_status`, `pause_queue_worker`, `resume_queue_worker` | Painel Sistema / Fila | `server.py` / Fila | `{ worker_id? }` | Telemetria e controlo de fila de execução | Baixa/Média | **Tauri `Command`** + **`Event` `queue_worker_status`** (Rust Core) |
| `toggle_voice` | Barra de Voz / `VoiceOrb` | `services/gemini_live.py` | `{ enabled, mode? }` | Ativa/desativa captura microfone + Gemini Live | Baixa (ação) | **Tauri `Command` `voice_toggle`** → `voice_swarm_worker` + **`Channel<VoiceLevel>`** |

#### B. Projetos, Código & AST (`projects`: 13, `coding`: 4 — Total: 17)
| Evento / Operação | Origem | Destino Atual | Payload Resumido | Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| `list_projects`, `open_project`, `create_project`, `delete_project` | `ProjectsView`, `WorkspaceViewer` | `intelligence/project_*.py`, `database.py` | `{ project_id, name, path, template? }` | Gestão de ciclo de vida de projetos no workspace | Baixa/Média | **Tauri `Command`** em Rust (`storage/sqlite` + `process`) |
| `select_template`, `run_project`, `stop_project` | IDE / Preview Toolbar | `project_builder.py`, `sandbox.py` | `{ project_id, template, entry? }` | Escolha de template, execução e paragem de servidor/build | Média | **Tauri `Command`** em Rust (`process/job_object.rs` + `preview_server.rs`) + **`Channel<ProjectOutputChunk>`** |
| `create_project_file`, `save_project_file`, `rename_project_file`, `delete_project_file` | Monaco Editor / Explorer | `services/project_files` + `workspace_policy` | `{ project_id, path, content, new_path? }` | CRUD de ficheiros do projeto (com Path Jail) | Alta (edição) | **Tauri `Command`** em Rust (`permissions/path_jail.rs` + `atomic_fs.rs`) |
| `index_project`, `get_ast_state`, `find_references`, `semantic_search` | IDE Intelligence Panel | `tree-sitter`, `scripts/ts_ast_parser.js`, `chromadb` | `{ project_id, symbol, query, file? }` | Indexação AST/semântica e pesquisa de referências | Média | **Tauri `Command`** → delegado via **NDJSON para `knowledge_worker`** |
| `create_coding_session`, `get_coding_session`, `apply_coding_session`, `rollback_coding_session` | `CodingAgent` / Diff Viewer | `intelligence/coding_session.py` (`git_blob`/backups) | `{ session_id, project_id, patches }` | Edições multi-ficheiro com checkpoint e rollback | Média | **Tauri `Command`** (fase transitória via worker; checkpoints migrados para Rust git/backup atómico) |

#### C. Permissões & Aprovação HITL (`permissions`: 6)
| Evento / Operação | Origem | Destino Atual | Payload Resumido | Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| `permission_get_pending`, `permission_approve`, `permission_deny`, `permission_resolve_choice`, `permission_rollback`, `action_confirm_response` | Modal de Confirmação / Gate UI | `security/permission_gateway/` (`.jarvis/permissions/`) | `{ request_id, approved, choice?, scope }` | Aprovação humana explícita (TTL 300s) para comandos/ficheiros sensíveis e rollback | Média (bloqueante) | **Tauri `Command`** em **Rust Core (`permissions/gateway.rs`)** + **`Event` `permission_request_created/expired`** |

#### D. Sentinel (`sentinel`: 10)
| Evento / Operação | Origem | Destino Atual | Payload Resumido | Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| `sentinel_get_status`, `sentinel_get_baseline`, `sentinel_get_actions`, `sentinel_get_shadow_telemetry`, `sentinel_run_audit` | Painel Sentinel | `security/sentinel/` (6 coletores Win32) | `{ scope?, limit? }` | Inspeção de segurança local, baseline e modo shadow | Baixa/Média | **Tauri `Command`** em **Rust (`sentinel/`)** + **`Event` `sentinel_audit_completed`** |
| `sentinel_accept_known_good`, `sentinel_approve_action`, `sentinel_reject_action`, `sentinel_rollback_action`, `sentinel_submit_review` | Painel Sentinel HITL | `security/sentinel/response/engine.py` | `{ action_id, decision, notes? }` | Contenção Win32 (`schtasks`, `netsh`, `taskkill`) aprovada por humano e reversão | Baixa (crítica) | **Tauri `Command`** em Rust (executor protegido + registo atómico em SQLite/quarantine) |

#### E. Conhecimento / Obsidian (`knowledge`: 15)
| Evento / Operação | Origem | Destino Atual | Payload Resumido | Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| `get_notes`, `read_note`, `save_note`, `rollback_note`, `enrich_note`, `audit_note_quality`, `get_vault_diagnostics` | `ObsidianVaultView` / Graph UI | `services/obsidian_graph_engine.py`, `NoteFileLock` | `{ path, content, version_id?, query? }` | Navegação, edição atómica, grafo, auditoria e rollback de notas `.md` | Média/Alta | **Tauri `Command`** → **`knowledge_worker`** (ObsidianGraphEngine + LLM via OllamaGateway) |
| `get_rules`, `delete_rule`, `delete_decision`, `delete_architecture` | Painel Regras & ADRs | `database.py` / `obsidian_vault/` | `{ rule_id / decision_id / arch_id }` | Gestão de regras persistidas, decisões e arquiteturas | Baixa | **Tauri `Command`** em Rust (`storage/sqlite.rs` + `knowledge_worker` para markdown) |
| `get_planner_state`, `criterion_create`, `criterion_set_status`, `deliverable_create`, `deliverable_set_status`, `deliverable_update`, `evidence_attach` | Planner / Critérios / Entregáveis | `database.py` / `backend/websocket/handlers/knowledge.py` | `{ item_id, status, title, evidence }` | Acompanhamento de entregáveis e critérios de qualidade | Baixa/Média | **Tauri `Command`** em Rust (`storage/sqlite.rs`) |

*(Nota: o total exato confirmado de operações de cliente registadas no domínio `knowledge` no router atual é 15 mensagens de entrada; `criterion_*` / `deliverable_*` / `evidence_attach` partilham o contexto de planeamento/missões.)*

#### F. Estudos & Palestras/Aulas (`study`: 75 + `lectures`: 6 — Total: 81)
| Subgrupo | Operações (`CLIENT_MESSAGE_TYPES`) | Origem | Destino Atual | Payload / Utilização | Frequência | Substituição Proposta |
|---|---|---|---|---|---|---|
| **Biblioteca & Pastas** (10) | `study_list_documents`, `study_get_document`, `study_get_document_file`, `study_upload_document`, `study_retry_document`, `study_delete_document`, `study_create_collection`, `study_list_collections`, `study_link_folder`, `study_sync_folder`, `study_unlink_folder` | `StudyLibraryView`, `StudyContainer` | `StudyService`, `study_fs.py`, `data/study/` | Catálogo, upload/ingestão, sync de pastas locais, coleções | Média | **Tauri `Command`** → metadata em Rust SQLite + ingestão pesada no **`study_worker`** + **`Channel<Progress>`**; ficheiros lidos via Loopback HTTP (`127.0.0.1:0`) |
| **Leitura, AST, Vídeo & Progresso** (10) | `study_get_document_ast`, `study_update_progress`, `study_add_highlight`, `study_add_reading_note`, `study_ingest_video_url`, `study_get_video_context`, `study_update_video_progress`, `study_save_video_note`, `study_search_video_transcript`, `study_search_rag` | `StudyReaderView`, `StudyVideoReaderView` | `PyMuPDF`, `pdfplumber`, `ffmpeg`, `faster_whisper`, `youtube-transcript-api` | Leitura paginada, highlights/notas, vídeo aulas + frames + busca lexical | Alta (uso ativo) | **Tauri `Command`**; progresso/notas imediatos em Rust/JSON atómico; extração vídeo/AST/transcrição no **`study_worker`**; corrigir tipos TS para `study_update_video_progress` e `study_save_video_note` |
| **Síntese IA, Q&A & Documentos Gerados** (18) | `study_generate_summary`, `study_synthesize_documents`, `study_ask_course`, `study_ask_paper`, `study_ask_video`, `study_contextual_assist`, `study_explain_video_moment`, `study_explain_video_visual`, `study_get_course_details`, `study_generate_academic_reasoning`, `study_get_academic_reasoning`, `study_generate_editorial_plan`, `study_get_editorial_plan`, `study_generate_study_document`, `study_get_generated_document_status`, `study_get_generated_document_file`, `study_cancel_generation`, `study_cancel_operation`, `study_get_operation_status` | `StudySummaryView`, `StudyAssistantPanel`, `StudyGeneration` | `StudyService` + `Ollama` + `PDFDocumentComposer` (`PyMuPDF`) / `python-docx` / Word COM | Dossiers académicos, planos editoriais, síntese e geração PDF/DOCX com cancelamento | Média (operações longas) | **Tauri `Command`** + **`Channel<GenerationProgress>`** + `CancellationToken` em Rust; inferência via **`OllamaGateway`** e composição binária PDF/DOCX no **`study_worker`** |
| **Modos de Estudo & Exportação** (37) | `study_generate_cornell`, `study_generate_quiz`, `study_submit_quiz`, `study_list_flashcards`, `study_review_flashcard`, `study_save_to_knowledge`, `study_save_to_vault`, `study_mode_start_session`, `study_mode_pause_session`, `study_mode_resume_session`, `study_mode_complete_session`, `study_mode_update_session`, `study_mode_list_sessions`, `study_mode_get_progress`, `study_mode_get_readiness`, `study_mode_get_daily_queue`, `study_mode_generate_flashcards`, `study_mode_get_flashcards`, `study_mode_create_flashcard`, `study_mode_edit_flashcard`, `study_mode_delete_flashcard`, `study_mode_review_flashcard`, `study_mode_regenerate_flashcard`, `study_mode_generate_cornell`, `study_mode_get_cornell`, `study_mode_add_cornell_note`, `study_mode_edit_cornell_entry`, `study_mode_export_cornell_vault`, `study_mode_generate_assessment`, `study_mode_get_assessments`, `study_mode_submit_assessment`, `study_mode_check_question`, `study_mode_generate_active_recall`, `study_mode_get_active_recall`, `study_mode_submit_active_recall` | `StudyModes` (Flashcards, Cornell, Quiz, Active Recall) | `StudyModeEngine` + `ObsidianVault` + `Ollama` | Sessões adaptativas, repetição espaçada (SRS), avaliações, Cornell e exportação Obsidian | Média | **Tauri `Command`**; estado SRS e sessões em **Rust SQLite WAL**; geração de questões/cartões via **`OllamaGateway`**; exportação para Vault via **`knowledge_worker`** |
| **Palestras / Gravação de Aulas (`lectures`)** (6) | `start_lecture_recording`, `stop_lecture_recording`, `get_lecture_status`, `list_lecture_history`, `generate_lecture_lesson`, `submit_lecture_quiz` | `LecturesView` | `sounddevice`, `webrtcvad`, `faster_whisper`, `Ollama` | Gravação microfone de aulas, níveis áudio live, transcrição e geração de lição | Baixa (sessão longa) | **Tauri `Command`** → **`voice_swarm_worker`** + **`Channel<LectureAudioLevel>`** + **`Event` `lecture_session_update`** |

#### G. Missões, Swarm & Autonomia (`missions`: 129 registadas no schema; 33 sem handler em `handle()`)
| Subgrupo | Exemplos Confirmados (`CLIENT_MESSAGE_TYPES`) | Destino Atual | Utilização | Estado Real no Código [Confirmado] | Substituição Proposta |
|---|---|---|---|---|---|
| **Ciclo Base & Work Packages** (14) | `mission_create`, `mission_list`, `mission_get`, `mission_update`, `mission_delete`, `mission_set_status`, `mission_execute_work_package`, `mission_apply_execution`, `mission_cancel_execution`, `mission_retry_execution`, `mission_review_execution`, `work_package_create`, `work_package_update`, `work_package_set_status`, `work_package_add_dependency` | `agents/mission_*.py`, `workspace/.jarvis/projects/*/missions/*/state.db` | CRUD, dependências e execução de missões | Ativo | **Tauri `Command`** (Rust `MissionCoordinator` sobre SQLite WAL `state.db`; execução de código/agentes delegada ao runtime adequado) |
| **Controlo, Checkpoints, Timeline & Swarm** (24) | `mission_control_command`, `mission_control_get`, `mission_control_event_stream`, `mission_checkpoint_create`, `mission_checkpoint_restore`, `mission_resume_snapshot`, `mission_timeline_get`, `mission_autonomy_run`, `mission_loop_run`, `mission_loop_step`, `mission_loop_status`, `mission_loop_respond_human`, `mission_swarm_status`, `mission_swarm_reassign`, `mission_plan_decompose`, `mission_plan_evaluate`, `mission_predict_impact`, `mission_get_predictions`, `mission_intent_preview`, `mission_intent_change`, `mission_understanding_get`, `mission_understanding_review`, `mission_subdag_propose`, `mission_subdag_get_history`, `mission_release_stale_lock`, `mission_adaptation_propose`, `mission_adaptation_get_history` | `mission_orchestrator.py`, `swarm_coordinator.py`, `dynamic_subdag.py`, `file_lease_manager.py` | Orquestração CrewAI/Swarm, sub-DAGs, leases, HITL loop | Ativo (parcialmente acoplado a CrewAI) | **Tauri `Command` + `Channel<MissionEvent>`**; leases/checkpoints/timeline em **Rust Core**, CrewAI mantido inicialmente em `voice_swarm_worker` até reavaliação (Stage 7/8) |
| **Governança, Contratos, Confiabilidade, Produção & Long-Horizon** (~91) | Prefixos `mission_contract_*` (8), `mission_debt_remediation_*` (7), `mission_quality_governance_*` (7), `mission_release_readiness_*` (6), `mission_reliability_*` (7), `mission_production_operations_*` (7), `mission_long_horizon_*` (8), `mission_federation_*` (4), `mission_multi_agent_*` (4), `mission_polymorphic_*` (3), `mission_self_modification_*` (3), `mission_architecture_evolution_*` (3), `mission_behavioral_*` (3), `mission_build_contract_*` (2), `mission_experience_*` (2), `mission_collaboration_*` (2), `mission_policy_*` (2), `mission_decision_quality_status`, `mission_semantic_graph_status`, `mission_dynamic_consumer_resolution` | `backend/websocket/handlers/missions.py` (`MISSION_HANDLERS`) | Subsistema avançado/experimental de governança e simulação de missões | **33 chaves em `MISSION_HANDLERS` são no-op em `handle()`; 14 ramos em `missions.py` são código morto** | **Auditoria e poda obrigatória na Stage 2/7**: consolidar num único `Command` `mission_governance_dispatch(op, payload)` apenas as operações com consumidor real na UI; remover os 14 ramos mortos e implementar/excluir os 33 handlers órfãos |

---

## 4. Eventos Servidor → Cliente (272 Declarados + ~39 Emitidos Não-Listados)

| Categoria de Evento | Origem Atual | Exemplos Confirmados | Frequência | Substituição Proposta (Tauri 2) |
|---|---|---|---|---|
| **Estado Global & UI** | `server.py` / `InitialSyncHandler` | `state`, `chat`, `complete`, `system`, `ui`, `ui_action`, `ui_theme`, `template_changed`, `kanban`, `file`, `planner_state` (+ `error`, `safety_refusal`) | Alta / Média | **Tauri `Event`** (`app.emit("jarvis://...")`) + **`Channel<ChatToken>`** para respostas em streaming; `complete` passa a ser a resolução da Promise/fim do `Channel` |
| **Projetos & Execução** | `sandbox.py` / `project_builder.py` / IDE | `projects_list`, `project_status`, `project_output`, `project_context`, `project_references`, `project_file_save_result`, `project_deleted`, `project_delete_error`, `project_file_deleted`, `project_file_delete_error`, `sandbox_status`, `ast_state`, `coding_session` (+ `coding_session_error`, `project_intake_status`), `semantic_results`, `improvement_batch_result` | Alta (`project_output`) / Média | `project_output` em **`Channel<OutputLine>`**; estados discretos em retorno de **`Command`** ou **`Event`**; unificar tipos de erro no `JarvisError` do `invoke` |
| **Estudos & Aulas** | `StudyService` / `Lectures` | `study_documents_list`, `study_document_ready`, `study_document_processing`, `study_document_failed`, `study_generated_document_progress`, `study_academic_reasoning_progress`, `study_editorial_plan_progress`, `study_mode_progress_event`, `study_navigate`, `study_error`, `lecture_audio_level`, `lecture_session_update` (+ `study_document_deleted`, `lecture_error`) | Média / Alta (`*_progress`, `lecture_audio_level`) | Eventos `*_progress` e `lecture_audio_level` → **`Channel<T>`**; notificações assíncronas (`study_document_ready/failed/deleted`, `lecture_session_update`) → **Tauri `Event`** |
| **Permissões & Sentinel** | `PermissionGatewayService` / `Sentinel` | `action_confirm_request`, `permission_request_created`, `permission_request_approved`, `permission_request_denied`, `permission_request_expired`, `permission_pending_list`, `permission_capability_result`, `permission_execution_result`, `sentinel_status`, `sentinel_event`, `sentinel_action_proposed`, `sentinel_action_result`, `sentinel_audit_completed` (+ `sentinel_review_result`, `sentinel_shadow_telemetry`) | Média / Periódica (60s) | **Tauri `Event`** em **Rust Core** para pushes imediatos (modal HITL, alerta Sentinel); respostas síncronas devolvidas diretamente pelos `Command` |
| **Conhecimento Obsidian** | `KnowledgeWebSocketHandler` | `notes_list`, `note_content`, `note_saved` *(sem handler em `WebSocketContext`)*, `note_quality_audit`, `note_enrichment_result`, `note_rollback_result`, `vault_diagnostics`, `rules_list`, `rules_updated`, `architecture_list`, `architecture_updated`, `decisions_list`, `decisions_updated` (+ `architecture_snapshot`) | Baixa/Média | Devolvidos diretamente como resposta dos **`Command`** respetivos + **`Event` `vault_updated`** apenas quando houver alteração externa/assíncrona |
| **Missões Ativas** | `missions.py` / `mission_orchestrator.py` | `mission_list`, `mission_snapshot`, `mission_event`, `mission_deleted`, `mission_plan_status`, `mission_subdag_*`, `mission_*_result`, `mission_*_response` (+ `IMPACT_*` não listados) | Média | `mission_event` → **`Channel<MissionEvent>`** ou **`Event` scoped**; retornos `*_result`/`*_response` → resposta direta do **`Command`** |
| **Telemetria Distribuída Não Utilizada (~58)** | `websocket_schema.py` | `quic_path_migrated`, `shared_memory_*`, `ipc_*`, `io_backend_*`, `io_worker_*`, `cross_node_dependency`, `cross_swarm_conflict`, `node_*`, `partition_*`, `stream_*`, `subswarm_*`, `worker_*`, `adaptive_scaling`, `control_plane_latency`, `flow_control_backpressure`, `network_*`, `lease_fenced` | **Zero em runtime** [Confirmado] | **NÃO migrar** na transição base; arquivar para eventual telemetria futura apenas se uma arquitetura multi-nó vier a existir |

---

## 5. Resumo Quantitativo da Simplificação IPC [Recomendação]

| Métrica | Arquitetura Atual (Electron + Python WS/HTTP) | Arquitetura Alvo (Tauri 2 + Rust + Workers) |
|---|---|---|
| **Canais de entrada Frontend ↔ Backend** | 3 caminhos sobrepostos (`ws://:8001`, `http://:8000`, `window.jarvisIPC`) | **1 barramento unificado** (`@tauri-apps/api` `invoke`/`listen`/`Channel` + Loopback HTTP `127.0.0.1:0`) |
| **Portas TCP locais abertas pela App** | 3 (`:8000` HTTP, `:8001` WS, `:8080` Sandbox em `0.0.0.0`) | **0 portas fixas obrigatórias** em produção (`127.0.0.1:0` apenas quando preview IDE ativo) |
| **Correlação manual de timeouts no React** | Ad-hoc (`6s` notas, `4s–900s` estudos, dedup `1500ms` IPC) | **Nativa no `invoke()` + `CancellationToken` real por `job_id`** |
| **Superfície de mensagens obsoletas a podar** | 33 handlers sem ramo + 14 ramos mortos + ~58 eventos fantasma | **0** (contrato único validado em compilação Rust + TS) |

