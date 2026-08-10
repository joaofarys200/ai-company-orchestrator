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
} from '../protocol/websocket';

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

    // Separate normal client/Jarvis communication from peer agent debates
    const isDebate = !['OPENCLAW', 'JARVIS', 'SISTEMA', 'CLIENTE'].includes(msg.sender.toUpperCase());
    if (isDebate) {
      setDebateMessages((prev) => appendLimited(prev, newMsg, MAX_DEBATE_MESSAGES));
    } else {
      setChatMessages((prev) => appendLimited(prev, newMsg, MAX_CHAT_MESSAGES));
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

  const connect = useCallback(function connectSocket() {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

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
      socketRef.current = null;
      setIsConnected(false);
      setSystemStatus('OFFLINE');
      setVoiceStatus('offline');
      setIsProjectRunning(false);

      if (shouldReconnectRef.current) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectSocket();
        }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      addSystemMessage('Ligacao ao backend interrompida. A tentar reconectar...');
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const msg = normalizeServerMessage(JSON.parse(event.data));
        if (!msg) {
          console.warn('[WebSocket] Ignored malformed message');
          addSystemMessage('Mensagem do backend ignorada por formato invalido.');
          return;
        }
        console.log('[WebSocket] Message received:', msg.type);

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
          case 'sandbox_status':
            setSandboxStatus(msg.status);
            break;
          case 'unknown':
            console.warn('[WebSocket] Unknown message type:', msg.originalType);
            break;
          default:
            break;
        }
      } catch (err) {
        console.error('[WebSocket] Error parsing message data:', err);
        addSystemMessage('Erro ao processar uma mensagem do backend.');
      }
    };
  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      shouldReconnectRef.current = false;
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
    if (!cleanText || socketRef.current?.readyState !== WebSocket.OPEN) return;

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
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'select_template', template: templateName });
    }
  };

  const toggleVoice = (active: boolean) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'toggle_voice', active });
    }
  };

  const runProject = () => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id) {
      setProjectOutput('[Client] A enviar comando de execução para o servidor...\n');
      setIsProjectRunning(true);
      sendClientMessage({ type: 'run_project', project_id: projectContext.project_id });
    }
  };

  const stopProject = () => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      setIsProjectRunning(false);
      sendClientMessage({ type: 'stop_project' });
    }
  };

  const clearChat = () => {
    setChatMessages([]);
    setDebateMessages([]);
  };

  const getNotes = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'get_notes' });
    }
  }, [sendClientMessage]);

  const readNote = useCallback((filename: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'read_note', filename });
    }
  }, [sendClientMessage]);

  const saveNote = useCallback((filename: string, content: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'save_note', filename, content });
    }
  }, [sendClientMessage]);

  const deleteRule = useCallback((key: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'delete_rule', key });
    }
  }, [sendClientMessage]);

  const deleteArchitecture = useCallback((module: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'delete_architecture', module });
    }
  }, [sendClientMessage]);

  const deleteDecision = useCallback((decision: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'delete_decision', decision });
    }
  }, [sendClientMessage]);

  const getPlannerState = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage({ type: 'get_planner_state' });
    }
  }, [sendClientMessage]);

  const getMissions = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id) {
      sendClientMessage({ type: 'mission_list', project_id: projectContext.project_id });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const openMission = useCallback((missionId: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && missionId) {
      sendClientMessage({ type: 'mission_resume_snapshot', project_id: projectContext.project_id, mission_id: missionId });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const sendMissionOperation = useCallback((operation: MissionClientOperation) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      sendClientMessage(operation);
    }
  }, [sendClientMessage]);

  const getAstState = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id) {
      sendClientMessage({ type: 'get_ast_state', project_id: projectContext.project_id });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const openProject = useCallback((projectId: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectId) {
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
  }, [sendClientMessage]);

  const createProject = useCallback((projectId: string, projectName?: string, template?: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectId.trim()) {
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
  }, [sendClientMessage]);

  const saveProjectFile = useCallback((filename: string, content: string) => {
    const expectedHash = projectFileHashes[filename];
    if (
      socketRef.current?.readyState !== WebSocket.OPEN
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
  }, [projectContext?.project_id, projectFileHashes, sendClientMessage]);

  const reindexProject = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id) {
      setIsIndexingProject(true);
      sendClientMessage({ type: 'index_project', project_id: projectContext.project_id });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const findReferences = useCallback((symbol: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && symbol.trim()) {
      sendClientMessage({ type: 'find_references', project_id: projectContext.project_id, symbol: symbol.trim() });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const semanticSearch = useCallback((query: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && query.trim()) {
      setSemanticResults('A pesquisar...');
      sendClientMessage({ type: 'semantic_search', project_id: projectContext.project_id, query: query.trim() });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const createCodingSession = useCallback((objective: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && objective.trim()) {
      setIsCodingSessionBusy(true);
      sendClientMessage({ type: 'create_coding_session', project_id: projectContext.project_id, objective: objective.trim() });
    }
  }, [projectContext?.project_id, sendClientMessage]);

  const applyCodingSession = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && codingSession?.session_id) {
      setIsCodingSessionBusy(true);
      sendClientMessage({
        type: 'apply_coding_session',
        project_id: projectContext.project_id,
        session_id: codingSession.session_id,
      });
    }
  }, [codingSession?.session_id, projectContext?.project_id, sendClientMessage]);

  const rollbackCodingSession = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN && projectContext?.project_id && codingSession?.session_id) {
      setIsCodingSessionBusy(true);
      sendClientMessage({
        type: 'rollback_coding_session',
        project_id: projectContext.project_id,
        session_id: codingSession.session_id,
        confirmed: true,
      });
    }
  }, [codingSession?.session_id, projectContext?.project_id, sendClientMessage]);

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
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
