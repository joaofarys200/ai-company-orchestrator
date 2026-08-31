# Relatório de Auditoria Técnica e Taxonomia do Portfólio GitHub

**Perfil Alvo**: [github.com/joaofarys200](https://github.com/joaofarys200)  
**Auditor**: Antigravity Autonomous Engineering Agent  
**Data**: Agosto de 2026  
**Identidade Alvo**: *"Estudante de Engenharia Informática / Mestrando com sólida amplitude técnica e um projeto individual sério de engenharia."*

---

## 1. Resumo Executivo

Foi realizada uma auditoria técnica detalhada e em modo de apenas-leitura a todos os repositórios públicos e acessíveis sob a conta GitHub `@joaofarys200`.

### Principais Conclusões da Auditoria
1. **Força Principal**: O utilizador possui um projeto individual de grande dimensão, rigoroso e testado: **JARVIS OS (`ai-company-orchestrator`)**, com 953 testes automatizados, 10 esquemas de arquitetura em SVG, 6 ADRs e 10 relatórios de validação empírica.
2. **Ponto Fraco Anterior do Portfólio**: O perfil exibia uma biografia genérica de estudante (*"Repositório de projetos desenvolvidos durante a licenciatura..."*), sem tópicos/tags, sem descrições de uma linha e com READMEs vazios na maioria dos projetos académicos, fazendo com que o projeto principal ficasse "escondido" entre exercícios de aula.
3. **Amplitude Técnica Real**: Vários repositórios universitários possuem engenharia técnica muito interessante (motor 3D C++ com curvas de Bezier e Catmull-Rom, servidor concorrente distribuído em Erlang com atores, sistema de apoio à decisão em Python com previsão multivariada e otimização metaheurística NSGA-II, e microsserviço Docker/Nginx/Prometheus com autoscaler dinâmico). Faltava documentação estruturada que demonstrasse esse valor a recrutadores e avaliadores.

---

## 2. Inventário Completo e Avaliação dos Repositórios

| # | Nome do Repositório | Linguagem Principal | Tamanho (KB) | Commits | Estado do README | Tipo | Classificação no Portfólio | Valor de Portfólio |
|---|---|---|---|---|---|---|---|---|
| 1 | **`ai-company-orchestrator`** | Python / TypeScript / HTML | ~35.000 | 50+ | Completo (15 KB) | **Individual / Independente** | **`FLAGSHIP`** | **Crítico (10/10)** |
| 2 | **`CG`** | C++ / CMake | 12.305 | 11 | Básico 4 Fases (4.1 KB) | Académico (Grupo de 4) | **`STRONG / SUPPORTING`** | **Alto (8.5/10)** |
| 3 | **`Tiapose2026`** | Python | 19.917 | 33 | Nenhum (0 KB) | Académico (Individual/Grupo) | **`STRONG / SUPPORTING`** | **Alto (8.5/10)** |
| 4 | **`ITIPOSAPRESENTACAO`** | Python / Docker | 7 | 1 | Nenhum (0 KB) | Académico (Individual/Grupo) | **`SUPPORTING`** | **Médio-Alto (7.5/10)** |
| 5 | **`PC`** | Erlang / Processing | 21 | 6 | Placeholder (4 bytes) | Académico (Individual/Grupo) | **`SUPPORTING`** | **Médio-Alto (7.5/10)** |
| 6 | **`SSD`** | Python / Streamlit | 17.157 | 7 | Nenhum (0 KB) | Académico (Individual/Grupo) | **`ACADEMIC`** | **Médio (6.5/10)** |
| 7 | **`aase`** | Python / Jupyter | 28 | 2 | Nenhum (0 KB) | Académico (Individual/Grupo) | **`ACADEMIC`** | **Médio (6.0/10)** |
| 8 | **`PLC`** | Python (PLY) | 3 | 1 | Nenhum (0 KB) | Académico (Individual/Grupo) | **`ACADEMIC`** | **Médio (6.0/10)** |
| 9 | **`ITI-2025`** | Python / Docker | 10 | 7 | Nenhum (0 KB) | Académico (Grupo) | **`ARCHIVE`** | **Baixo (Substituído pelo #4)** |
| 10 | **`tvsi-pytest`** | Python | 3 | 3 | Nenhum (0 KB) | Académico (Individual) | **`ARCHIVE`** | **Baixo (Demo de aula)** |
| 11 | **`Programa-o-Concorrente`**| Nenhum | 0 | 0 | Nenhum (0 KB) | Académico (Placeholder) | **`ARCHIVE`** | **Nulo (Repo vazio)** |

---

## 3. Análise Detalhada dos Projetos

### 3.1. `ai-company-orchestrator` (JARVIS OS)
- **Classificação**: **`FLAGSHIP`** (Projeto Individual Independente)
- **Domínio Técnico**: Sistemas Cognitivos Multi-Agente, Manipulação de AST / Compiladores, Endpoint Detection & Response (EDR), RAG e Grafos Epistémicos.
- **Stack Tecnológico**: Python 3.11+, TypeScript, React 18, Electron Desktop HUD, SQLite, Chrome DevTools Protocol, Playwright, Whisper, ModelHarness (Ollama / OpenRouter / Anthropic / OpenAI).
- **Evidências de Validação**: 953 testes aprovados (`pytest`), 10 esquemas de arquitetura SVG, 10 relatórios de validação empírica, 6 ADRs, Schemas JSON Draft-07.
- **Qualidade Documental**: Elevada (README de 15 KB, pasta `docs/`, `SECURITY.md`, `ARCHITECTURE.md`).
- **Papel no Portfólio**: O projeto central e indiscutível, comprovando visão arquitetural, engenharia de software autónoma e capacidade de entrega a longo prazo.

---

### 3.2. `CG` (Motor 3D OpenGL & Sistema Solar)
- **Classificação**: **`STRONG / SUPPORTING`** (Académico — 3.º Ano de CC/Eng. Informática, Nota: 17/20)
- **Domínio Técnico**: Computação Gráfica, Modelação Geométrica e Renderização 3D de Baixo Nível.
- **Stack Tecnológico**: C++17, OpenGL, CMake, Shaders GLSL, GLUT/GLEW, Parser XML.
- **Funcionalidades Chave**:
  - Gerador de primitivas procedimentais (`plano`, `cubo`, `esfera`, `cone`, `toro`).
  - Grafo de cena hierárquico com transformações compostas a partir de ficheiros XML.
  - Animação de câmara e órbitas através de splines cúbicas de Catmull-Rom.
  - Tesselação de superfícies paramétricas de Bezier (cometa, bule).
  - Aceleração por hardware com Vertex Buffer Objects (VBOs).
  - Modelo de iluminação de Phong (componentes ambiente, difusa e especular) e mapeamento de texturas com coordenadas UV.
- **Papel no Portfólio**: Demonstra rigor em sistemas C++, base matemática sólida (álgebra linear, cálculo paramétrico) e domínio de pipelines gráficos.

---

### 3.3. `Tiapose2026` (Sistema de Apoio à Decisão: Previsão & Otimização)
- **Classificação**: **`STRONG / SUPPORTING`** (Académico — Ciência de Dados & Investigação Operacional)
- **Domínio Técnico**: Previsão de Séries Temporais, Econometria Exógena, Otimização Metaheurística Evolutiva, Dashboards Interativos.
- **Stack Tecnológico**: Python, Streamlit, Plotly, Pandas, NumPy, Scikit-learn, XGBoost, Statsmodels (SARIMAX, VAR), Nevergrad, Pymoo (NSGA-II, Algoritmos Genéticos), Scipy.
- **Funcionalidades Chave**:
  - Previsão multivariada de procura de clientes para 4 lojas regionais (Baltimore, Lancaster, Filadélfia, Richmond).
  - Validação cruzada temporal com backtesting de 12 janelas para horizontes $h \in [1, 7]$.
  - Otimização metaheurística multiobjetivo para escalonamento de recursos com 84 variáveis de decisão ($[PR, X, J] \times 4 \text{ lojas} \times 7 \text{ dias}$).
  - Operadores customizados de reparação (`Repair`), mutação e verificação de restrições operacionais.
  - Dashboard interativo em Streamlit com análise de fronteira de Pareto e curvas comparativas no Plotly.
- **Papel no Portfólio**: Demonstra capacidade analítica, matemática e algorítmica aplicada à ciência de dados e otimização.

---

### 3.4. `ITIPOSAPRESENTACAO` (Microsserviço em Nuvem & Autoscaler Prometheus)
- **Classificação**: **`SUPPORTING`** (Académico — Infraestruturas Cloud & DevOps)
- **Domínio Técnico**: Microsserviços, Reverse Proxy, Contentores, Telemetria e Autoscaling Dinâmico.
- **Stack Tecnológico**: Docker, Docker Compose, Nginx, Prometheus, cAdvisor, Python Flask, Flasgger (OpenAPI/Swagger), Volume NFS partilhado.
- **Funcionalidades Chave**:
  - Arquitetura multicontentor com isolamento de rede e volumes.
  - Load balancer dinâmico em Nginx com resolução de DNS interno do Docker e TTL de 5 segundos (`zone ... resolve`).
  - Exposição de métricas via `prometheus_client` e recolha de telemetria de hardware dos contentores com cAdvisor.
  - Autoscaler Horizontal em Python que consulta periodicamente a API HTTP do Prometheus (uso agregado de CPU, taxa de pedidos por segundo e taxa de erros 5xx) e ajusta dinamicamente as réplicas da API com `docker compose up --scale api=N`.
- **Papel no Portfólio**: Comprova competências reais em DevOps, orquestração de contentores e observabilidade de sistemas em produção.

---

### 3.5. `PC` (Servidor de Jogo Concorrente Distribuído em Erlang)
- **Classificação**: **`SUPPORTING`** (Académico — Sistemas Distribuídos & Concorrência)
- **Domínio Técnico**: Concorrência com Modelo de Atores, Comunicação por Sockets TCP, Sistemas Distribuídos.
- **Stack Tecnológico**: Erlang/OTP (`gen_tcp`, processos, passagem de mensagens), Processing (Cliente gráfico em Java).
- **Funcionalidades Chave**:
  - Servidor multi-cliente TCP desenhado segundo o Modelo de Atores do Erlang.
  - Processos concorrentes isolados para gestão de ligações, autenticação e filas de espera/matchmaking.
  - Processo de simulação de jogo com ciclo temporal determinístico (`timer:send_interval`).
  - Persistência e serialização binária de contas e níveis em disco (`accounts.bin`, `levels.bin`).
- **Papel no Portfólio**: Demonstra compreensão aprofundada de primitivas de concorrência, passagem assíncrona de mensagens e tolerância a falhas sem bloqueios ou mutexes.

---

### 3.6. `SSD` (Motor de Regras de Decisão para E-Commerce)
- **Classificação**: **`ACADEMIC`** (Académico — Sistemas de Suporte à Decisão)
- **Stack Tecnológico**: Python, Streamlit, Schemas JSON de Regras, API DecisionRules.io, Pandas, Plotly.
- **Funcionalidades**: Avaliação em tempo real do carrinho de compras para gerar recomendações de upsell/cross-sell com cálculo de margens e explicações contextuais.

---

### 3.7. `aase` (Pipeline Preditivo de Saúde Mental & Dashboard)
- **Classificação**: **`ACADEMIC`** (Académico — Aprendizagem Automática / CRISP-DM)
- **Stack Tecnológico**: Python, CRISP-DM, Scikit-learn (Árvores de Decisão, Random Forest, KMeans), Streamlit, Plotly, Joblib.

---

### 3.8. `PLC` (Compilador / Frontend: Lexer & Parser)
- **Classificação**: **`ACADEMIC`** (Académico — Processamento de Linguagens & Compiladores)
- **Stack Tecnológico**: Python, PLY (Python Lex-Yacc), Gramáticas BNF, Geração de AST.

---

### 3.9. `ITI-2025`, `tvsi-pytest`, `Programa-o-Concorrente`
- **Classificação**: **`ARCHIVE`** (Deixar não fixados / arquivados).

---

## 4. Matriz Estruturada do Portfólio

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                               FLAGSHIP (Destaque Principal)                      │
│  ai-company-orchestrator (JARVIS OS) — Sistema Multi-Agente & EDR Autónomo       │
└──────────────────────────────────────────────────────────────────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│     SUPPORTING 1: Sistemas & 3D       │   │    SUPPORTING 2: DS & Otimização      │
│  CG — Motor 3D OpenGL C++ (Nota: 17)  │   │  Tiapose2026 — DSS Previsão & NSGA-II │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
                   │                                           │
                   ▼                                           ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│    SUPPORTING 3: Cloud & DevOps       │   │    SUPPORTING 4: Concorrência & Distr │
│  ITIPOSAPRESENTACAO — Infra & Scaler  │   │  PC — Servidor Erlang (Atores / TCP)  │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             AMPLITUDE ACADÉMICA BASE                             │
│  SSD (Regras de Decisão) • aase (ML / CRISP-DM) • PLC (Compiladores & Gramáticas)│
└──────────────────────────────────────────────────────────────────────────────────┘
```
