# Relatório de Governança de Dependências Externas (External Dependency Governance)

**Data:** Outubro 2026  
**Status do Sistema:** `EXTERNAL_DEPENDENCY_GOVERNANCE_READY = TRUE`  
**Target:** Prevenção de Downgrade Silencioso de Ferramentas Externas  
**Componentes Auditados:** Planner, Dependency Governor, Permission Gateway, Capability Checker, Coding Session, Project Builder, Sentinel S3 Policy.

---

## 1. Causa Raiz (Root Cause)

No fluxo anterior do JARVIS, observou-se o seguinte comportamento:
```
USER REQUEST ("Analisa a rede local e descobre portas abertas")
  ↳ AGENT / PLANNER PROPOSES SOLUTION (Requer Nmap)
    ↳ NMAP NOT INSTALLED
      ↳ AGENT SILENTLY SWITCHES TO arp -a
        ↳ TASK CONTINUES WITH A DIFFERENT / REDUCED SOLUTION
          ↳ DECLARA "SUCCESS" FALSAMENTE
```

### Análise Técnica da Falha:
1. **Ausência de Classificação Formal:** As dependências eram tratadas como texto genérico sem distinguir dependências estritamente obrigatórias (`REQUIRED`) de ferramentas decorativas (`OPTIONAL`) ou substitutos reais (`ALTERNATIVE`).
2. **Falta de Validação de Critérios no Fallback:** O fallback `arp -a` lê apenas a cache ARP local do SO (descoberta passiva). Ele **não** realiza varredura ativa de rede e **não descobre portas abertas**. Substituir Nmap por `arp -a` violava 100% dos critérios de aceitação do utilizador.
3. **Falsa Conclusão de Missão:** Ao comutar silenciosamente para `arp -a` sem consentimento explícito do utilizador, o sistema mascarava uma incapacidade técnica como uma execução bem-sucedida.

---

## 2. Classificação Explícita de Dependências

