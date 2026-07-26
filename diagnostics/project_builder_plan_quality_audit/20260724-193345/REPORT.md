# ProjectBuilder Plan Quality and Focal Correction Audit

Data: 2026-07-24
Auditoria: `20260724-193345`
Escopo: qualidade do planeamento e da correcao focal do ProjectBuilder.

Esta auditoria nao investigou novamente infraestrutura, AirLLM, Ollama runtime,
streaming, timeouts, MissionState ou materializacao. Nao executou WP1 completo,
WP2, npm, preview ou healthcheck de um projeto gerado.

## 1. Resumo executivo

O plano inicial foi JSON valido e continha uma implementacao parcial coerente,
mas falhou requisitos semanticos essenciais: nao declarou `preview`, nao mapeou
componentes para artefactos, nao demonstrou persistencia duravel e nao permitiu
ao validator associar a rota `/health` ao backend.

A correcao focal recebeu o plano completo anterior, os erros e o schema focal
v2. O protocolo derivou `allowed_plan_updates` para
`component_files`, `components` e `preview_strategy`, mas derivou
`allowed_replacements=[]` e `affected_files={}`. Isto tornou impossivel alterar
o conteudo de `server.js`, embora `PERSISTENCE_NOT_IMPLEMENTED` exigisse uma
alteracao real nesse ficheiro.

O modelo corrigiu `components` e `preview_strategy`, mas inventou seis paths em
`component_files`; apenas `server.js` existia. O resultado foi rejeitado antes
da materializacao. A mesma resposta focal foi reproduzida exactamente numa
sonda independente pelo mesmo SHA-256.

Conclusao principal: o bloqueio observado pertence primeiro ao desenho do
protocolo focal e ao namespace de artefactos, com uma exigencia de raciocinio
coordenado entre varios campos e conteudo. A capacidade geral do modelo nao foi
refutada de forma suficiente para justificar trocar o modelo.

Estrategia principal recomendada: **substituir a correcao de plano parcial por
uma correcao operacional tipada**, mantendo os validadores e exigindo que cada
operacao use IDs/caminhos existentes e que a aplicacao deterministica faca a
composicao final. O prototipo isolado desta estrategia ainda nao passou; por
isso nao e uma autorizacao de integracao.

Decisao final: `FOCAL_PROTOCOL_REDESIGN_REQUIRED`.

Confianca:

- falha semantica do plano inicial: alta;
- resposta focal historica e erros finais: alta;
- allowlist focal vazia para `server.js`: alta;
- origem dos paths inventados como convencoes do ecossistema: media-alta;
- incapacidade intrinseca do qwen3.5:9b: nao demonstrada;
- autorizacao para novo WP1: bloqueada ate um prototipo focal passar offline.

## 2. Artefactos analisados

Fonte primária do run:

- `diagnostics/project_builder_flight_recorder/5ac225a31d8b471db547d15b36b9d0e4/`
- `workspace/.jarvis/project_builder/runs/a794351f203f48828fde4de76fa34972.json`
- `workspace/.jarvis/projects/flight-recorder-wp1-9864320f2fa3/missions/mission-9864320f2fa3/`
- `workspace/.jarvis/projects/flight-recorder-wp1-9864320f2fa3/missions/mission-9864320f2fa3/executions/ce4090ed6d0a46be809b4dccade64353.json`

Codigo inspecionado:

- `agents/orchestrator/project_builder.py`
- `agents/mission_executor.py`
- `agents/orchestrator/flight_recorder.py`
- `tests/test_project_builder_correction_effectiveness.py`
- `tests/test_project_builder_focal_v2.py`
- `tests/test_project_builder_semantic_gaps.py`

Artefactos de contexto já preservados:

- `diagnostics/ollama_requester_audit/20260724-145926/`
- `diagnostics/full_system_audit/20260722-140649/`
- `docs/project_builder_flight_recorder_report.md`

Cópias e análises desta auditoria estão em:

`diagnostics/project_builder_plan_quality_audit/20260724-193345/`

O `source_hashes.json` contém hashes dos artefactos copiados e do código
inspecionado. Exemplos:

| Artefacto | SHA-256 |
|---|---|
| journal do ProjectBuilder | `ad5513e20facc8045f6cf117299b667e98bf880d90b3c6ed145159b9efec8997` |
| `events.jsonl` do Flight Recorder | `354d4c69a328245f3223731b20dd4791f7628e54841463509e22513c65d797db` |
| `summary.json` do Flight Recorder | `43e29df3615198a1bf08a0b15ef0b2e7b6b5f84e01e9ede6229e47b38cf58f28` |
| `payload_metrics.json` | `fe1e322321f3d3446b9561d9869721d1f737103356ffdbd98da10b2030a2edc0` |
| `project_builder.py` atual | `bb6a3d0f5ae7104e1dc0afb223f4d367f4e2abcb2caba5c3918874a5034fb251` |

