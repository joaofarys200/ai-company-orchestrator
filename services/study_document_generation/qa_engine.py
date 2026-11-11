"""
JARVIS OS — Study Engine Phase 5: Document Quality Assurance Engine (Componente 5.8)
Auditoria exaustiva do documento gerado e da Representação Intermédia nos 4 eixos obrigatórios:
- CONTENT_INTEGRITY
- VISUAL_INTEGRITY
- DOCUMENT_INTEGRITY
- PEDAGOGICAL_QUALITY
Executa verificação física coordenada em todas as páginas do PDF via PyMuPDF (detetando
transbordo horizontal/vertical, clipping, texto não renderizado, perda silenciosa entre IR e PDF,
imagens fora da área útil, páginas em branco e títulos órfãos) e garante integridade epistémica.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pymupdf

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_document_generation.contracts import (
    ElaborationType,
    IRBlock,
    IRBlockKind,
    QAAxis,
    QASeverity,
    StudyDocumentIR,
    StudyDocumentQAFinding,
    StudyDocumentQAReport,
)
from services.study_document_generation.design_system import (
    AcademicDesignSystem,
    DesignStyleProfile,
)


class DocumentQualityAssuranceEngine:
    """
    Componente 5.8 — Document Quality Assurance Engine.
    Executa verificação multidimensional do documento de estudo final.
    """

    def audit(
        self,
        ir: StudyDocumentIR,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        pdf_path: Optional[str | Path] = None,
        docx_path: Optional[str | Path] = None,
        *,
        design_profile: Optional[DesignStyleProfile] = None,
        render_result: Optional[Any] = None,
    ) -> StudyDocumentQAReport:
        findings: List[StudyDocumentQAFinding] = []
        axis_summaries: Dict[str, str] = {}
        profile = design_profile or AcademicDesignSystem.get_profile(
            getattr(ir.metadata, "design_profile_id", None)
        )

        # 0. Verificar erros explícitos de overflow reportados pelo compositor durante a renderização
        if render_result is not None:
            overflows = getattr(render_result, "render_overflow_errors", []) or []
            if overflows:
                findings.append(
                    StudyDocumentQAFinding(
                        finding_id="qa_render_overflow_loss",
                        axis=QAAxis.DOCUMENT_INTEGRITY.value,
                        code="RENDER_OVERFLOW_LOSS",
                        severity=QASeverity.BLOCKING_ERROR.value,
                        message=(
                            f"O compositor PDF reportou {len(overflows)} evento(s) de overflow em insert_textbox() "
                            "com risco de truncagem de conteúdo."
                        ),
                        affected_elements=[str(o.get("block_id") or "") for o in overflows[:10]],
                        recommendation="Fragmentar os blocos extensos antes de renderizar ou ajustar altura alocada.",
                    )
                )

        # 1. Eixo 1: Integridade de Conteúdo
        content_findings = self._audit_content_integrity(ir, plan, dossier)
        findings.extend(content_findings)

        # 2. Eixo 2 & 3: Integridade Visual, Física e Recuperação Integral do PDF
        pdf_findings, pdf_meta = self._audit_pdf_file(pdf_path, ir, profile)
        findings.extend(pdf_findings)

        # 3. Eixo 3: Integridade Documental adicional (DOCX, Metadados, TOC)
        doc_findings = self._audit_document_integrity(ir, docx_path, pdf_meta)
        findings.extend(doc_findings)

        # 4. Eixo 4: Qualidade Pedagógica & Rigor Epistémico
        ped_findings = self._audit_pedagogical_quality(ir, plan)
        findings.extend(ped_findings)

        blocking_count = sum(1 for f in findings if f.severity == QASeverity.BLOCKING_ERROR.value)
        warnings_count = sum(1 for f in findings if f.severity == QASeverity.WARNING.value)
        recs_count = sum(1 for f in findings if f.severity == QASeverity.RECOMMENDATION.value)

        if blocking_count > 0:
            val_status = "INVALID_BLOCKING"
            is_valid = False
        elif warnings_count > 0:
            val_status = "VALID_WITH_WARNINGS"
            is_valid = True
        else:
            val_status = "VALID"
            is_valid = True

        expected_chaps = len(plan.chapters)
        actual_chaps = len(ir.chapters)
        ch_cov = (actual_chaps / expected_chaps * 100.0) if expected_chaps > 0 else 100.0

        expected_secs = sum(len(c.sections) for c in plan.chapters)
        actual_secs = sum(len(c.sections) for c in ir.chapters)
        sec_cov = (actual_secs / expected_secs * 100.0) if expected_secs > 0 else 100.0

        visual_findings_cnt = sum(
            1 for f in pdf_findings if f.severity in (QASeverity.BLOCKING_ERROR.value, QASeverity.WARNING.value)
        )
        visual_score = max(0.0, 100.0 - (visual_findings_cnt * 15.0))

        axis_summaries[QAAxis.CONTENT_INTEGRITY.value] = (
            f"Capítulos: {actual_chaps}/{expected_chaps} ({ch_cov:.1f}%), "
            f"Secções: {actual_secs}/{expected_secs} ({sec_cov:.1f}%)."
        )
        axis_summaries[QAAxis.VISUAL_INTEGRITY.value] = (
            f"Pontuação visual: {visual_score:.1f}/100. Páginas inspecionadas: {pdf_meta.get('total_pages', 0)}."
        )
        axis_summaries[QAAxis.DOCUMENT_INTEGRITY.value] = (
            f"TOC e Metadados: {'OK' if pdf_meta.get('toc_verified') else 'AVISO'}. "
            f"Texto selecionável: {'SIM' if pdf_meta.get('selectable_text') else 'NÃO'}. "
            f"Recuperação integral IR->PDF: {'SIM' if pdf_meta.get('ir_completeness_verified') else 'FALHA'}."
        )
        axis_summaries[QAAxis.PEDAGOGICAL_QUALITY.value] = (
            f"Rastreabilidade epistémica e distinção factos/inferências: "
            f"{'CONFORME' if not any(f.axis == QAAxis.PEDAGOGICAL_QUALITY.value and f.severity == QASeverity.BLOCKING_ERROR.value for f in findings) else 'INCOMPLETA'}."
        )

        return StudyDocumentQAReport(
            validation_status=val_status,
            is_valid=is_valid,
            blocking_errors_count=blocking_count,
            warnings_count=warnings_count,
            recommendations_count=recs_count,
            chapter_coverage_pct=round(ch_cov, 1),
            section_coverage_pct=round(sec_cov, 1),
            visual_integrity_score=round(visual_score, 1),
            total_pages_inspected=pdf_meta.get("total_pages", 0),
            selectable_text_verified=pdf_meta.get("selectable_text", False),
            toc_verified=pdf_meta.get("toc_verified", False),
            no_blank_pages_verified=pdf_meta.get("no_blank_pages", False),
            no_orphan_headings_verified=pdf_meta.get("no_orphan_headings", False),
            no_text_clipping_verified=pdf_meta.get("no_clipping", False),
            docx_verified=pdf_meta.get("docx_verified", False),
            axis_summaries=axis_summaries,
            findings=findings,
        )

    # -----------------------------------------------------------------------
    # Eixo 1: Integridade de Conteúdo
    # -----------------------------------------------------------------------

    def _audit_content_integrity(
        self,
        ir: StudyDocumentIR,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
    ) -> List[StudyDocumentQAFinding]:
        findings: List[StudyDocumentQAFinding] = []

        plan_ch_ids = [c.chapter_id for c in plan.chapters]
        ir_ch_ids = [c.chapter_id for c in ir.chapters]

        missing_chaps = set(plan_ch_ids) - set(ir_ch_ids)
        if missing_chaps:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_content_missing_chaps",
                    axis=QAAxis.CONTENT_INTEGRITY.value,
                    code="MISSING_CHAPTERS",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Capítulos obrigatórios planeados não constam no documento final: {sorted(missing_chaps)}",
                    affected_elements=sorted(missing_chaps),
                    recommendation="Regerar capítulos em falta através do orchestrator de checkpoints.",
                )
            )

        seen_ch: Set[str] = set()
        dup_ch: List[str] = []
        for cid in ir_ch_ids:
            if cid in seen_ch:
                dup_ch.append(cid)
            seen_ch.add(cid)
        if dup_ch:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_content_dup_chaps",
                    axis=QAAxis.CONTENT_INTEGRITY.value,
                    code="DUPLICATE_CHAPTERS",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Identificadores de capítulo duplicados detetados: {dup_ch}",
                    affected_elements=dup_ch,
                )
            )

        plan_sec_ids: List[str] = [s.section_id for c in plan.chapters for s in c.sections]
        ir_sec_ids: List[str] = [s.section_id for c in ir.chapters for s in c.sections]

        missing_secs = set(plan_sec_ids) - set(ir_sec_ids)
        if missing_secs:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_content_missing_secs",
                    axis=QAAxis.CONTENT_INTEGRITY.value,
                    code="MISSING_SECTIONS",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Secções obrigatórias planeadas ausentes no documento final: {sorted(missing_secs)}",
                    affected_elements=sorted(missing_secs),
                )
            )

        seen_sec: Set[str] = set()
        dup_sec: List[str] = []
        for sid in ir_sec_ids:
            if sid in seen_sec:
                dup_sec.append(sid)
            seen_sec.add(sid)
        if dup_sec:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_content_dup_secs",
                    axis=QAAxis.CONTENT_INTEGRITY.value,
                    code="DUPLICATE_SECTIONS",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Identificadores de secção duplicados detetados: {dup_sec}",
                    affected_elements=dup_sec,
                )
            )

        empty_secs: List[str] = []
        for c in ir.chapters:
            for s in c.sections:
                if not s.blocks or len(s.blocks) <= 1:
                    empty_secs.append(s.section_id)
        if empty_secs:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_content_empty_secs",
                    axis=QAAxis.CONTENT_INTEGRITY.value,
                    code="EMPTY_SECTIONS",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Secções sem conteúdo desenvolvido detetadas: {empty_secs}",
                    affected_elements=empty_secs,
                    recommendation="Gerar conteúdo fundamentado para as secções vazias.",
                )
            )

        return findings

    # -----------------------------------------------------------------------
    # Eixo 2 & 3: Inspeção Física, Coordenadas e Completude IR -> PDF
    # -----------------------------------------------------------------------

    def _audit_pdf_file(
        self,
        pdf_path: Optional[str | Path],
        ir: StudyDocumentIR,
        profile: DesignStyleProfile,
    ) -> Tuple[List[StudyDocumentQAFinding], Dict[str, Any]]:
        findings: List[StudyDocumentQAFinding] = []
        meta: Dict[str, Any] = {
            "total_pages": 0,
            "selectable_text": False,
            "toc_verified": False,
            "no_blank_pages": False,
            "no_orphan_headings": False,
            "no_clipping": False,
            "ir_completeness_verified": False,
            "docx_verified": False,
        }

        if not pdf_path or not os.path.exists(pdf_path):
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_pdf_not_found",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="PDF_FILE_MISSING",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Ficheiro PDF final não encontrado no disco: {pdf_path}",
                )
            )
            return findings, meta

        try:
            doc = pymupdf.open(str(pdf_path))
        except Exception as exc:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_pdf_corrupted",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="PDF_CORRUPTED",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Ficheiro PDF corrompido ou ilegível: {exc}",
                )
            )
            return findings, meta

        geo = profile.geometry
        total_pages = len(doc)
        meta["total_pages"] = total_pages

        if total_pages < 2:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_pdf_insufficient_pages",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="PDF_TOO_SHORT",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=f"Documento PDF com extensão anormalmente reduzida ({total_pages} página).",
                )
            )

        try:
            pdf_toc = doc.get_toc()
            if pdf_toc and len(pdf_toc) >= 2:
                meta["toc_verified"] = True
            else:
                findings.append(
                    StudyDocumentQAFinding(
                        finding_id="qa_pdf_toc_empty",
                        axis=QAAxis.DOCUMENT_INTEGRITY.value,
                        code="PDF_TOC_MISSING",
                        severity=QASeverity.WARNING.value,
                        message="Árvore de marcadores PDF (TOC) ausente ou com menos de 2 entradas.",
                    )
                )
        except Exception:
            pass

        has_any_text = False
        has_blank_page = False
        has_orphan_heading = False
        has_clipping_or_overflow = False
        extracted_pages_text: List[str] = []

        # Limites úteis físicos com tolerância mínima para kerning (em pt)
        tol = 5.0
        min_x = geo.margin_left_pt - tol
        max_x = geo.page_width_pt - geo.margin_right_pt + tol
        min_body_y = geo.margin_top_pt - 8.0
        max_body_y = geo.max_content_y_pt + tol

        for p_idx, page in enumerate(doc, start=1):
            raw_text = page.get_text().strip()
            extracted_pages_text.append(raw_text)
            p_rect = page.rect
            p_height = p_rect.height
            p_width = p_rect.width

            # 1. Caracteres nulos ou ilegíveis (\x00 / \ufffd)
            if "\x00" in raw_text or "\ufffd" in raw_text:
                findings.append(
                    StudyDocumentQAFinding(
                        finding_id=f"qa_pdf_null_chars_p{p_idx}",
                        axis=QAAxis.VISUAL_INTEGRITY.value,
                        code="ILLEGIBLE_CHARACTERS",
                        severity=QASeverity.BLOCKING_ERROR.value,
                        message=f"Caracteres nulos ou glifos corrompidos detetados na página {p_idx}.",
                        page_numbers=[p_idx],
                    )
                )

            # 2. Deteção de páginas em branco
            if not raw_text or len(raw_text.replace("\n", "").strip()) < 10:
                has_blank_page = True
                findings.append(
                    StudyDocumentQAFinding(
                        finding_id=f"qa_pdf_blank_page_p{p_idx}",
                        axis=QAAxis.VISUAL_INTEGRITY.value,
                        code="BLANK_PAGE_DETECTED",
                        severity=QASeverity.BLOCKING_ERROR.value,
                        message=f"Página {p_idx} está completamente em branco.",
                        page_numbers=[p_idx],
                    )
                )
                continue

            has_any_text = True

            # 3. Inspeção detalhada por bloco/linha/bbox físico via `get_text("dict")`
            p_dict = page.get_text("dict")
            content_line_boxes: List[Tuple[Tuple[float, float, float, float], str]] = []

            for blk in p_dict.get("blocks", []):
                if blk.get("type") != 0:
                    continue
                for line in blk.get("lines", []):
                    lbbox = line.get("bbox") or (0.0, 0.0, 0.0, 0.0)
                    l_x0, l_y0, l_x1, l_y1 = lbbox
                    l_txt = "".join(sp.get("text", "") for sp in line.get("spans", [])).strip()
                    if not l_txt:
                        continue

                    # Verificar se pertence à banda intencional de cabeçalho/rodapé ou capa
                    is_running_footer = (
                        l_y0 >= geo.footer_y_pt - 12.0
                        and l_y1 <= p_height - 12.0
                        and ("Página " in l_txt or "JARVIS OS" in l_txt or "Proveniência" in l_txt or (ir.header_footer.footer_left[:12] in l_txt if ir.header_footer.footer_left else False))
                    )
                    is_running_header = (
                        l_y0 <= geo.header_y_pt + 10.0
                        and l_y1 <= geo.margin_top_pt - 4.0
                        and (p_idx > 1)
                    )
                    is_cover_banner = (p_idx == 1 and l_y0 >= 28.0 and l_y1 <= geo.margin_top_pt + 10.0)

                    # Verificar limites horizontais em TODOS os elementos (incluindo cabeçalhos/rodapés)
                    if l_x0 < min_x or l_x1 > max_x or l_x1 > p_width - 4.0:
                        has_clipping_or_overflow = True
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_pdf_h_overflow_p{p_idx}_{int(l_y0)}",
                                axis=QAAxis.VISUAL_INTEGRITY.value,
                                code="TEXT_CLIPPING",
                                severity=QASeverity.BLOCKING_ERROR.value,
                                message=(
                                    f"Transbordo horizontal na página {p_idx} (x=[{l_x0:.1f}, {l_x1:.1f}] "
                                    f"fora de [{min_x:.1f}, {max_x:.1f}]): «{l_txt[:40]}»"
                                ),
                                page_numbers=[p_idx],
                            )
                        )

                    if is_running_footer or is_running_header or is_cover_banner:
                        continue

                    content_line_boxes.append(((l_x0, l_y0, l_x1, l_y1), l_txt))

                    # Verificar limites verticais da área útil do corpo
                    if l_y1 > max_body_y or l_y0 < (26.0 if p_idx == 1 else min_body_y):
                        has_clipping_or_overflow = True
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_pdf_v_overflow_p{p_idx}_{int(l_y0)}",
                                axis=QAAxis.VISUAL_INTEGRITY.value,
                                code="VERTICAL_OVERFLOW",
                                severity=QASeverity.BLOCKING_ERROR.value,
                                message=(
                                    f"Conteúdo fora dos limites verticais úteis na página {p_idx} "
                                    f"(y=[{l_y0:.1f}, {l_y1:.1f}] fora de [{min_body_y:.1f}, {max_body_y:.1f}]): "
                                    f"«{l_txt[:40]}»"
                                ),
                                page_numbers=[p_idx],
                            )
                        )

            # 4. Verificação de limites físicos de imagens integradas (`get_image_info`)
            try:
                for img_idx, im in enumerate(page.get_image_info(xrefs=True)):
                    ibbox = im.get("bbox") or (0.0, 0.0, 0.0, 0.0)
                    ix0, iy0, ix1, iy1 = ibbox
                    if ix0 < min_x or ix1 > max_x or iy0 < min_body_y or iy1 > max_body_y:
                        has_clipping_or_overflow = True
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_pdf_img_bounds_p{p_idx}_{img_idx}",
                                axis=QAAxis.VISUAL_INTEGRITY.value,
                                code="VISUAL_OUT_OF_BOUNDS",
                                severity=QASeverity.BLOCKING_ERROR.value,
                                message=(
                                    f"Elemento visual fora da área útil na página {p_idx} "
                                    f"(bbox=[{ix0:.1f}, {iy0:.1f}, {ix1:.1f}, {iy1:.1f}])."
                                ),
                                page_numbers=[p_idx],
                            )
                        )
            except Exception:
                pass

            # 5. Títulos órfãos no fundo da página de conteúdo
            if p_idx > 1 and content_line_boxes:
                content_line_boxes.sort(key=lambda pair: pair[0][1])
                last_bbox, last_txt = content_line_boxes[-1]
                if last_bbox[1] > (geo.max_content_y_pt - 52.0):
                    is_h = (
                        len(last_txt) < 90
                        and (
                            last_txt.startswith("Capítulo")
                            or re.match(r"^\d+(\.\d+)+\s*[—\-]", last_txt) is not None
                        )
                    )
                    if is_h:
                        has_orphan_heading = True
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_pdf_orphan_heading_p{p_idx}",
                                axis=QAAxis.VISUAL_INTEGRITY.value,
                                code="ORPHAN_HEADING_AT_BOTTOM",
                                severity=QASeverity.WARNING.value,
                                message=f"Título órfão detetado no fundo da página {p_idx}: «{last_txt[:50]}»",
                                page_numbers=[p_idx],
                            )
                        )

        doc.close()

        # 6. Verificar recuperabilidade integral do conteúdo da IR no PDF extraído
        missing_ir_chunks = self._verify_ir_content_in_pdf_text(ir, "\n".join(extracted_pages_text))
        if missing_ir_chunks:
            has_clipping_or_overflow = True
            meta["ir_completeness_verified"] = False
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_pdf_content_lost",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="CONTENT_LOST_IN_PDF",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message=(
                        f"{len(missing_ir_chunks)} bloco(s) ou segmento(s) esperados da IR estão ausentes no texto extraído do PDF "
                        f"(possível truncagem silenciosa): {missing_ir_chunks[:5]}"
                    ),
                    affected_elements=missing_ir_chunks[:10],
                )
            )
        else:
            meta["ir_completeness_verified"] = has_any_text

        meta["selectable_text"] = has_any_text
        meta["no_blank_pages"] = not has_blank_page
        meta["no_orphan_headings"] = not has_orphan_heading
        meta["no_clipping"] = not has_clipping_or_overflow

        if not has_any_text:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_pdf_no_selectable_text",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="NO_SELECTABLE_TEXT",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message="O ficheiro PDF não contém texto selecionável (renderização vazia).",
                )
            )

        return findings, meta

    def _verify_ir_content_in_pdf_text(self, ir: StudyDocumentIR, extracted_pdf_text: str) -> List[str]:
        """
        Compara o texto esperado na StudyDocumentIR (objetivos, TOC, capítulos, parágrafos extensos,
        listas, caixas pedagógicas, linhas de tabelas e bibliografia) com o texto extraído do PDF.
        """
        if not extracted_pdf_text or not extracted_pdf_text.strip():
            return ["<PDF_EMPTY>"]

        def _norm(txt: str) -> str:
            s = (
                AcademicDesignSystem.sanitize_text_for_font(txt)
                .replace("\u2010", "-")
                .replace("\u2011", "-")
                .replace("\xad", "-")
                .replace("\u2212", "-")
                .replace("\xa0", " ")
            )
            return re.sub(r"\s+", " ", s).strip().lower()

        norm_pdf = _norm(extracted_pdf_text)
        # Unifica pontuação que possa ter quebrado de linha após URL/token longo (ex.: "html2012\n.")
        norm_pdf_punct = re.sub(r"\s+([.,;:!?)])", r"\1", norm_pdf)
        norm_pdf_compact = norm_pdf.replace(" ", "")
        missing: List[str] = []

        def _segment_present(seg: str) -> bool:
            s_n = _norm(seg)
            if len(s_n) < 4:
                return True
            if s_n in norm_pdf or re.sub(r"\s+([.,;:!?)])", r"\1", s_n) in norm_pdf_punct:
                return True
            words = [w for w in s_n.split() if len(w) >= 2]
            if not words:
                return True
            if len(words) == 1:
                return words[0] in norm_pdf_compact
            if len(words) <= 5:
                return all(
                    (w in norm_pdf) or (len(w) >= 30 and w in norm_pdf_compact)
                    for w in words
                )
            for i in range(0, len(words) - 3, max(1, len(words) // 4)):
                probe = " ".join(words[i : i + 4])
                if probe in norm_pdf or probe in norm_pdf_punct:
                    continue
                if (
                    any(len(w) >= 30 for w in words[i : i + 4])
                    and probe.replace(" ", "") in norm_pdf_compact
                ):
                    continue
                return False
            return True

        def _check_long_text(label: str, raw_text: str) -> None:
            clean = _norm(raw_text)
            if len(clean) < 5:
                return
            if len(clean) <= 90:
                if not _segment_present(clean):
                    missing.append(f"{label}: {raw_text[:45]}")
                return
            # Para textos extensos/multi-página: validar início, meio e FIM absoluto
            words = clean.split()
            n_w = len(words)
            if n_w <= 12:
                if not _segment_present(clean):
                    missing.append(f"{label}: {raw_text[:45]}")
                return
            anchors = [
                ("início", " ".join(words[:7])),
                ("meio", " ".join(words[n_w // 2 : min(n_w, n_w // 2 + 7)])),
                ("fim", " ".join(words[max(0, n_w - 7) :])),
            ]
            for pos_lbl, anc in anchors:
                if not _segment_present(anc):
                    missing.append(f"{label} ({pos_lbl}): {anc[:40]}")
                    break

        # 1. Todos os objetivos de aprendizagem
        for idx, obj in enumerate(ir.learning_objectives):
            _check_long_text(f"Objetivo[{idx+1}]", obj)

        # 2. Todas as entradas do índice
        for entry in ir.toc_entries:
            _check_long_text(f"TOC[{entry.entry_id}]", entry.title)

        # 3. Todos os blocos de overview, capítulos, secções e síntese global
        all_blocks: List[IRBlock] = list(ir.executive_overview_blocks)
        for ch in ir.chapters:
            all_blocks.extend(ch.intro_blocks)
            for sec in ch.sections:
                all_blocks.extend(sec.blocks)
            all_blocks.extend(ch.synthesis_blocks)
        all_blocks.extend(ir.global_synthesis_blocks)

        for b in all_blocks:
            if b.kind == IRBlockKind.HEADING.value and b.title:
                _check_long_text(f"Heading[{b.block_id}]", b.title)
            elif b.kind == IRBlockKind.PARAGRAPH.value:
                for p_i, p in enumerate(b.paragraphs):
                    _check_long_text(f"Parágrafo[{b.block_id}#{p_i}]", p)
            elif b.kind in (IRBlockKind.BULLET_LIST.value, IRBlockKind.NUMBERED_LIST.value):
                for l_i, it in enumerate(b.items):
                    _check_long_text(f"Lista[{b.block_id}#{l_i}]", it)
            elif b.kind == IRBlockKind.CALLOUT_BOX.value:
                if b.title:
                    _check_long_text(f"CaixaTítulo[{b.block_id}]", b.title)
                for p_i, p in enumerate(b.paragraphs):
                    _check_long_text(f"CaixaParágrafo[{b.block_id}#{p_i}]", p)
                for l_i, it in enumerate(b.items):
                    _check_long_text(f"CaixaItem[{b.block_id}#{l_i}]", it)
            elif b.kind == IRBlockKind.TABLE.value:
                for h_txt in b.table_headers:
                    _check_long_text(f"TabelaHdr[{b.block_id}]", h_txt)
                for r_i, row in enumerate(b.table_rows):
                    for c_i, cell in enumerate(row):
                        _check_long_text(f"Tabela[{b.block_id} r{r_i}c{c_i}]", str(cell))

        # 4. Todas as entradas bibliográficas
        for b_i, bib in enumerate(ir.bibliography):
            _check_long_text(f"Bib[{b_i+1}]", bib.formatted_reference)

        return missing

    # -----------------------------------------------------------------------
    # Eixo 3: Integridade Documental adicional (DOCX, Metadados, TOC)
    # -----------------------------------------------------------------------

    def _audit_document_integrity(
        self,
        ir: StudyDocumentIR,
        docx_path: Optional[str | Path],
        pdf_meta: Dict[str, Any],
    ) -> List[StudyDocumentQAFinding]:
        findings: List[StudyDocumentQAFinding] = []

        if not ir.toc_entries:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_ir_toc_empty",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="IR_TOC_EMPTY",
                    severity=QASeverity.BLOCKING_ERROR.value,
                    message="A representação intermédia não contém entradas no Índice (toc_entries vazio).",
                )
            )

        if not ir.bibliography:
            findings.append(
                StudyDocumentQAFinding(
                    finding_id="qa_ir_bib_empty",
                    axis=QAAxis.DOCUMENT_INTEGRITY.value,
                    code="BIBLIOGRAPHY_EMPTY",
                    severity=QASeverity.WARNING.value,
                    message="Secção de referências bibliográficas vazia na representação intermédia.",
                    recommendation="Incluir pelo menos a entrada da Fonte Primária verificada.",
                )
            )

        if docx_path:
            p = Path(docx_path)
            if not p.exists() or p.stat().st_size == 0:
                findings.append(
                    StudyDocumentQAFinding(
                        finding_id="qa_docx_missing",
                        axis=QAAxis.DOCUMENT_INTEGRITY.value,
                        code="DOCX_FILE_MISSING",
                        severity=QASeverity.WARNING.value,
                        message=f"Ficheiro DOCX exportado ausente ou com 0 bytes: {docx_path}",
                    )
                )
            else:
                try:
                    from docx import Document
                    d_obj = Document(str(p))
                    if len(d_obj.paragraphs) < 5:
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id="qa_docx_empty",
                                axis=QAAxis.DOCUMENT_INTEGRITY.value,
                                code="DOCX_CONTENT_EMPTY",
                                severity=QASeverity.WARNING.value,
                                message="O documento DOCX gerado possui menos de 5 parágrafos.",
                            )
                        )
                    else:
                        pdf_meta["docx_verified"] = True
                except Exception as d_exc:
                    findings.append(
                        StudyDocumentQAFinding(
                            finding_id="qa_docx_corrupted",
                            axis=QAAxis.DOCUMENT_INTEGRITY.value,
                            code="DOCX_CORRUPTED",
                            severity=QASeverity.WARNING.value,
                            message=f"Ficheiro DOCX não pôde ser aberto: {d_exc}",
                        )
                    )

        return findings

    # -----------------------------------------------------------------------
    # Eixo 4: Qualidade Pedagógica & Integridade Epistémica
    # -----------------------------------------------------------------------

    def _audit_pedagogical_quality(
        self,
        ir: StudyDocumentIR,
        plan: EditorialStudyPlan,
    ) -> List[StudyDocumentQAFinding]:
        findings: List[StudyDocumentQAFinding] = []

        for ch in ir.chapters:
            for sec in ch.sections:
                for b in sec.blocks:
                    if b.is_hypothetical_example and b.epistemic_status == "SOURCE_FACT":
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_ped_hyp_fact_{b.block_id}",
                                axis=QAAxis.PEDAGOGICAL_QUALITY.value,
                                code="HYPOTHETICAL_LABELED_AS_FACT",
                                severity=QASeverity.BLOCKING_ERROR.value,
                                message=(
                                    f"O bloco '{b.title}' em {sec.section_id} é um exemplo hipotético, "
                                    "mas foi incorretamente classificado como SOURCE_FACT (violação da Regra 4.2 / 5.2)."
                                ),
                                affected_elements=[b.block_id, sec.section_id],
                            )
                        )
                    if (
                        b.epistemic_status == "SOURCE_FACT"
                        and b.elaboration_type in (
                            ElaborationType.HYPOTHETICAL_EXAMPLE.value,
                            ElaborationType.UNVERIFIED_CLAIM.value,
                        )
                    ):
                        findings.append(
                            StudyDocumentQAFinding(
                                finding_id=f"qa_epistemic_mismatch_{b.block_id}",
                                axis=QAAxis.PEDAGOGICAL_QUALITY.value,
                                code="EPISTEMIC_ELABORATION_CONFLICT",
                                severity=QASeverity.BLOCKING_ERROR.value,
                                message=(
                                    f"Conflito epistémico no bloco '{b.block_id}': "
                                    f"epistemic_status='SOURCE_FACT' incompatível com elaboration_type='{b.elaboration_type}'."
                                ),
                                affected_elements=[b.block_id, sec.section_id],
                            )
                        )

        return findings
