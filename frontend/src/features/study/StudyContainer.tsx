import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Library,
  BookOpen,
  FileText,
  Bookmark,
  HelpCircle,
  Layers,
  Brain,
  Activity,
  Sparkles,
  Home,
  Mic,
  ChevronDown,
  Search,
} from 'lucide-react';
import { StudyLandingView } from './StudyLandingView';
import { StudyLibraryView } from './StudyLibraryView';
import { StudyReaderView } from './StudyReaderView';
import { StudyVideoReaderView } from './StudyVideoReaderView';
import { StudySummaryView } from './StudySummaryView';
import { StudyNotesView } from './StudyNotesView';
import { StudyQuizView } from './StudyQuizView';
import { StudyFlashcardsView } from './StudyFlashcardsView';
import { StudyActiveRecallView } from './StudyActiveRecallView';
import { StudyAdaptiveHubView } from './StudyAdaptiveHubView';
import { StudyGeneratedDocumentView } from './StudyGeneratedDocumentView';
import { LecturesPanel } from '../lectures/LecturesPanel';
import {
  getCurrentSessionItem,
  isSessionAllItemsCompleted,
  resolveTabForSessionItem,
} from './dailyReviewSession';
import type {
  StudyDocument,
  StudyReadingNote,
  StudyHighlight,
  ExplanationLevel,
  SummaryMode,
  StudyQuiz,
  QuizEvaluationResult,
  CornellNotesData,
  StudyCollection,
  EditorialStudyPlan,
  EditorialPlanStatus,
  StudyDocumentGenerationStatus,
  StudyDocumentGenerationResult,
  StudyDocumentFilePayload,
  StudyModesBridge,
  StudySessionState,
} from './types';

import type {
  StudyNavigatePayload,
  StudyUiContextPayload,
} from '../../protocol/websocket';

export type StudyTab =
  | 'overview'
  | 'library'
  | 'reader'
  | 'generated_doc'
  | 'summary'
  | 'notes'
  | 'flashcards'
  | 'active_recall'
  | 'quiz'
  | 'adaptive'
  | 'lectures'
  | 'knowledge';

export interface StudyUploadPayload {
  filename: string;
  file_path?: string;
  content_base64?: string;
  content_text?: string;
  video_url?: string;
  collection_id?: string;
  subject?: string;
  source_type?: string;
  title?: string;
}

