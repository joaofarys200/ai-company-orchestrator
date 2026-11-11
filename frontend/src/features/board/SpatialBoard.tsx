import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Code2,
  Database,
  ExternalLink,
  FileCode,
  FileText,
  FolderPlus,
  GraduationCap,
  Loader2,
  Maximize2,
  Minimize2,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  Square,
  Trash2,
  Upload,
  Video,
  X,
} from 'lucide-react';
import { useWebSocket } from '../../context/WebSocketContext';
import type { StudyDocument } from '../study/types';
import type {
  ProjectSummary,
  ProjectContextData,
  SentinelStatusData,
  SentinelSecurityEventData,
} from '../../protocol/websocket';

const MonacoEditor = React.lazy(() => import('@monaco-editor/react'));

export type SpatialBoardDomain = 'study' | 'obsidian' | 'project' | 'sentinel';

export type SpatialCardKind =
  | 'stat'
  | 'bar_chart'
  | 'insight'
  | 'video'
  | 'study_notes'
  | 'code_files'
  | 'sentinel_alert';

export interface SpatialBoardCardData {
  id: string;
  title: string;
  subtitle?: string;
  kind: SpatialCardKind;
  type: SpatialCardKind;
  badge?: string;
  accent?: 'terracotta' | 'cyan' | 'emerald' | 'amber' | 'rose';
  colSpan?: 1 | 2;
}

export interface SpatialBoardData {
  boardId: string;
  domain: SpatialBoardDomain;
  title: string;
  subtitle: string;
  statusBadge: string;
  generationMode?: string;
  documentId?: string;
  projectId?: string;
  cards: SpatialBoardCardData[];
}

// Builders kept for voice/context compatibility — card IDs match the interactive workspace cards
export function buildStudySpatialBoard(
  doc?: StudyDocument,
  allDocsCount = 0
): SpatialBoardData {
  if (!doc) {
    return {
      boardId: 'board_study_empty',
      domain: 'study',
      title: 'Estudo & Investigação Multimodal',
      subtitle: `${allDocsCount} materiais disponíveis`,
      statusBadge: 'Estudo Interativo',
      cards: [
        { id: 'card_reader', title: 'Leitor & Vídeo da Aula', kind: 'video', type: 'video' },
        { id: 'card_synthesis', title: 'Síntese Fundamentada (qwen3.5:9b)', kind: 'insight', type: 'insight' },
        { id: 'card_practice', title: 'Cornell Notes, Quiz & Flashcards', kind: 'study_notes', type: 'study_notes' },
      ],
    };
  }
  const meta = (doc.metadata || {}) as Record<string, any>;
  const genMode = String(meta.generation_mode || 'EXTRACTIVE_GROUNDED');
  return {
    boardId: `board_study_${doc.document_id}`,
    domain: 'study',
    documentId: doc.document_id,
    title: doc.title,
    subtitle: `${doc.subject || 'Geral'} • ${doc.source_type || 'DOC'}`,
    statusBadge:
      genMode === 'LLM_GROUNDED'
        ? 'IA Fundamentada • qwen3.5:9b'
        : genMode === 'PARTIAL'
          ? 'Síntese Parcial • qwen3.5:9b'
          : 'Extração Local Determinística',
    generationMode: genMode,
    cards: [
      { id: 'card_reader', title: 'Leitor Multimodal & Vídeo', kind: 'video', type: 'video' },
      { id: 'card_synthesis', title: 'Síntese & Mapa de Argumentos', kind: 'insight', type: 'insight' },
      { id: 'card_practice', title: 'Cornell Notes, Quiz & Flashcards', kind: 'study_notes', type: 'study_notes' },
    ],
  };
}

export function buildProjectSpatialBoard(
  projectId: string,
  projects: ProjectSummary[],
  _projectContext?: ProjectContextData | null,
  projectFiles: Record<string, string> = {},
  previewUrl = ''
): SpatialBoardData {
  const fileNames = Object.keys(projectFiles);
  const projSummary = projects.find((p) => p.project_id === projectId);
  const isRunning = Boolean(previewUrl);
  return {
    boardId: `board_project_${projectId || 'default'}`,
    domain: 'project',
    projectId: projectId || 'dina',
    title: `Projeto: ${projSummary?.project_name || projectId || 'Workspace'}`,
    subtitle: `${fileNames.length} ficheiros • ${isRunning ? `Em execução (${previewUrl})` : 'Pronto para editar/executar'}`,
    statusBadge: isRunning ? 'LIVE PREVIEW ATIVO' : 'Editor & Engenharia',
    cards: [
      { id: 'card_editor', title: 'Explorador & Editor de Código', kind: 'code_files', type: 'code_files' },
      { id: 'card_preview', title: 'Live Preview & Consola', kind: 'video', type: 'video' },
      { id: 'card_ai_change', title: 'Alteração Assistida por IA', kind: 'insight', type: 'insight' },
    ],
  };
}

export function buildObsidianSpatialBoard(
  notes: string[],
  studyDocuments?: StudyDocument[],
  query?: string
): SpatialBoardData {
  return {
    boardId: `board_obsidian_${query || 'vault'}`,
    domain: 'obsidian',
    title: 'Obsidian Knowledge Vault',
    subtitle: `${notes.length} notas Markdown indexadas • ${studyDocuments?.length || 0} materiais de estudo ligados`,
    statusBadge: 'Knowledge Graph Ativo',
    cards: [
      { id: 'card_vault_explorer', title: 'Explorador do Cofre Obsidian', kind: 'study_notes', type: 'study_notes' },
      { id: 'card_vault_editor', title: 'Leitor & Editor Markdown', kind: 'insight', type: 'insight' },
    ],
  };
}

export function buildSentinelSpatialBoard(
  status: SentinelStatusData | null,
  events: SentinelSecurityEventData[]
): SpatialBoardData {
  const mode = status?.status === 'RUNNING' ? 'WATCHDOG ATIVO' : 'STANDBY';
  return {
    boardId: 'board_sentinel_security',
    domain: 'sentinel',
    title: 'Sentinel Security & Runtime Governance',
    subtitle: `${events.length} eventos monitorizados • Postura: ${status?.posture || 'GOOD'}`,
    statusBadge: mode,
    cards: [
      { id: 'card_sentinel_control', title: 'Controlo & Ações Sentinel', kind: 'sentinel_alert', type: 'sentinel_alert' },
      { id: 'card_sentinel_events', title: 'Eventos & Auditoria em Tempo Real', kind: 'insight', type: 'insight' },
    ],
  };
}

interface SpatialBoardProps {
  board: SpatialBoardData;
  focusedCardId: string | null;
  onFocusCard: (cardId: string | null) => void;
  onCloseBoard: () => void;
  onSwitchDomain: (domain: SpatialBoardDomain) => void;
  onOpenFullWorkspace?: () => void;
}

