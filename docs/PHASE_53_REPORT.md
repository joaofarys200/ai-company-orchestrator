# JARVIS OS — Relatório Técnico Oficial: Fase 53
## Universal Project Preflight & Runtime Failure Auto-Recovery

**Data de Conclusão**: 14 de Setembro de 2026  
**Status**: Concluído com Sucesso  
**Decision Gate**: `UNIVERSAL_PROJECT_PREFLIGHT_RECOVERY_READY`  
**Browser QA**: 11/11 Cenários Aprovados no Microsoft Edge Oficial (0 Erros de Consola, 0 Falhas de Rede)  
**Suíte de Testes Unitários**: 24/24 Testes Aprovados (`tests/test_project_preflight_recovery.py`)  
**Regressão Multi-Fase**: 104/104 Testes Aprovados (Fases 40–53)  

---

### 1. Executive Summary & Epistemic Evolution

A Fase 53 introduz no JARVIS OS o subsistema definitivo de **Universal Project Preflight & Runtime Failure Auto-Recovery**. Até à Fase 52, o JARVIS possuía avançadas garantias formais de contratos comportamentais, exploração adaptativa direcionada por risco e migrações determinísticas. Contudo, ao interagir com projetos externos reais e protótipos em geração contínua (como o projeto `dina`), uma vulnerabilidade pragmática tornava-se evidente:

> **O Paradoxo do Liveness Cego**: Um processo pode ser instanciado (`process alive`), mas falhar imediatamente a nível de execução (`ReferenceError: app is not defined`, `Cannot find module`, `NameError`), sem que o sistema disponha de um mecanismo de preflight determinístico antes do start ou de auto-recuperação cirúrgica pós-crash.

A Fase 53 resolve esta vulnerabilidade através de um pipeline formal em 5 estágios:
$$\text{PREFLIGHT} \longrightarrow \text{RUN \& PROBE} \longrightarrow \text{DIAGNOSE} \longrightarrow \text{SAFE REPAIR} \longrightarrow \text{VERIFY \& ROLLBACK}$$

O sistema garante formalmente:
1. **Preflight Read-Only Invariante**: O preflight não modifica nenhum ficheiro ($\text{hash}_{\text{before}} \equiv \text{hash}_{\text{after}}$).
2. **Separação Epistêmica Fundamental**: `process_alive` $\neq$ `application_healthy`.
3. **Reparações Cirúrgicas Reversíveis**: Nenhuma alteração é aplicada sem snapshot atómico e plano de rollback preservado.
4. **Veto Soberano do Security Sentinel**: Nenhuma mutação de autenticação, código remoto malicioso ou lógica económica é permitida sem revisão humana explícita.
5. **Anti-Looping**: Tentativas de recuperação estritamente limitadas por política (máx. 3 no perfil `STANDARD`).

---

### 2. Root Cause Analysis of Unhandled Project Crashes (dina ReferenceError)

A motivação direta para a Fase 53 originou-se do projeto real `dina` (`workspace/projects/dina/app.js`), onde o script invocava:
```javascript
app.post('/ddos', (req, res) => { ... });
```
Sem que o objeto `app` tivesse sido importado ou instanciado com `express()`.

#### Falhas do Modelo Anterior:
- O orquestrador executava cegamente `node app.js` ou `npm start`.
- O processo terminava imediatamente com `ReferenceError: app is not defined`.
- O runtime tratava a saída como erro opaco de processo sem isolar o símbolo nem propor a injeção do boilerplate do Express.

#### Solução na Fase 53:
1. **Preflight Estático AST**: Deteta símbolos globais ilegítimos antes do arranque.
2. **Runtime Diagnostic Engine**: Classifica o crash em `DiagnosticErrorClass.REFERENCE_ERROR`, isola o símbolo `app`, a linha `79` e a causa raiz em menos de 0.05ms.
3. **Safe Repair Planner**: Gera um patch cirúrgico injetando `const express = require('express'); const app = express();` e middlewares de JSON.
4. **Post-Repair Verification**: Valida o ficheiro com `node --check` e sonda a porta 3000 via HTTP GET antes de declarar sucesso.

