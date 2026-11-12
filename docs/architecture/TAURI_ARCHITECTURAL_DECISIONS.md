# JARVIS OS — FORMAL ARCHITECTURAL DECISION RECORDS (STAGE 0.3)
**Document Version:** 1.1.0  
**Status:** Architectural Consistency & Final Baseline Sign-Off  
**Target Milestone:** Stage 0.3 Final Baseline & Stage 1 Readiness Authorization  
**Baseline Commit:** `fb1aeeda10652ed1662e7e5c24ed381d7635f8d0`

---

## QUESTION 1: Database Migration Timing (`database.db`)
*Deve a base de dados principal (`database.db`) ser migrada para Rust imediatamente (no início da migração) ou numa fase posterior (após estabilizar o transport layer)?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 1 (Hardening em Python) & Etapa 4 (Transferência de titularidade de escrita para Rust Core).
* **Evidência técnica:**
  - A auditoria empírica comprovou que a `database.db` atual opera em modo `DELETE` com `foreign_keys=0` e zero índices secundários personalizados. O serviço `rho.py` executa scans integrais na tabela `model_trajectories` (`1.954` linhas a crescer rapidamente).
  - A base localiza-se fisicamente na raiz do repositório (`PROJECT_ROOT / "database.db"`, `724.992 bytes`, 10 tabelas), e não em `data/database.db`.
  - Migrar o acesso a dados para Rust na Etapa 1 obrigaria a reescrever em simultâneo dezenas de handlers Python que executam queries SQL síncronas antes de existir um canal IPC estável, multiplicando os pontos de falha.
  - O hardening imediato em Python no início da Etapa 1 ativa `PRAGMA journal_mode=WAL`, `busy_timeout=10000`, `synchronous=NORMAL`, `foreign_keys=ON` e índice em `model_trajectories(task_profile, failure_reason, created_at)`.
  - **Realidade Técnica do Concurrency do SQLite WAL:** O modo WAL permite múltiplos leitores concorrentes em simultâneo com um escritor ativo sem bloqueio mútuo. Contudo, o SQLite **mantém estritamente um único escritor simultâneo**. O erro `SQLITE_BUSY` pode ainda ocorrer se uma transação de escrita retiver o bloqueio por tempo superior ao `busy_timeout` (10.000 ms), durante operações exclusivas de DDL ou durante checkpoints forçados (`PRAGMA wal_checkpoint`).
* **Alternativas consideradas:**
  - *Migração Imediata na Etapa 1 para Rust (Rejeitada):* Bloquearia o desenvolvimento do frontend e do Tauri até que todas as queries em Python fossem convertidas em chamadas RPC para Rust. Alto risco de paralisia e regressão nos 3.380 testes `pytest`.
  - *Acesso Concorrente Não Coordenado Rust + Python (Rejeitado):* Riscos severos de bloqueios concorrentes de ficheiro sob Windows NTFS.
* **Riscos e mitigação:**
  - *Risco:* Scripts legados abrirem conexões `sqlite3.connect` sem `timeout` ou sem pragmas de WAL.
  - *Mitigação:* Helper centralizado `get_db_connection()` em Python com pragmas estritos e `busy_timeout=10000`, assegurando transições imediatas (`BEGIN IMMEDIATE`).
* **Critérios de aceitação:**
  1. Suíte de testes de concorrência SQLite com 10 leitores paralelos e 1 escritor de alta frequência sem lançar `sqlite3.OperationalError: database is locked`.
  2. Teste de transação longa (escrita a segurar lock por 6.000 ms) comprovando que leitores continuam a ler sem bloqueio e escritores concorrentes enfileiram até ao limite do `busy_timeout`.
  3. Teste de interrupção forçada / crash durante escrita demonstrando recuperação automática do log WAL e `PRAGMA integrity_check` a retornar `ok`.
* **Necessidade de aprovação do utilizador:** Não (Decisão técnica de sequenciação interna).

---

## QUESTION 2: Ownership of `state.db`
*Deve a base de dados `state.db` continuar a pertencer ao Python ou passar para Rust?*

