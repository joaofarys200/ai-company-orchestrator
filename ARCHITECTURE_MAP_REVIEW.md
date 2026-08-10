# Revisão Independente de `architecture-map.json`

Data da revisão: 2026-07-27  
Mapa analisado: `architecture-map.json`  
Commit declarado pelo mapa: `aedd750da2279803a5715af4f0883c950554886d`  
Gerador declarado: `1.0.0`

## Conclusão executiva

O mapa é um inventário útil de módulos Python e de algumas relações lexicais,
mas não é ainda uma base de conhecimento arquitetural suficientemente precisa
para responder com confiança a perguntas de impacto, ownership ou ciclo de
vida.

Classificação: **parcialmente confiável; requer correções antes de ser usado
como fonte de decisão automática**.

Estimativas da revisão:

- Cobertura estrutural de código nas raízes de produção auditadas: **97,2%**
  (139 de 143 ficheiros Python/JS/TS/TSX encontrados têm uma referência de
  path em algum bucket). Esta métrica não mede a qualidade das relações.
- Cobertura arquitetural efetiva: **aproximadamente 70%**. O mapa encontra
  muitos símbolos, mas omite categorias importantes e mistura produção,
  fixtures, testes e diagnóstico.
- Precisão estimada das relações: **aproximadamente 65%**. A confiança é
  baixa/média porque 4.255 das 4.328 relações são inferidas por chamadas
  lexicais/AST simplificado, sem prova de binding ou execução.
- Precisão dos paths de endpoint: **baixa**. Os 14 endpoints encontrados são
  todos de `sandbox_dir`; o gateway real de produção é WebSocket e não é
  representado como endpoint operacional.

Estas percentagens são estimativas de auditoria, não métricas instrumentadas
do runtime.

## O que foi comparado

Foi lido o mapa existente e refeito um inventário read-only do repositório,
comparando:

- ficheiros fonte em `agents`, `backend`, `intelligence`, `persistence`,
  `services`, `frontend/src` e `src`;
- entrypoint `server.py` e arranque frontend;
- `websocket_schema.py`, `server.py` e `backend/websocket_gateway.py`;
- `agents/tools.py`, `agents/tool_registry.py` e `agents/orchestrator/__init__.py`;
- providers de `agents/providers` e `backend/model_harness/provider.py`;
- `MissionState`, `MissionExecutor`, `CodingSession` e `ProjectContext`;
- testes e scripts classificados pelo mapa.

Não foram executadas missões, providers, benchmarks, preview ou chamadas de
rede. `architecture-map.json` não foi regenerado nem alterado.

## Inventário declarado pelo mapa

| Bucket | Quantidade |
|---|---:|
| components | 2145 |
| relations | 4328 |
| endpoints | 14 |
| websockets | 2 |
| tools | 28 |
| agents | 0 |
| providers | 5 |
| datastores | 4 |
| workflows | 7 |
| state_machines | 2 |
| tests | 45 |
| benchmarks | 6 |
| diagnostics | 3 |
| risks | 15 |

## Falsos negativos

### 1. Agentes e executores não estão modelados

`agents` está vazio. O repositório contém, entre outros:

- `agents/mission_executor.py`, `agents/mission_state.py` e
  `agents/mission_autonomy.py`;
- `agents/swarm.py`;
- `agents/orchestrator/__init__.py` e os seus módulos de dispatch, estado,
  validação, planner e execução;
- `agents/executors/base.py`, `coding.py`, `project_build.py` e `registry.py`;
- `agents/tool_registry.py`.

O mapa representa parte destes ficheiros como módulos/classes genéricos, mas
não como agentes, executores, registry de executores ou ownership de missão.
Isto impede perguntas como “que executor trata este WorkPackage?”.

### 2. O frontend workspace desapareceu por colisão de nome

O gerador exclui qualquer path que contenha o segmento `workspace`. Essa
regra excluiu também o código real em:

- `frontend/src/features/workspace/WorkspaceViewer.tsx`;
- `frontend/src/features/workspace/CodeEditor.tsx`;
- `frontend/src/features/workspace/HologramCore.tsx`;
- `frontend/src/features/workspace/index.ts`.

São quatro ficheiros fonte de produção não representados. A exclusão deveria
ser aplicada a raízes de dados, como `workspace/`, e não a qualquer segmento
com esse nome.

### 3. Backend/model harness e Semantic Context não têm integração corretamente classificada

O mapa classifica os símbolos de `backend/model_harness` e
`backend/semantic_context` como `production_integrated`, embora a própria
evidência do mapa diga que a integração automática do Semantic Context não foi
demonstrada. O subsystem usado pelo gerador é o primeiro segmento (`backend`),
por isso a regra de reclassificação para `semantic_context` e
`capability_registry` não funciona.

