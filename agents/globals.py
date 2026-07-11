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
    import anthropic
except ImportError:
    pass
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


# --- message_callback ---
message_callback = None


# --- file_callback ---
file_callback = None


# --- kanban_callback ---
kanban_callback = None


# --- is_gemini_valid ---
is_gemini_valid = True


# --- gemini_key ---
gemini_key = os.getenv("GEMINI_API_KEY")


# --- mode ---
mode = os.getenv("ORCHESTRATOR_MODE", "local").lower()


# --- active_template_name ---
active_template_name = "builder_swarm"


# --- _ECC_BASE_DIR ---
_ECC_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- _SKILL_AGENT_MAP ---
_SKILL_AGENT_MAP = {
    "alex":   "pm-brief",
    "devon":  "web-dev",
    "clara":  "ui-ux-guide",
    "quinn":  "qa-checklist",
    "sofia":  "pm-brief",
    "leonel": "pm-brief",
    "bruno":  "pm-brief",
}


# --- _MEMORY_DIR ---
_MEMORY_DIR = Path(_ECC_BASE_DIR) / "config"


# --- _MEMORY_PATH ---
_MEMORY_PATH = _MEMORY_DIR / "session_memory.json"


# --- _METRICS_PATH ---
_METRICS_PATH = _MEMORY_DIR / "loop_metrics.json"


# --- _SPAWNED_AGENTS_PATH ---
_SPAWNED_AGENTS_PATH = Path(_ECC_BASE_DIR) / "config" / "spawned_agents.json"


# --- BASE_DIR ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

