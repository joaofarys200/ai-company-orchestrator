import os
import re
import asyncio
import json
import subprocess
import httpx
import base64
import io
import yaml
import datetime
from pathlib import Path
from PIL import ImageGrab
from sandbox import SANDBOX_DIR

try:
    from crewai import Agent, Task, Crew, LLM
    from crewai.tools import tool
except ImportError:
    Agent = Task = Crew = LLM = None
    def tool(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda f: f

import agents.globals as glb
import agents.utils as utils
import agents.memory as memory
import agents.tools as ag_tools
import agents.obsidian_tools as obs_tools
import agents.swarm as swarm
import server
from workspace_policy import (
    BASE_DIR,
    COMMAND_BLOCKLIST,
    WORKSPACE_ROOT,
    resolve_workspace_path,
    validate_local_command,
)

# --- run_local_command ---
async def run_local_command(command: str) -> str:
    """Executa um comando no terminal do sistema (PowerShell)."""
    allowed, reason = validate_local_command(command)
    if not allowed:
        return f"Erro de seguranca: {reason}"

    loop = asyncio.get_running_loop()
    def run_cmd():
        try:
            run_kwargs = {
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "capture_output": True,
                "timeout": 60,
                "cwd": BASE_DIR,
            }
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            process = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                **run_kwargs,
            )
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            status = f"Comando terminado com código {process.returncode}."
            return f"{status}\n\n[STDOUT]\n{stdout}\n\n[STDERR]\n{stderr}"
        except subprocess.TimeoutExpired:
            return "Erro: O comando excedeu o tempo limite de 60 segundos."
        except Exception as e:
            return f"Erro ao executar o comando: {str(e)}"
            
    return await loop.run_in_executor(None, run_cmd)


# --- run_write_file ---
def write_file_sync(filename: str, content: str, file_callback=None) -> str:
    """Implementacao sincronizada partilhada pela tool write_file."""
    try:
        if not filename:
            return "Erro ao escrever no ficheiro: O nome do ficheiro esta em falta ou e None."
        abs_path = resolve_workspace_path(filename)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        if file_callback:
            rel_path = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
            tab_name = rel_path.replace("sandbox_dir/", "") if rel_path.startswith("sandbox_dir/") else rel_path
            file_callback(tab_name, content)
        return f"Ficheiro '{filename}' guardado com sucesso ({len(content)} bytes)."
    except Exception as e:
        return f"Erro ao escrever no ficheiro: {str(e)}"


