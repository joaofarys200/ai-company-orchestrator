# Diagnóstico do contexto do ProjectBuilder com Ollama

Data da medição: 21-07-2026. Esta investigação não alterou o código funcional, o modelo, o `.env` ou o fluxo de validação. A captura foi feita por monkey-patch apenas em memória num processo Python descartável; a instrumentação desapareceu quando o processo terminou.

## 1. Resumo executivo

Classificação: **B — existe um limite configurado de 8192, mas os pedidos reais medidos ficam abaixo dele e não há evidência de truncamento**.

- O ProjectBuilder envia `num_ctx=8192` em cada chamada ao Ollama porque `.env:6` contém `PROJECT_BUILDER_PLAN_CONTEXT_TOKENS=8192`.
- O código tem fallback de `32768` em `agents/orchestrator/project_builder.py:3918`; portanto, 8192 não é o limite nativo do modelo nem uma constante global do Ollama.
- O modelo local expõe `qwen35.context_length=262144` em `/api/show`. O `Modelfile` não define `num_ctx`.
- A chamada inicial usa JSON mode (`format="json"`); a correção usa o schema estruturado de `project_builder_focal_correction_v2` (`format={...}`), mantendo o mesmo `num_ctx`.
- Foram executados três pedidos reais (pequeno, médio e SaaS de inventário). Cada pedido fez duas chamadas: geração inicial e correção focal. Foram seis respostas HTTP 200.
- Todos os chunks finais tinham `done_reason="stop"`; nenhum terminou por `length`, nenhum timeout ocorreu, e não houve erro HTTP, CUDA ou resposta não-JSON.
- A utilização medida de contexto (tokens de entrada + saída, comparada com 8192) variou entre 17,0% e 38,3%. As falhas observadas foram exclusivamente `PLAN_SEMANTIC_INVALID` após a única correção permitida.
- A medição não prova que qualquer pedido futuro é seguro: uma correção suficientemente grande pode consumir a janela. Prova apenas que os casos reais observados não atingem o limite.

## 2. Caminho completo das chamadas

1. `server.py:2336-2340` chama `build_project(prompt, ...)` para pedidos de criação.
2. `agents/orchestrator/project_builder.py:7040-7055` valida a intenção e cria `OllamaPlanRequester` quando não é fornecido um requester alternativo. O plano é obtido antes de qualquer materialização (`:7071-7077`).
3. `get_valid_project_plan` (`:5837-5844`) acrescenta apenas os constraints derivados da intenção (`_prompt_with_intent_constraints`, `:4433-4445`) e faz a primeira chamada.
4. A primeira chamada chega a `OllamaPlanRequester.__call__` (`:4288-4309`) e `_generate` (`:4150-4181`), que faz `POST http://127.0.0.1:11434/api/chat`.
5. A resposta é acumulada por streaming JSONL. O ProjectBuilder verifica HTTP, JSON, `done`, `done_reason` e limites de saída (`:4181-4286`).
6. O plano é validado localmente (`:5849-5853`). Se falhar, `_structured_plan_correction` (`:5799-5806`) cria a correção focal.
7. A segunda e última chamada reutiliza o mesmo requester (`:5864-5870`), com `project_builder_focal_correction_v2` e schema estruturado. A ausência de terceira chamada está explícita em `PLAN_MAX_ATTEMPTS=2` (`:67`), no contrato de correção (`:5583-5586`, `:5710-5713`) e no erro final (`:5901-5903`).
8. Só depois de um plano válido começa a materialização (`:7071-7085`). Nos três casos deste diagnóstico a validação falhou, logo nenhum projeto foi materializado.

### Chamadas Ollama relacionadas, mas fora do planeamento

- `agents/orchestrator/__init__.py:1104-1141` pode chamar `/api/generate` para classificar complexidade quando `ORCHESTRATOR_COMPLEXITY_MODEL_ENABLED=true`; usa `num_predict=10`, não define `num_ctx` e não é chamado por `build_project` no caminho de `server.py` acima.
- `agents/orchestrator/__init__.py:1145-1213` usa `/api/chat` para agentes com ferramentas, sem `num_ctx`; é outro fluxo.
- `intelligence/coding_session.py:928-951` usa `/api/chat` para plano de edição, também sem `num_ctx`.
- Não existe `/api/generate` dentro da implementação do ProjectBuilder. A única chamada de geração do ProjectBuilder é `/api/chat` em `:4181`.

