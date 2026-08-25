# JARVIS OS — Security Sentinel
# Fase S3: Política de Resposta & Contenção Defensiva

## 1. Princípio Fundamental
O Security Sentinel **nunca** executa respostas autónomas ou mutações no sistema sem autorização humana explícita. O fluxo operacional obedece estritamente ao pipeline:

$$\text{OBSERVE} \to \text{DETECT} \to \text{CORRELATE} \to \text{EXPLAIN} \to \text{RECOMMEND} \to \mathbf{HUMAN\ APPROVAL} \to \text{EXECUTE} \to \text{VERIFY} \to \text{RECORD} \to \text{ROLLBACK}$$

## 2. Níveis de Permissão (Permission Levels)
A política de segurança da Fase S3 classifica todas as ações em quatro níveis:

| Nível | Descrição | Estado na Fase S3 |
|---|---|---|
| `READ_ONLY` | Coleta e auditoria de telemetria passiva | **Permitido** |
| `LOW_RISK_MUTATION` | Mutações cirúrgicas, isoladas e reversíveis | **Permitido sob Aprovação Humana** |
| `HIGH_RISK_MUTATION` | Modificações em chaves de sistema, drivers ou ficheiros globais | **Bloqueado Estritamente** |
| `CRITICAL_MUTATION` | Exclusão permanente de dados, formatação ou operações destrutivas | **Bloqueado Estritamente** |

## 3. Ações de Resposta Autorizadas na Fase S3
1. **`TERMINATE_PROCESS` (Finalização de Processo)**:
   - Restrito a processos em espaço de utilizador (userland).
   - Processos essenciais do Windows (`system`, `csrss.exe`, `explorer.exe`, `lsass.exe`, `services.exe`, `svchost.exe`, etc.) e processos do JARVIS são estritamente protegidos.
   - Não-reversível (`rollback_available=False`).

2. **`DISABLE_SCHEDULED_TASK` (Desativação de Tarefa Agendada)**:
   - Apenas desativa tarefas via `schtasks /Change /TN <nome> /DISABLE`.
   - É **proibida** a exclusão de tarefas agendadas.
   - Reversível via reativação da tarefa (`/ENABLE`).

3. **`BLOCK_NETWORK_ENDPOINT` (Bloqueio de Endpoint de Rede)**:
   - Cria regras isoladas na Windows Firewall com o prefixo restrito `JARVIS-SENTINEL-{ACTION_ID}`.
   - Reversível via remoção exclusiva da regra criada, sem tocar em regras pré-existentes.

4. **`QUARANTINE_FILE` (Quarentena de Ficheiro)**:
   - Move o ficheiro para o diretório isolado `sentinel/quarantine/` com metadados JSON e cálculo de hash SHA-256.
   - Protege diretórios críticos do SO (`C:\Windows`, `C:\Windows\System32`, `C:\Program Files`).
   - Reversível via restauração exata para o caminho de origem.

5. **`MARK_KNOWN_GOOD` (Registo como Benigno)**:
   - Regista itens benignos com justificação humana e data de revisão (máx. 30 dias).
   - Reversível via remoção do registo.

## 4. Requisitos de Autenticação da Aprovação
Nenhuma aprovação é aceite sem:
- `user`: Identificador do operador humano autenticado.
- `session_id`: Sessão ativa autenticada no WebSocket/IPC.
- `action_id`: Identificador único da proposta.
- `incident_id`: Identificador do incidente correlacionado (proteção contra replay e falsificação).
