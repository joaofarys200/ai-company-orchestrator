# JARVIS OS — Security Sentinel Threat Model (STRIDE)

Este documento mapeia os vetores de ameaça, superfícies de ataque e controlos defensivos do Sentinel contra invasões e malware no Windows.

---

## 1. Mapeamento de Vetores de Ameaça

| Ameaça / Vetor | Superfície de Ataque | Mecanismo de Deteção (Sentinel) | Mitigação Defensiva | Limitações em S1 |
|---|---|---|---|---|
| **Infostealers / Spyware** | `%TEMP%`, `%APPDATA%`, Scripts não assinados | `ProcessCollector` (Alerta de executáveis em diretórios temporários + hash SHA-256) | Inventário contínuo e correlação com tarefas agendadas | Não mata o processo em S1 (apenas audita) |
| **Persistência de Malware** | Registo `Run`, `RunOnce`, `Startup`, `schtasks`, Serviços | `PersistenceCollector` (Inspeção periódica de chaves e tarefas) | Diff com baseline para sinalizar novas entradas não autorizadas | Não remove chaves em S1 |
| **C2 / Reverse Shells** | Portas de rede locais e conexões externas suspeitas | `NetworkCollector` (Mapeamento de IP remoto, porta e PID proprietário) | Deteção de novos sockets abertos por processos recém-criados | Não bloqueia IP na Firewall em S1 |
| **Redirecionamento de DNS / Pharming** | `C:\Windows\System32\drivers\etc\hosts` | `HostsCollector` (Monitorização de SHA-256 e parsing de domínios) | Deteção instantânea de alteração de integridade no ficheiro | Não restaura o ficheiro em S1 |
| **Extensões Maliciosas de Browser** | Manifests em `%LocalAppData%\Google\Chrome\...` | `BrowserCollector` (Inventário de IDs e auditoria de permissões sensíveis como cookies/tabs) | Destaque de extensões com permissões excessivas e fontes desconhecidas | Não desinstala a extensão em S1 |
| **Desativação de Segurança** | Desativação de Defender ou Firewall | `WindowsSecurityEventsCollector` | Alerta prioritário se `RealTimeProtectionEnabled == False` | Apenas observação em S1 |

---

## 2. Ameaças contra o Próprio Sentinel

| Ameaça ao Sentinel | Vetor | Mitigação Arquitetural |
|---|---|---|
| **Falsificação de Evidência** | Processo malicioso a tentar corromper dados | Cada evidência é selada com hash SHA-256 imutável no momento da captura |
| **Fuga de Credenciais do Utilizador** | Processo contém palavras-passe na linha de comando | `sanitize_cmdline()` mascara chaves, tokens e passwords antes de guardar |
| **Negação de Serviço / Crash no Scanner** | Processo com permissão negada ou ficheiro bloqueado | Todos os coletores usam blocos de isolamento e captura segura de exceções |
| **Falsos Positivos Massivos** | Processos legítimos do Windows a correr em background | Princípio de "Não Assumir Comprometimento": novas entradas são marcadas como `NEW_PROCESS` / `UNKNOWN`, nunca como `CONFIRMED_MALICIOUS` sem evidência correlacionada |
