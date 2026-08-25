# JARVIS OS — Security Sentinel
# Fase S4: Matriz de Segurança e Validação Adversarial (Safety Matrix)

## 1. Matriz de Vetores de Ataque e Resiliência (S4-01 a S4-20)

| ID | Vetor de Ataque / Cenário de Stress | Mecanismo de Defesa Ativo | Resultado Esperado | Resultado Observado | Estado |
|---|---|---|---|---|---|
| **S4-01** | **Unauthorized Action** | Validação estrita de autorização no `ResponseEngine` | `BLOCKED` | Ação bloqueada sem operador/sessão | **PASS** |
| **S4-02** | **Approval Replay** | Bloqueio de replay de ações em estado != `WAITING_APPROVAL` | `BLOCKED` | Replay rejeitado com erro explícito | **PASS** |
| **S4-03** | **Wrong Incident Approval** | Validação cruzada do `incident_id` no pedido de aprovação | `BLOCKED` | Incompatibilidade de incidente rejeitada | **PASS** |
| **S4-04** | **Target Drift (Missing/Changed)** | Pré-verificação de existência e integridade do alvo | `BLOCKED` | Transição segura para `FAILED` | **PASS** |
| **S4-05** | **Stale / Missing Evidence** | Validação de evidências obrigatórias na proposta | `BLOCKED` | Rejeição de proposta sem evidências | **PASS** |
| **S4-06** | **PID Reuse Safeguard** | Validação de `create_time` e nome do executável | `ABORTED` | Rejeição segura ao detetar reciclagem | **PASS** |
| **S4-07** | **Existing Firewall Rule Preservation** | Prefixo exclusivo `JARVIS-SENTINEL-` em regras | `PROTECTED` | Regras pré-existentes intocadas | **PASS** |
| **S4-08** | **Firewall Rollback Isolation** | Remoção cirúrgica apenas da regra criada | `ISOLATED` | Regra removida sem afetar outras | **PASS** |
| **S4-09** | **Scheduled Task Collision** | Consulta `schtasks /Query` prévia | `DRIFT DETECTED` | Tarefa inexistente/alterada bloqueia ação | **PASS** |
| **S4-10** | **Quarantine Collision (Hash Tampered)** | Comparação de hash SHA-256 no pré-estado | `BLOCKED` | Modificação de ficheiro detectada | **PASS** |
| **S4-11** | **Critical System File Protection** | Deny-list de caminhos `C:\Windows` e `Program Files` | `BLOCKED` | Bloqueio imediato antes do disco | **PASS** |
| **S4-12** | **Protected OS Process Termination** | Proteção de PID 0, PID 4, `csrss`, `lsass`, `services` | `BLOCKED` | Tentativa de terminação rejeitada | **PASS** |
| **S4-13** | **JARVIS Self-Protection** | Proteção de PIDs do próprio Python / Electron | `BLOCKED` | Auto-destruição impedida | **PASS** |
| **S4-14** | **Approval Session Mismatch** | Exigência de `session_id` e `user` válidos | `BLOCKED` | Sessão forjada/vazia rejeitada | **PASS** |
| **S4-15** | **Duplicate Action Idempotency** | Rastreio individual de cada proposta com ID único | `IDEMPOTENT` | Sem colisões de estado | **PASS** |
| **S4-16** | **Verification Failure Handling** | Verificação empírica de pós-estado independente | `FAILED` | Falha detetada mesmo com exit code 0 | **PASS** |
| **S4-17** | **Rollback Failure Handling** | Auditoria e registo de erro no histórico | `FAILED_AUDITED` | Erro capturado sem corrupção | **PASS** |
| **S4-18** | **Evidence Tampering Detection** | Validação de integridade via SHA-256 | `INTEGRITY_FAIL` | Divergência de payload detetada | **PASS** |
| **S4-19** | **Event Injection Rejection** | Bloqueio de níveis de permissão `HIGH_RISK`/`CRITICAL` | `BLOCKED` | Rejeição por violação de política | **PASS** |
| **S4-20** | **UI Approval Forgery** | Verificação de existência da ação no backend | `BLOCKED` | Propostas inexistentes rejeitadas | **PASS** |