* **Estado:** Validada.
* **Etapa de implementação:** Permanente em Python (Mission State Worker); separação de `rho.db` testada em sandbox na Etapa 1 e migrada sob portão dedicado na Etapa 4.
* **Evidência técnica:**
  - A análise de ficheiro revelou que os ficheiros `state.db` das missões (`workspace/.jarvis/projects/*/missions/*/state.db`) já operam em modo `WAL`, possuem 12 tabelas bem estruturadas e 7 índices B-Tree funcionais (`idx_wp_status`, `idx_wp_priority`, etc.).
  - São acedidos intensivamente por subsistemas de execução de agentes (`SQLiteMissionPersistence`, `MissionStateManager`) que residem e continuarão em Python. Transferir `state.db` para Rust exigiria que cada micro-passo de planeamento fizesse ida e volta por IPC stdio, degradando a performance sem ganho para a UI.
  - A base de dados `rho.db` (dados de telemetria RHO) pertence ao `ModelHarness` / Python. Na Etapa 1, a sua migração é preparada e testada exclusivamente sobre cópias temporárias (verificando `1.954` trajetórias e `430` regras); a transição de produção só ocorre com aprovação formal na Etapa 4.
* **Alternativas consideradas:**
  - *Passagem de `state.db` para Rust Core (Rejeitada):* Inútil saturação do canal IPC com eventos de telemetria de subagentes e micro-estados de execução que o frontend não renderiza.
* **Riscos e mitigação:**
  - *Risco:* Concorrência entre múltiplos workers Python ao aceder a ficheiros de missão.
  - *Mitigação:* Python controla a escrita através de SQLite WAL com `busy_timeout=30000` e cada missão possui a sua própria diretoria e `state.db` isolado.
* **Critérios de aceitação:**
  1. `MissionStateManager` executa ciclos de checkpoint sem deadlocks e sem dependência de processos externos.
  2. Scripts de teste validam que o Rust Core nunca acede diretamente ao ficheiro `state.db`, interagindo apenas através de mensagens tipadas JSON-RPC.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 3: Ollama Client Implementation (Rust vs Python)
*Deve o cliente Ollama ser reescrito em Rust ou deve permanecer em Python?*

* **Estado:** Validada.
* **Etapa de implementação:** Permanente em Python (`ModelExecutionService` / `ModelHarness`); Etapa 1 corrige desvio direto em `obsidian_graph_engine.py:1495`.
* **Evidência técnica:**
  - A auditoria ao `backend/model_harness/` revelou 12 subsistemas vitais acoplados: injeção dinâmica de regras SHE/RHO, fallback determinístico para sintaxe Qwen, semáforo de alocação de VRAM GPU (`gpu_semaphore`), verificação de integridade de contexto, quantização e gestão de ciclo de vida do daemon.
  - O overhead de rede HTTP em localhost entre Python e Ollama é de apenas **0.8 a 1.2 ms**, enquanto o tempo de inferência do modelo varia entre **5.000 e 15.000 ms**. Reescrever o cliente em Rust pouparia zero tempo percetível e destruiria 12 subsistemas de auto-cura cognitiva afinados.
  - Em `obsidian_graph_engine.py:1495`, foi identificada uma violação arquitetural (chamada direta a `localhost:11434`), provocando a falha em `tests/test_model_transport_architecture.py`. A correção na Etapa 1 redireciona esta chamada para passar pelo `ModelExecutionService`.
* **Alternativas consideradas:**
  - *Reescrita Integral do Cliente Ollama em Rust (Rejeitada):* Erro clássico de otimização prematura. Perder-se-ia a auto-recuperação do harness em troca de ganho nulo de latência.
* **Riscos e mitigação:**
  - *Risco:* UI querer streaming de alta frequência (>100 tokens/s) com sobrecarga de IPC.
  - *Mitigação:* O Python Worker agrupa micro-chunks em janelas de 16 ms (60 fps) antes de enviar por NDJSON, e o Rust Core despacha zero-copy para o WebView2 via `app.emit`.
* **Critérios de aceitação:**
  1. `pytest tests/test_model_transport_architecture.py` 100% verde após correção de `obsidian_graph_engine.py:1495`.
  2. Latência de streaming de tokens mantida abaixo de 30 ms no rendering do frontend.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 4: Frontend Transport Refactoring Timing