interface StudyContainerProps {
  documents?: StudyDocument[];
  initialActiveDocumentId?: string;
  notes?: Array<{ filename: string; content?: string }>;
  isRecording?: boolean;
  onStartRecording?: () => void;
  onStopRecording?: () => void;
  onUploadDocument?: (payload: StudyUploadPayload) => Promise<void> | void;
  onTranslate?: (text: string, docId?: string) => Promise<string>;
  onExplain?: (
    text: string,
    level: ExplanationLevel,
    docId?: string
  ) => Promise<{ literal: string; simple: string; context_importance: string }>;
  onSummarizeSection?: (sectionId: string, docId?: string) => Promise<{
    main_idea: string;
    key_points: string[];
    terms: string[];
    doubts: string[];
  }>;
  onExplainMedia?: (mediaId: string, docId?: string) => Promise<string>;
  onAskPaper?: (query: string, docId?: string) => Promise<{ answer: string; sources: string[] }>;
  onGetDocumentFile?: (docId: string) => Promise<{ contentBase64?: string; filename?: string; error?: string }>;
  onGenerateSummary?: (documentId: string, mode: SummaryMode, forceRegenerate?: boolean) => Promise<any>;
  onCancelGeneration?: (documentId: string) => void;
  pipelineStage?: string;
  lastDocumentError?: { filename: string; error: string; ts: number } | null;
  onSynthesizeDocuments?: (documentIds: string[]) => Promise<{
    common_points: string[];
    differences: string[];
    shared_concepts: string[];
    contradictions: string[];
    idea_evolution: string[];
  }>;
  onSaveToVault?: (data: {
    title: string;
    markdown_content: string;
    source_document_ids: string[];
    source_hash: string;
  }) => Promise<boolean>;
  activeStudyQuiz?: StudyQuiz | null;
  studyQuizResult?: QuizEvaluationResult | null;
  onGenerateQuiz?: (documentId: string, count: number) => Promise<StudyQuiz>;
  onSubmitQuiz?: (
    quizId: string,
    answers: Record<string, number | string>,
    transferAnswer: string
  ) => Promise<QuizEvaluationResult>;
  onReviewFlashcard?: (cardId: string, rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void;
  onPrepareForExam?: (documentId: string) => Promise<void>;
  onGenerateCornell?: (documentId: string) => Promise<CornellNotesData>;
  onSearchRag?: (query: string, docId?: string) => Promise<Array<{ text: string; source: string; score?: number; title?: string }>>;
  onReadNote?: (filename: string) => Promise<string>;
  onSaveNoteToObsidian?: (filename: string, content: string) => void;
  onRefreshDocuments?: () => void;
  onDeleteDocument?: (docId: string) => Promise<boolean> | void;
  collections?: StudyCollection[];
  onRefreshCollections?: () => void;
  onCreateCollection?: (name: string, subject?: string) => Promise<any> | void;
  onLinkFolder?: (collectionId: string, folderPath: string, syncEnabled?: boolean, recursive?: boolean) => Promise<any>;
  onUnlinkFolder?: (collectionId: string, folderPath: string, removeMaterials?: boolean) => Promise<any>;
  onSyncFolder?: (collectionId: string, folderPath?: string) => Promise<any>;
  onAskCourse?: (collectionId: string, question: string) => Promise<{ answer: string; citations: string[]; sources: string[] }>;
  onRetryDocument?: (documentId: string) => Promise<any>;
  onGetEditorialPlan?: (documentId: string) => Promise<{
    plan: EditorialStudyPlan | null;
    plan_status: EditorialPlanStatus | null;
  }>;
  onGenerateEditorialPlan?: (
    documentId: string,
    forceRecompute?: boolean,
    autoGenerateDossier?: boolean
  ) => Promise<{
    plan: EditorialStudyPlan | null;
    plan_status: EditorialPlanStatus | null;
  }>;
  onGetGeneratedDocumentStatus?: (documentId: string) => Promise<StudyDocumentGenerationStatus | null>;
  onGenerateStudyDocument?: (
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
  onGetGeneratedDocumentFile?: (
    documentId: string,
    format?: 'pdf' | 'docx',
    version?: number
  ) => Promise<StudyDocumentFilePayload | null>;
  studyModesApi?: StudyModesBridge;
  externalNavigationTarget?: (StudyNavigatePayload & { nonce?: number }) | null;
  onStudyContextChange?: (ctx: StudyUiContextPayload) => void;
  onActiveDocumentChange?: (docId: string | null) => void;
  onActiveTabChange?: (tab: StudyTab) => void;
  readingNotesByDoc?: Record<string, StudyReadingNote[]>;
  highlightsByDoc?: Record<string, StudyHighlight[]>;
  onRequestDocumentDetails?: (docId: string) => void;
  onAddReadingNote?: (docId: string, page: number, note: string, selection?: string, sectionId?: string) => void;
  onAddHighlight?: (docId: string, page: number, selectedText: string, context?: string, color?: string) => void;
}

export const StudyContainer: React.FC<StudyContainerProps> = ({
  documents: initialDocuments = [],
  initialActiveDocumentId,
  notes: _notes = [],
  isRecording = false,
  activeStudyQuiz,
  studyQuizResult,
  onStartRecording,
  onStopRecording,
  onUploadDocument,
  onTranslate,
  onExplain,
  onSummarizeSection,
  onExplainMedia,
  onAskPaper,
  onGenerateSummary,
  onCancelGeneration,
  pipelineStage,
  lastDocumentError,
  onSynthesizeDocuments,
  onSaveToVault,
  onGenerateQuiz,
  onSubmitQuiz,
  onReviewFlashcard,
  onPrepareForExam,
  onGenerateCornell,
  onSearchRag,
  onReadNote: _onReadNote,
  onSaveNoteToObsidian: _onSaveNoteToObsidian,
  onRefreshDocuments,
  onGetDocumentFile,
  onDeleteDocument,
  collections = [],
  onRefreshCollections,
  onCreateCollection,
  onLinkFolder,
  onUnlinkFolder,
  onSyncFolder,
  onAskCourse,
  onRetryDocument,
  onGetEditorialPlan,
  onGenerateEditorialPlan,
  onGetGeneratedDocumentStatus,
  onGenerateStudyDocument,
  onGetGeneratedDocumentFile,
  studyModesApi,
  externalNavigationTarget,
  onStudyContextChange,
  onActiveDocumentChange,
  onActiveTabChange,
  readingNotesByDoc,
  highlightsByDoc,
  onRequestDocumentDetails,
  onAddReadingNote,
  onAddHighlight,
}) => {
  // Navigation — PDF/Video-first when an active or initial document exists, otherwise Landing Overview
  const [activeTab, setActiveTab] = useState<StudyTab>(
    initialActiveDocumentId || initialDocuments.length > 0 ? 'reader' : 'overview'
  );
  const [practiceMenuOpen, setPracticeMenuOpen] = useState<boolean>(false);
  const practiceMenuRef = useRef<HTMLDivElement | null>(null);
  const [ragQuickQuery, setRagQuickQuery] = useState<string>('');
  const [ragQuickResults, setRagQuickResults] = useState<Array<{ text: string; source: string; score?: number; title?: string }>>([]);
  const [ragSearching, setRagSearching] = useState<boolean>(false);
  const [topicFilterHint, setTopicFilterHint] = useState<string>('');
  const [activeDailySession, setActiveDailySession] = useState<StudySessionState | null>(null);
  const [documents, setDocuments] = useState<StudyDocument[]>(initialDocuments);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    initialActiveDocumentId || (initialDocuments[0]?.document_id ?? null)
  );
  const prevInitialDocIdRef = React.useRef<string | undefined>(initialActiveDocumentId);

  useEffect(() => {
    if (!practiceMenuOpen) return;
    const handleOutside = (event: MouseEvent) => {
      if (practiceMenuRef.current && !practiceMenuRef.current.contains(event.target as Node)) {
        setPracticeMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', handleOutside);
    return () => window.removeEventListener('mousedown', handleOutside);
  }, [practiceMenuOpen]);

  useEffect(() => {
    if (activeDocumentId && onRequestDocumentDetails) {
      onRequestDocumentDetails(activeDocumentId);
    }
  }, [activeDocumentId, onRequestDocumentDetails]);

  useEffect(() => {
    if (
      initialActiveDocumentId &&
      initialActiveDocumentId !== prevInitialDocIdRef.current
    ) {
      prevInitialDocIdRef.current = initialActiveDocumentId;
      setActiveDocumentId(initialActiveDocumentId);
    }
  }, [initialActiveDocumentId]);

  useEffect(() => {
    onActiveDocumentChange?.(activeDocumentId);
  }, [activeDocumentId, onActiveDocumentChange]);

  useEffect(() => {
    onActiveTabChange?.(activeTab);
  }, [activeTab, onActiveTabChange]);

  // Reset active mixed daily session when switching document
  useEffect(() => {
    setActiveDailySession((prev) =>
      prev && prev.document_id === activeDocumentId ? prev : null
    );
  }, [activeDocumentId]);

  const handleStartOrResumeDailySession = useCallback((session: StudySessionState) => {
    setActiveDailySession(session);
    const curItem = getCurrentSessionItem(session);
    const targetTab = resolveTabForSessionItem(curItem, session.mode);
    setTopicFilterHint('');
    setActiveTab(targetTab);
  }, []);

  const handleDailySessionUpdated = useCallback(
    async (session: StudySessionState, options?: { navigateNext?: boolean }) => {
      const shouldNavigate = options?.navigateNext !== false;
      if (isSessionAllItemsCompleted(session) && shouldNavigate) {
        if (studyModesApi && session.status !== 'COMPLETED') {
          await studyModesApi.completeSession(session.session_id);
        }
        setActiveDailySession(null);
        setActiveTab('adaptive');
        return;
      }
      setActiveDailySession(session);
      if (shouldNavigate) {
        const nextItem = getCurrentSessionItem(session);
        const targetTab = resolveTabForSessionItem(nextItem, session.mode);
        setTopicFilterHint('');
        setActiveTab(targetTab);
      }
    },
    [studyModesApi]
  );

  const handlePauseDailySession = useCallback(
    async (draft?: { itemId: string; response: string }) => {
      if (!activeDailySession || !studyModesApi) return;
      if (draft?.itemId && draft.response.trim()) {
        await studyModesApi.updateSession(activeDailySession.session_id, {
          item_id: draft.itemId,
          partial_response: draft.response,
          mark_completed: false,
        });
      }
      await studyModesApi.pauseSession(activeDailySession.session_id);
      setActiveDailySession(null);
      setActiveTab('adaptive');
    },
    [activeDailySession, studyModesApi]
  );

  const handleCompleteDailySession = useCallback(async () => {
    if (!activeDailySession || !studyModesApi) return;
    await studyModesApi.completeSession(activeDailySession.session_id);
    setActiveDailySession(null);
    setActiveTab('adaptive');
  }, [activeDailySession, studyModesApi]);

  // Upload progress state
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  // Report light active study context to JARVIS chat orchestration
  useEffect(() => {
    if (!onStudyContextChange) return;
    onStudyContextChange({
      document_id: activeDocumentId,
      tab: activeTab,
      session_id: activeDailySession?.session_id || null,
    });
  }, [activeDocumentId, activeTab, activeDailySession?.session_id, onStudyContextChange]);

  // Apply external validated deep-link navigation from JARVIS conversation
  const lastHandledNavNonceRef = React.useRef<number | undefined>(undefined);
  const retriedNavNonceRef = React.useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!externalNavigationTarget) return;
    const navNonce = externalNavigationTarget.nonce;
    if (navNonce !== undefined && lastHandledNavNonceRef.current === navNonce) return;

    const validTabs = new Set<StudyTab>([
      'overview',
      'library',
      'reader',
      'generated_doc',
      'summary',
      'notes',
      'flashcards',
      'active_recall',
      'quiz',
      'adaptive',
      'lectures',
      'knowledge',
    ]);
    const rawRequested = externalNavigationTarget.tab === 'home' ? 'overview' : externalNavigationTarget.tab;
    const requestedTab: StudyTab = validTabs.has(rawRequested as StudyTab)
      ? (rawRequested as StudyTab)
      : 'overview';

    const targetDocId = externalNavigationTarget.document_id;
    if (targetDocId) {
      const exists = documents.some((d) => d.document_id === targetDocId);
      if (exists) {
        setActiveDocumentId(targetDocId);
      } else {
        setTopicFilterHint('');
        setActiveTab('library');
        if (retriedNavNonceRef.current !== navNonce) {
          retriedNavNonceRef.current = navNonce;
          onRefreshDocuments?.();
          return;
        }
        lastHandledNavNonceRef.current = navNonce;
        return;
      }
    }
    lastHandledNavNonceRef.current = navNonce;

    if (externalNavigationTarget.topic) {
      setTopicFilterHint(externalNavigationTarget.topic);
    } else {
      setTopicFilterHint('');
    }

    if (externalNavigationTarget.session_id && studyModesApi && targetDocId) {
      let cancelled = false;
      studyModesApi
        .listSessions(targetDocId)
        .then((res) => {
          if (cancelled) return;
          const sessions = Array.isArray(res) ? res : [];
          const found = sessions.find(
            (s) => s.session_id === externalNavigationTarget.session_id
          );
          if (found) {
            handleStartOrResumeDailySession(found);
            return;
          }
          setActiveTab(requestedTab);
        })
        .catch(() => {
          if (!cancelled) setActiveTab(requestedTab);
        });
      return () => {
        cancelled = true;
      };
    }

    setActiveTab(requestedTab);
  }, [
    externalNavigationTarget,
    documents,
    studyModesApi,
    onRefreshDocuments,
    handleStartOrResumeDailySession,
  ]);

