import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Search,
  Sparkles,
  FileText,
  Save,
  FolderOpen,
  ArrowLeft,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import type { StudyDocument } from './types';

interface StudyKnowledgeViewProps {
  document: StudyDocument | null;
  notes?: Array<{ filename: string; content?: string }>;
  onSearchRag?: (query: string) => Promise<Array<{ text: string; source: string; score?: number; title?: string }>>;
  onReadNote?: (filename: string) => Promise<string>;
  onSaveNote?: (filename: string, content: string) => void;
}

export const StudyKnowledgeView: React.FC<StudyKnowledgeViewProps> = ({
  document,
  notes = [],
  onSearchRag,
  onReadNote,
  onSaveNote,
}) => {
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [isLoadingNote, setIsLoadingNote] = useState<boolean>(false);
  const [selectedNote, setSelectedNote] = useState<{ filename: string; content: string } | null>(null);
  const [editContent, setEditContent] = useState<string>('');

  // RAG query state
  const [ragPrompt, setRagPrompt] = useState<string>('Explica-me isto com base no que já estudei');
  const [ragResults, setRagResults] = useState<Array<{ text: string; source: string; score?: number; title?: string }>>([]);

  // Auto-search on mount and when document changes
  useEffect(() => {
    let cancelled = false;
    if (onSearchRag) {
      setIsSearching(true);
      const query = ragPrompt.trim() || 'Explica-me isto com base no que já estudei';
      onSearchRag(query)
        .then((res) => {
          if (!cancelled && res && res.length > 0) {
            setRagResults(res);
          }
        })
        .catch((err) => {
          console.error('[StudyKnowledgeView] RAG search error:', err);
        })
        .finally(() => {
          if (!cancelled) setIsSearching(false);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [document?.document_id, onSearchRag]);

  // Curated vault notes list with lecture notes included
  const defaultVaultNotes = [
    {
      filename: '10 - Lectures/Metodologia de Investigacao/2026-10-03 - Predicting the Performance of Online Consumer Reviews - Aula.md',
      content: '',
    },
    {
      filename: '10 - Lectures/Metodologia de Investigacao/2026-10-03 - Predicting the Performance of Online Consumer Reviews - Notas Cornell.md',
      content: '',
    },
    {
      filename: '10 - Lectures/Metodologia de Investigacao/2026-10-03 - Predicting the Performance of Online Consumer Reviews - Transcrição Integral.md',
      content: '',
    },
    {
      filename: '00 - MOC/Knowledge Index.md',
      content: '',
    },
    {
      filename: '01 - AI & LLM/RAG/Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG.md',
      content: '',
    },
  ];

  // Merge provided notes with curated lecture notes so they always appear
  const mergedNotesMap = new Map<string, { filename: string; content?: string }>();
  defaultVaultNotes.forEach((n) => mergedNotesMap.set(n.filename, n));
  notes.forEach((n) => mergedNotesMap.set(n.filename, n));
  const vaultNotes = Array.from(mergedNotesMap.values());

  const handleSelectNote = async (note: { filename: string; content?: string }) => {
    setIsLoadingNote(true);
    let content = note.content;
    if (!content && onReadNote) {
      try {
        const fetched = await onReadNote(note.filename);
        if (fetched) {
          content = fetched;
        }
      } catch (err) {
        console.error('[StudyKnowledgeView] Error reading note:', err);
      }
    }

    const fullNote = {
      filename: note.filename,
      content: content || `# ${note.filename}\n\nNota recuperada do Obsidian Knowledge Vault.`,
    };
    setSelectedNote(fullNote);
    setEditContent(fullNote.content);
    setIsLoadingNote(false);
  };

  const handleRagSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragPrompt.trim() || isSearching) return;
    setIsSearching(true);
    try {
      if (onSearchRag) {
        const results = await onSearchRag(ragPrompt.trim());
        setRagResults(results);
      }
    } catch (err) {
      console.error('[StudyKnowledgeView] RAG search submission failed:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSaveCurrentNote = () => {
    if (!selectedNote) return;
    onSaveNote?.(selectedNote.filename, editContent);
  };

  return (
    <div className="flex h-full w-full bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Left Column: Vault Explorer & RAG Search */}
      <aside className="w-80 lg:w-96 flex flex-col border-r border-[#a1bebf]/15 bg-[#10171e] shrink-0">
        <div className="border-b border-white/10 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <FolderOpen className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white tracking-wide">Obsidian Knowledge Vault</h3>
              <p className="text-[10px] text-gray-400">Grafo Unificado de Conhecimento RAG</p>
            </div>
          </div>

          {/* Quick RAG Search Input */}
          <form onSubmit={handleRagSearchSubmit} className="relative">
            <input
              id="study-knowledge-rag-input"
              type="text"
              value={ragPrompt}
              onChange={(e) => setRagPrompt(e.target.value)}
              placeholder="Explica-me isto com base no que já estudei..."
              className="w-full rounded-md border border-white/10 bg-black/40 py-1.5 pl-3 pr-8 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={isSearching}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-cyan-400 hover:text-cyan-300 p-1 disabled:opacity-50"
              title="Pesquisar no Vault com RAG"
            >
              {isSearching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            </button>
          </form>
        </div>

        {/* Notes list in Vault */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <div className="flex items-center justify-between px-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Ficheiros Markdown & Notas de Estudo
            </span>
            <span className="text-[10px] text-cyan-400 font-mono">
              {vaultNotes.length} notas
            </span>
          </div>

          {vaultNotes.map((n) => {
            const isSelected = selectedNote?.filename === n.filename;
            const isLectureNote = n.filename.includes('Metodologia') || n.filename.includes('Lectures');
            return (
              <button
                key={n.filename}
                onClick={() => handleSelectNote(n)}
                disabled={isLoadingNote}
                className={`w-full text-left p-2.5 rounded-md border text-xs transition space-y-1 ${
                  isSelected
                    ? 'border-cyan-500/40 bg-cyan-950/30 text-white shadow-sm'
                    : isLectureNote
                    ? 'border-cyan-500/20 bg-cyan-950/10 text-cyan-200 hover:border-cyan-500/40 hover:bg-cyan-950/20'
                    : 'border-white/5 bg-black/20 text-gray-400 hover:border-white/15 hover:text-gray-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText className={`h-3.5 w-3.5 shrink-0 ${isLectureNote ? 'text-amber-400' : 'text-cyan-400'}`} />
                  <span className="truncate font-medium">{n.filename.split('/').pop()?.replace('.md', '')}</span>
                </div>
                <p className="text-[10px] text-gray-500 truncate">{n.filename}</p>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Right Column: Note Editor or RAG Synthesis Viewer */}
      <section className="flex-1 flex flex-col min-w-0 bg-[#0d1217] overflow-hidden">
        {selectedNote ? (
          <div className="flex flex-col h-full">
            <header className="flex items-center justify-between border-b border-white/10 bg-[#121921] px-6 py-3 shrink-0">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  onClick={() => setSelectedNote(null)}
                  className="flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/10 transition"
                  title="Voltar ao Grafo e Resultados RAG"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>Voltar ao RAG</span>
                </button>
                <div className="h-4 w-px bg-white/10" />
                <BookOpen className="h-4 w-4 text-cyan-400 shrink-0" />
                <h3 className="text-sm font-semibold text-white truncate">
                  {selectedNote.filename.split('/').pop()}
                </h3>
              </div>
              <button
                onClick={handleSaveCurrentNote}
                className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 transition shadow-sm"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Guardar Nota</span>
              </button>
            </header>

            <div className="flex-1 p-6 overflow-hidden">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="h-full w-full resize-none rounded-lg border border-white/10 bg-black/40 p-5 font-mono text-xs text-gray-200 focus:border-cyan-400 focus:outline-none leading-relaxed"
                placeholder="Conteúdo em Markdown com [[Wikilinks]]..."
              />
            </div>
          </div>
        ) : (
          <div className="flex-1 p-8 overflow-y-auto space-y-6">
            <div className="max-w-3xl mx-auto space-y-6">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-cyan-400" />
                  Recuperação RAG com Base no Histórico de Estudo
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  Evidência substantiva correlacionada a partir das tuas leituras, notas de aula e documentos do Obsidian Vault.
                </p>
              </div>

              {isSearching && (
                <div className="flex items-center gap-2.5 rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-4 text-xs text-cyan-300">
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  <span>A pesquisar notas de aula, transcrições e grafos de conhecimento no Vault...</span>
                </div>
              )}

              {/* RAG Results List */}
              <div className="space-y-4">
                {ragResults.length > 0 ? (
                  ragResults.map((res, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-3 hover:border-cyan-500/30 transition shadow-sm"
                    >
                      <p className="text-xs sm:text-sm text-gray-200 leading-relaxed font-sans">
                        {res.text}
                      </p>
                      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-cyan-400 font-mono pt-2 border-t border-white/5">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-400">Origem comprovada:</span>
                          <button
                            type="button"
                            onClick={() => handleSelectNote({ filename: res.source.replace(/^obsidian_vault\//, '') })}
                            className="rounded bg-black/40 px-2.5 py-1 text-cyan-300 hover:text-white hover:bg-cyan-950/60 border border-white/10 transition inline-flex items-center gap-1.5 group"
                            title="Abrir nota no editor"
                          >
                            <span className="truncate max-w-[280px] sm:max-w-md">{res.source}</span>
                            <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100" />
                          </button>
                        </div>
                        {res.score !== undefined && (
                          <span className="rounded bg-cyan-400/10 px-2 py-0.5 text-cyan-300 border border-cyan-400/20">
                            Relevância: {res.score}%
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : !isSearching ? (
                  <div className="rounded-xl border border-white/10 bg-[#121921] p-8 text-center text-xs text-gray-400 space-y-2">
                    <p>Nenhum resultado RAG encontrado para esta pesquisa.</p>
                    <p className="text-[11px] text-gray-500">Tenta pesquisar termos como "metodologia", "sentiment mining", "readership" ou "helpfulness".</p>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
