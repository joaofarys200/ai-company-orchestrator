# JARVIS OS — Stage 0.3: Auditoria de Persistência, Propriedade de Dados & Transição SQLite

**Baseline verificada:** `main` @ `fb1aeeda10652ed1662e7e5c24ed381d7635f8d0`  
**Natureza:** Validação crítica, consistência arquitetural e especificação de propriedade de persistência (Stage 0.3 — Sem alterações de código ou BD).  
**Documento principal associado:** [TAURI_MIGRATION_AUDIT.md](./TAURI_MIGRATION_AUDIT.md)

---

## 1. Descobertas Críticas na Auditoria de Disco e Código [Factos Verificados]

1. **`database.db` (`724.992 bytes`, `10` tabelas aplicacionais, NÃO 11):**
   - **Localização física real no disco:** `C:\Users\joaor\Desktop\JarvisOS\database.db` (na raiz do workspace).
   - **Verificação empírica de caminho:** `data/database.db` **NÃO existe**.
   - **Defeito crítico de resolução:** `database.py:24`, `persistence/db.py:7`, `backend/model_harness/rho.py:12` e `intelligence/runtime_observer.py:7` utilizam caminhos relativos literais não ancorados (`"database.db"`), gerando risco de criar uma nova base vazia se o diretório de trabalho mudar.
   - **Caminho Canónico Definido:** Deve ser ancorado estritamente em `PROJECT_ROOT / "database.db"`. Qualquer relocação futura para `data/database.db` ou diretório de utilizador (`%APPDATA%`) deve ser executada mediante um procedimento explícito de migração, backup físico `.bak`, verificação de integridade e checksum SHA256, com capacidade de rollback.
   - `PRAGMA journal_mode` = **`delete`** (WAL **NÃO** está ativo no baseline).
   - `PRAGMA foreign_keys` = **`0`** (Desativado, apesar de `projects` e `messages` definirem `FOREIGN KEY (session_id) REFERENCES sessions (id)`).
   - `PRAGMA busy_timeout` = **`5000`** (Default do driver; sem configuração explícita).
   - `PRAGMA user_version` = **`0`** (Sem versionamento de migrações); `PRAGMA schema_version` = `10` (contador interno DDL); `PRAGMA synchronous` = `2` (`FULL`); `PRAGMA integrity_check` = `ok`.
   - **Zero índices personalizados** (apenas `sqlite_autoindex_compounding_memory_1` e `sqlite_autoindex_architecture_memory_1`).
   - **Contagens verificadas por tabela:** `model_trajectories` (`1.954`), `rho_compounding_rules` (`430`), `sessions` (`317`), `projects` (`69`), `messages` (`0`), `compounding_memory` (`0`), `architecture_memory` (`0`), `engineering_decisions` (`0`), `strategic_goals` (`0`), `event_sourcing_log` (`0`).
   - **Gargalo ativo:** `backend/model_harness/rho.py:101-105` executa `SELECT COUNT(*) FROM model_trajectories WHERE task_profile = ? AND failure_reason = ? AND created_at > ?` em **full table scan** sobre `1.954` linhas.
   - **Múltiplos escritores/leitores descoordenados em `database.db`:** `database.py` (via `persistence/db.py:10-11` e `persistence/repositories/*`), `backend/model_harness/rho.py:38,75,98,122`, e `intelligence/runtime_observer.py:30` abrem conexões `sqlite3.connect` independentes sem locks inter-processo nem WAL.

