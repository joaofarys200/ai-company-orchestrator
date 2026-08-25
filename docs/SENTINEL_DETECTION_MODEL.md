# JARVIS OS — Security Sentinel Detection Model

## 1. Princípios de Deteção
O modelo de deteção do Sentinel baseia-se em **evidência correlacionada** e na rejeição estrita de heurísticas cegas.

### Níveis de Classificação:
1. **`BENIGN`**:
   - Processo conhecido e presente no baseline com hash correspondente;
   - Serviço ou processo assinado localizado em diretórios padrão do Windows / Program Files;
   - Mapeamento padrão no ficheiro hosts (`localhost`).
2. **`UNKNOWN`**:
   - Novo processo legítimo instalado recentemente;
   - Nova conexão de rede padrão de aplicações do utilizador;
   - Sem histórico no baseline, mas sem indicadores de ataque.
3. **`SUSPICIOUS`**:
   - Processo a executar a partir de pastas temporárias (`%TEMP%`, `%APPDATA%\Local\Temp`);
   - Nova entrada de arranque criada no registo a apontar para executável não catalogado;
   - Ficheiro `hosts` modificado com novos domínios externos;
   - Extensão de navegador recém-instalada com permissões sensíveis de captura de tráfego.
4. **`HIGH_RISK`**:
   - Correlação temporal de 3 ou mais sinais:
     * Exemplo: Executável em `%TEMP%` + Nova Tarefa Agendada no Windows + Conexão TCP externa ativa.
5. **`CONFIRMED_MALICIOUS`**:
   - Deteção confirmada por múltiplas fontes com indicadores corroborados e/ou assinatura de malware reconhecida pelo subsistema do Defender.

---

## 2. Matriz de Correlação de Sinais

```
           [ SINAL 1: Processo em %TEMP% ]
                         +
           [ SINAL 2: Nova chave RunOnce ]
                         +
           [ SINAL 3: Conexão TCP Outbound ]
                         ↓
           [ CORRELAÇÃO: SecurityIncident ]
                         ↓
           [ SEVERIDADE: HIGH_RISK ]
```

Nenhum sinal individual isolado eleva automaticamente o estado para `CONFIRMED_MALICIOUS`. A incerteza é mantida como `UNKNOWN` ou `SUSPICIOUS` até corroboração por múltiplos coletores independentes.
