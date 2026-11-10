"""
JARVIS OS — Study Engine Phase 5: Document Quality Assurance Engine (Componente 5.8)
Auditoria exaustiva do documento gerado e da Representação Intermédia nos 4 eixos obrigatórios:
- CONTENT_INTEGRITY
- VISUAL_INTEGRITY
- DOCUMENT_INTEGRITY
- PEDAGOGICAL_QUALITY
Classifica achados em BLOCKING_ERROR, WARNING e RECOMMENDATION.
Inspeciona fisicamente o ficheiro PDF gerado através do PyMuPDF (páginas, blocos, caracteres ilegíveis).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pymupdf

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_document_generation.contracts import (
    IRBlockKind,
    QAAxis,
    QASeverity,
    StudyDocumentIR,
    StudyDocumentQAFinding,
    StudyDocumentQAReport,
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
    ) -> StudyDocumentQAReport:
        findings: List[StudyDocumentQAFinding] = []
        axis_summaries: Dict[str, str] = {}

        # 1. Eixo 1: Integridade de Conteúdo
        content_findings = self._audit_content_integrity(ir, plan, dossier)
        findings.extend(content_findings)

        # 2. Eixo 2 & 3: Integridade Visual e Documental (Inspecionando o PDF Real)
        pdf_findings, pdf_meta = self._audit_pdf_file(pdf_path, ir)
        findings.extend(pdf_findings)

        # 3. Eixo 3: Integridade Documental adicional (DOCX, Metadados, TOC)
        doc_findings = self._audit_document_integrity(ir, docx_path)
        findings.extend(doc_findings)

        # 4. Eixo 4: Qualidade Pedagógica
        ped_findings = self._audit_pedagogical_quality(ir, plan)
        findings.extend(ped_findings)

        # Contabilização de severidades
        blocking_count = sum(1 for f in findings if f.severity == QASeverity.BLOCKING_ERROR.value)
        warnings_count = sum(1 for f in findings if f.severity == QASeverity.WARNING.value)
        recs_count = sum(1 for f in findings if f.severity == QASeverity.RECOMMENDATION.value)

        # Determinar status global
        if blocking_count > 0:
            val_status = "INVALID_BLOCKING"
            is_valid = False
        elif warnings_count > 0:
            val_status = "VALID_WITH_WARNINGS"
            is_valid = True
        else:
            val_status = "VALID"
            is_valid = True

        # Métricas de cobertura
        expected_chaps = len(plan.chapters)
        actual_chaps = len(ir.chapters)
        ch_cov = (actual_chaps / expected_chaps * 100.0) if expected_chaps > 0 else 100.0

        expected_secs = sum(len(c.sections) for c in plan.chapters)
        actual_secs = sum(len(c.sections) for c in ir.chapters)
        sec_cov = (actual_secs / expected_secs * 100.0) if expected_secs > 0 else 100.0

        visual_score = max(0.0, 100.0 - (len(pdf_findings) * 15.0))

        axis_summaries[QAAxis.CONTENT_INTEGRITY.value] = (
            f"Capítulos: {actual_chaps}/{expected_chaps} ({ch_cov:.1f}%), "
            f"Secções: {actual_secs}/{expected_secs} ({sec_cov:.1f}%)."
        )
        axis_summaries[QAAxis.VISUAL_INTEGRITY.value] = (
            f"Pontuação visual: {visual_score:.1f}/100. Páginas inspecionadas: {pdf_meta.get('total_pages', 0)}."
        )
        axis_summaries[QAAxis.DOCUMENT_INTEGRITY.value] = (
            f"TOC e Metadados: {'OK' if pdf_meta.get('toc_verified') else 'AVISO'}. "
            f"Texto selecionável: {'SIM' if pdf_meta.get('selectable_text') else 'NÃO'}."
        )
        axis_summaries[QAAxis.PEDAGOGICAL_QUALITY.value] = (
            f"Rastreabilidade de objetivos e conceitos: {'CONFORME' if not any(f.axis == QAAxis.PEDAGOGICAL_QUALITY.value and f.severity == QASeverity.BLOCKING_ERROR.value for f in findings) else 'INCOMPLETA'}."
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

        # 1. Verificar cobertura de capítulos
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

        # 2. Verificar duplicações de capítulos
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

        # 3. Verificar cobertura e identidade estrita de secções
        plan_sec_ids: List[str] = []
        for c in plan.chapters:
            for s in c.sections:
                plan_sec_ids.append(s.section_id)

        ir_sec_ids: List[str] = []
        for c in ir.chapters:
            for s in c.sections:
                ir_sec_ids.append(s.section_id)

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

        # 4. Verificar se existem secções vazias
        empty_secs: List[str] = []
        for c in ir.chapters:
            for s in c.sections:
                if not s.blocks or len(s.blocks) <= 1:  # Apenas título conta como vazia
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
    # Eixo 2 & 3: Integridade Visual e Física do PDF
    # -----------------------------------------------------------------------

    def _audit_pdf_file(
        self,
        pdf_path: Optional[str | Path],
        ir: StudyDocumentIR,
    ) -> Tuple[List[StudyDocumentQAFinding], Dict[str, Any]]:
        findings: List[StudyDocumentQAFinding] = []
        meta: Dict[str, Any] = {
            "total_pages": 0,
            "selectable_text": False,
            "toc_verified": False,
            "no_blank_pages": False,
            "no_orphan_headings": False,
            "no_clipping": False,
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

        # Verificar se o TOC nativo está presente
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
        has_clipping = False
        has_null_chars = False

        for p_idx, page in enumerate(doc, start=1):
            raw_text = page.get_text().strip()
            p_rect = page.rect
            p_height = p_rect.height
            p_width = p_rect.width

            # 1. Caracteres nulos ou ilegíveis (\x00 / \ufffd)
            if "\x00" in raw_text or "\ufffd" in raw_text:
                has_null_chars = True
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

            # 3. Deteção de títulos órfãos no fundo da página (keep-with-next violation)
            blocks = page.get_text("blocks")
            text_blocks = [b for b in blocks if len(b) >= 5 and b[4].strip()]
            if text_blocks:
                last_block = text_blocks[-1]
                b_y0 = last_block[1]
                b_text = last_block[4].strip()

                # Se o último bloco estiver nos últimos 10% da página e tiver aspeto de cabeçalho
                if b_y0 > (p_height * 0.90):
                    is_h = (
                        len(b_text) < 90
                        and (
                            b_text.isupper()
                            or b_text.startswith("Capítulo")
                            or any(b_text.startswith(f"{i}.") for i in range(1, 15))
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
                                message=f"Título órfão detetado no fundo da página {p_idx}: «{b_text[:50]}»",
                                page_numbers=[p_idx],
                            )
                        )

            # 4. Verificação de transbordo lateral (clipping)
            for b in text_blocks:
                b_x1 = b[2]
                if b_x1 > (p_width - 8.0):
                    has_clipping = True
                    findings.append(
                        StudyDocumentQAFinding(
                            finding_id=f"qa_pdf_clipping_p{p_idx}",
                            axis=QAAxis.VISUAL_INTEGRITY.value,
                            code="TEXT_CLIPPING",
                            severity=QASeverity.WARNING.value,
                            message=f"Texto excede a margem direita na página {p_idx} (x={b_x1:.1f}pt).",
                            page_numbers=[p_idx],
                        )
                    )

        doc.close()

        meta["selectable_text"] = has_any_text
        meta["no_blank_pages"] = not has_blank_page
        meta["no_orphan_headings"] = not has_orphan_heading
        meta["no_clipping"] = not has_clipping

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

    # -----------------------------------------------------------------------
    # Eixo 3: Integridade Documental adicional (DOCX, Metadados, TOC)
    # -----------------------------------------------------------------------

    def _audit_document_integrity(
        self,
        ir: StudyDocumentIR,
        docx_path: Optional[str | Path],
    ) -> List[StudyDocumentQAFinding]:
        findings: List[StudyDocumentQAFinding] = []

        # Verificar se o TOC do IR tem pelo menos capítulos e secções
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

        # Verificar presença de bibliografia
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

        # Se foi fornecido caminho de DOCX, validar integridade física do ficheiro DOCX
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
    # Eixo 4: Qualidade Pedagógica
    # -----------------------------------------------------------------------

    def _audit_pedagogical_quality(
        self,
        ir: StudyDocumentIR,
        plan: EditorialStudyPlan,
    ) -> List[StudyDocumentQAFinding]:
        findings: List[StudyDocumentQAFinding] = []

        # Verificar se os exemplos hipotéticos estão explicitamente rotulados
        for ch in ir.chapters:
            for sec in ch.sections:
                for b in sec.blocks:
                    if b.is_hypothetical_example:
                        if b.epistemic_status == "SOURCE_FACT":
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

        return findings