2. **`state.db` de Missões (Arquitetura Já Robusta):**
   - `4` ficheiros ativos (`147.456 bytes` cada): `workspace/.jarvis/projects/aba/missions/m_61b3e665147d/state.db` e `workspace/.jarvis/projects/dina/missions/{m_2a228fb54faa,m_4448068632c3,m_f01dd44234cf}/state.db`.
   - Geridos por `agents/mission_persistence.py` (`SQLiteMissionPersistence`, `HybridMissionPersistence:176-195`) e `agents/mission_state.py` (`MissionStateManager:188-195`).
   - Configurados corretamente com `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=30000` (`timeout=30.0`), **`12` tabelas** e **`7` índices B-Tree** (`idx_wp_status`, `idx_wp_priority`, `idx_wp_parent`, `idx_wp_subdag`, `idx_deliv_wp`, `idx_ev_wp`, `idx_crit_owner`).
   - `HybridMissionPersistence` sincroniza `mission.json` (L1404-1407) e `checkpoints/checkpoint_XXXX.json` (L1447-1450) atomicamente (`.tmp.<uuid>` + `os.replace`) e `MissionMigrationEngine` (L1559-1587) cria `.backup_pre_migration_<ts>`.

3. **22 Localizações Não-Atómicas Confirmadas (8 Obsidian/Knowledge + 14 Adicionais):**
   - Stage 0 citou `8` pontos; a auditoria confirmou os `8` e identificou **+14 pontos vulneráveis** em segurança, inteligência, contexto de projeto e ferramentas de agentes que requerem migração para `atomic_write` na Stage 6.

---

## 2. Matriz Completa de Propriedade de Persistência

| Recurso / Domínio | Caminho no Disco | Formato / Esquema | Dono Atual / Escritores | Leitores Atuais | Transações / Concorrência / Atomicidade | Backup / Recuperação Atual | Dono Alvo & Etapa |
|---|---|---|---|---|---|---|---|
| **Core DB (Sessões, Projetos, Regras, Mensagens)** | `PROJECT_ROOT / "database.db"` (8 tabelas core) | SQLite (`delete`, FK OFF, `user_version=0`) | `database.py`, `persistence/repositories/*` | `server.py`, `intelligence/runtime_observer.py:30`, UI | `conn.commit()`/`close()` manual; **sem locks inter-processo, sem WAL** | Nenhum | **Abordagem C:** Python coordenado (Stages 1–3) → **Rust `SqlitePoolManager`** (Stage 4 escritor único) |
| **Model Harness Telemetry (RHO)** | `PROJECT_ROOT / "database.db"` (`model_trajectories`, `rho_compounding_rules`) | SQLite (sem índice em `model_trajectories`) | `backend/model_harness/rho.py:38,75,98,122` | `backend/model_harness/rho.py` | Conexões `sqlite3.connect` ad-hoc; colisão potencial com `database.py` | Nenhum | **Stage 1:** Script preparado e testado em sandbox cópia (dados de produção permanecem em `database.db`); **Stage 4:** Migração efetiva para `data/rho.db` sob titularidade de `ModelHarness` Python sob aprovação formal |
| **Mission State Engine** | `workspace/.jarvis/projects/<proj>/missions/<id>/state.db` | SQLite (`WAL`, FK ON, `busy_timeout=30s`, 12 tabelas, 7 índices) | `agents/mission_persistence.py`, `agents/mission_state.py` | Subagentes de missão | Transações com `BEGIN IMMEDIATE`; WAL bem configurado; `timeout=30.0` | `.backup_pre_migration_*` | **Python permanente:** mantido 100% sob `MissionWorker` Python (Approach C). Rust Core apenas observa e comanda via IPC |
| **Study Documents Metadata** | `data/study/documents.json` | JSON formatado | `backend/services/study_document_service.py` | UI, Document Library | `json.dump` síncrono ad-hoc sem lock; risco de race condition com múltiplos uploads | Nenhum | **Rust Study Store** com `atomic_write` e cache de memória em `Arc<RwLock<...>>` (Stage 5) |
| **Study Video Cache & OCR** | `data/study/videos_cache/<doc_id>/` | Ficheiros de áudio, `.vtt`, `.srt`, frames | `backend/services/video_intelligence_service.py` | UI (StudyVideoReader) | Escrita direta no filesystem local; sem locking | Nenhum | **Python Study Worker** escreve chunks; **Rust Loopback HTTP** serve stream via Range 206 (Stage 3/5) |
| **Obsidian Vault Markdown** | `obsidian_vault/**/*.md` | Ficheiros Markdown com frontmatter YAML | `obsidian_vault_service.py`, utilizador | `obsidian_graph_engine.py`, UI | 8 pontos de escrita não-atómica; risco de corrupção | Nenhum | **Python Knowledge Worker** com `NoteFileLock` e `atomic_write` obrigatório (Stage 5/6) |