  // Synced documents prop
  useEffect(() => {
    if (initialDocuments) {
      setDocuments(initialDocuments);
      setActiveDocumentId((current) => current || initialDocuments[0]?.document_id || null);
      setIsUploading(false);
      setUploadStatus('');
    }
  }, [initialDocuments]);

  useEffect(() => {
    if (!lastDocumentError) return;
    setIsUploading(false);
    setUploadStatus(
      `Erro: ${lastDocumentError.error || `Falha ao processar ${lastDocumentError.filename}`}`
    );
  }, [lastDocumentError]);

  // Reading Notes & Highlights state (persisted backend records + optimistic local additions)
  const [localReadingNotes, setLocalReadingNotes] = useState<StudyReadingNote[]>([]);
  const [localHighlights, setLocalHighlights] = useState<StudyHighlight[]>([]);

  const readingNotes = useMemo(() => {
    const persisted = activeDocumentId ? readingNotesByDoc?.[activeDocumentId] ?? [] : [];
    const seen = new Set(persisted.map((n) => `${n.page}:${n.note}`));
    const extras = localReadingNotes.filter(
      (n) => (!activeDocumentId || n.document_id === activeDocumentId) && !seen.has(`${n.page}:${n.note}`)
    );
    return [...persisted, ...extras];
  }, [activeDocumentId, localReadingNotes, readingNotesByDoc]);