O resultado correto deveria distinguir pelo menos:

- módulo existente;
- importado por produção;
- importado apenas por testes/benchmarks;
- integração runtime confirmada;
- integração runtime não demonstrada.

### 4. Providers incompletos

O bucket `providers` contém apenas os cinco ficheiros de `agents/providers`.
Ficam fora do catálogo explícito:

- `backend/model_harness/provider.py`, que define `ModelProvider`,
  `CallableModelProvider` e `ProviderRegistry`;
- `backend/model_harness/benchmarking/runner.py`, que instancia
  `OllamaBenchmarkProvider`;
- `agents/orchestrator/providers.py`, se considerado adapter de provider;
- o uso produtivo de Anthropic/Gemini/Ollama em `server.py` e no orquestrador.

O mapa não consegue distinguir o provider operacional principal do provider
de benchmark apenas pelo bucket atual.

### 5. Contratos WebSocket incompletos

O mapa tem apenas:

- `SERVER_MESSAGE_TYPES`;
- `CLIENT_MESSAGE_TYPES`.

O contrato real contém dezenas de mensagens, campos obrigatórios e regras de
validação em `websocket_schema.py`, além de handlers em `server.py` e consumo
em `frontend/src/context/WebSocketContext.tsx` e
`frontend/src/protocol/websocket.ts`. Não estão representados:

- mensagens de `project_context`, `coding_session`, `mission_snapshot`,
  `project_references`, `semantic_results`;
- operações `open_project`, `index_project`, `create_coding_session`,
  `apply_coding_session`, `rollback_coding_session`;
- requisitos de payload e validações por mensagem;
- relação cliente -> mensagem -> handler -> resposta.

### 6. Entry points não documentados

O mapa lista `server.py` no resumo, mas não modela adequadamente:

- `server.py:2525` (`main`);
- `server.py:2542` (`websockets.serve(handle_client, ...)`);
- `server.py:2545` (`if __name__ == "__main__"`);
- `frontend/src/main.tsx` como arranque Vite/React e ligação do contexto;
- scripts operacionais que são entrypoints de benchmark/diagnóstico, com
  argumentos e efeitos próprios.

O resumo menciona `src/main.py` e `main.js`, mas não prova que sejam os
entrypoints ativos no fluxo atual.

### 7. Configuração praticamente ausente

`config/agents.yaml`, `config/tasks.yaml`, `config/templates.yaml`,
`config/skills/*`, `frontend/package.json`, `requirements.txt`, `.env.example`
e configurações de provider não têm relações de dependência de configuração
por componente.

Isto é particularmente importante para `OLLAMA_MODEL`, portas WebSocket,
tokens, feature flags, scripts npm e seleção de providers.

### 8. Persistência e estado operacional sub-representados

O mapa enumera quatro datastores, mas não liga de forma demonstrada:

- `database.py` às decisões, mensagens, sessões, memória e projetos;
- `persistence/db.py` e os repositories;
- `MissionStateStore` às entidades Mission, WorkPackage, Deliverable,
  Evidence e AcceptanceCriterion;
- `CodingSession` aos snapshots, checkpoints e backups;
- ProjectContext aos índices por projeto.

O estado de `MissionExecutor` e os estados de execução não aparecem em
`state_machines`; apenas `MissionState` e `CodingSession` são listados.

## Falsos positivos

### 1. Endpoints de fixtures são apresentados como arquitetura do sistema

Os 14 endpoints do mapa apontam para:

- `sandbox_dir/api/main.py`;
- `sandbox_dir/app.py`;
- `sandbox_dir/bench_T008/server.py`;
- `sandbox_dir/server/app.py`.

Isto é código de sandbox/benchmark, não o gateway produtivo principal. O mapa
deveria classificá-los como `fixture_only` ou `benchmark_only` e separá-los do
catálogo de endpoints de produção.

### 2. Chamadas inferidas tratadas como relações arquiteturais

4.255 relações são `calls` com `confidence: inferred`. O analisador associa
nomes por correspondência global, e não por binding lexical completo. Exemplos
observados incluem:

- construtores de exceções dentro do mesmo módulo como relações arquiteturais;
- chamadas de testes para símbolos de produção como relações de produção;
- possíveis colisões de nomes entre módulos diferentes;
- chamadas geradas por referências em fixtures e diagnósticos.

Estas relações são úteis como pistas, mas não devem ter o mesmo peso visual ou
semântico de imports confirmados, rotas despachadas ou chamadas observadas.

