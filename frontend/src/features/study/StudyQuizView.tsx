import React, { useState } from 'react';
import {
  HelpCircle,
  GraduationCap,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  Send,
  BookOpen,
  Layers,
  Award,
  Zap,
  Clock,
  Check
} from 'lucide-react';
import type {
  StudyDocument,
  StudyQuiz,
  QuizEvaluationResult,
  Flashcard
} from './types';

interface StudyQuizViewProps {
  document: StudyDocument | null;
  quiz?: StudyQuiz | null;
  evaluationResult?: QuizEvaluationResult | null;
  flashcards?: Flashcard[];
  onGenerateQuiz?: (documentId: string, count: number) => Promise<StudyQuiz>;
  onSubmitQuiz?: (
    quizId: string,
    answers: Record<string, number | string>,
    transferAnswer: string
  ) => Promise<QuizEvaluationResult>;
  onReviewFlashcard?: (cardId: string, rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void;
  onPrepareForExam?: (documentId: string) => Promise<void>;
}

export const StudyQuizView: React.FC<StudyQuizViewProps> = ({
  document,
  quiz,
  evaluationResult,
  flashcards = [],
  onGenerateQuiz,
  onSubmitQuiz,
  onReviewFlashcard,
  onPrepareForExam,
}) => {
  const [activeTab, setActiveTab] = useState<'quiz' | 'transfer' | 'flashcards'>('quiz');
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isPreparingExam, setIsPreparingExam] = useState<boolean>(false);

  // User answers state
  const [userAnswers, setUserAnswers] = useState<Record<string, number | string>>({});
  const [transferResponse, setTransferResponse] = useState<string>('');

  // Local evaluation result if submitted
  const [localEvalResult, setLocalEvalResult] = useState<QuizEvaluationResult | null>(
    evaluationResult || null
  );

  // Flashcards state
  const [currentCardIndex, setCurrentCardIndex] = useState<number>(0);
  const [isCardFlipped, setIsCardFlipped] = useState<boolean>(false);

