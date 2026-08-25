# JARVIS OS — Security Sentinel (Deteção, Correlação & Score Forense)

## 1. Matriz de Correlação Multi-Sinal

O Sentinel implementa correlação determinística entre diferentes camadas do sistema operativo para identificar padrões anómalos com alta confiança e baixa taxa de falsos positivos.

| Regra | Sinais Combinados | Classificação | Confiança | Rationale e Impacto Forense |
|---|---|---|---|---|
| **R1: Observação Benigna** | Novo processo legítimo em diretório padrão (`Program Files`, `System32`) | `BENIGN` | 0.95 | Observação de processo normal de aplicação de utilizador. |
| **R2: Execução em Diretório Temporário** | Executável localizado em `%TEMP%`, `AppData\Local\Temp` | `SUSPICIOUS` | 0.70 | Executáveis a correr de pastas temporárias são comuns em instaladores, mas também em vetores iniciais de droppers. |
| **R3: Temp + Conexão de Rede** | Executável em `%TEMP%` com socket de rede ativo | `HIGH_RISK` | 0.85 | Processo em diretório volátil a estabelecer comunicação externa (possível beacon/C2). |
| **R4: Temp + Persistência** | Executável em `%TEMP%` registado em Startup, Registry Run ou Serviço | `HIGH_RISK` | 0.90 | Mecanismo clássico de sobrevivência a reinicializações a partir de ficheiro temporário. |
| **R5: Triplo Sinal (Temp + Rede + Persistência)** | Executável em `%TEMP%` com persistência e comunicação de rede ativa | `HIGH_RISK` | 0.95 | Padrão altamente correlacionado com malware ativo e estabelecido. |
| **R6: Alteração do Ficheiro Hosts** | Modificação de hash SHA-256 ou novas entradas em `C:\Windows\System32\drivers\etc\hosts` | `SUSPICIOUS` | 0.80 | Possível tentativa de redirecionamento de DNS local (ex: bloquear atualizações ou phishing). |
| **R7: Degradação do Windows Defender / Firewall** | Desativação de proteção em tempo real ou desativação de perfis do Windows Firewall | `HIGH_RISK` | 0.95 | Redução intencional ou acidental das barreiras de defesa primárias do Windows. |
| **R8: Extensão de Browser com Permissões Elevadas** | Nova extensão instalada com acesso a `cookies`, `webRequest` ou `<all_urls>` | `SUSPICIOUS` | 0.75 | Extensão com privilégios de interceção de tráfego web e extração de sessões. |

---

## 2. Cálculo de Confiança & Rationale Explicável

Cada `SecurityEvent` gerado contém:
* `rationale`: Explicação clara em linguagem natural dos sinais detetados.
* `recommended_action`: Ação defensiva recomendada para o utilizador.
* `evidence_ids`: Lista de identificadores das evidências criptográficas associadas.
* `is_known_good`: Indicador se a alteração foi aprovada pelo utilizador.
* `observation_timeline`: Histórico cronológico das observações contínuas.

---

## 3. Filosofia "Known Good" e Supressão Inteligente

Quando o utilizador valida que uma determinada alteração é legítima (ex: um instalador de confiança que correu em `%TEMP%`), a ação **"Aceitar como Known Good"**:
1. Regista a assinatura e o motivo fornecido pelo utilizador em memória persistente.
2. Marca o evento correspondente como `RESOLVED`.
3. Evita novos alertas repetidos para essa exata combinação nos ciclos subsequentes do Watchdog.
