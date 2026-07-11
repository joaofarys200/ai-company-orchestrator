import os
import json
import asyncio
import base64
import threading
import queue
import time
import numpy as np
import websockets
import sounddevice as sd
import webrtcvad
from dotenv import load_dotenv

# Load env
load_dotenv()

class GeminiLiveService:
    @staticmethod
    def _env_int(name, default, minimum=None, maximum=None):
        value = os.getenv(name)
        if value is None or value.strip() == "":
            return default
        try:
            parsed = int(value)
        except ValueError:
            return default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    @staticmethod
    def _env_float(name, default, minimum=None, maximum=None):
        value = os.getenv(name)
        if value is None or value.strip() == "":
            return default
        try:
            parsed = float(value)
        except ValueError:
            return default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    @staticmethod
    def _env_bool(name, default=False):
        value = os.getenv(name)
        if value is None or value.strip() == "":
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_csv(name):
        value = os.getenv(name, "")
        return {item.strip() for item in value.split(",") if item.strip()}

    VOICE_CONTROL_TOOLS = {
        "voice_prepare_directive",
        "voice_confirm_directive",
        "voice_cancel_directive",
    }

    def __init__(
        self,
        api_key,
        voice_name="Puck",
        on_state_change=None,
        on_message=None,
        on_voice_directive=None,
        on_voice_confirm=None,
        on_voice_cancel=None,
    ):
        self.api_key = api_key
        self.voice_name = voice_name
        self.on_state_change = on_state_change  # Callback for listening/speaking/idle state changes
        self.on_message = on_message            # Callback for text transcription responses
        self.on_voice_directive = on_voice_directive
        self.on_voice_confirm = on_voice_confirm
        self.on_voice_cancel = on_voice_cancel
        
        self.ws = None
        self.is_running = False
        self.loop = None
        
        # Audio setups
        self.input_sample_rate = 16000
        self.output_sample_rate = 24000
        self.interval_size = 30  # ms
        self.input_block_size = int(self.input_sample_rate * self.interval_size / 1000) # 480 samples
        
        # webrtcvad for local interruption detection
        self.vad_sensitivity = self._env_int("VOICE_VAD_SENSITIVITY", 2, 0, 3)
        self.vad = webrtcvad.Vad(self.vad_sensitivity)
        self.interrupt_min_speech_ms = self._env_int("VOICE_INTERRUPT_MIN_SPEECH_MS", 500, 0, 5000)
        self.interrupt_cooldown_ms = self._env_int("VOICE_INTERRUPT_COOLDOWN_MS", 1200, 0, 10000)
        self.interrupt_rms_threshold = self._env_float("VOICE_INTERRUPT_RMS_THRESHOLD", 900.0, 0.0, 32768.0)
        self.interrupt_speech_ms = 0.0
        self.interrupt_last_at = 0.0
        
        # Speaker buffers
        self.speaker_buffer = bytearray()
        self.speaker_lock = threading.Lock()
        
        self.mic_stream = None
        self.speaker_stream = None
        self.thread = None
        self.send_queue = None
        
        # State tracking for VAD interruption avoidance
        self.is_processing = False
        self.active_tasks = set()
        self.active_tool_count = 0
        self.enable_interruption = os.getenv("VOICE_INTERRUPTION", "true").lower() == "true"
        self.allow_tools = self._env_bool("VOICE_ALLOW_TOOLS", False)
        self.allowed_tools = self._env_csv("VOICE_ALLOWED_TOOLS")
        self.voice_confirmation_mode = self._env_bool("VOICE_CONFIRMATION_MODE", True)

    def play_audio_chunk(self, chunk_bytes):
        with self.speaker_lock:
            self.speaker_buffer.extend(chunk_bytes)

    def stop_speaking(self):
        with self.speaker_lock:
            self.speaker_buffer.clear()
        if self.on_state_change:
            self.on_state_change("idle")

    def speaker_callback(self, outdata, frames, time_info, status):
        # 16-bit PCM (2 bytes per sample)
        bytes_to_fill = frames * 2
        with self.speaker_lock:
            if len(self.speaker_buffer) >= bytes_to_fill:
                outdata[:] = np.frombuffer(self.speaker_buffer[:bytes_to_fill], dtype=np.int16).reshape(-1, 1)
                del self.speaker_buffer[:bytes_to_fill]
                
                # Speak state notification
                if self.on_state_change:
                    self.on_state_change("speaking")
            else:
                outdata.fill(0)
                if len(self.speaker_buffer) > 0:
                    remaining = len(self.speaker_buffer)
                    outdata_bytes = bytearray(bytes_to_fill)
                    outdata_bytes[:remaining] = self.speaker_buffer
                    outdata[:] = np.frombuffer(outdata_bytes, dtype=np.int16).reshape(-1, 1)
                    self.speaker_buffer.clear()
                
                if self.on_state_change:
                    self.on_state_change("idle")

    def mic_callback(self, indata, frames, time_info, status):
        if not self.is_running or self.ws is None:
            return
            
        gain = self._env_float("VOICE_GAIN", 1.0, 0.0, 10.0)
        if gain != 1.0:
            audio_frame = np.clip(indata.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
        else:
            audio_frame = indata
        raw_bytes = audio_frame.tobytes()
            
        try:
            rms = float(np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))) if audio_frame.size else 0.0
            is_speech = self.vad.is_speech(raw_bytes, self.input_sample_rate) and rms >= self.interrupt_rms_threshold
        except Exception:
            is_speech = False
            rms = 0.0

        frame_ms = (frames / self.input_sample_rate) * 1000 if self.input_sample_rate else self.interval_size
        if is_speech:
            self.interrupt_speech_ms += frame_ms
        else:
            self.interrupt_speech_ms = 0.0

        if is_speech:
            # Check if interruption is enabled and if we are NOT executing a task or tool
            is_processing = getattr(self, 'is_processing', False)
            active_tasks = getattr(self, 'active_tasks', set())
            active_tool_count = getattr(self, 'active_tool_count', 0)
            now = time.monotonic()
            interruption_allowed = (
                self.enable_interruption and 
                not is_processing and 
                not active_tasks and 
                active_tool_count == 0 and
                self.interrupt_speech_ms >= self.interrupt_min_speech_ms and
                ((now - self.interrupt_last_at) * 1000) >= self.interrupt_cooldown_ms
            )
            
            # User is speaking steadily: interrupt assistant playback.
            if interruption_allowed and len(self.speaker_buffer) > 0:
                print(f"GeminiLive: Interrupted assistant voice playback by speaking (VAD, rms={rms:.0f}).")
                self.interrupt_last_at = now
                self.interrupt_speech_ms = 0.0
                self.stop_speaking()
                # Send a cancel content turn to the server
                if self.loop and self.loop.is_running():
                    # Notify Gemini server of user turn interruption if supported by protocol
                    pass
            
            if self.on_state_change:
                self.on_state_change("listening")
                
        # Send raw PCM block (base64) using the new audio API format
        base64_audio = base64.b64encode(raw_bytes).decode("utf-8")
        payload = {
            "realtimeInput": {
                "audio": {
                    "mimeType": "audio/pcm;rate=16000",
                    "data": base64_audio
                }
            }
        }
        
        if self.loop and self.loop.is_running() and self.send_queue is not None:
            try:
                self.loop.call_soon_threadsafe(self.send_queue.put_nowait, json.dumps(payload))
            except RuntimeError:
                # The audio callback can race with shutdown while the loop is closing.
                pass

    async def send_ws(self, payload_str):
        if self.ws and self.ws.state == websockets.State.OPEN and self.is_running:
            try:
                await self.ws.send(payload_str)
            except Exception as e:
                print(f"GeminiLive error sending message: {e}")

    def is_voice_control_tool(self, name):
        return self.voice_confirmation_mode and name in self.VOICE_CONTROL_TOOLS

    async def execute_voice_control_tool(self, name, args):
        if name == "voice_prepare_directive":
            prompt = (args.get("prompt") or "").strip()
            if not prompt:
                return "Sem diretiva de voz para preparar."
            if self.on_voice_directive:
                self.on_voice_directive(prompt)
            return "Diretiva de voz preparada. Aguarda confirmacao explicita."

        if name == "voice_confirm_directive":
            confirmation = (args.get("confirmation") or "").strip()
            if self.on_voice_confirm:
                self.on_voice_confirm(confirmation)
            return "Confirmacao de voz recebida."

        if name == "voice_cancel_directive":
            cancel_phrase = (args.get("cancel_phrase") or "").strip()
            if self.on_voice_cancel:
                self.on_voice_cancel(cancel_phrase)
            return "Cancelamento de voz recebido."

        return f"Comando de voz interno '{name}' desconhecido."

    async def execute_tool(self, name, args, call_id):
        self.active_tool_count += 1
        try:
            print(f"GeminiLive: Executing tool '{name}' with args: {args}")
            
            result_str = ""
            try:
                if self.is_voice_control_tool(name):
                    result_str = await self.execute_voice_control_tool(name, args)
                else:
                    import agents
                    import server

                    if name == "execute_command":
                        cmd = args.get("command")
                        result_str = await agents.run_local_command(cmd)
                    elif name == "write_file":
                        fn = args.get("filename")
                        content = args.get("content")
                        result_str = await agents.run_write_file(fn, content, server.on_file_update)
                    elif name == "read_file":
                        fn = args.get("filename")
                        result_str = await agents.run_read_file(fn)
                    elif name == "list_directory":
                        dir_path = args.get("directory_path", ".")
                        result_str = await agents.run_list_directory(dir_path)
                    elif name == "obsidian_write_note":
                        fn = args.get("filename")
                        content = args.get("content")
                        result_str = await agents.run_obsidian_write_note(fn, content)
                    elif name == "obsidian_read_note":
                        fn = args.get("filename")
                        result_str = await agents.run_obsidian_read_note(fn)
                    elif name == "obsidian_list_notes":
                        result_str = await agents.run_obsidian_list_notes()
                    elif name == "obsidian_search_notes":
                        query = args.get("query")
                        result_str = await agents.run_obsidian_search_notes(query)
                    elif name == "firecrawl_scrape_url":
                        url = args.get("url")
                        result_str = await agents.run_firecrawl_scrape(url)
                    elif name == "apify_run_actor":
                        actor_id = args.get("actor_id")
                        input_data = args.get("input_data", {})
                        result_str = await agents.run_apify_actor(actor_id, input_data)
                    elif name == "browserbase_load_page":
                        url = args.get("url")
                        result_str = await agents.run_browserbase_load(url)
                    elif name == "youtube_get_transcript":
                        video_id_or_url = args.get("video_id_or_url")
                        result_str = await agents.run_youtube_transcript(video_id_or_url)
                    elif name == "composio_execute_action":
                        action_name = args.get("action_name")
                        arguments = args.get("arguments", {})
                        result_str = await agents.run_composio_action(action_name, arguments)
                    elif name == "list_active_windows":
                        result_str = agents.get_visible_windows_text()
                    elif name == "capture_screen":
                        path, b64 = await agents.run_capture_screen()
                        if path:
                            result_str = f"Captura de ecrÃƒÂ£ tirada e guardada com sucesso em '{path}'."
                        else:
                            result_str = "Erro ao tirar captura de ecrÃƒÂ£."
                    elif name == "frontend_ui_command":
                        action_name = args.get("action")
                        async def send_ui():
                            await server.broadcast({
                                "type": "ui_action",
                                "action": action_name
                            })
                        asyncio.create_task(send_ui())
                        result_str = f"Comando de UI '{action_name}' emitido para o frontend com sucesso."
                    elif name == "chamar_swarm_dominio":
                        dominio = args.get("dominio")
                        prompt_p = args.get("prompt_projeto")
                        async def run_swarm_bg():
                            current_task = asyncio.current_task()
                            self.active_tasks.add(current_task)
                            try:
                                await server.broadcast_state("processing")
                                def on_msg_dummy(sender, role, content):
                                    print(f"[Swarm {dominio} log] {sender} ({role}): {content}")
                                def on_file_dummy(name, content):
                                    pass
                                def on_kanban_dummy(card_id, status):
                                    pass
                                res = await agents.run_crew_orchestration(prompt_p, 999, on_msg_dummy, on_file_dummy, on_kanban_dummy, template_name=dominio)
                                print(f"[Swarm {dominio} completed]: {res}")
                            except Exception as e:
                                print(f"Error running Swarm {dominio}: {e}")
                            finally:
                                self.active_tasks.discard(current_task)
                                if not self.active_tasks:
                                    await server.broadcast_state("idle")
                        asyncio.create_task(run_swarm_bg())
                        result_str = f"Swarm de domÃƒÂ­nio '{dominio}' iniciado com sucesso em segundo plano com o prompt: '{prompt_p}'."
                    elif name == "criar_agente_especialista":
                        nome = args.get("nome", "Especialista")
                        especialidade = args.get("especialidade", "Especialista")
                        backstory = args.get("backstory", "")
                        tarefa = args.get("tarefa", "")
                        contexto = args.get("contexto_projeto", "")
                        async def run_specialist_bg():
                            current_task = asyncio.current_task()
                            self.active_tasks.add(current_task)
                            try:
                                await server.broadcast_state("processing")
                                def on_msg_dummy(sender, role, content):
                                    print(f"[Specialist {nome} log] {sender} ({role}): {content}")
                                res = await agents.spawn_specialist_agent(nome, especialidade, backstory, tarefa, contexto, on_msg_dummy)
                                print(f"[Specialist {nome} completed]: {res}")
                            except Exception as e:
                                print(f"Error running specialist {nome}: {e}")
                            finally:
                                self.active_tasks.discard(current_task)
                                if not self.active_tasks:
                                    await server.broadcast_state("idle")
                        asyncio.create_task(run_specialist_bg())
                        result_str = f"Agente especialista '{nome}' ({especialidade}) criado e iniciado em segundo plano para executar a tarefa."
                    elif name == "declarar_objetivo":
                        objetivo = args.get("objetivo")
                        criterios = args.get("criterios_de_sucesso", [])
                        complexidade = args.get("complexidade_estimada", "mÃƒÂ©dia")
                        crit_str = ", ".join(criterios)
                        result_str = f"Objetivo declarado: '{objetivo}' com critÃƒÂ©rios: {crit_str}. Complexidade: {complexidade}."
                    elif name == "verificar_qualidade":
                        pronto = args.get("pronto_para_entrega", False)
                        result_str = f"Qualidade verificada. Pronto para entrega: {pronto}."
                    elif name == "gravar_regra_compounding":
                        chave = args.get("chave")
                        descricao = args.get("descricao")
                        correcao = args.get("correcao")
                        import database
                        database.add_compounding_rule(chave, descricao, correcao)
                        result_str = f"Ã¢Å“â€¦ Regra de Compounding Memory '{chave}' gravada com sucesso no SQLite."
                    else:
                        result_str = f"Ferramenta {name} nÃƒÂ£o suportada ou nÃƒÂ£o implementada."
            except Exception as e:
                result_str = f"Erro ao executar a ferramenta {name}: {str(e)}"

            print(f"GeminiLive: Tool result: {result_str[:150]}...")

            # Respond back to Gemini
            response_payload = {
                "toolResponse": {
                    "functionResponses": [
                        {
                            "response": {"output": result_str},
                            "id": call_id
                        }
                    ]
                }
            }
            await self.send_ws(json.dumps(response_payload))
        finally:
            self.active_tool_count -= 1

    def is_tool_allowed(self, name):
        if self.is_voice_control_tool(name):
            return True
        if not self.allow_tools:
            return False
        if self.allowed_tools:
            return name in self.allowed_tools
        return True

    async def reject_tool_call(self, name, call_id):
        result_str = (
            f"Ferramenta '{name}' bloqueada pelo modo voz seguro. "
            "Defina VOICE_ALLOW_TOOLS=true e, opcionalmente, VOICE_ALLOWED_TOOLS para permitir ferramentas por voz."
        )
        print(f"GeminiLive: Blocked voice tool call '{name}'.")
        response_payload = {
            "toolResponse": {
                "functionResponses": [
                    {
                        "response": {"output": result_str},
                        "id": call_id
                    }
                ]
            }
        }
        await self.send_ws(json.dumps(response_payload))

    async def handle_server_message(self, msg):
        # 1. Handle server inline audio/text content
        server_content = msg.get("serverContent")
        if server_content:
            model_turn = server_content.get("modelTurn")
            if model_turn:
                parts = model_turn.get("parts", [])
                for part in parts:
                    text = part.get("text")
                    if text and self.on_message:
                        self.on_message(text)
                    
                    inline_data = part.get("inlineData")
                    if inline_data:
                        audio_b64 = inline_data.get("data")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            self.play_audio_chunk(audio_bytes)
                            
        # 2. Handle tool calls requested by Gemini
        tool_call = msg.get("toolCall")
        if tool_call:
            function_calls = tool_call.get("functionCalls", [])
            for call in function_calls:
                name = call.get("name")
                args = call.get("args", {})
                call_id = call.get("id")
                if not self.is_tool_allowed(name):
                    asyncio.create_task(self.reject_tool_call(name, call_id))
                    continue
                # Run tool execution asynchronously
                asyncio.create_task(self.execute_tool(name, args, call_id))

    def map_schema_to_gemini(self, schema):
        if not isinstance(schema, dict):
            return schema
        
        res = {}
        for k, v in schema.items():
            if k == "type" and isinstance(v, str):
                res[k] = v.upper()
            elif k == "properties" and isinstance(v, dict):
                res[k] = {pk: self.map_schema_to_gemini(pv) for pk, pv in v.items()}
            elif k == "items" and isinstance(v, dict):
                res[k] = self.map_schema_to_gemini(v)
            else:
                res[k] = v
        return res

    def get_voice_control_tool_declarations(self):
        raw_declarations = [
            {
                "name": "voice_prepare_directive",
                "description": (
                    "Prepara uma diretiva de voz para o orquestrador, sem executar. "
                    "Usa apenas quando o utilizador pedir uma tarefa concreta para construir, criar, alterar, investigar ou executar."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Texto exato da tarefa pedida pelo utilizador."
                        }
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "voice_confirm_directive",
                "description": (
                    "Confirma a diretiva de voz pendente. Usa apenas quando o utilizador disser claramente "
                    "'confirma', 'executa', 'avanca' ou equivalente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "confirmation": {
                            "type": "string",
                            "description": "Frase de confirmacao dita pelo utilizador."
                        }
                    },
                    "required": ["confirmation"]
                }
            },
            {
                "name": "voice_cancel_directive",
                "description": (
                    "Cancela a diretiva de voz pendente. Usa apenas quando o utilizador disser claramente "
                    "'cancela', 'anula', 'esquece' ou equivalente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cancel_phrase": {
                            "type": "string",
                            "description": "Frase de cancelamento dita pelo utilizador."
                        }
                    },
                    "required": ["cancel_phrase"]
                }
            }
        ]
        return [
            {
                **declaration,
                "parameters": self.map_schema_to_gemini(declaration["parameters"])
            }
            for declaration in raw_declarations
        ]

    def get_gemini_tools(self):
        declarations = []

        if self.voice_confirmation_mode:
            declarations.extend(self.get_voice_control_tool_declarations())

        if not self.allow_tools:
            if declarations:
                print("GeminiLive: Voice confirmation tools enabled; computer tools disabled.")
                return [{"functionDeclarations": declarations}]
            print("GeminiLive: Voice tools disabled by VOICE_ALLOW_TOOLS=false.")
            return []

        from agents import JARVIS_TOOLS
        for tool in JARVIS_TOOLS:
            name = tool["name"]
            if self.allowed_tools and name not in self.allowed_tools:
                continue
            description = tool["description"]
            input_schema = tool["input_schema"]
            
            # Map input_schema type and properties recursively to uppercase for Gemini
            params = self.map_schema_to_gemini(input_schema)
                    
            declarations.append({
                "name": name,
                "description": description,
                "parameters": params
            })
        return [{"functionDeclarations": declarations}]

    async def _runner(self):
        self.send_queue = asyncio.Queue()
        device_index_env = os.getenv("VOICE_DEVICE_INDEX")
        device_index = int(device_index_env) if (device_index_env and device_index_env.strip() != "") else None
        
        # Start sounddevice output and input once (keep active across reconnects)
        self.speaker_stream = sd.OutputStream(
            samplerate=self.output_sample_rate,
            channels=1,
            dtype='int16',
            blocksize=0, # Use default system blocksize for scheduling stability under CPU load
            callback=self.speaker_callback
        )
        
        try:
            self.mic_stream = sd.InputStream(
                device=device_index,
                samplerate=self.input_sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.input_block_size,
                callback=self.mic_callback
            )
        except Exception as mic_err:
            print(f"GeminiLive: Failed to query/open configured device {device_index}: {mic_err}. Falling back to default system microphone.")
            self.mic_stream = sd.InputStream(
                device=None,
                samplerate=self.input_sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.input_block_size,
                callback=self.mic_callback
            )
        
        self.speaker_stream.start()
        self.mic_stream.start()
        print("GeminiLive: Audio recording and playback streams are active.")
        
        url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={self.api_key}"
        
        reconnect_delay = 1.0
        while self.is_running:
            print("GeminiLive: Connecting to Google Live endpoint...")
            if self.on_state_change:
                self.on_state_change("connecting")
                
            try:
                async with websockets.connect(url) as websocket:
                    self.ws = websocket
                    reconnect_delay = 1.0  # Reset backoff on successful connection
                    if self.on_state_change:
                        self.on_state_change("idle")
                    
                    # --- Project Intelligence & Runtime Awareness ---
                    project_intelligence = ""
                    try:
                        if os.path.exists("symbols_index.json"):
                            with open("symbols_index.json", "r", encoding="utf-8") as f:
                                idx_data = f.read()
                                if len(idx_data) > 6000:
                                    idx_data = idx_data[:6000] + "\n... [TRUNCADO PARA POUPAR TOKENS] ..."
                                project_intelligence = f"\n\n## Project Intelligence (AST & Symbol Graph)\nO mapa estrutural da aplicaÃ§Ã£o:\n```json\n{idx_data}\n```"
                    except Exception:
                        pass
                        
                    runtime_awareness = ""
                    try:
                        from intelligence.runtime_observer import RuntimeObserver
                        observer = RuntimeObserver()
                        rt_state = observer.compile_runtime_state(websocket_connected=True, active_agents=0, frontend_connected=True)
                        runtime_awareness = f"\n\n## Runtime Awareness (System Health)\nEstado da mÃ¡quina e base de dados em tempo real:\n```json\n{json.dumps(rt_state, indent=2)}\n```"
                    except Exception:
                        pass
                        
                    # â”€â”€ IDENTITY PROVIDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    identity_prompt = """
