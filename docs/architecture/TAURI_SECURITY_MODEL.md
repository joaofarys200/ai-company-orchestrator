# JARVIS OS — Modelo de Segurança Tauri 2 + Rust

**Baseline analisada:** `main` @ `fb1aeeda10652ed1662e7e5c24ed381d7635f8d0`  
**Princípio orientador:** Migrar para Rust e Tauri 2 **não garante segurança automaticamente**. Segurança real exige fronteiras explícitas entre WebView (não confiável por princípio face a conteúdos externos/projetos), Núcleo Rust (autoridade de política e IO), Workers Python (runtime isolado por domínio) e o Sistema Operativo Windows.

---

## 1. Postura Atual vs Riscos Confirmados no Código [Confirmado no código]

| Superfície | Controlo Atual | Vulnerabilidade ou Fragilidade Confirmada | Correção na Arquitetura Alvo |
|---|---|---|---|
| **Sandbox IDE Preview (`sandbox.py`)** | Servidor HTTP embutido na porta `8080` | `TCPServer(("", 8080), ...)` faz bind a **`0.0.0.0`**, expondo ficheiros e UI do projeto na rede local | Bind exclusivo em **`127.0.0.1:0`** (porta efémera) com header `X-Content-Type-Options: nosniff` |
| **Autenticação Media/WS (`main.js`, `server.py`, `sandbox_service.py`)** | `X-Jarvis-Token` injetado via `webRequest`; `?token=` em `<video>`/`<img>` (`StudyVideoReaderView.tsx`); `ws://127.0.0.1:8001/?token=` (`hmac.compare_digest`) | Token exposto em query strings de URL (`window.__JARVIS_HTTP_TOKEN__` + DOM); CORS em `:8000` não reconhece origens Tauri (`tauri://localhost` / `http://tauri.localhost`) | **Eliminar HTTP `:8000` e WS `:8001` em produção**; usar `invoke()` nativo + **Servidor Loopback HTTP (`127.0.0.1:0`)** com cookie de sessão HttpOnly |
| **Validação de Mensagens IPC (`backend/transport_gateway.py`)** | `backend/websocket/gateway.py` valida com `validate_client_message()` | `StdioTransportGateway` encaminha JSON de `stdin` **sem chamar `validate_client_message()`** | Comandos Tauri tipados em `serde` + schema único obrigatório no canal NDJSON dos workers Python |
| **Gestão de Portas no Arranque (`main.js`)** | `freePortIfLocked` nas portas `8000` e `8001` | Executa `netstat` + `taskkill /F /T` contra **qualquer processo externo** que ocupe as portas `8000` ou `8001` | Arquitetura baseada em pipes anónimos (`stdin`/`stdout`) + Win32 Job Objects: **zero portas fixas para matar** |
| **Escrita em Disco & Vault** | `study_fs.py` usa `mkstemp` + `fsync` + `os.replace`; `ObsidianGraphEngine` usa `NoteFileLock` (`O_CREAT|O_EXCL`) | **22 pontos de escrita não-atómica confirmados** em ficheiros de inteligência, cache, sessões, notas e sentinela (risco de ficheiros vazios/corrompidos em crash ou concorrência) | Centralizar toda escrita crítica em `atomic_write` (Rust `NamedTempFile::persist` / `study_fs.atomic_write`) |
| **Execução de Comandos (`workspace_policy.py`)** | `COMMAND_BLOCKLIST` (9 regexes simples) | **7 vetores de evasão confirmados** (PowerShell aliases, LOLBins, separadores `/`, expansão de variáveis, caminhos UNC, redirecionamento `>`, encadeamento `&&`) | Substituir regexes por AST lexer de comandos em Rust + whitelist estrita de executáveis permitidos |
| **Injeção de Scriptblock (`project_builder.py:3405`)** | String interpolation `f"& {{ {command} }}"` | **Vulnerabilidade de Command Injection crítica:** quebra de aspas/chaves permite execução arbitrária fora do workspace | Passagem de argumentos como array de tokens nativo (`std::process::Command::args`) sem invocação de shell não auditado |
| **Race Condition no Spawn de Processos (`project_builder.py:3474`)** | `subprocess.Popen` seguido de atribuição a Job Object | **Janela de corrida (Spawn vs Job Assignment):** o processo filho pode spawnar netos antes de o Job ser atribuído, escapando ao controlo | Criação de processos em estado suspenso (`CREATE_SUSPENDED`), vinculação ao Job Object, e subsequente `ResumeThread` |
| **SSRF e Validação de URLs (`video_intelligence_service.py:700`)** | Validação por regex de sufixo `.mp4` | **Bypass de SSRF por DNS Rebinding:** URLs com sufixo `.mp4` contornam allowlists e podem aceder a `127.0.0.1` ou `169.254.169.254` | Validação estrita de IP após resolução DNS com rejeição de intervalos privados/loopback |
| **Proteção de Processos Sentinel (`security/sentinel/`)** | `ResponseEngine` protege `python.exe`, `node.exe`, `electron.exe` de auto-terminação | Ao substituir `electron.exe` pelo binário Tauri, a allowlist atual não protege o novo processo nativo nem os sidecars isolados | Atualizar allowlist dinâmica para PID/árvore do binário Tauri (`jarvis-os.exe`), PIDs dos workers registados e `ollama.exe` |
| **Permissões HITL (`security/permission_gateway/`)** | `PermissionGatewayService` (TTL 300s, `.jarvis/permissions/requests/*.json`, `audit_log.jsonl`), `CrossProjectApprovalError`, fail-closed `PermissionPolicyEngine` | Política sólida em Python, mas subordinada a um único processo onde ferramentas e backend partilham o mesmo espaço de memória | Mover a decisão e o estado da `PermissionGate` para o **Rust Core**, tornando-a intransponível pelos workers |

