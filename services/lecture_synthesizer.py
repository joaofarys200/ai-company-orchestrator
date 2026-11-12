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
from services.study_ai_engine import (
    generate_complete_study_bundle,
    transcribe_audio_real,
)


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
    """Executa transcrição real de áudio (Faster-Whisper local ou motor multimodal por blocos, sem texto inventado)."""

    def __init__(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size
        self.device = (device or os.getenv("WHISPER_DEVICE") or "cpu").strip() or "cpu"
        self.compute_type = (compute_type or os.getenv("WHISPER_COMPUTE_TYPE") or "int8").strip() or "int8"
        self._model = None
        self.last_status: str = ""
        self.asr_unavailable_reason: Optional[str] = "WHISPER_NOT_INSTALLED" if WhisperModel is None else None

    def _get_model(self):
        if self._model is None and WhisperModel is not None:
            # Fallback seguro para CPU float32/int8 se CUDA não estiver disponível
            try:
                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception:
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcreve arquivo de áudio gerando texto real formatado e segmentos com timestamps (nunca devolve transcrições falsas)."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

        model = self._get_model()
        full_transcript, structured_segments, status = transcribe_audio_real(
            audio_path,
            language=language,
            faster_whisper_model=model,
        )
        self.last_status = status
        if status == "TRANSCRIPTION_FAILED":
            self.asr_unavailable_reason = "WHISPER_NOT_INSTALLED" if WhisperModel is None else "RUNTIME_ERROR"
        else:
            self.asr_unavailable_reason = None
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

        # 4. Salvar no diretório da disciplina (arquivando versão anterior se existir)
        clean_subject = "".join(c for c in session.subject if c.isalnum() or c in (" ", "-", "_")).strip() or "Geral"
        clean_title = "".join(c for c in session.title if c.isalnum() or c in (" ", "-", "_")).strip() or "Aula"
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y-%m-%d")

        subject_dir = self.lectures_dir / clean_subject
        subject_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date_str} - {clean_title}.md"
        output_file = subject_dir / filename

        if output_file.exists():
            archive_dir = subject_dir / ".archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            ts_suffix = now_dt.strftime("%Y%m%d_%H%M%S_%f")
            try:
                (archive_dir / f"{output_file.stem}_{ts_suffix}.md").write_bytes(output_file.read_bytes())
            except Exception:
                pass

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
        """Constrói o documento Markdown formatado no padrão Cornell Notes fundamentado na fala real."""
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y-%m-%d")
        generated_at = now_dt.isoformat()
        duration_min = round(session.duration_seconds / 60.0, 1)

        seg_lines = []
        for s in segments or []:
            txt = (s.get("text") or "").strip()
            if not txt:
                continue
            ts = s.get("timestamp") or f"{int(float(s.get('start', 0))) // 60:02d}:{int(float(s.get('start', 0))) % 60:02d}"
            seg_lines.append(f"[{ts}] {txt}")

        effective_text = "\n".join(seg_lines) if seg_lines else (raw_transcript or "").strip()

        bundle = generate_complete_study_bundle(
            title=session.title,
            subject=session.subject,
            source_type="LECTURE_AUDIO",
            text=effective_text,
            document_id=getattr(session, "session_id", "lecture_session"),
            metadata={"segments": segments or []},
        )
        cornell = bundle["cornell_notes"]
        gen_mode = bundle.get("generation_mode", "EXTRACTIVE_GROUNDED")
        telem = bundle.get("generation_telemetry") or {}
        model_used = telem.get("model", "qwen3.5:9b") if gen_mode in ("LLM_GROUNDED", "PARTIAL") else "deterministic_extractor"
        vault_status = "llm_grounded_verified" if gen_mode == "LLM_GROUNDED" else ("llm_partial_verified" if gen_mode == "PARTIAL" else "extractive_unverified")

        exec_summary = cornell.get("executive_summary") or "Nenhum discurso inteligível detetado na gravação."
        cue_rows = []
        for item in cornell.get("cue_column") or []:
            cue_q = str(item.get("cue") or "").replace("|", "/").strip()
            idea_a = str(item.get("idea") or "").replace("|", "/").strip()
            if cue_q and idea_a:
                cue_rows.append(f"| **{cue_q}** | {idea_a} |")
        if not cue_rows:
            cue_rows.append("| **Estado da Gravação** | Áudio sem fala inteligível detetada para extrair conceitos. |")
        cue_table_body = "\n".join(cue_rows)

        detailed_body = cornell.get("detailed_notes") or self._format_detailed_body(segments)
        glossary_body = cornell.get("glossary") or "- *(Sem termos técnicos extraídos — gravação sem discurso detetado)*"
        action_lines = "\n".join(f"- [ ] {act}" for act in (cornell.get("action_items") or []))
        transcript_block = raw_transcript.strip() if (raw_transcript and raw_transcript.strip()) else "\n".join(seg_lines)

        md = f"""---
type: lecture_notes
domain: academic
status: {vault_status}
source_type: PRIMARY_SOURCE
generation_mode: "{gen_mode}"
model_used: "{model_used}"
generated_at: "{generated_at}"
confidence: {"high" if gen_mode == "LLM_GROUNDED" else "extractive"}
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
{exec_summary}

---

## 💡 2. Cornell Cue Column & Conceitos-Chave

| Perguntas de Revisão & Cues | Ideias Centrais & Respostas Rápidas |
|---|---|
{cue_table_body}

---

## 📖 3. Notas Detalhadas de Conteúdo (Detailed Notes)

{detailed_body}

---

## 📚 4. Glossário Técnico & Definições
{glossary_body}

---

## 🎯 5. Ações, Prazos & Avaliações (Action Items & Exam Alerts)
{action_lines}

---

## 🎙️ 6. Transcrição com Marcas de Tempo
<details>
<summary><b>Clique para expandir a transcrição completa ({len(segments)} segmentos)</b></summary>

```text
{transcript_block}
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
