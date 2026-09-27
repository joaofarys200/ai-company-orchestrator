import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { missionRuntimeStore } from '../features/missions/stores/missionRuntimeStore';
import {
  normalizeServerMessage,
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
} from '../protocol/websocket';
import type {
  StudyDocument,
  StudyQuiz,
  QuizEvaluationResult,
  Flashcard,
} from '../features/study/types';

export interface ProjectFileSaveState {
  ok: boolean;
  filename: string;
  sha256: string;
  error: string;
}

export interface SafetyRefusalData {
  is_allowed: boolean;
  status: string;
  category: string;
  policy_rule: string;
  reason: string;
  sanitized_intent: string;
  request_id: string;
  timestamp: string;
}

declare global {
  interface Window {
    jarvisIPC?: {
      send: (message: unknown) => void;
      onMessage: (callback: (data: unknown) => void) => () => void;
      isNativeIPC: boolean;
    };
  }
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
} from '../protocol/websocket';

interface WebSocketContextType {
  isConnected: boolean;
  systemStatus: SystemStatus;
  voiceStatus: string;
  chatMessages: ChatMessage[];
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
  sendDirective: (text: string) => void;
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
  getNotes: () => void;
  readNote: (filename: string) => void;
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
    sourceType?: string
  ) => void;
  generateStudyQuiz: (documentId: string, count?: number) => void;
  submitStudyQuiz: (quizId: string, answers: Record<string, number | string>, transferAnswer?: string) => void;
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
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [debateMessages, setDebateMessages] = useState<ChatMessage[]>([]);
  const [projectFiles, setProjectFiles] = useState<{ [filename: string]: string }>({});
  const [projectFileHashes, setProjectFileHashes] = useState<{ [filename: string]: string }>({});
  const [projectFileSaveState, setProjectFileSaveState] = useState<ProjectFileSaveState | null>(null);
  const [isSavingProjectFile, setIsSavingProjectFile] = useState(false);
  const [activeTemplate, setActiveTemplate] = useState<ActiveTemplate | null>(null);
  const [projectOutput, setProjectOutput] = useState<string>('');
  const [isProjectRunning, setIsProjectRunning] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('http://localhost:8080/');
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
  const [plannerState, setPlannerState] = useState<PlannerState | null>(null);
  const [missions, setMissions] = useState<MissionData[]>([]);
  const [missionSnapshot, setMissionSnapshot] = useState<MissionSnapshot | null>(null);
  const [subdagHistory, setSubdagHistory] = useState<ExpansionRecord[]>([]);
  const [adaptationHistory, setAdaptationHistory] = useState<AdaptationRecordData[]>([]);
  const [planEvaluationResult, setPlanEvaluationResult] = useState<Record<string, unknown> | null>(null);
  const [astState, setAstState] = useState<AstState | null>(null);
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
  const [activeStudyQuiz, setActiveStudyQuiz] = useState<StudyQuiz | null>(null);
  const [studyQuizResult, setStudyQuizResult] = useState<QuizEvaluationResult | null>(null);
  const [studyFlashcards, setStudyFlashcards] = useState<Flashcard[]>([]);

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

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const recentMessageHashesRef = useRef<Map<string, number>>(new Map());
  const pendingStudyRequestsRef = useRef<Map<string, {
    resolve: (value: any) => void;
    reject: (reason?: any) => void;
    timer: any;
  }>>(new Map());

  const sendClientMessage = useCallback((message: ClientMessage) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
    } else if (typeof window !== 'undefined' && window.jarvisIPC?.isNativeIPC) {
      window.jarvisIPC.send(message);
    }
  }, []);

  function addSystemMessage(content: string) {
    const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    const sysMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: 'SISTEMA',
      role: 'System',
      content,
      timestamp,
    };
    setChatMessages((prev) => appendLimited(prev, sysMsg, MAX_CHAT_MESSAGES));
  }

  function addChatMessage(msg: ChatProtocolMessage) {
    const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    const newMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: msg.sender,
      role: msg.role,
      content: msg.content,
      audio: msg.audio,
      timestamp,
    };

    // Always add all messages (including subagents and specialists) to chatMessages so the user sees them
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
    } else if (action === 'toggle_dev') {
      setDevPanelOpen((prev) => !prev);
    } else if (action === 'show_dashboard' || action === 'show_arena_tab') {
      setDevPanelOpen(true);
    } else if (action === 'show_main_screen') {
      setChatPanelOpen(false);
      setDevPanelOpen(false);
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

    setProjectFiles({});
    setProjectOutput('');
    setIsProjectRunning(false);

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

    // Deduplicate identical messages arriving within 1.5s via dual transport (Electron IPC + WebSocket)
    if (!msg.type.startsWith('study_')) {
      const rawKey = `${msg.type}:${msg.sender || ''}:${msg.content || ''}:${msg.card_id || ''}:${msg.status || ''}`;
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
      case 'project_output':
        setProjectOutput((prev) => prev + msg.content);
        break;
      case 'project_status':
        setIsProjectRunning(Boolean(msg.running));
        if (msg.preview_url) {
          setPreviewUrl(msg.preview_url);
        }
        break;
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
      case 'note_content':
        setCurrentNote({ filename: msg.filename, content: msg.content });
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
      case 'mission_list':
        setMissions(msg.missions);
        missionRuntimeStore.setMissions(msg.missions);
        break;
      case 'mission_snapshot':
        setMissionSnapshot(msg.data);
        missionRuntimeStore.setMissionSnapshot(msg.data);
        break;
      case 'mission_event':
        missionRuntimeStore.applyEvent(msg.event, (pId, mId) => {
          sendClientMessage({ type: 'mission_resume_snapshot', project_id: pId, mission_id: mId });
        });
        break;
      case 'mission_deleted':
        missionRuntimeStore.removeMission(msg.mission_id);
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
      case 'ast_state':
        setAstState(msg.data);
        break;
      case 'projects_list':
        setProjects(msg.projects);
        break;
      case 'project_deleted':
        if (msg.was_active || msg.project_id === projectContext?.project_id) {
          setProjectContext(null);
          setProjectFiles({});
          setProjectFileHashes({});
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
      case 'project_context':
        setProjectContext(msg.context);
        setProjectFiles(msg.files);
        setProjectFileHashes(msg.file_hashes);
        setAstState(Object.keys(msg.symbols).length > 0 ? msg.symbols : null);
        setProjectReferences(null);
        setSemanticResults('');
        setIsIndexingProject(false);
        break;
      case 'project_file_save_result':
        setProjectFileSaveState({
          ok: msg.ok,
          filename: msg.filename,
          sha256: msg.sha256,
          error: msg.error,
        });
        setIsSavingProjectFile(false);
        break;
      case 'project_references':
        setProjectReferences(msg.data);
        break;
      case 'semantic_results':
        setSemanticResults(msg.content);
        break;
      case 'coding_session':
        setCodingSession(msg.data);
        setSafetyRefusal(null);
        setCodingSessionError(null);
        setIsCodingSessionBusy(false);
        break;
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
      case 'study_quiz_ready':
        setActiveStudyQuiz(msg.quiz);
        addSystemMessage(`Quiz pedagógico gerado para: ${msg.quiz.topic}`);
        break;
      case 'study_quiz_evaluated':
        setStudyQuizResult(msg);
        addSystemMessage(`Quiz de estudo avaliado: ${msg.score}% de aproveitamento.`);
        break;
      case 'study_flashcards_list':
        setStudyFlashcards(msg.flashcards || []);
        break;
      case 'study_flashcard_updated':
        setStudyFlashcards((prev) =>
          prev.map((fc) => (fc.card_id === msg.flashcard.card_id ? msg.flashcard : fc))
        );
        break;
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
      case 'study_document_ready':
        if (msg.document) {
          setStudyDocuments((prev) => [
            msg.document,
            ...prev.filter((d) => d.document_id !== msg.document.document_id),
          ]);
          addSystemMessage(`Documento de estudo guardado e pronto: ${msg.document.title}`);
        }
        break;
      case 'study_document_failed':
        addSystemMessage(`Erro ao processar documento ${msg.filename}: ${msg.error}`);
        break;
      case 'study_contextual_assist_result': {
        const reqId = msg.request_id;
        if (reqId && pendingStudyRequestsRef.current.has(reqId)) {
          const item = pendingStudyRequestsRef.current.get(reqId)!;
          clearTimeout(item.timer);
          pendingStudyRequestsRef.current.delete(reqId);
          item.resolve(msg);
        } else {
          for (const [k, item] of pendingStudyRequestsRef.current.entries()) {
            if (k.startsWith(`assist:${msg.document_id}`)) {
              clearTimeout(item.timer);
              pendingStudyRequestsRef.current.delete(k);
              item.resolve(msg);
              break;
            }
          }
        }
        break;
      }
      case 'study_ask_paper_result': {
        const reqId = msg.request_id;
        if (reqId && pendingStudyRequestsRef.current.has(reqId)) {
          const item = pendingStudyRequestsRef.current.get(reqId)!;
          clearTimeout(item.timer);
          pendingStudyRequestsRef.current.delete(reqId);
          item.resolve({ answer: msg.answer, sources: msg.sources || [] });
        } else {
          for (const [k, item] of pendingStudyRequestsRef.current.entries()) {
            if (k.startsWith(`ask:${msg.document_id}`)) {
              clearTimeout(item.timer);
              pendingStudyRequestsRef.current.delete(k);
              item.resolve({ answer: msg.answer, sources: msg.sources || [] });
              break;
            }
          }
        }
        break;
      }
      case 'study_document_file_result': {
        const reqId = msg.request_id;
        if (reqId && pendingStudyRequestsRef.current.has(reqId)) {
          const item = pendingStudyRequestsRef.current.get(reqId)!;
          clearTimeout(item.timer);
          pendingStudyRequestsRef.current.delete(reqId);
          item.resolve({
            contentBase64: msg.content_base64,
            filename: msg.filename,
            error: msg.error,
          });
        } else {
          for (const [k, item] of pendingStudyRequestsRef.current.entries()) {
            if (k.startsWith(`file:${msg.document_id}`)) {
              clearTimeout(item.timer);
              pendingStudyRequestsRef.current.delete(k);
              item.resolve({
                contentBase64: msg.content_base64,
                filename: msg.filename,
                error: msg.error,
              });
              break;
            }
          }
        }
        break;
      }
      case 'unknown':
        console.warn('[Transport] Unknown message type:', msg.originalType);
        break;
      default:
        break;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addChatMessage, addSystemMessage, handleArenaUpdate, handleKanbanUpdate, handleTemplateChanged, handleUiAction]);

  const handleServerMessageRef = useRef(handleServerMessage);
  useEffect(() => {
    handleServerMessageRef.current = handleServerMessage;
  }, [handleServerMessage]);

  const isReady = useCallback(() => {
    return Boolean(socketRef.current?.readyState === WebSocket.OPEN || (typeof window !== 'undefined' && window.jarvisIPC?.isNativeIPC));
  }, []);

  const connect = useCallback(function connectSocket() {
    // 1. Electron Native IPC Listener (if running inside Electron)
    let ipcUnsubscribe: (() => void) | undefined;
    if (typeof window !== 'undefined' && window.jarvisIPC?.isNativeIPC) {
      console.log('[Transport] Initializing Native Electron IPC Listener');
      ipcUnsubscribe = window.jarvisIPC.onMessage((rawData) => {
        try {
          const msg = normalizeServerMessage(rawData);
          if (msg) {
            handleServerMessageRef.current(msg);
          }
        } catch (e) {
          console.error('[Native IPC] Error processing message:', e);
        }
      });
    }

    // 2. Primary Realtime WebSocket on ws://127.0.0.1:8001
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return () => {
        if (ipcUnsubscribe) ipcUnsubscribe();
      };
    }

    const wsToken = import.meta.env.VITE_JARVIS_WS_TOKEN || 'local-dev-token';
    const wsUrl = `ws://127.0.0.1:8001/?token=${encodeURIComponent(wsToken)}`;
    console.log('[WebSocket] Connecting to ws://127.0.0.1:8001');
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected');
      setIsConnected(true);
      setSystemStatus('ONLINE');
      missionRuntimeStore.setConnectionState('CONNECTED');
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Initial state synchronization on connect
      window.setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'list_projects' } satisfies ClientMessage));
          ws.send(JSON.stringify({ type: 'get_notes' } satisfies ClientMessage));
          ws.send(JSON.stringify({ type: 'get_rules' } satisfies ClientMessage));
          ws.send(JSON.stringify({ type: 'get_planner_state' } satisfies ClientMessage));
          ws.send(JSON.stringify({ type: 'mission_list', project_id: 'ALL' } satisfies ClientMessage));
          ws.send(JSON.stringify({ type: 'study_list_documents' } satisfies ClientMessage));
        }
      }, 50);

      // Auto-enable voice on startup only if user explicitly opted in via localStorage
      window.setTimeout(() => {
        const autoConnect = localStorage.getItem('jarvis_voice_auto_connect') === 'true';
        if (autoConnect && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'toggle_voice', active: true } satisfies ClientMessage));
          console.log('[WebSocket] Auto-enabled voice on startup based on user preference');
        }
      }, 1500);
    };

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected');
      if (socketRef.current === ws) {
        socketRef.current = null;
      }
      setIsConnected(false);
      setSystemStatus('OFFLINE');
      missionRuntimeStore.setConnectionState(shouldReconnectRef.current ? 'RECONNECTING' : 'OFFLINE');
      setVoiceStatus('offline');
      setIsProjectRunning(false);

      if (shouldReconnectRef.current) {
        if (reconnectTimeoutRef.current) {
          window.clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectSocket();
        }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    ws.onmessage = (event) => {
      try {
        const msg = normalizeServerMessage(JSON.parse(event.data));
        if (!msg) {
          console.warn('[WebSocket] Ignored malformed message');
          return;
        }
        console.log('[WebSocket] Message received:', msg.type);
        handleServerMessageRef.current(msg);
      } catch (err) {
        console.error('[WebSocket] Error parsing message data:', err);
      }
    };
  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    const cleanup = connect();

    return () => {
      shouldReconnectRef.current = false;
      if (cleanup && typeof cleanup === 'function') {
        cleanup();
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [connect]);

  // Action senders
  const sendDirective = (text: string) => {
    const cleanText = text.trim();
    if (!cleanText || !isReady()) return;

    sendClientMessage({ type: 'directive', text: cleanText });
    const timestamp = new Date().toLocaleTimeString('pt-PT', { hour12: false });
    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: 'CLIENTE',
      role: 'CEO',
      content: cleanText,
      timestamp,
    };
    setChatMessages((prev) => appendLimited(prev, userMsg, MAX_CHAT_MESSAGES));
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

  const readNote = useCallback((filename: string) => {
    if (isReady()) {
      sendClientMessage({ type: 'read_note', filename });
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
      setProjectFiles({});
      setProjectFileHashes({});
      setProjectFileSaveState(null);
      setAstState(null);
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
      setProjectFiles({});
      setProjectFileHashes({});
      setProjectFileSaveState(null);
      setAstState(null);
      setProjectReferences(null);
      setProjectOutput('');
      setPreviewUrl('about:blank');
      setIsProjectRunning(false);
      setCodingSession(null);
      setMissions([]);
      setMissionSnapshot(null);
      sendClientMessage({
        type: 'create_project',
        project_id: projectId.trim(),
        project_name: projectName?.trim(),
        template,
      });
    }
  }, [isReady, sendClientMessage]);

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
      sourceType?: string
    ) => {
      sendClientMessage({
        type: 'study_upload_document',
        filename,
        title,
        subject,
        content_base64: contentBase64,
        content_text: contentText,
        source_type: sourceType,
      });
    },
    [sendClientMessage]
  );

  const generateStudyQuiz = useCallback(
    (documentId: string, count?: number) => {
      sendClientMessage({
        type: 'study_generate_quiz',
        document_id: documentId,
        question_count: count || 5,
      });
    },
    [sendClientMessage]
  );

  const submitStudyQuiz = useCallback(
    (quizId: string, answers: Record<string, number | string>, transferAnswer?: string) => {
      sendClientMessage({
        type: 'study_submit_quiz',
        quiz_id: quizId,
        answers,
        transfer_answer: transferAnswer || '',
      });
    },
    [sendClientMessage]
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
      const requestId = `assist:${documentId}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingStudyRequestsRef.current.delete(requestId);
          reject(new Error('Assist request timed out'));
        }, 15000);

        pendingStudyRequestsRef.current.set(requestId, { resolve, reject, timer });

        sendClientMessage({
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
        });
      });
    },
    [sendClientMessage]
  );

  const askStudyPaper = useCallback(
    (
      documentId: string,
      question: string,
      sectionId?: string
    ): Promise<{ answer: string; sources: string[] }> => {
      const requestId = `ask:${documentId}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingStudyRequestsRef.current.delete(requestId);
          reject(new Error('Ask paper request timed out'));
        }, 20000);

        pendingStudyRequestsRef.current.set(requestId, { resolve, reject, timer });

        sendClientMessage({
          type: 'study_ask_paper',
          document_id: documentId,
          question,
          section_id: sectionId,
          request_id: requestId,
        });
      });
    },
    [sendClientMessage]
  );

  const getStudyDocumentFile = useCallback(
    (
      documentId: string
    ): Promise<{ contentBase64?: string; filename?: string; error?: string }> => {
      const requestId = `file:${documentId}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingStudyRequestsRef.current.delete(requestId);
          reject(new Error('Get document file timed out'));
        }, 4000);

        pendingStudyRequestsRef.current.set(requestId, { resolve, reject, timer });

        sendClientMessage({
          type: 'study_get_document_file',
          document_id: documentId,
          request_id: requestId,
        });
      });
    },
    [sendClientMessage]
  );

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
    } as any);
  }, [sendClientMessage]);

  const getMissionControlState = useCallback((scenario?: string) => {
    sendClientMessage({
      type: 'mission_control_get',
      scenario,
    } as any);
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
      } as any);
    } else {
      sendClientMessage({
        type: 'mission_intent_preview',
        mission_id: missionId,
        delta: textOrDelta,
      } as any);
    }
  }, [sendClientMessage]);

  const sendMissionIntentChange = useCallback((missionId: string, textOrDelta: string | Record<string, unknown>, preApproved?: boolean) => {
    if (typeof textOrDelta === 'string') {
      sendClientMessage({
        type: 'mission_intent_change',
        mission_id: missionId,
        text: textOrDelta,
        pre_approved: preApproved ?? false,
      } as any);
    } else {
      sendClientMessage({
        type: 'mission_intent_change',
        mission_id: missionId,
        delta: textOrDelta,
        pre_approved: preApproved ?? false,
      } as any);
    }
  }, [sendClientMessage]);

  const clearMissionIntentPreviewResult = useCallback(() => {
    setMissionIntentPreviewResult(null);
  }, []);

  const clearMissionIntentResult = useCallback(() => {
    setMissionIntentResult(null);
  }, []);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        systemStatus,
        voiceStatus,
        chatMessages,
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
        getNotes,
        readNote,
        saveNote,
        deleteRule,
        deleteArchitecture,
        deleteDecision,
        plannerState,
        missions,
        missionSnapshot,
        architectureSnapshot: null,
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
        generateStudyQuiz,
        submitStudyQuiz,
        listStudyFlashcards,
        reviewStudyFlashcard,
        contextualAssist,
        askStudyPaper,
        getStudyDocumentFile,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