---

### 3. Architecture of Universal Project Preflight (22 Submodules)

O subsistema foi desenhado modularmente em `agents/project_preflight/` e espelhado em `backend/agents/project_preflight/`:

| Submódulo | Responsabilidade Principal |
| :--- | :--- |
| `models.py` | Modelos de dados, Enums de severidade, `RuntimeDiagnostic`, `RepairPlan`, `RecoveryRun`. |
| `language.py` | Tabelas de símbolos legítimos para Node.js, Browsers e Python. |
| `detector.py` | Deteção heurística de linguagem, package manager, portas e entrypoints. |
| `javascript.py` | Analisador pré-execução de ficheiros JavaScript via AST seguro. |
| `typescript.py` | Validador de `tsconfig.json` e entrypoints TypeScript. |
| `python.py` | Validador de scripts Python via `py_compile` e inspeção de AST. |
| `node.py` | Verificador de ferramentas e binários do ambiente Node.js. |
| `dependencies.py` | Validação de manifestos (`package.json`, `requirements.txt`) vs pacotes instalados. |
| `entrypoint.py` | Verificação de existência e permissões de leitura do entrypoint. |
| `config.py` | Validação de portas e conflitos de socket (`EADDRINUSE`). |
| `healthcheck.py` | Sonda ativa de saúde funcional (sockets e requisições HTTP GET). |
| `diagnostics.py` | Motor de parsing e classificação estruturada de stack traces. |
| `confidence.py` | Classificador de confiança de evidência (`HIGH`, `MEDIUM`, `LOW`). |
| `repair.py` | Planeador atómico de reparações cirúrgicas e snapshots reversíveis. |
| `policy.py` | Avaliador de gates e limites máximos de tentativas de recuperação. |
| `security.py` | Sentinela soberano de segurança contra poisoning e mutações não autorizadas. |
| `metrics.py` | Emissor de telemetria, eventos de auditoria e métricas de latência. |
| `cache.py` | Cache determinístico de fingerprints de erro e histórico de reparações. |
| `validator.py` | Validador de gates de pré-voo e prova de smoke comportamental pós-reparação. |
| `index.py` | Repositório em memória e ledger de perfis, preflights e reparações. |
| `bridge.py` | Orquestrador mestre integrando todo o ciclo de vida. |
| `__init__.py` | Manifesto do pacote e exportações públicas. |

---

### 4. Runtime Profiling & Heuristic Project Detection

O detetor inspeciona a estrutura do diretório do projeto e infere:
- **Linguagem**: `JAVASCRIPT`, `TYPESCRIPT`, `PYTHON`, `HTML_STATIC`.
- **Runtime**: `NODE_CJS`, `NODE_ESM`, `PYTHON_3`, `BROWSER_ONLY`.
- **Package Manager**: `npm`, `yarn`, `pnpm`, `pip`, `poetry`.
- **Entrypoint**: Deteção automática via campo `main` ou busca sequencial em `app.js`, `server.js`, `index.js`, `main.py`, `app.py`.
- **Porta**: Resolução hierárquica a partir do ficheiro de configuração, variáveis de ambiente ou porta padrão (3000, 5173, 8000).

---

### 5. Language Syntax & Abstract Syntax Tree Preflight Analyzers

Para evitar arranque de scripts com erros triviais de sintaxe:
- **JavaScript**: Validação via AST seguro verificando que chamadas estruturais como `app.post` possuem a instância correspondente no escopo.
- **Python**: Execução de `py_compile.compile(doraise=True)` garantindo compilação a bytecode e captura imediata de `SyntaxError` com número de linha e coluna.

---

### 6. Node.js & CommonJS/ESM Execution Boundary

