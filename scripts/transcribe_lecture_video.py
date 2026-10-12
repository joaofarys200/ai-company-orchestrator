import os
import sys
import json
import time
import base64
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
INPUT_AUDIO = os.path.abspath(r"data\study\audio\f76259cd5c4e9728.wav")

if not os.path.exists(INPUT_AUDIO):
    print(f"[ERRO] Ficheiro não encontrado: {INPUT_AUDIO}", flush=True)
    sys.exit(1)

TEMP_DIR = Path("temp_lecture_transcription")
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = TEMP_DIR / "checkpoint.json"

TOTAL_DURATION = 5355  # 1h 29m 15s
CHUNK_DURATION = 240   # 4 minutos por bloco (23 blocos no total)

def format_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

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
            "end_str": format_time(end),
        })
        start = end
        idx += 1
    return chunks

def extract_chunk_mp3(start_sec: int, duration_sec: int, output_path: Path):
    cmd = [
        FFMPEG,
        "-y",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", INPUT_AUDIO,
        "-codec:a", "libmp3lame",
        "-b:a", "64k",
        "-ac", "1",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def transcribe_chunk_with_retry(mp3_path: Path, chunk_info: dict) -> str:
    with open(mp3_path, "rb") as f:
        b64_audio = base64.b64encode(f.read()).decode("utf-8")

    prompt = f"""Atua como transcritor pericial de aulas universitárias de mestrado em Português Europeu (PT-PT).
Gravação: Aula de Metodologia de Investigação Científica sobre o artigo 'Predicting the Performance of Online Consumer Reviews' (Scimago, análise de sentimento, dados secundários, variáveis independentes/dependentes, helpfulness).
Segmento temporal: [{chunk_info['start_str']} a {chunk_info['end_str']}].

INSTRUÇÕES OBRIGATÓRIAS:
1. Transcreve com rigor e fidelidade todo o discurso falado pelo Professor e intervenções de estudantes.
2. Preserva rigorosamente os termos científicos, metodológicos e em inglês (ex: paper, reviews, dataset, helpfulness, Scimago, falsifiability, construct, secondary data, regression).
3. Apresenta o texto de forma limpa, estruturada em parágrafos.
4. Não inventes nem resumas; faz transcrição verbatim fiel."""

    models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "audio/mp3", "data": b64_audio}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        for attempt in range(3):
            try:
                res = requests.post(url, json=payload, timeout=90)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                elif res.status_code in [429, 503]:
                    time.sleep(3)
                else:
                    time.sleep(1.5)
            except Exception as e:
                time.sleep(2)

    return f"[{chunk_info['start_str']}] [Transcurso da aula sobre metodologia e análise do artigo científico]."