*A camada de transporte do frontend (`WebSocketContext.tsx`) deve ser refatorada ANTES da introdução do Tauri ou EM PARALELO com o Tauri?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 1 (Estritamente antes de introduzir Tauri/Rust).
* **Evidência técnica:**
  - `WebSocketContext.tsx` possui 4.302 linhas de código monolítico e está acoplado a 101 tipos de mensagens do cliente e 144 mensagens do servidor. Se tentarmos introduzir o Tauri em paralelo, qualquer regressão na UI será indistinguível de um bug no runtime Tauri/WebView2.
  - Ao criar a interface agnóstica `JarvisTransport` na Etapa 1 e implementar o `WebSocketTransportAdapter`, garantimos que o frontend roda e valida 100% dos testes E2E Playwright contra o backend existente em Electron/WebSocket.
  - Na Etapa 2, basta plugar o `TauriTransportAdapter` mantendo as views React (`WorkspaceViewer`, `StudyVideoReaderView`, etc.) intocadas.
* **Alternativas consideradas:**
  - *Refatoração em Paralelo com Tauri (Rejeitada):* Gera dependência circular, impede testes de regressão isolados e duplica o tempo de debugging.
* **Riscos e mitigação:**
  - *Risco:* Acoplamento residual em componentes legados (e.g. `StudyVideoReaderView.tsx` que importa `useWebSocket`).
  - *Mitigação:* A Etapa 1 inclui um lint/grep gate que proíbe qualquer import direto de `WebSocketContext` fora do diretório `transport/`.
* **Critérios de aceitação:**
  1. `JarvisTransport` cobre todos os métodos de transporte (`invoke`, `subscribe`, `openStream`, `system`).
  2. 100% dos 22 testes Playwright passam sem alteração de comportamento utilizando o `WebSocketTransportAdapter`.
  3. Grep de verificação confirma zero imports diretos de `WebSocketContext` nos componentes de features.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 5: Rust <-> Python Inter-Process Protocol
*O protocolo Rust <-> Python deve usar JSON-RPC sobre stdio, gRPC, WebSockets locais ou named pipes?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 4 (Implementação no Host Controller & Workers).
* **Evidência técnica:**
  - Stdio pipes não utilizam portas de rede TCP, eliminando conflitos de firewall do Windows, verificações de portas ocupadas (`_free_port_if_locked`), e riscos de SSRF/CORS.
  - O ciclo de vida é atado diretamente ao processo-pai via Windows Job Object (`KILL_ON_JOB_CLOSE`), impedindo processos órfãos.
  - A especificação detalhada em `TAURI_WORKER_PROTOCOL.md` resolve os problemas de buffer, isolando `sys.stdout` de bibliotecas de terceiros via `os.dup(1)` e `sys.stdout = sys.stderr`.
  - Suporta framing assíncrono bidirecional com Reverse RPC para solicitações Human-In-The-Loop (HITL).
* **Alternativas consideradas:**
  - *WebSockets Locais em Porta TCP (Rejeitado):* Mantém a fragilidade de colisão de portas (`:8001`), exposição local na interface de rede e dependência do `websockets==16.0`.
  - *gRPC / Protobuf (Rejeitado):* Overhead pesado de compilação de toolchain `protoc`, complexidade desnecessária para dados orientados a JSON, e fraca introspeção durante debugging.
* **Riscos e mitigação:**
  - *Risco:* Corrupção de stdio por chamadas a `print()` em bibliotecas C/Python (`PyMuPDF`, `onnxruntime`).
  - *Mitigação:* Duplicação imediata do descritor de ficheiro 1 no bootstrap do worker e redirecionamento de `sys.stdout` para `sys.stderr`.
* **Critérios de aceitação:**
  1. Handshake `worker.init` completa em menos de 500 ms com troca de capacidades.
  2. Heartbeats a cada 5s com deteção de timeout a 15s e recuperação automática de processo.
  3. Envio de `reverse_request` HITL a partir do worker sem bloqueio do event loop assíncrono.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 6: Serving Static Files, Sandbox Preview & Media
