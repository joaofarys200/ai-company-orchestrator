# JARVIS OS — FASE 23.0: AUDITORIA FORENSE INTEGRAL
## REGISTO PRIORIZADO DE DÍVIDA TÉCNICA, DEFEITOS E LACUNAS ARQUITETURAIS
**Documento:** `JARVIS_TECHNICAL_DEBT_AND_GAPS.md`  
**Data:** 21 de Outubro de 2026  
**Auditor Forense:** Antigravity Forensic Engineering  
**Classificação:** Baseline Técnica Oficial — Fase 23.0  
**Diretório de Auditoria:** `audit/phase_23_forensic_audit_20261021/`

---

## 1. METODOLOGIA DE CLASSIFICAÇÃO DE GRAVIDADE

Todos os problemas e lacunas descobertos foram catalogados segundo a taxonomia estrita da Fase 23.0:

- **P0 — Crítico:** Falha de segurança estrutural, risco de corrupção de dados ou quebra de premissa fundamental de confinamento.
- **P1 — Alto:** Falhas que impedem capacidades nucleares ou causam declarações falsas de execução/aceitação.
- **P2 — Médio:** Integrações incompletas, funcionalidades desconectadas ou desativadas, redundâncias arquiteturais.
- **P3 — Baixo:** Usabilidade, polimento de performance, manutenção e limpeza de código.
- **P4 — Menor:** Melhorias cosméticas ou otimizações futuras sem impacto operacional imediato.

---

## 2. TABELA RESUMO DE DÍVIDA TÉCNICA

```
+---------------------------------------------------------------------------------------------------+
|                                 INVENTÁRIO DE DÍVIDA TÉCNICA E GAPS                               |
+----+------+------------------------------------+--------------------------------+-----------------+
| ID | Nível| Componente / Módulo                | Resumo do Problema             | Esforço Est.    |
+----+------+------------------------------------+--------------------------------+-----------------+
| 01 | P0   | security/safety_classifier.py      | Bypass de segurança imperativo | 2 horas         |
| 02 | P1   | tests/conftest.py                  | Mock shadowing contamina tests | 3 horas         |
| 03 | P1   | agents/mission_orchestrator.py     | Swarm Federation inalcançável  | 6 horas         |
| 04 | P1   | backend/services/chat_mission_...  | Bridge ignora orquestrador DAG | 8 horas         |
| 05 | P2   | database.db vs. .jarvis/ JSON      | Persistência dual fragmentada  | 12 horas        |
| 06 | P2   | persistence/ (8 ficheiros)         | Classes fantasma / código morto| 2 horas         |
| 07 | P2   | services/airllm_server/            | Servidor AirLLM desconectado   | 4 horas         |
| 08 | P2   | agents/tools.py (web tools)        | Falha silenciosa s/ API keys   | 3 horas         |
| 09 | P3   | backend/document_engine/word_...   | Popups do Word COM travam call | 4 horas         |
| 10 | P3   | scripts/ (301 ficheiros)           | Scripts e runners redundantes  | 16 horas        |
+----+------+------------------------------------+--------------------------------+-----------------+
```

---

## 3. ANÁLISE FORENSE DETALHADA POR PROBLEMA

