# JARVIS OS — Security Sentinel
# Fase S3: Verificação Empírica de Pós-Estado (Post-State Verification)

## 1. Princípio: Exit Code 0 Nunca é Suficiente
Muitos utilitários de sistema e scripts reportam código de saída 0 mesmo quando a operação falha silenciosamente, cria condições de corrida ou é bloqueada por software de terceiros. Por essa razão, o Sentinel impõe **verificação empírica de pós-estado** obrigatória antes de transitar qualquer ação para `COMPLETED`.

## 2. Protocolo de Verificação por Tipo de Ação

### 1. `TERMINATE_PROCESS`
- **Método de Execução**: `psutil.Process(pid).terminate()` / `kill()`.
- **Verificação Empírica**:
  - Consulta a tabela de processos do kernel do Windows via `psutil.pid_exists(pid)`.
  - Se o PID ainda existir, verifica `create_time` para confirmar que não se trata do mesmo processo.
  - Se o PID ainda existir com os mesmos atributos, a verificação falha e o estado passa para `FAILED`.

### 2. `DISABLE_SCHEDULED_TASK`
- **Método de Execução**: `schtasks.exe /Change /TN <task_name> /DISABLE`.
- **Verificação Empírica**:
  - Executa consulta independente `schtasks.exe /Query /TN <task_name> /FO LIST /V`.
  - Realiza parsing do campo `Status` confirmando `Disabled` / `Desativada`.
  - Se o estado não for `Disabled`, a verificação falha.

### 3. `BLOCK_NETWORK_ENDPOINT`
- **Método de Execução**: `netsh.exe advfirewall firewall add rule name="JARVIS-SENTINEL-<ACTION_ID>" dir=out action=block remoteip=<IP>`.
- **Verificação Empírica**:
  - Consulta direta via `netsh.exe advfirewall firewall show rule name="JARVIS-SENTINEL-<ACTION_ID>"`.
  - Valida que a regra específica existe, está ativa e associada aos perfis corretos.

### 4. `QUARANTINE_FILE`
- **Método de Execução**: Movimento atómico de ficheiro para `sentinel/quarantine/<action_id>/`.
- **Verificação Empírica**:
  1. `os.path.exists(original_path)` deve ser estritamente `False` (ficheiro removido do ponto de origem).
  2. `os.path.isfile(quarantine_path)` deve ser estritamente `True`.
  3. Cálculo de SHA-256 do ficheiro na quarentena deve coincidir bit a bit com o hash original registado na pré-captura.

### 5. `MARK_KNOWN_GOOD`
- **Método de Execução**: Registo no banco JSON de exclusões conhecidas com data de revisão (30 dias).
- **Verificação Empírica**:
  - Validação de presença da chave no armazenamento e validação de schema.
