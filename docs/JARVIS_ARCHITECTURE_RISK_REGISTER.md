# ⚠️ JARVIS OS — ARCHITECTURE RISK REGISTER

**Data**: 2026-08-13  
**Classificação**: Análise de Riscos Sistémicos, Falhas Críticas e Vulnerabilidades Operacionais

---

## 1. 📋 REGISTO DE RISCOS SISTÉMICOS

| ID | Área de Risco | Descrição do Risco | Impacto | Severidade | Gatilho / Cenário | Mitigação Atual | Correção Necessária |
|---|---|---|---|---|---|---|---|
| **R-01** | **Falsa Evidência Económica** | Agente injetar registos em `payments.sqlite` ou `leads.sqlite` via código Python e declarar `SUCCESS` sem dinheiro real. | Alto | **P0 (Crítico)** | Benchmark ou agente a executar sem validação de assinatura externa. | `ECONOMIC_GATEWAY_REALITY_AUDIT.md` documenta a fronteira. | Exigir `EXTERNAL_VERIFIED` com assinatura HMAC de webhook para monetização. |
| **R-02** | **Concorrência em Ficheiros JSON** | Duas missões ou agentes a escreverem no mesmo ficheiro `mission.json` ou `symbols_index.json` em simultâneo. | Médio | **P1 (Alto)** | Execução concorrente de múltiplos builders sem lock distribuído. | Bloqueio de ficheiro no `MissionStateStore`. | Centralizar locks em memória com `asyncio.Lock` por `project_id`. |
| **R-03** | **Perda de Contexto em Long-Running Missions** | LLM exceder a janela de contexto durante sessões de coding com dezenas de iterações. | Médio | **P1 (Alto)** | Missões complexas com mais de 15 passos de patching. | `ProgressTracker` para em `NO_PROGRESS`. | Compressão de histórico de diffs e truncamento inteligente via AST. |
| **R-04** | **Ações Externas Irreversíveis Não Aprovadas** | Agente disparar emails reais ou efetuar pagamentos se forem adicionadas ferramentas externas sem portão de segurança. | Alto | **P0 (Crítico)** | Execução em autonomia desregulada sem human approval gate. | `PermissionPolicyManager` pausa em `PENDING_APPROVAL`. | Manter bloqueio absoluto de ferramentas `FINANCIAL_ACTION` por defeito. |
| **R-05** | **Falso Positivo em Sandbox Health Check** | O servidor sandbox retornar `200 OK` numa página HTML estática vazia ou com erro de JavaScript no runtime do browser. | Baixo | **P2 (Médio)** | `index.html` básico sem o formulário funcional de conversão. | `WebDeploymentGateway` verifica status 200 via HTTPX. | Validar a presença de elementos DOM específicos (tags `<form>` e `<input>`) via Playwright. |
| **R-06** | **Falta de Recuperação Pós-Crash de Missão** | Processo ser terminado no meio de um work package `IN_PROGRESS`, deixando o estado pendente sem rollback. | Médio | **P1 (Alto)** | Reinício abrupto do servidor ou terminação de processo. | `MissionStateStore` deteta versão e permite recarregar. | Implementar watchdog na inicialização que reverte pacotes `IN_PROGRESS` órfãos para `READY`. |
| **R-07** | **Exposição de Segredos em Logs de Telemetria** | Tokens de API ou chaves privadas serem serializadas no `ModelResponse` ou no log do RHO. | Alto | **P1 (Alto)** | Prompt ou resposta do LLM contendo strings de credenciais. | Variáveis de ambiente isoladas em `.env`. | Adicionar filtro regex de sanitização de tokens antes de gravar logs/telemetria. |
| **R-08** | **Desvio de Foco / Alucinação em Documentos** | Geração de documentação ou relatórios técnicos com factos não verificados no código fonte ou na web. | Médio | **P2 (Médio)** | Agente redator a inferir comportamento de bibliotecas sem ler o código. | Validação de referências no ModelHarness. | Pipeline de documentos em 10 estágios com recolha e citação obrigatória de fontes. |

---

## 2. 🛑 CENÁRIOS DE FALHA & MATRIZ DE RECUPERAÇÃO

```
┌─────────────────────────┬──────────────────────────────────┬─────────────────────────────────┐
│ Cenário de Falha        │ Comportamento Atual              │ Comportamento Desejado          │
├─────────────────────────┼──────────────────────────────────┼─────────────────────────────────┤
│ Syntax Failure (AST)    │ Rollback automático para backup  │ ✅ Mantido (Já funciona 100%)    │
│ Teste Unitário Falha    │ Registado como FAILED no harness │ Repetir com prompt de diagnóstico│
│ Ficheiro Inexistente    │ Retorna erro de filesystem       │ Corrigir path via context lookup│
│ Timeout em Scraping     │ Fallback Playwright -> HTTPX     │ ✅ Mantido (Já funciona 100%)    │
│ Servidor Crash durante WP│ Fica marcado como IN_PROGRESS   │ Watchdog redefine para READY    │
│ Injeção de Lead Fake    │ Aceita se tiver formato de email │ Requer assinatura de webhook ext│
└─────────────────────────┴──────────────────────────────────┴─────────────────────────────────┘
```
