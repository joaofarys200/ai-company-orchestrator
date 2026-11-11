"""
JARVIS OS — Study Engine Phase 6: Structured Cornell Notes Engine
Produz notas Cornell por capítulo/secção com coluna de pistas (cues), área de notas
fundamentada e síntese, protegendo edições manuais e recusando conteúdo artificial
em secções sem matéria suficiente.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.lecture_synthesizer import VaultLinker
from services.study_modes.contracts import (
    CornellCueItem,
    CornellNoteEntry,
    CornellPersonalNote,
    CornellStudyDocument,
)
from services.study_modes.grounding import (
    LLMCaller,
    Phase6GroundingHelper,
    compute_source_fingerprints,
    invoke_phase6_json_llm,
)
from services.study_modes.persistence import StudyModePersistence
from services.study_modes.qa_engine import StudyModeQA


class CornellNotesEngine:
    """Motor de notas Cornell estruturadas por secção/capítulo com edições preservadas."""

    CORNELL_FILE = "cornell_notes.json"

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence

    def load_cornell(self, document_id: str) -> Optional[CornellStudyDocument]:
        raw = self.persistence.load_json_doc_artifact(document_id, self.CORNELL_FILE, None)
        if isinstance(raw, dict) and raw.get("document_id"):
            return CornellStudyDocument.from_dict(raw)
        return None

    def save_cornell(self, doc: CornellStudyDocument) -> CornellStudyDocument:
        doc.updated_at = datetime.now().isoformat()
        self.persistence.save_json_doc_artifact(doc.document_id, self.CORNELL_FILE, doc.to_dict())
        return doc

    def _has_sufficient_section_evidence(
        self,
        grounding: Phase6GroundingHelper,
        sec: Any,
    ) -> Tuple[bool, str]:
        orig_sids = list(getattr(sec, "original_section_ids", []) or [])
        analyses = [grounding.sections_by_id[s] for s in orig_sids if s in grounding.sections_by_id]
        total_text_len = sum(
            len(str(getattr(sa, "in_depth_synthesis", "") or ""))
            + sum(len(str(x)) for x in (getattr(sa, "core_ideas", []) or []))
            for sa in analyses
        )
        total_concepts = len(getattr(sec, "associated_concept_ids", []) or [])
        _, pids, _ = grounding.resolve_section_evidence_pool(sec)
        if total_text_len < 60 and total_concepts == 0 and not pids:
            return False, (
                f"A secção «{sec.title}» não contém conteúdo analítico ou evidências suficientes "
                "na fonte original para gerar notas Cornell substantivas."
            )
        return True, "OK"

    def generate_cornell(
        self,
        grounding: Phase6GroundingHelper,
        *,
        force_regenerate: bool = False,
        llm_caller: Optional[LLMCaller] = None,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> CornellStudyDocument:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        current_fp = compute_source_fingerprints(grounding.plan, grounding.dossier, grounding.ast)
        existing = self.load_cornell(doc_id)

        if (
            not force_regenerate
            and existing is not None
            and existing.fingerprints is not None
            and existing.fingerprints.plan_fingerprint == current_fp.plan_fingerprint
            and existing.fingerprints.dossier_fingerprint == current_fp.dossier_fingerprint
            and existing.entries
        ):
            return existing

        existing_by_sec: Dict[str, CornellNoteEntry] = {
            e.section_id: e for e in (existing.entries if existing else [])
        }

        entries: List[CornellNoteEntry] = []
        failed_ops: List[Dict[str, Any]] = []
        llm_used = False
        chapters = list(grounding.plan.chapters or [])

        for c_idx, chapter in enumerate(chapters):
            if on_progress:
                on_progress(
                    "CORNELL_NOTES",
                    0.1 + 0.75 * ((c_idx + 1) / max(1, len(chapters))),
                    f"A estruturar notas Cornell do Capítulo {c_idx + 1}/{len(chapters)}: {chapter.title}",
                )

            chap_payload = grounding.build_chapter_prompt_payload(chapter)
            # Identificar previamente quais secções têm material suficiente
            sufficient_map: Dict[str, Tuple[bool, str]] = {
                sec.section_id: self._has_sufficient_section_evidence(grounding, sec)
                for sec in (chapter.sections or [])
            }
            sufficient_sec_ids = [sid for sid, (ok, _) in sufficient_map.items() if ok]

            parsed_sections_map: Dict[str, Dict[str, Any]] = {}
            if sufficient_sec_ids:
                system_prompt = (
                    "És um tutor académico rigoroso. Produz Cornell Notes em Português Europeu "
                    "para as secções indicadas, usando APENAS o conteúdo analisado nas Fases 3–4.\n"
                    "Nunca inventes factos, páginas ou paragraph_ids.\n"
                    "Devolve JSON com chave 'sections': lista de objetos cada um com:\n"
                    "{\"section_id\", \"main_concepts\": [{\"name\", \"note\"}], \"explanations\": [...], "
                    "\"supporting_details\": [...], \"examples\": [...], \"concept_relationships\": [...], "
                    "\"methodology_notes\", \"results_and_conclusions_notes\", "
                    "\"cue_column\": [{\"cue_prompt\", \"cue_type\", \"answer_hint\", \"evidence_refs\"}], "
                    "\"summary_section\", \"evidence_refs\", \"epistemic_status\"}."
                )
                user_prompt = (
                    f"Secções elegíveis com section_id exatamente igual a {sufficient_sec_ids}:\n"
                    f"{chap_payload}"
                )

                def _validate(obj: Dict[str, Any]) -> Tuple[bool, str]:
                    secs = obj.get("sections")
                    if not isinstance(secs, list) or not secs:
                        return False, "Campo 'sections' deve ser uma lista não vazia."
                    for item in secs:
                        if not isinstance(item, dict) or str(item.get("section_id", "")) not in sufficient_sec_ids:
                            return False, f"section_id desconhecido ou inválido na resposta Cornell: {item.get('section_id') if isinstance(item, dict) else None}"
                    return True, "OK"

                parsed, meta = invoke_phase6_json_llm(
                    llm_caller=llm_caller,
                    operation=f"phase6_cornell_{chapter.chapter_id}",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    document_id=doc_id,
                    validator=_validate,
                    max_output_tokens=2600,
                )
                if parsed and isinstance(parsed.get("sections"), list):
                    llm_used = True
                    for item in parsed["sections"]:
                        parsed_sections_map[str(item["section_id"])] = item
                else:
                    failed_ops.append({
                        "operation": f"phase6_cornell_{chapter.chapter_id}",
                        "error": meta.get("error", "Falha LLM nas notas Cornell; usada síntese determinística."),
                        "timestamp": datetime.now().isoformat(),
                    })

            for sec in (chapter.sections or []):
                prev = existing_by_sec.get(sec.section_id)
                ok_suff, reason = sufficient_map.get(sec.section_id, (False, "Sem análise"))
                if not ok_suff:
                    entry = CornellNoteEntry(
                        entry_id=prev.entry_id if prev else f"cn_{sec.section_id}",
                        chapter_id=chapter.chapter_id,
                        chapter_title=chapter.title,
                        section_id=sec.section_id,
                        section_title=sec.title,
                        sufficient_evidence=False,
                        insufficiency_reason=reason,
                        epistemic_status="NOT_FOUND",
                        is_important=prev.is_important if prev else False,
                        personal_notes=list(prev.personal_notes) if prev else [],
                        generation_mode="INSUFFICIENT_SOURCE",
                    )
                    entries.append(entry)
                    continue

                raw_llm_sec = parsed_sections_map.get(sec.section_id)
                if raw_llm_sec:
                    entry = self._build_entry_from_llm(grounding, chapter, sec, raw_llm_sec)
                else:
                    entry = self._build_deterministic_entry(grounding, chapter, sec)

                # Preservar anotações pessoais, importância e campos editados pelo utilizador
                if prev is not None:
                    entry.is_important = prev.is_important
                    entry.personal_notes = list(prev.personal_notes)
                    if prev.user_edited:
                        entry.user_edited = True
                        entry.edited_fields = list(prev.edited_fields)
                        for fld in prev.edited_fields:
                            if hasattr(prev, fld):
                                setattr(entry, fld, getattr(prev, fld))
                        # Preservar também pistas editadas manualmente
                        edited_cues = [c for c in prev.cue_column if c.user_edited]
                        if edited_cues:
                            existing_prompts = {c.cue_prompt.lower() for c in edited_cues}
                            entry.cue_column = edited_cues + [
                                c for c in entry.cue_column if c.cue_prompt.lower() not in existing_prompts
                            ]

                ok_qa, _ = StudyModeQA(grounding).validate_cornell_entry(entry)
                if not ok_qa:
                    entry = self._build_deterministic_entry(grounding, chapter, sec)
                entries.append(entry)

        doc = CornellStudyDocument(
            cornell_id=existing.cornell_id if existing else f"cornell_{hashlib.sha1(doc_id.encode('utf-8')).hexdigest()[:10]}",
            document_id=doc_id,
            title=getattr(grounding.dossier.document_analysis, "title", "") or doc_id,
            subject=str(getattr(grounding.plan.overview, "document_nature", "Académico") or "Académico"),
            global_summary=str(getattr(grounding.dossier.cross_section_synthesis, "global_synthesis", "") or getattr(grounding.plan.overview, "global_organization_summary", "")),
            entries=entries,
            fingerprints=current_fp,
            generation_mode="LLM_GROUNDED" if llm_used and not failed_ops else ("PARTIAL_FALLBACK" if llm_used else "DETERMINISTIC_GROUNDED"),
            status="COMPLETED" if entries else "PARTIAL",
            failed_operations=failed_ops,
        )
        return self.save_cornell(doc)

    def _build_entry_from_llm(
        self,
        grounding: Phase6GroundingHelper,
        chapter: Any,
        sec: Any,
        raw: Dict[str, Any],
    ) -> CornellNoteEntry:
        orig_sids = list(getattr(sec, "original_section_ids", []) or [])
        summary_txt = str(raw.get("summary_section") or "").strip()
        explanations = [str(x).strip() for x in (raw.get("explanations") or []) if str(x).strip()]
        valid_refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
            raw.get("evidence_refs"),
            allowed_section_ids=orig_sids,
            candidate_text=f"{summary_txt} {' '.join(explanations)}",
            requested_status=str(raw.get("epistemic_status") or "MODEL_INFERENCE"),
        )

        cues: List[CornellCueItem] = []
        for idx, rc in enumerate(raw.get("cue_column") or []):
            if not isinstance(rc, dict) or not str(rc.get("cue_prompt") or "").strip():
                continue
            c_refs, _, c_ep, _ = grounding.validate_and_ground_refs(
                rc.get("evidence_refs") or [r.__dict__ for r in valid_refs[:2]],
                allowed_section_ids=orig_sids,
                candidate_text=f"{rc.get('cue_prompt', '')} {rc.get('answer_hint', '')}",
                requested_status="MODEL_INFERENCE",
            )
            cues.append(
                CornellCueItem(
                    cue_id=f"cue_{sec.section_id}_{idx + 1:02d}",
                    cue_prompt=str(rc.get("cue_prompt") or "").strip(),
                    cue_type=str(rc.get("cue_type") or "QUESTION").upper(),
                    answer_hint=str(rc.get("answer_hint") or "").strip(),
                    epistemic_status=c_ep,
                    evidence_refs=c_refs,
                )
            )

        main_concepts = [
            {"name": str(mc.get("name", "")).strip(), "note": str(mc.get("note", "")).strip()}
            for mc in (raw.get("main_concepts") or [])
            if isinstance(mc, dict) and str(mc.get("name", "")).strip()
        ]
        return CornellNoteEntry(
            entry_id=f"cn_{sec.section_id}",
            chapter_id=chapter.chapter_id,
            chapter_title=chapter.title,
            section_id=sec.section_id,
            section_title=sec.title,
            sufficient_evidence=True,
            main_concepts=main_concepts,
            explanations=explanations,
            supporting_details=[str(x).strip() for x in (raw.get("supporting_details") or []) if str(x).strip()],
            examples=[str(x).strip() for x in (raw.get("examples") or []) if str(x).strip()],
            concept_relationships=[str(x).strip() for x in (raw.get("concept_relationships") or []) if str(x).strip()],
            methodology_notes=str(raw.get("methodology_notes") or "").strip(),
            results_and_conclusions_notes=str(raw.get("results_and_conclusions_notes") or "").strip(),
            cue_column=cues,
            summary_section=summary_txt,
            source_pages=pages,
            evidence_refs=valid_refs,
            epistemic_status=ep_st,
            generation_mode="LLM_GROUNDED",
        )

    def _build_deterministic_entry(
        self,
        grounding: Phase6GroundingHelper,
        chapter: Any,
        sec: Any,
    ) -> CornellNoteEntry:
        orig_sids = list(getattr(sec, "original_section_ids", []) or [])
        grounded_refs, _, pages = grounding.resolve_section_evidence_pool(sec)

        main_concepts: List[Dict[str, Any]] = []
        cues: List[CornellCueItem] = []
        for cid in (getattr(sec, "associated_concept_ids", []) or [])[:6]:
            c = grounding.concepts_by_id.get(cid)
            if not c:
                continue
            note_txt = (c.definition or c.explanation or "").strip()
            main_concepts.append({"name": c.name, "note": note_txt})
            cues.append(
                CornellCueItem(
                    cue_id=f"cue_{sec.section_id}_{len(cues) + 1:02d}",
                    cue_prompt=f"O que define «{c.name}» e qual o seu papel nesta secção?",
                    cue_type="CONCEPT",
                    answer_hint=note_txt[:220],
                    epistemic_status="SOURCE_FACT" if c.definition else "MODEL_INFERENCE",
                    concept_ids=[cid],
                    evidence_refs=list(c.evidence_refs or [])[:2],
                )
            )

        explanations: List[str] = []
        supporting: List[str] = []
        for osid in orig_sids:
            sa = grounding.sections_by_id.get(osid)
            if not sa:
                continue
            if sa.in_depth_synthesis:
                explanations.append(sa.in_depth_synthesis.strip())
            for idea in (sa.core_ideas or [])[:5]:
                if str(idea).strip():
                    supporting.append(str(idea).strip())
                    cues.append(
                        CornellCueItem(
                            cue_id=f"cue_{sec.section_id}_{len(cues) + 1:02d}",
                            cue_prompt=f"Reconstituir ponto-chave: {str(idea).strip()[:75]}?",
                            cue_type="RECALL_PROMPT",
                            answer_hint=str(idea).strip()[:200],
                            epistemic_status="MODEL_INFERENCE",
                            evidence_refs=grounded_refs[:2],
                        )
                    )

        # Incluir blocos desenvolvidos da Fase 5 se existirem no disco
        dev_sec = grounding.dev_sections_by_id.get(sec.section_id)
        if isinstance(dev_sec, dict) and not explanations:
            for blk in (dev_sec.get("content_blocks") or [])[:3]:
                if isinstance(blk, dict):
                    for bp in (blk.get("body_paragraphs") or [])[:2]:
                        if str(bp).strip():
                            explanations.append(str(bp).strip())

        rels: List[str] = []
        c_set = set(getattr(sec, "associated_concept_ids", []) or [])
        for rel in getattr(grounding.plan, "conceptual_relationships", []) or []:
            if rel.source_concept_id in c_set or rel.target_concept_id in c_set:
                rels.append(f"{rel.source_concept_name} ({rel.relation_type}) → {rel.target_concept_name}: {rel.justification}")

        if not cues:
            cues.append(
                CornellCueItem(
                    cue_id=f"cue_{sec.section_id}_01",
                    cue_prompt=f"Qual o objetivo central de «{sec.title}»?",
                    cue_type="QUESTION",
                    answer_hint=(sec.pedagogical_objective or chapter.pedagogical_objective)[:220],
                    epistemic_status="MODEL_INFERENCE",
                    evidence_refs=grounded_refs[:2],
                )
            )

        summary_txt = (
            f"Síntese de «{sec.title}»: {sec.pedagogical_objective}. "
            + (explanations[0][:280] if explanations else "Fundamentado nos conceitos e evidências originais da secção.")
        ).strip()

        return CornellNoteEntry(
            entry_id=f"cn_{sec.section_id}",
            chapter_id=chapter.chapter_id,
            chapter_title=chapter.title,
            section_id=sec.section_id,
            section_title=sec.title,
            sufficient_evidence=True,
            main_concepts=main_concepts,
            explanations=explanations,
            supporting_details=supporting,
            concept_relationships=rels[:5],
            cue_column=cues[:8],
            summary_section=summary_txt,
            source_pages=pages,
            evidence_refs=grounded_refs[:6],
            epistemic_status="MODEL_INFERENCE",
            generation_mode="DETERMINISTIC_GROUNDED",
        )

    # ------------------------------------------------------------------
    # Edição, Anotações Pessoais e Exportação Vault
    # ------------------------------------------------------------------

    def edit_entry(
        self,
        document_id: str,
        section_id: str,
        *,
        summary_section: Optional[str] = None,
        explanations: Optional[List[str]] = None,
        supporting_details: Optional[List[str]] = None,
        cue_column: Optional[List[Dict[str, Any]]] = None,
        is_important: Optional[bool] = None,
    ) -> CornellNoteEntry:
        doc = self.load_cornell(document_id)
        if not doc:
            raise ValueError(f"Notas Cornell não encontradas para '{document_id}'.")
        for entry in doc.entries:
            if entry.section_id == section_id:
                edited_fields = set(entry.edited_fields or [])
                if summary_section is not None:
                    entry.summary_section = summary_section
                    edited_fields.add("summary_section")
                if explanations is not None:
                    entry.explanations = [str(x) for x in explanations if str(x).strip()]
                    edited_fields.add("explanations")
                if supporting_details is not None:
                    entry.supporting_details = [str(x) for x in supporting_details if str(x).strip()]
                    edited_fields.add("supporting_details")
                if cue_column is not None:
                    entry.cue_column = [
                        CornellCueItem.from_dict({**c, "user_edited": True})
                        for c in cue_column
                        if isinstance(c, dict)
                    ]
                    edited_fields.add("cue_column")
                if is_important is not None:
                    entry.is_important = bool(is_important)
                entry.user_edited = bool(edited_fields)
                entry.edited_fields = sorted(edited_fields)
                self.save_cornell(doc)
                return entry
        raise ValueError(f"Secção Cornell '{section_id}' não encontrada.")

    def add_personal_note(
        self,
        document_id: str,
        section_id: str,
        content: str,
        *,
        is_important: bool = False,
    ) -> CornellPersonalNote:
        doc = self.load_cornell(document_id)
        if not doc:
            raise ValueError(f"Notas Cornell não encontradas para '{document_id}'.")
        for entry in doc.entries:
            if entry.section_id == section_id:
                note = CornellPersonalNote(
                    note_id=f"pnote_{uuid.uuid4().hex[:8]}",
                    section_id=section_id,
                    content=content.strip(),
                    is_important=is_important,
                )
                entry.personal_notes.append(note)
                self.save_cornell(doc)
                return note
        raise ValueError(f"Secção Cornell '{section_id}' não encontrada.")

    def export_markdown(self, doc: CornellStudyDocument, vault_root: Optional[str] = None) -> str:
        lines: List[str] = [
            f"# Cornell Notes — {doc.title}",
            "",
            f"- **Documento:** `{doc.document_id}`",
            f"- **Modo de Geração:** `{doc.generation_mode}`",
            "",
            "## Síntese Global",
            doc.global_summary or "(Sem síntese global)",
            "",
        ]
        for entry in doc.entries:
            star = " ★" if entry.is_important else ""
            lines.append(f"## {entry.chapter_title} / {entry.section_title}{star}")
            if not entry.sufficient_evidence:
                lines.append(f"> Nota: {entry.insufficiency_reason}")
                lines.append("")
                continue
            pages_str = ", ".join(str(p) for p in entry.source_pages) or "N/D"
            lines.append(f"_Classificação epistémica: `{entry.epistemic_status}` | Páginas: {pages_str}_")
            lines.append("")
            if entry.cue_column:
                lines.append("### Cue Column (Pistas & Perguntas de Recuperação)")
                for cue in entry.cue_column:
                    lines.append(f"- **{cue.cue_prompt}** — _{cue.answer_hint}_")
                lines.append("")
            if entry.main_concepts:
                lines.append("### Conceitos Principais")
                for mc in entry.main_concepts:
                    lines.append(f"- **{mc.get('name', '')}**: {mc.get('note', '')}")
                lines.append("")
            if entry.explanations or entry.supporting_details:
                lines.append("### Área de Notas")
                for exp in entry.explanations:
                    lines.append(exp)
                    lines.append("")
                for det in entry.supporting_details:
                    lines.append(f"- {det}")
                lines.append("")
            if entry.personal_notes:
                lines.append("### Notas Pessoais do Estudante")
                for pn in entry.personal_notes:
                    lines.append(f"- {pn.content}")
                lines.append("")
            lines.append("### Resumo da Secção")
            lines.append(entry.summary_section)
            lines.append("")

        md = "\n".join(lines)
        if vault_root:
            try:
                linker = VaultLinker(vault_root=vault_root)
                md = linker.link_text(md)
            except Exception:
                pass
        return md

