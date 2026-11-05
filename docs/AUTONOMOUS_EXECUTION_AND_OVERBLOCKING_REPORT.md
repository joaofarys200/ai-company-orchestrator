# JARVIS OS — RELATÓRIO DE EXECUÇÃO AUTÓNOMA E ELIMINAÇÃO DE SOBRE-BLOQUEIOS

**Data**: 2026-10-15  
**Ambiente**: Windows (x64) | Python 3.14.7 | Pytest 9.1.1  
**Estado da Validação**: 100% Validado (107 testes executados, 107 aprovados, 0 falhas)

---

## 1. Causas Concretas do Bloqueio Excessivo

Durante a auditoria integral da cadeia de execução (FASE 1), identificámos oito pontos críticos de desvio e degradação:

1. **A Armadilha de Contagem de Palavras (`len(clean.split()) <= 4`)**:
   - *Localização*: `backend/services/chat_mission_bridge.py` (antiga linha 704).
   - *Mecanismo*: Qualquer diretiva legítima de 4 palavras ou menos (ex: `"muda a porta para 3000"`, `"corrige o bug"`, `"instala express"`, `"configura logger"`) era sumariamente rebaixada para `ChatIntentType.CHAT` (conversa casual), contornando os executores e terminando com `status: "COMPLETED"` sem qualquer chamada de ferramenta.
2. **Definição Estrita e Incompleta de Alvos de Código (`CODING_TARGET_PATTERNS`)**:
   - *Localização*: `ChatRequestResolver.CODING_TARGET_PATTERNS`.
   - *Mecanismo*: Diretivas contendo verbos operacionais válidos como `"muda"`, `"ajusta"`, `"configura"` ou alvos reais como `"porta"`, `"logger"`, `"timeout"`, `"cors"`, `"jwt"` não correspondiam à lista rígida de substantivos. A ausência de correspondência exata empurrava o pedido para `ChatIntentType.AMBIGUOUS`.
3. **Classificação Cega de Risco Dual-Use como Ciberataque Ofensivo**:
   - *Localização*: `security/safety_classifier.py` (`SafetyClassifier.evaluate`).
   - *Mecanismo*: Termos como `"ddos"`, `"scan"`, `"flooding"` bloqueavam imediatamente tarefas legítimas de resiliência local (ex: middleware de rate limiting, endpoints de monitorização `/scan-local-ips`).
4. **Perda de Contexto e Herança Unilateral nas Confirmações Curtas**:
   - *Localização*: `ChatRequestResolver.resolve_request` (Secção 4.5).
   - *Mecanismo*: Comandos curtos (`"faz isso"`, `"avança"`, `"implementa"`) inspecionavam unicamente mensagens com `role == "user"`. Se o utilizador tivesse colocado uma questão ("como resolvo o timeout?") e o assistente proposto uma solução técnica ("alterando server.timeout para 30s"), a confirmação perdia a proposta do assistente e falhava em criar a missão.
5. **Abandono Total perante Limitações Parciais**:
   - *Localização*: `backend/services/chat_mission_bridge.py` (`handle_directive`).
   - *Mecanismo*: Quando uma dependência externa a nível de SO (ex: utilitário `nmap`) não estava presente, todo o fluxo era abortado, impedindo a criação dos componentes locais viáveis (endpoints, adaptadores, mockers e UI).
6. **Teatro de Execução no Chat Casual**:
   - *Localização*: `backend/services/orchestration_runtime.py` (`run_casual_chat`).
   - *Mecanismo*: Quando o modelo local ou remoto gerava respostas coloquiais afirmando "Já corrigi o código" ou "Já tratei disso", nenhuma ferramenta tinha sido executada nem ficheiro modificado, violando a Verdade de Execução.
7. **Exigência Injustificada de Confirmação para Operações Locais Rotineiras**:
   - Ações normais de desenvolvimento local (criação de rotas, edição de ficheiros de projeto) eram tratadas com a mesma gravidade que comandos destrutivos irreversiveis.
8. **Substituição de Execução por Proposta Alternativa Não Solicitada**:
   - Em vez de selecionar uma abordagem técnica viável e executá-la, o sistema parava para apresentar opções genéricas ao utilizador.

---

## 2. Componentes e Ficheiros Efetivamente Alterados