Criou-se a enumeração rigorosa `DependencyClassification` em [`models.py`](file:///c:/Users/joaor/Desktop/JarvisOS/security/permission_gateway/models.py):

| Classificação | Definição Semântica | Comportamento se Ausente |
|---|---|---|
| **`REQUIRED`** | A solução proposta **não cumpre** o objetivo sem esta dependência. | **Bloqueio Just-In-Time (`AWAITING_HUMAN_APPROVAL`)**. Proibido comutar silenciosamente. |
| **`OPTIONAL`** | A solução continua a cumprir o objetivo sem a ferramenta. | Execução direta com implementação base; **não bloqueia**. |
| **`ALTERNATIVE`** | Existe outra implementação equivalente que cumpre **todos** os critérios de aceitação. | Seleciona a ferramenta disponível automaticamente **sem solicitar autorização inútil**. |

### Rastreabilidade Estrita (`DependencyRequirement`):
Para cada dependência detectada, o motor gera um registo completo:
- `dependency_id`: Identificador rastreável único.
- `tool_name`: Ex: `Nmap`.
- `reason`: Justificação contextualizada.
- `required_for`: Funcionalidade requerida (ex: *"Varredura ativa da rede local"*).
- `acceptance_criteria`: Lista formal de critérios (ex: `["discover active hosts", "discover open ports"]`).
- `classification`: `REQUIRED` | `OPTIONAL` | `ALTERNATIVE`.
- `fallback`: Ferramenta alternativa (ex: `arp -a`).
- `fallback_capability`: Capacidade técnica real do fallback (ex: *"passive ARP cache only"*).
- `fallback_satisfies_acceptance_criteria`: Avaliado rigorosamente por `evaluate_fallback_satisfaction(...)`.
- `fallback_limitations`: Detalhe explícito das limitações (ex: *"Não executa varredura ativa de portas"*).

---

## 3. Integração com o Planner, Coding Session e Project Builder

Antes de iniciar qualquer execução ou escrita de código:
```
PROPOSED PLAN
  ↳ DEPENDENCY ANALYSIS (analyze_dependencies)
    ↳ CAPABILITY CHECK (CapabilityChecker)
      ↳ Se REQUIRED + NOT_AVAILABLE:
          ↳ Can Execute = False
          ↳ Mission / Session State = AWAITING_HUMAN_APPROVAL
          ↳ Criação de PermissionRequest Just-In-Time
          ↳ NUNCA executar fallback automaticamente!
```

### Pontos de Integração:
1. **`DependencyGovernanceService.analyze_dependencies(...)`**: Avalia o plano, mapeia critérios inferidos e verifica presença de binários e privilégios.
2. **`intelligence/coding_session.py`**:
   - `detect_dependency_requirements(...)` detecta Nmap/FFmpeg/Tesseract e gera metadados de rastreabilidade.
   - `create_session(...)` transiciona a sessão para `AWAITING_HUMAN_APPROVAL` se houver dependências obrigatórias pendentes.
3. **`agents/orchestrator/project_builder.py`**:
   - `_build_project_impl(...)` executa análise de dependências antes da compilação e interrompe com `technical_success = False`, `status = "AWAITING_HUMAN_APPROVAL"`.

---

## 4. Integração com Permission Gateway e Semântica de Decisão

### Separação de Semânticas de Autorização:
1. **`AUTHORIZE_USE`**:
   - Autoriza o uso da ferramenta.
   - O sistema realiza `CapabilityChecker.check_capability`.
   - Se o binário **já estiver instalado**, transiciona para `EXECUTION_READY`.
   - Se o binário **não estiver instalado**, **NÃO finge execução**. Transiciona para `INSTALLATION_REQUIRED` e gera um pedido formal de instalação de ferramenta externa.
2. **`AUTHORIZE_INSTALLATION`**:
   - Autoriza a instalação formal e auditada.
   - Exige fontes oficiais validadas por `SupplyChainValidator`.
   - Verifica privilégios de administrador UAC no Windows.
3. **`USE_LIMITED_FALLBACK`**:
   - **Regra Fundamental:** Se `fallback_satisfies_acceptance_criteria == False`, a ação é **rejeitada com aviso no ecrã**:
     > *"A alternativa não cumpre todos os requisitos."*
   - O modal permanece ativo e a missão permanece em `BLOCKED_REQUIRED_CAPABILITY`.
4. **`CANCEL`**:
   - Cancela a operação e transiciona o pedido para `DENIED`.

---

## 5. Interface com o Utilizador (Modal de Decisão Just-In-Time)

Apresentação minimalista, factual e escura no centro do ecrã ([`PermissionApprovalModal.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/permissions/PermissionApprovalModal.tsx)):

- **Subtítulo Factual:** *"Esta alteração requer uma ferramenta externa."*
- **Tabela de Atributos:**
  - **Ferramenta:** `Nmap`
  - **Risco:** `HIGH RISK`
  - **Necessidade:** `Varredura ativa da rede local e identificação de portas abertas`
  - **Porque:** `A solução proposta exige descoberta de hosts/portas.`
  - **Estado:** `Nmap não está instalado` (destaque âmbar)
  - **Privilégios Necessários:** `Administrador / Npcap`
  - **Impacto / Recursos Afetados:** `network:local_interfaces, driver:npcap`
  - **Alternativa:** `arp -a`
  - **Limitação da Alternativa:** `Não executa varredura ativa nem fornece a mesma cobertura.`
- **3 Botões de Ação:**
  - `[ Cancelar ]`
  - `[ Usar alternativa limitada ]` *(Bloqueado se os critérios de aceitação não forem cumpridos)*
  - `[ Autorizar Nmap ]`

---

## 6. Verificação de Capacidade e UAC do Windows

- O sistema distingue claramente entre `USER_APPROVED` (consentimento dado pelo utilizador na interface) e `OS_ADMIN_GRANTED` (privilégios elevados de Administrador no processo do sistema operacional).
- Ferramentas de baixo nível de rede (como Nmap com varredura SYN / sockets crus / Npcap) exigem privilégios de administrador.
- Se o utilizador aprovar mas o processo não tiver privilégios UAC elevados:
  - Estado: `ADMIN_PRIVILEGE_REQUIRED`.
  - Mensagem explicativa apresentada sem tentar contornar ou burlar o UAC do Windows.

---

## 7. Evidência de Browser QA (Microsoft Edge + Playwright)

Executado via [`scripts/browser_qa_dependency_governance.cjs`](file:///c:/Users/joaor/Desktop/JarvisOS/scripts/browser_qa_dependency_governance.cjs):

| Cenário | Descrição | Resultado | Evidência Gravada |
|---|---|---|---|
| **Cenário 1** | Pedido requer Nmap ausente. Modal aparece no centro. Não comuta para `arp -a`. Exibe limitações. | **PASSED** | `evidence/dependency_governance/01_scenario1_nmap_required_modal.png` |
| **Cenário 2** | Utilizador clica `[ Usar alternativa limitada ]`. Critérios não cumpridos. Exibe aviso: *"A alternativa não cumpre todos os requisitos."* e mantém bloqueado. | **PASSED** | `evidence/dependency_governance/02_scenario2_limited_fallback_rejected.png` |
| **Cenário 3** | Utilizador clica `[ Autorizar Nmap ]`. Capability Check detecta ausência e transiciona para `INSTALLATION_REQUIRED`. Não declara falsa execução. | **PASSED** | `evidence/dependency_governance/03_scenario3_authorized_awaiting_installation.png` |
| **Cenário 4** | Pedido com ferramenta `OPTIONAL`. Execução nativa direta sem exigir autorização ou exibir modal desnecessário. | **PASSED** | `evidence/dependency_governance/04_scenario4_optional_dependency_clean_flow.png` |

---

## 8. Cobertura de Testes Automatizados

### Suíte de Governança (`tests/test_external_dependency_governance.py`): **25/25 PASSED**
1. `test_01_required_dependency` - Classificação rigorosa de REQUIRED para Nmap com critérios de portas.
2. `test_02_optional_dependency` - Classificação de OPTIONAL para utilitário decorativo.
3. `test_03_true_alternative` - Validação de substituto equivalente (wget vs curl).
4. `test_04_unavailable_required` - REQUIRED ausente bloqueia execução imediata e gera JIT request.
5. `test_05_unavailable_optional` - OPTIONAL ausente não bloqueia nem cria pedidos inúteis.
6. `test_06_fallback_satisfies_criteria` - Critérios satisfeitos pelo fallback avaliados como True.
7. `test_07_fallback_fails_criteria` - Critérios violados pelo fallback avaliados como False.
8. `test_08_permission_request` - Criação de requisição com metadados de rastreabilidade.
9. `test_09_use_approval` - Autorização com binário presente transiciona para `EXECUTION_READY`.
10. `test_10_installation_approval` - Autorização com binário ausente transiciona para `INSTALLATION_REQUIRED`.
11. `test_11_capability_check` - Verificação de caminho, executável e SO.
12. `test_12_admin_required_distinguishes_uac` - Distinção entre consentimento do utilizador e UAC do SO.
13. `test_13_policy_blocked` - Política de mutação crítica permanece ativa e inviolável.
14. `test_14_user_denial` - Recusa pelo utilizador marca pedido como `DENIED`.
15. `test_15_fallback_rejection_when_criteria_fail` - `USE_LIMITED_FALLBACK` bloqueado com aviso formal.
16. `test_16_no_silent_downgrade` - Proibição de substituição silenciosa de ferramenta.
17. `test_17_false_completion_prevention` - Proibição de declarar falso sucesso em dependências não resolvidas.
18. `test_18_mission_waiting_state` - Transição para `AWAITING_HUMAN_APPROVAL` em vez de falso `FAILED`.
19. `test_19_idempotent_approval` - Idempotência em chamadas sucessivas de aprovação.
20. `test_20_expiry` - Rejeição estrita de aprovações com TTL expirado.
21. `test_21_audit_trail` - Trilha de auditoria cronológica e imutável de eventos.
22. `test_22_planner_integration` - Interceção pelo Planner antes da execução do plano.
23. `test_23_coding_session_integration` - Interceção em sessões de código assistidas.
24. `test_24_project_builder_integration` - Interceção no construtor de projetos.
25. `test_25_nmap_scenario_full_lifecycle` - Ciclo completo da missão Nmap.

### Suíte de Suporte (`tests/test_permission_gateway.py`): **32/32 PASSED**
**Total de Testes Automatizados:** **57 Testes Passando com Sucesso (100%)**.

---

## 9. Primeira Falha, Primeira Limitação e Menor Próxima Correção

1. **Primeira Falha Encontrada (First Failure):**
   - Ao adicionar o endpoint de protocolo `"permission_resolve_choice"` no handler, o `create_websocket_handlers` em `backend/websocket/registry.py` disparou um erro de divergência de tipos canónicos de mensagens. A causa foi a validação estrita de integridade com `websocket_schema.py` e `contracts.py`.
   - **Correção aplicada:** Atualização simétrica de `CLIENT_MESSAGE_TYPES`, `MISSION_CLIENT_REQUIRED_FIELDS` e `EXPECTED_MESSAGE_TYPES`.
2. **Primeira Limitação (First Limitation):**
   - No ambiente Windows, a instalação do driver Npcap do Nmap exige aceitação interativa de driver pelo utilizador (UAC / Driver Signature). O backend do JARVIS não pode (e não deve) tentar burlar o UAC em modo não-assistido.
3. **Menor Próxima Correção (Smallest Next Fix):**
   - Integrar deteção prévia de pacote via gerenciador de pacotes corporativo (como `winget` ou Chocolatey) com verificação de privilégios elevados, sugerindo ao utilizador o comando oficial de instalação em janela de Administrador quando o driver de rede não estiver presente.

---

## 10. Conclusão do Gate

```
[✓] 1 required dependencies are detected
[✓] 2 no silent downgrade
[✓] 3 optional dependencies do not block unnecessarily
[✓] 4 real alternatives are validated
[✓] 5 permission request works
[✓] 6 installation request works
[✓] 7 capability check works
[✓] 8 UAC state is distinguished
[✓] 9 policy remains enforced
[✓] 10 no false completion
[✓] 11 browser QA passes (Microsoft Edge)
[✓] 12 tests pass (57/57)
[✓] 13 build passes (npm run build: 0 errors)

EXTERNAL_DEPENDENCY_GOVERNANCE_READY = TRUE
```