---

## 3. Avaliação Comparativa de Estratégias SQLite

| Vetor de Análise | Opção A: Migração Rust Imediata (Stage 1) | Opção B: Permanecer 100% Python | Opção C: Partição por Domínio & Endurecimento Progressivo [Válida] |
|---|---|---|---|
| **Complexidade** | **Muito Alta:** exige portar todas as queries de `database.py`, `rho.py` e `runtime_observer.py` e reescrever `rho.py` para fazer IPC a cada tentativa do LLM | **Baixa:** nenhuma reescrita imediata de SQL; Rust trata apenas ciclo de vida e transporte | **Moderada e Controlada:** endurece SQLite já em Python (WAL + índices), prepara migração de `rho.db` em cópias de sandbox na Stage 1, e migra tabelas core (`sessions`, `projects`, `messages`, `rules`) para Rust Core na Stage 4 |
| **Desempenho & Latência** | **Degradação em loops LLM:** `rho.record_trajectory` e `get_compounding_rules` em `ModelHarness.execute()` passariam a pagar overhead RPC inter-processo | **Ótimo para Python**, mas impede o Rust Core de ler sessões/projetos diretamente sem pedir ao worker | **Ótimo:** `rho.db` (`WAL`) fica local ao `ModelHarness` (0 IPC no caminho quente LLM); Rust detém escrita exclusiva de `database.db` a partir da Stage 4 |
| **Integridade & Concorrência** | Alta após conclusão, mas **alto risco durante transição** se algum módulo Python ainda abrir `sqlite3.connect("database.db")` | **Frágil:** enquanto `database.py`, `rho.py` e `runtime_observer.py` abrirem conexões `delete`-mode sem lock único, o risco `SQLITE_BUSY` mantém-se | **Excelente:** `WAL` + `busy_timeout=10000` + 1 único escritor por base de dados elimina colisões de escrita descoordenada |
| **Acoplamento** | Acopla `ModelHarness` (Python) à API interna do storage Rust | Mantém acoplamento atual de UI/sessões a um processo Python único | **Desacoplado:** fronteira clara (`database.db` Core/UI ↔ `rho.db` ModelHarness ↔ `state.db` Missions) |
| **Risco de Migração** | **Alto** (refatoração massiva e regressões silenciosas nos 3.380 testes pytest) | **Baixo**, mas não resolve o problema de fundo | **Baixo / Reversível:** cada passo tem backup `.bak` e rollback limpo |

### Realidade Técnica do Concurrency no SQLite WAL
É fundamental esclarecer formalmente o comportamento de concorrência do SQLite sob o modo Write-Ahead Logging (WAL):
- **O que o WAL resolve:** O WAL permite leituras concorrentes e simultâneas sem bloqueio mútuo com uma transação de escrita ativa. Múltiplos processos ou threads podem ler snapshots consistentes enquanto um escritor está a atualizar a base.
- **O que o WAL NÃO resolve (Mito dos "100% de bloqueios eliminados"):** O SQLite impõe **estritamente um único escritor simultâneo** em todo o ficheiro de base de dados. Se duas conexões tentarem iniciar uma transação de escrita concorrente (`BEGIN IMMEDIATE`), a segunda conexão é bloqueada até que a primeira termine ou até que o `busy_timeout` (10.000 ms) seja atingido, resultando no erro `SQLITE_BUSY`.
- Além disso, operações de checkpoint do WAL (`PRAGMA wal_checkpoint`) e operações de modificação de schema (DDL) requerem bloqueios exclusivos que suspendem temporariamente tanto leitores como escritores.
- **Suíte de Testes de Concorrência Obrigatória:**
  1. *Teste de Leitores Concorrentes com Escritor Ativo:* 10 leitores simultâneos executando queries de alta frequência enquanto um escritor atualiza `model_trajectories`, garantindo zero falhas de leitura.
  2. *Teste de Transação Longa & Timeout:* Simulação de uma escrita retendo o lock por 6.000 ms; leitores continuam a responder normalmente e um segundo escritor aguarda no pool até 10.000 ms sem falhar prematuramente.
  3. *Teste de Interrupção & Crash Recovery:* Finalização abrupta (`kill -9` / `taskkill /F`) do processo durante uma escrita ativa; reabertura da base deve executar replay automático dos frames WAL válidos, com `PRAGMA integrity_check` a retornar `ok`.

