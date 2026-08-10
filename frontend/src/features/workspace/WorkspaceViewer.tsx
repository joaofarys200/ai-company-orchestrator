import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BookOpen,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Code2,
  FileCode,
  FolderOpen,
  GitPullRequest,
  KanbanSquare,
  LayoutDashboard,
  Layers,
  MessageSquare,
  MoreHorizontal,
  Play,
  Plus,
  RefreshCw,
  Rocket,
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
import { Modal } from '../../components/Modal';

interface WorkspaceViewerProps {
  onClose?: () => void;
}

type TabType = 'kanban' | 'debates' | 'files' | 'preview' | 'terminal' | 'coding' | 'knowledge' | 'rules' | 'planner';

const PANEL = 'bg-[#0f1b20]/80 border border-[#a1bebf]/15 rounded-md shadow-[0_16px_50px_rgba(0,0,0,0.28)]';
const SUBTLE_PANEL = 'bg-[#a1bebf]/[0.045] border border-[#a1bebf]/15 rounded-md';
const BUTTON_BASE = 'inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-45';
const ICON_BUTTON = 'inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/8 bg-white/[0.04] text-gray-400 transition-all hover:border-white/16 hover:bg-white/[0.08] hover:text-white';

const KANBAN_COLUMNS = [
  { id: 'backlog', label: 'Backlog', tone: 'border-gray-500/30', dot: 'bg-gray-400' },
  { id: 'progress', label: 'Em execucao', tone: 'border-sky-400/30', dot: 'bg-sky-400' },
  { id: 'review', label: 'Revisao QA', tone: 'border-amber-400/30', dot: 'bg-amber-400' },
  { id: 'done', label: 'Concluido', tone: 'border-emerald-400/30', dot: 'bg-emerald-400' },
] as const;

type WorkspaceSection = 'overview' | 'code' | 'run' | 'missions' | 'more';

const PRIMARY_SECTIONS: Array<{ id: WorkspaceSection; label: string; icon: LucideIcon; defaultTab: TabType }> = [
  { id: 'overview', label: 'Visão geral', icon: LayoutDashboard, defaultTab: 'kanban' },
  { id: 'code', label: 'Código', icon: Code2, defaultTab: 'files' },
  { id: 'run', label: 'Executar', icon: Rocket, defaultTab: 'preview' },
  { id: 'missions', label: 'Missões', icon: Activity, defaultTab: 'planner' },
  { id: 'more', label: 'Mais', icon: MoreHorizontal, defaultTab: 'debates' },
];

const SECONDARY_TABS: Record<WorkspaceSection, Array<{ id: TabType; label: string; icon: LucideIcon }>> = {
  overview: [],
  code: [
    { id: 'files', label: 'Ficheiros', icon: FileCode },
    { id: 'coding', label: 'Alteração', icon: GitPullRequest },
  ],
  run: [
    { id: 'preview', label: 'Preview', icon: Play },
    { id: 'terminal', label: 'Consola', icon: Terminal },
  ],
  missions: [],
  more: [
    { id: 'debates', label: 'Debates', icon: MessageSquare },
    { id: 'knowledge', label: 'Conhecimento', icon: BookOpen },
    { id: 'rules', label: 'Memória', icon: Brain },
  ],
};

const TECHNICAL_PROJECT_PATTERN = /(benchmark|fixture|flight-recorder|health-attempt|mission-validation|validation-|stress|scratch|diagnostic)/i;
const CodeEditor = React.lazy(() => import('./CodeEditor').then((module) => ({ default: module.CodeEditor })));

const normalizePlannerStatus = (status: string | undefined) => String(status || '').toUpperCase();

