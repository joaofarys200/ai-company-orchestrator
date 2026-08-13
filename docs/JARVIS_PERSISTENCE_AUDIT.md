# 💾 JARVIS OS — PERSISTENCE & STATE DEEP AUDIT

**Data**: 2026-08-13  
**Foco**: Mapeamento e auditoria exaustiva de todos os mecanismos de persistência no repositório.

---

## 1. 🗄️ MAPA DE ARMAZENAMENTOS PERSISTENTES

| Armazenamento | Tipo | Ficheiro / Caminho | Schema / Formato | Concorrência / Locks | Risco de Corrupção |
|---|---|---|---|---|---|
| **Mission State** | JSON + JSONL | `workspace/.jarvis/missions/{proj}/{id}/` | Dataclasses `Mission`, `WorkPackage`, `Deliverable`, `Evidence` | File lock via `_locked_mission` + Optimistic Versioning | **Muito Baixo** (Isolamento por ficheiro e append-only events) |
| **RHO Trajectories** | SQLite | `config/rho.sqlite` | `model_trajectories`, `compounding_rules` | Conexões context manager `sqlite3.connect()` com WAL | **Muito Baixo** (Transacional ACID) |
| **Leads Gateway** | SQLite | `config/leads.sqlite` | `captured_leads` (`id`, `mission_id`, `email`, `is_converted`) | Context manager transacional | **Muito Baixo** (Transacional ACID) |
| **Payments Gateway** | SQLite | `config/payments.sqlite` | `payment_events` (`id`, `mission_id`, `amount_usd`, `signature`) | Context manager transacional com unicidade em `transaction_id` | **Muito Baixo** (Transacional ACID) |
| **Project Symbols** | JSON | `symbols_index.json` | Dicionário de símbolos AST extraídos pelo Tree-sitter | Escrita atómica no fim da indexação | **Baixo** (Regerável a qualquer momento a partir do código) |
| **Coding Backups** | Ficheiros | `.jarvis_backup/` | Cópia raw de ficheiros antes de modificação pelo `PatchEngine` | Nomenclatura baseada em timestamp e hash | **Zero** (Imutável após criação) |
| **Knowledge Vault** | Markdown | `obsidian_vault/` | Ficheiros `.md` de texto estruturado | Read-only pelo RAG em tempo de execução | **Zero** (Não versionado no Git por diretiva) |

---

## 2. 📋 RESPOSTAS ÀS 15 QUESTÕES DE AUDITORIA DE PERSISTÊNCIA

1. **Quem escreve?**: Cada subsistema escreve apenas no seu domínio (MissionStore em missões, Gateway em leads/pagamentos, RHO em telemetria).
2. **Quem lê?**: Os runners, executores e serviços de analytics através de APIs especializadas.
3. **Qual é o schema?**: Esquemas formais em Dataclasses tipadas (JSON) e DDL explícito com tipos e constraints (SQLite).
4. **Existe versionamento?**: Sim. As entidades de missão possuem o campo `version: int` incrementado a cada mutação.
5. **Existe migração?**: As tabelas SQLite usam `CREATE TABLE IF NOT EXISTS`; migrações de missão usam deserialização tolerante com valores padrão.
6. **Existe concorrência?**: Sim, gerida por bloqueios de ficheiro no MissionStore e transações ACID no SQLite.
7. **Existem race conditions?**: Mitigadas pelo `expected_version` que lança `StaleVersionError` se houver mutação concorrente.
8. **Existem operações não atómicas?**: A escrita de entidades em JSON é feita ficheiro a ficheiro; recomenda-se unificar em transação em memória para pacotes complexos.
9. **Existe risco de corrupção?**: Muito baixo. SQLite possui journaling WAL e os ficheiros JSON são pequenos e formatados de forma padronizada.
10. **Existe perda de estado depois de crash?**: O estado é gravado antes e depois de cada transição de work package.
11. **Existe recovery depois de restart?**: Sim. As missões podem ser recarregadas via `load_mission()`. Recomenda-se adicionar watchdog para desmarcar pacotes órfãos em `IN_PROGRESS`.
12. **Existe duplicação de estado?**: Não. O `MissionStateStore` é a fonte única de verdade para o plano de trabalho.
13. **Existe source of truth único?**: Sim, segregado por responsabilidade clara.
14. **É possível reconstruir o estado a partir dos eventos?**: Sim, através do ficheiro de auditoria `events.jsonl`.
15. **Existem estados impossíveis/inconsistentes?**: O `MissionStateStore` valida rigorosamente a máquina de estados através de matrizes de transição permitidas (`MISSION_TRANSITIONS`, `WORK_PACKAGE_TRANSITIONS`).
