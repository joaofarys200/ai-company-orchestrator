import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  AlertCircle,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Code2,
  Compass,
  Cpu,
  FileCode,
  FolderOpen,
  Database,
  GitPullRequest,
  GraduationCap,
  History,
  KanbanSquare,
  Loader2,
  MessageSquare,
  Network,
  PanelBottomClose,
  PanelBottomOpen,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  Square,
  Terminal,
  Trash2,
  Undo2,
  WandSparkles,
  PanelRightClose,
  PanelRightOpen,
  Globe,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';
import { MissionPlanner } from '../planner';
import { MissionControlCenter, MissionListView } from '../missions';
import { StudyContainer, type StudyTab } from '../study';
import { SentinelDashboard } from '../sentinel/SentinelDashboard';
import { Modal } from '../../components/Modal';
import { ResizableHandle, usePersistedPaneSize } from '../../components/ui';
import { ProjectArchitectureView } from './ProjectArchitectureView';
import { ObsidianVaultView } from './ObsidianVaultView';
import { ProjectsLandingView } from './ProjectsLandingView';
import { recordRecentProject } from './projectStorage';
import { SpatialOverviewPanel } from '../board/SpatialOverviewPanel';
import type { SpatialBoardDomain } from '../board/boardBuilders';

interface WorkspaceViewerProps {
  onClose?: () => void;
}

type TabType = 'kanban' | 'debates' | 'files' | 'architecture' | 'preview' | 'terminal' | 'coding' | 'knowledge' | 'rules' | 'planner' | 'mission_control' | 'lectures' | 'study' | 'sentinel';

const PANEL = 'bg-[#0b111a]/95 border border-slate-800/90 rounded-lg shadow-[0_12px_36px_rgba(0,0,0,0.35)]';
const SUBTLE_PANEL = 'bg-[#0f1722] border border-slate-800/80 rounded-lg';
const BUTTON_BASE = 'inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-45 cursor-pointer';
const ICON_BUTTON = 'inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-800 bg-[#0f1722] text-slate-400 transition-all hover:border-slate-700 hover:bg-slate-800/70 hover:text-slate-100 cursor-pointer';

const KANBAN_COLUMNS = [
  { id: 'backlog', label: 'Backlog', tone: 'border-slate-600/40', dot: 'bg-slate-400' },
  { id: 'progress', label: 'Em execucao', tone: 'border-sky-400/35', dot: 'bg-sky-400' },
  { id: 'review', label: 'Revisao QA', tone: 'border-amber-400/35', dot: 'bg-amber-400' },
  { id: 'done', label: 'Concluido', tone: 'border-emerald-400/35', dot: 'bg-emerald-400' },
] as const;

const TECHNICAL_PROJECT_PATTERN = /(benchmark|fixture|flight-recorder|health-attempt|mission-validation|validation-|stress|scratch|diagnostic)/i;
const CodeEditor = React.lazy(() => import('./CodeEditor').then((module) => ({ default: module.CodeEditor })));

