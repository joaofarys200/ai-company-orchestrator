import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Check,
  CheckCircle2,
  Edit3,
  Eye,
  EyeOff,
  Highlighter,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Star,
  Tag,
  Trash2,
  X,
} from 'lucide-react';
import type {
  CornellCueItem,
  CornellNoteEntry,
  CornellNotesData,
  CornellStudyDocument,
  StudyDocument,
  StudyHighlight,
  StudyModeReadiness,
  StudyModesBridge,
  StudyReadingNote,
} from './types';
import { EpistemicBadge, EvidenceRefChips, ReadinessBanner } from './StudyEpistemicBadge';

interface StudyNotesViewProps {
  document: StudyDocument | null;
  readingNotes?: StudyReadingNote[];
  highlights?: StudyHighlight[];
  studyModes?: StudyModesBridge;
  onGoToSummary?: () => void;
  onSaveToVault?: (data: {
    title: string;
    markdown_content: string;
    source_document_ids: string[];
    source_hash: string;
  }) => Promise<boolean>;
  onDeleteNote?: (noteId: string) => void;
  onGenerateCornell?: (documentId: string) => Promise<CornellNotesData>;
}

const buildLegacyDocumentCornell = (doc?: StudyDocument | null): CornellNotesData => {
  const metaNotes = (doc?.metadata as Record<string, any> | undefined)?.cornell_notes;
  const genMode =
    (doc?.metadata as Record<string, any> | undefined)?.generation_mode ||
    metaNotes?.generation_mode ||
    '';
  if (metaNotes) {
    return {
      document_id: doc?.document_id || '',
      topic: metaNotes.topic || doc?.title || 'Notas de Estudo',
      subject: metaNotes.subject || doc?.subject || 'Geral',
      date: metaNotes.date || new Date().toISOString().split('T')[0],
      executive_summary: metaNotes.executive_summary || '',
      cue_column: metaNotes.cue_column || [],
      detailed_notes: metaNotes.detailed_notes || '',
      glossary: metaNotes.glossary || '',
      action_items: metaNotes.action_items || [],
      generation_mode: genMode,
    };
  }
  return {
    document_id: doc?.document_id || '',
    topic: doc?.title || 'Notas de Estudo',
    subject: doc?.subject || 'Geral',
    date: new Date().toISOString().split('T')[0],
    executive_summary: '',
    cue_column: [],
    detailed_notes: '',
    glossary: '',
    action_items: [],
    generation_mode: genMode,
  };
};