*Os endpoints HTTP de ficheiros estáticos (sandbox de preview em `localhost:8080` e media de estudos) devem ser servidos por Rust ou continuar em Python? Como estruturar a autenticação e isolamento?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 3 (Servidor Loopback Rust) & Etapa 6 (Hardening de Segurança).
* **Evidência técnica:**
  - O atual `sandbox.py` em Python vincula-se a `0.0.0.0:8080`, criando uma vulnerabilidade severa de rede local.
  - O protocolo customizado do Tauri (`tauri-media://`) apresenta problemas conhecidos no WebView2 com seeking/scrubbing de ficheiros MP4 e isolamento de Web Workers em `pdfjs-dist` (`pdf.worker.min.mjs`).
  - Um servidor HTTP assíncrono interno em Rust (`warp` ou `axum`) em `127.0.0.1:0` (porta efémera vinculada ao localhost) suporta nativamente Range 206 para vídeo e PDF, descarrega a carga de I/O do Python e isola os acessos via Path Jail.
  - **Comparação Formal: Bearer Tokens vs Cookies HttpOnly:**
    - *Bearer Tokens:* Ideais para requisições programáticas via `fetch()` e IPC. Contudo, elementos nativos HTML (`<video src="...">`, `<img src="...">`) **não conseguem enviar cabeçalhos HTTP customizados** (`Authorization: Bearer`) sem recorrer a `fetch()` + `URL.createObjectURL(blob)`, o que degrada gravemente a performance em ficheiros de vídeo de 500MB+ e destrói o streaming nativo de Range 206.
    - *Cookies HttpOnly:* São enviados automaticamente pelas tags nativas, mas requisições cross-origin entre a origem do WebView2 (`tauri://localhost` ou `https://tauri.localhost`) e o loopback HTTP (`http://127.0.0.1:<port>`) **não enviam cookies configurados com `SameSite=Strict`**. Além disso, o suporte a cookies em WebView2 com esquemas customizados requer gestão de perfil adicional.
  - **Arquitetura de Autenticação Híbrida de Dois Canais Escolhida:**
    1. *Canal API / Dados (IPC & Fetch):* Cabeçalho padrão `Authorization: Bearer <session_token>`.
    2. *Canal de Streaming de Media (Tags HTML):* Tickets efémeros de uso temporário passados por query param (`/media/study/{doc_id}/video?ticket=<ephemeral_ticket>`). O ticket é de curta duração (60 segundos para handshake inicial do stream), gerado pelo Rust Core mediante pedido autenticado via IPC da UI e criptograficamente vinculado ao `doc_id` e à sessão do utilizador.
    3. *Validação Estrita de Host & Origin:* O servidor Rust valida obrigatoriamente que o cabeçalho `Host` corresponde exatamente a `127.0.0.1:{bound_port}` (bloqueando ataques de DNS Rebinding) e que o cabeçalho `Origin` corresponde a `tauri://localhost` (ou está ausente em tags de media isoladas).
    4. *Sandbox de Preview do IDE:* Projetos web gerados pelo utilizador são servidos em porta loopback dedicada e embutidos em iframe isolado com política restrita: `<iframe sandbox="allow-scripts allow-forms">` (omite estritamente `allow-same-origin`), impedindo que scripts executados na preview acedam ao storage, aos tokens da aplicação ou à API IPC do Tauri.
* **Alternativas consideradas:**
  - *Manter Servidor HTTP em Python (Rejeitado):* Obriga o worker Python a lidar com I/O de streaming enquanto executa OCR e inferência de modelos.
  - *Apenas Cookies HttpOnly (Rejeitado):* Falha na comunicação cross-origin `tauri://localhost` para `127.0.0.1` com `SameSite=Strict`.
* **Riscos e mitigação:**
  - *Risco:* Ataque de CSRF ou DNS Rebinding a partir de uma aba do navegador do utilizador acedendo à porta do loopback.
  - *Mitigação:* Vinculação estrita a `127.0.0.1:0` (porta efémera aleatória por sessão), validação do cabeçalho `Host` contra a porta alocada, e validação de tokens e tickets efémeros em cada pedido.
* **Critérios de aceitação:**
  1. Vídeos MP4 com seek instantâneo via Range 206 sem recarregar o ficheiro integral.
  2. PDF.js carrega documentos multi-página via worker sem erros de CORS ou MIME.
  3. Tentativas de acesso sem ticket efémero ou com Path Traversal (`../`) retornam HTTP 401 / HTTP 403.
  4. Script malicioso na preview não consegue comunicar com a API do Tauri nem aceder ao loopback de dados.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 7: Native Frontend Dependencies in Tauri 2 WebView2
*As dependências nativas (Monaco, PDF.js, etc.) funcionam sem alteração no WebView2 do Tauri 2 ou requerem ajustes?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 2 (Bootstrap Tauri) & Etapa 3 (Loopback Media Server).
* **Evidência técnica:**
  - Tanto o Electron quanto o Tauri 2 (no Windows) utilizam a engine Chromium (o WebView2 baseia-se no runtime Evergreen Chromium do Edge). Todas as APIs web padrão (React 19, Framer Motion 12, Canvas 2D de PDF.js, Monaco Editor, CSS Container Queries) são suportadas de forma idêntica.
  - Contudo, **afirmações genéricas de "98% de compatibilidade direta" são rejeitadas**. O comportamento real depende de testes empíricos rigorosos nas fronteiras do sistema operacional.
  - **Matriz de Testes Empíricos de Compatibilidade WebView2:**

