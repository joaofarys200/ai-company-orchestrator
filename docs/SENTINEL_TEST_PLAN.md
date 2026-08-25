# JARVIS OS — Security Sentinel Test Plan

## 1. Estratégia de Testes Multi-Camadas

### Nível 1: Testes Unitários de Contratos e Sanitização
- Validação de serialização e imutabilidade dos modelos `SecurityEvidence`, `SecurityEvent`, `SystemBaseline`, `BaselineDiff`.
- Validação da máscara de segredos em linhas de comando (`--password`, `--token`, `-p`, `Bearer`).
- Validação da função de cálculo de hash SHA-256 em buffers de ficheiros e exceções de I/O.

### Nível 2: Testes Unitários de Coletores
- **ProcessCollector**: Validação de extração de processos em execução e deteção de diretórios temporários.
- **NetworkCollector**: Validação de sockets TCP/UDP e resolução de nomes de processos.
- **PersistenceCollector**: Validação de enumeração de chaves `Run`, pastas de arranque e tarefas.
- **HostsCollector**: Validação de parsing de domínios em ficheiros hosts de teste.
- **BrowserCollector**: Validação de resolução de nomes localizados e permissões em manifestos Chromium.
- **WindowsSecurityEventsCollector**: Validação de queries ao estado do Defender e Firewall.

### Nível 3: Testes de Baseline e Diff Determinístico
- Geração de snapshot `BASE-A`.
- Modificação simulada em `BASE-B` (injeção de processo em `%TEMP%`, porta 44444 e nova chave `RunOnce`).
- Verificação se o motor `BaselineDiff` deteta exatamente 1 novo processo, 1 nova porta e 1 nova persistência com 0 falsos positivos.

### Nível 4: Teste Real-Host Read-Only
- Execução do `SecurityAuditRunner` no ambiente real do Windows.
- Garantia estrita de que **nenhuma operação de escrita/mutação** é executada no sistema operativo durante a auditoria.
