import React, { useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  Highlighter,
  MessageSquare,
  RefreshCw,
  Save,
  Sparkles,
  Tag,
  Trash2
} from 'lucide-react';
import type {
  StudyDocument,
  StudyReadingNote,
  StudyHighlight,
  CornellNotesData
} from './types';

interface StudyNotesViewProps {
  document: StudyDocument | null;
  readingNotes?: StudyReadingNote[];
  highlights?: StudyHighlight[];
  onSaveToVault?: (data: {
    title: string;
    markdown_content: string;
    source_document_ids: string[];
    source_hash: string;
  }) => Promise<boolean>;
  onDeleteNote?: (noteId: string) => void;
  onGenerateCornell?: (documentId: string) => Promise<CornellNotesData>;
}

export const StudyNotesView: React.FC<StudyNotesViewProps> = ({
  document,
  readingNotes = [],
  highlights = [],
  onSaveToVault,
  onDeleteNote,
  onGenerateCornell,
}) => {
  const [activeSubtab, setActiveSubtab] = useState<'cornell' | 'reading_notes'>('cornell');
  const [isSavingVault, setIsSavingVault] = useState<boolean>(false);
  const [vaultSavedMessage, setVaultSavedMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  // Default or generated Cornell Note
  const [cornellData, setCornellData] = useState<CornellNotesData>(() => {
    return {
      document_id: document?.document_id || 'doc-1',
      topic: document?.title || 'Metodologia e Arquiteturas Epistémicas',
      subject: document?.subject || 'Engenharia de Software & IA',
      date: new Date().toISOString().split('T')[0],
      executive_summary:
        'Síntese sistemática dos conceitos centrais abordados no material. Enfatiza a separação entre inferências e dados verificados, garantindo reprodutibilidade.',
      cue_column: [
        {
          cue: 'Qual a tese metodológica central?',
          idea: 'Estruturação hierárquica por página e parágrafo preservando proveniência auditável.',
        },
        {
          cue: 'Como evitar sobreposições de tradução?',
          idea: 'Tradução estritamente contextual de segmentos, mantendo os termos científicos originais.',
        },
        {
          cue: 'Como funciona o scoring de quiz?',
          idea: 'Avaliação matemática real baseada em gabaritos sem presunção de 100% de acerto.',
        },
      ],
      detailed_notes:
        '### 1. Enquadramento Teórico\nO sistema estabelece limites rigorosos entre observação e inferência epistemológica.\n\n### 2. Mecanismos Operacionais\n- Extração via PyMuPDF e pdfplumber\n- Indexação com Hash SHA-256\n- RAG direcionado com restrição ao corpus atual e Obsidian Vault\n\n### 3. Integração com Obsidian Vault\nOs conceitos são transpostos com [[Wikilinks]] permitindo navegação em grafo.',
      glossary:
        '- [[Generalização]]: Capacidade do modelo operar em distribuições não vistas.\n- [[Adaptação de Domínio]]: Transferência entre conjuntos com distribuições divergentes.\n- [[RAG]]: Geração aumentada por recuperação com validação factual.',
      action_items: [
        'Rever secção de resultados experimentais (p. 6 a 8)',
        'Executar quiz de 10 questões para validar retenção',
        'Sintetizar com o material da aula anterior no Vault',
      ],
    };
  });

  const handleGenerateCornell = async () => {
    if (!document) return;
    setIsGenerating(true);
    try {
      if (onGenerateCornell) {
        const data = await onGenerateCornell(document.document_id);
        setCornellData(data);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveToKnowledgeVault = async () => {
    if (!document) return;
    setIsSavingVault(true);
    setVaultSavedMessage(null);
    try {
      const markdown = `# ${cornellData.topic}\n\n` +
        `**Disciplina**: [[${cornellData.subject}]]\n` +
        `**Data**: ${cornellData.date}\n` +
        `**Origem**: [[${document.title}]] (SHA256: \`${document.source_hash || 'N/A'}\`)\n\n` +
        `## Sumário Executivo\n${cornellData.executive_summary}\n\n` +
        `## Cue Column & Ideias Centrais\n` +
        cornellData.cue_column.map((c) => `- **${c.cue}**: ${c.idea}`).join('\n') +
        `\n\n## Notas Detalhadas\n${cornellData.detailed_notes}\n\n` +
        `## Glossário Relacionado\n${cornellData.glossary}\n\n` +
        `## Itens de Ação\n` +
        cornellData.action_items.map((a) => `- [ ] ${a}`).join('\n');

      if (onSaveToVault) {
        await onSaveToVault({
          title: cornellData.topic,
          markdown_content: markdown,
          source_document_ids: [document.document_id],
          source_hash: document.source_hash,
        });
      }
      setVaultSavedMessage(
        `Nota guardada com sucesso em obsidian_vault/10 - Study/${cornellData.topic}.md com [[Wikilinks]]!`
      );
    } catch {
      setVaultSavedMessage('Erro ao salvar no Knowledge Vault.');
    } finally {
      setIsSavingVault(false);
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
          Acede à Biblioteca para abrir as notas de leitura e gerar notas Cornell.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Header Bar */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <BookOpen className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">
              {document.title}
            </h2>
            <p className="text-[11px] text-gray-400">
              Sistema de Notas Cornell & Anotações de Leitura
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Subtab toggle */}
          <div className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
            <button
              onClick={() => setActiveSubtab('cornell')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeSubtab === 'cornell'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Cornell Notes</span>
            </button>
            <button
              id="study-tab-reading-notes"
              onClick={() => setActiveSubtab('reading_notes')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeSubtab === 'reading_notes'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Highlighter className="h-3.5 w-3.5" />
              <span>
                Notas & Destaques ({readingNotes.length + highlights.length})
              </span>
            </button>
          </div>

          {/* Action: Save to Vault */}
          <button
            id="study-save-vault-btn"
            onClick={handleSaveToKnowledgeVault}
            disabled={isSavingVault}
            className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition shadow-sm"
            title="Exportar para o Obsidian Knowledge Vault"
          >
            <Save className="h-3.5 w-3.5" />
            <span>{isSavingVault ? 'A guardar...' : 'Guardar no Conhecimento'}</span>
          </button>
        </div>
      </header>

      {/* Success banner if saved */}
      {vaultSavedMessage && (
        <div className="bg-emerald-950/40 border-b border-emerald-500/30 px-6 py-2 text-xs text-emerald-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            {vaultSavedMessage}
          </span>
          <button
            onClick={() => setVaultSavedMessage(null)}
            className="text-emerald-400 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ============================================================ */}
        {/* SUBTAB 1: CORNELL NOTES VIEW                                 */}
        {/* ============================================================ */}
        {activeSubtab === 'cornell' && (
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Header / Meta */}
            <div className="rounded-xl border border-white/10 bg-[#121921] p-5">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white">{cornellData.topic}</h3>
                  <p className="text-xs text-cyan-400 mt-0.5">
                    Disciplina: {cornellData.subject} • Data: {cornellData.date}
                  </p>
                </div>
                <button
                  onClick={handleGenerateCornell}
                  disabled={isGenerating}
                  className="flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                  <span>Regenerar Cornell</span>
                </button>
              </div>

              {/* Executive Summary */}
              <div className="mt-4 rounded-lg bg-cyan-950/20 border border-cyan-500/20 p-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-1.5">
                  1. Sumário Executivo
                </h4>
                <p className="text-xs text-gray-200 leading-relaxed">
                  {cornellData.executive_summary}
                </p>
              </div>

              {/* Cornell 2-Column Split: Cue Column (Left ~30%) & Detailed Notes (Right ~70%) */}
              <div className="mt-5 grid grid-cols-1 md:grid-cols-12 gap-4 border-t border-b border-white/10 py-5">
                {/* Left: Cue Column */}
                <div className="md:col-span-4 border-r-0 md:border-r border-white/10 pr-0 md:pr-4 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400">
                    2. Cue Column (Pistas / Perguntas)
                  </h4>
                  {cornellData.cue_column.map((item, idx) => (
                    <div key={idx} className="rounded bg-black/30 p-2.5 border border-white/5 space-y-1">
                      <p className="text-xs font-semibold text-amber-300">{item.cue}</p>
                      <p className="text-[11px] text-gray-400 italic">{item.idea}</p>
                    </div>
                  ))}
                </div>

                {/* Right: Detailed Notes */}
                <div className="md:col-span-8 pl-0 md:pl-2 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                    3. Detailed Notes (Notas Detalhadas)
                  </h4>
                  <div className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap rounded bg-black/30 p-4 border border-white/5 font-mono">
                    {cornellData.detailed_notes}
                  </div>
                </div>
              </div>

              {/* Glossary & Action Items */}
              <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-lg bg-black/30 border border-white/5 p-4 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5" /> Glossário de Conceitos ([[Wikilinks]])
                  </h4>
                  <div className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                    {cornellData.glossary}
                  </div>
                </div>

                <div className="rounded-lg bg-black/30 border border-white/5 p-4 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Itens de Ação & Estudo Futuro
                  </h4>
                  <ul className="text-xs text-gray-300 space-y-1.5">
                    {cornellData.action_items.map((item, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* SUBTAB 2: READING NOTES & HIGHLIGHTS TIMELINE                */}
        {/* ============================================================ */}
        {activeSubtab === 'reading_notes' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">
                Notas de Leitura e Trechos Destacados
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Registo contínuo de anotações capturadas diretamente durante a leitura do artigo.
              </p>
            </div>

            {readingNotes.length === 0 && highlights.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-black/20 p-8 text-center text-xs text-gray-400">
                Ainda não foram criadas notas ou destaques para este artigo.
                Selecione qualquer trecho no Modo Leitura e clique em "Nota" ou "Destacar".
              </div>
            ) : (
              <div className="space-y-4">
                {/* Notes list */}
                {readingNotes.map((note) => (
                  <div
                    key={note.note_id}
                    className="rounded-lg border border-emerald-500/20 bg-[#121921] p-4 space-y-2 hover:border-emerald-500/40 transition"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                        <MessageSquare className="h-3.5 w-3.5" /> Nota na p. {note.page}
                      </span>
                      <div className="flex items-center gap-2 text-[11px] text-gray-500">
                        <span>{note.created_at}</span>
                        {onDeleteNote && (
                          <button
                            onClick={() => onDeleteNote(note.note_id)}
                            className="text-gray-500 hover:text-red-400 p-1"
                            title="Apagar nota"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-gray-400 italic bg-black/30 p-2 rounded border border-white/5">
                      "{note.selection}"
                    </div>
                    <p className="text-xs text-white font-medium leading-relaxed">
                      {note.note}
                    </p>
                  </div>
                ))}

                {/* Highlights list */}
                {highlights.map((h) => (
                  <div
                    key={h.highlight_id}
                    className="rounded-lg border border-yellow-500/20 bg-[#121921] p-4 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-yellow-300 flex items-center gap-1.5">
                        <Highlighter className="h-3.5 w-3.5" /> Destaque na p. {h.page}
                      </span>
                      <span className="text-[11px] text-gray-500">{h.created_at}</span>
                    </div>
                    <p className="text-xs text-gray-200 leading-relaxed bg-yellow-950/20 p-2 rounded border border-yellow-500/20">
                      "{h.selected_text}"
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
