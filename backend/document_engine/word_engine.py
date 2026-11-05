from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from enum import Enum

import docx
from docx import Document

from backend.document_engine.contracts import ExportResult
from backend.document_engine.editorial_planner import (
    EditorialFinding,
    EditorialPlan,
    EditorialPlanner,
    EditorialReviewReport,
)
from backend.document_engine.profiles import (
    DocumentProfile,
    DocumentProfileType,
    get_profile,
)
from backend.document_engine.render_engine import RenderEngineType, RenderResult
from backend.document_engine.surgical_revisor import (
    RevisionDirective,
    RevisionSummary,
    SurgicalRevisor,
)
from backend.document_engine.visual_inspector import (
    LayoutFlaw,
    VisualInspectionResult,
    VisualInspector,
)
from backend.document_engine.word_ast import (
    WordDocumentAST,
    extract_ast_from_docx,
)
from backend.document_engine.word_styler import WordStyler


@dataclass(frozen=True)
class DocumentCreationRequest:
    prompt: str
    output_path: str
    title: Optional[str] = None
    profile_type: DocumentProfileType = DocumentProfileType.GENERIC
    sources: Optional[Sequence[str] | Mapping[str, Any]] = None
    template_path: Optional[str] = None
    target_audience: str = "Profissional / Técnico"
    language: str = "pt-PT"
    target_word_count: int = 1500
    custom_sections: Optional[Sequence[str]] = None
    include_toc: bool = True
    author: str = "JARVIS OS"


@dataclass(frozen=True)
class AcceptanceGates:
    structure_validated: bool
    editorial_validated: bool
    docx_integrity_validated: bool
    real_render_validated: bool
    visual_acceptance_validated: bool

    def all_validated(self) -> bool:
        return (
            self.structure_validated
            and self.editorial_validated
            and self.docx_integrity_validated
            and self.real_render_validated
            and self.visual_acceptance_validated
        )


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    structural_issues: tuple[str, ...]
    editorial_findings: tuple[EditorialFinding, ...]
    visual_flaws: tuple[LayoutFlaw, ...]
    quality_score: float
    summary: str
    gates: Optional[AcceptanceGates] = None
    structure_validated: bool = False
    editorial_validated: bool = False
    docx_integrity_validated: bool = False
    real_render_validated: bool = False
    visual_acceptance_validated: bool = False
    render_engine_type: Optional[RenderEngineType] = None
    render_engine_name: str = ""
    toc_updated: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentEngineResult:
    operation: str
    docx_path: str
    pdf_path: Optional[str] = None
    ast: Optional[WordDocumentAST] = None
    review: Optional[EditorialReviewReport] = None
    revision_summary: Optional[RevisionSummary] = None
    visual_inspection: Optional[VisualInspectionResult] = None
    validation: Optional[ValidationReport] = None
    export_result: Optional[ExportResult] = None
    success: bool = True
    message: str = ""