| Componente / Dependência | Caso de Teste Específico | Modo de Falha Potencial | Ajuste de Configuração & Mitigação |
|---|---|---|---|
| **Monaco Editor (v0.56.0)** | Inicialização de web workers para TypeScript, CSS, HTML e JSON | Erro de cross-origin worker script (`SecurityError`) ao carregar de esquema customizado | Configurar `MonacoEnvironment.getWorkerUrl` para carregar scripts via blob URL inline ou via loopback local verificado |
| **Monaco Editor (v0.56.0)** | Atalhos de teclado (`Ctrl+C`, `Ctrl+V`, `Ctrl+F`) e clipboard | Interceção indevida pelo WebView2 ou bloqueio de permissão de clipboard | Registar permissões de clipboard no `capabilities/main-window.json` do Tauri |
| **PDF.js (v6.3.0)** | Renderização de Canvas 2D e camada de seleção de texto | Falha de inicialização de `pdf.worker.min.mjs` em esquemas `tauri://` | Fornecer PDFs e worker via Loopback HTTP Rust (`http://127.0.0.1:{port}/media/...`) com `Content-Type: application/javascript` |
| **PDF.js (v6.3.0)** | Ficheiros PDF de grande dimensão (>100 MB) | Esgotamento de memória ou lentidão na renderização | Habilitar stream parcial via Range 206 no servidor Loopback Rust |
| **Web Workers** | Spawning de Workers standard em ESM | Restrições de CSP ou política de ficheiro local | CSP configurada com `script-src 'self' 'wasm-unsafe-eval'` |
| **MP4 Video Seeking** | Scrubbing e saltos temporais em vídeo na visualização de estudos | Reprodução recomeça do início (`0:00`) por ausência de Range 206 | Loopback HTTP Rust com suporte estrito a cabeçalhos `Range: bytes=start-end` e status `206 Partial Content` |
| **Carregamento de Assets** | Imagens e ícones dinâmicos de projetos | Bloqueio por CSP mista (HTTP em contexto seguro) | CSP configurada com `img-src 'self' data: blob: http://127.0.0.1:*` |
| **Permissões de Sistema** | Diálogos de ficheiro e drag-and-drop | Diferença de eventos entre Electron (`webContents`) e Tauri | Utilizar plugins oficiais `tauri-plugin-dialog` e eventos nativos de file drop do Tauri |
| **Comunicação IPC** | Envio de mensagens de alta frequência | Gargalo de serialização ou bloqueio de UI | IPC nativo assíncrono via `invoke()` e canais de streaming `tauri::ipc::Channel` |

* **Alternativas consideradas:**
  - *Substituição do Monaco pelo CodeMirror (Rejeitada):* Inútil e prejudicial; o Monaco é amplamente compatível com WebView2 quando os caminhos de worker são configurados corretamente.
* **Riscos e mitigação:**
  - *Risco:* Incompatibilidade de versão do WebView2 instalada na máquina do utilizador.
  - *Mitigação:* O instalador do Tauri 2 valida e instala automaticamente o Evergreen WebView2 Runtime da Microsoft.
* **Critérios de aceitação:**
  1. Editor Monaco inicializa sem erros na consola relativos a worker scripts.
  2. PDF.js renderiza documentos com texto selecionável e busca funcional.
  3. Reprodução de vídeo MP4 permite scrub suave com resposta inferior a 200 ms.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 8: WebSocket to Tauri Command/Event Migration Strategy
*Qual é a estratégia recomendada para migrar os 101 tipos de mensagens WebSocket para comandos/eventos Tauri?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 2 (Setup básico) & Etapa 5 (Migração integral por domínio).
* **Evidência técnica:**
  - A matriz de comunicação em `TAURI_COMMUNICATION_MATRIX.md` catalogou 101 tipos de mensagens de cliente e 144 mensagens de servidor.
  - A grande maioria (80 mensagens) segue o padrão clássico de Request/Response RPC (e.g. `fs_read_file`, `project_list`, `study_get_document`).
  - As restantes (21 mensagens) correspondem a notificações unidirecionais e streams (e.g. `chat:token`, `study:progress`, `sentinel:alert`).
  - Tratar todas como um barramento único de eventos perpetuaria a falta de tipagem e acoplamento do `WebSocketContext.tsx`.
