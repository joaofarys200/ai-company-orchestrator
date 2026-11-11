import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Pause,
  Play,
  RefreshCw,
} from 'lucide-react';
import type {
  DailyReviewQueue,
  LearningProgressSnapshot,
  StudyDocument,
  StudyModesBridge,
  StudySessionState,
} from './types';
import { EvidenceRefChips } from './StudyEpistemicBadge';
import {
  buildDailySessionItems,
  getCurrentSessionItem,
  getSessionItems,
  resolveTabForSessionItem,
} from './dailyReviewSession';

interface StudyAdaptiveHubViewProps {
  document: StudyDocument | null;
  studyModes?: StudyModesBridge;
  onNavigateTab?: (tab: 'flashcards' | 'active_recall' | 'notes' | 'quiz', topicHint?: string) => void;
  onStartOrResumeSession?: (session: StudySessionState) => void;
}

const MASTERY_LABELS: Record<string, { label: string; style: string }> = {
  INSUFFICIENT_EVIDENCE: {
    label: 'Dados Insuficientes',
    style: 'border-gray-500/30 bg-gray-500/10 text-gray-300',
  },
  EMERGING: {
    label: 'Emergente',
    style: 'border-rose-400/30 bg-rose-500/10 text-rose-300',
  },
  DEVELOPING: {
    label: 'Em Consolidação',
    style: 'border-amber-400/30 bg-amber-500/10 text-amber-300',
  },
  PROFICIENT: {
    label: 'Proficiente (Verificado)',
    style: 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300',
  },
};

