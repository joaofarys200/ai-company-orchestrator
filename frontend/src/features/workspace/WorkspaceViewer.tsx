import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BookOpen,
  Brain,
  Check,
  Copy,
  FileCode,
  FolderOpen,
  GitCompareArrows,
  GitPullRequest,
  KanbanSquare,
  Layers,
  MessageSquare,
  Play,
  RefreshCw,
  Save,
  Search,
  Shield,
  Square,
  Terminal,
  Trash2,
  Undo2,
  WandSparkles,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';
import { MissionPlanner } from '../planner';

interface WorkspaceViewerProps {
  onClose?: () => void;
}

type TabType = 'kanban' | 'debates' | 'files' | 'preview' | 'terminal' | 'coding' | 'knowledge' | 'rules' | 'planner';
type DiffLine = { type: 'added' | 'removed' | 'unchanged'; text: string };

const PANEL = 'bg-[#070a10]/80 border border-white/8 rounded-md shadow-[0_16px_50px_rgba(0,0,0,0.28)]';
const SUBTLE_PANEL = 'bg-white/[0.035] border border-white/8 rounded-md';
const BUTTON_BASE = 'inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-45';
const ICON_BUTTON = 'inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/8 bg-white/[0.04] text-gray-400 transition-all hover:border-white/16 hover:bg-white/[0.08] hover:text-white';

const KANBAN_COLUMNS = [
  { id: 'backlog', label: 'Backlog', tone: 'border-gray-500/30', dot: 'bg-gray-400' },
  { id: 'progress', label: 'Em execucao', tone: 'border-sky-400/30', dot: 'bg-sky-400' },
  { id: 'review', label: 'Revisao QA', tone: 'border-amber-400/30', dot: 'bg-amber-400' },
  { id: 'done', label: 'Concluido', tone: 'border-emerald-400/30', dot: 'bg-emerald-400' },
] as const;

function computeDiff(oldCode: string, newCode: string): DiffLine[] {
  const oldLines = oldCode.split('\n');
  const newLines = newCode.split('\n');
  const m = oldLines.length;
  const n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 1; i <= m; i += 1) {
    for (let j = 1; j <= n; j += 1) {
      dp[i][j] = oldLines[i - 1] === newLines[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  const result: DiffLine[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.push({ type: 'unchanged', text: oldLines[i - 1] });
      i -= 1;
      j -= 1;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'added', text: newLines[j - 1] });
      j -= 1;
    } else {
      result.push({ type: 'removed', text: oldLines[i - 1] });
      i -= 1;
    }
  }

  return result.reverse();
}

const lineNumbersFor = (code: string) => Array.from({ length: code.split('\n').length }, (_, index) => index + 1);

const normalizePlannerStatus = (status: string | undefined) => String(status || '').toUpperCase();

function plannerStatusLabel(status: string | undefined) {
  const normalized = normalizePlannerStatus(status);
  if (normalized === 'DONE') return 'Concluido';
  if (normalized === 'IN_PROGRESS') return 'Em curso';
  if (normalized === 'BLOCKED') return 'Bloqueado';
  if (normalized === 'FAILED') return 'Falhou';
  return 'Pendente';
}

function plannerStepTone(status: string | undefined) {
  const normalized = normalizePlannerStatus(status);
  if (normalized === 'DONE') {
    return {
      article: 'border-emerald-300/24 bg-emerald-300/8',
      marker: 'border-emerald-300 bg-emerald-300 text-black',
      label: 'text-emerald-200',
      line: 'bg-emerald-300/25',
    };
  }
  if (normalized === 'IN_PROGRESS') {
    return {
      article: 'border-cyan-300/35 bg-cyan-300/10 shadow-[0_0_26px_rgba(34,211,238,0.08)]',
      marker: 'border-cyan-300 bg-cyan-300 text-black',
      label: 'text-cyan-100',
      line: 'bg-cyan-300/25',
    };
  }
  if (normalized === 'BLOCKED' || normalized === 'FAILED') {
    return {
      article: 'border-rose-300/25 bg-rose-300/8',
      marker: 'border-rose-300 bg-rose-300 text-black',
      label: 'text-rose-200',
      line: 'bg-rose-300/20',
    };
  }
  return {
    article: 'border-white/8 bg-white/[0.035]',
    marker: 'border-white/12 bg-[#080b12] text-gray-500',
    label: 'text-gray-500',
    line: 'bg-white/10',
  };
}

function EmptyState({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex h-full min-h-48 flex-col items-center justify-center gap-3 text-center text-gray-500">
      <div className="flex h-11 w-11 items-center justify-center rounded-md border border-white/8 bg-white/[0.04]">
        <Icon className="h-5 w-5 text-gray-400" />
      </div>
      <p className="max-w-sm text-sm">{title}</p>
    </div>
  );
}

function ViewFrame({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.16 }}
      className={`h-full overflow-hidden ${className}`}
    >
      {children}
    </motion.div>
  );
}

