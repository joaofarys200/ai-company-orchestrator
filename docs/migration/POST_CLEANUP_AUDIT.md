# AUDITORIA PÓS-COMMIT — ELIMINAÇÃO DE CMD E LIMPEZA DO LEGADO (PÓS-CORREÇÕES)

- **Data da Auditoria (UTC):** `2026-11-16`
- **Branch:** `fix/eliminate-cmd-windows` (`origin/fix/eliminate-cmd-windows`)
- **Base `main` (intocada):** `7dcd5ffb9677005a6b6faf03b24eaf4599c18b0b` (`7dcd5ff`)
- **Cadeia de Commits Validados na Branch:**
  1. `ad2c8bfb6fe71228481d08bf2becde34aa3f27a9` (`ad2c8bf`) — Eliminação de consolas CMD, correção do runtime autónomo e limpeza de legado Electron/WS/arquivos obsoletos.
  2. `799f94d` — Restauro de `scripts/run_real_browser_qa.cjs` + fallback Playwright Edge em `RealBrowserQAValidator`, remoção de 4 ficheiros órfãos partidos (`agents/streaming_transport.py`, `scripts/model_harness_stateful_provider_diagnostic.py`, `workspace/infra_monitor/{server,anomaly_detector}.py`), limpeza de `agents.mission_recovery` e alinhamento de testes/docs.
  3. `20f72a2` — Proteção `CREATE_NO_WINDOW` e `SW_HIDE` para `multiprocessing.popen_spawn_win32` e `ProcessPoolExecutor` (`SwarmFederation`).
  4. Commit final de documentação/licenciamento/artefactos — `THIRD_PARTY_LICENSES.md` (raiz + empacotado em `src-tauri/py-runtime/`), `scripts/prepare_python_runtime.py`, `src-tauri/py-runtime/manifest.json` e este relatório atualizado.
- **Classificação Final:** **`READY FOR PR`**

---

## 1. Resolução Integral dos Bloqueadores de `ad2c8bf`

Todos os problemas concretos levantados na auditoria inicial a `ad2c8bf` foram corrigidos de forma cirúrgica e validados:

