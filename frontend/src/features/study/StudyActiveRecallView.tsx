import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Brain,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Send,
  Sparkles,
} from 'lucide-react';
import type {
  ActiveRecallAttempt,
  ActiveRecallPrompt,
  StudyDocument,
  StudyModeReadiness,
  StudyModesBridge,
  StudySessionState,
} from './types';
import { EpistemicBadge, EvidenceRefChips, ReadinessBanner } from './StudyEpistemicBadge';
import {
  getCurrentSessionItem,
  getSessionItems,
  isSessionAllItemsCompleted,
} from './dailyReviewSession';

interface StudyActiveRecallViewProps {
  document: StudyDocument | null;
  studyModes?: StudyModesBridge;
  onGoToSummary?: () => void;
  activeDailySession?: StudySessionState | null;
  onDailySessionUpdated?: (session: StudySessionState, options?: { navigateNext?: boolean }) => void;
  onPauseDailySession?: (draft?: { itemId: string; response: string }) => Promise<void>;
  onCompleteDailySession?: () => Promise<void>;
}

const PROMPT_TYPE_LABELS: Record<string, string> = {
  CONCEPT_EXPLANATION: 'Explicação de Conceito',
  ARGUMENT_RECONSTRUCTION: 'Reconstrução Argumentativa',
  METHODOLOGY_STEPS: 'Passos Metodológicos',
  CONCEPT_RELATIONSHIPS: 'Relações Conceptuais',
  RESULT_SIGNIFICANCE: 'Significado de Resultados',
  CHAPTER_STRUCTURE: 'Estrutura de Capítulo',
};