Garante compatibilidade de módulos:
- Distinção clara entre projetos CommonJS (`require`) e ESM (`"type": "module"` / `import`).
- Prevenção de conflitos onde `require()` é utilizado em projetos ESM sem transpile ou onde `import` é invocado em ambientes CJS estritos.

---

### 7. Python Virtualenv & Module Load Preflight

- Verificação de isolamento virtual (`venv/` ou `.venv/`).
- Deteção de bibliotecas essenciais declaradas em `requirements.txt` que não estejam importáveis no interpretador local.

---

### 8. Dependency Validation & Manifest Integrity (Zero Blind Installs)

**Regra Estrita**: O JARVIS nunca executa `npm install <arbitrary>` ou `pip install` cegamente sem política autorizada.
- Compara dependências declaradas em `package.json` com o diretório físico `node_modules`.
- Em caso de discrepância, emite `PreflightIssue` com severidade `BLOCKER` e propõe a ação sugerida.

---

### 9. Entrypoint Resolution & Execution Target Verification

- Valida a presença física do ficheiro indicado no manifesto antes de disparar qualquer subprocesso.
- Confirma que o script `start`, `dev` ou `serve` existe em `package.json.scripts`.

---

### 10. Configuration & Socket Availability Probing

- Verifica que a porta pretendida (ex: 3000) está livre no loopback local.
- Se a porta já estiver em uso, emite aviso prévio evitando o crash por `EADDRINUSE`.

---

### 11. Functional Readiness vs Process Liveness (Startup Healthcheck)

O subsistema consagra a distinção crítica:
- **Process Alive**: O processo do sistema operativo está na tabela de processos (`poll() is None`).
- **Application Healthy**: O socket está aberto, aceita conexões TCP e responde com código HTTP válido (< 500) a um pedido GET com latência quantificada.

---

### 12. Crash Classifier & Deterministic Symbol Diagnostic Engine

Em caso de crash do processo, o `RuntimeDiagnosticEngine` aplica regex determinístico de alta precisão sobre o log de erro:
- Extrai símbolo causador, ficheiro, linha e coluna.
- Gera um `diagnostic_id` único baseado no hash determinístico SHA-256 do erro:
$$\text{diag\_id} = \text{SHA256}(\text{error\_class} \parallel \text{symbol} \parallel \text{file} \parallel \text{line})$$

---

### 13. ReferenceError & Undeclared Global Recovery Taxonomy

O catálogo de ReferenceErrors mapeia símbolos canónicos:
- `app` $\longrightarrow$ Falta de inicialização do servidor Express.
- `axios` $\longrightarrow$ Falta de `require('axios')`.
- `path`, `fs` $\longrightarrow$ Módulos nativos do Node.js não importados.
- Símbolos desconhecidos $\longrightarrow$ Classificados como `LOW_CONFIDENCE` e bloqueados para auto-reparação arbitrária.

---

### 14. Missing Module & Dependency Resolution Protocols

- Erros `Cannot find module 'X'` são correlacionados com o `package.json`.
- A reparação propõe a declaração no manifesto sob aprovação ou verificação de integridade do lockfile.

---

### 15. Safe Atomic Repair Planner & Minimal Patch Generation

O `SafeRepairPlanner` produz apenas patches cirúrgicos e mínimos. É expressamente proibida a reescrita arbitrária de código (`arbitrary code rewrite`). O patch especifica:
- `relative_path`
- `original_content`
- `patched_content`
- `reason`

---

### 16. Non-Destructive Snapshotting & Reversible Rollback Lineage

Antes de gravar qualquer modificação no disco:
1. Um snapshot integral dos ficheiros alvo é armazenado em memória.
2. Em caso de falha no preflight pós-patch ou no healthcheck, o método `rollback_repair` restaura o conteúdo original byte a byte.
3. A linhagem do rollback é registada no `RecoveryRun` e no Ledger de auditoria.

---

### 17. Multi-Level Recovery Confidence (High / Medium / Low)