  const highlights = useMemo(() => {
    const persisted = activeDocumentId ? highlightsByDoc?.[activeDocumentId] ?? [] : [];
    const seen = new Set(persisted.map((h) => `${h.page}:${h.selected_text}`));
    const extras = localHighlights.filter(
      (h) => (!activeDocumentId || h.document_id === activeDocumentId) && !seen.has(`${h.page}:${h.selected_text}`)
    );
    return [...persisted, ...extras];
  }, [activeDocumentId, highlightsByDoc, localHighlights]);

  // Find active document
  const activeDocument = documents.find((d) => d.document_id === activeDocumentId) || null;

  // Handler: Select Document from Library
  const handleSelectDocument = useCallback((doc: StudyDocument) => {
    setActiveDocumentId(doc.document_id);
    setActiveTab('reader');
  }, []);

  const handleDeleteDocument = useCallback(
    async (docId: string) => {
      if (activeDocumentId === docId) {
        setActiveDocumentId(null);
        setActiveTab('library');
      }
      setDocuments((prev) => prev.filter((d) => d.document_id !== docId));
      if (onDeleteDocument) {
        await onDeleteDocument(docId);
      }
    },
    [activeDocumentId, onDeleteDocument]
  );

  // Handler: Update progress (stabilized with no-op check to prevent infinite re-renders)
  const handleUpdateProgress = useCallback((page: number, section: string, percent: number) => {
    setActiveDocumentId((currentDocId) => {
      if (!currentDocId) return currentDocId;
      setDocuments((prev) => {
        const target = prev.find((d) => d.document_id === currentDocId);
        if (
          target &&
          target.reading_progress?.current_page === page &&
          target.reading_progress?.current_section === section &&
          target.reading_progress?.progress_percent === percent
        ) {
          return prev;
        }
        return prev.map((d) => {
          if (d.document_id === currentDocId) {
            return {
              ...d,
              reading_progress: {
                ...d.reading_progress,
                current_page: page,
                current_section: section,
                progress_percent: percent,
                last_read_at: new Date().toISOString(),
              },
            };
          }
          return d;
        });
      });
      return currentDocId;
    });
  }, []);

  // Handler: Save Highlight
  const handleSaveHighlight = (page: number, text: string, color?: string) => {
    if (!activeDocumentId) return;
    const newHighlight: StudyHighlight = {
      highlight_id: `hl-${Date.now()}`,
      document_id: activeDocumentId,
      page,
      selected_text: text,
      color: color || '#fef08a',
      created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
    };
    setLocalHighlights((prev) => [newHighlight, ...prev]);
    onAddHighlight?.(activeDocumentId, page, text, undefined, color);
  };

