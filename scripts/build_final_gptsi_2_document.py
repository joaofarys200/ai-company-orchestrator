import json
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")
key = os.getenv("GEMINI_API_KEY")

checkpoint_file = Path("temp_transcription_gptsi_2/transcription_checkpoint.json")
with open(checkpoint_file, "r", encoding="utf-8") as f:
    completed = json.load(f)

# Reassemble verbatim transcript
chunks_order = [str(i) for i in range(1, 13)]
transcript_parts = []
for c_idx in chunks_order:
    item = completed[c_idx]
    c = item["chunk"]
    transcript_parts.append(f"### [{c['start_str']} - {c['end_str']}]\n\n{item['text']}\n")

full_transcript_text = "\n".join(transcript_parts)

# Generate executive summary with gemini-2.5-flash
prompt = f"""Atua como Secretário Técnico e Consultor Sénior de Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI).
Com base na transcrição integral da Reunião 2 de 22/10/2026 entre o Professor Luís e os alunos (sobre o projeto SIUM - Sistema de Informação do Novo Museu), elabora uma Síntese Executiva abrangente, detalhada, técnica e de elevado rigor.

IMPORTANTE:
- Integra os esclarecimentos cruciais dos grupos:
  * Grupo 1 / Definição formal: Projeto de SI com finalidade de conceber, desenvolver e implementar sistema integrado; arquiteturas (dados, tecnológica, segurança, integração, informação);
  * Grupo 2 / Framework & Orçamento: Utilização do TOGAF para arquitetura corporativa; se o orçamento (200.000) não chegar, a ordem de corte dita que a LOJA é a primeira a ser cortada em caso extremo;
  * Grupo 3 / Equipamentos: Não há nada a reutilizar, criação é 100% de raiz;
  * Grupo 4 / Requisitos e Aplicações: Gestão de Coleções (inventário, catalogação, localização, conservação/restauro); Bilhética/Vendas (vendas online e presenciais, reservas, pagamentos eletrónicos, bilhetes digitais, estatísticas);
  * Migração de dados legados (Excel) com margem de erro controlada;
  * SIUM como website e fonte de dados; comunicação do projeto.

Estrutura OBRIGATÓRIA:
# SÍNTESE EXECUTIVA — REUNIÃO 2 GPTSI (22/10/2026)

## 1. Contexto, Objetivos e Evolução da Reunião 2
## 2. Conceção, Escopo e Alinhamento Estratégico
## 3. Requisitos, Arquitetura e Modelagem do SIUM (incluindo TOGAF)
## 4. Orientações Metodológicas e Práticas do Professor Luís (Orçamento, Reutilização, Cortes)
## 5. Tabela Síntese de Decisões, Ações e Entregáveis
(Formata a tabela Markdown de forma limpa, com linhas concisas e colunas bem alinhadas)
## 6. Pontos Críticos, Questões em Aberto e Próximos Passos

---
TRANSCRIÇÃO INTEGRAL:
{full_transcript_text}"""

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
}
res = requests.post(url, json=payload, timeout=120)
summary_text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

final_doc = f"""# REUNIÃO 2 GPTSI — TRANSCRIÇÃO INTEGRAL E SÍNTESE EXECUTIVA

- **Data da Gravação**: 22 de Outubro de 2026
- **Duração Total**: 00:33:39 (33 minutos e 39 segundos)
- **Ficheiro de Origem**: `reunião gptsi 2.m4a`
- **Unidade Curricular**: Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI)
- **Projeto em Análise**: SIUM — Sistema de Informação para o Novo Museu (Reunião 2: Requisitos, Arquitetura & Diretrizes)
- **Intervenientes Principais**: Professor Luís, Estudantes / Grupos de Trabalho (Grupo 1, Grupo 2, Grupo 3, Grupo 4)
- **Motor de Transcrição**: Gemini 2.5 Flash Multimodal com Verificação Acústica e Timestamps Absolutos

---

{summary_text}

---

# TRANSCRIÇÃO INTEGRAL (VERBATIM COM TIMESTAMPS)

{full_transcript_text}
"""

docs_file = Path("docs/transcriptions/2026-10-22_reuniao_gptsi_2.md")
with open(docs_file, "w", encoding="utf-8") as f:
    f.write(final_doc)

obsidian_file = Path("obsidian_vault/10 - Lectures/GPTSI/2026-10-22 - Reunião GPTSI 2 - Transcrição e Síntese.md")
with open(obsidian_file, "w", encoding="utf-8") as f:
    f.write(final_doc)

print("Successfully re-generated and updated both files!")
print("File size:", os.path.getsize(docs_file), "bytes")
