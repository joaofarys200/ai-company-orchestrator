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


# --- truncate_result ---
def truncate_result(res: str, limit: int = 100000) -> str:
    """Trunca resultados de ferramentas extremamente longos para evitar estoiros de limites de contexto."""
    if not isinstance(res, str):
        res = str(res)
    if len(res) > limit:
        return res[:limit] + f"\n\n... [Aviso: Conteúdo truncado pelo sistema com {len(res) - limit} caracteres restantes ocultados para poupar limites de contexto] ..."
    return res


# --- extract_code_block ---
def extract_code_block(text: str) -> str:
    # Extract content from markdown code blocks
    pattern = re.compile(r"```(?:\w+)?\n(.*?)\n```", re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


# --- get_output_text ---
def get_output_text(output):
    if hasattr(output, 'raw'):
        return output.raw
    return str(output)


# --- load_yaml_config ---
def load_yaml_config(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

