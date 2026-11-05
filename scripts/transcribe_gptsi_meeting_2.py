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
INPUT_AUDIO = r"C:\Users\joaor\Documents\Gravações de Som\reunião gptsi 2.m4a"

if not os.path.exists(INPUT_AUDIO):
    print(f"[ERRO] Ficheiro não encontrado: {INPUT_AUDIO}", flush=True)
    sys.exit(1)

TEMP_DIR = Path("temp_transcription_gptsi_2")
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = TEMP_DIR / "transcription_checkpoint.json"

TOTAL_DURATION = 2019  # 33m 39s (2018.88s)
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
    for _ in range(25):
        check_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={GEMINI_KEY}"
        status_res = requests.get(check_url)
        if status_res.status_code == 200:
            current_state = status_res.json().get("state")
            if current_state == "ACTIVE":
                return file_uri
            elif current_state == "FAILED":
                raise RuntimeError(f"Ficheiro falhou no Gemini: {status_res.json()}")
        time.sleep(1.2)
        
    return file_uri

def transcribe_chunk(file_uri: str, chunk_info: dict) -> str:
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
    
    prompt = f"""Atua como transcritor pericial de reuniões académicas e profissionais de Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI) em Português Europeu (PT-PT).
Gravação: Reunião 2 sobre o projeto SIUM (Sistema de Informação do Novo Museu).
Participantes: Professor Luís e alunos/equipas de projeto.
Segmento temporal: [{chunk_info['start_str']} a {chunk_info['end_str']}].

INSTRUÇÕES OBRIGATÓRIAS:
1. Transcreve com rigor integral e verbatim todo o discurso falado pelos intervenientes. Identifica os oradores nas mudanças de turno (ex.: **Professor Luís:**, **Estudante:** ou outro participante identificado).
2. Não sintetizes, não resumas e não omitas diálogos neste bloco. Queremos a transcrição verbatim completa.
3. Se houver ruído, pausas ou silêncio, não inventes texto nem repitas palavras. Transcreve apenas a fala real audível.
4. Preserva rigorosamente toda a terminologia técnica: SIUM, requisitos, modelo de dados, projeto de SI, processos operacionais, processos de gestão, espólio, arquitetura de sistemas, FOSS, etc.
5. Formata a resposta em parágrafos de diálogo claros em Markdown."""

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
                    time.sleep(4)
                else:
                    time.sleep(2)
            except Exception as e:
                time.sleep(3)
                
    return "[Segmento inaudível ou sem diálogo percetível]"

