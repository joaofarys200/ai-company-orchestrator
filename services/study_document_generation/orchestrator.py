"""
JARVIS OS — Study Engine Phase 5: Document Generation Orchestrator
Orquestrador central da Fase 5 com suporte a checkpoints incrementais, histórico versionado,
reutilização de inferência local (qwen3.5:9b) e garantia não-destrutiva de integridade.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ContextBudgetManager,
)
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialStudyPlan,
)
from services.study_document_generation.content_generator import DocumentContentGenerationEngine
from services.study_document_generation.contracts import (
    DevelopedChapterContent,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    DocumentGenerationState,
    DocumentGenerationTelemetry,
    GeneratedVisualAsset,
    StudyDocumentGenerationResult,
    StudyDocumentQAReport,
    StudyDocumentVersionRecord,
    compute_plan_fingerprint,
)
from services.study_document_generation.design_system import (
    ACADEMIC_EDITORIAL_CLASSIC,
    AcademicDesignSystem,
    DesignStyleProfile,
)
from services.study_document_generation.ir_compiler import DocumentStructureCompiler
from services.study_document_generation.layout_composer import (
    DOCXDocumentComposer,
    PDFDocumentComposer,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer
from services.study_document_generation.qa_engine import DocumentQualityAssuranceEngine
from services.study_document_generation.visual_generator import VisualGenerationEngine


def compute_file_sha256(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DocumentGenerationOrchestrator:
    """
    Orquestrador coordenador da Fase 5:
    Plano Editorial (Fase 4) + Dossier (Fase 3) + AST (Fase 2)
      -> Conteúdo Desenvolvido (5.1 & 5.2)
      -> Elementos Visuais Fundamentados (5.4)
      -> Compilador IR (5.3)
      -> Layout & Composição PDF/DOCX (5.5)
      -> QA Documental em 4 Eixos (5.8)
      -> Persistência Versionada com Checkpoints
    """

    def __init__(
        self,
        storage_dir: Path,
        *,
        llm_caller: Optional[Callable] = None,
        budget_manager: Optional[ContextBudgetManager] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.llm_caller = llm_caller
        self.budget_manager = budget_manager or ContextBudgetManager()

    def generate_document(
        self,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST] = None,
        *,
        design_profile_id: str = "ACADEMIC_EDITORIAL_CLASSIC",
        export_docx: bool = True,
        force_recompute: bool = False,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> StudyDocumentGenerationResult:
        start_time = time.time()
        doc_id = plan.metadata.document_id

        doc_dir = self.storage_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        visuals_dir = doc_dir / "generated_visuals"
        visuals_dir.mkdir(parents=True, exist_ok=True)
        history_dir = doc_dir / "generated_documents_history"
        history_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_path = doc_dir / "document_generation_checkpoint.json"
        content_path = doc_dir / "developed_study_content.json"
        ir_path = doc_dir / "study_document_ir.json"
        qa_path = doc_dir / "study_document_qa_report.json"
        final_pdf_path = doc_dir / "study_document_final.pdf"
        final_docx_path = doc_dir / "study_document_final.docx"
        meta_result_path = doc_dir / "document_generation_result.json"

        profile = AcademicDesignSystem.get_profile(design_profile_id)
        provenance = ReferenceAndProvenanceRenderer(dossier, ast)

        telemetry = DocumentGenerationTelemetry()
        failed_operations: List[Dict[str, Any]] = []

        def _notify(stage: str, pct: float, msg: str):
            if on_progress:
                try:
                    on_progress(stage, pct, msg)
                except Exception:
                    pass

        def _check_cancelled():
            if cancellation_check and cancellation_check():
                raise InterruptedError("Geração documental cancelada pelo utilizador.")

        _notify("INITIALIZATION", 0.05, "A inicializar motor de composição e proveniência...")

        # 1. Carregar Checkpoint se existir e não for force_recompute
        checkpoint: Dict[str, Any] = {}
        if checkpoint_path.exists() and not force_recompute:
            try:
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except Exception:
                checkpoint = {}

        # 2. Etapa 5.1 & 5.2: Geração e Enriquecimento de Conteúdo Pedagógico
        content_engine = DocumentContentGenerationEngine(
            llm_caller=self.llm_caller,
            budget_manager=self.budget_manager,
        )

        completed_chapters: List[DevelopedChapterContent] = []
        cached_sections_by_chap: Dict[str, Dict[str, DevelopedSectionContent]] = {}

        if checkpoint.get("chapters") and not force_recompute:
            for ch_dict in checkpoint["chapters"]:
                ch_obj = DevelopedChapterContent.from_dict(ch_dict)
                cached_sections_by_chap[ch_obj.chapter_id] = {s.section_id: s for s in ch_obj.sections}

        total_sections = sum(len(c.sections) for c in plan.chapters)
        processed_sections = 0

        _notify("CONTENT_GENERATION", 0.10, f"A desenvolver conteúdo pedagógico ({len(plan.chapters)} capítulos, {total_sections} secções)...")

        for ch_idx, ch in enumerate(plan.chapters, start=1):
            _check_cancelled()
            ch_cached = cached_sections_by_chap.get(ch.chapter_id, {})
            developed_sections: List[DevelopedSectionContent] = []

            for sec in ch.sections:
                _check_cancelled()
                if sec.section_id in ch_cached and not force_recompute:
                    dev_sec = ch_cached[sec.section_id]
                else:
                    _notify(
                        "CONTENT_GENERATION",
                        0.10 + (processed_sections / max(1, total_sections)) * 0.45,
                        f"A aprofundar secção «{sec.title}» (Cap. {ch.order})...",
                    )
                    t0 = time.time()
                    dev_sec = content_engine.generate_section_content(
                        chapter=ch,
                        section=sec,
                        plan=plan,
                        dossier=dossier,
                        ast=ast,
                        provenance=provenance,
                        telemetry=telemetry,
                        failed_operations=failed_operations,
                    )
                    telemetry.stage_timings_ms[f"sec_{sec.section_id}"] = (time.time() - t0) * 1000.0

                developed_sections.append(dev_sec)
                processed_sections += 1
                telemetry.sections_processed += 1

            # Finalizar capítulo
            dev_chap = content_engine.finalize_chapter_content(
                chapter=ch,
                developed_sections=developed_sections,
                dossier=dossier,
                provenance=provenance,
            )
            completed_chapters.append(dev_chap)
            telemetry.chapters_processed += 1

            # Gravar checkpoint incremental por capítulo
            checkpoint_payload = {
                "document_id": doc_id,
                "plan_id": plan.metadata.plan_id,
                "chapters": [c.to_dict() for c in completed_chapters],
                "saved_at": datetime.now().isoformat(),
            }
            checkpoint_path.write_text(json.dumps(checkpoint_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Compilar DevelopedStudyDocumentContent
        plan_fp = compute_plan_fingerprint(plan)
        developed_content = DevelopedStudyDocumentContent(
            document_id=doc_id,
            plan_id=plan.metadata.plan_id,
            plan_version=plan.metadata.plan_version,
            dossier_fingerprint=getattr(plan.metadata, "dossier_fingerprint", ""),
            plan_fingerprint=plan_fp,
            document_title=dossier.document_title or "Caderno Académico de Estudo",
            document_subtitle=plan.overview.central_theme or "Estudo Aprofundado & Rigor Epistémico",
            executive_study_overview=plan.overview.global_organization_summary or plan.overview.editorial_strategy,
            chapters=completed_chapters,
            global_integrative_synthesis=getattr(dossier.cross_section_synthesis, "global_synthesis", getattr(dossier.cross_section_synthesis, "integrative_synthesis", "")),
            created_at=datetime.now().isoformat(),
            model_name="qwen3.5:9b",
            generation_status="COMPLETED",
        )
        content_path.write_text(json.dumps(developed_content.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # 3. Etapa 5.4: Geração de Elementos Visuais Fundamentados
        _notify("VISUAL_GENERATION", 0.60, f"A renderizar elementos visuais fundamentados ({len(plan.visual_plans)} visuais)...")
        _check_cancelled()
        t_vis0 = time.time()
        visual_engine = VisualGenerationEngine(visuals_dir, profile=profile)
        visual_assets = visual_engine.generate_visual_assets(
            plan=plan,
            dossier=dossier,
            ast=ast,
            provenance=provenance,
        )
        telemetry.stage_timings_ms["visual_generation"] = (time.time() - t_vis0) * 1000.0
        telemetry.visuals_rendered = sum(1 for v in visual_assets if v.render_status in ("RENDERED", "RENDERED_AS_TABLE"))
        telemetry.visuals_omitted = sum(1 for v in visual_assets if v.render_status.startswith("OMITTED"))

        # 4. Etapa 5.3: Compilação da Representação Intermédia (IR)
        _notify("IR_COMPILATION", 0.70, "A compilar árvore semântica do documento (Representação Intermédia)...")
        _check_cancelled()
        ir_compiler = DocumentStructureCompiler(profile=profile, provenance=provenance)
        doc_ir = ir_compiler.compile(
            developed=developed_content,
            plan=plan,
            dossier=dossier,
            visual_assets=visual_assets,
            ast=ast,
        )
        ir_path.write_text(json.dumps(doc_ir.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # 5. Etapa 5.5: Composição e Layout do PDF
        _notify("PDF_COMPOSITION", 0.78, "A compilar layout e tipografia do PDF com controlo de órfãos e quebras...")
        _check_cancelled()
        t_pdf0 = time.time()
        pdf_composer = PDFDocumentComposer(profile=profile)
        final_pdf_str = pdf_composer.compose_to_pdf(doc_ir, final_pdf_path)
        telemetry.stage_timings_ms["pdf_composition"] = (time.time() - t_pdf0) * 1000.0

        pdf_p = Path(final_pdf_str)
        pdf_sha = compute_file_sha256(pdf_p)
        telemetry.pdf_size_bytes = pdf_p.stat().st_size if pdf_p.exists() else 0

        # Contar páginas do PDF gerado
        try:
            doc_probe = pymupdf.open(str(pdf_p))
            telemetry.pdf_pages_count = len(doc_probe)
            doc_probe.close()
        except Exception:
            pass

        # 6. Etapa 5.5: Exportação DOCX (se solicitada)
        final_docx_str: Optional[str] = None
        docx_sha: Optional[str] = None
        if export_docx:
            _notify("DOCX_EXPORT", 0.88, "A exportar documento em formato DOCX a partir da mesma IR semântica...")
            try:
                t_docx0 = time.time()
                docx_composer = DOCXDocumentComposer(profile=profile)
                final_docx_str = docx_composer.compose_to_docx(doc_ir, final_docx_path)
                telemetry.stage_timings_ms["docx_export"] = (time.time() - t_docx0) * 1000.0
                docx_p = Path(final_docx_str)
                docx_sha = compute_file_sha256(docx_p)
                telemetry.docx_size_bytes = docx_p.stat().st_size if docx_p.exists() else 0
            except Exception as d_err:
                failed_operations.append({
                    "operation": "docx_export",
                    "error": str(d_err),
                    "timestamp": datetime.now().isoformat(),
                })

        # 7. Etapa 5.8: Quality Assurance Documental em 4 Eixos
        _notify("QUALITY_ASSURANCE", 0.94, "A auditar integridade física, visual, pedagógica e documental...")
        qa_engine = DocumentQualityAssuranceEngine()
        qa_report = qa_engine.audit(
            ir=doc_ir,
            plan=plan,
            dossier=dossier,
            pdf_path=final_pdf_path,
            docx_path=final_docx_path if export_docx else None,
        )
        qa_path.write_text(json.dumps(qa_report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Determinar estado final
        if not qa_report.is_valid:
            final_status = DocumentGenerationState.FAILED.value
        elif qa_report.warnings_count > 0:
            final_status = DocumentGenerationState.COMPLETED.value
        else:
            final_status = DocumentGenerationState.COMPLETED.value

        # 8. Versionamento Seguro (generated_documents_history/)
        new_version = self._determine_next_version(history_dir)
        v_sub_dir = history_dir / f"v{new_version}"
        v_sub_dir.mkdir(parents=True, exist_ok=True)
        hist_pdf_path = v_sub_dir / f"study_document_v{new_version}.pdf"
        shutil.copy2(final_pdf_path, hist_pdf_path)

        hist_docx_path_str = None
        if final_docx_str and os.path.exists(final_docx_str):
            hist_docx_path = v_sub_dir / f"study_document_v{new_version}.docx"
            shutil.copy2(final_docx_str, hist_docx_path)
            hist_docx_path_str = str(hist_docx_path)

        # Atualizar manifesto de versões
        versions_manifest = self._load_versions_history(history_dir)
        version_record = StudyDocumentVersionRecord(
            version=new_version,
            created_at=datetime.now().isoformat(),
            status=final_status,
            design_profile=profile.profile_id,
            pdf_path=str(hist_pdf_path),
            docx_path=hist_docx_path_str,
            pdf_sha256=pdf_sha,
            docx_sha256=docx_sha,
            total_pages=telemetry.pdf_pages_count,
            qa_validation_status=qa_report.validation_status,
            plan_version=plan.metadata.plan_version,
        )
        versions_manifest.append(version_record)
        self._save_versions_history(history_dir, versions_manifest)

        # Limpar checkpoint temporário quando concluído com sucesso
        if final_status == DocumentGenerationState.COMPLETED.value and checkpoint_path.exists():
            try:
                checkpoint_path.unlink()
            except Exception:
                pass

        total_duration = (time.time() - start_time) * 1000.0
        telemetry.total_duration_ms = total_duration

        result = StudyDocumentGenerationResult(
            document_id=doc_id,
            version=new_version,
            status=final_status,
            design_profile=profile.profile_id,
            pdf_path=str(final_pdf_path),
            docx_path=str(final_docx_path) if export_docx and final_docx_str else None,
            pdf_sha256=pdf_sha,
            docx_sha256=docx_sha,
            ir_path=str(ir_path),
            developed_content_path=str(content_path),
            qa_report_path=str(qa_path),
            qa_report=qa_report,
            plan_fingerprint=plan_fp,
            dossier_fingerprint=getattr(plan.metadata, "dossier_fingerprint", ""),
            telemetry=telemetry,
            visual_assets=visual_assets,
            versions_history=versions_manifest,
            failed_operations=failed_operations,
            created_at=datetime.now().isoformat(),
        )

        meta_result_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        _notify("FINISHED", 1.0, f"Documento de estudo concluído ({telemetry.pdf_pages_count} págs, QA: {qa_report.validation_status}).")

        return result

    def get_document_generation_status(self, document_id: str) -> Dict[str, Any]:
        """Consulta o estado da geração documental, ficheiros e versão ativa."""
        doc_dir = self.storage_dir / "documents" / document_id
        meta_res_path = doc_dir / "document_generation_result.json"
        checkpoint_path = doc_dir / "document_generation_checkpoint.json"
        pdf_path = doc_dir / "study_document_final.pdf"
        docx_path = doc_dir / "study_document_final.docx"
        history_dir = doc_dir / "generated_documents_history"

        has_pdf = pdf_path.exists() and pdf_path.stat().st_size > 0
        has_docx = docx_path.exists() and docx_path.stat().st_size > 0
        has_checkpoint = checkpoint_path.exists()

        res_obj: Optional[StudyDocumentGenerationResult] = None
        if meta_res_path.exists():
            try:
                res_obj = StudyDocumentGenerationResult.from_dict(json.loads(meta_res_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        versions = self._load_versions_history(history_dir)

        if res_obj:
            state = res_obj.status
        elif has_checkpoint:
            state = DocumentGenerationState.PARTIAL.value
        elif has_pdf:
            state = DocumentGenerationState.COMPLETED.value
        else:
            state = DocumentGenerationState.PENDING.value

        return {
            "document_id": document_id,
            "state": state,
            "has_pdf": has_pdf,
            "has_docx": has_docx,
            "has_checkpoint": has_checkpoint,
            "version": res_obj.version if res_obj else (versions[-1].version if versions else 1),
            "pdf_path": str(pdf_path) if has_pdf else None,
            "docx_path": str(docx_path) if has_docx else None,
            "pdf_size_bytes": pdf_path.stat().st_size if has_pdf else 0,
            "docx_size_bytes": docx_path.stat().st_size if has_docx else 0,
            "qa_validation_status": res_obj.qa_report.validation_status if res_obj else "NOT_AUDITED",
            "qa_report": res_obj.qa_report.to_dict() if res_obj else None,
            "telemetry": res_obj.telemetry.to_dict() if res_obj else None,
            "versions_count": len(versions),
            "updated_at": res_obj.created_at if res_obj else (datetime.now().isoformat() if has_pdf else None),
        }

    def _determine_next_version(self, history_dir: Path) -> int:
        versions = self._load_versions_history(history_dir)
        disk_versions: List[int] = []
        if history_dir.exists():
            for p in history_dir.iterdir():
                if p.is_dir() and p.name.startswith("v"):
                    try:
                        disk_versions.append(int(p.name[1:]))
                    except ValueError:
                        pass
        all_v = [v.version for v in versions] + disk_versions
        if not all_v:
            return 1
        return max(all_v) + 1

    def _load_versions_history(self, history_dir: Path) -> List[StudyDocumentVersionRecord]:
        manifest_p = history_dir / "versions_manifest.json"
        if manifest_p.exists():
            try:
                raw = json.loads(manifest_p.read_text(encoding="utf-8"))
                return [StudyDocumentVersionRecord.from_dict(x) for x in raw if isinstance(x, dict)]
            except Exception:
                pass
        return []

    def _save_versions_history(self, history_dir: Path, versions: List[StudyDocumentVersionRecord]) -> None:
        manifest_p = history_dir / "versions_manifest.json"
        raw = [v.to_dict() for v in versions]
        manifest_p.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
