# JARVIS OS — Security Sentinel
# Fase S4: Relatório de Ameaças e Vulnerabilidades (Threat Findings)

## 1. Escopo da Avaliação de Ameaças
A auditoria adversarial da Fase S4 avaliou os limites de segurança da arquitetura do Sentinel sob o modelo de ameaças STRIDE e cenários específicos de abuso.

## 2. Findings da Auditoria Adversarial

### FINDING-S4-01: Tentativa de Ação Mutativa Não Autorizada
- **Classificação**: Baixa Severidade (Mitigada)
- **Vetor**: Invocação de métodos de resposta sem contexto autenticado de utilizador ou sessão.
- **Defesa**: O `ResponseEngine` valida estritamente a presença de `user` e `session_id`. Pedidos anónimos são rejeitados com `403/Forbidden` e transição bloqueada.

### FINDING-S4-02: Replay de Aprovação de Incidentes
- **Classificação**: Média Severidade (Mitigada)
- **Vetor**: Reutilização de tokens de aprovação para reexecutar ações antigas.
- **Defesa**: O `ResponseEngine` apenas aceita aprovações para ações no estado estrito `WAITING_APPROVAL`. Qualquer ação em estado `COMPLETED`, `EXECUTING`, `FAILED` ou `REJECTED` bloqueia tentativas de replay.

### FINDING-S4-03: TOCTOU & Target Drift (Substituição de Alvo)
- **Classificação**: Alta Severidade (Mitigada)
- **Vetor**: Alteração do alvo (PID reciclado por novo processo ou ficheiro modificado com novo conteúdo) no intervalo entre a proposta (`PROPOSED`) e a execução (`EXECUTING`).
- **Defesa**: Todos os executores executam um `pre_check` síncrono e atómico que valida:
  - Para processos: `pid`, `create_time`, `exe_path` e nome.
  - Para ficheiros: caminho absoluto, existência e hash criptográfico `SHA-256`.
  - Para tarefas agendadas: consulta de estado no subsistema do Windows.
  Se houver discrepância em relação ao `pre_state` capturado no momento da proposta, a ação falha com `Target Drift Detected` e nenhuma mutação é aplicada.

### FINDING-S4-04: Violação de Limites do Sistema Operativo
- **Classificação**: Crítica (Mitigada)
- **Vetor**: Tentativa de quarentenar arquivos vitais de `C:\Windows` ou finalizar processos do kernel (`System Idle / PID 0`, `System / PID 4`, `csrss.exe`, `explorer.exe`).
- **Defesa**: Os executores implementam listas de negação estritas de caminhos de sistema e nomes de processos protegidos. As tentativas são rejeitadas imediatamente no `pre_check`.

### FINDING-S4-05: Falsificação de Sucesso de Executores (Exit Code 0 Falso)
- **Classificação**: Média Severidade (Mitigada)
- **Vetor**: Utilitários do sistema retornando exit code 0 sem aplicar a mutação desejada.
- **Defesa**: Verificação empírica de pós-estado obrigatória e independente (consulta de tabela de processos no kernel, regras de firewall ativas e integridade do arquivo em quarentena). Ações só transitam para `COMPLETED` após confirmação do pós-estado.