| Ponto Identificado em `ad2c8bf` | Correção Aplicada | Estado Atual |
| :--- | :--- | :--- |
| **`scripts/run_real_browser_qa.cjs` ausente / `RealBrowserQAValidator` quebrado** | Restaurado [scripts/run_real_browser_qa.cjs](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/run_real_browser_qa.cjs) integralmente a partir de `7dcd5ff`; atualizado [real_browser_qa.py](file:///c:/Users/joaor/Desktop/JarvisOS/security/delivery_governance/real_browser_qa.py) para ler `stdout`/`stderr`, usar diretório temporário quando `evidence_dir` é omitido e recorrer a `playwright.sync_api` (`channel="msedge"`) em dev/testes quando `playwright` npm não existe (sem adicionar dependências ao `frontend/package.json` nem ao `runtime-bundle.zip`). | **RESOLVIDO** (`test_e2e_isolated_fixture_gate.py` passou em Edge real). |
| **Módulo órfão partido `agents/streaming_transport.py`** | Confirmados `0` chamadores em todo o repositório; eliminado em `799f94d` em vez de restaurar `io_dispatch`/`distributed_transport`. | **RESOLVIDO** (`0` imports quebrados). |
| **Referências quebradas em arranque/scripts/infra** | Eliminados `scripts/model_harness_stateful_provider_diagnostic.py` e `workspace/infra_monitor/{server,anomaly_detector}.py` (sem chamadores); removido bloco morto `agents.mission_recovery` em [application_lifecycle.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/application_lifecycle.py); atualizado comentário ADR em [mission_dispatch.rs](file:///c:/Users/joaor/Desktop/JarvisOS/src-tauri/src/commands/mission_dispatch.rs#L3). | **RESOLVIDO** (`test_application_lifecycle.py` e scan AST `0` erros). |
| **Gap de consola CMD em `ProcessPoolExecutor` (`agents/swarm_federation.py`)** | Implementado `_NoWindowMpWinApiProxy` em [process_utils.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/process_utils.py) para envolver `multiprocessing.popen_spawn_win32._winapi.CreateProcess` com `CREATE_NO_WINDOW` (`0x08000000`), `SW_HIDE` e logging `mp_process_start`; consolidado `_create_spawn_process_pool` + `_swarm_worker_bootstrap` em [swarm_federation.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/swarm_federation.py); fixado também `hidden_startupinfo` quando caller passa `startupinfo` customizado em `_guarded_popen_init`. | **RESOLVIDO** (verificado com espião `_winapi`, evento `mp_process_start` e prova viva com `0` janelas CMD). |
| **Testes & Docs desatualizados pelas remoções** | Atualizado [test_architecture_preservation.py](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_architecture_preservation.py) para validar docs/ADRs canónicos e `manifest.json`; corrigida criação temporária de `src/` em [test_project_builder_working_directory.py](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_project_builder_working_directory.py#L54-L74); apontado [test_mission_model_harness_e2e.py](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_mission_model_harness_e2e.py#L34-L39) para `tests/fixtures/task-app`; corrigido comando pytest em [README.md](file:///c:/Users/joaor/Desktop/JarvisOS/README.md#L378). | **RESOLVIDO** (`4/4` testes corrigidos passam). |

---

## 2. Sumário do Diff, Ficheiros Removidos & Lockfiles

- **Base `ad2c8bf` (`3305` ficheiros alterados face a `7dcd5ff`)** combinada com os incrementos `799f94d` e `20f72a2`:
  - **Electron & Arquitetura Híbrida**: removidos `scripts/inspect_electron.py`, transportes nativos RIO/QUIC/distribuído obsoletos, código `electron-ipc`, fallback `tauri-hybrid` em `frontend/src/transport/*` e proxy `:8000` em `frontend/vite.config.ts`.
  - **Runtime Discovery**: removidos 6 submódulos mortos + captura obsoleta; preservado apenas `RuntimeDiscoverySecurity`.
  - **Documentação, Diagnósticos, Evidence, Workspace & Painéis Mortos Frontend**: removidos 41 ficheiros não montados/legados no frontend (mantendo todas as vistas core) e relatórios históricos obsoletos; 5 PNGs do README preservados em `docs/assets/`.
  - **Análise AST pós-correções**: `0` imports internos quebrados em qualquer pacote de produção (`backend`, `workers`, `services`, `intelligence`, `agents`, `security`, `persistence`, `schemas`, `config`, `scripts`). *(Os 166 padrões `backend.agents.*` em `tests/` usam o alias suportado em `tests/` e executam normalmente).*
- **Lockfiles e Dependências**:
  - `src-tauri/Cargo.lock`, `frontend/package-lock.json`, `package-lock.json` da raiz e `requirements.txt` estão **todos presentes, versionados e ativos** na CI (`cargo check/test --locked`, `npm ci`, `npm --prefix frontend ci`).

---

## 3. Avaliação Técnica de PDF (PyMuPDF vs `pypdfium2`) e FFmpeg (LGPL vs GPLv3)

Documentação formal publicada em [THIRD_PARTY_LICENSES.md](file:///c:/Users/joaor/Desktop/JarvisOS/THIRD_PARTY_LICENSES.md) (e empacotada dentro dos instaladores em `py-runtime/THIRD_PARTY_LICENSES.md` e `app/THIRD_PARTY_LICENSES.md`):

1. **PyMuPDF (`pymupdf==1.28.2` — Mantido por preservação funcional)**:
   - O exame de todos os módulos consumidores (`services/study_document_generation/layout_composer.py` [91 linhas], `orchestrator.py`, `qa_engine.py`, `services/document_intelligence.py`, `backend/document_engine/render_engine.py`, `visual_inspector.py`, `services/study_service.py`) demonstrou que o JARVIS OS utiliza extensivamente a API de **composição/autoria programática de PDF** (`pymupdf.Font`, `Shape.draw_line`, `Shape.draw_rect`, `insert_textbox`, `insert_link`, extração de figuras por `xref` com `Pixmap(pdf, xref)`).
   - `pypdfium2==5.13.0` (`Apache-2.0 / BSD-3-Clause`, também incluído no bundle) não possui equivalente drop-in para composição tipográfica/gráfica nem extração por `xref`, pelo que substituí-lo comprometeria funcionalidades ativas de geração e análise de documentos de estudo.
   - **Licenciamento**: mantido `pymupdf==1.28.2` com aviso explícito das obrigações **AGPL-3.0 / Licença Comercial Artifex** em `THIRD_PARTY_LICENSES.md`.

2. **FFmpeg (`ffmpeg-win-x86_64-v7.1.exe` via `imageio-ffmpeg==0.6.0` — GPLv3 documentado)**:
   - [services/video_intelligence_service.py](file:///c:/Users/joaor/Desktop/JarvisOS/services/video_intelligence_service.py#L147) utiliza explicitamente `-c:v libx264` em `ensure_playable_mp4()` para converter `.wmv`/`.mkv`/`.avi` em MP4 compatível com WebView2. Compilações exclusivamente LGPL não incluem `libx264`.
   - O binário é invocado estritamente out-of-process como subprocesso CLI com `CREATE_NO_WINDOW`.
   - **Licenciamento**: documentadas integralmente em `THIRD_PARTY_LICENSES.md` as obrigações da Secção 6 da **GPLv3** (aviso GPLv3 e acesso/referência ao código-fonte correspondente da build `7.1-essentials_build-www.gyan.dev`).

---

## 4. Runtime Autónomo, Eliminação de Janelas CMD e Estado dos Workers

- **Bundle Atualizado ([manifest.json](file:///c:/Users/joaor/Desktop/JarvisOS/src-tauri/py-runtime/manifest.json))**:
  - **Arquivo**: `src-tauri/py-runtime/runtime-bundle.zip` (`110 142 147` bytes | SHA-256: `2476e3bb978c48da7cd6b3a60d75183341602a250ea602353dbbf7c1c9735a93`).
  - **Composição**: Python `3.14.7`, `app_files_count: 800`, `python_files_count: 2751`, `site_packages_count: 94`.
  - **Arquitetura PE & DLLs**: 100% dos binários de execução (`python.exe`, `pythonw.exe`, `numpy 2.5.2`, `OpenBLAS`, `pymupdf`, `pypdfium2`, `libportaudio64bit.dll`, `ffmpeg-win-x86_64-v7.1.exe`, `vcruntime140*.dll`, `msvcp140*.dll`) são `x86_64` AMD64 (`0x8664`, PE32+ `0x20b`). Zero dependências faltantes; `PYTHONNOUSERSITE=1` comprovado em isolamento.
- **Estado dos 4 Workers (`ai`, `study`, `mission`, `voice`)**:
  - Todos arrancam em ambiente Windows limpo (`PATH=C:\Windows\System32;C:\Windows`, sem Python/Node/`ffmpeg`), comunicam via Tauri stdio JSON-RPC, capturam `stdout`/`stderr` para logs rotativos em `%LOCALAPPDATA%\JarvisOS\logs\` com redação de segredos, operam sob `JobObject` (`KILL_ON_JOB_CLOSE`, limite 4 GiB, `BREAKAWAY_OK` para CUDA/Ollama sem `DETACHED_PROCESS`), e encerram com **0 janelas CMD** e **0 processos órfãos**.

---

## 5. Resultados Finais de Validação e Instaladores (Pós-Última Edição)

### Builds, Suites de Testes e Coleta
| Verificação | Resultado Observado | Detalhes / Notas |
| :--- | :--- | :--- |
| **Frontend Tests (`npm --prefix frontend test`)** | **18 passed, 0 failed** (5 suites, 396.5 ms) | Transporte Tauri IPC, origem virtual, iframe sandbox, `CodeEditor`, `StudyVideoReaderView`. |
| **Frontend Prod Build (`npm --prefix frontend run build`)** | **Exit 0** (`3518` módulos, 4.73s) | `tsc -b && vite build` sem erros. |
| **Rust Check & Tests (`cargo --locked`)** | **59 passed, 0 failed, 0 ignored** (3.37s) | `cargo check --locked --all-targets` (`exit 0`) + `cargo test --locked`. |
| **Python CI Pass 1 (11 suítes Windows CI)** | **54 passed, 1 skipped, 17 subtests** (27.23s) | Skipped: `test_rho_migration_sandbox.py` (`WinError 1314` symlink sem privilégio Windows). |
| **Python CI Pass 2 (9 suítes Windows CI)** | **99 passed, 321 subtests, 2 warnings** (13.01s) | Warnings de `AnyThreadEventLoopPolicy` em Python 3.14. |
| **Python Domínio, Crash Recovery, PDF & Browser QA (25 suítes)** | **291 passed, 2 skipped, 0 failed** (150.28s) | Inclui `crash_recovery_loop`, `coding_session`, `project_context`, `study_*`, `video_intelligence`, `word_document_engine`, `document_generation_phase5`, `document_intelligence_phase2`, `editorial_intelligence_phase4`, `phase5_corrective_audit`, `obsidian_graph_engine`, `mission_*`, `sentinel_lifecycle`, `voice_*`, `process_utils_no_window`, `model_harness_*`, `e2e_isolated_fixture_gate` (Edge real OK), `architecture_preservation`. |
| **Python SwarmFederation (`phase17..phase18_3`, processo próprio)** | **57 passed, 0 failed** (12.95s) | Nota: num lote único combinado de 30 suítes (`p3`), `test_memory_budget_at_scale_512` registou RSS acumulado de `235.88 MB` (`Parent: 178.38 MB` herdado das suítes anteriores); no seu processo dedicado passa `57/57`. |
| **`test_project_builder_working_directory.py`** | **7 passed, 1 deselected** | A falha corrigida por nós (`test_node_src_test_uses_project_file_not_jarvis_root`) agora passa; o único caso restante (`test_timeout_is_reported_without_losing_working_directory`) já falhava na `main` (`7dcd5ff`) por cold-start PowerShell > 50 ms. |
| **Coleta Global (`pytest --collect-only -q`)** | **2410 tests collected** (4.98s, `exit 0`) | Zero erros de coleta/sintaxe/importação em todo o repositório. |
| **Janela Zero-CMD Viva (`ProcessPoolExecutor`)** | **Passed** (`NEW_CONSOLE_WINDOWS: set()`) | Processo pai sem consola a executar `_create_spawn_process_pool(2)` no Windows sem qualquer janela visível. |

### Instaladores, Runtime Multimédia/PDF e Preservação de Dados
- **MSI (`JARVIS OS_0.1.0_x64_en-US.msi`, `119 721 984` bytes / `114.18 MiB`)**: extração limpa via `msiexec /a`, arranque com `PATH` mínimo (`C:\Windows\System32;C:\Windows`), boot completo dos 4 workers (`ai`, `study`, `mission`, `voice`), **0 janelas CMD**, **0 órfãos**, e preservação confirmada de sessão SQLite + documento de estudo após upgrade simulado.
- **NSIS (`JARVIS OS_0.1.0_x64-setup.exe`, `117 660 067` bytes / `112.21 MiB`)**: instalação silenciosa `/S`, SHA-256 do bundle idêntico ao manifest (`2476e3bb...`), arranque dos 4 workers (`PHASE_A_EXIT=0`, `CONSOLE_WINDOWS=0`), arranque normal da GUI (`MAIN_HWNDS=1`, `CONSOLE_WINDOWS=0`), encerramento via `WM_CLOSE` com **0 processos órfãos**, `THIRD_PARTY_LICENSES.md` presente em `%LOCALAPPDATA%\JARVIS OS\py-runtime\` e `app/`, e warmup Ollama `qwen3.5:9b` carregado 100% em VRAM GPU (`size_vram == size == 5 502 937 332` bytes).
- **Pipeline Funcional Multimédia & PDF (`PYTHONNOUSERSITE=1`, `PATH` limpo)**: geração MP4 H.264/AAC (`10 101` B), extração WAV + keyframe PNG via `ffmpeg`, análise FFT `440.4 Hz` & cosine similarity `0.9965` via `numpy 2.5.2`, `PIL` `640x360`, geração/leitura PDF via `pymupdf 1.28.2`, captura de stderr em erro, redação de segredos e rotação de logs.
- **Dados Locais & Pessoais**: [database.db](file:///c:/Users/joaor/Desktop/JarvisOS/database.db) (`1 060 864` bytes, `PRAGMA integrity_check = ('ok',)`, `PRAGMA foreign_key_check = []`, `wal`), `workspace/projects/dina` (`792` ficheiros), `data/study`, `obsidian_vault`, `docs/transcriptions`, `docs/portfolio_readmes`, `ideias_projeto_CG.md`, `plano_rendimento.md`, 22 scripts em `scripts/` e ficheiros locais não commitados permaneceram integralmente preservados.

### Vistas Core & Comparação Funcional/Visual
- Todas as vistas (`HologramCore`, `ChatPanel`, `WorkspaceViewer`, `SentinelDashboard`, `CodeEditor`, `StudyContainer`, `ObsidianVaultView`, `MissionControlCenter`, `Voice`, preview iframe com sandbox, Dev Tools) permanecem intactas e ligadas em [App.tsx](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/App.tsx) e [WorkspaceViewer.tsx](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/workspace/WorkspaceViewer.tsx), compilando sem erros (`3518` módulos) e com arranque real da janela WebView2 verificado.

---

## 6. Conclusão e Compatibilidade Git/CI

- Todos os critérios de conclusão foram cumpridos: nenhum problema introduzido por `ad2c8bf` permanece aberto, a criação de processos multi-processo no Windows respeita `CREATE_NO_WINDOW`, `RealBrowserQAValidator` e `scripts/run_real_browser_qa.cjs` funcionam integralmente sem inchar o runtime instalado, as obrigações GPLv3 (FFmpeg) e AGPL-3.0 (PyMuPDF) estão formalmente justificadas e empacotadas, `main` não foi alterada e não foi aberto PR nem feito merge.
- O workflow [.github/workflows/tauri-windows-validation.yml](file:///c:/Users/joaor/Desktop/JarvisOS/.github/workflows/tauri-windows-validation.yml) executará automaticamente assim que for aberto um Pull Request de `fix/eliminate-cmd-windows` para `main`.

**Classificação Final:** **`READY FOR PR`**
