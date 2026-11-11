import React, { useState, useEffect, useCallback } from 'react';
import {
  Library,
  BookOpen,
  FileText,
  Bookmark,
  HelpCircle,
  Database,
  ArrowLeft,
  Layers,
  Brain,
  Activity
} from 'lucide-react';
import { StudyLibraryView } from './StudyLibraryView';
import { StudyReaderView } from './StudyReaderView';
import { StudyVideoReaderView } from './StudyVideoReaderView';
import { StudySummaryView } from './StudySummaryView';
import { StudyNotesView } from './StudyNotesView';
import { StudyQuizView } from './StudyQuizView';
import { StudyKnowledgeView } from './StudyKnowledgeView';
import { StudyFlashcardsView } from './StudyFlashcardsView';
import { StudyActiveRecallView } from './StudyActiveRecallView';
import { StudyAdaptiveHubView } from './StudyAdaptiveHubView';
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
  | 'library'
  | 'reader'
  | 'summary'
  | 'notes'
  | 'flashcards'
  | 'active_recall'
  | 'quiz'
  | 'adaptive'
  | 'knowledge';

export interface StudyUploadPayload {
  filename: string;
  file_path?: string;
  content_base64?: string;
  content_text?: string;
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
}

export const StudyContainer: React.FC<StudyContainerProps> = ({
  documents: initialDocuments = [],
  initialActiveDocumentId,
  notes = [],
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
  onSynthesizeDocuments,
  onSaveToVault,
  onGenerateQuiz,
  onSubmitQuiz,
  onReviewFlashcard,
  onPrepareForExam,
  onGenerateCornell,
  onSearchRag,
  onReadNote,
  onSaveNoteToObsidian,
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
}) => {
  // Navigation
  const [activeTab, setActiveTab] = useState<StudyTab>('library');
  const [topicFilterHint, setTopicFilterHint] = useState<string>('');
  const [activeDailySession, setActiveDailySession] = useState<StudySessionState | null>(null);
  const [documents, setDocuments] = useState<StudyDocument[]>(initialDocuments);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    initialActiveDocumentId || (initialDocuments[0]?.document_id ?? null)
  );

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
  useEffect(() => {
    if (!externalNavigationTarget) return;
    const navNonce = externalNavigationTarget.nonce;
    if (navNonce !== undefined && lastHandledNavNonceRef.current === navNonce) return;
    lastHandledNavNonceRef.current = navNonce;

    const validTabs = new Set<StudyTab>([
      'library',
      'reader',
      'summary',
      'notes',
      'flashcards',
      'active_recall',
      'quiz',
      'adaptive',
      'knowledge',
    ]);
    const requestedTab: StudyTab = validTabs.has(externalNavigationTarget.tab as StudyTab)
      ? (externalNavigationTarget.tab as StudyTab)
      : 'library';

    const targetDocId = externalNavigationTarget.document_id;
    if (targetDocId) {
      const exists = documents.some((d) => d.document_id === targetDocId);
      if (exists) {
        setActiveDocumentId(targetDocId);
      } else {
        onRefreshDocuments?.();
        setTopicFilterHint('');
        setActiveTab('library');
        return;
      }
    }

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

  // Reading Notes & Highlights state
  const [readingNotes, setReadingNotes] = useState<StudyReadingNote[]>([]);
  const [highlights, setHighlights] = useState<StudyHighlight[]>([]);

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
    setHighlights((prev) => [newHighlight, ...prev]);
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
    setReadingNotes((prev) => [newNote, ...prev]);
  };

  // Handler: Delete Note
  const handleDeleteNote = (noteId: string) => {
    setReadingNotes((prev) => prev.filter((n) => n.note_id !== noteId));
  };

  // Handler: Stabilized document file fetcher
  const handleGetDocumentFile = useCallback(() => {
    if (onGetDocumentFile && activeDocumentId) {
      return onGetDocumentFile(activeDocumentId);
    }
    return Promise.resolve({ error: 'Nenhum documento ativo' });
  }, [onGetDocumentFile, activeDocumentId]);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0a0f14] text-gray-200">
      {/* ============================================================ */}
      {/* TOP NAVIGATION BAR: 6 STUDY AREAS                            */}
      {/* ============================================================ */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#0f171d]/95 px-6 py-2.5 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab('library')}
            className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 hover:text-cyan-300 transition"
            title="Voltar à Biblioteca"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Estudo</span>
          </button>

          {activeDocument && (
            <div className="flex items-center gap-2 border-l border-white/10 pl-3">
              <span className="text-[11px] text-gray-500 uppercase font-semibold">Artigo:</span>
              <span className="text-xs font-semibold text-white truncate max-w-[200px] sm:max-w-xs md:max-w-md">
                {activeDocument.title}
              </span>
              {activeDocument.language?.toLowerCase() === 'en' && (
                <span className="rounded bg-sky-400/10 px-1.5 py-0.2 text-[10px] font-medium text-sky-300 border border-sky-400/20">
                  EN
                </span>
              )}
            </div>
          )}
        </div>

        {/* The 6 Main Study Navigation Tabs */}
        <nav aria-label="Navegação do módulo de estudo" className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
          <button
            id="study-nav-library-btn"
            onClick={() => {
              setActiveTab('library');
              if (onRefreshDocuments) onRefreshDocuments();
            }}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'library'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Library className="h-3.5 w-3.5" />
            <span>Biblioteca</span>
          </button>

          <button
            id="study-nav-reader-btn"
            onClick={() => setActiveTab('reader')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'reader'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Leitura</span>
          </button>

          <button
            id="study-nav-summary-btn"
            onClick={() => setActiveTab('summary')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'summary'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Resumo</span>
          </button>

          <button
            id="study-nav-notes-btn"
            onClick={() => setActiveTab('notes')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'notes'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Bookmark className="h-3.5 w-3.5" />
            <span>Notas</span>
          </button>

          <button
            id="study-nav-flashcards-btn"
            onClick={() => {
              setTopicFilterHint('');
              setActiveTab('flashcards');
            }}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'flashcards'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Flashcards</span>
          </button>

          <button
            id="study-nav-recall-btn"
            onClick={() => setActiveTab('active_recall')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'active_recall'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Brain className="h-3.5 w-3.5" />
            <span>Recordação Ativa</span>
          </button>

          <button
            id="study-nav-quiz-btn"
            onClick={() => {
              setTopicFilterHint('');
              setActiveTab('quiz');
            }}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'quiz'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Avaliações</span>
          </button>

          <button
            id="study-nav-adaptive-btn"
            onClick={() => setActiveTab('adaptive')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'adaptive'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Progresso</span>
          </button>

          <button
            id="study-nav-knowledge-btn"
            onClick={() => setActiveTab('knowledge')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition ${
              activeTab === 'knowledge'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Database className="h-3.5 w-3.5" />
            <span>Conhecimento</span>
          </button>
        </nav>
      </header>

      {/* ============================================================ */}
      {/* ACTIVE TAB VIEWPORT                                          */}
      {/* ============================================================ */}
      <main className="flex-1 overflow-hidden min-h-0">
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
                document={activeDocument}
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
                document={activeDocument}
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

        {activeTab === 'knowledge' && (
          <StudyKnowledgeView
            document={activeDocument}
            notes={notes}
            onSearchRag={onSearchRag ? (q) => onSearchRag(q, activeDocument?.document_id) : undefined}
            onReadNote={onReadNote}
            onSaveNote={onSaveNoteToObsidian}
          />
        )}
      </main>
    </div>
  );
};