| Nível de Confiança | Critérios | Auto-Repair Permitido? |
| :--- | :--- | :--- |
| `HIGH_CONFIDENCE` | Símbolo canónico conhecido, alvo único determinístico, score $\ge 0.90$. | Sim (sob política `STANDARD`) |
| `MEDIUM_CONFIDENCE` | Categoria clara, ficheiro identificado, score $\ge 0.70$, ligeira ambiguidade. | Requer Revisão Humana |
| `LOW_CONFIDENCE` | Símbolo arbitrário desconhecido, múltiplos ficheiros candidatos. | **Estritamente Bloqueado** |

---

### 18. Recovery Authorization Policies & Human Review Thresholds

- `STANDARD`: Auto-reparação autorizada apenas para `HIGH_CONFIDENCE` (máx. 3 tentativas).
- `STRICT`: Avisos requerem revisão humana (máx. 2 tentativas).
- `CRITICAL`: Tolerância zero a mutações automáticas; toda alteração de código requer aprovação explícita.
- `ECONOMIC_CRITICAL`: Bloqueio de qualquer mutação que toque em montantes, moedas ou contabilidade.
- `SECURITY_CRITICAL`: Bloqueio de qualquer mutação que altere autenticação ou privilégios.

---

### 19. Anti-Loop Retry Bounds & Cascading Failure Suppression

Para impedir loops infinitos de reparação e crash:
- O número de tentativas é estritamente contabilizado por projeto (`attempt_number`).
- Se `attempt_number > max_recovery_attempts`, o gate emite `PreflightGateDecision.EXECUTION_BLOCKED` e o processo é suspenso para intervenção humana.

---

### 20. Security Sentinel Sovereign Authority & Veto Rules

O `PreflightSecuritySentinel` detém autoridade suprema e inspeciona todos os planos de reparação antes da sua aplicação física:
- **Vetado**: Injeção de URLs remotas em scripts (`http://`, `.sh`, `.exe`).
- **Vetado**: Injeção de `eval()` ou comandos `child_process.exec()` não autorizados.
- **Vetado**: Pacotes maliciosos adicionados ao `package.json` (`package poisoning`).

---

### 21. Economic Invariant Safeguards & Financial Logic Freezing

Em projetos com operações económicas:
- O Sentinel inspeciona padrões como `amount =`, `currency =`, `ledger`, `refund`.
- Qualquer alteração a estas linhas sem aprovação humana direta resulta em `SecurityVetoError` imediato.

---

### 22. Deterministic Failure Fingerprinting & Deduplication

Cada crash gera uma impressão digital normalizada:
$$\text{Fingerprint} = \text{SHA256}(\text{runtime} \parallel \text{error\_class} \parallel \text{file} \parallel \text{line} \parallel \text{symbol})$$
Permite deduplicação em tempo real de crashes repetidos e correlação imediata no histórico.

---

### 23. Consultive Experience Memory ("Memory is Not Authority")

O `DeterministicFailureCache` armazena reparações bem sucedidas do passado:
- A memória serve de **aceleração heurística consultiva**, mas nunca de autoridade.
- Qualquer reparação recuperada da memória tem obrigatoriamente de passar pela validação de preflight estático e de segurança antes de ser executada.

---

### 24. Browser QA Methodology & Microsoft Edge Test Suite

