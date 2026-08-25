# JARVIS OS — Security Sentinel: Unknown Events Analysis & Handling (Fase S6)

## 1. Visão Geral e Taxonomia
No âmbito do Sentinel Fase S6 (Real-World Shadow Mode & Detection Telemetry), eventos que não possuem assinatura conclusiva de risco alto (`HIGH_RISK`), nem correspondência determinística a um processo/conexão padrão (`BENIGN`), nem anomalia evidente (`SUSPICIOUS`) são classificados defensivamente como **`UNKNOWN`**.

O estado `UNKNOWN` existe para:
1. **Eliminar inferências falsas**: Não presumir benignidade nem malícia sem evidência suficiente.
2. **Evitar Fadiga de Alertas**: Alertar de forma ponderada (sem acionar alertas críticos espúrios).
3. **Alimentar a Revisão Humana**: Permitir que o operador analise os metadados brutos e decida a classificação correta.

---

## 2. Casos de Análise em Ambiente Real Windows

| ID de Padrão | Categoria | Descrição do Padrão | Motivo do UNKNOWN | Resolução / Ação do Operador |
|---|---|---|---|---|
| **UNK-PAT-001** | `PROCESS` | Processos sem assinatura digital (`is_signed=None`) mas executados a partir de `C:\Program Files\` | Ficheiro binário não assinado ou assinatura de catálogo não extraível localmente. | Operador revê via Human Review -> Se conhecido da organização, aceita como `KNOWN_GOOD`. |
| **UNK-PAT-002** | `NETWORK` | Conexões TCP efémeras para portas de alto valor (ex: `> 50000`) de processos locais não documentados | Tráfego P2P/RPC local sem correlação com persistência ou alteração de hosts. | Telemetria contínua analisa frequência. Se for tráfego único/efémero sem persistência, mantém em monitorização passiva. |
| **UNK-PAT-003** | `PERSISTENCE` | Entradas de Tarefas Agendadas criadas por instaladores de terceiros sem argumentos descritivos | Falta de metadados no XML da tarefa do Windows Task Scheduler. | Verificação de integridade SHA-256 do binário de destino. |
| **UNK-PAT-004** | `BROWSER` | Extensão de browser instalada em modo de programador (`unpacked`) | Extensão local sem ID da Web Store oficial. | Auditoria de permissões (ex: `<all_urls>`). Revisão humana mandatada. |

---

## 3. Política de Mitigação & Melhoria Contínua
- **Imutabilidade**: As evidências de eventos `UNKNOWN` são gravadas no log criptográfico imutável.
- **Transição de Estado**: Um evento `UNKNOWN` só transita para `KNOWN_GOOD` ou `BENIGN` após confirmação explícita no modal de **Human Review** com registo de operador e justificativa.
- **Taxa de Desconhecidos (`Unknown Rate`)**: Monitorizada continuamente na telemetria do Shadow Mode para garantir que permanece abaixo do limiar aceitável (< 10%).
