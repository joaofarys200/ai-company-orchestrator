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

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CODE_ARTIFACT_NOTE_RE = re.compile(
    r"\.(?:py|js|jsx|ts|tsx|css|html?|json|ya?ml|toml|sql|sh|bat|ps1|env)(?:\.md)?$",
    re.IGNORECASE,
)


def obsidian_path_looks_like_code_artifact(filename: str) -> bool:
    normalized = str(filename or "").strip().replace("\\", "/").lstrip("/")
    lowered = normalized.lower()
    if not lowered:
        return False
    if lowered.startswith(("sandbox_dir/", "sandbox/")):
        return True
    leaf = lowered.rsplit("/", 1)[-1]
    return bool(CODE_ARTIFACT_NOTE_RE.search(leaf))


# --- get_obsidian_vault_path ---
def get_obsidian_vault_path() -> str:
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        vault_path = os.path.join(BASE_DIR, "obsidian_vault")
    else:
        vault_path = os.path.abspath(vault_path)
    os.makedirs(vault_path, exist_ok=True)
    return vault_path


# --- buscar_contexto_obsidian ---
def buscar_contexto_obsidian(prompt: str) -> str:
    """
    RAG Automático do Obsidian — analisa o prompt, pesquisa no vault local e
    retorna o conteúdo das 2 notas mais relevantes.
    """
    try:
        vault_path = get_obsidian_vault_path()
        if not os.path.exists(vault_path):
            return ""
            
        # Extrair palavras-chave simples
        palavras = [w.strip().lower() for w in re.findall(r"\w+", prompt) if len(w.strip()) > 3]
        if not palavras:
            return ""
            
        scores = []
        for root, _, files in os.walk(vault_path):
            # Ignorar diretórios internos do Obsidian
            if ".obsidian" in root:
                continue
            for f in files:
                if f.lower().endswith(".md"):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, vault_path).replace("\\", "/")
                    
                    score = 0
                    # 1. Pontuação pelo nome do ficheiro (peso maior)
                    nome_f = f.lower()
                    for p in palavras:
                        if p in nome_f:
                            score += 10
                            
                    # 2. Pontuação pelo conteúdo
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                            content = file_obj.read()
                        content_lower = content.lower()
                        for p in palavras:
                            # Contar ocorrências
                            score += content_lower.count(p)
                    except Exception:
                        content = ""
                        
                    if score > 0:
                        scores.append((score, rel_path, content))
                        
        if not scores:
            return ""
            
        # Ordenar por pontuação descendente e tirar as 2 melhores notas
        scores.sort(key=lambda x: x[0], reverse=True)
        melhores = scores[:2]
        
        context_parts = ["\n## Contexto Local do Obsidian (RAG)"]
        context_parts.append("Ficheiros relevantes encontrados no teu cofre do Obsidian:")
        for score, path, content in melhores:
            # Limitar conteúdo a ~3000 caracteres para evitar estourar limites de contexto
            if len(content) > 3000:
                content = content[:3000] + "\n... [Restante conteúdo omitido para poupar tokens] ..."
            context_parts.append(f"### Nota: `{path}` (Score: {score})\n```markdown\n{content}\n```\n")
            
        return "\n".join(context_parts)
    except Exception as e:
        print(f"[RAG Obsidian] Erro ao buscar contexto: {e}")
        return ""


# --- safe_join_vault ---
def safe_join_vault(vault_path: str, filename: str) -> str:
    filename = filename.replace("\\", "/").lstrip("/")
    vault_root = os.path.realpath(os.path.abspath(vault_path))
    full_path = os.path.realpath(os.path.abspath(os.path.join(vault_root, filename)))
    try:
        outside_vault = os.path.commonpath([vault_root, full_path]) != vault_root
    except ValueError:
        outside_vault = True
    if outside_vault:
        raise ValueError("Acesso fora da pasta do Obsidian não permitido.")
    return full_path


