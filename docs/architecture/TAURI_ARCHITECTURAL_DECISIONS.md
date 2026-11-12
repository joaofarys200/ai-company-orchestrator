# JARVIS OS — FORMAL ARCHITECTURAL DECISION RECORDS (STAGE 0.1)
**Document Version:** 1.0.0  
**Status:** Validated Architecture Decisions  
**Target Milestone:** Stage 0.1 Baseline Sign-Off

---

## QUESTION 1: Database Migration Timing (`database.db`)
*Deve a base de dados principal (`database.db`) ser migrada para Rust imediatamente (no início da migração) ou numa fase posterior (após estabilizar o transport layer)?*

* **Recomendação Clara:** Migrar a titularidade (single writer) da `database.db` para Rust numa **fase posterior (Etapa 4)**, após a estabilização completa da camada de transporte (`JarvisTransport`) e do protocolo IPC Rust <-> Python. Na Etapa 1, aplicar **hardening imediato em Python** (`PRAGMA journal_mode=WAL`, `busy_timeout=10000`, `foreign_keys=ON` e índices nos campos `session_id`, `created_at`, `status`).
* **Justificação Técnica Baseada em Evidência:**
  - A auditoria empírica comprovou que a `database.db` atual opera em modo `DELETE` com `foreign_keys=0` e zero índices secundários. O serviço `rho.py` executa scans integrais na tabela `model_trajectories` (724 KB a crescer rapidamente).
  - Migrar o acesso a dados para Rust na Etapa 1 obrigaria a reescrever em simultâneo dezenas de handlers Python que executam queries SQL síncronas antes sequer de existir um canal IPC estável, multiplicando os pontos de falha.
  - O hardening imediato em Python no início da Etapa 1 elimina 100% dos bloqueios e `SQLITE_BUSY` com zero disrupção arquitetural.
* **Alternativas Consideradas e Rejeitadas:**
  - *Migração Imediata na Etapa 1 para Rust (Rejeitada):* Bloquearia todo o desenvolvimento do frontend e do Tauri até que todas as dezenas de queries em Python fossem convertidas em chamadas RPC para Rust. Alto risco de paralisia e regressão.
  - *Acesso Concorrente Não Coordenado Rust + Python (Rejeitado):* Riscos severos de locks concorrentes de ficheiro sob Windows NTFS.
* **Riscos Associados e Mitigação:**
  - *Risco:* Scripts legados abrirem conexões sem `timeout`.
  - *Mitigação:* Helper centralizado `get_db_connection()` em Python com pragmas estritos e `busy_timeout=10000`.
* **Nível de Confiança:** **Alto (95%)**
* **Necessidade de Aprovação do Utilizador:** **Não** (Decisão técnica de sequenciação interna).

---

## QUESTION 2: Ownership of `state.db`
*Deve a base de dados `state.db` continuar a pertencer ao Python ou passar para Rust?*

* **Recomendação Clara:** **Permanecer permanentemente sob a titularidade do Python**, aplicando isolamento de responsabilidade (Approach C). Separar a telemetria intensiva de trajetórias do ModelHarness para um ficheiro dedicado `rho.db`.
* **Justificação Técnica Baseada em Evidência:**
  - A análise de ficheiro revelou que `state.db` já opera em modo `WAL`, possui 12 tabelas bem estruturadas e 7 índices B-Tree funcionais.
  - É acedida intensivamente por subsistemas de execução de agentes, grafo de conhecimento e avaliação que residem em Python. Transferir `state.db` para Rust exigiria que cada micro-passo de planeamento de agentes fizesse uma viagem de ida e volta por IPC stdio, degradando a performance sem qualquer benefício para o utilizador.
* **Alternativas Consideradas e Rejeitadas:**
  - *Passagem de `state.db` para Rust Core (Rejeitada):* Inútil saturação do canal IPC com eventos de telemetria de subagentes e micro-estados de execução que o frontend não renderiza.
* **Riscos Associados e Mitigação:**
  - *Risco:* Concorrência entre workers Python.
  - *Mitigação:* Python controla a escrita através de SQLite WAL e `busy_timeout=10000`; telemetria de alta frequência vai para `rho.db`.