O Flight Recorder preservou respostas normalizadas no journal, mas nao o texto
cru do prompt inicial. O modo de payload diagnostico estava desligado. A
correcao focal foi reconstruida pelo helper atual e o hash reconstruido coincide
com o hash persistido: `2a1645421ca2a8c02c23593793c135a9cedc520d87d43326af7d113ef7fb0a25`.

## 3. Intencao do WP1

O objetivo persistido na MissionState foi:

> Cria um projeto full-stack pequeno chamado health-boundary-probe, com
> frontend, backend, persistencia simples, testes executaveis e preview. Usa
> apenas Node.js standard library, sem dependencias externas. Nao uses Obsidian.

Matriz de requisitos sem acrescentar requisitos externos ao pedido:

| ID | Requisito | Obrigatorio | Origem | Criterio verificavel |
|---|---|---:|---|---|
| R1 | Nome `health-boundary-probe` | Sim | pedido | `project_name` correspondente |
| R2 | Projeto full-stack | Sim | pedido | componentes frontend e backend com artefactos mapeados |
| R3 | Frontend | Sim | pedido | ficheiro frontend real, por exemplo HTML |
| R4 | Backend | Sim | pedido | ficheiro backend real e entrypoint |
| R5 | Persistencia simples | Sim | pedido | leitura e escrita duraveis, nao apenas memoria |
| R6 | Testes executaveis | Sim | pedido | teste finito que exercita entrypoint real |
| R7 | Preview | Sim | pedido | estrategia/comando coerente com frontend |
| R8 | Apenas Node standard library, sem dependencias externas | Sim | pedido | `dependencies` vazio e imports suportados |
| R9 | Nao usar Obsidian | Sim | pedido/intent constraint | nenhum target ou escrita no Vault |
| R10 | Paths unicos, relativos e schema valido | Sim | contrato ProjectBuilder | validacao estrutural |
| R11 | Healthcheck `/health` | Contrato derivado | preview/validator | rota em backend mapeado |

R11 nao aparece literalmente no pedido persistido; foi introduzido pelo
contrato de preview/healthcheck usado pelo ProjectBuilder. Por isso nao e
classificado como omissao do pedido, mas como requisito do contrato de execucao.

## 4. Análise do prompt inicial

### Reconstrucao

O Flight Recorder registou `prompt_length=609`,
`planning_prompt_length=609` e o hash
`40b244db9fb79d154a7f761fa98279f270b362a1cb6c0ef8c1e7b4a880b3cb63`.

O texto integral desse prompt nao existe no run. O objetivo persistido tem 223
bytes e a reconstrução equivalente disponível em
`diagnostics/ollama_requester_audit/20260724-145926/wp1_prompt.txt` tem 583
bytes. Como o hash e o tamanho nao coincidem, essa cópia nao foi tratada como
o prompt exacto do M1.

Pelo codigo de `get_valid_project_plan`, o prompt enviado contém:

1. pedido do utilizador;
2. bloco `ProjectBuilder intent constraints (mandatory)`;
3. JSON de constraints negativas e targets excluidos;
4. regra para nao criar ficheiros/comandos/targets que violem constraints.

O requester acrescenta separadamente um system prompt, o schema autoritativo
do plano e instrucoes de paths, entrypoints, comandos finitos e testes reais.

### Classificacao dos blocos

| Bloco | Observacao | Classificacao |
|---|---|---|
| papel do modelo | gerador de plano JSON | VALID |
| objetivo | pedido curto, sem ambiguidade sobre os componentes | VALID |
| schema | muitos campos e tipos internos | OVERLOADED / MODEL_UNFRIENDLY |
| persistence | requisito sem tecnologia concreta, apenas "simples" | UNDERSPECIFIED |
| preview | exigido, mas sem mecanismo concreto | UNDERSPECIFIED |
| paths | relativos, mas sem namespace fechado de ficheiros candidatos | AMBIGUOUS |
| testes | devem exercitar entrypoints reais | VALID |
| constraints | no Obsidian e sem dependencias externas | VALID |
| comandos | devem terminar rapidamente, mas nao define como lidar com servidor | UNDERSPECIFIED |
| schema interno | vocabulario `array[string]`/`object[array[string]]` nao e JSON Schema Draft | MODEL_UNFRIENDLY para structured output |

Nao há evidencia de contradicao directa no prompt. Ha, contudo, muitos
conceitos concorrentes para uma resposta de 9B: componentes, mapping,
entrypoints, imports, persistencia, comandos, preview, healthcheck e testes.