export const StudyNotesView: React.FC<StudyNotesViewProps> = ({
  document,
  readingNotes = [],
  highlights = [],
  studyModes,
  onGoToSummary,
  onSaveToVault,
  onDeleteNote,
  onGenerateCornell,
}) => {
  const [activeSubtab, setActiveSubtab] = useState<'cornell' | 'reading_notes'>('cornell');
  const [isSavingVault, setIsSavingVault] = useState(false);
  const [vaultSavedMessage, setVaultSavedMessage] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Phase 6 structured Cornell state
  const [phase6Cornell, setPhase6Cornell] = useState<CornellStudyDocument | null>(null);
  const [readiness, setReadiness] = useState<StudyModeReadiness | null>(null);
  const [isLoadingCornell, setIsLoadingCornell] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedSectionId, setSelectedSectionId] = useState<string>('');
  const [hideCueHints, setHideCueHints] = useState(false);
  const [revealedCueIds, setRevealedCueIds] = useState<Record<string, boolean>>({});
  const [filterImportantOnly, setFilterImportantOnly] = useState(false);

  // Inline editing state
  const [isEditingEntry, setIsEditingEntry] = useState(false);
  const [editSummary, setEditSummary] = useState('');
  const [editExplanationsText, setEditExplanationsText] = useState('');
  const [editDetailsText, setEditDetailsText] = useState('');
  const [editCues, setEditCues] = useState<CornellCueItem[]>([]);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Personal note composer state
  const [personalNoteInput, setPersonalNoteInput] = useState('');
  const [personalNoteImportant, setPersonalNoteImportant] = useState(false);
  const [isAddingPersonalNote, setIsAddingPersonalNote] = useState(false);

  // Legacy fallback state (only used when studyModes bridge isn't passed)
  const [legacyCornellData, setLegacyCornellData] = useState<CornellNotesData>(() =>
    buildLegacyDocumentCornell(document)
  );

  const loadPhase6Cornell = useCallback(async () => {
    if (!document || !studyModes) return;
    setIsLoadingCornell(true);
    setErrorMsg(null);
    try {
      const res = await studyModes.getCornell(document.document_id);
      setPhase6Cornell(res.cornell);
      setReadiness(res.readiness);
      if (res.cornell && res.cornell.entries.length > 0) {
        setSelectedSectionId((prev) =>
          res.cornell!.entries.some((e) => e.section_id === prev)
            ? prev
            : res.cornell!.entries[0].section_id
        );
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao carregar Notas Cornell.');
    } finally {
      setIsLoadingCornell(false);
    }
  }, [document, studyModes]);

  useEffect(() => {
    setVaultSavedMessage(null);
    setErrorMsg(null);
    setIsEditingEntry(false);
    setRevealedCueIds({});
    if (studyModes && document) {
      void loadPhase6Cornell();
    } else {
      setLegacyCornellData(buildLegacyDocumentCornell(document));
    }
  }, [document?.document_id, studyModes, loadPhase6Cornell]);

  const handleGenerateCornell = async (force = false) => {
    if (!document) return;
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      if (studyModes) {
        const res = await studyModes.generateCornell(document.document_id, force);
        setPhase6Cornell(res.cornell);
        setReadiness(res.readiness);
        if (res.cornell && res.cornell.entries.length > 0) {
          setSelectedSectionId(res.cornell.entries[0].section_id);
        }
      } else if (onGenerateCornell) {
        const data = await onGenerateCornell(document.document_id);
        setLegacyCornellData(data);
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Falha ao gerar Notas Cornell.');
    } finally {
      setIsGenerating(false);
    }
  };

  const visibleEntries = (phase6Cornell?.entries || []).filter(
    (entry) => !filterImportantOnly || entry.is_important
  );

  const selectedEntry: CornellNoteEntry | undefined =
    visibleEntries.find((e) => e.section_id === selectedSectionId) || visibleEntries[0];

  const startEditingEntry = (entry: CornellNoteEntry) => {
    setEditSummary(entry.summary_section || '');
    setEditExplanationsText((entry.explanations || []).join('\n'));
    setEditDetailsText((entry.supporting_details || []).join('\n'));
    setEditCues((entry.cue_column || []).map((c) => ({ ...c })));
    setIsEditingEntry(true);
  };

  const handleSaveEntryEdit = async () => {
    if (!document || !studyModes || !selectedEntry) return;
    setIsSavingEdit(true);
    setErrorMsg(null);
    try {
      const updated = await studyModes.editCornellEntry(
        document.document_id,
        selectedEntry.section_id,
        {
          summary_section: editSummary.trim(),
          explanations: editExplanationsText
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean),
          supporting_details: editDetailsText
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean),
          cue_column: editCues,
        }
      );
      setPhase6Cornell((prev) =>
        prev
          ? {
              ...prev,
              entries: prev.entries.map((e) =>
                e.section_id === updated.section_id ? updated : e
              ),
            }
          : prev
      );
      setIsEditingEntry(false);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao guardar alterações.');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleToggleEntryImportant = async (entry: CornellNoteEntry) => {
    if (!document || !studyModes) return;
    try {
      const updated = await studyModes.editCornellEntry(document.document_id, entry.section_id, {
        is_important: !entry.is_important,
      });
      setPhase6Cornell((prev) =>
        prev
          ? {
              ...prev,
              entries: prev.entries.map((e) =>
                e.section_id === updated.section_id ? updated : e
              ),
            }
          : prev
      );
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao atualizar marcador.');
    }
  };

  const handleAddPersonalNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!document || !studyModes || !selectedEntry || !personalNoteInput.trim()) return;
    setIsAddingPersonalNote(true);
    setErrorMsg(null);
    try {
      const created = await studyModes.addCornellNote(
        document.document_id,
        selectedEntry.section_id,
        personalNoteInput.trim(),
        personalNoteImportant
      );
      setPhase6Cornell((prev) =>
        prev
          ? {
              ...prev,
              entries: prev.entries.map((entry) =>
                entry.section_id === selectedEntry.section_id
                  ? {
                      ...entry,
                      personal_notes: [...(entry.personal_notes || []), created],
                      is_important: entry.is_important || created.is_important,
                    }
                  : entry
              ),
            }
          : prev
      );
      setPersonalNoteInput('');
      setPersonalNoteImportant(false);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao adicionar anotação pessoal.');
    } finally {
      setIsAddingPersonalNote(false);
    }
  };

  const handleSaveToKnowledgeVault = async () => {
    if (!document) return;
    setIsSavingVault(true);
    setVaultSavedMessage(null);
    setErrorMsg(null);
    try {
      if (studyModes) {
        const res = await studyModes.exportCornellVault(document.document_id);
        setVaultSavedMessage(`Notas Cornell exportadas para: ${res.vault_path}`);
        return;
      }

      const markdown =
        `# ${legacyCornellData.topic}\n\n` +
        `**Disciplina**: [[${legacyCornellData.subject}]]\n` +
        `**Data**: ${legacyCornellData.date}\n` +
        `**Origem**: [[${document.title}]] (SHA256: \`${document.source_hash || 'N/A'}\`)\n\n` +
        `## Sumário Executivo\n${legacyCornellData.executive_summary}\n\n` +
        `## Cue Column & Ideias Centrais\n` +
        legacyCornellData.cue_column.map((c) => `- **${c.cue}**: ${c.idea}`).join('\n') +
        `\n\n## Notas Detalhadas\n${legacyCornellData.detailed_notes}\n\n` +
        `## Glossário Relacionado\n${legacyCornellData.glossary}\n\n` +
        `## Itens de Ação\n` +
        legacyCornellData.action_items.map((a) => `- [ ] ${a}`).join('\n');

      if (onSaveToVault) {
        await onSaveToVault({
          title: legacyCornellData.topic,
          markdown_content: markdown,
          source_document_ids: [document.document_id],
          source_hash: document.source_hash,
        });
      }
      setVaultSavedMessage(
        `Nota guardada com sucesso em obsidian_vault/10 - Study/${legacyCornellData.topic}.md!`
      );
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : 'Erro ao exportar Notas Cornell para o Vault.'
      );
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
          Acede à Biblioteca para abrir as notas de leitura e gerar Notas Cornell fundamentadas.
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
              Sistema de Notas Cornell Fundamentadas & Anotações de Leitura
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Subtab toggle */}
          <div className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
            <button
              type="button"
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
              type="button"
              id="study-tab-reading-notes"
              onClick={() => setActiveSubtab('reading_notes')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
                activeSubtab === 'reading_notes'
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Highlighter className="h-3.5 w-3.5" />
              <span>Notas & Destaques ({readingNotes.length + highlights.length})</span>
            </button>
          </div>

          <button
            type="button"
            id="study-save-vault-btn"
            onClick={handleSaveToKnowledgeVault}
            disabled={isSavingVault || (Boolean(studyModes) && !phase6Cornell)}
            className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition shadow-sm"
            title="Exportar para o Obsidian Knowledge Vault"
          >
            <Save className="h-3.5 w-3.5" />
            <span>{isSavingVault ? 'A exportar...' : 'Exportar Vault'}</span>
          </button>
        </div>
      </header>

      {/* Banners */}
      {vaultSavedMessage && (
        <div className="bg-emerald-950/40 border-b border-emerald-500/30 px-6 py-2 text-xs text-emerald-300 flex items-center justify-between shrink-0">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            {vaultSavedMessage}
          </span>
          <button
            type="button"
            onClick={() => setVaultSavedMessage(null)}
            className="text-emerald-400 hover:text-white"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="bg-rose-950/40 border-b border-rose-500/30 px-6 py-2 text-xs text-rose-300 flex items-center justify-between shrink-0">
          <span>{errorMsg}</span>
          <button type="button" onClick={() => setErrorMsg(null)} className="hover:text-white">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeSubtab === 'cornell' && studyModes && (
          <div className="max-w-6xl mx-auto space-y-5">
            <ReadinessBanner readiness={readiness} onGoToSummary={onGoToSummary} />

            {/* Action bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-[#121921] px-4 py-3">
              <div>
                <h3 className="text-sm font-bold text-white">
                  {phase6Cornell?.title || `Notas Cornell — ${document.title}`}
                </h3>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {phase6Cornell
                    ? `${phase6Cornell.entries.length} secções estruturadas • Modo: ${phase6Cornell.generation_mode}`
                    : 'Estrutura por secção com Coluna de Pistas (Recordação Ativa), Notas & Resumo.'}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {phase6Cornell && (
                  <>
                    <button
                      type="button"
                      onClick={() => setHideCueHints((v) => !v)}
                      className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition ${
                        hideCueHints
                          ? 'border-amber-400/40 bg-amber-500/15 text-amber-300'
                          : 'border-white/15 bg-black/30 text-gray-300 hover:bg-white/5'
                      }`}
                    >
                      {hideCueHints ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                      <span>{hideCueHints ? 'Mostrar Respostas das Pistas' : 'Ocultar Pistas (Auto-Teste)'}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setFilterImportantOnly((v) => !v)}
                      className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition ${
                        filterImportantOnly
                          ? 'border-yellow-400/40 bg-yellow-500/15 text-yellow-300'
                          : 'border-white/15 bg-black/30 text-gray-300 hover:bg-white/5'
                      }`}
                    >
                      <Star className="h-3.5 w-3.5" />
                      <span>Só Importantes</span>
                    </button>
                  </>
                )}
                <button
                  type="button"
                  onClick={() => handleGenerateCornell(Boolean(phase6Cornell))}
                  disabled={isGenerating || (readiness ? !readiness.is_ready : false)}
                  className="flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/25 disabled:opacity-50 transition"
                >
                  {isGenerating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" />
                  )}
                  <span>{phase6Cornell ? 'Regenerar (Preservar Edições)' : 'Gerar Notas Cornell'}</span>
                </button>
              </div>
            </div>

            {isLoadingCornell ? (
              <div className="flex items-center justify-center py-14 text-xs text-gray-400 gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                <span>A carregar estrutura Cornell...</span>
              </div>
            ) : !phase6Cornell || phase6Cornell.entries.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-[#121921] p-10 text-center space-y-3">
                <Sparkles className="h-8 w-8 text-cyan-400 mx-auto opacity-80" />
                <h4 className="text-sm font-semibold text-white">Notas Cornell ainda não geradas</h4>
                <p className="text-xs text-gray-400 max-w-md mx-auto">
                  As Notas Cornell estruturam cada capítulo e secção em pistas de recordação ativa,
                  conceitos-chave, evidência de páginas e sínteses editáveis.
                </p>
              </div>
            ) : (
              <>
                {phase6Cornell.global_summary && (
                  <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/15 p-4 text-xs text-gray-200 leading-relaxed">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 block mb-1">
                      Síntese Global do Documento
                    </span>
                    {phase6Cornell.global_summary}
                  </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
                  {/* Left Chapter / Section Navigator */}
                  <aside className="lg:col-span-3 rounded-xl border border-white/10 bg-[#121921] p-3 space-y-1.5 max-h-[680px] overflow-y-auto">
                    <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                      Secções ({visibleEntries.length})
                    </p>
                    {visibleEntries.length === 0 ? (
                      <p className="px-2 py-3 text-xs text-gray-500">
                        Nenhuma secção marcada como importante.
                      </p>
                    ) : (
                      visibleEntries.map((entry) => {
                        const active = selectedEntry?.section_id === entry.section_id;
                        return (
                          <button
                            key={entry.entry_id}
                            type="button"
                            onClick={() => {
                              setSelectedSectionId(entry.section_id);
                              setIsEditingEntry(false);
                            }}
                            className={`w-full text-left rounded-lg px-3 py-2 text-xs transition border ${
                              active
                                ? 'border-cyan-400/40 bg-cyan-500/15 text-white'
                                : 'border-transparent bg-black/20 text-gray-300 hover:bg-white/5'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="font-semibold truncate">{entry.section_title}</span>
                              <div className="flex items-center gap-1 shrink-0">
                                {entry.is_important && (
                                  <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                                )}
                                {!entry.sufficient_evidence && (
                                  <AlertTriangle className="h-3 w-3 text-amber-400" />
                                )}
                              </div>
                            </div>
                            <div className="text-[10px] text-gray-500 truncate mt-0.5">
                              {entry.chapter_title}
                              {entry.user_edited ? ' • Editado' : ''}
                            </div>
                          </button>
                        );
                      })
                    )}
                  </aside>

                  {/* Selected Cornell Section Sheet */}
                  {selectedEntry && (
                    <section className="lg:col-span-9 rounded-xl border border-white/10 bg-[#121921] p-5 space-y-5">
                      {/* Section Header */}
                      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
                        <div className="space-y-1.5">
                          <p className="text-[11px] font-mono text-cyan-400">
                            {selectedEntry.chapter_title} ({selectedEntry.section_id})
                          </p>
                          <h4 className="text-base font-bold text-white">
                            {selectedEntry.section_title}
                          </h4>
                          <div className="flex flex-wrap items-center gap-2">
                            <EpistemicBadge status={selectedEntry.epistemic_status} />
                            {selectedEntry.user_edited && (
                              <span className="rounded-full border border-indigo-400/30 bg-indigo-500/15 px-2 py-0.5 text-[10px] text-indigo-300">
                                Editado pelo utilizador (protegido)
                              </span>
                            )}
                          </div>
                          <EvidenceRefChips
                            refs={selectedEntry.evidence_refs}
                            pages={selectedEntry.source_pages}
                          />
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleToggleEntryImportant(selectedEntry)}
                            className={`rounded-md border p-1.5 text-xs transition ${
                              selectedEntry.is_important
                                ? 'border-yellow-400/40 bg-yellow-500/15 text-yellow-300'
                                : 'border-white/10 bg-black/30 text-gray-400 hover:text-yellow-300'
                            }`}
                            title="Marcar secção como importante"
                          >
                            <Star
                              className={`h-4 w-4 ${selectedEntry.is_important ? 'fill-yellow-400' : ''}`}
                            />
                          </button>
                          {!isEditingEntry ? (
                            <button
                              type="button"
                              onClick={() => startEditingEntry(selectedEntry)}
                              className="flex items-center gap-1 rounded-md border border-white/15 bg-black/30 px-2.5 py-1.5 text-xs text-gray-200 hover:bg-white/10"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                              <span>Editar</span>
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setIsEditingEntry(false)}
                              className="flex items-center gap-1 rounded-md border border-white/15 bg-black/30 px-2.5 py-1.5 text-xs text-gray-300 hover:bg-white/10"
                            >
                              <X className="h-3.5 w-3.5" />
                              <span>Cancelar</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Insufficient Evidence Guard Warning */}
                      {!selectedEntry.sufficient_evidence && (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-950/25 p-3 text-xs text-amber-200 flex items-start gap-2">
                          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
                          <div>
                            <p className="font-semibold">Evidência insuficiente para síntese completa</p>
                            <p className="text-[11px] opacity-90 mt-0.5">
                              {selectedEntry.insufficiency_reason ||
                                'Esta secção não possui suporte suficiente na fonte para gerar notas detalhadas sem especulação.'}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Inline Edit Mode vs Reading Mode */}
                      {isEditingEntry ? (
                        <div className="space-y-4 rounded-xl border border-cyan-500/30 bg-black/30 p-4">
                          <div className="space-y-1.5">
                            <label className="text-[11px] font-semibold uppercase text-cyan-300">
                              Resumo da Secção
                            </label>
                            <textarea
                              value={editSummary}
                              onChange={(e) => setEditSummary(e.target.value)}
                              rows={3}
                              className="w-full rounded-lg border border-white/15 bg-[#0d1217] p-2.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
                            />
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <label className="text-[11px] font-semibold uppercase text-emerald-300">
                                Explicações (1 por linha)
                              </label>
                              <textarea
                                value={editExplanationsText}
                                onChange={(e) => setEditExplanationsText(e.target.value)}
                                rows={5}
                                className="w-full rounded-lg border border-white/15 bg-[#0d1217] p-2.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="text-[11px] font-semibold uppercase text-gray-300">
                                Detalhes de Suporte (1 por linha)
                              </label>
                              <textarea
                                value={editDetailsText}
                                onChange={(e) => setEditDetailsText(e.target.value)}
                                rows={5}
                                className="w-full rounded-lg border border-white/15 bg-[#0d1217] p-2.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
                              />
                            </div>
                          </div>

                          <div className="space-y-2">
                            <label className="text-[11px] font-semibold uppercase text-amber-300">
                              Pistas (Cue Column)
                            </label>
                            {editCues.map((cue, idx) => (
                              <div
                                key={cue.cue_id || idx}
                                className="grid grid-cols-1 md:grid-cols-2 gap-2 rounded-lg border border-white/10 bg-[#0d1217] p-2.5"
                              >
                                <input
                                  value={cue.cue_prompt}
                                  onChange={(e) =>
                                    setEditCues((prev) =>
                                      prev.map((c, i) =>
                                        i === idx ? { ...c, cue_prompt: e.target.value, user_edited: true } : c
                                      )
                                    )
                                  }
                                  placeholder="Pergunta / Pista"
                                  className="rounded border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-white"
                                />
                                <input
                                  value={cue.answer_hint}
                                  onChange={(e) =>
                                    setEditCues((prev) =>
                                      prev.map((c, i) =>
                                        i === idx ? { ...c, answer_hint: e.target.value, user_edited: true } : c
                                      )
                                    )
                                  }
                                  placeholder="Dica de resposta"
                                  className="rounded border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-gray-300"
                                />
                              </div>
                            ))}
                          </div>

                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={handleSaveEntryEdit}
                              disabled={isSavingEdit}
                              className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
                            >
                              {isSavingEdit ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Check className="h-3.5 w-3.5" />
                              )}
                              <span>Guardar Edições</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          {/* True 2-Column Cornell Layout */}
                          <div className="grid grid-cols-1 md:grid-cols-12 gap-5 border-b border-white/10 pb-5">
                            {/* Left: Cue Column (~35%) */}
                            <div className="md:col-span-4 md:border-r md:border-white/10 md:pr-4 space-y-3">
                              <div className="flex items-center justify-between">
                                <h5 className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                                  Coluna de Pistas
                                </h5>
                                <span className="text-[10px] text-gray-500">
                                  {selectedEntry.cue_column.length} itens
                                </span>
                              </div>

                              {selectedEntry.cue_column.length === 0 ? (
                                <p className="text-xs text-gray-500 italic">
                                  Sem pistas geradas para esta secção.
                                </p>
                              ) : (
                                selectedEntry.cue_column.map((cue) => {
                                  const isRevealed = !hideCueHints || revealedCueIds[cue.cue_id];
                                  return (
                                    <div
                                      key={cue.cue_id}
                                      className="rounded-lg border border-white/10 bg-black/30 p-3 space-y-1.5"
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="text-[10px] font-mono uppercase text-amber-300/80">
                                          {cue.cue_type}
                                        </span>
                                        <EpistemicBadge status={cue.epistemic_status} />
                                      </div>
                                      <p className="text-xs font-semibold text-amber-200 leading-snug">
                                        {cue.cue_prompt}
                                      </p>
                                      {cue.answer_hint && (
                                        <div>
                                          {isRevealed ? (
                                            <p className="text-[11px] text-gray-300 leading-relaxed pt-1 border-t border-white/5">
                                              {cue.answer_hint}
                                            </p>
                                          ) : (
                                            <button
                                              type="button"
                                              onClick={() =>
                                                setRevealedCueIds((prev) => ({
                                                  ...prev,
                                                  [cue.cue_id]: true,
                                                }))
                                              }
                                              className="text-[11px] text-cyan-400 hover:underline pt-1"
                                            >
                                              Revelar dica para verificar recordação →
                                            </button>
                                          )}
                                        </div>
                                      )}
                                      <EvidenceRefChips refs={cue.evidence_refs} />
                                    </div>
                                  );
                                })
                              )}
                            </div>

                            {/* Right: Notes Column (~65%) */}
                            <div className="md:col-span-8 space-y-4">
                              <h5 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                                Notas Estruturadas
                              </h5>

                              {selectedEntry.main_concepts.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-cyan-300">
                                    Conceitos Principais
                                  </p>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    {selectedEntry.main_concepts.map((c, idx) => (
                                      <div
                                        key={idx}
                                        className="rounded-lg border border-white/10 bg-black/30 p-2.5 text-xs"
                                      >
                                        <p className="font-semibold text-white">{c.name}</p>
                                        <p className="text-[11px] text-gray-300 mt-0.5">{c.note}</p>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {selectedEntry.explanations.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-emerald-300">
                                    Explicações
                                  </p>
                                  <ul className="space-y-1.5 rounded-lg border border-white/10 bg-black/25 p-3 text-xs text-gray-200">
                                    {selectedEntry.explanations.map((exp, idx) => (
                                      <li key={idx} className="flex items-start gap-2">
                                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                                        <span className="leading-relaxed">{exp}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {selectedEntry.supporting_details.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-gray-300">
                                    Detalhes & Evidência de Suporte
                                  </p>
                                  <ul className="space-y-1 rounded-lg border border-white/10 bg-black/25 p-3 text-xs text-gray-300">
                                    {selectedEntry.supporting_details.map((d, idx) => (
                                      <li key={idx} className="leading-relaxed">
                                        • {d}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {selectedEntry.examples.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-indigo-300">Exemplos</p>
                                  <ul className="space-y-1 rounded-lg border border-indigo-500/20 bg-indigo-950/15 p-3 text-xs text-indigo-100">
                                    {selectedEntry.examples.map((ex, idx) => (
                                      <li key={idx}>• {ex}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {selectedEntry.concept_relationships.length > 0 && (
                                <div className="space-y-1.5">
                                  <p className="text-[11px] font-semibold text-cyan-300">
                                    Relações Conceptuais
                                  </p>
                                  <ul className="space-y-1 rounded-lg border border-white/10 bg-black/25 p-3 text-xs text-gray-300">
                                    {selectedEntry.concept_relationships.map((rel, idx) => (
                                      <li key={idx}>→ {rel}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {(selectedEntry.methodology_notes ||
                                selectedEntry.results_and_conclusions_notes) && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                  {selectedEntry.methodology_notes && (
                                    <div className="rounded-lg border border-white/10 bg-black/25 p-3">
                                      <p className="text-[10px] font-bold uppercase text-cyan-400 mb-1">
                                        Metodologia
                                      </p>
                                      <p className="text-gray-300 leading-relaxed">
                                        {selectedEntry.methodology_notes}
                                      </p>
                                    </div>
                                  )}
                                  {selectedEntry.results_and_conclusions_notes && (
                                    <div className="rounded-lg border border-white/10 bg-black/25 p-3">
                                      <p className="text-[10px] font-bold uppercase text-emerald-400 mb-1">
                                        Resultados & Conclusões
                                      </p>
                                      <p className="text-gray-300 leading-relaxed">
                                        {selectedEntry.results_and_conclusions_notes}
                                      </p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Bottom Summary Section */}
                          <div className="rounded-xl border border-cyan-500/25 bg-cyan-950/20 p-4 space-y-1.5">
                            <h5 className="text-[11px] font-bold uppercase tracking-wider text-cyan-300">
                              Síntese da Secção (Cornell Summary)
                            </h5>
                            <p className="text-xs text-gray-100 leading-relaxed">
                              {selectedEntry.summary_section || 'Sem síntese registada.'}
                            </p>
                          </div>
                        </>
                      )}

                      {/* Personal Notes Composer & List */}
                      <div className="rounded-xl border border-white/10 bg-black/30 p-4 space-y-3">
                        <h5 className="text-xs font-bold uppercase tracking-wider text-gray-300 flex items-center gap-1.5">
                          <MessageSquare className="h-3.5 w-3.5 text-cyan-400" />
                          Anotações Pessoais ({selectedEntry.personal_notes?.length || 0})
                        </h5>

                        {selectedEntry.personal_notes && selectedEntry.personal_notes.length > 0 && (
                          <div className="space-y-2">
                            {selectedEntry.personal_notes.map((pn) => (
                              <div
                                key={pn.note_id}
                                className="rounded-lg border border-white/10 bg-[#0d1217] p-2.5 text-xs flex items-start justify-between gap-2"
                              >
                                <p className="text-gray-200 leading-relaxed">{pn.content}</p>
                                {pn.is_important && (
                                  <Star className="h-3.5 w-3.5 text-yellow-400 fill-yellow-400 shrink-0" />
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        <form onSubmit={handleAddPersonalNote} className="space-y-2">
                          <textarea
                            value={personalNoteInput}
                            onChange={(e) => setPersonalNoteInput(e.target.value)}
                            rows={2}
                            placeholder="Adicionar anotação pessoal fundamentada nesta secção..."
                            className="w-full rounded-lg border border-white/15 bg-[#0d1217] px-3 py-2 text-xs text-white placeholder:text-gray-500 focus:border-cyan-400 focus:outline-none"
                          />
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={personalNoteImportant}
                                onChange={(e) => setPersonalNoteImportant(e.target.checked)}
                                className="rounded border-white/20 bg-black/40"
                              />
                              <span>Marcar secção como importante</span>
                            </label>
                            <button
                              type="submit"
                              disabled={isAddingPersonalNote || !personalNoteInput.trim()}
                              className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
                            >
                              <Plus className="h-3.5 w-3.5" />
                              <span>Guardar Anotação</span>
                            </button>
                          </div>
                        </form>
                      </div>
                    </section>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* Legacy Cornell fallback when studyModes isn't provided */}
        {activeSubtab === 'cornell' && !studyModes && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="rounded-xl border border-white/10 bg-[#121921] p-5">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white">{legacyCornellData.topic}</h3>
                  <p className="text-xs text-cyan-400 mt-0.5">
                    Disciplina: {legacyCornellData.subject} • Data: {legacyCornellData.date}
                  </p>
                </div>
                {onGenerateCornell && (
                  <button
                    type="button"
                    onClick={() => handleGenerateCornell(true)}
                    disabled={isGenerating}
                    className="flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                    <span>Regenerar Cornell</span>
                  </button>
                )}
              </div>

              {!legacyCornellData.executive_summary && !legacyCornellData.detailed_notes ? (
                <div className="py-10 text-center text-xs text-gray-400">
                  Ainda não existem Notas Cornell para este documento.
                </div>
              ) : (
                <>
                  <div className="mt-4 rounded-lg bg-cyan-950/20 border border-cyan-500/20 p-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-1.5">
                      1. Sumário Executivo
                    </h4>
                    <p className="text-xs text-gray-200 leading-relaxed">
                      {legacyCornellData.executive_summary}
                    </p>
                  </div>

                  <div className="mt-5 grid grid-cols-1 md:grid-cols-12 gap-4 border-t border-b border-white/10 py-5">
                    <div className="md:col-span-4 border-r-0 md:border-r border-white/10 pr-0 md:pr-4 space-y-3">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400">
                        2. Cue Column (Pistas / Perguntas)
                      </h4>
                      {legacyCornellData.cue_column.map((item, idx) => (
                        <div key={idx} className="rounded bg-black/30 p-2.5 border border-white/5 space-y-1">
                          <p className="text-xs font-semibold text-amber-300">{item.cue}</p>
                          <p className="text-[11px] text-gray-400 italic">{item.idea}</p>
                          {item.source_refs && item.source_refs.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-0.5">
                              {item.source_refs.slice(0, 2).map((ref, rIdx) => (
                                <span
                                  key={rIdx}
                                  className="rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-mono text-gray-400 border border-white/10"
                                >
                                  [{ref}]
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="md:col-span-8 pl-0 md:pl-2 space-y-3">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                        3. Detailed Notes
                      </h4>
                      <div className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap rounded bg-black/30 p-4 border border-white/5 font-mono">
                        {legacyCornellData.detailed_notes}
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-lg bg-black/30 border border-white/5 p-4 space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-1.5">
                        <Tag className="h-3.5 w-3.5" /> Glossário
                      </h4>
                      <div className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
                        {legacyCornellData.glossary}
                      </div>
                    </div>
                    <div className="rounded-lg bg-black/30 border border-white/5 p-4 space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Itens de Ação
                      </h4>
                      <ul className="text-xs text-gray-300 space-y-1.5">
                        {legacyCornellData.action_items.map((item, idx) => (
                          <li key={idx} className="flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* SUBTAB 2: READING NOTES & HIGHLIGHTS TIMELINE */}
        {activeSubtab === 'reading_notes' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">Notas de Leitura e Trechos Destacados</h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Registo contínuo de anotações capturadas diretamente durante a leitura do artigo.
              </p>
            </div>

            {readingNotes.length === 0 && highlights.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-black/20 p-8 text-center text-xs text-gray-400">
                Ainda não foram criadas notas ou destaques para este artigo. Selecione qualquer
                trecho no Modo Leitura e clique em "Nota" ou "Destacar".
              </div>
            ) : (
              <div className="space-y-4">
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
                            type="button"
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
                    <p className="text-xs text-white font-medium leading-relaxed">{note.note}</p>
                  </div>
                ))}

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