function plannerStatusLabel(status: string | undefined) {
  const normalized = normalizePlannerStatus(status);
  if (normalized === 'DONE') return 'Concluído';
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
      article: 'border-cyan-300/35 bg-cyan-300/10',
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

function codingStatusMeta(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === 'PROPOSED') return { label: 'Pronta para rever', tone: 'bg-cyan-300/10 text-cyan-100' };
  if (normalized === 'SUCCEEDED') return { label: 'Validada', tone: 'bg-emerald-300/10 text-emerald-200' };
  if (normalized === 'ROLLED_BACK') return { label: 'Revertida', tone: 'bg-gray-300/10 text-gray-300' };
  if (normalized === 'ERROR_ROLLED_BACK') return { label: 'Erro revertido', tone: 'bg-amber-300/10 text-amber-200' };
  if (normalized === 'VALIDATION_FAILED') return { label: 'Validação falhou', tone: 'bg-rose-300/10 text-rose-200' };
  if (normalized === 'ROLLBACK_FAILED') return { label: 'Falha ao reverter', tone: 'bg-rose-300/10 text-rose-200' };
  if (normalized === 'ERROR') return { label: 'Erro', tone: 'bg-rose-300/10 text-rose-200' };
  return { label: status.replaceAll('_', ' ').toLowerCase(), tone: 'bg-white/[0.06] text-gray-300' };
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
      initial={{ opacity: 0, x: 14, filter: 'blur(4px)' }}
      animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
      exit={{ opacity: 0, x: -10, filter: 'blur(4px)' }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={`workspace-view h-full overflow-hidden ${className}`}
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
    projectFileSaveState,
    isSavingProjectFile,
    saveProjectFile,
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
    sandboxStatus,
    projectReferences,
    semanticResults,
    isIndexingProject,
    openProject,
    createProject,
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
  const [previewKey, setPreviewKey] = useState(0);
  const [noteSearch, setNoteSearch] = useState('');
  const [selectedNoteName, setSelectedNoteName] = useState('');
  const [editNoteContent, setEditNoteContent] = useState('');
  const [codeSearch, setCodeSearch] = useState('');
  const [codingObjective, setCodingObjective] = useState('');
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [showTechnicalProjects, setShowTechnicalProjects] = useState(false);
  const [fileSelectionProjectId, setFileSelectionProjectId] = useState('');

  // Project Creation Modal State
  const [createProjectModalOpen, setCreateProjectModalOpen] = useState(false);
  const [newProjectId, setNewProjectId] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectTemplate, setNewProjectTemplate] = useState('web-app');

  // Confirmation Modal State
  const [confirmRollbackOpen, setConfirmRollbackOpen] = useState(false);

  const filenames = useMemo(() => Object.keys(projectFiles), [projectFiles]);
  const filenamesKey = filenames.join('|');
  const filteredNotes = notes.filter((note) => note.toLowerCase().includes(noteSearch.toLowerCase()));
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
        ? 'Concluído'
        : 'Sem passos';
  const workItems = useMemo(
    () => KANBAN_COLUMNS.flatMap((column) => (kanban[column.id] ?? []).map((card) => ({ ...card, column }))),
    [kanban],
  );
  const activeSection: WorkspaceSection = activeTab === 'kanban'
    ? 'overview'
    : activeTab === 'files' || activeTab === 'coding'
      ? 'code'
      : activeTab === 'preview' || activeTab === 'terminal'
        ? 'run'
          : activeTab === 'planner'
            ? 'missions'
            : 'more';
  const projectFilter = projectSearch.trim().toLowerCase();
  const filteredProjects = projects.filter((project) => (
    `${project.project_name} ${project.project_id}`.toLowerCase().includes(projectFilter)
  ));
  const regularProjects = filteredProjects.filter((project) => !TECHNICAL_PROJECT_PATTERN.test(`${project.project_name} ${project.project_id}`));
  const technicalProjects = filteredProjects.filter((project) => TECHNICAL_PROJECT_PATTERN.test(`${project.project_name} ${project.project_id}`));
  const codingStatus = codingSession ? codingStatusMeta(codingSession.status) : null;

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
    const currentProjectId = projectContext?.project_id ?? '';
    if (!firstFile) {
      if (selectedFile) {
        const timeoutId = window.setTimeout(() => setSelectedFile(''), 0);
        return () => window.clearTimeout(timeoutId);
      }
      return;
    }

    if (currentProjectId && currentProjectId !== fileSelectionProjectId) {
      const timeoutId = window.setTimeout(() => {
        setSelectedFile(firstFile);
        setFileSelectionProjectId(currentProjectId);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    if (selectedFile && !projectFiles[selectedFile]) {
      const timeoutId = window.setTimeout(() => setSelectedFile(firstFile), 0);
      return () => window.clearTimeout(timeoutId);
    }
  }, [fileSelectionProjectId, filenames, filenamesKey, projectContext?.project_id, projectFiles, selectedFile]);

  const activateTab = (tab: TabType) => {
    setActiveTab(tab);
    if (tab === 'knowledge') getNotes();
    if (tab === 'files') {
      getAstState();
    }
  };

  const activateSection = (section: WorkspaceSection) => {
    setProjectPickerOpen(false);
    const availableTabs = SECONDARY_TABS[section].map((tab) => tab.id);
    if (availableTabs.includes(activeTab)) return;
    const target = PRIMARY_SECTIONS.find((item) => item.id === section)?.defaultTab ?? 'kanban';
    activateTab(target);
  };

  const handleProjectSelect = (projectId: string) => {
    openProject(projectId);
    setProjectPickerOpen(false);
    setProjectSearch('');
  };

  const handleFileSelect = useCallback((filename: string) => {
    setSelectedFile(filename);
  }, []);

  const renderCodeInsights = () => (
    <aside className={`${PANEL} flex min-h-0 w-full flex-col overflow-hidden xl:w-80 xl:shrink-0`}>
      <div className="flex items-center gap-2 border-b border-white/8 px-3 py-3">
        <Search className="h-4 w-4 text-violet-300" />
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-100">Símbolos e referências</h3>
        <button
          onClick={reindexProject}
          disabled={!projectContext || isIndexingProject}
          className={ICON_BUTTON}
          title="Reindexar projeto"
        >
          <RefreshCw className={`h-4 w-4 ${isIndexingProject ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="border-b border-white/8 p-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
          <input
            value={codeSearch}
            onChange={(event) => setCodeSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') findReferences(codeSearch);
            }}
            placeholder="Procurar símbolo"
            className="h-9 w-full rounded-md border border-white/8 bg-black/25 pl-9 pr-20 text-xs text-gray-200 outline-none focus:border-cyan-300/30"
          />
          <div className="absolute right-1 top-1 flex gap-1">
            <button
              onClick={() => findReferences(codeSearch)}
              className="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-white/[0.06] hover:text-cyan-200"
              title="Localizar referências"
            >
              <FileCode className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => semanticSearch(codeSearch)}
              className="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-white/[0.06] hover:text-violet-200"
              title="Pesquisa semântica"
            >
              <Brain className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-gray-600">
          <span>{String(projectContext?.ast_index.status ?? 'Sem índice')}</span>
          <span>{projectContext?.last_indexed_at ? new Date(projectContext.last_indexed_at).toLocaleDateString('pt-PT') : 'Nunca indexado'}</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {projectReferences && (
          <section className="mb-3 border-b border-white/8 pb-3 text-xs">
            <h4 className="mb-2 font-semibold text-gray-200">Referências de {projectReferences.symbol}</h4>
            {[...projectReferences.definitions, ...projectReferences.references].length === 0 ? (
              <p className="text-gray-600">Nenhuma ocorrência.</p>
            ) : (
              <div className="space-y-1">
                {[...projectReferences.definitions, ...projectReferences.references].map((reference, index) => (
                  <button
                    key={`${reference.file}-${reference.line}-${index}`}
                    onClick={() => handleFileSelect(reference.file)}
                    className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-gray-400 hover:bg-white/[0.04] hover:text-cyan-100"
                    title={reference.text}
                  >
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${reference.confirmed ? 'bg-emerald-300' : 'bg-amber-300'}`} />
                    <span className="truncate">{reference.file}:{reference.line}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {semanticResults && (
          <pre className="mb-3 max-h-32 overflow-auto whitespace-pre-wrap border-b border-white/8 pb-3 text-xs text-gray-400">{semanticResults}</pre>
        )}

        {!astState ? (
          <EmptyState icon={FileCode} title="Reindexe o projeto para ver símbolos." />
        ) : (
          <div className="space-y-3">
            {Object.entries(astState).map(([filename, symbols]) => (
              <section key={filename}>
                <button
                  onClick={() => handleFileSelect(filename)}
                  className="mb-1.5 block w-full truncate text-left text-xs font-semibold text-gray-300 hover:text-cyan-100"
                  title={filename}
                >
                  {filename}
                </button>
                <div className="space-y-1 border-l border-white/10 pl-2.5 text-xs">
                  {symbols.classes?.map((symbol, index) => (
                    <button
                      key={`class-${index}`}
                      onClick={() => {
                        setCodeSearch(symbol.name);
                        findReferences(symbol.name);
                      }}
                      className="block max-w-full truncate text-left text-sky-200/80 hover:text-sky-100"
                    >
                      class {symbol.name}
                    </button>
                  ))}
                  {symbols.functions?.map((symbol, index) => (
                    <button
                      key={`function-${index}`}
                      onClick={() => {
                        setCodeSearch(symbol.name);
                        findReferences(symbol.name);
                      }}
                      className="block max-w-full truncate text-left text-violet-200/80 hover:text-violet-100"
                    >
                      {symbol.name}()
                    </button>
                  ))}
                  {!symbols.classes?.length && !symbols.functions?.length && (
                    <p className="text-gray-700">Sem símbolos</p>
                  )}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </aside>
  );

  const renderHeader = () => {
    const secondaryTabs = SECONDARY_TABS[activeSection];

    return (
      <header className="workspace-header border-b border-white/8 bg-[#091217]/95">
        <div className="flex min-h-14 items-center gap-2 px-3">
          <div className="relative shrink-0">
            <button
              onClick={() => setProjectPickerOpen((current) => !current)}
              className={`flex h-9 w-44 items-center gap-2 rounded-md border px-3 text-left text-xs font-semibold transition-colors sm:w-52 ${
                projectPickerOpen
                  ? 'border-cyan-300/30 bg-cyan-300/8 text-white'
                  : 'border-white/8 bg-[#070a10] text-gray-200 hover:border-white/15'
              }`}
              aria-expanded={projectPickerOpen}
            >
              <FolderOpen className="h-4 w-4 shrink-0 text-cyan-300" />
              <span className="min-w-0 flex-1 truncate">{projectContext?.project_name || 'Selecionar projeto'}</span>
              <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-gray-500 transition-transform ${projectPickerOpen ? 'rotate-180' : ''}`} />
            </button>

            {projectPickerOpen && (
              <>
                <button
                  type="button"
                  aria-label="Fechar seletor de projetos"
                  onClick={() => setProjectPickerOpen(false)}
                  className="fixed inset-0 z-20 cursor-default"
                />
                <div className="absolute left-0 top-11 z-30 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-md border border-white/10 bg-[#0a0d14] shadow-2xl">
                <div className="border-b border-white/8 p-2 space-y-2">
                  <button
                    onClick={() => {
                      setCreateProjectModalOpen(true);
                      setProjectPickerOpen(false);
                    }}
                    className="flex w-full items-center justify-center gap-2 rounded-md border border-cyan-300/30 bg-cyan-300/10 py-1.5 text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-300/20"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Criar novo projeto</span>
                  </button>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
                    <input
                      autoFocus
                      value={projectSearch}
                      onChange={(event) => setProjectSearch(event.target.value)}
                      placeholder="Pesquisar projetos"
                      className="h-9 w-full rounded-md border border-white/8 bg-black/25 pl-9 pr-3 text-xs text-gray-200 outline-none focus:border-cyan-300/30"
                    />
                  </div>
                </div>
                <div className="max-h-80 overflow-y-auto p-1.5">
                  {regularProjects.map((project) => (
                    <button
                      key={project.project_id}
                      onClick={() => handleProjectSelect(project.project_id)}
                      className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                        project.project_id === projectContext?.project_id
                          ? 'bg-cyan-300/10 text-cyan-100'
                          : 'text-gray-300 hover:bg-white/[0.05]'
                      }`}
                    >
                      <FolderOpen className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{project.project_name}</span>
                      {project.project_id === projectContext?.project_id && <Check className="ml-auto h-3.5 w-3.5" />}
                    </button>
                  ))}

                  {regularProjects.length === 0 && !showTechnicalProjects && (
                    <p className="px-3 py-4 text-center text-xs text-gray-600">Nenhum projeto encontrado.</p>
                  )}

                  {technicalProjects.length > 0 && (
                    <>
                      <button
                        onClick={() => setShowTechnicalProjects((current) => !current)}
                        className="mt-1 flex w-full items-center gap-2 border-t border-white/8 px-3 py-2.5 text-left text-[11px] font-medium text-gray-500 hover:text-gray-300"
                      >
                        <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showTechnicalProjects ? 'rotate-90' : ''}`} />
                        <span>{showTechnicalProjects ? 'Ocultar' : 'Mostrar'} {technicalProjects.length} projetos técnicos</span>
                      </button>
                      {showTechnicalProjects && technicalProjects.map((project) => (
                        <button
                          key={project.project_id}
                          onClick={() => handleProjectSelect(project.project_id)}
                          className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                            project.project_id === projectContext?.project_id
                              ? 'bg-cyan-300/10 text-cyan-100'
                              : 'text-gray-500 hover:bg-white/[0.05] hover:text-gray-300'
                          }`}
                        >
                          <FolderOpen className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{project.project_name}</span>
                        </button>
                      ))}
                    </>
                  )}
                </div>
                </div>
              </>
            )}
          </div>

          <nav className="workspace-primary-nav flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
            {PRIMARY_SECTIONS.map((section) => {
              const Icon = section.icon;
              const active = activeSection === section.id;
              return (
                <button
                  key={section.id}
                  onClick={() => activateSection(section.id)}
                  className={`workspace-primary-tab flex h-9 shrink-0 items-center gap-2 rounded-md border px-3 text-xs font-semibold transition-all ${
                    active
                      ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100'
                      : 'border-transparent text-gray-500 hover:bg-white/[0.04] hover:text-gray-200'
                  }`}
                  data-active={active}
                >
                  <Icon className="h-4 w-4" />
                  <span>{section.label}</span>
                </button>
              );
            })}
          </nav>

          {sandboxStatus && !sandboxStatus.is_docker && (
            <span
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-amber-400/25 bg-amber-400/10 px-2.5 py-1 text-[11px] font-medium text-amber-200"
              title="Contentor Docker indisponível. O preview da sandbox está a rodar no servidor local de fallback."
            >
              <Shield className="h-3.5 w-3.5 text-amber-400" />
              <span className="hidden md:inline">Fallback Local (Sem Docker)</span>
            </span>
          )}

          {onClose && (
            <button onClick={onClose} className={ICON_BUTTON} title="Fechar painel">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {secondaryTabs.length > 0 && (
          <nav className="workspace-secondary-nav flex h-10 items-center gap-1 overflow-x-auto border-t border-white/[0.05] px-3 sm:pl-[13.75rem]">
            {secondaryTabs.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => activateTab(tab.id)}
                  className={`workspace-secondary-tab flex h-8 items-center gap-2 rounded-md px-3 text-xs font-medium transition-colors ${
                    active ? 'bg-white/[0.07] text-white' : 'text-gray-500 hover:text-gray-200'
                  }`}
                  data-active={active}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        )}
      </header>
    );
  };

  return (
    <div className="workspace-shell flex h-full flex-col overflow-hidden rounded-md border border-white/8 bg-[#091217]/85 backdrop-blur-xl">
      {renderHeader()}

      <div className="min-h-0 flex-1 overflow-hidden p-3">
        <AnimatePresence mode="wait">
          {activeTab === 'kanban' && (
            <ViewFrame key="kanban" className="overflow-y-auto">
              <div className="mx-auto grid w-full max-w-[1500px] gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
                <section className={`${PANEL} min-w-0 overflow-hidden`}>
                  <div className="flex flex-col gap-4 border-b border-white/8 p-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <FolderOpen className="h-4 w-4 text-cyan-300" />
                        <h2 className="truncate text-base font-semibold text-white">
                          {projectContext?.project_name || 'Nenhum projeto selecionado'}
                        </h2>
                      </div>
                      <p className="truncate text-xs text-gray-500">
                        {projectContext
                          ? [...projectContext.stack, ...projectContext.frameworks].join(' · ') || projectContext.root_path
                          : 'Selecione um projeto para começar.'}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => activateTab('files')}
                        disabled={!projectContext}
                        className={`${BUTTON_BASE} border-white/8 bg-white/[0.04] text-gray-300 hover:bg-white/[0.08] hover:text-white`}
                      >
                        <Code2 className="h-4 w-4" />
                        <span>Abrir código</span>
                      </button>
                      <button
                        onClick={() => activateTab('preview')}
                        disabled={!projectContext}
                        className={`${BUTTON_BASE} border-cyan-300/25 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/15`}
                      >
                        <Play className="h-4 w-4" />
                        <span>Preview</span>
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 border-b border-white/8 sm:grid-cols-4">
                    {KANBAN_COLUMNS.map((column, index) => (
                      <div
                        key={column.id}
                        className={`flex items-center gap-3 px-4 py-3 ${index > 0 ? 'border-l border-white/8' : ''}`}
                      >
                        <span className={`h-2 w-2 shrink-0 rounded-full ${column.dot}`} />
                        <div className="min-w-0">
                          <p className="truncate text-[11px] text-gray-500">{column.label}</p>
                          <p className="text-base font-semibold text-gray-100">{kanban[column.id]?.length ?? 0}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-100">Trabalho atual</h3>
                      <p className="mt-0.5 text-xs text-gray-600">{workItems.length} tarefas no projeto</p>
                    </div>
                    <KanbanSquare className="h-4 w-4 text-gray-600" />
                  </div>

                  {workItems.length === 0 ? (
                    <EmptyState icon={KanbanSquare} title="Ainda não existem tarefas neste projeto." />
                  ) : (
                    <div className="divide-y divide-white/[0.06]">
                      {workItems.map((card) => (
                        <article key={`${card.column.id}-${card.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-white/[0.025]">
                          <span className={`h-2 w-2 shrink-0 rounded-full ${card.column.dot}`} />
                          <p className="min-w-0 flex-1 truncate text-sm font-medium text-gray-200">{card.title}</p>
                          <span className="hidden text-xs text-gray-600 sm:block">{card.agent}</span>
                          <span className="rounded bg-white/[0.05] px-2 py-1 text-[10px] text-gray-400">{card.column.label}</span>
                        </article>
                      ))}
                    </div>
                  )}
                </section>

                <aside className="space-y-3">
                  <section className={`${PANEL} overflow-hidden`}>
                    <div className="border-b border-white/8 px-4 py-3">
                      <h3 className="text-sm font-semibold text-gray-100">Projeto</h3>
                    </div>
                    <dl className="divide-y divide-white/[0.06] text-xs">
                      <div className="flex items-start justify-between gap-3 px-4 py-3">
                        <dt className="text-gray-500">Ficheiros</dt>
                        <dd className="font-medium text-gray-200">{filenames.length}</dd>
                      </div>
                      <div className="flex items-start justify-between gap-3 px-4 py-3">
                        <dt className="text-gray-500">Entradas</dt>
                        <dd className="max-w-44 text-right text-gray-300">
                          {projectContext?.entrypoints.join(', ') || 'Não detetadas'}
                        </dd>
                      </div>
                      <div className="flex items-start justify-between gap-3 px-4 py-3">
                        <dt className="text-gray-500">Índice</dt>
                        <dd className="text-gray-300">{String(projectContext?.ast_index.status ?? 'indisponível')}</dd>
                      </div>
                      <div className="flex items-start justify-between gap-3 px-4 py-3">
                        <dt className="text-gray-500">Validações</dt>
                        <dd className="font-medium text-gray-200">{projectContext?.suggested_commands.length ?? 0}</dd>
                      </div>
                    </dl>
                  </section>

                  <button
                    onClick={() => activateTab('coding')}
                    disabled={!projectContext}
                    className="flex w-full items-center gap-3 rounded-md border border-white/8 bg-white/[0.025] p-4 text-left transition-colors hover:border-cyan-300/20 hover:bg-cyan-300/[0.04] disabled:opacity-45"
                  >
                    <GitPullRequest className="h-4 w-4 text-cyan-300" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-gray-200">Nova alteração</span>
                      <span className="mt-0.5 block text-xs text-gray-600">Planear, rever e validar</span>
                    </span>
                    <ChevronRight className="h-4 w-4 text-gray-600" />
                  </button>
                </aside>
              </div>
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
                  <div className="flex flex-col items-center justify-center p-8 text-center">
                    <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-500/10 text-cyan-300">
                      <MessageSquare className="h-6 w-6" />
                    </div>
                    <h4 className="text-sm font-semibold text-gray-200">Canal de Debates Multi-Agente</h4>
                    <p className="mt-1 max-w-md text-xs leading-relaxed text-gray-400">
                      Este canal regista a comunicação direta entre subagentes de desenvolvimento (Devon, Quinn, Swarm, etc.) quando discutem decisões de arquitetura, validações ou planos de execução de missões.
                    </p>
                    <div className="mt-4 space-y-1 rounded-md border border-white/10 bg-white/[0.03] p-3 text-left text-xs text-gray-400">
                      <p className="font-medium text-gray-300">💡 Como acionar um debate:</p>
                      <p>• Executa uma missão complexa que exija colaboração entre múltiplos especialistas.</p>
                      <p>• Escreve no chat: <code className="font-mono text-cyan-300">"Pede a Quinn e Devon para debaterem o plano de testes"</code>.</p>
                    </div>
                  </div>
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
            <ViewFrame key="files">
              {projectContext ? (
                <React.Suspense fallback={<EmptyState icon={Code2} title="A abrir o editor..." />}>
                  <CodeEditor
                    key={projectContext.project_id}
                    projectId={projectContext.project_id}
                    projectName={projectContext.project_name}
                    rootPath={projectContext.root_path}
                    files={projectFiles}
                    selectedFile={selectedFile}
                    onSelectFile={handleFileSelect}
                    onSaveFile={saveProjectFile}
                    onOpenChanges={() => activateTab('coding')}
                    onOpenPreview={() => activateTab('preview')}
                    isSaving={isSavingProjectFile}
                    saveState={projectFileSaveState}
                    insights={renderCodeInsights()}
                  />
                </React.Suspense>
              ) : (
                <EmptyState icon={Code2} title="Selecione um projeto para abrir o editor." />
              )}
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
              <div className="relative min-h-0 flex-1 bg-white">
                {previewUrl && previewUrl !== 'about:blank' ? (
                  <iframe key={previewKey} src={previewUrl} className="h-full w-full border-none" title="Project Preview" />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#070a10] p-6 text-center text-gray-400">
                    <Rocket className="h-10 w-10 text-cyan-300/60" />
                    <h4 className="text-sm font-semibold text-white">Preview Não Iniciado</h4>
                    <p className="max-w-sm text-xs text-gray-500">Inicie a execução do projeto para visualizar a aplicação em tempo real.</p>
                    <button
                      onClick={runProject}
                      disabled={isProjectRunning || !projectContext}
                      className={`${BUTTON_BASE} border-emerald-400/30 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/20`}
                    >
                      <Play className="h-4 w-4" />
                      <span>Iniciar Aplicação</span>
                    </button>
                  </div>
                )}
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
                  <h3 className="flex-1 text-sm font-semibold text-gray-100">Alteração assistida</h3>
                  {codingStatus && (
                    <span className={`rounded px-2 py-1 text-[10px] font-semibold ${codingStatus.tone}`}>{codingStatus.label}</span>
                  )}
                </div>
                <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                  <label htmlFor="coding-objective" className="block text-xs font-medium text-gray-400">Objetivo</label>
                  <textarea
                    id="coding-objective"
                    value={codingObjective}
                    onChange={(event) => setCodingObjective(event.target.value)}
                    placeholder="Descreva a alteração pretendida"
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
                      onClick={() => setConfirmRollbackOpen(true)}
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
                        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-white/8 bg-black/30 p-3 font-mono text-xs leading-relaxed text-gray-300">{change.unified_diff}</pre>
                        <details className="mt-2 rounded-md border border-white/8 bg-white/[0.02]">
                          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-gray-400 hover:text-gray-200">Comparar versões</summary>
                          <div className="grid gap-2 border-t border-white/8 p-2 xl:grid-cols-2">
                            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-rose-300/10 bg-rose-300/[0.04] p-3 text-xs text-rose-100/75">{change.previous_excerpt || '(novo ficheiro)'}</pre>
                            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-emerald-300/10 bg-emerald-300/[0.04] p-3 text-xs text-emerald-100/75">{change.proposed_excerpt}</pre>
                          </div>
                        </details>
                      </article>
                    ))}

                    {codingSession.validation_results.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-sm font-semibold text-gray-100">Resultados de validacao</h4>
                        <div className="space-y-2">
                          {codingSession.validation_results.map((result) => (
                            <div key={result.command} className={`${SUBTLE_PANEL} p-3 text-xs`}>
                              <div className="flex items-center gap-2">
                                {result.exit_code === 0
                                  ? <Check className="h-4 w-4 text-emerald-300" />
                                  : <CircleAlert className="h-4 w-4 text-rose-300" />}
                                <code className="min-w-0 flex-1 break-all text-gray-200">{result.command}</code>
                                <span className={result.exit_code === 0 ? 'text-emerald-300' : 'text-rose-300'}>exit {result.exit_code}</span>
                                <span className="text-gray-600">{result.duration_seconds}s</span>
                              </div>
                              {(result.stdout || result.stderr) && (
                                <details className="mt-2 border-t border-white/[0.06] pt-2">
                                  <summary className="cursor-pointer text-gray-500 hover:text-gray-300">Ver output</summary>
                                  <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap bg-black/20 p-2 text-gray-500">{result.stderr || result.stdout}</pre>
                                </details>
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
            <ViewFrame key="planner" className="overflow-hidden">
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

              <section className={`${PANEL} hidden min-h-0 flex-col overflow-hidden`} aria-hidden="true">
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

      {/* Create Project Modal */}
      <Modal
        isOpen={createProjectModalOpen}
        onClose={() => setCreateProjectModalOpen(false)}
        title="Criar Novo Projeto"
        footer={(
          <>
            <button onClick={() => setCreateProjectModalOpen(false)} className={`${BUTTON_BASE} border-white/10 text-gray-400`}>Cancelar</button>
            <button
              onClick={() => {
                if (newProjectId.trim()) {
                  createProject(newProjectId.trim(), newProjectName.trim(), newProjectTemplate);
                  setCreateProjectModalOpen(false);
                  setNewProjectId('');
                  setNewProjectName('');
                }
              }}
              disabled={!newProjectId.trim()}
              className={`${BUTTON_BASE} border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/20`}
            >
              Criar Projeto
            </button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">ID do projeto (diretório) *</label>
            <input
              value={newProjectId}
              onChange={(e) => setNewProjectId(e.target.value)}
              placeholder="ex: meu-novo-app"
              className="h-9 w-full rounded-md border border-white/10 bg-black/40 px-3 text-xs text-gray-200 outline-none focus:border-cyan-300/40"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Nome de exibição</label>
            <input
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="ex: Meu Novo App"
              className="h-9 w-full rounded-md border border-white/10 bg-black/40 px-3 text-xs text-gray-200 outline-none focus:border-cyan-300/40"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Template inicial</label>
            <select
              value={newProjectTemplate}
              onChange={(e) => setNewProjectTemplate(e.target.value)}
              className="h-9 w-full rounded-md border border-white/10 bg-[#070a10] px-3 text-xs text-gray-200 outline-none focus:border-cyan-300/40"
            >
              <option value="web-app">Web App (HTML/CSS/JS + package.json)</option>
              <option value="blank">Projeto Limpo (README.md)</option>
            </select>
          </div>
        </div>
      </Modal>

      {/* Confirm Rollback Modal */}
      <Modal
        isOpen={confirmRollbackOpen}
        onClose={() => setConfirmRollbackOpen(false)}
        title="Confirmar Reversão"
        footer={(
          <>
            <button onClick={() => setConfirmRollbackOpen(false)} className={`${BUTTON_BASE} border-white/10 text-gray-400`}>Cancelar</button>
            <button
              onClick={() => {
                rollbackCodingSession();
                setConfirmRollbackOpen(false);
              }}
              className={`${BUTTON_BASE} border-rose-300/30 bg-rose-300/10 text-rose-100 hover:bg-rose-300/20`}
            >
              Reverter Alterações
            </button>
          </>
        )}
      >
        <p className="text-xs text-gray-300">Tem a certeza que pretende reverter apenas os ficheiros alterados por esta sessão de código?</p>
      </Modal>
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