### Complexidade observada

Do artefacto anterior de fronteira do requester:

- schema de plano: 15 propriedades;
- profundidade máxima observada: 6;
- schema textual: 1.243 bytes;
- prompt base de requester preservado nessa sonda: 583 bytes;
- prompt focal real do run: 7.596 bytes;
- contexto: 8.192 tokens;
- modelo: `qwen3.5:9b`.

O tamanho, por si só, nao prova falha. Prova que a tarefa combina varias
decisoes que precisam ser coerentes entre si.

## 5. Qualidade do plano inicial

Resposta inicial preservada em `validation_history[original].response`, com
1.995 caracteres e SHA-256
`5bb52a11725969fe7907c3c9b3ea29970aadaa85bae806ce03be67e96fd4540f`.

Plano observado:

- `project_name`: correcto;
- `stack`: `nodejs-standard-library`, coerente;
- `components`: `frontend`, `backend`, `persistence`, `tests`; omite `preview`;
- files: `package.json`, `server.js`, `index.html`, `test.js`;
- `component_files`: `{}`;
- entrypoints: `./server.js`, `./index.html`;
- preview: `static-server`, sem `preview_command`;
- setup: `node server.js`;
- validation: `node test.js`, `curl http://localhost:3000/health`;
- dependencies: vazio;
- constraints: vazio;
- `server.js`: contém literalmente a rota `/health`;
- `test.js`: importa `./server.js`, faz pedido real e usa `process.exit(1)` em falha;
- nao existe leitura/escrita durável.

| Requisito | Cumprido | Parcial | Violado | Evidencia |
|---|---:|---:|---:|---|
| R1 nome | Sim |  |  | nome exacto |
| R2 full-stack |  | Sim |  | files existem, mapping ausente |
| R3 frontend |  | Sim |  | `index.html` existe, nao mapeado |
| R4 backend |  | Sim |  | `server.js` existe, nao mapeado |
| R5 persistence |  |  | Sim | nenhuma operacao durável |
| R6 testes |  | Sim |  | teste exercita backend, mas setup e processo sao frágeis |
| R7 preview |  |  | Sim | componente omitido e comando vazio |
| R8 standard library | Sim |  |  | dependencies vazio/imports builtin |
| R9 Obsidian |  | Sim |  | constraint nao foi refletida em `constraints` |
| R10 schema/paths | Sim |  |  | JSON e paths dos files validos |
| R11 healthcheck |  | Sim |  | rota existe, mas mapping vazio impede evidencia |

Contagem desta matriz: 3 cumpridos, 5 parciais, 2 violados. A contagem nao é
uma pontuação do sistema; separa requisitos demonstrados de requisitos apenas
implícitos no conteúdo.

Métricas estruturais observadas:

- paths em `files`: 4, todos válidos e únicos;
- entrypoints normalizados: 2, ambos existentes;
- paths inventados no plano inicial: 0;
- mappings de componentes: 0;
- artefactos com persistencia durável: 0;
- comandos inválidos explicitamente reportados: 0;
- comandos com risco: `node server.js` é potencialmente long-running e `curl`
  nao é uma garantia da standard library/Windows;
- erro crítico: persistence e ausência de mapping.

O plano inicial nao falhou por sintaxe ou JSON. Falhou na coerência semântica
entre componentes declarados, files, comportamento e validações.

## 6. Erros dos validadores

Os validators foram executados antes de qualquer materialização. Os validators
principais estão em `_semantic_errors`, `analyze_project_artifacts`,
`semantic_error_artifact_mappings` e no fluxo `_validated_raw_project_plan`.

### Primeira resposta

| Error code | Validator/evidencia | Elemento | Qualidade |
|---|---|---|---|
| `MISSING_REQUESTED_COMPONENTS` | components nao contém preview | `components` | ACTIONABLE |
| `MISSING_COMPONENT_MAPPING` | frontend/backend sem mapping | `component_files` | PARTIALLY_ACTIONABLE |
| `DECLARED_COMPONENT_WITHOUT_ARTIFACTS` | mappings vazios para frontend/backend/persistence/tests | `component_files.*` | PARTIALLY_ACTIONABLE |
| `PERSISTENCE_NOT_IMPLEMENTED` | nao há leitura/escrita durável | persistence | ACTIONABLE, mas sem alvo de conteúdo |
| `MISSING_HEALTH_ROUTE` | nenhum backend mapeado contém `/health` | preview healthcheck | MISLEADING neste caso |