## IDENTIDADE

Ã‰s o OpenClaw.

Ã‰s o sistema operativo inteligente do JARVIS OS.

O utilizador Ã© o CEO.

A tua funÃ§Ã£o nÃ£o Ã© responder a perguntas.

A tua funÃ§Ã£o Ã© transformar objetivos em resultados.

Ã‰s simultaneamente:

â€¢ COO
â€¢ Orquestrador
â€¢ Arquiteto TÃ©cnico
â€¢ Gestor de Agentes
â€¢ Supervisor de ExecuÃ§Ã£o

Coordenas pessoas artificiais, ferramentas, memÃ³ria e conhecimento.

Pensas sempre antes de agir.
Planeias antes de executar.
Observas antes de decidir.
Executas apenas quando tens confianÃ§a suficiente.

Nunca ages por impulso.
Nunca assumes informaÃ§Ã£o que nÃ£o possuis.

## EQUIPA

Tens acesso aos seguintes especialistas que sÃ³ ativas quando acrescentam valor real:

â€¢ Alex â€” Produto
â€¢ Clara â€” Design
â€¢ Devon â€” Engenharia
â€¢ Quinn â€” QA

Os swarms sÃ£o assÃ­ncronos. Depois de iniciares um swarm informa o CEO e aguarda os resultados.
Caso contrÃ¡rio resolve diretamente sem delegar.
"""

                    # â”€â”€ COMMUNICATION PROVIDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    communication_prompt = """