async def run_write_file(filename: str, content: str, file_callback=None) -> str:
    """Escreve conteudo num ficheiro local."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: write_file_sync(filename, content, file_callback))


# --- run_read_file ---
async def run_read_file(filename: str) -> str:
    """Lê o conteúdo de um ficheiro local."""
    loop = asyncio.get_running_loop()
    def read_f():
        try:
            if not filename:
                return "Erro ao ler o ficheiro: O nome do ficheiro (filename) está em falta ou é None."
            abs_path = resolve_workspace_path(filename)
                
            if not os.path.exists(abs_path):
                return f"Erro: O ficheiro '{filename}' não existe."
                
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Erro ao ler o ficheiro: {str(e)}"
            
    return await loop.run_in_executor(None, read_f)


# --- run_list_directory ---
async def run_list_directory(path: str) -> str:
    """Lista o conteúdo de um diretório local."""
    loop = asyncio.get_running_loop()
    def list_dir_func():
        try:
            target_path = path if (path and isinstance(path, str)) else "."
            abs_path = resolve_workspace_path(target_path)
                
            if not os.path.exists(abs_path):
                return f"Erro: O diretório '{target_path}' não existe."
                
            items = os.listdir(abs_path)
            result = []
            for item in items:
                item_path = os.path.join(abs_path, item)
                is_dir = os.path.isdir(item_path)
                prefix = "[DIR]" if is_dir else "[FILE]"
                result.append(f"{prefix} {item}")
            return "\n".join(result) if result else "(Diretório vazio)"
        except Exception as e:
            return f"Erro ao listar o diretório: {str(e)}"
            
    return await loop.run_in_executor(None, list_dir_func)


# --- get_visible_windows_text ---
def get_visible_windows_text() -> str:
    try:
        import ctypes
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        GetWindowTextW = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
        
        titles = []
        
        def foreach_window(hwnd, lParam):
            if IsWindowVisible(hwnd):
                length = GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    GetWindowTextW(hwnd, buff, length + 1)
                    titles.append(buff.value)
            return True
            
        EnumWindows(EnumWindowsProc(foreach_window), 0)
        unique_titles = sorted(list(set(titles)))
        lines = [f"- {t}" for t in unique_titles if t.strip()]
        return "\n".join(lines) if lines else "(Nenhuma janela visível)"
    except Exception as e:
        return f"Erro ao listar janelas: {str(e)}"


# --- run_capture_screen ---
async def run_capture_screen() -> tuple[str, str]:
    """Tira uma captura de ecrã do monitor principal e devolve (caminho, base64)."""
    loop = asyncio.get_running_loop()
    def grab_screen():
        try:
            img = ImageGrab.grab()
            path = os.path.join(BASE_DIR, "sandbox_dir", "screenshot.png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.save(path, "PNG")
            
            buf = io.BytesIO()
            img.thumbnail((1200, 900))
            img.save(buf, format="PNG")
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            
            return path, b64_str
        except Exception as e:
            print(f"Erro ao capturar ecrã: {e}")
            return "", ""
    return await loop.run_in_executor(None, grab_screen)


# --- run_local_scrape ---
async def run_local_scrape(url: str) -> str:
    """Core local scraper selector. First tries Playwright, then falls back to HTTPX."""
    print(f"[Scraper Local] A tentar obter {url}...")
    try:
        content = await run_playwright_scrape_impl(url)
        if content and not content.startswith("Erro:"):
            return content
        print(f"[Scraper Local] Playwright falhou ou não está configurado: {content[:150]}. A tentar fallback com HTTPX...")
    except Exception as e:
        print(f"[Scraper Local] Erro ao inicializar Playwright: {e}. A tentar fallback com HTTPX...")
    return await run_httpx_scrape_impl(url)


# --- run_playwright_scrape_impl ---
async def run_playwright_scrape_impl(url: str) -> str:
    """Loads URL via headless Playwright, extracts title and converts body to markdown."""
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup
    from markdownify import markdownify
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            await page.goto(url, wait_until="load", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            html = await page.content()
            title = await page.title()
            
            soup = BeautifulSoup(html, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "form", "iframe", "header"]):
                element.decompose()
            body_html = str(soup.body) if soup.body else str(soup)
            
            md = markdownify(body_html, heading_style="ATX", strip=["a", "img"])
            md_clean = "\n".join([line.strip() for line in md.split("\n") if line.strip()])
            return f"# {title}\n\n{md_clean}"
        finally:
            await browser.close()


# --- run_httpx_scrape_impl ---
async def run_httpx_scrape_impl(url: str) -> str:
    """Basic fallback using HTTPX and BeautifulSoup/markdownify."""
    import httpx
    from bs4 import BeautifulSoup
    from markdownify import markdownify
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
        if response.status_code != 200:
            return f"Erro ao aceder ao website localmente: Código HTTP {response.status_code}"
        
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if (soup.title and soup.title.string) else "Página Web"
        for element in soup(["script", "style", "nav", "footer", "form", "iframe", "header"]):
            element.decompose()
        body_html = str(soup.body) if soup.body else str(soup)
        
        md = markdownify(body_html, heading_style="ATX", strip=["a", "img"])
        md_clean = "\n".join([line.strip() for line in md.split("\n") if line.strip()])
        return f"# {title} (HTTPX Fallback)\n\n{md_clean}"
    except Exception as e:
        return f"Erro em todos os métodos de scraping local para '{url}': {str(e)}"


# --- run_firecrawl_scrape ---
async def run_firecrawl_scrape(url: str) -> str:
    """Scrapes content from a webpage using the official Firecrawl SDK with local fallbacks."""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("[Scraper] FIRECRAWL_API_KEY não configurada. A usar o Scraper Local...")
        return await run_local_scrape(url)
    
    loop = asyncio.get_running_loop()
    def execute():
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=api_key)
            result = app.scrape_url(url, params={"formats": ["markdown"]})
            if isinstance(result, dict) and "markdown" in result:
                return result["markdown"]
            elif hasattr(result, "get"):
                return result.get("markdown") or str(result)
            elif hasattr(result, "markdown"):
                return result.markdown
            return str(result)
        except Exception as e:
            print(f"[Scraper] Erro no Firecrawl: {e}. A tentar Scraper Local...")
            return None
            
    res = await loop.run_in_executor(None, execute)
    if res is not None:
        return res
    return await run_local_scrape(url)


# --- read_pdf ---
async def read_pdf(file_path: str, max_pages: int = 20) -> str:
    """Extracts text content from a local PDF file using pdfplumber.
    Returns the extracted text page by page up to max_pages."""
    try:
        import pdfplumber
        from pathlib import Path as _Path

        p = _Path(file_path)
        if not p.is_absolute():
            p = _Path(SANDBOX_DIR) / file_path
        if not p.exists():
            return f"Erro: O ficheiro PDF '{file_path}' nao foi encontrado."

        loop = asyncio.get_running_loop()
        def extract():
            pages_text = []
            with pdfplumber.open(str(p)) as pdf:
                total = len(pdf.pages)
                for i, page in enumerate(pdf.pages[:max_pages]):
                    text = page.extract_text() or ""
                    pages_text.append(f"--- Pagina {i+1}/{total} ---\n{text}")
            return "\n\n".join(pages_text)

        text = await loop.run_in_executor(None, extract)
        return text or "O PDF nao continha texto extraivel."
    except ImportError:
        return "Erro: pdfplumber nao esta instalado."
    except Exception as e:
        return f"Erro ao ler o PDF '{file_path}': {str(e)}"


# --- search_arxiv ---
async def search_arxiv(query: str, max_results: int = 5) -> str:
    """Searches arXiv.org for academic papers matching a query.
    Returns title, authors, abstract and PDF link for each result."""
    try:
        encoded = query.replace(" ", "+")
        url = (
            f"https://export.arxiv.org/api/query"
            f"?search_query=all:{encoded}&start=0&max_results={max_results}"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text

        import xml.etree.ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(content)
        entries = root.findall("atom:entry", ns)
        if not entries:
            return f"Nenhum resultado encontrado no arXiv para: '{query}'"

        results = []
        for entry in entries:
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", "", ns) or "").strip()[:400]
            authors = ", ".join(
                (a.findtext("atom:name", "", ns) or "").strip()
                for a in entry.findall("atom:author", ns)
            )
            pdf_link = next(
                (lnk.get("href", "") for lnk in entry.findall("atom:link", ns)
                 if lnk.get("type") == "application/pdf"),
                ""
            )
            results.append(
                f"**{title}**\nAutores: {authors}\nResumo: {summary}...\nPDF: {pdf_link}"
            )
        return "\n\n".join(results)
    except Exception as e:
        return f"Erro ao pesquisar no arXiv: {str(e)}"


# --- run_apify_actor ---
async def run_apify_actor(actor_id: str, input_data: dict) -> str:
    """Runs a specific Apify Actor and returns the dataset output."""
    loop = asyncio.get_running_loop()
    def execute():
        token = os.getenv("APIFY_API_TOKEN")
        if not token:
            return "Erro: O token API 'APIFY_API_TOKEN' não está configurado no .env. Configure-o para utilizar o Apify."
        try:
            from apify_client import ApifyClient
            client = ApifyClient(token=token)
            run = client.actor(actor_id).call(run_input=input_data)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            return json.dumps(dataset_items, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Erro ao executar actor {actor_id} no Apify: {str(e)}"
    return await loop.run_in_executor(None, execute)


# --- run_browserbase_load ---
async def run_browserbase_load(url: str) -> str:
    """Loads a webpage content securely using the official Browserbase Fetch API."""
    loop = asyncio.get_running_loop()
    def execute():
        api_key = os.getenv("BROWSERBASE_API_KEY")
        if not api_key:
            return "Erro: A chave API 'BROWSERBASE_API_KEY' não está configurada no .env. Configure-a para utilizar o Browserbase."
        try:
            from browserbase import Browserbase
            client = Browserbase(api_key=api_key)
            response = client.fetch_api.create(url=url)
            if hasattr(response, "content"):
                return response.content
            return str(response)
        except Exception as e:
            return f"Erro ao carregar página no Browserbase: {str(e)}"
    return await loop.run_in_executor(None, execute)


# --- run_youtube_transcript ---
async def run_youtube_transcript(video_id_or_url: str) -> str:
    """Retrieves the full text transcript of a YouTube video using the youtube-transcript-api."""
    loop = asyncio.get_running_loop()
    def execute():
        import re
        video_id = video_id_or_url
        if "youtube.com" in video_id_or_url or "youtu.be" in video_id_or_url:
            match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", video_id_or_url)
            if match:
                video_id = match.group(1)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            transcript_list = api.fetch(video_id, languages=['pt', 'en', 'es'])
            text = " ".join([t.text for t in transcript_list])
            return text
        except Exception as e:
            return f"Erro ao obter legenda do YouTube para o vídeo {video_id}: {str(e)}"
    return await loop.run_in_executor(None, execute)


# --- run_composio_action ---
async def run_composio_action(action_name: str, arguments: dict) -> str:
    """Executes a dynamic action on external applications (e.g. GMAIL_SEND_EMAIL) using the official Composio SDK."""
    loop = asyncio.get_running_loop()
    def execute():
        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            return "Erro: A chave API 'COMPOSIO_API_KEY' não está configurada no .env. Configure-a para utilizar as ferramentas do Composio."
        try:
            from composio import Composio
            client = Composio(api_key=api_key)
            result = client.tools.execute(action_name, arguments, user_id="default_user")
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Erro ao executar ação {action_name} no Composio: {str(e)}"
    return await loop.run_in_executor(None, execute)


# --- JARVIS_TOOLS ---
JARVIS_TOOLS = [
    {
        "name": "refactor_move_symbol",
        "description": "Move uma classe ou função inteira de um ficheiro para o outro de forma limpa usando a AST.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_file": {"type": "string"},
                "target_file": {"type": "string"},
                "symbol_name": {"type": "string"}
            },
            "required": ["source_file", "target_file", "symbol_name"]
        }
    },
    {
        "name": "refactor_rename_symbol",
        "description": "Altera o nome a uma função ou classe num ficheiro, restruturando a sua assinatura.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "old_name": {"type": "string"},
                "new_name": {"type": "string"}
            },
            "required": ["filepath", "old_name", "new_name"]
        }
    },
    {
        "name": "start_autonomous_plan",
        "description": "Usa isto para pedidos complexos ou ambíguos. O sistema vai criar um plano passo-a-passo num ficheiro persistente (.jarvis_plan.json) e executá-lo à vez através de um agente especializado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "O objetivo geral detalhado do utilizador."
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "apply_code_patch",
        "description": "Edita cirurgicamente uma função ou classe num ficheiro baseado em AST, sem o reescrever todo. Protege o código de corrupções, ideal para edições multi-file seguras.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Caminho relativo do ficheiro a editar."
                },
                "symbol_name": {
                    "type": "string",
                    "description": "O nome da função ou classe exata que se pretende editar."
                },
                "new_code": {
                    "type": "string",
                    "description": "O bloco novo de código completo (função/classe inteira) que substituirá a antiga."
                }
            },
            "required": ["file_path", "symbol_name", "new_code"]
        }
    },
    {
        "name": "semantic_code_search",
        "description": "Pesquisa semanticamente na base de código usando intenção em vez de pesquisa exata. Use isto para descobrir onde uma funcionalidade ou lógica se encontra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A pergunta ou intenção (ex: 'onde é que a base de dados é guardada?')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "registar_decisao_engenharia",
        "description": "Grava uma decisão técnica de engenharia de software na memória de longo prazo (Decision Memory) do JARVIS, detalhando o porquê da abordagem escolhida e o seu impacto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "description": "A decisão de engenharia tomada (ex: 'Uso de WebSockets em vez de REST para a UI')."
                },
                "reason": {
                    "type": "string",
                    "description": "A razão por detrás desta decisão."
                },
                "impact": {
                    "type": "string",
                    "description": "O impacto esperado ou restrições impostas por esta decisão (opcional)."
                }
            },
            "required": ["decision", "reason"]
        }
    },
    {
        "name": "atualizar_memoria_arquitetura",
        "description": "Adiciona ou atualiza a documentação de arquitetura de um módulo específico na memória de longo prazo (Architecture Memory), especificando o seu propósito, dependências e restrições obrigatórias.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "O nome do módulo ou ficheiro (ex: 'server.py', 'database.py')."
                },
                "purpose": {
                    "type": "string",
                    "description": "O propósito ou função principal do módulo."
                },
                "dependencies": {
                    "type": "string",
                    "description": "Lista de dependências principais do módulo (opcional)."
                },
                "constraints": {
                    "type": "string",
                    "description": "Constraints ou restrições obrigatórias a cumprir (opcional)."
                }
            },
            "required": ["module", "purpose"]
        }
    },
    {
        "name": "execute_command",
        "description": "Executes a shell command (PowerShell) on the user's Windows host machine within the workspace directory. Use this to open programs, run scripts, organize folders, compile, install packages, check states, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command line string to run inside the project workspace. Destructive commands and paths outside the workspace are blocked."
                }
            },
        }
    },
    {
        "name": "frontend_ui_command",
        "description": "Controla a interface gráfica (UI) holográfica do ecrã do utilizador. Pode abrir ou fechar o painel de chat e o painel de desenvolvimento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "A ação a executar na interface. Opções: 'open_chat', 'close_chat', 'toggle_chat', 'open_dev', 'close_dev', 'toggle_dev'"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "write_file",
        "description": "Writes content to a local file. Use this to create or update scripts, configurations, notes, or code assets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The workspace-relative path to write (e.g., 'src/main.py', 'config.json', 'notes.txt'). Paths outside the workspace are blocked."
                },
                "content": {
                    "type": "string",
                    "description": "The exact full text content of the file."
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Reads the content of a local file inside the workspace. Paths outside the workspace are blocked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The workspace-relative path to the file to read."
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "list_directory",
        "description": "Lists the files and folders within a workspace directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The workspace-relative directory path to list. Leave empty or use '.' for workspace root."
                }
            }
        }
    },
    {
        "name": "list_active_windows",
        "description": "Lists the titles of all open application windows currently visible on the user's desktop screen. Use this for situational awareness to check which programs are running, which files are open in editors, or which websites are open in browser tabs.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "capture_screen",
        "description": "Captures a screenshot of the user's primary desktop monitor. Use this to inspect the current state of a program, see error messages, or view the visual layout of any application the user has open.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "chamar_swarm_dominio",
        "description": "Delega tarefas complexas a um swarm de domínio especializado da CrewAI. Os domínios disponíveis são: 'builder_swarm' (código, websites, apps, APIs, scripts, bases de dados), 'operator_swarm' (ficheiros, backups, contentores, comandos do SO), 'creator_swarm' (designs, ebooks, landing pages, cursos, copy persuasivo), 'growth_swarm' (marketing, SEO, monetização, nichos, vendas) e 'research_swarm' (pesquisas web, Obsidian, sumários).",
        "input_schema": {
            "type": "object",
            "properties": {
                "dominio": {
                    "type": "string",
                    "enum": ["builder_swarm", "operator_swarm", "creator_swarm", "growth_swarm", "research_swarm"],
                    "description": "O nome do domínio do swarm a acionar."
                },
                "prompt_projeto": {
                    "type": "string",
                    "description": "O objetivo ou tarefa específica a ser executada pelo swarm (ex: 'Pesquisa de nichos lucrativos para infoprodutos de IA')."
                }
            },
            "required": ["dominio", "prompt_projeto"]
        }
    },
    # ECC Pattern 6: Verification Loop Tool
    {
        "name": "verificar_qualidade",
        "description": "ECC Quality Gate — verifica se o trabalho produzido cumpre os critérios de qualidade antes de reportar 'concluído' ao CEO. Usa SEMPRE antes de terminar qualquer tarefa de criação de código ou ficheiros.",
        "input_schema": {
            "type": "object",
            "properties": {
                "criterios_cumpridos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista dos critérios verificados e cumpridos (ex: ['HTML válido', 'CSS mobile-first', 'JS sem console.log'])"
                },
                "problemas_encontrados": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de problemas encontrados. Vazia se tudo OK."
                },
                "pronto_para_entrega": {
                    "type": "boolean",
                    "description": "true se o trabalho está pronto para o CEO, false se precisa de mais iterações."
                },
                "ficheiros_criados": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista dos ficheiros criados ou modificados nesta sessão (ex: ['sandbox_dir/index.html'])"
                }
            },
            "required": ["criterios_cumpridos", "pronto_para_entrega"]
        }
    },
    # Loop Engineering: Goal Declaration Tool (Slide 2 — Goal → Run → Check cycle)
    {
        "name": "declarar_objetivo",
        "description": "Loop Engineering — declara o OBJETIVO do loop antes de qualquer acção. DEVES chamar esta ferramenta PRIMEIRO, antes de qualquer outra, para definir claramente o que constitui sucesso. Isto define o 'Goal' do loop automático.",
        "input_schema": {
            "type": "object",
            "properties": {
                "objetivo": {
                    "type": "string",
                    "description": "O objetivo claro e conciso do loop (ex: 'Criar um website de portfólio com 3 páginas funcionais')"
                },
                "criterios_de_sucesso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de critérios verificavéis que definem quando o objetivo está atingido (ex: ['index.html existe em sandbox_dir', 'CSS tem variáveis CSS definidas', 'JS sem erros de consola'])"
                },
                "complexidade_estimada": {
                    "type": "string",
                    "enum": ["baixa", "média", "alta"],
                    "description": "Estimativa de complexidade da tarefa. Baixa: 1-3 passos. Média: 4-8 passos. Alta: 9+ passos."
                }
            },
            "required": ["objetivo", "criterios_de_sucesso"]
        }
    },
    # Dynamic Agent Spawning Tool
    # Any agent can request a specialist to be created on-the-fly
    {
        "name": "criar_agente_especialista",
        "description": "Dynamic Agent Spawning — cria um agente especialista ad-hoc quando a equipa não tem a expertise necessária para uma tarefa específica. O agente é instanciado com uma persona, backstory e tarefa definidos por ti. Usa isto quando precisares de uma competência que nenhum membro da equipa actual tem (ex: especialista em SQL, perito em segurança, tradutor, membro de algoritmos, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": "O nome do agente especialista a criar (ex: 'Marta', 'Prof. Chen', 'DriveBot')"
                },
                "especialidade": {
                    "type": "string",
                    "description": "A especialidade/função do agente (ex: 'Especialista em Optimização SQL', 'Perito em Segurança Web', 'Revisor de Código Python')"
                },
                "backstory": {
                    "type": "string",
                    "description": "A persona e experiência do agente (ex: 'Tens 15 anos de experiência em bases de dados relacionais e PostgreSQL. Optimizaste queries para empresas Fortune 500.')"
                },
                "tarefa": {
                    "type": "string",
                    "description": "A tarefa concreta e detalhada que o agente deve executar. Inclui todo o contexto relevante."
                },
                "contexto_projeto": {
                    "type": "string",
                    "description": "Resumo do projecto actual para dar contexto ao especialista (ex: 'Estamos a construir uma loja e-commerce em HTML/CSS/JS vanilla. O problema actual é X.')"
                },
                "guardar_agente": {
                    "type": "boolean",
                    "description": "Se true, o agente é guardado no regiâo de agentes para reutilização futura. Default: false."
                }
            },
            "required": ["nome", "especialidade", "backstory", "tarefa", "contexto_projeto"]
        }
    },
    {
        "name": "obsidian_list_notes",
        "description": "Lists all markdown notes (.md) currently present in your Obsidian Vault recursively. Returns the relative file paths.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "obsidian_read_note",
        "description": "Reads the text content of a specific Obsidian note. You can provide the file path relative to the vault root (e.g. 'Resumos/Biologia.md' or 'Ideas/GameDesign'). Extension .md is optional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The relative path of the note to read (e.g. 'Projetos/Ideias' or 'Meeting.md')"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "obsidian_write_note",
        "description": "Writes text content to a specific Obsidian knowledge-base Markdown note. Do not use for apps, frontend/backend code, or sandbox files; use write_file for those.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The relative path of the note to write (e.g. 'Projetos/Planeamento' or 'Inbox.md')"
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write to the note."
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "obsidian_search_notes",
        "description": "Searches for notes matching a search query inside their content within the Obsidian Vault.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text query or keyword to search for inside notes."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "firecrawl_scrape_url",
        "description": "Scrapes a webpage and converts its content into clean Markdown using the Firecrawl API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The absolute URL of the webpage to scrape."
                }
            },
            "required": ["url"]
        }
    },

    {
        "name": "apify_run_actor",
        "description": "Runs a specific Apify Actor (web scraper / automation) and returns the dataset results in JSON format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "actor_id": {
                    "type": "string",
                    "description": "The ID of the Apify Actor to run (e.g. 'apify/google-maps-scraper')."
                },
                "input_data": {
                    "type": "object",
                    "description": "The JSON input data arguments required by the Actor."
                }
            },
            "required": ["actor_id", "input_data"]
        }
    },
    {
        "name": "browserbase_load_page",
        "description": "Loads a webpage securely using Browserbase headless cloud browser and returns the HTML content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The absolute URL of the page to load."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "youtube_get_transcript",
        "description": "Retrieves the full textual transcript of a YouTube video, useful for analyzing and summarizing video content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id_or_url": {
                    "type": "string",
                    "description": "The YouTube video ID or full video URL (e.g. 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')."
                }
            },
            "required": ["video_id_or_url"]
        }
    },
    {
        "name": "composio_execute_action",
        "description": "Executes a dynamic action on external applications (such as Gmail, Slack, GitHub, Trello, Google Calendar) via the Composio SDK.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_name": {
                    "type": "string",
                    "description": "The uppercase name of the action to execute (e.g. 'GMAIL_SEND_EMAIL', 'SLACK_POST_MESSAGE', 'GITHUB_CREATE_ISSUE', 'TRELLO_CREATE_CARD')."
                },
                "arguments": {
                    "type": "object",
                    "description": "The dictionary of argument key-values required for the specific action."
                }
            },
            "required": ["action_name", "arguments"]
        }
    },
    {
        "name": "gravar_regra_compounding",
        "description": "ECC Compounding Memory — Grava uma nova regra ou lição aprendida de compounding memory no banco de dados SQLite do Jarvis OS. Deves chamar esta ferramenta sempre que cometeres um erro e o corrigires, ou quando o utilizador (CEO) te corrigir ou der uma preferência explícita, para que não te esqueças nas próximas sessões.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chave": {
                    "type": "string",
                    "description": "Uma palavra-chave única em inglês ou português (sem espaços, minúscula, ex: 'neon_theme', 'python_venv', 'fastapi_routing') para identificar a regra."
                },
                "descricao": {
                    "type": "string",
                    "description": "Descrição detalhada do contexto ou do erro que ocorreu (ex: 'O utilizador prefere o tema visual neon do que o cyberpunk.')"
                },
                "correcao": {
                    "type": "string",
                    "description": "A instrução corretiva que o agente deve seguir daqui para a frente (ex: 'Sempre que o tema visual for solicitado ou alterado, usar neon por defeito.')"
                }
            },
            "required": ["chave", "descricao", "correcao"]
        }
    },
    {
        "name": "read_pdf",
        "description": "Extracts and returns the full text content of a local PDF file (research papers, documents, reports). Use this to read academic papers the user has placed in the sandbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the PDF file. Relative to the sandbox directory or absolute."
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum number of pages to extract. Defaults to 20."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "search_arxiv",
        "description": "Searches arXiv.org for academic research papers. Returns titles, authors, abstracts and PDF links. Ideal for literature reviews and finding related work for a thesis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. 'multi-agent orchestration large language models')."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of papers to return. Defaults to 5."
                }
            },
            "required": ["query"]
        }
    }
]


def get_tool_registry():
    from agents.tool_registry import build_registry

    return build_registry(JARVIS_TOOLS)


def get_tool_definitions():
    return get_tool_registry().to_llm_tools()