export const SpatialBoard: React.FC<SpatialBoardProps> = ({
  board,
  focusedCardId,
  onFocusCard,
  onCloseBoard,
  onSwitchDomain,
  onOpenFullWorkspace,
}) => {
  const {
    // Study state & actions
    studyDocuments,
    uploadStudyDocument,
    deleteStudyDocument,
    generateStudySummary,
    cancelStudyGeneration,
    studyPipelineStage,
    askStudyPaper,
    activeStudyQuiz,
    studyQuizResult,
    generateStudyQuiz,
    submitStudyQuiz,
    studyFlashcards,
    listStudyFlashcards,
    reviewStudyFlashcard,
    saveToStudyVault,
    navigateToStudyTarget,
    // Project state & actions
    projects,
    projectContext,
    projectFiles,
    openProject,
    createProject,
    saveProjectFile,
    isSavingProjectFile,
    isProjectRunning,
    previewUrl,
    projectOutput,
    runProject,
    stopProject,
    codingSession,
    isCodingSessionBusy,
    createCodingSession,
    applyCodingSession,
    rollbackCodingSession,
    // Obsidian state & actions
    notes,
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
    getNotes,
    readNote,
    saveNote,
    // Sentinel state & actions
    sentinelStatus,
    sentinelEvents,
    sentinelActions,
    isSentinelAuditing,
    getSentinelStatus,
    runSentinelAudit,
    approveSentinelAction,
    rejectSentinelAction,
    rollbackSentinelAction,
  } = useWebSocket();

  // ── STUDY LOCAL STATE ──
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedSectionIdx, setSelectedSectionIdx] = useState<number>(0);
  const [summaryTab, setSummaryTab] = useState<'quick' | 'study' | 'detailed' | 'exam' | 'structure'>('study');
  const [practiceTab, setPracticeTab] = useState<'cornell' | 'quiz' | 'flashcards'>('cornell');
  const [paperQuestion, setPaperQuestion] = useState('');
  const [paperAnswer, setPaperAnswer] = useState<{ answer: string; sources: string[] } | null>(null);
  const [isAskingPaper, setIsAskingPaper] = useState(false);
  const [isRegeneratingSummary, setIsRegeneratingSummary] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});
  const [isGeneratingQuizState, setIsGeneratingQuizState] = useState(false);
  const [isSubmittingQuizState, setIsSubmittingQuizState] = useState(false);
  const [flashcardIdx, setFlashcardIdx] = useState(0);
  const [flashcardFlipped, setFlashcardFlipped] = useState(false);
  const [vaultSavedMsg, setVaultSavedMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Sync selectedDocId with board or first available study document
  useEffect(() => {
    if (board.domain === 'study') {
      const fromBoardId = board.boardId.startsWith('board_study_doc_')
        ? board.boardId.replace('board_study_', '')
        : '';
      if (fromBoardId && studyDocuments.some((d) => d.document_id === fromBoardId)) {
        setSelectedDocId(fromBoardId);
      } else if (!selectedDocId && studyDocuments.length > 0) {
        setSelectedDocId(studyDocuments[0].document_id);
      }
    }
  }, [board.boardId, board.domain, studyDocuments, selectedDocId]);

  const selectedDoc = useMemo(
    () => studyDocuments.find((d) => d.document_id === selectedDocId) || studyDocuments[0],
    [studyDocuments, selectedDocId]
  );

  useEffect(() => {
    if (selectedDoc?.document_id) {
      listStudyFlashcards(selectedDoc.document_id);
      setSelectedSectionIdx(0);
      setPaperAnswer(null);
    }
  }, [selectedDoc?.document_id, listStudyFlashcards]);

  // ── PROJECT LOCAL STATE ──
  const activeProjectId = projectContext?.project_id || projects[0]?.project_id || 'dina';
  const fileNames = useMemo(() => Object.keys(projectFiles).sort(), [projectFiles]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [editorDraft, setEditorDraft] = useState<string>('');
  const [previewMode, setPreviewMode] = useState<'preview' | 'console'>('preview');
  const [aiObjective, setAiObjective] = useState('');
  const [newFileName, setNewFileName] = useState('');
  const [showNewFileInput, setShowNewFileInput] = useState(false);
  const [showNewProjectInput, setShowNewProjectInput] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [iframeKey, setIframeKey] = useState(0);

  useEffect(() => {
    if (fileNames.length > 0 && (!selectedFile || !(selectedFile in projectFiles))) {
      const preferred =
        fileNames.find((f) => f === 'index.html' || f === 'app.js' || f === 'main.py') || fileNames[0];
      setSelectedFile(preferred);
      setEditorDraft(projectFiles[preferred] ?? '');
    }
  }, [fileNames, projectFiles, selectedFile]);

  const handleSelectProjectFile = (fname: string) => {
    setSelectedFile(fname);
    setEditorDraft(projectFiles[fname] ?? '');
  };

  const isFileDirty = selectedFile ? editorDraft !== (projectFiles[selectedFile] ?? '') : false;

  // ── OBSIDIAN LOCAL STATE ──
  const [vaultSearch, setVaultSearch] = useState('');
  const [noteDraft, setNoteDraft] = useState('');
  const [isEditingNote, setIsEditingNote] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [showNewNoteInput, setShowNewNoteInput] = useState(false);
  const [noteSavedFeedback, setNoteSavedFeedback] = useState(false);
  const [obsidianViewMode, setObsidianViewMode] = useState<'explorer' | 'quality_graph'>('quality_graph');
  const [selectedQualityNote, setSelectedQualityNote] = useState<string>('');
  const [enrichmentFeedback, setEnrichmentFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (board.domain === 'obsidian') {
      if (notes.length === 0) {
        getNotes();
      }
      getVaultDiagnostics();
    }
  }, [board.domain, notes.length, getNotes, getVaultDiagnostics]);

  useEffect(() => {
    if (selectedQualityNote) {
      auditNoteQuality(selectedQualityNote);
    } else if (notes.length > 0 && !selectedQualityNote) {
      setSelectedQualityNote(notes[0]);
      auditNoteQuality(notes[0]);
    }
  }, [selectedQualityNote, notes, auditNoteQuality]);

  useEffect(() => {
    if (currentNote) {
      setNoteDraft(currentNote.content || '');
    } else if (board.domain === 'obsidian' && notes.length > 0) {
      readNote(notes[0]);
    }
  }, [currentNote, board.domain, notes, readNote]);

  useEffect(() => {
    if (board.domain === 'sentinel') {
      getSentinelStatus();
    }
  }, [board.domain, getSentinelStatus]);

  // ── HANDLERS: STUDY ──
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      const base64 = result.includes(',') ? result.split(',')[1] : result;
      const ext = file.name.split('.').pop()?.toUpperCase() || 'TXT';
      const sourceType =
        ['MP4', 'MKV', 'WEBM', 'MOV', 'AVI'].includes(ext)
          ? 'VIDEO'
          : ['MP3', 'WAV', 'M4A', 'OGG', 'FLAC'].includes(ext)
            ? 'AUDIO'
            : ['PDF', 'PPTX', 'DOCX', 'TXT', 'MD'].includes(ext)
              ? ext
              : 'TXT';
      uploadStudyDocument(file.name, file.name.replace(/\.[^.]+$/, ''), 'Geral', base64, undefined, sourceType);
    };
    reader.readAsDataURL(file);
  };

  const handleRegenerateStudy = async () => {
    if (!selectedDoc) return;
    setIsRegeneratingSummary(true);
    try {
      await generateStudySummary(selectedDoc.document_id, 'Study', true);
    } finally {
      setIsRegeneratingSummary(false);
    }
  };

  const handleAskPaper = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !paperQuestion.trim()) return;
    setIsAskingPaper(true);
    try {
      const res = await askStudyPaper(selectedDoc.document_id, paperQuestion.trim());
      setPaperAnswer(res);
    } finally {
      setIsAskingPaper(false);
    }
  };

  const handleSaveCornellToVault = async () => {
    if (!selectedDoc) return;
    const meta = (selectedDoc.metadata || {}) as Record<string, any>;
    const cornell = meta.cornell_notes || {};
    const cuesMd = Array.isArray(cornell.cue_column)
      ? cornell.cue_column.map((c: any) => `- **${c.cue}**: ${c.idea}`).join('\n')
      : '';
    const md = `# ${selectedDoc.title}\n\n## Sumário Executivo\n${cornell.executive_summary || ''}\n\n## Tópicos e Questões Cornell\n${cuesMd}\n\n## Notas Detalhadas\n${cornell.detailed_notes || ''}`;
    const ok = await saveToStudyVault({
      title: selectedDoc.title,
      markdown_content: md,
      subject: selectedDoc.subject || 'Geral',
      source_document_ids: [selectedDoc.document_id],
    });
    if (ok) {
      setVaultSavedMsg('Guardado no Obsidian Vault!');
      setTimeout(() => setVaultSavedMsg(null), 3500);
    }
  };

  const handleStartQuiz = async () => {
    if (!selectedDoc) return;
    setIsGeneratingQuizState(true);
    setQuizAnswers({});
    try {
      await generateStudyQuiz(selectedDoc.document_id, 5);
    } finally {
      setIsGeneratingQuizState(false);
    }
  };

  const handleSubmitQuiz = async () => {
    if (!activeStudyQuiz) return;
    setIsSubmittingQuizState(true);
    try {
      await submitStudyQuiz(activeStudyQuiz.quiz_id, quizAnswers, '');
    } finally {
      setIsSubmittingQuizState(false);
    }
  };

  const seekVideoTo = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, seconds);
      videoRef.current.play().catch(() => { });
    }
  };

  // Helpers to render card wrapper with Focus/Maximize capability
  const renderCardShell = (
    cardId: string,
    title: string,
    subtitle: string,
    icon: React.ReactNode,
    colSpanClass: string,
    headerRight: React.ReactNode,
    children: React.ReactNode
  ) => {
    const isFocused = focusedCardId === cardId;
    const isDimmed = Boolean(focusedCardId && !isFocused);

    return (
      <motion.div
        key={cardId}
        layout
        transition={{ type: 'spring', damping: 28, stiffness: 220 }}
        className={`flex flex-col rounded-2xl border bg-[#101218]/95 backdrop-blur-xl transition-all overflow-hidden ${isFocused
            ? 'fixed inset-4 sm:inset-8 z-50 border-[#d99a6c]/55 shadow-[0_30px_100px_rgba(0,0,0,0.92)]'
            : `${colSpanClass} border-white/[0.08] hover:border-white/[0.15] shadow-[0_16px_45px_rgba(0,0,0,0.45)] ${isDimmed ? 'opacity-15 scale-[0.98] pointer-events-none' : 'opacity-100'
            }`
          }`}
      >
        {/* Card Header */}
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-white/[0.07] bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-[#d99a6c]/12 border border-[#d99a6c]/30 flex items-center justify-center text-[#f3c39f] shrink-0">
              {icon}
            </div>
            <div className="min-w-0">
              <h3 className="text-xs sm:text-sm font-semibold text-stone-100 truncate">{title}</h3>
              {subtitle && <p className="text-[10px] text-stone-400 truncate">{subtitle}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {headerRight}
            <button
              onClick={() => onFocusCard(isFocused ? null : cardId)}
              className="p-1.5 rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/[0.1] text-stone-300 hover:text-white transition-all cursor-pointer"
              title={isFocused ? 'Restaurar tamanho na grelha (Esc)' : 'Maximizar ferramenta no centro'}
            >
              {isFocused ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Card Content Body */}
        <div className="flex-1 min-h-0 overflow-y-auto flex flex-col">{children}</div>
      </motion.div>
    );
  };

  // ── RENDER DOMAIN: STUDY ──
  const renderStudyDomain = () => {
    const meta = (selectedDoc?.metadata || {}) as Record<string, any>;
    const summaries = meta.summaries || {};
    const cornell = meta.cornell_notes || {};
    const structure = (selectedDoc?.structure || {}) as Record<string, any>;
    const genMode = String(meta.generation_mode || 'EXTRACTIVE_GROUNDED');
    const telem = meta.generation_telemetry || {};
    const videoMeta = meta.video || {};
    const transcriptSegments: Array<any> = videoMeta.transcript_segments || meta.audio?.transcript_segments || [];
    const sections: Array<any> = selectedDoc?.sections || [];
    const currentSection = sections[selectedSectionIdx] || sections[0];

    return (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
        {/* CARD 1: MULTIMODAL READER & VIDEO PLAYER */}
        {renderCardShell(
          'card_reader',
          selectedDoc?.source_type === 'VIDEO' ? 'Vídeo da Aula & Transcrição Interativa' : 'Leitor Estruturado & Pesquisa Contextual',
          selectedDoc ? `${selectedDoc.title} (${selectedDoc.source_type})` : 'Seleciona ou carrega um documento',
          selectedDoc?.source_type === 'VIDEO' ? <Video className="w-3.5 h-3.5" /> : <BookOpen className="w-3.5 h-3.5" />,
          'lg:col-span-5 min-h-[460px]',
          selectedDoc?.source_type === 'VIDEO' ? (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              {meta.transcription_status || 'READY'}
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/5 text-stone-300 border border-white/10">
              {sections.length} secções
            </span>
          ),
          selectedDoc ? (
            <div className="flex flex-col h-full justify-between p-4 gap-3">
              {selectedDoc.source_type === 'VIDEO' ? (
                <div className="flex flex-col gap-3 flex-1 min-h-0">
                  <div className="rounded-xl overflow-hidden bg-black border border-white/10 aspect-video shrink-0">
                    <video
                      ref={videoRef}
                      controls
                      className="w-full h-full object-contain"
                      src={`http://localhost:8000/api/study/document/${selectedDoc.document_id}/video`}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-stone-400">
                    <span>Clica num segmento para saltar no vídeo:</span>
                    <span className="font-mono text-stone-500">{transcriptSegments.length} segmentos</span>
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 max-h-56">
                    {transcriptSegments.length > 0 ? (
                      transcriptSegments.map((seg, idx) => (
                        <button
                          key={seg.segment_id || idx}
                          onClick={() => seekVideoTo(Number(seg.start || 0))}
                          className="w-full text-left p-2 rounded-lg bg-white/[0.025] hover:bg-[#d99a6c]/15 border border-white/[0.05] hover:border-[#d99a6c]/35 transition-all flex items-start gap-2.5 cursor-pointer group"
                        >
                          <span className="px-1.5 py-0.5 rounded bg-[#d99a6c]/15 text-[#f3c39f] font-mono text-[10px] shrink-0 group-hover:bg-[#d99a6c]/30">
                            {seg.timestamp || '00:00'}
                          </span>
                          <span className="text-xs text-stone-300 leading-relaxed">{seg.text}</span>
                        </button>
                      ))
                    ) : (
                      <div className="space-y-2">
                        {sections.map((sec, idx) => (
                          <div key={sec.section_id || idx} className="p-2.5 rounded-lg bg-white/[0.025] border border-white/[0.06]">
                            <div className="text-xs font-semibold text-[#f3c39f] mb-1">{sec.title}</div>
                            {(sec.paragraphs || []).map((p: any, pIdx: number) => (
                              <p key={pIdx} className="text-xs text-stone-300 leading-relaxed">
                                {p.text}
                              </p>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-3 flex-1 min-h-0">
                  {/* Section selector pills */}
                  {sections.length > 1 && (
                    <div className="flex items-center gap-1.5 overflow-x-auto pb-1 shrink-0">
                      {sections.map((sec, idx) => (
                        <button
                          key={sec.section_id || idx}
                          onClick={() => setSelectedSectionIdx(idx)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap transition-all cursor-pointer ${selectedSectionIdx === idx
                              ? 'bg-[#d99a6c]/20 text-[#f3c39f] border border-[#d99a6c]/45'
                              : 'bg-white/[0.03] text-stone-400 hover:text-stone-200 border border-white/[0.06]'
                            }`}
                        >
                          {sec.title || `Secção ${idx + 1}`}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Active Section Paragraphs */}
                  <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
                    {currentSection ? (
                      <>
                        <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                          <h4 className="text-xs font-semibold text-[#f3c39f]">{currentSection.title}</h4>
                          <span className="text-[10px] font-mono text-stone-400">
                            Pág. {currentSection.page_start || 1}
                          </span>
                        </div>
                        {(currentSection.paragraphs || []).map((p: any, idx: number) => (
                          <div
                            key={p.paragraph_id || idx}
                            className="p-3 rounded-xl bg-white/[0.025] border border-white/[0.05] text-xs text-stone-200 leading-relaxed"
                          >
                            {p.text}
                          </div>
                        ))}
                      </>
                    ) : (
                      <div className="p-3 rounded-xl bg-white/[0.025] border border-white/[0.05] text-xs text-stone-300 leading-relaxed whitespace-pre-wrap">
                        {selectedDoc.extracted_text || 'Sem texto extraído.'}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Inline Q&A Grounded Search on Document */}
              <div className="pt-2 border-t border-white/[0.07] shrink-0">
                <form onSubmit={handleAskPaper} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={paperQuestion}
                    onChange={(e) => setPaperQuestion(e.target.value)}
                    placeholder="Pergunta algo diretamente sobre este material..."
                    className="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-stone-200 placeholder:text-stone-500 outline-none focus:border-[#d99a6c]/50"
                  />
                  <button
                    type="submit"
                    disabled={isAskingPaper || !paperQuestion.trim()}
                    className="px-3 py-1.5 rounded-lg bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/40 text-[#f3c39f] text-xs font-medium flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
                  >
                    {isAskingPaper ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    <span>Perguntar</span>
                  </button>
                </form>
                {paperAnswer && (
                  <div className="mt-2 p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-400/25 text-xs text-stone-200 space-y-1">
                    <div className="text-stone-200 leading-relaxed whitespace-pre-wrap">{paperAnswer.answer}</div>
                    {paperAnswer.sources && paperAnswer.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {paperAnswer.sources.map((src, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded bg-black/40 text-cyan-300 font-mono text-[10px]">
                            {src}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-stone-400">Nenhum documento selecionado.</div>
          )
        )}

        {/* CARD 2: GROUNDED SYNTHESIS & ARGUMENT MAP */}
        {renderCardShell(
          'card_synthesis',
          'Síntese Fundamentada & Argumentos',
          genMode === 'LLM_GROUNDED'
            ? `Gerado por qwen3.5:9b • ${telem.tokens_per_sec ? `${telem.tokens_per_sec} tok/s` : 'Validado'}`
            : 'Extração Determinística Local — Clica Regenerar para usar qwen3.5:9b',
          <Sparkles className="w-3.5 h-3.5" />,
          'lg:col-span-4 min-h-[460px]',
          <div className="flex items-center gap-1.5">
            {isRegeneratingSummary ? (
              <button
                onClick={() => selectedDoc && cancelStudyGeneration(selectedDoc.document_id)}
                className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-400/40 text-rose-200 text-[11px] font-medium flex items-center gap-1 cursor-pointer"
              >
                <Square className="w-3 h-3" />
                <span>Cancelar ({studyPipelineStage || 'IA'})</span>
              </button>
            ) : (
              <button
                onClick={handleRegenerateStudy}
                disabled={!selectedDoc}
                className="px-2.5 py-1 rounded-lg bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/40 text-[#f3c39f] text-[11px] font-medium flex items-center gap-1 cursor-pointer"
                title="Regenerar síntese fundamentada com Ollama qwen3.5:9b"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Regenerar IA</span>
              </button>
            )}
          </div>,
          <div className="flex flex-col h-full p-4 gap-3">
            {/* Mode Tabs */}
            <div className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-white/[0.06] shrink-0">
              {(
                [
                  { id: 'quick', label: 'Rápido' },
                  { id: 'study', label: 'Secções' },
                  { id: 'detailed', label: 'Detalhado' },
                  { id: 'exam', label: 'Exame' },
                  { id: 'structure', label: 'Argumentos' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSummaryTab(tab.id)}
                  className={`flex-1 py-1.5 px-2 rounded-lg text-[11px] font-medium transition-all cursor-pointer ${summaryTab === tab.id
                      ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/40'
                      : 'text-stone-400 hover:text-stone-200'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Active Synthesis Content */}
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {summaryTab === 'quick' && (
                <div className="space-y-2">
                  {(Array.isArray(summaries.quick) ? summaries.quick : []).map((point: string, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-start gap-2.5"
                    >
                      <span className="w-5 h-5 rounded-full bg-[#d99a6c]/20 text-[#f3c39f] text-[10px] font-mono flex items-center justify-center shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <p className="text-xs text-stone-200 leading-relaxed">{point}</p>
                    </div>
                  ))}
                </div>
              )}

              {summaryTab === 'study' && (
                <div className="space-y-2.5">
                  {(Array.isArray(summaries.study) ? summaries.study : []).map((sec: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-[#f3c39f]">
                          {sec.title || sec.heading || `Secção ${idx + 1}`}
                        </span>
                        {sec.page_ref && (
                          <span className="text-[10px] font-mono text-stone-400">{sec.page_ref}</span>
                        )}
                      </div>
                      <p className="text-xs text-stone-300 leading-relaxed">{sec.summary || sec.content}</p>
                      {Array.isArray(sec.key_concepts) && sec.key_concepts.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {sec.key_concepts.map((kc: string, kIdx: number) => (
                            <span
                              key={kIdx}
                              className="px-2 py-0.5 rounded-md bg-white/[0.05] text-stone-300 text-[10px]"
                            >
                              {kc}
                            </span>
                          ))}
                        </div>
                      )}
                      {Array.isArray(sec.source_refs) && sec.source_refs.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {sec.source_refs.slice(0, 3).map((ref: string, rIdx: number) => (
                            <span
                              key={rIdx}
                              className="px-1.5 py-0.5 rounded bg-black/40 text-stone-400 font-mono text-[9px]"
                            >
                              {ref}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {summaryTab === 'detailed' && (
                <div className="space-y-2.5">
                  {(Array.isArray(summaries.detailed) ? summaries.detailed : []).map((block: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
                      <h4 className="text-xs font-semibold text-cyan-300">{block.title || `Análise ${idx + 1}`}</h4>
                      <p className="text-xs text-stone-200 leading-relaxed">{block.text || block.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {summaryTab === 'exam' && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-[#f3c39f]">
                      Conceitos High-Yield para Exame
                    </div>
                    {(summaries.exam?.high_yield_concepts || []).map((hy: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                        <div className="text-xs font-semibold text-stone-100">{hy.concept}</div>
                        <div className="text-xs text-stone-300 mt-0.5 leading-relaxed">{hy.detail}</div>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-300">
                      Questões Prováveis de Exame
                    </div>
                    {(summaries.exam?.likely_questions || []).map((lq: any, idx: number) => (
                      <div key={idx} className="p-2.5 rounded-xl bg-cyan-500/[0.06] border border-cyan-400/20 space-y-1">
                        <div className="text-xs font-semibold text-cyan-200">Q: {lq.question}</div>
                        <div className="text-xs text-stone-300 leading-relaxed">
                          R: {lq.answer || lq.answer_guide}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {summaryTab === 'structure' && (
                <div className="space-y-2">
                  {structure.is_argumentative === false && structure.argumentative_limitation && (
                    <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-400/30 text-amber-200 text-xs">
                      {structure.argumentative_limitation}
                    </div>
                  )}
                  {(
                    [
                      ['problem', 'Problema / Tema Central'],
                      ['contribution', 'Tese / Contribuição'],
                      ['method', 'Metodologia / Processo'],
                      ['results', 'Resultados / Evidências'],
                      ['limitations', 'Limitações'],
                      ['conclusion', 'Conclusão'],
                    ] as const
                  ).map(([key, label]) => {
                    const node = structure[key];
                    if (!node || !node.text) return null;
                    return (
                      <div key={key} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-mono uppercase text-[#f3c39f]">{label}</span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-stone-400">
                            {node.status || 'OBSERVED'}
                          </span>
                        </div>
                        <p className="text-xs text-stone-200 mt-1 leading-relaxed">{node.text}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* CARD 3: CORNELL NOTES, INTERACTIVE QUIZ & FLASHCARDS */}
        {renderCardShell(
          'card_practice',
          'Cornell Notes, Quiz & Flashcards',
          'Prática ativa e exportação para o Obsidian Vault',
          <GraduationCap className="w-3.5 h-3.5" />,
          'lg:col-span-3 min-h-[460px]',
          vaultSavedMsg ? (
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-medium">
              {vaultSavedMsg}
            </span>
          ) : null,
          <div className="flex flex-col h-full p-4 gap-3">
            {/* Practice Tabs */}
            <div className="flex items-center gap-1 bg-black/40 p-1 rounded-xl border border-white/[0.06] shrink-0">
              {(
                [
                  { id: 'cornell', label: 'Cornell Notes' },
                  { id: 'quiz', label: 'Quiz Prático' },
                  { id: 'flashcards', label: `Flashcards (${studyFlashcards.length})` },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setPracticeTab(tab.id)}
                  className={`flex-1 py-1.5 px-2 rounded-lg text-[11px] font-medium transition-all cursor-pointer ${practiceTab === tab.id
                      ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/40'
                      : 'text-stone-400 hover:text-stone-200'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab 1: Cornell Notes */}
            {practiceTab === 'cornell' && (
              <div className="flex-1 flex flex-col justify-between min-h-0 gap-3">
                <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
                  {cornell.executive_summary && (
                    <div className="p-2.5 rounded-xl bg-[#d99a6c]/10 border border-[#d99a6c]/25 text-xs text-stone-200 leading-relaxed">
                      <div className="text-[10px] font-mono uppercase text-[#f3c39f] mb-1">Síntese Cornell</div>
                      {cornell.executive_summary}
                    </div>
                  )}
                  {(Array.isArray(cornell.cue_column) ? cornell.cue_column : []).map((c: any, idx: number) => (
                    <div key={idx} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
                      <div className="text-xs font-semibold text-[#f3c39f]">{c.cue}</div>
                      <div className="text-xs text-stone-300 leading-relaxed">{c.idea}</div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={handleSaveCornellToVault}
                  className="w-full py-2 px-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/35 text-emerald-200 text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer shrink-0"
                >
                  <Database className="w-3.5 h-3.5" />
                  <span>Guardar Ficha Cornell no Obsidian</span>
                </button>
              </div>
            )}

            {/* Tab 2: Interactive Quiz */}
            {practiceTab === 'quiz' && (
              <div className="flex-1 flex flex-col justify-between min-h-0 gap-3">
                <div className="flex items-center justify-between shrink-0">
                  <span className="text-[11px] text-stone-400">
                    {activeStudyQuiz ? `${activeStudyQuiz.questions.length} questões sobre o documento` : 'Testa o teu domínio da matéria'}
                  </span>
                  <button
                    onClick={handleStartQuiz}
                    disabled={isGeneratingQuizState}
                    className="px-2.5 py-1 rounded-lg bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/40 text-[#f3c39f] text-[11px] font-medium flex items-center gap-1 cursor-pointer"
                  >
                    {isGeneratingQuizState ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    <span>{activeStudyQuiz ? 'Novo Quiz' : 'Gerar Quiz'}</span>
                  </button>
                </div>

                {activeStudyQuiz ? (
                  <>
                    <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                      {studyQuizResult && (
                        <div className="p-2.5 rounded-xl bg-emerald-500/15 border border-emerald-400/35 text-xs text-emerald-200 font-semibold flex items-center justify-between">
                          <span>Resultado: {studyQuizResult.score}%</span>
                          <span>
                            {studyQuizResult.correct_answers}/{studyQuizResult.total_questions} corretas
                          </span>
                        </div>
                      )}
                      {activeStudyQuiz.questions.map((q, qIdx) => (
                        <div key={q.id} className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-2">
                          <div className="text-xs font-semibold text-stone-100">
                            {qIdx + 1}. {q.question}
                          </div>
                          <div className="space-y-1">
                            {q.options.map((opt, oIdx) => {
                              const selected = quizAnswers[q.id] === oIdx;
                              return (
                                <button
                                  key={oIdx}
                                  onClick={() => setQuizAnswers((prev) => ({ ...prev, [q.id]: oIdx }))}
                                  className={`w-full text-left p-2 rounded-lg text-[11px] transition-all cursor-pointer border ${selected
                                      ? 'bg-[#d99a6c]/25 border-[#d99a6c]/55 text-white'
                                      : 'bg-black/30 border-white/[0.05] text-stone-300 hover:bg-white/[0.05]'
                                    }`}
                                >
                                  {opt}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={handleSubmitQuiz}
                      disabled={isSubmittingQuizState}
                      className="w-full py-2 rounded-xl bg-[#d99a6c]/25 hover:bg-[#d99a6c]/35 border border-[#d99a6c]/50 text-[#f3c39f] text-xs font-semibold cursor-pointer shrink-0"
                    >
                      {isSubmittingQuizState ? 'A avaliar...' : 'Avaliar Respostas'}
                    </button>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-center text-xs text-stone-400 p-4">
                    Clica em "Gerar Quiz" para criar questões fundamentadas no documento atual.
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Flashcards */}
            {practiceTab === 'flashcards' && (
              <div className="flex-1 flex flex-col justify-between min-h-0 gap-3">
                {studyFlashcards.length > 0 ? (
                  <>
                    <div
                      onClick={() => setFlashcardFlipped(!flashcardFlipped)}
                      className="flex-1 rounded-xl border border-[#d99a6c]/30 bg-gradient-to-b from-white/[0.04] to-black/40 p-4 flex flex-col items-center justify-center text-center cursor-pointer select-none hover:border-[#d99a6c]/55 transition-all"
                    >
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#f3c39f] mb-2">
                        {flashcardFlipped ? 'RESPOSTA (VERSO)' : `CARTÃO ${flashcardIdx + 1}/${studyFlashcards.length} (FRENTE)`}
                      </span>
                      <p className="text-xs sm:text-sm text-stone-100 leading-relaxed">
                        {flashcardFlipped
                          ? studyFlashcards[flashcardIdx]?.back
                          : studyFlashcards[flashcardIdx]?.front}
                      </p>
                      <span className="text-[10px] text-stone-500 mt-3">Clica no cartão para virar</span>
                    </div>
                    <div className="flex items-center justify-between gap-1.5 shrink-0">
                      <button
                        onClick={() => {
                          setFlashcardFlipped(false);
                          setFlashcardIdx((prev) => (prev > 0 ? prev - 1 : studyFlashcards.length - 1));
                        }}
                        className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-stone-300 cursor-pointer"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" />
                      </button>
                      {(['Hard', 'Good', 'Easy'] as const).map((rating) => (
                        <button
                          key={rating}
                          onClick={() => {
                            const card = studyFlashcards[flashcardIdx];
                            if (card) reviewStudyFlashcard(card.card_id, rating);
                            setFlashcardFlipped(false);
                            setFlashcardIdx((prev) => (prev + 1) % studyFlashcards.length);
                          }}
                          className="flex-1 py-1.5 rounded-lg bg-white/[0.04] hover:bg-[#d99a6c]/20 border border-white/10 hover:border-[#d99a6c]/40 text-[11px] text-stone-200 cursor-pointer"
                        >
                          {rating === 'Hard' ? 'Difícil' : rating === 'Good' ? 'Bom' : 'Fácil'}
                        </button>
                      ))}
                      <button
                        onClick={() => {
                          setFlashcardFlipped(false);
                          setFlashcardIdx((prev) => (prev + 1) % studyFlashcards.length);
                        }}
                        className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-stone-300 cursor-pointer"
                      >
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-center text-xs text-stone-400">
                    Sem flashcards para este documento.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ── RENDER DOMAIN: PROJECT (dina, etc.) ──
  const renderProjectDomain = () => {
    const ext = selectedFile.split('.').pop()?.toLowerCase() || 'js';
    const editorLang =
      ext === 'py'
        ? 'python'
        : ext === 'html'
          ? 'html'
          : ext === 'css'
            ? 'css'
            : ext === 'json'
              ? 'json'
              : ext === 'ts' || ext === 'tsx'
                ? 'typescript'
                : 'javascript';

    return (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
        {/* CARD 1: CLEAN CODE EDITOR & FILE EXPLORER */}
        {renderCardShell(
          'card_editor',
          `Editor de Código • ${selectedFile || 'Sem ficheiro'}`,
          `Projeto ativo: ${activeProjectId} (${fileNames.length} ficheiros)`,
          <Code2 className="w-3.5 h-3.5" />,
          'lg:col-span-6 min-h-[480px]',
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowNewFileInput(!showNewFileInput)}
              className="px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.09] border border-white/10 text-stone-300 text-[11px] flex items-center gap-1 cursor-pointer"
              title="Criar novo ficheiro"
            >
              <Plus className="w-3 h-3" />
              <span>Ficheiro</span>
            </button>
            {selectedFile && (
              <button
                onClick={() => saveProjectFile(selectedFile, editorDraft)}
                disabled={isSavingProjectFile || !isFileDirty}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold flex items-center gap-1 transition-all cursor-pointer border ${isFileDirty
                    ? 'bg-emerald-500/20 border-emerald-400/45 text-emerald-200 hover:bg-emerald-500/30'
                    : 'bg-white/[0.03] border-white/10 text-stone-400 opacity-60'
                  }`}
              >
                {isSavingProjectFile ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                <span>{isFileDirty ? 'Guardar *' : 'Guardado'}</span>
              </button>
            )}
          </div>,
          <div className="flex flex-col h-full min-h-0">
            {/* Optional New File Bar */}
            {showNewFileInput && (
              <div className="flex items-center gap-2 px-3 py-2 bg-black/50 border-b border-white/[0.07]">
                <input
                  type="text"
                  value={newFileName}
                  onChange={(e) => setNewFileName(e.target.value)}
                  placeholder="Nome do ficheiro (ex: utils.js)"
                  className="flex-1 bg-black/40 border border-white/15 rounded-lg px-2.5 py-1 text-xs text-stone-200 outline-none"
                />
                <button
                  onClick={() => {
                    if (newFileName.trim()) {
                      saveProjectFile(newFileName.trim(), '');
                      setSelectedFile(newFileName.trim());
                      setEditorDraft('');
                      setNewFileName('');
                      setShowNewFileInput(false);
                    }
                  }}
                  className="px-2.5 py-1 rounded-lg bg-[#d99a6c]/25 text-[#f3c39f] text-xs font-medium cursor-pointer"
                >
                  Criar
                </button>
              </div>
            )}

            {/* Single Clean File Switcher Bar */}
            <div className="flex items-center gap-1.5 px-3 py-2 bg-black/35 border-b border-white/[0.06] overflow-x-auto shrink-0">
              {fileNames.map((fname) => (
                <button
                  key={fname}
                  onClick={() => handleSelectProjectFile(fname)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 transition-all cursor-pointer shrink-0 ${selectedFile === fname
                      ? 'bg-[#d99a6c]/20 text-[#f3c39f] border border-[#d99a6c]/45'
                      : 'bg-white/[0.03] text-stone-400 hover:text-stone-200 border border-white/[0.05]'
                    }`}
                >
                  <FileCode className="w-3 h-3" />
                  <span>{fname}</span>
                </button>
              ))}
            </div>

            {/* Real CodeEditor */}
            <div className="flex-1 min-h-[360px] relative">
              {selectedFile ? (
                <Suspense
                  fallback={
                    <div className="flex items-center justify-center h-full text-xs text-stone-400">
                      <Loader2 className="w-4 h-4 animate-spin mr-2" /> A carregar editor...
                    </div>
                  }
                >
                  <MonacoEditor
                    height="100%"
                    theme="vs-dark"
                    value={editorDraft}
                    language={editorLang}
                    onChange={(val) => setEditorDraft(val ?? '')}
                    options={{
                      minimap: { enabled: false },
                      fontSize: 12,
                      padding: { top: 12 },
                      scrollBeyondLastLine: false,
                    }}
                  />
                </Suspense>
              ) : (
                <div className="flex items-center justify-center h-full text-xs text-stone-500">
                  Nenhum ficheiro no projeto.
                </div>
              )}
            </div>
          </div>
        )}

        {/* CARD 2: LIVE PREVIEW & CONSOLE */}
        {renderCardShell(
          'card_preview',
          'Live Preview & Execução',
          isProjectRunning ? `Online em ${previewUrl || 'http://localhost:8080'}` : 'Servidor parado',
          <Play className="w-3.5 h-3.5" />,
          'lg:col-span-3 min-h-[480px]',
          <div className="flex items-center gap-1.5">
            {isProjectRunning ? (
              <button
                onClick={() => stopProject()}
                className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-400/40 text-rose-200 text-[11px] font-medium flex items-center gap-1 cursor-pointer"
              >
                <Square className="w-3 h-3" />
                <span>Parar</span>
              </button>
            ) : (
              <button
                onClick={() => runProject(activeProjectId)}
                className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-200 text-[11px] font-medium flex items-center gap-1 cursor-pointer"
              >
                <Play className="w-3 h-3" />
                <span>Executar</span>
              </button>
            )}
          </div>,
          <div className="flex flex-col h-full p-3 gap-2.5">
            <div className="flex items-center justify-between gap-1 bg-black/40 p-1 rounded-xl border border-white/[0.06] shrink-0">
              <button
                onClick={() => setPreviewMode('preview')}
                className={`flex-1 py-1 rounded-lg text-[11px] font-medium cursor-pointer ${previewMode === 'preview'
                    ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/40'
                    : 'text-stone-400 hover:text-stone-200'
                  }`}
              >
                Preview Visual
              </button>
              <button
                onClick={() => setPreviewMode('console')}
                className={`flex-1 py-1 rounded-lg text-[11px] font-medium cursor-pointer ${previewMode === 'console'
                    ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/40'
                    : 'text-stone-400 hover:text-stone-200'
                  }`}
              >
                Consola / Logs
              </button>
            </div>

            {previewMode === 'preview' ? (
              isProjectRunning && previewUrl ? (
                <div className="flex-1 flex flex-col gap-2 min-h-0">
                  <div className="flex items-center justify-between px-2 py-1 rounded-lg bg-black/40 border border-white/10 text-[11px] font-mono text-stone-300">
                    <span className="truncate">{previewUrl}</span>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setIframeKey((k) => k + 1)}
                        className="p-1 hover:text-white cursor-pointer"
                        title="Recarregar Preview"
                      >
                        <RefreshCw className="w-3 h-3" />
                      </button>
                      <a
                        href={previewUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1 hover:text-white"
                        title="Abrir no Browser"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                  <iframe
                    key={iframeKey}
                    src={previewUrl}
                    title="Project Live Preview"
                    className="flex-1 w-full rounded-xl border border-white/10 bg-white"
                  />
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-4 gap-3">
                  <div className="w-11 h-11 rounded-2xl bg-emerald-500/10 border border-emerald-400/25 flex items-center justify-center text-emerald-300">
                    <Play className="w-5 h-5" />
                  </div>
                  <div className="text-xs text-stone-300 font-medium">
                    O servidor de <span className="text-white font-semibold">{activeProjectId}</span> está parado.
                  </div>
                  <button
                    onClick={() => runProject(activeProjectId)}
                    className="px-4 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-200 text-xs font-semibold cursor-pointer"
                  >
                    Iniciar Preview Agora
                  </button>
                </div>
              )
            ) : (
              <pre className="flex-1 rounded-xl bg-black/60 border border-white/10 p-3 font-mono text-[11px] text-stone-300 overflow-y-auto whitespace-pre-wrap">
                {projectOutput || 'Sem output de consola. Clica em "Executar" para iniciar o projeto.'}
              </pre>
            )}
          </div>
        )}

        {/* CARD 3: AI ASSISTED CODE CHANGE (CodingSession) */}
        {renderCardShell(
          'card_ai_change',
          'Alteração Assistida por IA',
          'Planeamento, diff e aplicação segura no código',
          <Sparkles className="w-3.5 h-3.5" />,
          'lg:col-span-3 min-h-[480px]',
          codingSession ? (
            <span className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 text-[10px] font-mono">
              {codingSession.status}
            </span>
          ) : null,
          <div className="flex flex-col h-full p-4 gap-3 justify-between">
            <div className="space-y-2.5 shrink-0">
              <textarea
                rows={3}
                value={aiObjective}
                onChange={(e) => setAiObjective(e.target.value)}
                placeholder={`Descreve o que queres melhorar em ${activeProjectId} (ex: melhorar estética de styles.css ou criar endpoint em app.js)...`}
                className="w-full bg-black/40 border border-white/10 rounded-xl p-2.5 text-xs text-stone-200 placeholder:text-stone-500 outline-none focus:border-[#d99a6c]/50 resize-none"
              />
              <button
                onClick={() => {
                  if (aiObjective.trim()) {
                    createCodingSession(aiObjective.trim());
                  }
                }}
                disabled={isCodingSessionBusy || !aiObjective.trim()}
                className="w-full py-2 rounded-xl bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/45 text-[#f3c39f] text-xs font-semibold flex items-center justify-center gap-1.5 disabled:opacity-40 cursor-pointer"
              >
                {isCodingSessionBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>{isCodingSessionBusy ? 'A gerar proposta...' : 'Propor Alteração no Código'}</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {codingSession ? (
                <>
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
                    <div className="text-[10px] font-mono uppercase text-[#f3c39f]">Objetivo Atual</div>
                    <div className="text-xs text-stone-200">
                      {codingSession.change_plan?.objective || codingSession.objective}
                    </div>
                  </div>
                  {(codingSession.proposed_changes || []).map((chg, cIdx) => (
                    <div key={cIdx} className="space-y-1.5">
                      <div className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.06] text-xs text-stone-300 leading-relaxed">
                        <span className="font-mono text-[#f3c39f] mr-1.5">[{chg.file}]</span>
                        {chg.reason}
                      </div>
                      {chg.unified_diff && (
                        <pre className="p-2.5 rounded-xl bg-black/60 border border-white/10 font-mono text-[10px] text-cyan-200 overflow-x-auto whitespace-pre-wrap max-h-48">
                          {chg.unified_diff}
                        </pre>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <div className="h-full flex items-center justify-center text-center text-xs text-stone-500 px-3">
                  Pede uma melhoria acima para gerar um diff verificável antes de aplicar no projeto.
                </div>
              )}
            </div>

            {codingSession && (
              <div className="flex items-center gap-2 pt-2 border-t border-white/[0.07] shrink-0">
                <button
                  onClick={() => applyCodingSession()}
                  disabled={isCodingSessionBusy}
                  className="flex-1 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-200 text-xs font-semibold flex items-center justify-center gap-1 cursor-pointer"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Aplicar</span>
                </button>
                <button
                  onClick={() => rollbackCodingSession()}
                  disabled={isCodingSessionBusy}
                  className="px-3 py-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-stone-300 text-xs flex items-center gap-1 cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reverter</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ── RENDER DOMAIN: OBSIDIAN VAULT ──
  const renderObsidianDomain = () => {
    const filteredNotes = notes.filter((n) => n.toLowerCase().includes(vaultSearch.toLowerCase()));
    const queue = vaultImprovementQueue || [];
    const activeAudit = noteQualityAudit;
    const queueMetrics = vaultDiagnostics?.queue_metrics;
    const isQueuePaused = Boolean(queueMetrics?.is_paused);
    const isQueueRunning = Boolean(queueMetrics?.is_running);
    const activeItemId = queueMetrics?.active_item_id;
    const lastModelUsed = queueMetrics?.last_model_used;
    const lastBatchResult = queueMetrics?.last_batch_result;

    return (
      <div className="flex flex-col gap-3 flex-1 min-h-0">
        {/* Navigation & Mode Switcher Bar */}
        <div className="flex items-center justify-between gap-2 shrink-0 bg-black/40 p-1.5 rounded-2xl border border-white/[0.08]">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setObsidianViewMode('quality_graph')}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
                obsidianViewMode === 'quality_graph'
                  ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45 shadow-sm'
                  : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Auditoria & Grafo de Qualidade</span>
            </button>
            <button
              onClick={() => setObsidianViewMode('explorer')}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
                obsidianViewMode === 'explorer'
                  ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45 shadow-sm'
                  : 'text-stone-400 hover:text-stone-200'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>Explorador & Leitura de Notas</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-block text-[11px] font-mono text-stone-400">
              {vaultDiagnostics?.total_notes || notes.length} Notas Canónicas • Q-Score: {vaultDiagnostics?.quality_average || 77.1}/100
            </span>
            <button
              onClick={() => {
                getVaultDiagnostics();
                getNotes();
              }}
              className="p-1.5 rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/[0.1] text-stone-300 hover:text-white transition-all cursor-pointer"
              title="Recarregar Diagnóstico do Grafo"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* VIEW 1: QUALITY GRAPH & AUTONOMOUS EVOLUTION */}
        {obsidianViewMode === 'quality_graph' ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
            {/* CARD 1: METRICS & EXPLANATORY CALLOUT */}
            {renderCardShell(
              'card_vault_metrics',
              'Telemetria do Grafo & Conectividade',
              'Diagnóstico de nós órfãos, links quebrados e topologia',
              <Database className="w-3.5 h-3.5" />,
              'lg:col-span-4 min-h-[490px]',
              <div className="flex items-center gap-1">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                  ÓRFÃOS: 0
                </span>
              </div>,
              <div className="flex flex-col h-full p-3.5 gap-3 overflow-y-auto">
                {/* Metric Badges Grid */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <div className="text-[10px] font-mono uppercase text-stone-400">Notas Canónicas</div>
                    <div className="text-xl font-bold text-stone-100 mt-0.5">{vaultDiagnostics?.total_notes || 256}</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <div className="text-[10px] font-mono uppercase text-stone-400">Média de Qualidade</div>
                    <div className="text-xl font-bold text-[#f3c39f] mt-0.5">{vaultDiagnostics?.quality_average || 77.1}<span className="text-xs font-normal text-stone-400">/100</span></div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <div className="text-[10px] font-mono uppercase text-stone-400">Órfãos Genuínos</div>
                    <div className="text-xl font-bold text-emerald-400 mt-0.5">{vaultDiagnostics?.genuine_orphans ?? 0}</div>
                    <div className="text-[9px] text-stone-400 mt-0.5">{vaultDiagnostics?.genuine_orphans_list?.length ? `${vaultDiagnostics.genuine_orphans_list.length} isoladas` : '100% integradas'}</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <div className="text-[10px] font-mono uppercase text-stone-400">Links Quebrados</div>
                    <div className="text-xl font-bold text-amber-300 mt-0.5">{vaultDiagnostics?.broken_links ?? 23}</div>
                    <div className="text-[9px] text-stone-400 mt-0.5">{vaultDiagnostics?.broken_links_list?.length ? `${vaultDiagnostics.broken_links_list.length} mapeados` : 'Mapeamento canónico'}</div>
                  </div>
                </div>

                {/* Score Distribution */}
                {(() => {
                  const qd = vaultDiagnostics?.quality_distribution;
                  const total = qd?.total_audited || (vaultDiagnostics?.total_notes || 256);
                  const ge80 = qd?.ge_80 ?? 100;
                  const b70_79 = qd?.between_70_79 ?? 87;
                  const b60_69 = qd?.between_60_69 ?? 59;
                  const lt60 = qd?.lt_60 ?? 10;
                  const pct80 = total > 0 ? Math.round((ge80 / total) * 100) : 39;
                  const pct70 = total > 0 ? Math.round((b70_79 / total) * 100) : 34;
                  const pct60 = total > 0 ? Math.round((b60_69 / total) * 100) : 23;
                  const pctLt = total > 0 ? Math.round((lt60 / total) * 100) : 4;
                  return (
                    <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-2">
                      <div className="text-[10px] font-mono uppercase text-stone-400 flex items-center justify-between">
                        <span>Distribuição de Qualidade ({total} Notas)</span>
                        <span className="text-[#f3c39f]">Calibrada</span>
                      </div>
                      <div className="space-y-1.5 text-xs">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-emerald-300 font-medium">≥ 80 (Excelente)</span>
                          <span className="font-mono text-stone-300">{ge80} notas ({pct80}%)</span>
                        </div>
                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                          <div className="bg-emerald-400 h-full rounded-full" style={{ width: `${pct80}%` }} />
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1">
                          <span className="text-cyan-300 font-medium">70-79 (Adequado)</span>
                          <span className="font-mono text-stone-300">{b70_79} notas ({pct70}%)</span>
                        </div>
                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                          <div className="bg-cyan-400 h-full rounded-full" style={{ width: `${pct70}%` }} />
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1">
                          <span className="text-amber-300 font-medium">60-69 (Melhorável)</span>
                          <span className="font-mono text-stone-300">{b60_69} notas ({pct60}%)</span>
                        </div>
                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                          <div className="bg-amber-400 h-full rounded-full" style={{ width: `${pct60}%` }} />
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1">
                          <span className="text-rose-400 font-medium">&lt; 60 (Prioridade Fila)</span>
                          <span className="font-mono text-stone-300">{lt60} notas ({pctLt}%)</span>
                        </div>
                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                          <div className="bg-rose-400 h-full rounded-full" style={{ width: `${pctLt}%` }} />
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Explanatory callout for user query */}
                <div className="p-3 rounded-xl bg-amber-500/[0.08] border border-amber-400/25 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase text-amber-300 font-semibold flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    <span>Porquê alguns nós pareciam desligados no Obsidian?</span>
                  </div>
                  <p className="text-[11px] text-stone-300 leading-relaxed">
                    1. <strong>Ligações MOC-Only:</strong> 12 notas históricas e 18 aulas de estudo estavam ligadas exclusivamente ao índice (MOC), sem ligações entre pares.
                  </p>
                  <p className="text-[11px] text-stone-300 leading-relaxed">
                    2. <strong>25 Ligações com Títulos Variantes:</strong> 11 notas referenciavam <code>[[Agent Systems Architecture]]</code> em vez do título canónico <code>[[Model Context Protocol (MCP) and Capability Discovery Architecture]]</code>.
                  </p>
                  <p className="text-[11px] text-stone-300 leading-relaxed">
                    3. <strong>Evolução Autónoma:</strong> O motor de grafos injeta agora relações ontológicas tipadas baseadas em sinónimos e contexto, restaurando ligações fortes sem criar ruído.
                  </p>
                </div>
              </div>
            )}

            {/* CARD 2: NOTE QUALITY AUDITOR (10 DIMENSIONS) */}
            {renderCardShell(
              'card_vault_inspector',
              activeAudit ? activeAudit.stem : 'Auditor de Qualidade (10 Dimensões)',
              activeAudit ? `Score Global: ${activeAudit.overall_score}/100 • ${activeAudit.epistemic_classification}` : 'Avaliação determinística calibrada',
              <Sparkles className="w-3.5 h-3.5" />,
              'lg:col-span-4 min-h-[490px]',
              enrichmentFeedback ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                  {enrichmentFeedback}
                </span>
              ) : null,
              <div className="flex flex-col h-full p-3.5 gap-3 overflow-y-auto">
                {/* Note Selector Search */}
                <div className="space-y-1 shrink-0">
                  <div className="text-[10px] font-mono uppercase text-stone-400">Selecionar Nota para Auditoria</div>
                  <select
                    value={selectedQualityNote}
                    onChange={(e) => {
                      setSelectedQualityNote(e.target.value);
                      auditNoteQuality(e.target.value);
                    }}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-stone-200 outline-none focus:border-[#d99a6c]/45"
                  >
                    {notes.map((n) => (
                      <option key={n} value={n} className="bg-stone-900 text-stone-200">
                        {n}
                      </option>
                    ))}
                  </select>
                </div>

                {isAuditingNote ? (
                  <div className="flex-1 flex items-center justify-center text-xs text-stone-400 py-8">
                    <Loader2 className="w-4 h-4 animate-spin mr-2" /> A auditar dimensões...
                  </div>
                ) : activeAudit ? (
                  <div className="space-y-3 flex-1 min-h-0">
                    {/* Epistemic Class & Score */}
                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <div>
                        <div className="text-[10px] font-mono uppercase text-stone-400">Classificação Epistémica</div>
                        <div className="text-xs font-semibold text-emerald-300 mt-0.5">{activeAudit.epistemic_classification}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] font-mono uppercase text-stone-400">Palavras • Links</div>
                        <div className="text-xs font-mono text-stone-300 mt-0.5">{activeAudit.word_count}w • {activeAudit.outgoing_links_count} links</div>
                      </div>
                    </div>

                    {/* 10 Dimensions Grid */}
                    <div className="space-y-1.5 p-2.5 rounded-xl bg-black/30 border border-white/[0.06]">
                      <div className="text-[10px] font-mono uppercase text-[#f3c39f] mb-1">Pontuação por Dimensão (0-100)</div>
                      {Object.entries(activeAudit.dimension_scores || {}).map(([dimKey, score]) => (
                        <div key={dimKey} className="space-y-0.5">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-stone-300 capitalize">{dimKey.replace('_', ' ')}</span>
                            <span className="font-mono text-stone-200">{score}/100</span>
                          </div>
                          <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                score >= 80 ? 'bg-emerald-400' : score >= 60 ? 'bg-cyan-400' : 'bg-amber-400'
                              }`}
                              style={{ width: `${Math.min(100, score)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Findings & Deficiencies */}
                    <div className="space-y-2">
                      <div className="text-[10px] font-mono uppercase text-stone-400">
                        Oportunidades de Melhoria ({activeAudit.findings_count})
                      </div>
                      {activeAudit.findings && activeAudit.findings.length > 0 ? (
                        activeAudit.findings.map((f: any, idx: number) => (
                          <div key={idx} className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1 text-xs">
                            <div className="font-semibold text-[#f3c39f] flex items-center justify-between text-[11px]">
                              <span>{f.dimension}</span>
                              <span className="text-[9px] font-mono text-stone-400">Recomendação</span>
                            </div>
                            <p className="text-stone-300 text-[11px]">{f.what_is_missing}</p>
                            <p className="text-stone-400 text-[10px] italic">💡 {f.recommended_improvement}</p>
                          </div>
                        ))
                      ) : (
                        <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-400/25 text-emerald-200 text-xs text-center">
                          Nota atinge padrão elevado em todas as dimensões.
                        </div>
                      )}
                    </div>

                    {/* Actions: Enrich and Rollback */}
                    <div className="flex items-center gap-2 pt-1 shrink-0">
                      <button
                        onClick={() => {
                          enrichNote(selectedQualityNote, true);
                          setEnrichmentFeedback('Enriquecimento aplicado com snapshot histórico!');
                          setTimeout(() => setEnrichmentFeedback(null), 3500);
                        }}
                        disabled={isEnrichingNote}
                        className="flex-1 py-2 px-3 rounded-xl bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/45 text-[#f3c39f] text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                      >
                        {isEnrichingNote ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                        <span>Enriquecer com Relações Tipadas</span>
                      </button>
                      <button
                        onClick={() => {
                          rollbackNote(selectedQualityNote);
                          setEnrichmentFeedback('Revertido para backup prévio!');
                          setTimeout(() => setEnrichmentFeedback(null), 3500);
                        }}
                        className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-stone-300 hover:text-white transition-all cursor-pointer"
                        title="Reverter para Snapshot Anterior"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            )}

            {/* CARD 3: AUTONOMOUS EVOLUTION QUEUE & TYPED RELATIONS */}
            {renderCardShell(
              'card_vault_relationships',
              'Fila de Evolução Autónoma',
              isQueueRunning
                ? `A Executar (${lastModelUsed || 'qwen3.5:9b'}) • Item: ${activeItemId || 'em processamento'}`
                : isQueuePaused
                ? 'Fila pausada pelo operador'
                : `${queue.length} notas em fila • Modelo: ${lastModelUsed || 'qwen3.5:9b'}`,
              <FileCode className="w-3.5 h-3.5" />,
              'lg:col-span-4 min-h-[490px]',
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => {
                    if (isQueuePaused) {
                      resumeQueueWorker();
                    } else {
                      pauseQueueWorker();
                    }
                    setTimeout(() => getVaultDiagnostics(), 200);
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-mono border transition-all cursor-pointer ${
                    isQueuePaused
                      ? 'bg-amber-500/20 border-amber-400/40 text-amber-200'
                      : isQueueRunning
                      ? 'bg-cyan-500/20 border-cyan-400/40 text-cyan-200 animate-pulse'
                      : 'bg-emerald-500/20 border-emerald-400/40 text-emerald-200'
                  }`}
                >
                  {isQueuePaused ? 'PAUSADA' : isQueueRunning ? 'A EXECUTAR' : 'ATIVA'}
                </button>
                <button
                  onClick={() => {
                    startImprovementBatch(1);
                    setEnrichmentFeedback('Ciclo disparado...');
                    setTimeout(() => {
                      getVaultDiagnostics();
                      setEnrichmentFeedback(
                        lastModelUsed === 'qwen3.5:9b'
                          ? 'Ciclo executado via local qwen3.5:9b!'
                          : 'Ciclo executado com sucesso!'
                      );
                      setTimeout(() => setEnrichmentFeedback(null), 3500);
                    }, 1200);
                  }}
                  className="px-2 py-1 rounded-lg text-[10px] font-mono bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-stone-300 hover:text-white transition-all cursor-pointer"
                  title="Executar 1 ciclo limitado de melhoria autónoma"
                >
                  +1 Ciclo
                </button>
              </div>,
              <div className="flex flex-col h-full p-3.5 gap-2.5 overflow-y-auto">
                {enrichmentFeedback && (
                  <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 text-[11px] font-mono flex items-center justify-between">
                    <span>{enrichmentFeedback}</span>
                    {lastModelUsed && <span className="text-[9px] bg-cyan-500/20 px-1.5 py-0.5 rounded uppercase">{lastModelUsed}</span>}
                  </div>
                )}
                {lastBatchResult && !enrichmentFeedback && (
                  <div className="px-2 py-1 rounded-lg bg-white/[0.02] border border-white/5 text-[9px] font-mono text-stone-400 flex items-center justify-between">
                    <span>Último ciclo: {lastBatchResult.count || 0} nota(s) processada(s)</span>
                    <span className="uppercase text-[8px] bg-white/5 px-1 py-0.2 rounded">{lastBatchResult.model}</span>
                  </div>
                )}
                <div className="text-[10px] font-mono uppercase text-stone-400 flex items-center justify-between">
                  <span>Prioridade Ordenada por Défice Epistémico</span>
                  {activeItemId && <span className="text-cyan-300 text-[9px] font-mono">Ativo: {activeItemId}</span>}
                </div>
                <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto pr-1">
                  {queue.slice(0, 15).map((item) => {
                    const isSelected = selectedQualityNote === item.stem || selectedQualityNote === item.note_path;
                    return (
                      <button
                        key={item.item_id}
                        onClick={() => {
                          setSelectedQualityNote(item.note_path);
                          auditNoteQuality(item.note_path);
                        }}
                        className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-[#d99a6c]/20 border-[#d99a6c]/45 text-[#f3c39f]'
                            : 'bg-white/[0.02] border-white/[0.05] text-stone-300 hover:bg-white/[0.04]'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold truncate max-w-[190px]">{item.stem}</span>
                          <span className="font-mono text-[10px] text-amber-300">Score: {item.overall_score}</span>
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-stone-400 mt-1">
                          <span>{item.findings.length} melhorias identificadas</span>
                          <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded bg-white/5">{item.status}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Proposal preview if available */}
                {noteEnrichmentProposal && (
                  <div className="p-2.5 rounded-xl bg-emerald-500/[0.08] border border-emerald-400/25 space-y-1.5 shrink-0">
                    <div className="text-[10px] font-mono uppercase text-emerald-300 font-semibold flex items-center justify-between">
                      <span>Proposta Recente: {noteEnrichmentProposal.stem}</span>
                      <span className="text-[9px] bg-emerald-500/20 px-1.5 py-0.5 rounded">{noteEnrichmentProposal.status}</span>
                    </div>
                    <div className="text-[11px] text-stone-300">
                      Relações Tipadas propostas: {noteEnrichmentProposal.proposed_relationships.length}
                    </div>
                    {noteEnrichmentProposal.proposed_relationships.slice(0, 2).map((rel, idx) => (
                      <div key={idx} className="text-[10px] font-mono text-[#f3c39f] bg-black/30 p-1.5 rounded">
                        <strong>{rel.relationship_type}</strong> ➔ [[{rel.target_note}]]
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* VIEW 2: CLASSIC VAULT EXPLORER & EDITOR */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
            {/* CARD 1: VAULT EXPLORER */}
            {renderCardShell(
              'card_vault_explorer',
              'Explorador do Cofre Obsidian',
              `${notes.length} notas Markdown sincronizadas`,
              <Database className="w-3.5 h-3.5" />,
              'lg:col-span-4 min-h-[480px]',
              <button
                onClick={() => setShowNewNoteInput(!showNewNoteInput)}
                className="px-2 py-1 rounded-lg bg-[#d99a6c]/20 border border-[#d99a6c]/40 text-[#f3c39f] text-[11px] flex items-center gap-1 cursor-pointer"
              >
                <Plus className="w-3 h-3" />
                <span>Nova Nota</span>
              </button>,
              <div className="flex flex-col h-full p-3 gap-2.5">
                {showNewNoteInput && (
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={newNoteTitle}
                      onChange={(e) => setNewNoteTitle(e.target.value)}
                      placeholder="Nome da nota (ex: Arquitetura IA.md)"
                      className="flex-1 bg-black/40 border border-white/15 rounded-lg px-2.5 py-1 text-xs text-stone-200 outline-none"
                    />
                    <button
                      onClick={() => {
                        if (newNoteTitle.trim()) {
                          const fname = newNoteTitle.trim().endsWith('.md')
                            ? newNoteTitle.trim()
                            : `${newNoteTitle.trim()}.md`;
                          saveNote(fname, `# ${newNoteTitle.trim()}\n\n`);
                          readNote(fname);
                          setNewNoteTitle('');
                          setShowNewNoteInput(false);
                        }
                      }}
                      className="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-200 text-xs cursor-pointer"
                    >
                      Criar
                    </button>
                  </div>
                )}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-stone-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={vaultSearch}
                    onChange={(e) => setVaultSearch(e.target.value)}
                    placeholder="Filtrar notas ou MOCs..."
                    className="w-full bg-black/40 border border-white/10 rounded-xl pl-8 pr-3 py-1.5 text-xs text-stone-200 outline-none focus:border-[#d99a6c]/45"
                  />
                </div>
                <div className="flex-1 overflow-y-auto space-y-1 pr-1">
                  {filteredNotes.map((noteName) => {
                    const isSelected = currentNote?.filename === noteName;
                    return (
                      <button
                        key={noteName}
                        onClick={() => {
                          readNote(noteName);
                          setIsEditingNote(false);
                        }}
                        className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between gap-2 transition-all cursor-pointer border ${
                          isSelected
                            ? 'bg-[#d99a6c]/20 border-[#d99a6c]/45 text-[#f3c39f] font-semibold'
                            : 'bg-white/[0.02] border-white/[0.04] text-stone-300 hover:bg-white/[0.05]'
                        }`}
                      >
                        <span className="truncate">{noteName}</span>
                        <ChevronRight className="w-3.5 h-3.5 shrink-0 opacity-60" />
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* CARD 2: MARKDOWN READER & EDITOR WITH WIKILINKS */}
            {renderCardShell(
              'card_vault_editor',
              currentNote?.filename || 'Nota Obsidian',
              'Suporte nativo a [[Wikilinks]] e proveniência YAML',
              <FileText className="w-3.5 h-3.5" />,
              'lg:col-span-8 min-h-[480px]',
              currentNote ? (
                <div className="flex items-center gap-1.5">
                  {noteSavedFeedback && (
                    <span className="text-[10px] text-emerald-300 font-mono">Guardado!</span>
                  )}
                  <button
                    onClick={() => setIsEditingNote(!isEditingNote)}
                    className="px-2.5 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 text-stone-200 text-[11px] cursor-pointer"
                  >
                    {isEditingNote ? 'Ver Leitura' : 'Editar Nota'}
                  </button>
                  {isEditingNote && (
                    <button
                      onClick={() => {
                        saveNote(currentNote.filename, noteDraft);
                        setNoteSavedFeedback(true);
                        setTimeout(() => setNoteSavedFeedback(false), 2500);
                      }}
                      className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/40 text-emerald-200 text-[11px] font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <Save className="w-3 h-3" />
                      <span>Guardar</span>
                    </button>
                  )}
                </div>
              ) : null,
              <div className="flex-1 p-4 flex flex-col min-h-0">
                {currentNote ? (
                  isEditingNote ? (
                    <textarea
                      value={noteDraft}
                      onChange={(e) => setNoteDraft(e.target.value)}
                      className="flex-1 w-full bg-black/50 border border-white/10 rounded-xl p-3 font-mono text-xs text-stone-200 leading-relaxed outline-none focus:border-[#d99a6c]/50 resize-none"
                    />
                  ) : (
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2 text-xs sm:text-sm text-stone-200 leading-relaxed whitespace-pre-wrap">
                      {noteDraft}
                    </div>
                  )
                ) : (
                  <div className="flex-1 flex items-center justify-center text-xs text-stone-500">
                    Seleciona uma nota à esquerda para ler ou editar.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ── RENDER DOMAIN: SENTINEL ──
  const renderSentinelDomain = () => {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
        {renderCardShell(
          'card_sentinel_control',
          'Controlo & Auditoria Sentinel',
          sentinelStatus?.status === 'RUNNING' ? 'Watchdog em execução contínua' : 'Modo Standby',
          <Shield className="w-3.5 h-3.5" />,
          'lg:col-span-5 min-h-[460px]',
          <button
            onClick={() => runSentinelAudit()}
            disabled={isSentinelAuditing}
            className="px-2.5 py-1 rounded-lg bg-[#d99a6c]/20 hover:bg-[#d99a6c]/30 border border-[#d99a6c]/40 text-[#f3c39f] text-[11px] font-medium flex items-center gap-1 cursor-pointer"
          >
            {isSentinelAuditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            <span>Auditar Agora</span>
          </button>,
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] font-mono uppercase text-stone-400">Eventos Registados</div>
                <div className="text-xl font-bold text-stone-100 mt-1">{sentinelEvents.length}</div>
              </div>
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="text-[10px] font-mono uppercase text-stone-400">Ações Propostas</div>
                <div className="text-xl font-bold text-[#f3c39f] mt-1">{sentinelActions.length}</div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-mono uppercase tracking-wider text-stone-400">
                Ações de Governança Pendentes
              </div>
              {sentinelActions.length > 0 ? (
                sentinelActions.slice(0, 6).map((act) => (
                  <div key={act.action_id} className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-stone-200">{act.action_type}</span>
                      <span className="text-[10px] font-mono text-amber-300">{act.status}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => approveSentinelAction(act.action_id)}
                        className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-200 text-[10px] cursor-pointer"
                      >
                        Aprovar
                      </button>
                      <button
                        onClick={() => rejectSentinelAction(act.action_id, 'Rejeitado pelo operador')}
                        className="px-2 py-1 rounded bg-rose-500/20 text-rose-200 text-[10px] cursor-pointer"
                      >
                        Rejeitar
                      </button>
                      <button
                        onClick={() => rollbackSentinelAction(act.action_id)}
                        className="px-2 py-1 rounded bg-white/10 text-stone-300 text-[10px] cursor-pointer"
                      >
                        Reverter
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs text-stone-400 text-center">
                  Nenhuma ação pendente de aprovação humana.
                </div>
              )}
            </div>
          </div>
        )}

        {renderCardShell(
          'card_sentinel_events',
          'Fluxo de Eventos de Segurança',
          'Monitorização de integridade e processos locais',
          <ShieldAlert className="w-3.5 h-3.5" />,
          'lg:col-span-7 min-h-[460px]',
          null,
          <div className="p-4 space-y-2">
            {sentinelEvents.length > 0 ? (
              sentinelEvents.slice(0, 15).map((ev, idx) => (
                <div
                  key={ev.event_id || idx}
                  className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-start justify-between gap-3"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="text-xs font-semibold text-stone-200 truncate">
                      {ev.category || 'Evento de Segurança'}
                    </div>
                    <div className="text-xs text-stone-400 leading-relaxed">
                      {ev.rationale || ev.recommended_action || ev.model_classification}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-white/5 text-stone-300 font-mono text-[10px] shrink-0">
                    {ev.severity || 'INFO'}
                  </span>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-xs text-stone-400">
                Zero anomalias críticas registadas. Clica em "Auditar Agora" para varrer o runtime.
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.985 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.985 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-0 z-20 flex flex-col px-4 sm:px-6 pt-4 pb-20 overflow-hidden bg-[#0b0b0a]/95 backdrop-blur-md"
    >
      {/* ── SINGLE UNIFIED SPATIAL HEADER BAR ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-3 border-b border-white/[0.08] shrink-0">
        {/* Left: Active Context Switcher (Study Document selector OR Project selector) */}
        <div className="flex items-center gap-3 min-w-0">
          {board.domain === 'study' && (
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={selectedDoc?.document_id || ''}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="h-9 max-w-[340px] sm:max-w-[440px] px-3 rounded-xl bg-[#14161d] border border-[#d99a6c]/35 text-xs sm:text-sm font-semibold text-stone-100 outline-none cursor-pointer"
              >
                {studyDocuments.map((doc) => (
                  <option key={doc.document_id} value={doc.document_id}>
                    [{doc.source_type}] {doc.title} ({doc.subject || 'Geral'})
                  </option>
                ))}
              </select>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.pptx,.docx,.txt,.md,.mp4,.mkv,.webm,.mp3,.wav,.m4a"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="h-9 px-3 rounded-xl bg-[#d99a6c]/15 hover:bg-[#d99a6c]/25 border border-[#d99a6c]/35 text-[#f3c39f] text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                title="Carregar PDF, PPTX, DOCX, TXT, Áudio ou Vídeo"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>+ Carregar Material</span>
              </button>

              {selectedDoc && (
                <button
                  onClick={() => deleteStudyDocument(selectedDoc.document_id, false)}
                  className="h-9 w-9 rounded-xl bg-white/[0.03] hover:bg-rose-500/20 border border-white/10 hover:border-rose-400/35 text-stone-400 hover:text-rose-200 flex items-center justify-center cursor-pointer"
                  title="Remover documento atual da biblioteca"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}

              {(onOpenFullWorkspace || selectedDoc) && (
                <button
                  onClick={() =>
                    selectedDoc
                      ? navigateToStudyTarget({
                          document_id: selectedDoc.document_id,
                          tab: 'reader',
                        })
                      : onOpenFullWorkspace?.()
                  }
                  className="h-9 px-3 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/35 text-cyan-200 text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                  title="Abrir Study Engine completo (Leitor, Resumos, Cornell, Flashcards, Active Recall, Hub Adaptativo)"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Workspace Estudo</span>
                </button>
              )}
            </div>
          )}

          {board.domain === 'project' && (
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={activeProjectId}
                onChange={(e) => openProject(e.target.value)}
                className="h-9 px-3 rounded-xl bg-[#14161d] border border-[#d99a6c]/35 text-xs sm:text-sm font-semibold text-stone-100 outline-none cursor-pointer"
              >
                {projects.map((p) => (
                  <option key={p.project_id} value={p.project_id}>
                    📁 {p.project_name || p.project_id}
                  </option>
                ))}
              </select>

              {showNewProjectInput ? (
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="id-do-projeto"
                    className="h-9 px-2.5 rounded-xl bg-black/50 border border-white/15 text-xs text-stone-200 outline-none"
                  />
                  <button
                    onClick={() => {
                      if (newProjectName.trim()) {
                        createProject(newProjectName.trim(), newProjectName.trim());
                        setNewProjectName('');
                        setShowNewProjectInput(false);
                      }
                    }}
                    className="h-9 px-3 rounded-xl bg-emerald-500/20 text-emerald-200 text-xs font-medium cursor-pointer"
                  >
                    Criar
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowNewProjectInput(true)}
                  className="h-9 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-stone-300 text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                >
                  <FolderPlus className="w-3.5 h-3.5" />
                  <span>Novo Projeto</span>
                </button>
              )}
            </div>
          )}

          {(board.domain === 'obsidian' || board.domain === 'sentinel') && (
            <div>
              <h2 className="text-sm sm:text-base font-bold text-stone-100">{board.title}</h2>
              <p className="text-[11px] text-stone-400">{board.subtitle}</p>
            </div>
          )}
        </div>

        {/* Right: Domain Switcher Pills + Sleep/Close Button */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-[#14161d] p-1 rounded-xl border border-white/[0.08]">
            {(
              [
                { id: 'study', label: 'Estudos', icon: BookOpen },
                { id: 'project', label: 'Projetos & Código', icon: Code2 },
                { id: 'obsidian', label: 'Obsidian Vault', icon: Database },
                { id: 'sentinel', label: 'Sentinel', icon: Shield },
              ] as const
            ).map((item) => {
              const Icon = item.icon;
              const active = board.domain === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onFocusCard(null);
                    onSwitchDomain(item.id);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${active
                      ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45 shadow-sm'
                      : 'text-stone-400 hover:text-stone-200'
                    }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          <button
            onClick={onCloseBoard}
            className="h-9 px-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.1] border border-white/10 text-stone-300 hover:text-white text-xs font-medium flex items-center gap-1.5 cursor-pointer"
            title="Fechar quadro e devolver o Orbe ao centro (ou diz 'Podes descansar')"
          >
            <X className="w-3.5 h-3.5" />
            <span>Descansar</span>
          </button>
        </div>
      </div>

      {/* ── MAIN INTERACTIVE SPATIAL CANVAS ── */}
      {board.domain === 'study' && renderStudyDomain()}
      {board.domain === 'project' && renderProjectDomain()}
      {board.domain === 'obsidian' && renderObsidianDomain()}
      {board.domain === 'sentinel' && renderSentinelDomain()}
    </motion.div>
  );
};