| Ficheiro | Camada / Módulo | Alteração Realizada |
| :--- | :--- | :--- |
| `security/delivery_governance/decision_model.py` | Governança & Decisão | Implementação do Modelo de Decisão com 6 dimensões (`UserIntentType`, `TaskFeasibilityStatus`, `TaskAuthorizationStatus`, `PolicyStatus`, `ExecutionPlan`, `AcceptanceCriteria`), Máquina de Estados para Verdade de Execução (`ExecutionTruthState`) e fiscalizador `ExecutionTruthEnforcer`. |
| `backend/services/chat_mission_bridge.py` | Encaminhamento & Orquestração | Expansão de verbos executivos e confirmações contextuais, eliminação da armadilha de contagem de palavras, integração com `DecisionEngine`, fiscalização da verdade de execução em `broadcast_chat`, e execução parcial para tarefas viáveis independentes. |
| `backend/services/orchestration_runtime.py` | Runtime do Modelo | Interceção de alegações de teatro com `ExecutionTruthEnforcer.audit_response_truth` antes de emitir qualquer resposta de chat casual. |
| `security/safety_classifier.py` | Classificador de Segurança | Atualização do método `has_defensive_focus` para reconhecer desenvolvimento local, resiliência, rate limiting e endpoints de diagnóstico sem falsos positivos. |
| `intelligence/mission_understanding.py` | Compreensão Pré-Execução | Admissão de verbos de ação isolados e projetos ativos como contexto suficiente para avançar diretamente para `READY`. |
| `tests/test_autonomous_execution_and_overblocking.py` | Suíte Canónica de Regressão | Criação dos 15 cenários formais exercitando todo o pipeline de execução e validação. |

---

## 3. Comportamento Anterior vs. Comportamento Corrigido

| Situação / Prompt | Comportamento Anterior (Defeituoso) | Comportamento Corrigido (Autónomo) |
| :--- | :--- | :--- |
| `"muda a porta para 3000"` | Convertido em conversa casual (`CHAT`) por ter $\le 4$ palavras. | Classificado como `EXECUTION_REQUEST`, cria missão e executa no projeto ativo. |
| `"corrige o bug"` | Rebaixado para `CHAT` sem qualquer tentativa de resolução. | Classificado como `EXECUTION_REQUEST`, inspeciona o código e cria plano de correção. |
| `"configura o logger em json"` | Rejeitado como `AMBIGUOUS` por `logger` não ser alvo catalogado. | Classificado como `EXECUTION_REQUEST`, cria ficheiro e atualiza `package.json`. |
| Proposta técnica seguida de `"faz isso"` | Perdia o contexto da solução proposta pelo assistente; tratava como nova conversa. | Herda o contexto técnico da proposta do assistente e do pedido raiz, acionando o pipeline de missão. |
| Pedido com ferramenta externa ausente (`nmap`) | Abortava integralmente a tarefa com erro. | Prepara os componentes e interfaces viáveis no disco e devolve `PARTIALLY_COMPLETED` com explicação transparente. |
| Modelo afirma "Já corrigi" sem ferramentas | Mensagem textual enganosa transmitida ao utilizador como verdade factual. | Intercetada por `ExecutionTruthEnforcer`, substituída por aviso de transparência indicando que nenhuma ferramenta foi chamada. |
| Pedido de diagnóstico (`"diagnostica erro"`) | Encaminhado como missão genérica ou rejeitado. | Identificado como inspeção factual, lê ficheiros reais no disco sem poluir o repositório de missões. |
| Tarefa complexa (rate limiter distribuído) | Bloqueado por cautela abstrata ou "complexidade excessiva". | Decomposto em plano interno, mantido como `FULLY_FEASIBLE` e executado. |

---

## 4. Testes Executados e Resultados Reais