O último erro é importante: `server.js` contém `/health`, mas
`component_files.backend` está vazio. A mensagem apresenta "route not found"
sem distinguir "rota ausente" de "backend não mapeado". Isto incentiva uma
correção por criação de `routes/health.js`, embora a rota já exista.

Além disso, os cinco mapeamentos de erro da primeira fase tinham
`affected_artifacts=[]`. O mapeamento de `PERSISTENCE_NOT_IMPLEMENTED` só
adiciona artefactos de `component_files.persistence`/`backend` se eles já
existirem. Com mapping vazio, o alvo de alteração fica vazio.

### Segunda resposta

| Error code | Elemento | Qualidade |
|---|---|---|
| `MAPPED_FILE_NOT_FOUND` | `src/index.html`, `public/styles.css`, `routes/health.js` | ACTIONABLE |
| `DECLARED_COMPONENT_WITHOUT_ARTIFACTS` | mappings apontam para paths fora de files | ACTIONABLE |
| `PERSISTENCE_NOT_IMPLEMENTED` | persistence continua sem mecanismo durável | ACTIONABLE |
| `MISSING_REQUIRED_COMPONENT` | frontend nao tem artefacto compatível mapeado | ACTIONABLE |

Os erros finais descrevem o estado final com clareza razoável, mas chegam tarde:
o protocolo já aceitou que a resposta focal inventasse paths no `plan_updates`.

## 7. Prompt de correção focal

O prompt focal reconstruído exactamente tem:

- protocolo `project_builder_focal_correction_v2`;
- schema `project_builder_focal_correction_schema_v2`;
- 7.596 bytes;
- SHA-256 `2a1645421ca2a8c02c23593793c135a9cedc520d87d43326af7d113ef7fb0a25`;
- dois campos de resposta: `plan_updates` e `replacements`;
- manifest gerado pelo modelo proibido;
- máximo de duas chamadas, sem terceira correção;
- plano anterior completo e inválido incluídos;
- erros, evidencia, postconditions e mappings incluídos;
- `allowed_plan_updates`: `component_files`, `components`,
  `preview_strategy`;
- `allowed_replacements`: vazio;
- `affected_files`: vazio;
- `file_creation_allowed=false`.

O prompt inclui a regra correta de valores finais completos para `components`,
e exemplos de `Original`, `Invalido` e `Valido`. Também inclui a regra de que
uma allowlist de ficheiros nao obriga a alterar todos os ficheiros. Essas
propriedades estavam presentes no run e nao são a causa da regressão observada.

Limitações do input focal:

1. `component_files` podia ser alterado, mas nao havia lista fechada de paths
   existentes para restringir os valores do campo;
2. o modelo recebeu o plano anterior, mas a parte explícita de artefactos
   afectados estava vazia;
3. `PERSISTENCE_NOT_IMPLEMENTED` exigia alteração de conteúdo, mas o seu
   allowlist de replacements era vazio;
4. `MISSING_HEALTH_ROUTE` nao informava que a rota existia em `server.js` e
   só faltava associá-la ao backend;
5. a correcção tinha de resolver mapping, preview e persistencia coordenados,
   embora fosse chamada focal;
6. plan updates permitiam valores globais de mapping sem um schema de paths
   fechados.

O schema permite representar a correcção ideal em abstracto. O escopo derivado
para este caso concreto nao permite representá-la.

## 8. Comparação antes/depois

Resposta corrigida preservada em `validation_history[corrected]`, com 495
caracteres e SHA-256
`e021bef2af8e9418e8426c54107e7eca1f4eccc08f36a53e6916fea53d6b050c`.

| Elemento | Antes | Depois | Classificação | Efeito |
|---|---|---|---|---|
| components | 4 componentes, sem preview | 5 componentes, com preview | REQUIRED_FIX | corrigiu a omissão |
| component_files | `{}` | 7 referências | PARTIAL_FIX + NEW_HALLUCINATION | só 1 referência existia |
| preview_strategy | `static-server` | healthcheck/enabled/method | REQUIRED_FIX | tornou contrato explícito |
| replacements | nenhum | nenhum | NO_EFFECT | persistence não foi implementada |
| server.js | rota health e nenhuma persistência | inalterado | REGRESSION/NO_EFFECT | erro de persistence manteve-se |
| files | 4 paths reais | os mesmos 4 | VALID_PRESERVATION | nao houve criação de ficheiros |

Mappings da resposta corrigida:

- existente: `server.js`;
- inexistentes: `src/index.html`, `public/styles.css`, `routes/health.js`,
  `db/storage.json`, `run-tests.js`, `index-preview.html`;
- paths reportados explicitamente por `MAPPED_FILE_NOT_FOUND`: os três
  primeiros do grupo acima;