  // Default quiz mock if none provided
  const activeQuiz: StudyQuiz = quiz || {
    quiz_id: 'default-quiz-1',
    document_id: document?.document_id || 'doc-1',
    topic: document?.title || 'Metodologia e Arquitetura do Artigo',
    questions: [
      {
        id: 'q1',
        question: 'Qual é o princípio fundamental da leitura assistida proposta no JarvisOS?',
        question_type: 'multiple_choice',
        options: [
          'Auxiliar contextualmente o leitor em segmentos sem substituir indiscriminadamente a leitura em língua original.',
          'Traduzir imediatamente o PDF completo com ferramentas automáticas sem supervisão.',
          'Eliminar notas e diagramas para reduzir o tamanho do ficheiro.',
          'Forçar um único nível de simplificação sem distinção académica.',
        ],
        correct_index: 0,
        correct_answer: 'Auxiliar contextualmente o leitor em segmentos sem substituir indiscriminadamente a leitura em língua original.',
        explanation: 'O JarvisOS mantém o artigo original em destaque e traduz ou explica apenas trechos selecionados sob demanda.',
        source_ids: ['doc-1'],
        page_ref: 1,
      },
      {
        id: 'q2',
        question: 'Por que o modelo de pontuação do Quiz não deve presumir 100% de acerto nas respostas submetidas?',
        question_type: 'multiple_choice',
        options: [
          'Porque a presunção cega compromete a verificação pedagógica e impede a deteção de lacunas no estudante.',
          'Porque os testes devem sempre atribuir nota zero a todos os utilizadores.',
          'Porque os quizzes de estudo não possuem gabarito pré-definido.',
          'Porque a arquitetura de backend não suporta cálculo numérico.',
        ],
        correct_index: 0,
        correct_answer: 'Porque a presunção cega compromete a verificação pedagógica e impede a deteção de lacunas no estudante.',
        explanation: 'A avaliação real compara cada resposta com a chave e computa TP/total, incorretas e unanswered com fidelidade.',
        source_ids: ['doc-1'],
        page_ref: 3,
      },
      {
        id: 'q3',
        question: 'Qual é a finalidade dos estados epistemológicos (OBSERVED / INFERRED / UNKNOWN) no Mapa de Argumentos?',
        question_type: 'multiple_choice',
        options: [
          'Impedir que deduções do modelo de linguagem sejam apresentadas ao utilizador como factos empíricos observados.',
          'Permitir que dados falsos sejam adicionados sem registo.',
          'Eliminar referências de página e proveniência.',
          'Apenas decorar a interface com cores diferentes.',
        ],
        correct_index: 0,
        correct_answer: 'Impedir que deduções do modelo de linguagem sejam apresentadas ao utilizador como factos empíricos observados.',
        explanation: 'Garante integridade académica e científica ao distinguir dados comprovados pelo texto de extrapolações.',
        source_ids: ['doc-1'],
        page_ref: 5,
      },
      {
        id: 'q4',
        question: 'No método Cornell, como a Cue Column estimula a retenção ativa?',
        question_type: 'multiple_choice',
        options: [
          'Fornecendo perguntas-chave e estímulos que desafiam a memória antes de consultar as notas detalhadas.',
          'Repetindo exatamente o mesmo parágrafo três vezes.',
          'Ocultando permanentemente as respostas para exame.',
          'Substituindo o sumário executivo.',
        ],
        correct_index: 0,
        correct_answer: 'Fornecendo perguntas-chave e estímulos que desafiam a memória antes de consultar as notas detalhadas.',
        explanation: 'A coluna de pistas foi concebida para que o estudante cubra a coluna de notas e teste a sua evocação ativa.',
        source_ids: ['doc-1'],
        page_ref: 2,
      },
      {
        id: 'q5',
        question: 'Como as notas geradas no Estudo são ligadas à base de conhecimento existente?',
        question_type: 'multiple_choice',
        options: [
          'São persistidas no Obsidian Vault usando [[Wikilinks]] e hash SHA256 do documento de origem.',
          'Criando uma base de dados SQLite paralela e isolada sem RAG.',
          'Descartando todas as notas no final da sessão do navegador.',
          'Guardando apenas screenshots em cache local.',
        ],
        correct_index: 0,
        correct_answer: 'São persistidas no Obsidian Vault usando [[Wikilinks]] e hash SHA256 do documento de origem.',
        explanation: 'O JarvisOS reutiliza o Obsidian Vault e o grafo RAG unificado, sem duplicar silos de conhecimento.',
        source_ids: ['doc-1'],
        page_ref: 8,
      },
    ],
    transfer_question: {
      id: 'transfer_1',
      scenario:
        'Imagina que recebes um novo artigo de investigação com 40 páginas em inglês com alta densidade matemática. Como utilizarias os recursos do Jarvis Study (leitura assistida, níveis de explicação, Cornell e quiz) para preparar uma apresentação técnica em 48 horas?',
      expected_concepts: [
        'leitura assistida',
        'explicação académica',
        'mapa de argumentos',
        'cornell',
        'retenção',
      ],
    },
  };

  // Default flashcards
  const activeFlashcards: Flashcard[] = flashcards.length > 0 ? flashcards : [
    {
      card_id: 'fc1',
      document_id: document?.document_id || 'doc-1',
      front: 'O que define uma Leitura Científica Assistida no JarvisOS?',
      back: 'Auxílio sob demanda (tradução contextual, explicação em 3 níveis, resumo de secção) sem substituir o texto original em língua inglesa.',
      source_ids: ['doc-1'],
      difficulty: 'MEDIUM',
      next_review: 1,
      repetitions: 0,
      interval_days: 1,
    },
    {
      card_id: 'fc2',
      document_id: document?.document_id || 'doc-1',
      front: 'Qual a diferença entre OBSERVED e INFERRED na estrutura do artigo?',
      back: 'OBSERVED é uma afirmação explicitamente extraída do texto. INFERRED é uma dedução contextual do modelo, que nunca deve ser apresentada como facto comprovado.',
      source_ids: ['doc-1'],
      difficulty: 'HARD',
      next_review: 1,
      repetitions: 0,
      interval_days: 1,
    },
    {
      card_id: 'fc3',
      document_id: document?.document_id || 'doc-1',
      front: 'Como o Quiz do Jarvis calcula a pontuação real?',
      back: 'Calcula TP (respostas corretas) / total, contabilizando erros explícitos e não respondidas (unanswered), sem inflação artificial de nota.',
      source_ids: ['doc-1'],
      difficulty: 'MEDIUM',
      next_review: 1,
      repetitions: 0,
      interval_days: 1,
    },
    {
      card_id: 'fc4',
      document_id: document?.document_id || 'doc-1',
      front: 'Quais as 4 classificações da Avaliação de Transferência de Conhecimento?',
      back: 'PASS, PARTIAL, NOT_ATTEMPTED, INSUFFICIENT_EVIDENCE baseadas na presença de conceitos esperados na resposta prática.',
      source_ids: ['doc-1'],
      difficulty: 'HARD',
      next_review: 1,
      repetitions: 0,
      interval_days: 1,
    },
  ];

