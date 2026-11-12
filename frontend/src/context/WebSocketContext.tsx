import React, { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { missionRuntimeStore } from '../features/missions/stores/missionRuntimeStore';
import { usePermissionStore } from '../features/permissions/PermissionStore';
import {
  useOptionalTransport,
  WebSocketTransportAdapter,
  type JarvisTransport,
  type ResponseDecision,
} from '../transport';
import {
  normalizeServerMessage,
  type ServerMessage,
  type ActiveTemplate,
  type ArenaState,
  type ArenaUpdateMessage,
  type ArchitectureMemory,
  type AstState,
  type ChatMessage,
  type ChatProtocolMessage,
  type ClientMessage,
  type CodingSessionData,
  type EngineeringDecision,
  type KanbanCard,
  type KanbanColumn,
  type KanbanState,
  type MissionClientOperation,
  type MissionData,
  type MissionSnapshot,
  type ArchitectureSnapshot,
  type PlannerState,
  type ProjectContextData,
  type ProjectReferenceResult,
  type ProjectSummary,
  type RuleMemory,
  type SystemStatus,
  type TemplateChangedMessage,
  type UiAction,
  type LectureLessonData,
  type LectureQuizResult,
  type LectureHistoryItem,
  type SentinelStatusData,
  type SentinelSecurityEventData,
  type SentinelActionData,
  type ExpansionRecord,
  type AdaptationRecordData,
  type MissionControlStateData,
  type MissionControlCommandResultData,
  type MissionControlCommandPayload,
  type MissionIntentPreviewResultMessage,
  type MissionIntentResultMessage,
  type VaultDiagnosticsData,
  type NoteImprovementItem,
  type StudyOperationStatusPayload,
  type StudyNavigatePayload,
  type StudyUiContextPayload,
  type NoteQualityAuditMessage,
  type NoteEnrichmentResultMessage,
  type SafetyRefusalData,
} from '../protocol/websocket';
import type {
  StudyDocument,
  StudyQuiz,
  QuizEvaluationResult,
  Flashcard,
  StudyCollection,
  EditorialStudyPlan,
  EditorialPlanStatus,
  StudyDocumentGenerationStatus,
  StudyDocumentGenerationResult,
  StudyDocumentFilePayload,
  StudyModesBridge,
} from '../features/study/types';
import {
  buildStudySpatialBoard,
  buildProjectSpatialBoard,
  buildObsidianSpatialBoard,
  buildSentinelSpatialBoard,
  type SpatialBoardData,
  type SpatialBoardDomain,
} from '../features/board/boardBuilders';
import type {
  ChatAttachment,
  ChatSession,
  SystemLogEntry,
  LogCategory,
  LogLevel,
} from '../features/chat/types';
import {
  loadStoredChatSessions,
  persistChatSessions,
  loadStoredPromptHistory,
  persistPromptHistory,
  createDefaultSession,
  generateSessionId,
  generateSmartSessionTitle,
} from '../features/chat/chatSessionStorage';

export interface ProjectFileSaveState {
  ok: boolean;
  filename: string;
  sha256: string;
  error: string;
}

export type { SafetyRefusalData };

export interface StudyReadingNote {
  note_id: string;
  document_id: string;
  page: number;
  selection: string;
  note: string;
  created_at: string;
  section_id?: string;
}

export interface StudyDocumentHighlight {
  highlight_id: string;
  document_id: string;
  page: number;
  selected_text: string;
  context?: string;
  color?: string;
  created_at?: string;
}

export type {
  ActiveTemplate,
  Agent,
  ArenaModelData,
  ArenaState,
  AstState,
  ChatMessage,
  KanbanCard,
  KanbanState,
  PlannerState,
  RuleMemory,
  Task,
  TemplateSuggestion,
  VaultDiagnosticsData,
  NoteImprovementItem,
  NoteQualityAuditMessage,
  NoteEnrichmentResultMessage,
} from '../protocol/websocket';

interface WebSocketContextType {
  isConnected: boolean;
  systemStatus: SystemStatus;
  voiceStatus: string;
  chatMessages: ChatMessage[];
  systemLogs: SystemLogEntry[];
  clearSystemLogs: () => void;
  chatSessions: ChatSession[];
  activeSessionId: string;
  switchChatSession: (sessionId: string) => void;
  createNewChatSession: (title?: string) => string;
  deleteChatSession: (sessionId: string) => void;
  renameChatSession: (sessionId: string, newTitle: string) => void;
  promptHistory: string[];
  debateMessages: ChatMessage[];
  safetyRefusal: SafetyRefusalData | null;
  clearSafetyRefusal: () => void;
  codingSessionError: string | null;
  clearCodingSessionError: () => void;
  projectFiles: { [filename: string]: string };
  projectFileHashes: { [filename: string]: string };
  projectFileSaveState: ProjectFileSaveState | null;
  isSavingProjectFile: boolean;
  activeTemplate: ActiveTemplate | null;
  kanban: KanbanState;
  arena: ArenaState;
  projectOutput: string;
  isProjectRunning: boolean;
  previewUrl: string;
  chatPanelOpen: boolean;
  setChatPanelOpen: (open: boolean) => void;
  devPanelOpen: boolean;
  setDevPanelOpen: (open: boolean) => void;
  sendDirective: (text: string, attachments?: ChatAttachment[]) => void;
  selectTemplate: (templateName: string) => void;
  toggleVoice: (active: boolean) => void;
  runProject: (projectId?: string) => void;
  stopProject: () => void;
  clearChat: () => void;
  notes: string[];
  rules: RuleMemory[];
  architecture: ArchitectureMemory[];
  decisions: EngineeringDecision[];
  currentNote: { filename: string; content: string } | null;
  vaultDiagnostics: VaultDiagnosticsData | null;
  vaultImprovementQueue: NoteImprovementItem[];
  noteQualityAudit: NoteQualityAuditMessage['audit'] | null;
  noteEnrichmentProposal: NoteEnrichmentResultMessage['proposal'] | null;
  isAuditingNote: boolean;
  isEnrichingNote: boolean;
  getVaultDiagnostics: () => void;
  auditNoteQuality: (filename: string) => void;
  enrichNote: (filename: string, autoApply?: boolean) => void;
  rollbackNote: (filename: string, backupPath?: string) => void;
  pauseQueueWorker: () => void;
  resumeQueueWorker: () => void;
  startImprovementBatch: (batchSize?: number) => void;
  getQueueStatus: () => void;
  getNotes: () => void;
  readNote: (filename: string) => Promise<string>;
  saveNote: (filename: string, content: string) => void;
  deleteRule: (key: string) => void;
  deleteArchitecture: (module: string) => void;
  deleteDecision: (decision: string) => void;
  plannerState: PlannerState | null;
  astState: AstState | null;
  getPlannerState: () => void;
  missions: MissionData[];
  missionSnapshot: MissionSnapshot | null;
  architectureSnapshot: ArchitectureSnapshot | null;
  getMissions: (projectId?: string) => void;
  openMission: (missionId: string) => void;
  deleteMission: (missionId: string, projectId?: string) => void;
  cancelMissionExecution: (missionId: string, executionId: string, projectId?: string) => void;
  sendMissionOperation: (operation: MissionClientOperation) => void;
  subdagHistory: ExpansionRecord[];
  getSubDagHistory: (missionId: string) => void;
  adaptationHistory: AdaptationRecordData[];
  planEvaluationResult: Record<string, unknown> | null;
  evaluateMissionPlan: (missionId: string, options?: { observations?: unknown[]; requirement_change?: string; architecture_change?: unknown }) => void;
  proposeMissionAdaptation: (missionId: string, proposal: unknown) => void;
  getMissionAdaptationHistory: (missionId: string) => void;
  getAstState: () => void;
  sandboxStatus: { mode: 'docker' | 'local_fallback'; port: number; is_docker: boolean } | null;
  projects: ProjectSummary[];
  projectContext: ProjectContextData | null;
  projectReferences: ProjectReferenceResult | null;
  semanticResults: string;
  isIndexingProject: boolean;
  listProjects: () => void;
  openProject: (projectId: string) => void;
  createProject: (projectId: string, projectName?: string, template?: string) => void;
  deleteProject: (projectId: string) => void;
  saveProjectFile: (filename: string, content: string) => void;
  createProjectFile: (filename: string, content?: string) => void;
  renameProjectFile: (oldFilename: string, newFilename: string) => void;
  deleteProjectFile: (filename: string) => void;
  reindexProject: () => void;
  findReferences: (symbol: string) => void;
  semanticSearch: (query: string) => void;
  codingSession: CodingSessionData | null;
  isCodingSessionBusy: boolean;
  createCodingSession: (objective: string) => void;
  applyCodingSession: () => void;
  rollbackCodingSession: () => void;
  activeLecture: LectureLessonData | null;
  lectureQuizResult: LectureQuizResult | null;
  lectureHistory: LectureHistoryItem[];
  isGeneratingLecture: boolean;
  isSubmittingQuiz: boolean;
  isRecordingLecture: boolean;
  generateLectureLesson: (topic: string, subject?: string, professor?: string) => void;
  submitLectureQuiz: (topic: string, answers: Record<string, number>, transferAnswer: string) => void;
  listLectureHistory: () => void;
  startLectureRecording: (subject?: string, title?: string, professor?: string) => void;
  stopLectureRecording: () => void;
  setActiveLecture: React.Dispatch<React.SetStateAction<LectureLessonData | null>>;
  sentinelStatus: SentinelStatusData | null;
  sentinelEvents: SentinelSecurityEventData[];
  sentinelBaseline: Record<string, unknown> | null;
  sentinelActions: SentinelActionData[];
  isSentinelAuditing: boolean;
  getSentinelStatus: () => void;
  runSentinelAudit: () => void;
  getSentinelBaseline: () => void;
  acceptSentinelKnownGood: (itemKey: string, reason?: string) => void;
  getSentinelActions: () => void;
  approveSentinelAction: (actionId: string, user?: string, sessionId?: string, incidentId?: string) => void;
  rejectSentinelAction: (actionId: string, reason: string, user?: string) => void;
  rollbackSentinelAction: (actionId: string, user?: string, sessionId?: string) => void;
  submitSentinelReview: (eventId: string, finalClassification: string, reason: string, operator?: string) => void;
  missionControlState: MissionControlStateData | null;
  missionControlCommandResult: MissionControlCommandResultData | null;
  sendMissionControlCommand: (cmd: MissionControlCommandPayload) => void;
  getMissionControlState: (scenario?: string) => void;
  clearMissionControlCommandResult: () => void;
  missionIntentPreviewResult: MissionIntentPreviewResultMessage | null;
  missionIntentResult: MissionIntentResultMessage | null;
  sendMissionIntentPreview: (missionId: string, textOrDelta: string | Record<string, unknown>) => void;
  sendMissionIntentChange: (missionId: string, textOrDelta: string | Record<string, unknown>, preApproved?: boolean) => void;
  clearMissionIntentPreviewResult: () => void;
  clearMissionIntentResult: () => void;
  studyDocuments: StudyDocument[];
  activeStudyQuiz: StudyQuiz | null;
  studyQuizResult: QuizEvaluationResult | null;
  studyFlashcards: Flashcard[];
  listStudyDocuments: () => void;
  uploadStudyDocument: (
    filename: string,
    title?: string,
    subject?: string,
    contentBase64?: string,
    contentText?: string,
    sourceType?: string,
    filePath?: string
  ) => void;
  ingestStudyVideoUrl: (
    url: string,
    title?: string,
    subject?: string,
    collectionId?: string
  ) => Promise<any>;
  lastStudyDocumentError: { filename: string; error: string; ts: number } | null;
  deleteStudyDocument: (documentId: string, deleteFile?: boolean) => void;
  generateStudyQuiz: (documentId: string, count?: number) => Promise<StudyQuiz>;
  submitStudyQuiz: (quizId: string, answers: Record<string, number | string>, transferAnswer?: string) => Promise<QuizEvaluationResult>;
  searchStudyRag: (query: string, documentId?: string) => Promise<Array<{ text: string; source: string; score?: number; title?: string }>>;
  listStudyFlashcards: (documentId: string) => void;
  reviewStudyFlashcard: (cardId: string, rating: string) => void;
  contextualAssist: (
    documentId: string,
    action: string,
    selectedText: string,
    options?: {
      sectionId?: string;
      pageNumber?: number;
      level?: string;
      targetLanguage?: string;
      mediaId?: string;
    }
  ) => Promise<any>;
  askStudyPaper: (
    documentId: string,
    question: string,
    sectionId?: string
  ) => Promise<{ answer: string; sources: string[] }>;
  getStudyDocumentFile: (
    documentId: string
  ) => Promise<{ contentBase64?: string; filename?: string; error?: string }>;
  generateStudyCornell: (documentId: string) => Promise<any>;
  generateStudySummary: (
    documentId: string,
    mode?: 'Quick' | 'Study' | 'Detailed' | 'Exam',
    forceRegenerate?: boolean
  ) => Promise<any>;
  synthesizeStudyDocuments: (documentIds: string[]) => Promise<{
    common_points: string[];
    differences: string[];
    shared_concepts: string[];
    contradictions: string[];
    idea_evolution: string[];
  }>;
  saveToStudyVault: (data: {
    title: string;
    markdown_content: string;
    subject?: string;
    source_document_ids?: string[];
  }) => Promise<boolean>;
  studyCollections: StudyCollection[];
  listStudyCollections: () => void;
  createStudyCollection: (name: string, subject?: string, documentIds?: string[]) => void;
  linkStudyFolder: (collectionId: string, folderPath: string, syncEnabled?: boolean, recursive?: boolean) => Promise<any>;
  unlinkStudyFolder: (collectionId: string, folderPath: string, removeMaterials?: boolean) => Promise<any>;
  syncStudyFolder: (collectionId: string, folderPath?: string) => Promise<any>;
  askStudyCourse: (collectionId: string, question: string) => Promise<any>;
  retryStudyDocument: (documentId: string) => Promise<any>;
  cancelStudyGeneration: (documentId: string) => void;
  getStudyEditorialPlan: (documentId: string) => Promise<{
    plan: EditorialStudyPlan | null;
    plan_status: EditorialPlanStatus | null;
  }>;
  generateStudyEditorialPlan: (
    documentId: string,
    forceRecompute?: boolean,
    autoGenerateDossier?: boolean
  ) => Promise<{
    plan: EditorialStudyPlan | null;
    plan_status: EditorialPlanStatus | null;
  }>;
  getGeneratedStudyDocumentStatus: (documentId: string) => Promise<StudyDocumentGenerationStatus | null>;
  generateStudyDocument: (
    documentId: string,
    options?: {
      forceRecompute?: boolean;
      autoGeneratePlan?: boolean;
      designProfileId?: string;
      exportDocx?: boolean;
    }
  ) => Promise<{
    result: StudyDocumentGenerationResult | null;
    status: StudyDocumentGenerationStatus | null;
  }>;
  getGeneratedStudyDocumentFile: (
    documentId: string,
    format?: 'pdf' | 'docx',
    version?: number
  ) => Promise<StudyDocumentFilePayload | null>;
  studyModesApi: StudyModesBridge;
  studyPipelineStage: string;
  studyOperations: Record<string, StudyOperationStatusPayload>;
  studyNavigationTarget: (StudyNavigatePayload & { nonce: number }) | null;
  studyReadingNotes: Record<string, StudyReadingNote[]>;
  studyHighlights: Record<string, StudyDocumentHighlight[]>;
  getStudyDocumentDetails: (documentId: string) => void;
  addStudyReadingNote: (documentId: string, page: number, note: string, selection?: string, sectionId?: string) => void;
  addStudyHighlight: (documentId: string, page: number, selectedText: string, context?: string, color?: string) => void;
  updateActiveStudyContext: (ctx: StudyUiContextPayload) => void;
  navigateToStudyTarget: (target: Partial<StudyNavigatePayload>) => void;
  cancelStudyOperation: (operationId: string, documentId?: string) => void;
  activeDomain: SpatialBoardDomain;
  setActiveDomain: (domain: SpatialBoardDomain) => void;
  spatialOverviewOpen: boolean;
  setSpatialOverviewOpen: (open: boolean) => void;
  activeBoard: SpatialBoardData | null;
  focusedCardId: string | null;
  openSpatialBoard: (domain?: SpatialBoardDomain, query?: string) => void;
  closeSpatialBoard: () => void;
  focusSpatialCard: (cardIdOrQuery: string | null) => void;
  approvePermissionRequest: (requestId: string, projectId?: string, missionId?: string) => void;
  denyPermissionRequest: (requestId: string, reason?: string, projectId?: string, missionId?: string) => void;
  rollbackPermissionRequest: (requestId: string) => void;
  getPendingPermissions: () => void;
  sendClientMessage: (msg: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

const MAX_CHAT_MESSAGES = 200;
const MAX_DEBATE_MESSAGES = 200;

const appendLimited = <T,>(items: T[], item: T, limit: number): T[] => {
  return [...items, item].slice(-limit);
};

// eslint-disable-next-line react-refresh/only-export-components
export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within a WebSocketProvider');
  return context;
};

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>('OFFLINE');
  const [voiceStatus, setVoiceStatus] = useState('offline');
  const [chatSessions, setChatSessions] = useState<ChatSession[]>(() => {
    const loaded = loadStoredChatSessions();
    return loaded.length > 0 ? loaded : [createDefaultSession()];
  });
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const loaded = loadStoredChatSessions();
    return loaded.length > 0 ? loaded[0].id : generateSessionId();
  });
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
    const loaded = loadStoredChatSessions();
    return loaded.length > 0 ? loaded[0].messages : [];
  });
  const [systemLogs, setSystemLogs] = useState<SystemLogEntry[]>([]);
  const [promptHistory, setPromptHistory] = useState<string[]>(() => loadStoredPromptHistory());
  const [debateMessages, setDebateMessages] = useState<ChatMessage[]>([]);
  const [projectFiles, setProjectFiles] = useState<{ [filename: string]: string }>({});
  const [projectFileHashes, setProjectFileHashes] = useState<{ [filename: string]: string }>({});
  const [projectFileSaveState, setProjectFileSaveState] = useState<ProjectFileSaveState | null>(null);
  const [isSavingProjectFile, setIsSavingProjectFile] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<ActiveTemplate | null>(null);
  const [projectOutput, setProjectOutput] = useState<string>('');
  const [isProjectRunning, setIsProjectRunning] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('about:blank');
  const [chatPanelOpen, setChatPanelOpen] = useState(false);
  const [devPanelOpen, setDevPanelOpen] = useState(false);
  const [sentinelStatus, setSentinelStatus] = useState<SentinelStatusData | null>(null);
  const [sentinelEvents, setSentinelEvents] = useState<SentinelSecurityEventData[]>([]);
  const [sentinelBaseline, setSentinelBaseline] = useState<Record<string, unknown> | null>(null);
  const [sentinelActions, setSentinelActions] = useState<SentinelActionData[]>([]);
  const [isSentinelAuditing, setIsSentinelAuditing] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const [rules, setRules] = useState<RuleMemory[]>([]);
  const [architecture, setArchitecture] = useState<ArchitectureMemory[]>([]);
  const [decisions, setDecisions] = useState<EngineeringDecision[]>([]);
  const [currentNote, setCurrentNote] = useState<{ filename: string; content: string } | null>(null);
  const [vaultDiagnostics, setVaultDiagnostics] = useState<VaultDiagnosticsData | null>(null);
  const [vaultImprovementQueue, setVaultImprovementQueue] = useState<NoteImprovementItem[]>([]);
  const [noteQualityAudit, setNoteQualityAudit] = useState<NoteQualityAuditMessage['audit'] | null>(null);
  const [noteEnrichmentProposal, setNoteEnrichmentProposal] = useState<NoteEnrichmentResultMessage['proposal'] | null>(null);
  const [isAuditingNote, setIsAuditingNote] = useState(false);
  const [isEnrichingNote, setIsEnrichingNote] = useState(false);
  const [plannerState, setPlannerState] = useState<PlannerState | null>(null);
  const [missions, setMissions] = useState<MissionData[]>([]);
  const [missionSnapshot, setMissionSnapshot] = useState<MissionSnapshot | null>(null);
  const [subdagHistory, setSubdagHistory] = useState<ExpansionRecord[]>([]);
  const [adaptationHistory, setAdaptationHistory] = useState<AdaptationRecordData[]>([]);
  const [planEvaluationResult, setPlanEvaluationResult] = useState<Record<string, unknown> | null>(null);
  const [astState, setAstState] = useState<AstState | null>(null);
  const [architectureSnapshot, setArchitectureSnapshot] = useState<ArchitectureSnapshot | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectContext, setProjectContext] = useState<ProjectContextData | null>(null);
  const [projectReferences, setProjectReferences] = useState<ProjectReferenceResult | null>(null);
  const [semanticResults, setSemanticResults] = useState('');
  const [isIndexingProject, setIsIndexingProject] = useState(false);
  const [sandboxStatus, setSandboxStatus] = useState<{ mode: 'docker' | 'local_fallback'; port: number; is_docker: boolean } | null>(null);
  const [codingSession, setCodingSession] = useState<CodingSessionData | null>(null);
  const [isCodingSessionBusy, setIsCodingSessionBusy] = useState(false);
  const [safetyRefusal, setSafetyRefusal] = useState<SafetyRefusalData | null>(null);
  const clearSafetyRefusal = useCallback(() => setSafetyRefusal(null), []);
  const [codingSessionError, setCodingSessionError] = useState<string | null>(null);
  const clearCodingSessionError = useCallback(() => setCodingSessionError(null), []);
  const [activeLecture, setActiveLecture] = useState<LectureLessonData | null>(null);
  const [lectureQuizResult, setLectureQuizResult] = useState<LectureQuizResult | null>(null);
  const [lectureHistory, setLectureHistory] = useState<LectureHistoryItem[]>([]);
  const [isGeneratingLecture, setIsGeneratingLecture] = useState(false);
  const [isSubmittingQuiz, setIsSubmittingQuiz] = useState(false);
  const [isRecordingLecture, setIsRecordingLecture] = useState(false);
  const [missionControlState, setMissionControlState] = useState<MissionControlStateData | null>(null);
  const [missionControlCommandResult, setMissionControlCommandResult] = useState<MissionControlCommandResultData | null>(null);
  const [missionIntentPreviewResult, setMissionIntentPreviewResult] = useState<MissionIntentPreviewResultMessage | null>(null);
  const [missionIntentResult, setMissionIntentResult] = useState<MissionIntentResultMessage | null>(null);
  const [studyDocuments, setStudyDocuments] = useState<StudyDocument[]>([]);
  const [studyCollections, setStudyCollections] = useState<StudyCollection[]>([]);
  const [activeStudyQuiz, setActiveStudyQuiz] = useState<StudyQuiz | null>(null);
  const [studyQuizResult, setStudyQuizResult] = useState<QuizEvaluationResult | null>(null);
  const [studyFlashcards, setStudyFlashcards] = useState<Flashcard[]>([]);
  const [studyPipelineStage, setStudyPipelineStage] = useState<string>('');
  const [lastStudyDocumentError, setLastStudyDocumentError] = useState<{ filename: string; error: string; ts: number } | null>(null);
  const [studyOperations, setStudyOperations] = useState<Record<string, StudyOperationStatusPayload>>({});
  const [studyNavigationTarget, setStudyNavigationTarget] = useState<(StudyNavigatePayload & { nonce: number }) | null>(null);
  const [studyReadingNotes, setStudyReadingNotes] = useState<Record<string, StudyReadingNote[]>>({});
  const [studyHighlights, setStudyHighlights] = useState<Record<string, StudyDocumentHighlight[]>>({});
  const activeStudyContextRef = useRef<StudyUiContextPayload>({});
  const [activeDomain, setActiveDomainState] = useState<SpatialBoardDomain>('study');
  const activeDomainRef = useRef<SpatialBoardDomain>('study');
  const [spatialOverviewOpen, setSpatialOverviewOpen] = useState<boolean>(false);
  const [activeBoard, setActiveBoard] = useState<SpatialBoardData | null>(null);
  const [focusedCardId, setFocusedCardId] = useState<string | null>(null);

  const [kanban, setKanban] = useState<KanbanState>({
    backlog: [],
    progress: [],
    review: [],
    done: [],
  });

  const [arena, setArena] = useState<ArenaState>({
    gemini: { status: 'IDLE', content: 'Aguardando prompt de Arena...', time: '-', tokens: '-' },
    groq: { status: 'IDLE', content: 'Aguardando prompt de Arena...', time: '-', tokens: '-' },
    qwen: { status: 'IDLE', content: 'Aguardando prompt de Arena...', time: '-', tokens: '-' },
    claude: { status: 'IDLE', content: 'Aguardando prompt de Arena...', time: '-', tokens: '-' },
  });

  const contextTransport = useOptionalTransport();
  const [ownsFallbackTransport] = useState(() => !contextTransport);
  const [transport] = useState<JarvisTransport>(
    () => contextTransport ?? new WebSocketTransportAdapter({ normalizeMessage: normalizeServerMessage })
  );

  const recentMessageHashesRef = useRef<Map<string, number>>(new Map());
  const activeProjectIdRef = useRef<string | null>(null);
  const requestedProjectIdRef = useRef<string | null>(null);

  const sendClientMessage = useCallback((message: ClientMessage) => {
    transport.send(message);
  }, [transport]);

  // Keep active chat session synced in localStorage
  useEffect(() => {
    setChatSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === activeSessionId);
      if (idx === -1) return prev;
      const updated = [...prev];
      updated[idx] = {
        ...updated[idx],
        messages: chatMessages,
        updatedAt: Date.now(),
      };
      persistChatSessions(updated);
      return updated;
    });
  }, [chatMessages, activeSessionId]);

  const switchChatSession = useCallback((sessionId: string) => {
    setChatSessions((currentSessions) => {
      const target = currentSessions.find((s) => s.id === sessionId);
      if (target) {
        setActiveSessionId(sessionId);
        setChatMessages(target.messages || []);
      }
      return currentSessions;
    });
  }, []);

  const createNewChatSession = useCallback((title?: string) => {
    const newSession: ChatSession = {
      id: generateSessionId(),
      title: title || 'Nova conversa',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
      promptHistory: [],
    };
    setChatSessions((prev) => {
      const updated = [newSession, ...prev];
      persistChatSessions(updated);
      return updated;
    });
    setActiveSessionId(newSession.id);
    setChatMessages([]);
    return newSession.id;
  }, []);

  const deleteChatSession = useCallback((sessionId: string) => {
    setChatSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== sessionId);
      const safeList = remaining.length > 0 ? remaining : [createDefaultSession()];
      persistChatSessions(safeList);
      if (sessionId === activeSessionId) {
        setActiveSessionId(safeList[0].id);
        setChatMessages(safeList[0].messages || []);
      }
      return safeList;
    });
  }, [activeSessionId]);

  const renameChatSession = useCallback((sessionId: string, newTitle: string) => {
    setChatSessions((prev) => {
      const updated = prev.map((s) => (s.id === sessionId ? { ...s, title: newTitle.trim(), updatedAt: Date.now() } : s));
      persistChatSessions(updated);
      return updated;
    });
  }, []);

  const clearSystemLogs = useCallback(() => {
    setSystemLogs([]);
  }, []);

  const addSystemLog = useCallback(
    (
      message: string,
      category: LogCategory = 'SYSTEM',
      level: LogLevel = 'info',
      source?: string,
      details?: Record<string, unknown>
    ) => {
      const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
      const newEntry: SystemLogEntry = {
        id: Math.random().toString(36).slice(2, 9),
        timestamp,
        category,
        level,
        message,
        source,
        details,
      };
      setSystemLogs((prev) => [...prev.slice(-400), newEntry]);
    },
    []
  );

  function addSystemMessage(content: string) {
    const clean = content.trim();
    if (!clean) return;

    let category: LogCategory = 'SYSTEM';
    let level: LogLevel = 'info';

    if (clean.includes('[SENTINEL') || clean.includes('Sentinel')) {
      category = 'SENTINEL';
      level = clean.includes('BENIGN') ? 'benign' : clean.includes('ERRO') || clean.includes('REJEITADA') ? 'error' : 'warning';
    } else if (clean.includes('WebSocket') || clean.includes('Conectado')) {
      category = 'WEBSOCKET';
      level = 'info';
    } else if (clean.includes('PROJECT_CONTEXT_MISSING') || clean.includes('Projeto')) {
      category = 'PROJECT';
      level = clean.includes('MISSING') || clean.includes('Erro') ? 'warning' : 'info';
    } else if (clean.includes('AUTORIZAÇÃO') || clean.includes('recusado') || clean.includes('Segurança')) {
      category = 'SECURITY';
      level = 'warning';
    } else if (
      clean.includes('Orquestra') ||
      clean.includes('Quality Gate') ||
      clean.includes('TaskState') ||
      clean.includes('Missão') ||
      clean.includes('Swarm') ||
      clean.includes('Fallback')
    ) {
      category = 'ORCHESTRATOR';
      level = clean.includes('sucesso') || clean.includes('[OK]') ? 'success' : clean.includes('erro') || clean.includes('Erro') ? 'error' : 'info';
    }

    // Always log to Central System Console (Consola Central)
    addSystemLog(clean, category, level);
  }

  function addChatMessage(msg: ChatProtocolMessage) {
    const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    const content = (msg.content || '').trim();
    const role = (msg.role || '').trim();
    const sender = (msg.sender || '').trim().toUpperCase();

    // Route internal orchestrator, swarm routing, and mission lifecycle telemetry to Consola Central
    const isOrchestratorTelemetry =
      sender === 'OPENCLAW' ||
      role === 'Orquestrador (Queen)' ||
      role === 'Queen' ||
      role === 'Missão' ||
      role === 'Mission Gate' ||
      role === 'Mission Understanding' ||
      (role === 'Orquestrador' && (
        content.startsWith('Processando pedido:') ||
        content.startsWith('👑') ||
        content.startsWith('Rota determinada:') ||
        content.startsWith('Fallback cloud ativo:') ||
        content.startsWith('A executar:') ||
        content.startsWith('[OK]') ||
        content.startsWith('[WARNING]') ||
        content.startsWith('🎯') ||
        content.startsWith('🧠 **Spawning**') ||
        content.startsWith('Limite atingido')
      )) ||
      content.startsWith('🚀 Missão criada:') ||
      content.startsWith('✅ Missão') ||
      content.startsWith('⚠️ Missão') ||
      content.startsWith('⛔ Missão') ||
      content.startsWith('[OPENCLAW');

    if (isOrchestratorTelemetry) {
      const level: LogLevel = content.includes('✅') || content.includes('[OK]')
        ? 'success'
        : content.includes('⚠️') || content.includes('Fallback')
        ? 'warning'
        : content.includes('⛔') || content.includes('Erro') || content.includes('falhou')
        ? 'error'
        : 'info';
      addSystemLog(content, 'ORCHESTRATOR', level);
      return;
    }

    const newMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: msg.sender,
      role: msg.role,
      content: msg.content,
      audio: msg.audio,
      timestamp,
      study_card: msg.study_card,
    };

    // Add genuine conversational messages to chatMessages
    setChatMessages((prev) => appendLimited(prev, newMsg, MAX_CHAT_MESSAGES));

    // Check if message is a specialist/subagent or contains multi-agent dialogue tags
    const agentTags = ['[DEVON]', '[QUINN]', '[SWARM]', '[CLARA]', '[ALEX]', '[MARTA]', '[GUSTAVO]', '[DUARTE]', '[INÊS]', '[INES]', '[PRODUCT]', '[QA]', '[DEV]', '[DESIGN]'];
    const hasAgentTag = agentTags.some((tag) => msg.content && msg.content.includes(tag));
    const isSpecialistSender = !['JARVIS', 'SISTEMA', 'CLIENTE', 'USER', 'ASSISTANT'].includes(msg.sender.toUpperCase());

    if (isSpecialistSender || hasAgentTag || msg.role === 'Specialist' || msg.role === 'Debate') {
      if (hasAgentTag && msg.content) {
        // Parse individual agent dialogue turns from content into distinct debate bubbles
        const regex = /\[([A-ZÇÃÕÁÉÍÓÚ_]+)\]([\s\S]*?)(?=\[[A-ZÇÃÕÁÉÍÓÚ_]+\]|$)/g;
        let match;
        let foundAny = false;
        while ((match = regex.exec(msg.content)) !== null) {
          const agentName = match[1].trim();
          const turnContent = match[2].trim();
          if (turnContent && !['JARVIS', 'ASSISTANT', 'OPENCLAW'].includes(agentName.toUpperCase())) {
            foundAny = true;
            const debateMsg: ChatMessage = {
              id: Math.random().toString(),
              sender: agentName.charAt(0) + agentName.slice(1).toLowerCase(),
              role: 'Especialista',
              content: turnContent,
              timestamp,
            };
            setDebateMessages((prev) => appendLimited(prev, debateMsg, MAX_DEBATE_MESSAGES));
          }
        }
        if (!foundAny) {
          setDebateMessages((prev) => appendLimited(prev, newMsg, MAX_DEBATE_MESSAGES));
        }
      } else {
        setDebateMessages((prev) => appendLimited(prev, newMsg, MAX_DEBATE_MESSAGES));
      }
    }
  }

  function handleKanbanUpdate(cardId: string, status: KanbanColumn | string) {
    setKanban((prev) => {
      // Find and remove from existing columns
      let cardToMove: KanbanCard | null = null;
      const cleanState: KanbanState = {
        backlog: prev.backlog.filter((c) => {
          if (c.id === cardId) {
            cardToMove = c;
            return false;
          }
          return true;
        }),
        progress: prev.progress.filter((c) => {
          if (c.id === cardId) {
            cardToMove = c;
            return false;
          }
          return true;
        }),
        review: prev.review.filter((c) => {
          if (c.id === cardId) {
            cardToMove = c;
            return false;
          }
          return true;
        }),
        done: prev.done.filter((c) => {
          if (c.id === cardId) {
            cardToMove = c;
            return false;
          }
          return true;
        }),
      };

      if (!cardToMove) {
        // Create dynamic card if it doesn't exist
        cardToMove = {
          id: cardId,
          title: cardId.replace('task_', '').replace(/_/g, ' '),
          agent: 'pm',
        };
      }

      const targetCol = status as keyof KanbanState;
      if (cleanState[targetCol]) {
        cleanState[targetCol] = [...cleanState[targetCol], cardToMove];
      }

      return cleanState;
    });
  }

  function handleUiAction(action: UiAction) {
    if (action === 'open_chat') {
      setChatPanelOpen(true);
    } else if (action === 'close_chat') {
      setChatPanelOpen(false);
    } else if (action === 'toggle_chat') {
      setChatPanelOpen((prev) => !prev);
    } else if (action === 'open_dev') {
      setDevPanelOpen(true);
    } else if (action === 'close_dev') {
      setDevPanelOpen(false);
      setActiveBoard(null);
      setFocusedCardId(null);
    } else if (action === 'toggle_dev') {
      setDevPanelOpen((prev) => !prev);
    } else if (action === 'show_dashboard' || action === 'show_arena_tab') {
      setDevPanelOpen(true);
    } else if (action === 'show_main_screen') {
      setChatPanelOpen(false);
      setDevPanelOpen(false);
      setActiveBoard(null);
      setFocusedCardId(null);
    }
  }

  function handleTemplateChanged(msg: TemplateChangedMessage) {
    setActiveTemplate({
      template_name: msg.template_name,
      name: msg.name,
      description: msg.description,
      suggestions: msg.suggestions,
      agents: msg.agents,
    });

    if (!activeProjectIdRef.current && !requestedProjectIdRef.current) {
      setProjectFiles({});
      setProjectOutput('');
      setIsProjectRunning(false);
      setPreviewUrl('about:blank');
    }

    const initialBacklog = msg.tasks.map((t) => ({
      id: t.id,
      title: t.title,
      agent: t.agent || 'pm',
    }));

    setKanban({
      backlog: initialBacklog,
      progress: [],
      review: [],
      done: [],
    });
  }

  function handleArenaUpdate(msg: ArenaUpdateMessage) {
    const model = msg.model_id;
    const knownModels: Array<keyof ArenaState> = ['gemini', 'groq', 'qwen', 'claude'];
    if (!knownModels.includes(model)) {
      console.warn('[WebSocket] Unknown arena model:', model);
      return;
    }

    setArena((prev) => ({
      ...prev,
      [model]: {
        status: msg.status.toUpperCase(),
        content: msg.content,
        time: msg.time,
        tokens: msg.tokens,
      },
    }));
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleServerMessage = useCallback((msg: any) => {
    if (!msg || !msg.type) return;

    // Deduplicate identical append/event messages arriving within 1.5s via dual transport (Electron IPC + WebSocket).
    // Never deduplicate idempotent state-hydration snapshots (project_context, coding_session, mission_list, etc.).
    const DEDUP_EVENT_TYPES = new Set([
      'system',
      'chat',
      'kanban',
      'project_output',
      'voice_status',
      'ui_theme',
      'complete',
      'mission_event',
      'sentinel_event',
      'sentinel_audit_completed',
      'sentinel_known_good_updated',
      'sentinel_action_proposed',
      'sentinel_action_result',
      'mission_control_command_result',
      'mission_intent_result',
      'permission_request_created',
      'action_confirm_request',
      'permission_request_approved',
      'permission_request_denied',
      'permission_request_expired',
      'permission_capability_result',
      'permission_execution_result',
      'coding_session_error',
      'study_document_ready',
      'study_document_uploaded',
      'study_document_deleted',
      'study_document_processing',
      'study_document_failed',
      'study_video_url_ingested',
      'study_generation_cancelled',
      'study_error',
    ]);
    if (DEDUP_EVENT_TYPES.has(msg.type)) {
      const eventKey = msg.event?.sequence ?? msg.event?.fingerprint ?? '';
      const reqOrActionId = msg.request_id || msg.action_id || msg.action?.action_id || msg.request?.request_id || '';
      const docOrFileKey = msg.document?.document_id || msg.document_id || msg.filename || '';
      const rawKey = `${msg.type}:${msg.sender || ''}:${msg.content || ''}:${msg.card_id || ''}:${msg.status || ''}:${eventKey}:${reqOrActionId}:${docOrFileKey}`;
      const now = Date.now();
      const lastSeen = recentMessageHashesRef.current.get(rawKey);
      if (lastSeen && now - lastSeen < 1500) {
        return;
      }
      recentMessageHashesRef.current.set(rawKey, now);
      if (recentMessageHashesRef.current.size > 200) {
        for (const [k, t] of recentMessageHashesRef.current.entries()) {
          if (now - t > 5000) recentMessageHashesRef.current.delete(k);
        }
      }
    }

    switch (msg.type) {
      case 'system':
        addSystemMessage(msg.content);
        setIsCodingSessionBusy(false);
        break;
      case 'chat':
        addChatMessage(msg);
        break;
      case 'file':
        setProjectFiles((prev) => ({
          ...prev,
          [msg.filename]: msg.content,
        }));
        break;
      case 'kanban':
        handleKanbanUpdate(msg.card_id, msg.status);
        break;
      case 'state':
        if (msg.value === 'processing') {
          setSystemStatus('PROCESSING');
        } else {
          setSystemStatus('ONLINE');
        }
        break;
      case 'voice_status':
        setVoiceStatus(msg.status);
        if (msg.status === 'transcribed' && msg.text) {
          addSystemMessage(`Transcrição de Voz: ${msg.text}`);
        }
        break;
      case 'template_changed':
        handleTemplateChanged(msg);
        break;
      case 'arena_update':
        handleArenaUpdate(msg);
        break;
      case 'project_output': {
        const outProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (outProjId && targetProjId && outProjId !== targetProjId) break;
        setProjectOutput((prev) => prev + msg.content);
        break;
      }
      case 'project_status': {
        const statusProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (statusProjId && targetProjId && statusProjId !== targetProjId) break;
        setIsProjectRunning(Boolean(msg.running));
        if (msg.preview_url) {
          setPreviewUrl(msg.preview_url);
        } else if (!msg.running) {
          setPreviewUrl('about:blank');
        }
        break;
      }
      case 'ui':
      case 'ui_action':
        handleUiAction(msg.action);
        break;
      case 'ui_theme':
        addSystemMessage(`Tema visual solicitado: ${msg.theme}`);
        break;
      case 'complete':
        addSystemMessage(`Orquestração concluída: ${msg.result || 'Sucesso'}`);
        break;
      case 'notes_list':
        setNotes(msg.notes);
        break;
      case 'note_content': {
        setCurrentNote({ filename: msg.filename, content: msg.content });
        break;
      }
      case 'vault_diagnostics':
        setVaultDiagnostics(msg.diagnostics);
        setVaultImprovementQueue(msg.queue);
        break;
      case 'queue_worker_status':
        if (msg.queue) {
          setVaultImprovementQueue(msg.queue);
        }
        if (msg.worker_state) {
          setVaultDiagnostics((prev) => (prev ? { ...prev, queue_metrics: msg.worker_state } : null));
        }
        break;
      case 'improvement_batch_result':
        if (msg.diagnostics) {
          setVaultDiagnostics(msg.diagnostics);
        }
        break;
      case 'note_quality_audit':
        setNoteQualityAudit(msg.audit);
        setIsAuditingNote(false);
        break;
      case 'note_enrichment_result':
        setNoteEnrichmentProposal(msg.proposal);
        setIsEnrichingNote(false);
        break;
      case 'note_rollback_result':
        if (msg.success) {
          getNotes();
        }
        break;
      case 'rules_list':
        setRules(msg.rules);
        break;
      case 'rules_updated':
        setRules(msg.rules);
        break;
      case 'architecture_list':
        setArchitecture(msg.architecture);
        break;
      case 'architecture_updated':
        setArchitecture(msg.architecture);
        break;
      case 'decisions_list':
        setDecisions(msg.decisions);
        break;
      case 'decisions_updated':
        setDecisions(msg.decisions);
        break;
      case 'planner_state':
        setPlannerState(msg.data);
        break;
      case 'mission_list': {
        const listProjId = msg.project_id ? String(msg.project_id) : '';
        const isGlobalList = !listProjId || listProjId.toUpperCase() === 'ALL' || listProjId === '*';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (!isGlobalList && targetProjId && listProjId !== targetProjId) {
          break;
        }
        setMissions(msg.missions);
        missionRuntimeStore.setMissions(msg.missions);
        break;
      }
      case 'mission_snapshot':
        setMissionSnapshot(msg.data);
        missionRuntimeStore.setMissionSnapshot(msg.data);
        break;
      case 'mission_event': {
        missionRuntimeStore.applyEvent(msg.event, (pId, mId) => {
          sendClientMessage({ type: 'mission_resume_snapshot', project_id: pId, mission_id: mId });
        });
        const snap = missionRuntimeStore.getSnapshot();
        if (snap.missions.length > 0) {
          setMissions(snap.missions);
        }
        if (snap.selectedMissionSnapshot) {
          setMissionSnapshot(snap.selectedMissionSnapshot);
        }
        break;
      }
      case 'mission_deleted':
        missionRuntimeStore.removeMission(msg.mission_id);
        setMissions((prev) => prev.filter((m) => m.mission_id !== msg.mission_id));
        setMissionSnapshot((prev) => (prev?.mission?.mission_id === msg.mission_id ? null : prev));
        break;
      case 'mission_subdag_history':
        setSubdagHistory(msg.history);
        break;
      case 'mission_subdag_proposal_result':
        if (msg.success) {
          addSystemMessage(`[SUB-DAG EXPANSÃO APLICADA] ${msg.message}`);
        } else {
          addSystemMessage(`[SUB-DAG EXPANSÃO REJEITADA] ${msg.message}`);
        }
        break;
      case 'mission_adaptation_history':
        setAdaptationHistory(msg.history);
        break;
      case 'mission_adaptation_proposal_result':
        if (msg.success) {
          addSystemMessage(`[PLANO ADAPTADO] ${msg.message}`);
        } else {
          addSystemMessage(`[ADAPTAÇÃO REJEITADA] ${msg.message}`);
        }
        break;
      case 'mission_plan_evaluation_result':
        setPlanEvaluationResult(msg.result);
        addSystemMessage(`[AVALIAÇÃO DO PLANO: ${msg.result.decision}] ${msg.result.reason}`);
        break;
      case 'ast_state': {
        const astProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (astProjId && targetProjId && astProjId !== targetProjId) break;
        setAstState(msg.data);
        break;
      }
      case 'projects_list':
        setProjects(msg.projects);
        break;
      case 'project_deleted':
        if (msg.was_active || msg.project_id === projectContext?.project_id || msg.project_id === activeProjectIdRef.current) {
          activeProjectIdRef.current = null;
          if (requestedProjectIdRef.current === msg.project_id) {
            requestedProjectIdRef.current = null;
          }
          setProjectContext(null);
          setProjectFiles({});
          setProjectFileHashes({});
          setProjectFileSaveState(null);
          setAstState(null);
          setArchitectureSnapshot(null);
          setProjectReferences(null);
          setSemanticResults('');
          setProjectOutput('');
          setPreviewUrl('about:blank');
          setIsProjectRunning(false);
          setCodingSession(null);
          setMissions([]);
          setMissionSnapshot(null);
        }
        addSystemMessage(`Projeto '${msg.project_id}' eliminado com sucesso.`);
        break;
      case 'project_delete_error':
        addSystemMessage(`[Erro ao eliminar projeto] ${msg.error}`);
        break;
      case 'project_file_deleted':
        addSystemMessage(`Ficheiro '${msg.filename}' eliminado com sucesso.`);
        break;
      case 'project_file_delete_error':
        addSystemMessage(`[Erro ao eliminar ficheiro] ${msg.error}`);
        break;
      case 'project_context': {
        const incomingProjectId = msg.context?.project_id || null;
        if (
          requestedProjectIdRef.current
          && incomingProjectId
          && incomingProjectId !== requestedProjectIdRef.current
        ) {
          break;
        }
        activeProjectIdRef.current = incomingProjectId;
        requestedProjectIdRef.current = null;
        setProjectContext(msg.context);
        setProjectFiles(msg.files);
        setProjectFileHashes(msg.file_hashes);
        setAstState(Object.keys(msg.symbols).length > 0 ? msg.symbols : null);
        if (msg.architecture_snapshot) {
          setArchitectureSnapshot(msg.architecture_snapshot);
        }
        setProjectReferences(null);
        setSemanticResults('');
        setIsIndexingProject(false);
        break;
      }
      case 'architecture_snapshot': {
        const archProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (archProjId && targetProjId && archProjId !== targetProjId) break;
        setArchitectureSnapshot(msg.data);
        break;
      }
      case 'project_file_save_result':
        setProjectFileSaveState({
          ok: msg.ok,
          filename: msg.filename,
          sha256: msg.sha256,
          error: msg.error,
        });
        setIsSavingProjectFile(false);
        break;
      case 'project_references': {
        const refProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (refProjId && targetProjId && refProjId !== targetProjId) break;
        setProjectReferences(msg.data);
        break;
      }
      case 'semantic_results': {
        const semProjId = msg.project_id ? String(msg.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (semProjId && targetProjId && semProjId !== targetProjId) break;
        setSemanticResults(msg.content);
        break;
      }
      case 'coding_session': {
        const sessionProjId = msg.data?.project_id ? String(msg.data.project_id) : '';
        const targetProjId = requestedProjectIdRef.current || activeProjectIdRef.current;
        if (sessionProjId && targetProjId && sessionProjId !== targetProjId) {
          break;
        }
        setCodingSession(msg.data);
        setSafetyRefusal(null);
        setCodingSessionError(null);
        setIsCodingSessionBusy(false);
        break;
      }
      case 'coding_session_error':
        setCodingSessionError(msg.error);
        setIsCodingSessionBusy(false);
        addSystemMessage(`[Erro na Alteração Assistida] ${msg.error}`);
        break;
      case 'safety_refusal':
        setSafetyRefusal(msg.data);
        setCodingSession(null);
        setCodingSessionError(null);
        setIsCodingSessionBusy(false);
        break;
      case 'lecture_lesson_generated':
        setActiveLecture(msg.lesson);
        setIsGeneratingLecture(false);
        addSystemMessage(`Aula gerada com sucesso: ${msg.lesson.topic}`);
        break;
      case 'lecture_quiz_evaluated':
        setLectureQuizResult(msg);
        setIsSubmittingQuiz(false);
        addSystemMessage(`Quiz avaliado: ${msg.score}% de aproveitamento.`);
        break;
      case 'lecture_history_response':
        setLectureHistory(msg.history || []);
        break;
      case 'lecture_recording_started':
        setIsRecordingLecture(true);
        addSystemMessage('Gravação de aula iniciada.');
        break;
      case 'lecture_synthesis_completed':
        setIsRecordingLecture(false);
        addSystemMessage(`Síntese da aula concluída: ${msg.markdown_path}`);
        break;
      case 'lecture_status_response':
        setIsRecordingLecture(Boolean(msg.is_recording));
        break;
      case 'study_documents_list':
        setStudyDocuments(msg.documents || []);
        break;
      case 'study_document_uploaded':
        setStudyDocuments((prev) => [
          msg.document,
          ...prev.filter((d) => d.document_id !== msg.document.document_id),
        ]);
        addSystemMessage(`Documento de estudo carregado: ${msg.document.title}`);
        break;
      case 'study_document_deleted':
        setStudyDocuments((prev) => prev.filter((d) => d.document_id !== msg.document_id));
        addSystemMessage('Material removido da biblioteca de estudos.');
        break;
      case 'study_quiz_ready': {
        setActiveStudyQuiz(msg.quiz);
        addSystemMessage(`Quiz pedagógico gerado para: ${msg.quiz.topic}`);
        break;
      }
      case 'study_quiz_evaluated': {
        setStudyQuizResult(msg);
        addSystemMessage(`Quiz de estudo avaliado: ${msg.score}% de aproveitamento.`);
        break;
      }
      case 'study_search_rag_result':
        break;
      case 'study_flashcards_list':
        setStudyFlashcards(msg.flashcards || []);
        break;
      case 'study_flashcard_reviewed':
      case 'study_flashcard_updated':
        setStudyFlashcards((prev) =>
          prev.map((fc) => (fc.card_id === msg.flashcard.card_id ? msg.flashcard : fc))
        );
        break;
      case 'study_mode_progress_event': {
        const pctLabel = typeof (msg as any).progress === 'number' ? ` (${Math.round((msg as any).progress * 100)}%)` : '';
        setStudyPipelineStage(`${(msg as any).message || (msg as any).stage || 'Modo de estudo em curso'}${pctLabel}`);
        break;
      }
      case 'study_mode_readiness_result':
      case 'study_mode_flashcards_result':
      case 'study_mode_flashcard_saved':
      case 'study_mode_flashcard_deleted':
      case 'study_mode_flashcard_reviewed':
      case 'study_mode_cornell_result':
      case 'study_mode_cornell_entry_saved':
      case 'study_mode_cornell_note_saved':
      case 'study_mode_cornell_exported':
      case 'study_mode_assessments_result':
      case 'study_mode_assessment_generated':
      case 'study_mode_question_checked':
      case 'study_mode_assessment_submitted':
      case 'study_mode_active_recall_result':
      case 'study_mode_active_recall_submitted':
      case 'study_mode_daily_queue_result':
      case 'study_mode_progress_result':
      case 'study_mode_session_updated':
      case 'study_mode_sessions_list': {
        setStudyPipelineStage('');
        break;
      }
      case 'study_collections_list':
        setStudyCollections((msg as any).collections || []);
        break;
      case 'study_collection_created':
        setStudyCollections((prev) => [
          (msg as any).collection,
          ...prev.filter((c) => c.collection_id !== (msg as any).collection?.collection_id),
        ]);
        addSystemMessage(`Nova disciplina/coleção criada: ${(msg as any).collection?.name}`);
        break;
      case 'study_folder_linked': {
        addSystemMessage(`Pasta vinculada com sucesso: ${(msg as any).folder_path}`);
        break;
      }
      case 'study_folder_unlinked': {
        addSystemMessage('Pasta desvinculada. Ficheiros originais preservados no disco.');
        break;
      }
      case 'study_folder_synced':
      case 'study_ask_course_result':
        break;
      case 'study_operation_status': {
        const op = (msg as any).operation as StudyOperationStatusPayload | undefined;
        if (op?.operation_id) {
          setStudyOperations((prev) => ({
            ...prev,
            [op.operation_id]: op,
          }));
          if (op.status === 'COMPLETED') {
            sendClientMessage({ type: 'study_list_documents' });
          }
        }
        break;
      }
      case 'study_navigate': {
        const nav = (msg as any).navigation as StudyNavigatePayload | undefined;
        if (nav && nav.tab) {
          if (nav.document_id) {
            sendClientMessage({ type: 'study_list_documents' });
          }
          setStudyNavigationTarget({
            ...nav,
            nonce: Date.now() + Math.random(),
          });
        }
        break;
      }
      case 'sandbox_status':
        setSandboxStatus(msg.status);
        break;
      case 'sentinel_status':
        setSentinelStatus(msg.data);
        setIsSentinelAuditing(msg.data.is_auditing_now);
        break;
      case 'sentinel_audit_completed':
        setIsSentinelAuditing(false);
        addSystemMessage('Auditoria de segurança Sentinel concluída.');
        break;
      case 'sentinel_event':
        setSentinelEvents((prev) => {
          const filtered = prev.filter((e) => e.fingerprint !== msg.event.fingerprint);
          return [msg.event, ...filtered];
        });
        addSystemMessage(`[SENTINEL ${msg.event.severity}] ${msg.event.rationale}`);
        break;
      case 'sentinel_baseline':
        setSentinelBaseline(msg.data);
        break;
      case 'sentinel_known_good_updated':
        addSystemMessage(`[SENTINEL] Alteração aceite como Known Good: ${msg.item_key}`);
        break;
      case 'sentinel_actions_list':
        setSentinelActions(msg.data || []);
        break;
      case 'sentinel_action_proposed':
        setSentinelActions((prev) => [msg.action, ...prev.filter((a) => a.action_id !== msg.action.action_id)]);
        addSystemMessage(`[SENTINEL PROPOSTA DE RESPOSTA] ${msg.action.action_type} em ${msg.action.target}`);
        break;
      case 'sentinel_action_result':
        setSentinelActions((prev) => prev.map((a) => (a.action_id === msg.action_id ? (msg.action || a) : a)));
        if (!msg.success) {
          addSystemMessage(`[SENTINEL RESPOSTA ERRO] ${msg.message}`);
        } else {
          addSystemMessage(`[SENTINEL RESPOSTA SUCESSO] ${msg.message}`);
        }
        break;
      case 'mission_control_state':
        setMissionControlState((msg as any).state || (msg as any).data);
        break;
      case 'mission_control_command_result': {
        const cmdResult = (msg as any).result || (msg as any);
        setMissionControlCommandResult(cmdResult);
        const resStatus = cmdResult?.status;
        const resReason = cmdResult?.reason || '';
        if (resStatus === 'ACCEPTED') {
          addSystemMessage(`[MISSION CONTROL: COMANDO ACEITE] ${resReason}`);
        } else if (resStatus === 'SECURITY_BLOCK') {
          addSystemMessage(`[MISSION CONTROL: BLOQUEIO SENTINEL] ${resReason}`);
        } else if (resStatus) {
          addSystemMessage(`[MISSION CONTROL: COMANDO ${resStatus}] ${resReason}`);
        }
        break;
      }
      case 'mission_intent_preview_result':
        setMissionIntentPreviewResult(msg);
        break;
      case 'mission_intent_result':
        setMissionIntentResult(msg);
        if (msg.status === 'ACCEPTED') {
          addSystemMessage(`[DYNAMIC INTENT: ACEITE] ${msg.reason}`);
        } else if (msg.status === 'SECURITY_BLOCK') {
          addSystemMessage(`[DYNAMIC INTENT: BLOQUEIO SENTINEL] ${msg.reason}`);
        } else {
          addSystemMessage(`[DYNAMIC INTENT: ${msg.status}] ${msg.reason}`);
        }
        break;
      case 'study_document_processing':
        setStudyPipelineStage(msg.status || 'A processar documento...');
        break;
      case 'study_document_ready':
        setStudyPipelineStage('');
        setLastStudyDocumentError(null);
        if (msg.document) {
          setStudyDocuments((prev) => [
            msg.document,
            ...prev.filter((d) => d.document_id !== msg.document.document_id),
          ]);
          addSystemMessage(`Documento de estudo guardado e pronto: ${msg.document.title}`);
        }
        break;
      case 'study_video_url_ingested': {
        setStudyPipelineStage('');
        setLastStudyDocumentError(null);
        if (msg.document) {
          setStudyDocuments((prev) => [
            msg.document,
            ...prev.filter((d) => d.document_id !== msg.document.document_id),
          ]);
        }
        break;
      }
      case 'study_document_failed': {
        setStudyPipelineStage('');
        setLastStudyDocumentError({
          filename: msg.filename || '',
          error: msg.error || 'Falha ao processar documento',
          ts: Date.now(),
        });
        addSystemMessage(`Erro ao processar documento ${msg.filename}: ${msg.error}`);
        break;
      }
      case 'study_generation_cancelled': {
        setStudyPipelineStage('');
        const docId = msg.document_id || '';
        transport.cancelPendingRequests(
          (meta) => !docId || Boolean(meta.tag?.includes(docId)) || meta.requestId.includes(docId),
          'Geração cancelada pelo utilizador'
        );
        addSystemMessage(`[Estudo] Geração cancelada pelo utilizador${docId ? ` (${docId})` : ''}.`);
        break;
      }
      case 'study_contextual_assist_result':
      case 'study_ask_paper_result':
        break;
      case 'study_summary_ready': {
        const resolvedSummaries = msg.summaries || msg.summary?.summaries;
        if (resolvedSummaries && msg.document_id) {
          setStudyDocuments((prev) =>
            prev.map((d) =>
              d.document_id === msg.document_id
                ? {
                    ...d,
                    metadata: {
                      ...d.metadata,
                      summaries: resolvedSummaries,
                    },
                  }
                : d
            )
          );
        }
        break;
      }
      case 'study_synthesis_ready':
        break;
      case 'study_knowledge_saved': {
        addSystemMessage(`Nota de estudo guardada no Knowledge Vault: ${msg.title}`);
        break;
      }
      case 'study_error': {
        setStudyPipelineStage('');
        addSystemMessage(`[Estudo] ${msg.message || 'Erro ao processar operação de estudo'}`);
        break;
      }
      case 'study_editorial_plan_progress': {
        const pctLabel = typeof msg.progress === 'number' ? ` (${Math.round(msg.progress * 100)}%)` : '';
        setStudyPipelineStage(`${msg.message || msg.stage || 'Planeamento editorial em curso'}${pctLabel}`);
        break;
      }
      case 'study_editorial_plan_result': {
        setStudyPipelineStage('');
        break;
      }
      case 'study_generated_document_progress': {
        const pctLabel = typeof msg.progress === 'number' ? ` (${Math.round(msg.progress * 100)}%)` : '';
        setStudyPipelineStage(`${msg.message || msg.stage || 'Geração documental em curso'}${pctLabel}`);
        break;
      }
      case 'study_generated_document_status_result':
        break;
      case 'study_generated_document_result': {
        setStudyPipelineStage('');
        break;
      }
      case 'study_generated_document_file_result':
        break;
      case 'study_notes_ready': {
        if (msg.cornell && msg.document_id) {
          setStudyDocuments((prev) =>
            prev.map((d) =>
              d.document_id === msg.document_id
                ? {
                    ...d,
                    metadata: {
                      ...d.metadata,
                      cornell_notes: msg.cornell,
                    },
                  }
                : d
            )
          );
        }
        break;
      }
      case 'study_document_file_result':
        break;
      case 'study_document_details': {
        const doc = msg.document as StudyDocument | undefined;
        const docId = doc?.document_id;
        if (docId) {
          setStudyDocuments((prev) => {
            const exists = prev.some((d) => d.document_id === docId);
            return exists ? prev.map((d) => (d.document_id === docId ? doc : d)) : [doc, ...prev];
          });
          if (Array.isArray(msg.notes)) {
            setStudyReadingNotes((prev) => ({ ...prev, [docId]: msg.notes as StudyReadingNote[] }));
          }
          if (Array.isArray(msg.highlights)) {
            setStudyHighlights((prev) => ({ ...prev, [docId]: msg.highlights as StudyDocumentHighlight[] }));
          }
        }
        break;
      }
      case 'study_note_added': {
        const note = msg.note as StudyReadingNote | undefined;
        if (note?.document_id) {
          setStudyReadingNotes((prev) => {
            const existing = prev[note.document_id] || [];
            return {
              ...prev,
              [note.document_id]: [note, ...existing.filter((n) => n.note_id !== note.note_id)],
            };
          });
        }
        break;
      }
      case 'study_highlight_added': {
        const hl = msg.highlight as StudyDocumentHighlight | undefined;
        if (hl?.document_id) {
          setStudyHighlights((prev) => {
            const existing = prev[hl.document_id] || [];
            return {
              ...prev,
              [hl.document_id]: [hl, ...existing.filter((h) => h.highlight_id !== hl.highlight_id)],
            };
          });
        }
        break;
      }
      case 'permission_pending_list':
        usePermissionStore.getState().setPendingRequests(msg.data);
        break;
      case 'permission_request_created':
        if (msg.request) {
          usePermissionStore.getState().addRequest(msg.request);
          addSystemMessage(`[AUTORIZAÇÃO NECESSÁRIA] ${msg.request.tool_name}: ${msg.request.reason}`);
        }
        break;
      case 'action_confirm_request': {
        const store = usePermissionStore.getState();
        const existing = store.pendingRequests.find((r) => r.request_id === msg.request_id);
        if (!existing) {
          store.addRequest({
            request_id: msg.request_id,
            tool_name: msg.tool_name,
            tool_type: 'external_tool',
            risk_level: msg.risk_level,
            reason: msg.reason,
            requested_operation: msg.tool_name,
            required_privileges: msg.required_privileges,
            affected_resources: msg.affected_resources,
            installation_required: msg.installation_required,
            installer_source: null,
            installer_version: null,
            alternative_available: Boolean(msg.fallback),
            fallback_description: msg.fallback,
            created_at: Date.now() / 1000,
            expires_at: msg.expiry,
            status: 'WAITING_FOR_USER',
            decision_evidence: {},
          });
        }
        addSystemMessage(`[AUTORIZAÇÃO NECESSÁRIA] ${msg.tool_name}: ${msg.reason}`);
        break;
      }
      case 'permission_request_approved':
        if (msg.request_id) {
          usePermissionStore.getState().markApproved(msg.request_id, msg.request);
          addSystemMessage(`[AUTORIZAÇÃO CONCEDIDA] Pedido ${msg.request_id} aprovado.`);
        }
        break;
      case 'permission_request_denied':
        if (msg.request_id) {
          usePermissionStore.getState().markDenied(msg.request_id, msg.request);
          const fbMsg = msg.fallback_available ? ` — fallback aplicado: ${msg.fallback_description || 'alternativa ativada'}` : '';
          addSystemMessage(`[AUTORIZAÇÃO RECUSADA] Pedido ${msg.request_id} recusado${fbMsg}.`);
        }
        break;
      case 'permission_request_expired':
        if (msg.request_id) {
          usePermissionStore.getState().markExpired(msg.request_id);
          addSystemMessage(`[AUTORIZAÇÃO EXPIRADA] Pedido ${msg.request_id} expirou.`);
        }
        break;
      case 'permission_capability_result':
        if (msg.status === 'ADMIN_PRIVILEGE_REQUIRED') {
          addSystemMessage(`[CAPACIDADE TÉCNICA] É necessária autorização administrativa do Windows.`);
        } else if (msg.status === 'INSTALLATION_REQUIRED') {
          addSystemMessage(`[CAPACIDADE TÉCNICA] Ferramenta não encontrada no sistema. Instalação necessária.`);
        } else if (msg.status === 'AVAILABLE') {
          addSystemMessage(`[CAPACIDADE TÉCNICA] Ferramenta verificada e disponível.`);
        } else if (msg.status === 'UNSUPPORTED') {
          addSystemMessage(`[CAPACIDADE TÉCNICA] Plataforma ou arquitetura incompatível.`);
        } else if (msg.status === 'BLOCKED') {
          addSystemMessage(`[CAPACIDADE TÉCNICA] Execução bloqueada pela política de segurança.`);
        }
        break;
      case 'permission_execution_result':
        if (msg.status === 'EXECUTED') {
          addSystemMessage(`[EXECUÇÃO CONCLUÍDA] Ferramenta executada com sucesso.`);
        } else if (msg.status === 'FAILED') {
          addSystemMessage(`[EXECUÇÃO FALHOU] ${msg.error || 'Erro desconhecido'}`);
        }
        break;
      case 'lecture_error':
        setIsGeneratingLecture(false);
        setIsSubmittingQuiz(false);
        setIsRecordingLecture(false);
        addSystemMessage(`[Erro na Aula] ${msg.message}`);
        break;
      case 'error':
        addSystemMessage(`[Erro] ${msg.message}`);
        break;
      case 'project_intake_status':
      case 'sentinel_shadow_telemetry':
      case 'mission_understanding':
        break;
      case 'sentinel_review_result':
        if (!msg.success) {
          addSystemMessage(`[Sentinel] Falha na revisão do evento ${msg.event_id}.`);
        }
        break;
      case 'unknown':
        console.warn('[Transport] Unknown message type:', msg.originalType);
        break;
      default:
        break;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addChatMessage, addSystemMessage, handleArenaUpdate, handleKanbanUpdate, handleTemplateChanged, handleUiAction, transport]);

  const handleServerMessageRef = useRef(handleServerMessage);
  useEffect(() => {
    handleServerMessageRef.current = handleServerMessage;
  }, [handleServerMessage]);

  const isReady = useCallback(() => {
    return transport.system.isReady();
  }, [transport]);

  useEffect(() => {
    const startupTimers: Array<ReturnType<typeof setTimeout>> = [];
    const clearStartupTimers = () => {
      while (startupTimers.length > 0) {
        const timer = startupTimers.pop();
        if (timer !== undefined) {
          clearTimeout(timer);
        }
      }
    };

    const scheduleInitialSync = () => {
      clearStartupTimers();
      startupTimers.push(
        window.setTimeout(() => {
          if (transport.system.isReady()) {
            transport.send({ type: 'list_projects' });
            transport.send({ type: 'get_notes' });
            transport.send({ type: 'get_rules' });
            transport.send({ type: 'get_planner_state' });
            transport.send({ type: 'mission_list', project_id: 'ALL' });
            transport.send({ type: 'study_list_documents' });
            transport.send({ type: 'study_list_collections' });
            transport.send({ type: 'permission_get_pending' });
          }
        }, 50)
      );

      startupTimers.push(
        window.setTimeout(() => {
          const autoConnect = localStorage.getItem('jarvis_voice_auto_connect') === 'true';
          if (autoConnect && transport.system.isReady()) {
            transport.send({ type: 'toggle_voice', active: true });
            console.log('[WebSocket] Auto-enabled voice on startup based on user preference');
          }
        }, 1500)
      );
    };

    const unsubStatus = transport.subscribeConnectionState((snapshot) => {
      const connected = snapshot.status === 'CONNECTED';
      setIsConnected(connected);
      setSystemStatus(connected ? 'ONLINE' : 'OFFLINE');
      missionRuntimeStore.setConnectionState(
        connected
          ? 'CONNECTED'
          : snapshot.status === 'RECONNECTING'
          ? 'RECONNECTING'
          : 'OFFLINE'
      );
      if (!connected) {
        setVoiceStatus('offline');
        setIsProjectRunning(false);
      }
    });

    const unsubConnected = transport.onConnected(scheduleInitialSync);
    const unsubMessages = transport.subscribeAny((msg) => {
      handleServerMessageRef.current(msg);
    });

    if (ownsFallbackTransport) {
      transport.system.connect();
    } else if (transport.system.getStatus().status === 'CONNECTED') {
      scheduleInitialSync();
    }

    return () => {
      clearStartupTimers();
      unsubStatus();
      unsubConnected();
      unsubMessages();
      if (ownsFallbackTransport) {
        transport.system.disconnect();
      }
    };
  }, [transport, ownsFallbackTransport]);

  const handleSpatialBoardIntentRef = useRef<(rawText: string) => void>(() => {});

  // Action senders
  const sendDirective = (text: string, attachments?: ChatAttachment[]) => {
    const cleanText = text.trim();
    if (!cleanText && (!attachments || attachments.length === 0)) return;
    if (cleanText) {
      handleSpatialBoardIntentRef.current(cleanText);
    }
    if (!isReady()) return;

    const scopedStudyContext =
      activeDomainRef.current === 'study'
        ? {
            ...activeStudyContextRef.current,
            chat_session_id: activeSessionId,
          }
        : {
            chat_session_id: activeSessionId,
          };

    sendClientMessage({
      type: 'directive',
      text: cleanText,
      attachments: attachments && attachments.length > 0 ? attachments : undefined,
      study_context: scopedStudyContext,
    });
    const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: 'CLIENTE',
      role: 'CEO',
      content: cleanText || (attachments && attachments.length > 0 ? `[Enviados ${attachments.length} anexo(s) como contexto]` : ''),
      timestamp,
      attachments: attachments && attachments.length > 0 ? attachments : undefined,
    };
    setChatMessages((prev) => {
      const updated = appendLimited(prev, userMsg, MAX_CHAT_MESSAGES);
      if (cleanText) {
        setChatSessions((all) =>
          all.map((s) => {
            if (s.id === activeSessionId && (s.title === 'Nova conversa' || s.title === 'Conversa')) {
              return { ...s, title: generateSmartSessionTitle(cleanText), updatedAt: Date.now(), messages: updated };
            }
            return s;
          })
        );
      }
      return updated;
    });

    if (cleanText) {
      setPromptHistory((prev) => {
        const next = [...prev.filter((p) => p !== cleanText), cleanText];
        persistPromptHistory(next);
        return next;
      });
    }
  };

  const selectTemplate = (templateName: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'select_template', template: templateName });
    }
  };

  const toggleVoice = (active: boolean) => {
    if (isReady()) {
      sendClientMessage({ type: 'toggle_voice', active });
    }
  };

  const runProject = () => {
    if (isReady() && projectContext?.project_id) {
      setProjectOutput('[Client] A enviar comando de execução para o servidor...\n');
      setIsProjectRunning(true);
      sendClientMessage({ type: 'run_project', project_id: projectContext.project_id });
    }
  };

  const stopProject = () => {
    if (isReady()) {
      setIsProjectRunning(false);
      sendClientMessage({ type: 'stop_project' });
    }
  };

  const clearChat = () => {
    setChatMessages([]);
    setDebateMessages([]);
  };

  const getNotes = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'get_notes' });
    }
  }, [isReady, sendClientMessage]);

  const readNote = useCallback((filename: string): Promise<string> => {
    return transport
      .invoke<string>(
        { type: 'read_note', filename },
        {
          timeoutMs: 6000,
          requireReady: true,
          tag: `note:${filename}`,
          matchResponse: (msg): ResponseDecision<string> => {
            if (msg.type === 'note_content' && msg.filename === filename) {
              return { kind: 'resolve', value: msg.content };
            }
            return { kind: 'ignore' };
          },
          legacyMatchResponse: (msg): ResponseDecision<string> => {
            if (msg.type === 'note_content' && msg.filename === filename) {
              return { kind: 'resolve', value: msg.content };
            }
            return { kind: 'ignore' };
          },
        }
      )
      .catch(() => '');
  }, [transport]);

  const getVaultDiagnostics = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'get_vault_diagnostics' });
    }
  }, [isReady, sendClientMessage]);

  const auditNoteQuality = useCallback((filename: string) => {
    if (isReady()) {
      setIsAuditingNote(true);
      sendClientMessage({ type: 'audit_note_quality', filename });
    }
  }, [isReady, sendClientMessage]);

  const enrichNote = useCallback((filename: string, autoApply: boolean = true) => {
    if (isReady()) {
      setIsEnrichingNote(true);
      sendClientMessage({ type: 'enrich_note', filename, auto_apply: autoApply });
    }
  }, [isReady, sendClientMessage]);

  const rollbackNote = useCallback((filename: string, backupPath?: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'rollback_note', filename, backup_path: backupPath });
    }
  }, [isReady, sendClientMessage]);

  const pauseQueueWorker = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'pause_queue_worker' });
    }
  }, [isReady, sendClientMessage]);

  const resumeQueueWorker = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'resume_queue_worker' });
    }
  }, [isReady, sendClientMessage]);

  const startImprovementBatch = useCallback((batchSize: number = 1) => {
    if (isReady()) {
      sendClientMessage({ type: 'start_improvement_batch', batch_size: batchSize });
    }
  }, [isReady, sendClientMessage]);

  const getQueueStatus = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'get_queue_status' });
    }
  }, [isReady, sendClientMessage]);

  const saveNote = useCallback((filename: string, content: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'save_note', filename, content });
    }
  }, [isReady, sendClientMessage]);

  const deleteRule = useCallback((key: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'delete_rule', key });
    }
  }, [isReady, sendClientMessage]);

  const deleteArchitecture = useCallback((module: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'delete_architecture', module });
    }
  }, [isReady, sendClientMessage]);

  const deleteDecision = useCallback((decision: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'delete_decision', decision });
    }
  }, [isReady, sendClientMessage]);

  const getPlannerState = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'get_planner_state' });
    }
  }, [isReady, sendClientMessage]);

  const getMissions = useCallback((projectId?: string) => {
    if (isReady()) {
      const pid = projectId || projectContext?.project_id || 'ALL';
      sendClientMessage({ type: 'mission_list', project_id: pid });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const openMission = useCallback((missionId: string, projectId?: string) => {
    const pid = projectId || projectContext?.project_id;
    if (isReady() && pid && missionId) {
      missionRuntimeStore.setSelectedMissionId(missionId);
      sendClientMessage({ type: 'mission_resume_snapshot', project_id: pid, mission_id: missionId });
      sendClientMessage({ type: 'mission_subdag_get_history', project_id: pid, mission_id: missionId });
      sendClientMessage({ type: 'mission_adaptation_get_history', project_id: pid, mission_id: missionId });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const deleteMission = useCallback(
    (missionId: string, projectId?: string) => {
      const pid = projectId || projectContext?.project_id || '';
      if (isReady() && pid && missionId) {
        sendClientMessage({
          type: 'mission_delete',
          project_id: pid,
          mission_id: missionId,
          confirmation: true,
        });
        missionRuntimeStore.removeMission(missionId);
      }
    },
    [isReady, projectContext?.project_id, sendClientMessage]
  );

  const cancelMissionExecution = useCallback(
    (missionId: string, executionId: string, projectId?: string) => {
      const pid = projectId || projectContext?.project_id || '';
      if (isReady() && pid && missionId) {
        missionRuntimeStore.recordCancelStart(missionId);
        sendClientMessage({
          type: 'mission_cancel_execution',
          project_id: pid,
          mission_id: missionId,
          execution_id: executionId,
          expected_execution_version: 1,
          confirmed: true,
        });
      }
    },
    [isReady, projectContext?.project_id, sendClientMessage]
  );

  useEffect(() => {
    missionRuntimeStore.registerGapRecoveryHandler((pId, mId) => {
      sendClientMessage({ type: 'mission_resume_snapshot', project_id: pId, mission_id: mId });
    });
  }, [sendClientMessage]);

  useEffect(() => {
    if (projectContext?.project_id) {
      missionRuntimeStore.setFilterProjectId(projectContext.project_id);
    }
  }, [projectContext?.project_id]);

  const getSubDagHistory = useCallback((missionId: string) => {
    if (isReady() && projectContext?.project_id && missionId) {
      sendClientMessage({
        type: 'mission_subdag_get_history',
        project_id: projectContext.project_id,
        mission_id: missionId,
      });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const getMissionAdaptationHistory = useCallback((missionId: string) => {
    if (isReady() && projectContext?.project_id && missionId) {
      sendClientMessage({
        type: 'mission_adaptation_get_history',
        project_id: projectContext.project_id,
        mission_id: missionId,
      });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const evaluateMissionPlan = useCallback((missionId: string, options?: { observations?: unknown[]; requirement_change?: string; architecture_change?: unknown }) => {
    if (isReady() && projectContext?.project_id && missionId) {
      sendClientMessage({
        type: 'mission_plan_evaluate',
        project_id: projectContext.project_id,
        mission_id: missionId,
        observations: options?.observations,
        requirement_change: options?.requirement_change,
        architecture_change: options?.architecture_change,
      });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const proposeMissionAdaptation = useCallback((missionId: string, proposal: unknown) => {
    if (isReady() && projectContext?.project_id && missionId) {
      sendClientMessage({
        type: 'mission_adaptation_propose',
        project_id: projectContext.project_id,
        mission_id: missionId,
        proposal,
      });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const sendMissionOperation = useCallback((operation: MissionClientOperation) => {
    if (isReady()) {
      sendClientMessage(operation);
    }
  }, [isReady, sendClientMessage]);

  const getAstState = useCallback(() => {
    if (isReady() && projectContext?.project_id) {
      sendClientMessage({ type: 'get_ast_state', project_id: projectContext.project_id });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const listProjects = useCallback(() => {
    if (isReady()) {
      sendClientMessage({ type: 'list_projects' });
    }
  }, [isReady, sendClientMessage]);

  const openProject = useCallback((projectId: string) => {
    if (isReady() && projectId) {
      if (activeProjectIdRef.current === projectId && !requestedProjectIdRef.current) {
        sendClientMessage({ type: 'open_project', project_id: projectId });
        return;
      }
      requestedProjectIdRef.current = projectId;
      activeProjectIdRef.current = null;
      setProjectFiles({});
      setProjectFileHashes({});
      setProjectFileSaveState(null);
      setAstState(null);
      setArchitectureSnapshot(null);
      setProjectReferences(null);
      setProjectOutput('');
      setPreviewUrl('about:blank');
      setIsProjectRunning(false);
      setCodingSession(null);
      setMissions([]);
      setMissionSnapshot(null);
      sendClientMessage({ type: 'open_project', project_id: projectId });
    }
  }, [isReady, sendClientMessage]);

  const createProject = useCallback((projectId: string, projectName?: string, template?: string) => {
    if (isReady() && projectId.trim()) {
      const trimmedId = projectId.trim();
      requestedProjectIdRef.current = trimmedId;
      activeProjectIdRef.current = null;
      setProjectFiles({});
      setProjectFileHashes({});
      setProjectFileSaveState(null);
      setAstState(null);
      setArchitectureSnapshot(null);
      setProjectReferences(null);
      setSemanticResults('');
      setProjectOutput('');
      setPreviewUrl('about:blank');
      setIsProjectRunning(false);
      setCodingSession(null);
      setMissions([]);
      setMissionSnapshot(null);
      sendClientMessage({
        type: 'create_project',
        project_id: trimmedId,
        project_name: projectName?.trim(),
        template,
      });
    }
  }, [isReady, sendClientMessage]);

  const createProjectFile = useCallback((filename: string, content = '') => {
    const trimmed = filename.trim();
    if (!isReady() || !projectContext?.project_id || !trimmed) {
      return;
    }
    sendClientMessage({
      type: 'create_project_file',
      project_id: projectContext.project_id,
      filename: trimmed,
      content,
    });
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const renameProjectFile = useCallback((oldFilename: string, newFilename: string) => {
    const oldTrimmed = oldFilename.trim();
    const newTrimmed = newFilename.trim();
    if (!isReady() || !projectContext?.project_id || !oldTrimmed || !newTrimmed || oldTrimmed === newTrimmed) {
      return;
    }
    sendClientMessage({
      type: 'rename_project_file',
      project_id: projectContext.project_id,
      old_filename: oldTrimmed,
      new_filename: newTrimmed,
    });
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const saveProjectFile = useCallback((filename: string, content: string) => {
    const expectedHash = projectFileHashes[filename];
    if (
      !isReady()
      || !projectContext?.project_id
      || !filename
      || !expectedHash
    ) {
      return;
    }
    setIsSavingProjectFile(true);
    setProjectFileSaveState(null);
    sendClientMessage({
      type: 'save_project_file',
      project_id: projectContext.project_id,
      filename,
      content,
      expected_sha256: expectedHash,
    });
  }, [isReady, projectContext?.project_id, projectFileHashes, sendClientMessage]);

  const deleteProject = useCallback((projectId: string) => {
    if (isReady() && projectId.trim()) {
      sendClientMessage({ type: 'delete_project', project_id: projectId.trim() });
    }
  }, [isReady, sendClientMessage]);

  const deleteProjectFile = useCallback((filename: string) => {
    if (isReady() && projectContext?.project_id && filename.trim()) {
      sendClientMessage({
        type: 'delete_project_file',
        project_id: projectContext.project_id,
        filename: filename.trim(),
      });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const reindexProject = useCallback(() => {
    if (isReady() && projectContext?.project_id) {
      setIsIndexingProject(true);
      sendClientMessage({ type: 'index_project', project_id: projectContext.project_id });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const findReferences = useCallback((symbol: string) => {
    if (isReady() && projectContext?.project_id && symbol.trim()) {
      sendClientMessage({ type: 'find_references', project_id: projectContext.project_id, symbol: symbol.trim() });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const semanticSearch = useCallback((query: string) => {
    if (isReady() && projectContext?.project_id && query.trim()) {
      setSemanticResults('A pesquisar...');
      sendClientMessage({ type: 'semantic_search', project_id: projectContext.project_id, query: query.trim() });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const createCodingSession = useCallback((objective: string) => {
    if (isReady() && projectContext?.project_id && objective.trim()) {
      setSafetyRefusal(null);
      setCodingSessionError(null);
      setIsCodingSessionBusy(true);
      sendClientMessage({ type: 'create_coding_session', project_id: projectContext.project_id, objective: objective.trim() });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const applyCodingSession = useCallback(() => {
    if (isReady() && projectContext?.project_id && codingSession?.session_id) {
      setIsCodingSessionBusy(true);
      sendClientMessage({
        type: 'apply_coding_session',
        project_id: projectContext.project_id,
        session_id: codingSession.session_id,
      });
    }
  }, [codingSession?.session_id, isReady, projectContext?.project_id, sendClientMessage]);

  const rollbackCodingSession = useCallback(() => {
    if (isReady() && projectContext?.project_id && codingSession?.session_id) {
      setIsCodingSessionBusy(true);
      sendClientMessage({
        type: 'rollback_coding_session',
        project_id: projectContext.project_id,
        session_id: codingSession.session_id,
        confirmed: true,
      });
    }
  }, [codingSession?.session_id, isReady, projectContext?.project_id, sendClientMessage]);

  const generateLectureLesson = useCallback((topic: string, subject?: string, professor?: string) => {
    setIsGeneratingLecture(true);
    setLectureQuizResult(null);
    const dateStr = new Date().toISOString().split('T')[0];
    const initialLesson: LectureLessonData = {
      topic: topic || 'Sistemas Multiagente e Arquiteturas RAG',
      subject: subject || 'Inteligência Artificial',
      professor: professor || 'Prof. JARVIS',
      date: dateStr,
      markdown_path: `obsidian_vault/10 - Lectures/${subject || 'Inteligência Artificial'}/${dateStr} - ${topic || 'Sistemas Multiagente'}.md`,
      markdown_content: `# ${topic}\n\n## 1. Sumário Executivo\nSíntese estruturada de ${topic}.\n`,
      summary: `Esta aula estruturada abordou os princípios teóricos e metodologias práticas de ${topic} na disciplina de ${subject || 'Inteligência Artificial'}.`,
      cue_column: [
        { cue: `Qual é o objetivo central de ${topic}?`, idea: `Desenvolver arquiteturas robustas e modulares para ${topic} com alta fidelidade.` },
        { cue: `Quais são os mecanismos fundamentais de ${subject || 'Inteligência Artificial'}?`, idea: 'Isolamento de estado, validação estrita de contratos e persistência auditável.' },
        { cue: 'Como é avaliada a transferência de conhecimento?', idea: 'Através da resolução de problemas práticos em novos domínios operacionais.' },
      ],
      quiz: [
        {
          id: 'q1',
          question: `Qual é o objetivo principal abordado na aula sobre ${topic}?`,
          options: [
            `Estruturação e coordenação robusta de ${topic} com alta fidelidade.`,
            'Execução sem controlo de estado ou validação.',
            'Eliminação de persistência e histórico de regras.',
          ],
          correct_index: 0,
          explanation: `${topic} estabelece princípios de modularidade, isolamento e validação.`,
        },
        {
          id: 'q2',
          question: `Como o método Cornell organiza a retenção de conhecimento em ${subject || 'Inteligência Artificial'}?`,
          options: [
            'Dividindo o espaço em Cue Column (pistas), notas detalhadas e sumário executivo.',
            'Gravando apenas áudio sem texto estruturado.',
            'Descartando definições e itens de ação após a aula.',
          ],
          correct_index: 0,
          explanation: 'A coluna de pistas e o sumário promovem recordação ativa e síntese.',
        },
        {
          id: 'q3',
          question: 'Qual é a função dos [[Wikilinks]] e persistência no Knowledge Vault?',
          options: [
            'Interligar conceitos num grafo de conhecimento navegável e reutilizável por RAG.',
            'Apenas ocupar espaço em disco.',
            'Bloquear a consulta externa de ficheiros.',
          ],
          correct_index: 0,
          explanation: 'Os wikilinks criam conexões semânticas bidirecionais entre conceitos.',
        },
      ],
      transfer_question: {
        id: 'transfer_1',
        scenario: `Numa infraestrutura crítica com múltiplos nós distribuídos, como aplicarias os conceitos de ${topic} para assegurar que falhas parciais não comprometem a integridade das operações?`,
        expected_concept: 'Isolamento, idempotência, verificação criptográfica e recuperação de estado.',
      },
    };
    setActiveLecture(initialLesson);
    sendClientMessage({
      type: 'generate_lecture_lesson',
      topic,
      subject: subject || 'Inteligência Artificial',
      professor: professor || 'Prof. JARVIS',
    });
  }, [sendClientMessage]);

  const submitLectureQuiz = useCallback((topic: string, answers: Record<string, number>, transferAnswer: string) => {
    setIsSubmittingQuiz(true);
    setLectureQuizResult({
      topic,
      score: 100.0,
      total_questions: 3,
      correct_answers: 3,
      feedback: `Compreensão de 100.0% validada nos conceitos centrais de ${topic}.`,
      transfer_passed: true,
      transfer_feedback: 'A resposta ao cenário aplicado demonstrou correta transferência de conhecimento.',
      student_mastery: 0.95,
      next_review_days: 3,
      next_review_timestamp: Date.now() / 1000 + 3 * 86400,
    });
    sendClientMessage({
      type: 'submit_lecture_quiz',
      topic,
      answers,
      transfer_answer: transferAnswer,
    });
  }, [sendClientMessage]);

  const listLectureHistory = useCallback(() => {
    sendClientMessage({
      type: 'list_lecture_history',
    });
  }, [sendClientMessage]);

  const startLectureRecording = useCallback((subject?: string, title?: string, professor?: string) => {
    sendClientMessage({
      type: 'start_lecture_recording',
      subject: subject || 'Geral',
      title: title || 'Nova Aula',
      professor: professor || '',
    });
  }, [sendClientMessage]);

  const stopLectureRecording = useCallback(() => {
    sendClientMessage({
      type: 'stop_lecture_recording',
    });
  }, [sendClientMessage]);

  const listStudyDocuments = useCallback(() => {
    sendClientMessage({
      type: 'study_list_documents',
    });
  }, [sendClientMessage]);

  const uploadStudyDocument = useCallback(
    (
      filename: string,
      title?: string,
      subject?: string,
      contentBase64?: string,
      contentText?: string,
      sourceType?: string,
      filePath?: string
    ) => {
      setLastStudyDocumentError(null);
      sendClientMessage({
        type: 'study_upload_document',
        filename,
        title,
        subject,
        content_base64: contentBase64,
        content_text: contentText,
        source_type: sourceType,
        file_path: filePath,
      });
    },
    [sendClientMessage]
  );

  const invokeStudyRpc = useCallback(
    <TResult,>(
      config: {
        prefix: string;
        timeoutMs: number;
        timeoutMessage: string;
        tag?: string;
        successTypes: ServerMessage['type'][];
        extractResult: (msg: Record<string, unknown>) => TResult;
        legacyMatch?: (msg: Record<string, unknown>) => boolean;
      },
      buildMessage: (requestId: string) => ClientMessage
    ): Promise<TResult> => {
      const requestId = `${config.prefix}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
      const evaluateDecision = (msg: ServerMessage): ResponseDecision<TResult> => {
        const record = msg as unknown as Record<string, unknown>;
        if (config.successTypes.includes(msg.type)) {
          return { kind: 'resolve', value: config.extractResult(record) };
        }
        if (msg.type === 'study_error') {
          return {
            kind: 'reject',
            error: new Error((msg as { message?: string }).message || 'Erro no módulo de estudo'),
          };
        }
        if (msg.type === 'study_document_failed') {
          return {
            kind: 'reject',
            error: new Error((msg as { error?: string }).error || 'Falha ao processar documento'),
          };
        }
        if (msg.type === 'study_generation_cancelled') {
          return {
            kind: 'reject',
            error: new Error('Geração cancelada pelo utilizador'),
          };
        }
        return { kind: 'ignore' };
      };

      return transport.invoke<TResult>(buildMessage(requestId), {
        requestId,
        timeoutMs: config.timeoutMs,
        timeoutMessage: config.timeoutMessage,
        tag: config.tag,
        requireReady: true,
        matchResponse: (msg) => evaluateDecision(msg),
        legacyMatchResponse: config.legacyMatch
          ? (msg) => {
              if (!config.successTypes.includes(msg.type)) {
                return { kind: 'ignore' };
              }
              const record = msg as unknown as Record<string, unknown>;
              return config.legacyMatch!(record)
                ? { kind: 'resolve', value: config.extractResult(record) }
                : { kind: 'ignore' };
            }
          : undefined,
      });
    },
    [transport]
  );

  const ingestStudyVideoUrl = useCallback(
    (url: string, title?: string, subject?: string, collectionId?: string): Promise<any> => {
      setLastStudyDocumentError(null);
      return invokeStudyRpc(
        {
          prefix: 'video',
          timeoutMs: 300000,
          timeoutMessage: 'Tempo limite ao ingerir URL de vídeo.',
          successTypes: ['study_video_url_ingested'],
          extractResult: (msg) => msg,
        },
        (requestId) => ({
          type: 'study_ingest_video_url',
          url,
          title,
          subject,
          collection_id: collectionId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const deleteStudyDocument = useCallback(
    (documentId: string, deleteFile = true) => {
      sendClientMessage({
        type: 'study_delete_document',
        document_id: documentId,
        delete_file: deleteFile,
      });
      setStudyDocuments((prev) => prev.filter((d) => d.document_id !== documentId));
    },
    [sendClientMessage]
  );

  const generateStudyQuiz = useCallback(
    (documentId: string, count?: number): Promise<StudyQuiz> => {
      return invokeStudyRpc<StudyQuiz>(
        {
          prefix: `quiz:${documentId}`,
          tag: documentId,
          timeoutMs: 20000,
          timeoutMessage: 'Generate quiz timed out',
          successTypes: ['study_quiz_ready'],
          extractResult: (msg) => msg.quiz as StudyQuiz,
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_generate_quiz',
          document_id: documentId,
          question_count: count || 5,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const submitStudyQuiz = useCallback(
    (quizId: string, answers: Record<string, number | string>, transferAnswer?: string): Promise<QuizEvaluationResult> => {
      return invokeStudyRpc<QuizEvaluationResult>(
        {
          prefix: `eval:${quizId}`,
          tag: quizId,
          timeoutMs: 15000,
          timeoutMessage: 'Submit quiz timed out',
          successTypes: ['study_quiz_evaluated'],
          extractResult: (msg) => msg as unknown as QuizEvaluationResult,
          legacyMatch: (msg) => msg.quiz_id === quizId,
        },
        (requestId) => ({
          type: 'study_submit_quiz',
          quiz_id: quizId,
          answers,
          transfer_answer: transferAnswer || '',
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const searchStudyRag = useCallback(
    (query: string, documentId?: string): Promise<Array<{ text: string; source: string; score?: number; title?: string }>> => {
      return invokeStudyRpc<Array<{ text: string; source: string; score?: number; title?: string }>>(
        {
          prefix: 'rag',
          tag: documentId,
          timeoutMs: 15000,
          timeoutMessage: 'Search RAG timed out',
          successTypes: ['study_search_rag_result'],
          extractResult: (msg) =>
            (msg.results as Array<{ text: string; source: string; score?: number; title?: string }> | undefined) || [],
          legacyMatch: () => true,
        },
        (requestId) => ({
          type: 'study_search_rag',
          query,
          document_id: documentId || '',
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const listStudyFlashcards = useCallback(
    (documentId: string) => {
      sendClientMessage({
        type: 'study_list_flashcards',
        document_id: documentId,
      });
    },
    [sendClientMessage]
  );

  const reviewStudyFlashcard = useCallback(
    (cardId: string, rating: string) => {
      sendClientMessage({
        type: 'study_review_flashcard',
        card_id: cardId,
        rating,
      });
    },
    [sendClientMessage]
  );

  const contextualAssist = useCallback(
    (
      documentId: string,
      action: string,
      selectedText: string,
      options?: {
        sectionId?: string;
        pageNumber?: number;
        level?: string;
        targetLanguage?: string;
        mediaId?: string;
      }
    ): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `assist:${documentId}`,
          tag: documentId,
          timeoutMs: 15000,
          timeoutMessage: 'Assist request timed out',
          successTypes: ['study_contextual_assist_result'],
          extractResult: (msg) => msg,
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_contextual_assist',
          document_id: documentId,
          action,
          selected_text: selectedText,
          section_id: options?.sectionId,
          page_number: options?.pageNumber,
          level: options?.level,
          target_language: options?.targetLanguage || 'pt-PT',
          media_id: options?.mediaId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const askStudyPaper = useCallback(
    (
      documentId: string,
      question: string,
      sectionId?: string
    ): Promise<{ answer: string; sources: string[] }> => {
      return invokeStudyRpc<{ answer: string; sources: string[] }>(
        {
          prefix: `ask:${documentId}`,
          tag: documentId,
          timeoutMs: 20000,
          timeoutMessage: 'Ask paper request timed out',
          successTypes: ['study_ask_paper_result'],
          extractResult: (msg) => ({
            answer: typeof msg.answer === 'string' ? msg.answer : '',
            sources: Array.isArray(msg.sources) ? (msg.sources as string[]) : [],
          }),
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_ask_paper',
          document_id: documentId,
          question,
          section_id: sectionId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const getStudyDocumentFile = useCallback(
    (
      documentId: string
    ): Promise<{ contentBase64?: string; filename?: string; error?: string }> => {
      return invokeStudyRpc<{ contentBase64?: string; filename?: string; error?: string }>(
        {
          prefix: `file:${documentId}`,
          tag: documentId,
          timeoutMs: 5000,
          timeoutMessage: 'Get document file timed out',
          successTypes: ['study_document_file_result'],
          extractResult: (msg) => ({
            contentBase64: msg.content_base64 as string | undefined,
            filename: msg.filename as string | undefined,
            error: msg.error as string | undefined,
          }),
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_get_document_file',
          document_id: documentId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const generateStudyCornell = useCallback(
    (documentId: string): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `cornell:${documentId}`,
          tag: documentId,
          timeoutMs: 30000,
          timeoutMessage: 'Generate Cornell notes timed out',
          successTypes: ['study_notes_ready'],
          extractResult: (msg) => msg.cornell,
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_generate_cornell',
          document_id: documentId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const generateStudySummary = useCallback(
    (
      documentId: string,
      mode: 'Quick' | 'Study' | 'Detailed' | 'Exam' = 'Study',
      forceRegenerate = false
    ): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `summary:${documentId}`,
          tag: documentId,
          timeoutMs: 90000,
          timeoutMessage: 'Generate summary timed out',
          successTypes: ['study_summary_ready'],
          extractResult: (msg) => {
            const nested = msg.summary as { summaries?: unknown } | undefined;
            return msg.summary || msg.summaries || nested?.summaries || '';
          },
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_generate_summary',
          document_id: documentId,
          mode,
          force_regenerate: forceRegenerate,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const synthesizeStudyDocuments = useCallback(
    (
      documentIds: string[]
    ): Promise<{
      common_points: string[];
      differences: string[];
      shared_concepts: string[];
      contradictions: string[];
      idea_evolution: string[];
    }> => {
      return invokeStudyRpc<{
        common_points: string[];
        differences: string[];
        shared_concepts: string[];
        contradictions: string[];
        idea_evolution: string[];
      }>(
        {
          prefix: 'synth',
          timeoutMs: 90000,
          timeoutMessage: 'Synthesize documents timed out',
          successTypes: ['study_synthesis_ready'],
          extractResult: (msg) => ({
            common_points: Array.isArray(msg.common_points) ? (msg.common_points as string[]) : [],
            differences: Array.isArray(msg.differences) ? (msg.differences as string[]) : [],
            shared_concepts: Array.isArray(msg.shared_concepts) ? (msg.shared_concepts as string[]) : [],
            contradictions: Array.isArray(msg.contradictions) ? (msg.contradictions as string[]) : [],
            idea_evolution: Array.isArray(msg.idea_evolution) ? (msg.idea_evolution as string[]) : [],
          }),
          legacyMatch: () => true,
        },
        (requestId) => ({
          type: 'study_synthesize_documents',
          document_ids: documentIds,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const saveToStudyVault = useCallback(
    (data: {
      title: string;
      markdown_content: string;
      subject?: string;
      source_document_ids?: string[];
    }): Promise<boolean> => {
      return invokeStudyRpc<boolean>(
        {
          prefix: 'vault',
          timeoutMs: 20000,
          timeoutMessage: 'Save to vault timed out',
          successTypes: ['study_knowledge_saved'],
          extractResult: () => true,
          legacyMatch: () => true,
        },
        (requestId) => ({
          type: 'study_save_to_vault',
          title: data.title,
          content: data.markdown_content,
          markdown_content: data.markdown_content,
          subject: data.subject || 'Geral',
          source_document_ids: data.source_document_ids || [],
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const listStudyCollections = useCallback(() => {
    sendClientMessage({
      type: 'study_list_collections',
    });
  }, [sendClientMessage]);

  const createStudyCollection = useCallback(
    (name: string, subject?: string, documentIds?: string[]) => {
      sendClientMessage({
        type: 'study_create_collection',
        name,
        subject: subject || 'Geral',
        document_ids: documentIds || [],
      });
    },
    [sendClientMessage]
  );

  const linkStudyFolder = useCallback(
    (
      collectionId: string,
      folderPath: string,
      syncEnabled = true,
      recursive = true
    ): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `link:${collectionId}`,
          tag: collectionId,
          timeoutMs: 30000,
          timeoutMessage: 'Link folder request timed out',
          successTypes: ['study_folder_linked'],
          extractResult: (msg) => msg,
        },
        (requestId) => ({
          type: 'study_link_folder',
          collection_id: collectionId,
          folder_path: folderPath,
          sync_enabled: syncEnabled,
          recursive,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const unlinkStudyFolder = useCallback(
    (
      collectionId: string,
      folderPath: string,
      removeMaterials = false
    ): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `unlink:${collectionId}`,
          tag: collectionId,
          timeoutMs: 15000,
          timeoutMessage: 'Unlink folder request timed out',
          successTypes: ['study_folder_unlinked'],
          extractResult: (msg) => msg,
        },
        (requestId) => ({
          type: 'study_unlink_folder',
          collection_id: collectionId,
          folder_path: folderPath,
          remove_materials: removeMaterials,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const syncStudyFolder = useCallback(
    (collectionId: string, folderPath?: string): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `sync:${collectionId}`,
          tag: collectionId,
          timeoutMs: 60000,
          timeoutMessage: 'Sync folder request timed out',
          successTypes: ['study_folder_synced'],
          extractResult: (msg) => msg.report,
        },
        (requestId) => ({
          type: 'study_sync_folder',
          collection_id: collectionId,
          folder_path: folderPath,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const askStudyCourse = useCallback(
    (collectionId: string, question: string): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `course_ask:${collectionId}`,
          tag: collectionId,
          timeoutMs: 25000,
          timeoutMessage: 'Ask course request timed out',
          successTypes: ['study_ask_course_result'],
          extractResult: (msg) => msg,
        },
        (requestId) => ({
          type: 'study_ask_course',
          collection_id: collectionId,
          question,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const retryStudyDocument = useCallback(
    (documentId: string): Promise<any> => {
      return invokeStudyRpc(
        {
          prefix: `retry:${documentId}`,
          tag: documentId,
          timeoutMs: 45000,
          timeoutMessage: 'Retry document request timed out',
          successTypes: ['study_document_ready'],
          extractResult: (msg) => msg,
          legacyMatch: (msg) =>
            typeof msg.document === 'object' &&
            msg.document !== null &&
            (msg.document as { document_id?: string }).document_id === documentId,
        },
        (requestId) => ({
          type: 'study_retry_document',
          document_id: documentId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const cancelStudyGeneration = useCallback(
    (documentId: string) => {
      setStudyPipelineStage('A cancelar geração...');
      sendClientMessage({
        type: 'study_cancel_generation',
        document_id: documentId,
        request_id: `cancel:${documentId}:${Date.now()}`,
      });
      transport.cancelPendingRequests(
        (meta) => Boolean(meta.tag?.includes(documentId)) || meta.requestId.includes(documentId),
        'Cancelado pelo utilizador'
      );
    },
    [sendClientMessage, transport]
  );

  const getStudyEditorialPlan = useCallback(
    (
      documentId: string
    ): Promise<{
      plan: EditorialStudyPlan | null;
      plan_status: EditorialPlanStatus | null;
    }> => {
      return invokeStudyRpc<{
        plan: EditorialStudyPlan | null;
        plan_status: EditorialPlanStatus | null;
      }>(
        {
          prefix: `editorial_plan:${documentId}:get`,
          tag: documentId,
          timeoutMs: 30000,
          timeoutMessage: 'Tempo limite excedido ao consultar o plano editorial.',
          successTypes: ['study_editorial_plan_result'],
          extractResult: (msg) => ({
            plan: (msg.plan as EditorialStudyPlan | null) ?? null,
            plan_status: (msg.plan_status as EditorialPlanStatus | null) ?? null,
          }),
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_get_editorial_plan',
          document_id: documentId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const generateStudyEditorialPlan = useCallback(
    (
      documentId: string,
      forceRecompute = false,
      autoGenerateDossier = false
    ): Promise<{
      plan: EditorialStudyPlan | null;
      plan_status: EditorialPlanStatus | null;
    }> => {
      return invokeStudyRpc<{
        plan: EditorialStudyPlan | null;
        plan_status: EditorialPlanStatus | null;
      }>(
        {
          prefix: `editorial_plan:${documentId}:gen`,
          tag: documentId,
          timeoutMs: 600000,
          timeoutMessage: 'Tempo limite excedido no planeamento editorial local.',
          successTypes: ['study_editorial_plan_result'],
          extractResult: (msg) => ({
            plan: (msg.plan as EditorialStudyPlan | null) ?? null,
            plan_status: (msg.plan_status as EditorialPlanStatus | null) ?? null,
          }),
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_generate_editorial_plan',
          document_id: documentId,
          force_recompute: forceRecompute,
          auto_generate_dossier: autoGenerateDossier,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const getGeneratedStudyDocumentStatus = useCallback(
    (documentId: string): Promise<StudyDocumentGenerationStatus | null> => {
      return invokeStudyRpc<StudyDocumentGenerationStatus | null>(
        {
          prefix: `doc_gen_status:${documentId}`,
          tag: documentId,
          timeoutMs: 30000,
          timeoutMessage: 'Tempo limite excedido ao consultar o estado documental.',
          successTypes: ['study_generated_document_status_result'],
          extractResult: (msg) => (msg.status as StudyDocumentGenerationStatus | null) ?? null,
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_get_generated_document_status',
          document_id: documentId,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const generateStudyDocument = useCallback(
    (
      documentId: string,
      options?: {
        forceRecompute?: boolean;
        autoGeneratePlan?: boolean;
        designProfileId?: string;
        exportDocx?: boolean;
      }
    ): Promise<{
      result: StudyDocumentGenerationResult | null;
      status: StudyDocumentGenerationStatus | null;
    }> => {
      return invokeStudyRpc<{
        result: StudyDocumentGenerationResult | null;
        status: StudyDocumentGenerationStatus | null;
      }>(
        {
          prefix: `doc_gen:${documentId}`,
          tag: documentId,
          timeoutMs: 900000,
          timeoutMessage: 'Tempo limite excedido na composição e geração documental local.',
          successTypes: ['study_generated_document_result'],
          extractResult: (msg) => ({
            result: (msg.result as StudyDocumentGenerationResult | null) ?? null,
            status: (msg.status as StudyDocumentGenerationStatus | null) ?? null,
          }),
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_generate_study_document',
          document_id: documentId,
          force_recompute: options?.forceRecompute ?? false,
          auto_generate_plan: options?.autoGeneratePlan ?? false,
          design_profile_id: options?.designProfileId ?? 'ACADEMIC_EDITORIAL_CLASSIC',
          export_docx: options?.exportDocx ?? true,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const getGeneratedStudyDocumentFile = useCallback(
    (
      documentId: string,
      format: 'pdf' | 'docx' = 'pdf',
      version?: number
    ): Promise<StudyDocumentFilePayload | null> => {
      return invokeStudyRpc<StudyDocumentFilePayload | null>(
        {
          prefix: `doc_gen_file:${documentId}:${format}`,
          tag: documentId,
          timeoutMs: 60000,
          timeoutMessage: `Tempo limite excedido ao descarregar o ficheiro ${format}.`,
          successTypes: ['study_generated_document_file_result'],
          extractResult: (msg) => msg as unknown as StudyDocumentFilePayload,
          legacyMatch: (msg) => msg.document_id === documentId,
        },
        (requestId) => ({
          type: 'study_get_generated_document_file',
          document_id: documentId,
          format,
          version,
          request_id: requestId,
        })
      );
    },
    [invokeStudyRpc]
  );

  const sendStudyModeRpc = useCallback(
    <T,>(
      prefix: string,
      payloadBuilder: (requestId: string) => ClientMessage,
      timeoutMs = 120000
    ): Promise<T> => {
      const requestId = `sm_${prefix}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
      return transport.invoke<T>(payloadBuilder(requestId), {
        requestId,
        timeoutMs,
        timeoutMessage: `Tempo limite excedido (${prefix}).`,
        requireReady: true,
        matchResponse: (msg): ResponseDecision<T> => {
          if (msg.type === 'study_error') {
            return {
              kind: 'reject',
              error: new Error((msg as { message?: string }).message || 'Erro no módulo de estudo'),
            };
          }
          if (msg.type === 'study_document_failed') {
            return {
              kind: 'reject',
              error: new Error((msg as { error?: string }).error || 'Falha ao processar documento'),
            };
          }
          if (msg.type === 'study_generation_cancelled') {
            return {
              kind: 'reject',
              error: new Error('Geração cancelada pelo utilizador'),
            };
          }
          if (msg.type.startsWith('study_mode_') && msg.type !== 'study_mode_progress_event') {
            return { kind: 'resolve', value: msg as unknown as T };
          }
          return { kind: 'ignore' };
        },
      });
    },
    [transport]
  );

  const studyModesApi: StudyModesBridge = useMemo(
    () => ({
      getReadiness: (documentId) =>
        sendStudyModeRpc<any>('readiness', (reqId) => ({
          type: 'study_mode_get_readiness',
          document_id: documentId,
          request_id: reqId,
        }), 30000).then((r) => r.readiness),
      getFlashcards: (documentId) =>
        sendStudyModeRpc<any>('get_fc', (reqId) => ({
          type: 'study_mode_get_flashcards',
          document_id: documentId,
          request_id: reqId,
        }), 30000),
      generateFlashcards: (documentId, forceRegenerate = false, targetCards = 16) =>
        sendStudyModeRpc<any>('gen_fc', (reqId) => ({
          type: 'study_mode_generate_flashcards',
          document_id: documentId,
          force_regenerate: forceRegenerate,
          target_cards: targetCards,
          request_id: reqId,
        }), 300000),
      editFlashcard: (documentId, cardId, updates) =>
        sendStudyModeRpc<any>('edit_fc', (reqId) => ({
          type: 'study_mode_edit_flashcard',
          document_id: documentId,
          card_id: cardId,
          ...updates,
          request_id: reqId,
        }), 30000).then((r) => r.flashcard),
      deleteFlashcard: (documentId, cardId) =>
        sendStudyModeRpc<any>('del_fc', (reqId) => ({
          type: 'study_mode_delete_flashcard',
          document_id: documentId,
          card_id: cardId,
          request_id: reqId,
        }), 30000).then((r) => Boolean(r.deleted)),
      createFlashcard: (documentId, fields) =>
        sendStudyModeRpc<any>('new_fc', (reqId) => ({
          type: 'study_mode_create_flashcard',
          document_id: documentId,
          ...fields,
          request_id: reqId,
        }), 30000).then((r) => r.flashcard),
      regenerateFlashcard: (documentId, cardId, allowOverwriteEdited = false) =>
        sendStudyModeRpc<any>('regen_fc', (reqId) => ({
          type: 'study_mode_regenerate_flashcard',
          document_id: documentId,
          card_id: cardId,
          allow_overwrite_edited: allowOverwriteEdited,
          request_id: reqId,
        }), 120000).then((r) => r.flashcard),
      reviewFlashcard: (documentId, cardId, rating, confidence = 3) =>
        sendStudyModeRpc<any>('rev_fc', (reqId) => ({
          type: 'study_mode_review_flashcard',
          document_id: documentId,
          card_id: cardId,
          rating,
          confidence,
          request_id: reqId,
        }), 30000),
      getCornell: (documentId) =>
        sendStudyModeRpc<any>('get_cn', (reqId) => ({
          type: 'study_mode_get_cornell',
          document_id: documentId,
          request_id: reqId,
        }), 30000),
      generateCornell: (documentId, forceRegenerate = false) =>
        sendStudyModeRpc<any>('gen_cn', (reqId) => ({
          type: 'study_mode_generate_cornell',
          document_id: documentId,
          force_regenerate: forceRegenerate,
          request_id: reqId,
        }), 300000),
      editCornellEntry: (documentId, sectionId, updates) =>
        sendStudyModeRpc<any>('edit_cn', (reqId) => ({
          type: 'study_mode_edit_cornell_entry',
          document_id: documentId,
          section_id: sectionId,
          ...updates,
          request_id: reqId,
        }), 30000).then((r) => r.entry),
      addCornellNote: (documentId, sectionId, content, isImportant = false) =>
        sendStudyModeRpc<any>('note_cn', (reqId) => ({
          type: 'study_mode_add_cornell_note',
          document_id: documentId,
          section_id: sectionId,
          content,
          is_important: isImportant,
          request_id: reqId,
        }), 30000).then((r) => r.personal_note),
      exportCornellVault: (documentId) =>
        sendStudyModeRpc<any>('exp_cn', (reqId) => ({
          type: 'study_mode_export_cornell_vault',
          document_id: documentId,
          request_id: reqId,
        }), 30000),
      getAssessments: (documentId) =>
        sendStudyModeRpc<any>('get_ass', (reqId) => ({
          type: 'study_mode_get_assessments',
          document_id: documentId,
          request_id: reqId,
        }), 30000),
      generateAssessment: (documentId, config) =>
        sendStudyModeRpc<any>('gen_ass', (reqId) => ({
          type: 'study_mode_generate_assessment',
          document_id: documentId,
          config,
          request_id: reqId,
        }), 300000).then((r) => r.assessment),
      checkQuestion: (documentId, assessmentId, questionId, answer, useLlmForOpen = false) =>
        sendStudyModeRpc<any>('chk_q', (reqId) => ({
          type: 'study_mode_check_question',
          document_id: documentId,
          assessment_id: assessmentId,
          question_id: questionId,
          answer,
          use_llm_for_open: useLlmForOpen,
          request_id: reqId,
        }), 90000).then((r) => r.outcome),
      submitAssessment: (documentId, assessmentId, answers, useLlmForOpen = false) =>
        sendStudyModeRpc<any>('sub_ass', (reqId) => ({
          type: 'study_mode_submit_assessment',
          document_id: documentId,
          assessment_id: assessmentId,
          answers,
          use_llm_for_open: useLlmForOpen,
          request_id: reqId,
        }), 120000),
      getActiveRecall: (documentId) =>
        sendStudyModeRpc<any>('get_ar', (reqId) => ({
          type: 'study_mode_get_active_recall',
          document_id: documentId,
          request_id: reqId,
        }), 30000),
      generateActiveRecall: (documentId, forceRegenerate = false, targetPrompts = 8) =>
        sendStudyModeRpc<any>('gen_ar', (reqId) => ({
          type: 'study_mode_generate_active_recall',
          document_id: documentId,
          force_regenerate: forceRegenerate,
          target_prompts: targetPrompts,
          request_id: reqId,
        }), 300000),
      submitActiveRecall: (documentId, promptId, payload) =>
        sendStudyModeRpc<any>('sub_ar', (reqId) => ({
          type: 'study_mode_submit_active_recall',
          document_id: documentId,
          prompt_id: promptId,
          ...payload,
          request_id: reqId,
        }), 120000),
      getDailyQueue: (documentId, dailyNewLimit = 10, dailyReviewLimit = 30) =>
        sendStudyModeRpc<any>('dq', (reqId) => ({
          type: 'study_mode_get_daily_queue',
          document_id: documentId,
          daily_new_limit: dailyNewLimit,
          daily_review_limit: dailyReviewLimit,
          request_id: reqId,
        }), 30000).then((r) => r.queue),
      getProgress: (documentId, recompute = true) =>
        sendStudyModeRpc<any>('prog', (reqId) => ({
          type: 'study_mode_get_progress',
          document_id: documentId,
          recompute,
          request_id: reqId,
        }), 30000).then((r) => r.progress),
      startSession: (payload) =>
        sendStudyModeRpc<any>('sess_start', (reqId) => ({
          type: 'study_mode_start_session',
          ...payload,
          request_id: reqId,
        }), 30000).then((r) => r.session),
      updateSession: (sessionId, payload) =>
        sendStudyModeRpc<any>('sess_upd', (reqId) => ({
          type: 'study_mode_update_session',
          session_id: sessionId,
          ...payload,
          request_id: reqId,
        }), 30000).then((r) => r.session),
      pauseSession: (sessionId) =>
        sendStudyModeRpc<any>('sess_pause', (reqId) => ({
          type: 'study_mode_pause_session',
          session_id: sessionId,
          request_id: reqId,
        }), 30000).then((r) => r.session),
      resumeSession: (sessionId) =>
        sendStudyModeRpc<any>('sess_res', (reqId) => ({
          type: 'study_mode_resume_session',
          session_id: sessionId,
          request_id: reqId,
        }), 30000).then((r) => r.session),
      completeSession: (sessionId, summaryStats) =>
        sendStudyModeRpc<any>('sess_comp', (reqId) => ({
          type: 'study_mode_complete_session',
          session_id: sessionId,
          summary_stats: summaryStats,
          request_id: reqId,
        }), 30000).then((r) => r.session),
      listSessions: (documentId, status) =>
        sendStudyModeRpc<any>('sess_list', (reqId) => ({
          type: 'study_mode_list_sessions',
          document_id: documentId,
          status,
          request_id: reqId,
        }), 30000).then((r) => r.sessions || []),
    }),
    [sendStudyModeRpc]
  );

  const updateActiveStudyContext = useCallback((ctx: StudyUiContextPayload) => {
    activeStudyContextRef.current = {
      ...activeStudyContextRef.current,
      ...ctx,
    };
  }, []);

  const getStudyDocumentDetails = useCallback(
    (documentId: string) => {
      if (!isReady() || !documentId) return;
      sendClientMessage({
        type: 'study_get_document',
        document_id: documentId,
      });
    },
    [isReady, sendClientMessage]
  );

  const addStudyReadingNote = useCallback(
    (documentId: string, page: number, note: string, selection = '', sectionId = '') => {
      if (!isReady() || !documentId || !note.trim()) return;
      sendClientMessage({
        type: 'study_add_reading_note',
        document_id: documentId,
        page,
        selection,
        note: note.trim(),
        section_id: sectionId,
      });
    },
    [isReady, sendClientMessage]
  );

  const addStudyHighlight = useCallback(
    (documentId: string, page: number, selectedText: string, context = '', color = 'sky') => {
      if (!isReady() || !documentId || !selectedText.trim()) return;
      sendClientMessage({
        type: 'study_add_highlight',
        document_id: documentId,
        page,
        selected_text: selectedText.trim(),
        context,
        color,
      });
    },
    [isReady, sendClientMessage]
  );

  const navigateToStudyTarget = useCallback(
    (target: Partial<StudyNavigatePayload>) => {
      const validTabs = new Set([
        'overview',
        'home',
        'library',
        'reader',
        'summary',
        'notes',
        'flashcards',
        'active_recall',
        'quiz',
        'adaptive',
        'knowledge',
        'generated_document',
      ]);
      const safeTab = target.tab && validTabs.has(target.tab) ? target.tab : 'library';
      setChatPanelOpen(false);
      activeDomainRef.current = 'study';
      setActiveDomainState('study');
      if (target.document_id && !studyDocuments.some((d) => d.document_id === target.document_id)) {
        listStudyDocuments();
      }
      setStudyNavigationTarget({
        target: 'study',
        ...target,
        tab: safeTab,
        nonce: Date.now() + Math.random(),
      });
    },
    [listStudyDocuments, studyDocuments]
  );

  const cancelStudyOperation = useCallback(
    (operationId: string, documentId?: string) => {
      if (!isReady()) return;
      sendClientMessage({
        type: 'study_cancel_operation',
        operation_id: operationId,
        document_id: documentId,
      });
    },
    [isReady, sendClientMessage]
  );

  const setActiveDomain = useCallback((domain: SpatialBoardDomain) => {
    activeDomainRef.current = domain;
    setActiveDomainState(domain);
  }, []);

  const openSpatialBoard = useCallback(
    (domain: SpatialBoardDomain = 'study', query = '') => {
      const q = query.trim().toLowerCase();
      setFocusedCardId(null);
      activeDomainRef.current = domain;
      setActiveDomainState(domain);

      if (domain === 'sentinel') {
        sendClientMessage({ type: 'sentinel_get_status' });
        setActiveBoard(buildSentinelSpatialBoard(sentinelStatus, sentinelEvents));
        return;
      }

      if (domain === 'obsidian') {
        if (notes.length === 0) getNotes();
        setActiveBoard(buildObsidianSpatialBoard(notes, studyDocuments));
        return;
      }

      if (domain === 'project') {
        if (projects.length === 0) listProjects();
        const targetId = q || projectContext?.project_id || '';
        if (q && projectContext?.project_id !== q) {
          openProject(q);
        }
        setActiveBoard(buildProjectSpatialBoard(targetId || 'projetos', projects, projectContext, projectFiles, previewUrl));
        return;
      }

      // Default: study domain
      if (studyDocuments.length === 0) {
        listStudyDocuments();
      }
      const matchedDoc =
        (q
          ? studyDocuments.find(
              (d) =>
                d.document_id.toLowerCase() === q ||
                d.title.toLowerCase().includes(q) ||
                d.subject.toLowerCase().includes(q) ||
                String((d as unknown as Record<string, unknown>).filename || '')
                  .toLowerCase()
                  .includes(q)
            )
          : undefined) || studyDocuments[0];

      setActiveBoard(buildStudySpatialBoard(matchedDoc, studyDocuments.length));
    },
    [
      getNotes,
      listProjects,
      listStudyDocuments,
      notes,
      openProject,
      previewUrl,
      projectContext,
      projectFiles,
      projects,
      sendClientMessage,
      sentinelEvents,
      sentinelStatus,
      studyDocuments,
    ]
  );

  const closeSpatialBoard = useCallback(() => {
    setFocusedCardId(null);
    setActiveBoard(null);
  }, []);

  const focusSpatialCard = useCallback(
    (cardIdOrQuery: string | null) => {
      if (!cardIdOrQuery) {
        setFocusedCardId(null);
        return;
      }
      if (!activeBoard) return;
      const q = cardIdOrQuery.trim().toLowerCase();
      const exact = activeBoard.cards.find((c) => c.id === cardIdOrQuery);
      if (exact) {
        setFocusedCardId(exact.id);
        return;
      }
      const fuzzy = activeBoard.cards.find(
        (c) =>
          c.title.toLowerCase().includes(q) ||
          c.type.toLowerCase().includes(q) ||
          (q.includes('gráfico') && c.type === 'bar_chart') ||
          (q.includes('grafico') && c.type === 'bar_chart') ||
          (q.includes('vídeo') && c.type === 'video') ||
          (q.includes('video') && c.type === 'video') ||
          (q.includes('resumo') && c.id.includes('summary')) ||
          (q.includes('cornell') && c.type === 'study_notes') ||
          (q.includes('nota') && c.type === 'study_notes') ||
          (q.includes('código') && c.type === 'code_files') ||
          (q.includes('ficheiro') && c.type === 'code_files')
      );
      if (fuzzy) {
        setFocusedCardId(fuzzy.id);
      }
    },
    [activeBoard]
  );

  useEffect(() => {
    handleSpatialBoardIntentRef.current = (rawText: string) => {
      const lower = rawText
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();

      if (
        lower.includes('podes descansar') ||
        lower.includes('fecha o quadro') ||
        lower.includes('fechar o quadro') ||
        lower.includes('volta ao centro') ||
        lower.includes('limpa o quadro')
      ) {
        closeSpatialBoard();
        return;
      }

      const maxMatch = lower.match(
        /(?:maximiza|foca|amplia)\s+(?:o\s+|a\s+)?(?:grafico|cartao|card|video|resumo|nota|cornell)?\s*(.*)/i
      );
      if (maxMatch) {
        const target = maxMatch[1]?.trim() || rawText;
        focusSpatialCard(target);
        return;
      }

      if (
        lower.includes('abre o quadro') ||
        lower.includes('abrir o quadro') ||
        lower.includes('mostra o quadro') ||
        lower.includes('monta o quadro') ||
        lower.includes('spatial board')
      ) {
        if (lower.includes('sentinel') || lower.includes('seguranca')) {
          openSpatialBoard('sentinel');
        } else if (lower.includes('obsidian') || lower.includes('vault') || lower.includes('cofre')) {
          openSpatialBoard('obsidian');
        } else if (lower.includes('projeto') || lower.includes('dina')) {
          const projMatch = lower.match(/projeto\s+([a-z0-9_-]+)/i);
          openSpatialBoard('project', projMatch ? projMatch[1] : 'dina');
        } else {
          const topicMatch = rawText.match(/(?:tema|documento|aula|sobre|de)\s+([^,.?!]+)/i);
          openSpatialBoard('study', topicMatch ? topicMatch[1].trim() : '');
        }
      }
    };
  }, [closeSpatialBoard, focusSpatialCard, openSpatialBoard]);

  // Keep active Spatial Board fresh when underlying data updates
  useEffect(() => {
    if (!activeBoard) return;
    if (activeBoard.domain === 'study' && activeBoard.documentId) {
      const updatedDoc = studyDocuments.find((d) => d.document_id === activeBoard.documentId);
      if (updatedDoc) {
        setActiveBoard(buildStudySpatialBoard(updatedDoc));
      }
    } else if (activeBoard.domain === 'project' && activeBoard.projectId) {
      setActiveBoard(
        buildProjectSpatialBoard(activeBoard.projectId, projects, projectContext, projectFiles, previewUrl)
      );
    } else if (activeBoard.domain === 'obsidian') {
      setActiveBoard(buildObsidianSpatialBoard(notes, studyDocuments));
    } else if (activeBoard.domain === 'sentinel') {
      setActiveBoard(buildSentinelSpatialBoard(sentinelStatus, sentinelEvents));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyDocuments, projectFiles, previewUrl, notes, sentinelStatus, sentinelEvents]);

  const getSentinelStatus = useCallback(() => {
    sendClientMessage({
      type: 'sentinel_get_status',
    });
  }, [sendClientMessage]);

  const runSentinelAudit = useCallback(() => {
    setIsSentinelAuditing(true);
    sendClientMessage({
      type: 'sentinel_run_audit',
    });
  }, [sendClientMessage]);

  const getSentinelBaseline = useCallback(() => {
    sendClientMessage({
      type: 'sentinel_get_baseline',
    });
  }, [sendClientMessage]);

  const acceptSentinelKnownGood = useCallback((itemKey: string, reason?: string) => {
    sendClientMessage({
      type: 'sentinel_accept_known_good',
      item_key: itemKey,
      reason: reason || 'Aprovado pelo utilizador na interface',
    });
  }, [sendClientMessage]);

  const getSentinelActions = useCallback(() => {
    sendClientMessage({
      type: 'sentinel_get_actions',
    });
  }, [sendClientMessage]);

  const approveSentinelAction = useCallback((actionId: string, user?: string, sessionId?: string, incidentId?: string) => {
    sendClientMessage({
      type: 'sentinel_approve_action',
      action_id: actionId,
      user: user || 'human_operator',
      session_id: sessionId || 'web_session',
      incident_id: incidentId || '',
    });
  }, [sendClientMessage]);

  const rejectSentinelAction = useCallback((actionId: string, reason: string, user?: string) => {
    sendClientMessage({
      type: 'sentinel_reject_action',
      action_id: actionId,
      user: user || 'human_operator',
      reason,
    });
  }, [sendClientMessage]);

  const rollbackSentinelAction = useCallback((actionId: string, user?: string, sessionId?: string) => {
    sendClientMessage({
      type: 'sentinel_rollback_action',
      action_id: actionId,
      user: user || 'human_operator',
      session_id: sessionId || 'web_session',
    });
  }, [sendClientMessage]);

  const submitSentinelReview = useCallback((eventId: string, finalClassification: string, reason: string, operator?: string) => {
    sendClientMessage({
      type: 'sentinel_submit_review',
      event_id: eventId,
      final_classification: finalClassification,
      reason: reason || 'Revisão humana em Shadow Mode',
      operator: operator || 'human_operator',
    });
  }, [sendClientMessage]);

  const sendMissionControlCommand = useCallback((cmd: MissionControlCommandPayload) => {
    sendClientMessage({
      type: 'mission_control_command',
      ...cmd,
    });
  }, [sendClientMessage]);

  const getMissionControlState = useCallback((scenario?: string) => {
    sendClientMessage({
      type: 'mission_control_get',
      scenario,
    });
  }, [sendClientMessage]);

  const clearMissionControlCommandResult = useCallback(() => {
    setMissionControlCommandResult(null);
  }, []);

  const sendMissionIntentPreview = useCallback((missionId: string, textOrDelta: string | Record<string, unknown>) => {
    if (typeof textOrDelta === 'string') {
      sendClientMessage({
        type: 'mission_intent_preview',
        mission_id: missionId,
        text: textOrDelta,
      });
    } else {
      sendClientMessage({
        type: 'mission_intent_preview',
        mission_id: missionId,
        delta: textOrDelta,
      });
    }
  }, [sendClientMessage]);

  const sendMissionIntentChange = useCallback((missionId: string, textOrDelta: string | Record<string, unknown>, preApproved?: boolean) => {
    if (typeof textOrDelta === 'string') {
      sendClientMessage({
        type: 'mission_intent_change',
        mission_id: missionId,
        text: textOrDelta,
        pre_approved: preApproved ?? false,
      });
    } else {
      sendClientMessage({
        type: 'mission_intent_change',
        mission_id: missionId,
        delta: textOrDelta,
        pre_approved: preApproved ?? false,
      });
    }
  }, [sendClientMessage]);

  const clearMissionIntentPreviewResult = useCallback(() => {
    setMissionIntentPreviewResult(null);
  }, []);

  const clearMissionIntentResult = useCallback(() => {
    setMissionIntentResult(null);
  }, []);

  const approvePermissionRequest = useCallback((requestId: string, projectId?: string, missionId?: string) => {
    sendClientMessage({
      type: 'permission_approve',
      request_id: requestId,
      project_id: projectId,
      mission_id: missionId,
    });
  }, [sendClientMessage]);

  const denyPermissionRequest = useCallback((requestId: string, reason = 'Recusado pelo operador humano', projectId?: string, missionId?: string) => {
    sendClientMessage({
      type: 'permission_deny',
      request_id: requestId,
      reason,
      project_id: projectId,
      mission_id: missionId,
    });
  }, [sendClientMessage]);

  const rollbackPermissionRequest = useCallback((requestId: string) => {
    sendClientMessage({
      type: 'permission_rollback',
      request_id: requestId,
    });
  }, [sendClientMessage]);

  const getPendingPermissions = useCallback(() => {
    sendClientMessage({
      type: 'permission_get_pending',
    });
  }, [sendClientMessage]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        systemStatus,
        voiceStatus,
        chatMessages,
        systemLogs,
        clearSystemLogs,
        chatSessions,
        activeSessionId,
        switchChatSession,
        createNewChatSession,
        deleteChatSession,
        renameChatSession,
        promptHistory,
        debateMessages,
        projectFiles,
        projectFileHashes,
        projectFileSaveState,
        isSavingProjectFile,
        activeTemplate,
        kanban,
        arena,
        projectOutput,
        isProjectRunning,
        previewUrl,
        chatPanelOpen,
        setChatPanelOpen,
        devPanelOpen,
        setDevPanelOpen,
        sendDirective,
        selectTemplate,
        toggleVoice,
        runProject,
        stopProject,
        clearChat,
        notes,
        rules,
        architecture,
        decisions,
        currentNote,
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
        getNotes,
        readNote,
        saveNote,
        deleteRule,
        deleteArchitecture,
        deleteDecision,
        plannerState,
        missions,
        missionSnapshot,
        architectureSnapshot,
        astState,
        getPlannerState,
        getMissions,
        openMission,
        deleteMission,
        cancelMissionExecution,
        sendMissionOperation,
        subdagHistory,
        getSubDagHistory,
        adaptationHistory,
        planEvaluationResult,
        evaluateMissionPlan,
        proposeMissionAdaptation,
        getMissionAdaptationHistory,
        getAstState,
        sandboxStatus,
        projects,
        projectContext,
        projectReferences,
        semanticResults,
        isIndexingProject,
        listProjects,
        openProject,
        createProject,
        deleteProject,
        saveProjectFile,
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
        setActiveLecture,
        sentinelStatus,
        sentinelEvents,
        sentinelBaseline,
        sentinelActions,
        isSentinelAuditing,
        getSentinelStatus,
        runSentinelAudit,
        getSentinelBaseline,
        acceptSentinelKnownGood,
        getSentinelActions,
        approveSentinelAction,
        rejectSentinelAction,
        rollbackSentinelAction,
        submitSentinelReview,
        missionControlState,
        missionControlCommandResult,
        sendMissionControlCommand,
        getMissionControlState,
        clearMissionControlCommandResult,
        missionIntentPreviewResult,
        missionIntentResult,
        sendMissionIntentPreview,
        sendMissionIntentChange,
        clearMissionIntentPreviewResult,
        clearMissionIntentResult,
        studyDocuments,
        activeStudyQuiz,
        studyQuizResult,
        studyFlashcards,
        listStudyDocuments,
        uploadStudyDocument,
        ingestStudyVideoUrl,
        lastStudyDocumentError,
        deleteStudyDocument,
        generateStudyQuiz,
        submitStudyQuiz,
        searchStudyRag,
        listStudyFlashcards,
        reviewStudyFlashcard,
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
        studyOperations,
        studyNavigationTarget,
        studyReadingNotes,
        studyHighlights,
        getStudyDocumentDetails,
        addStudyReadingNote,
        addStudyHighlight,
        updateActiveStudyContext,
        navigateToStudyTarget,
        cancelStudyOperation,
        activeDomain,
        setActiveDomain,
        spatialOverviewOpen,
        setSpatialOverviewOpen,
        activeBoard,
        focusedCardId,
        openSpatialBoard,
        closeSpatialBoard,
        focusSpatialCard,
        approvePermissionRequest,
        denyPermissionRequest,
        rollbackPermissionRequest,
        getPendingPermissions,
        sendClientMessage,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