- paths adicionais rejeitados por componentes sem artefactos: os restantes.

Estados por erro derivado pelo ProjectBuilder:

- resolvidos: `MISSING_REQUESTED_COMPONENTS`, `MISSING_COMPONENT_MAPPING`,
  `MISSING_HEALTH_ROUTE`;
- mantidos: `DECLARED_COMPONENT_WITHOUT_ARTIFACTS`,
  `PERSISTENCE_NOT_IMPLEMENTED`;
- novos: `MAPPED_FILE_NOT_FOUND`, `MISSING_REQUIRED_COMPONENT`.

Pontuação de eficácia usada nesta auditoria:

```text
erros_resolvidos - erros_novos - alteracoes_fora_escopo - regressões_criticas
3 - 2 - 0 - 1 = 0
```

Foi contado um único regression critical porque a correcção introduziu uma
namespace de mappings com paths inexistentes. O resultado não é uma métrica
oficial do ProjectBuilder; é uma medida explícita para esta comparação.

## 9. Paths inventados

| Path | Apareceu primeiro | Existia antes | Origem provável |
|---|---|---:|---|
| `src/index.html` | resposta focal | Não | `inferred_from_convention` |
| `public/styles.css` | resposta focal | Não | `inferred_from_convention` |
| `routes/health.js` | resposta focal | Não | `inferred_from_error` + convention |
| `db/storage.json` | resposta focal | Não | `inferred_from_convention` para persistence |
| `run-tests.js` | resposta focal | Não | `inferred_from_component_convention` |
| `index-preview.html` | resposta focal | Não | `inferred_from_component_convention` |

Nenhum destes paths aparece no pedido original, no plano inicial ou no schema
como path concreto. O validator menciona directamente apenas os três primeiros
na mensagem de `MAPPED_FILE_NOT_FOUND`. Os outros derivam do campo que o modelo
tentou preencher e não de uma instrução textual explícita.

Isto não deve ser chamado de hallucination pura sem qualificação. A evidencia
suporta `ambiguity_induced` e `inferred_from_convention`: o modelo tinha de
preencher um mapping final, não recebeu um namespace fechado de valores e viu
erros de componentes que pediam artefactos reais. Ainda assim, os paths não
existentes são uma violação objetiva do plano.

## 10. Complexidade da correcção ideal

Foi criado o protótipo offline em:

- `offline/ideal_minimal_correction.json`;
- `offline/ideal_corrected_plan.json`;
- `offline/offline_validation.json`;
- `offline/explanation.md`.

Correcção mínima ideal:

1. `components` final: `frontend`, `backend`, `persistence`, `tests`, `preview`;
2. `component_files.frontend = ["index.html"]`;
3. `component_files.backend = ["server.js"]`;
4. `component_files.persistence = ["server.js"]`;
5. `component_files.tests = ["test.js"]`;
6. `component_files.preview = ["index.html"]`;
7. `preview_strategy.healthcheck_path = "/health"`;
8. replacement localizado de `server.js` com `node:fs`, leitura e escrita
   duráveis, preservando a rota `/health`.

Esta correcção foi aceite pelo validator de plano offline. Não foi aplicada a
nenhum projecto. É uma correcção coordenada de três campos de plano e um
ficheiro. Não é uma alteração de um único campo.

O schema focal poderia transportar essa correcção se `server.js` estivesse na
allowlist. No run real, `allowed_replacements=[]`; portanto, a correcção ideal
seria rejeitada pelo próprio limite focal antes da revalidação. Este é o facto
mais forte contra a hipótese de que a falha foi apenas falta de obediencia do
modelo.

## 11. Testes isolados do modelo

Nenhum teste abaixo entrou em MissionState ou no ProjectBuilder de execução.
Todos foram chamadas directas ao endpoint Ollama e os resultados foram apenas
analisados offline.

| Teste | Resultado | Tempo | Evidencia |
|---|---|---:|---|
| M1 exacto | NOT_TESTED | - | prompt cru de 609 bytes não foi preservado; a cópia disponível tem 583 bytes |
| M2 correcção original | JSON válido, validator rejeita | 22,995 s | SHA `e021bef2...` exactamente igual ao run real |
| M3 namespace fechado | JSON válido, validator rejeita | 4,697 s | não inventou paths, mas omitiu `component_files` |
| M4 operações | JSON válido, contrato operacional inválido | 10,869 s | `components` foi objecto, persistence apontou para `package.json` |
| M5a diagnóstico | JSON válido, diagnóstico semanticamente errado | 8,029 s | tratou persistence como mapping genérico e ignorou evidencia de `/health` |
| M5b aplicação | JSON válido, sem efeito | 4,565 s | não devolveu mappings nem replacement úteis |

