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
    pass

import agents.globals as glb
import agents.utils as utils
import agents.memory as memory
import agents.tools as ag_tools
import agents.obsidian_tools as obs_tools
import agents.swarm as swarm
import server
from agents.providers.factory import build_crewai_llm


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_ECC_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_SKILL_AGENT_MAP = {
    "pm": ["pm-brief", "idea-refine", "interview-me"],
    "qa": ["qa-checklist", "browser-testing-with-devtools", "debugging-and-error-recovery"],
    "tester": ["qa-checklist", "browser-testing-with-devtools", "debugging-and-error-recovery"],
    "designer": ["ui-ux-guide", "frontend-ui-engineering"],
    "coder": ["web-dev", "test-driven-development", "code-review-and-quality", "code-simplification", "incremental-implementation"],
    "dev_lead": ["api-and-interface-design", "spec-driven-development", "planning-and-task-breakdown", "documentation-and-adrs"],
    "sys_admin": ["ci-cd-and-automation", "git-workflow-and-versioning"],
    "ops_specialist": ["observability-and-instrumentation", "security-and-hardening"],
}

_PROMPT_KEYWORD_SKILLS = [
    (["test", "tdd", "assert", "jest", "pytest", "spec"], "test-driven-development"),
    (["refactor", "limpar", "simplificar", "clean code"], "code-simplification"),
    (["api", "rest", "endpoint", "interface", "swagger"], "api-and-interface-design"),
    (["ui", "ux", "frontend", "css", "component", "taildwind"], "frontend-ui-engineering"),
    (["bug", "erro", "fix", "debug", "stacktrace"], "debugging-and-error-recovery"),
    (["git", "commit", "branch", "pr", "merge"], "git-workflow-and-versioning"),
    (["segurança", "security", "auth", "token", "jwt"], "security-and-hardening"),
    (["doc", "readme", "adr", "documentar"], "documentation-and-adrs"),
    (["desempenho", "perf", "webperf", "lenta", "otimizar"], "performance-optimization"),
    (["deploy", "ci", "cd", "docker", "release", "ship"], "shipping-and-launch"),
]


def _read_skill_file(skill_name: str) -> str:
    """Reads and compiles a skill file from .agents/skills/<name>/SKILL.md or config/skills/<name>.md using SkVM."""
    from backend.model_harness.skvm import SkillVMCompiler
    raw_content = ""
    p1 = Path(_ECC_BASE_DIR) / ".agents" / "skills" / skill_name / "SKILL.md"
    if p1.exists():
        raw_content = p1.read_text(encoding="utf-8")
    else:
        p2 = Path(_ECC_BASE_DIR) / "config" / "skills" / f"{skill_name}.md"
        if p2.exists():
            raw_content = p2.read_text(encoding="utf-8")

    if not raw_content:
        return ""

    compiled = SkillVMCompiler.compile_markdown_skill(raw_content, skill_name=skill_name)
    return compiled.to_prompt_contract()


def _build_local_llm():
    """Build the CrewAI LLM used by dynamic swarms from the existing env config."""
    return build_crewai_llm(LLM)


local_llm = _build_local_llm()


# --- load_agent_skills ---
def load_agent_skills(agent_name: str) -> str:
    """ECC Skill Loader — loads all compiled skill files mapped to a given agent."""
    skill_names = _SKILL_AGENT_MAP.get(agent_name.lower(), [])
    skills: list[str] = []
    for s_name in skill_names:
        text = _read_skill_file(s_name)
        if text:
            skills.append(text)
    return "\n\n".join(skills)


# --- load_skills_for_template ---
def load_skills_for_template(template_cfg: dict, prompt_text: str = "") -> str:
    """Loads and concatenates skills for all agents in a template, plus prompt-triggered skills."""
    skills_text = ""
    for agent_name in template_cfg.get("agents", {}).keys():
        skill = load_agent_skills(agent_name)
        if skill:
            skills_text += f"\n\n### Skills de {agent_name.capitalize()}\n{skill}"

    if prompt_text:
        prompt_lower = prompt_text.lower()
        matched_skills = []
        for keywords, skill_name in _PROMPT_KEYWORD_SKILLS:
            if any(k in prompt_lower for k in keywords):
                text = _read_skill_file(skill_name)
                if text:
                    matched_skills.append(f"#### Skill Relevante: {skill_name}\n{text[:1200]}...")
        if matched_skills:
            skills_text += "\n\n### Skills de Engenharia Ativadas por Contexto\n" + "\n\n".join(matched_skills)

    return skills_text