### 3. Dependências externas falsas

O mapa declara 629 `external_dependencies`. A lista contém muitos símbolos
internos, constantes, tipos e nomes de classes, por exemplo `CodingSession`,
`CapabilityRegistry`, `Mission`, `CLIENT_MESSAGE_TYPES`, `Any` e
`AcceptanceCriterion`. Isto resulta de tratar nomes não resolvidos pelo parser
como dependências externas.

O bucket deve ser derivado de imports de topo de pacote e dos manifestos reais,
não de qualquer identificador que não tenha sido resolvido.

### 4. ChromaDB e paths conceptuais

`chroma_db` aparece como datastore `implemented_not_integrated`, mas a
existência do diretório por si só não prova uso runtime. O mesmo vale para
paths conceptuais em `workspace/.jarvis/projects` e `workspace` quando os
diretórios foram excluídos da análise. Estes itens devem indicar explicitamente
`path_conceptual` e evidência de código consumidor.

### 5. Risco central de `server.py` está correto, mas incompleto

O risco de concentração em `server.py` é confirmado. Contudo, o mapa não
regista riscos equivalentes:

- duplicação de caminhos de provider entre `server.py`, orchestrator e
  ModelHarness;
- divergência entre contrato WebSocket Python e tipos TypeScript;
- mistura de produção com fixtures em `sandbox_dir`;
- relações inferidas em massa sem validação de binding;
- exclusão acidental do frontend workspace.

## Componentes órfãos e mortos

Não é possível declarar “morto” apenas por ausência de import estático: o
repositório usa imports dinâmicos, entrypoints, configuração e reflexão.

Ainda assim, foram identificados candidatos a validação manual:

- `backend/semantic_context/*`: existem e têm testes, mas a integração no
  caminho produtivo não está demonstrada pelo mapa;
- `backend/capability_registry/*`: idem;
- `agents/providers/anthropic.py` e `agents/providers/gemini.py`: o factory
  conhece-os, mas a disponibilidade depende de configuração e não há uma
  relação de runtime confirmada no mapa;
- `services/airllm_server/*`: mistura serviço experimental, compatibilidade e
  validação; a classificação por ficheiro é insuficiente;
- scripts de benchmark/diagnóstico: não são mortos, mas devem ser separados
  de componentes de produção.

Conclusão: **componentes mortos não demonstrados**. Há candidatos órfãos
estáticos, não prova suficiente de código morto.

## Workflows

Os sete workflows do mapa são uma boa primeira enumeração, mas estão
incompletos em três dimensões:

1. A sequência contém paths, não transições confirmadas entre chamadas.
2. Não há estado, guardas, erro, retry, checkpoint ou evidência de saída por
   etapa.
3. Não existe um workflow explícito para:
   - WebSocket client -> dispatch -> serviço -> mensagem de resposta;
   - ProjectContext -> index -> referências -> CodingSession;
   - MissionState -> executor -> CodingSession/ProjectBuilder -> evidence;
   - provider selection -> ModelHarness -> validation/recovery;
   - voice directive -> confirmação -> orquestração.

Os workflows atuais devem ser marcados como `documented_static_sequence`, não
como prova de execução completa.

## Estados

`CodingSession` e `MissionState` aparecem com listas de estados plausíveis, mas
sem transições no mapa (`transitions: []`). Isto perde a parte mais importante
do contrato:

- estados permitidos por tipo de entidade;
- transições válidas e inválidas;
- pré-condições;
- efeitos de rollback;
- stale lock/version;
- estados de `MissionExecution` e de WorkPackage.

O mapa não demonstra se as transições listadas são todas as transições reais ou
apenas uma enumeração parcial.

## Contratos divergentes ou não comparados

Foram encontrados vários pares que exigem comparação semântica, mas o mapa não
os liga:

- `websocket_schema.py` vs `frontend/src/protocol/websocket.ts`;
- `SERVER_MESSAGE_TYPES`/`CLIENT_MESSAGE_TYPES` vs branches de `server.py`;
- `agents/tools.py` vs `agents/tool_registry.py` vs dispatch em
  `agents/orchestrator/__init__.py`;
- `agents/providers/factory.py` vs `backend/model_harness/provider.py`;
- `MissionState` vs `MissionExecutor` vs `websocket_schema.py`;
- `ProjectContext`/`CodingSession` vs payloads consumidos por
  `WorkspaceViewer.tsx` e `WebSocketContext.tsx`.

Não foi demonstrado um contrato divergente concreto em runtime nesta auditoria
read-only; o problema confirmado é a ausência dessas relações no mapa.