M2 é uma reprodução forte da correcção, não da geração inicial: o conteúdo
inteiro da correcção e o SHA coincidem. M1 exacto permanece não demonstrado.

O M3 confirma que uma lista fechada reduz paths inventados, mas não prova que
resolve o problema. O M4 e M5 não passaram o critério de sucesso; são
protótipos negativos, não alterações produtivas.

## 12. Métricas dos testes do modelo

| Teste | JSON válido | Erros resolvidos | Erros novos | Paths inventados | Fora de escopo | Resultado |
|---|---:|---:|---:|---:|---:|---|
| M1 exacto | não executado | não medido | não medido | não medido | não medido | inconclusivo |
| M2 original | Sim | 3 | 2 códigos | 6 referências | 0 | falhou |
| M3 fechado | Sim | 1 parcial | 0 paths novos | 0 | 0 | falhou por omissão |
| M4 operações | Sim | não aplicável | 2 violações de operação | 0 | 0 | falhou contrato |
| M5 diagnóstico/aplicação | Sim | 0 | diagnóstico errado | 0 | 0 | falhou |

No M2, os três erros resolvidos são componentes, mapping vazio e healthcheck;
persistence e artefactos continuaram inválidos. A tabela conta códigos distintos
quando indica “erros novos”.

## 13. Capacidade observada do qwen3.5:9b

| Capacidade | Estado | Evidencia | Confiança |
|---|---|---|---|
| produzir JSON sintacticamente válido | MOSTLY_RELIABLE | M2-M5 válidos | alta |
| preencher components final completo | MOSTLY_RELIABLE | M2 e M3 incluíram preview | média-alta |
| preservar namespace de paths aberto | UNRELIABLE | M2 inventou 6 mappings | alta |
| cumprir namespace fechado | MOSTLY_RELIABLE | M3 não inventou paths | média |
| resolver erro local de campo | MOSTLY_RELIABLE | preview/components melhoraram | média |
| interpretar erro com evidencia de mapping | UNSTABLE | MISSING_HEALTH_ROUTE levou a estratégia extra | média-alta |
| corrigir persistence durável | UNRELIABLE nesta tarefa | M2/M5 não associaram `server.js` com fs | média |
| coordenar fields e conteúdo | UNRELIABLE nesta tarefa | allowlist vazia e M2 sem replacement | alta para o protocolo, baixa para capacidade pura |
| operar em patch tipado | UNSTABLE | M4 devolveu valores semanticamente errados | média |
| diagnóstico separado da aplicação | UNSTABLE | M5a identificou paths mas errou semântica | média |
| determinismo da correcção | MOSTLY_RELIABLE | M2 repetiu exatamente a resposta histórica | alta |
| geração inicial exacta | NOT_TESTED | prompt original cru não preservado | alta |

Não é legítimo concluir `MODEL_UPGRADE_REQUIRED` apenas com esta evidência. O
M2 mostra que o modelo é determinista para a mesma correcção, mas também que o
contrato determinista pode conduzir à mesma resposta inválida.

## 14. Avaliação do protocolo

### Planeamento inicial

O pedido funcional é curto, mas o contrato exige uma planificação global:
componentes precisam de mapping, persistence precisa de código, testes precisam
de entrypoint e preview precisa de estratégia. O schema expõe essas decisões
num único plano. Para um modelo de 9B, isto é `OVERLOADED` e parcialmente
`MODEL_UNFRIENDLY`, embora não seja provado que o prompt sozinho seja a causa.

O schema autoritativo é adequado para o validator, mas não é uma representação
particularmente fácil para geração: usa defaults, mappings opcionais,
entrypoints, commands e estratégias com dependencias cruzadas.

### Correcção focal

A correcção é focal na quantidade de chamadas, mas não é focal na dependência
semântica. Os erros requerem:

- identificar paths já existentes;
- associar components aos mesmos paths;
- reconhecer que `/health` já existe;
- alterar `server.js` para persistência;
- manter files, entrypoints, testes e preview coerentes.

Isto é uma correcção coordenada multi-campo e multi-conteúdo. A allowlist vazia
transforma uma correcção necessária numa correcção não representável.

O feedback do validator é suficiente para um engenheiro que leia o plano, mas
é parcialmente accionável para o modelo porque omite candidatos concretos e
não distingue route ausente de backend não mapeado.

## 15. Matriz de causa raiz