# --- get_active_template ---
def get_active_template(template_name: str = None) -> dict:
    if template_name is None:
        template_name = "builder_swarm"
    
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
    templates_path = os.path.join(config_dir, "templates.yaml")
    
    if os.path.exists(templates_path):
        try:
            all_templates = utils.load_yaml_config(templates_path)
            if template_name in all_templates:
                return all_templates[template_name]
        except Exception as e:
            print(f"Error loading templates.yaml: {e}")
            
    # Fallback to older configs if templates.yaml is missing or fails
    try:
        agents_cfg = utils.load_yaml_config(os.path.join(config_dir, "agents.yaml"))
        tasks_cfg = utils.load_yaml_config(os.path.join(config_dir, "tasks.yaml"))
        return {
            "name": "Desenvolvimento de Software",
            "description": "Equipa de engenharia ágil para criar websites, landing pages e aplicações web funcionais.",
            "agents": agents_cfg,
            "tasks": tasks_cfg
        }
    except Exception as e:
        print(f"Error in dynamic fallback configuration: {e}")
        return {
            "name": "Desenvolvimento de Software",
            "description": "",
            "agents": {},
            "tasks": {}
        }


# --- run_crew_orchestration ---
async def run_crew_orchestration(prompt_text: str, session_id: int, on_msg, on_file, on_kanban, template_name: str = "builder_swarm"):
    global message_callback, file_callback, kanban_callback
    message_callback = on_msg
    file_callback = on_file
    kanban_callback = on_kanban
    verbose_progress = _env_bool("ORCHESTRATOR_VERBOSE_PROGRESS", False)
    
    template = get_active_template(template_name)
    agents_cfg = template["agents"]
    tasks_cfg = template["tasks"]

    # 0. Load Awesome Design System if available (specifically for coding/design tasks)
    design_system_content = ""
    vault_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "obsidian_vault")
    if os.path.exists(vault_dir):
        for root, dirs, files in os.walk(vault_dir):
            if "Awesome Design.md" in files:
                try:
                    with open(os.path.join(root, "Awesome Design.md"), "r", encoding="utf-8") as f:
                        design_system_content = f.read()
                    break
                except Exception as e:
                    print(f"Erro ao ler Awesome Design.md no RAG da Crew: {e}")

    # 0. Load Obsidian dynamic context (RAG)
    obsidian_context = obs_tools.buscar_contexto_obsidian(prompt_text)
    if obsidian_context and verbose_progress:
        on_msg("OPENCLAW", "Orquestrador", "📖 *Contexto relevante do Obsidian carregado para o Swarm.*")

    # Create dynamic Agent objects
    agents_map = {}
    for agent_id, cfg in agents_cfg.items():
        if agent_id.lower() == "jarvis":
            continue
            
        backstory = cfg["backstory"]
        if design_system_content and agent_id in ["designer", "coder"]:
            backstory += f"\n\nATENÇÃO OBRIGATÓRIA: Segue o Design System da agência:\n{design_system_content}"
            
        if obsidian_context:
            backstory += f"\n\n{obsidian_context}"
            
        agents_map[agent_id] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=backstory,
            verbose=verbose_progress,
            llm=local_llm,
            tools=CREW_TOOLS
        )

    # Create dynamic Task objects
    tasks = []
    
    def make_task_callback(tid, agent_id, agent_role, agent_name):
        def task_callback(output):
            text = get_output_text(output)
            on_kanban(tid, "done")
            
            on_msg(agent_name, agent_role, text)
            
            # Move next task to progress
            task_ids = list(tasks_cfg.keys())
            try:
                idx = task_ids.index(tid)
                if idx + 1 < len(task_ids):
                    on_kanban(task_ids[idx + 1], "progress")
            except ValueError:
                pass
        return task_callback

    for tid, tcfg in tasks_cfg.items():
        ag_id = tcfg["agent"]
        ag_obj = agents_map.get(ag_id)
        if not ag_obj:
            continue
            
        agent_name = ag_id.capitalize()
        agent_role = agents_cfg[ag_id]["role"]
        
        # Format task description
        task_desc = tcfg["description"]
        if "{prompt_text}" in task_desc:
            task_desc = task_desc.format(prompt_text=prompt_text)
            
        tasks.append(Task(
            description=task_desc,
            expected_output=tcfg.get("expected_output", "Resultado da tarefa."),
            agent=ag_obj,
            callback=make_task_callback(tid, ag_id, agent_role, agent_name)
        ))

    # Define Crew
    crew = Crew(
        agents=list(agents_map.values()),
        tasks=tasks,
        verbose=verbose_progress
    )

    # Kickoff Crew execution
    first_tid = None
    if tasks:
        first_tid = list(tasks_cfg.keys())[0]
        on_kanban(first_tid, "progress")
        
    try:
        result = await crew.kickoff_async()
    except asyncio.CancelledError:
        if first_tid:
            on_kanban(first_tid, "review")
        on_msg("OPENCLAW", "Orquestrador", f"Swarm '{template_name}' cancelado durante a execucao.")
        raise
    except Exception as e:
        if first_tid:
            on_kanban(first_tid, "review")
        error_msg = f"Swarm '{template_name}' interrompido com erro: {e}"
        on_msg("OPENCLAW", "Orquestrador", error_msg)
        return error_msg

    result_text = get_output_text(result)
    
    return f"Orquestração do swarm '{template_name}' finalizada com sucesso! Relatório final:\n\n{result_text}"


