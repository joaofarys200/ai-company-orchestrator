import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(".env")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    print("[ERRO] GEMINI_API_KEY não encontrada no .env", flush=True)
    sys.exit(1)

TRANSCRIPT_PATH = Path("docs/transcriptions/2026-10-03_aula_metodologia_investigacao.md")
DOCS_PATH = Path("data/study/documents.json")
OBSIDIAN_DIR = Path("obsidian_vault/10 - Lectures/Metodologia de Investigacao")

def call_gemini_json(prompt: str) -> dict:
    models = ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-1.5-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json"
        }
    }

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        for attempt in range(3):
            try:
                res = requests.post(url, json=payload, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            text = parts[0]["text"].strip()
                            if text.startswith("```json"):
                                text = text[7:]
                            if text.startswith("```"):
                                text = text[3:]
                            if text.endswith("```"):
                                text = text[:-3]
                            return json.loads(text.strip())
                elif res.status_code in [429, 503]:
                    time.sleep(3)
                else:
                    time.sleep(1.5)
            except Exception as e:
                print(f"Erro na tentativa {attempt+1} com {model_name}: {e}")
                time.sleep(2)
    raise RuntimeError("Falha ao chamar API Gemini")

def main():
    print("[1] A ler transcrição integral...")
    with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    # Chamada 1: Resumos e Mapa de Argumentos
    prompt1 = f"""
És um especialista em Metodologia de Investigação Científica e docente universitário.
Abaixo está a transcrição integral de uma aula de 1h29m analisando o artigo "Predicting the Performance of Online Consumer Reviews".
Gera um JSON válido com os seguintes campos:

{{
  "quick_summary": [
    "Ponto 1...",
    "Ponto 2...",
    "Ponto 3...",
    "Ponto 4...",
    "Ponto 5..."
  ],
  "detailed_summary": [
    {{
      "title": "1. Contextualização e Perguntas de Investigação (RQ1 e RQ2)",
      "text": "Detalhes..."
    }},
    {{
      "title": "2. Modelo de Investigação e Variáveis",
      "text": "Detalhes..."
    }},
    {{
      "title": "3. Classificação Epistemológica e Tipologia de Gregor",
      "text": "Detalhes..."
    }},
    {{
      "title": "4. Racional Hipotético-Dedutivo e Falsificabilidade (Feynman)",
      "text": "Detalhes..."
    }},
    {{
      "title": "5. Método Observacional e Dados Secundários vs Rastos Digitais",
      "text": "Detalhes..."
    }},
    {{
      "title": "6. Ferramentas Analíticas e Questões Éticas/Privacidade",
      "text": "Detalhes..."
    }}
  ],
  "exam_summary": {{
    "high_yield_concepts": [
      {{
        "concept": "Conceito 1",
        "detail": "Explicação..."
      }},
      {{
        "concept": "Conceito 2",
        "detail": "Explicação..."
      }},
      {{
        "concept": "Conceito 3",
        "detail": "Explicação..."
      }},
      {{
        "concept": "Conceito 4",
        "detail": "Explicação..."
      }}
    ],
    "likely_questions": [
      {{
        "question": "Pergunta 1",
        "answer": "Resposta esperada..."
      }},
      {{
        "question": "Pergunta 2",
        "answer": "Resposta esperada..."
      }},
      {{
        "question": "Pergunta 3",
        "answer": "Resposta esperada..."
      }}
    ],
    "key_definitions": [
      {{
        "term": "Termo 1",
        "def": "Definição..."
      }},
      {{
        "term": "Termo 2",
        "def": "Definição..."
      }},
      {{
        "term": "Termo 3",
        "def": "Definição..."
      }},
      {{
        "term": "Termo 4",
        "def": "Definição..."
      }}
    ]
  }},
  "argument_map": {{
    "problem": {{ "text": "Volume, variedade, velocidade e veracidade das reviews online que dificultam a sua análise pelos consumidores e empresas.", "status": "OBSERVED", "page_ref": 1 }},
    "research_gap": {{ "text": "Falta de compreensão dos determinantes da leitura (readership) e impacto do sentimento do texto na utilidade (helpfulness).", "status": "OBSERVED", "page_ref": 1 }},
    "research_question": {{ "text": "RQ1: Que fatores determinam a probabilidade de um consumidor ler uma review? RQ2: Que fatores determinam a utilidade percebida da review?", "status": "OBSERVED", "page_ref": 1 }},
    "hypothesis": {{ "text": "Relação entre características das reviews (tamanho, longevidade, sentimento do título/texto) e as variáveis de performance (readership e helpfulness).", "status": "OBSERVED", "page_ref": 2 }},
    "contribution": {{ "text": "Modelo preditivo da performance de reviews baseado em text mining e sentiment analysis para big data.", "status": "OBSERVED", "page_ref": 2 }},
    "method": {{ "text": "Estudo de campo observacional baseado em rastos informacionais de compras e avaliações na Amazon (sem intervenção de laboratório).", "status": "OBSERVED", "page_ref": 3 }},
    "dataset": {{ "text": "Dados secundários de 35 reviews de 20 produtos recolhidos na Amazon via crawler automatizado.", "status": "OBSERVED", "page_ref": 3 }},
    "experiment": {{ "text": "Análise de sentimentos usando SentiStrength e regressões estatísticas para validação de hipóteses.", "status": "OBSERVED", "page_ref": 4 }},
    "results": {{ "text": "Longevidade e tamanho afetam readership e helpfulness; sentimento positivo do título afeta readership quando combinado com texto; certas hipóteses diretas foram rejeitadas.", "status": "OBSERVED", "page_ref": 6 }},
    "limitations": {{ "text": "Dados restritos à Amazon; análise de sentimento limitada pela ferramenta; natureza observacional não prova causalidade direta.", "status": "OBSERVED", "page_ref": 8 }},
    "conclusion": {{ "text": "Classificada como investigação básica confirmatória com teoria predominantemente preditiva segundo a taxonomia de Gregor.", "status": "OBSERVED", "page_ref": 9 }}
  }}
}}

Apenas JSON válido.
TRANSCRIÇÃO:
{transcript_text[:40000]}
"""

    print("[2] Gerando resumos e mapa de argumentos...")
    data1 = call_gemini_json(prompt1)

    # Chamada 2: Capítulos e Cornell Notes
    prompt2 = f"""
És um especialista em Metodologia de Investigação Científica.
Com base na transcrição da aula de 1h29m (dividida em blocos de 4 minutos), gera um JSON com os seguintes campos:
{{
  "chapters": [
    {{
      "title": "Título do capítulo com base no conteúdo real",
      "start_time": 0,
      "start_timestamp": "00:00",
      "end_time": 240,
      "end_timestamp": "04:00",
      "summary": "Resumo do que foi discutido neste intervalo",
      "key_concepts": ["Conceito 1", "Conceito 2"]
    }}
  ],
  "cornell_notes": {{
    "topic": "Análise Metodológica: Predicting the Performance of Online Consumer Reviews",
    "subject": "Metodologia de Investigação Científica",
    "date": "2026-10-03",
    "executive_summary": "Resumo executivo completo e detalhado da aula...",
    "cue_column": [
      {{ "cue": "Pergunta ou conceito de estudo", "idea": "Resposta detalhada" }}
    ],
    "detailed_notes": "Notas detalhadas da aula divididas por secções em Markdown...",
    "glossary": "- [[Conceito 1]]: Definição...\\n- [[Conceito 2]]: Definição...",
    "action_items": [
      "Item 1",
      "Item 2"
    ]
  }}
}}

Gera entre 10 e 15 capítulos cronológicos cobrindo toda a duração (00:00 até 01:29:15).
Apenas JSON válido.
TRANSCRIÇÃO:
{transcript_text}
"""

    print("[3] Gerando capítulos e Notas Cornell...")
    data2 = call_gemini_json(prompt2)

    print("[4] Atualizando documents.json...")
    with open(DOCS_PATH, "r", encoding="utf-8") as f:
        docs_data = json.load(f)

    vdoc = docs_data.get("doc_vid_f76259cd5c4e")
    if vdoc:
        vdoc["structure"] = data1.get("argument_map", vdoc.get("structure"))
        if "metadata" not in vdoc:
            vdoc["metadata"] = {}
        vdoc["metadata"]["summaries"] = {
            "quick": data1.get("quick_summary", []),
            "detailed": data1.get("detailed_summary", []),
            "exam": data1.get("exam_summary", {})
        }
        vdoc["metadata"]["summary"] = data2.get("cornell_notes", {}).get("executive_summary", "")
        vdoc["metadata"]["cornell_notes"] = data2.get("cornell_notes", {})

        if "video" in vdoc["metadata"]:
            vdoc["metadata"]["video"]["chapters"] = data2.get("chapters", [])

        # Glossário
        if "key_definitions" in data1.get("exam_summary", {}):
            glossary_items = []
            for kd in data1["exam_summary"]["key_definitions"]:
                glossary_items.append({
                    "term": kd.get("term", ""),
                    "translation": kd.get("term", ""),
                    "explanation": kd.get("def", ""),
                    "first_occurrence": "Aula",
                    "occurrences": 1,
                    "importance": "HIGH"
                })
            vdoc["glossary"] = glossary_items

        with open(DOCS_PATH, "w", encoding="utf-8") as f:
            json.dump(docs_data, f, ensure_ascii=False, indent=2)
        print("[SUCESSO] documents.json atualizado!")

    # Guardar Notas Cornell no Obsidian Vault
    c_notes = data2.get("cornell_notes", {})
    cornell_md = f"""# {c_notes.get('topic', 'Aula de Metodologia')}
**Unidade Curricular:** {c_notes.get('subject', 'Metodologia de Investigação')}  
**Data:** {c_notes.get('date', '2026-10-03')}  
**Gravação:** `video1845185762.mp4`  

## 📌 Sumário Executivo
{c_notes.get('executive_summary', '')}

---

## 💡 Notas e Perguntas-Chave (Cue Column)
| Pergunta / Conceito | Resposta / Ideia Central |
| :--- | :--- |
"""
    for item in c_notes.get('cue_column', []):
        cue = item.get('cue', '')
        idea = item.get('idea', '')
        cornell_md += f"| **{cue}** | {idea} |\n"

    cornell_md += f"""
---

## 📝 Notas Detalhadas da Sessão
{c_notes.get('detailed_notes', '')}

---

## 📖 Glossário de Conceitos
{c_notes.get('glossary', '')}

---

## 🎯 Tarefas e Ações Recomendadas
"""
    for act in c_notes.get('action_items', []):
        cornell_md += f"- [ ] {act}\n"

    OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)
    cornell_file = OBSIDIAN_DIR / "2026-10-03 - Predicting the Performance of Online Consumer Reviews - Notas Cornell.md"
    with open(cornell_file, "w", encoding="utf-8") as f:
        f.write(cornell_md)
    print(f"[SUCESSO] Notas Cornell gravadas no Obsidian: {cornell_file}")

if __name__ == "__main__":
    main()