export const WorkspaceViewer: React.FC<WorkspaceViewerProps> = ({ onClose }) => {
  const {
    kanban,
    debateMessages,
    projectFiles,
    projectOutput,
    isProjectRunning,
    previewUrl,
    runProject,
    stopProject,
    notes,
    rules,
    architecture,
    decisions,
    currentNote,
    getNotes,
    readNote,
    saveNote,
    deleteRule,
    deleteArchitecture,
    deleteDecision,
    plannerState,
    astState,
    getPlannerState,
    getAstState,
    projects,
    projectContext,
    projectReferences,
    semanticResults,
    isIndexingProject,
    openProject,
    reindexProject,
    findReferences,
    semanticSearch,
    codingSession,
    isCodingSessionBusy,
    createCodingSession,
    applyCodingSession,
    rollbackCodingSession,
  } = useWebSocket();

  const [activeTab, setActiveTab] = useState<TabType>('kanban');
  const [selectedFile, setSelectedFile] = useState('');
  const [copiedFile, setCopiedFile] = useState(false);
  const [diffMode, setDiffMode] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [noteSearch, setNoteSearch] = useState('');
  const [selectedNoteName, setSelectedNoteName] = useState('');
  const [editNoteContent, setEditNoteContent] = useState('');
  const [previousFiles, setPreviousFiles] = useState<Record<string, string>>({});
  const [codeSearch, setCodeSearch] = useState('');
  const [codingObjective, setCodingObjective] = useState('');

  const filenames = useMemo(() => Object.keys(projectFiles), [projectFiles]);
  const fileRows = useMemo(() => filenames.sort((left, right) => left.localeCompare(right)).map((filename) => ({
    filename,
    label: filename.split('/').pop() ?? filename,
    depth: Math.max(filename.split('/').length - 1, 0),
  })), [filenames]);
  const filenamesKey = filenames.join('|');
  const filteredNotes = notes.filter((note) => note.toLowerCase().includes(noteSearch.toLowerCase()));
  const currentCode = selectedFile ? (projectFiles[selectedFile] ?? '') : '';
  const previousCode = selectedFile ? (previousFiles[selectedFile] ?? '') : '';
  const diffLines = diffMode ? computeDiff(previousCode, currentCode) : [];
  const changedLineCount = diffLines.filter((line) => line.type !== 'unchanged').length;
  const plannerSteps = plannerState?.steps ?? [];
  const plannerCompletedCount = plannerSteps.filter((step) => normalizePlannerStatus(step.status) === 'DONE').length;
  const plannerActiveStep = plannerSteps.find((step) => normalizePlannerStatus(step.status) === 'IN_PROGRESS')
    ?? plannerSteps.find((step) => normalizePlannerStatus(step.status) !== 'DONE');
  const plannerProgress = plannerSteps.length > 0 ? Math.round((plannerCompletedCount / plannerSteps.length) * 100) : 0;
  const plannerPendingCount = Math.max(plannerSteps.length - plannerCompletedCount, 0);
  const plannerStatus = plannerState?.status
    ? plannerStatusLabel(plannerState.status)
    : plannerActiveStep
      ? 'Em curso'
      : plannerSteps.length > 0
        ? 'Concluido'
        : 'Sem passos';

  const tabs: Array<{ id: TabType; label: string; icon: LucideIcon; badge?: number }> = [
    { id: 'kanban', label: 'Kanban', icon: KanbanSquare },
    { id: 'debates', label: 'Debates', icon: MessageSquare, badge: debateMessages.length },
    { id: 'files', label: 'Ficheiros', icon: FileCode, badge: filenames.length },
    { id: 'preview', label: 'Preview', icon: Play },
    { id: 'terminal', label: 'Execucao', icon: Terminal },
    { id: 'coding', label: 'Alteracao', icon: GitPullRequest },
    { id: 'knowledge', label: 'Conhecimento', icon: BookOpen, badge: notes.length },
    { id: 'rules', label: 'Memoria', icon: Brain, badge: rules.length + architecture.length + decisions.length },
    { id: 'planner', label: 'Planner', icon: Activity },
  ];

  useEffect(() => {
    if (!currentNote) return;
    const timeoutId = window.setTimeout(() => setEditNoteContent(currentNote.content), 0);
    return () => window.clearTimeout(timeoutId);
  }, [currentNote]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setPreviewKey((key) => key + 1), 0);
    return () => window.clearTimeout(timeoutId);
  }, [projectFiles]);

  useEffect(() => {
    const firstFile = filenames[0] ?? '';
    if (!firstFile) {
      if (selectedFile) {
        const timeoutId = window.setTimeout(() => {
          setSelectedFile('');
          setDiffMode(false);
        }, 0);
        return () => window.clearTimeout(timeoutId);
      }
      return;
    }

    if (!selectedFile || !projectFiles[selectedFile]) {
      const timeoutId = window.setTimeout(() => {
        setSelectedFile(firstFile);
        setDiffMode(false);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }
  }, [filenames, filenamesKey, projectFiles, selectedFile]);

  const activateTab = (tab: TabType) => {
    setActiveTab(tab);
    if (tab === 'knowledge') getNotes();
    if (tab === 'planner') {
      getPlannerState();
      getAstState();
    }
  };

  const handleCopyCode = () => {
    if (!selectedFile || !projectFiles[selectedFile]) return;
    navigator.clipboard.writeText(projectFiles[selectedFile]);
    setCopiedFile(true);
    window.setTimeout(() => setCopiedFile(false), 1800);
  };

  const handleFileSelect = useCallback((filename: string) => {
    if (selectedFile && projectFiles[selectedFile]) {
      setPreviousFiles((prev) => ({ ...prev, [selectedFile]: projectFiles[selectedFile] }));
    }
    setSelectedFile(filename);
    setDiffMode(false);
  }, [projectFiles, selectedFile]);

  const diffLineStyle = (type: DiffLine['type']) => {
    if (type === 'added') return 'border-l-2 border-emerald-400 bg-emerald-500/10 text-emerald-200';
    if (type === 'removed') return 'border-l-2 border-rose-400 bg-rose-500/10 text-rose-200 line-through opacity-80';
    return 'border-l-2 border-transparent text-gray-300';
  };

  const renderHeader = () => (
    <div className="flex min-h-14 items-center gap-3 border-b border-white/8 bg-[#080b12]/95 px-3">
      <div className="flex shrink-0 items-center gap-2 border-r border-white/8 pr-3">
        <FolderOpen className="h-4 w-4 text-cyan-300" />
        <select
          value={projectContext?.project_id ?? ''}
          onChange={(event) => openProject(event.target.value)}
          className="h-9 max-w-48 rounded-md border border-white/8 bg-[#070a10] px-2 text-xs font-semibold text-gray-200 outline-none focus:border-cyan-300/35"
          title="Projeto selecionado"
        >
          <option value="" disabled>Selecionar projeto</option>
          {projects.map((project) => (
            <option key={project.project_id} value={project.project_id}>{project.project_name}</option>
          ))}
        </select>
      </div>
      <div className="flex flex-1 items-center gap-2 overflow-x-auto py-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => activateTab(tab.id)}
              className={`flex h-9 shrink-0 items-center gap-2 rounded-md border px-3 text-xs font-semibold transition-all ${
                active
                  ? 'border-cyan-400/35 bg-cyan-400/10 text-cyan-200 shadow-[0_0_18px_rgba(34,211,238,0.08)]'
                  : 'border-transparent text-gray-500 hover:border-white/8 hover:bg-white/[0.04] hover:text-gray-200'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
              {typeof tab.badge === 'number' && tab.badge > 0 && (
                <span className={`rounded px-1.5 py-0.5 text-[10px] ${active ? 'bg-cyan-300/15 text-cyan-100' : 'bg-white/8 text-gray-400'}`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {onClose && (
        <button onClick={onClose} className={ICON_BUTTON} title="Fechar painel">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-md border border-white/8 bg-[#05070c]/85 backdrop-blur-xl">
      {renderHeader()}

      <div className="min-h-0 flex-1 overflow-hidden p-3">
        <AnimatePresence mode="wait">
          {activeTab === 'kanban' && (
            <ViewFrame key="kanban" className="grid grid-cols-1 gap-3 overflow-y-auto lg:grid-cols-4">
              {KANBAN_COLUMNS.map((column) => {
                const cards = kanban[column.id];
                return (
                  <section key={column.id} className={`${PANEL} flex min-h-64 flex-col overflow-hidden border-t-2 ${column.tone}`}>
                    <div className="flex items-center justify-between border-b border-white/8 px-3 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${column.dot}`} />
                        <h3 className="text-sm font-semibold text-gray-100">{column.label}</h3>
                      </div>
                      <span className="rounded bg-white/[0.06] px-2 py-1 text-xs text-gray-400">{cards.length}</span>
                    </div>
                    <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                      {cards.length === 0 ? (
                        <div className="flex h-32 items-center justify-center text-xs text-gray-600">Sem items</div>
                      ) : (
                        cards.map((card) => (
                          <article key={card.id} className="rounded-md border border-white/8 bg-white/[0.045] p-3 shadow-sm">
                            <p className="text-sm font-medium leading-relaxed text-gray-100">{card.title}</p>
                            <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
                              <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                              <span>{card.agent}</span>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  </section>
                );
              })}
            </ViewFrame>
          )}

          {activeTab === 'debates' && (
            <ViewFrame key="debates" className={`${PANEL} flex flex-col`}>
              <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
                <h3 className="text-sm font-semibold text-gray-100">Debates internos</h3>
                <span className="text-xs text-gray-500">{debateMessages.length} mensagens</span>
              </div>
              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                {debateMessages.length === 0 ? (
                  <EmptyState icon={MessageSquare} title="Nenhum debate ativo." />
                ) : (
                  debateMessages.map((message) => (
                    <article key={message.id} className={`${SUBTLE_PANEL} p-3`}>
                      <div className="mb-2 flex items-center gap-2 text-xs">
                        <span className="font-semibold text-cyan-200">{message.sender}</span>
                        <span className="text-gray-600">{message.role}</span>
                        <span className="ml-auto text-gray-600">{message.timestamp}</span>
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-300">{message.content}</p>
                    </article>
                  ))
                )}
              </div>
            </ViewFrame>
          )}

          {activeTab === 'files' && (
            <ViewFrame key="files" className="flex flex-col gap-3 lg:flex-row">
              <aside className={`${PANEL} flex max-h-52 shrink-0 flex-col overflow-hidden lg:max-h-none lg:w-64`}>
                <div className="border-b border-white/8 px-3 py-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-100">Ficheiros</h3>
                    <span className="text-xs text-gray-500">{filenames.length}</span>
                  </div>
                  {projectContext && (
                    <div className="mt-2 space-y-1 text-[11px] text-gray-500">
                      <p className="truncate" title={projectContext.root_path}>{projectContext.root_path}</p>
                      <p>{[...projectContext.stack, ...projectContext.frameworks].join(' / ') || 'Stack desconhecida'}</p>
                      {projectContext.entrypoints.length > 0 && <p className="truncate">Entrada: {projectContext.entrypoints.join(', ')}</p>}
                    </div>
                  )}
                </div>
                <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
                  {filenames.length === 0 ? (
                    <div className="py-8 text-center text-xs text-gray-600">Sem ficheiros</div>
                  ) : (
                    fileRows.map(({ filename, label, depth }) => (
                      <button
                        key={filename}
                        onClick={() => handleFileSelect(filename)}
                        className={`w-full rounded-md px-3 py-2 text-left text-xs transition-all ${
                          selectedFile === filename
                            ? 'bg-cyan-400/10 text-cyan-100'
                            : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-100'
                        }`}
                      >
                        <span className="block truncate" style={{ paddingLeft: `${depth * 12}px` }} title={filename}>{label}</span>
                      </button>
                    ))
                  )}
                </div>
              </aside>

              <section className={`${PANEL} min-w-0 flex-1 overflow-hidden`}>
                <div className="flex items-center gap-2 border-b border-white/8 px-3 py-3">
                  <FileCode className="h-4 w-4 text-cyan-300" />
                  <span className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-100">{selectedFile || 'Sem ficheiro selecionado'}</span>
                  <button
                    onClick={() => setDiffMode((value) => !value)}
                    className={`${BUTTON_BASE} ${diffMode ? 'border-violet-400/40 bg-violet-400/10 text-violet-200' : 'border-white/8 bg-white/[0.04] text-gray-400 hover:text-white'}`}
                    disabled={!selectedFile}
                  >
                    <GitCompareArrows className="h-4 w-4" />
                    <span>{diffMode ? `Diff ${changedLineCount}` : 'Diff'}</span>
                  </button>
                  <button onClick={handleCopyCode} className={`${BUTTON_BASE} border-white/8 bg-white/[0.04] text-gray-400 hover:text-white`} disabled={!selectedFile}>
                    {copiedFile ? <Check className="h-4 w-4 text-emerald-300" /> : <Copy className="h-4 w-4" />}
                    <span>{copiedFile ? 'Copiado' : 'Copiar'}</span>
                  </button>
                </div>

                <div className="h-[calc(100%-58px)] overflow-auto bg-[#040609] p-4 font-mono text-xs leading-relaxed">
                  {!selectedFile || !currentCode ? (
                    <EmptyState icon={FileCode} title="Selecione um ficheiro para ver o codigo." />
                  ) : diffMode ? (
                    <div className="min-w-max">
                      {diffLines.map((line, index) => (
                        <div key={`${index}-${line.type}`} className={`grid grid-cols-[44px_28px_1fr] gap-2 rounded-sm px-2 py-0.5 ${diffLineStyle(line.type)}`}>
                          <span className="select-none text-right text-gray-600">{index + 1}</span>
                          <span className="select-none text-gray-500">{line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ''}</span>
                          <pre className="whitespace-pre">{line.text}</pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="grid min-w-max grid-cols-[44px_1fr]">
                      <div className="select-none border-r border-white/8 pr-3 text-right text-gray-700">
                        {lineNumbersFor(currentCode).map((line) => (
                          <div key={line}>{line}</div>
                        ))}
                      </div>
                      <pre className="pl-4 text-gray-300"><code>{currentCode}</code></pre>
                    </div>
                  )}
                </div>
              </section>
            </ViewFrame>
          )}

          {activeTab === 'preview' && (
            <ViewFrame key="preview" className={`${PANEL} flex flex-col`}>
              <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
                <Play className="h-4 w-4 text-emerald-300" />
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-gray-100">Preview do projeto</h3>
                  {projectContext && <p className="truncate text-[11px] text-gray-500">{projectContext.root_path}</p>}
                </div>
                <button onClick={() => setPreviewKey((key) => key + 1)} className={ICON_BUTTON} title="Atualizar preview">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
              <div className="min-h-0 flex-1 bg-white">
                <iframe key={previewKey} src={previewUrl} className="h-full w-full border-none" title="Project Preview" />
              </div>
            </ViewFrame>
          )}

          {activeTab === 'terminal' && (
            <ViewFrame key="terminal" className={`${PANEL} flex flex-col`}>
              <div className="flex flex-col gap-3 border-b border-white/8 px-4 py-3 sm:flex-row sm:items-center">
                <div className="flex flex-1 items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${isProjectRunning ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]' : 'bg-gray-600'}`} />
                  <h3 className="text-sm font-semibold text-gray-100">Consola</h3>
                </div>
                <div className="flex gap-2">
                  <button onClick={runProject} disabled={isProjectRunning || !projectContext} className={`${BUTTON_BASE} border-emerald-400/25 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/15`}>
                    <Play className="h-4 w-4" />
                    <span>Iniciar</span>
                  </button>
                  <button onClick={stopProject} disabled={!isProjectRunning} className={`${BUTTON_BASE} border-rose-400/25 bg-rose-400/10 text-rose-200 hover:bg-rose-400/15`}>
                    <Square className="h-4 w-4" />
                    <span>Parar</span>
                  </button>
                </div>
              </div>
              {projectContext?.suggested_commands.length ? (
                <div className="border-b border-white/8 bg-black/20 px-4 py-3">
                  <p className="mb-2 text-xs font-semibold text-gray-300">Validacoes sugeridas</p>
                  <div className="flex flex-wrap gap-2">
                    {projectContext.suggested_commands.map((command) => (
                      <code key={`${command.kind}-${command.command}`} className="rounded bg-white/[0.05] px-2 py-1 text-[11px] text-cyan-100" title={command.source}>
                        {command.command}
                      </code>
                    ))}
                  </div>
                </div>
              ) : null}
              <pre className="min-h-0 flex-1 overflow-auto bg-[#030503] p-4 font-mono text-xs leading-relaxed text-emerald-300">
                <code>{projectOutput || '[Consola] Sem output.'}</code>
              </pre>
            </ViewFrame>
          )}

          {activeTab === 'coding' && (
            <ViewFrame key="coding" className="grid grid-cols-1 gap-3 overflow-y-auto lg:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
              <section className={`${PANEL} flex min-h-0 flex-col overflow-hidden`}>
                <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
                  <GitPullRequest className="h-4 w-4 text-cyan-300" />
                  <h3 className="flex-1 text-sm font-semibold text-gray-100">CodingSession</h3>
                  {codingSession && (
                    <span className="rounded bg-white/[0.06] px-2 py-1 text-[10px] font-semibold text-gray-300">{codingSession.status}</span>
                  )}
                </div>
                <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                  <textarea
                    value={codingObjective}
                    onChange={(event) => setCodingObjective(event.target.value)}
                    placeholder="Objetivo da alteracao"
                    className="h-28 w-full resize-none rounded-md border border-white/8 bg-black/25 p-3 text-sm leading-relaxed text-gray-200 outline-none focus:border-cyan-300/30"
                  />
                  <button
                    onClick={() => createCodingSession(codingObjective)}
                    disabled={!projectContext || !codingObjective.trim() || isCodingSessionBusy}
                    className={`${BUTTON_BASE} w-full border-cyan-300/25 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15`}
                  >
                    <WandSparkles className={`h-4 w-4 ${isCodingSessionBusy ? 'animate-pulse' : ''}`} />
                    <span>Criar plano</span>
                  </button>

                  {codingSession && (
                    <div className="space-y-3 border-t border-white/8 pt-3 text-xs">
                      <div>
                        <p className="mb-1 font-semibold text-gray-200">Objetivo</p>
                        <p className="leading-relaxed text-gray-400">{codingSession.change_plan.objective}</p>
                      </div>
                      <div>
                        <p className="mb-1 font-semibold text-gray-200">Ficheiros</p>
                        {codingSession.affected_files.map((file) => <code key={file} className="block py-0.5 text-cyan-200">{file}</code>)}
                      </div>
                      {codingSession.change_plan.affected_symbols.length > 0 && (
                        <div>
                          <p className="mb-1 font-semibold text-gray-200">Simbolos</p>
                          <p className="text-violet-200">{codingSession.change_plan.affected_symbols.join(', ')}</p>
                        </div>
                      )}
                      {codingSession.change_plan.risks.length > 0 && (
                        <div>
                          <p className="mb-1 font-semibold text-amber-200">Riscos</p>
                          {codingSession.change_plan.risks.map((risk) => <p key={risk} className="py-0.5 text-amber-100/75">{risk}</p>)}
                        </div>
                      )}
                      <div>
                        <p className="mb-1 font-semibold text-gray-200">Validacoes</p>
                        {codingSession.change_plan.validations.map((validation) => (
                          <code key={validation.command} className="block break-all py-0.5 text-gray-400">{validation.command}</code>
                        ))}
                      </div>
                      {Object.keys(codingSession.checkpoint).length > 0 && (
                        <p className="text-gray-500">Checkpoint: {String(codingSession.checkpoint.type ?? 'criado')}</p>
                      )}
                    </div>
                  )}
                </div>
                {codingSession && (
                  <div className="flex gap-2 border-t border-white/8 p-3">
                    <button
                      onClick={applyCodingSession}
                      disabled={codingSession.status !== 'PROPOSED' || isCodingSessionBusy}
                      className={`${BUTTON_BASE} flex-1 border-emerald-300/25 bg-emerald-300/10 text-emerald-100 hover:bg-emerald-300/15`}
                    >
                      <Play className="h-4 w-4" />
                      <span>Aplicar</span>
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('Reverter apenas os ficheiros alterados por esta sessao?')) rollbackCodingSession();
                      }}
                      disabled={!Object.keys(codingSession.checkpoint).length || ['ROLLED_BACK', 'ERROR_ROLLED_BACK'].includes(codingSession.status) || isCodingSessionBusy}
                      className={`${BUTTON_BASE} flex-1 border-rose-300/25 bg-rose-300/10 text-rose-100 hover:bg-rose-300/15`}
                    >
                      <Undo2 className="h-4 w-4" />
                      <span>Reverter</span>
                    </button>
                  </div>
                )}
              </section>

              <section className={`${PANEL} min-h-0 overflow-y-auto p-4`}>
                {!codingSession ? (
                  <EmptyState icon={GitPullRequest} title="Nenhuma alteracao preparada." />
                ) : (
                  <div className="space-y-4">
                    {codingSession.proposed_changes.map((change) => (
                      <article key={`${change.file}-${change.symbol ?? change.operation}`} className="border-b border-white/8 pb-4 last:border-0">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <h4 className="font-mono text-sm font-semibold text-gray-100">{change.file}</h4>
                          {change.symbol && <span className="rounded bg-violet-300/10 px-2 py-1 text-[10px] text-violet-200">{change.symbol}</span>}
                        </div>
                        <p className="mb-3 text-xs leading-relaxed text-gray-400">{change.reason}</p>
                        <div className="grid gap-2 xl:grid-cols-2">
                          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-rose-300/10 bg-rose-300/[0.04] p-3 text-xs text-rose-100/75">{change.previous_excerpt || '(novo ficheiro)'}</pre>
                          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-emerald-300/10 bg-emerald-300/[0.04] p-3 text-xs text-emerald-100/75">{change.proposed_excerpt}</pre>
                        </div>
                        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-black/30 p-3 font-mono text-xs leading-relaxed text-gray-300">{change.unified_diff}</pre>
                      </article>
                    ))}

                    {codingSession.validation_results.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-sm font-semibold text-gray-100">Resultados de validacao</h4>
                        <div className="space-y-2">
                          {codingSession.validation_results.map((result) => (
                            <div key={result.command} className={`${SUBTLE_PANEL} p-3 text-xs`}>
                              <div className="flex items-center gap-2">
                                <Check className={`h-4 w-4 ${result.exit_code === 0 ? 'text-emerald-300' : 'text-rose-300'}`} />
                                <code className="min-w-0 flex-1 break-all text-gray-200">{result.command}</code>
                                <span className={result.exit_code === 0 ? 'text-emerald-300' : 'text-rose-300'}>exit {result.exit_code}</span>
                                <span className="text-gray-600">{result.duration_seconds}s</span>
                              </div>
                              {(result.stdout || result.stderr) && (
                                <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap bg-black/20 p-2 text-gray-500">{result.stderr || result.stdout}</pre>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {codingSession.errors.length > 0 && (
                      <div className="rounded-md border border-rose-300/20 bg-rose-300/8 p-3 text-xs text-rose-100">
                        {codingSession.errors.map((error) => <p key={error}>{error}</p>)}
                      </div>
                    )}
                  </div>
                )}
              </section>
            </ViewFrame>
          )}

          {activeTab === 'knowledge' && (
            <ViewFrame key="knowledge" className="flex flex-col gap-3 lg:flex-row">
              <aside className={`${PANEL} flex max-h-64 shrink-0 flex-col overflow-hidden lg:max-h-none lg:w-72`}>
                <div className="border-b border-white/8 px-3 py-3">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-100">Obsidian</h3>
                    <span className="text-xs text-gray-500">{filteredNotes.length}</span>
                  </div>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
                    <input
                      type="text"
                      placeholder="Pesquisar"
                      value={noteSearch}
                      onChange={(event) => setNoteSearch(event.target.value)}
                      className="h-9 w-full rounded-md border border-white/8 bg-black/30 pl-9 pr-3 text-sm text-gray-200 outline-none transition focus:border-cyan-300/30"
                    />
                  </div>
                </div>
                <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
                  {filteredNotes.length === 0 ? (
                    <div className="py-8 text-center text-xs text-gray-600">Sem notas</div>
                  ) : (
                    filteredNotes.map((name) => (
                      <button
                        key={name}
                        onClick={() => {
                          setSelectedNoteName(name);
                          readNote(name);
                        }}
                        className={`w-full rounded-md px-3 py-2 text-left text-xs transition-all ${
                          selectedNoteName === name
                            ? 'bg-cyan-400/10 text-cyan-100'
                            : 'text-gray-400 hover:bg-white/[0.05] hover:text-gray-100'
                        }`}
                      >
                        <span className="block truncate">{name}</span>
                      </button>
                    ))
                  )}
                </div>
                <button
                  onClick={() => {
                    const newName = prompt('Nome da nova nota');
                    if (newName) {
                      saveNote(newName, `# ${newName}`);
                      setSelectedNoteName(newName);
                    }
                  }}
                  className="m-2 rounded-md border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-300/15"
                >
                  Nova nota
                </button>
              </aside>

              <section className={`${PANEL} min-w-0 flex-1 overflow-hidden`}>
                {currentNote && currentNote.filename === selectedNoteName ? (
                  <div className="flex h-full flex-col">
                    <div className="flex items-center gap-3 border-b border-white/8 px-3 py-3">
                      <BookOpen className="h-4 w-4 text-cyan-300" />
                      <span className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-100">{currentNote.filename}</span>
                      <button onClick={() => saveNote(currentNote.filename, editNoteContent)} className={`${BUTTON_BASE} border-cyan-300/25 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15`}>
                        <Save className="h-4 w-4" />
                        <span>Guardar</span>
                      </button>
                    </div>
                    <textarea
                      value={editNoteContent}
                      onChange={(event) => setEditNoteContent(event.target.value)}
                      className="min-h-0 flex-1 resize-none bg-[#040609] p-4 font-mono text-sm leading-relaxed text-gray-300 outline-none"
                      placeholder="Markdown"
                    />
                  </div>
                ) : (
                  <EmptyState icon={BookOpen} title="Selecione uma nota." />
                )}
              </section>
            </ViewFrame>
          )}

          {activeTab === 'rules' && (
            <ViewFrame key="rules" className="grid grid-cols-1 gap-3 overflow-hidden xl:grid-cols-3">
              <MemoryColumn
                title="Compounding"
                icon={Brain}
                tone="text-cyan-200"
                count={`${rules.length} regras`}
                empty="Sem regras ativas."
              >
                {rules.map((rule) => (
                  <article key={rule.rule_key} className={`${SUBTLE_PANEL} p-3`}>
                    <div className="mb-2 flex items-start gap-2">
                      <Brain className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
                      <div className="min-w-0 flex-1">
                        <h4 className="truncate text-sm font-semibold text-gray-100">{rule.rule_key}</h4>
                      </div>
                      <button
                        onClick={() => {
                          if (confirm(`Apagar regra '${rule.rule_key}'?`)) deleteRule(rule.rule_key);
                        }}
                        className="text-gray-600 transition hover:text-rose-300"
                        title="Apagar regra"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="mb-2 text-xs leading-relaxed text-gray-500">{rule.description}</p>
                    <p className="rounded-md bg-black/25 p-2 text-xs leading-relaxed text-gray-300">{rule.correction}</p>
                  </article>
                ))}
              </MemoryColumn>

              <MemoryColumn
                title="Arquitetura"
                icon={Layers}
                tone="text-violet-200"
                count={`${architecture.length} modulos`}
                empty="Sem modulos registados."
              >
                {architecture.map((item) => (
                  <article key={item.module} className={`${SUBTLE_PANEL} p-3`}>
                    <div className="mb-2 flex items-start gap-2">
                      <Layers className="mt-0.5 h-4 w-4 shrink-0 text-violet-300" />
                      <h4 className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-100">{item.module}</h4>
                      <button
                        onClick={() => {
                          if (confirm(`Apagar modulo '${item.module}'?`)) deleteArchitecture(item.module);
                        }}
                        className="text-gray-600 transition hover:text-rose-300"
                        title="Apagar modulo"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    {item.purpose && <p className="mb-2 text-xs leading-relaxed text-gray-300">{item.purpose}</p>}
                    {item.dependencies && <p className="mb-2 text-xs leading-relaxed text-gray-500">Deps: {item.dependencies}</p>}
                    {item.constraints && <p className="rounded-md border border-amber-300/10 bg-amber-300/8 p-2 text-xs leading-relaxed text-amber-100">{item.constraints}</p>}
                  </article>
                ))}
              </MemoryColumn>

              <MemoryColumn
                title="Decisoes"
                icon={Shield}
                tone="text-emerald-200"
                count={`${decisions.length} decisoes`}
                empty="Sem decisoes registadas."
              >
                {decisions.map((decision) => (
                  <article key={decision.decision} className={`${SUBTLE_PANEL} p-3`}>
                    <div className="mb-2 flex items-start gap-2">
                      <Shield className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                      <h4 className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-100">{decision.decision}</h4>
                      <button
                        onClick={() => {
                          if (confirm(`Apagar decisao '${decision.decision}'?`)) deleteDecision(decision.decision);
                        }}
                        className="text-gray-600 transition hover:text-rose-300"
                        title="Apagar decisao"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="mb-2 text-xs leading-relaxed text-gray-300">{decision.reason}</p>
                    {decision.impact && <p className="rounded-md bg-black/25 p-2 text-xs leading-relaxed text-gray-400">{decision.impact}</p>}
                  </article>
                ))}
              </MemoryColumn>
            </ViewFrame>
          )}

          {activeTab === 'planner' && (
            <ViewFrame key="planner" className="grid grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.75fr)]">
              <MissionPlanner />
              <section className={`${PANEL} hidden min-h-0 flex-col overflow-hidden`} aria-hidden="true">
                <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
                  <Activity className="h-4 w-4 text-cyan-300" />
                  <h3 className="flex-1 text-sm font-semibold text-gray-100">Plano persistente</h3>
                  {plannerState && (
                    <span className="rounded-md border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-1 text-xs font-semibold text-cyan-100">
                      {plannerStatus}
                    </span>
                  )}
                  <button onClick={getPlannerState} className={ICON_BUTTON} title="Atualizar plano">
                    <RefreshCw className="h-4 w-4" />
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-4">
                  {!plannerState ? (
                    <EmptyState icon={Activity} title="Nenhum plano ativo." />
                  ) : (
                    <div className="space-y-4">
                      <div className={`${SUBTLE_PANEL} overflow-hidden`}>
                        <div className="flex flex-col gap-3 p-4 lg:flex-row lg:items-start">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Objetivo</p>
                            <p className="mt-2 text-base font-semibold leading-relaxed text-gray-100">{plannerState.goal || 'Sem objetivo definido'}</p>
                          </div>
                          <div className="grid grid-cols-3 gap-2 lg:w-72">
                            <div className="rounded-md border border-white/8 bg-black/20 p-2.5">
                              <p className="text-[10px] uppercase text-gray-600">Progresso</p>
                              <p className="mt-1 text-lg font-semibold text-cyan-100">{plannerProgress}%</p>
                            </div>
                            <div className="rounded-md border border-white/8 bg-black/20 p-2.5">
                              <p className="text-[10px] uppercase text-gray-600">Feitos</p>
                              <p className="mt-1 text-lg font-semibold text-emerald-100">{plannerCompletedCount}</p>
                            </div>
                            <div className="rounded-md border border-white/8 bg-black/20 p-2.5">
                              <p className="text-[10px] uppercase text-gray-600">Por fazer</p>
                              <p className="mt-1 text-lg font-semibold text-gray-100">{plannerPendingCount}</p>
                            </div>
                          </div>
                        </div>
                        <div className="h-1 bg-white/[0.04]">
                          <div className="h-full bg-cyan-300 transition-all duration-500" style={{ width: `${plannerProgress}%` }} />
                        </div>
                      </div>

                      {plannerActiveStep && (
                        <div className="rounded-md border border-cyan-300/20 bg-cyan-300/8 p-4">
                          <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-cyan-100">
                            <Play className="h-3.5 w-3.5" />
                            <span>Proxima acao</span>
                          </div>
                          <p className="text-sm leading-relaxed text-gray-100">{plannerActiveStep.action}</p>
                        </div>
                      )}

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-semibold text-gray-100">Linha de execucao</h4>
                          <span className="text-xs text-gray-500">{plannerSteps.length} passos</span>
                        </div>

                        {plannerSteps.length === 0 ? (
                          <EmptyState icon={Activity} title="O plano existe, mas ainda nao tem passos." />
                        ) : (
                          <div className="relative space-y-3">
                            {plannerSteps.map((step, index) => {
                              const tone = plannerStepTone(step.status);
                              const normalized = normalizePlannerStatus(step.status);
                              const isDone = normalized === 'DONE';
                              const isCurrent = normalized === 'IN_PROGRESS' || step === plannerActiveStep;

                              return (
                                <article key={step.id} className="relative grid grid-cols-[40px_1fr] gap-3">
                                  {index < plannerSteps.length - 1 && (
                                    <span className={`absolute left-[19px] top-10 h-[calc(100%+12px)] w-px ${tone.line}`} />
                                  )}
                                  <div className={`z-10 flex h-10 w-10 items-center justify-center rounded-full border text-xs font-bold ${tone.marker}`}>
                                    {isDone ? <Check className="h-4 w-4" /> : step.id}
                                  </div>
                                  <div className={`rounded-md border p-3 ${tone.article}`}>
                                    <div className="mb-2 flex flex-wrap items-center gap-2">
                                      <span className={`text-xs font-semibold ${tone.label}`}>Passo {step.id}</span>
                                      <span className="rounded bg-white/[0.06] px-2 py-0.5 text-[10px] text-gray-400">{plannerStatusLabel(step.status)}</span>
                                      {isCurrent && (
                                        <span className="rounded bg-cyan-300/12 px-2 py-0.5 text-[10px] font-semibold text-cyan-100">ativo</span>
                                      )}
                                    </div>
                                    <p className="text-sm leading-relaxed text-gray-200">{step.action}</p>
                                  </div>
                                </article>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </section>

              <section className={`${PANEL} flex min-h-0 flex-col overflow-hidden`}>
                <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
                  <FileCode className="h-4 w-4 text-violet-300" />
                  <h3 className="flex-1 text-sm font-semibold text-gray-100">AST e simbolos</h3>
                  <button onClick={reindexProject} disabled={!projectContext || isIndexingProject} className={`${BUTTON_BASE} border-violet-300/20 bg-violet-300/8 text-violet-100 hover:bg-violet-300/12`} title="Reindexar o projeto selecionado">
                    <RefreshCw className={`h-4 w-4 ${isIndexingProject ? 'animate-spin' : ''}`} />
                    <span>Reindexar</span>
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-4">
                  {projectContext && (
                    <div className={`${SUBTLE_PANEL} mb-3 space-y-2 p-3 text-xs`}>
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold text-gray-200">{projectContext.project_name}</span>
                        <span className="text-gray-500">{String(projectContext.ast_index.status ?? 'sem indice')}</span>
                      </div>
                      <p className="break-all text-gray-500">{projectContext.root_path}</p>
                      <div className="flex flex-wrap gap-2 text-gray-400">
                        {[...projectContext.stack, ...projectContext.frameworks, ...projectContext.package_managers].map((item) => (
                          <span key={item} className="rounded bg-white/[0.05] px-2 py-1">{item}</span>
                        ))}
                      </div>
                      <p className="text-gray-500">Ultimo indice: {projectContext.last_indexed_at ? new Date(projectContext.last_indexed_at).toLocaleString('pt-PT') : 'nunca'}</p>
                    </div>
                  )}

                  <div className="mb-3 flex gap-2">
                    <div className="relative min-w-0 flex-1">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
                      <input
                        value={codeSearch}
                        onChange={(event) => setCodeSearch(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') findReferences(codeSearch);
                        }}
                        placeholder="Simbolo ou pesquisa contextual"
                        className="h-9 w-full rounded-md border border-white/8 bg-black/25 pl-9 pr-3 text-xs text-gray-200 outline-none focus:border-cyan-300/30"
                      />
                    </div>
                    <button onClick={() => findReferences(codeSearch)} className={ICON_BUTTON} title="Localizar definicao e referencias">
                      <FileCode className="h-4 w-4" />
                    </button>
                    <button onClick={() => semanticSearch(codeSearch)} className={ICON_BUTTON} title="Pesquisa semantica">
                      <Search className="h-4 w-4" />
                    </button>
                  </div>

                  {projectReferences && (
                    <div className={`${SUBTLE_PANEL} mb-3 p-3 text-xs`}>
                      <h4 className="mb-2 font-semibold text-gray-100">Referencias de {projectReferences.symbol}</h4>
                      {[...projectReferences.definitions, ...projectReferences.references].length === 0 ? (
                        <p className="text-gray-500">Nenhuma ocorrencia encontrada.</p>
                      ) : (
                        <div className="space-y-1.5">
                          {[...projectReferences.definitions, ...projectReferences.references].map((reference, index) => (
                            <button
                              key={`${reference.file}-${reference.line}-${index}`}
                              onClick={() => handleFileSelect(reference.file)}
                              className="block w-full text-left text-gray-300 hover:text-cyan-100"
                              title={reference.text}
                            >
                              <span className={reference.confirmed ? 'text-emerald-300' : 'text-amber-300'}>{reference.confirmed ? 'AST' : 'texto'}</span>
                              {' '}{reference.file}:{reference.line}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {semanticResults && (
                    <pre className={`${SUBTLE_PANEL} mb-3 max-h-48 overflow-auto whitespace-pre-wrap p-3 text-xs text-gray-300`}>{semanticResults}</pre>
                  )}

                  {!astState ? (
                    <EmptyState icon={FileCode} title="Nenhum indice AST disponivel." />
                  ) : (
                    <div className="space-y-4">
                      {Object.entries(astState).map(([filename, symbols]) => (
                        <article key={filename} className={`${SUBTLE_PANEL} p-3`}>
                          <h4 className="mb-3 break-all text-sm font-semibold text-gray-100">{filename}</h4>
                          <div className="space-y-2 border-l border-white/10 pl-3 text-xs">
                            {symbols.classes?.map((symbol, index) => (
                              <button key={`class-${index}`} onClick={() => { setCodeSearch(symbol.name); findReferences(symbol.name); }} className="block text-left text-sky-200 hover:text-sky-100">
                                class <span className="font-semibold">{symbol.name}</span>
                                {symbol.line && <span className="text-gray-600"> :{symbol.line}</span>}
                              </button>
                            ))}
                            {symbols.functions?.map((symbol, index) => (
                              <button key={`function-${index}`} onClick={() => { setCodeSearch(symbol.name); findReferences(symbol.name); }} className="block text-left text-violet-200 hover:text-violet-100">
                                def <span className="font-semibold">{symbol.name}</span>()
                                {symbol.line && <span className="text-gray-600"> :{symbol.line}</span>}
                              </button>
                            ))}
                            {!symbols.classes?.length && !symbols.functions?.length && (
                              <div className="text-gray-600">Sem classes ou funcoes declaradas</div>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </ViewFrame>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

function MemoryColumn({
  title,
  icon: Icon,
  tone,
  count,
  empty,
  children,
}: {
  title: string;
  icon: LucideIcon;
  tone: string;
  count: string;
  empty: string;
  children: React.ReactNode;
}) {
  const hasChildren = React.Children.count(children) > 0;

  return (
    <section className={`${PANEL} flex min-h-0 flex-col overflow-hidden`}>
      <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3">
        <Icon className={`h-4 w-4 ${tone}`} />
        <h3 className="flex-1 text-sm font-semibold text-gray-100">{title}</h3>
        <span className="text-xs text-gray-500">{count}</span>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {hasChildren ? children : <EmptyState icon={Icon} title={empty} />}
      </div>
    </section>
  );
}
