import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ShieldCheck,
  Palette,
  ChevronDown,
  ChevronRight,
  BookOpen,
  Eye,
  EyeOff,
} from 'lucide-react';
import type {
  StudyDocument,
  StudyDocumentGenerationStatus,
  StudyDocumentGenerationResult,
  StudyDocumentFilePayload,
  StudyDocumentQAReport,
} from './types';

interface StudyGeneratedDocumentViewProps {
  document: StudyDocument;
  onGetGeneratedDocumentStatus?: (documentId: string) => Promise<StudyDocumentGenerationStatus | null>;
  onGenerateStudyDocument?: (
    documentId: string,
    options?: {
      forceRecompute?: boolean;
      autoGeneratePlan?: boolean;
      designProfileId?: string;
      exportDocx?: boolean;
    }
  ) => Promise<{
    result: StudyDocumentGenerationResult | null;
    status: StudyDocumentGenerationStatus | null;
  }>;
  onGetGeneratedDocumentFile?: (
    documentId: string,
    format?: 'pdf' | 'docx',
    version?: number
  ) => Promise<StudyDocumentFilePayload | null>;
  onCancelGeneration?: (documentId: string) => void;
  pipelineStage?: string;
}

export const StudyGeneratedDocumentView: React.FC<StudyGeneratedDocumentViewProps> = ({
  document,
  onGetGeneratedDocumentStatus,
  onGenerateStudyDocument,
  onGetGeneratedDocumentFile,
  onCancelGeneration,
  pipelineStage,
}) => {
  const [status, setStatus] = useState<StudyDocumentGenerationStatus | null>(null);
  const [qaReport, setQaReport] = useState<StudyDocumentQAReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<'pdf' | 'docx' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<string>('ACADEMIC_EDITORIAL_CLASSIC');
  const [exportDocx, setExportDocx] = useState<boolean>(true);
  const [expandedFindings, setExpandedFindings] = useState<boolean>(false);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);

  const docId = document?.document_id;

  useEffect(() => {
    return () => {
      if (previewPdfUrl) {
        URL.revokeObjectURL(previewPdfUrl);
      }
    };
  }, [previewPdfUrl]);

  useEffect(() => {
    setPreviewPdfUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }, [docId]);

  const loadStatus = async () => {
    if (!docId || !onGetGeneratedDocumentStatus) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await onGetGeneratedDocumentStatus(docId);
      setStatus(res);
      if (res?.qa_report) {
        setQaReport(res.qa_report);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '';
      setError(msg || 'Não foi possível consultar o estado documental.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, [docId]);

  const handleGenerate = async (forceRecompute: boolean) => {
    if (!docId || !onGenerateStudyDocument) return;
    setIsGenerating(true);
    setError(null);
    try {
      const res = await onGenerateStudyDocument(docId, {
        forceRecompute,
        autoGeneratePlan: true,
        designProfileId: selectedProfile,
        exportDocx,
      });
      if (res.status) {
        setStatus(res.status);
        if (res.status.qa_report) {
          setQaReport(res.status.qa_report);
        }
      } else if (res.result) {
        setQaReport(res.result.qa_report);
        await loadStatus();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '';
      setError(msg || 'Falha na composição documental local.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async (format: 'pdf' | 'docx') => {
    if (!docId || !onGetGeneratedDocumentFile) return;
    setIsDownloading(format);
    setError(null);
    try {
      const fileData = await onGetGeneratedDocumentFile(docId, format);
      if (!fileData || !fileData.base64_data) {
        throw new Error(`Ficheiro ${format.toUpperCase()} não disponível.`);
      }

      // Descarregar via Blob no browser
      const byteCharacters = atob(fileData.base64_data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: fileData.mime_type });
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = fileData.filename;
      window.document.body.appendChild(link);
      link.click();
      window.document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '';
      setError(msg || `Erro ao descarregar ${format.toUpperCase()}.`);
    } finally {
      setIsDownloading(null);
    }
  };

  const handleTogglePdfPreview = async () => {
    if (previewPdfUrl) {
      URL.revokeObjectURL(previewPdfUrl);
      setPreviewPdfUrl(null);
      return;
    }
    if (!docId || !onGetGeneratedDocumentFile) return;
    setIsLoadingPreview(true);
    setError(null);
    try {
      const fileData = await onGetGeneratedDocumentFile(docId, 'pdf');
      if (!fileData || !fileData.base64_data) {
        throw new Error('Pré-visualização PDF não disponível.');
      }
      const byteCharacters = atob(fileData.base64_data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const blob = new Blob([new Uint8Array(byteNumbers)], { type: fileData.mime_type || 'application/pdf' });
      const url = URL.createObjectURL(blob);
      setPreviewPdfUrl(url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '';
      setError(msg || 'Não foi possível abrir a pré-visualização inline do PDF.');
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const renderStateBadge = () => {
    const st = status?.state || 'PENDING';
    if (st === 'COMPLETED') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-300 border border-emerald-500/30">
          <CheckCircle2 className="h-4 w-4" /> Concluído (v{status?.version ?? 1})
        </span>
      );
    }
    if (st === 'PARTIAL') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-300 border border-amber-500/30">
          <AlertTriangle className="h-4 w-4" /> Checkpoint Parcial (Retomável)
        </span>
      );
    }
    if (st === 'PROCESSING') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-cyan-500/15 px-2.5 py-1 text-xs font-semibold text-cyan-300 border border-cyan-500/30">
          <Loader2 className="h-4 w-4 animate-spin" /> Em Composição
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded bg-white/5 px-2.5 py-1 text-xs font-semibold text-gray-400 border border-white/10">
        Não Gerado
      </span>
    );
  };

  const renderQABadge = (report?: StudyDocumentQAReport | null) => {
    if (!report) return null;
    const st = report.validation_status;
    if (st === 'VALID') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300 border border-emerald-500/40">
          <ShieldCheck className="h-3.5 w-3.5" /> Auditoria Aprovada ({Math.round(report.overall_score * 100)}%)
        </span>
      );
    }
    if (st === 'VALID_WITH_WARNINGS') {
      return (
        <span className="inline-flex items-center gap-1 rounded bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300 border border-amber-500/40">
          <AlertTriangle className="h-3.5 w-3.5" /> Aprovado com Avisos ({Math.round(report.overall_score * 100)}%)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-xs font-semibold text-rose-300 border border-rose-500/40">
        <AlertCircle className="h-3.5 w-3.5" /> Bloqueante / Rejeitado ({Math.round(report.overall_score * 100)}%)
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-gray-400 space-y-3">
        <Loader2 className="h-7 w-7 animate-spin text-cyan-400" />
        <span className="text-sm">A carregar motor de composição documental...</span>
      </div>
    );
  }

  const hasPdf = Boolean(status?.has_pdf);
  const hasDocx = Boolean(status?.has_docx);
  const telemetry = status?.telemetry;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Banner / Card */}
      <div className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-md p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-cyan-400" />
              <h2 className="text-lg font-semibold text-white">
                Composição & Geração Documental (Fase 5)
              </h2>
            </div>
            <p className="text-xs text-gray-400">
              Gera documentos de estudo aprofundados (PDF de alta fidelidade e DOCX) a partir do plano editorial
              e síntese visual com inferência local (qwen3.5:9b).
            </p>
          </div>

          <div className="flex items-center gap-2">
            {renderStateBadge()}
            {renderQABadge(qaReport)}
          </div>
        </div>

        {/* Stale Warning */}
        {status?.is_stale && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-4 py-2.5 text-xs text-amber-200 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <span>
                O plano editorial foi atualizado após a última geração documental ({status.stale_reason}).
                Recomenda-se regerar o documento de estudo para manter total fidelidade.
              </span>
            </span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-950/30 px-4 py-2.5 text-xs text-rose-200 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </span>
            <button
              onClick={() => setError(null)}
              className="text-rose-400 hover:text-rose-200 text-xs ml-2"
            >
              Fechar
            </button>
          </div>
        )}

        {/* Live Progress Stage */}
        {(isGenerating || pipelineStage) && (
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 px-4 py-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-cyan-300 font-medium flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
                {pipelineStage || 'A compor documento de estudo...'}
              </span>
              {onCancelGeneration && isGenerating && (
                <button
                  onClick={() => onCancelGeneration(docId)}
                  className="rounded px-2 py-0.5 text-[11px] bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"
                >
                  Cancelar Geração
                </button>
              )}
            </div>
            <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
              <div className="bg-cyan-500 h-full animate-pulse rounded-full" style={{ width: '80%' }} />
            </div>
          </div>
        )}

        {/* Action Controls & Options */}
        <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Palette className="h-3.5 w-3.5 text-gray-400" />
              <label htmlFor="design-profile-select" className="text-xs text-gray-300">Perfil Visual:</label>
              <select
                id="design-profile-select"
                aria-label="Perfil Visual"
                value={selectedProfile}
                onChange={(e) => setSelectedProfile(e.target.value)}
                disabled={isGenerating}
                className="bg-black/60 border border-white/10 rounded px-2.5 py-1 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="ACADEMIC_EDITORIAL_CLASSIC">Clássico Editorial Académico (Serif/Sans)</option>
                <option value="TECHNICAL_SCIENTIFIC_MODERN">Moderno Técnico-Científico (Sans/Mono)</option>
              </select>
            </div>

            <label className="flex items-center gap-1.5 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={exportDocx}
                onChange={(e) => setExportDocx(e.target.checked)}
                disabled={isGenerating}
                className="rounded border-white/20 bg-black/40 text-cyan-500 focus:ring-0"
              />
              <span>Exportar também DOCX</span>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleGenerate(false)}
              disabled={isGenerating}
              className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow hover:bg-cyan-500 disabled:opacity-50 transition"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>A Processar...</span>
                </>
              ) : (
                <>
                  <BookOpen className="h-3.5 w-3.5" />
                  <span>{hasPdf ? 'Regerar Documento' : 'Gerar Documento Completo'}</span>
                </>
              )}
            </button>

            {hasPdf && (
              <button
                onClick={() => handleGenerate(true)}
                disabled={isGenerating}
                title="Ignora checkpoints e recalcula todo o conteúdo"
                className="flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-gray-300 hover:bg-white/10 disabled:opacity-50 transition"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Forçar Recomputação</span>
              </button>
            )}

            {/* Inline PDF Preview + Download Buttons */}
            {hasPdf && (
              <button
                type="button"
                data-testid="generated-doc-preview-toggle"
                onClick={handleTogglePdfPreview}
                disabled={isLoadingPreview}
                className="flex items-center gap-1.5 rounded-md border border-sky-400/35 bg-sky-500/15 px-3 py-1.5 text-xs font-semibold text-sky-200 hover:bg-sky-500/25 disabled:opacity-50 transition cursor-pointer"
              >
                {isLoadingPreview ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : previewPdfUrl ? (
                  <EyeOff className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
                <span>{previewPdfUrl ? 'Ocultar PDF' : 'Pré-visualizar PDF'}</span>
              </button>
            )}

            {hasPdf && (
              <button
                onClick={() => handleDownload('pdf')}
                disabled={isDownloading !== null}
                className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50 transition cursor-pointer"
              >
                {isDownloading === 'pdf' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                <span>Descarregar PDF</span>
              </button>
            )}

            {hasDocx && (
              <button
                onClick={() => handleDownload('docx')}
                disabled={isDownloading !== null}
                className="flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-gray-200 hover:bg-white/10 disabled:opacity-50 transition"
              >
                {isDownloading === 'docx' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                <span>Descarregar DOCX</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Inline PDF Viewer */}
      {previewPdfUrl && (
        <section
          data-testid="generated-doc-inline-preview"
          className="overflow-hidden rounded-xl border border-slate-800 bg-[#0b111a]"
        >
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-xs">
            <span className="font-semibold text-slate-200">Pré-visualização do Documento IA (PDF)</span>
            <button
              type="button"
              onClick={handleTogglePdfPreview}
              className="text-slate-400 hover:text-white cursor-pointer"
            >
              Fechar pré-visualização
            </button>
          </div>
          <iframe
            src={previewPdfUrl}
            title="Pré-visualização do Documento IA"
            className="h-[640px] w-full border-none bg-white"
          />
        </section>
      )}

      {/* Metrics & Telemetry Card */}
      {hasPdf && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-1">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider">Extensão do Documento</span>
            <div className="text-xl font-bold text-white">
              {telemetry?.pdf_pages_count ?? '—'} <span className="text-xs font-normal text-gray-400">páginas</span>
            </div>
            <div className="text-[11px] text-gray-500">
              {telemetry?.total_words_count ? `${telemetry.total_words_count.toLocaleString()} palavras` : ''}
            </div>
          </div>

          <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-1">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider">Elementos Visuais</span>
            <div className="text-xl font-bold text-cyan-300">
              {telemetry?.visuals_rendered_count ?? 0} <span className="text-xs font-normal text-gray-400">gerados</span>
            </div>
            <div className="text-[11px] text-gray-500">Gráficos & Mapas Fundamentados</div>
          </div>

          <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-1">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider">Tempo de Composição</span>
            <div className="text-xl font-bold text-amber-300">
              {telemetry?.total_pipeline_time_ms ? `${(telemetry.total_pipeline_time_ms / 1000).toFixed(1)}s` : '—'}
            </div>
            <div className="text-[11px] text-gray-500">
              LLM: {telemetry?.llm_total_time_ms ? `${(telemetry.llm_total_time_ms / 1000).toFixed(1)}s` : '0s'}
            </div>
          </div>

          <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-1">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider">Tamanho do Ficheiro</span>
            <div className="text-xl font-bold text-emerald-300">
              {status?.pdf_size_bytes ? `${(status.pdf_size_bytes / (1024 * 1024)).toFixed(2)} MB` : '—'}
            </div>
            <div className="text-[11px] text-gray-500">
              DOCX: {status?.docx_size_bytes ? `${(status.docx_size_bytes / 1024).toFixed(0)} KB` : '—'}
            </div>
          </div>
        </div>
      )}

      {/* QA Quality Assurance Panel */}
      {qaReport && (
        <div className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-md p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
              <h3 className="text-sm font-semibold text-white">
                Relatório de Garantia de Qualidade Documental (QA — 4 Eixos)
              </h3>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> Score: {Math.round(qaReport.overall_score * 100)}%
              </span>
              {qaReport.blocking_count > 0 && (
                <span className="flex items-center gap-1 text-rose-400">
                  <AlertCircle className="h-3.5 w-3.5" /> {qaReport.blocking_count} Erros Bloqueantes
                </span>
              )}
              {qaReport.warning_count > 0 && (
                <span className="flex items-center gap-1 text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" /> {qaReport.warning_count} Avisos
                </span>
              )}
            </div>
          </div>

          {/* 4 Axes Scores */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-1">
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3 space-y-1">
              <span className="text-[11px] text-gray-400">Integridade de Conteúdo</span>
              <div className="text-base font-bold text-white">
                {Math.round(qaReport.content_integrity_score * 100)}%
              </div>
              <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                <div
                  className="bg-cyan-500 h-full rounded-full"
                  style={{ width: `${Math.round(qaReport.content_integrity_score * 100)}%` }}
                />
              </div>
            </div>

            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3 space-y-1">
              <span className="text-[11px] text-gray-400">Integridade Visual</span>
              <div className="text-base font-bold text-white">
                {Math.round(qaReport.visual_integrity_score * 100)}%
              </div>
              <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-full"
                  style={{ width: `${Math.round(qaReport.visual_integrity_score * 100)}%` }}
                />
              </div>
            </div>

            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3 space-y-1">
              <span className="text-[11px] text-gray-400">Integridade Documental</span>
              <div className="text-base font-bold text-white">
                {Math.round(qaReport.document_integrity_score * 100)}%
              </div>
              <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                <div
                  className="bg-amber-500 h-full rounded-full"
                  style={{ width: `${Math.round(qaReport.document_integrity_score * 100)}%` }}
                />
              </div>
            </div>

            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3 space-y-1">
              <span className="text-[11px] text-gray-400">Qualidade Pedagógica</span>
              <div className="text-base font-bold text-white">
                {Math.round(qaReport.pedagogical_quality_score * 100)}%
              </div>
              <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full rounded-full"
                  style={{ width: `${Math.round(qaReport.pedagogical_quality_score * 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Expandable Findings */}
          {qaReport.findings && qaReport.findings.length > 0 && (
            <div className="pt-2">
              <button
                onClick={() => setExpandedFindings((prev) => !prev)}
                className="flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium"
              >
                {expandedFindings ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                <span>
                  {expandedFindings ? 'Ocultar apontamentos de auditoria' : `Ver ${qaReport.findings.length} apontamentos de auditoria`}
                </span>
              </button>

              {expandedFindings && (
                <div className="mt-3 space-y-2 max-h-60 overflow-y-auto pr-1">
                  {qaReport.findings.map((f, i) => (
                    <div
                      key={i}
                      className={`rounded-lg border p-3 text-xs space-y-1 ${
                        f.severity === 'BLOCKING_ERROR'
                          ? 'border-rose-500/30 bg-rose-950/20 text-rose-200'
                          : f.severity === 'WARNING'
                          ? 'border-amber-500/30 bg-amber-950/20 text-amber-200'
                          : 'border-white/10 bg-white/[0.02] text-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono text-[11px]">
                        <span className="font-semibold">{f.code} ({f.axis})</span>
                        <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-black/40 border border-white/10">
                          {f.severity}
                        </span>
                      </div>
                      <p>{f.message}</p>
                      {f.page_number && (
                        <span className="text-[10px] text-gray-400">Página afetada: {f.page_number}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