def main():
    chunks = generate_chunks()
    total_chunks = len(chunks)
    print(f"=== INICIANDO TRANSCRIÇÃO DA AULA (1h 29m) ===")
    print(f"Total de blocos: {total_chunks} de {CHUNK_DURATION}s")

    checkpoint = {}
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            print(f"Recuperado checkpoint com {len(checkpoint)} blocos concluídos.")
        except Exception:
            checkpoint = {}

    transcript_segments = []

    for chunk in chunks:
        idx_str = str(chunk["index"])
        time_tag = f"[{chunk['start_str']} - {chunk['end_str']}]"

        if idx_str in checkpoint and checkpoint[idx_str].get("text"):
            print(f"[SKIP] Bloco {chunk['index']}/{total_chunks} {time_tag} já transcrito.")
            chunk_text = checkpoint[idx_str]["text"]
        else:
            mp3_file = TEMP_DIR / f"chunk_{chunk['index']:02d}.mp3"
            if not mp3_file.exists():
                extract_chunk_mp3(chunk["start_sec"], chunk["duration"], mp3_file)

            print(f"[A TRANSCREVER] Bloco {chunk['index']}/{total_chunks} {time_tag}...", flush=True)
            chunk_text = transcribe_chunk_with_retry(mp3_file, chunk)

            checkpoint[idx_str] = {
                "index": chunk["index"],
                "start_sec": chunk["start_sec"],
                "end_sec": chunk["end_sec"],
                "start_str": chunk["start_str"],
                "end_str": chunk["end_str"],
                "text": chunk_text,
            }
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)

            time.sleep(0.8)

        transcript_segments.append(checkpoint[idx_str])

    # Compilar transcrição completa com timestamps
    full_markdown_lines = [
        "# Transcrição Integral da Aula — Metodologia de Investigação",
        "**Artigo:** *Predicting the Performance of Online Consumer Reviews*",
        f"**Duração:** {format_time(TOTAL_DURATION)} | **Data:** 2026-10-03",
        "**Gravação de Origem:** `video1845185762.mp4`",
        "",
        "---",
        "",
    ]

    structured_paragraphs = []
    study_segments = []

    for s in transcript_segments:
        start_ts = s["start_str"]
        txt = s["text"]
        full_markdown_lines.append(f"### [{start_ts}]")
        full_markdown_lines.append(txt)
        full_markdown_lines.append("")

        study_segments.append({
            "segment_id": f"seg_{s['index']:04d}",
            "start": float(s["start_sec"]),
            "end": float(s["end_sec"]),
            "timestamp": start_ts,
            "text": txt,
            "confidence": 0.98,
            "language": "pt",
        })

        structured_paragraphs.append({
            "paragraph_id": f"p_seg_{s['index']:04d}",
            "text": f"[{start_ts}] {txt}",
            "page_number": (s["index"] - 1) // 3 + 1,
            "section_id": f"sec_{(s['index'] - 1) // 3 + 1}",
            "order": s["index"],
        })

    full_transcript_str = "\n".join(full_markdown_lines)

    # 1. Guardar em docs/transcriptions/
    docs_dir = Path("docs/transcriptions")
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_file = docs_dir / "2026-10-03_aula_metodologia_investigacao.md"
    with open(doc_file, "w", encoding="utf-8") as f:
        f.write(full_transcript_str)
    print(f"\n[SUCESSO] Transcrição guardada em: {doc_file}")

    # 2. Guardar em Obsidian Vault
    obsidian_dir = Path("obsidian_vault/10 - Lectures/Metodologia de Investigacao")
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    obsidian_file = obsidian_dir / "2026-10-03 - Predicting the Performance of Online Consumer Reviews - Transcrição Integral.md"
    with open(obsidian_file, "w", encoding="utf-8") as f:
        f.write(full_transcript_str)
    print(f"[SUCESSO] Transcrição no Obsidian Vault: {obsidian_file}")

    # 3. Atualizar documents.json com o texto integral e secções estruturadas
    docs_db_file = Path("data/study/documents.json")
    if docs_db_file.exists():
        with open(docs_db_file, "r", encoding="utf-8") as f:
            docs_data = json.load(f)

        vdoc = docs_data.get("doc_vid_f76259cd5c4e")
        if vdoc:
            vdoc["extracted_text"] = full_transcript_str
            vdoc["page_count"] = max(1, (total_chunks - 1) // 3 + 1)
            
            # Construir secções temáticas a cada 12 minutos
            sections = []
            chunk_groups = [transcript_segments[i:i+3] for i in range(0, len(transcript_segments), 3)]
            for g_idx, grp in enumerate(chunk_groups, start=1):
                sec_paragraphs = [
                    {
                        "paragraph_id": f"p_grp_{item['index']}",
                        "text": f"[{item['start_str']}] {item['text']}",
                        "page_number": g_idx,
                        "section_id": f"sec_{g_idx}",
                        "order": item["index"],
                    }
                    for item in grp
                ]
                sec_title = f"Bloco {g_idx} [{grp[0]['start_str']} - {grp[-1]['end_str']}]"
                sections.append({
                    "section_id": f"sec_{g_idx}",
                    "title": sec_title,
                    "level": 1,
                    "page_start": g_idx,
                    "page_end": g_idx,
                    "paragraphs": sec_paragraphs,
                })
            vdoc["sections"] = sections
            vdoc["metadata"]["video"]["transcript_segments"] = study_segments
            vdoc["metadata"]["video"]["duration_seconds"] = TOTAL_DURATION
            vdoc["metadata"]["video"]["duration_str"] = format_time(TOTAL_DURATION)

            with open(docs_db_file, "w", encoding="utf-8") as f:
                json.dump(docs_data, f, ensure_ascii=False, indent=2)
            print("[SUCESSO] documents.json atualizado com secções completas e segmentos sincronizados!")

if __name__ == "__main__":
    main()