# --- run_sync ---
def run_sync(coro):
    """Executa uma coroutine de forma síncrona, lidando com loops de eventos existentes ou novos."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import threading
        result = []
        error = []
        def run_in_thread():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result.append(new_loop.run_until_complete(coro))
            except Exception as e:
                error.append(e)
            finally:
                new_loop.close()
        t = threading.Thread(target=run_in_thread)
        t.start()
        t.join()
        if error:
            raise error[0]
        res = result[0]
    else:
        res = loop.run_until_complete(coro)
    return utils.truncate_result(res)


# --- crew_apply_code_patch ---
@tool("apply_code_patch")
def crew_apply_code_patch(file_path: str, symbol_name: str, new_code: str) -> str:
    """Edita cirurgicamente uma função ou classe num ficheiro baseado em AST."""
    from agents.patch_engine import PatchEngine
    pe = PatchEngine()
    return pe.apply_patch(file_path, symbol_name, new_code)

# --- crew_refactor_move_symbol ---
@tool("refactor_move_symbol")
def crew_refactor_move_symbol(source_file: str, target_file: str, symbol_name: str) -> str:
    """Move uma classe ou função inteira de um ficheiro para o outro de forma limpa usando a AST."""
    from agents.refactor_engine import RefactorEngine
    re = RefactorEngine()
    return re.move_symbol(source_file, target_file, symbol_name)

# --- crew_refactor_rename_symbol ---
@tool("refactor_rename_symbol")
def crew_refactor_rename_symbol(filepath: str, old_name: str, new_name: str) -> str:
    """Altera o nome a uma função ou classe num ficheiro."""
    from agents.refactor_engine import RefactorEngine
    re = RefactorEngine()
    return re.rename_symbol(filepath, old_name, new_name)

# --- crew_semantic_code_search ---
@tool("semantic_code_search")
def crew_semantic_code_search(query: str) -> str:
    """Pesquisa semanticamente na base de código usando intenção em vez de pesquisa exata. Use isto para descobrir onde uma funcionalidade ou lógica se encontra."""
    from intelligence.semantic_index import SemanticCodeIndex
    idx = SemanticCodeIndex()
    idx.build_index()
    return idx.search(query)

# --- crew_execute_command ---
@tool("execute_command")
def crew_execute_command(command: str) -> str:
    """Executes a shell command (PowerShell) on the user's Windows host machine within the workspace directory. Use this to open programs, run scripts, organize folders, compile, install packages, check states, etc."""
    return run_sync(ag_tools.run_local_command(command))


# --- crew_write_file ---
@tool("write_file")
def crew_write_file(filename: str, content: str) -> str:
    """Writes content to a local file. Use this to create or update scripts, configurations, notes, or code assets."""
    return run_sync(ag_tools.run_write_file(filename, content))


# --- crew_read_file ---
@tool("read_file")
def crew_read_file(filename: str) -> str:
    """Reads the content of any local file in the workspace or system."""
    return run_sync(ag_tools.run_read_file(filename))


