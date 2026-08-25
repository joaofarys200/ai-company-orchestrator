import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
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
} from '../protocol/websocket';

declare global {
  interface Window {
    jarvisIPC?: {
      send: (message: any) => void;
      onMessage: (callback: (data: any) => void) => () => void;
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

export interface ProjectFileSaveState {
  ok: boolean;
  filename: string;
  sha256: string;
  error: string;
}

interface WebSocketContextType {
  isConnected: boolean;
  systemStatus: SystemStatus;
  voiceStatus: string;
  chatMessages: ChatMessage[];
  debateMessages: ChatMessage[];
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
  runProject: () => void;
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
  getMissions: () => void;
  openMission: (missionId: string) => void;
  sendMissionOperation: (operation: MissionClientOperation) => void;
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
  saveProjectFile: (filename: string, content: string) => void;
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
  const [astState, setAstState] = useState<AstState | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectContext, setProjectContext] = useState<ProjectContextData | null>(null);
  const [projectReferences, setProjectReferences] = useState<ProjectReferenceResult | null>(null);
  const [semanticResults, setSemanticResults] = useState('');
  const [isIndexingProject, setIsIndexingProject] = useState(false);
  const [sandboxStatus, setSandboxStatus] = useState<{ mode: 'docker' | 'local_fallback'; port: number; is_docker: boolean } | null>(null);
  const [codingSession, setCodingSession] = useState<CodingSessionData | null>(null);
  const [isCodingSessionBusy, setIsCodingSessionBusy] = useState(false);
  const [activeLecture, setActiveLecture] = useState<LectureLessonData | null>(null);
  const [lectureQuizResult, setLectureQuizResult] = useState<LectureQuizResult | null>(null);
  const [lectureHistory, setLectureHistory] = useState<LectureHistoryItem[]>([]);
  const [isGeneratingLecture, setIsGeneratingLecture] = useState(false);
  const [isSubmittingQuiz, setIsSubmittingQuiz] = useState(false);
  const [isRecordingLecture, setIsRecordingLecture] = useState(false);

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

    // Separate peer agent debates to debateMessages as well
    const isDebate = !['OPENCLAW', 'JARVIS', 'SISTEMA', 'CLIENTE'].includes(msg.sender.toUpperCase());
    if (isDebate) {
      setDebateMessages((prev) => appendLimited(prev, newMsg, MAX_DEBATE_MESSAGES));
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

  const handleServerMessage = useCallback((msg: any) => {
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
        break;
      case 'mission_snapshot':
        setMissionSnapshot(msg.data);
        break;
      case 'ast_state':
        setAstState(msg.data);
        break;
      case 'projects_list':
        setProjects(msg.projects);
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
      case 'unknown':
        console.warn('[Transport] Unknown message type:', msg.originalType);
        break;
      default:
        break;
    }
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

  const getMissions = useCallback(() => {
    if (isReady() && projectContext?.project_id) {
      sendClientMessage({ type: 'mission_list', project_id: projectContext.project_id });
    }
  }, [isReady, projectContext?.project_id, sendClientMessage]);

  const openMission = useCallback((missionId: string) => {
    if (isReady() && projectContext?.project_id && missionId) {
      sendClientMessage({ type: 'mission_resume_snapshot', project_id: projectContext.project_id, mission_id: missionId });
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
        astState,
        getPlannerState,
        getMissions,
        openMission,
        sendMissionOperation,
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
        saveProjectFile,
        reindexProject,
        findReferences,
        semanticSearch,
        codingSession,
        isCodingSessionBusy,
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
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