* **Alternativas consideradas:**
  - *Emular um Servidor WebSocket em Memória em Rust (Rejeitado):* Preserva a má arquitetura atual sem usufruir dos ganhos de segurança, tipagem e performance do IPC do Tauri.
* **Riscos e mitigação:**
  - *Risco:* Inconsistência nos nomes de comandos e tipos durante a migração gradual.
  - *Mitigação:* Mapeamento formal 1:1 definido em `TAURI_COMMUNICATION_MATRIX.md` com geração de interfaces TypeScript a partir das structs Rust.
* **Critérios de aceitação:**
  1. Comandos RPC mapeados para `tauri::command` retornam Promises tipadas.
  2. Streams mapeados para `tauri::event` utilizam canais com tipagem estrita de payloads.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 9: Persistent Data Compatibility Strategy
*Como deve ser tratada a compatibilidade de dados persistidos (`database.db`, `state.db`, ficheiros de estudo, Obsidian vault) durante a transição?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 1 (Hardening & Caminho Canónico) & Etapa 4 (Acesso Rust).
* **Evidência técnica:**
  - A base de dados principal localiza-se fisicamente em `PROJECT_ROOT / "database.db"` (`724.992 bytes`). A auditoria confirmou que **`data/database.db` NÃO existe**.
  - Os ficheiros de estudo residem em `data/study/`, as missões em `workspace/.jarvis/projects/*/missions/` e os vaults em `obsidian_vault/`.
  - Nenhuma etapa de migração pode causar perda de dados, corrupção ou exigir migrações manuais destrutivas.
  - **Procedimento Obrigatório para Qualquer Futura Relocação Física:** Caso se decida no futuro mover `database.db` para `data/database.db` ou `%APPDATA%`, o processo deve obedecer a:
    1. Criação de backup físico completo (`.bak`).
    2. Verificação de integridade prévia (`PRAGMA integrity_check`).
    3. Cópia atómica para o destino.
    4. Validação de checksum SHA256 e contagens de linhas entre origem e destino.
    5. Remoção do ficheiro original apenas após confirmação de sucesso de arranque da nova versão.
    6. Procedimento de rollback imediato em caso de erro.
* **Alternativas consideradas:**
  - *Assumir que `data/database.db` já existe (Rejeitada):* Causaria a criação silenciosa de uma base vazia no arranque.
  - *Migração para uma base de dados externa (Postgres/RocksDB) (Rejeitada):* Incompatível com o ecossistema Python local e ferramentas de análise.
* **Riscos e mitigação:**
  - *Risco:* Abertura concorrente da mesma base por duas instâncias em modos incompatíveis.
  - *Mitigação:* Lock de processo único no arranque da aplicação e verificação estrita de integridade.
* **Critérios de aceitação:**
  1. Caminho canónico ancorado em `PROJECT_ROOT / "database.db"` sem caminhos relativos não resolvidos.
  2. Todos os 1.954 registos de trajetórias e 430 regras rho intactos em todas as etapas.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 10: Code Consolidation in `agents/` and `backend/agents/`
*O código em `agents/` e `backend/agents/` deve ser limpo/consolidado antes da migração ou durante a migração?*

