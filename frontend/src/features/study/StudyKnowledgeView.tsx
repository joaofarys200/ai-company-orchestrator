import React, { useState } from 'react';
import {
  BookOpen,
  Search,
  Sparkles,
  FileText,
  Save,
  FolderOpen
} from 'lucide-react';
import type { StudyDocument } from './types';

interface StudyKnowledgeViewProps {
  document: StudyDocument | null;
  notes?: Array<{ filename: string; content?: string }>;
  onSearchRag?: (query: string) => Promise<Array<{ text: string; source: string; score?: number }>>;
  onSaveNote?: (filename: string, content: string) => void;
}

export const StudyKnowledgeView: React.FC<StudyKnowledgeViewProps> = ({
  document,
  notes = [],
  onSearchRag,
  onSaveNote,
}) => {
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [selectedNote, setSelectedNote] = useState<{ filename: string; content: string } | null>(null);
  const [editContent, setEditContent] = useState<string>('');

  // RAG query state
  const [ragPrompt, setRagPrompt] = useState<string>('Explica-me isto com base no que já estudei');
  const [ragResults, setRagResults] = useState<Array<{ text: string; source: string }>>([
    {
      text: 'O RAG Híbrido combina recuperação léxica (BM25) com representações densas (Embeddings), garantindo precisão terminológica e correspondência semântica alargada.',
      source: 'obsidian_vault/01 - AI & LLM/RAG/Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG.md',
    },
    {
      text: 'As notas de aula sintetizadas segundo o método Cornell organizam-se em torno de Cues, Notas Detalhadas e Sumário Executivo com [[Wikilinks]] de ancoragem.',
      source: 'obsidian_vault/10 - Lectures/Inteligência Artificial/Sistemas Multiagente.md',
    },
  ]);

  // Default vault notes list
  const vaultNotes = notes.length > 0 ? notes : [
    {
      filename: '01 - AI & LLM/RAG/Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG.md',
      content: '# Comparação RAG\n\nEstudo aprofundado entre [[BM25]] e [[Embeddings Densos]].\n\n## 1. Vantagens do RAG Híbrido\nCombina a precisão exata de termos com generalização semântica.',
    },
    {
      filename: '03 - Backend & Distributed Systems/WebSockets/Comparison - REST Polling vs WebSocket Full-Duplex Streaming.md',
      content: '# Streaming Full-Duplex\n\nAnálise de latência e concorrência para aplicações em tempo real.',
    },
    {
      filename: '10 - Study/Metodologia e Arquiteturas Epistémicas.md',
      content: '# Metodologia e Arquiteturas Epistémicas\n\n**Origem**: [[Artigo Científico]]\n\n## Sumário Executivo\nSíntese auditável com proveniência de dados.',
    },
  ];

  const handleSelectNote = (note: { filename: string; content?: string }) => {
    const fullNote = {
      filename: note.filename,
      content: note.content || `# ${note.filename}\n\nNota recuperada do Obsidian Vault...`,
    };
    setSelectedNote(fullNote);
    setEditContent(fullNote.content);
  };

  const handleRagSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragPrompt.trim() || isSearching) return;
    setIsSearching(true);
    try {
      if (onSearchRag) {
        const results = await onSearchRag(ragPrompt.trim());
        setRagResults(results);
      } else {
        setRagResults([
          {
            text: `Resposta contextualizada para "${ragPrompt}": O corpus do artigo "${document?.title || 'Material'}" alinha-se com a nota [[Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG]], reforçando a separação entre inferências e dados verificados.`,
            source: `${document?.title || 'Artigo'} § Methodology, p. 4`,
          },
          {
            text: 'Conexões no grafo de conhecimento: O conceito de [[Adaptação de Domínio]] partilha relações bidirecionais com [[Generalização]].',
            source: 'obsidian_vault/10 - Study/Metodologia e Arquiteturas Epistémicas.md',
          },
        ]);
      }
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
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-cyan-400 hover:text-cyan-300 p-1"
              title="Pesquisar no Vault com RAG"
            >
              <Search className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>

        {/* Notes list in Vault */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 px-2">
            Ficheiros Markdown & Notas de Estudo
          </span>
          {vaultNotes.map((n) => {
            const isSelected = selectedNote?.filename === n.filename;
            return (
              <button
                key={n.filename}
                onClick={() => handleSelectNote(n)}
                className={`w-full text-left p-2.5 rounded-md border text-xs transition space-y-1 ${
                  isSelected
                    ? 'border-cyan-500/30 bg-cyan-950/20 text-white'
                    : 'border-white/5 bg-black/20 text-gray-400 hover:border-white/15 hover:text-gray-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                  <span className="truncate font-medium">{n.filename.split('/').pop()}</span>
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
              <div className="flex items-center gap-2 min-w-0">
                <BookOpen className="h-4 w-4 text-cyan-400 shrink-0" />
                <h3 className="text-sm font-semibold text-white truncate">
                  {selectedNote.filename}
                </h3>
              </div>
              <button
                onClick={handleSaveCurrentNote}
                className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 transition"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Guardar Nota</span>
              </button>
            </header>

            <div className="flex-1 p-6 overflow-hidden">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="h-full w-full resize-none rounded-lg border border-white/10 bg-black/30 p-4 font-mono text-xs text-gray-200 focus:border-cyan-400 focus:outline-none leading-relaxed"
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
                  Resultados correlacionados a partir das tuas leituras, notas Cornell e documentos do Vault.
                </p>
              </div>

              {/* RAG Results List */}
              <div className="space-y-4">
                {ragResults.map((res, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-white/10 bg-[#121921] p-5 space-y-3"
                  >
                    <p className="text-xs sm:text-sm text-gray-200 leading-relaxed">
                      {res.text}
                    </p>
                    <div className="flex items-center gap-2 text-[10px] text-cyan-400 font-mono pt-1 border-t border-white/5">
                      <span>Origem comprovada:</span>
                      <span className="rounded bg-black/40 px-2 py-0.5 text-gray-300 border border-white/10">
                        {res.source}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
