# JARVIS OS — Security Sentinel (Guia de Interface Visual & UX)

## 1. Localização e Acesso

O painel visual do Sentinel está integrado diretamente no **Workspace** do JARVIS OS:
* **Separador Principal**: `Segurança` (Ícone de Escudo / `Shield`)
* **Componente React**: `frontend/src/features/sentinel/SentinelDashboard.tsx`

---

## 2. Estrutura e Separadores do Dashboard

### 1. Banner Superior & Postura
* **Título & Badge**: `JARVIS SECURITY SENTINEL — FASE S2: CONTINUOUS WATCHDOG`
* **Pill de Postura**: Indicação dinâmica com cores adaptativas:
  * 🟢 `GOOD`: Sistema seguro e em conformidade com o baseline.
  * 🔵 `MONITORING`: Watchdog ativo a inspecionar alterações passivas.
  * 🟡 `ATTENTION`: Alterações detetadas a aguardar interpretação ou revisão.
  * 🔴 `HIGH_RISK`: Anomalia crítica ou degradação de segurança identificada.
* **Botão "Executar Auditoria Agora"**: Dispara uma auditoria imediata protegida contra concorrência e com animação de spinner sem bloquear a interface.

### 2. Overview (Visão Geral)
* **KPI Cards**:
  * **Watchdog Status**: Estado do serviço (`RUNNING`/`PAUSED`), intervalo de varrimento (60s), total de scans e temporizador para o próximo ciclo.
  * **Recursos Sentinel**: Consumo de memória RAM (MB) e percentagem de CPU do processo.
  * **Windows Defender**: Estado da proteção antivírus e proteção em tempo real.
  * **Windows Firewall**: Estado dos perfis de rede público, privado e domínio.
* **Banner de Integridade**: Baseline ID ativo e hash criptográfico SHA-256 de integridade.
* **Incident Timeline**: Lista cronológica de anomalias recentes correlacionadas.

### 3. Processos (`Processos (N)`)
* Tabela pesquisável em tempo real por nome, PID ou caminho de ficheiro executável.
* **Filtros rápidos**: `Todos`, `⚠️ Pastas %TEMP%` e `Não Assinados`.
* Destaque visual a vermelho/âmbar para processos em execução fora dos diretórios de instalação de sistema.
* Hashes SHA-256 e nomes de utilizador associados a cada processo.

### 4. Rede & Portas (`Rede & Portas (N)`)
* Inventário de sockets ativos e portas locais em escuta (*LISTEN*).
* Mapeamento de protocolo (TCP/UDP), endereços locais e remotos, portas e PIDs/processos responsáveis.
* **Filtros**: `Todos`, `Portas LISTEN`, `Conexões Ativas`.

### 5. Persistência (`Persistência (N)`)
* Auditoria dos mecanismos de inicialização automática no Windows:
  * Registo do Windows (`HKCU\...\Run`, `HKLM\...\Run`, `RunOnce`)
  * Pastas de Inicialização (*Startup folders*)
  * Tarefas Agendadas (*Scheduled Tasks*)
  * Serviços do Windows (*Services*)

### 6. Extensões de Browser (`Extensões (N)`)
* Cartões modulares para Google Chrome e Microsoft Edge com versão, ID e permissões concedidas.
* Destaque para extensões com permissões sensíveis de captura de tráfego (`cookies`, `webRequest`, `all_urls`).

### 7. Eventos de Segurança & Modal Known Good
* Detalhe de cada anomalia com rationale forense e ação recomendada.
* Linha do tempo de observações históricas (*Observation Timeline*).
* Botão **"Aceitar como Benigno"** que abre um modal para inserir o motivo de aprovação e suprimir alertas futuros.

### 8. Evidence Inspector
* Visualizador formatado JSON dos metadados criptográficos das evidências normalizadas.