function codingStatusMeta(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === 'PROPOSED') return { label: 'Pronta para rever', tone: 'bg-cyan-300/10 text-cyan-100' };
  if (normalized === 'SUCCEEDED' || normalized === 'PRODUCT_ACCEPTED') return { label: 'Produto Aceite', tone: 'bg-emerald-300/10 text-emerald-200' };
  if (normalized === 'TECHNICALLY_VALIDATED') return { label: 'Validação Técnica', tone: 'bg-blue-300/10 text-blue-200' };
  if (normalized === 'VISUALLY_VALIDATED') return { label: 'Validação Visual', tone: 'bg-indigo-300/10 text-indigo-200' };
  if (normalized === 'BLOCKED_INTEGRITY_REGRESSION') return { label: 'Regressão Detetada', tone: 'bg-rose-400/20 text-rose-200 border border-rose-500/30' };
  if (normalized === 'ACCEPTANCE_FAILED') return { label: 'Falha de Aceitação', tone: 'bg-rose-300/10 text-rose-200' };
  if (normalized === 'AWAITING_HUMAN_APPROVAL' || normalized === 'HUMAN_REVIEW') return { label: 'Revisão Humana Necessária', tone: 'bg-amber-300/10 text-amber-200 border border-amber-500/30' };
  if (normalized === 'INSUFFICIENT_EVIDENCE') return { label: 'Evidência Insuficiente', tone: 'bg-amber-300/10 text-amber-200' };
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
    astState,
    getAstState,
    projects,
    projectContext,
    sandboxStatus,
    projectReferences,
    semanticResults,
    isIndexingProject,
    listProjects,
    openProject,
    createProject,
    deleteProject,
    createProjectFile,
    renameProjectFile,
    deleteProjectFile,
    reindexProject,
    findReferences,
    semanticSearch,
    codingSession,
    isCodingSessionBusy,
    safetyRefusal,
    clearSafetyRefusal,
    codingSessionError,
    clearCodingSessionError,
    createCodingSession,
    applyCodingSession,
    rollbackCodingSession,
    architectureSnapshot,
    openMission,
    isRecordingLecture,
    startLectureRecording,
    stopLectureRecording,
    studyDocuments,
    activeStudyQuiz,
    studyQuizResult,
    generateStudyQuiz,
    submitStudyQuiz,
    searchStudyRag,
    listStudyDocuments,
    uploadStudyDocument,
    ingestStudyVideoUrl,
    deleteStudyDocument,
    contextualAssist,
    askStudyPaper,
    getStudyDocumentFile,
    generateStudyCornell,
    generateStudySummary,
    synthesizeStudyDocuments,
    saveToStudyVault,
    studyCollections,
    listStudyCollections,
    createStudyCollection,
    linkStudyFolder,
    unlinkStudyFolder,
    syncStudyFolder,
    askStudyCourse,
    retryStudyDocument,
    cancelStudyGeneration,
    getStudyEditorialPlan,
    generateStudyEditorialPlan,
    getGeneratedStudyDocumentStatus,
    generateStudyDocument,
    getGeneratedStudyDocumentFile,
    studyModesApi,
    studyPipelineStage,
    lastStudyDocumentError,
    studyNavigationTarget,
    studyReadingNotes,
    studyHighlights,
    getStudyDocumentDetails,
    addStudyReadingNote,
    addStudyHighlight,
    navigateToStudyTarget,
    updateActiveStudyContext,
    sendDirective,
    chatPanelOpen,
    setChatPanelOpen,
    chatMessages,
    activeBoard,
    openSpatialBoard,
    closeSpatialBoard,
    setActiveDomain: syncGlobalDomain,
    spatialOverviewOpen,
    setSpatialOverviewOpen,
    vaultDiagnostics,
    vaultImprovementQueue,
    noteQualityAudit,
    noteEnrichmentProposal,
    isAuditingNote,
    isEnrichingNote,
    getVaultDiagnostics,
    auditNoteQuality,
    enrichNote,
    rollbackNote,
    pauseQueueWorker,
    resumeQueueWorker,
    startImprovementBatch,
    getQueueStatus,
    sentinelStatus,
    sentinelEvents,
    sentinelActions,
    isSentinelAuditing,
    runSentinelAudit,
  } = useWebSocket();

  const [activeTab, setActiveTab] = useState<TabType>(() => {
    if (activeBoard?.domain === 'study') return 'study';
    if (activeBoard?.domain === 'obsidian') return 'knowledge';
    if (activeBoard?.domain === 'sentinel') return 'sentinel';
    return 'files';
  });
  const [contextAssistantOpen, setContextAssistantOpen] = useState<boolean>(false);
  const [assistantInput, setAssistantInput] = useState<string>('');
  const [assistantWidth, setAssistantWidth] = usePersistedPaneSize('jarvis.assistant.width', 340, 260, 520);
  const [ideDockOpen, setIdeDockOpen] = useState<boolean>(false);
  const [ideDockTab, setIdeDockTab] = useState<'console' | 'preview' | 'problems'>('console');
  const [ideDockHeight, setIdeDockHeight] = usePersistedPaneSize('jarvis.ide.dock.height', 230, 140, 440);
  const [showProjectsLanding, setShowProjectsLanding] = useState<boolean>(false);
  const [obsidianSubTabOverride, setObsidianSubTabOverride] = useState<'vault' | 'graph' | 'rules' | undefined>(undefined);
  const [studyInternalTab, setStudyInternalTab] = useState<StudyTab>('reader');
  const [selectedFile, setSelectedFile] = useState('');
  const [selectedLine, setSelectedLine] = useState<number | undefined>(undefined);
  const [previewKey, setPreviewKey] = useState(0);
  const [viewingMissionControlId, setViewingMissionControlId] = useState<string | null>(null);
  const [selectedNoteName, setSelectedNoteName] = useState('');
  const [codeSearch, setCodeSearch] = useState('');
  const [codingObjective, setCodingObjective] = useState('');
  const [codingObjectiveHistory, setCodingObjectiveHistory] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('jarvis_coding_objectives_history');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return [
      'e porque nao fazer uma varedura ativa da rede?',
      'Adicionar autenticação JWT com rotas protegidas',
      'Implementar pesquisa em tempo real com filtros',
      'Criar dashboard com métricas do sistema',
    ];
  });
  const [showObjectiveHistory, setShowObjectiveHistory] = useState(false);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [showTechnicalProjects, setShowTechnicalProjects] = useState(false);
  const [fileSelectionProjectId, setFileSelectionProjectId] = useState('');

  // Project Creation Modal State
  const [createProjectModalOpen, setCreateProjectModalOpen] = useState(false);
  const [newProjectId, setNewProjectId] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectTemplate, setNewProjectTemplate] = useState('web-app');
  const [projectToDelete, setProjectToDelete] = useState<{ id: string; name: string } | null>(null);

  // Confirmation Modal State
  const [confirmRollbackOpen, setConfirmRollbackOpen] = useState(false);

  // Automatically synchronize study catalogue when entering study workspace
  useEffect(() => {
    if (activeTab === 'study' || activeTab === 'lectures') {
      listStudyDocuments();
    }
    (window as any).__jarvisRefreshStudy = listStudyDocuments;
    (window as any).__jarvisUploadStudy = uploadStudyDocument;
    return () => {
      delete (window as any).__jarvisRefreshStudy;
      delete (window as any).__jarvisUploadStudy;
    };
  }, [activeTab, listStudyDocuments, uploadStudyDocument]);

  useEffect(() => {
    if (!studyNavigationTarget) return;
    setActiveTab('study');
  }, [studyNavigationTarget]);

  const activeDomain: SpatialBoardDomain = useMemo(() => {
    if (activeTab === 'study' || activeTab === 'lectures') return 'study';
    if (activeTab === 'knowledge' || activeTab === 'rules') return 'obsidian';
    if (activeTab === 'sentinel') return 'sentinel';
    return 'project';
  }, [activeTab]);

  useEffect(() => {
    syncGlobalDomain(activeDomain);
  }, [activeDomain, syncGlobalDomain]);

  useEffect(() => {
    if (!activeBoard) return;
    if (activeBoard.domain === 'study' && activeTab !== 'study' && activeTab !== 'lectures') {
      setActiveTab('study');
    } else if (activeBoard.domain === 'obsidian' && activeTab !== 'knowledge' && activeTab !== 'rules') {
      setActiveTab('knowledge');
      getNotes();
      getVaultDiagnostics();
      getQueueStatus();
    } else if (activeBoard.domain === 'sentinel' && activeTab !== 'sentinel') {
      setActiveTab('sentinel');
    } else if (
      activeBoard.domain === 'project' &&
      ['study', 'lectures', 'knowledge', 'rules', 'sentinel'].includes(activeTab)
    ) {
      setActiveTab('files');
      getAstState();
    }
  }, [activeBoard?.domain, getAstState, getNotes, getQueueStatus, getVaultDiagnostics]);

  const handleSwitchUnifiedDomain = useCallback(
    (domain: SpatialBoardDomain) => {
      setProjectPickerOpen(false);
      openSpatialBoard(domain);
      if (domain === 'study') {
        setActiveTab('study');
      } else if (domain === 'obsidian') {
        setActiveTab('knowledge');
        getNotes();
        getVaultDiagnostics();
        getQueueStatus();
      } else if (domain === 'sentinel') {
        setActiveTab('sentinel');
      } else {
        if (['study', 'lectures', 'knowledge', 'rules', 'sentinel'].includes(activeTab)) {
          setActiveTab('files');
        }
        getAstState();
      }
    },
    [activeTab, getAstState, getNotes, getQueueStatus, getVaultDiagnostics, openSpatialBoard]
  );

  const handleSendContextualPrompt = useCallback(
    (rawPrompt?: string) => {
      const prompt = (rawPrompt ?? assistantInput).trim();
      if (!prompt) return;
      const prefix =
        activeDomain === 'project'
          ? `[Contexto Código: Projeto=${projectContext?.project_id || 'default'}${selectedFile ? `, Ficheiro=${selectedFile}` : ''}] `
          : activeDomain === 'obsidian'
          ? `[Contexto Obsidian${selectedNoteName ? `: Nota=${selectedNoteName}` : ''}] `
          : activeDomain === 'sentinel'
          ? `[Contexto Sentinel: Postura=${sentinelStatus?.posture || 'GOOD'}] `
          : `[Contexto Estudo] `;
      sendDirective(`${prefix}${prompt}`);
      if (!rawPrompt) setAssistantInput('');
    },
    [
      activeDomain,
      assistantInput,
      projectContext?.project_id,
      selectedFile,
      selectedNoteName,
      sendDirective,
      sentinelStatus?.posture,
    ]
  );

  const filenames = useMemo(() => Object.keys(projectFiles), [projectFiles]);
  const filenamesKey = filenames.join('|');
  const workItems = useMemo(
    () => KANBAN_COLUMNS.flatMap((column) => (kanban[column.id] ?? []).map((card) => ({ ...card, column }))),
    [kanban],
  );

  const totalAstSymbols = useMemo<number>(() => {
    if (typeof architectureSnapshot?.symbols?.total_count === 'number') {
      return architectureSnapshot.symbols.total_count;
    }
    const candidate = projectContext?.ast_index?.symbol_count;
    if (typeof candidate === 'number') {
      return candidate;
    }
    if (astState) {
      return Object.values(astState).reduce((acc, file) => {
        return acc + (file.classes?.length || 0) + (file.functions?.length || 0);
      }, 0);
    }
    return 0;
  }, [architectureSnapshot, projectContext, astState]);
  const normalizeSearch = (text: string) => (
    text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
  );
  const projectFilter = normalizeSearch(projectSearch);
  const filteredProjects = projects.filter((project) => (
    normalizeSearch(`${project.project_name} ${project.project_id}`).includes(projectFilter)
  ));
  const regularProjects = filteredProjects.filter((project) => !TECHNICAL_PROJECT_PATTERN.test(`${project.project_name} ${project.project_id}`));
  const technicalProjects = filteredProjects.filter((project) => TECHNICAL_PROJECT_PATTERN.test(`${project.project_name} ${project.project_id}`));
  const codingStatus = codingSession ? codingStatusMeta(codingSession.status) : null;

  useEffect(() => {
    if (notes.length === 0) {
      getNotes();
    }
  }, [notes.length, getNotes]);

  useEffect(() => {
    listProjects();
  }, [listProjects]);

  useEffect(() => {
    listStudyDocuments();
  }, [listStudyDocuments]);

  useEffect(() => {
    if (activeTab === 'study' || activeTab === 'lectures') {
      listStudyDocuments();
    }
  }, [activeTab, listStudyDocuments]);

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

  const activateTab = useCallback((tab: TabType) => {
    setActiveTab(tab);
    if (tab === 'knowledge') getNotes();
    if (tab === 'files' || tab === 'architecture') {
      getAstState();
    }
  }, [getAstState, getNotes]);

  useEffect(() => {
    const win = window as unknown as Record<string, unknown>;
    win.__setActiveTab = activateTab;
    return () => {
      delete win.__setActiveTab;
    };
  }, [activateTab]);

  const handleProjectSelect = (projectId: string) => {
    recordRecentProject(projectId);
    openProject(projectId);
    setShowProjectsLanding(false);
    setProjectPickerOpen(false);
    setProjectSearch('');
  };

  const handleFileSelect = useCallback((filename: string, line?: number) => {
    setSelectedFile(filename);
    setSelectedLine(line);
    setActiveTab('files');
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

  const domainTitle =
    activeDomain === 'study'
      ? 'Estudos'
      : activeDomain === 'obsidian'
        ? 'Obsidian & Conhecimento'
        : activeDomain === 'sentinel'
          ? 'Sentinel'
          : 'Código & Projetos';

  const projectModeTabs: Array<{ id: TabType; label: string; icon: LucideIcon }> = [
    { id: 'files', label: 'Código', icon: FileCode },
    { id: 'preview', label: 'Preview', icon: Play },
    { id: 'terminal', label: 'Consola', icon: Terminal },
    { id: 'coding', label: 'Alteração IA', icon: GitPullRequest },
    { id: 'architecture', label: 'Arquitetura', icon: Network },
    { id: 'kanban', label: 'Kanban', icon: KanbanSquare },
    { id: 'debates', label: 'Debates', icon: MessageSquare },
    { id: 'mission_control', label: 'Missões', icon: Activity },
    { id: 'planner', label: 'Plano & DAG', icon: Sparkles },
  ];

  const renderHeader = () => {
    return (
      <header className="workspace-header border-b border-slate-800/80 bg-[#0b111a] shrink-0">
        <div className="flex h-11 items-center justify-between gap-2 px-4">
          {/* Left: Breadcrumbs + Active Domain Context Controls */}
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-semibold tracking-wider text-slate-500">JARVIS OS</span>
              <span className="text-slate-600">/</span>
              <span className="font-semibold text-sky-300">{domainTitle}</span>
            </div>

            {activeDomain === 'project' && (
              <div className="relative flex shrink-0 items-center gap-1.5 border-l border-slate-800 pl-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowProjectsLanding((prev) => !prev);
                    setActiveTab('files');
                    setProjectPickerOpen(false);
                  }}
                  className={`inline-flex h-7.5 items-center gap-1 rounded-md border px-2 text-[11px] font-medium transition cursor-pointer ${
                    showProjectsLanding || !projectContext
                      ? 'border-sky-400/35 bg-sky-500/15 text-sky-200'
                      : 'border-slate-800 bg-[#0f1722] text-slate-400 hover:text-slate-100'
                  }`}
                  title="Ver todos os projetos"
                >
                  <span>Projetos</span>
                </button>
                <button
                  onClick={() => {
                    setProjectPickerOpen((current) => {
                      const next = !current;
                      if (next) listProjects();
                      return next;
                    });
                  }}
                  className={`flex h-7.5 w-44 items-center gap-2 rounded-md border px-2.5 text-left text-xs font-semibold transition-colors sm:w-52 cursor-pointer ${
                    projectPickerOpen
                      ? 'border-sky-400/35 bg-sky-500/15 text-slate-100'
                      : 'border-slate-800 bg-[#080c12] text-slate-200 hover:border-slate-700'
                  }`}
                  aria-expanded={projectPickerOpen}
                >
                  <FolderOpen className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                  <span className="min-w-0 flex-1 truncate">{projectContext?.project_name || 'Selecionar projeto'}</span>
                  <ChevronDown className={`h-3 w-3 shrink-0 text-slate-500 transition-transform ${projectPickerOpen ? 'rotate-180' : ''}`} />
                </button>

                {projectPickerOpen && (
                  <>
                    <button
                      type="button"
                      aria-label="Fechar seletor de projetos"
                      onClick={() => setProjectPickerOpen(false)}
                      className="fixed inset-0 z-20 cursor-default"
                    />
                    <div className="absolute left-3 top-9 z-30 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-md border border-white/10 bg-[#0a0d14] shadow-2xl">
                      <div className="border-b border-white/8 p-2 space-y-2">
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => {
                              setCreateProjectModalOpen(true);
                              setProjectPickerOpen(false);
                            }}
                            className="flex flex-1 items-center justify-center gap-2 rounded-md border border-cyan-300/30 bg-cyan-300/10 py-1.5 text-xs font-semibold text-cyan-100 transition-colors hover:bg-cyan-300/20"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            <span>Criar novo projeto</span>
                          </button>
                          <button
                            onClick={() => listProjects()}
                            className="flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-gray-400 hover:text-white transition-colors"
                            title="Recarregar lista de projetos"
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" />
                          <input
                            autoFocus
                            value={projectSearch}
                            onChange={(event) => setProjectSearch(event.target.value)}
                            placeholder="Pesquisar projetos..."
                            className="h-8.5 w-full rounded-md border border-white/8 bg-black/25 pl-9 pr-3 text-xs text-gray-200 outline-none focus:border-cyan-300/30"
                          />
                        </div>
                      </div>
                      <div className="max-h-80 overflow-y-auto p-1.5 space-y-0.5">
                        {regularProjects.map((project) => (
                          <div
                            key={project.project_id}
                            className={`group flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-xs transition-colors ${
                              project.project_id === projectContext?.project_id
                                ? 'bg-cyan-300/10 text-cyan-100'
                                : 'text-gray-400 hover:bg-white/[0.05]'
                            }`}
                          >
                            <button
                              type="button"
                              onClick={() => handleProjectSelect(project.project_id)}
                              className="flex min-w-0 flex-1 items-center gap-2 text-left"
                            >
                              <FolderOpen className="h-3.5 w-3.5 shrink-0 text-gray-500" />
                              <span className="truncate">{project.project_name}</span>
                              {project.project_id === projectContext?.project_id && <Check className="ml-1 h-3.5 w-3.5 text-cyan-300 shrink-0" />}
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                setProjectToDelete({ id: project.project_id, name: project.project_name });
                              }}
                              className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-all shrink-0"
                              title={`Eliminar projeto ${project.project_name}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
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
                              <div
                                key={project.project_id}
                                className={`group flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-xs transition-colors ${
                                  project.project_id === projectContext?.project_id
                                    ? 'bg-cyan-300/10 text-cyan-100'
                                    : 'text-gray-500 hover:bg-white/[0.05] hover:text-gray-300'
                                }`}
                              >
                                <button
                                  type="button"
                                  onClick={() => handleProjectSelect(project.project_id)}
                                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                >
                                  <FolderOpen className="h-3.5 w-3.5 shrink-0" />
                                  <span className="truncate">{project.project_name}</span>
                                  {project.project_id === projectContext?.project_id && <Check className="ml-1 h-3.5 w-3.5 text-cyan-300 shrink-0" />}
                                </button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setProjectToDelete({ id: project.project_id, name: project.project_name });
                                  }}
                                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-all shrink-0"
                                  title={`Eliminar projeto técnico ${project.project_name}`}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ))}
                          </>
                        )}
                      </div>
                    </div>
                  </>
                )}

                <button
                  onClick={() => setCreateProjectModalOpen(true)}
                  className="hidden sm:inline-flex h-7.5 items-center gap-1 rounded-md border border-cyan-400/25 bg-cyan-500/10 px-2.5 text-[11px] font-semibold text-cyan-200 hover:bg-cyan-500/20 cursor-pointer"
                >
                  <Plus className="h-3 w-3" />
                  <span>Novo</span>
                </button>

                {projectContext?.project_id && (
                  isProjectRunning ? (
                    <button
                      onClick={() => stopProject()}
                      className="inline-flex h-7.5 items-center gap-1 rounded-md border border-rose-500/30 bg-rose-500/15 px-2.5 text-[11px] font-semibold text-rose-200 hover:bg-rose-500/25 cursor-pointer"
                    >
                      <Square className="h-3 w-3" />
                      <span>Parar</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        runProject(projectContext.project_id);
                        activateTab('preview');
                      }}
                      className="inline-flex h-7.5 items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2.5 text-[11px] font-semibold text-emerald-200 hover:bg-emerald-500/25 cursor-pointer"
                    >
                      <Play className="h-3 w-3" />
                      <span>Executar</span>
                    </button>
                  )
                )}
              </div>
            )}

            {activeDomain === 'obsidian' && vaultDiagnostics && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded border border-cyan-500/25 bg-cyan-500/10 px-2 py-0.5 text-[11px] text-cyan-200">
                <span>Qualidade média: {vaultDiagnostics.quality_average.toFixed(1)}%</span>
                <span>•</span>
                <span>{vaultDiagnostics.total_notes} notas</span>
              </span>
            )}

            {activeDomain === 'sentinel' && (
              <div className="flex items-center gap-2 border-l border-white/10 pl-3">
                <span className="rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                  Postura: {sentinelStatus?.posture || 'GOOD'}
                </span>
                <button
                  onClick={runSentinelAudit}
                  disabled={isSentinelAuditing}
                  className="inline-flex h-7 items-center gap-1 rounded border border-cyan-400/25 bg-cyan-500/10 px-2.5 text-[11px] font-semibold text-cyan-200 hover:bg-cyan-500/20 cursor-pointer disabled:opacity-50"
                >
                  {isSentinelAuditing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  <span>Auditar Sistema</span>
                </button>
              </div>
            )}
          </div>

          {/* Right: Spatial Overview Toggle, Contextual Assistant Toggle, Chat & Sandbox Badge */}
          <div className="flex items-center gap-1.5 shrink-0">
            {sandboxStatus && !sandboxStatus.is_docker && (
              <span
                className="hidden xl:inline-flex items-center gap-1 rounded border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 text-[10px] font-medium text-amber-200"
                title="Preview em servidor local de fallback"
              >
                <Shield className="h-3 w-3 text-amber-400" />
                <span>Local</span>
              </span>
            )}

            <button
              type="button"
              data-testid="toggle-spatial-overview"
              onClick={() => setSpatialOverviewOpen(!spatialOverviewOpen)}
              className={`inline-flex h-7.5 items-center gap-1.5 rounded-md border px-2.5 text-[11px] font-semibold transition cursor-pointer ${
                spatialOverviewOpen
                  ? 'border-sky-400/35 bg-sky-500/15 text-sky-200'
                  : 'border-slate-800 bg-[#0f1722] text-slate-300 hover:border-slate-700 hover:text-white'
              }`}
              title="Alternar Vista Espacial (Resumo dos módulos)"
            >
              <Compass className="h-3.5 w-3.5 text-sky-400" />
              <span className="hidden lg:inline">Vista Espacial</span>
            </button>

            {!(activeDomain === 'study' && studyInternalTab === 'reader') && (
              <button
                type="button"
                data-testid="toggle-context-assistant"
                onClick={() => setContextAssistantOpen((v) => !v)}
                className={`inline-flex h-7.5 items-center gap-1.5 rounded-md border px-2.5 text-[11px] font-semibold transition cursor-pointer ${
                  contextAssistantOpen
                    ? 'border-sky-400/35 bg-sky-500/15 text-sky-200'
                    : 'border-slate-800 bg-[#0f1722] text-slate-300 hover:border-slate-700 hover:text-white'
                }`}
                title="Alternar Painel Assistente Contextual Jarvis"
              >
                {contextAssistantOpen ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
                <span className="hidden md:inline">Assistente Jarvis</span>
              </button>
            )}

            <button
              type="button"
              data-testid="open-global-chat-btn"
              onClick={() => setChatPanelOpen(!chatPanelOpen)}
              className={`inline-flex h-7.5 items-center gap-1.5 rounded-md border px-2.5 text-[11px] font-medium transition cursor-pointer ${
                chatPanelOpen
                  ? 'border-sky-400/35 bg-sky-500/15 text-sky-200'
                  : 'border-slate-800 bg-[#0f1722] text-slate-300 hover:border-slate-700 hover:text-white'
              }`}
              title="Abrir Histórico Completo de Chat IA (Ctrl+J)"
            >
              <MessageSquare className="h-3.5 w-3.5 text-sky-400" />
              <span className="hidden md:inline">Chat</span>
            </button>
          </div>
        </div>

        {/* Contextual Sub-navigation Row for Projects */}
        {activeDomain === 'project' && !showProjectsLanding && projectContext && (
          <nav className="workspace-secondary-nav flex h-9.5 items-center gap-1 overflow-x-auto border-t border-slate-800/70 bg-[#080c12] px-4">
            {projectModeTabs.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => activateTab(tab.id)}
                  className={`workspace-secondary-tab flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium transition cursor-pointer ${
                    active
                      ? 'bg-[#0f1722] text-slate-100 border border-slate-700/80 font-semibold'
                      : 'text-slate-400 hover:bg-slate-900/70 hover:text-slate-200 border border-transparent'
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${active ? 'text-sky-400' : 'text-slate-400'}`} />
                  <span>{tab.label}</span>
                  {tab.id === 'files' && projectFiles && Object.keys(projectFiles).length > 0 && (
                    <span className="ml-0.5 rounded bg-slate-800 px-1 text-[10px] font-mono text-slate-300">
                      {Object.keys(projectFiles).length}
                    </span>
                  )}
                  {tab.id === 'architecture' && totalAstSymbols > 0 && (
                    <span className="ml-0.5 rounded bg-sky-500/15 px-1 text-[10px] font-mono text-sky-300">
                      {totalAstSymbols}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        )}
      </header>
    );
  };

  const fullBleedCanvas = activeDomain === 'study' || activeTab === 'knowledge' || activeTab === 'rules';
  const showOuterAssistant = contextAssistantOpen && !(activeDomain === 'study' && studyInternalTab === 'reader');

  return (
    <div data-testid="unified-workspace-shell" className="workspace-shell flex h-full w-full overflow-hidden bg-[#080c12] text-slate-200">
      {/* Left Compact Vertical Navigation Rail (Single Standby & Domain Rail) */}
      <aside className="flex w-14 shrink-0 flex-col items-center justify-between border-r border-slate-800/80 bg-[#0b111a] py-3">
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            data-testid="workspace-close-standby"
            onClick={() => {
              closeSpatialBoard();
              onClose?.();
            }}
            className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl border border-sky-400/30 bg-sky-500/10 text-sky-300 hover:bg-sky-500/20 cursor-pointer"
            title="Descansar e voltar ao Orbe Jarvis"
          >
            <Globe className="h-4 w-4" />
          </button>

          {[
            { id: 'study' as SpatialBoardDomain, label: 'Estudos', icon: GraduationCap },
            { id: 'project' as SpatialBoardDomain, label: 'Código & Projetos', icon: Code2 },
            { id: 'obsidian' as SpatialBoardDomain, label: 'Obsidian Vault', icon: Database },
            { id: 'sentinel' as SpatialBoardDomain, label: 'Sentinel', icon: Shield },
          ].map((item) => {
            const Icon = item.icon;
            const active = activeDomain === item.id;
            return (
              <button
                key={item.id}
                type="button"
                data-testid={`rail-domain-${item.id}`}
                onClick={() => {
                  setSpatialOverviewOpen(false);
                  handleSwitchUnifiedDomain(item.id);
                }}
                title={item.label}
                className={`group relative flex h-10 w-10 items-center justify-center rounded-xl border transition cursor-pointer ${
                  active
                    ? 'border-sky-400/35 bg-sky-500/15 text-sky-300 shadow-[0_0_12px_rgba(56,189,248,0.12)]'
                    : 'border-transparent text-slate-500 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                {active && <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r bg-sky-400" />}
                <Icon className="h-4.5 w-4.5" />
              </button>
            );
          })}
        </div>

        <div className="flex flex-col items-center gap-2 text-[9px] font-mono text-slate-600 select-none">
          <span>J-OS</span>
        </div>
      </aside>

      {/* Main Column: Clean Header + Center Canvas + Collapsible Contextual Assistant */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {renderHeader()}

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <div className={`min-w-0 flex-1 overflow-hidden ${fullBleedCanvas || spatialOverviewOpen ? 'p-0' : 'p-3'}`}>
            {spatialOverviewOpen ? (
              <div className="h-full overflow-y-auto bg-[#080c12] p-5">
                <SpatialOverviewPanel
                  domain={activeDomain}
                  studyDocuments={studyDocuments}
                  activeStudyDoc={
                    studyDocuments.find((d) => d.document_id === activeBoard?.documentId) ||
                    studyDocuments[0] ||
                    null
                  }
                  projectContext={projectContext}
                  projectFilesCount={filenames.length}
                  isProjectRunning={isProjectRunning}
                  previewUrl={previewUrl}
                  notesCount={notes.length}
                  vaultDiagnostics={vaultDiagnostics}
                  sentinelStatus={sentinelStatus}
                  sentinelEvents={sentinelEvents}
                  sentinelActions={sentinelActions}
                  onCloseOverview={() => setSpatialOverviewOpen(false)}
                  onJumpToTarget={(target) => {
                    setSpatialOverviewOpen(false);
                    handleSwitchUnifiedDomain(target.domain);
                    if (target.domain === 'study') {
                      const tabMap = {
                        landing: 'overview',
                        library: 'library',
                        reader: 'reader',
                        generated_doc: 'generated_document',
                        summary: 'summary',
                        practice: 'flashcards',
                      } as const;
                      navigateToStudyTarget({
                        tab: target.studyTab ? tabMap[target.studyTab] : 'reader',
                        document_id: target.documentId,
                      });
                    } else if (target.domain === 'project' && target.projectTab) {
                      setShowProjectsLanding(false);
                      setActiveTab(target.projectTab);
                    } else if (target.domain === 'obsidian') {
                      setObsidianSubTabOverride(target.obsidianTab || 'vault');
                      setActiveTab('knowledge');
                    }
                  }}
                />
              </div>
            ) : (
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
            <ViewFrame key="files" className="flex flex-col overflow-hidden">
              {!projectContext || showProjectsLanding ? (
                <ProjectsLandingView
                  projects={projects}
                  activeProjectId={projectContext?.project_id}
                  onOpenProject={(pId) => {
                    handleProjectSelect(pId);
                  }}
                  onCreateNewProject={(tpl) => {
                    if (tpl) setNewProjectTemplate(tpl);
                    setCreateProjectModalOpen(true);
                  }}
                  onDeleteProject={(proj) => setProjectToDelete(proj)}
                  onRefreshProjects={listProjects}
                />
              ) : (
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <div className="min-h-0 flex-1 overflow-hidden">
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
                        onCreateFile={createProjectFile}
                        onRenameFile={renameProjectFile}
                        onDeleteFile={deleteProjectFile}
                        onOpenChanges={() => activateTab('coding')}
                        onOpenPreview={() => {
                          setIdeDockOpen(true);
                          setIdeDockTab('preview');
                        }}
                        onOpenArchitecture={() => activateTab('architecture')}
                        isSaving={isSavingProjectFile}
                        saveState={projectFileSaveState}
                        insights={renderCodeInsights()}
                        entrypoints={projectContext.entrypoints || []}
                        astState={astState}
                        initialLine={selectedLine}
                        architectureSnapshot={architectureSnapshot}
                        projectContext={projectContext}
                        onReindex={reindexProject}
                        isIndexing={isIndexingProject}
                      />
                    </React.Suspense>
                  </div>

                  {/* Bottom IDE Dock Toggle Bar */}
                  <div className="flex h-8 shrink-0 items-center justify-between border-t border-slate-800/90 bg-[#0b111a] px-3 text-[11px]">
                    <div className="flex items-center gap-1">
                      {(
                        [
                          { id: 'console', label: 'Consola & Execução', icon: Terminal },
                          { id: 'preview', label: 'Preview Ao Vivo', icon: Play },
                          { id: 'problems', label: 'Problemas & Validação', icon: AlertCircle },
                        ] as const
                      ).map((dt) => {
                        const DIcon = dt.icon;
                        const activeDock = ideDockOpen && ideDockTab === dt.id;
                        return (
                          <button
                            key={dt.id}
                            type="button"
                            data-testid={`ide-dock-tab-${dt.id}`}
                            onClick={() => {
                              if (activeDock) {
                                setIdeDockOpen(false);
                              } else {
                                setIdeDockTab(dt.id);
                                setIdeDockOpen(true);
                              }
                            }}
                            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 font-medium transition cursor-pointer ${
                              activeDock
                                ? 'bg-sky-500/15 text-sky-200 border border-sky-400/30'
                                : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200 border border-transparent'
                            }`}
                          >
                            <DIcon className="h-3 w-3" />
                            <span>{dt.label}</span>
                            {dt.id === 'problems' && (codingSession?.errors?.length || 0) > 0 && (
                              <span className="rounded bg-rose-500/20 px-1 font-mono text-[10px] text-rose-300">
                                {codingSession?.errors.length}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    <div className="flex items-center gap-2">
                      {isProjectRunning && (
                        <span className="inline-flex items-center gap-1.5 text-[10px] text-emerald-300">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                          Em execução
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => setIdeDockOpen((v) => !v)}
                        className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200 cursor-pointer"
                        title={ideDockOpen ? 'Recolher painel inferior' : 'Expandir painel inferior'}
                      >
                        {ideDockOpen ? <PanelBottomClose className="h-3.5 w-3.5" /> : <PanelBottomOpen className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* Resizable Bottom IDE Dock Panel */}
                  {ideDockOpen && (
                    <>
                      <ResizableHandle
                        direction="vertical"
                        reverse
                        value={ideDockHeight}
                        min={140}
                        max={440}
                        onChange={setIdeDockHeight}
                        ariaLabel="Redimensionar consola do IDE"
                      />
                      <div
                        data-testid="ide-bottom-dock"
                        style={{ height: ideDockHeight }}
                        className="flex shrink-0 flex-col overflow-hidden border-t border-slate-800 bg-[#080c12]"
                      >
                        {ideDockTab === 'console' && (
                          <div className="flex min-h-0 flex-1 flex-col">
                            {projectContext.suggested_commands?.length > 0 && (
                              <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-800/80 bg-[#0b111a] px-3 py-1.5 text-[11px]">
                                <span className="text-slate-400 font-medium mr-1">Validações:</span>
                                {projectContext.suggested_commands.map((cmd) => (
                                  <button
                                    key={`${cmd.kind}-${cmd.command}`}
                                    type="button"
                                    onClick={() => {
                                      try {
                                        navigator.clipboard?.writeText(cmd.command);
                                      } catch {}
                                      sendDirective(`Executa validação no projeto '${projectContext.project_id}': ${cmd.command}`);
                                    }}
                                    className="rounded border border-slate-700/80 bg-[#0f1722] px-2 py-0.5 font-mono text-[10px] text-sky-300 hover:border-sky-400/40 hover:bg-sky-500/10 cursor-pointer"
                                    title={`${cmd.source} — Clica para enviar ao Jarvis e copiar`}
                                  >
                                    $ {cmd.command}
                                  </button>
                                ))}
                              </div>
                            )}
                            <pre className="min-h-0 flex-1 overflow-auto bg-[#06090e] p-3 font-mono text-xs leading-relaxed text-emerald-300 select-text">
                              <code>{projectOutput || '[Consola IDE] Sem output de execução.'}</code>
                            </pre>
                          </div>
                        )}

                        {ideDockTab === 'preview' && (
                          <div className="relative min-h-0 flex-1 bg-white">
                            {previewUrl && previewUrl !== 'about:blank' ? (
                              <iframe key={previewKey} src={previewUrl} className="h-full w-full border-none" title="IDE Dock Preview" />
                            ) : (
                              <div className="flex h-full flex-col items-center justify-center gap-2 bg-[#080c12] p-4 text-center text-slate-400">
                                <Rocket className="h-7 w-7 text-sky-400/70" />
                                <p className="text-xs text-slate-300">
                                  {isProjectRunning ? 'A aguardar servidor na porta local...' : 'Nenhum servidor de preview ativo.'}
                                </p>
                                {!isProjectRunning && (
                                  <button
                                    type="button"
                                    onClick={() => runProject(projectContext.project_id)}
                                    className="inline-flex items-center gap-1.5 rounded-md border border-emerald-400/35 bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 cursor-pointer"
                                  >
                                    <Play className="h-3 w-3" />
                                    <span>Iniciar Preview</span>
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {ideDockTab === 'problems' && (
                          <div className="min-h-0 flex-1 overflow-y-auto p-3 text-xs space-y-2">
                            {(!codingSession?.errors?.length && !codingSession?.validation_results?.length && !projectFileSaveState?.error) ? (
                              <p className="text-slate-500">Sem erros de compilação, gravação ou validação detetados neste momento.</p>
                            ) : (
                              <>
                                {projectFileSaveState?.error && (
                                  <div className="rounded-md border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-rose-200">
                                    Erro ao guardar {projectFileSaveState.filename}: {projectFileSaveState.error}
                                  </div>
                                )}
                                {codingSession?.errors?.map((err) => (
                                  <div key={err} className="rounded-md border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-rose-200">
                                    {err}
                                  </div>
                                ))}
                                {codingSession?.validation_results?.map((vr) => (
                                  <div key={vr.command} className="rounded-md border border-slate-800 bg-[#0b111a] px-3 py-2">
                                    <div className="flex items-center justify-between gap-2">
                                      <code className="font-mono text-slate-200">{vr.command}</code>
                                      <span className={vr.exit_code === 0 ? 'text-emerald-300' : 'text-rose-300'}>
                                        exit {vr.exit_code}
                                      </span>
                                    </div>
                                    {vr.stderr && <pre className="mt-1 max-h-24 overflow-auto text-[11px] text-rose-300/90">{vr.stderr}</pre>}
                                  </div>
                                ))}
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </ViewFrame>
          )}

          {activeTab === 'architecture' && (
            <ViewFrame key="architecture" className="h-full overflow-hidden">
              <ProjectArchitectureView
                onNavigateToFile={(file, line) => {
                  handleFileSelect(file, line);
                }}
                onOpenChanges={() => activateTab('coding')}
              />
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
                {isProjectRunning && (!previewUrl || previewUrl === 'about:blank') ? (
                  <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#070a10] p-6 text-center text-gray-300">
                    <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
                    <h4 className="text-sm font-semibold text-white">A Iniciar Servidor</h4>
                    <p className="max-w-sm text-xs text-gray-400">A compilar projeto e a aguardar escuta ativa na porta de rede...</p>
                  </div>
                ) : previewUrl && previewUrl !== 'about:blank' ? (
                  <iframe key={previewKey} src={previewUrl} className="h-full w-full border-none" title="Project Preview" />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#070a10] p-6 text-center text-gray-400">
                    <Rocket className="h-10 w-10 text-cyan-300/60" />
                    <h4 className="text-sm font-semibold text-white">Preview Não Iniciado</h4>
                    <p className="max-w-sm text-xs text-gray-500">Inicie a execução do projeto para visualizar a aplicação em tempo real.</p>
                    <button
                      onClick={() => runProject()}
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
                  <button onClick={() => runProject()} disabled={isProjectRunning || !projectContext} className={`${BUTTON_BASE} border-emerald-400/25 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/15`}>
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
                  <div className="flex items-center justify-between">
                    <label htmlFor="coding-objective" className="block text-xs font-medium text-gray-300">
                      Objetivo
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowObjectiveHistory((prev) => !prev)}
                      className={`flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] font-medium transition-all cursor-pointer ${
                        showObjectiveHistory
                          ? 'border-cyan-300/40 bg-cyan-300/15 text-cyan-200'
                          : 'border-white/10 bg-white/[0.04] text-cyan-300 hover:bg-white/[0.08] hover:text-white'
                      }`}
                      title="Ver e reutilizar objetivos pedidos anteriormente"
                    >
                      <History className="h-3 w-3 text-cyan-300" />
                      <span>Histórico de pedidos ({codingObjectiveHistory.length})</span>
                    </button>
                  </div>

                  {/* Sugestões rápidas em chips */}
                  {codingObjectiveHistory.length > 0 && !codingObjective && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {codingObjectiveHistory.slice(0, 3).map((item, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setCodingObjective(item)}
                          className="px-2 py-1 rounded bg-white/[0.03] hover:bg-cyan-300/10 border border-white/8 hover:border-cyan-300/30 text-[10px] text-gray-400 hover:text-cyan-200 font-mono text-left truncate max-w-full transition-all cursor-pointer"
                          title={`Usar: ${item}`}
                        >
                          ↳ {item}
                        </button>
                      ))}
                    </div>
                  )}

                  {showObjectiveHistory && (
                    <div className="rounded-md border border-cyan-400/25 bg-[#070b12]/95 p-2.5 text-xs space-y-1.5 max-h-52 overflow-y-auto backdrop-blur-xl shadow-xl">
                      <div className="flex items-center justify-between pb-1 mb-1 border-b border-white/8 text-[10px] text-gray-400 font-mono">
                        <span className="font-semibold text-gray-300">Pedidos Anteriores</span>
                        <button
                          type="button"
                          onClick={() => {
                            setCodingObjectiveHistory([]);
                            try { localStorage.removeItem('jarvis_coding_objectives_history'); } catch {}
                          }}
                          className="hover:text-rose-300 cursor-pointer text-gray-500"
                        >
                          Limpar tudo
                        </button>
                      </div>
                      {codingObjectiveHistory.length === 0 ? (
                        <div className="text-gray-500 text-xs py-2 text-center">Nenhum pedido anterior guardado.</div>
                      ) : (
                        codingObjectiveHistory.map((prevObj, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setCodingObjective(prevObj);
                              setShowObjectiveHistory(false);
                            }}
                            className="p-1.5 rounded hover:bg-cyan-300/10 cursor-pointer text-gray-300 hover:text-cyan-100 font-mono text-[11px] transition-colors flex items-center justify-between group"
                            title={prevObj}
                          >
                            <span className="truncate flex-1">{prevObj}</span>
                            <span className="text-[10px] text-cyan-400/60 opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0">Usar ↵</span>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  <textarea
                    id="coding-objective"
                    value={codingObjective}
                    onChange={(event) => setCodingObjective(event.target.value)}
                    placeholder="Descreva a alteração pretendida de forma detalhada..."
                    className="min-h-[160px] w-full resize-y rounded-md border border-white/12 bg-black/45 p-3.5 text-sm leading-relaxed text-gray-100 placeholder:text-gray-600 outline-none focus:border-cyan-300/50 focus:ring-1 focus:ring-cyan-300/25 shadow-inner transition-all font-sans"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        const obj = codingObjective.trim();
                        if (!obj) return;
                        setCodingObjectiveHistory((prev) => {
                          const next = [obj, ...prev.filter((p) => p !== obj)].slice(0, 30);
                          try {
                            localStorage.setItem('jarvis_coding_objectives_history', JSON.stringify(next));
                          } catch {}
                          return next;
                        });
                        createCodingSession(obj);
                      }}
                      disabled={!projectContext || !codingObjective.trim() || isCodingSessionBusy}
                      className={`${BUTTON_BASE} flex-1 border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/20 ${isCodingSessionBusy ? 'cursor-wait bg-cyan-300/20' : ''}`}
                    >
                      {isCodingSessionBusy ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
                          <span>A planear alteração...</span>
                        </>
                      ) : (
                        <>
                          <WandSparkles className="h-4 w-4" />
                          <span>Criar plano</span>
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (codingObjective.trim()) {
                          sendDirective(`[Objetivo de Alteração]: ${codingObjective.trim()}`);
                        }
                        setChatPanelOpen(true);
                      }}
                      className="px-3 border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-gray-300 hover:text-cyan-200 text-xs rounded-md flex items-center gap-1.5 transition-all cursor-pointer"
                      title="Abrir no Chat com IA"
                    >
                      <MessageSquare className="h-3.5 w-3.5 text-cyan-300" />
                      <span className="hidden sm:inline">Discutir no Chat</span>
                    </button>
                  </div>

                  {safetyRefusal && (
                    <div className="rounded-md border border-rose-500/30 bg-rose-950/40 p-3 text-xs text-rose-200">
                      <div className="flex items-start gap-2">
                        <ShieldAlert className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between font-semibold text-rose-300">
                            <span>{safetyRefusal.status}</span>
                            <button onClick={clearSafetyRefusal} className="text-gray-400 hover:text-white">
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                          <p className="text-rose-100/90 leading-relaxed">{safetyRefusal.reason}</p>
                          <div className="text-[10px] text-rose-300/75 pt-1 border-t border-rose-500/20">
                            <div><span className="font-semibold">Regra:</span> {safetyRefusal.policy_rule}</div>
                            <div><span className="font-semibold">Ref ID:</span> {safetyRefusal.request_id}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {codingSessionError && (
                    <div className="rounded-md border border-amber-500/30 bg-amber-950/40 p-3 text-xs text-amber-200">
                      <div className="flex items-start gap-2">
                        <CircleAlert className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between font-semibold text-amber-300">
                            <span>Erro no Planeamento</span>
                            <button onClick={clearCodingSessionError} className="text-gray-400 hover:text-white">
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                          <p className="text-amber-100/90 leading-relaxed">{codingSessionError}</p>
                        </div>
                      </div>
                    </div>
                  )}

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
                      {isCodingSessionBusy ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin text-emerald-300" />
                          <span>A aplicar...</span>
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4" />
                          <span>Aplicar</span>
                        </>
                      )}
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
                {isCodingSessionBusy ? (
                  <div className="flex h-full min-h-80 flex-col items-center justify-center gap-5 p-8 text-center animate-in fade-in duration-300">
                    <div className="relative flex items-center justify-center">
                      <div className="absolute h-20 w-20 animate-ping rounded-full border border-cyan-400/20 bg-cyan-400/5 duration-1000" />
                      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/40 bg-gradient-to-br from-cyan-950/80 to-[#0f1b20] shadow-[0_0_30px_rgba(6,182,212,0.25)]">
                        <Cpu className="h-8 w-8 animate-pulse text-cyan-300" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <h4 className="text-sm font-semibold tracking-wide text-cyan-100 flex items-center justify-center gap-2">
                        <Sparkles className="h-4 w-4 text-cyan-300 animate-spin" />
                        <span>A Orquestrar Alteração de Código...</span>
                      </h4>
                      <p className="max-w-md text-xs text-gray-400 leading-relaxed">
                        O agente de engenharia está a analisar a árvore de sintaxe (AST), a mapear dependências e a produzir diffs atómicos de forma transacional.
                      </p>
                    </div>

                    <div className="w-full max-w-sm space-y-2 rounded-lg border border-white/8 bg-black/40 p-3.5 text-left text-xs">
                      <div className="flex items-center gap-2 text-cyan-200">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />
                        <span className="font-medium">1. Mapeamento de contexto e grafos do projeto</span>
                      </div>
                      <div className="flex items-center gap-2 text-cyan-200/80 pl-5.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
                        <span>2. Raciocínio de Código (Gemini / Qwen 3.5 9B)</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-500 pl-5.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-gray-600" />
                        <span>3. Geração de Diffs unificados e validações</span>
                      </div>
                    </div>

                    <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-white/10">
                      <div className="h-full w-full animate-pulse bg-gradient-to-r from-cyan-500 via-teal-300 to-cyan-500" />
                    </div>
                  </div>
                ) : !codingSession ? (
                  safetyRefusal ? (
                    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 text-center p-6">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-rose-500/30 bg-rose-950/30 text-rose-400">
                        <ShieldAlert className="h-6 w-6" />
                      </div>
                      <h4 className="text-sm font-semibold text-rose-200">{safetyRefusal.status}</h4>
                      <p className="max-w-md text-xs text-gray-400 leading-relaxed">{safetyRefusal.reason}</p>
                      <div className="rounded border border-white/8 bg-black/30 px-3 py-2 text-[11px] font-mono text-gray-400">
                        Política: {safetyRefusal.policy_rule} | Execuções Bloqueadas: 0 ferramentas / 0 ficheiros alterados
                      </div>
                    </div>
                  ) : codingSessionError ? (
                    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 text-center p-6">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-amber-500/30 bg-amber-950/30 text-amber-400">
                        <CircleAlert className="h-6 w-6" />
                      </div>
                      <h4 className="text-sm font-semibold text-amber-200">Não foi possível criar o plano</h4>
                      <p className="max-w-md text-xs text-gray-300 leading-relaxed">{codingSessionError}</p>
                      <button
                        onClick={() => createCodingSession(codingObjective)}
                        className="mt-2 inline-flex items-center gap-2 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs text-cyan-200 hover:bg-cyan-400/20"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        <span>Tentar novamente</span>
                      </button>
                    </div>
                  ) : (
                    <EmptyState icon={GitPullRequest} title="Nenhuma alteracao preparada." />
                  )
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

          {(activeTab === 'knowledge' || activeTab === 'rules') && (
            <ViewFrame key="knowledge" className="h-full">
              <ObsidianVaultView
                notes={notes}
                currentNote={currentNote}
                vaultDiagnostics={vaultDiagnostics}
                vaultImprovementQueue={vaultImprovementQueue}
                noteQualityAudit={noteQualityAudit}
                noteEnrichmentProposal={noteEnrichmentProposal}
                isAuditingNote={isAuditingNote}
                isEnrichingNote={isEnrichingNote}
                onRefreshNotes={getNotes}
                onReadNote={async (filename) => {
                  setSelectedNoteName(filename);
                  return readNote(filename);
                }}
                onSaveNote={saveNote}
                onRefreshDiagnostics={getVaultDiagnostics}
                onAuditNoteQuality={auditNoteQuality}
                onEnrichNote={enrichNote}
                onRollbackNote={rollbackNote}
                onPauseQueueWorker={pauseQueueWorker}
                onResumeQueueWorker={resumeQueueWorker}
                onStartImprovementBatch={startImprovementBatch}
                onGetQueueStatus={getQueueStatus}
                rules={rules}
                architecture={architecture}
                decisions={decisions}
                onDeleteRule={deleteRule}
                onDeleteArchitecture={deleteArchitecture}
                onDeleteDecision={deleteDecision}
                initialSubTab={activeTab === 'rules' ? 'rules' : obsidianSubTabOverride}
                studyDocuments={studyDocuments}
                onOpenStudyDocument={(docId) => {
                  handleSwitchUnifiedDomain('study');
                  navigateToStudyTarget({ tab: 'reader', document_id: docId });
                }}
                onAskAssistant={(prompt) => {
                  setContextAssistantOpen(true);
                  handleSendContextualPrompt(prompt);
                }}
              />
            </ViewFrame>
          )}

          {activeTab === 'mission_control' && (
            <ViewFrame key="mission_control" className="overflow-hidden">
              {viewingMissionControlId ? (
                <MissionControlCenter
                  activeMissionId={viewingMissionControlId}
                  onBackToList={() => setViewingMissionControlId(null)}
                  onOpenInCode={(filePath, line) => {
                    setSelectedFile(filePath);
                    if (line !== undefined) setSelectedLine(line);
                    setActiveTab('files');
                  }}
                  onOpenArchitecture={() => {
                    setActiveTab('architecture');
                  }}
                />
              ) : (
                <MissionListView
                  selectedProjectId={projectContext?.project_id}
                  onSelectProject={(pId) => {
                    if (pId !== 'ALL') openProject(pId);
                  }}
                  onOpenMission={(mId, pId) => {
                    if (pId && pId !== projectContext?.project_id) {
                      openProject(pId);
                    }
                    openMission(mId);
                    setViewingMissionControlId(mId);
                  }}
                />
              )}
            </ViewFrame>
          )}

          {activeTab === 'planner' && (
            <ViewFrame key="planner" className="overflow-hidden">
              <MissionPlanner />
            </ViewFrame>
          )}

          {(activeTab === 'study' || activeTab === 'lectures') && (
            <ViewFrame key="study" className="h-full">
              <StudyContainer
                documents={studyDocuments}
                initialActiveDocumentId={activeBoard?.domain === 'study' ? activeBoard.documentId : undefined}
                onActiveDocumentChange={(docId) => {
                  if (docId && activeBoard?.domain === 'study' && activeBoard.documentId !== docId) {
                    openSpatialBoard('study', docId);
                  }
                }}
                onActiveTabChange={setStudyInternalTab}
                notes={notes.map((n) => ({ filename: n }))}
                isRecording={isRecordingLecture}
                onStartRecording={startLectureRecording}
                onStopRecording={stopLectureRecording}
                onSaveNoteToObsidian={saveNote}
                onRefreshDocuments={listStudyDocuments}
                onUploadDocument={async (payload) => {
                  const candidateVideoUrl =
                    payload.video_url ||
                    (payload.source_type === 'VIDEO' &&
                    /^https?:\/\//i.test(payload.content_text || payload.filename || '')
                      ? (payload.content_text || payload.filename)
                      : undefined);
                  if (candidateVideoUrl) {
                    await ingestStudyVideoUrl(
                      candidateVideoUrl,
                      payload.title,
                      payload.subject,
                      payload.collection_id
                    );
                    return;
                  }
                  uploadStudyDocument(
                    payload.filename,
                    payload.title,
                    payload.subject,
                    payload.content_base64,
                    payload.content_text,
                    payload.source_type,
                    payload.file_path
                  );
                }}
                onTranslate={async (text, docId) => {
                  if (!docId) return text;
                  const res = await contextualAssist(docId, 'translate', text, { targetLanguage: 'pt-PT' });
                  return res?.translation || text;
                }}
                onExplain={async (text, level, docId) => {
                  if (!docId) return { literal: text, simple: text, context_importance: '' };
                  const res = await contextualAssist(docId, 'explain', text, { level });
                  return {
                    literal: res?.translation || text,
                    simple: res?.simple_explanation || '',
                    context_importance: res?.contextual_importance || '',
                  };
                }}
                onSummarizeSection={async (sectionId, docId) => {
                  if (!docId) return { main_idea: '', key_points: [], terms: [], doubts: [] };
                  const res = await contextualAssist(docId, 'summarize_section', '', { sectionId });
                  return {
                    main_idea: res?.main_idea || '',
                    key_points: res?.key_points || [],
                    terms: res?.terms || [],
                    doubts: res?.open_questions || [],
                  };
                }}
                onExplainMedia={async (mediaId, docId) => {
                  if (!docId) return '';
                  const res = await contextualAssist(docId, 'explain_figure', '', { mediaId });
                  return res?.media_explanation || res?.explanation || '';
                }}
                onAskPaper={async (query, docId) => {
                  if (!docId) return { answer: '', sources: [] };
                  return askStudyPaper(docId, query);
                }}
                onGetDocumentFile={async (docId) => {
                  return getStudyDocumentFile(docId);
                }}
                onGenerateCornell={generateStudyCornell}
                onDeleteDocument={deleteStudyDocument}
                activeStudyQuiz={activeStudyQuiz}
                studyQuizResult={studyQuizResult}
                onGenerateQuiz={generateStudyQuiz}
                onSubmitQuiz={submitStudyQuiz}
                onSearchRag={async (query, docId) => searchStudyRag(query, docId)}
                onReadNote={readNote}
                onGenerateSummary={(docId, mode, forceRegenerate) => generateStudySummary(docId, mode, Boolean(forceRegenerate))}
                onSynthesizeDocuments={synthesizeStudyDocuments}
                onSaveToVault={saveToStudyVault}
                collections={studyCollections}
                onRefreshCollections={listStudyCollections}
                onCreateCollection={createStudyCollection}
                onLinkFolder={linkStudyFolder}
                onUnlinkFolder={unlinkStudyFolder}
                onSyncFolder={syncStudyFolder}
                onAskCourse={askStudyCourse}
                onRetryDocument={retryStudyDocument}
                onCancelGeneration={cancelStudyGeneration}
                onGetEditorialPlan={getStudyEditorialPlan}
                onGenerateEditorialPlan={generateStudyEditorialPlan}
                onGetGeneratedDocumentStatus={getGeneratedStudyDocumentStatus}
                onGenerateStudyDocument={generateStudyDocument}
                onGetGeneratedDocumentFile={getGeneratedStudyDocumentFile}
                studyModesApi={studyModesApi}
                pipelineStage={studyPipelineStage}
                lastDocumentError={lastStudyDocumentError}
                externalNavigationTarget={studyNavigationTarget}
                readingNotesByDoc={studyReadingNotes}
                highlightsByDoc={studyHighlights}
                onRequestDocumentDetails={getStudyDocumentDetails}
                onAddReadingNote={addStudyReadingNote}
                onAddHighlight={addStudyHighlight}
                onStudyContextChange={updateActiveStudyContext}
              />
            </ViewFrame>
          )}

          {activeTab === 'sentinel' && (
            <ViewFrame key="sentinel" className="h-full">
              <SentinelDashboard />
            </ViewFrame>
          )}
            </AnimatePresence>
            )}
          </div>

          {showOuterAssistant && (
            <>
              <ResizableHandle
                direction="horizontal"
                reverse
                value={assistantWidth}
                min={260}
                max={520}
                onChange={setAssistantWidth}
                ariaLabel="Redimensionar assistente contextual"
              />
              <aside
                data-testid="contextual-jarvis-panel"
                style={{ width: assistantWidth }}
                className="flex shrink-0 flex-col border-l border-slate-800/80 bg-[#0b111a]"
              >
              <div className="flex h-10 shrink-0 items-center justify-between border-b border-white/[0.07] bg-[#0b1016] px-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Assistente Jarvis</span>
                </div>
                <button
                  type="button"
                  onClick={() => setContextAssistantOpen(false)}
                  className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white cursor-pointer"
                  title="Fechar assistente"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>

              <div className="border-b border-white/[0.06] px-3 py-2 text-[11px] text-zinc-400">
                <div className="font-semibold text-zinc-200 truncate">
                  {activeDomain === 'project'
                    ? `Projeto: ${projectContext?.project_name || 'Workspace'}${selectedFile ? ` • ${selectedFile}` : ''}`
                    : activeDomain === 'obsidian'
                      ? `Obsidian${selectedNoteName ? ` • ${selectedNoteName}` : ` (${notes.length} notas)`}`
                      : activeDomain === 'sentinel'
                        ? `Sentinel • ${sentinelStatus?.posture || 'GOOD'}`
                        : `Estudos • ${studyDocuments.length} materiais`}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {activeDomain === 'project' && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleSendContextualPrompt('Explica a arquitetura e dependências principais deste projeto.')}
                        className="rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-zinc-300 hover:border-cyan-400/35 hover:text-cyan-200 cursor-pointer"
                      >
                        Explicar Arquitetura
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSendContextualPrompt('Revê o ficheiro atual e sugere melhorias de qualidade.')}
                        className="rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-zinc-300 hover:border-cyan-400/35 hover:text-cyan-200 cursor-pointer"
                      >
                        Rever Ficheiro
                      </button>
                    </>
                  )}
                  {activeDomain === 'obsidian' && (
                    <button
                      type="button"
                      onClick={() => handleSendContextualPrompt('Analisa ligações conceptuais em falta no meu Obsidian Vault.')}
                      className="rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-zinc-300 hover:border-cyan-400/35 hover:text-cyan-200 cursor-pointer"
                    >
                      Mapear Ligações
                    </button>
                  )}
                  {activeDomain === 'sentinel' && (
                    <button
                      type="button"
                      onClick={() => handleSendContextualPrompt('Resume os eventos Sentinel mais recentes e riscos detetados.')}
                      className="rounded border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-zinc-300 hover:border-cyan-400/35 hover:text-cyan-200 cursor-pointer"
                    >
                      Analisar Riscos
                    </button>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-2.5 text-xs">
                {chatMessages.slice(-8).map((msg, idx) => (
                  <div
                    key={msg.id || idx}
                    className={`rounded-lg border p-2.5 leading-relaxed ${
                      msg.sender === 'USER'
                        ? 'ml-4 border-cyan-500/25 bg-cyan-950/20 text-cyan-100'
                        : 'mr-2 border-white/[0.07] bg-[#0e141b] text-zinc-300'
                    }`}
                  >
                    <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
                      {msg.sender === 'USER' ? 'Tu' : 'Jarvis'}
                    </div>
                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  </div>
                ))}
                {chatMessages.length === 0 && (
                  <p className="py-6 text-center text-[11px] text-zinc-500">
                    Faz uma pergunta contextual sobre o domínio ativo.
                  </p>
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendContextualPrompt();
                }}
                className="border-t border-white/[0.07] p-2.5"
              >
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={assistantInput}
                    onChange={(e) => setAssistantInput(e.target.value)}
                    placeholder="Perguntar ao Jarvis neste contexto..."
                    className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-white placeholder-zinc-500 focus:border-cyan-400/40 focus:outline-none"
                  />
                  <button
                    type="submit"
                    disabled={!assistantInput.trim()}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-40 cursor-pointer"
                    title="Enviar"
                  >
                    <Send className="h-3.5 w-3.5" />
                  </button>
                </div>
              </form>
            </aside>
            </>
          )}
        </div>
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
                const rawId = newProjectId.trim() || newProjectName.trim();
                if (!rawId) return;
                const cleanId = rawId
                  .normalize('NFD')
                  .replace(/[\u0300-\u036f]/g, '')
                  .replace(/[^a-zA-Z0-9._-]/g, '-')
                  .replace(/-+/g, '-')
                  .replace(/^-|-$/g, '')
                  .toLowerCase();
                const displayName = newProjectName.trim() || rawId;
                if (cleanId) {
                  createProject(cleanId, displayName, newProjectTemplate);
                  setCreateProjectModalOpen(false);
                  setNewProjectId('');
                  setNewProjectName('');
                }
              }}
              disabled={!newProjectId.trim() && !newProjectName.trim()}
              className={`${BUTTON_BASE} border-cyan-300/30 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/20`}
            >
              Criar Projeto
            </button>
          </>
        )}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">Nome de exibição</label>
            <input
              value={newProjectName}
              onChange={(e) => {
                const name = e.target.value;
                setNewProjectName(name);
                if (!newProjectId || newProjectId === newProjectName.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9._-]/g, '-').toLowerCase()) {
                  setNewProjectId(
                    name
                      .normalize('NFD')
                      .replace(/[\u0300-\u036f]/g, '')
                      .replace(/[^a-zA-Z0-9._-]/g, '-')
                      .replace(/-+/g, '-')
                      .replace(/^-|-$/g, '')
                      .toLowerCase()
                  );
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const rawId = newProjectId.trim() || newProjectName.trim();
                  if (rawId) {
                    const cleanId = rawId.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9._-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').toLowerCase();
                    const displayName = newProjectName.trim() || rawId;
                    if (cleanId) {
                      createProject(cleanId, displayName, newProjectTemplate);
                      setCreateProjectModalOpen(false);
                      setNewProjectId('');
                      setNewProjectName('');
                    }
                  }
                }
              }}
              placeholder="ex: Meu Novo App"
              className="h-9 w-full rounded-md border border-white/10 bg-black/40 px-3 text-xs text-gray-200 outline-none focus:border-cyan-300/40"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-300">ID do projeto (diretório) *</label>
            <input
              value={newProjectId}
              onChange={(e) => setNewProjectId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const rawId = newProjectId.trim() || newProjectName.trim();
                  if (rawId) {
                    const cleanId = rawId.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9._-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').toLowerCase();
                    const displayName = newProjectName.trim() || rawId;
                    if (cleanId) {
                      createProject(cleanId, displayName, newProjectTemplate);
                      setCreateProjectModalOpen(false);
                      setNewProjectId('');
                      setNewProjectName('');
                    }
                  }
                }
              }}
              placeholder="ex: meu-novo-app"
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

      {/* Confirm Delete Project Modal */}
      {projectToDelete && (
        <Modal
          isOpen={Boolean(projectToDelete)}
          onClose={() => setProjectToDelete(null)}
          title="Eliminar Projeto"
          footer={(
            <>
              <button
                type="button"
                onClick={() => setProjectToDelete(null)}
                className={`${BUTTON_BASE} border-white/10 text-gray-400`}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => {
                  deleteProject(projectToDelete.id);
                  setProjectToDelete(null);
                }}
                className={`${BUTTON_BASE} border-rose-500/30 bg-rose-500/20 text-rose-200 hover:bg-rose-500/30 font-semibold`}
              >
                Eliminar Projeto
              </button>
            </>
          )}
        >
          <div className="space-y-3 text-xs text-gray-300">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-500/10 border border-rose-500/20 shrink-0">
                <Trash2 className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-white">Eliminar Projeto Permanentemente</h4>
                <p className="text-xs text-rose-300/80 font-mono mt-0.5 truncate">{projectToDelete.name} ({projectToDelete.id})</p>
              </div>
            </div>
            <p className="leading-relaxed">
              Tem a certeza de que deseja eliminar o projeto <strong className="text-white">{projectToDelete.name}</strong>?
              Todos os ficheiros de código, histórico e tarefas associadas serão removidos do disco.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
};
