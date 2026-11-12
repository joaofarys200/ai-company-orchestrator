import React, { useEffect, useMemo, useState } from 'react';
import {
  Database,
  Search,
  Plus,
  RefreshCw,
  FileText,
  Edit3,
  Eye,
  Save,
  Sparkles,
  ShieldAlert,
  Activity,
  Pause,
  Play,
  RotateCcw,
  CheckCircle2,
  Link2,
  PanelRightClose,
  PanelRightOpen,
  Layers,
  Loader2,
  Network,
  BookOpen,
  Trash2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Shield,
} from 'lucide-react';
import type {
  VaultDiagnosticsData,
  NoteImprovementItem,
  NoteQualityAuditMessage,
  NoteEnrichmentResultMessage,
  RuleMemory,
  ArchitectureMemory,
  EngineeringDecision,
} from '../../protocol/websocket';
import type { StudyDocument } from '../study/types';
import { ResizableHandle, usePersistedPaneSize } from '../../components/ui';

export interface ObsidianVaultViewProps {
  notes: string[];
  currentNote: { filename: string; content: string } | null;
  vaultDiagnostics: VaultDiagnosticsData | null;
  vaultImprovementQueue: NoteImprovementItem[];
  noteQualityAudit: NoteQualityAuditMessage['audit'] | null;
  noteEnrichmentProposal: NoteEnrichmentResultMessage['proposal'] | null;
  isAuditingNote: boolean;
  isEnrichingNote: boolean;
  onRefreshNotes: () => void;
  onReadNote: (filename: string) => Promise<string>;
  onSaveNote: (filename: string, content: string) => void;
  onRefreshDiagnostics: () => void;
  onAuditNoteQuality: (filename: string) => void;
  onEnrichNote: (filename: string, autoApply?: boolean) => void;
  onRollbackNote: (filename: string, backupPath?: string) => void;
  onPauseQueueWorker: () => void;
  onResumeQueueWorker: () => void;
  onStartImprovementBatch: (batchSize?: number) => void;
  onGetQueueStatus?: () => void;
  onAskAssistant?: (prompt: string) => void;
  rules?: RuleMemory[];
  architecture?: ArchitectureMemory[];
  decisions?: EngineeringDecision[];
  onDeleteRule?: (key: string) => void;
  onDeleteArchitecture?: (module: string) => void;
  onDeleteDecision?: (decision: string) => void;
  initialSubTab?: 'vault' | 'graph' | 'rules';
  studyDocuments?: StudyDocument[];
  onOpenStudyDocument?: (docId: string) => void;
}

