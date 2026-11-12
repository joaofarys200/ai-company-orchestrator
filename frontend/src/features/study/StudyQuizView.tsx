import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Award,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Filter,
  HelpCircle,
  History,
  ListChecks,
  Loader2,
  Play,
  Send,
  Sliders,
  X,
  XCircle,
} from 'lucide-react';
import type {
  AssessmentAttempt,
  AssessmentConfig,
  AssessmentQuestion,
  QuestionAttemptOutcome,
  QuizEvaluationResult,
  StudyAssessment,
  StudyDocument,
  StudyModeReadiness,
  StudyModesBridge,
  StudyQuiz,
} from './types';
import { EpistemicBadge, EvidenceRefChips, ReadinessBanner } from './StudyEpistemicBadge';

interface StudyQuizViewProps {
  document: StudyDocument | null;
  studyModes?: StudyModesBridge;
  onGoToSummary?: () => void;
  initialTopicFilter?: string;
  quiz?: StudyQuiz | null;
  evaluationResult?: QuizEvaluationResult | null;
  flashcards?: unknown[];
  onGenerateQuiz?: (documentId: string, count: number) => Promise<StudyQuiz>;
  onSubmitQuiz?: (
    quizId: string,
    answers: Record<string, number | string>,
    transferAnswer: string
  ) => Promise<QuizEvaluationResult>;
  onReviewFlashcard?: (cardId: string, rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void;
  onPrepareForExam?: (documentId: string) => Promise<void>;
}

const QUESTION_TYPE_OPTIONS: Array<{ id: string; label: string }> = [
  { id: 'MULTIPLE_CHOICE', label: 'Escolha Múltipla' },
  { id: 'TRUE_FALSE', label: 'Verdadeiro / Falso' },
  { id: 'SHORT_ANSWER', label: 'Resposta Curta' },
  { id: 'CONCEPT_EXPLANATION', label: 'Explicação Conceptual' },
  { id: 'COMPARISON', label: 'Comparação' },
  { id: 'APPLICATION_SCENARIO', label: 'Cenário Hipotético' },
  { id: 'ANALYTICAL', label: 'Analítica' },
];

const VERDICT_META: Record<string, { label: string; cls: string }> = {
  CORRECT: {
    label: 'Correto',
    cls: 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300',
  },
  PARTIAL: {
    label: 'Parcial',
    cls: 'border-amber-400/40 bg-amber-500/15 text-amber-300',
  },
  INCOMPLETE_EXPLANATION: {
    label: 'Explicação Incompleta',
    cls: 'border-amber-400/40 bg-amber-500/15 text-amber-300',
  },
  FACTUAL_ERROR: {
    label: 'Erro Factual',
    cls: 'border-rose-400/40 bg-rose-500/15 text-rose-300',
  },
  AMBIGUOUS: {
    label: 'Ambíguo / Vago',
    cls: 'border-orange-400/40 bg-orange-500/15 text-orange-300',
  },
  UNANSWERED: {
    label: 'Em Branco',
    cls: 'border-white/15 bg-white/5 text-gray-400',
  },
};

export const StudyQuizView: React.FC<StudyQuizViewProps> = ({
  document,
  studyModes,
  onGoToSummary,
  initialTopicFilter = '',
  quiz: legacyQuizProp,
  evaluationResult: legacyEvalProp,
  onGenerateQuiz,
  onSubmitQuiz,
}) => {
  const [subtab, setSubtab] = useState<'session' | 'history'>('session');

  // Phase 6 state
  const [readiness, setReadiness] = useState<StudyModeReadiness | null>(null);
  const [assessments, setAssessments] = useState<StudyAssessment[]>([]);
  const [history, setHistory] = useState<AssessmentAttempt[]>([]);
  const [activeAssessment, setActiveAssessment] = useState<StudyAssessment | null>(null);
  const [activeAttempt, setActiveAttempt] = useState<AssessmentAttempt | null>(null);
  const [immediateOutcomes, setImmediateOutcomes] = useState<
    Record<string, QuestionAttemptOutcome>
  >({});
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [incorrectOnlyFilter, setIncorrectOnlyFilter] = useState(false);

  // Configurator state
  const [showConfigurator, setShowConfigurator] = useState(true);
  const [questionCount, setQuestionCount] = useState(6);
  const [sessionMode, setSessionMode] = useState<'PRACTICE' | 'ASSESSMENT'>('PRACTICE');
  const [difficulty, setDifficulty] = useState<'ALL' | 'EASY' | 'MEDIUM' | 'HARD'>('ALL');
  const [selectedTypes, setSelectedTypes] = useState<string[]>([
    'MULTIPLE_CHOICE',
    'TRUE_FALSE',
    'SHORT_ANSWER',
    'CONCEPT_EXPLANATION',
    'COMPARISON',
  ]);
  const [topicInput, setTopicInput] = useState(initialTopicFilter);
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([]);
  const [useLlmForOpen, setUseLlmForOpen] = useState(true);

  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCheckingId, setIsCheckingId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Legacy fallback state
  const [legacyQuiz, setLegacyQuiz] = useState<StudyQuiz | null>(legacyQuizProp || null);
  const [legacyEval, setLegacyEval] = useState<QuizEvaluationResult | null>(legacyEvalProp || null);
  const [legacyAnswers, setLegacyAnswers] = useState<Record<string, number | string>>({});

  useEffect(() => {
    if (initialTopicFilter) {
      setTopicInput(initialTopicFilter);
      setShowConfigurator(true);
      setActiveAttempt(null);
    }
  }, [initialTopicFilter]);

  useEffect(() => {
    if (legacyQuizProp) setLegacyQuiz(legacyQuizProp);
  }, [legacyQuizProp]);

  useEffect(() => {
    if (legacyEvalProp) setLegacyEval(legacyEvalProp);
  }, [legacyEvalProp]);

  const loadAssessments = useCallback(async () => {
    if (!document || !studyModes) return;
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await studyModes.getAssessments(document.document_id);
      setAssessments(res.assessments || []);
      setHistory(res.history || []);
      setReadiness(res.readiness);
      if (res.assessments && res.assessments.length > 0) {
        setActiveAssessment((prev) => prev || res.assessments[0]);
      } else {
        setActiveAssessment(null);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao carregar avaliações.');
    } finally {
      setIsLoading(false);
    }
  }, [document, studyModes]);

  useEffect(() => {
    setActiveAttempt(null);
    setImmediateOutcomes({});
    setAnswers({});
    setCurrentIdx(0);
    setIncorrectOnlyFilter(false);
    setErrorMsg(null);
    if (studyModes && document) {
      void loadAssessments();
    }
  }, [document?.document_id, studyModes, loadAssessments]);

  const availableChapters: Array<{ chapter_id: string; title: string }> =
    ((document?.metadata as Record<string, any> | undefined)?.editorial_plan?.chapters as Array<{
      chapter_id: string;
      title: string;
    }>) || [];

  const handleToggleType = (typeId: string) => {
    setSelectedTypes((prev) => {
      if (prev.includes(typeId)) {
        return prev.length > 1 ? prev.filter((x) => x !== typeId) : prev;
      }
      return [...prev, typeId];
    });
  };

  const handleGeneratePhase6 = async () => {
    if (!document || !studyModes) return;
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const config: Partial<AssessmentConfig> = {
        question_count: questionCount,
        session_mode: sessionMode,
        feedback_mode: sessionMode === 'PRACTICE' ? 'IMMEDIATE' : 'DEFERRED',
        difficulty,
        question_types: selectedTypes,
        topics: topicInput
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        chapter_ids: selectedChapterIds,
      };
      const created = await studyModes.generateAssessment(document.document_id, config);
      setAssessments((prev) => [created, ...prev]);
      setActiveAssessment(created);
      setActiveAttempt(null);
      setImmediateOutcomes({});
      setAnswers({});
      setCurrentIdx(0);
      setShowConfigurator(false);
      setSubtab('session');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao gerar avaliação.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCheckSingleQuestion = async (q: AssessmentQuestion) => {
    if (!document || !studyModes || !activeAssessment) return;
    const ans = answers[q.question_id];
    setIsCheckingId(q.question_id);
    setErrorMsg(null);
    try {
      const outcome = await studyModes.checkQuestion(
        document.document_id,
        activeAssessment.assessment_id,
        q.question_id,
        ans ?? '',
        useLlmForOpen
      );
      setImmediateOutcomes((prev) => ({ ...prev, [q.question_id]: outcome }));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao verificar questão.');
    } finally {
      setIsCheckingId(null);
    }
  };

  const handleSubmitFullAssessment = async () => {
    if (!document || !studyModes || !activeAssessment) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await studyModes.submitAssessment(
        document.document_id,
        activeAssessment.assessment_id,
        answers,
        useLlmForOpen
      );
      setActiveAttempt(res.attempt);
      setHistory((prev) => [res.attempt, ...prev]);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao submeter avaliação.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLegacyGenerate = async () => {
    if (!document || !onGenerateQuiz) return;
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const q = await onGenerateQuiz(document.document_id, questionCount);
      setLegacyQuiz(q);
      setLegacyEval(null);
      setLegacyAnswers({});
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao gerar quiz.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleLegacySubmit = async () => {
    if (!legacyQuiz || !onSubmitQuiz) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await onSubmitQuiz(legacyQuiz.quiz_id, legacyAnswers, '');
      setLegacyEval(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao submeter quiz.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 mb-3 text-cyan-400">
          <HelpCircle className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-white">Nenhum documento selecionado</h3>
        <p className="mt-1 max-w-sm text-xs text-gray-400">
          Seleciona um documento na Biblioteca para criar sessões de prática ou exame fundamentadas.
        </p>
      </div>
    );
  }

  // Legacy fallback view when studyModes is omitted
  if (!studyModes) {
    return (
      <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">{document.title}</h2>
            <p className="text-[11px] text-gray-400">Modo de Avaliação</p>
          </div>
          {onGenerateQuiz && (
            <button
              type="button"
              onClick={handleLegacyGenerate}
              disabled={isGenerating}
              className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
            >
              {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              <span>Gerar Quiz</span>
            </button>
          )}
        </header>
        {errorMsg && (
          <div className="bg-rose-950/40 border-b border-rose-500/30 px-6 py-2 text-xs text-rose-300 flex items-center justify-between shrink-0">
            <span>{errorMsg}</span>
            <button type="button" onClick={() => setErrorMsg(null)}>
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-6">
          {!legacyQuiz ? (
            <div className="max-w-xl mx-auto rounded-xl border border-white/10 bg-[#121921] p-8 text-center text-xs text-gray-400">
              Nenhum quiz ativo para este documento. Clica em "Gerar Quiz" para começar.
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {legacyQuiz.questions.map((q, idx) => (
                <div key={q.id} className="rounded-xl border border-white/10 bg-[#121921] p-4 space-y-3">
                  <p className="text-sm font-semibold text-white">
                    {idx + 1}. {q.question}
                  </p>
                  <div className="space-y-1.5">
                    {q.options.map((opt, optIdx) => (
                      <button
                        key={optIdx}
                        type="button"
                        disabled={Boolean(legacyEval)}
                        onClick={() => setLegacyAnswers((prev) => ({ ...prev, [q.id]: optIdx }))}
                        className={`w-full text-left rounded-lg border px-3 py-2 text-xs transition ${
                          legacyAnswers[q.id] === optIdx
                            ? 'border-cyan-400 bg-cyan-500/15 text-white'
                            : 'border-white/10 bg-black/25 text-gray-300'
                        }`}
                      >
                        {String.fromCharCode(65 + optIdx)}. {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {!legacyEval && onSubmitQuiz && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    id="study-submit-quiz-btn"
                    onClick={handleLegacySubmit}
                    disabled={isSubmitting}
                    className="rounded-lg bg-cyan-600 px-5 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
                  >
                    Submeter e Avaliar Quiz
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  const activeQuestion: AssessmentQuestion | undefined =
    activeAssessment?.questions?.[currentIdx];
  const immediateOutcome = activeQuestion
    ? immediateOutcomes[activeQuestion.question_id]
    : undefined;

  const displayedAttemptOutcomes = (activeAttempt?.outcomes || []).filter(
    (o) => !incorrectOnlyFilter || !o.is_correct
  );

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Header Bar */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <ListChecks className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">{document.title}</h2>
            <p className="text-[11px] text-gray-400">
              Avaliações Interativas, Rúbricas Fundamentadas & Verificação de Domínio
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
            <button
              type="button"
              onClick={() => setSubtab('session')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                subtab === 'session'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Play className="h-3.5 w-3.5" />
              <span>Sessão Ativa</span>
            </button>
            <button
              type="button"
              onClick={() => setSubtab('history')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                subtab === 'history'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <History className="h-3.5 w-3.5" />
              <span>Histórico ({history.length})</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              setSubtab('session');
              setShowConfigurator((v) => !v);
            }}
            className="flex items-center gap-1.5 rounded-md border border-white/15 bg-black/30 px-3 py-1.5 text-xs font-medium text-gray-200 hover:bg-white/10"
          >
            <Sliders className="h-3.5 w-3.5 text-cyan-400" />
            <span>{showConfigurator ? 'Fechar Configurador' : 'Nova Sessão / Configurar'}</span>
          </button>
        </div>
      </header>

      {errorMsg && (
        <div className="bg-rose-950/40 border-b border-rose-500/30 px-6 py-2 text-xs text-rose-300 flex items-center justify-between shrink-0">
          <span>{errorMsg}</span>
          <button type="button" onClick={() => setErrorMsg(null)}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-5">
          <ReadinessBanner readiness={readiness} onGoToSummary={onGoToSummary} />

          {/* HISTORY TAB */}
          {subtab === 'history' && (
            <div className="space-y-4">
              {history.length === 0 ? (
                <div className="rounded-xl border border-white/10 bg-[#121921] p-10 text-center text-xs text-gray-400">
                  Ainda não existem tentativas concluídas para este documento.
                </div>
              ) : (
                history.map((att) => (
                  <div
                    key={att.attempt_id}
                    className="rounded-xl border border-white/10 bg-[#121921] p-4 flex flex-wrap items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-white">{att.score_pct.toFixed(0)}%</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            att.passed
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-400/30'
                              : 'bg-amber-500/15 text-amber-300 border border-amber-400/30'
                          }`}
                        >
                          {att.passed ? 'Aprovado' : 'Reforço Recomendado'}
                        </span>
                        <span className="rounded border border-white/10 bg-black/30 px-2 py-0.5 text-[10px] font-mono text-gray-300">
                          {att.session_mode} • {att.feedback_mode}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">
                        {att.correct_count} corretas, {att.partial_count} parciais,{' '}
                        {att.incorrect_count} incorretas (de {att.total_questions}) •{' '}
                        {new Date(att.submitted_at).toLocaleString()}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveAttempt(att);
                        const matching = assessments.find((a) => a.assessment_id === att.assessment_id);
                        if (matching) setActiveAssessment(matching);
                        setShowConfigurator(false);
                        setSubtab('session');
                      }}
                      className="rounded-md border border-cyan-400/30 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/25"
                    >
                      Rever Respostas
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* SESSION CONFIGURATOR & RUNNER */}
          {subtab === 'session' && (
            <>
              {showConfigurator && (
                <div className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-white">Configurar Sessão de Avaliação</h3>
                      <p className="text-[11px] text-gray-400">
                        Define o modo de feedback, tipos de questão, dificuldade e escopo do documento.
                      </p>
                    </div>
                    {assessments.length > 0 && activeAssessment && (
                      <select
                        value={activeAssessment.assessment_id}
                        onChange={(e) => {
                          const found = assessments.find((a) => a.assessment_id === e.target.value);
                          if (found) {
                            setActiveAssessment(found);
                            setActiveAttempt(null);
                            setImmediateOutcomes({});
                            setAnswers({});
                            setCurrentIdx(0);
                            setShowConfigurator(false);
                          }
                        }}
                        className="rounded-md border border-white/15 bg-black/40 px-2.5 py-1.5 text-xs text-gray-200"
                      >
                        {assessments.map((a) => (
                          <option key={a.assessment_id} value={a.assessment_id}>
                            Retomar: {a.title} ({a.questions.length} q.)
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    {/* Mode */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold uppercase text-gray-400">
                        Modo & Feedback
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setSessionMode('PRACTICE')}
                          className={`rounded-lg border px-3 py-2 text-left transition ${
                            sessionMode === 'PRACTICE'
                              ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-200'
                              : 'border-white/10 bg-black/30 text-gray-400'
                          }`}
                        >
                          <p className="font-semibold">Prática</p>
                          <p className="text-[10px] opacity-80">Feedback imediato</p>
                        </button>
                        <button
                          type="button"
                          onClick={() => setSessionMode('ASSESSMENT')}
                          className={`rounded-lg border px-3 py-2 text-left transition ${
                            sessionMode === 'ASSESSMENT'
                              ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-200'
                              : 'border-white/10 bg-black/30 text-gray-400'
                          }`}
                        >
                          <p className="font-semibold">Avaliação</p>
                          <p className="text-[10px] opacity-80">Feedback no final</p>
                        </button>
                      </div>
                    </div>

                    {/* Question Count */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold uppercase text-gray-400">
                        Número de Questões ({questionCount})
                      </label>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {[3, 5, 6, 8, 10, 15].map((n) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() => setQuestionCount(n)}
                            className={`rounded-md border px-2.5 py-1.5 text-xs font-semibold ${
                              questionCount === n
                                ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200'
                                : 'border-white/10 bg-black/30 text-gray-400'
                            }`}
                          >
                            {n}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Difficulty */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold uppercase text-gray-400">
                        Dificuldade das Questões
                      </label>
                      <select
                        value={difficulty}
                        onChange={(e) =>
                          setDifficulty(e.target.value as 'ALL' | 'EASY' | 'MEDIUM' | 'HARD')
                        }
                        className="w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-xs text-white"
                      >
                        <option value="ALL">Mista (Todos os níveis)</option>
                        <option value="EASY">Básico (EASY)</option>
                        <option value="MEDIUM">Intermédio (MEDIUM)</option>
                        <option value="HARD">Avançado / Analítico (HARD)</option>
                      </select>
                    </div>
                  </div>

                  {/* Question Types */}
                  <div className="space-y-1.5 text-xs">
                    <label className="text-[11px] font-semibold uppercase text-gray-400">
                      Tipos de Questão (seleciona pelo menos 1)
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {QUESTION_TYPE_OPTIONS.map((t) => {
                        const active = selectedTypes.includes(t.id);
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => handleToggleType(t.id)}
                            className={`rounded-md border px-2.5 py-1 text-[11px] font-medium transition ${
                              active
                                ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-200'
                                : 'border-white/10 bg-black/25 text-gray-400 hover:text-gray-200'
                            }`}
                          >
                            {t.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Topic & Chapter Filters */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold uppercase text-gray-400">
                        Focar Tópicos (opcional, separados por vírgula)
                      </label>
                      <input
                        value={topicInput}
                        onChange={(e) => setTopicInput(e.target.value)}
                        placeholder="Ex: Attention, Regularização, Metodologia"
                        className="w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-xs text-white placeholder:text-gray-500"
                      />
                    </div>
                    {availableChapters.length > 0 && (
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold uppercase text-gray-400">
                          Filtrar Capítulos (vazio = todos)
                        </label>
                        <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">
                          {availableChapters.map((ch) => {
                            const checked = selectedChapterIds.includes(ch.chapter_id);
                            return (
                              <button
                                key={ch.chapter_id}
                                type="button"
                                onClick={() =>
                                  setSelectedChapterIds((prev) =>
                                    checked
                                      ? prev.filter((id) => id !== ch.chapter_id)
                                      : [...prev, ch.chapter_id]
                                  )
                                }
                                className={`rounded border px-2 py-1 text-[10px] transition ${
                                  checked
                                    ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-200'
                                    : 'border-white/10 bg-black/25 text-gray-400'
                                }`}
                              >
                                {ch.title}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-white/10">
                    <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useLlmForOpen}
                        onChange={(e) => setUseLlmForOpen(e.target.checked)}
                        className="rounded border-white/20 bg-black/40"
                      />
                      <span>Avaliar respostas abertas com Ollama local (qwen3.5:9b) + rúbrica</span>
                    </label>
                    <button
                      type="button"
                      onClick={handleGeneratePhase6}
                      disabled={isGenerating || (readiness ? !readiness.is_ready : false)}
                      className="flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
                    >
                      {isGenerating ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="h-3.5 w-3.5" />
                      )}
                      <span>{isGenerating ? 'A compor questões...' : 'Gerar Avaliação Fundamentada'}</span>
                    </button>
                  </div>
                </div>
              )}

              {isLoading ? (
                <div className="flex items-center justify-center py-12 text-xs text-gray-400 gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                  <span>A carregar sessões...</span>
                </div>
              ) : activeAttempt ? (
                /* RESULTS & REVIEW MODE */
                <div className="space-y-5">
                  <div
                    className={`rounded-xl border p-5 ${
                      activeAttempt.passed
                        ? 'border-emerald-500/30 bg-emerald-950/20'
                        : 'border-amber-500/30 bg-amber-950/20'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2.5">
                          <Award className="h-6 w-6 text-cyan-300" />
                          <span className="text-2xl font-bold text-white">
                            {activeAttempt.score_pct.toFixed(1)}%
                          </span>
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${
                              activeAttempt.passed
                                ? 'bg-emerald-400/20 text-emerald-300'
                                : 'bg-amber-400/20 text-amber-300'
                            }`}
                          >
                            {activeAttempt.passed ? 'Aprovado' : 'Revisão Recomendada'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-300 mt-1">
                          {activeAttempt.session_mode} ({activeAttempt.feedback_mode}) • Progresso e
                          lacunas conceptuais atualizados.
                        </p>
                      </div>

                      <div className="grid grid-cols-4 gap-2 text-center text-xs">
                        <div className="rounded bg-black/40 px-3 py-2 border border-white/10">
                          <span className="text-[10px] text-gray-400 block">Corretas</span>
                          <span className="font-bold text-emerald-400">{activeAttempt.correct_count}</span>
                        </div>
                        <div className="rounded bg-black/40 px-3 py-2 border border-white/10">
                          <span className="text-[10px] text-gray-400 block">Parciais</span>
                          <span className="font-bold text-amber-300">{activeAttempt.partial_count}</span>
                        </div>
                        <div className="rounded bg-black/40 px-3 py-2 border border-white/10">
                          <span className="text-[10px] text-gray-400 block">Incorretas</span>
                          <span className="font-bold text-rose-400">{activeAttempt.incorrect_count}</span>
                        </div>
                        <div className="rounded bg-black/40 px-3 py-2 border border-white/10">
                          <span className="text-[10px] text-gray-400 block">Branco</span>
                          <span className="font-bold text-gray-400">{activeAttempt.unanswered_count}</span>
                        </div>
                      </div>
                    </div>

                    {/* Topic & Difficulty Breakdown */}
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 pt-4 border-t border-white/10 text-xs">
                      <div className="rounded-lg bg-black/30 p-3 space-y-1.5">
                        <p className="text-[10px] font-bold uppercase text-cyan-300">
                          Desempenho por Tópico
                        </p>
                        {Object.entries(activeAttempt.by_topic || {}).map(([topic, stat]) => (
                          <div key={topic} className="flex items-center justify-between text-[11px]">
                            <span className="text-gray-300 truncate max-w-[70%]">{topic}</span>
                            <span className="font-mono text-white">
                              {stat.accuracy_pct}% ({stat.correct}/{stat.total})
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="rounded-lg bg-black/30 p-3 space-y-1.5">
                        <p className="text-[10px] font-bold uppercase text-cyan-300">
                          Desempenho por Dificuldade
                        </p>
                        {Object.entries(activeAttempt.by_difficulty || {}).map(([diff, stat]) => (
                          <div key={diff} className="flex items-center justify-between text-[11px]">
                            <span className="text-gray-300">{diff}</span>
                            <span className="font-mono text-white">
                              {stat.accuracy_pct}% ({stat.correct}/{stat.total})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Filter bar */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setIncorrectOnlyFilter((v) => !v)}
                      className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium ${
                        incorrectOnlyFilter
                          ? 'border-rose-400/50 bg-rose-500/15 text-rose-200'
                          : 'border-white/15 bg-[#121921] text-gray-300'
                      }`}
                    >
                      <Filter className="h-3.5 w-3.5" />
                      <span>
                        {incorrectOnlyFilter
                          ? 'A mostrar só incorretas / parciais'
                          : 'Rever apenas incorretas'}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveAttempt(null);
                        setShowConfigurator(true);
                      }}
                      className="rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500"
                    >
                      Iniciar Nova Sessão
                    </button>
                  </div>

                  {/* Detailed Outcome Cards */}
                  <div className="space-y-4">
                    {displayedAttemptOutcomes.map((o, i) => {
                      const vm = VERDICT_META[o.verdict] || VERDICT_META.PARTIAL;
                      return (
                        <div
                          key={o.question_id}
                          className="rounded-xl border border-white/10 bg-[#121921] p-4 space-y-3 text-xs"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono text-gray-400">#{i + 1}</span>
                              <span className="rounded border border-white/10 bg-black/30 px-2 py-0.5 text-[10px]">
                                {o.question_type} • {o.question_difficulty}
                              </span>
                              <span className="text-cyan-300 font-medium">{o.topic}</span>
                              <EpistemicBadge status={o.epistemic_status} />
                            </div>
                            <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${vm.cls}`}>
                              {vm.label} ({Math.round(o.score_ratio * 100)}%)
                            </span>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div className="rounded-lg bg-black/30 p-3 border border-white/5">
                              <p className="text-[10px] uppercase text-gray-400 mb-1">A tua resposta</p>
                              <p className="text-gray-200">
                                {o.student_answer !== null && o.student_answer !== undefined && o.student_answer !== ''
                                  ? String(o.student_answer)
                                  : '(Em branco)'}
                              </p>
                            </div>
                            <div className="rounded-lg bg-emerald-950/20 p-3 border border-emerald-500/20">
                              <p className="text-[10px] uppercase text-emerald-300 mb-1">
                                Resposta / Referência Fundamentada
                              </p>
                              <p className="text-emerald-100">{o.correct_answer}</p>
                            </div>
                          </div>

                          {o.open_evaluation && (
                            <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/15 p-3 space-y-1.5">
                              <p className="font-semibold text-cyan-300">
                                Avaliação por Rúbrica ({o.open_evaluation.evaluation_mode})
                              </p>
                              <p className="text-gray-200">{o.open_evaluation.reasoning}</p>
                              {o.open_evaluation.covered_points.length > 0 && (
                                <p className="text-emerald-300 text-[11px]">
                                  ✓ Pontos cobertos: {o.open_evaluation.covered_points.join('; ')}
                                </p>
                              )}
                              {o.open_evaluation.missing_points.length > 0 && (
                                <p className="text-amber-300 text-[11px]">
                                  ! Em falta: {o.open_evaluation.missing_points.join('; ')}
                                </p>
                              )}
                              {o.open_evaluation.factual_errors.length > 0 && (
                                <p className="text-rose-300 text-[11px]">
                                  ✕ Inconsistências: {o.open_evaluation.factual_errors.join('; ')}
                                </p>
                              )}
                            </div>
                          )}

                          {o.explanation && (
                            <p className="text-gray-300 leading-relaxed bg-black/25 rounded p-2.5">
                              <strong className="text-cyan-300">Explicação: </strong>
                              {o.explanation}
                            </p>
                          )}

                          <EvidenceRefChips refs={o.evidence_refs} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : activeAssessment && activeAssessment.questions.length > 0 && activeQuestion ? (
                /* SEQUENTIAL QUESTION RUNNER */
                <div className="space-y-4">
                  {/* Top Progress & Question Selector Pills */}
                  <div className="rounded-xl border border-white/10 bg-[#121921] p-4 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div>
                        <span className="font-bold text-white">{activeAssessment.title}</span>
                        <span className="ml-2 rounded border border-cyan-400/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                          {activeAssessment.config.session_mode} •{' '}
                          {activeAssessment.config.feedback_mode}
                        </span>
                      </div>
                      <span className="font-mono text-gray-400">
                        Questão {currentIdx + 1} / {activeAssessment.questions.length}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1.5">
                      {activeAssessment.questions.map((q, idx) => {
                        const checked = immediateOutcomes[q.question_id];
                        const hasAns =
                          answers[q.question_id] !== undefined && answers[q.question_id] !== '';
                        let cls = 'border-white/10 bg-black/30 text-gray-400';
                        if (idx === currentIdx) {
                          cls = 'border-cyan-400 bg-cyan-500/20 text-white font-bold';
                        } else if (checked) {
                          cls = checked.is_correct
                            ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300'
                            : 'border-rose-400/40 bg-rose-500/15 text-rose-300';
                        } else if (hasAns) {
                          cls = 'border-indigo-400/40 bg-indigo-500/15 text-indigo-200';
                        }
                        return (
                          <button
                            key={q.question_id}
                            type="button"
                            onClick={() => setCurrentIdx(idx)}
                            className={`h-7 min-w-[28px] rounded border px-2 text-xs transition ${cls}`}
                          >
                            {idx + 1}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Active Question Card */}
                  <div className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="rounded border border-white/10 bg-black/30 px-2 py-0.5 font-mono text-cyan-300">
                          {activeQuestion.question_type}
                        </span>
                        <span className="rounded border border-white/10 bg-black/30 px-2 py-0.5 text-gray-300">
                          {activeQuestion.question_difficulty}
                        </span>
                        <span className="text-gray-400">{activeQuestion.topic}</span>
                      </div>
                      <EpistemicBadge
                        status={activeQuestion.epistemic_status}
                        isHypothetical={activeQuestion.is_hypothetical_scenario}
                      />
                    </div>

                    <h4 className="text-sm font-semibold text-white leading-relaxed">
                      {activeQuestion.question_text}
                    </h4>

                    {/* Objective options vs Open response */}
                    {activeQuestion.question_type === 'MULTIPLE_CHOICE' ||
                    activeQuestion.question_type === 'TRUE_FALSE' ? (
                      <div className="space-y-2">
                        {(activeQuestion.options && activeQuestion.options.length > 0
                          ? activeQuestion.options
                          : ['Verdadeiro', 'Falso']
                        ).map((opt, optIdx) => {
                          const selected = answers[activeQuestion.question_id] === optIdx;
                          let style =
                            'border-white/10 bg-black/25 text-gray-300 hover:border-white/25';
                          if (immediateOutcome) {
                            if (optIdx === activeQuestion.correct_index) {
                              style = 'border-emerald-500/60 bg-emerald-950/25 text-emerald-200';
                            } else if (selected) {
                              style = 'border-rose-500/60 bg-rose-950/25 text-rose-200';
                            }
                          } else if (selected) {
                            style = 'border-cyan-400 bg-cyan-950/30 text-white';
                          }
                          return (
                            <button
                              key={optIdx}
                              type="button"
                              onClick={() =>
                                setAnswers((prev) => ({
                                  ...prev,
                                  [activeQuestion.question_id]: optIdx,
                                }))
                              }
                              className={`w-full flex items-start gap-3 rounded-lg border p-3 text-left text-xs transition ${style}`}
                            >
                              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-white/20 text-[10px] font-mono shrink-0">
                                {String.fromCharCode(65 + optIdx)}
                              </span>
                              <span className="flex-1">{opt}</span>
                              {immediateOutcome && optIdx === activeQuestion.correct_index && (
                                <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        <textarea
                          value={String(answers[activeQuestion.question_id] || '')}
                          onChange={(e) =>
                            setAnswers((prev) => ({
                              ...prev,
                              [activeQuestion.question_id]: e.target.value,
                            }))
                          }
                          rows={5}
                          placeholder="Escreve a tua resposta fundamentada..."
                          className="w-full rounded-lg border border-white/15 bg-black/40 p-3 text-xs text-white placeholder:text-gray-500 focus:border-cyan-400 focus:outline-none"
                        />
                        {activeQuestion.scoring_criteria &&
                          activeQuestion.scoring_criteria.length > 0 && (
                            <div className="rounded-lg border border-white/5 bg-black/25 p-2.5 text-[11px] text-gray-400">
                              <span className="font-semibold text-gray-300">Critérios esperados: </span>
                              {activeQuestion.scoring_criteria.map((c) => c.description).join(' • ')}
                            </div>
                          )}
                      </div>
                    )}

                    {/* Immediate Feedback Panel (PRACTICE Mode) */}
                    {immediateOutcome && (
                      <div className="rounded-xl border border-cyan-500/25 bg-black/40 p-4 space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold flex items-center gap-1.5">
                            {immediateOutcome.is_correct ? (
                              <>
                                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                                <span className="text-emerald-300">
                                  {VERDICT_META[immediateOutcome.verdict]?.label || 'Correto'}
                                </span>
                              </>
                            ) : immediateOutcome.score_ratio > 0 ? (
                              <>
                                <AlertTriangle className="h-4 w-4 text-amber-400" />
                                <span className="text-amber-300">
                                  {VERDICT_META[immediateOutcome.verdict]?.label || 'Parcial'}
                                </span>
                              </>
                            ) : (
                              <>
                                <XCircle className="h-4 w-4 text-rose-400" />
                                <span className="text-rose-300">
                                  {VERDICT_META[immediateOutcome.verdict]?.label || 'Incorreto'}
                                </span>
                              </>
                            )}
                          </span>
                          <span className="font-mono text-gray-300">
                            Pontuação: {Math.round(immediateOutcome.score_ratio * 100)}%
                          </span>
                        </div>
                        <p className="text-gray-200 leading-relaxed">{immediateOutcome.explanation}</p>
                        {immediateOutcome.open_evaluation && (
                          <p className="text-cyan-200 text-[11px]">
                            {immediateOutcome.open_evaluation.reasoning}
                          </p>
                        )}
                        <EvidenceRefChips refs={immediateOutcome.evidence_refs} />
                      </div>
                    )}

                    {/* Navigation + Check / Submit Actions */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-white/10">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                          disabled={currentIdx === 0}
                          className="flex items-center gap-1 rounded-md border border-white/15 bg-black/30 px-3 py-1.5 text-xs text-gray-200 disabled:opacity-40"
                        >
                          <ChevronLeft className="h-3.5 w-3.5" />
                          <span>Anterior</span>
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setCurrentIdx((i) =>
                              Math.min(activeAssessment.questions.length - 1, i + 1)
                            )
                          }
                          disabled={currentIdx >= activeAssessment.questions.length - 1}
                          className="flex items-center gap-1 rounded-md border border-white/15 bg-black/30 px-3 py-1.5 text-xs text-gray-200 disabled:opacity-40"
                        >
                          <span>Seguinte</span>
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {activeAssessment.config.feedback_mode === 'IMMEDIATE' && (
                          <button
                            type="button"
                            onClick={() => handleCheckSingleQuestion(activeQuestion)}
                            disabled={isCheckingId === activeQuestion.question_id}
                            className="flex items-center gap-1.5 rounded-md border border-cyan-400/40 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/25 disabled:opacity-50"
                          >
                            {isCheckingId === activeQuestion.question_id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Clock className="h-3.5 w-3.5" />
                            )}
                            <span>Verificar Questão</span>
                          </button>
                        )}
                        <button
                          type="button"
                          id="study-submit-quiz-btn"
                          onClick={handleSubmitFullAssessment}
                          disabled={isSubmitting}
                          className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
                        >
                          {isSubmitting ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Send className="h-3.5 w-3.5" />
                          )}
                          <span>{isSubmitting ? 'A avaliar...' : 'Submeter Sessão Completa'}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-white/10 bg-[#121921] p-8 text-center text-xs text-gray-400">
                  Configura os parâmetros acima e clica em "Gerar Avaliação Fundamentada" para iniciar.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