---

## 2. Capabilities, ACLs e Isolamento de Janelas (Tauri 2) [Recomendação]

Em Tauri 2, o acesso da WebView a comandos Rust e plugins é negado por omissão e habilitado granularmente em `src-tauri/capabilities/`.

### 2.1 Capability da Janela Principal (`capabilities/main-window.json`)
- **Identificador**: `main-capability` vinculada exclusivamente à label `main` e URL local empacotada (`tauri://localhost` / `http://tauri.localhost` ou `http://127.0.0.1:5173` apenas em perfil `debug`).
- **Plugins autorizados (mínimo privilégio)**:
  - `core:default` (apenas eventos/janelas necessários, sem `shell:allow-execute` genérico!)
  - `dialog:allow-open` (apenas para `selectFolder` e seleção de ficheiros pelo utilizador — **nunca `shell` nem `fs` irrestrito na WebView**).
  - `opener:deny-default` — toda abertura de ficheiro/URL passa pelo comando Rust auditado `system_open_path` que aplica Path Jail antes de invocar o `opener` internamente.
- **Comandos permitidos**: whitelist explícita por domínio (`jarvis:chat`, `jarvis:study`, `jarvis:projects`, `jarvis:knowledge`, `jarvis:permissions`, `jarvis:sentinel`, `jarvis:missions`, `jarvis:system`). **Zero comando genérico `exec_shell(cmd)` exposto à UI.**

### 2.2 Capability de Pré-visualização / Iframes de Projeto (`capabilities/preview-sandbox.json`)
- Projetos gerados no IDE (`WorkspaceViewer.tsx`) correm código potencialmente não auditado ou criado por LLM dentro de `<iframe src="http://127.0.0.1:<ephemeral_port>">` (ou WebView separada).
- Essa origem **NÃO recebe acesso ao `window.__TAURI_INTERNALS__`** (`dangerousUseHttpScheme` desativado para origens de preview; `remote.urls` NÃO inclui `127.0.0.1:*` do preview).
- O `<iframe sandbox="allow-scripts allow-forms allow-same-origin">` (ou sem `allow-same-origin` quando aplicável) não pode invocar comandos Tauri nem aceder às rotas de media do loopback.

---