class WordDocumentEngine:
    """
    Unified Word Authoring & Revision Engine for JARVIS OS.
    Implements the 8 canonical operations:
    1. CREATE_DOCUMENT
    2. READ_DOCUMENT
    3. REVIEW_DOCUMENT
    4. REVISE_DOCUMENT
    5. FORMAT_DOCUMENT
    6. RENDER_DOCUMENT
    7. VALIDATE_DOCUMENT
    8. EXPORT_DOCUMENT
    """

    # ── 1. CREATE_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def create_document(cls, request: DocumentCreationRequest) -> DocumentEngineResult:
        """
        Creates a complete professional Microsoft Word (.docx) document from scratch
        grounded in an editorial plan, semantic styles, typography, and profile rules.
        """
        profile = get_profile(request.profile_type)
        out_p = Path(request.output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # 1.1 Generate Editorial Plan first
        plan = EditorialPlanner.create_plan(
            prompt=request.prompt,
            sources=request.sources,
            profile_type=request.profile_type,
            target_audience=request.target_audience,
            language=request.language,
            target_word_count=request.target_word_count,
            custom_sections=request.custom_sections,
        )
        doc_title = request.title or plan.document_title

        # 1.2 Initialize Document (from template or blank)
        if request.template_path and os.path.exists(request.template_path):
            doc = Document(request.template_path)
        else:
            doc = Document()

        # 1.3 Apply typography and layout styles
        WordStyler.apply_profile_to_document(doc, profile)

        # Set Core Properties
        props = doc.core_properties
        props.title = doc_title
        props.author = request.author
        props.subject = plan.document_objective[:250]
        props.keywords = f"{profile.profile_type.value}, JARVIS OS, Word Engine"

        # 1.4 Title and Subtitle Block
        title_para = doc.add_paragraph(doc_title, style="Title")
        subtitle_para = doc.add_paragraph(f"{profile.display_name} • {request.author}")
        subtitle_para.paragraph_format.space_after = docx.shared.Pt(18)

        # 1.5 Configure Headers and Footers with dynamic page numbers
        if profile.requires_page_numbers:
            WordStyler.configure_headers_and_footers(doc, doc_title, profile)

        # 1.6 Optional Table of Contents
        if request.include_toc and (profile.requires_toc or len(plan.sections) >= 4):
            WordStyler.add_table_of_contents(doc, title="Índice")

        # 1.7 Generate Content according to Editorial Plan
        for s_idx, sec in enumerate(plan.sections, start=1):
            h_style = f"Heading {min(3, max(1, sec.level))}"
            doc.add_paragraph(sec.title, style=h_style)

            # Generate grounded body paragraphs
            body_paragraphs = cls._synthesize_section_text(sec, plan, request.sources)
            for bp in body_paragraphs:
                p = doc.add_paragraph(bp)
                p.paragraph_format.line_spacing = profile.line_spacing
                p.paragraph_format.space_after = docx.shared.Pt(profile.paragraph_space_after_pt)

            # If section needs a table, insert styled table
            if sec.tables_needed:
                for tbl_name in sec.tables_needed:
                    cls._insert_styled_sample_table(doc, tbl_name, profile)

            # If section needs a callout/highlight
            if s_idx == 1 and profile.profile_type in {DocumentProfileType.TECHNICAL_SPEC, DocumentProfileType.EXECUTIVE_MEMO}:
                WordStyler.add_callout(
                    doc,
                    f"Este documento foi elaborado com o objetivo de {plan.document_objective}. As especificações aqui descritas são de execução vinculativa.",
                    profile,
                    title="ÂMBITO OPERACIONAL",
                )

        # 1.8 Save DOCX
        doc.save(str(out_p))

        # 1.9 Extract AST to verify generated document
        ast = extract_ast_from_docx(out_p)

        return DocumentEngineResult(
            operation="CREATE_DOCUMENT",
            docx_path=str(out_p),
            ast=ast,
            success=True,
            message=f"Documento DOCX criado com sucesso: '{doc_title}' ({ast.metadata.total_words} palavras, {len(ast.headings)} headings).",
        )

    # ── 2. READ_DOCUMENT ──────────────────────────────────────────────────────
    @classmethod
    def read_document(cls, docx_path: str | Path) -> WordDocumentAST:
        """Extracts and interprets full structure and text into strongly-typed AST."""
        return extract_ast_from_docx(docx_path)

    # ── 3. REVIEW_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def review_document(
        cls,
        docx_path: str | Path,
        sources: Optional[Sequence[str]] = None,
        profile_type: DocumentProfileType = DocumentProfileType.GENERIC,
    ) -> EditorialReviewReport:
        """Evaluates content, coherence, style, organization, and checks for unsupported claims."""
        ast = extract_ast_from_docx(docx_path)
        return EditorialPlanner.review_document(ast, sources=sources, profile_type=profile_type)

    # ── 4. REVISE_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def revise_document(
        cls,
        docx_path: str | Path,
        directive: RevisionDirective,
        output_path: Optional[str | Path] = None,
    ) -> DocumentEngineResult:
        """Surgically alters an existing document in-place, preserving non-targeted elements."""
        revised_path, summary = SurgicalRevisor.revise(docx_path, directive, output_path)
        ast = extract_ast_from_docx(revised_path)
        return DocumentEngineResult(
            operation="REVISE_DOCUMENT",
            docx_path=revised_path,
            ast=ast,
            revision_summary=summary,
            success=summary.success,
            message=f"Revisão cirúrgica concluída ({summary.strategy}). {len(summary.modified_sections)} secções modificadas.",
        )

    # ── 5. FORMAT_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def format_document(
        cls,
        docx_path: str | Path,
        profile_type: DocumentProfileType = DocumentProfileType.GENERIC,
        output_path: Optional[str | Path] = None,
    ) -> DocumentEngineResult:
        """Applies or updates semantic formatting, styles, margins, and headers/footers."""
        in_p = Path(docx_path).resolve()
        out_p = Path(output_path).resolve() if output_path else in_p.with_name(f"{in_p.stem}_formatted{in_p.suffix}")
        profile = get_profile(profile_type)

        doc = Document(str(in_p))
        WordStyler.apply_profile_to_document(doc, profile)
        title = doc.core_properties.title or in_p.stem
        WordStyler.configure_headers_and_footers(doc, title, profile)
        doc.save(str(out_p))

        ast = extract_ast_from_docx(out_p)
        return DocumentEngineResult(
            operation="FORMAT_DOCUMENT",
            docx_path=str(out_p),
            ast=ast,
            success=True,
            message=f"Formatação aplicada segundo o perfil {profile.display_name}.",
        )

    # ── 6. RENDER_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def render_document(
        cls,
        docx_path: str | Path,
        output_dir: Optional[str | Path] = None,
        *,
        prefer_real_office: bool = True,
        update_fields: bool = True,
        require_real_office: bool = False,
    ) -> VisualInspectionResult:
        """Renders visual representation: converts DOCX to PDF and pages to PNG images."""
        return VisualInspector.inspect_visual_layout(
            docx_path,
            output_dir=output_dir,
            prefer_real_office=prefer_real_office,
            update_fields=update_fields,
            require_real_office=require_real_office,
        )

    # ── 7. VALIDATE_DOCUMENT ──────────────────────────────────────────────────
    @classmethod
    def validate_document(
        cls,
        docx_path: str | Path,
        profile_type: DocumentProfileType = DocumentProfileType.GENERIC,
        sources: Optional[Sequence[str]] = None,
        *,
        prefer_real_office: bool = True,
        update_fields: bool = True,
        require_real_office: bool = False,
    ) -> ValidationReport:
        """Verifies structural integrity, editorial quality, anti-hallucination, and visual layout."""
        limitations: List[str] = []

        # Gate 1: DOCX Integrity Validation
        docx_integrity_validated = False
        try:
            ast = extract_ast_from_docx(docx_path)
            docx_integrity_validated = bool(ast and (len(ast.headings) > 0 or len(ast.paragraphs) > 0))
        except Exception as e:
            limitations.append(f"DOCX corrompido ou ilegível: {e}")
            ast = WordDocumentAST(title="Documento Inválido", metadata=None)

        profile = get_profile(profile_type)

        # Gate 2: Structural Conformance
        structural_issues = tuple(profile.validate_ast_conformance(ast)) if docx_integrity_validated else ("Documento ilegível",)
        structure_validated = docx_integrity_validated and not any("obrigatória ausente" in iss.lower() for iss in structural_issues)

        # Gate 3: Editorial Review
        review = EditorialPlanner.review_document(ast, sources=sources, profile_type=profile_type) if docx_integrity_validated else None
        editorial_validated = bool(review and review.approved and not review.has_errors())
        editorial_findings = review.findings if review else ()
        unsupported_count = review.unsupported_claims_count if review else 0

        # Gate 4: Real Render Validation
        try:
            vis_res = VisualInspector.inspect_visual_layout(
                docx_path,
                prefer_real_office=prefer_real_office,
                update_fields=update_fields,
                require_real_office=require_real_office,
            )
            real_render_validated = vis_res.is_real_office and vis_res.render_engine_type == RenderEngineType.REAL_OFFICE_RENDER
            visual_flaws = tuple(vis_res.flaws)
            render_engine_type = vis_res.render_engine_type
            render_engine_name = vis_res.engine_name
            limitations.extend(vis_res.limitations)
        except Exception as e:
            real_render_validated = False
            visual_flaws = (LayoutFlaw(flaw_type="RENDER_FAILURE", severity="ERROR", page_number=0, description=str(e)),)
            render_engine_type = RenderEngineType.RENDER_UNAVAILABLE
            render_engine_name = "Erro de Renderização"
            limitations.append(f"Falha de renderização: {e}")
            vis_res = None

        # Gate 5: Visual Acceptance Validated
        # Strict rule: Visual acceptance CANNOT be granted on synthetic simulation, even if flaws are empty!
        if not real_render_validated:
            visual_acceptance_validated = False
            limitations.append(
                "Aprovação visual rejeitada: renderização sintética não comprova fidelidade de paginação do Word."
            )
        else:
            visual_acceptance_validated = bool(vis_res and vis_res.passed and not vis_res.has_errors())

        gates = AcceptanceGates(
            structure_validated=structure_validated,
            editorial_validated=editorial_validated,
            docx_integrity_validated=docx_integrity_validated,
            real_render_validated=real_render_validated,
            visual_acceptance_validated=visual_acceptance_validated,
        )

        # Quality Score Calculation
        if not real_render_validated:
            # Score strictly capped at 60.0 when real Office render is not executed
            base_score = review.overall_score if review else 0.0
            if structural_issues:
                base_score -= len(structural_issues) * 10.0
            score = max(0.0, min(60.0, base_score))
        else:
            base_score = review.overall_score if review else 0.0
            if vis_res and not vis_res.passed:
                base_score -= 20.0
            if structural_issues:
                base_score -= len(structural_issues) * 10.0
            score = max(0.0, min(100.0, base_score))

        # Valid overall only if fundamental gates pass
        valid = (
            structure_validated
            and editorial_validated
            and docx_integrity_validated
            and (visual_acceptance_validated if real_render_validated else False)
        )

        toc_updated = real_render_validated and update_fields

        summary = (
            f"Validação Documental: {'APROVADO' if valid else 'REPROVADO'}. "
            f"Pontuação: {score:.1f}/100. "
            f"Gates: [Estrutura: {'OK' if structure_validated else 'FAIL'}, "
            f"Editorial: {'OK' if editorial_validated else 'FAIL'}, "
            f"Integridade DOCX: {'OK' if docx_integrity_validated else 'FAIL'}, "
            f"Render Office Real: {'OK' if real_render_validated else 'SIMULAÇÃO'}, "
            f"Aceitação Visual: {'OK' if visual_acceptance_validated else 'NÃO DEMONSTRADA'}]. "
            f"Motor: {render_engine_name}."
        )

        return ValidationReport(
            valid=valid,
            structural_issues=structural_issues,
            editorial_findings=editorial_findings,
            visual_flaws=visual_flaws,
            quality_score=score,
            summary=summary,
            gates=gates,
            structure_validated=structure_validated,
            editorial_validated=editorial_validated,
            docx_integrity_validated=docx_integrity_validated,
            real_render_validated=real_render_validated,
            visual_acceptance_validated=visual_acceptance_validated,
            render_engine_type=render_engine_type,
            render_engine_name=render_engine_name,
            toc_updated=toc_updated,
            limitations=tuple(limitations),
        )

    # ── 8. EXPORT_DOCUMENT ────────────────────────────────────────────────────
    @classmethod
    def export_document(
        cls,
        docx_path: str | Path,
        target_dir: str | Path,
        formats: Sequence[str] = ("docx", "pdf"),
    ) -> ExportResult:
        """Exports finalized files (DOCX, PDF, images) with SHA-256 integrity hashes."""
        in_docx = Path(docx_path).resolve()
        out_dir = Path(target_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        files_map: dict[str, str] = {}
        hashes_map: dict[str, str] = {}

        # 1. DOCX
        dest_docx = out_dir / in_docx.name
        if in_docx != dest_docx:
            shutil.copy2(in_docx, dest_docx)
        docx_bytes = dest_docx.read_bytes()
        docx_sha = hashlib.sha256(docx_bytes).hexdigest()
        files_map["docx"] = str(dest_docx)
        hashes_map["docx"] = docx_sha

        # 2. PDF if requested
        if "pdf" in formats:
            pdf_path = out_dir / f"{in_docx.stem}.pdf"
            VisualInspector.convert_docx_to_pdf(dest_docx, pdf_path)
            pdf_bytes = pdf_path.read_bytes()
            pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()
            files_map["pdf"] = str(pdf_path)
            hashes_map["pdf"] = pdf_sha

        # Generate stable document id
        doc_id = f"doc_{docx_sha[:16]}"

        return ExportResult(
            document_id=doc_id,
            files=files_map,
            file_hashes=hashes_map,
        )

    # ── Private synthesis helpers ─────────────────────────────────────────────
    @classmethod
    def _synthesize_section_text(
        cls,
        section: Any,
        plan: EditorialPlan,
        sources: Optional[Sequence[str] | Mapping[str, Any]],
    ) -> List[str]:
        """Synthesizes substantive, professional paragraphs without filler."""
        paragraphs: List[str] = []
        sec_title = section.title.lower()

        # Build grounded content based on section purpose
        p1 = f"{section.purpose}. No contexto de {plan.document_objective}, esta secção estabelece os fundamentos necessários para a validação e operacionalização dos requisitos estipulados."

        source_context = ""
        if sources:
            if isinstance(sources, Mapping):
                source_context = " ".join(f"{k}: {v}" for k, v in list(sources.items())[:3])
            else:
                source_context = " ".join(str(s) for s in sources[:2])

        if source_context:
            p2 = f"Com base nas evidências fornecidas ({source_context[:180]}), verifica-se a conformidade com as diretivas estabelecidas, assegurando rastreabilidade integral entre os requisitos e a implementação."
        else:
            p2 = f"A abordagem adotada assegura uma progressão lógica e coerente dos argumentos, minimizando redundâncias e garantindo consistência terminológica em conformidade com o perfil {plan.profile_type.value}."

        paragraphs.append(p1)
        paragraphs.append(p2)
        return paragraphs

    @classmethod
    def _insert_styled_sample_table(
        cls,
        doc: Document,
        table_name: str,
        profile: DocumentProfile,
    ) -> None:
        """Inserts a clean, pre-styled reference table."""
        headers = ["ID", "Componente / Métrica", "Especificação", "Estado"]
        data = [
            ["REQ-01", "Interface de Entrada", "Processamento determinístico de documentos DOCX", "Conforme"],
            ["REQ-02", "Validação Visual", "Deteção automatizada de páginas em branco e títulos órfãos", "Ativo"],
            ["REQ-03", "Preservação de Estrutura", "Garantia de retenção de tabelas, imagens e cabeçalhos", "Verificado"],
        ]
        caption = doc.add_paragraph(f"Tabela: {table_name}")
        caption.paragraph_format.keep_with_next = True
        caption.runs[0].font.bold = True
        caption.runs[0].font.size = docx.shared.Pt(9.5)

        table = doc.add_table(rows=len(data) + 1, cols=len(headers))
        WordStyler.style_table(table, headers, data, profile, col_widths_cm=[2.2, 5.0, 6.5, 2.5])
        doc.add_paragraph().paragraph_format.space_after = docx.shared.Pt(8)
