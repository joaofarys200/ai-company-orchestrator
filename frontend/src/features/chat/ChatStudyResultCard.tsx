import React from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Loader2,
  XCircle,
} from 'lucide-react';
import type {
  StudyChatCard,
  StudyNavigatePayload,
  StudyOperationStatusPayload,
} from '../../protocol/websocket';

interface ChatStudyResultCardProps {
  card: StudyChatCard;
  liveOp?: StudyOperationStatusPayload;
  onNavigate: (target: Partial<StudyNavigatePayload>) => void;
  onCancelOperation: (operationId: string, documentId?: string) => void;
}

const EPISTEMIC_BADGE_MAP: Record<string, { label: string; cls: string }> = {
  SOURCE_FACT: {
    label: 'SOURCE_FACT',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30',
  },
  MODEL_INFERENCE: {
    label: 'MODEL_INFERENCE',
    cls: 'bg-amber-500/15 text-amber-200 border-amber-400/30',
  },
  NOT_FOUND: {
    label: 'NOT_FOUND',
    cls: 'bg-rose-500/15 text-rose-300 border-rose-400/30',
  },
  UNVERIFIED: {
    label: 'UNVERIFIED',
    cls: 'bg-slate-500/20 text-slate-300 border-slate-400/30',
  },
};

export const ChatStudyResultCard: React.FC<ChatStudyResultCardProps> = ({
  card,
  liveOp,
  onNavigate,
  onCancelOperation,
}) => {
  const effectiveStatus = String(liveOp?.status || card.status || 'COMPLETED').toUpperCase();
  const effectiveMessage = liveOp?.message || card.progress?.message;
  const effectiveStage = liveOp?.stage || card.progress?.stage;
  const pct =
    typeof liveOp?.progress_percent === 'number'
      ? liveOp.progress_percent
      : typeof card.progress?.percent === 'number'
      ? card.progress.percent
      : null;

  const isRunning = effectiveStatus === 'RUNNING' || effectiveStatus === 'QUEUED';
  const isCancelling = isRunning && effectiveStage === 'CANCELLING';
  const isFailed = effectiveStatus === 'FAILED';
  const isCancelled = effectiveStatus === 'CANCELLED';
  const isClarification = effectiveStatus === 'NEEDS_CLARIFICATION';

  const primaryEpistemic = card.epistemic_breakdown?.primary_status;
  const epMeta = primaryEpistemic ? EPISTEMIC_BADGE_MAP[primaryEpistemic] : null;
  const actions = card.actions || [];
  const citations = card.citations || [];

  return (
    <div
      data-testid="chat-study-result-card"
      className="mt-2.5 rounded-lg border border-cyan-400/20 bg-[#07111a]/80 p-3 text-xs text-gray-200 space-y-2"
    >
      {/* Header row: document title + operation status */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-semibold text-cyan-200 min-w-0">
          <BookOpen className="w-3.5 h-3.5 text-cyan-300 shrink-0" />
          <span className="truncate">{card.document_title || card.capability}</span>
        </div>

        <div className="flex items-center gap-1.5">
          {epMeta && (
            <span
              className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${epMeta.cls}`}
              title="Classificação epistémica predominante"
            >
              {epMeta.label}
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono border ${
              isRunning
                ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200'
                : isFailed
                ? 'border-rose-400/30 bg-rose-500/15 text-rose-200'
                : isCancelled
                ? 'border-amber-400/30 bg-amber-500/15 text-amber-200'
                : isClarification
                ? 'border-sky-400/30 bg-sky-500/15 text-sky-200'
                : 'border-emerald-400/30 bg-emerald-500/15 text-emerald-200'
            }`}
          >
            {isRunning && <Loader2 className="w-3 h-3 animate-spin" />}
            {effectiveStatus === 'COMPLETED' && <CheckCircle2 className="w-3 h-3" />}
            {isFailed && <AlertTriangle className="w-3 h-3" />}
            {isCancelled && <XCircle className="w-3 h-3" />}
            <span>{isCancelling ? 'CANCELLING' : effectiveStatus}</span>
          </span>
        </div>
      </div>

      {/* Live progress bar when running (only shows percentage when honestly available) */}
      {isRunning && (
        <div className="rounded bg-black/30 p-2 border border-white/5 space-y-1.5">
          <div className="flex items-center justify-between gap-2 text-[11px] text-cyan-100/90">
            <span className="flex items-center gap-1.5 truncate">
              <Activity className="w-3 h-3 text-cyan-300 shrink-0" />
              <span className="truncate">{effectiveMessage || effectiveStage || 'A processar...'}</span>
            </span>
            {pct !== null && <span className="font-mono text-cyan-300">{Math.round(pct)}%</span>}
          </div>
          {pct !== null && (
            <div className="h-1 w-full rounded bg-white/10 overflow-hidden">
              <div
                className="h-full bg-cyan-400 transition-all"
                style={{ width: `${Math.min(100, Math.max(2, pct))}%` }}
              />
            </div>
          )}
          <div className="flex justify-end">
            <button
              type="button"
              disabled={isCancelling}
              onClick={() => onCancelOperation(card.operation_id, card.document_id || undefined)}
              className="rounded border border-rose-400/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium text-rose-200 hover:bg-rose-500/20 disabled:opacity-50 cursor-pointer"
            >
              {isCancelling ? 'A cancelar...' : 'Cancelar operação'}
            </button>
          </div>
        </div>
      )}

      {/* Explicit error diagnostics */}
      {isFailed && card.error_message && (
        <div className="rounded border border-rose-500/25 bg-rose-950/30 px-2.5 py-1.5 text-[11px] text-rose-200">
          {card.error_message}
        </div>
      )}

      {/* Grounded provenance citations */}
      {citations.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {citations.slice(0, 5).map((cit, idx) => (
            <span
              key={idx}
              className="rounded bg-white/[0.04] border border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-gray-300"
            >
              {cit}
            </span>
          ))}
        </div>
      )}

      {/* Validated deep-link action buttons opening existing Study views */}
      {actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {actions.map((act, idx) => (
            <button
              key={`${act.tab}_${idx}`}
              type="button"
              onClick={() =>
                onNavigate({
                  document_id: act.document_id || card.document_id || undefined,
                  tab: act.tab,
                  chapter_id: act.chapter_id,
                  section_id: act.section_id,
                  assessment_id: act.assessment_id,
                  session_id: act.session_id || card.study_session_id || undefined,
                  topic: act.topic,
                })
              }
              className="inline-flex items-center gap-1 rounded-md border border-cyan-300/25 bg-cyan-400/10 px-2.5 py-1 text-[11px] font-medium text-cyan-100 hover:bg-cyan-400/20 hover:border-cyan-300/45 transition-all cursor-pointer"
            >
              <span>{act.label || `Abrir ${act.tab}`}</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