export const StudyActiveRecallView: React.FC<StudyActiveRecallViewProps> = ({
  document,
  studyModes,
  onGoToSummary,
  activeDailySession,
  onDailySessionUpdated,
  onPauseDailySession,
  onCompleteDailySession,
}) => {
  const [prompts, setPrompts] = useState<ActiveRecallPrompt[]>([]);
  const [history, setHistory] = useState<ActiveRecallAttempt[]>([]);
  const [readiness, setReadiness] = useState<StudyModeReadiness | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [showOutline, setShowOutline] = useState(false);
  const [responseText, setResponseText] = useState('');
  const [confidence, setConfidence] = useState(3);
  const [lastAttempt, setLastAttempt] = useState<ActiveRecallAttempt | null>(null);
  const [pendingAdvanceSession, setPendingAdvanceSession] = useState<StudySessionState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!document?.document_id || !studyModes) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await studyModes.getActiveRecall(document.document_id);
      setPrompts(res.prompts || []);
      setHistory(res.history || []);
      if (res.readiness) setReadiness(res.readiness);
      setActiveIdx(0);
      setLastAttempt(null);
      setResponseText('');
    } catch (err: any) {
      setError(err?.message || 'Erro ao carregar exercícios de Active Recall.');
    } finally {
      setIsLoading(false);
    }
  }, [document?.document_id, studyModes]);

  useEffect(() => {
    setPendingAdvanceSession(null);
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!activeDailySession) {
      setPendingAdvanceSession(null);
    }
  }, [activeDailySession]);

  useEffect(() => {
    setPendingAdvanceSession(null);
  }, [activeDailySession?.session_id]);

  const dailyCurrentItem = !pendingAdvanceSession ? getCurrentSessionItem(activeDailySession) : null;
  const isDailyActiveRecallStep = Boolean(
    activeDailySession && dailyCurrentItem && dailyCurrentItem.item_type === 'active_recall'
  );

  // Focus prompt matching the active Daily Review step and restore any paused draft
  useEffect(() => {
    if (!isDailyActiveRecallStep || !dailyCurrentItem || prompts.length === 0) return;
    const idx = prompts.findIndex((p) => p.prompt_id === dailyCurrentItem.item_id);
    if (idx >= 0) {
      setActiveIdx(idx);
      const savedDraft = activeDailySession?.partial_responses?.[dailyCurrentItem.item_id];
      setResponseText(typeof savedDraft === 'string' ? savedDraft : '');
      setLastAttempt(null);
      setShowOutline(false);
    }
  }, [
    isDailyActiveRecallStep,
    dailyCurrentItem?.item_id,
    activeDailySession?.session_id,
    activeDailySession?.partial_responses,
    prompts,
  ]);

  const activePrompt = prompts[activeIdx] || null;

  const handleGenerate = async () => {
    if (!document || !studyModes) return;
    setIsGenerating(true);
    setError(null);
    setPendingAdvanceSession(null);
    try {
      const res = await studyModes.generateActiveRecall(document.document_id, prompts.length > 0, 8);
      setPrompts(res.prompts || []);
      setActiveIdx(0);
      setLastAttempt(null);
      setResponseText('');
    } catch (err: any) {
      setError(err?.message || 'Falha ao gerar atividades de Active Recall.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSubmit = async () => {
    if (!document || !studyModes || !activePrompt || !responseText.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await studyModes.submitActiveRecall(document.document_id, activePrompt.prompt_id, {
        student_response: responseText,
        self_confidence: confidence,
        outline_used: showOutline,
        use_llm: false,
      });
      setLastAttempt(res.attempt);
      setHistory((prev) => [res.attempt, ...prev]);
      if (activeDailySession && isDailyActiveRecallStep) {
        const updatedSess = await studyModes.updateSession(activeDailySession.session_id, {
          item_id: activePrompt.prompt_id,
          item_type: 'active_recall',
          partial_response: responseText,
          outcome: {
            self_rating: res.attempt.self_rating,
            score_ratio: res.attempt.score_ratio,
            self_confidence: confidence,
          },
          mark_completed: true,
        });
        setPendingAdvanceSession(updatedSess);
        onDailySessionUpdated?.(updatedSess, { navigateNext: false });
      }
    } catch (err: any) {
      setError(err?.message || 'Erro ao registar tentativa de recuperação.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <BookOpen className="h-8 w-8 text-cyan-400 mb-3" />
        <h3 className="text-sm font-semibold text-white">Nenhum documento selecionado</h3>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Brain className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">{document.title}</h2>
            <p className="text-[11px] text-gray-400">
              Active Recall • Recuperação ativa antes da revelação das referências
            </p>
          </div>
        </div>

        <button
          type="button"
          disabled={isGenerating || (readiness ? !readiness.is_ready : false)}
          onClick={handleGenerate}
          className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          <span>{prompts.length > 0 ? 'Regenerar Exercícios' : 'Gerar Active Recall'}</span>
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-5">
          <ReadinessBanner readiness={readiness} onGoToSummary={onGoToSummary} />

          {(pendingAdvanceSession || (activeDailySession && isDailyActiveRecallStep && dailyCurrentItem)) && (() => {
            const bannerSess = (pendingAdvanceSession || activeDailySession)!;
            const totalItems = getSessionItems(bannerSess).length;
            const doneAll = isSessionAllItemsCompleted(bannerSess);
            return (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-400/35 bg-indigo-950/30 px-4 py-2.5 text-xs">
                <div className="space-y-0.5">
                  <p className="font-semibold text-indigo-200">
                    Sessão Diária Mista • {bannerSess.completed_item_ids.length}/{totalItems} concluídos (Active Recall)
                  </p>
                  <p className="text-[11px] text-indigo-300/80">
                    {pendingAdvanceSession
                      ? doneAll
                        ? 'Todos os itens da fila diária foram concluídos.'
                        : 'Item registado! Podes rever a referência abaixo e avançar para o próximo item.'
                      : `Item atual ${bannerSess.current_index + 1} / ${totalItems}${
                          dailyCurrentItem?.queue_category ? ` • Categoria: ${dailyCurrentItem.queue_category}` : ''
                        }`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {pendingAdvanceSession && onDailySessionUpdated && (
                    <button
                      type="button"
                      onClick={() => {
                        const sessToAdvance = pendingAdvanceSession;
                        setPendingAdvanceSession(null);
                        onDailySessionUpdated(sessToAdvance, { navigateNext: true });
                      }}
                      className="rounded bg-indigo-600 px-3 py-1 text-[11px] font-semibold text-white hover:bg-indigo-500"
                    >
                      {doneAll ? 'Concluir Sessão Diária ✓' : 'Próximo Item da Sessão →'}
                    </button>
                  )}
                  {onPauseDailySession && (
                    <button
                      type="button"
                      onClick={() =>
                        onPauseDailySession(
                          !pendingAdvanceSession && activePrompt && responseText.trim()
                            ? { itemId: activePrompt.prompt_id, response: responseText }
                            : undefined
                        )
                      }
                      className="rounded border border-amber-400/40 bg-amber-500/15 px-2.5 py-1 text-[11px] font-medium text-amber-200 hover:bg-amber-500/25"
                    >
                      Pausar Sessão
                    </button>
                  )}
                  {onCompleteDailySession && !pendingAdvanceSession && (
                    <button
                      type="button"
                      onClick={() => onCompleteDailySession()}
                      className="rounded border border-white/20 bg-black/30 px-2.5 py-1 text-[11px] font-medium text-gray-200 hover:text-white"
                    >
                      Concluir
                    </button>
                  )}
                </div>
              </div>
            );
          })()}

          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/30 px-4 py-2.5 text-xs text-rose-200">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="rounded-xl border border-white/10 bg-[#121921] p-12 text-center text-xs text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-400" />
              A carregar desafios de recuperação...
            </div>
          ) : !activePrompt ? (
            <div className="rounded-xl border border-white/10 bg-[#121921] p-10 text-center space-y-2">
              <Brain className="h-8 w-8 mx-auto text-gray-500" />
              <p className="text-sm font-semibold text-white">Sem atividades de Active Recall geradas</p>
              <p className="text-xs text-gray-400 max-w-md mx-auto">
                Esta experiência oculta propositadamente as respostas até que formules a tua reconstrução em memória livre.
              </p>
            </div>
          ) : (
            <>
              {/* Prompt Selector */}
              <div className="flex flex-wrap items-center gap-2">
                {prompts.map((p, idx) => (
                  <button
                    key={p.prompt_id}
                    type="button"
                    onClick={() => {
                      setPendingAdvanceSession(null);
                      setActiveIdx(idx);
                      setLastAttempt(null);
                      setResponseText('');
                      setShowOutline(false);
                    }}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium border transition ${
                      idx === activeIdx
                        ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200'
                        : 'border-white/10 bg-black/30 text-gray-400 hover:text-white'
                    }`}
                  >
                    #{idx + 1} • {PROMPT_TYPE_LABELS[p.prompt_type] || p.prompt_type}
                  </button>
                ))}
              </div>

              {/* Prompt Card */}
              <div className="rounded-xl border border-white/10 bg-[#121921] p-6 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-indigo-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-300 border border-indigo-400/20">
                      {PROMPT_TYPE_LABELS[activePrompt.prompt_type] || activePrompt.prompt_type}
                    </span>
                    <EpistemicBadge status={activePrompt.epistemic_status} />
                  </div>
                  <span className="text-[11px] text-gray-400">
                    {activePrompt.chapter_title} → {activePrompt.section_title}
                  </span>
                </div>

                <h3 className="text-base font-bold text-white leading-relaxed">
                  {activePrompt.prompt_text}
                </h3>

                {activePrompt.learning_objective_text && (
                  <p className="text-[11px] text-cyan-300/80">
                    Objetivo de aprendizagem: {activePrompt.learning_objective_text}
                  </p>
                )}

                {/* Optional Outline Toggle */}
                {activePrompt.optional_outline.length > 0 && (
                  <div className="space-y-2">
                    <button
                      type="button"
                      onClick={() => setShowOutline((s) => !s)}
                      className="flex items-center gap-1.5 text-xs text-amber-300 hover:text-amber-200"
                    >
                      {showOutline ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      <span>{showOutline ? 'Ocultar Guião Opcional' : 'Mostrar Guião Estruturado Opcional'}</span>
                    </button>
                    {showOutline && (
                      <ul className="rounded-lg border border-amber-500/20 bg-amber-950/15 p-3 space-y-1 text-xs text-amber-200 list-disc list-inside">
                        {activePrompt.optional_outline.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* Student Attempt Input */}
                <div className="space-y-3 pt-2 border-t border-white/10">
                  <label className="block text-xs font-semibold text-gray-300">
                    A tua reconstrução de memória (a referência da fonte só será revelada após submeter):
                  </label>
                  <textarea
                    rows={5}
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    placeholder="Escreve a explicação, passos metodológicos ou relações conceptuais sem consultar..."
                    className="w-full rounded-lg border border-white/10 bg-black/40 p-3.5 text-xs text-white placeholder-gray-500 focus:border-indigo-400 focus:outline-none leading-relaxed"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-gray-400">Confiança autoavaliada:</span>
                      {[1, 2, 3, 4, 5].map((lvl) => (
                        <button
                          key={lvl}
                          type="button"
                          onClick={() => setConfidence(lvl)}
                          className={`h-7 w-7 rounded text-xs font-bold border transition ${
                            confidence === lvl
                              ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200'
                              : 'border-white/10 bg-black/30 text-gray-400'
                          }`}
                        >
                          {lvl}
                        </button>
                      ))}
                    </div>

                    <button
                      type="button"
                      disabled={isSubmitting || responseText.trim().length < 5}
                      onClick={handleSubmit}
                      className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-40"
                    >
                      {isSubmitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                      <span>Submeter & Revelar Referência</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Post-Attempt Reveal & Rubric Comparison */}
              {lastAttempt && (
                <div className="rounded-xl border border-emerald-500/30 bg-[#121921] p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                        Referência Fundamentada & Avaliação
                      </h4>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-[11px] font-bold ${
                          lastAttempt.self_rating === 'RECALLED'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : lastAttempt.self_rating === 'PARTIAL'
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {lastAttempt.self_rating} ({Math.round(lastAttempt.score_ratio * 100)}%)
                      </span>
                    </div>
                  </div>

                  {lastAttempt.identified_gap_triggered && (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-950/25 px-3 py-2 text-xs text-amber-200 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span>Lacuna de conhecimento sinalizada neste conceito e priorizada na repetição espaçada.</span>
                    </div>
                  )}

                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-cyan-300 mb-1">
                      Referência da Fonte Original
                    </p>
                    <p className="text-xs text-gray-200 leading-relaxed whitespace-pre-wrap bg-black/30 rounded-lg p-3.5 border border-white/5">
                      {lastAttempt.revealed_reference}
                    </p>
                  </div>

                  {lastAttempt.evaluation && (
                    <div className="space-y-2 text-xs">
                      <p className="text-gray-300">
                        <strong className="text-white">Análise ({lastAttempt.evaluation.evaluation_mode}):</strong>{' '}
                        {lastAttempt.evaluation.reasoning}
                      </p>
                      {lastAttempt.evaluation.missing_points.length > 0 && (
                        <ul className="text-amber-300 list-disc list-inside space-y-0.5">
                          {lastAttempt.evaluation.missing_points.map((mp, i) => (
                            <li key={i}>{mp}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  <EvidenceRefChips refs={lastAttempt.evidence_refs} />

                  {pendingAdvanceSession && onDailySessionUpdated && (
                    <div className="flex justify-end pt-2 border-t border-white/10">
                      <button
                        type="button"
                        onClick={() => {
                          const sessToAdvance = pendingAdvanceSession;
                          setPendingAdvanceSession(null);
                          onDailySessionUpdated(sessToAdvance, { navigateNext: true });
                        }}
                        className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                      >
                        {isSessionAllItemsCompleted(pendingAdvanceSession)
                          ? 'Concluir Sessão Diária ✓'
                          : 'Avançar para Próximo Item da Sessão →'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* History summary */}
              {history.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-[#121921] p-4 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                    Tentativas Anteriores ({history.length})
                  </h4>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {history.slice(0, 6).map((h) => (
                      <div key={h.attempt_id} className="flex items-center justify-between rounded bg-black/30 px-3 py-2 text-xs">
                        <span className="truncate max-w-md text-gray-300">{h.student_response}</span>
                        <span className="font-mono text-[11px] text-cyan-300 shrink-0 ml-2">
                          {h.self_rating} • {Math.round(h.score_ratio * 100)}% • Confiança {h.self_confidence}/5
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

