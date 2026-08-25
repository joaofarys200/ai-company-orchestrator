# JARVIS OS — Security Sentinel Response Policy

## 1. Regra Absoluta de Não-Destrutividade
1. Na **Fase S1**, o Sentinel opera exclusivamente em modo **READ-ONLY**.
2. Quaisquer ações de contenção ou resposta mutativa (ex.: terminar PIDs, remover tarefas agendadas, bloquear IPs na Firewall) são estritamente proibidas em S1 e requerem **Aprovação Humana Explícita** nas fases subsequentes (S6+).

---

## 2. Categorias de Ação

### Ações Automáticas Seguras (`SAFE_AUTOMATIC`)
- Recolher evidência do processo (PID, hash, linha de comando);
- Calcular hash SHA-256 de ficheiros;
- Registar eventos de telemetria no histórico local;
- Gerar relatório Markdown de auditoria;
- Emitir alerta no dashboard do utilizador.

### Ações que Exigem Aprovação Humana (`APPROVAL_REQUIRED`)
- Terminar um processo (`kill_process`);
- Desativar ou eliminar uma tarefa agendada (`disable_scheduled_task`);
- Desativar um serviço suspeito (`disable_service`);
- Bloquear um endereço IP na Firewall do Windows (`block_ip_firewall`);
- Remover chaves de arranque no Registo (`delete_registry_run_entry`);
- Restaurar o ficheiro hosts para o padrão de fábrica (`restore_hosts_file`).

---

## 3. Política de Verificação Pós-Ação e Rollback (Para Fases Futuras)
Sempre que uma ação aprovada pelo utilizador for executada:
1. **Pre-State Snapshot**: O Sentinel regista o estado antes da ação.
2. **Execução**: O comando de remediação é aplicado.
3. **Post-State Verification**: O Sentinel verifica se o processo foi realmente terminado (e se não foi re-gerado por um processo pai) ou se a regra de Firewall está ativa.
4. **Rollback Procedural**: Se o resultado for anómalo, o Sentinel oferece a reversão imediata com um clique.
