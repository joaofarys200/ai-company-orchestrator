"""
JARVIS OS — Study Engine Phase 5: Reference and Provenance Renderer (Componente 5.7)
Apresentação rigorosa de proveniência, páginas de origem, distinção epistémica
e referências bibliográficas sem invenção de metadados.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialEvidenceRef
from services.study_document_generation.contracts import IRBibliographyEntry


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
        self.sec_to_pages: Dict[str, List[int]] = {}
        self.tables_by_id: Dict[str, Tuple[str, int]] = {}
        self.figures_by_id: Dict[str, Tuple[str, int]] = {}
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
                if para.page_number > 0:
                    self.para_to_page[para.paragraph_id] = para.page_number
                    self.valid_pages.add(para.page_number)
            for tbl in self.ast.tables:
                self.tables_by_id[tbl.table_id] = (tbl.caption or tbl.table_id, tbl.page_number)
                if tbl.page_number > 0:
                    self.valid_pages.add(tbl.page_number)
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
                if getattr(ref, "paragraph_id", None):
                    self.valid_paragraphs.add(ref.paragraph_id)
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

    def sanitize_evidence_refs(
        self,
        refs: Sequence[EditorialEvidenceRef],
        fallback_section_ids: Optional[Sequence[str]] = None,
    ) -> List[EditorialEvidenceRef]:
        """
        Filtra e valida referências de evidência contra o documento original,
        impedindo a citação de páginas, secções ou parágrafos inexistentes.
        """
        cleaned: List[EditorialEvidenceRef] = []
        seen: Set[Tuple[str, str, int, str]] = set()

        for r in refs or []:
            pid = str(r.paragraph_id or "").strip()
            sid = str(r.section_id or "").strip()
            pg = int(r.page_number) if r.page_number and int(r.page_number) > 0 else None

            if pid and self.valid_paragraphs and pid not in self.valid_paragraphs:
                pid = ""
            if sid and self.valid_sections and sid not in self.valid_sections:
                sid = ""
            if pg is not None and self.valid_pages and pg not in self.valid_pages:
                pg = None

            if pg is None and pid and pid in self.para_to_page:
                pg = self.para_to_page[pid]
            if pg is None and sid and sid in self.sec_to_pages and self.sec_to_pages[sid]:
                pg = self.sec_to_pages[sid][0]

            if not pid and not sid and pg is None:
                continue

            st = str(r.status or "SOURCE_FACT").strip()
            if st not in ("SOURCE_FACT", "MODEL_INFERENCE", "NOT_FOUND", "UNVERIFIED"):
                st = "SOURCE_FACT"

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
                    excerpt=str(r.excerpt or "")[:180],
                )
            )

        if not cleaned and fallback_section_ids:
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
                        status="SOURCE_FACT",
                        excerpt="",
                    )
                )
                break

        return cleaned

    def format_provenance_summary(
        self,
        epistemic_status: str,
        evidence_refs: Sequence[EditorialEvidenceRef],
        *,
        is_hypothetical_example: bool = False,
        source_table_refs: Optional[Sequence[str]] = None,
        source_figure_refs: Optional[Sequence[str]] = None,
    ) -> str:
        """
        Gera uma linha de proveniência clara e auditável para um bloco ou secção.
        Distingue explicitamente factos da fonte de inferências do modelo e de exemplos hipotéticos.
        """
        valid_refs = self.sanitize_evidence_refs(evidence_refs)
        pages = sorted({r.page_number for r in valid_refs if r.page_number and r.page_number > 0})
        paras = [r.paragraph_id for r in valid_refs if r.paragraph_id]
        paras_unique = list(dict.fromkeys(paras))[:5]
        secs = [r.section_id for r in valid_refs if r.section_id]
        secs_unique = list(dict.fromkeys(secs))[:3]

        if is_hypothetical_example:
            status_badge = "Elaboração Pedagógica (Exemplo Ilustrativo Hipotético — não constitui evidência empírica da fonte)"
        elif epistemic_status == "MODEL_INFERENCE":
            status_badge = "Inferência Analítica e Pedagógica (MODEL_INFERENCE) fundamentada na fonte"
        elif epistemic_status == "UNVERIFIED":
            status_badge = "Informação Não Verificada na Fonte (UNVERIFIED)"
        elif epistemic_status == "NOT_FOUND":
            status_badge = "Informação Ausente na Fonte (NOT_FOUND)"
        else:
            status_badge = "Facto Confirmado na Fonte Original (SOURCE_FACT)"

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
        if all_details:
            return f"Proveniência: {status_badge} | Origem: {' • '.join(all_details)}"
        return f"Proveniência: {status_badge}"

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