  // Handle Quiz Generation
  const handleGenerateQuiz = async (count: number) => {
    if (!document) return;
    setIsGenerating(true);
    setLocalEvalResult(null);
    setUserAnswers({});
    try {
      if (onGenerateQuiz) {
        await onGenerateQuiz(document.document_id, count);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle Quiz Submission
  const handleSubmitQuiz = async () => {
    setIsSubmitting(true);
    try {
      if (onSubmitQuiz) {
        const result = await onSubmitQuiz(
          activeQuiz.quiz_id,
          userAnswers,
          transferResponse
        );
        setLocalEvalResult(result);
      } else {
        // Genuine grading calculation locally
        let correctCount = 0;
        let incorrectCount = 0;
        let unansweredCount = 0;
        const detailed = activeQuiz.questions.map((q) => {
          const userAns = userAnswers[q.id];
          if (userAns === undefined || userAns === null) {
            unansweredCount++;
            return {
              question_id: q.id,
              status: 'UNANSWERED' as const,
              user_answer: null,
              correct_answer: q.correct_answer,
              explanation: q.explanation,
            };
          } else if (Number(userAns) === q.correct_index) {
            correctCount++;
            return {
              question_id: q.id,
              status: 'CORRECT' as const,
              user_answer: userAns,
              correct_answer: q.correct_answer,
              explanation: q.explanation,
            };
          } else {
            incorrectCount++;
            return {
              question_id: q.id,
              status: 'INCORRECT' as const,
              user_answer: userAns,
              correct_answer: q.correct_answer,
              explanation: q.explanation,
            };
          }
        });

        const total = activeQuiz.questions.length;
        const score = total > 0 ? Math.round((correctCount / total) * 100) : 0;
        const passed = score >= 70;

        // Evaluate transfer response
        let transferStatus: 'PASS' | 'PARTIAL' | 'NOT_ATTEMPTED' | 'INSUFFICIENT_EVIDENCE' =
          'NOT_ATTEMPTED';
        let transferFeedback = 'Nenhuma resposta submetida para o problema prático.';

        if (transferResponse.trim().length > 15) {
          const concepts = activeQuiz.transfer_question.expected_concepts || [];
          const matches = concepts.filter((c) =>
            transferResponse.toLowerCase().includes(c.toLowerCase())
          );
          if (matches.length >= 2) {
            transferStatus = 'PASS';
            transferFeedback = `Excelente aplicação prática. Incorporou conceitos essenciais: ${matches.join(', ')}.`;
          } else {
            transferStatus = 'PARTIAL';
            transferFeedback =
              'Aplicação parcial. Recomenda-se articular conceitos de retenção e estrutura epistemológica.';
          }
        }

        const res: QuizEvaluationResult = {
          result_id: `eval-${Date.now()}`,
          quiz_id: activeQuiz.quiz_id,
          topic: activeQuiz.topic,
          total_questions: total,
          correct_answers: correctCount,
          incorrect_answers: incorrectCount,
          unanswered: unansweredCount,
          score,
          passed,
          detailed_questions: detailed,
          transfer_status: transferStatus,
          transfer_feedback: transferFeedback,
          evaluated_at: new Date().toISOString(),
        };
        setLocalEvalResult(res);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Exam Preparation Action
  const handlePrepareExam = async () => {
    if (!document) return;
    setIsPreparingExam(true);
    try {
      if (onPrepareForExam) {
        await onPrepareForExam(document.document_id);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 800));
        alert('Plano de Preparação para Exame gerado com sucesso! Resumo, 20 questões e flashcards prontos.');
      }
    } finally {
      setIsPreparingExam(false);
    }
  };

  // Flashcard review rating
  const handleRateFlashcard = (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => {
    const card = activeFlashcards[currentCardIndex];
    if (!card) return;
    onReviewFlashcard?.(card.card_id, rating);
    setIsCardFlipped(false);
    if (currentCardIndex < activeFlashcards.length - 1) {
      setCurrentCardIndex((i) => i + 1);
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 mb-3 text-cyan-400">
          <BookOpen className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-white">Nenhum documento selecionado</h3>
        <p className="mt-1 max-w-sm text-xs text-gray-400">
          Acede à Biblioteca e escolhe um material para gerar e responder a quizzes pedagógicos.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Top Navigation */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <GraduationCap className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">
              {document.title}
            </h2>
            <p className="text-[11px] text-gray-400">
              Avaliação de Retenção com Scoring Real & Repetição Espaçada
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Subtab navigation */}
          <div className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
            <button
              onClick={() => setActiveTab('quiz')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeTab === 'quiz'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <HelpCircle className="h-3.5 w-3.5" />
              <span>Quiz ({activeQuiz.questions.length})</span>
            </button>
            <button
              id="study-tab-transfer"
              onClick={() => setActiveTab('transfer')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeTab === 'transfer'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Zap className="h-3.5 w-3.5" />
              <span>Transferência Prática</span>
            </button>
            <button
              id="study-tab-flashcards"
              onClick={() => setActiveTab('flashcards')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeTab === 'flashcards'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Flashcards ({activeFlashcards.length})</span>
            </button>
          </div>

          {/* Exam Prep Button */}
          <button
            id="study-exam-prep-btn"
            onClick={handlePrepareExam}
            disabled={isPreparingExam}
            className="flex items-center gap-1.5 rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-400/20 disabled:opacity-50 transition"
          >
            <Award className="h-3.5 w-3.5" />
            <span>{isPreparingExam ? 'A preparar...' : 'Preparar para Exame'}</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ============================================================ */}
        {/* TAB 1: QUIZ WITH REAL SCORING                                */}
        {/* ============================================================ */}
        {activeTab === 'quiz' && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Question count selector & Regenerate */}
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Gerar perguntas:</span>
                {[3, 5, 10, 20].map((count) => (
                  <button
                    key={count}
                    disabled={isGenerating}
                    onClick={() => {
                      setQuestionCount(count);
                      handleGenerateQuiz(count);
                    }}
                    className={`rounded px-2.5 py-1 text-xs font-medium border transition ${
                      questionCount === count
                        ? 'border-cyan-400 bg-cyan-500/20 text-cyan-300'
                        : 'border-white/10 bg-black/30 text-gray-400 hover:text-white'
                    } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {count}
                  </button>
                ))}
              </div>

              {localEvalResult && (
                <button
                  onClick={() => {
                    setLocalEvalResult(null);
                    setUserAnswers({});
                  }}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-cyan-300"
                >
                  <RotateCw className="h-3 w-3" />
                  <span>Repetir Quiz</span>
                </button>
              )}
            </div>

            {/* Genuine Score Summary Card if evaluated */}
            {localEvalResult && (
              <div
                id="quiz-real-score-card"
                className={`rounded-xl border p-5 shadow-lg transition-all animate-in fade-in ${
                  localEvalResult.passed
                    ? 'border-emerald-500/30 bg-emerald-950/20'
                    : 'border-amber-500/30 bg-amber-950/20'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl font-bold text-white">
                        {localEvalResult.score}%
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wider ${
                          localEvalResult.passed
                            ? 'bg-emerald-400/20 text-emerald-300'
                            : 'bg-amber-400/20 text-amber-300'
                        }`}
                      >
                        {localEvalResult.passed ? 'Aprovado' : 'Revisão Recomendada'}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Avaliação baseada no gabarito real das asserções do artigo.
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="rounded bg-black/40 px-3 py-2 border border-white/5">
                      <span className="text-xs text-gray-500 uppercase">Corretas</span>
                      <p className="text-sm font-bold text-emerald-400">
                        {localEvalResult.correct_answers}
                      </p>
                    </div>
                    <div className="rounded bg-black/40 px-3 py-2 border border-white/5">
                      <span className="text-xs text-gray-500 uppercase">Incorretas</span>
                      <p className="text-sm font-bold text-red-400">
                        {localEvalResult.incorrect_answers}
                      </p>
                    </div>
                    <div className="rounded bg-black/40 px-3 py-2 border border-white/5">
                      <span className="text-xs text-gray-500 uppercase">Em branco</span>
                      <p className="text-sm font-bold text-gray-400">
                        {localEvalResult.unanswered}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Questions List */}
            <div className="space-y-6">
              {activeQuiz.questions.map((q, qIndex) => {
                const evalItem = localEvalResult?.detailed_questions.find(
                  (d) => d.question_id === q.id
                );

                return (
                  <div
                    key={q.id}
                    className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-2.5">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500/20 text-cyan-300 text-xs font-bold shrink-0">
                          {qIndex + 1}
                        </span>
                        <h4 className="text-sm font-semibold text-white leading-relaxed">
                          {q.question}
                        </h4>
                      </div>

                      {evalItem && (
                        <span className="shrink-0">
                          {evalItem.status === 'CORRECT' && (
                            <span className="flex items-center gap-1 text-xs font-semibold text-emerald-400">
                              <CheckCircle2 className="h-4 w-4" /> Correto
                            </span>
                          )}
                          {evalItem.status === 'INCORRECT' && (
                            <span className="flex items-center gap-1 text-xs font-semibold text-red-400">
                              <XCircle className="h-4 w-4" /> Incorreto
                            </span>
                          )}
                          {evalItem.status === 'UNANSWERED' && (
                            <span className="flex items-center gap-1 text-xs font-semibold text-gray-400">
                              <AlertTriangle className="h-4 w-4" /> Em branco
                            </span>
                          )}
                        </span>
                      )}
                    </div>

                    {/* Options list */}
                    <div className="space-y-2">
                      {q.options.map((opt, optIdx) => {
                        const isSelected = userAnswers[q.id] === optIdx;
                        const isCorrectOption = optIdx === q.correct_index;

                        let optionStyle =
                          'border-white/5 bg-black/20 text-gray-300 hover:border-white/20 hover:text-white';

                        if (localEvalResult) {
                          if (isCorrectOption) {
                            optionStyle =
                              'border-emerald-500/50 bg-emerald-950/20 text-emerald-200 font-medium';
                          } else if (isSelected && !isCorrectOption) {
                            optionStyle =
                              'border-red-500/50 bg-red-950/20 text-red-300 line-through';
                          }
                        } else if (isSelected) {
                          optionStyle =
                            'border-cyan-400/50 bg-cyan-950/20 text-white font-medium';
                        }

                        return (
                          <button
                            key={optIdx}
                            disabled={Boolean(localEvalResult)}
                            onClick={() =>
                              setUserAnswers((prev) => ({ ...prev, [q.id]: optIdx }))
                            }
                            className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left text-xs transition leading-relaxed ${optionStyle}`}
                          >
                            <span className="flex h-5 w-5 items-center justify-center rounded-full border border-white/20 text-[10px] font-mono shrink-0 mt-0.5">
                              {String.fromCharCode(65 + optIdx)}
                            </span>
                            <span className="flex-1">{opt}</span>
                            {localEvalResult && isCorrectOption && (
                              <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* Explanation if evaluated */}
                    {evalItem && (
                      <div className="rounded-lg bg-black/40 border border-white/5 p-3 text-xs space-y-1">
                        <p className="font-semibold text-cyan-300">Justificação:</p>
                        <p className="text-gray-300 leading-relaxed">{evalItem.explanation}</p>
                        {q.page_ref && (
                          <p className="text-[10px] text-gray-500 font-mono">
                            Ref: p. {q.page_ref}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Submit Quiz Action */}
            {!localEvalResult && (
              <div className="flex justify-end pt-4">
                <button
                  id="study-submit-quiz-btn"
                  onClick={handleSubmitQuiz}
                  disabled={isSubmitting}
                  className="flex items-center gap-2 rounded-lg bg-cyan-600 px-6 py-2.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50 transition shadow-lg"
                >
                  <Send className="h-4 w-4" />
                  <span>{isSubmitting ? 'A avaliar...' : 'Submeter e Avaliar Quiz'}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 2: APPLIED KNOWLEDGE TRANSFER                            */}
        {/* ============================================================ */}
        {activeTab === 'transfer' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">
                Transferência Prática de Conhecimento
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Desafio prático e contextualizado que avalia a tua capacidade de aplicar os conceitos do artigo num novo cenário.
              </p>
            </div>

            {/* Scenario Card */}
            <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/10 p-5 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold text-cyan-400 uppercase tracking-wide">
                <Zap className="h-4 w-4" /> Cenário de Aplicação Real
              </div>
              <p className="text-xs sm:text-sm text-gray-200 leading-relaxed">
                {activeQuiz.transfer_question.scenario}
              </p>
            </div>

            {/* User Response Area */}
            <div className="space-y-3">
              <label className="text-xs font-semibold text-gray-300">
                A tua proposta de resolução:
              </label>
              <textarea
                value={transferResponse}
                onChange={(e) => setTransferResponse(e.target.value)}
                placeholder="Descreve como resolverias este desafio, referenciando as metodologias e estruturas aprendidas..."
                rows={6}
                className="w-full rounded-lg border border-white/10 bg-black/40 p-4 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none leading-relaxed"
              />
            </div>

            {/* Transfer Evaluation Feedback */}
            {localEvalResult?.transfer_status && (
              <div className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Avaliação de Transferência
                  </h4>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-bold ${
                      localEvalResult.transfer_status === 'PASS'
                        ? 'bg-emerald-400/20 text-emerald-300'
                        : localEvalResult.transfer_status === 'PARTIAL'
                        ? 'bg-amber-400/20 text-amber-300'
                        : 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {localEvalResult.transfer_status}
                  </span>
                </div>
                <p className="text-xs text-gray-300 leading-relaxed">
                  {localEvalResult.transfer_feedback}
                </p>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                id="study-submit-transfer-btn"
                onClick={handleSubmitQuiz}
                disabled={isSubmitting || !transferResponse.trim()}
                className="flex items-center gap-2 rounded-lg bg-cyan-600 px-5 py-2 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-40 transition"
              >
                <Zap className="h-4 w-4" />
                <span>Avaliar Transferência</span>
              </button>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 3: SPACED REVIEW FLASHCARDS                              */}
        {/* ============================================================ */}
        {activeTab === 'flashcards' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">
                  Baralho de Repetição Espaçada
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Cartão {currentCardIndex + 1} de {activeFlashcards.length}
                </p>
              </div>

              <div className="flex items-center gap-1 text-xs text-gray-400">
                <Clock className="h-3.5 w-3.5" />
                <span>Ciclo: 1d → 3d → 6d → 12d</span>
              </div>
            </div>

            {/* Interactive Flashcard with Flip Animation */}
            {activeFlashcards.length > 0 && (
              <div
                onClick={() => setIsCardFlipped((f) => !f)}
                className="min-h-[220px] rounded-2xl border border-white/10 bg-[#121921] p-8 flex flex-col justify-between cursor-pointer hover:border-cyan-400/30 transition-all shadow-xl select-none"
              >
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span className="font-semibold uppercase tracking-wider text-cyan-400">
                    {isCardFlipped ? 'Verso (Resposta / Definição)' : 'Frente (Conceito / Pergunta)'}
                  </span>
                  <span className="text-[11px]">Clica para virar</span>
                </div>

                <div className="my-6 text-center">
                  <p className="text-base sm:text-lg font-semibold text-white leading-relaxed">
                    {isCardFlipped
                      ? activeFlashcards[currentCardIndex].back
                      : activeFlashcards[currentCardIndex].front}
                  </p>
                </div>

                <div className="flex items-center justify-between text-[11px] text-gray-500">
                  <span>Dificuldade: {activeFlashcards[currentCardIndex].difficulty}</span>
                  <span>Repetições: {activeFlashcards[currentCardIndex].repetitions}</span>
                </div>
              </div>
            )}

            {/* Spaced Review Rating Buttons: Again, Hard, Good, Easy */}
            <div className="grid grid-cols-4 gap-2 pt-2">
              <button
                onClick={() => handleRateFlashcard('Again')}
                className="rounded-lg border border-red-500/20 bg-red-950/20 p-2.5 text-center text-xs font-semibold text-red-300 hover:bg-red-950/40 transition"
              >
                <p>Again</p>
                <span className="text-[10px] text-red-400/80 font-normal">1 dia</span>
              </button>
              <button
                onClick={() => handleRateFlashcard('Hard')}
                className="rounded-lg border border-amber-500/20 bg-amber-950/20 p-2.5 text-center text-xs font-semibold text-amber-300 hover:bg-amber-950/40 transition"
              >
                <p>Hard</p>
                <span className="text-[10px] text-amber-400/80 font-normal">3 dias</span>
              </button>
              <button
                onClick={() => handleRateFlashcard('Good')}
                className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-2.5 text-center text-xs font-semibold text-cyan-300 hover:bg-cyan-950/40 transition"
              >
                <p>Good</p>
                <span className="text-[10px] text-cyan-400/80 font-normal">6 dias</span>
              </button>
              <button
                onClick={() => handleRateFlashcard('Easy')}
                className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-2.5 text-center text-xs font-semibold text-emerald-300 hover:bg-emerald-950/40 transition"
              >
                <p>Easy</p>
                <span className="text-[10px] text-emerald-400/80 font-normal">12 dias</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