## 3. Origem e semântica do limite 8192

| Camada | Evidência | Valor efetivo |
|---|---|---:|
| Configuração atual | `.env:6` | `8192` |
| Leitura de configuração | `project_builder.py:3687-3696` | ambiente > `.env` > default |
| Conversão/validação | `:3707-3712` | inteiro positivo; valor inválido volta ao default |
| Default do ProjectBuilder | `:3917-3919` | `num_predict=16384`, `num_ctx=32768`, `keep_alive=15m` |
| Payload Ollama | `:4160-4172` | `options.num_ctx=8192`, `options.num_predict=16384` |
| Contexto nativo do modelo | `/api/show qwen3.5:9b` | `qwen35.context_length=262144` |

`num_ctx` é a janela total usada pelo runner para prompt e geração/KV; não é apenas o tamanho da entrada. `num_predict` é um teto de saída separado, mas a saída real fica limitada pelo espaço restante da janela. O código ainda impõe um limite defensivo de caracteres (`max_output_tokens * 12`, `:4178`) e converte `done_reason="length"` em `PLAN_OUTPUT_LIMIT_EXCEEDED` (`:4277-4285`).

O `Modelfile` retornado por `ollama show` não contém `num_ctx`; contém defaults de `temperature=1`, `top_k=20`, `top_p=0.95` e `presence_penalty=1.5`. O ProjectBuilder substitui temperature e top_p no payload.

O `/api/show` identifica `qwen3.5:9b` como família `qwen35`, 9,7B, `Q4_K_M`, com capabilities `completion`, `vision`, `tools` e `thinking`. Neste caminho só são enviados mensagens textuais; `think=false`, não há imagens e não são enviados tools.

## 4. Payloads reais

### Geração inicial

Construído em `:4158-4172` e em `_ollama_messages` (`:3847-3899`):

```json
{
  "model": "qwen3.5:9b",
  "messages": [
    {"role": "system", "content": "instruções de plano JSON"},
    {"role": "user", "content": "schema autoritativo + pedido + constraints"}
  ],
  "stream": true,
  "format": "json",
  "think": false,
  "keep_alive": "15m",
  "options": {
    "temperature": 0,
    "top_p": 0.8,
    "num_predict": 16384,
    "num_ctx": 8192
  }
}
```

### Correção focal v2

O pedido contém apenas o sistema de correção e o envelope de correção focal (erros, evidência, allowlists e conteúdos afetados quando aplicável); não é uma repetição do prompt de planeamento completo. O schema é criado em `:3815-3832` e o protocolo em `:5621-5796`:

```json
{
  "model": "qwen3.5:9b",
  "messages": [
    {"role": "system", "content": "deterministic focal project-plan corrector"},
    {"role": "user", "content": "JSON com protocol=project_builder_focal_correction_v2"}
  ],
  "stream": true,
  "format": "<objeto JSON Schema dinâmico>",
  "think": false,
  "keep_alive": "15m",
  "options": {
    "temperature": 0,
    "top_p": 0.8,
    "num_predict": 16384,
    "num_ctx": 8192
  }
}
```

Não são enviados `seed`, `top_k`, `min_p`, `repeat_penalty`, `history`, árvore do workspace ou ficheiros já materializados pelo ProjectBuilder.

## 5. Medição de três pedidos reais

Os contadores abaixo são os campos do chunk final do Ollama (`prompt_eval_count`, `eval_count`, `prompt_eval_duration`, `eval_duration`, `total_duration`, `load_duration`). `prompt_bytes` é a contagem UTF-8 feita pela aplicação; não é uma contagem de tokens.