## COMUNICAÃ‡ÃƒO

Responde sempre em portuguÃªs de Portugal.

SÃª natural, profissional, direto e objetivo.

Normalmente responde em poucas frases, aumentando o detalhe apenas quando necessÃ¡rio.

Podes tratar o utilizador ocasionalmente por "CEO" ou "Sir", sem exagero.
"""

                    # â”€â”€ EXECUTION PROVIDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    execution_prompt = """
## EXECUÃ‡ÃƒO

Ferramentas existem para executar trabalho. NÃ£o existem para produzir texto.

Quando uma ferramenta consegue executar uma tarefa de forma segura e fiÃ¡vel, utiliza-a imediatamente.

Evita responder com instruÃ§Ãµes quando podes produzir um resultado real.
Nunca cries trabalho manual para o utilizador quando o podes automatizar.

Depois de executar:
- confirma o resultado;
- resume o que foi feito;
- apresenta apenas os prÃ³ximos passos relevantes.

Se uma ferramenta falhar:
- tenta apenas uma abordagem alternativa;
- se voltar a falhar, explica o motivo e aguarda novas instruÃ§Ãµes.

## PLANEAMENTO

Antes de executar tarefas complexas:

1. Compreende o objetivo.
2. Divide-o em subtarefas.
3. Avalia dependÃªncias.
4. Escolhe os agentes necessÃ¡rios.
5. Executa.
6. Valida.
7. Reporta.
"""

                    # â”€â”€ ENGINEERING PROVIDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    engineering_prompt = """
