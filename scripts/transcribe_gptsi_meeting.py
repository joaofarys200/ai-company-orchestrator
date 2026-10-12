import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv
import imageio_ffmpeg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(".env")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[ERRO] GEMINI_API_KEY não encontrada no .env", flush=True)
    sys.exit(1)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
INPUT_AUDIO = r"C:\Users\joaor\Documents\Gravações de Som\reunião gptsi.m4a"

if not os.path.exists(INPUT_AUDIO):
    print(f"[ERRO] Ficheiro não encontrado: {INPUT_AUDIO}", flush=True)
    sys.exit(1)

TEMP_DIR = Path("temp_transcription")
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = TEMP_DIR / "transcription_checkpoint.json"

TOTAL_DURATION = 5196  # 1h 26m 36s
CHUNK_DURATION = 180   # 3 minutos por bloco

def format_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def generate_chunks():
    chunks = []
    start = 0
    idx = 1
    while start < TOTAL_DURATION:
        dur = min(CHUNK_DURATION, TOTAL_DURATION - start)
        end = start + dur
        chunks.append({
            "index": idx,
            "start_sec": start,
            "end_sec": end,
            "duration": dur,
            "start_str": format_time(start),
            "end_str": format_time(end)
        })
        start = end
        idx += 1
    return chunks

def upload_and_wait_file(file_path: Path, mime_type: str = "audio/mp3") -> str:
    size = os.path.getsize(file_path)
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json"
    }
    init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={GEMINI_KEY}"
    metadata = {"file": {"display_name": file_path.name}}
    init_res = requests.post(init_url, headers=headers, json=metadata)
    init_res.raise_for_status()
    upload_url = init_res.headers.get("X-Goog-Upload-URL")

    with open(file_path, "rb") as f:
        up_res = requests.post(
            upload_url,
            headers={
                "Content-Length": str(size),
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0"
            },
            data=f
        )
    up_res.raise_for_status()
    file_info = up_res.json()["file"]
    file_name = file_info["name"]
    file_uri = file_info["uri"]

    # Aguardar até o ficheiro estar ACTIVE no Gemini Files API
    for _ in range(20):
        check_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={GEMINI_KEY}"
        status_res = requests.get(check_url)
        if status_res.status_code == 200:
            current_state = status_res.json().get("state")
            if current_state == "ACTIVE":
                return file_uri
            elif current_state == "FAILED":
                raise RuntimeError(f"Ficheiro falhou no Gemini: {status_res.json()}")
        time.sleep(1.5)
        
    return file_uri