## 3. Política de Conteúdo (CSP) e Servidor Loopback HTTP (`127.0.0.1:0`) [Recomendação Validada]

### 3.1 CSP Recomendada (`tauri.conf.json`)
```json
{
  "app": {
    "security": {
      "csp": {
        "default-src": "'self'",
        "script-src": "'self' 'wasm-unsafe-eval'",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: blob: http://127.0.0.1:*",
        "media-src": "'self' blob: http://127.0.0.1:*",
        "connect-src": "'self' ipc: http://ipc.localhost ws://127.0.0.1:8001 http://127.0.0.1:8000",
        "frame-src": "http://127.0.0.1:*",
        "object-src": "'none'",
        "base-uri": "'self'"
      }
    }
  }
}
```
*Notas:*
- `'wasm-unsafe-eval'` destina-se exclusivamente aos workers WASM/JS locais do `pdfjs-dist` e Monaco Editor empacotados em `'self'` (evitando `unsafe-eval` amplo).
- `ws://127.0.0.1:8001` e `http://127.0.0.1:8000` na `connect-src` existem **apenas na fase transitória** (Stages 1–3) e devem ser removidos na Stage 8 ao descomissionar o gateway WebSocket/HTTP legado.

### 3.2 Hardening do Servidor Loopback HTTP (`127.0.0.1:0`) & Path Jail
Toda requisição a `http://127.0.0.1:<port>/study/{doc_id}/...` no handler Rust deve impor:
1. **Validação estrita de `doc_id`**: apenas `^[a-zA-Z0-9_-]{4,64}$` (rejeita `..`, `/`, `\`, `%2e%2e`).
2. **Canonical Path Jail**: resolver `canonicalize()` da raiz `data/study/` e do ficheiro destino e confirmar `target.starts_with(&study_root)`. Rejeita symlinks/junctions que apontem para fora de `data/study/`.
3. **Allowlist de extensões/MIME**: `.pdf` (`application/pdf`), `.mp4` (`video/mp4`), `.png`/`.jpg`/`.webp` — bloqueando execução acidental de `.html`/`.svg` ativos com `Content-Disposition: inline` ou servindo `.svg` apenas com `Content-Security-Policy: sandbox` caso exista.
4. **Limitação de método**: apenas `GET` e `HEAD`.

---

## 4. Path Jail, Nomes Reservados Windows e Anti-Symlink [Recomendação]

Para reproduzir e superar as defesas existentes em `workspace_policy.py` e `study_fs.py`:
- **Canonicalização segura em Windows**: usar `dunce::canonicalize` (evita prefixos UNC `\\?\` incompatíveis com algumas ferramentas Win32/Python) sobre o caminho e sobre a raiz permitida (`WORKSPACE_ROOT`, `data/study`, `obsidian_vault`, `os.tmpdir()`).
- **Verificação pré-criação**: quando o ficheiro destino ainda não existe (`create_project_file`, `save_note`), canonicalizar o diretório pai existente e validar o último segmento contra `..`, separadores e **nomes reservados Win32** (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`, com ou sem extensão).
- **Prevenção TOCTOU em ficheiros sensíveis**: operações destrutivas ou dentro de `.jarvis/` devem verificar atributos (`symlink_metadata`) antes de abrir para escrita/leitura.

---

## 5. Modelo HITL de Permissões, Execução de Código & Sentinel [Confirmado + Recomendação]

### 5.1 Preservação e Reforço do `PermissionGatewayService`
- **Compatibilidade de formato [Confirmado no código]**: manter o esquema de pedidos em `.jarvis/permissions/requests/*.json` (TTL padrão **300s**) e trilha apendicular `audit_log.jsonl` (atualmente com 25.182 B e 23 ficheiros de pedido existentes) durante a transição, permitindo que o Rust Core leia e continue a auditar o mesmo formato ou migre com compatibilidade retroativa.
- **Invariantes Fail-Closed**:
  1. `PermissionPolicyEngine` nega por omissão se a avaliação falhar, expirar (>300s) ou houver erro de deserialização.
  2. `CrossProjectApprovalError`: uma aprovação concedida ao projeto `A` **nunca** autoriza mutação ou execução no projeto `B`.
  3. **`COMMAND_BLOCKLIST` (9 regexes de `workspace_policy.py`) + `SafetyClassifier`**: validados em Rust **antes** de criar qualquer `tokio::process::Command` ou encaminhar execução para builder/worker.

