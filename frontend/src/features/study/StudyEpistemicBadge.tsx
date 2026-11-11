import React from 'react';
import { AlertCircle, BookOpen, CheckCircle2, HelpCircle, ShieldAlert, Sparkles } from 'lucide-react';
import type { EditorialEvidenceRef, StudyModeReadiness } from './types';

export const EpistemicBadge: React.FC<{
  status?: string;
  isHypothetical?: boolean;
}> = ({ status, isHypothetical }) => {
  if (isHypothetical) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
        <Sparkles className="h-3 w-3" /> Cenário Hipotético (MODEL_INFERENCE)
      </span>
    );
  }
  const s = (status || 'MODEL_INFERENCE').toUpperCase();
  if (s === 'SOURCE_FACT') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
        <CheckCircle2 className="h-3 w-3" /> Facto na Fonte
      </span>
    );
  }
  if (s === 'UNVERIFIED' || s === 'NOT_FOUND') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-rose-400/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium text-rose-300">
        <ShieldAlert className="h-3 w-3" /> {s === 'NOT_FOUND' ? 'Não Encontrado' : 'Não Verificado'}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-medium text-cyan-300">
      <HelpCircle className="h-3 w-3" /> Inferência Pedagógica
    </span>
  );
};

export const EvidenceRefChips: React.FC<{
  refs?: EditorialEvidenceRef[];
  pages?: number[];
}> = ({ refs = [], pages = [] }) => {
  const uniqueLabels: string[] = [];
  const seen = new Set<string>();
  for (const r of refs) {
    const parts: string[] = [];
    if (r.page_number) parts.push(`p. ${r.page_number}`);
    if (r.section_id) parts.push(r.section_id);
    if (r.paragraph_id) parts.push(r.paragraph_id);
    const lbl = parts.join(' • ');
    if (lbl && !seen.has(lbl)) {
      seen.add(lbl);
      uniqueLabels.push(lbl);
    }
  }
  if (uniqueLabels.length === 0 && pages.length > 0) {
    uniqueLabels.push(`pp. ${pages.join(', ')}`);
  }
  if (uniqueLabels.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] text-gray-500 flex items-center gap-1">
        <BookOpen className="h-3 w-3" /> Fontes:
      </span>
      {uniqueLabels.slice(0, 4).map((lbl, i) => (
        <span
          key={i}
          className="rounded border border-white/10 bg-black/40 px-1.5 py-0.5 font-mono text-[10px] text-gray-300"
        >
          {lbl}
        </span>
      ))}
    </div>
  );
};

export const ReadinessBanner: React.FC<{
  readiness: StudyModeReadiness | null;
  onGoToSummary?: () => void;
}> = ({ readiness, onGoToSummary }) => {
  if (!readiness) return null;
  if (readiness.is_ready && !readiness.is_stale) return null;

  const isBlocking = !readiness.is_ready;
  return (
    <div
      className={`rounded-xl border px-4 py-3 text-xs flex flex-wrap items-center justify-between gap-3 ${
        isBlocking
          ? 'border-amber-500/30 bg-amber-950/25 text-amber-200'
          : 'border-cyan-500/30 bg-cyan-950/20 text-cyan-200'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">
            {isBlocking ? 'Pré-requisitos académicos em falta' : 'Artefactos de estudo possivelmente desatualizados'}
          </p>
          <p className="text-[11px] opacity-90 mt-0.5">{readiness.actionable_message}</p>
        </div>
      </div>
      {isBlocking && onGoToSummary && (
        <button
          type="button"
          onClick={onGoToSummary}
          className="rounded-md bg-amber-500/20 border border-amber-400/40 px-3 py-1.5 text-[11px] font-semibold text-amber-200 hover:bg-amber-500/30 transition"
        >
          Ir para Resumo & Plano Editorial
        </button>
      )}
    </div>
  );
};

