"""
JARVIS OS — Study Engine Phase 5: Document Generation Orchestrator
Orquestrador central da Fase 5 com suporte a checkpoints incrementais validados por
fingerprints compostos (documento, plano, versão, overview, dossier, AST, prompts e modelo),
recuperação parcial estrita em ordem canónica, persistência atómica segura via ficheiro
temporário + os.replace() e histórico versionado não-destrutivo.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import pymupdf

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ContextBudgetManager,
)
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import (
    EditorialStudyPlan,
    compute_dossier_fingerprint,
)
from services.study_document_generation.content_generator import (
    DocumentContentGenerationEngine,
    PROMPT_VERSIONS_PHASE5,
)
from services.study_document_generation.contracts import (
    DevelopedChapterContent,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    DocumentGenerationState,
    DocumentGenerationTelemetry,
    StudyDocumentGenerationResult,
    StudyDocumentVersionRecord,
    build_section_fingerprint_index,
    compute_ast_fingerprint,
    compute_plan_fingerprint,
    compute_plan_overview_fingerprint,
    compute_section_plan_fingerprint,
)
from services.study_document_generation.design_system import (
    AcademicDesignSystem,
)
from services.study_document_generation.ir_compiler import DocumentStructureCompiler
from services.study_document_generation.layout_composer import (
    DOCXDocumentComposer,
    PDFDocumentComposer,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer
from services.study_document_generation.qa_engine import DocumentQualityAssuranceEngine
from services.study_document_generation.visual_generator import VisualGenerationEngine
from services.study_fs import resolve_confined_path, safe_document_id

logger = logging.getLogger("document_generation_orchestrator")

CHECKPOINT_SCHEMA_VERSION = "5.1.0"


def compute_file_sha256(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_text(target_path: Path, text: str) -> None:
    """
    Escrita atómica segura:
    1. Cria ficheiro temporário na mesma pasta/sistema de ficheiros.
    2. Escreve o conteúdo integral com flush + fsync.
    3. Verifica que os bytes gravados correspondem integralmente ao payload.
    4. Substitui o alvo via `os.replace()`.
    Em caso de falha, remove o temporário e preserva o ficheiro anterior intacto.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    expected_bytes = text.encode("utf-8")

    fd, tmp_name = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".{target_path.stem}_",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(expected_bytes)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

        if not tmp_path.exists() or tmp_path.stat().st_size != len(expected_bytes):
            raise IOError(f"Falha na verificação de integridade do ficheiro temporário '{tmp_path}'.")

        os.replace(tmp_path, target_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _atomic_write_json(target_path: Path, payload: Any) -> None:
    """Serializa para JSON em memória e persiste atomicamente em disco."""
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    _atomic_write_text(target_path, serialized)


class DocumentGenerationOrchestrator:
    """
    Orquestrador coordenador da Fase 5:
    Plano Editorial (Fase 4) + Dossier (Fase 3) + AST (Fase 2)
      -> Conteúdo Desenvolvido (5.1 & 5.2) com validação estrita de checkpoints
      -> Elementos Visuais Fundamentados (5.4)
      -> Compilador IR (5.3)
      -> Layout & Composição PDF/DOCX (5.5)
      -> QA Documental em 4 Eixos (5.8)
      -> Persistência Atómica & Versionada
    """

    def __init__(
        self,
        storage_dir: Path,
        *,
        llm_caller: Optional[Callable] = None,
        budget_manager: Optional[ContextBudgetManager] = None,
        prompt_versions: Optional[Dict[str, str]] = None,
        model_name: str = "qwen3.5:9b",
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.llm_caller = llm_caller
        self.budget_manager = budget_manager or ContextBudgetManager()
        self.prompt_versions = dict(prompt_versions) if prompt_versions is not None else None
        self.model_name = model_name

    def _active_prompt_versions(self) -> Dict[str, str]:
        return dict(self.prompt_versions) if self.prompt_versions is not None else dict(PROMPT_VERSIONS_PHASE5)

    def _load_and_validate_checkpoint(
        self,
        checkpoint_path: Path,
        *,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        cur_overview_fp: str,
        cur_dossier_fp: str,
        cur_ast_fp: str,
        cur_prompt_versions: Dict[str, str],
        cur_model_name: str,
    ) -> Tuple[Dict[str, Dict[str, DevelopedSectionContent]], str]:
        """
        Carrega e valida um checkpoint existente.
        Garante:
        - Consistência global (`document_id`, `plan_id`, `plan_version`, `overview_fingerprint`,
          `dossier_id`, `dossier_fingerprint`, `ast_fingerprint`, `prompt_versions`, `model_name`).
        - Consistência granular por secção (`section_fingerprint` e integridade do payload) para
          recuperação parcial segura sem reutilizar unidades obsoletas ou corrompidas.
        """
        if not checkpoint_path.exists():
            return {}, "NO_CHECKPOINT"

        try:
            raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"[DocGenCheckpoint] Checkpoint corrompido ou truncado em {checkpoint_path}: {exc}")
            return {}, "CORRUPTED_CHECKPOINT"

        if not isinstance(raw, dict):
            return {}, "INVALID_CHECKPOINT_FORMAT"

        doc_id = plan.metadata.document_id
        # Exigir envelope mínimo de integridade; checkpoints legados sem fingerprints são invalidados
        required_keys = (
            "schema_version",
            "document_id",
            "plan_id",
            "plan_version",
            "overview_fingerprint",
            "dossier_id",
            "dossier_fingerprint",
            "ast_fingerprint",
            "prompt_versions",
            "model_name",
        )
        if any(k not in raw for k in required_keys):
            logger.info("[DocGenCheckpoint] Checkpoint sem metadados de consistência obrigatórios. Invalidado.")
            return {}, "MISSING_FINGERPRINT_ENVELOPE"

        if raw.get("document_id") != doc_id:
            return {}, "DOCUMENT_ID_MISMATCH"
        if raw.get("plan_id") != plan.metadata.plan_id:
            return {}, "PLAN_ID_MISMATCH"
        if raw.get("plan_version") != getattr(plan.metadata, "plan_version", 1):
            return {}, "PLAN_VERSION_MISMATCH"
        if raw.get("overview_fingerprint") != cur_overview_fp:
            return {}, "PLAN_OVERVIEW_CHANGED"
        if raw.get("dossier_id") != dossier.dossier_id or raw.get("dossier_fingerprint") != cur_dossier_fp:
            return {}, "DOSSIER_CHANGED"
        if raw.get("ast_fingerprint") != cur_ast_fp:
            return {}, "AST_CHANGED"
        if raw.get("prompt_versions") != cur_prompt_versions:
            return {}, "PROMPT_VERSIONS_CHANGED"
        if raw.get("model_name") != cur_model_name:
            return {}, "MODEL_CHANGED"

        section_records = raw.get("section_records")
        if not isinstance(section_records, dict):
            return {}, "MISSING_SECTION_RECORDS"

        recovered: Dict[str, Dict[str, DevelopedSectionContent]] = {}
        reused_count = 0
        invalid_units = 0

        for ch in plan.chapters:
            for sec in ch.sections:
                rec = section_records.get(sec.section_id)
                if not isinstance(rec, dict):
                    continue
                if rec.get("chapter_id") != ch.chapter_id:
                    invalid_units += 1
                    continue
                expected_unit_fp = compute_section_plan_fingerprint(ch, sec, dossier=dossier, ast=ast)
                if rec.get("section_fingerprint") != expected_unit_fp:
                    invalid_units += 1
                    continue
                sec_data = rec.get("section_data")
                if not isinstance(sec_data, dict):
                    invalid_units += 1
                    continue
                try:
                    dev_sec = DevelopedSectionContent.from_dict(sec_data)
                    if dev_sec.section_id != sec.section_id or dev_sec.chapter_id != ch.chapter_id:
                        invalid_units += 1
                        continue
                    recovered.setdefault(ch.chapter_id, {})[sec.section_id] = dev_sec
                    reused_count += 1
                except Exception:
                    invalid_units += 1
                    continue

        if reused_count == 0:
            return {}, "NO_VALID_SECTIONS_RECOVERED"
        if invalid_units > 0:
            return recovered, "PARTIAL_RECOVERY"
        return recovered, "FULL_RECOVERY"

    def _save_checkpoint_atomic(
        self,
        checkpoint_path: Path,
        *,
        doc_id: str,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        plan_fp: str,
        overview_fp: str,
        dossier_fp: str,
        ast_fp: str,
        prompt_versions: Dict[str, str],
        model_name: str,
        section_records: Dict[str, Dict[str, Any]],
        completed_chapters: List[DevelopedChapterContent],
    ) -> None:
        payload = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "document_id": doc_id,
            "plan_id": plan.metadata.plan_id,
            "plan_version": getattr(plan.metadata, "plan_version", 1),
            "plan_fingerprint": plan_fp,
            "overview_fingerprint": overview_fp,
            "dossier_id": dossier.dossier_id,
            "dossier_fingerprint": dossier_fp,
            "ast_fingerprint": ast_fp,
            "source_sha256": getattr(dossier, "source_sha256", "") or getattr(plan.metadata, "source_sha256", ""),
            "prompt_versions": prompt_versions,
            "model_name": model_name,
            "section_records": section_records,
            "chapters": [c.to_dict() for c in completed_chapters],
            "saved_at": datetime.now().isoformat(),
        }
        _atomic_write_json(checkpoint_path, payload)

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
        doc_id = safe_document_id(plan.metadata.document_id)

        doc_dir = resolve_confined_path(self.storage_dir / "documents", doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        visuals_dir = resolve_confined_path(doc_dir, "generated_visuals")
        visuals_dir.mkdir(parents=True, exist_ok=True)
        history_dir = resolve_confined_path(doc_dir, "generated_documents_history")
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
        cur_prompt_versions = self._active_prompt_versions()
        telemetry.prompt_versions.update(cur_prompt_versions)
        failed_operations: List[Dict[str, Any]] = []

        # Calcular todos os fingerprints de consistência
        plan_fp = compute_plan_fingerprint(plan)
        overview_fp = compute_plan_overview_fingerprint(plan)
        dossier_fp = compute_dossier_fingerprint(dossier)
        ast_fp = compute_ast_fingerprint(ast)

        def _notify(stage: str, pct: float, msg: str):
            if on_progress:
                try:
                    on_progress(stage, pct, msg)
                except Exception:
                    pass

        def _check_cancelled():
            if cancellation_check and cancellation_check():
                raise InterruptedError("Geração documental cancelada pelo utilizador.")

        _notify("INITIALIZATION", 0.05, "A inicializar motor de composição, fingerprints e proveniência...")

        # 1. Validar e carregar Checkpoint com verificação estrita de consistência
        cached_sections_by_chap: Dict[str, Dict[str, DevelopedSectionContent]] = {}
        recovery_status = "SKIPPED_FORCE_RECOMPUTE"
        if not force_recompute:
            cached_sections_by_chap, recovery_status = self._load_and_validate_checkpoint(
                checkpoint_path,
                plan=plan,
                dossier=dossier,
                ast=ast,
                cur_overview_fp=overview_fp,
                cur_dossier_fp=dossier_fp,
                cur_ast_fp=ast_fp,
                cur_prompt_versions=cur_prompt_versions,
                cur_model_name=self.model_name,
            )

        # 2. Etapa 5.1 & 5.2: Geração e Enriquecimento de Conteúdo Pedagógico
        content_engine = DocumentContentGenerationEngine(
            llm_caller=self.llm_caller,
            budget_manager=self.budget_manager,
            model_name=self.model_name,
        )

        completed_chapters: List[DevelopedChapterContent] = []
        section_records_for_cp: Dict[str, Dict[str, Any]] = {}
        total_sections = sum(len(c.sections) for c in plan.chapters)
        processed_sections = 0
        fp_index = build_section_fingerprint_index(dossier, ast)

        _notify(
            "CONTENT_GENERATION",
            0.10,
            f"A desenvolver conteúdo pedagógico ({len(plan.chapters)} capítulos, {total_sections} secções; checkpoint={recovery_status})...",
        )

        for ch in plan.chapters:
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
                section_records_for_cp[sec.section_id] = {
                    "chapter_id": ch.chapter_id,
                    "section_fingerprint": compute_section_plan_fingerprint(
                        ch, sec, dossier=dossier, ast=ast, context_index=fp_index
                    ),
                    "section_data": dev_sec.to_dict(),
                }
                processed_sections += 1
                telemetry.sections_processed += 1

            dev_chap = content_engine.finalize_chapter_content(
                chapter=ch,
                developed_sections=developed_sections,
                dossier=dossier,
                provenance=provenance,
            )
            completed_chapters.append(dev_chap)
            telemetry.chapters_processed += 1

            # Gravar checkpoint incremental atomicamente por capítulo
            self._save_checkpoint_atomic(
                checkpoint_path,
                doc_id=doc_id,
                plan=plan,
                dossier=dossier,
                plan_fp=plan_fp,
                overview_fp=overview_fp,
                dossier_fp=dossier_fp,
                ast_fp=ast_fp,
                prompt_versions=cur_prompt_versions,
                model_name=self.model_name,
                section_records=section_records_for_cp,
                completed_chapters=completed_chapters,
            )

        # Compilar DevelopedStudyDocumentContent
        developed_content = DevelopedStudyDocumentContent(
            document_id=doc_id,
            plan_id=plan.metadata.plan_id,
            plan_version=getattr(plan.metadata, "plan_version", 1),
            dossier_fingerprint=dossier_fp,
            plan_fingerprint=plan_fp,
            document_title=dossier.document_title or "Caderno Académico de Estudo",
            document_subtitle=plan.overview.central_theme or "Estudo Aprofundado & Rigor Epistémico",
            executive_study_overview=plan.overview.global_organization_summary or plan.overview.editorial_strategy,
            chapters=completed_chapters,
            global_integrative_synthesis=getattr(
                dossier.cross_section_synthesis,
                "global_synthesis",
                getattr(dossier.cross_section_synthesis, "integrative_synthesis", ""),
            ),
            created_at=datetime.now().isoformat(),
            model_name=self.model_name,
            generation_status="COMPLETED",
        )
        _atomic_write_json(content_path, developed_content.to_dict())

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
        _atomic_write_json(ir_path, doc_ir.to_dict())

        # 5. Etapa 5.5: Composição e Layout do PDF em staging (promovido a final apenas após passar QA)
        _notify("PDF_COMPOSITION", 0.78, "A compilar layout e tipografia do PDF com medição real e fragmentação...")
        _check_cancelled()
        staging_pdf_path = doc_dir / ".staging_study_document.pdf"
        staging_docx_path = doc_dir / ".staging_study_document.docx"
        for st_p in (staging_pdf_path, staging_docx_path):
            if st_p.exists():
                try:
                    st_p.unlink()
                except OSError:
                    pass

        t_pdf0 = time.time()
        pdf_composer = PDFDocumentComposer(profile=profile)
        pdf_render_result = pdf_composer.compose_to_pdf(doc_ir, staging_pdf_path)
        telemetry.stage_timings_ms["pdf_composition"] = (time.time() - t_pdf0) * 1000.0

        pdf_p = Path(pdf_render_result.file_path)
        pdf_sha = compute_file_sha256(pdf_p)
        telemetry.pdf_size_bytes = pdf_p.stat().st_size if pdf_p.exists() else 0

        try:
            with pymupdf.open(str(pdf_p)) as doc_probe:
                telemetry.pdf_pages_count = len(doc_probe)
        except Exception:
            pass

        # 6. Etapa 5.5: Exportação DOCX em staging (se solicitada)
        docx_render_result = None
        docx_sha: Optional[str] = None
        if export_docx:
            _notify("DOCX_EXPORT", 0.88, "A exportar documento em formato DOCX a partir da mesma IR semântica...")
            try:
                t_docx0 = time.time()
                docx_composer = DOCXDocumentComposer(profile=profile)
                docx_render_result = docx_composer.compose_to_docx(doc_ir, staging_docx_path)
                telemetry.stage_timings_ms["docx_export"] = (time.time() - t_docx0) * 1000.0
                docx_p = Path(docx_render_result.file_path)
                docx_sha = compute_file_sha256(docx_p)
                telemetry.docx_size_bytes = docx_p.stat().st_size if docx_p.exists() else 0
            except Exception as d_err:
                failed_operations.append({
                    "operation": "docx_export",
                    "error": str(d_err),
                    "timestamp": datetime.now().isoformat(),
                })

        # 7. Etapa 5.8: Quality Assurance Documental em 4 Eixos antes da promoção final
        _notify("QUALITY_ASSURANCE", 0.94, "A auditar integridade física, visual, pedagógica e epistémica...")
        qa_engine = DocumentQualityAssuranceEngine()
        qa_report = qa_engine.audit(
            ir=doc_ir,
            plan=plan,
            dossier=dossier,
            pdf_path=staging_pdf_path,
            docx_path=staging_docx_path if export_docx and docx_render_result else None,
            design_profile=profile,
            render_result=pdf_render_result,
        )
        _atomic_write_json(qa_path, qa_report.to_dict())

        # 8. Versionamento Seguro e Promoção Condicional (preserva final válido se QA falhar!)
        new_version = self._determine_next_version(history_dir)
        v_sub_dir = resolve_confined_path(history_dir, f"v{new_version}")
        v_sub_dir.mkdir(parents=True, exist_ok=True)
        hist_pdf_path = v_sub_dir / f"study_document_v{new_version}.pdf"
        shutil.copy2(staging_pdf_path, hist_pdf_path)

        hist_docx_path_str = None
        if docx_render_result and staging_docx_path.exists():
            hist_docx_path = v_sub_dir / f"study_document_v{new_version}.docx"
            shutil.copy2(staging_docx_path, hist_docx_path)
            hist_docx_path_str = str(hist_docx_path)

        if not qa_report.is_valid:
            final_status = DocumentGenerationState.FAILED.value
            for st_p in (staging_pdf_path, staging_docx_path):
                if st_p.exists():
                    try:
                        st_p.unlink()
                    except OSError:
                        pass
            published_pdf_path = str(final_pdf_path) if final_pdf_path.exists() else str(hist_pdf_path)
            published_docx_path = (
                str(final_docx_path)
                if (export_docx and final_docx_path.exists())
                else hist_docx_path_str
            )
        else:
            final_status = DocumentGenerationState.COMPLETED.value
            os.replace(staging_pdf_path, final_pdf_path)
            published_pdf_path = str(final_pdf_path)
            if docx_render_result and staging_docx_path.exists():
                os.replace(staging_docx_path, final_docx_path)
                published_docx_path = str(final_docx_path)
            else:
                published_docx_path = None

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
            plan_version=getattr(plan.metadata, "plan_version", 1),
        )
        versions_manifest.append(version_record)
        self._save_versions_history(history_dir, versions_manifest)

        # Limpar checkpoint temporário apenas quando concluído com sucesso
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
            pdf_path=published_pdf_path,
            docx_path=published_docx_path,
            pdf_sha256=pdf_sha,
            docx_sha256=docx_sha,
            ir_path=str(ir_path),
            developed_content_path=str(content_path),
            qa_report_path=str(qa_path),
            qa_report=qa_report,
            plan_fingerprint=plan_fp,
            dossier_fingerprint=dossier_fp,
            ast_fingerprint=ast_fp,
            plan_version=getattr(plan.metadata, "plan_version", 1),
            model_name=self.model_name,
            prompt_versions=cur_prompt_versions,
            telemetry=telemetry,
            visual_assets=visual_assets,
            versions_history=versions_manifest,
            failed_operations=failed_operations,
            created_at=datetime.now().isoformat(),
        )

        _atomic_write_json(meta_result_path, result.to_dict())
        _notify("FINISHED", 1.0, f"Documento de estudo concluído ({telemetry.pdf_pages_count} págs, QA: {qa_report.validation_status}).")

        return result

    def get_document_generation_status(self, document_id: str) -> Dict[str, Any]:
        """Consulta o estado da geração documental, ficheiros e versão ativa."""
        clean_id = safe_document_id(document_id)
        doc_dir = resolve_confined_path(self.storage_dir / "documents", clean_id)
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
        _atomic_write_json(manifest_p, raw)