  // Handler: Save Note
  const handleSaveNote = (page: number, text: string, note: string) => {
    if (!activeDocumentId) return;
    const newNote: StudyReadingNote = {
      note_id: `note-${Date.now()}`,
      document_id: activeDocumentId,
      page,
      selection: text,
      note,
      created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
    };
    setLocalReadingNotes((prev) => [newNote, ...prev]);
    onAddReadingNote?.(activeDocumentId, page, note, text);
  };

  // Handler: Delete Note
  const handleDeleteNote = (noteId: string) => {
    setLocalReadingNotes((prev) => prev.filter((n) => n.note_id !== noteId));
  };

  const handleDropUploadFiles = useCallback(
    async (fileList: FileList) => {
      if (!onUploadDocument || !fileList?.length) return;
      for (const file of Array.from(fileList)) {
        const nativePath = (window as any)?.jarvisIPC?.getPathForFile?.(file) || '';
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        const inferredType =
          ext === 'mp4' || ext === 'mkv' || ext === 'mov' || ext === 'webm' || ext === 'avi'
            ? 'VIDEO'
            : ext === 'pdf'
            ? 'PDF'
            : ext === 'pptx' || ext === 'ppt'
            ? 'SLIDES'
            : 'TEXT';
        setIsUploading(true);
        setUploadStatus(`A processar ${file.name}...`);
        if (nativePath) {
          await onUploadDocument({
            filename: file.name,
            file_path: nativePath,
            subject: 'Estudos',
            source_type: inferredType,
          });
        } else {
          const base64 = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const raw = String(reader.result || '');
              const idx = raw.indexOf(',');
              resolve(idx >= 0 ? raw.slice(idx + 1) : raw);
            };
            reader.onerror = () => reject(new Error(`Falha ao ler ${file.name}`));
            reader.readAsDataURL(file);
          });
          await onUploadDocument({
            filename: file.name,
            content_base64: base64,
            subject: 'Estudos',
            source_type: inferredType,
          });
        }
      }
      setActiveTab('library');
    },
    [onUploadDocument]
  );

  // Handler: Stabilized document file fetcher
  const handleGetDocumentFile = useCallback(() => {
    if (onGetDocumentFile && activeDocumentId) {
      return onGetDocumentFile(activeDocumentId);
    }
    return Promise.resolve({ error: 'Nenhum documento ativo' });
  }, [onGetDocumentFile, activeDocumentId]);

  const isPracticeTabActive =
    activeTab === 'notes' ||
    activeTab === 'flashcards' ||
    activeTab === 'active_recall' ||
    activeTab === 'quiz' ||
    activeTab === 'adaptive' ||
    activeTab === 'lectures';

  const practiceTabLabel: Record<string, string> = {
    notes: 'Notas Cornell',
    flashcards: 'Flashcards',
    active_recall: 'Recordação',
    quiz: 'Avaliações',
    adaptive: 'Progresso',
    lectures: 'Gravar Aula',
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#080c12] text-slate-200">
      {/* ============================================================ */}
      {/* TOP NAVIGATION BAR: STREAMLINED WORKFLOW + PRACTICE GROUP    */}
      {/* ============================================================ */}
      <header className="relative z-20 flex flex-wrap items-center justify-between gap-2.5 border-b border-slate-800/80 bg-[#0b111a]/95 px-4 py-2 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          {documents.length > 0 ? (
            <select
              aria-label="Selecionar documento de estudo ativo"
              data-testid="study-document-switcher"
              value={activeDocumentId || ''}
              onChange={(e) => {
                const nextId = e.target.value;
                if (nextId) {
                  setActiveDocumentId(nextId);
                  if (activeTab === 'library' || activeTab === 'overview') {
                    setActiveTab('reader');
                  }
                }
              }}
              className="max-w-[230px] sm:max-w-xs md:max-w-sm rounded-md border border-slate-700/70 bg-[#0f1722] px-2.5 py-1 text-xs font-semibold text-white outline-none hover:border-sky-400/50 focus:border-sky-400/60 cursor-pointer"
            >
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  [{doc.source_type}] {doc.title}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs font-medium text-slate-400">Biblioteca vazia</span>
          )}

          {activeDocument?.language?.toLowerCase() === 'en' && (
            <span className="rounded bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium text-sky-300 border border-sky-400/20">
              EN
            </span>
          )}
        </div>

        {/* Streamlined Study Navigation Tabs */}
        <nav
          aria-label="Navegação do módulo de estudo"
          className="flex flex-wrap items-center gap-1 rounded-lg border border-slate-800/90 bg-[#070b11] p-0.5 text-[11px]"
        >
          <button
            id="study-nav-overview-btn"
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Home className="h-3.5 w-3.5" />
            <span>Início</span>
          </button>

          <button
            id="study-nav-library-btn"
            type="button"
            onClick={() => {
              setActiveTab('library');
              if (onRefreshDocuments) onRefreshDocuments();
            }}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
              activeTab === 'library'
                ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Library className="h-3.5 w-3.5" />
            <span>Biblioteca</span>
          </button>

          <button
            id="study-nav-reader-btn"
            type="button"
            onClick={() => setActiveTab('reader')}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
              activeTab === 'reader'
                ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Leitura</span>
          </button>

          <button
            id="study-nav-generated-doc-btn"
            type="button"
            onClick={() => setActiveTab('generated_doc')}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
              activeTab === 'generated_doc'
                ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Documento de Estudo Estruturado (Qwen 3.5)"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Documento IA</span>
          </button>

          <button
            id="study-nav-summary-btn"
            type="button"
            onClick={() => setActiveTab('summary')}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
              activeTab === 'summary'
                ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Síntese</span>
          </button>

          <span className="mx-0.5 h-4 w-px bg-slate-800" aria-hidden="true" />

          {/* Purpose-Grouped Practice Menu */}
          <div className="relative" ref={practiceMenuRef}>
            <button
              id="study-nav-practice-btn"
              data-testid="study-nav-practice-btn"
              type="button"
              onClick={() => setPracticeMenuOpen((v) => !v)}
              aria-expanded={practiceMenuOpen}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition cursor-pointer ${
                isPracticeTabActive
                  ? 'bg-sky-500/20 text-sky-200 font-semibold shadow-sm'
                  : 'text-slate-300 hover:bg-white/[0.04] hover:text-white'
              }`}
            >
              <Brain className="h-3.5 w-3.5" />
              <span>{isPracticeTabActive ? practiceTabLabel[activeTab] || 'Praticar' : 'Praticar'}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>

            {practiceMenuOpen && (
              <div
                data-testid="study-practice-dropdown"
                className="absolute right-0 top-full mt-1.5 w-60 rounded-xl border border-slate-700/80 bg-[#0d141f] p-2 shadow-2xl z-40"
              >
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Estudar
                </div>
                <button
                  id="study-nav-notes-btn"
                  type="button"
                  onClick={() => {
                    setActiveTab('notes');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'notes' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <Bookmark className="h-3.5 w-3.5 text-sky-400" />
                  <span>Notas Cornell</span>
                </button>
                <button
                  id="study-nav-flashcards-btn"
                  type="button"
                  onClick={() => {
                    setTopicFilterHint('');
                    setActiveTab('flashcards');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'flashcards' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <Layers className="h-3.5 w-3.5 text-sky-400" />
                  <span>Flashcards</span>
                </button>
                <button
                  id="study-nav-recall-btn"
                  type="button"
                  onClick={() => {
                    setActiveTab('active_recall');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'active_recall' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <Brain className="h-3.5 w-3.5 text-sky-400" />
                  <span>Recordação Ativa</span>
                </button>

                <div className="my-1.5 border-t border-slate-800/80" />
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Avaliar
                </div>
                <button
                  id="study-nav-quiz-btn"
                  type="button"
                  onClick={() => {
                    setTopicFilterHint('');
                    setActiveTab('quiz');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'quiz' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <HelpCircle className="h-3.5 w-3.5 text-amber-400" />
                  <span>Avaliações & Quizzes</span>
                </button>
                <button
                  id="study-nav-adaptive-btn"
                  type="button"
                  onClick={() => {
                    setActiveTab('adaptive');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'adaptive' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <Activity className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Progresso & Plano Diário</span>
                </button>

                <div className="my-1.5 border-t border-slate-800/80" />
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Criar & Registar
                </div>
                <button
                  id="study-nav-lectures-btn"
                  type="button"
                  onClick={() => {
                    setActiveTab('lectures');
                    setPracticeMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition cursor-pointer ${
                    activeTab === 'lectures' ? 'bg-sky-500/15 text-sky-200 font-semibold' : 'text-slate-300 hover:bg-white/[0.05]'
                  }`}
                >
                  <Mic className="h-3.5 w-3.5 text-rose-400" />
                  <span>Gravar Aula & Lição</span>
                </button>
              </div>
            )}
          </div>
        </nav>
      </header>

      {/* ============================================================ */}
      {/* ACTIVE TAB VIEWPORT                                          */}
      {/* ============================================================ */}
      <main className="flex-1 overflow-hidden min-h-0">
        {activeTab === 'overview' && (
          <StudyLandingView
            documents={documents}
            collections={collections}
            activeDocument={activeDocument}
            onSelectDocument={(doc, targetTab) => {
              setActiveDocumentId(doc.document_id);
              setActiveTab(targetTab || 'reader');
            }}
            onNavigateTab={(tab) => setActiveTab(tab)}
            onDropFiles={handleDropUploadFiles}
          />
        )}

        {activeTab === 'library' && (
          <StudyLibraryView
            documents={documents}
            onOpenDocument={(docId, initialTab) => {
              const doc = documents.find((d) => d.document_id === docId);
              if (doc) handleSelectDocument(doc);
              if (initialTab) setActiveTab(initialTab);
            }}
            onUpload={async (payload) => {
              setIsUploading(true);
              setUploadStatus(`A processar ${payload.filename}...`);
              if (onUploadDocument) {
                try {
                  await onUploadDocument(payload);
                } catch (err: any) {
                  setIsUploading(false);
                  setUploadStatus(`Erro: ${err?.message || 'Falha ao processar'}`);
                }
              }
              // Timeout de segurança: resetar estado de upload se não houver resposta em 60s
              setTimeout(() => {
                setIsUploading((prev) => {
                  if (prev) {
                    setUploadStatus('');
                    return false;
                  }
                  return prev;
                });
              }, 60000);
            }}
            isUploading={isUploading}
            uploadStatus={uploadStatus}
            onStartLectureRecording={onStartRecording}
            isRecording={isRecording}
            onStopRecording={onStopRecording}
            onRefresh={onRefreshDocuments}
            onDeleteDocument={handleDeleteDocument}
            collections={collections}
            onRefreshCollections={onRefreshCollections}
            onCreateCollection={onCreateCollection}
            onLinkFolder={onLinkFolder}
            onUnlinkFolder={onUnlinkFolder}
            onSyncFolder={onSyncFolder}
            onAskCourse={onAskCourse}
            onRetryDocument={onRetryDocument}
          />
        )}

        {activeTab === 'reader' && (
          activeDocument ? (
            activeDocument.source_type === 'VIDEO' ? (
              <StudyVideoReaderView
                key={activeDocument.document_id}
                document={activeDocument}
                documents={documents}
                onSelectDocument={(id) => setActiveDocumentId(id)}
                onOpenGeneratedDocument={() => setActiveTab('generated_doc')}
                onOpenSummary={() => setActiveTab('summary')}
                onRetryDocument={onRetryDocument}
                onUpdateProgress={handleUpdateProgress}
                onSaveHighlight={handleSaveHighlight}
                onSaveNote={handleSaveNote}
                readingNotes={readingNotes}
                highlights={highlights}
                onTranslate={onTranslate ? (text) => onTranslate(text, activeDocument.document_id) : undefined}
                onExplain={onExplain ? (text, level) => onExplain(text, level, activeDocument.document_id) : undefined}
              />
            ) : (
              <StudyReaderView
                key={activeDocument.document_id}
                document={activeDocument}
                documents={documents}
                onSelectDocument={(id) => setActiveDocumentId(id)}
                onOpenGeneratedDocument={() => setActiveTab('generated_doc')}
                onOpenSummary={() => setActiveTab('summary')}
                onUpdateProgress={handleUpdateProgress}
                onSaveHighlight={handleSaveHighlight}
                onSaveNote={handleSaveNote}
                readingNotes={readingNotes}
                highlights={highlights}
                onTranslate={onTranslate ? (text) => onTranslate(text, activeDocument.document_id) : undefined}
                onExplain={onExplain ? (text, level) => onExplain(text, level, activeDocument.document_id) : undefined}
                onSummarizeSection={onSummarizeSection ? (secId) => onSummarizeSection(secId, activeDocument.document_id) : undefined}
                onExplainMedia={onExplainMedia ? (mId) => onExplainMedia(mId, activeDocument.document_id) : undefined}
                onAskPaper={onAskPaper ? (q) => onAskPaper(q, activeDocument.document_id) : undefined}
                onGetDocumentFile={onGetDocumentFile ? handleGetDocumentFile : undefined}
              />
            )
          ) : (
            <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217]">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 mb-3 text-cyan-400">
                <BookOpen className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-white">Nenhum documento aberto no leitor</h3>
              <p className="mt-1 max-w-sm text-xs text-gray-400 mb-4">
                Começa por carregar um artigo, slides ou gravação na Biblioteca.
              </p>
              <button
                onClick={() => setActiveTab('library')}
                className="rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
              >
                Abrir Biblioteca
              </button>
            </div>
          )
        )}

        {activeTab === 'generated_doc' && (
          <div className="h-full overflow-y-auto bg-[#070b10] p-6">
            <div className="mx-auto max-w-5xl">
              {activeDocument ? (
                <StudyGeneratedDocumentView
                  document={activeDocument}
                  onGetGeneratedDocumentStatus={onGetGeneratedDocumentStatus}
                  onGenerateStudyDocument={onGenerateStudyDocument}
                  onGetGeneratedDocumentFile={onGetGeneratedDocumentFile}
                  onCancelGeneration={onCancelGeneration}
                  pipelineStage={pipelineStage}
                />
              ) : (
                <div className="rounded-xl border border-white/10 bg-[#0b1016] p-8 text-center text-xs text-zinc-400">
                  Seleciona um documento na Biblioteca ou no seletor superior para gerar e ler o Documento IA (Fase 5).
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'summary' && (
          <StudySummaryView
            document={activeDocument}
            allDocuments={documents}
            onGenerateSummary={onGenerateSummary}
            onCancelGeneration={onCancelGeneration}
            pipelineStage={pipelineStage}
            onSynthesizeDocuments={onSynthesizeDocuments}
            onGetEditorialPlan={onGetEditorialPlan}
            onGenerateEditorialPlan={onGenerateEditorialPlan}
            onGetGeneratedDocumentStatus={onGetGeneratedDocumentStatus}
            onGenerateStudyDocument={onGenerateStudyDocument}
            onGetGeneratedDocumentFile={onGetGeneratedDocumentFile}
            onOpenGeneratedDocument={() => setActiveTab('generated_doc')}
          />
        )}

        {activeTab === 'notes' && (
          <StudyNotesView
            document={activeDocument}
            readingNotes={readingNotes}
            highlights={highlights}
            studyModes={studyModesApi}
            onGoToSummary={() => setActiveTab('summary')}
            onSaveToVault={onSaveToVault}
            onDeleteNote={handleDeleteNote}
            onGenerateCornell={onGenerateCornell}
          />
        )}

        {activeTab === 'flashcards' && (
          <StudyFlashcardsView
            document={activeDocument}
            studyModes={studyModesApi}
            onGoToSummary={() => setActiveTab('summary')}
            initialFilterTopic={topicFilterHint}
            activeDailySession={activeDailySession}
            onDailySessionUpdated={handleDailySessionUpdated}
            onPauseDailySession={() => handlePauseDailySession()}
            onCompleteDailySession={handleCompleteDailySession}
          />
        )}

        {activeTab === 'active_recall' && (
          <StudyActiveRecallView
            document={activeDocument}
            studyModes={studyModesApi}
            onGoToSummary={() => setActiveTab('summary')}
            activeDailySession={activeDailySession}
            onDailySessionUpdated={handleDailySessionUpdated}
            onPauseDailySession={handlePauseDailySession}
            onCompleteDailySession={handleCompleteDailySession}
          />
        )}

        {activeTab === 'quiz' && (
          <StudyQuizView
            document={activeDocument}
            studyModes={studyModesApi}
            onGoToSummary={() => setActiveTab('summary')}
            initialTopicFilter={topicFilterHint}
            quiz={activeStudyQuiz?.document_id === activeDocument?.document_id ? activeStudyQuiz : null}
            evaluationResult={studyQuizResult}
            onGenerateQuiz={onGenerateQuiz}
            onSubmitQuiz={onSubmitQuiz}
            onReviewFlashcard={onReviewFlashcard}
            onPrepareForExam={onPrepareForExam}
          />
        )}

        {activeTab === 'adaptive' && (
          <StudyAdaptiveHubView
            document={activeDocument}
            studyModes={studyModesApi}
            onStartOrResumeSession={handleStartOrResumeDailySession}
            onNavigateTab={(tab, topicHint) => {
              setTopicFilterHint(topicHint || '');
              setActiveTab(tab);
            }}
          />
        )}

        {activeTab === 'lectures' && (
          <div className="h-full overflow-y-auto bg-[#080c12] p-5">
            <div className="mx-auto max-w-5xl">
              <LecturesPanel />
            </div>
          </div>
        )}

        {activeTab === 'knowledge' && (
          <div className="h-full overflow-y-auto bg-[#080c12] p-6">
            <div className="mx-auto max-w-3xl space-y-4">
              <div className="rounded-xl border border-slate-800 bg-[#0d141f] p-5">
                <h2 className="text-sm font-semibold text-white">Pesquisa Semântica RAG nos Materiais</h2>
                <p className="mt-1 text-xs text-slate-400">
                  O repositório Obsidian e o grafo de conhecimento ficam centralizados no domínio <strong className="text-slate-200">Obsidian</strong> da barra lateral esquerda. Aqui podes pesquisar rapidamente passagens no índice RAG de estudo.
                </p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!onSearchRag || !ragQuickQuery.trim()) return;
                    setRagSearching(true);
                    try {
                      const hits = await onSearchRag(ragQuickQuery.trim(), activeDocument?.document_id);
                      setRagQuickResults(Array.isArray(hits) ? hits : []);
                    } finally {
                      setRagSearching(false);
                    }
                  }}
                  className="mt-3 flex gap-2"
                >
                  <input
                    type="text"
                    value={ragQuickQuery}
                    onChange={(e) => setRagQuickQuery(e.target.value)}
                    placeholder="Pesquisar conceitos ou citações nos documentos indexados..."
                    className="flex-1 rounded-lg border border-slate-700 bg-[#080c12] px-3 py-2 text-xs text-white outline-none focus:border-sky-400/60"
                  />
                  <button
                    type="submit"
                    disabled={ragSearching || !ragQuickQuery.trim()}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50 cursor-pointer"
                  >
                    <Search className="h-3.5 w-3.5" />
                    <span>{ragSearching ? 'A pesquisar...' : 'Pesquisar RAG'}</span>
                  </button>
                </form>
              </div>
              {ragQuickResults.length > 0 && (
                <div className="space-y-2">
                  {ragQuickResults.map((hit, idx) => (
                    <div key={`${hit.source}-${idx}`} className="rounded-xl border border-slate-800 bg-[#0c121b] p-4 text-xs">
                      <div className="flex items-center justify-between text-[11px] text-sky-300 font-medium mb-1">
                        <span>{hit.title || hit.source}</span>
                        {hit.score !== undefined && <span>Relevância: {(hit.score * 100).toFixed(0)}%</span>}
                      </div>
                      <p className="text-slate-300 leading-relaxed">{hit.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