## ENGENHARIA DE SOFTWARE

Quando trabalhas sobre software:

Nunca edites cÃ³digo sem compreender primeiro a arquitetura.
Nunca assumes que um ficheiro representa todo o sistema.

Sempre que possÃ­vel:
- identifica dependÃªncias;
- identifica impacto;
- identifica riscos;
- define um plano;
- executa alteraÃ§Ãµes;
- valida resultados;
- aprende com o resultado.

Privilegia sempre alteraÃ§Ãµes pequenas, seguras e reversÃ­veis.

Pensa sempre em sistemas completos e nÃ£o em ficheiros isolados.

## PRIORIDADES

1. Integridade do sistema.
2. CorreÃ§Ã£o tÃ©cnica.
3. ConclusÃ£o da tarefa.
4. EficiÃªncia.
5. ElegÃ¢ncia.
"""

                    # â”€â”€ SYSTEM AWARENESS PROVIDER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    system_awareness_prompt = """
## CONSCIÃŠNCIA DO SISTEMA

Antes de responder ou executar uma tarefa consulta mentalmente:

â€¢ Runtime Observer
â€¢ Project Intelligence Engine
â€¢ Architecture Memory
â€¢ Decision Memory

Estes componentes representam a tua memÃ³ria operacional e devem prevalecer sobre suposiÃ§Ãµes.