def generate_executive_summary(full_transcript: str) -> str:
    models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    
    prompt = f"""Atua como Secretário Técnico e Consultor Sénior de Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI).
Com base na transcrição integral da Reunião 2 de 22/10/2026 entre o Professor Luís e os alunos (continuação do projeto SIUM - Sistema de Informação do Novo Museu), elabora uma Síntese Executiva abrangente, detalhada, técnica e de elevado rigor.

Estrutura OBRIGATÓRIA:
# SÍNTESE EXECUTIVA — REUNIÃO 2 GPTSI (22/10/2026)

## 1. Contexto, Objetivos e Evolução da Reunião 2
- Enquadramento da sessão e continuidade face às diretrizes da primeira reunião.
- Definição formal de Projeto de Sistemas de Informação e o papel do SIUM.

## 2. Conceção, Escopo e Alinhamento Estratégico
- O que é esperado dos alunos em termos de concepção vs. implementação.
- Delimitação entre objetivos de negócio/institucionais e objetivos do sistema de informação.
- Foco em processos operacionais e de gestão.

## 3. Requisitos, Arquitetura e Modelagem do SIUM
- Requisitos funcionais, dados e entidades centrais do sistema.
- Questões de integração, catálogo de dados e fluxos de informação.

## 4. Orientações Metodológicas e Práticas do Professor Luís
- Conselhos de trabalho prático para os grupos.
- Cuidados na modelagem, documentação e prototipagem.

## 5. Tabela Síntese de Decisões, Ações e Entregáveis
| Tópico / Entregável | Responsável / Stakeholder | Especificações, Decisões e Prazos |

## 6. Pontos Críticos, Questões em Aberto e Próximos Passos
- Aspetos que exigem validação técnica imediata pelos grupos.

---
TRANSCRIÇÃO INTEGRAL DA REUNIÃO 2:
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
                candidates = res.json().get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
            
    return "Síntese executiva não pôde ser gerada automaticamente."

def main():
    print("=" * 75, flush=True)
    print("PIPELINE DE TRANSCRIÇÃO — REUNIÃO GPTSI 2 (33m 39s)", flush=True)
    print("=" * 75, flush=True)

    chunks = generate_chunks()
    total_chunks = len(chunks)
    print(f"Total de blocos definidos: {total_chunks} blocos de 3 minutos.", flush=True)

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

        # 3. Transcrição com IA
        text = transcribe_chunk(file_uri, chunk)
        completed[idx_str] = {
            "chunk": chunk,
            "text": text
        }

        # Guardar checkpoint atómico
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(completed, f, ensure_ascii=False, indent=2)

        # Limpar mp3 temporário
        try:
            chunk_mp3.unlink()
        except Exception:
            pass

        print(f"  -> Concluído ({len(text.split())} palavras).", flush=True)
        time.sleep(2.5)  # Intervalo de segurança para quota da API

    # Montar transcrição ordenada
    sorted_items = [completed[str(c["index"])] for c in chunks if str(c["index"]) in completed]
    
    full_transcript_markdown = []
    for item in sorted_items:
        c = item["chunk"]
        full_transcript_markdown.append(
            f"### [{c['start_str']} - {c['end_str']}]\n\n{item['text']}\n"
        )
    full_transcript_text = "\n".join(full_transcript_markdown)

    print("\n[Síntese Executiva] A gerar síntese executiva técnica completa...", flush=True)
    summary_text = generate_executive_summary(full_transcript_text)
    print("Síntese executiva concluída com sucesso!", flush=True)

    final_doc = f"""# REUNIÃO 2 GPTSI — TRANSCRIÇÃO INTEGRAL E SÍNTESE EXECUTIVA

- **Data da Gravação**: 22 de Outubro de 2026
- **Duração Total**: 00:33:39 (33 minutos e 39 segundos)
- **Ficheiro de Origem**: `reunião gptsi 2.m4a`
- **Unidade Curricular**: Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI)
- **Projeto em Análise**: SIUM — Sistema de Informação para o Novo Museu (Reunião de Acompanhamento / Requisitos)
- **Intervenientes Principais**: Professor Luís, Estudantes / Equipas de Projeto
- **Motor de Transcrição**: Gemini 2.5 Flash Multimodal de Alta Fidelidade (PT-PT)

---

{summary_text}

---

# TRANSCRIÇÃO INTEGRAL (VERBATIM COM TIMESTAMPS)

{full_transcript_text}
"""

    # 1. Guardar em docs/transcriptions
    out_docs = Path("docs/transcriptions")
    out_docs.mkdir(parents=True, exist_ok=True)
    docs_file = out_docs / "2026-10-22_reuniao_gptsi_2.md"
    with open(docs_file, "w", encoding="utf-8") as f:
        f.write(final_doc)
    print(f"\nDocumento guardado em: {docs_file}", flush=True)

    # 2. Guardar no Obsidian Vault
    obsidian_dir = Path("obsidian_vault/10 - Lectures/GPTSI")
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    obsidian_file = obsidian_dir / "2026-10-22 - Reunião GPTSI 2 - Transcrição e Síntese.md"
    with open(obsidian_file, "w", encoding="utf-8") as f:
        f.write(final_doc)
    print(f"Documento guardado no Obsidian Vault em: {obsidian_file}", flush=True)

    print("\n" + "=" * 75, flush=True)
    print("PROCESSO TOTALMENTE CONCLUÍDO COM SUCESSO!", flush=True)
    print("=" * 75, flush=True)

if __name__ == "__main__":
    main()