export const ObsidianVaultView: React.FC<ObsidianVaultViewProps> = ({
  notes,
  currentNote,
  vaultDiagnostics,
  vaultImprovementQueue,
  noteQualityAudit,
  noteEnrichmentProposal,
  isAuditingNote,
  isEnrichingNote,
  onRefreshNotes,
  onReadNote,
  onSaveNote,
  onRefreshDiagnostics,
  onAuditNoteQuality,
  onEnrichNote,
  onRollbackNote,
  onPauseQueueWorker,
  onResumeQueueWorker,
  onStartImprovementBatch,
  onGetQueueStatus,
  onAskAssistant,
  rules = [],
  architecture = [],
  decisions = [],
  onDeleteRule,
  onDeleteArchitecture,
  onDeleteDecision,
  initialSubTab = 'vault',
  studyDocuments = [],
  onOpenStudyDocument,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNote, setSelectedNote] = useState<string>('');
  const [noteContent, setNoteContent] = useState<string>('');
  const [viewMode, setViewMode] = useState<'preview' | 'edit'>('preview');
  const [isCreatingNote, setIsCreatingNote] = useState(false);
  const [newNoteName, setNewNoteName] = useState('');
  const [savedNotice, setSavedNotice] = useState('');
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<'overview' | 'audit' | 'queue'>('overview');
  const [activeViewTab, setActiveViewTab] = useState<'vault' | 'graph' | 'rules'>(initialSubTab);
  const [graphFilter, setGraphFilter] = useState<'all' | 'hubs' | 'orphans'>('all');
  const [graphZoom, setGraphZoom] = useState<number>(1);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [leftWidth, setLeftWidth, resetLeftWidth] = usePersistedPaneSize('jarvis.obsidian.left_width', 256, 180, 400);
  const [rightWidth, setRightWidth, resetRightWidth] = usePersistedPaneSize('jarvis.obsidian.right_width', 352, 260, 520);

  useEffect(() => {
    setActiveViewTab(initialSubTab);
  }, [initialSubTab]);

  const activeNoteName = selectedNote || currentNote?.filename || '';
  const activeContent =
    currentNote && currentNote.filename === activeNoteName ? noteContent || currentNote.content : noteContent;

  const filteredNotes = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return notes;
    return notes.filter((n) => n.toLowerCase().includes(q));
  }, [notes, searchQuery]);

  const orphanSet = useMemo(
    () => new Set((vaultDiagnostics?.genuine_orphans_list || []).map((n) => n.toLowerCase())),
    [vaultDiagnostics]
  );

  const handleSelectNote = async (filename: string) => {
    setSelectedNote(filename);
    try {
      const content = await onReadNote(filename);
      setNoteContent(content);
    } catch {
      // Keep UI responsive if read fails
    }
  };

  const handleSaveCurrent = () => {
    if (!activeNoteName) return;
    onSaveNote(activeNoteName, activeContent);
    setSavedNotice('Nota guardada');
    setTimeout(() => setSavedNotice(''), 2500);
  };

  const handleCreateNote = () => {
    const cleaned = newNoteName.trim();
    if (!cleaned) return;
    const finalName = cleaned.endsWith('.md') ? cleaned : `${cleaned}.md`;
    const initialBody = `# ${finalName.replace(/\.md$/i, '')}\n\n`;
    onSaveNote(finalName, initialBody);
    setSelectedNote(finalName);
    setNoteContent(initialBody);
    setIsCreatingNote(false);
    setNewNoteName('');
    setViewMode('edit');
    setTimeout(() => {
      onRefreshNotes();
      onReadNote(finalName);
    }, 350);
  };

  const handleWikilinkClick = (target: string) => {
    const normalized = target.trim().toLowerCase();
    const match = notes.find((n) => {
      const bare = n.replace(/\.md$/i, '').toLowerCase();
      return bare === normalized || bare.endsWith(`/${normalized}`) || n.toLowerCase() === normalized;
    });
    if (match) {
      handleSelectNote(match);
    }
  };

  const renderMarkdownPreview = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      const h1 = line.match(/^#\s+(.*)/);
      if (h1) {
        return (
          <h1 key={idx} className="mt-4 mb-2 border-b border-white/10 pb-1.5 text-lg font-bold text-white">
            {h1[1]}
          </h1>
        );
      }
      const h2 = line.match(/^##\s+(.*)/);
      if (h2) {
        return (
          <h2 key={idx} className="mt-3 mb-1.5 text-sm font-bold text-cyan-200">
            {h2[1]}
          </h2>
        );
      }
      const h3 = line.match(/^###\s+(.*)/);
      if (h3) {
        return (
          <h3 key={idx} className="mt-2.5 mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-300">
            {h3[1]}
          </h3>
        );
      }

      const parts = line.split(/(\[\[[^\]]+\]\])/g);
      return (
        <p key={idx} className="min-h-[1.25rem] text-xs leading-relaxed text-zinc-300">
          {parts.map((part, pIdx) => {
            const linkMatch = part.match(/^\[\[([^\]|]+)(?:\|([^\]]+))?\]\]$/);
            if (linkMatch) {
              const target = linkMatch[1];
              const label = linkMatch[2] || target;
              return (
                <button
                  key={pIdx}
                  onClick={() => handleWikilinkClick(target)}
                  className="mx-0.5 inline-flex items-center gap-1 rounded bg-cyan-500/10 px-1.5 py-0.5 text-[11px] font-medium text-cyan-300 border border-cyan-500/20 hover:bg-cyan-500/20 cursor-pointer"
                  title={`Abrir [[${target}]]`}
                >
                  <Link2 className="h-2.5 w-2.5" />
                  {label}
                </button>
              );
            }
            return <React.Fragment key={pIdx}>{part}</React.Fragment>;
          })}
        </p>
      );
    });
  };

  const queueMetrics = vaultDiagnostics?.queue_metrics;
  const dist = vaultDiagnostics?.quality_distribution;

  const graphLayout = useMemo(() => {
    const rawNodes = vaultDiagnostics?.graph_nodes ?? [];
    const filteredNodes = rawNodes.filter((n) => {
      if (graphFilter === 'hubs') return Boolean(n.is_hub);
      if (graphFilter === 'orphans') return Boolean(n.is_orphan);
      return true;
    });
    const limited = filteredNodes.slice(0, 60);
    const ids = new Set(limited.map((n) => n.id));
    const sorted = [...limited].sort((a, b) => (b.degree || 0) - (a.degree || 0));
    const cx = 430;
    const cy = 270;
    const positioned = sorted.map((node, idx) => {
      if (idx === 0 && sorted.length > 3) {
        return { ...node, x: cx, y: cy };
      }
      const angle = idx * 2.399963229728653; // Golden angle distribution
      const radius = 55 + Math.sqrt(idx) * 34;
      return {
        ...node,
        x: Math.round(cx + Math.cos(angle) * Math.min(radius, 360)),
        y: Math.round(cy + Math.sin(angle) * Math.min(radius * 0.65, 225)),
      };
    });
    const byId = new Map(positioned.map((n) => [n.id, n]));
    const edges = (vaultDiagnostics?.graph_edges ?? []).filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes: positioned, edges, byId };
  }, [graphFilter, vaultDiagnostics?.graph_edges, vaultDiagnostics?.graph_nodes]);

  const selectedGraphNode = useMemo(
    () => graphLayout.nodes.find((n) => n.id === selectedGraphNodeId) || null,
    [graphLayout.nodes, selectedGraphNodeId]
  );

  const openNoteFromGraph = (nodeLabelOrId: string) => {
    const lower = nodeLabelOrId.toLowerCase();
    const match = notes.find((n) => {
      const bare = n.replace(/\.md$/i, '').toLowerCase();
      return bare === lower || n.toLowerCase() === lower || bare.endsWith(`/${lower}`);
    });
    if (match) {
      setActiveViewTab('vault');
      handleSelectNote(match);
    }
  };

  return (
    <div data-testid="obsidian-vault-view" className="flex h-full min-h-0 overflow-hidden bg-[#080c12] text-slate-200">
      {/* Left: Vault Notes Explorer */}
      <aside style={{ width: leftWidth }} className="flex shrink-0 flex-col border-r border-slate-800/80 bg-[#090e15]">
        <div className="flex items-center justify-between border-b border-white/[0.07] px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-semibold text-white">Obsidian Vault</span>
            <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
              {notes.length}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsCreatingNote((v) => !v)}
              className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-cyan-300 cursor-pointer"
              title="Nova Nota"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => {
                onRefreshNotes();
                onRefreshDiagnostics();
                onGetQueueStatus?.();
              }}
              className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-white cursor-pointer"
              title="Atualizar Vault e Grafo"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {isCreatingNote && (
          <div className="border-b border-white/[0.07] bg-[#0d141b] p-2.5 space-y-2">
            <input
              type="text"
              value={newNoteName}
              onChange={(e) => setNewNoteName(e.target.value)}
              placeholder="Nome da nota (ex: GestaoRiscos.md)"
              className="w-full rounded border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-white placeholder-zinc-500 focus:border-cyan-400/50 focus:outline-none"
            />
            <div className="flex justify-end gap-1.5">
              <button
                onClick={() => setIsCreatingNote(false)}
                className="rounded px-2 py-1 text-[11px] text-zinc-400 hover:text-white"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateNote}
                className="rounded bg-cyan-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-cyan-500 cursor-pointer"
              >
                Criar
              </button>
            </div>
          </div>
        )}

        <div className="border-b border-white/[0.07] p-2.5">
          <div className="relative flex items-center">
            <Search className="absolute left-2.5 h-3.5 w-3.5 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filtrar notas..."
              className="w-full rounded-lg border border-white/[0.07] bg-white/[0.03] py-1.5 pl-8 pr-2.5 text-xs text-white placeholder-zinc-500 focus:border-cyan-400/40 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filteredNotes.length === 0 ? (
            <div className="px-3 py-8 text-center text-xs text-zinc-500">
              Nenhuma nota encontrada no vault.
            </div>
          ) : (
            filteredNotes.map((note) => {
              const isActive = note === activeNoteName;
              const isOrphan = orphanSet.has(note.toLowerCase());
              return (
                <button
                  key={note}
                  onClick={() => handleSelectNote(note)}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    isActive
                      ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/25'
                      : 'text-zinc-300 hover:bg-white/[0.04] border border-transparent'
                  }`}
                >
                  <span className="flex items-center gap-2 truncate">
                    <FileText className={`h-3.5 w-3.5 shrink-0 ${isActive ? 'text-cyan-400' : 'text-zinc-500'}`} />
                    <span className="truncate">{note.replace(/\.md$/i, '')}</span>
                  </span>
                  {isOrphan && (
                    <span
                      className="shrink-0 rounded bg-amber-500/15 px-1 py-0.5 text-[9px] font-semibold text-amber-300"
                      title="Nota órfã no grafo"
                    >
                      órfã
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </aside>
      <ResizableHandle
        direction="horizontal"
        value={leftWidth}
        min={180}
        max={400}
        onChange={setLeftWidth}
        onReset={resetLeftWidth}
        ariaLabel="Redimensionar explorador de notas"
      />

      {/* Center: Reader / Markdown Editor / Interactive Graph / RHO Rules */}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-[#080c12]">
        <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b border-slate-800/80 bg-[#0b111a] px-4">
          <div className="flex items-center gap-3 min-w-0">
            {/* Primary Sub-Tab Switcher */}
            <div className="flex items-center rounded-lg border border-slate-800 bg-[#070b11] p-0.5 text-[11px] shrink-0">
              <button
                type="button"
                data-testid="obsidian-tab-vault"
                onClick={() => setActiveViewTab('vault')}
                className={`flex items-center gap-1 rounded px-2.5 py-1 transition cursor-pointer ${
                  activeViewTab === 'vault' ? 'bg-sky-500/20 text-sky-200 font-semibold' : 'text-slate-400 hover:text-white'
                }`}
              >
                <FileText className="h-3 w-3" />
                <span>Notas</span>
              </button>
              <button
                type="button"
                data-testid="obsidian-tab-graph"
                onClick={() => setActiveViewTab('graph')}
                className={`flex items-center gap-1 rounded px-2.5 py-1 transition cursor-pointer ${
                  activeViewTab === 'graph' ? 'bg-sky-500/20 text-sky-200 font-semibold' : 'text-slate-400 hover:text-white'
                }`}
              >
                <Network className="h-3 w-3" />
                <span>Grafo</span>
              </button>
              <button
                type="button"
                data-testid="obsidian-tab-rules"
                onClick={() => setActiveViewTab('rules')}
                className={`flex items-center gap-1 rounded px-2.5 py-1 transition cursor-pointer ${
                  activeViewTab === 'rules' ? 'bg-sky-500/20 text-sky-200 font-semibold' : 'text-slate-400 hover:text-white'
                }`}
              >
                <Shield className="h-3 w-3" />
                <span>Regras & Memória</span>
              </button>
            </div>

            {activeViewTab === 'vault' && (
              <span className="truncate text-xs font-semibold text-white">
                {activeNoteName || 'Seleciona uma nota do Vault'}
              </span>
            )}
            {savedNotice && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                <CheckCircle2 className="h-3 w-3" />
                {savedNotice}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {activeViewTab === 'vault' && activeNoteName && (
              <>
                <div className="flex rounded-lg border border-white/[0.08] bg-black/30 p-0.5 text-[11px]">
                  <button
                    onClick={() => setViewMode('preview')}
                    className={`flex items-center gap-1 rounded px-2 py-1 cursor-pointer ${
                      viewMode === 'preview' ? 'bg-sky-500/20 text-sky-200' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Eye className="h-3 w-3" />
                    <span>Leitura</span>
                  </button>
                  <button
                    onClick={() => setViewMode('edit')}
                    className={`flex items-center gap-1 rounded px-2 py-1 cursor-pointer ${
                      viewMode === 'edit' ? 'bg-sky-500/20 text-sky-200' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Edit3 className="h-3 w-3" />
                    <span>Editar</span>
                  </button>
                </div>

                {viewMode === 'edit' && (
                  <button
                    onClick={handleSaveCurrent}
                    className="inline-flex items-center gap-1 rounded-lg bg-sky-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-sky-500 cursor-pointer"
                  >
                    <Save className="h-3 w-3" />
                    <span>Guardar</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    onAuditNoteQuality(activeNoteName);
                    setInspectorOpen(true);
                    setInspectorTab('audit');
                  }}
                  disabled={isAuditingNote}
                  className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-slate-200 hover:border-sky-400/40 hover:text-sky-200 cursor-pointer disabled:opacity-50"
                >
                  {isAuditingNote ? <Loader2 className="h-3 w-3 animate-spin" /> : <Activity className="h-3 w-3 text-sky-400" />}
                  <span>Auditar 10D</span>
                </button>

                <button
                  onClick={() => {
                    onEnrichNote(activeNoteName, true);
                    setInspectorOpen(true);
                    setInspectorTab('audit');
                  }}
                  disabled={isEnrichingNote}
                  className="inline-flex items-center gap-1 rounded-lg border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-200 hover:bg-sky-500/20 cursor-pointer disabled:opacity-50"
                >
                  {isEnrichingNote ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  <span>Enriquecer</span>
                </button>
              </>
            )}

            <button
              onClick={() => setInspectorOpen((v) => !v)}
              className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-slate-300 hover:text-white cursor-pointer"
              title="Alternar Inspetor de Diagnóstico"
            >
              {inspectorOpen ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
              <span className="hidden lg:inline">Inspetor</span>
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {activeViewTab === 'graph' ? (
            <div className="flex h-full flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 bg-[#0b111a] px-4 py-2.5 text-xs">
                <div className="flex items-center gap-1.5">
                  {[
                    { id: 'all' as const, label: `Tudo (${vaultDiagnostics?.graph_nodes?.length ?? 0})` },
                    { id: 'hubs' as const, label: 'Hubs' },
                    { id: 'orphans' as const, label: 'Órfãs' },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setGraphFilter(f.id)}
                      className={`rounded-md px-2.5 py-1 transition cursor-pointer ${
                        graphFilter === f.id ? 'bg-sky-500/20 text-sky-200 font-semibold' : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setGraphZoom((z) => Math.max(0.6, +(z - 0.15).toFixed(2)))}
                    className="rounded border border-slate-700 bg-[#080c12] p-1 text-slate-300 hover:text-white cursor-pointer"
                    title="Reduzir zoom"
                  >
                    <ZoomOut className="h-3.5 w-3.5" />
                  </button>
                  <span className="w-11 text-center font-mono text-[11px] text-slate-400">
                    {Math.round(graphZoom * 100)}%
                  </span>
                  <button
                    type="button"
                    onClick={() => setGraphZoom((z) => Math.min(2, +(z + 0.15).toFixed(2)))}
                    className="rounded border border-slate-700 bg-[#080c12] p-1 text-slate-300 hover:text-white cursor-pointer"
                    title="Aumentar zoom"
                  >
                    <ZoomIn className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setGraphZoom(1)}
                    className="rounded border border-slate-700 bg-[#080c12] p-1 text-slate-300 hover:text-white cursor-pointer"
                    title="Repor zoom"
                  >
                    <Maximize2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {graphLayout.nodes.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-[#0b111a]/60 p-8 text-center">
                  <Network className="mb-3 h-8 w-8 text-slate-500" />
                  <p className="text-sm font-semibold text-white">Sem nós disponíveis neste filtro</p>
                  <p className="mt-1 text-xs text-slate-400">
                    Clica em Atualizar Diagnóstico ou seleciona Outro filtro para visualizar ligações entre notas.
                  </p>
                </div>
              ) : (
                <div className="relative flex-1 min-h-[380px] overflow-hidden rounded-xl border border-slate-800 bg-[#070a10]">
                  <svg
                    data-testid="obsidian-graph-canvas"
                    viewBox="0 0 860 540"
                    className="h-full w-full select-none"
                  >
                    <g transform={`translate(430 270) scale(${graphZoom}) translate(-430 -270)`}>
                      {graphLayout.edges.map((edge, idx) => {
                        const s = graphLayout.byId.get(edge.source);
                        const t = graphLayout.byId.get(edge.target);
                        if (!s || !t) return null;
                        const highlighted =
                          selectedGraphNodeId === edge.source || selectedGraphNodeId === edge.target;
                        return (
                          <line
                            key={`${edge.source}-${edge.target}-${idx}`}
                            x1={s.x}
                            y1={s.y}
                            x2={t.x}
                            y2={t.y}
                            stroke={highlighted ? '#38bdf8' : '#1e293b'}
                            strokeOpacity={highlighted ? 0.85 : 0.65}
                            strokeWidth={highlighted ? 1.8 : 1}
                          />
                        );
                      })}
                      {graphLayout.nodes.map((node) => {
                        const isSelected = node.id === selectedGraphNodeId;
                        const radius = Math.min(18, 7 + (node.degree || 0) * 1.4);
                        const fill = node.is_orphan
                          ? '#f59e0b'
                          : node.is_hub
                          ? '#38bdf8'
                          : (node.score ?? 100) < 60
                          ? '#f43f5e'
                          : '#10b981';
                        return (
                          <g
                            key={node.id}
                            transform={`translate(${node.x}, ${node.y})`}
                            onClick={() => setSelectedGraphNodeId(node.id)}
                            onDoubleClick={() => openNoteFromGraph(node.label || node.id)}
                            className="cursor-pointer"
                          >
                            <circle
                              r={radius + (isSelected ? 4 : 0)}
                              fill={fill}
                              fillOpacity={isSelected ? 0.95 : 0.78}
                              stroke={isSelected ? '#ffffff' : '#0b111a'}
                              strokeWidth={isSelected ? 2.5 : 1.5}
                            />
                            <text
                              y={radius + 13}
                              textAnchor="middle"
                              className="fill-slate-300 text-[10px] font-medium pointer-events-none"
                            >
                              {(node.label || node.id).slice(0, 22)}
                            </text>
                          </g>
                        );
                      })}
                    </g>
                  </svg>

                  {selectedGraphNode && (
                    <div className="absolute bottom-3 left-3 right-3 sm:right-auto sm:w-80 rounded-xl border border-slate-700/80 bg-[#0d141f]/95 p-3 text-xs shadow-2xl backdrop-blur">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-semibold text-white">{selectedGraphNode.label}</span>
                        <span className="font-mono text-[10px] text-sky-300">grau {selectedGraphNode.degree}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-400">
                        <span>Entrada: {selectedGraphNode.in_degree}</span>
                        <span>Saída: {selectedGraphNode.out_degree}</span>
                        {selectedGraphNode.score !== null && selectedGraphNode.score !== undefined && (
                          <span>Score: {selectedGraphNode.score.toFixed(0)}%</span>
                        )}
                      </div>
                      <div className="mt-2.5 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => openNoteFromGraph(selectedGraphNode.label || selectedGraphNode.id)}
                          className="rounded-lg bg-sky-600 px-3 py-1 text-[11px] font-semibold text-white hover:bg-sky-500 cursor-pointer"
                        >
                          Abrir Nota
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedGraphNodeId(null)}
                          className="rounded-lg px-2 py-1 text-[11px] text-slate-400 hover:text-white cursor-pointer"
                        >
                          Fechar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : activeViewTab === 'rules' ? (
            <div data-testid="obsidian-rules-panel" className="mx-auto max-w-4xl space-y-6">
              {/* Linked Study Materials */}
              {studyDocuments.length > 0 && (
                <section className="rounded-xl border border-slate-800 bg-[#0b111a] p-5">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-sky-300">
                      <BookOpen className="h-4 w-4" />
                      <span>Materiais de Estudo Ligados ({studyDocuments.length})</span>
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {studyDocuments.slice(0, 6).map((doc) => (
                      <button
                        key={doc.document_id}
                        type="button"
                        onClick={() => onOpenStudyDocument?.(doc.document_id)}
                        className="flex items-center justify-between rounded-lg border border-slate-800 bg-[#080c12] px-3 py-2 text-left text-xs transition hover:border-sky-400/40 cursor-pointer"
                      >
                        <span className="truncate font-medium text-white">{doc.title}</span>
                        <span className="ml-2 shrink-0 text-[10px] font-mono text-sky-300">{doc.source_type}</span>
                      </button>
                    ))}
                  </div>
                </section>
              )}

              {/* Rules */}
              <section className="rounded-xl border border-slate-800 bg-[#0b111a] p-5">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-amber-300">
                  Regras & Memória Operacional ({rules.length})
                </h3>
                {rules.length === 0 ? (
                  <p className="text-xs text-slate-400">Sem regras persistidas neste projeto.</p>
                ) : (
                  <div className="space-y-2">
                    {rules.map((rule) => (
                      <div key={rule.rule_key} className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 bg-[#080c12] p-3 text-xs">
                        <div>
                          <div className="font-mono text-[11px] font-semibold text-sky-300">{rule.rule_key}</div>
                          <p className="mt-0.5 text-slate-200">{rule.description}</p>
                          {rule.correction && <p className="mt-1 text-[11px] text-emerald-300">Correção: {rule.correction}</p>}
                        </div>
                        {onDeleteRule && (
                          <button
                            type="button"
                            onClick={() => onDeleteRule(rule.rule_key)}
                            className="rounded p-1 text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 cursor-pointer"
                            title="Remover regra"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Architecture Memory */}
              <section className="rounded-xl border border-slate-800 bg-[#0b111a] p-5">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-sky-300">
                  Memória de Arquitetura ({architecture.length})
                </h3>
                {architecture.length === 0 ? (
                  <p className="text-xs text-slate-400">Sem módulos registados na memória arquitetural.</p>
                ) : (
                  <div className="space-y-2">
                    {architecture.map((arch) => (
                      <div key={arch.module} className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 bg-[#080c12] p-3 text-xs">
                        <div>
                          <div className="font-mono font-semibold text-white">{arch.module}</div>
                          {arch.purpose && <p className="mt-0.5 text-slate-300">{arch.purpose}</p>}
                          {arch.constraints && <p className="mt-0.5 text-[11px] text-amber-300">Restrições: {arch.constraints}</p>}
                        </div>
                        {onDeleteArchitecture && (
                          <button
                            type="button"
                            onClick={() => onDeleteArchitecture(arch.module)}
                            className="rounded p-1 text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 cursor-pointer"
                            title="Remover memória arquitetural"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Engineering Decisions */}
              <section className="rounded-xl border border-slate-800 bg-[#0b111a] p-5">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-emerald-300">
                  Decisões de Engenharia ({decisions.length})
                </h3>
                {decisions.length === 0 ? (
                  <p className="text-xs text-slate-400">Sem decisões de engenharia registadas.</p>
                ) : (
                  <div className="space-y-2">
                    {decisions.map((dec, idx) => (
                      <div key={`${dec.decision}-${idx}`} className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 bg-[#080c12] p-3 text-xs">
                        <div>
                          <div className="font-semibold text-white">{dec.decision}</div>
                          <p className="mt-0.5 text-slate-300">{dec.reason}</p>
                          {dec.impact && <p className="mt-0.5 text-[11px] text-sky-300">Impacto: {dec.impact}</p>}
                        </div>
                        {onDeleteDecision && (
                          <button
                            type="button"
                            onClick={() => onDeleteDecision(dec.decision)}
                            className="rounded p-1 text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 cursor-pointer"
                            title="Remover decisão"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          ) : !activeNoteName ? (
            <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-sky-500/25 bg-sky-500/10 text-sky-400">
                <Database className="h-6 w-6" />
              </div>
              <h2 className="text-sm font-semibold text-white">Conhecimento & Grafo Obsidian</h2>
              <p className="mt-1 text-xs text-slate-400">
                Seleciona uma nota à esquerda para ler, editar com wikilinks `[[...]]`, auditar as 10 dimensões epistémicas ou explorar o grafo de ligações.
              </p>
            </div>
          ) : viewMode === 'edit' ? (
            <textarea
              value={activeContent}
              onChange={(e) => setNoteContent(e.target.value)}
              className="h-full min-h-[500px] w-full resize-none rounded-xl border border-slate-800 bg-[#0b111a] p-4 font-mono text-xs leading-relaxed text-slate-200 focus:border-sky-400/50 focus:outline-none"
            />
          ) : (
            <article className="mx-auto max-w-3xl rounded-xl border border-slate-800/80 bg-[#0b111a] p-6 shadow-lg space-y-1.5">
              {renderMarkdownPreview(activeContent || '')}
            </article>
          )}
        </div>
      </main>

      {/* Right: Collapsible Quality Graph & Autonomous Queue Inspector */}
      {inspectorOpen && (
        <>
          <ResizableHandle
            direction="horizontal"
            reverse
            value={rightWidth}
            min={260}
            max={520}
            onChange={setRightWidth}
            onReset={resetRightWidth}
            ariaLabel="Redimensionar inspetor Obsidian"
          />
          <aside style={{ width: rightWidth }} className="flex shrink-0 flex-col border-l border-slate-800/80 bg-[#090e15]">
          <div className="flex items-center gap-1 border-b border-white/[0.07] bg-[#0b1016] p-2 text-[11px]">
            {[
              { id: 'overview', label: 'Saúde do Grafo' },
              { id: 'audit', label: 'Auditoria 10D' },
              { id: 'queue', label: `Fila (${vaultImprovementQueue.length})` },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setInspectorTab(tab.id as 'overview' | 'audit' | 'queue')}
                className={`flex-1 rounded-md px-2 py-1.5 font-medium transition cursor-pointer ${
                  inspectorTab === tab.id
                    ? 'bg-cyan-500/20 text-cyan-200'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
            {inspectorTab === 'overview' && (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5">
                    <div className="text-[10px] uppercase text-zinc-500">Qualidade Média</div>
                    <div className="mt-0.5 text-base font-bold text-cyan-300">
                      {vaultDiagnostics ? `${vaultDiagnostics.quality_average.toFixed(1)}%` : '—'}
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5">
                    <div className="text-[10px] uppercase text-zinc-500">Órfãs Genuínas</div>
                    <div className="mt-0.5 text-base font-bold text-amber-300">
                      {vaultDiagnostics?.genuine_orphans ?? 0}
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5">
                    <div className="text-[10px] uppercase text-zinc-500">Links Quebrados</div>
                    <div className="mt-0.5 text-base font-bold text-rose-300">
                      {vaultDiagnostics?.broken_links ?? 0}
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5">
                    <div className="text-[10px] uppercase text-zinc-500">Por Melhorar</div>
                    <div className="mt-0.5 text-base font-bold text-zinc-100">
                      {vaultDiagnostics?.notes_requiring_improvement ?? 0}
                    </div>
                  </div>
                </div>

                {dist && (
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-3 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-semibold text-zinc-200">
                      <span>Distribuição Epistémica</span>
                      <span className="font-mono text-zinc-400">{dist.total_audited} auditadas</span>
                    </div>
                    {[
                      { label: 'Excelente (≥ 80)', val: dist.ge_80, color: 'bg-emerald-400' },
                      { label: 'Boa (70–79)', val: dist.between_70_79, color: 'bg-cyan-400' },
                      { label: 'Média (60–69)', val: dist.between_60_69, color: 'bg-amber-400' },
                      { label: 'Fraca (< 60)', val: dist.lt_60, color: 'bg-rose-400' },
                    ].map((row) => (
                      <div key={row.label} className="space-y-1">
                        <div className="flex justify-between text-[10px] text-zinc-400">
                          <span>{row.label}</span>
                          <span className="font-mono text-zinc-200">{row.val}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/[0.06]">
                          <div
                            className={`h-full rounded-full ${row.color}`}
                            style={{
                              width: `${dist.total_audited ? Math.min(100, (row.val / dist.total_audited) * 100) : 0}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {vaultDiagnostics?.genuine_orphans_list && vaultDiagnostics.genuine_orphans_list.length > 0 && (
                  <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-3 space-y-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-300">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      <span>Notas Órfãs ({vaultDiagnostics.genuine_orphans_list.length})</span>
                    </div>
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {vaultDiagnostics.genuine_orphans_list.slice(0, 12).map((orphan) => (
                        <button
                          key={orphan}
                          onClick={() => handleSelectNote(orphan)}
                          className="block w-full truncate rounded px-2 py-1 text-left text-[11px] text-zinc-300 hover:bg-white/[0.06] hover:text-cyan-300 cursor-pointer"
                        >
                          {orphan}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {onAskAssistant && activeNoteName && (
                  <button
                    onClick={() => onAskAssistant(`Analisa ligações conceptuais e melhorias para a nota Obsidian "${activeNoteName}".`)}
                    className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20 cursor-pointer"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Pedir Análise Contextual ao Jarvis</span>
                  </button>
                )}
              </>
            )}

            {inspectorTab === 'audit' && (
              <>
                {noteQualityAudit ? (
                  <div className="space-y-3">
                    <div className="rounded-lg border border-white/[0.08] bg-[#0d131a] p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white truncate">{noteQualityAudit.stem}</span>
                        <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-xs font-bold text-cyan-300">
                          {noteQualityAudit.overall_score.toFixed(0)}%
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-400">
                        <span>{noteQualityAudit.epistemic_classification}</span>
                        <span>•</span>
                        <span>{noteQualityAudit.word_count} palavras</span>
                        <span>•</span>
                        <span>{noteQualityAudit.outgoing_links_count} links</span>
                      </div>
                    </div>

                    <div className="rounded-lg border border-white/[0.08] bg-[#0d131a] p-3 space-y-2">
                      <div className="text-[11px] font-semibold text-zinc-200">Dimensões Avaliadas</div>
                      {Object.entries(noteQualityAudit.dimension_scores || {}).map(([dim, score]) => (
                        <div key={dim} className="space-y-1">
                          <div className="flex justify-between text-[10px] text-zinc-400">
                            <span className="capitalize">{dim.replace(/_/g, ' ')}</span>
                            <span className="font-mono text-zinc-200">{Number(score).toFixed(0)}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-white/[0.06]">
                            <div
                              className="h-full rounded-full bg-cyan-400"
                              style={{ width: `${Math.min(100, Math.max(0, Number(score)))}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {noteQualityAudit.findings?.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold text-zinc-300">Oportunidades de Melhoria</div>
                        {noteQualityAudit.findings.map((f, idx) => (
                          <div key={idx} className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5 text-[11px] space-y-1">
                            <div className="font-semibold text-amber-300 capitalize">{f.dimension.replace(/_/g, ' ')}</div>
                            <p className="text-zinc-300">{f.what_is_missing}</p>
                            <p className="text-cyan-300/90">{f.recommended_improvement}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {noteEnrichmentProposal && (
                      <div className="rounded-lg border border-emerald-500/25 bg-emerald-950/15 p-3 space-y-2 text-[11px]">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-emerald-300">Proposta Aplicada/Gerada</span>
                          <button
                            onClick={() =>
                              onRollbackNote(noteEnrichmentProposal.rel_path, noteEnrichmentProposal.backup_path)
                            }
                            className="inline-flex items-center gap-1 text-[10px] text-amber-300 hover:underline cursor-pointer"
                          >
                            <RotateCcw className="h-3 w-3" />
                            <span>Reverter</span>
                          </button>
                        </div>
                        <p className="text-zinc-400">
                          {noteEnrichmentProposal.proposed_relationships?.length || 0} ligações sugeridas
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-5 text-center text-xs text-zinc-400">
                    Clica em <strong className="text-cyan-300">Auditar 10D</strong> numa nota para inspecionar rigor epistémico, lacunas e ligações em falta.
                  </div>
                )}
              </>
            )}

            {inspectorTab === 'queue' && (
              <div className="space-y-3">
                <div className="rounded-lg border border-white/[0.08] bg-[#0d131a] p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-white">Worker Autónomo</span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                        queueMetrics?.is_paused
                          ? 'bg-amber-500/15 text-amber-300'
                          : queueMetrics?.is_running
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : 'bg-white/10 text-zinc-300'
                      }`}
                    >
                      {queueMetrics?.is_paused ? 'Pausado' : queueMetrics?.is_running ? 'Em Execução' : 'Em Espera'}
                    </span>
                  </div>
                  <div className="flex gap-1.5">
                    {queueMetrics?.is_paused ? (
                      <button
                        onClick={onResumeQueueWorker}
                        className="flex flex-1 items-center justify-center gap-1 rounded bg-emerald-600/80 py-1.5 text-[11px] font-semibold text-white hover:bg-emerald-500 cursor-pointer"
                      >
                        <Play className="h-3 w-3" />
                        <span>Retomar</span>
                      </button>
                    ) : (
                      <button
                        onClick={onPauseQueueWorker}
                        className="flex flex-1 items-center justify-center gap-1 rounded border border-white/10 bg-white/[0.05] py-1.5 text-[11px] text-zinc-200 hover:bg-white/10 cursor-pointer"
                      >
                        <Pause className="h-3 w-3" />
                        <span>Pausar</span>
                      </button>
                    )}
                    <button
                      onClick={() => onStartImprovementBatch(2)}
                      className="flex flex-1 items-center justify-center gap-1 rounded bg-cyan-600 py-1.5 text-[11px] font-semibold text-white hover:bg-cyan-500 cursor-pointer"
                    >
                      <Layers className="h-3 w-3" />
                      <span>Executar Lote</span>
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  {vaultImprovementQueue.length === 0 ? (
                    <div className="rounded-lg border border-white/[0.06] bg-[#0d131a] p-4 text-center text-xs text-zinc-500">
                      Nenhuma nota pendente na fila de melhoria.
                    </div>
                  ) : (
                    vaultImprovementQueue.map((item) => (
                      <div
                        key={item.item_id}
                        className="rounded-lg border border-white/[0.07] bg-[#0d131a] p-2.5 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <button
                            onClick={() => {
                              handleSelectNote(item.note_path);
                              onAuditNoteQuality(item.note_path);
                            }}
                            className="truncate font-semibold text-cyan-300 hover:underline cursor-pointer"
                          >
                            {item.stem}
                          </button>
                          <span className="font-mono text-[10px] text-zinc-400">
                            {item.overall_score.toFixed(0)}%
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-zinc-500">
                          <span>{item.epistemic_classification}</span>
                          <span>{item.status}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
          </aside>
        </>
      )}
    </div>
  );
};