Executámos a bateria integral de testes em ambiente real:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_autonomous_execution_and_overblocking.py tests/test_chat_mission_bridge.py tests/test_chat_router_consolidation.py tests/test_chat_anti_theater_and_confirmations.py tests/test_chat_safety_and_gates.py tests/test_chat_money_pipeline.py tests/test_product_delivery_governance.py tests/test_runtime_and_product_acceptance_integrity.py
```

**Resultado Observável**:
- **Total de Testes**: 107
- **Aprovados**: 107 (100%)
- **Falhas**: 0
- **Duração**: 10.38 segundos
- **Pip Check**: `No broken requirements found`

### Detalhe dos 15 Cenários Canónicos (FASE 9):
1. `test_scenario_01_direct_implementation_legitimate_feature`: **PASSED** (Verifica modificação de `app.js` e criação no `MissionStateStore`).
2. `test_scenario_02_multi_file_edits_existing_project`: **PASSED** (Verifica modificação atómica de `logger.js`, `package.json` e `app.js`).
3. `test_scenario_03_technical_problem_diagnosis`: **PASSED** (Inspeciona ficheiros no disco, 0 missões fantasmas criadas).
4. `test_scenario_04_technically_challenging_but_feasible`: **PASSED** (Tarefa complexa aceite e executada sem sobre-bloqueio).
5. `test_scenario_05_incomplete_info_with_sensible_default`: **PASSED** (Adota predefinição técnica segura e avança).
6. `test_scenario_06_contextual_continuation_faz_isso_avanca`: **PASSED** (Herda proposta técnica de assistente anterior).
7. `test_scenario_07_recoverable_failure_alternative_approach`: **PASSED** (Recupera com abordagem alternativa e conclui).
8. `test_scenario_08_real_restriction_requires_specific_authorization`: **PASSED** (Operação destrutiva `format c:` exige autorização humana).
9. `test_scenario_09_partially_executable_request`: **PASSED** (Falta de `nmap` executa `device_scanner.js` local e reporta `PARTIALLY_COMPLETED`).
10. `test_scenario_10_request_cannot_be_fulfilled_in_full`: **PASSED** (Impossibilidade matemática teórica explicada com precisão).
11. `test_scenario_11_real_restriction_requires_policy_refusal`: **PASSED** (Malware/roubo de credenciais recusado categoricamente).
12. `test_scenario_12_model_claiming_action_without_execution`: **PASSED** (Alegação não verificada é neutralizada e corrigida).
13. `test_scenario_13_gate_must_not_reject_when_requirements_met`: **PASSED** (Previne falsos negativos no Product Delivery Gate).
14. `test_scenario_14_gate_must_not_approve_without_evidence`: **PASSED** (Previne aprovação sem evidências objetivas).
15. `test_scenario_15_execution_fails_reported_honestly`: **PASSED** (Falha real é reportada como `FAILED` no `MissionStateStore`).

---

## 5. Prova de que Pedidos de Execução Chegam ao Executor

A integração foi verificada através de testes observáveis no sistema de ficheiros:
- Quando o utilizador submete uma instrução como `"Cria um endpoint /healthcheck no projeto dina"`, o `ChatRequestResolver` emite `ChatIntentType.EXECUTION_REQUEST`.
- O `ChatMissionBridge` invoca o `MissionStateStore`, criando a missão `m_<correlation_id>` e o pacote de trabalho `wp_<correlation_id>`.
- O executor é ativado e escreve efetivamente as linhas de código no ficheiro alvo (`app.js`).
- O critério de aceitação `crit_<correlation_id>` é satisfeito com referência à evidência `ev_<correlation_id>`.
- O estado da missão progride formalmente de `DRAFT` $\to$ `READY` $\to$ `ACTIVE` $\to$ `COMPLETED`.

---

## 6. Bloqueios Legítimos que Permanecem e a Razão Concreta de Cada Um

1. **Malware Explícito e Exfiltração de Credenciais**:
   - *Padrões*: Criação de ransomware, keyloggers, trojans, roubo de chaves privadas ou credenciais.
   - *Razão Concreta*: Violação criminal e de integridade do utilizador; sem enquadramento defensivo ou analítico explícito, a política de segurança (`PolicyStatus.BLOCKED_POLICY`) impede a execução.
2. **Comandos de Destruição em Massa Não Reversíveis**:
   - *Padrões*: `rm -rf /`, `format c:`, `wipe disk`, `drop database prod`.
   - *Razão Concreta*: Ações materialmente catastróficas que destroem dados do utilizador. Não são recusadas definitivamente, mas exigem autorização humana explícita (`TaskAuthorizationStatus.REQUIRES_USER_CONFIRMATION`).
3. **Impossibilidades Computacionais / Teóricas Fundamentais**:
   - *Padrões*: Resolução do problema da paragem (Halting Problem) para código arbitrário, $P=NP$ em tempo polinomial.
   - *Razão Concreta*: Limitações matemáticas fundamentais não passíveis de execução algorítmica (`TaskFeasibilityStatus.BLOCKED_TECHNICAL_IMPOSSIBILITY`).
4. **Requisitos de Conformidade Financeira em Produção Real**:
   - *Padrões*: Movimentação de dinheiro real sem credenciais bancárias ativas.
   - *Razão Concreta*: Proteção patrimonial em ambiente sem liquidação live verificada.

---

## 7. Limitações Ainda Existentes

1. **Dependência de Ferramentas Nativas do Sistema Operativo Host**:
   - Quando um pacote externo ausente (ex: compilador C++ não instalado, binário específico de hardware) é estritamente necessário para compilar código nativo, o JARVIS apenas consegue produzir os ficheiros-fonte e a configuração, mantendo a compilação final bloqueada até à instalação no ambiente.
2. **Ambiguidades Extremas Sem Contexto Anterior**:
   - Frases totalmente destituídas de semântica técnica enviadas numa conversa nova (ex: `"faz aquilo agora"`) continuam a requerer esclarecimento, conforme prescrito no Princípio Fundamental ("Uma ambiguidade material deve resultar numa pergunta de esclarecimento quando não for possível avançar responsavelmente").

---

## 8. Primeira Falha Restante

- Não existem falhas remanescentes na suíte de testes do projeto (107 testes executados com 100% de sucesso).
- No domínio operacional real, a primeira falha que pode surgir ocorrerá se o utilizador solicitar uma compilação de código nativo num sistema operativo host onde o respetivo compilador (ex: `gcc` ou `cl.exe`) não esteja configurado no `PATH` do sistema.

---

## 9. Menor Correção Seguinte

- Para colmatar a limitação de ferramentas nativas em falta no SO host, a menor correção seguinte consiste em adicionar ao `PreviewLifecycleManager` e ao `DependencyGovernor` um mecanismo autónomo de deteção e proposta de comando de instalação (ex: via `winget install` ou `npm install -g`), permitindo ao utilizador autorizar a instalação do utilitário com um simples clique ou confirmação "avança".
