import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv(".env")
key = os.getenv("GEMINI_API_KEY")
if not key:
    print("[ERRO] GEMINI_API_KEY não encontrada no .env")
    exit(1)

mp3_path = os.path.abspath(r"data\study\audio\f76259cd5c4e9728.mp3")
if not os.path.exists(mp3_path):
    print(f"[ERRO] Ficheiro MP3 não encontrado: {mp3_path}")
    exit(1)

uri_cache_file = os.path.abspath(r"data\study\audio\gemini_file_uri.txt")
file_uri = None
if os.path.exists(uri_cache_file):
    cached_name = open(uri_cache_file, "r").read().strip()
    try:
        check_url = f"https://generativelanguage.googleapis.com/v1beta/{cached_name}?key={key}"
        status_res = requests.get(check_url).json()
        if status_res.get("state") == "ACTIVE":
            file_name = cached_name
            file_uri = status_res.get("uri")
            print(f"Reusing cached active file: {file_name}")
    except Exception:
        pass

if not file_uri:
    size = os.path.getsize(mp3_path)
    print(f"Uploading {size / (1024*1024):.1f} MB to Gemini Files API...")

    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(size),
        "X-Goog-Upload-Header-Content-Type": "audio/mp3",
        "Content-Type": "application/json",
    }
    init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={key}"
    init_res = requests.post(init_url, headers=headers, json={"file": {"display_name": "aula_investigacao_mestrado.mp3"}})
    init_res.raise_for_status()
    upload_url = init_res.headers.get("X-Goog-Upload-URL")

    with open(mp3_path, "rb") as f:
        up_res = requests.post(
            upload_url,
            headers={
                "Content-Length": str(size),
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
            },
            data=f,
        )
    up_res.raise_for_status()

    file_info = up_res.json()["file"]
    file_name = file_info["name"]
    file_uri = file_info["uri"]
    print(f"File uploaded: {file_name}, state: {file_info.get('state')}")

    for _ in range(30):
        check_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={key}"
        status_res = requests.get(check_url).json()
        if status_res.get("state") == "ACTIVE":
            print("File is ACTIVE in Gemini Files API!")
            with open(uri_cache_file, "w") as f:
                f.write(file_name)
            break
        time.sleep(2)

prompt = """És um professor e especialista em Metodologia de Investigação Científica em Sistemas e Tecnologias de Informação.
Analisa atentamente toda a gravação desta aula universitária (1h 29m) de 2º ano de mestrado.
Gera um objeto JSON estrito com o formato exato das Cornell Notes detalhadas:
{
  "topic": "<Título real e específico da aula>",
  "subject": "Metodologia de Investigação",
  "date": "2026-10-03",
  "executive_summary": "<Síntese rigorosa e profunda dos temas e discussões reais abordados na aula>",
  "cue_column": [
    {"cue": "<Pergunta ou conceito chave 1>", "idea": "<Resposta/ideia central discutida na aula>"},
    {"cue": "<Pergunta ou conceito chave 2>", "idea": "<Resposta/ideia central discutida na aula>"},
    {"cue": "<Pergunta ou conceito chave 3>", "idea": "<Resposta/ideia central discutida na aula>"},
    {"cue": "<Pergunta ou conceito chave 4>", "idea": "<Resposta/ideia central discutida na aula>"},
    {"cue": "<Pergunta ou conceito chave 5>", "idea": "<Resposta/ideia central discutida na aula>"}
  ],
  "detailed_notes": "<Texto estruturado em Markdown com subtítulos ### detalhando os conceitos, explicações, metodologia, debate com os alunos e exemplos dados pelo professor>",
  "glossary": "<Lista em markdown com termos técnicos e [[Wikilinks]] explicados, ex: - [[Termo]]: explicação>",
  "action_items": [
    "<Ação de estudo concreta recomendada 1>",
    "<Ação de estudo concreta recomendada 2>",
    "<Ação de estudo concreta recomendada 3>"
  ],
  "chapters": [
    {"title": "<Nome do capítulo>", "start_timestamp": "00:00", "summary": "<Resumo do capítulo>"}
  ]
}
Responde APENAS com o JSON válido, sem markdown codeblocks antes ou depois.
"""

models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
raw_text = None

for m in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
    payload = {
        "contents": [{
            "parts": [
                {"file_data": {"mime_type": "audio/mp3", "file_uri": file_uri}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
        },
    }
    print(f"Calling {m} for complete Cornell Notes synthesis...")
    try:
        t0 = time.time()
        res = requests.post(url, json=payload, timeout=120)
        if res.status_code == 200:
            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"Cornell Notes generated successfully with {m} in {time.time()-t0:.1f}s!")
            break
        else:
            print(f"Model {m} returned status {res.status_code}: {res.text[:200]}")
    except Exception as e:
        print(f"Error calling {m}: {e}")

if not raw_text:
    print("[ERRO] Não foi possível gerar com nenhum modelo.")
    exit(1)

out_file = os.path.abspath(r"data\study\video_cornell_notes.json")
with open(out_file, "w", encoding="utf-8") as f:
    f.write(raw_text)

print(f"Cornell Notes generated successfully in {time.time()-t0:.1f}s!")
print(f"Saved to {out_file}")