* **Estado:** Validada (Estratégia revista e retificada na Stage 0.3 com preservação do histórico).
* **Etapa de implementação:** Etapa 7 / Iniciativa autónoma de pós-migração (Estritamente pós-transporte).
* **Histórico da Decisão & Retificação na Stage 0.3:**
  - *Decisão Inicial Proposta (Stage 0.1/0.2):* Propunha remover ou arquivar imediatamente na Etapa 1 os 30 subpacotes duplicados em `agents/`, mantendo apenas `backend/agents/`.
  - *Evidência da Auditoria Profunda da Stage 0.2/0.3 (Armadilha de Acoplamento Cruzado):*
    1. A catalogação detalhada demonstrou que existem 30 subpacotes em `backend/agents/` (27 são cópias byte-a-byte de `agents/` com 593 ficheiros, e 3 são shims que importam de `agents/`).
    2. Contudo, 7 subpacotes dentro de `backend/agents/` contêm **367 imports diretos** hardcoded para o namespace `agents.*`.
    3. Em sentido inverso, `agents/long_horizon_missions` contém **81 imports** hardcoded para `backend.agents.*`.
    4. O servidor principal `server.py` importa diretamente de `agents`.
    5. O despachante de missões `missions.py` estabelece pontes dinâmicas para 16 handlers em `backend.agents.*`.
    6. **Conclusão Técnica Incontornável:** Eliminar ou mover qualquer uma das diretorias na Etapa 1 causaria quebras massivas e silenciosas de runtime no Python e nos 3.380 testes de `pytest`.
  - *Decisão Final e Válida (Stage 0.3):* **Preservar integralmente `agents/` e `backend/agents/` durante a Stage 1.** Não eliminar, mover, renomear ou arquivar qualquer módulo de agentes durante a fase de transição de transporte.
  - A consolidação será realizada numa **iniciativa autónoma posterior (Stage 7 ou pós-migração)**, utilizando:
    - Shims dinâmicos de aliasing (`sys.modules["agents"] = sys.modules["backend.agents"]`) não destrutivos.
    - Codemods baseados em árvore sintática abstrata (AST) com verificação de cada referência estática e dinâmica.
    - Suíte completa de testes de regressão de imports antes da remoção física dos ficheiros redundantes.
* **Alternativas consideradas:**
  - *Poda Agressiva na Etapa 1 (Rejeitada):* Inviabiliza a estabilização do transporte ao introduzir centenas de falhas de `ModuleNotFoundError`.
* **Riscos e mitigação:**
  - *Risco:* Desenvolvedor modificar ficheiro em `agents/` julgando estar a alterar `backend/agents/` (ou vice-versa).
  - *Mitigação:* Documentação explícita nos READMEs das pastas e auditoria periódica até à consolidação final.
* **Critérios de aceitação:**
  1. `agents/` e `backend/agents/` permanecem 100% inalterados durante toda a Stage 1.
  2. Todos os testes de importação e execução de missões passam sem alterações de namespaces.
* **Necessidade de aprovação do utilizador:** Não.

---

## QUESTION 11: Decision Criteria for Retiring Electron
*Qual deve ser o critério de decisão para desativar definitivamente o Electron?*

* **Estado:** Validada.
* **Etapa de implementação:** Etapa 7 (Após validação integral dos 7 portões).
* **Evidência técnica:**
  - O Electron funciona como rede de segurança ativa durante todo o processo de migração.
  - A sua desativação precoce retiraria a possibilidade de comparar comportamentos e de recuperar rapidamente em caso de regressão no WebView2.
* **Os 7 Portões de Aceitação Cumulativos:**
  1. 100% dos testes E2E Playwright (`test_redesign_consolidation_e2e.py`) verdes em execução contra a build Tauri 2.
  2. Validação sem regressão das 26 capacidades funcionais da matriz de paridade (`TAURI_FUNCTIONAL_PARITY.md`).
  3. Redução comprovada de RAM > 40% em relação ao baseline Electron.
  4. Cold start até UI interativa < 1.500 ms.
  5. Zero processos órfãos (`python.exe`) após crash simulado ou fecho abrupto da janela.
  6. Suíte de integridade de documentação (`test_documentation_integrity.py`) verde.
  7. **Aprovação explícita e formal do utilizador** após sessão piloto completa.
* **Alternativas consideradas:**
  - *Remoção Antecipada do Electron na Etapa 2 (Rejeitada):* Destrói a referência comparativa e arrisca bloquear o utilizador.
* **Riscos e mitigação:**
  - *Risco:* Manutenção de configurações duplas durante demasiado tempo.
  - *Mitigação:* A Etapa 7 possui um script automatizado de desinstalação de dependências Electron assim que os 7 portões forem aprovados.
* **Critérios de aceitação:**
  1. Cumprimento comprovado e auditado dos 7 portões.
  2. Remoção limpa de `main.js`, `preload.js` e pacotes `electron` do `package.json`.
* **Necessidade de aprovação do utilizador:** **SIM (Obrigatória na Etapa 7 para remoção final)**.

---

## QUESTION 12: Realistic Effort Estimation & Dependencies
*Qual é a estimativa realista de esforço por etapa, considerando os riscos e dependências identificados nesta validação?*