A automação de interface executou o binário oficial do Microsoft Edge (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`) através do Playwright, acedendo à aplicação em `http://127.0.0.1:5173`.
- Resolução de ecrã: 1920x1080.
- Tolerância: 0 erros de consola e 0 falhas de rede.
- Captura de 11 cenários oficiais de alta resolução.

---

### 25. 11 Real Browser QA Validation Scenarios

| # | Cenário | Descrição e Validação |
| :---: | :--- | :--- |
| **01** | `01_preflight_recovery_overview.png` | Mission Control Center com a nova aba da Fase 53 visível e selecionada. |
| **02** | `02_project_runtime_profile.png` | Faixa de perfil de runtime (dina, Node.js CJS, porta 3000, npm, package.json). |
| **03** | `03_read_only_preflight_inspection.png` | Tabela de inspeção read-only com verificação de invariância de hash. |
| **04** | `04_runtime_crash_diagnostic.png` | Cartão estruturado de crash exibindo `ReferenceError: app is not defined`. |
| **05** | `05_safe_repair_plan_view.png` | Visualização do patch atómico com Express boilerplate e diff cirúrgico. |
| **06** | `06_supervised_auto_recovery_execution.png` | Auto-Recovery supervisionado exibindo `GATE_CLEARED` e snapshot atómico. |
| **07** | `07_active_healthcheck_probe.png` | Sondagem ativa de saúde HTTP 200 OK na porta 3000 com latência de 1.9ms. |
| **08** | `08_repair_rollback_demonstration.png` | Acionamento de reversão atómica restaurando o snapshot original (`ROLLED_BACK`). |
| **09** | `09_re_apply_and_verify.png` | Re-aplicação da reparação com verificação pós-patch aprovada. |
| **10** | `10_security_sentinel_policy_matrix.png` | Matriz de soberania do Security Sentinel e limites de tentativas. |
| **11** | `11_finish_gate_cleared.png` | Estado consolidado com verificação aprovada para o Finish Gate. |

---

### 26. Microbenchmark Latency & Performance Scalability (50+ Runs)

Resultados extraídos de 50 execuções completas de microbenchmarks (`docs/phase53_performance.json`):

| Operação | Latência Média | Latência Mínima | Latência Máxima |
| :--- | :---: | :---: | :---: |
| **Preflight Read-Only Completo** | 340.42 ms | 315.10 ms | 388.20 ms |
| **Diagnóstico Estruturado de Crash** | 0.04 ms | 0.02 ms | 0.25 ms |
| **Planeamento & Aplicação de Reparação**| 0.04 ms | 0.03 ms | 0.22 ms |
| **Tempo até ao Primeiro Diagnóstico** | 0.25 ms | — | — |

---

### 27. Real Corpus Evaluation & Verification Ledger

A avaliação contra o corpus real de falhas gerou os 6 ficheiros canónicos em `docs/`:
- `docs/phase53_project_profiles.json` (Perfis de projetos analisados).
- `docs/phase53_preflight_results.json` (Resultados das validações pré-execução).
- `docs/phase53_diagnostics.json` (Diagnósticos estruturados de crashes).
- `docs/phase53_repair_plans.json` (Planos de reparação com diffs cirúrgicos).
- `docs/phase53_recovery_runs.json` (Registos de execução e auditoria de recuperação).
- `docs/phase53_verification_ledger.json` (Ledger consolidado com declaração de gate).

---

### 28. First Implementation Failure & Root Cause Diagnostic

Durante a execução da suíte de testes e automação, foram diagnosticadas e resolvidas duas falhas de implementação:
1. **Expressão Regular EADDRINUSE com Espaçamento**: O formato de saída do log `::: 3000` continha múltiplos espaços após os dois pontos. A regex `EADDRINUSE.*:(\d+)` falhava e foi corrigida para `EADDRINUSE.*:+\s*(\d+)`.
2. **Veto Económico em Ficheiros Pré-existentes**: O filtro do Sentinel verificava apenas se o padrão económico era novo no patch; contudo, quando uma linha económica pré-existente era alterada (`original != patched`), o teste falhava. A regra foi endurecida para vetar qualquer mutação onde `is_economic=True` e `original_content != patched_content`.

---

### 29. First Real Limit & Epistemic Calibration

- **Limite Físico dos Símbolos Não Declarados**: Se o código invocar uma variável `fooBar()` sem qualquer pista semântica no projeto, manifesto ou contexto, o sistema **recusa-se a inventar uma função arbitrária**. O diagnóstico classifica o símbolo como `UNRESOLVED_SYMBOL`, atribuindo `LOW_CONFIDENCE` e exigindo intervenção humana.
- **Calibração Epistêmica**: O JARVIS nunca converte a ausência de erro em garantia absoluta de que a lógica de negócio está correta; apenas garante sanidade estrutural, arranque limpo e resposta HTTP do endpoint.

---

### 30. Comparison With Industry State-of-the-Art

| Capacidade | Turborepo / Nx | PM2 / Nodemon | Next.js / Vite | **JARVIS Fase 53** |
| :--- | :---: | :---: | :---: | :---: |
| Preflight Read-Only Estático | Parcial | Não | Parcial | **Sim (com hash invariante)** |
| Classificação Estruturada de Crash | Não | Não | Limitada | **Sim (AST + Regex Determinístico)** |
| Safe Atomic Repair com Snapshot | Não | Não | Não | **Sim (Reversível byte a byte)** |
| Veto Soberano de Segurança | Não | Não | Não | **Sim (Security Sentinel)** |
| Distinção Process Alive vs Healthy | Não | Limitada | Não | **Sim (Healthcheck TCP/HTTP GET)** |

---

### 31. Zero False Success & Epistemic Calibration Proof

O sistema rejeita categorized False Successes:
1. Se o processo arrancar mas o socket não abrir em 5 segundos $\implies$ `StartupHealthResult(ready=False)`.
2. Se o socket abrir mas a rota devolver status 500 $\implies$ `StartupHealthResult(ready=False)`.
3. Se a reparação for aplicada mas o teste de sintaxe `node --check` falhar $\implies$ `rollback_repair()` imediato.

---

### 32. Mathematical Invariants & State Transition Formalism

O ciclo de vida obedece aos seguintes invariantes formais:

$$\forall \text{ preflight}: \quad \mathcal{H}(\text{workspace}_{\text{before}}) = \mathcal{H}(\text{workspace}_{\text{after}})$$

$$\text{Auto-Repair Autorizado} \iff \big(\text{confidence} = \text{HIGH}\big) \land \big(\text{attempt} \le 3\big) \land \big(\text{Sentinel\_Veto} = \emptyset\big)$$

$$\text{Post-Repair Failure} \implies \text{Rollback}(\text{snapshot}) \land \text{State} \equiv \text{Original}$$

---

### 33. Observability & Event Telemetry Schema

Todos os eventos contêm:
```json
{
  "event_name": "repair_applied",
  "phase": 53,
  "project_id": "dina",
  "repair_id": "rep_dina_express_app",
  "confidence": "HIGH_CONFIDENCE",
  "risk": 0.10,
  "timestamp": 1726330000.0,
  "provenance": { ... }
}
```

---

### 34. Operator Runbook: Diagnosing & Recovering Third-Party Repositories

1. **Inspeção Inicial**: Execute `bridge.run_preflight(project_dir)`. Verifique a lista de `PreflightIssue`.
2. **Em caso de crash**: Capture as linhas de stderr e invoque `bridge.diagnose_failure(logs, project_dir)`.
3. **Avaliação do Plano**: Inspecione o `RepairPlan.file_patches` e confirme o nível de confiança.
4. **Aplicação com Garantia**: Invoque `bridge.plan_and_apply_recovery()`. Em caso de anomalia, execute `bridge.repair_planner.rollback_repair()`.

---

### 35. Decision Gate Declaration

Declaramos formalmente atingido o marco:

```
================================================================================
GATE STATUS: [UNIVERSAL_PROJECT_PREFLIGHT_RECOVERY_READY]
Todos os 24 testes unitários da Fase 53 passaram com sucesso.
Regressão multi-fase (Fases 40-53): 104 testes aprovados (100%).
Browser QA no Microsoft Edge: 11/11 cenários aprovados com 0 erros de consola.
Artifacts de desempenho, diagnóstico, perfis e ledger gerados em docs/.
================================================================================
```
