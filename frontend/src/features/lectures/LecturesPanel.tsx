import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock,
  GraduationCap,
  HelpCircle,
  Mic,
  MicOff,
  RefreshCw,
  Send,
  Sparkles,
  User,
  Zap,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';

export const LecturesPanel: React.FC = () => {
  const {
    activeLecture,
    lectureQuizResult,
    lectureHistory,
    isGeneratingLecture,
    isSubmittingQuiz,
    isRecordingLecture,
    generateLectureLesson,
    submitLectureQuiz,
    listLectureHistory,
    startLectureRecording,
    stopLectureRecording,
  } = useWebSocket();

  const [topic, setTopic] = useState('Sistemas Multiagente e Arquiteturas RAG');
  const [subject, setSubject] = useState('Inteligência Artificial');
  const [professor, setProfessor] = useState('Prof. JARVIS');
  const [activeSubtab, setActiveSubtab] = useState<'cornell' | 'quiz' | 'transfer' | 'history'>('cornell');

  // Quiz state
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [transferAnswer, setTransferAnswer] = useState(
    'Aplicando nós distribuídos com isolamento de falhas, idempotência nas transações e recuperação atómica de estado.'
  );

  useEffect(() => {
    listLectureHistory();
  }, [listLectureHistory]);

  const handleGenerate = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!topic.trim()) return;
    generateLectureLesson(topic, subject, professor);
  };

  const handleOptionSelect = (questionId: string, optionIndex: number) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionIndex,
    }));
  };

  const handleSubmitQuiz = () => {
    if (!activeLecture) return;
    submitLectureQuiz(activeLecture.topic, selectedAnswers, transferAnswer);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0a0f14] text-gray-200">
      {/* Top Configuration & Action Bar */}
      <div className="border-b border-[#a1bebf]/15 bg-[#0f171d]/90 p-4 shadow-sm backdrop-blur">
        <form onSubmit={handleGenerate} className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <GraduationCap className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Centro de Aprendizagem & Aulas</h2>
              <p className="text-[11px] text-gray-400">Síntese Cornell Notes, Quizzes e Retenção Pedagógica</p>
            </div>
          </div>

          <div className="flex flex-1 flex-wrap items-center gap-2 min-w-[300px]">
            <input
              id="lecture-topic-input"
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Tópico da Aula (ex: Sistemas Multiagente...)"
              className="flex-1 min-w-[200px] rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400"
            />
            <input
              id="lecture-subject-input"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Disciplina (ex: Inteligência Artificial)"
              className="w-36 rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
            />
            <input
              id="lecture-professor-input"
              type="text"
              value={professor}
              onChange={(e) => setProfessor(e.target.value)}
              placeholder="Professor / Fonte"
              className="w-32 rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              id="generate-lecture-btn"
              type="button"
              onClick={handleGenerate}
              disabled={isGeneratingLecture || !topic.trim()}
              className="inline-flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-200 transition-all hover:bg-cyan-500/25 disabled:opacity-40"
            >
              {isGeneratingLecture ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Sintetizando...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Gerar Aula Cornell</span>
                </>
              )}
            </button>

            <button
              id="toggle-recording-btn"
              type="button"
              onClick={() => {
                if (isRecordingLecture) {
                  stopLectureRecording();
                } else {
                  startLectureRecording(subject, topic, professor);
                }
              }}
              className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold transition-all ${
                isRecordingLecture
                  ? 'border-rose-400/40 bg-rose-500/20 text-rose-200 animate-pulse'
                  : 'border-white/15 bg-white/5 text-gray-300 hover:bg-white/10'
              }`}
            >
              {isRecordingLecture ? (
                <>
                  <MicOff className="h-3.5 w-3.5" />
                  <span>Parar Gravação</span>
                </>
              ) : (
                <>
                  <Mic className="h-3.5 w-3.5" />
                  <span>Gravar Áudio</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Subtab Navigation */}
        <div className="mt-3 flex items-center gap-1 border-t border-white/5 pt-2">
          <button
            onClick={() => setActiveSubtab('cornell')}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
              activeSubtab === 'cornell'
                ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30'
                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Notas Cornell</span>
          </button>

          <button
            onClick={() => setActiveSubtab('quiz')}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
              activeSubtab === 'quiz'
                ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30'
                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Quiz & Avaliação</span>
            {activeLecture?.quiz && (
              <span className="ml-1 rounded-full bg-cyan-400/20 px-1.5 py-0.2 text-[10px] text-cyan-300">
                {activeLecture.quiz.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubtab('transfer')}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
              activeSubtab === 'transfer'
                ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30'
                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Transferência de Conhecimento</span>
          </button>

          <button
            onClick={() => {
              setActiveSubtab('history');
              listLectureHistory();
            }}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
              activeSubtab === 'history'
                ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30'
                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Histórico & Vault</span>
            {lectureHistory.length > 0 && (
              <span className="ml-1 rounded-full bg-white/10 px-1.5 py-0.2 text-[10px] text-gray-300">
                {lectureHistory.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* CORNELL NOTES TAB */}
        {activeSubtab === 'cornell' && (
          <div className="mx-auto max-w-5xl space-y-4">
            {activeLecture ? (
              <div className="space-y-4">
                {/* Header Card */}
                <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[11px] font-semibold text-cyan-300">
                          {activeLecture.subject}
                        </span>
                        <span className="text-xs text-gray-400">{activeLecture.date}</span>
                      </div>
                      <h1 className="mt-1.5 text-lg font-bold text-white">{activeLecture.topic}</h1>
                      <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <User className="h-3.5 w-3.5" /> {activeLecture.professor}
                        </span>
                        <span className="flex items-center gap-1">
                          <BookOpen className="h-3.5 w-3.5" /> Vault: {activeLecture.markdown_path}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Executive Summary */}
                  <div className="mt-4 rounded-md border border-cyan-500/20 bg-cyan-950/20 p-3">
                    <h3 className="text-xs font-semibold text-cyan-300">📝 Sumário Executivo</h3>
                    <p className="mt-1 text-xs leading-relaxed text-gray-300">{activeLecture.summary}</p>
                  </div>
                </div>

                {/* Cornell Cue Column Table */}
                <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4">
                  <h3 className="text-xs font-semibold text-white mb-3 flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-cyan-400" />
                    <span>Cornell Cue Column (Perguntas de Revisão & Ideias Centrais)</span>
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-white/10 bg-white/[0.02] text-gray-400">
                        <tr>
                          <th className="py-2 px-3 font-semibold text-cyan-300 w-1/3">Perguntas de Revisão & Cues</th>
                          <th className="py-2 px-3 font-semibold text-gray-300">Ideias Centrais & Respostas Rápidas</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {activeLecture.cue_column.map((item, idx) => (
                          <tr key={idx} className="hover:bg-white/[0.02]">
                            <td className="py-2.5 px-3 font-medium text-white/90">{item.cue}</td>
                            <td className="py-2.5 px-3 text-gray-300 leading-relaxed">{item.idea}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Full Markdown View */}
                <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4">
                  <h3 className="text-xs font-semibold text-white mb-2">📖 Conteúdo Completo da Nota</h3>
                  <pre className="overflow-x-auto rounded bg-black/50 p-3 font-mono text-[11px] text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {activeLecture.markdown_content}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-white/15 p-12 text-center">
                <GraduationCap className="h-10 w-10 text-gray-500 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">Nenhuma aula ativa</h3>
                <p className="text-xs text-gray-500 max-w-sm mt-1">
                  Insere um tópico acima e clica em <strong>"Gerar Aula Cornell"</strong> para criar uma síntese pedagógica com
                  quiz interativo e persistência no Vault.
                </p>
              </div>
            )}
          </div>
        )}

        {/* QUIZ TAB */}
        {activeSubtab === 'quiz' && (
          <div className="mx-auto max-w-3xl space-y-4">
            {activeLecture?.quiz && activeLecture.quiz.length > 0 ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-white">Quiz de Avaliação: {activeLecture.topic}</h2>
                      <p className="text-xs text-gray-400">Responde às questões para verificar a retenção do conteúdo.</p>
                    </div>
                    {lectureQuizResult && (
                      <div className="flex items-center gap-1.5 rounded bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Aproveitamento: {lectureQuizResult.score.toFixed(1)}%</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Questions List */}
                <div className="space-y-3">
                  {activeLecture.quiz.map((q, qIdx) => (
                    <div key={q.id} className="rounded-lg border border-white/10 bg-[#0d161c] p-4">
                      <h4 className="text-xs font-semibold text-white">
                        {qIdx + 1}. {q.question}
                      </h4>

                      <div className="mt-2.5 space-y-1.5">
                        {q.options.map((opt, optIdx) => {
                          const isSelected = selectedAnswers[q.id] === optIdx;
                          return (
                            <button
                              key={optIdx}
                              type="button"
                              onClick={() => handleOptionSelect(q.id, optIdx)}
                              className={`w-full text-left rounded border px-3 py-2 text-xs transition-all flex items-center justify-between ${
                                isSelected
                                  ? 'border-cyan-400/60 bg-cyan-950/40 text-cyan-100'
                                  : 'border-white/5 bg-black/20 text-gray-300 hover:bg-white/5'
                              }`}
                            >
                              <span>{opt}</span>
                              {isSelected && <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400 shrink-0 ml-2" />}
                            </button>
                          );
                        })}
                      </div>

                      {lectureQuizResult && (
                        <div className="mt-2.5 rounded bg-white/[0.03] p-2 text-[11px] text-gray-400">
                          💡 <strong>Explicação:</strong> {q.explanation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Submit Quiz Button */}
                <div className="flex justify-end">
                  <button
                    id="submit-quiz-btn"
                    type="button"
                    onClick={handleSubmitQuiz}
                    disabled={isSubmittingQuiz}
                    className="inline-flex items-center gap-1.5 rounded-md border border-cyan-400/40 bg-cyan-500/20 px-4 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 transition-all disabled:opacity-50"
                  >
                    {isSubmittingQuiz ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        <span>Avaliando...</span>
                      </>
                    ) : (
                      <>
                        <Send className="h-3.5 w-3.5" />
                        <span>Submeter Respostas do Quiz</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-white/15 p-12 text-center">
                <HelpCircle className="h-10 w-10 text-gray-500 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">Sem quiz disponível</h3>
                <p className="text-xs text-gray-500 max-w-sm mt-1">Gera uma aula primeiro para aceder ao quiz de avaliação.</p>
              </div>
            )}
          </div>
        )}

        {/* TRANSFER KNOWLEDGE TAB */}
        {activeSubtab === 'transfer' && (
          <div className="mx-auto max-w-3xl space-y-4">
            {activeLecture?.transfer_question ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4">
                  <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-amber-400" />
                    <span>Cenário Aplicado de Transferência de Conhecimento</span>
                  </h3>
                  <p className="mt-1 text-xs text-gray-400">
                    Aplica os conceitos aprendidos num problema prático de engenharia para validar compreensão profunda.
                  </p>
                </div>

                <div className="rounded-lg border border-white/10 bg-[#0d161c] p-4 space-y-3">
                  <div className="rounded border border-amber-500/20 bg-amber-950/20 p-3">
                    <h4 className="text-xs font-semibold text-amber-200">📌 Cenário Operacional:</h4>
                    <p className="mt-1 text-xs leading-relaxed text-gray-300">
                      {activeLecture.transfer_question.scenario}
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1">
                      A tua resolução proposta / Estratégia de implementação:
                    </label>
                    <textarea
                      id="transfer-answer-input"
                      rows={4}
                      value={transferAnswer}
                      onChange={(e) => setTransferAnswer(e.target.value)}
                      placeholder="Descreve como resolverias este cenário aplicando os conceitos da aula..."
                      className="w-full rounded-md border border-white/10 bg-black/40 p-3 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
                    />
                  </div>

                  {lectureQuizResult?.transfer_feedback && (
                    <div className="rounded border border-emerald-500/30 bg-emerald-950/20 p-3 text-xs text-emerald-200">
                      ✅ <strong>Validação de Transferência:</strong> {lectureQuizResult.transfer_feedback}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-white/15 p-12 text-center">
                <Zap className="h-10 w-10 text-gray-500 mb-2" />
                <h3 className="text-sm font-semibold text-gray-300">Sem teste de transferência ativo</h3>
                <p className="text-xs text-gray-500 max-w-sm mt-1">Gera uma aula primeiro para aceder ao cenário de transferência.</p>
              </div>
            )}
          </div>
        )}

        {/* HISTORY & VAULT TAB */}
        {activeSubtab === 'history' && (
          <div className="mx-auto max-w-4xl space-y-4">
            <div className="rounded-lg border border-[#a1bebf]/20 bg-[#0d161c] p-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  <Clock className="h-4 w-4 text-cyan-400" />
                  <span>Aulas Guardadas no Obsidian Knowledge Vault</span>
                </h3>
                <p className="text-xs text-gray-400">Histórico de aulas sintetizadas e notas Cornell indexadas no cofre.</p>
              </div>
              <button
                type="button"
                onClick={() => listLectureHistory()}
                className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-gray-300 hover:bg-white/10"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Atualizar</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {lectureHistory.map((item, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setTopic(item.title);
                    setSubject(item.subject);
                    generateLectureLesson(item.title, item.subject, 'Prof. JARVIS');
                    setActiveSubtab('cornell');
                  }}
                  className="rounded-lg border border-white/10 bg-[#0d161c] p-3.5 hover:border-cyan-500/40 hover:bg-white/[0.02] cursor-pointer transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between text-[11px] text-gray-400">
                      <span className="rounded bg-cyan-500/10 px-2 py-0.5 text-cyan-300 font-medium">{item.subject}</span>
                      <span>{item.date}</span>
                    </div>
                    <h4 className="mt-2 text-xs font-semibold text-white line-clamp-1">{item.title}</h4>
                    {item.markdown_path && (
                      <p className="mt-1 text-[10px] text-gray-500 font-mono truncate">{item.markdown_path}</p>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-end text-xs font-medium text-cyan-300 gap-1">
                    <span>Ver Aula</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