# --- run_obsidian_list_notes ---
async def run_obsidian_list_notes() -> str:
    loop = asyncio.get_running_loop()
    def list_notes():
        try:
            vault_path = get_obsidian_vault_path()
            md_files = []
            for root, _, files in os.walk(vault_path):
                for f in files:
                    if f.lower().endswith(".md"):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, vault_path).replace("\\", "/")
                        md_files.append(rel_path)
            return "\n".join(md_files) if md_files else "(Nenhuma nota encontrada no Obsidian)"
        except Exception as e:
            return f"Erro ao listar notas: {str(e)}"
    return await loop.run_in_executor(None, list_notes)


# --- run_obsidian_read_note ---
async def run_obsidian_read_note(filename: str) -> str:
    loop = asyncio.get_running_loop()
    def read_note():
        try:
            vault_path = get_obsidian_vault_path()
            if not filename.lower().endswith(".md"):
                fn = filename + ".md"
            else:
                fn = filename
            full_path = safe_join_vault(vault_path, fn)
            if not os.path.exists(full_path):
                return f"Erro: A nota '{filename}' não existe no Obsidian."
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Erro ao ler nota: {str(e)}"
    return await loop.run_in_executor(None, read_note)


# --- run_obsidian_write_note ---
async def run_obsidian_write_note(filename: str, content: str) -> str:
    loop = asyncio.get_running_loop()
    def write_note():
        try:
            if not filename or not str(filename).strip():
                return "Erro ao escrever nota: filename em falta."
            if content is None:
                return "Erro ao escrever nota: content em falta."
            if obsidian_path_looks_like_code_artifact(filename):
                return (
                    "Erro ao escrever nota: caminho parece artefacto de codigo/sandbox. "
                    "Usa write_file para apps, frontend, backend e ficheiros da sandbox."
                )
            vault_path = get_obsidian_vault_path()
            if not filename.lower().endswith(".md"):
                fn = filename + ".md"
            else:
                fn = filename
            full_path = safe_join_vault(vault_path, fn)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Nota '{filename}' guardada com sucesso no Obsidian ({len(content)} bytes)."
        except Exception as e:
            return f"Erro ao escrever nota: {str(e)}"
    return await loop.run_in_executor(None, write_note)


# --- run_obsidian_search_notes ---
async def run_obsidian_search_notes(query: str) -> str:
    loop = asyncio.get_running_loop()
    def search_notes():
        try:
            vault_path = get_obsidian_vault_path()
            results = []
            query_lower = query.lower().strip()
            keywords = [w.strip().lower() for w in re.findall(r"[\w\-]+", query) if len(w.strip()) > 2]
            if not keywords and not query_lower:
                return "Pesquisa vazia."

            scored_matches = []
            for root, _, files in os.walk(vault_path):
                if ".obsidian" in root:
                    continue
                for f in files:
                    if f.lower().endswith(".md"):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, vault_path).replace("\\", "/")
                        rel_lower = rel_path.lower()
                        
                        score = 0
                        snippet = ""

                        try:
                            with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                                content = file_obj.read()
                        except Exception:
                            content = ""

                        content_lower = content.lower()

                        # Exact full query match
                        if query_lower in rel_lower:
                            score += 100
                            snippet = "[Correspondência exata no nome do ficheiro]"
                        elif query_lower in content_lower:
                            score += 80
                            idx = content_lower.find(query_lower)
                            start = max(0, idx - 40)
                            end = min(len(content), idx + len(query) + 40)
                            snippet = "..." + content[start:end].replace("\n", " ") + "..."

                        # Keyword token matches
                        for kw in keywords:
                            if kw in rel_lower:
                                score += 20
                            if kw in content_lower:
                                score += min(content_lower.count(kw), 10)
                                if not snippet:
                                    idx = content_lower.find(kw)
                                    start = max(0, idx - 40)
                                    end = min(len(content), idx + len(kw) + 60)
                                    snippet = "..." + content[start:end].replace("\n", " ") + "..."

                        if score > 0:
                            scored_matches.append((score, rel_path, snippet or "[Conteúdo relevante]"))

            scored_matches.sort(key=lambda x: x[0], reverse=True)
            for score, rel_path, snip in scored_matches[:10]:
                results.append(f"- **{rel_path}** (Score {score}): {snip}")

            return "\n".join(results) if results else f"Nenhuma nota correspondente a '{query}' encontrada."
        except Exception as e:
            return f"Erro ao pesquisar notas: {str(e)}"
    return await loop.run_in_executor(None, search_notes)