Baseia o teu raciocÃ­nio nesses dados antes de responder ou agir.

## OBJETIVO PERMANENTE

O teu objetivo permanente Ã© aumentar continuamente as capacidades do JARVIS OS.

Sempre que possÃ­vel deves:
- melhorar a arquitetura;
- reduzir complexidade;
- aumentar automaÃ§Ã£o;
- preservar estabilidade;
- acumular conhecimento;
- evitar regressÃµes.

Cada tarefa deve deixar o sistema melhor do que estava anteriormente.
"""

                    if not self.allow_tools and self.voice_confirmation_mode:
                        execution_prompt = """
## EXECUCAO

Modo voz seguro ativo.

Nao abras paineis, nao captures o ecra, nao controles apps externas e nao executes comandos no computador.

Quando o utilizador pedir uma tarefa concreta para construir, criar, alterar, investigar
ou executar, chama voice_prepare_directive com o texto exato da tarefa. Isto apenas
prepara a diretiva; nao executa.

Depois de preparar uma diretiva, aguarda confirmacao. Se o utilizador disser claramente
'confirma', 'executa' ou 'avanca', chama voice_confirm_directive. Se disser 'cancela',
'anula' ou 'esquece', chama voice_cancel_directive.

Para perguntas normais ou conversa, responde normalmente sem preparar diretivas.
"""
                    elif not self.allow_tools:
                        execution_prompt = """