| Causa | Evidencia | Contraevidencia | Confiança | Impacto | Teste |
|---|---|---|---:|---|---|
| `FOCAL_SCHEMA_INADEQUATE` | persistence exigia replacement, allowlist vazia | schema abstracto suporta replacements noutros casos | Alta | impede a correcção mínima | ideal offline válido, mas não representável |
| `PATH_NAMESPACE_NOT_CLOSED` | 6 paths novos não existentes | M3 com lista fechada não inventou paths | Alta | permite hallucination de mappings | M2 vs M3 |
| `VALIDATOR_FEEDBACK_NOT_ACTIONABLE` | health route existe mas erro diz route not found | os erros têm field paths e sugestões | Média-alta | leva a `routes/health.js` | análise do plano e mappings |
| `CORRECTION_REQUIRES_GLOBAL_REASONING` | mapping, persistence, health e preview dependem entre si | correcção ideal toca só 1 file + 3 fields | Alta | “focal” não significa local | ideal correction |
| `INITIAL_PROMPT_OVERLOAD` | muitos campos/conceitos numa chamada | pedido funcional curto e JSON inicial válido | Média | aumenta risco de omissões | análise estrutural |
| `MODEL_CAPACITY_LIMIT` | M4/M5 continuam semanticamente fracos | M1 exacto não testado; M2 reproduz protocolo | Baixa | não separar do desenho | não confirmado |
| `NON_DETERMINISTIC_MODEL_FAILURE` | não observado; M2 foi igual | duas respostas M2 iguais | Muito baixa | não é explicação atual | M2 |

Causa principal escolhida: `FOCAL_SCHEMA_INADEQUATE`.

## 16. Estratégia recomendada

Escolha única: **substituir plano corrigido parcial por patch operacional tipado**.

O objectivo desta estratégia é que o modelo produza operações sobre IDs de
campos e paths existentes, enquanto o programa:

- valida cada target contra o plano real;
- compõe o plano final deterministicamente;
- rejeita qualquer path fora da namespace fechada;
- permite content replacement apenas quando o artefacto existente é elegível;
- calcula hashes e reexecuta os mesmos validators;
- não cria ficheiros nem materializa durante a correcção.

Esta é uma recomendação de protocolo, não uma implementação nesta auditoria.
O M4 não passou: o modelo devolveu `components` como objecto e mapeou
persistence para `package.json`. Logo, a estratégia ainda precisa de um
prototipo offline mais estrito antes de qualquer mudança produtiva.

Não foi escolhida troca de modelo. Não foi escolhida redução dos validators.

## 17. Prova isolada da estratégia

Resultado: **não demonstrada como suficiente**.

- M3 provou apenas que paths fechados reduzem invenções; omitiu mappings
  necessários.
- M4 produziu JSON, mas não operações semânticas correctas.
- M5 separou diagnóstico e aplicação, mas o diagnóstico atribuiu persistence de
  forma errada e a aplicação não alterou nada útil.
- O ideal offline passou os validators, mas não passou o escopo focal actual.

Portanto não há autorização para integrar a estratégia nem para executar novo
WP1. O teste isolado cumpriu o propósito de localizar a fronteira, não o
critério de sucesso de produção.

## 18. Riscos

| Risco | Estado |
|---|---|
| regressão dos validators | evitável; validators não foram alterados |
| namespace fechada demasiado restritiva | real; pode omitir correcções válidas |
| correcções coordenadas multi-ficheiro | não representadas no run |
| dependência da capacidade do modelo | presente, mas não isolada como causa única |
| aumento de chamadas | não recomendado; o limite de duas chamadas deve permanecer |
| latência | fora do escopo desta auditoria e previamente estabilizada |
| falso sucesso | não observado; sem materialização e sem success final |
| perda de evidência | raw prompt inicial não foi persistido |

## 19. Próximo passo autorizado

Uma única acção, sem executar agora:

> Criar um prototipo offline de patch operacional tipado sobre os quatro paths
> reais do plano inicial, permitindo explicitamente `server.js` para o erro de
> persistence, validar a composição com os validators reais e exigir zero paths
> novos; só depois considerar um novo WP1.

O prototipo deve permanecer fora do fluxo produtivo, sem materialização, npm,
preview ou WP2. Se não passar, a decisão deve ser revista entre reformulação
mais profunda do protocolo e modelo maior; não se deve repetir WP1 como tentativa
cega.

## 20. Decisão final

`FOCAL_PROTOCOL_REDESIGN_REQUIRED`

Novo WP1: **bloqueado**.

Razão: o plano corrigido histórico e M2 falham com a mesma resposta; M3 reduz
hallucination mas omite trabalho; M4/M5 não provaram uma representação melhor;
e a correcção mínima manual aceita pelos validators exige um replacement que o
scope focal real não permitia.

## Contexto mínimo para outro LLM