### 5.2 Win32 Job Objects & Isolamento de Sidecars
- Todo subprocesso lançado pelo Rust Core (workers Python, `project_builder`, comandos aprovados de projeto, `ollama serve` auto-spawned) deve ser imediatamente atribuído a um Win32 Job Object com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
- **Benefício**: paridade nativa com `_WindowsJob` (`project_builder.py`) sem depender de Python para matar processos órfãos no shutdown ou em crash abrupto.

### 5.3 Sentinel & Contenção HITL
- Os 6 coletores (`Process`, `Network`, `Persistence`, `Hosts`, `Browser`, `WindowsSecurityEvents`) mantêm o **`shadow_mode=True` por omissão** [Confirmado no código].
- Nenhuma ação destrutiva dos 5 executores (`schtasks`, `netsh advfirewall`, `taskkill`, quarantine em `sentinel/quarantine/`) é disparada automaticamente sem aprovação explícita HITL registada no Rust Core (`sentinel_approve_action`), mantendo `sentinel/response_history.json` (com escrita atómica!) para suportar `sentinel_rollback_action`.

---

## 6. Segurança de Prompts, SSRF e Gestão de Segredos [Recomendação]

1. **Gestão de Segredos (`.env` / Chaves Cloud)**:
   - `GEMINI_API_KEY` e quaisquer tokens externos presentes em `.env` são carregados **exclusivamente no processo Rust Core** (e repassados por pipe/memória apenas ao `voice_swarm_worker` quando Gemini Live está ativo).
   - **Proibido** devolver variáveis de ambiente ou tokens nos payloads de `state`, `initial_sync`, `system` ou `localStorage`.