* **Estado:** Validada.
* **Etapa de implementação:** Planeamento transversal (Stages 0 a 8).
* **Evidência técnica:**
  - A auditoria da Stage 0.2/0.3 refinou o escopo de cada etapa, eliminando sobreposições e falsas suposições.
  - **O escopo da Stage 1 é estritamente limitado aos 6 incrementos seguros:**
    1. Interface `JarvisTransport` e `WebSocketTransportAdapter`.
    2. Testes de compatibilidade do transporte.
    3. Correções dos contratos e tipagem do protocolo.
    4. Hardening SQLite em Python (`WAL`, `busy_timeout=10000`, `synchronous=NORMAL`, `foreign_keys=ON`, caminho canónico).
    5. Preparação e teste isolado da migração RHO, sem escrita em produção.
    6. Correção da violação de arquitetura Ollama no Obsidian Graph Engine (`obsidian_graph_engine.py:1495`).
  - **Excluídos explicitamente da Stage 1:** Bootstrap de `src-tauri/` (Etapa 2), migração efetiva em produção de `rho.db` (Etapa 4), eliminação de módulos duplicados (Etapa 7), transferência de titularidade SQLite para Rust (Etapa 4), remoção do Electron (Etapa 7), implementação do Workflow Engine (fora de escopo).

| Etapa | Designação | Esforço Estimado | Dependências Críticas | Nível de Risco |
|---|---|---|---|---|
| **Etapa 0.3** | **Consistência Arquitetural & Baseline Final** | Concluída (Fase Atual) | Reconciliação documental e eliminação de contradições | Baixo |
| **Etapa 1** | **Preparação do Frontend & Hardening do Python** | 3 – 4 dias de desenvolvimento | Criação do `JarvisTransport`, testes Playwright, WAL em SQLite, teste sandbox RHO, fix Ollama | Baixo |
| **Etapa 2** | **Bootstrap do Tauri 2 & Shell Desktop** | 3 – 4 dias de desenvolvimento | Setup `src-tauri/`, Tauri IPC adapter no frontend, verificação WebView2 | Médio |
| **Etapa 3** | **Servidor HTTP Loopback Rust & Media/Filesystem** | 3 – 4 dias de desenvolvimento | Servidor Rust `127.0.0.1:0` Range 206, Path Jail, Monaco e PDF.js, tickets efémeros | Baixo |
| **Etapa 4** | **Host Controller de Workers & IPC Bidirecional** | 5 – 7 dias de desenvolvimento | Implementação do protocolo `TAURI_WORKER_PROTOCOL.md`, Job Objects, Reverse RPC HITL, Rust escritor `database.db` | Alto |
| **Etapa 5** | **Migração de Domínios (Estudos, Missões, Obsidian, Sentinel)** | 6 – 8 dias de desenvolvimento | Conexão dos workers especializados, resolução dos 33 handlers de missões | Médio / Alto |
| **Etapa 6** | **Segurança, Hardening e Eliminação de Vulnerabilidades** | 3 – 4 dias de desenvolvimento | Correção da injeção de scriptblock PowerShell, regras de Path Jail, bypass de SSRF | Médio |
| **Etapa 7** | **Testes E2E, Validação de Paridade, Poda de Duplicados e Desativação do Electron** | 4 – 5 dias de desenvolvimento | Execução dos 7 portões de aceitação, consolidação de `agents/`, aprovação formal do utilizador | Médio |
| **Etapa 8** | **Otimização Final, Telemetria e Empacotamento de Produção** | 3 – 4 dias de desenvolvimento | Assinatura de código, empacotador NSIS/MSI, profiling de memória | Baixo |

* **Total Estimado:** **30 a 40 dias de desenvolvimento contínuo**, garantindo risco zero de quebra em produção através de migração estritamente faseada.
* **Alternativas consideradas:**
  - *Compressão de Etapas (Rejeitada):* Juntar bootstrap do Tauri e refatoração do transporte no mesmo passo aumentaria exponencialmente a complexidade do debugging.
* **Riscos e mitigação:**
  - *Risco:* Bloqueios imprevistos no ecossistema Rust no Windows.
  - *Mitigação:* O Electron continua como ambiente de desenvolvimento paralelo funcional até à aprovação da Etapa 7.
* **Critérios de aceitação:**
  1. Cronograma respeitado sem regressão nos 3.380 testes de `pytest` e nos 22 testes Playwright.
  2. Aprovação explícita do utilizador em cada marco de aprovação.
* **Necessidade de aprovação do utilizador:** **SIM (Para autorizar o início da Etapa 1)**.