| Caso | Tentativa | bytes de prompt | prompt tokens | output tokens | total tokens | % de 8192 | formato | duração da resposta | tok/s | done |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| pequeno | 1 inicial | 2433 | 569 | 827 | 1396 | 17,0% | JSON | 44,69 s | 25,65 | stop |
| pequeno | 2 focal | 7645 | 1592 | 281 | 1873 | 22,9% | schema | 13,94 s | 24,99 | stop |
| médio | 1 inicial | 2625 | 613 | 1701 | 2314 | 28,2% | JSON | 69,64 s | 25,15 | stop |
| médio | 2 focal | 9677 | 2091 | 1049 | 3140 | 38,3% | schema | 45,56 s | 24,71 | stop |
| SaaS inventário | 1 inicial | 3039 | 720 | 1945 | 2665 | 32,5% | JSON | 80,02 s | 24,97 | stop |
| SaaS inventário | 2 focal | 8708 | 1687 | 165 | 1852 | 22,6% | schema | 9,34 s | 24,94 | stop |

Os tempos Ollama (`total_duration`; `load_duration`; `prompt_eval_duration`; `eval_duration`) foram, em segundos: pequeno inicial `44,69; 11,69; 0,71; 32,25`, pequeno focal `13,93; 1,37; 1,25; 11,24`; médio inicial `69,64; 1,40; 0,51; 67,64`, médio focal `45,55; 1,37; 1,65; 42,44`; inventário inicial `80,01; 1,41; 0,63; 77,89`, inventário focal `9,34; 1,32; 1,32; 6,62`.

Características comuns observadas:

- HTTP 200 em todas as seis chamadas.
- `num_ctx=8192`, `num_predict=16384`, `temperature=0`, `top_p=0.8`, `think=false`, `keep_alive=15m` em todas.
- JSON inicial e JSON Schema focal foram aceites pelo Ollama.
- O schema focal dinâmico teve 599, 715 e 667 bytes nos casos pequeno, médio e inventário, respetivamente (registado pelo próprio requester); não foi substituído por JSON livre.
- As respostas foram sintaticamente JSON; a validação semântica local rejeitou os três planos mesmo depois da correção. Isto não é evidência de insuficiência de contexto.
- O runner apareceu com contexto 8192 durante a execução; após a limpeza `ollama ps` ficou vazio.

### Recursos observados

Valores máximos do sistema durante cada caso (RAM é memória usada pelo sistema, não RSS isolado do processo):

| Caso | RAM usada máx. | RAM disponível mín. | VRAM usada máx. |
|---|---:|---:|---:|
| pequeno | 11,37 GiB | 4,34 GiB | 7,19 GiB |
| médio | 11,57 GiB | 4,14 GiB | 7,20 GiB |
| SaaS inventário | 11,83 GiB | 3,87 GiB | 7,27 GiB |

## 6. Evidência de truncamento e reduções antes da chamada

Não foi encontrada evidência de truncamento nos casos medidos:

- `done_reason` foi `stop` em todas as respostas; `length` seria convertido em erro explícito pelo código.
- `prompt_eval_count + eval_count` ficou no máximo em 3140 tokens, 38,3% de 8192.
- Não houve timeout de leitura (limite de 300 s), timeout de ligação, erro HTTP ou resposta parcial.
- O erro final foi `PLAN_SEMANTIC_INVALID` e ocorreu na validação do conteúdo, depois de o modelo terminar normalmente.

Reduções/transformações verificadas:

- `_prompt_with_intent_constraints` acrescenta constraints; não reduz o pedido.
- A primeira chamada inclui o schema autoritativo completo (`:3892-3899`).
- Na segunda chamada `compact=True` encurta o texto do sistema, mas o envelope focal inclui erros, evidência, allowlists e conteúdos afetados (`:5628-5786`). É uma correção focal, não um truncamento automático.
- Não há slicing, sumarização de histórico, seleção de ficheiros, truncamento por número de tokens ou compressão de prompt no caminho de `get_valid_project_plan`.
- O `effective_prompt_length` registado pelo ProjectBuilder (`:4294-4298`) é bytes UTF-8, não tokens.
- O limite de 100 mensagens em `conversation_history` no servidor ocorre depois do resultado e não é enviado a `build_project`.

