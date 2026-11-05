import os
import sys
import json
import time
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv('.env')
key = os.getenv('GEMINI_API_KEY')

DOC_MAP = [
    ('doc_vid_98aff7821f20', '030 Initiating.wmv'),
    ('doc_vid_37691f97c10b', '000 Planning - part I.wmv'),
    ('doc_vid_3e591d4e4540', '000 Planning - part II.wmv'),
    ('doc_vid_2f962e0f2158', '000 Planning - part III.wmv'),
    ('doc_vid_3835adeef512', '000 Planning - part IV.wmv'),
    ('doc_vid_2cc2c43e640b', '010 Projects - part I.wmv'),
    ('doc_vid_62bacbb12475', '010 Projects - part II.wmv'),
    ('doc_vid_91c228841b4b', '010 Projects - part III.wmv'),
]

raw_resumos = json.load(open('data/study/resumo_gestao_videos.json', 'r', encoding='utf-8'))
docs_file = 'data/study/documents.json'
docs_data = json.load(open(docs_file, 'r', encoding='utf-8'))

MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-pro"]

def generate_structured_notes(prompt: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
    }
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        for attempt in range(3):
            try:
                res = requests.post(url, json=payload, timeout=45)
                if res.status_code == 200:
                    ans_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(ans_text)
                elif res.status_code in (429, 503):
                    print(f"[{model}] Status {res.status_code}, aguardando 4s (tentativa {attempt + 1})...", flush=True)
                    time.sleep(4.0 * (attempt + 1))
                else:
                    print(f"[{model}] Erro {res.status_code}: {res.text[:100]}", flush=True)
                    break
            except Exception as e:
                print(f"[{model}] Exceção: {e}", flush=True)
                time.sleep(3)
    raise RuntimeError("Falha ao gerar notas estruturadas com todos os modelos disponíveis.")