---

## 4. Especificação Forense de Migração RHO (`rho.db`)

### 4.1 Limites de Execução na Stage 1
Na Stage 1:
- A base de dados de produção continua a ser `PROJECT_ROOT / "database.db"`.
- As tabelas de telemetria de produção (`model_trajectories` e `rho_compounding_rules`) **permanecem intactas em `database.db`**.
- O script `scripts/migrate_rho_db.py` é desenvolvido e testado **estritamente sobre cópias temporárias em ambiente de sandbox** (e.g. `tmp_test_rho.db`), validando:
  - Extração e carga de exatamente **1.954 registos** de `model_trajectories` e **430 regras** de `rho_compounding_rules`.
  - Checksums criptográficos SHA256 idênticos entre origem e destino.
  - Índices secundários B-Tree criados com sucesso.
  - Rollback limpo em caso de injeção de erro simulada.
- A migração física efetiva em produção para `data/rho.db` só ocorrerá na Stage 4 após aprovação formal do utilizador.

### 4.2 Schema DDL Alvo para `data/rho.db`
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 30000;
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS model_trajectories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    task_profile TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts_count INTEGER NOT NULL,
    failure_reason TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_trajectories_pattern 
    ON model_trajectories(task_profile, failure_reason, created_at);
CREATE INDEX IF NOT EXISTS idx_model_trajectories_request_id 
    ON model_trajectories(request_id);
CREATE INDEX IF NOT EXISTS idx_model_trajectories_fingerprint 
    ON model_trajectories(fingerprint);

CREATE TABLE IF NOT EXISTS rho_compounding_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_profile TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    failure_trigger TEXT NOT NULL,
    occurrences INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rho_rules_task_profile_id 
    ON rho_compounding_rules(task_profile, id DESC);
CREATE INDEX IF NOT EXISTS idx_rho_rules_trigger 
    ON rho_compounding_rules(task_profile, failure_trigger);
```

### 4.3 Baseline Empírica de Dados Preservados (Checksums Criptográficos)
- **`model_trajectories`**:
  - Contagem exata: **1.954 registos**
  - Amplitude temporal: `1787082828.9751422` a `1794492170.473098`
  - Distribuição: `SUCCEEDED` (1.036), `PROVIDER_FAILED` (784), `VALIDATION_FAILED` (90), `STOPPED` (44)
  - **Checksum SHA256:** `8fdea79a9faa2b7d9463a32928554798dbae194ae575eaf70d057d8102b5f9f1`
- **`rho_compounding_rules`**:
  - Contagem exata: **430 registos** (24 templates de regras ativas)
  - **Checksum SHA256:** `fd51ff24006ec25d94d94f2dc987ecdc0c5a6a592f4b5416ec23d289ca38f30e`

### 4.4 Protocolo Atómico de Migração em Produção (Gate da Stage 4)
Quando aprovada formalmente para execução em produção na Stage 4:
1. Snapshot físico pré-voo: `database.db.bak` com `sqlite3.backup()`.
2. Criação do esquema e índices em `data/rho.db`.
3. Bloco atómico `BEGIN EXCLUSIVE` via `ATTACH DATABASE`.
4. Cópia `INSERT INTO target_rho.model_trajectories ... SELECT ... FROM main.model_trajectories`.
5. Validação de contagens e hashes SHA256 antes do commit.
6. Atualização segura dos ponteiros de configuração do `ModelHarness`.
7. Em caso de discrepância, `ROLLBACK` atómico e restauro imediato do `.bak`.
