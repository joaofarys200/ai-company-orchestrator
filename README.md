# AI Company Orchestrator

Aplicacao local de orquestracao de agentes com backend Python, frontend React/Vite e shell Electron. O backend coordena agentes, WebSocket local, memoria SQLite, ferramentas desktop, scraping, Obsidian e preview sandbox. O frontend consome eventos em tempo real e apresenta chat, estado de agentes, ficheiros gerados e paineis de trabalho.

## Requisitos

- Windows 10/11 recomendado para o modo desktop local.
- Python 3.11+.
- Node.js 20+ e npm.
- Docker Desktop opcional, usado pelo preview sandbox quando disponivel.
- Ollama opcional para modo local com modelos como `qwen2.5:14b`.

No Windows, use sempre o Python do virtualenv do projeto:

```powershell
.\venv\Scripts\python.exe
```

## Instalacao Backend

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

Edite `.env` apenas com chaves locais suas. Nunca coloque chaves reais no `.env.example`.

## Instalacao Frontend e Electron

```powershell
npm install
npm install --prefix frontend
```

Para desenvolvimento com Vite e Electron:

```powershell
npm run dev
```

Para compilar o frontend:

```powershell
npm run build --prefix frontend
```

## Variaveis de Ambiente

As variaveis documentadas em `.env.example` cobrem o runtime principal:

- `ORCHESTRATOR_MODE`: `local`, `ollama`, `gemini`, `claude` ou `anthropic`.
- `JARVIS_WS_TOKEN`: token local simples exigido pelo WebSocket.
- `VITE_JARVIS_WS_TOKEN`: token equivalente para o frontend se o fallback `local-dev-token` for alterado.
- `OLLAMA_MODEL` e `OLLAMA_BASE_URL`: configuracao de modelo local.
- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`: chaves cloud opcionais.
- `ORCHESTRATOR_MAX_STEPS`, `ORCHESTRATOR_SPECIALIST_MAX_STEPS`, `ORCHESTRATOR_IDLE_RETRIES`: limites para evitar loops longos.
- `ORCHESTRATOR_SWARM_ENABLED`: quando `false`, o orquestrador evita swarms e trabalha diretamente com ferramentas.
- `ORCHESTRATOR_VERBOSE_PROGRESS`: quando `false`, reduz mensagens de progresso repetidas no chat.
- `ORCHESTRATOR_AUTO_LEARN`: quando `false`, evita a chamada extra de auto-aprendizagem por prompt.
- `ORCHESTRATOR_COMPLEXITY_MODEL_ENABLED`: quando `false`, usa heuristica rapida para simples/complexo em vez de chamar modelo.
- `VOICE_MODE`: use `none` para desativar voz numa instalacao limpa.
- `VOICE_GAIN`: ganho do microfone antes de enviar audio; valores abaixo de `1.0` reduzem sensibilidade.
- `VOICE_VAD_SENSITIVITY`: sensibilidade WebRTC VAD de `0` a `3`; valores mais baixos sao menos agressivos.
- `VOICE_RMS_THRESHOLD` e `VOICE_MIN_SPEECH_MS`: filtram ruido curto no modo local.
- `VOICE_INTERRUPTION`, `VOICE_INTERRUPT_MIN_SPEECH_MS`, `VOICE_INTERRUPT_COOLDOWN_MS`, `VOICE_INTERRUPT_RMS_THRESHOLD`: controlam quando a voz do Gemini Live pode ser interrompida pelo microfone.
- `VOICE_CONFIRMATION_MODE`: quando `true`, comandos por voz com efeitos laterais ficam pendentes ate dizeres `confirma`, `executa` ou `avanca`; consultas read-only podem avancar diretamente.
- `VOICE_CONFIRMATION_TTL_SECONDS`: tempo maximo para confirmar uma diretiva de voz pendente.
- `VOICE_ALLOW_TOOLS`: permite ou bloqueia ferramentas no Gemini Live por voz; por seguranca deve ficar `false` ate quereres comandos de computador por voz.
- `VOICE_ALLOW_READONLY_TOOLS`: permite observacao do ambiente, leitura de ficheiros e pesquisa sem alterar o computador; ativo por omissao.
- `VOICE_AUTO_READONLY`: inicia diretamente pedidos de pesquisa e observacao read-only, sem confirmacao.
- `VOICE_ALLOWED_TOOLS`: lista opcional separada por virgulas para limitar as ferramentas permitidas quando `VOICE_ALLOW_TOOLS=true`.
- `FIRECRAWL_API_KEY`, `APIFY_API_TOKEN`, `BROWSERBASE_API_KEY`, `COMPOSIO_API_KEY`: ferramentas externas opcionais.
- `OBSIDIAN_VAULT_PATH`: caminho opcional para um cofre Obsidian local.
- `DOCKER_PORT`: porta do preview sandbox, por omissao `8080`.

Se alterar `JARVIS_WS_TOKEN`, mantenha o mesmo valor em `VITE_JARVIS_WS_TOKEN` no ambiente do frontend. Em modo build, o frontend tambem tem fallback local `local-dev-token`.

## Comandos de Arranque

Backend apenas:

```powershell
.\venv\Scripts\python.exe server.py
```

Electron em modo producao local:

```powershell
npm start
```

Frontend Vite + Electron em modo desenvolvimento:

```powershell
npm run dev
```

## Portas Usadas

- `8000`: servidor HTTP local para o frontend compilado.
- `8001`: WebSocket local, ligado apenas a `127.0.0.1` e protegido por token.
- `8080`: preview sandbox, configuravel por `DOCKER_PORT`.
- `5173`: Vite dev server quando usado `npm run dev`.
- `11434`: Ollama local, se usado.

## Validacoes Minimas

```powershell
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -c "import server; print('IMPORT_SERVER_OK')"
node --check main.js
npm run build --prefix frontend
npm run lint --prefix frontend
```

Estado conhecido: o build do frontend deve passar. O lint pode falhar enquanto existirem avisos/erros antigos de tipagem e regras React ainda nao tratados.