## Classificação produção/teste/diagnóstico

### Confirmada ou razoável

- `tests/*` como `test_only`;
- `scripts/*benchmark*` como `benchmark_only`;
- scripts explicitamente chamados `diagnostic` como `diagnostic_only`;
- `frontend/src` como apresentação;
- `agents/providers/factory.py` e `agents/tools.py` como partes do sistema.

### Incorreta ou insuficiente

- `sandbox_dir` não está excluído e aparece como produção implícita através de
  endpoints;
- `frontend/src/features/workspace` é excluído indevidamente;
- módulos de benchmark dentro de `backend/model_harness/benchmarking` são
  classificados como `production_integrated` porque a classificação usa apenas
  o primeiro segmento `backend`;
- `backend/semantic_context` e `backend/capability_registry` são apresentados
  como produção integrada sem prova de integração runtime;
- o mapa não distingue `fixture_only`, `experimental`, `legacy` e
  `production_active` com evidência de chamada.

## Relações que faltam

As quatro relações sugeridas são apropriadas e devem ser adicionadas numa
versão futura:

| Relação | Evidência esperada |
|---|---|
| `ownership` | registry, composição, handler ou serviço que cria/possui o componente |
| `runtime_lifecycle` | startup, create, stop, dispose, restart, shutdown |
| `configuration_dependency` | leitura concreta de `.env`, YAML, JSON, argumentos ou defaults |
| `execution_frequency` | startup, request, mission, benchmark, test ou diagnostic |

Também recomendo:

- `dispatches_to` para WebSocket/commands;
- `implements_contract` para Python/TypeScript/tool schemas;
- `persists_to` e `reads_from` para DB/files/indexes;
- `validates` e `recovers_with` para validation/recovery;
- `fixture_for` para sandbox e benchmark;
- `imports` confirmado separado de `calls_inferred`.

## Melhorias recomendadas, por prioridade

### P0 — Corrigir o escopo

1. Corrigir a exclusão de `workspace` para não excluir
   `frontend/src/features/workspace`.
2. Excluir ou marcar explicitamente `sandbox_dir`, `scratch`, `obsidian_vault`
   e artefactos gerados como fixture/diagnóstico.
3. Separar buckets `production`, `test`, `benchmark`, `diagnostic`, `fixture`
   e `legacy` antes de gerar riscos e endpoints.

### P1 — Corrigir confiança das relações

1. Fazer resolução de imports por módulo e símbolos por escopo.
2. Não promover chamadas inferidas a relação arquitetural sem um campo de
   confiança e sem distinguir intra-módulo, cross-module e test-only.
3. Derivar dependências externas apenas de imports de pacote/manifests.

### P1 — Modelar contratos operacionais

1. Extrair cada mensagem WebSocket, campos obrigatórios, produtor, consumidor
   e resposta.
2. Extrair tools do registry e ligá-las a implementações e dispatchers.
3. Extrair providers de todos os adapters e registries, incluindo ModelHarness.

### P2 — Modelar execução

1. Representar entrypoints reais e comandos que os iniciam.
2. Adicionar `ownership`, `runtime_lifecycle`, `configuration_dependency` e
   `execution_frequency`.
3. Representar transições e guardas de MissionState, MissionExecution,
   WorkPackage e CodingSession.
4. Ligar datastores a operações concretas de leitura/escrita.

### P2 — Qualidade e manutenção

1. Adicionar testes de precisão com fixtures conhecidas e expected graph.
2. Guardar `analysis_commit`, `working_tree_state` e origem de cada relação.
3. Produzir uma lista explícita de `not_found` versus `not_analyzed`.
4. Não usar `architecture-map.json` anterior como input da própria análise.

## Resultado final

- **Cobertura estimada:** 70% arquitetural; 97,2% de paths de código nas
  raízes auditadas.
- **Precisão estimada:** 65% global, com precisão baixa para endpoints,
  dependências externas e chamadas inferidas.
- **Falsos positivos principais:** endpoints de `sandbox_dir`, 629 dependências
  externas inflacionadas, relações `calls` inferidas sem binding e componentes
  de benchmark classificados como backend de produção.
- **Falsos negativos principais:** agentes, executores, frontend workspace,
  mensagens WebSocket individuais, providers ModelHarness, dependências de
  configuração, persistência operacional e estados/transições de execução.
- **Melhoria mais importante:** corrigir primeiro o escopo e a separação
  produção/fixture; sem isso, relações adicionais aumentariam o ruído.

Estado do mapa: **útil para navegação inicial, não apto como fonte autoritativa
de impacto arquitetural**.