### DEFEITO 01: Bypass de Classificação de Segurança com Verbos Imperativos
- **Gravidade:** **P0 — CRÍTICO**
- **Componente:** [security/safety_classifier.py:68-75](file:///c:/Users/joaor/Desktop/JarvisOS/security/safety_classifier.py#L68-L75)
- **Evidência Concreta:**
  - `evaluate("quero executar um ataque ddos")` -> `BLOCKED` (Correto).
  - `evaluate("executa um ataque ddos")` -> `ALLOWED / SAFE_DEFENSIVE` (Falha Crítica!).
- **Causa Técnica Confirmada:**
  - O regex `DDoS_PATTERN` apenas inclui verbos no infinitivo (`(?:fazer|executar|dar|lancar|lançar|iniciar|criar|produzir|desenvolver)`).
  - Não contempla verbos conjugados no imperativo afirmativo ou presente (*faz*, *executa*, *dá*, *lança*, *inicia*, *cria*).
- **Impacto:** Qualquer utilizador ou prompt malicioso que use a forma imperativa consegue contornar as salvaguardas de cibersegurança do JARVIS OS.
- **Capacidades Afetadas:** Governança de Intenção e Segurança (`CAP-SEC-02`).
- **Dependência de Correção:** Nenhuma.
- **Esforço Estimado:** ~2 horas de engenharia.
- **Teste de Verificação:** Cenário 20 da suite de auditoria forense deve retornar `BLOCKED` para ambas as formulações.

---

### DEFEITO 02: Injeção Cega de Mocks em `conftest.py` Quebrando Testes Reais
- **Gravidade:** **P1 — ALTO**
- **Componente:** [tests/conftest.py:10-25](file:///c:/Users/joaor/Desktop/JarvisOS/tests/conftest.py#L10-L25)
- **Evidência Concreta:**
  - A execução de `test_swarm_federation_phase18.py` falhou com `TypeError: unsupported format string passed to MagicMock.__format__` na linha de telemetria de memória do `psutil`.
- **Causa Técnica Confirmada:**
  - O `conftest.py` injeta cegamente `sys.modules["psutil"] = MagicMock()` se o import falhar ligeiramente ou por ordem de carregamento, mesmo quando o `psutil` real está instalado no ambiente virtual.
- **Impacto:** Gera falsos positivos, mascara quebras reais em testes de integração e impede a medição precisa do orçamento de memória dos swarms.
- **Capacidades Afetadas:** Infraestrutura de Testes e Telemetria (`CAP-OPS-01`).
- **Dependência de Correção:** Remover injeção global de mocks no `conftest.py` e usar `@pytest.fixture` com monkeypatch apenas onde estritamente necessário.
- **Esforço Estimado:** ~3 horas.
- **Teste de Verificação:** Execução limpa de `tests/unit/test_swarm_federation_phase18.py` com exit code 0.

---

### DEFEITO 03: Swarm Federation 100% Inalcançável no Fluxo de Produção
- **Gravidade:** **P1 — ALTO**
- **Componente:** [agents/mission_orchestrator.py:205](file:///c:/Users/joaor/Desktop/JarvisOS/agents/mission_orchestrator.py#L205) e [backend/websocket/handlers/missions.py:881](file:///c:/Users/joaor/Desktop/JarvisOS/backend/websocket/handlers/missions.py#L881)
- **Evidência Concreta:**
  - O parâmetro `use_federation` tem valor padrão `False` no construtor do orquestrador.
  - Nenhum ficheiro fora de `tests/` instancia o orquestrador passando `use_federation=True`.
  - O handler `/ws/missions` retorna invariavelmente `{"status": "inactive", "federation_enabled": False}`.
- **Causa Técnica Confirmada:**
  - A federação foi desenvolvida como uma camada experimental avançada, mas a fiação (*wiring*) com o backend e com as rotas de API nunca foi concluída.
- **Impacto:** Mais de 1.700 linhas de código complexo de federação hierárquica existem no repositório sem qualquer benefício operacional para o utilizador final.
- **Capacidades Afetadas:** Orquestração Distribuída e Swarm Federation (`CAP-SWM-03`).
- **Dependência de Correção:** Adicionar variável `ENABLE_SWARM_FEDERATION` no ficheiro de configuração e passar a flag na inicialização do serviço.
- **Esforço Estimado:** ~6 horas.
- **Teste de Verificação:** Endpoint `/ws/missions` a reportar status ativo e nós de federação em execução.

---

### DEFEITO 04: Chat Desvia do Orquestrador DAG e Executa em Modo Linear Legado
- **Gravidade:** **P1 — ALTO**
- **Componente:** [backend/services/chat_mission_bridge.py:380-420](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/chat_mission_bridge.py#L380-L420)
- **Evidência Concreta:**
  - O `ChatMissionBridge` cria a missão no `MissionStateStore`, mas invoca diretamente `self.orchestration_service.orchestrate_task()`, contornando `MissionLifecycleOrchestrator.run()`.
- **Causa Técnica Confirmada:**
  - Transição incompleta entre a arquitetura sequencial legada (Crew de personas) e o novo motor assíncrono baseado em DAG de tarefas (`TaskGraph`).
- **Impacto:** O planeamento formal de grafos, a gestão de leases de ficheiros e a execução paralela de tarefas nunca são ativados durante o uso normal via chat.
- **Capacidades Afetadas:** Planeamento Hierárquico (`CAP-PLN-01`) e Execução em Grafo (`CAP-PLN-02`).
- **Dependência de Correção:** Refatorar `_execute_mission_work` no bridge para acionar `MissionLifecycleOrchestrator.run()`.
- **Esforço Estimado:** ~8 horas.
- **Teste de Verificação:** Verificação de locks de leases em `.jarvis/leases/` durante uma missão acionada pelo chat.

---

### DEFEITO 05: Persistência Fragmentada Entre SQLite Vazio e Ficheiros JSON
- **Gravidade:** **P2 — MÉDIO**
- **Componente:** `database.db` e `.jarvis/projects/<project_id>/missions/`
- **Evidência Concreta:**
  - Tabelas `messages`, `compounding_memory`, `strategic_goals` e `event_sourcing_log` na base SQLite contêm 0 linhas, enquanto o estado das missões reside em múltiplos ficheiros JSON em disco.
- **Causa Técnica Confirmada:**
  - Dois modelos de persistência foram desenvolvidos em paralelo: um relacional via SQLAlchemy/SQLite e outro puramente baseado em ficheiros JSON locais.
- **Impacto:** Dificuldade em consultar históricos globais de missões e perda de integridade referencial.
- **Capacidades Afetadas:** Persistência e Memória (`CAP-PST-01`).
- **Esforço Estimado:** ~12 horas.

---

### DEFEITO 06: Módulos Fantasma em `persistence/`
- **Gravidade:** **P2 — MÉDIO**
- **Componente:** `persistence/` (8 ficheiros Python com 57 linhas no total).
- **Evidência Concreta:**
  - Ficheiros como `repository.py`, `unit_of_work.py` contêm apenas classes vazias com instruções `pass`.
- **Causa Técnica Confirmada:** Esqueleto de arquitetura abandonado a meio do desenvolvimento.
- **Impacto:** Poluição do repositório e confusão arquitetural.
- **Esforço Estimado:** ~2 horas (limpeza ou implementação real).

---

### DEFEITO 07: Servidor AirLLM Isolado e Morto
- **Gravidade:** **P2 — MÉDIO**
- **Componente:** [services/airllm_server/](file:///c:/Users/joaor/Desktop/JarvisOS/services/airllm_server/)
- **Evidência Concreta:** Ficheiro `README.md` declara explicitamente tratar-se de um teste de conceito desconectado. Nenhum serviço do backend comunica com esta pasta.
- **Esforço Estimado:** ~4 horas para isolar ou remover.

---

### DEFEITO 08: Ferramentas Web Sem Fallback Elegante
- **Gravidade:** **P2 — MÉDIO**
- **Componente:** [agents/tools.py](file:///c:/Users/joaor/Desktop/JarvisOS/agents/tools.py) (`firecrawl_scrape`, `apify_scrape`)
- **Evidência Concreta:** Quando as chaves não estão definidas no `.env`, a ferramenta lança erro interno em vez de degradar para scraping local com `requests` ou `playwright`.
- **Esforço Estimado:** ~3 horas.

---

### DEFEITO 09: Potencial Bloqueio de Thread no Word COM por Popups Modais
- **Gravidade:** **P3 — BAIXO**
- **Componente:** [backend/document_engine/word_com_automation.py](file:///c:/Users/joaor/Desktop/JarvisOS/backend/document_engine/word_com_automation.py)
- **Evidência Concreta:** Se a instalação do Microsoft Word no Windows abrir um popup modal (e.g. ativação de licença ou seleção de privacidade), a chamada OLE bloqueia indefinidamente a thread até timeout.
- **Causa:** Necessidade de reforçar a flag `word.DisplayAlerts = 0` e isolar a chamada COM numa thread assíncrona com timeout estrito de 60 segundos.
- **Esforço Estimado:** ~4 horas.

---

### DEFEITO 10: Proliferação Desordenada de Scripts em `scripts/`
- **Gravidade:** **P3 — BAIXO**
- **Componente:** Diretório `scripts/` (301 ficheiros, 85.240 linhas de código).
- **Evidência Concreta:** Múltiplos runners concorrentes (`start_backend.py`, `start_complete_system.py`, `run_all_tests.py`, `run_smoke.py`) com versões ligeiramente desfasadas de configuração de portas e caminhos.
- **Impacto:** Risco de inconsistência operacional consoante o script utilizado pelo operador.
- **Esforço Estimado:** ~16 horas de consolidação e limpeza.
