"""
JARVIS OS — Study Engine Phase 5: Reference and Provenance Renderer (Componente 5.7)
Apresentação rigorosa de proveniência, páginas de origem, distinção epistémica
e referências bibliográficas sem invenção de metadados.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialEvidenceRef
from services.study_document_generation.contracts import (
    ElaborationType,
    IRBibliographyEntry,
    VALID_EPISTEMIC_STATUSES,
    normalize_epistemic_status,
)

_STOP_WORDS = frozenset({
    "para", "como", "sobre", "entre", "com", "sem", "uma", "umas", "uns", "dos", "das",
    "nos", "nas", "pelo", "pela", "pelos", "pelas", "este", "esta", "estes", "estas",
    "esse", "essa", "isso", "isto", "aquilo", "mais", "menos", "muito", "muita", "muitos",
    "onde", "quando", "porque", "pois", "que", "qual", "quais", "sendo", "foram", "esta",
    "está", "estão", "pode", "podem", "the", "and", "for", "with", "from", "that", "this",
    "were", "was", "are", "have", "has", "been", "into", "about", "which", "their",
})


class ReferenceAndProvenanceRenderer:
    """
    Formata e valida a proveniência epistémica, citações de páginas/parágrafos,
    referências a figuras/tabelas originais e bibliografia documental.
    """

    def __init__(
        self,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST] = None,
    ) -> None:
        self.dossier = dossier
        self.ast = ast
        self.valid_pages: Set[int] = set()
        self.valid_paragraphs: Set[str] = set()
        self.valid_sections: Set[str] = set()
        self.para_to_page: Dict[str, int] = {}
        self.para_to_section: Dict[str, str] = {}
        self.para_texts: Dict[str, str] = {}
        self.sec_texts: Dict[str, str] = {}
        self.page_texts: Dict[int, str] = {}
        self.sec_to_pages: Dict[str, List[int]] = {}
        self.tables_by_id: Dict[str, Tuple[str, int]] = {}
        self.figures_by_id: Dict[str, Tuple[str, int]] = {}
        self.verified_source_excerpts: Dict[str, str] = {}
        self._index_sources()

    def _index_sources(self) -> None:
        if self.ast is not None:
            for p in self.ast.pages:
                if p.page_number > 0:
                    self.valid_pages.add(p.page_number)
            for sec in self.ast.sections:
                self.valid_sections.add(sec.section_id)
                pages = [pg for pg in range(sec.page_start, sec.page_end + 1) if pg > 0]
                self.sec_to_pages[sec.section_id] = pages
                self.valid_pages.update(pages)
            for para in self.ast.paragraphs:
                self.valid_paragraphs.add(para.paragraph_id)
                if para.text:
                    self.para_texts[para.paragraph_id] = para.text
                    if para.section_id:
                        self.sec_texts[para.section_id] = (self.sec_texts.get(para.section_id, "") + " " + para.text).strip()
                    if para.page_number > 0:
                        self.page_texts[para.page_number] = (self.page_texts.get(para.page_number, "") + " " + para.text).strip()
                if para.section_id:
                    self.para_to_section[para.paragraph_id] = para.section_id
                if para.page_number > 0:
                    self.para_to_page[para.paragraph_id] = para.page_number
                    self.valid_pages.add(para.page_number)
            for tbl in self.ast.tables:
                self.tables_by_id[tbl.table_id] = (tbl.caption or tbl.table_id, tbl.page_number)
                if tbl.page_number > 0:
                    self.valid_pages.add(tbl.page_number)
                tbl_flat = " ".join(" ".join(str(c) for c in row) for row in (tbl.rows or []))
                if tbl.section_id and tbl_flat:
                    self.sec_texts[tbl.section_id] = (self.sec_texts.get(tbl.section_id, "") + " " + tbl_flat).strip()
            for fig in self.ast.figures:
                self.figures_by_id[fig.figure_id] = (fig.caption or fig.figure_id, fig.page_number)
                if fig.page_number > 0:
                    self.valid_pages.add(fig.page_number)

        for sa in self.dossier.section_analyses:
            self.valid_sections.add(sa.section_id)
            p_start = getattr(sa, "page_start", None)
            p_end = getattr(sa, "page_end", None)
            if p_start is not None and p_end is not None:
                pages = [pg for pg in range(p_start, p_end + 1) if pg > 0]
                if sa.section_id not in self.sec_to_pages and pages:
                    self.sec_to_pages[sa.section_id] = pages
                self.valid_pages.update(pages)

            for ref in getattr(sa, "source_refs", []):
                pid = getattr(ref, "paragraph_id", None)
                if pid:
                    self.valid_paragraphs.add(pid)
                    if getattr(ref, "excerpt", ""):
                        self.verified_source_excerpts[pid] = ref.excerpt
                        if pid not in self.para_texts:
                            self.para_texts[pid] = ref.excerpt
                if getattr(ref, "page_number", None) and ref.page_number > 0:
                    self.valid_pages.add(ref.page_number)
                    if sa.section_id not in self.sec_to_pages:
                        self.sec_to_pages[sa.section_id] = [ref.page_number]
                    elif ref.page_number not in self.sec_to_pages[sa.section_id]:
                        self.sec_to_pages[sa.section_id].append(ref.page_number)

            for ev_list in (getattr(sa, "explicit_facts", []), getattr(sa, "inferences", [])):
                for item in ev_list:
                    for ev in getattr(item, "evidence_refs", []):
                        for pid in getattr(ev, "paragraph_ids", [getattr(ev, "paragraph_id", None)]):
                            if pid:
                                self.valid_paragraphs.add(pid)
                        for pg in getattr(ev, "page_numbers", [getattr(ev, "page_number", None)]):
                            if pg and pg > 0:
                                self.valid_pages.add(pg)

    def validate_evidence_refs(
        self,
        refs: Sequence[EditorialEvidenceRef],
        *,
        fallback_section_ids: Optional[Sequence[str]] = None,
        allow_section_fallback: bool = False,
        default_status: str = "UNVERIFIED",
    ) -> Tuple[List[EditorialEvidenceRef], List[str], List[int], List[str]]:
        """
        Valida rigorosamente referências de evidência contra AST e Dossier.
        Devolve: (valid_refs, rejected_paragraph_ids, rejected_pages, rejected_section_ids).
        Nunca aceita parágrafos inexistentes e nunca promove referências não validadas para SOURCE_FACT.
        """
        cleaned: List[EditorialEvidenceRef] = []
        rejected_pids: List[str] = []
        rejected_pages: List[int] = []
        rejected_sids: List[str] = []
        seen: Set[Tuple[str, str, int, str]] = set()

        for r in refs or []:
            pid = str(getattr(r, "paragraph_id", "") or "").strip()
            sid = str(getattr(r, "section_id", "") or "").strip()
            raw_pg = getattr(r, "page_number", None)
            pg = int(raw_pg) if raw_pg and int(raw_pg) > 0 else None

            if pid:
                if not self.valid_paragraphs or pid not in self.valid_paragraphs:
                    rejected_pids.append(pid)
                    pid = ""
            if sid and self.valid_sections and sid not in self.valid_sections:
                rejected_sids.append(sid)
                sid = ""
            if pg is not None:
                if self.valid_pages and pg not in self.valid_pages:
                    rejected_pages.append(pg)
                    pg = None

            if pg is None and pid and pid in self.para_to_page:
                pg = self.para_to_page[pid]
            if not sid and pid and pid in self.para_to_section:
                sid = self.para_to_section[pid]
            if pg is None and sid and sid in self.sec_to_pages and self.sec_to_pages[sid]:
                pg = self.sec_to_pages[sid][0]

            if not pid and not sid and pg is None:
                continue

            st = normalize_epistemic_status(getattr(r, "status", None), default=default_status)

            key = (pid, sid, pg or 0, st)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(
                EditorialEvidenceRef(
                    paragraph_id=pid,
                    section_id=sid,
                    page_number=pg,
                    status=st,
                    excerpt=str(getattr(r, "excerpt", "") or "")[:180],
                )
            )

        if not cleaned and allow_section_fallback and fallback_section_ids:
            for f_sid in fallback_section_ids:
                s_clean = str(f_sid).strip()
                if not s_clean or (self.valid_sections and s_clean not in self.valid_sections):
                    continue
                pages = self.sec_to_pages.get(s_clean, [])
                pg = pages[0] if pages else None
                cleaned.append(
                    EditorialEvidenceRef(
                        paragraph_id="",
                        section_id=s_clean,
                        page_number=pg,
                        status=default_status if default_status in VALID_EPISTEMIC_STATUSES else "UNVERIFIED",
                        excerpt="",
                    )
                )
                break

        return cleaned, rejected_pids, rejected_pages, rejected_sids

    def sanitize_evidence_refs(
        self,
        refs: Sequence[EditorialEvidenceRef],
        fallback_section_ids: Optional[Sequence[str]] = None,
        *,
        allow_section_fallback: bool = True,
        default_status: str = "UNVERIFIED",
    ) -> List[EditorialEvidenceRef]:
        """
        Filtra e valida referências de evidência contra o documento original,
        impedindo a citação de páginas, secções ou parágrafos inexistentes.
        """
        cleaned, _, _, _ = self.validate_evidence_refs(
            refs,
            fallback_section_ids=fallback_section_ids,
            allow_section_fallback=allow_section_fallback,
            default_status=default_status,
        )
        return cleaned

    def has_minimal_source_overlap(
        self,
        claim_text: str,
        refs: Sequence[EditorialEvidenceRef],
    ) -> bool:
        """
        Verificação lexical de rastreabilidade: confirma apenas se o texto reivindica termos
        presentes nos parágrafos/excertos citados. NÃO constitui garantia semântica absoluta
        e serve exclusivamente para detetar reivindicações desconexas rotuladas como SOURCE_FACT.
        """
        if not claim_text or not refs:
            return False

        source_chunks: List[str] = []
        for r in refs:
            if r.paragraph_id and r.paragraph_id in self.para_texts:
                source_chunks.append(self.para_texts[r.paragraph_id])
            if getattr(r, "excerpt", ""):
                source_chunks.append(r.excerpt)
            if r.page_number and r.page_number in self.page_texts and not r.paragraph_id:
                source_chunks.append(self.page_texts[r.page_number])
            elif r.section_id and r.section_id in self.sec_texts and not r.paragraph_id:
                source_chunks.append(self.sec_texts[r.section_id])

        if not source_chunks:
            return False

        def _tokens(txt: str) -> Set[str]:
            return {
                tok for tok in re.findall(r"[0-9a-zà-öø-ÿ]{4,}", txt.lower())
                if tok not in _STOP_WORDS
            }

        claim_toks = _tokens(claim_text)
        source_toks = _tokens(" ".join(source_chunks))
        if not claim_toks or not source_toks:
            return False

        overlap = claim_toks & source_toks
        min_needed = 1 if len(claim_toks) <= 4 else 2
        return len(overlap) >= min_needed

    def format_provenance_summary(
        self,
        epistemic_status: str,
        evidence_refs: Sequence[EditorialEvidenceRef],
        *,
        is_hypothetical_example: bool = False,
        elaboration_type: str = "",
        source_table_refs: Optional[Sequence[str]] = None,
        source_figure_refs: Optional[Sequence[str]] = None,
        rejected_refs_count: int = 0,
    ) -> str:
        """
        Gera uma linha de proveniência clara e auditável para um bloco ou secção.
        Distingue explicitamente factos da fonte de inferências do modelo, conteúdo não verificado
        e exemplos hipotéticos, sem nunca promover referências ausentes/inválidas a SOURCE_FACT.
        """
        norm_status = normalize_epistemic_status(epistemic_status, default="UNVERIFIED")
        valid_refs = self.sanitize_evidence_refs(evidence_refs, allow_section_fallback=False)
        pages = sorted({r.page_number for r in valid_refs if r.page_number and r.page_number > 0})
        paras = [r.paragraph_id for r in valid_refs if r.paragraph_id]
        paras_unique = list(dict.fromkeys(paras))[:5]
        secs = [r.section_id for r in valid_refs if r.section_id]
        secs_unique = list(dict.fromkeys(secs))[:3]

        if is_hypothetical_example or elaboration_type == ElaborationType.HYPOTHETICAL_EXAMPLE.value:
            status_badge = (
                "Elaboração Pedagógica: Exemplo Ilustrativo Hipotético [MODEL_INFERENCE] "
                "— não constitui evidência empírica da fonte"
            )
        elif norm_status == "SOURCE_FACT" and elaboration_type in (
            ElaborationType.PEDAGOGICAL_EXPLANATION.value,
            ElaborationType.ANALYTICAL_INFERENCE.value,
            ElaborationType.EDITORIAL_SYNTHESIS.value,
        ):
            status_badge = (
                "Elaboração Pedagógica fundamentada na fonte [MODEL_INFERENCE] "
                "— baseada em evidências originais (não literal)"
            )
        elif norm_status == "SOURCE_FACT":
            status_badge = "Facto Confirmado na Fonte Original [SOURCE_FACT]"
        elif norm_status == "MODEL_INFERENCE":
            status_badge = "Inferência / Explicação do Modelo [MODEL_INFERENCE] fundamentada na fonte"
        elif norm_status == "NOT_FOUND":
            status_badge = "Informação Ausente na Fonte [NOT_FOUND]"
        else:
            status_badge = "Informação Não Verificada na Fonte [UNVERIFIED]"

        loc_parts: List[str] = []
        if pages:
            if len(pages) == 1:
                loc_parts.append(f"p. {pages[0]}")
            else:
                loc_parts.append(f"pp. {', '.join(str(p) for p in pages[:6])}")
        if secs_unique:
            loc_parts.append(f"Secções: {', '.join(secs_unique)}")
        if paras_unique:
            loc_parts.append(f"Parágrafos: {', '.join(paras_unique)}")

        media_parts: List[str] = []
        for tid in (source_table_refs or []):
            if tid in self.tables_by_id:
                cap, t_pg = self.tables_by_id[tid]
                media_parts.append(f"Tabela original {tid} (p. {t_pg})")
        for fid in (source_figure_refs or []):
            if fid in self.figures_by_id:
                cap, f_pg = self.figures_by_id[fid]
                media_parts.append(f"Figura original {fid} (p. {f_pg})")

        all_details = loc_parts + media_parts
        extra_notes: List[str] = []
        if rejected_refs_count > 0:
            extra_notes.append(f"{rejected_refs_count} ref(s) inexistente(s) rejeitada(s)")
        if norm_status in ("MODEL_INFERENCE", "UNVERIFIED") and all_details:
            extra_notes.append("referência contextual (cada frase não está literalmente comprovada)")

        summary = f"Proveniência: {status_badge}"
        if all_details:
            summary += f" | Origem: {' • '.join(all_details)}"
        if extra_notes:
            summary += f" | Nota: {'; '.join(extra_notes)}"
        return summary

    def compile_bibliography(self) -> Tuple[List[IRBibliographyEntry], List[str]]:
        """
        Compila a lista de referências bibliográficas exclusivamente a partir da AcademicDocumentAST.
        Nunca inventa autores, datas, títulos ou locais de publicação em falta.
        Regista explicitamente limitações quando os metadados estão incompletos.
        """
        entries: List[IRBibliographyEntry] = []
        notes: List[str] = []

        # 1. Documento original analisado como Fonte Primária
        if self.ast is not None and getattr(self.ast, "metadata", None) is not None:
            meta = self.ast.metadata
            doc_title = (getattr(meta, "title", None) or getattr(self.dossier, "document_title", None) or getattr(meta, "filename", None) or "Documento Original").strip()
            authors: List[str] = []
            for a in (getattr(meta, "authors", None) or []):
                if isinstance(a, dict):
                    name = a.get("name") or a.get("raw") or str(a)
                    if name.strip():
                        authors.append(name.strip())
                elif isinstance(a, str) and a.strip():
                    authors.append(a.strip())

            pub_date = getattr(meta, "publication_date", None)
            if isinstance(pub_date, dict):
                year = str(pub_date.get("year", "")).strip() or None
            elif pub_date:
                year = str(pub_date).strip()
            else:
                raw_year = getattr(meta, "publication_date_or_year", None) or getattr(meta, "year", None)
                year = str(raw_year).strip() if raw_year else None

            venue = getattr(meta, "journal_or_venue", None) or getattr(meta, "venue", None)
            if venue:
                venue = str(venue).strip()
            doi = str(meta.doi).strip() if getattr(meta, "doi", None) else None

            missing_fields: List[str] = []
            if not authors:
                missing_fields.append("autores")
            if not year:
                missing_fields.append("ano de publicação")
            if not venue:
                missing_fields.append("revista/editora")

            parts: List[str] = []
            if authors:
                parts.append(", ".join(authors))
            if year:
                parts.append(f"({year})")
            parts.append(f"«{doc_title}»")
            if venue:
                parts.append(venue)
            if doi:
                parts.append(f"DOI: {doi}")
            parts.append(f"[Ficheiro de origem: {getattr(meta, 'filename', '')}, {getattr(meta, 'page_count', 0)} págs.]")

            limitation = None
            if missing_fields:
                limitation = (
                    f"Metadados bibliográficos parciais na fonte original (campos não detetados explicitamente: "
                    f"{', '.join(missing_fields)}). Apresentados apenas os dados verificados."
                )

            entries.append(
                IRBibliographyEntry(
                    ref_id="SOURCE_PRIMARY",
                    citation_label="[Fonte Primária]",
                    formatted_reference=". ".join(parts),
                    authors=authors,
                    year=year,
                    title=doc_title,
                    venue=venue,
                    doi_or_url=doi,
                    is_metadata_complete=len(missing_fields) == 0,
                    metadata_limitation_note=limitation,
                )
            )

            # 2. Referências bibliográficas extraídas da secção de Referências do documento original
            for idx, ref in enumerate(self.ast.references or [], start=1):
                raw_txt = (getattr(ref, "raw", None) or getattr(ref, "raw_text", None) or "").strip()
                if not raw_txt:
                    continue
                r_authors: List[str] = []
                if getattr(ref, "authors_raw", None):
                    r_authors = [str(ref.authors_raw).strip()]
                elif getattr(ref, "authors", None):
                    r_authors = [str(a).strip() for a in ref.authors if str(a).strip()]

                r_year = str(ref.year).strip() if getattr(ref, "year", None) else None
                r_title = str(ref.title).strip() if getattr(ref, "title", None) else None
                r_venue = str(ref.venue).strip() if getattr(ref, "venue", None) else None
                r_doi = str(getattr(ref, "doi", None) or getattr(ref, "doi_or_url", None) or "").strip() or None

                is_complete = bool(r_authors and r_year and r_title)
                lim_note = None
                if not is_complete:
                    lim_note = (
                        "Referência preservada literalmente a partir da extração textual do documento original "
                        "(campos estruturados parciais não extrapolados)."
                    )

                ref_id_str = getattr(ref, "reference_id", None) or getattr(ref, "ref_id", None) or f"ref_{idx:02d}"
                label = f"[{getattr(ref, 'marker', None) or ref_id_str}]"
                entries.append(
                    IRBibliographyEntry(
                        ref_id=ref_id_str,
                        citation_label=label,
                        formatted_reference=raw_txt,
                        authors=r_authors,
                        year=r_year,
                        title=r_title,
                        venue=r_venue,
                        doi_or_url=r_doi,
                        is_metadata_complete=is_complete,
                        metadata_limitation_note=lim_note,
                    )
                )

            if not self.ast.references:
                notes.append(
                    "Nota Bibliográfica: O documento original não apresenta uma secção de referências bibliográficas "
                    "estruturadas extraível ou é um documento técnico autónomo; nenhuma referência externa foi inventada."
                )
        else:
            doc_title = (self.dossier.document_title or "Documento Académico Analisado").strip()
            entries.append(
                IRBibliographyEntry(
                    ref_id="SOURCE_PRIMARY",
                    citation_label="[Fonte Primária]",
                    formatted_reference=(
                        f"«{doc_title}» [Dossier Académico ID: {self.dossier.document_id}]. "
                        "Metadados bibliográficos adicionais indisponíveis por ausência de AST."
                    ),
                    authors=[],
                    year=None,
                    title=doc_title,
                    venue=None,
                    doi_or_url=None,
                    is_metadata_complete=False,
                    metadata_limitation_note=(
                        "AST original não fornecida; apresentados exclusivamente os dados constantes no Dossier Académico."
                    ),
                )
            )
            notes.append(
                "Nota de Proveniência: A compilação bibliográfica limitou-se estritamente aos metadados verificados no Dossier Académico."
            )

        notes.append(
            "Política de Rigor Epistémico (Fase 5): Afirmações marcadas como SOURCE_FACT refletem factos explícitos "
            "da fonte original com indicação de página/parágrafo. Explicações assinaladas como MODEL_INFERENCE ou "
            "Exemplo Ilustrativo Hipotético representam desenvolvimento pedagógico e síntese analítica local, "
            "nunca sendo confundidas com dados empíricos originais."
        )
        return entries, notes

