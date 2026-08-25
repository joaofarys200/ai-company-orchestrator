# JARVIS OS — Security Sentinel
# Fase S3: Mecânica de Reversão e Restauração (Rollback)

## 1. Princípios de Reversibilidade
O Security Sentinel exige que cada ação de resposta mutável possua uma estratégia determinística e segura de reversão para minimizar o impacto operacional em caso de falsos positivos ou necessidade de restauração de serviços.

## 2. Ações Reversíveis e Mecânica

| Tipo de Ação | Reversível? | Mecânica de Rollback | Verificação de Rollback |
|---|---|---|---|
| `TERMINATE_PROCESS` | **Não** | Não aplicável | Tentativa rejeitada com erro explícito |
| `DISABLE_SCHEDULED_TASK` | **Sim** | `schtasks /Change /TN <name> /ENABLE` | Consulta `schtasks /Query` confirmando `Ready` / `Ativa` |
| `BLOCK_NETWORK_ENDPOINT` | **Sim** | `netsh advfirewall firewall delete rule name="JARVIS-SENTINEL-<ID>"` | Validação de ausência da regra, preservando todas as outras regras do sistema |
| `QUARANTINE_FILE` | **Sim** | Move o ficheiro do diretório de quarentena de volta para o caminho original; remove pasta de quarentena | Validação de presença no caminho original e confirmação de hash SHA-256 |
| `MARK_KNOWN_GOOD` | **Sim** | Remove o registo de exclusão do arquivo JSON | Confirmação de ausência da chave |

## 3. Isolamento e Proteção contra Danos Colaterais
- **Escopo Restrito**: O rollback da Firewall **nunca** faz reset às regras globais (`reset` / `flush`); apenas remove a regra cujo nome começa estritamente por `JARVIS-SENTINEL-{ACTION_ID}`.
- **Restauração Segura**: Em caso de ficheiro já restaurado ou destino ocupado, o rollback bloqueia para prevenir corrupção de dados.
