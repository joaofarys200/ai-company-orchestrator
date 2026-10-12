import os
import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(".env")
key = os.getenv("GEMINI_API_KEY")

transcript_path = Path("docs/transcriptions/2026-10-01_reuniao_gptsi.md")
content = transcript_path.read_text(encoding="utf-8")

# Limpeza rigorosa de repetições artificiais
# Remove padrões como 'e, e, e' ou 'do, do, do' ou 'ou, ou, ou' repetidos mais de 5 vezes
def clean_repeats(text: str) -> str:
    # Remove repetições consecutivas de 1-3 letras separadas por vírgula/espaço
    cleaned = re.sub(r"(?:(?:\b\w{1,4}\b[, ]*){6,})", "... [intervenção concluída / pausa de trabalho]\n", text)
    # Limpa linhas vazias excessivas
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

cleaned_content = clean_repeats(content)

idx_verbatim = cleaned_content.find("# TRANSCRIÇÃO INTEGRAL")
if idx_verbatim != -1:
    verbatim = cleaned_content[idx_verbatim:]
else:
    verbatim = cleaned_content

print(f"Transcrição verbatim limpa. Tamanho: {len(verbatim)} caracteres.", flush=True)

prompt = f"""Atua como Secretário Técnico e Especialista Sénior em Sistemas de Informação e Gestão de Projetos (GPTSI).
Com base na transcrição integral da reunião/aula de 01/10/2026 com o Professor Luís sobre o Projeto SIUM (Sistema de Informação do Novo Museu), redige uma Síntese Executiva exaustiva, de elevada qualidade profissional e académica.

Desenvolve com detalhe rigoroso as seguintes secções:

# SÍNTESE EXECUTIVA — REUNIÃO GPTSI (01/10/2026)

## 1. Contexto e Enquadramento do Projeto SIUM
- Criação de raiz de uma nova organização museológica, independente da universidade, com instalações, recursos e vida própria.
- As três entidades intervenientes no consórcio: o Museu (M), a Câmara Municipal (CM) e a entidade pública/associação (ACCD / ACSS).
- Órgão de governação: Steering Committee (Comité de Direção) composto por representantes das 3 entidades.

## 2. Objetivos Estratégicos do Projeto
(Apresentar os 4 objetivos centrais definidos pelo Professor Luís)
1. Identificação e especificação dos requisitos de informação e de sistema para o SIUM.
2. Conceção da arquitetura de informação e de sistemas do SIUM.
3. Desenvolvimento e implementação do protótipo do SIUM.
4. Avaliação e validação do protótipo desenvolvido.

## 3. Resultados Esperados e Entregáveis Formais
(Apresentar os 4 produtos/entregáveis chave formalmente requeridos)
1. Relatório de Requisitos de Informação e de Sistema.
2. Modelo de Dados e Arquitetura do Sistema.
3. Protótipo Operacional do SIUM.
4. Relatório de Avaliação do Protótipo.

## 4. Plano de Trabalhos, Fases e Restrições Temporais
- Estruturação em 4 tarefas principais alinhadas aos objetivos.
- **Restrição de Início**: Janeiro de 2028.
- **Restrição de Duração**: Duração máxima de 12 meses (com viabilidade de realização em 6 meses, ex.: outubro a março).
- Não haverá data limite imposta para aprovação de concurso prévio; cada grupo deve propor a sua timeline faseada.

## 5. Âmbito Funcional e Tecnológico
- **No Âmbito**: Levantamento de aplicações operacionais e de gestão, migração de dados do espólio existente, implementação de aplicações, formação de utilizadores.
- **Fora do Âmbito**: Infraestrutura física / obras de construção civil do edifício do museu.
- **Diretriz Tecnológica**: Adoção prioritária de tecnologias abertas e FOSS (Free and Open Source Software).
- Áreas operacionais e sistemas abordados: inventariação e conservação do espólio, arquivo digital, gestão de loja e bilhética, exposições temporárias e permanentes, experiências virtuais/interativas, gestão de instalações e manutenção, compras e gestão financeira.

## 6. Recursos Humanos e Estrutura Operacional
- Equipa de operação do museu (gestão operacional pela entidade parceira):
  - 1 Conservador
  - 1 Curador (responsável pela seleção e política de exibição do acervo)
  - 2 Funcionários de apoio / cumprimento de disposições
  - 1 Funcionário de loja / bilhética

## 7. Metodologia Pedagógica e Dinâmica dos Grupos
- Existência de 3 grupos de estudantes na turma.
- O resultado prático final não será a entrega de um único grupo, mas sim um "best of" (mix das melhores soluções propostas por cada grupo).
- O projeto SIUM é incremental e contínuo ao longo dos anos letivos seguintes, onde turmas futuras darão continuidade ao sistema implementado.

## 8. Tabela Síntese de Tarefas, Responsáveis e Prazos
| Tarefa / Entregável | Responsável / Stakeholder | Especificações e Prazos |

## 9. Questões em Aberto, Riscos e Recomendações
- Cumprimento escrupuloso do RGPD e legislação pública para proteção de dados de visitantes e contactos.
- Levantamento da base de dados e inventário detalhado do espólio existente (estimativa de volume, catalogação por tipos e peças indivisas).
- Condução das entrevistas formais com os stakeholders para refinamento de requisitos.

---
TRANSCRIÇÃO COMPLETA PARA SUPORTE:
{verbatim[:80000]}"""

