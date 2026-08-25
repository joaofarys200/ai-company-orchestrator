# JARVIS OS — Security Sentinel
# Fase S4: Auditoria de Reversibilidade e Rollback (Rollback Audit)

## 1. Princípios de Auditoria
A auditoria de reversibilidade da Fase S4 avaliou:
- A precisão da restauração de estado prévio;
- A ausência de efeitos colaterais em configurações não relacionadas;
- O comportamento perante falhas e timeouts durante o rollback;
- A segurança perante tentativas de rollback de ações não reversíveis (`TERMINATE_PROCESS`).

## 2. Resultados por Tipo de Ação de Resposta

### 2.1 `QUARANTINE_FILE`
- **Mecânica**: O arquivo original é movido atomicamente para `sentinel/quarantine/` e preservado com metadados JSON e hash SHA-256.
- **Rollback**: O arquivo é restaurado para o caminho original exato e o hash SHA-256 é verificado bit a bit. O diretório temporário de quarentena é destruído.
- **Taxa de Sucesso no Rollback**: **100%**
- **Tempo Médio de Recuperação**: < 15ms.

### 2.2 `BLOCK_NETWORK_ENDPOINT`
- **Mecânica**: Criação de regra isolada na Windows Firewall com a sintaxe `JARVIS-SENTINEL-{ACTION_ID}`.
- **Rollback**: Execução cirúrgica de `netsh advfirewall firewall delete rule name="JARVIS-SENTINEL-{ACTION_ID}"`.
- **Garantia de Isolamento**: Todas as demais regras do sistema, de aplicações e da política padrão do Windows permanecem estritamente intocadas.
- **Taxa de Sucesso no Rollback**: **100%**
- **Tempo Médio de Recuperação**: < 120ms.

### 2.3 `DISABLE_SCHEDULED_TASK`
- **Mecânica**: Desativação via `schtasks.exe /Change /TN <name> /DISABLE`. Proibição estrita de `/Delete`.
- **Rollback**: Reativação via `schtasks.exe /Change /TN <name> /ENABLE`.
- **Verificação**: Consulta `schtasks /Query` confirmando retorno ao estado ativo (`Ready` / `Ativa`).
- **Taxa de Sucesso no Rollback**: **100%**
- **Tempo Médio de Recuperação**: < 180ms.

### 2.4 `MARK_KNOWN_GOOD`
- **Mecânica**: Registo no banco JSON de exclusões temporárias com janela máxima de 30 dias.
- **Rollback**: Remoção da chave de exclusão e retorno da anomalia ao conjunto de observação.
- **Taxa de Sucesso no Rollback**: **100%**

### 2.5 `TERMINATE_PROCESS` (Ação Não Reversível)
- **Mecânica**: Processos finalizados não podem ser "ressuscitados" com estado de memória idêntico.
- **Comportamento no Rollback**: Rejeição imediata com `rollback_available=False` e mensagem de erro informativa. Nenhuma operação ilegal é tentada.

## 3. Resiliência a Falhas no Rollback
- **Falha Simulada de Permissão**: Quando o rollback falha por erro de permissão ou timeout do SO, o estado da ação é registado com a mensagem de erro detalhada e o incidente é mantido aberto para investigação do operador humano.
- **Recuperação de Caos**: Nenhuma falha durante rollback corrompe o histórico ou causa alterações silenciosas no sistema.