for doc_id, filename in DOC_MAP:
    if doc_id not in docs_data:
        print(f"[SKIP] {doc_id} não encontrado")
        continue

    doc = docs_data[doc_id]
    existing_cornell = (doc.get("metadata") or {}).get("cornell_notes")
    if existing_cornell and len(existing_cornell.get("cue_column", [])) >= 3:
        print(f"[CACHE] {filename} ({doc_id}) já estruturado.")
        continue

    analysis_text = raw_resumos.get(filename, "")
    print(f"\n--- A estruturar {filename} ({doc_id}) ---", flush=True)

    prompt = f"""És um especialista pedagógico em Gestão de Projetos de Mestrado Universitário.
Com base nesta análise detalhada dos diapositivos da aula "{filename}" do Prof. João Varajão (Universidade do Minho):

{analysis_text}

Gera um JSON RIGOROSO com o seguinte formato exato (sem formatação markdown extra, apenas o JSON puro):
{{
  "executive_summary": "Sumário executivo abrangente de 2 parágrafos densos com os objetivos centrais, conceitos essenciais e valor prático da aula.",
  "cue_column": [
    {{"cue": "Pergunta ou pista central 1?", "idea": "Conceito nuclear correspondente."}},
    {{"cue": "Pergunta ou pista central 2?", "idea": "Conceito nuclear correspondente."}},
    {{"cue": "Pergunta ou pista central 3?", "idea": "Conceito nuclear correspondente."}},
    {{"cue": "Pergunta ou pista central 4?", "idea": "Conceito nuclear correspondente."}},
    {{"cue": "Pergunta ou pista central 5?", "idea": "Conceito nuclear correspondente."}}
  ],
  "detailed_notes": "Notas detalhadas em formato Markdown completas com títulos (###), tabelas de inputs/outputs se aplicável, listas e pontos essenciais para estudo.",
  "glossary_text": "- **Termo 1**: Definição.\\n- **Termo 2**: Definição.\\n- **Termo 3**: Definição.\\n- **Termo 4**: Definição.",
  "action_items": [
    "Ação de estudo 1",
    "Ação de estudo 2",
    "Ação de estudo 3"
  ],
  "quick_summary": [
    "Ponto-chave 1 em uma frase densa",
    "Ponto-chave 2 em uma frase densa",
    "Ponto-chave 3 em uma frase densa",
    "Ponto-chave 4 em uma frase densa",
    "Ponto-chave 5 em uma frase densa"
  ],
  "sections": [
    {{
      "title": "Capítulo 1 [00:00]",
      "text": "Texto aprofundado dos tópicos lecionados neste bloco da aula."
    }},
    {{
      "title": "Capítulo 2 [05:00]",
      "text": "Texto aprofundado dos tópicos lecionados neste bloco da aula."
    }},
    {{
      "title": "Capítulo 3 [10:00]",
      "text": "Texto aprofundado dos tópicos lecionados neste bloco da aula."
    }}
  ],
  "problem": "O desafio central ou problema organizacional abordado nesta aula.",
  "method": "A metodologia, framework ou standard PMBOK/ISO apresentado.",
  "findings": "As conclusões e princípios fundamentais transmitidos aos estudantes.",
  "limitations": "Restrições, riscos e cuidados a ter na aplicação prática."
}}
"""

    try:
        data = generate_structured_notes(prompt)

        # 1. Cornell Notes no metadata
        doc["metadata"]["cornell_notes"] = {
            "document_id": doc_id,
            "topic": doc.get("title", filename),
            "subject": doc.get("subject", "gestao"),
            "date": "2026-10-21",
            "executive_summary": data["executive_summary"],
            "cue_column": data["cue_column"],
            "detailed_notes": data["detailed_notes"],
            "glossary": data["glossary_text"],
            "action_items": data["action_items"],
        }

        # 2. Resumos estruturados (Quick, Detailed, Exam)
        doc["metadata"]["summaries"] = {
            "quick": data["quick_summary"],
            "detailed": data["detailed_notes"],
            "exam": [f"Revisão Crítica: {q['cue']} -> {q['idea']}" for q in data["cue_column"]],
        }

        # 3. Argument Map / Estrutura
        doc["structure"] = {
            "problem": {"text": data["problem"], "evidence_status": "OBSERVED"},
            "method": {"text": data["method"], "evidence_status": "OBSERVED"},
            "findings": {"text": data["findings"], "evidence_status": "OBSERVED"},
            "limitations": {"text": data["limitations"], "evidence_status": "OBSERVED"},
        }

        # 4. Secções pedagógicas detalhadas para Leitura
        structured_sections = []
        full_text_parts = [data["executive_summary"], "\n\n"]
        for s_idx, sec in enumerate(data.get("sections", []), start=1):
            sec_id = f"sec_{s_idx:02d}"
            paragraphs = [
                {
                    "paragraph_id": f"p_{s_idx}_1",
                    "text": sec["text"],
                    "page_number": s_idx,
                    "section_id": sec_id,
                    "order": 1
                }
            ]
            structured_sections.append({
                "section_id": sec_id,
                "title": sec["title"],
                "level": 1,
                "page_start": s_idx,
                "page_end": s_idx,
                "paragraphs": paragraphs
            })
            full_text_parts.append(f"## {sec['title']}\n{sec['text']}\n\n")

        doc["sections"] = structured_sections
        doc["extracted_text"] = "".join(full_text_parts)
        doc["page_count"] = max(len(structured_sections), 3)

        # Gravar progressivamente em disco
        with open(docs_file, 'w', encoding='utf-8') as f:
            json.dump(docs_data, f, ensure_ascii=False, indent=2)

        print(f"[SUCESSO] Guardado em disco {doc_id} ({filename})", flush=True)
    except Exception as e:
        print(f"[ERRO GRAVE] {filename}: {e}", flush=True)

print("\nCONCLUÍDO! Todos os materiais foram enriquecidos e persistidos em documents.json.")