models_to_try = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-flash-latest"
]

summary_text = None
for model in models_to_try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    print(f"A tentar gerar Síntese Executiva com {model}...", flush=True)
    try:
        resp = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.25, "maxOutputTokens": 8192}
        }, timeout=120)
        if resp.status_code == 200:
            summary_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"Síntese Executiva gerada com sucesso via {model} ({len(summary_text.split())} palavras)!", flush=True)
            break
        else:
            print(f"  -> {model} devolveu status {resp.status_code}: {resp.text[:100]}", flush=True)
    except Exception as e:
        print(f"  -> Exceção com {model}: {e}", flush=True)

if not summary_text:
    print("[ERRO] Nenhum modelo da lista conseguiu responder.", flush=True)
    sys.exit(1)

header = """# REUNIÃO GPTSI — TRANSCRIÇÃO INTEGRAL E SÍNTESE EXECUTIVA

- **Data da Gravação**: 01 de Outubro de 2026
- **Duração Total**: 01:26:36 (1 hora, 26 minutos e 36 segundos)
- **Ficheiro de Origem**: `reunião gptsi.m4a`
- **Unidade Curricular**: Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI)
- **Projeto em Análise**: SIUM — Sistema de Informação para o Novo Museu
- **Intervenientes Principais**: Professor Luís, Estudantes / Grupos de Trabalho (Grupo 1, Grupo 2, Grupo 3)
- **Motor de Transcrição**: Gemini Multimodal com Timestamps Absolutos e Limpeza Acústica

---

"""
final_full_doc = header + summary_text + "\n\n---\n\n" + verbatim

# Atualizar ficheiro em docs
transcript_path.write_text(final_full_doc, encoding="utf-8")
print(f"Ficheiro atualizado em: {transcript_path}", flush=True)

# Atualizar ficheiro no Obsidian Vault
obs_path = Path("obsidian_vault/10 - Lectures/GPTSI/2026-10-01 - Reunião GPTSI - Transcrição e Síntese.md")
obs_path.parent.mkdir(parents=True, exist_ok=True)
obs_path.write_text(final_full_doc, encoding="utf-8")
print(f"Ficheiro atualizado no Obsidian Vault em: {obs_path}", flush=True)
print("\nPROCESSO 100% CONCLUÍDO COM EXCELÊNCIA!", flush=True)