O sistema tem um ProjectBuilder real ligado a `MissionExecutorService`. O fluxo
é `MissionStateStore -> execute_work_package -> _run_project_builder ->
build_project -> get_valid_project_plan -> OllamaPlanRequester -> validators ->
uma correcção focal no máximo -> materialização -> pre-validation -> comandos e
preview -> ProjectBuildJournal -> MissionState`. A decisão de continuar ou
falhar acontece antes da escrita. O executor não avança autonomamente para WP2.

O modelo real do run foi `qwen3.5:9b`, provider Ollama, contexto 8192,
temperature 0, top_p 0.8, think false e stream true. A correcção usou
`project_builder_focal_correction_v2`, JSON Schema estruturado e a mesma
configuração. O limite de duas chamadas está preservado. Infraestrutura,
requester, streaming, timeouts, MissionState, materialização e preview não são
o próximo alvo desta investigação.

O único WP1 relevante para esta auditoria é:

- project: `flight-recorder-wp1-9864320f2fa3`;
- mission: `mission-9864320f2fa3`;
- execution: `ce4090ed6d0a46be809b4dccade64353`;
- build run: `a794351f203f48828fde4de76fa34972`;
- Flight Recorder run: `5ac225a31d8b471db547d15b36b9d0e4`.

O WP1 consumiu duas respostas completas. A primeira durou 37,235 s, teve 603
tokens de prompt avaliados, 623 de geração, 516 chunks e falhou semanticamente.
A segunda durou 8,891 s, teve 1.497 tokens de prompt avaliados, 146 de geração,
113 chunks e falhou na eficácia da correcção. Nao houve materialização, comandos,
preview, healthcheck ou ficheiro de projecto gerado.

O plano inicial completo está em
`workspace/.jarvis/project_builder/runs/a794351f203f48828fde4de76fa34972.json`,
na chave `planning_diagnostics.validation_history` com `label=original`. Ele
declara quatro componentes e quatro files:
`package.json`, `server.js`, `index.html` e `test.js`. `server.js` já contém uma
rota textual `/health`; `test.js` importa `./server.js`, faz um pedido real e
propaga falha com `process.exit(1)`. O plano não contém `component_files`, não
tem persistence durável, não declara preview e deixa `constraints` vazio.

Os erros iniciais distintos são `MISSING_REQUESTED_COMPONENTS`,
`MISSING_COMPONENT_MAPPING`, `DECLARED_COMPONENT_WITHOUT_ARTIFACTS`,
`PERSISTENCE_NOT_IMPLEMENTED` e `MISSING_HEALTH_ROUTE`. O último é parcialmente
enganador porque a rota existe, mas o backend não estava mapeado.

O prompt focal exacto foi reconstruído pelo código e bateu o hash persistido.
Ele tinha 7.596 bytes, mas produziu `allowed_replacements=[]` e
`affected_files={}`. Portanto o modelo só podia corrigir fields de plano. Para
resolver persistence de verdade, seria necessário alterar `server.js`; o
escopo não permitia isso.

A resposta focal histórica e M2 são byte-equivalentes pelo SHA
`e021bef2af8e9418e8426c54107e7eca1f4eccc08f36a53e6916fea53d6b050c`. Ela adiciona
preview e mapping para sete referências, mas seis não existem:
`src/index.html`, `public/styles.css`, `routes/health.js`, `db/storage.json`,
`run-tests.js` e `index-preview.html`. Não devolve replacements. Resultado:
`MAPPED_FILE_NOT_FOUND`, componentes sem artefactos, persistence sem implementação
e frontend incompatível.

A correcção mínima ideal, em
`offline/ideal_minimal_correction.json`, mapeia frontend para `index.html`,
backend/persistence para `server.js`, tests para `test.js`, preview para
`index.html`, explicita `/health` e altera `server.js` para usar `node:fs` com
leitura/escrita durável. O validator offline aceita-a. O protocolo focal do run
não a aceitaria por causa da allowlist vazia.

Testes isolados já executados nesta auditoria: M1 exacto não foi executado
porque o prompt cru não foi guardado; M2 reproduziu a resposta; M3 com paths
fechados não inventou paths mas omitiu mappings; M4 operacional produziu um
objecto em vez do array final de components e escolheu `package.json` para
persistence; M5 diagnóstico/aplicação produziu diagnóstico errado e nenhuma
correcção eficaz. Os resultados completos estão em
`analysis/model_evaluation.json` e `model_tests/`.

Não repetir investigação de infraestrutura nem executar WP1 antes de um único
prototipo offline de correcção operacional passar os validators, com zero paths
inventados e capacidade explícita de alterar `server.js` quando o erro for de
conteúdo. Não trocar o modelo nem enfraquecer validators com base neste run.