2. **Proteção SSRF na Ingestão de URLs/Vídeos (`video_intelligence_service.py:700`)**:
   - Atualmente, URLs com terminação `.mp4` contornam a allowlist de domínios, permitindo que atacantes ou prompts maliciosos forcem downloads de endpoints internos (`http://169.254.169.254/latest/meta-data/video.mp4` ou `http://127.0.0.1:11434/api/tags?.mp4`).
   - A mitigação em Rust exige: resolução de DNS pré-voo, validação de que o IP não pertence a gamas privadas/loopback (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`, `172.16.0.0/12`, `192.168.0.0/16`, `::1`, `fc00::/7`), e fixação do IP resolvido na conexão HTTP para prevenir ataques de DNS Rebinding.
3. **Fronteira LLM → Ferramentas (Prompt Injection)**:
   - Textos extraídos de PDFs, notas Obsidian ou páginas web são tratados como **dados não-confiáveis**; nenhuma invocação de ferramenta (`tools.py`, `obsidian_tools.py`, escrita de ficheiro ou comando de build) pode contornar a `PermissionGate` e a `PathJail` em Rust mesmo quando originada por um modelo Ollama ou agente CrewAI.

---

## 7. Análise Forense de Vulnerabilidades Críticas Identificadas na Etapa 0.1 [Confirmado no código]

### 7.1 Os 7 Vetores de Evasão do `COMMAND_BLOCKLIST` (`workspace_policy.py:10-20`)
A lista negra atual baseia-se em 9 expressões regulares simples (`r"(\brm\b|\bdel\b|\berase\b)"`, `r"(\bformat\b)"`, etc.). A auditoria de segurança comprovou 7 falhas críticas de evasão que permitem contornar a política com facilidade:
1. **Normalização de Separadores de Argumento:** Comandos como `rmdir /s /q` são bloqueados se usarem `/s`, mas o interpretador Windows aceita `rmdir \s \q` ou trailing separators não capturados pelas regexes.
2. **Caminhos de Nomes Longos e UNC:** Prefixos como `\\?\C:\...` ou `\\127.0.0.1\c$\...` contornam os testes de limites de palavras (`\b`).
3. **Expansão de Variáveis de Ambiente:** Comandos como `%COMSPEC% /c d`+`el` ou powershell `$env:ComSpec` reconstroem os binários bloqueados em runtime sem que a string literal surja no comando validado.
4. **Living Off the Land Binaries (LOLBins):** O blocklist não inclui ferramentas administrativas padrão do Windows como `certutil -urlcache`, `bitsadmin`, `wmic process call create`, `reg.exe` ou `rundll32.exe`.
5. **Aliases Nativos do PowerShell:** No PowerShell, `Remove-Item` possui aliases como `ri`, `rmdir`, `rd`, `del`, `erase`; `Set-Content` pode sobrescrever binários sem invocar `del`.
6. **Redirecionamento de Ficheiros Destrutivo:** Expressões como `type NUL > critical_file.sys` truncam e destroem ficheiros sem utilizar comandos de remoção explícita.
7. **Encadeamento e Interpolação:** O uso de operadores de controle de fluxo de PowerShell (`&`, `;`, `|`, `&&`, subexpressões `$(...)`) permite embutir chamadas bloqueadas.

*Solução Alvo em Rust:* Substituir regexes ad-hoc por um tokenizer/lexer estrito em Rust, permitindo apenas um conjunto fechado de executáveis pré-autorizados (`git`, `npm`, `cargo`, `python`, `tsc`) com argumentos validados posicionalmente.

### 7.2 Injeção de Scriptblock no `project_builder.py:3405-3412`
Em `project_builder.py`, a execução de comandos constrói a linha de comando do PowerShell através de interpolação não higienizada de strings:
```python
# project_builder.py:3405
powershell_cmd = f'powershell.exe -ExecutionPolicy Bypass -Command "& {{ {command} }}"'
```
Se a variável `{command}` (fornecida pelo LLM ou projeto) contiver aspas duplas desbalanceadas ou `} ; evil_payload ; & {`, ocorre fuga imediata do bloco de script `& { ... }`, permitindo execução arbitrária de código fora do workspace sem restrição de privilégios.
*Solução Alvo em Rust:* Descontinuar a montagem de strings de shell. Invocar diretamente o executável alvo com `tokio::process::Command::new(program).args(&tokens)`.

### 7.3 Janela de Corrida Spawn vs Atribuição a Job Object (`project_builder.py:3474-3483`)
No código atual em Python:
```python
proc = subprocess.Popen(cmd, ...)
job.assign_process(proc.pid)  # JANELA DE CORRIDA ATIVA
```
Entre o retorno de `Popen` e a chamada `assign_process`, o processo filho já está em execução no Windows. Se o comando for um script malicioso ou gerador de subprocessos rápidos, ele pode criar processos netos *antes* de ser associado ao Job Object. Os processos netos não herdam os limites do Job (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) e sobrevivem na máquina como processos órfãos permanentes.
*Solução Alvo em Rust:* Utilizar a API nativa do Windows `CreateProcessW` com a flag `CREATE_SUSPENDED (0x00000004)`. Associar o handle do processo ao Job Object com `AssignProcessToJobObject` *enquanto ele ainda está congelado*, e só depois chamar `ResumeThread`.

### 7.4 Catálogo Completo das 22 Localizações de Escrita Não-Atómica
Para evitar perda de dados, corrupção de ficheiros JSON ou corrupção de notas do Obsidian durante crashes ou concorrência, todos os 22 pontos identificados devem ser migrados para o helper atómico (`atomic_write`):
1. `agents/obsidian_tools.py:206` (`write_text` em nota sem lock)
2. `services/obsidian_graph_engine.py:1677` (`open("w")` em ficheiro de propostas)
3. `services/obsidian_graph_engine.py:1246` (`open("w")` em propostas pendentes)
4. `services/obsidian_graph_engine.py:1340` (`open("w")` em bridge legado)
5. `services/study_service.py:4676` (`write_text` direto em exportação para Obsidian)
6. `services/video_intelligence_service.py:1979` (`write_text` direto em notas de vídeo)
7. `services/video_intelligence_service.py:2028` (`write_text` direto em transcrições)
8. `intelligence/typescript_dependency/cache.py:162` (`open("w")` em cache de dependências)
9. `intelligence/project_context.py:256` (`open("w")` em snapshot de contexto)
10. `intelligence/project_context.py:1049` (`open("w")` em atualização de contexto)
11. `intelligence/project_intelligence.py:274` (`open("w")` em índice de símbolos)
12. `intelligence/project_intake.py:931` (`open("w")` em intake metadata)
13. `intelligence/coding_session.py:1202` (`open("w")` em auto-repair JSON)
14. `intelligence/coding_session.py:1596` (`open("w")` em snapshot de sessão)
15. `intelligence/failure_memory.py:90` (`open("w")` em lições de falha)
16. `security/sentinel/response/engine.py:73` (`open("w")` em histórico de resposta)
17. `security/sentinel/baseline.py:147` (`open("w")` em baseline de segurança)
18. `security/sentinel/quarantine.py:120` (`open("w")` em metadados de quarentena)
19. `security/sentinel/audit.py:59` (`open("w")` em log de auditoria)
20. `security/permission_gateway/gateway.py:180` (append direto em `audit_log.jsonl` sem lock)
21. `agents/tools.py:84` (`write_file_sync` com truncamento direto)
22. `agents/memory.py:50,101` (`open("w")` em memória de sessão e métricas de loop)



### 7.5 Falhas Adicionais Confirmadas & Matriz de Portões de Mitigação (Milestone Gates)

1. **Autenticação no Loopback HTTP & Token Padrão Inseguro:**
   - *Ficheiros:* `backend/services/sandbox_service.py:141-158` e `server.py:243`.
   - *Vulnerabilidade:* Se `JARVIS_HTTP_TOKEN` não for definido, `_is_study_request_authorized()` retorna `True` incondicionalmente, expondo todos os PDFs/vídeos da pasta `data/study/` a processos locais não autenticados. Adicionalmente, `server.py:243` utiliza como fallback o token hardcoded `"local-dev-token"`.
   - *Mitigação Obrigatória:* Geração de token criptográfico efémero no arranque (`secrets.token_urlsafe(32)`) sem qualquer fallback permissivo. Enforçar autenticação estrita em todas as rotas. **Portão: Antes da Etapa 1.**

2. **Spoofing de Identidade no Reverse RPC HITL:**
   - *Ficheiros:* `backend/websocket/handlers/permissions.py:92-95` e `security/permission_gateway/gateway.py:330-345`.
   - *Vulnerabilidade:* O handler confia cegamente em `message.get("user")` e `message.get("session_id")` fornecidos pelo payload do cliente em vez de extrair a identidade da sessão autenticada do transporte, permitindo que scripts ou agentes forjem aprovações de alto privilégio.
   - *Mitigação Obrigatória:* Validação estrita de que a identidade da aprovação provém do contexto da sessão do servidor autenticado. **Portão: Antes da Etapa 1.**

3. **Matriz Consolidada de Portões de Segurança:**
   - **Portão Antes da Etapa 1 (Bloqueadores Imediatos):**
     * Transição do `COMMAND_BLOCKLIST` para o modelo estruturado de executável e argumentos (`CreateProcessW`/`args`).
     * Eliminação do scriptblock com f-string em `project_builder.py:3405`.
     * Prevenção de fuga de processos no Win32 Job Object via `CREATE_SUSPENDED`.
     * Eliminação de `"local-dev-token"` e autenticação mandatória no loopback.
     * Correção do spoofing de identidade em `permissions.py`.
   - **Portão Antes da Etapa 2:**
     * Remediação completa de SSRF, resolução DNS fail-closed e IP pinning em `video_intelligence_service.py`.
   - **Portão Antes da Aposentação do Electron:**
     * Isolamento de descritores no worker Python (`os.dup(1)` + `sys.stdout = sys.stderr`).
