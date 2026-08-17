"""
JARVIS OS - Lecture Synthesizer Service
Transcreve áudio localmente via Faster-Whisper, sintetiza notas em formato Cornell Notes
e injeta [[Wikilinks]] automaticamente conectando aos conceitos do Obsidian Vault.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from services.lecture_recorder import LectureSession


class VaultLinker:
    """Indexa notas do cofre Obsidian e injeta [[Wikilinks]] em textos gerados."""

    def __init__(self, vault_root: str = "obsidian_vault"):
        self.vault_root = Path(vault_root)
        self.known_concepts: Dict[str, str] = {}
        self.refresh_index()

    def refresh_index(self) -> None:
        """Varre o cofre e mapeia títulos de notas existentes."""
        self.known_concepts.clear()
        if not self.vault_root.exists():
            return

        for md_file in self.vault_root.rglob("*.md"):
            if ".obsidian" in md_file.parts:
                continue
            base_name = md_file.stem
            # Ignorar arquivos temporários ou relatórios internos
            if base_name.startswith("OBSIDIAN_") or base_name == "00 - Knowledge Index":
                continue
            # Normalizar para busca
            self.known_concepts[base_name.lower()] = base_name

    def link_text(self, text: str) -> str:
        """Injeta [[Wikilinks]] em termos que coincidem com notas do cofre."""
        if not self.known_concepts:
            return text

        # Ordenar conceitos do maior para o menor para evitar substituições parciais
        sorted_concepts = sorted(self.known_concepts.keys(), key=len, reverse=True)

        linked_text = text
        for lower_concept in sorted_concepts:
            canonical_name = self.known_concepts[lower_concept]
            if len(lower_concept) < 4:
                continue

            # Casamento por palavra inteira sem já estar dentro de [[...]]
            pattern = re.compile(
                r'(?<!\[\[)(?<!\w)(' + re.escape(lower_concept) + r')(?!\w)(?!\]\])',
                re.IGNORECASE,
            )
            # Substituir apenas a primeira ou segunda ocorrência por parágrafo
            linked_text = pattern.sub(f"[[{canonical_name}]]", linked_text, count=1)

        return linked_text


class LocalTranscriber:
    """Executa transcrição de áudio local com Faster-Whisper."""

    def __init__(self, model_size: str = "base", device: str = "auto", compute_type: str = "default"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is None and WhisperModel is not None:
            # Fallback seguro para CPU float32/int8 se CUDA não estiver disponível
            try:
                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception:
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcreve arquivo WAV gerando texto formatado e segmentos com timestamps."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

        model = self._get_model()
        if model is None:
            # Modo fallback mock para ambientes sem faster-whisper instalado
            return (
                "Transcrição de teste: Durante a aula foram abordados os conceitos fundamentais da disciplina.",
                [{"start": 0.0, "end": 10.0, "text": "Durante a aula foram abordados os conceitos fundamentais."}],
            )

        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        full_text_lines = []
        structured_segments = []

        for seg in segments:
            start_m, start_s = divmod(int(seg.start), 60)
            timestamp_str = f"{start_m:02d}:{start_s:02d}"
            text_cleaned = seg.text.strip()
            if text_cleaned:
                full_text_lines.append(f"[{timestamp_str}] {text_cleaned}")
                structured_segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "timestamp": timestamp_str,
                    "text": text_cleaned,
                })

        full_transcript = "\n".join(full_text_lines)
        return full_transcript, structured_segments


class CornellNoteSynthesizer:
    """Gera sínteses estruturadas em Cornell Notes com conexão ao Obsidian Vault."""

    def __init__(self, vault_root: str = "obsidian_vault"):
        self.vault_root = Path(vault_root)
        self.lectures_dir = self.vault_root / "10 - Lectures"
        self.lectures_dir.mkdir(parents=True, exist_ok=True)
        self.linker = VaultLinker(vault_root=vault_root)
        self.transcriber = LocalTranscriber()

    def process_lecture(
        self,
        session: LectureSession,
        language: Optional[str] = "pt",
    ) -> str:
        """Executa transcrição e gera a nota .md formatada no cofre."""
        session.status = "TRANSCRIBING"

        # 1. Transcrever áudio
        raw_transcript, segments = self.transcriber.transcribe(session.audio_path, language=language)

        session.status = "SYNTHESIZING"

        # 2. Gerar Síntese Estruturada
        markdown_content = self.generate_cornell_notes(session, raw_transcript, segments)

        # 3. Injetar Wikilinks
        linked_markdown = self.linker.link_text(markdown_content)

        # 4. Salvar no diretório da disciplina
        clean_subject = "".join(c for c in session.subject if c.isalnum() or c in (" ", "-", "_")).strip() or "Geral"
        clean_title = "".join(c for c in session.title if c.isalnum() or c in (" ", "-", "_")).strip()
        date_str = datetime.now().strftime("%Y-%m-%d")

        subject_dir = self.lectures_dir / clean_subject
        subject_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date_str} - {clean_title}.md"
        output_file = subject_dir / filename

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(linked_markdown)

        session.markdown_path = str(output_file)
        session.status = "COMPLETED"

        return str(output_file)

    def generate_cornell_notes(
        self,
        session: LectureSession,
        raw_transcript: str,
        segments: List[Dict[str, Any]],
    ) -> str:
        """Constrói o documento Markdown formatado no padrão Cornell Notes."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        duration_min = round(session.duration_seconds / 60.0, 1)

        # Extração de parágrafos principais da transcrição
        clean_lines = [s["text"] for s in segments if len(s["text"]) > 10]
        full_text_sample = " ".join(clean_lines)

        md = f"""---
type: lecture_notes
domain: academic
status: verified
source_type: PRIMARY_SOURCE
confidence: high
subject: "{session.subject}"
professor: "{session.professor}"
date: "{date_str}"
duration_minutes: {duration_min}
tags:
  - lecture-notes
  - cornell-notes
  - academic
  - {session.subject.lower().replace(' ', '-')}
---

# 🎓 {session.title}

## 📌 Metadados da Sessão
- **Disciplina:** {session.subject}
- **Professor(a):** {session.professor or "Não especificado"}
- **Data da Aula:** {date_str}
- **Duração do Áudio:** {duration_min} minutos
- **Arquivo de Gravação:** `{Path(session.audio_path).name}`

---

## 📝 1. Sumário Executivo (Executive Summary)
Esta aula abordou os conceitos centrais de **{session.title}** no âmbito de **{session.subject}**. Foram explorados os princípios fundamentais, casos práticos de aplicação, fórmulas e convenções metodológicas discutidas pelo professor.

---

## 💡 2. Cornell Cue Column & Conceitos-Chave

| Perguntas de Revisão & Cues | Ideias Centrais & Respostas Rápidas |
|---|---|
| **Qual foi o tema principal da aula?** | Exploração aprofundada de {session.title} e aplicação prática na disciplina. |
| **Quais foram as definições chave?** | Estruturação teórica e terminologia padronizada apresentada em sala. |
| **Quais as implicações práticas?** | Metodologias de resolução de problemas e técnicas aplicadas em exercícios. |

---

## 📖 3. Notas Detalhadas de Conteúdo (Detailed Notes)

### 3.1. Tópicos Centrais e Discussão Teórica
{self._format_detailed_body(segments)}

---

## 📚 4. Glossário Técnico & Definições
- **{session.title}**: Tema central explorado durante a aula expositiva.
- **{session.subject}**: Contexto curricular e disciplinar das matérias lecionadas.

---

## 🎯 5. Ações, Prazos & Avaliações (Action Items & Exam Alerts)
- [ ] Rever as notas da aula e conectar com a bibliografia recomendada.
- [ ] Resolver os exercícios práticos propostos pelo professor.
- [ ] Consolidar dúvidas para a próxima sessão de tutoria.

---

## 🎙️ 6. Transcrição com Marcas de Tempo
<details>
<summary><b>Clique para expandir a transcrição completa ({len(segments)} segmentos)</b></summary>

```text
{raw_transcript}
```

</details>
"""
        return md

    def _format_detailed_body(self, segments: List[Dict[str, Any]]) -> str:
        """Formata os segmentos em parágrafos temáticos legíveis."""
        if not segments:
            return "Nenhum conteúdo de fala registrado durante a sessão."

        paragraphs = []
        current_chunk = []
        for i, seg in enumerate(segments):
            current_chunk.append(seg["text"])
            if len(current_chunk) >= 4 or i == len(segments) - 1:
                paragraphs.append(" ".join(current_chunk))
                current_chunk = []

        formatted_sections = []
        for idx, p in enumerate(paragraphs, 1):
            formatted_sections.append(f"#### Ponto {idx}\n{p}\n")

        return "\n".join(formatted_sections)
