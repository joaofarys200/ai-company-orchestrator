import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Edit3,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  RotateCw,
  Save,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import type {
  AdaptiveFlashcard,
  StudyDocument,
  StudyModeReadiness,
  StudyModesBridge,
} from './types';
import { EpistemicBadge, EvidenceRefChips, ReadinessBanner } from './StudyEpistemicBadge';

interface StudyFlashcardsViewProps {
  document: StudyDocument | null;
  studyModes?: StudyModesBridge;
  onGoToSummary?: () => void;
  initialFilterTopic?: string;
}

const CARD_TYPE_LABELS: Record<string, string> = {
  DEFINITION: 'Definição',
  CONCEPTUAL_UNDERSTANDING: 'Compreensão Conceptual',
  RELATIONSHIP: 'Relação entre Conceitos',
  METHODOLOGY: 'Metodologia',
  RESULTS_CONCLUSIONS: 'Resultados & Conclusões',
  APPLICATION: 'Aplicação',
  ANALYTICAL: 'Analítico',
};

export const StudyFlashcardsView: React.FC<StudyFlashcardsViewProps> = ({
  document,
  studyModes,
  onGoToSummary,
  initialFilterTopic = '',
}) => {
  const [cards, setCards] = useState<AdaptiveFlashcard[]>([]);
  const [readiness, setReadiness] = useState<StudyModeReadiness | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Study controls
  const [currentIdx, setCurrentIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [confidence, setConfidence] = useState<number>(3);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Filters
  const [filterChapter, setFilterChapter] = useState<string>('ALL');
  const [filterDifficulty, setFilterDifficulty] = useState<string>('ALL');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [topicSearch, setTopicSearch] = useState<string>(initialFilterTopic);

  // Edit / Create dialogs
  const [editingCard, setEditingCard] = useState<AdaptiveFlashcard | null>(null);
  const [editFront, setEditFront] = useState('');
  const [editBack, setEditBack] = useState('');
  const [editTopic, setEditTopic] = useState('');
  const [editDiff, setEditDiff] = useState('MEDIUM');
  const [isCreating, setIsCreating] = useState(false);
  const [lastSrsNotice, setLastSrsNotice] = useState<string | null>(null);

  useEffect(() => {
    setTopicSearch(initialFilterTopic);
  }, [initialFilterTopic]);

  const loadCards = useCallback(async () => {
    if (!document?.document_id || !studyModes) return;
    setIsLoading(true);
    setError(null);
    try {
      const payload = await studyModes.getFlashcards(document.document_id);
      setCards(payload.cards || []);
      if (payload.readiness) setReadiness(payload.readiness);
      setCurrentIdx(0);
      setFlipped(false);
    } catch (err: any) {
      setError(err?.message || 'Erro ao carregar flashcards.');
    } finally {
      setIsLoading(false);
    }
  }, [document?.document_id, studyModes]);

  useEffect(() => {
    loadCards();
  }, [loadCards]);

  const chapters = useMemo(() => {
    const map = new Map<string, string>();
    cards.forEach((c) => {
      if (c.chapter_id) map.set(c.chapter_id, c.chapter_title || c.chapter_id);
    });
    return Array.from(map.entries());
  }, [cards]);

  const filteredCards = useMemo(() => {
    const q = topicSearch.trim().toLowerCase();
    return cards.filter((c) => {
      if (c.is_deleted) return false;
      if (filterChapter !== 'ALL' && c.chapter_id !== filterChapter) return false;
      if (filterDifficulty !== 'ALL' && c.question_difficulty !== filterDifficulty) return false;
      if (filterType !== 'ALL' && c.card_type !== filterType) return false;
      if (
        q &&
        !c.topic.toLowerCase().includes(q) &&
        !c.front.toLowerCase().includes(q) &&
        !c.section_title.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [cards, filterChapter, filterDifficulty, filterType, topicSearch]);

  useEffect(() => {
    if (currentIdx >= filteredCards.length && filteredCards.length > 0) {
      setCurrentIdx(0);
      setFlipped(false);
    }
  }, [filteredCards.length, currentIdx]);

  const activeCard = filteredCards[currentIdx] || null;

  const handleGenerate = async (force = false) => {
    if (!document || !studyModes) return;
    setIsGenerating(true);
    setError(null);
    try {
      const payload = await studyModes.generateFlashcards(document.document_id, force, 16);
      setCards(payload.cards || []);
      if (payload.readiness) setReadiness(payload.readiness);
      setCurrentIdx(0);
      setFlipped(false);
    } catch (err: any) {
      setError(err?.message || 'Não foi possível gerar flashcards.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleReview = useCallback(
    async (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => {
      if (!document || !studyModes || !activeCard) return;
      setError(null);
      try {
        let activeSessId = sessionId;
        if (!activeSessId) {
          const s = await studyModes.startSession({
            document_id: document.document_id,
            mode: 'FLASHCARD_REVIEW',
            title: `Revisão de Flashcards: ${document.title}`,
            item_ids: filteredCards.map((c) => c.card_id),
          });
          activeSessId = s.session_id;
          setSessionId(s.session_id);
        }

        const res = await studyModes.reviewFlashcard(
          document.document_id,
          activeCard.card_id,
          rating,
          confidence
        );
        setCards((prev) =>
          prev.map((c) =>
            c.card_id === activeCard.card_id
              ? { ...res.flashcard, srs: res.srs_state }
              : c
          )
        );
        setLastSrsNotice(
          `Agendado para ${res.srs_state.interval_days}d (EF ${res.srs_state.ease_factor}, estado: ${res.srs_state.learning_state})`
        );
        await studyModes.updateSession(activeSessId, {
          item_id: activeCard.card_id,
          outcome: { rating, interval_days: res.srs_state.interval_days },
          next_index: Math.min(filteredCards.length - 1, currentIdx + 1),
          mark_completed: true,
        });
        setFlipped(false);
        if (currentIdx < filteredCards.length - 1) {
          setCurrentIdx((i) => i + 1);
        }
      } catch (err: any) {
        setError(err?.message || 'Erro ao registar revisão.');
      }
    },
    [document, studyModes, activeCard, sessionId, filteredCards, confidence, currentIdx]
  );

  // Keyboard shortcuts for study flow
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (editingCard || isCreating) return;
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.code === 'Space') {
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (e.code === 'ArrowRight') {
        setCurrentIdx((i) => Math.min(Math.max(0, filteredCards.length - 1), i + 1));
        setFlipped(false);
      } else if (e.code === 'ArrowLeft') {
        setCurrentIdx((i) => Math.max(0, i - 1));
        setFlipped(false);
      } else if (flipped && ['Digit1', 'Digit2', 'Digit3', 'Digit4'].includes(e.code)) {
        const ratings: Array<'Again' | 'Hard' | 'Good' | 'Easy'> = ['Again', 'Hard', 'Good', 'Easy'];
        handleReview(ratings[Number(e.code.replace('Digit', '')) - 1]);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editingCard, isCreating, flipped, filteredCards.length, handleReview]);

  const handleSaveEdit = async () => {
    if (!document || !studyModes) return;
    setError(null);
    try {
      if (isCreating) {
        const created = await studyModes.createFlashcard(document.document_id, {
          front: editFront,
          back: editBack,
          topic: editTopic || 'Personalizado',
          question_difficulty: editDiff,
          chapter_id: filterChapter !== 'ALL' ? filterChapter : '',
        });
        setCards((prev) => [created, ...prev]);
        setCurrentIdx(0);
        setIsCreating(false);
      } else if (editingCard) {
        const updated = await studyModes.editFlashcard(document.document_id, editingCard.card_id, {
          front: editFront,
          back: editBack,
          topic: editTopic,
          question_difficulty: editDiff,
        });
        setCards((prev) => prev.map((c) => (c.card_id === updated.card_id ? updated : c)));
        setEditingCard(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Erro ao guardar flashcard.');
    }
  };

  const handleDelete = async (card: AdaptiveFlashcard) => {
    if (!document || !studyModes) return;
    try {
      await studyModes.deleteFlashcard(document.document_id, card.card_id);
      setCards((prev) => prev.filter((c) => c.card_id !== card.card_id));
    } catch (err: any) {
      setError(err?.message || 'Erro ao remover flashcard.');
    }
  };

  const handleRegenerateSingle = async (card: AdaptiveFlashcard) => {
    if (!document || !studyModes) return;
    if (
      card.user_edited &&
      !window.confirm('Este cartão foi editado manualmente. Desejas mesmo regenerá-lo e perder a edição manual?')
    ) {
      return;
    }
    setIsGenerating(true);
    setError(null);
    try {
      const updated = await studyModes.regenerateFlashcard(document.document_id, card.card_id, card.user_edited);
      setCards((prev) => prev.map((c) => (c.card_id === updated.card_id ? updated : c)));
      setFlipped(false);
    } catch (err: any) {
      setError(err?.message || 'Não foi possível regenerar o cartão.');
    } finally {
      setIsGenerating(false);
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <BookOpen className="h-8 w-8 text-cyan-400 mb-3" />
        <h3 className="text-sm font-semibold text-white">Nenhum documento selecionado</h3>
        <p className="mt-1 max-w-sm text-xs text-gray-400">
          Seleciona um documento na Biblioteca para estudar os flashcards inteligentes fundamentados.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <Layers className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">{document.title}</h2>
            <p className="text-[11px] text-gray-400">
              Flashcards Adaptativos SM-2 • Atalhos: Espaço (virar), 1-4 (classificar), ←/→ (navegar)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setIsCreating(true);
              setEditingCard(null);
              setEditFront('');
              setEditBack('');
              setEditTopic('');
              setEditDiff('MEDIUM');
            }}
            className="flex items-center gap-1.5 rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs font-medium text-gray-200 hover:border-cyan-400/40"
          >
            <Plus className="h-3.5 w-3.5" /> Novo Cartão
          </button>
          <button
            type="button"
            disabled={isGenerating || (readiness ? !readiness.is_ready : false)}
            onClick={() => handleGenerate(cards.length > 0)}
            className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            <span>{cards.length > 0 ? 'Regenerar (Preserva Edições)' : 'Gerar Baralho com qwen3.5:9b'}</span>
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        <div className="max-w-4xl mx-auto space-y-4">
          <ReadinessBanner readiness={readiness} onGoToSummary={onGoToSummary} />

          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-950/30 px-4 py-2.5 text-xs text-rose-200">
              {error}
            </div>
          )}

          {/* Filters bar */}
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-[#121921] p-3">
            <select
              aria-label="Filtrar por capítulo"
              value={filterChapter}
              onChange={(e) => setFilterChapter(e.target.value)}
              className="rounded-md border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-gray-200"
            >
              <option value="ALL">Todos os capítulos ({cards.length})</option>
              {chapters.map(([cid, title]) => (
                <option key={cid} value={cid}>
                  {title}
                </option>
              ))}
            </select>

            <select
              aria-label="Filtrar por tipo"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="rounded-md border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-gray-200"
            >
              <option value="ALL">Todos os formatos</option>
              {Object.entries(CARD_TYPE_LABELS).map(([k, lbl]) => (
                <option key={k} value={k}>
                  {lbl}
                </option>
              ))}
            </select>

            <select
              aria-label="Filtrar por dificuldade"
              value={filterDifficulty}
              onChange={(e) => setFilterDifficulty(e.target.value)}
              className="rounded-md border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-gray-200"
            >
              <option value="ALL">Todas as dificuldades</option>
              <option value="EASY">Fácil</option>
              <option value="MEDIUM">Média</option>
              <option value="HARD">Difícil</option>
            </select>

            <input
              type="text"
              value={topicSearch}
              onChange={(e) => setTopicSearch(e.target.value)}
              placeholder="Filtrar por tópico ou secção..."
              className="flex-1 min-w-[160px] rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white placeholder-gray-500"
            />
          </div>

          {/* Modal / Inline Editor */}
          {(editingCard || isCreating) && (
            <div className="rounded-xl border border-cyan-500/30 bg-[#121921] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-300">
                  {isCreating ? 'Criar Flashcard Manual' : 'Editar Flashcard (Ficará protegido contra regeneração)'}
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    setEditingCard(null);
                    setIsCreating(false);
                  }}
                  className="text-gray-400 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-gray-400 mb-1">Frente (Pergunta)</label>
                  <textarea
                    rows={3}
                    value={editFront}
                    onChange={(e) => setEditFront(e.target.value)}
                    className="w-full rounded-md border border-white/10 bg-black/40 p-2.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-400 mb-1">Verso (Resposta Fundamentada)</label>
                  <textarea
                    rows={3}
                    value={editBack}
                    onChange={(e) => setEditBack(e.target.value)}
                    className="w-full rounded-md border border-white/10 bg-black/40 p-2.5 text-xs text-white"
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  type="text"
                  value={editTopic}
                  onChange={(e) => setEditTopic(e.target.value)}
                  placeholder="Tópico"
                  className="rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white"
                />
                <select
                  value={editDiff}
                  onChange={(e) => setEditDiff(e.target.value)}
                  className="rounded-md border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white"
                >
                  <option value="EASY">Fácil</option>
                  <option value="MEDIUM">Média</option>
                  <option value="HARD">Difícil</option>
                </select>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  disabled={!editFront.trim() || !editBack.trim()}
                  className="ml-auto flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
                >
                  <Save className="h-3.5 w-3.5" /> Guardar
                </button>
              </div>
            </div>
          )}

          {/* Loading or Empty State */}
          {isLoading ? (
            <div className="rounded-xl border border-white/10 bg-[#121921] p-12 text-center text-xs text-gray-400">
              <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-cyan-400" />
              A carregar baralho de estudo...
            </div>
          ) : filteredCards.length === 0 ? (
            <div className="rounded-xl border border-white/10 bg-[#121921] p-10 text-center space-y-3">
              <Layers className="h-8 w-8 mx-auto text-gray-500" />
              <p className="text-sm font-semibold text-white">
                {cards.length === 0
                  ? 'Nenhum flashcard gerado ainda para este documento'
                  : 'Nenhum cartão corresponde aos filtros aplicados'}
              </p>
              <p className="text-xs text-gray-400 max-w-md mx-auto">
                Os flashcards são gerados diretamente a partir do Dossier Académico (Fase 3) e do Plano Editorial (Fase 4).
              </p>
            </div>
          ) : (
            activeCard && (
              <div className="space-y-4">
                {/* Deck navigation header */}
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>
                    Cartão <strong className="text-white">{currentIdx + 1}</strong> de{' '}
                    <strong className="text-white">{filteredCards.length}</strong>
                    {activeCard.user_edited && (
                      <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300 border border-amber-400/20">
                        Editado manualmente
                      </span>
                    )}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingCard(activeCard);
                        setIsCreating(false);
                        setEditFront(activeCard.front);
                        setEditBack(activeCard.back);
                        setEditTopic(activeCard.topic);
                        setEditDiff(activeCard.question_difficulty);
                      }}
                      className="rounded border border-white/10 p-1.5 text-gray-300 hover:border-cyan-400/40"
                      title="Editar cartão"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRegenerateSingle(activeCard)}
                      className="rounded border border-white/10 p-1.5 text-gray-300 hover:border-cyan-400/40"
                      title="Regenerar apenas este cartão"
                    >
                      <RotateCw className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(activeCard)}
                      className="rounded border border-white/10 p-1.5 text-gray-400 hover:text-rose-400 hover:border-rose-400/40"
                      title="Apagar cartão"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Card viewport */}
                <AnimatePresence mode="wait">
                  <motion.div
                    key={`${activeCard.card_id}-${flipped ? 'back' : 'front'}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.16 }}
                    onClick={() => setFlipped((f) => !f)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') setFlipped((f) => !f);
                    }}
                    className="min-h-[250px] rounded-2xl border border-white/15 bg-[#121921] p-7 flex flex-col justify-between cursor-pointer hover:border-cyan-400/40 transition shadow-xl select-none"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-white/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-cyan-300 border border-white/10">
                          {CARD_TYPE_LABELS[activeCard.card_type] || activeCard.card_type}
                        </span>
                        <EpistemicBadge
                          status={activeCard.epistemic_status}
                          isHypothetical={activeCard.is_hypothetical_scenario}
                        />
                      </div>
                      <span className="text-[11px] font-medium text-gray-400">
                        {flipped ? 'Verso (Clica para ver pergunta)' : 'Frente (Clica ou Espaço para revelar)'}
                      </span>
                    </div>

                    <div className="my-6 space-y-3">
                      <p className="text-base sm:text-lg font-semibold text-white leading-relaxed whitespace-pre-wrap">
                        {flipped ? activeCard.back : activeCard.front}
                      </p>
                      {flipped && activeCard.learning_objective_text && (
                        <p className="text-[11px] text-cyan-300/80 border-t border-white/10 pt-2">
                          Objetivo associado: {activeCard.learning_objective_text}
                        </p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3 text-[11px] text-gray-400">
                      <EvidenceRefChips refs={activeCard.evidence_refs} pages={activeCard.source_pages} />
                      <div className="flex items-center gap-3 font-mono text-[10px]">
                        <span>Dificuldade: {activeCard.question_difficulty}</span>
                        {activeCard.srs && (
                          <span>
                            SM-2: {activeCard.srs.learning_state} ({activeCard.srs.interval_days}d • EF {activeCard.srs.ease_factor})
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                </AnimatePresence>

                {/* Confidence selector + SM-2 rating */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400">Confiança na recordação:</span>
                      {[1, 2, 3, 4, 5].map((lvl) => (
                        <button
                          key={lvl}
                          type="button"
                          onClick={() => setConfidence(lvl)}
                          className={`h-6 w-6 rounded text-xs font-bold border transition ${
                            confidence === lvl
                              ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200'
                              : 'border-white/10 bg-black/30 text-gray-400 hover:text-white'
                          }`}
                        >
                          {lvl}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={currentIdx === 0}
                        onClick={() => {
                          setCurrentIdx((i) => Math.max(0, i - 1));
                          setFlipped(false);
                        }}
                        className="rounded border border-white/10 p-1.5 text-gray-300 disabled:opacity-30"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        disabled={currentIdx >= filteredCards.length - 1}
                        onClick={() => {
                          setCurrentIdx((i) => Math.min(filteredCards.length - 1, i + 1));
                          setFlipped(false);
                        }}
                        className="rounded border border-white/10 p-1.5 text-gray-300 disabled:opacity-30"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-2">
                    <button
                      type="button"
                      onClick={() => handleReview('Again')}
                      className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-2.5 text-center text-xs font-semibold text-rose-300 hover:bg-rose-950/40 transition"
                    >
                      1 • Rever Agora (Again)
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReview('Hard')}
                      className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-2.5 text-center text-xs font-semibold text-amber-300 hover:bg-amber-950/40 transition"
                    >
                      2 • Difícil (Hard)
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReview('Good')}
                      className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5 text-center text-xs font-semibold text-cyan-300 hover:bg-cyan-950/40 transition"
                    >
                      3 • Bom (Good)
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReview('Easy')}
                      className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-2.5 text-center text-xs font-semibold text-emerald-300 hover:bg-emerald-950/40 transition"
                    >
                      4 • Fácil (Easy)
                    </button>
                  </div>

                  {lastSrsNotice && (
                    <p className="text-[11px] text-emerald-300 flex items-center gap-1.5">
                      <RefreshCw className="h-3 w-3" /> {lastSrsNotice}
                    </p>
                  )}
                </div>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
};