## 7. Impacto operacional

Com a configuração atual, pedidos comparáveis aos três casos têm margem ampla. A correção focal, apesar de ter mais bytes de envelope, continuou abaixo de 40% da janela medida. O risco aparece quando a combinação de schema + pedido + erros/artefactos da correção + geração se aproxima de 8192 tokens; nessa situação a saída disponível pode ser reduzida, `done_reason="length"` pode surgir e o ProjectBuilder falha explicitamente, sem terceira chamada.

O modelo anuncia 262144 tokens nativos, mas a aplicação está deliberadamente a pedir 8192. Assim, não se deve interpretar a ausência de truncamento destes testes como prova de que o ProjectBuilder usa a janela nativa completa.

## 8. Classificação final

**B — configurado em 8192, mas os prompts reais observados ficam abaixo do limite.**

Não é A porque existe um limite artificial fixo no `.env`; não é C porque não houve truncamento; não é D porque as duas chamadas do ProjectBuilder usam o mesmo `num_ctx`; e não é E porque existem seis observações reais com métricas Ollama completas.

## 9. Recomendações (não aplicadas)

1. Manter 8192 durante a revisão, pois cobre os casos observados e não houve pressão de contexto.
2. Antes de qualquer alteração, adicionar apenas uma métrica persistente/telemetria de `prompt_eval_count`, `eval_count` e margem restante por chamada; não fazer truncamento silencioso.
3. Definir um teste de regressão com correção focal grande que confirme o tratamento existente de `done_reason="length"` e a proibição da terceira chamada.
4. Se a aplicação passar a enviar histórico, ficheiros ou planos completos, reavaliar o valor de `num_ctx`; isso seria uma alteração deliberada, não parte deste diagnóstico.

Nenhuma recomendação foi aplicada nesta fase.

## 10. Ficheiros e linhas relevantes

- `.env:1,6` — modelo e limite efetivo.
- `agents/orchestrator/project_builder.py:65,67` — endpoint base e máximo de duas tentativas.
- `agents/orchestrator/project_builder.py:257-273` — timeouts HTTP.
- `agents/orchestrator/project_builder.py:3687-3721` — precedência e parsing de settings.
- `agents/orchestrator/project_builder.py:3815-3832` — JSON mode e schema focal.
- `agents/orchestrator/project_builder.py:3847-3904` — composição dos dois tipos de mensagens e medição em bytes.
- `agents/orchestrator/project_builder.py:3906-3962` — `OllamaPlanRequester`, modelo, `num_ctx`, `num_predict`, `keep_alive` e diagnósticos.
- `agents/orchestrator/project_builder.py:4050-4148` — cliente, readiness, `/api/tags` e `/api/ps`.
- `agents/orchestrator/project_builder.py:4150-4286` — payload `/api/chat`, streaming, erros HTTP e limite de output.
- `agents/orchestrator/project_builder.py:4288-4418` — tentativas, records e limite de duas chamadas.
- `agents/orchestrator/project_builder.py:4421-4445` — requester público e constraints de intenção.
- `agents/orchestrator/project_builder.py:5580-5796` — envelope da correção focal v2.
- `agents/orchestrator/project_builder.py:5837-5928` — validação, correção única e ausência de terceira chamada.
- `agents/orchestrator/project_builder.py:7040-7077` — entrada do ProjectBuilder e materialização somente após plano válido.
- `agents/orchestrator/__init__.py:1104-1141` — classificador opcional `/api/generate` fora do planeamento.
- `agents/orchestrator/__init__.py:1145-1213` — `/api/chat` genérico com ferramentas, fora do ProjectBuilder.
- `server.py:2317-2340` — chamada de `build_project` no servidor.

A captura detalhada (payloads resumidos, hashes de mensagens, contadores Ollama, exceções e amostras de recursos) está em `scratch/projectbuilder-context-diagnostic/context_diagnostic.json`; este ficheiro é evidência de diagnóstico e não altera a aplicação.