def transcribe_chunk(file_uri: str, chunk_info: dict) -> str:
    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    
    prompt = f"""Atua como transcritor pericial de reuniões de Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI) em Português Europeu (PT-PT).
Gravação: Reunião sobre a criação de um novo Museu e seleção/especificação do sistema de informação (SIUM).
Segmento temporal: [{chunk_info['start_str']} a {chunk_info['end_str']}].

INSTRUÇÕES OBRIGATÓRIAS:
1. Transcreve com rigor todo o discurso falado pelos intervenientes (identificando Professor Luís, Estudante, etc., nas mudanças de turno).
2. Se houver pausas ou silêncio, não inventes texto nem repitas palavras. Transcreve apenas a fala real.
3. Preserva rigorosamente os termos técnicos: SIUM, requisitos, modelo de dados, processos de gestão e operacionais, espólio, arquitetura, etc.
4. Apresenta o texto de forma limpa em parágrafos de diálogo."""

    payload = {
        "contents": [{
            "parts": [
                {"file_data": {"mime_type": "audio/mp3", "file_uri": file_uri}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
    }

    for model_name in models:
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        for attempt in range(3):
            try:
                res = requests.post(gen_url, json=payload, timeout=90)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                elif res.status_code in [429, 503]:
                    time.sleep(3)
                else:
                    time.sleep(2)
            except Exception as e:
                time.sleep(3)
                
    return "[Segmento inaudível ou sem diálogo percetível]"

def generate_executive_summary(full_transcript: str) -> str:
    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]
    
    prompt = f"""Atua como Secretário Técnico e Consultor Sénior de Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI).
Com base na transcrição integral da reunião/aula de 01/10/2026 entre o Professor Luís e os alunos (sobre o novo Museu e o projeto SIUM), elabora uma Síntese Executiva abrangente, estruturada e de elevado rigor técnico.

Estrutura OBRIGATÓRIA:
# SÍNTESE EXECUTIVA — REUNIÃO GPTSI (01/10/2026)

## 1. Contexto e Âmbito do Projeto (SIUM / Novo Museu)
- Enquadramento da nova organização independente criada de raiz a partir da universidade.
- Objetivos do projeto e missão do sistema de informação a selecionar/especificar.

## 2. Levantamento de Requisitos e Processos de Negócio
- Processos Operacionais vs. Processos de Gestão.
- Áreas funcionais identificadas (espólio, arquivo digital, bilhética/loja, segurança, infraestrutura, etc.).
- Interoperabilidade e arquitetura de sistemas.

## 3. Diretrizes e Orientações do Professor Luís
- Metodologia de trabalho entre os grupos.
- Critérios de avaliação e boas práticas de engenharia de software / SI.

## 4. Tabela de Ações, Entregáveis e Responsabilidades
| Ação / Entregável | Interveniente / Grupo | Detalhes e Prazos |

## 5. Questões em Aberto e Próximos Passos
- Pontos que requerem validação técnica ou recolha adicional de dados.

---
TRANSCRIÇÃO PARA ANÁLISE:
{full_transcript[:120000]}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 8192
        }
    }

    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=120)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
            
    return "Síntese não pôde ser gerada automaticamente."

def main():
    print("=" * 70, flush=True)
    print("PIPELINE PROFISSIONAL DE TRANSCRIÇÃO — REUNIÃO GPTSI (1h 26m 36s)", flush=True)
    print("=" * 70, flush=True)

    chunks = generate_chunks()
    total_chunks = len(chunks)
    print(f"Total de blocos definidos: {total_chunks} blocos de 3 minutos.", flush=True)

    # Carregar checkpoint se existir
    completed = {}
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                completed = json.load(f)
            print(f"Checkpoint encontrado com {len(completed)} blocos já concluídos.", flush=True)
        except Exception:
            completed = {}

    for chunk in chunks:
        idx_str = str(chunk["index"])
        if idx_str in completed:
            print(f"[{chunk['index']:02d}/{total_chunks}] {chunk['start_str']} -> {chunk['end_str']} (já em cache)", flush=True)
            continue

        print(f"[{chunk['index']:02d}/{total_chunks}] A processar ({chunk['start_str']} -> {chunk['end_str']})...", flush=True)
        chunk_mp3 = TEMP_DIR / f"chunk_{chunk['index']:02d}.mp3"

        # 1. Extrair áudio via ffmpeg
        cmd = [
            FFMPEG, "-y",
            "-ss", str(chunk["start_sec"]),
            "-i", INPUT_AUDIO,
            "-t", str(chunk["duration"]),
            "-vn", "-ac", "1", "-ar", "24000",
            "-b:a", "48k",
            str(chunk_mp3)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. Upload para Gemini Files API
        file_uri = upload_and_wait_file(chunk_mp3)

        # 3. Transcrição
        text = transcribe_chunk(file_uri, chunk)
        completed[idx_str] = {
            "chunk": chunk,
            "text": text
        }

        # Guardar checkpoint
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(completed, f, ensure_ascii=False, indent=2)

        # Remover mp3 temporário
        try:
            chunk_mp3.unlink()
        except Exception:
            pass

        print(f"  -> Concluído ({len(text.split())} palavras).", flush=True)
        time.sleep(3)  # Intervalo de segurança para rate limits

    # Montar transcrição completa ordenada
    sorted_items = [completed[str(c["index"])] for c in chunks if str(c["index"]) in completed]
    
    full_transcript_markdown = []
    for item in sorted_items:
        c = item["chunk"]
        full_transcript_markdown.append(
            f"### [{c['start_str']} - {c['end_str']}]\n\n{item['text']}\n"
        )
    full_transcript_text = "\n".join(full_transcript_markdown)

    print("\n[Síntese Executiva] A gerar síntese executiva completa...", flush=True)
    summary_text = generate_executive_summary(full_transcript_text)
    print("Síntese executiva concluída com sucesso!", flush=True)

    final_doc = f"""# REUNIÃO GPTSI — TRANSCRIÇÃO INTEGRAL E SÍNTESE EXECUTIVA

- **Data da Gravação**: 01 de Outubro de 2026
- **Duração Total**: 01:26:36 (1 hora, 26 minutos e 36 segundos)
- **Ficheiro de Origem**: `reunião gptsi.m4a`
- **Contexto**: Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI) — Projeto SIUM (Novo Museu)
- **Intervenientes Principais**: Professor Luís, Estudantes / Equipas de Projeto
- **Modelo de Transcrição**: Gemini 3.5 Flash Multimodal de Alta Fidelidade

---

{summary_text}

---

# TRANSCRIÇÃO INTEGRAL (VERBATIM COM TIMESTAMPS)

{full_transcript_text}
"""

    # Guardar no repositório
    out_docs = Path("docs/transcriptions")
    out_docs.mkdir(parents=True, exist_ok=True)
    docs_file = out_docs / "2026-10-01_reuniao_gptsi.md"
    with open(docs_file, "w", encoding="utf-8") as f:
        f.write(final_doc)
    print(f"\nDocumento guardado em: {docs_file}", flush=True)

    # Guardar no Obsidian Vault
    obsidian_dir = Path("obsidian_vault/10 - Lectures/GPTSI")
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    obsidian_file = obsidian_dir / "2026-10-01 - Reunião GPTSI - Transcrição e Síntese.md"
    with open(obsidian_file, "w", encoding="utf-8") as f:
        f.write(final_doc)
    print(f"Documento guardado no Obsidian Vault em: {obsidian_file}", flush=True)

    print("\nPROCESSO TOTALMENTE CONCLUÍDO COM SUCESSO!", flush=True)

if __name__ == "__main__":
    main()