## EXECUCAO

Modo voz seguro ativo.

Responde apenas por voz e texto. Nao chames ferramentas, nao abras paineis,
nao captures o ecra, nao controles apps externas e nao executes comandos no computador.
"""

                    final_instruction = "\n\n".join([
                        identity_prompt,
                        communication_prompt,
                        execution_prompt,
                        engineering_prompt,
                        system_awareness_prompt,
                        project_intelligence,
                        runtime_awareness,
                    ])
                    gemini_tools = self.get_gemini_tools()

                    # Send Setup
                    setup_msg = {
                        "setup": {
                            "model": "models/gemini-3.1-flash-live-preview",
                            "generationConfig": {
                                "responseModalities": ["AUDIO"],
                                "speechConfig": {
                                    "voiceConfig": {
                                        "prebuiltVoiceConfig": {
                                            "voiceName": self.voice_name
                                        }
                                    }
                                }
                            },
                            "systemInstruction": {
                                "parts": [
                                    {
                                        "text": final_instruction
                                    }
                                ]
                            }
                        }
                    }
                    if gemini_tools:
                        setup_msg["setup"]["tools"] = gemini_tools
                    await websocket.send(json.dumps(setup_msg))
                    print("GeminiLive: Handshake setup sent successfully.")
                    
                    # Drain any stale messages from queue before starting
                    while not self.send_queue.empty():
                        try:
                            self.send_queue.get_nowait()
                            self.send_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                    
                    # Tasks for reading and writing WebSocket messages concurrently
                    async def read_loop():
                        try:
                            async for message_str in websocket:
                                if not self.is_running:
                                    break
                                try:
                                    msg = json.loads(message_str)
                                    await self.handle_server_message(msg)
                                except Exception as e:
                                    print(f"GeminiLive Read Error: {e}")
                        except websockets.exceptions.ConnectionClosed as ce:
                            print(f"GeminiLive WebSocket connection closed in read_loop: {ce}")
                        except asyncio.CancelledError:
                            raise
                                
                    async def write_loop():
                        try:
                            while self.is_running:
                                payload_str = await self.send_queue.get()
                                try:
                                    if payload_str is None:
                                        break
                                    if self.ws and self.ws.state == websockets.State.OPEN:
                                        await websocket.send(payload_str)
                                finally:
                                    self.send_queue.task_done()
                        except websockets.exceptions.ConnectionClosed as ce:
                            print(f"GeminiLive WebSocket connection closed in write_loop: {ce}")
                        except asyncio.CancelledError:
                            raise
                            
                    read_task = asyncio.create_task(read_loop(), name="GeminiLive.read_loop")
                    write_task = asyncio.create_task(write_loop(), name="GeminiLive.write_loop")
                    done, pending = await asyncio.wait(
                        {read_task, write_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    await asyncio.gather(*done, return_exceptions=True)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.is_running:
                    print(f"GeminiLive loop exception: {e}")
                
            self.ws = None
            if self.is_running:
                print(f"GeminiLive: Disconnected. Reconnecting in {reconnect_delay} seconds...")
                if self.on_state_change:
                    self.on_state_change("connecting")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60.0)  # Exponential backoff up to 60s
                
        self.cleanup()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.speaker_buffer.clear()
        
        # Start async runner in background thread
        def start_loop():
            loop = asyncio.new_event_loop()
            self.loop = loop
            asyncio.set_event_loop(loop)
            try:
                try:
                    loop.run_until_complete(self._runner())
                except Exception as exc:
                    print(f"GeminiLive runner failed: {exc}")
                    self.cleanup()
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                if self.loop is loop:
                    self.loop = None
                loop.close()
            
        self.thread = threading.Thread(target=start_loop, daemon=True)
        self.thread.start()
        print("GeminiLive: Background thread started successfully.")

    def stop(self):
        self.is_running = False
        loop = self.loop
        if loop and loop.is_running():
            def request_shutdown():
                if self.send_queue is not None:
                    try:
                        self.send_queue.put_nowait(None)
                    except Exception:
                        pass
                if self.ws is not None:
                    try:
                        asyncio.create_task(self.ws.close(code=1000, reason="voice service stopping"))
                    except Exception:
                        pass

            try:
                loop.call_soon_threadsafe(request_shutdown)
            except RuntimeError:
                pass

        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=3.0)

        if not self.thread or not self.thread.is_alive():
            self.cleanup()
            print("GeminiLive: Voice service stopped.")
        else:
            print("GeminiLive: Stop requested; background thread is still closing.")

    def cleanup(self):
        self.stop_speaking()
        self.send_queue = None
        if self.mic_stream:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception:
                pass
            self.mic_stream = None
            
        if self.speaker_stream:
            try:
                self.speaker_stream.stop()
                self.speaker_stream.close()
            except Exception:
                pass
            self.speaker_stream = None
            
        self.ws = None
        self.loop = None
        if self.on_state_change:
            self.on_state_change("offline")