# --- crew_list_directory ---
@tool("list_directory")
def crew_list_directory(path: str = ".") -> str:
    """Lists the files and folders within a directory."""
    return run_sync(ag_tools.run_list_directory(path))


# --- crew_obsidian_list_notes ---
@tool("obsidian_list_notes")
def crew_obsidian_list_notes() -> str:
    """Lists all markdown notes (.md) currently present in your Obsidian Vault recursively. Returns the relative file paths."""
    return run_sync(obs_tools.run_obsidian_list_notes())


# --- crew_obsidian_read_note ---
@tool("obsidian_read_note")
def crew_obsidian_read_note(filename: str) -> str:
    """Reads the text content of a specific Obsidian note. You can provide the file path relative to the vault root (e.g. 'Resumos/Biologia.md' or 'Ideas/GameDesign'). Extension .md is optional."""
    return run_sync(obs_tools.run_obsidian_read_note(filename))


# --- crew_obsidian_write_note ---
@tool("obsidian_write_note")
def crew_obsidian_write_note(filename: str, content: str) -> str:
    """Writes text content to a specific Obsidian note (creates it if it doesn't exist, or overwrites it). Path is relative to the vault root."""
    return run_sync(obs_tools.run_obsidian_write_note(filename, content))


# --- crew_obsidian_search_notes ---
@tool("obsidian_search_notes")
def crew_obsidian_search_notes(query: str) -> str:
    """Searches for notes matching a search query inside their content within the Obsidian Vault."""
    return run_sync(obs_tools.run_obsidian_search_notes(query))


# --- crew_firecrawl_scrape_url ---
@tool("firecrawl_scrape_url")
def crew_firecrawl_scrape_url(url: str) -> str:
    """Scrapes a webpage and converts its content into clean Markdown using the Firecrawl API."""
    return run_sync(ag_tools.run_firecrawl_scrape(url))


# --- crew_browserbase_load_page ---
@tool("browserbase_load_page")
def crew_browserbase_load_page(url: str) -> str:
    """Loads a webpage securely using Browserbase headless cloud browser and returns the HTML content."""
    return run_sync(ag_tools.run_browserbase_load(url))


# --- crew_youtube_get_transcript ---
@tool("youtube_get_transcript")
def crew_youtube_get_transcript(video_id_or_url: str) -> str:
    """Retrieves the full textual transcript of a YouTube video, useful for analyzing and summarizing video content."""
    return run_sync(ag_tools.run_youtube_transcript(video_id_or_url))


# --- crew_capture_screen ---
@tool("capture_screen")
def crew_capture_screen() -> str:
    """Captures a screenshot of the user's desktop screen and returns the image format/path."""
    fmt, b64_or_path = run_sync(ag_tools.run_capture_screen())
    return f"Screenshot captured successfully format={fmt} path={b64_or_path[:100]}"

# --- crew_web_search ---
@tool("web_search")
def crew_web_search(query: str) -> str:
    """Performs a web search or URL scrape to gather information, research competitors, or find documentation."""
    if query.startswith("http://") or query.startswith("https://"):
        return run_sync(ag_tools.run_local_scrape(query))
    return run_sync(ag_tools.run_firecrawl_scrape(query))

# --- crew_run_unit_tests ---
@tool("run_unit_tests")
def crew_run_unit_tests(test_path: str = "tests") -> str:
    """Executes automated unit tests using python unittest or pytest in the current workspace directory."""
    cmd = f".\\venv\\Scripts\\python.exe -m unittest discover -s {test_path}" if os.name == "nt" else f"python -m unittest discover -s {test_path}"
    return run_sync(ag_tools.run_local_command(cmd))


# --- CREW_TOOLS ---
CREW_TOOLS = [
    crew_apply_code_patch,
    crew_refactor_move_symbol,
    crew_refactor_rename_symbol,
    crew_semantic_code_search,
    crew_execute_command,
    crew_write_file,
    crew_read_file,
    crew_list_directory,
    crew_obsidian_list_notes,
    crew_obsidian_read_note,
    crew_obsidian_write_note,
    crew_obsidian_search_notes,
    crew_firecrawl_scrape_url,
    crew_browserbase_load_page,
    crew_youtube_get_transcript,
    crew_capture_screen,
    crew_web_search,
    crew_run_unit_tests,
]