export const StudyAdaptiveHubView: React.FC<StudyAdaptiveHubViewProps> = ({
  document,
  studyModes,
  onNavigateTab,
  onStartOrResumeSession,
}) => {
  const [queue, setQueue] = useState<DailyReviewQueue | null>(null);
  const [progress, setProgress] = useState<LearningProgressSnapshot | null>(null);
  const [sessions, setSessions] = useState<StudySessionState[]>([]);
  const [dailyNewLimit, setDailyNewLimit] = useState<number>(10);
  const [dailyReviewLimit, setDailyReviewLimit] = useState<number>(25);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHub = useCallback(async () => {
    if (!document?.document_id || !studyModes) return;
    setIsLoading(true);
    setError(null);
    try {
      const [q, p, sessList] = await Promise.all([
        studyModes.getDailyQueue(document.document_id, dailyNewLimit, dailyReviewLimit),
        studyModes.getProgress(document.document_id, true),
        studyModes.listSessions(document.document_id),
      ]);
      setQueue(q);
      setProgress(p);
      setSessions(sessList || []);
    } catch (err: any) {
      setError(err?.message || 'Erro ao carregar revisão adaptativa e progresso.');
    } finally {
      setIsLoading(false);
    }
  }, [document?.document_id, studyModes, dailyNewLimit, dailyReviewLimit]);

  useEffect(() => {
    loadHub();
  }, [loadHub]);

  const handleStartDailySession = async () => {
    if (!document || !studyModes || !queue) return;
    const typedItems = buildDailySessionItems(queue);
    if (typedItems.length === 0) return;
    const itemIds = typedItems.map((i) => i.item_id);
    try {
      const s = await studyModes.startSession({
        document_id: document.document_id,
        mode: 'DAILY_REVIEW',
        title: `Revisão Diária (${typedItems.length} itens)`,
        items: typedItems,
        item_ids: itemIds,
        config: { dailyNewLimit, dailyReviewLimit },
      });
      setSessions((prev) => [s, ...prev]);
      if (onStartOrResumeSession) {
        onStartOrResumeSession(s);
      } else {
        const curItem = getCurrentSessionItem(s);
        const target = resolveTabForSessionItem(curItem, s.mode);
        onNavigateTab?.(target);
      }
    } catch (err: any) {
      setError(err?.message || 'Erro ao iniciar sessão diária.');
    }
  };

  const handleSessionAction = async (sess: StudySessionState, action: 'pause' | 'resume' | 'complete') => {
    if (!studyModes) return;
    try {
      const updated =
        action === 'pause'
          ? await studyModes.pauseSession(sess.session_id)
          : action === 'resume'
            ? await studyModes.resumeSession(sess.session_id)
            : await studyModes.completeSession(sess.session_id);
      setSessions((prev) => prev.map((s) => (s.session_id === updated.session_id ? updated : s)));
      if (action === 'resume') {
        if (onStartOrResumeSession) {
          onStartOrResumeSession(updated);
        } else {
          const curItem = getCurrentSessionItem(updated);
          const target = resolveTabForSessionItem(curItem, updated.mode);
          onNavigateTab?.(target);
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Erro ao atualizar sessão.');
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <BarChart3 className="h-8 w-8 text-cyan-400 mb-3" />
        <h3 className="text-sm font-semibold text-white">Seleciona um documento na Biblioteca</h3>
      </div>
    );
  }

  const mInfo = MASTERY_LABELS[progress?.mastery_level || 'INSUFFICIENT_EVIDENCE'] || MASTERY_LABELS.INSUFFICIENT_EVIDENCE;

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">{document.title}</h2>
            <p className="text-[11px] text-gray-400">
              Revisão Diária SM-2, Sessões Persistentes, Progresso & Lacunas de Conhecimento
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={loadHub}
          className="flex items-center gap-1.5 rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs font-medium text-gray-200 hover:border-cyan-400/40"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} /> Atualizar Métricas
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/30 px-4 py-2.5 text-xs text-rose-200">
              {error}
            </div>
          )}

          {isLoading && !progress ? (
            <div className="p-10 text-center text-xs text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-cyan-400" />
              A calcular fila diária e histórico...
            </div>
          ) : (
            <>
              {/* Daily Review Queue Card */}
              <section className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2">
                    <CalendarClock className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                      Plano de Revisão Diária ({queue?.total_queue_count || 0} itens selecionados)
                    </h3>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs">
                    <label className="flex items-center gap-1.5 text-gray-400">
                      Limite Novos:
                      <input
                        type="number"
                        min={0}
                        max={40}
                        value={dailyNewLimit}
                        onChange={(e) => setDailyNewLimit(Number(e.target.value) || 0)}
                        className="w-14 rounded border border-white/10 bg-black/40 px-2 py-1 text-white"
                      />
                    </label>
                    <label className="flex items-center gap-1.5 text-gray-400">
                      Limite Revisões:
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={dailyReviewLimit}
                        onChange={(e) => setDailyReviewLimit(Number(e.target.value) || 10)}
                        className="w-14 rounded border border-white/10 bg-black/40 px-2 py-1 text-white"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!queue || queue.total_queue_count === 0}
                      onClick={handleStartDailySession}
                      className="rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-40"
                    >
                      Iniciar Revisão Hoje
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                  <div className="rounded-lg border border-rose-500/20 bg-rose-950/15 p-3">
                    <p className="text-lg font-bold text-rose-300">{queue?.lapsed_items.length || 0}</p>
                    <p className="text-[11px] text-gray-400">Falhados / Lapsos</p>
                  </div>
                  <div className="rounded-lg border border-amber-500/20 bg-amber-950/15 p-3">
                    <p className="text-lg font-bold text-amber-300">{queue?.due_items.length || 0}</p>
                    <p className="text-[11px] text-gray-400">Devidos Hoje</p>
                  </div>
                  <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/15 p-3">
                    <p className="text-lg font-bold text-cyan-300">{queue?.low_confidence_items.length || 0}</p>
                    <p className="text-[11px] text-gray-400">Baixa Confiança / Fracos</p>
                  </div>
                  <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/15 p-3">
                    <p className="text-lg font-bold text-emerald-300">{queue?.new_items.length || 0}</p>
                    <p className="text-[11px] text-gray-400">Novos Introduzidos</p>
                  </div>
                </div>
              </section>

              {/* Progress Overview (Strictly evidence-gated) */}
              {progress && (
                <section className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-emerald-400" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                        Indicadores de Aprendizagem & Progresso
                      </h3>
                    </div>
                    <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${mInfo.style}`}>
                      {mInfo.label}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
                    <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                      <p className="text-base font-bold text-white">{progress.questions_answered}</p>
                      <p className="text-[11px] text-gray-400">Questões Respondidas</p>
                    </div>
                    <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                      <p className="text-base font-bold text-emerald-300">{progress.correct_answers}</p>
                      <p className="text-[11px] text-gray-400">Corretas</p>
                    </div>
                    <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                      <p className="text-base font-bold text-cyan-300">
                        {progress.overall_accuracy_pct !== null ? `${progress.overall_accuracy_pct}%` : 'N/D'}
                      </p>
                      <p className="text-[11px] text-gray-400">Precisão</p>
                    </div>
                    <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                      <p className="text-base font-bold text-white">{progress.flashcard_reviews_total}</p>
                      <p className="text-[11px] text-gray-400">Revisões SM-2</p>
                    </div>
                    <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                      <p className="text-base font-bold text-indigo-300">{progress.active_recall_attempts_total}</p>
                      <p className="text-[11px] text-gray-400">Active Recall</p>
                    </div>
                  </div>

                  {/* Concept & Chapter Breakdown */}
                  {Object.keys(progress.by_concept).length > 0 && (
                    <div className="space-y-2 pt-2">
                      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                        Desempenho por Conceito
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {Object.values(progress.by_concept).map((c) => {
                          const badge = MASTERY_LABELS[c.mastery_level] || MASTERY_LABELS.INSUFFICIENT_EVIDENCE;
                          return (
                            <div key={c.id} className="flex items-center justify-between rounded-lg bg-black/30 px-3 py-2 border border-white/5 text-xs">
                              <span className="font-medium text-gray-200 truncate mr-2">{c.label}</span>
                              <div className="flex items-center gap-2 shrink-0">
                                <span className="font-mono text-[11px] text-gray-400">
                                  {c.accuracy_pct}% ({c.attempts}x)
                                </span>
                                <span className={`rounded border px-1.5 py-0.5 text-[10px] ${badge.style}`}>
                                  {badge.label}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {progress.insufficient_evidence_objectives.length > 0 && (
                    <p className="text-[11px] text-gray-400">
                      Objetivos ainda sem evidência suficiente de domínio:{' '}
                      <span className="font-mono text-gray-300">
                        {progress.insufficient_evidence_objectives.join(', ')}
                      </span>
                    </p>
                  )}
                </section>
              )}

              {/* Knowledge Gaps */}
              <section className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-3">
                <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                    Lacunas de Conhecimento Identificadas ({progress?.knowledge_gaps.length || 0})
                  </h3>
                </div>

                {!progress || progress.knowledge_gaps.length === 0 ? (
                  <p className="text-xs text-gray-400">
                    Nenhuma lacuna recorrente detetada ainda (lacunas são inferidas apenas após múltiplos erros consistentes).
                  </p>
                ) : (
                  <div className="space-y-3">
                    {progress.knowledge_gaps.map((gap) => (
                      <div key={gap.gap_id} className="rounded-lg border border-amber-500/25 bg-black/30 p-4 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-bold text-amber-200">{gap.concept_name || gap.chapter_id}</span>
                          <span className="rounded bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold text-rose-300 border border-rose-500/30">
                            Severidade: {gap.severity} • {gap.failure_count} falhas / {gap.attempts_count} tentativas
                          </span>
                        </div>
                        <p className="text-xs text-gray-300">{gap.description}</p>
                        <EvidenceRefChips refs={gap.evidence_refs} />
                        {gap.suggested_activities.length > 0 && (
                          <div className="flex flex-wrap gap-2 pt-1">
                            {gap.suggested_activities.map((act, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  if (act.mode === 'ACTIVE_RECALL') onNavigateTab?.('active_recall');
                                  else if (act.mode === 'CORNELL_STUDY') onNavigateTab?.('notes');
                                  else if (act.mode === 'ASSESSMENT') onNavigateTab?.('quiz');
                                  else onNavigateTab?.('flashcards', gap.concept_name);
                                }}
                                className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] font-medium text-cyan-200 hover:bg-cyan-500/20"
                              >
                                {act.label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Persistent Sessions */}
              <section className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-white border-b border-white/10 pb-2">
                  Sessões de Estudo Persistentes ({sessions.length})
                </h3>
                {sessions.length === 0 ? (
                  <p className="text-xs text-gray-400">Nenhuma sessão iniciada para este documento.</p>
                ) : (
                  <div className="space-y-2">
                    {sessions.slice(0, 8).map((s) => {
                      const resolvedItems = getSessionItems(s);
                      const curItem = getCurrentSessionItem(s);
                      const totalCount = resolvedItems.length || s.item_ids.length;
                      return (
                      <div key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-black/30 px-3.5 py-2.5 border border-white/5 text-xs">
                        <div>
                          <p className="font-semibold text-white">{s.title}</p>
                          <p className="text-[11px] text-gray-400">
                            Modo: {s.mode} • Estado: <span className="text-cyan-300">{s.status}</span> • Progresso: {s.completed_item_ids.length}/{totalCount} itens
                            {curItem ? ` • Próximo: ${curItem.item_type === 'active_recall' ? 'Active Recall' : 'Flashcard'}` : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {(s.status === 'IN_PROGRESS' || s.status === 'PAUSED') && onStartOrResumeSession && (
                            <button
                              type="button"
                              onClick={() => (s.status === 'PAUSED' ? handleSessionAction(s, 'resume') : onStartOrResumeSession(s))}
                              className="flex items-center gap-1 rounded border border-emerald-500/30 px-2.5 py-1 text-[11px] text-emerald-300 hover:bg-emerald-950/30"
                            >
                              <Play className="h-3 w-3" /> {s.status === 'PAUSED' ? 'Retomar' : 'Continuar'}
                            </button>
                          )}
                          {s.status === 'IN_PROGRESS' && (
                            <button
                              type="button"
                              onClick={() => handleSessionAction(s, 'pause')}
                              className="flex items-center gap-1 rounded border border-amber-500/30 px-2.5 py-1 text-[11px] text-amber-300 hover:bg-amber-950/30"
                            >
                              <Pause className="h-3 w-3" /> Pausar
                            </button>
                          )}
                          {s.status === 'PAUSED' && !onStartOrResumeSession && (
                            <button
                              type="button"
                              onClick={() => handleSessionAction(s, 'resume')}
                              className="flex items-center gap-1 rounded border border-emerald-500/30 px-2.5 py-1 text-[11px] text-emerald-300 hover:bg-emerald-950/30"
                            >
                              <Play className="h-3 w-3" /> Retomar
                            </button>
                          )}
                          {s.status !== 'COMPLETED' && (
                            <button
                              type="button"
                              onClick={() => handleSessionAction(s, 'complete')}
                              className="flex items-center gap-1 rounded border border-white/15 px-2.5 py-1 text-[11px] text-gray-300 hover:text-white"
                            >
                              <CheckCircle2 className="h-3 w-3" /> Concluir
                            </button>
                          )}
                        </div>
                      </div>
                    );})}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

