# 🗺️ JARVIS OS — IMPROVEMENT ROADMAP

**Data**: 2026-08-13  
**Princípio Orientador**: Escolher sempre a **MENOR alteração arquitetural** que resolva o problema com o máximo impacto e zero quebras.

---

## 🎯 PRIORIZAÇÃO DE MELHORIAS (P0 a P3)

### 🔴 P0 — BLOQUEADORES (Integridade e Segurança)

#### **P0-1: Portão de Verificação Externa para Monetização e Leads**
- **Problema**: O sistema permite criar leads e transações financeiras locais e declarar `SUCCESS` económico sem comprovação do mundo exterior.
- **Evidência**: `backend/gateway/lead_gateway.py` e `monetization_gateway.py` aceitam inserções diretas por qualquer função Python.
- **Impacto**: Impede falsos positivos e ilusão de rendimento económico.
- **Risco**: Muito baixo (adiciona flag e validação de origem).
- **Complexidade**: Baixa.
- **Menor Correção Possível**: Exigir a flag `source_verified=True` e assinatura HMAC para que uma transação conte para `revenue_usd` de missões ativas; benchmarks sem flag são explicitamente marcados como `SYNTHETIC_BENCHMARK`.
- **Benefício**: Separação formal e estrita entre testes internos e transações reais.
- **Testes**: Testar rejeição de `SUCCESS` quando existirem apenas transações locais não assinadas.

---

### 🟠 P1 — MELHORIAS CRÍTICAS (Robustez e Recuperação)

#### **P1-1: Watchdog de Recuperação de Missões Órfãs Pós-Crash**
- **Problema**: Se o processo do JARVIS reiniciar enquanto um work package estiver `IN_PROGRESS`, o pacote permanece bloqueado sem ser retomado.
- **Evidência**: `agents/mission_state.py` não tem rotina de startup que verifique pacotes pendentes de sessões anteriores.
- **Impacto**: Garante que o JARVIS retoma o trabalho exatamente de onde parou após reinício.
- **Risco**: Baixo.
- **Complexidade**: Baixa.
- **Menor Correção Possível**: Criar método `recover_interrupted_missions()` no arranque do `OrchestrationRuntime` que reverte work packages `IN_PROGRESS` sem execução ativa para `READY`.
- **Benefício**: Autonomia contínua e resiliência a quebras de energia/processo.
- **Testes**: Simular encerramento abrupto com estado `IN_PROGRESS` e verificar recuperação automática no boot.

#### **P1-2: Sanitização Automática de Segredos em Logs e RHO**
- **Problema**: Prompts ou respostas que contenham acidentalmente tokens de API podem ser persistidos na tabela `model_trajectories` do SQLite.
- **Evidência**: `backend/model_harness/rho.py` grava `raw_text` diretamente.
- **Impacto**: Proteção de credenciais locais.
- **Risco**: Muito baixo.
- **Complexidade**: Baixa.
- **Menor Correção Possível**: Adicionar um filtro de regex simples no `rho.py` e `telemetry.py` que substitua padrões conhecidos de tokens (e.g. `sk-...`, `Bearer ...`) por `[REDACTED_SECRET]`.
- **Benefício**: Conformidade de segurança e privacidade total.

---

### 🟡 P2 — MELHORIAS IMPORTANTES (Capacidades e Eficiência)

#### **P2-1: Pipeline Estruturado de Geração de Documentos**
- **Problema**: Geração de relatórios pode ser propensa a omissão de fontes ou inconsistências estruturais se for feita num único prompt.
- **Evidência**: Ausência de um executor com pipeline formal em 10 etapas para documentos técnicos/comerciais.
- **Impacto**: Eleva drasticamente a qualidade e a veracidade dos relatórios técnicos e estudos de mercado.
- **Risco**: Baixo.
- **Complexidade**: Média.
- **Menor Correção Possível**: Criar `DocumentPipelineExecutor` no `ExecutorRegistry` seguindo o fluxo: *Research $\to$ Source Collection $\to$ Structure $\to$ Draft $\to$ Validation $\to$ Review $\to$ Final Export*.
- **Benefício**: Relatórios técnicos profissionais com citações verificadas e zero alucinações.

#### **P2-2: Validação Ativa de Elementos DOM no Sandbox via Playwright**
- **Problema**: O `WebDeploymentGateway` verifica apenas o código HTTP 200 via HTTPX, mas não valida se o formulário de conversão renderizou corretamente no motor do browser.
- **Evidência**: `backend/gateway/deployment_gateway.py` faz apenas `httpx.get()`.
- **Impacto**: Assegura que landing pages geradas pelo builder funcionam interativamente antes de serem consideradas prontas.
- **Risco**: Baixo.
- **Complexidade**: Baixa.
- **Menor Correção Possível**: Adicionar verificação opcional com Playwright headless que inspeciona a existência do seletor `form` e de botões de submit.
- **Benefício**: Confiança visual e funcional completa no MVP gerado.

---

### 🟢 P3 — NICE TO HAVE (Otimizações Futuras)

#### **P3-1: Compressão e Resumo Automático de Trajetórias Longas no RHO**
- **Problema**: A base de dados SQLite `rho.sqlite` pode crescer após milhares de missões.
- **Melhoria**: Rotina de manutenção que arquiva trajetórias com mais de 30 dias mantendo apenas as regras sintetizadas consolidadas.

---

## 📈 ORDEM RECOMENDADA DE IMPLEMENTAÇÃO

```
[1. P0-1: Portão de Verificação Externa] ──► [2. P1-1: Watchdog Pós-Crash] ──► [3. P1-2: Sanitização de Logs]
                                                                                       │
[5. P2-2: Validação DOM Playwright] ◄── [4. P2-1: Pipeline de Documentos] ◄───────────┘
```