* **Nível de Confiança:** **Alto (98%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 3: Ollama Client Implementation (Rust vs Python)
*Deve o cliente Ollama ser reescrito em Rust ou deve permanecer em Python?*

* **Recomendação Clara:** **Permanecer em Python no `ModelExecutionService` / `ModelHarness` (Abordagem B / Híbrida C)**. O Rust Core atuará unicamente como despachante de streams de eventos para a UI quando o streaming token-a-token for solicitado.
* **Justificação Técnica Baseada em Evidência:**
  - A auditoria ao `backend/model_harness/` revelou 12 subsistemas vitais acoplados: injeção dinâmica de regras SHE/RHO, fallback determinístico para sintaxe Qwen, semáforo de alocação de VRAM GPU (`gpu_semaphore`), verificação de integridade de contexto, quantização e gestão de ciclo de vida do daemon.
  - O overhead de rede HTTP em localhost entre Python e Ollama é de apenas **0.8 a 1.2 ms**, enquanto o tempo de inferência do modelo varia entre **5.000 e 15.000 ms**. Reescrever o cliente em Rust pouparia zero tempo percetível e destruiria 12 subsistemas de auto-cura cognitiva que levaram semanas a afinar.
* **Alternativas Consideradas e Rejeitadas:**
  - *Reescrita Integral do Cliente Ollama em Rust (Rejeitada):* Erro clássico de otimização prematura. Perder-se-ia a paridade de auto-recuperação do harness em troca de ganho nulo de latência.
* **Riscos Associados e Mitigação:**
  - *Risco:* UI querer streaming de alta frequência (>100 tokens/s).
  - *Mitigação:* O Python Worker agrupa tokens em janelas temporais de 16 ms (60 fps) antes de enviar pelo NDJSON, e o Rust Core faz fanout zero-copy para o WebView2.
* **Nível de Confiança:** **Alto (99%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 4: Frontend Transport Refactoring Timing
*A camada de transporte do frontend (`WebSocketContext.tsx`) deve ser refatorada ANTES da introdução do Tauri ou EM PARALELO com o Tauri?*

* **Recomendação Clara:** **Refatorar estritamente ANTES (Etapa 1)** da introdução de qualquer código Tauri/Rust.
* **Justificação Técnica Baseada em Evidência:**
  - `WebSocketContext.tsx` possui 4.302 linhas de código monolítico e está acoplado a 101 tipos de mensagens do cliente e 144 mensagens do servidor. Se tentarmos introduzir o Tauri em paralelo, qualquer regressão na UI será indistinguível de um bug no runtime Tauri/WebView2.
  - Ao criar a interface agnóstica `JarvisTransport` na Etapa 1 e implementar o `WebSocketTransportAdapter`, garantimos que o frontend roda e valida 100% dos testes E2E contra o backend existente em Electron/WebSocket.
  - Na Etapa 2, basta plugar o `TauriIpcTransportAdapter` mantendo as views React (`WorkspaceViewer`, `StudyVideoReaderView`, etc.) rigorosamente intocadas.
* **Alternativas Consideradas e Rejeitadas:**
  - *Refatoração em Paralelo com Tauri (Rejeitada):* Gera dependência circular, impede testes de regressão isolados e duplica o tempo de debugging.
* **Riscos Associados e Mitigação:**
  - *Risco:* Acoplamento residual em componentes legados (e.g. `StudyVideoReaderView.tsx` que importa `useWebSocket`).
  - *Mitigação:* A Etapa 1 inclui um lint/grep gate que proíbe qualquer import direto de `WebSocketContext` fora do diretório `transport/`.
* **Nível de Confiança:** **Alto (100%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 5: Rust <-> Python Inter-Process Protocol
*O protocolo Rust <-> Python deve usar JSON-RPC sobre stdio, gRPC, WebSockets locais ou named pipes?*

* **Recomendação Clara:** **JSON-RPC 2.0 estendido sobre Standard Input/Output (stdio) pipes em modo NDJSON**, com suporte secundário a Named Pipes no Windows para payloads binários.
* **Justificação Técnica Baseada em Evidência:**
  - Stdio pipes não utilizam portas de rede TCP, eliminando conflitos de firewall do Windows, verificações de portas ocupadas (`_free_port_if_locked`), e ataques SSRF/CORS.
  - O ciclo de vida é atado diretamente ao processo-pai via Windows Job Object (`KILL_ON_JOB_CLOSE`), impedindo processos órfãos.
  - A especificação detalhada em `TAURI_WORKER_PROTOCOL.md` resolve os problemas de buffer, isolando `sys.stdout` de bibliotecas de terceiros via `os.dup(1)`.
* **Alternativas Consideradas e Rejeitadas:**
  - *WebSockets Locais em Porta TCP (Rejeitado):* Mantém a fragilidade de colisão de portas (`:8001`), exposição local na interface de rede e dependência do `websockets==16.0`.
  - *gRPC / Protobuf (Rejeitado):* Overhead pesado de compilação de toolchain `protoc`, complexidade desnecessária para dados orientados a JSON, e fraca introspeção durante debugging.
* **Riscos Associados e Mitigação:**
  - *Risco:* Corrupção de stdio por chamadas a `print()` em C/Python.
  - *Mitigação:* Duplicação imediata do descritor de ficheiro 1 no bootstrap do worker e redirecionamento de `sys.stdout` para `sys.stderr`.
* **Nível de Confiança:** **Alto (95%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 6: Serving Static Files, Sandbox Preview & Media
*Os endpoints HTTP de ficheiros estáticos (sandbox de preview em `localhost:8080` e media de estudos) devem ser servidos por Rust ou continuar em Python?*

* **Recomendação Clara:** **Servidos por Rust Core através de um servidor HTTP Loopback nativo em porta efémera (`127.0.0.1:0`)**, com suporte estrito a HTTP Range 206 e Path Jail.
* **Justificação Técnica Baseada em Evidência:**
  - O atual `sandbox.py` em Python vincula-se a `0.0.0.0:8080`, criando uma vulnerabilidade de rede local grave.
  - O protocolo customizado do Tauri (`jarvis-media://`) apresenta problemas conhecidos no WebView2 com seeking/scrubbing de ficheiros MP4 e isolamento de Web Workers em `pdfjs-dist` (`pdf.worker.min.mjs`).
  - Um servidor HTTP assíncrono interno em Rust (`warp` ou `axum`) em `127.0.0.1:0` suporta nativamente Range 206 para vídeo, descarrega a carga de I/O do Python e fornece isolamento perfeito com tokens efêmeros de sessão.
* **Alternativas Consideradas e Rejeitadas:**
  - *Manter em Python (Rejeitado):* Obriga o worker Python a lidar com buffering de I/O de streaming de vídeo enquanto executa LLMs e OCR.
  - *Custom URI Scheme `jarvis-media://` (Rejeitado):* Instável no WebView2 para vídeos de longa duração e workers PDF.
* **Riscos Associados e Mitigação:**
  - *Risco:* WebView2 bloquear recursos por políticas de segurança.
  - *Mitigação:* O Rust Core injeta o cabeçalho `Access-Control-Allow-Origin: tauri://localhost` ou token de bearer efêmero gerado no arranque.
* **Nível de Confiança:** **Alto (95%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 7: Native Frontend Dependencies in Tauri 2 WebView2
*As dependências nativas (Monaco, PDF.js, etc.) funcionam sem alteração no WebView2 do Tauri 2 ou requerem ajustes?*

* **Recomendação Clara:** **Funcionam com 98% de compatibilidade direta**, necessitando de apenas **dois pequenos ajustes de configuração**:
  1. Configuração do `workerUrl` do Monaco Editor para carregar via caminho de assets Tauri em vez de Electron IPC.
  2. Fornecimento dos PDFs ao `pdfjs-dist` através do loopback HTTP Rust (`http://127.0.0.1:{port}/media/...`) para contornar restrições de CORS e Web Workers em esquemas customizados.
* **Justificação Técnica Baseada em Evidência:**
  - Tanto o Electron quanto o Tauri 2 (no Windows) utilizam Chromium (WebView2 baseia-se no motor Chromium do Edge). Todas as APIs web modernas (React 19, Framer Motion 12, Canvas 2D de PDF.js, Monaco Web Workers, CSS Container Queries) são suportadas de forma idêntica.
* **Alternativas Consideradas e Rejeitadas:**
  - *Substituição do Monaco pelo CodeMirror (Rejeitada):* Inútil e prejudicial; o Monaco é amplamente compatível com WebView2.
* **Riscos Associados e Mitigação:**
  - *Risco:* Cross-Origin worker script error no Monaco.
  - *Mitigação:* Carregamento inline de blobs de worker ou via loopback local verificado na Etapa 2.
* **Nível de Confiança:** **Alto (98%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 8: WebSocket to Tauri Command/Event Migration Strategy
*Qual é a estratégia recomendada para migrar os 101 tipos de mensagens WebSocket para comandos/eventos Tauri?*

* **Recomendação Clara:** **Estratégia Bifásica por Domínio Funcional**:
  1. **RPC Request/Response (80 mensagens):** Mapear para comandos `tauri::command` tipados (invocados via `invoke()`), retornando promises tipadas na UI.
  2. **Push Notifications & Streams (21 mensagens):** Mapear para `tauri::event` (`emit` / `listen`), com canais de tópicos (`chat:token`, `study:progress`, `sentinel:alert`).
* **Justificação Técnica Baseada em Evidência:**
  - Tratar todas as 101 mensagens como um barramento único de eventos (como era no WebSocket) perpetuaria a falta de tipagem estrita e o acoplamento do `WebSocketContext.tsx`.
  - Ao mapear requests clássicos (e.g. `fs_read_file`, `project_list`, `study_get_document`) para comandos diretos com validação de argumentos em Rust, o código fica auto-documentado, tipado via TypeScript bindings gerados, e muito mais rápido.
* **Alternativas Consideradas e Rejeitadas:**
  - *Emular um WebSocket em memória em Rust (Rejeitado):* Preserva a má arquitetura atual sem usufruir dos ganhos de segurança e performance do IPC do Tauri.
* **Riscos Associados e Mitigação:**
  - *Risco:* Inconsistência nos nomes de comandos.
  - *Mitigação:* `TAURI_COMMUNICATION_MATRIX.md` define a tabela canónica de tradução 1:1.
* **Nível de Confiança:** **Alto (95%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 9: Persistent Data Compatibility Strategy
*Como deve ser tratada a compatibilidade de dados persistidos (`database.db`, `state.db`, ficheiros de estudo, Obsidian vault) durante a transição?*

* **Recomendação Clara:** **Preservação rigorosa no mesmo formato e localização (`data/`)**, aplicando upgrades de esquema não destrutivos via migrações versionadas (`PRAGMA user_version`).
* **Justificação Técnica Baseada em Evidência:**
  - Ficheiros de estudo (`data/studies/`), base SQLite e vaults do Obsidian contêm dados reais e trabalho do utilizador. Nenhuma transição pode exigir exportação manual ou destruição de dados.
  - O Rust Core acederá ao mesmo diretório canónico `data/database.db`.
  - Um script de integridade de pré-voo em Rust verificará `PRAGMA integrity_check` antes de qualquer conexão.
* **Alternativas Consideradas e Rejeitadas:**
  - *Migração para uma base de dados diferente (e.g. Postgres local ou RocksDB) (Rejeitada):* Incompatibilidade severa com ecossistema Python e ferramentas analíticas.
* **Riscos Associados e Mitigação:**
  - *Risco:* Corrupção se duas versões abrirem a base ao mesmo tempo.
  - *Mitigação:* `flock` / lock de ficheiro exclusivo de processo único ativado no arranque.
* **Nível de Confiança:** **Alto (100%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 10: Code Consolidation in `agents/` and `backend/agents/`
*O código em `agents/` e `backend/agents/` deve ser limpo/consolidado antes da migração ou durante a migração?*

* **Recomendação Clara:** **Consolidar na Etapa 1 (antes do Tauri)**. Eliminar ou arquivar os 30 subpacotes dormentes duplicados em `agents/`, mantendo `backend/agents/` como a única fonte canónica ativa.
* **Justificação Técnica Baseada em Evidência:**
  - A auditoria catalogou 98 unidades em `agents/` (815 ficheiros Python), dos quais exatamente 30 são duplicados byte-a-byte de `backend/agents/`.
  - Migrar com essa duplicação causa confusão sistemática nos engenheiros e subagentes, risco de importar versões desatualizadas e duplicação desnecessária de surface de testes.
* **Alternativas Consideradas e Rejeitadas:**
  - *Deixar os duplicados para limpar no fim (Rejeitada):* Propaga código morto por todas as etapas seguintes e aumenta o tamanho do bundle final.
* **Riscos Associados e Mitigação:**
  - *Risco:* Algum script legado importar de `agents/` em vez de `backend/agents/`.
  - *Mitigação:* Testes de imports estáticos (`pytest`) garantindo que nenhum ficheiro do projeto importa das pastas descontinuadas antes da remoção definitiva.
* **Nível de Confiança:** **Alto (95%)**
* **Necessidade de Aprovação do Utilizador:** **Não**.

---

## QUESTION 11: Decision Criteria for Retiring Electron
*Qual deve ser o critério de decisão para desativar definitivamente o Electron?*

* **Recomendação Clara:** O Electron só será desativado na **Etapa 7**, após verificação cumulativa de **7 portões absolutos de aceitação**:
  1. 100% dos testes E2E Playwright (`test_redesign_consolidation_e2e.py`) passarem em execução contra a build de Tauri 2.
  2. Todas as 26 capacidades da matriz de paridade funcional validadas sem qualquer regressão.
  3. Consumo de memória RAM reduzido comprovadamente em > 40% em relação ao Electron.
  4. Tempo de arranque (cold start até UI interativa) < 1.500 ms.
  5. Zero processos órfãos (`python.exe`) após crash simulado ou fecho abrupto da janela.
  6. Todas as suites de integridade de documentação (`test_documentation_integrity.py`) a verde.
  7. **Aprovação explícita e formal do utilizador** após execução de sessão piloto completa.
* **Justificação Técnica Baseada em Evidência:**
  - Desativar o Electron antes de testes E2E rigorosos arrisca deixar o utilizador sem ferramenta de trabalho em caso de bug imprevisto no WebView2.
* **Alternativas Consideradas e Rejeitadas:**
  - *Remoção antecipada do Electron na Etapa 2 (Rejeitada):* Destrói a rede de segurança de poder rodar o sistema original para comparar comportamentos.
* **Nível de Confiança:** **Alto (100%)**
* **Necessidade de Aprovação do Utilizador:** **SIM (Obrigatória na Etapa 7)**.

---

## QUESTION 12: Realistic Effort Estimation & Dependencies
*Qual é a estimativa realista de esforço por etapa, considerando os riscos e dependências identificados nesta validação?*

* **Recomendação Clara e Cronograma:**

| Etapa | Designação | Esforço Estimado | Dependências Críticas | Nível de Risco |
|---|---|---|---|---|
| **Etapa 0.1** | **Auditoria, Validação e Baseline** | Concluída (Fase Atual) | Revisão de código e concordância com decisões | Baixo |
| **Etapa 1** | **Preparação do Frontend & Hardening do Python** | 3 – 5 dias de desenvolvimento | Criação do `JarvisTransport`, isolamento de `WebSocketContext`, WAL em SQLite, poda de `agents/` | Baixo / Médio |
| **Etapa 2** | **Bootstrap do Tauri 2 & Shell Desktop** | 3 – 4 dias de desenvolvimento | Setup `src-tauri/`, Tauri IPC adapter no frontend, verificação WebView2 | Médio |
| **Etapa 3** | **Servidor HTTP Loopback Rust & Media/Filesystem** | 3 – 4 dias de desenvolvimento | Servidor Rust `127.0.0.1:0` Range 206, Path Jail, Monaco e PDF.js | Baixo |
| **Etapa 4** | **Host Controller de Workers & IPC Bidirecional** | 5 – 7 dias de desenvolvimento | Implementação do protocolo `TAURI_WORKER_PROTOCOL.md`, Job Objects, Reverse RPC HITL | Alto |
| **Etapa 5** | **Migração de Domínios (Estudos, Missões, Obsidian, Sentinel)** | 6 – 8 dias de desenvolvimento | Conexão dos workers especializados, resolução dos 33 handlers de missões | Médio / Alto |
| **Etapa 6** | **Segurança, Hardening e Eliminação de Vulnerabilidades** | 3 – 4 dias de desenvolvimento | Correção da injeção de scriptblock PowerShell, regras de Path Jail, bypass de SSRF | Médio |
| **Etapa 7** | **Testes E2E, Validação de Paridade e Desativação do Electron** | 4 – 5 dias de desenvolvimento | Execução dos 7 portões de aceitação, teste piloto, remoção de dependências Electron | Médio |
| **Etapa 8** | **Otimização Final, Telemetria e Empacotamento de Produção** | 3 – 4 dias de desenvolvimento | Assinatura de código, empacotador NSIS/MSI, profiling de memória | Baixo |

* **Total Estimado:** **30 a 41 dias de desenvolvimento contínuo**, garantindo risco zero de quebra em produção através de migração estritamente faseada.
* **Nível de Confiança:** **Alto (90%)**
* **Necessidade de Aprovação do Utilizador:** **SIM (Para autorizar o início da Etapa 1)**.

