import React, { useState, useRef, useMemo } from 'react';
import {
  BookOpen,
  FileText,
  Image as ImageIcon,
  Search,
  Plus,
  UploadCloud,
  Clock,
  Headphones,
  FileCode,
  Filter,
  FileUp,
  ArrowRight,
  RotateCw,
  X,
  Video,
  Link as LinkIcon,
  Trash2,
  Folder,
  FolderPlus,
  FolderSync,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
  ShieldCheck,
  Loader2,
  FolderX,
  LayoutList,
  LayoutGrid,
  Star,
  ArrowUpDown,
  CheckSquare,
  Square,
} from 'lucide-react';
import type { StudyDocument, SourceType, StudyCollection, StudyFolderLink } from './types';

interface StudyLibraryViewProps {
  documents: StudyDocument[];
  onOpenDocument: (docId: string, initialTab?: 'reader' | 'summary' | 'notes' | 'quiz') => void;
  onUpload: (payload: {
    filename: string;
    file_path?: string;
    content_base64?: string;
    content_text?: string;
    subject: string;
    source_type?: SourceType;
    title?: string;
    collection_id?: string;
    video_url?: string;
  }) => void;
  onRefresh?: () => void;
  onDeleteDocument?: (docId: string) => void;
  isUploading?: boolean;
  uploadStatus?: string;
  onStartLectureRecording?: () => void;
  isRecording?: boolean;
  onStopRecording?: () => void;
  // Collections and Folder Sync Props
  collections?: StudyCollection[];
  onRefreshCollections?: () => void;
  onCreateCollection?: (name: string, subject?: string) => Promise<any> | void;
  onLinkFolder?: (collectionId: string, folderPath: string, syncEnabled?: boolean, recursive?: boolean) => Promise<any>;
  onUnlinkFolder?: (collectionId: string, folderPath: string, removeMaterials?: boolean) => Promise<any>;
  onSyncFolder?: (collectionId: string, folderPath?: string) => Promise<any>;
  onAskCourse?: (collectionId: string, question: string) => Promise<{ answer: string; citations: string[]; sources: string[] }>;
  onRetryDocument?: (documentId: string) => Promise<any>;
}

export const StudyLibraryView: React.FC<StudyLibraryViewProps> = ({
  documents,
  onOpenDocument,
  onUpload,
  onRefresh,
  isUploading = false,
  uploadStatus = '',
  onStartLectureRecording,
  onDeleteDocument,
  collections = [],
  onRefreshCollections,
  onCreateCollection,
  onLinkFolder,
  onUnlinkFolder,
  onSyncFolder,
  onAskCourse,
  onRetryDocument,
}) => {
  // Course / Collection Selection State
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);

  // Filter, Sort, Layout & Facet State
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>(() => {
    try {
      const saved = localStorage.getItem('jarvis.study.library.view_mode');
      return saved === 'grid' ? 'grid' : 'list';
    } catch {
      return 'list';
    }
  });
  const [sortBy, setSortBy] = useState<'recent' | 'title' | 'type' | 'progress'>('recent');
  const [activeFacet, setActiveFacet] = useState<'ALL' | 'RECENT' | 'FAVORITES' | 'FOLDERS' | 'MEDIA'>('ALL');
  const [favoriteIds, setFavoriteIds] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('jarvis.study.library.favorites');
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [canvasDragActive, setCanvasDragActive] = useState<boolean>(false);

  const handleSetViewMode = (mode: 'list' | 'grid') => {
    setViewMode(mode);
    try {
      localStorage.setItem('jarvis.study.library.view_mode', mode);
    } catch {
      // Ignore storage write errors
    }
  };

  const toggleFavorite = (docId: string) => {
    setFavoriteIds((prev) => {
      const next = prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId];
      try {
        localStorage.setItem('jarvis.study.library.favorites', JSON.stringify(next));
      } catch {
        // Ignore storage write errors
      }
      return next;
    });
  };

  const toggleSelectDoc = (docId: string) => {
    setSelectedDocIds((prev) => (prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]));
  };

  const handleCanvasDropUpload = async (files: FileList) => {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      const nativePath = (window as any)?.jarvisIPC?.getPathForFile?.(file) || '';
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      const inferredType: SourceType =
        ext === 'mp4' || ext === 'mkv' || ext === 'mov' || ext === 'webm' || ext === 'avi'
          ? 'VIDEO'
          : ext === 'pdf'
          ? 'PDF'
          : ext === 'pptx' || ext === 'ppt'
          ? 'PPTX'
          : 'TXT';
      const subject = activeCollection?.subject || activeCollection?.name || 'Estudos';
      const colId = activeCollection?.collection_id;
      if (nativePath) {
        onUpload({
          filename: file.name,
          file_path: nativePath,
          subject,
          source_type: inferredType,
          collection_id: colId,
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
        onUpload({
          filename: file.name,
          content_base64: base64,
          subject,
          source_type: inferredType,
          collection_id: colId,
        });
      }
    }
  };

  // Modals
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [documentToDelete, setDocumentToDelete] = useState<StudyDocument | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // New Course Modal
  const [isCreateCourseModalOpen, setIsCreateCourseModalOpen] = useState<boolean>(false);
  const [newCourseName, setNewCourseName] = useState<string>('');
  const [newCourseSubject, setNewCourseSubject] = useState<string>('');
  const [isCreatingCourse, setIsCreatingCourse] = useState<boolean>(false);

  // Link Folder Modal
  const [isLinkFolderModalOpen, setIsLinkFolderModalOpen] = useState<boolean>(false);
  const [linkFolderPathInput, setLinkFolderPathInput] = useState<string>('');
  const [linkFolderRecursive, setLinkFolderRecursive] = useState<boolean>(true);
  const [isLinkingFolder, setIsLinkingFolder] = useState<boolean>(false);

  // Unlink Folder Modal
  const [folderToUnlink, setFolderToUnlink] = useState<StudyFolderLink | null>(null);
  const [isUnlinking, setIsUnlinking] = useState<boolean>(false);

  // Syncing state tracking
  const [syncingFolders, setSyncingFolders] = useState<Record<string, boolean>>({});
  const [retryingDocs, setRetryingDocs] = useState<Record<string, boolean>>({});

  // Course Q&A State
  const [isCourseQaModalOpen, setIsCourseQaModalOpen] = useState<boolean>(false);
  const [courseQaQuery, setCourseQaQuery] = useState<string>('');
  const [isCourseQaLoading, setIsCourseQaLoading] = useState<boolean>(false);
  const [courseQaResult, setCourseQaResult] = useState<{
    answer: string;
    citations: string[];
    sources: string[];
  } | null>(null);

  // Upload modal form state
  const [uploadSubject, setUploadSubject] = useState<string>('Inteligência Artificial');
  const [uploadTitle, setUploadTitle] = useState<string>('');
  const [uploadMode, setUploadMode] = useState<'file' | 'video' | 'video_url' | 'text' | 'lecture'>('file');
  const [videoUrlInput, setVideoUrlInput] = useState<string>('');
  const [rawTextContent, setRawTextContent] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active collection object
  const activeCollection = collections.find((c) => c.collection_id === selectedCollectionId) || null;

  // Filtered and sorted documents by collection, facet, search query, and type
  const filteredDocs = useMemo(() => {
    const filtered = documents.filter((doc) => {
      // 1. Collection filter
      if (selectedCollectionId && activeCollection) {
        const inDocIds = activeCollection.document_ids?.includes(doc.document_id);
        const matchesColId = (doc as any).collection_id === selectedCollectionId;
        const matchesSubject =
          doc.subject &&
          activeCollection.subject &&
          doc.subject.trim().toLowerCase() === activeCollection.subject.trim().toLowerCase();
        if (!inDocIds && !matchesColId && !matchesSubject) {
          return false;
        }
      }

      // 1b. Facet filter
      if (activeFacet === 'FAVORITES' && !favoriteIds.includes(doc.document_id)) {
        return false;
      }
      if (activeFacet === 'RECENT' && !(doc.reading_progress?.last_read_at || doc.reading_progress?.progress_percent)) {
        return false;
      }
      if (activeFacet === 'FOLDERS') {
        const origin = (doc as any).source_origin || doc.provenance?.source_origin || 'manual_upload';
        if (origin !== 'linked_folder') return false;
      }
      if (activeFacet === 'MEDIA' && !['VIDEO', 'AUDIO', 'IMAGE', 'LECTURE_AUDIO'].includes(doc.source_type)) {
        return false;
      }

      // 2. Search query filter
      const title = (doc.title || '').toLowerCase();
      const subject = (doc.subject || '').toLowerCase();
      const relPath = (doc.provenance?.rel_path || '').toLowerCase();
      const q = searchQuery.toLowerCase();
      const matchesSearch = title.includes(q) || subject.includes(q) || relPath.includes(q);
      if (!matchesSearch) return false;

      // 3. Type filter
      if (filterType === 'ALL') return true;
      if (filterType === 'DOCS') return ['PDF', 'DOCX', 'PPTX', 'TXT', 'MARKDOWN'].includes(doc.source_type);
      if (filterType === 'VIDEO') return doc.source_type === 'VIDEO';
      if (filterType === 'IMAGES') return doc.source_type === 'IMAGE';
      if (filterType === 'AUDIO') return doc.source_type === 'AUDIO';
      if (filterType === 'LECTURES') return doc.source_type === 'LECTURE_AUDIO';
      if (filterType === 'NOTES') return doc.source_type === 'NOTE';
      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === 'title') return (a.title || '').localeCompare(b.title || '', 'pt');
      if (sortBy === 'type') return (a.source_type || '').localeCompare(b.source_type || '');
      if (sortBy === 'progress') {
        return (b.reading_progress?.progress_percent || 0) - (a.reading_progress?.progress_percent || 0);
      }
      const aTime = a.reading_progress?.last_read_at || a.updated_at || a.created_at || '';
      const bTime = b.reading_progress?.last_read_at || b.updated_at || b.created_at || '';
      return String(bTime).localeCompare(String(aTime));
    });
  }, [activeCollection, activeFacet, documents, favoriteIds, filterType, searchQuery, selectedCollectionId, sortBy]);

  const recentDocsShelf = useMemo(() => {
    return [...documents]
      .sort((a, b) => {
        const aTime = a.reading_progress?.last_read_at || a.updated_at || a.created_at || '';
        const bTime = b.reading_progress?.last_read_at || b.updated_at || b.created_at || '';
        return String(bTime).localeCompare(String(aTime));
      })
      .slice(0, 3);
  }, [documents]);

  // Calculate count per collection
  const getCollectionDocCount = (col: StudyCollection) => {
    return documents.filter((doc) => {
      const inDocIds = col.document_ids?.includes(doc.document_id);
      const matchesColId = (doc as any).collection_id === col.collection_id;
      const matchesSubject =
        doc.subject && col.subject && doc.subject.trim().toLowerCase() === col.subject.trim().toLowerCase();
      return inDocIds || matchesColId || matchesSubject;
    }).length;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      if (!uploadTitle) {
        setUploadTitle(file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '));
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      if (!uploadTitle) {
        setUploadTitle(file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' '));
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleConfirmDelete = async () => {
    if (!documentToDelete) return;
    try {
      setIsDeleting(true);
      if (onDeleteDocument) {
        await onDeleteDocument(documentToDelete.document_id);
      }
    } finally {
      setIsDeleting(false);
      setDocumentToDelete(null);
    }
  };

  const handleCreateCourseSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newCourseName.trim();
    const subj = newCourseSubject.trim() || name;
    if (!name) return;

    try {
      setIsCreatingCourse(true);
      if (onCreateCollection) {
        await onCreateCollection(name, subj);
      }
      if (onRefreshCollections) {
        onRefreshCollections();
      }
      setIsCreateCourseModalOpen(false);
      setNewCourseName('');
      setNewCourseSubject('');
    } catch (err) {
      console.error('[Study] Error creating course:', err);
    } finally {
      setIsCreatingCourse(false);
    }
  };

  // Folder Linking Handlers
  const handleTriggerLinkFolder = async () => {
    if (!activeCollection) return;

    // Check if Electron native dialog is available
    if ((window as any).jarvisIPC?.selectFolder) {
      try {
        const folderPath = await (window as any).jarvisIPC.selectFolder();
        if (folderPath && typeof folderPath === 'string') {
          setIsLinkingFolder(true);
          if (onLinkFolder) {
            await onLinkFolder(activeCollection.collection_id, folderPath, true, true);
            if (onRefreshCollections) onRefreshCollections();
            if (onRefresh) onRefresh();
          }
          setIsLinkingFolder(false);
          return;
        }
      } catch (err) {
        console.warn('[Study] Native folder selection failed, opening fallback modal:', err);
      }
    }

    // Fallback: Open manual input modal
    setLinkFolderPathInput('');
    setIsLinkFolderModalOpen(true);
  };

  const handleManualLinkFolderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCollection || !linkFolderPathInput.trim()) return;

    try {
      setIsLinkingFolder(true);
      if (onLinkFolder) {
        await onLinkFolder(
          activeCollection.collection_id,
          linkFolderPathInput.trim(),
          true,
          linkFolderRecursive
        );
        if (onRefreshCollections) onRefreshCollections();
        if (onRefresh) onRefresh();
      }
      setIsLinkFolderModalOpen(false);
      setLinkFolderPathInput('');
    } catch (err) {
      console.error('[Study] Error linking folder manually:', err);
    } finally {
      setIsLinkingFolder(false);
    }
  };

  const handleUnlinkFolderConfirm = async () => {
    if (!activeCollection || !folderToUnlink) return;

    try {
      setIsUnlinking(true);
      if (onUnlinkFolder) {
        await onUnlinkFolder(activeCollection.collection_id, folderToUnlink.folder_path, false);
        if (onRefreshCollections) onRefreshCollections();
        if (onRefresh) onRefresh();
      }
      setFolderToUnlink(null);
    } catch (err) {
      console.error('[Study] Error unlinking folder:', err);
    } finally {
      setIsUnlinking(false);
    }
  };

  const handleSyncNow = async (folderPath: string) => {
    if (!activeCollection) return;
    setSyncingFolders((prev) => ({ ...prev, [folderPath]: true }));
    try {
      if (onSyncFolder) {
        await onSyncFolder(activeCollection.collection_id, folderPath);
        if (onRefreshCollections) onRefreshCollections();
        if (onRefresh) onRefresh();
      }
    } catch (err) {
      console.error('[Study] Sync failed:', err);
    } finally {
      setSyncingFolders((prev) => ({ ...prev, [folderPath]: false }));
    }
  };

  const handleOpenFolderOnDisk = (folderPath: string) => {
    if ((window as any).jarvisIPC?.openPath) {
      (window as any).jarvisIPC.openPath(folderPath);
    } else {
      alert(`Caminho local da pasta: ${folderPath}`);
    }
  };

  const handleRetryDoc = async (docId: string) => {
    setRetryingDocs((prev) => ({ ...prev, [docId]: true }));
    try {
      if (onRetryDocument) {
        await onRetryDocument(docId);
        if (onRefresh) onRefresh();
      }
    } catch (err) {
      console.error('[Study] Retry document failed:', err);
    } finally {
      setRetryingDocs((prev) => ({ ...prev, [docId]: false }));
    }
  };

  const handleCourseQaSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeCollection || !courseQaQuery.trim() || isCourseQaLoading) return;

    try {
      setIsCourseQaLoading(true);
      if (onAskCourse) {
        const res = await onAskCourse(activeCollection.collection_id, courseQaQuery.trim());
        setCourseQaResult(res);
      }
    } catch (err: any) {
      setCourseQaResult({
        answer: `Erro ao consultar a disciplina: ${err?.message || 'Falha na resposta'}`,
        citations: [],
        sources: [],
      });
    } finally {
      setIsCourseQaLoading(false);
    }
  };

  const handleSubmitUpload = () => {
    const finalSubject = activeCollection?.subject || uploadSubject || 'Geral';
    const finalCollectionId = activeCollection?.collection_id;

    if (uploadMode === 'lecture') {
      setIsUploadModalOpen(false);
      if (onStartLectureRecording) onStartLectureRecording();
      return;
    }

    if (uploadMode === 'video_url') {
      if (!videoUrlInput.trim()) return;
      const baseTitle = uploadTitle.trim() || 'Vídeo Online';
      onUpload({
        filename: videoUrlInput.trim(),
        content_text: videoUrlInput.trim(),
        video_url: videoUrlInput.trim(),
        subject: finalSubject,
        source_type: 'VIDEO',
        title: baseTitle,
        collection_id: finalCollectionId,
      });
      setIsUploadModalOpen(false);
      setVideoUrlInput('');
      setUploadTitle('');
      return;
    }

    if (uploadMode === 'text') {
      if (!rawTextContent.trim()) return;
      const baseTitle = uploadTitle.trim() || 'Nota de Estudo';
      const finalFilename = baseTitle.endsWith('.txt') ? baseTitle : `${baseTitle}.txt`;
      onUpload({
        filename: finalFilename,
        content_text: rawTextContent,
        subject: finalSubject,
        source_type: 'TXT',
        title: baseTitle,
        collection_id: finalCollectionId,
      });
      setIsUploadModalOpen(false);
      setRawTextContent('');
      setSelectedFile(null);
      setUploadTitle('');
      return;
    }

    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop()?.toLowerCase() || '';
    const isVideo = ['mp4', 'webm', 'mkv', 'mov', 'avi', 'wmv', 'm4v'].includes(ext);
    const isAudio = ['mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac', 'wma'].includes(ext);
    const detectedSourceType: SourceType | undefined = isVideo ? 'VIDEO' : isAudio ? 'AUDIO' : undefined;

    // Em ambiente Electron desktop, utilizar o caminho nativo diretamente
    const localFilePath =
      (window as any).jarvisIPC?.getPathForFile?.(selectedFile) ||
      (selectedFile as any).path ||
      '';

    if (localFilePath) {
      onUpload({
        filename: selectedFile.name,
        file_path: localFilePath,
        subject: finalSubject,
        source_type: detectedSourceType,
        title: uploadTitle || selectedFile.name,
        collection_id: finalCollectionId,
      });
      setIsUploadModalOpen(false);
      setSelectedFile(null);
      setUploadTitle('');
      return;
    }

    if (selectedFile.size > 25 * 1024 * 1024) {
      alert(
        `O ficheiro ${selectedFile.name} tem ${(selectedFile.size / (1024 * 1024)).toFixed(
          1
        )}MB. No navegador web, uploads base64 estão limitados a 25MB. Abre a aplicação JarvisOS Desktop para processamento local de ficheiros de grande porte.`
      );
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const resultStr = reader.result as string;
      const commaIdx = resultStr.indexOf(',');
      const b64 = commaIdx !== -1 ? resultStr.substring(commaIdx + 1).trim() : resultStr.trim();
      onUpload({
        filename: selectedFile.name,
        content_base64: b64,
        subject: finalSubject,
        source_type: detectedSourceType,
        title: uploadTitle || selectedFile.name,
        collection_id: finalCollectionId,
      });
      setIsUploadModalOpen(false);
      setSelectedFile(null);
      setUploadTitle('');
    };
    reader.onerror = (err) => {
      console.error('[Study] Error reading file for upload:', err);
      setIsUploadModalOpen(false);
    };
    reader.readAsDataURL(selectedFile);
  };

  const getSourceIcon = (type: SourceType) => {
    switch (type) {
      case 'PDF':
      case 'DOCX':
      case 'PPTX':
      case 'TXT':
      case 'MARKDOWN':
        return <FileText className="h-4 w-4 text-cyan-400" />;
      case 'IMAGE':
        return <ImageIcon className="h-4 w-4 text-emerald-400" />;
      case 'VIDEO':
        return <Video className="h-4 w-4 text-purple-400" />;
      case 'AUDIO':
      case 'LECTURE_AUDIO':
        return <Headphones className="h-4 w-4 text-purple-400" />;
      case 'NOTE':
        return <FileCode className="h-4 w-4 text-amber-400" />;
      default:
        return <BookOpen className="h-4 w-4 text-cyan-400" />;
    }
  };

  return (
    <div data-testid="study-library-view" className="flex h-full flex-col bg-[#0b1015] text-zinc-200">
      {/* 1. Header & Primary Actions */}
      <div className="border-b border-white/[0.08] bg-[#0e161c]/90 px-6 py-4 backdrop-blur-md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
                <BookOpen className="h-4 w-4" />
              </div>
              <h1 className="text-base font-semibold tracking-tight text-white">
                Biblioteca de Estudo & Disciplinas
              </h1>
              <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-xs text-zinc-400">
                {documents.length} materiais
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-400">
              Organização de cursos e disciplinas com sincronização automática de pastas locais, artigos, diapositivos e vídeos.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                id="study-refresh-library-btn"
                onClick={() => {
                  onRefresh();
                  if (onRefreshCollections) onRefreshCollections();
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/[0.08] hover:text-white cursor-pointer shadow-sm"
                title="Atualizar Catálogo"
              >
                <RotateCw className="h-3.5 w-3.5" />
                <span>Atualizar</span>
              </button>
            )}
            <button
              onClick={() => {
                if (activeCollection) {
                  setUploadSubject(activeCollection.subject || activeCollection.name);
                }
                setIsUploadModalOpen(true);
              }}
              data-testid="study-upload-doc-btn"
              className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/40 bg-cyan-500/15 px-3.5 py-2 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/25 shadow-sm cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>+ Adicionar conteúdo</span>
            </button>
          </div>
        </div>

        {/* 2. Course / Discipline Navigation Bar */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400 font-medium mr-1">
            <Folder className="h-3.5 w-3.5 text-cyan-400" />
            <span>Disciplina:</span>
          </div>

          {/* All Courses Tab */}
          <button
            onClick={() => setSelectedCollectionId(null)}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              selectedCollectionId === null
                ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 shadow-sm'
                : 'text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200 border border-transparent'
            }`}
          >
            <span>Todas as Disciplinas</span>
            <span className="rounded-full bg-white/[0.08] px-1.5 py-0.2 text-[10px] text-zinc-400">
              {documents.length}
            </span>
          </button>

          {/* Course Tabs */}
          {collections.map((col) => {
            const isSelected = selectedCollectionId === col.collection_id;
            const docCount = getCollectionDocCount(col);
            const hasFolders = col.linked_folders && col.linked_folders.length > 0;

            return (
              <button
                key={col.collection_id}
                onClick={() => setSelectedCollectionId(col.collection_id)}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  isSelected
                    ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40 shadow-sm'
                    : 'text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200 border border-transparent'
                }`}
              >
                <span>{col.name}</span>
                {hasFolders && (
                  <span
                    title={`${col.linked_folders?.length} pasta(s) vinculada(s)`}
                    className="flex items-center text-[10px] text-cyan-400"
                  >
                    📁 {col.linked_folders?.length}
                  </span>
                )}
                <span className="rounded-full bg-white/[0.08] px-1.5 py-0.2 text-[10px] text-zinc-400">
                  {docCount}
                </span>
              </button>
            );
          })}

          {/* + New Course Button */}
          <button
            onClick={() => setIsCreateCourseModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-white/15 px-2.5 py-1.5 text-xs text-zinc-400 hover:border-cyan-400/40 hover:text-cyan-300 transition"
            title="Criar nova disciplina ou cadeira académica"
          >
            <Plus className="h-3 w-3" />
            <span>Nova Disciplina</span>
          </button>
        </div>

        {/* 3. Linked Folders Toolbar for Active Course */}
        {activeCollection && (
          <div className="mt-3.5 rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-3.5 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-300">
                  <FolderSync className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold text-cyan-100 flex items-center gap-2">
                    <span>{activeCollection.name}</span>
                    <span className="text-[10px] text-cyan-400 font-normal">({activeCollection.subject})</span>
                  </h3>
                  <p className="text-[11px] text-zinc-400">
                    Sincronização contínua com pastas locais e inteligência de curso.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setCourseQaResult(null);
                    setCourseQaQuery('');
                    setIsCourseQaModalOpen(true);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-purple-400/40 bg-purple-500/15 px-3 py-1.5 text-xs font-semibold text-purple-200 hover:bg-purple-500/25 transition cursor-pointer"
                  title="Fazer perguntas a todos os materiais desta disciplina"
                >
                  <Sparkles className="h-3.5 w-3.5 text-purple-300" />
                  <span>Perguntar à Disciplina</span>
                </button>

                <button
                  onClick={handleTriggerLinkFolder}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/40 bg-cyan-500/20 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 transition cursor-pointer"
                  title="Vincular uma pasta do disco local a esta disciplina"
                >
                  <FolderPlus className="h-3.5 w-3.5 text-cyan-300" />
                  <span>Vincular Pasta Local</span>
                </button>
              </div>
            </div>

            {/* List of linked folders in this collection */}
            {activeCollection.linked_folders && activeCollection.linked_folders.length > 0 ? (
              <div className="mt-3 space-y-2 border-t border-cyan-500/15 pt-3">
                {activeCollection.linked_folders.map((link) => {
                  const isSyncing = syncingFolders[link.folder_path] || link.status === 'SYNCING';
                  const isError = link.status === 'ERROR';

                  return (
                    <div
                      key={link.folder_path}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-black/40 px-3 py-2"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <Folder className="h-4 w-4 text-cyan-400 shrink-0" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className="font-mono text-xs text-white truncate max-w-sm sm:max-w-md md:max-w-xl"
                              title={link.folder_path}
                            >
                              {link.folder_path}
                            </span>
                            {/* Sync Status Badge */}
                            {isSyncing ? (
                              <span className="inline-flex items-center gap-1 rounded bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-medium text-cyan-300 border border-cyan-500/20 animate-pulse">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                <span>A Sincronizar...</span>
                              </span>
                            ) : isError ? (
                              <span className="inline-flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-300 border border-red-500/20">
                                <AlertCircle className="h-3 w-3" />
                                <span>Erro na Sincronização</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300 border border-emerald-500/20">
                                <CheckCircle2 className="h-3 w-3" />
                                <span>Sincronizado</span>
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-zinc-400 flex items-center gap-2 mt-0.5">
                            <span>{link.file_count || 0} ficheiros detetados</span>
                            {Boolean(link.unsupported_count && link.unsupported_count > 0) && (
                              <span className="text-amber-400">
                                ({link.unsupported_count} não suportados)
                              </span>
                            )}
                            {link.last_synced_at && (
                              <span>
                                • Última verificação:{' '}
                                {new Date(link.last_synced_at).toLocaleTimeString('pt-PT', {
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </span>
                            )}
                          </p>
                        </div>
                      </div>

                      {/* Folder Actions */}
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleSyncNow(link.folder_path)}
                          disabled={isSyncing}
                          className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-zinc-300 hover:bg-white/[0.08] hover:text-white transition disabled:opacity-50"
                          title="Escanear e sincronizar alterações agora"
                        >
                          <RotateCw className={`h-3 w-3 ${isSyncing ? 'animate-spin text-cyan-300' : ''}`} />
                          <span>Sincronizar</span>
                        </button>

                        <button
                          onClick={() => handleOpenFolderOnDisk(link.folder_path)}
                          className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-zinc-300 hover:bg-white/[0.08] hover:text-white transition"
                          title="Abrir pasta no explorador de ficheiros do sistema"
                        >
                          <ExternalLink className="h-3 w-3" />
                          <span>Abrir</span>
                        </button>

                        <button
                          onClick={() => setFolderToUnlink(link)}
                          className="inline-flex items-center gap-1 rounded border border-red-500/20 bg-red-500/10 px-2 py-1 text-[11px] font-medium text-red-300 hover:bg-red-500/20 transition"
                          title="Desvincular esta pasta da disciplina (ficheiros no disco não serão apagados)"
                        >
                          <FolderX className="h-3 w-3" />
                          <span>Desvincular</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 flex items-center justify-between rounded-lg border border-dashed border-cyan-500/25 bg-black/20 p-3">
                <div className="flex items-center gap-2 text-zinc-300 text-xs">
                  <FolderPlus className="h-4 w-4 text-cyan-400" />
                  <span>
                    Nenhuma pasta local vinculada a esta disciplina. Vincule uma pasta para monitorização contínua.
                  </span>
                </div>
                <button
                  onClick={handleTriggerLinkFolder}
                  className="rounded-lg border border-cyan-400/30 bg-cyan-500/15 px-2.5 py-1 text-xs font-medium text-cyan-200 hover:bg-cyan-500/25 transition cursor-pointer"
                >
                  + Vincular Agora
                </button>
              </div>
            )}
          </div>
        )}

        {/* 4. Filters, Sort, View Toggle & Search Bar */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-2">
          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="mr-1 text-slate-500 flex items-center gap-1">
              <Filter className="h-3 w-3" /> Filtro:
            </span>
            {[
              { id: 'ALL', label: 'Todos' },
              { id: 'DOCS', label: 'Documentos' },
              { id: 'VIDEO', label: 'Vídeos' },
              { id: 'IMAGES', label: 'Imagens' },
              { id: 'AUDIO', label: 'Áudio' },
              { id: 'LECTURES', label: 'Aulas' },
              { id: 'NOTES', label: 'Notas' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                className={`rounded-md px-2.5 py-1 transition cursor-pointer ${
                  filterType === f.id
                    ? 'bg-sky-500/20 text-sky-200 border border-sky-400/30 font-medium'
                    : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 flex-1 sm:flex-none justify-end">
            {/* Sort Select */}
            <label className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-[#080c12] px-2.5 py-1 text-xs text-slate-300">
              <ArrowUpDown className="h-3 w-3 text-slate-500" />
              <select
                aria-label="Ordenar materiais"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="bg-transparent text-xs text-slate-200 outline-none cursor-pointer"
              >
                <option value="recent">Recentes</option>
                <option value="title">Título (A-Z)</option>
                <option value="type">Tipo</option>
                <option value="progress">Progresso</option>
              </select>
            </label>

            {/* List / Grid Toggle */}
            <div className="inline-flex items-center rounded-lg border border-slate-800 bg-[#080c12] p-0.5">
              <button
                type="button"
                data-testid="study-library-view-list"
                onClick={() => handleSetViewMode('list')}
                className={`rounded-md p-1.5 transition cursor-pointer ${
                  viewMode === 'list' ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400 hover:text-white'
                }`}
                title="Vista em Lista"
              >
                <LayoutList className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                data-testid="study-library-view-grid"
                onClick={() => handleSetViewMode('grid')}
                className={`rounded-md p-1.5 transition cursor-pointer ${
                  viewMode === 'grid' ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400 hover:text-white'
                }`}
                title="Vista em Grelha"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Search Box */}
            <div className="relative min-w-[220px] flex-1 sm:flex-none">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Pesquisar por título, disciplina ou pasta..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-full rounded-lg border border-slate-800 bg-[#080c12] pl-8 pr-3 text-xs text-slate-200 placeholder-slate-500 outline-none focus:border-sky-400/50"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Upload Progress Banner if active */}
      {isUploading && (
        <div className="border-b border-cyan-400/30 bg-cyan-950/40 px-6 py-2.5 flex items-center gap-3 text-xs text-cyan-200 animate-pulse">
          <UploadCloud className="h-4 w-4 animate-bounce text-cyan-300" />
          <span>A processar documento: {uploadStatus || 'A extrair páginas e secções...'}</span>
        </div>
      )}
      {!isUploading && uploadStatus.startsWith('Erro:') && (
        <div className="border-b border-rose-500/30 bg-rose-950/40 px-6 py-2.5 flex items-center gap-3 text-xs text-rose-200">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{uploadStatus}</span>
        </div>
      )}

      {/* 5. Library Body: Left Facets + Drag-Drop Canvas */}
      <div
        className={`relative flex flex-1 overflow-hidden ${canvasDragActive ? 'ring-2 ring-inset ring-sky-400/60 bg-sky-500/[0.04]' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setCanvasDragActive(true);
        }}
        onDragLeave={() => setCanvasDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setCanvasDragActive(false);
          if (e.dataTransfer.files?.length) {
            handleCanvasDropUpload(e.dataTransfer.files);
          }
        }}
      >
        {/* Left Discrete Facets Rail */}
        <aside className="hidden md:flex w-48 shrink-0 flex-col border-r border-slate-800/80 bg-[#090e15] p-3 gap-1">
          <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Vistas Rápidas
          </div>
          {[
            { id: 'ALL' as const, label: 'Todos os Materiais', count: documents.length },
            {
              id: 'RECENT' as const,
              label: 'Recentes',
              count: documents.filter((d) => Boolean(d.reading_progress?.last_read_at || d.reading_progress?.progress_percent)).length,
            },
            { id: 'FAVORITES' as const, label: 'Favoritos', count: favoriteIds.length },
            {
              id: 'FOLDERS' as const,
              label: 'Pastas Sincronizadas',
              count: documents.filter((d) => ((d as any).source_origin || d.provenance?.source_origin) === 'linked_folder').length,
            },
            {
              id: 'MEDIA' as const,
              label: 'Vídeo & Média',
              count: documents.filter((d) => ['VIDEO', 'AUDIO', 'IMAGE', 'LECTURE_AUDIO'].includes(d.source_type)).length,
            },
          ].map((facet) => (
            <button
              key={facet.id}
              type="button"
              onClick={() => setActiveFacet(facet.id)}
              className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition cursor-pointer ${
                activeFacet === facet.id
                  ? 'bg-sky-500/15 text-sky-200 font-semibold border border-sky-400/25'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200 border border-transparent'
              }`}
            >
              <span className="truncate">{facet.label}</span>
              <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-400">{facet.count}</span>
            </button>
          ))}

          <div className="mt-auto rounded-lg border border-dashed border-slate-800 bg-[#070b11] p-2.5 text-[11px] text-slate-400">
            Arrasta PDFs, slides ou vídeos para qualquer ponto desta biblioteca.
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Bulk Selection Toolbar */}
          {selectedDocIds.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-sky-400/30 bg-sky-500/10 px-4 py-2 text-xs">
              <div className="flex items-center gap-3 text-sky-100 font-medium">
                <span>{selectedDocIds.length} selecionado(s)</span>
                <button
                  type="button"
                  onClick={() => setSelectedDocIds(filteredDocs.map((d) => d.document_id))}
                  className="text-sky-300 hover:underline cursor-pointer"
                >
                  Selecionar todos ({filteredDocs.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDocIds([])}
                  className="text-slate-400 hover:text-white cursor-pointer"
                >
                  Limpar
                </button>
              </div>
              {onDeleteDocument && (
                <button
                  type="button"
                  onClick={async () => {
                    for (const docId of selectedDocIds) {
                      await onDeleteDocument(docId);
                    }
                    setSelectedDocIds([]);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/15 px-3 py-1 text-xs font-semibold text-rose-200 hover:bg-rose-500/25 cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Eliminar selecionados</span>
                </button>
              )}
            </div>
          )}

          {/* Recently Opened Shelf */}
          {recentDocsShelf.length > 0 && activeFacet === 'ALL' && !searchQuery.trim() && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Abertos Recentemente
                </h2>
              </div>
              <div className="grid grid-cols-1 gap-2.5 md:grid-cols-3">
                {recentDocsShelf.map((doc) => {
                  const pct = Math.round(doc.reading_progress?.progress_percent || 0);
                  return (
                    <button
                      key={`recent-${doc.document_id}`}
                      type="button"
                      onClick={() => onOpenDocument(doc.document_id, 'reader')}
                      className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-[#0d141f] p-3 text-left transition hover:border-sky-400/40 hover:bg-[#111b29] cursor-pointer"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-xs font-semibold text-white">{doc.title}</div>
                        <div className="mt-0.5 text-[11px] text-slate-400 truncate">
                          {doc.subject || 'Geral'} • {doc.source_type}
                        </div>
                      </div>
                      <span className="shrink-0 rounded-full bg-sky-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-sky-300">
                        {pct}%
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {filteredDocs.length === 0 ? (
            <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-[#0b111a]/60 p-8 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.04] text-slate-500 mb-3">
                <BookOpen className="h-6 w-6" />
              </div>
              <p className="text-sm font-semibold text-slate-300">
                {activeCollection
                  ? `Nenhum material associado à disciplina "${activeCollection.name}".`
                  : 'Nenhum material de estudo encontrado.'}
              </p>
              <p className="mt-1 text-xs text-slate-500 max-w-md">
                {activeCollection
                  ? 'Vincula uma pasta local com apontamentos e diapositivos ou carrega os ficheiros manualmente.'
                  : 'Arrasta ficheiros para aqui ou começa por carregar um artigo científico, vídeo ou nota de estudo.'}
              </p>
              <div className="mt-4 flex items-center gap-3">
                {activeCollection && (
                  <button
                    onClick={handleTriggerLinkFolder}
                    className="inline-flex items-center gap-2 rounded-lg border border-sky-400/40 bg-sky-500/20 px-4 py-2 text-xs font-semibold text-sky-200 hover:bg-sky-500/30 transition cursor-pointer"
                  >
                    <FolderPlus className="h-4 w-4" />
                    <span>Vincular Pasta Local</span>
                  </button>
                )}
                <button
                  onClick={() => setIsUploadModalOpen(true)}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-white/[0.05] px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-white/10 transition cursor-pointer"
                >
                  <FileUp className="h-4 w-4" />
                  <span>Carregar Ficheiro</span>
                </button>
              </div>
            </div>
          ) : viewMode === 'list' ? (
            <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-[#0b111a]">
              <div className="grid grid-cols-12 items-center gap-2 border-b border-slate-800/80 bg-[#080c12] px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <div className="col-span-5">Documento / Disciplina</div>
                <div className="col-span-2 hidden sm:block">Tipo & Origem</div>
                <div className="col-span-2 hidden md:block">Progresso</div>
                <div className="col-span-3 text-right">Ações</div>
              </div>
              <div className="divide-y divide-slate-800/60">
                {filteredDocs.map((doc) => {
                  const progressPct = Math.round(doc.reading_progress?.progress_percent || 0);
                  const isVideo = doc.source_type === 'VIDEO';
                  const isFav = favoriteIds.includes(doc.document_id);
                  const isChecked = selectedDocIds.includes(doc.document_id);
                  const sourceOrigin = (doc as any).source_origin || doc.provenance?.source_origin || 'manual_upload';
                  const isLinkedFolder = sourceOrigin === 'linked_folder';
                  const syncStatus = (doc as any).sync_status || doc.provenance?.sync_status || 'synced';
                  const isRetrying = retryingDocs[doc.document_id];

                  return (
                    <div
                      key={doc.document_id}
                      className={`grid grid-cols-12 items-center gap-2 px-4 py-3 text-xs transition hover:bg-white/[0.03] ${
                        isChecked ? 'bg-sky-500/[0.06]' : ''
                      }`}
                    >
                      <div className="col-span-8 sm:col-span-5 flex items-center gap-2.5 min-w-0">
                        <button
                          type="button"
                          onClick={() => toggleSelectDoc(doc.document_id)}
                          className="text-slate-500 hover:text-sky-300 shrink-0 cursor-pointer"
                          title="Selecionar documento"
                        >
                          {isChecked ? <CheckSquare className="h-4 w-4 text-sky-400" /> : <Square className="h-4 w-4" />}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleFavorite(doc.document_id)}
                          className={`shrink-0 cursor-pointer ${isFav ? 'text-amber-400' : 'text-slate-600 hover:text-amber-300'}`}
                          title={isFav ? 'Remover dos favoritos' : 'Marcar como favorito'}
                        >
                          <Star className={`h-3.5 w-3.5 ${isFav ? 'fill-amber-400' : ''}`} />
                        </button>
                        <div className="min-w-0">
                          <button
                            type="button"
                            onClick={() => onOpenDocument(doc.document_id, 'reader')}
                            className="truncate block text-left font-semibold text-white hover:text-sky-300 transition cursor-pointer max-w-full"
                            title={doc.title}
                          >
                            {doc.title}
                          </button>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 truncate">
                            <span>{doc.subject || 'Geral'}</span>
                            {syncStatus === 'failed' && (
                              <span className="text-rose-400 font-medium">• Erro no processamento</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="col-span-2 hidden sm:flex items-center gap-1.5">
                        <span className="inline-flex items-center gap-1 rounded border border-slate-700/80 bg-[#080c12] px-1.5 py-0.5 text-[10px] font-medium text-sky-300">
                          {getSourceIcon(doc.source_type)}
                          <span>{doc.source_type}</span>
                        </span>
                        {isLinkedFolder && (
                          <span title="Pasta vinculada" className="inline-flex">
                            <Folder className="h-3.5 w-3.5 text-sky-400" />
                          </span>
                        )}
                      </div>

                      <div className="col-span-2 hidden md:flex items-center gap-2">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className={`h-full rounded-full ${isVideo ? 'bg-purple-400' : 'bg-sky-400'}`}
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                        <span className="w-8 text-right font-mono text-[10px] text-slate-300">{progressPct}%</span>
                      </div>

                      <div className="col-span-4 sm:col-span-3 flex items-center justify-end gap-1">
                        {syncStatus === 'failed' && (
                          <button
                            type="button"
                            onClick={() => handleRetryDoc(doc.document_id)}
                            disabled={isRetrying}
                            className="rounded px-2 py-1 text-[10px] font-semibold bg-rose-500/15 text-rose-200 hover:bg-rose-500/25 cursor-pointer"
                          >
                            {isRetrying ? '...' : 'Retry'}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => onOpenDocument(doc.document_id, 'summary')}
                          className="rounded px-2 py-1 text-[11px] text-slate-400 hover:bg-white/[0.06] hover:text-white cursor-pointer"
                        >
                          Resumo
                        </button>
                        <button
                          type="button"
                          onClick={() => onOpenDocument(doc.document_id, 'reader')}
                          className="inline-flex items-center gap-1 rounded-md border border-sky-400/30 bg-sky-500/15 px-2.5 py-1 text-[11px] font-semibold text-sky-200 hover:bg-sky-500/25 cursor-pointer"
                        >
                          <span>Ler</span>
                          <ArrowRight className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDocumentToDelete(doc)}
                          className="rounded p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 cursor-pointer"
                          title="Eliminar material"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {filteredDocs.map((doc) => {
                const progressPct = Math.round(doc.reading_progress?.progress_percent || 0);
                const isEn = (doc.language || 'en').toLowerCase().startsWith('en');
                const isVideo = doc.source_type === 'VIDEO';
                const isFav = favoriteIds.includes(doc.document_id);
                const isChecked = selectedDocIds.includes(doc.document_id);
                const videoDuration =
                  (doc.metadata as any)?.video?.duration_seconds || (doc.metadata as any)?.duration_seconds;
                const videoDurationStr = videoDuration
                  ? `${Math.floor(videoDuration / 60)}:${Math.floor(videoDuration % 60)
                      .toString()
                      .padStart(2, '0')}`
                  : null;
                const lastWatched = (doc.metadata as any)?.video_progress?.last_watched_at;

                const sourceOrigin = (doc as any).source_origin || doc.provenance?.source_origin || 'manual_upload';
                const isLinkedFolder = sourceOrigin === 'linked_folder';
                const relPath = doc.provenance?.rel_path || '';

                const syncStatus = (doc as any).sync_status || doc.provenance?.sync_status || 'synced';
                const syncError = (doc as any).sync_error || doc.provenance?.sync_error;
                const isRetrying = retryingDocs[doc.document_id];

                return (
                  <div
                    key={doc.document_id}
                    className={`group relative flex flex-col justify-between rounded-xl border bg-[#0c131d]/90 p-5 transition hover:border-slate-600 hover:bg-[#101927] shadow-sm ${
                      isChecked ? 'border-sky-400/60' : 'border-slate-800/80'
                    }`}
                  >
                    <div>
                      {/* Top Row */}
                      <div className="flex items-center justify-between gap-2 mb-2 text-xs">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <button
                            type="button"
                            onClick={() => toggleSelectDoc(doc.document_id)}
                            className="text-slate-500 hover:text-sky-300 cursor-pointer"
                            title="Selecionar documento"
                          >
                            {isChecked ? <CheckSquare className="h-3.5 w-3.5 text-sky-400" /> : <Square className="h-3.5 w-3.5" />}
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleFavorite(doc.document_id)}
                            className={`cursor-pointer ${isFav ? 'text-amber-400' : 'text-slate-600 hover:text-amber-300'}`}
                            title={isFav ? 'Remover dos favoritos' : 'Marcar como favorito'}
                          >
                            <Star className={`h-3.5 w-3.5 ${isFav ? 'fill-amber-400' : ''}`} />
                          </button>
                          <span
                            className={`flex items-center gap-1 rounded px-2 py-0.5 font-medium border ${
                              isVideo
                                ? 'bg-purple-500/10 text-purple-300 border-purple-500/20'
                                : 'bg-white/[0.05] text-sky-300 border-white/5'
                            }`}
                          >
                            {getSourceIcon(doc.source_type)}
                            <span>{doc.source_type}</span>
                          </span>

                          <span className="rounded bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-slate-400 border border-white/5">
                            {isEn ? 'English' : 'Português'}
                          </span>

                          {isLinkedFolder ? (
                            <span
                              className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-300 border border-blue-500/20"
                              title={`Origem: Pasta local vinculada (${relPath || doc.provenance?.source_file})`}
                            >
                              <Folder className="h-3 w-3" />
                              <span className="truncate max-w-[120px]">{relPath || 'Pasta Local'}</span>
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 rounded bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-slate-400 border border-white/5"
                              title="Carregamento individual"
                            >
                              <UploadCloud className="h-3 w-3" />
                              <span>Upload Manual</span>
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          {isVideo ? (
                            <span className="text-[11px] text-slate-400 font-mono">⏱️ {videoDurationStr || 'Vídeo'}</span>
                          ) : (
                            <span className="text-[11px] text-slate-500">
                              {doc.page_count} {doc.page_count === 1 ? 'página' : 'páginas'}
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDocumentToDelete(doc);
                            }}
                            className="rounded p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition opacity-60 group-hover:opacity-100 cursor-pointer"
                            title="Eliminar material da biblioteca"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {syncStatus === 'failed' && (
                        <div className="mb-2 flex items-center justify-between rounded bg-red-500/10 px-2 py-1 text-[11px] text-red-300 border border-red-500/20">
                          <div className="flex items-center gap-1 truncate mr-2">
                            <AlertCircle className="h-3 w-3 shrink-0" />
                            <span className="truncate">Falha: {syncError || 'Erro no processamento'}</span>
                          </div>
                          <button
                            onClick={() => handleRetryDoc(doc.document_id)}
                            disabled={isRetrying}
                            className="rounded bg-red-500/20 px-2 py-0.5 text-[10px] font-semibold text-red-200 hover:bg-red-500/30 transition shrink-0"
                          >
                            {isRetrying ? 'A tentar...' : 'Tentar Novamente'}
                          </button>
                        </div>
                      )}

                      {syncStatus === 'processing' && (
                        <div className="mb-2 flex items-center gap-1.5 rounded bg-amber-500/10 px-2 py-1 text-[11px] text-amber-300 border border-amber-500/20 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                          <span>A processar conteúdo em segundo plano...</span>
                        </div>
                      )}

                      <h2
                        onClick={() => onOpenDocument(doc.document_id, 'reader')}
                        className="text-sm font-semibold text-white group-hover:text-sky-200 transition-colors cursor-pointer line-clamp-2"
                        title={doc.title}
                      >
                        {doc.title}
                      </h2>
                      <p className="mt-1 text-xs text-slate-400 flex items-center gap-1">
                        <span className="text-slate-500">Disciplina:</span> {doc.subject}
                      </p>

                      <div className="mt-4">
                        <div className="flex items-center justify-between text-[11px] mb-1">
                          <span className="text-slate-500">{isVideo ? 'Visualização' : 'Progresso de Leitura'}</span>
                          <span className="font-mono text-slate-300">
                            {progressPct}% {isVideo ? 'assistido' : ''}
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                          <div
                            className={`h-full transition-all duration-300 rounded-full ${isVideo ? 'bg-purple-400' : 'bg-sky-400'}`}
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                        {isVideo && lastWatched && (
                          <p className="mt-1 text-[10px] text-slate-500 font-mono">
                            Última visualização: {new Date(lastWatched).toLocaleDateString('pt-PT')}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-white/[0.06] flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1 text-[10px] text-slate-500">
                        <Clock className="h-3 w-3" />
                        <span>{new Date(doc.updated_at || doc.created_at).toLocaleDateString('pt-PT')}</span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => onOpenDocument(doc.document_id, 'summary')}
                          className="rounded-md px-2 py-1 text-xs text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] transition cursor-pointer"
                          title="Ver Resumo e Argument Map"
                        >
                          Resumo
                        </button>
                        <button
                          onClick={() => onOpenDocument(doc.document_id, 'quiz')}
                          className="rounded-md px-2 py-1 text-xs text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] transition cursor-pointer"
                          title="Fazer Quiz"
                        >
                          Quiz
                        </button>
                        <button
                          onClick={() => onOpenDocument(doc.document_id, 'reader')}
                          className="inline-flex items-center gap-1 rounded-md border border-sky-400/30 bg-sky-400/10 px-2.5 py-1 text-xs font-medium text-sky-300 hover:bg-sky-400/20 transition cursor-pointer"
                        >
                          <span>Ler</span>
                          <ArrowRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ============================================================ */}
      {/* 6. Create Course Modal                                       */}
      {/* ============================================================ */}
      {isCreateCourseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md rounded-xl border border-white/[0.12] bg-[#0e161c] p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <FolderPlus className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Criar Nova Disciplina</h3>
              </div>
              <button
                onClick={() => setIsCreateCourseModalOpen(false)}
                className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateCourseSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Nome da Disciplina / Cadeira *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Engenharia de Software, Álgebra Linear, IA..."
                  value={newCourseName}
                  onChange={(e) => setNewCourseName(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-cyan-400/40"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Área Científica / Assunto
                </label>
                <input
                  type="text"
                  placeholder="Ex: Ciência da Computação, Matemática..."
                  value={newCourseSubject}
                  onChange={(e) => setNewCourseSubject(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-cyan-400/40"
                />
              </div>

              <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-3 text-[11px] text-zinc-300">
                <p>
                  Após criar a disciplina, poderás vincular qualquer pasta local do teu computador para que todos os PDFs, slides e gravações sejam importados automaticamente.
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateCourseModalOpen(false)}
                  className="rounded-lg border border-white/[0.08] px-3.5 py-1.5 text-xs text-zinc-400 hover:bg-white/[0.05]"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={!newCourseName.trim() || isCreatingCourse}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/40 bg-cyan-500/20 px-4 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 transition disabled:opacity-50"
                >
                  <span>{isCreatingCourse ? 'A criar...' : 'Criar Disciplina'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 7. Link Folder Manual Fallback Modal                         */}
      {/* ============================================================ */}
      {isLinkFolderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg rounded-xl border border-cyan-500/30 bg-[#0e161c] p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <FolderPlus className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">
                  Vincular Pasta Local a {activeCollection?.name}
                </h3>
              </div>
              <button
                onClick={() => setIsLinkFolderModalOpen(false)}
                className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleManualLinkFolderSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Caminho da Pasta no Computador *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: C:\Universidade\Engenharia_Software ou /home/user/materiais"
                  value={linkFolderPathInput}
                  onChange={(e) => setLinkFolderPathInput(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-2 font-mono text-xs text-white placeholder-zinc-500 outline-none focus:border-cyan-400/40"
                  autoFocus
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="recursive-sync-chk"
                  checked={linkFolderRecursive}
                  onChange={(e) => setLinkFolderRecursive(e.target.checked)}
                  className="rounded border-white/20 bg-black/40 text-cyan-500 focus:ring-0"
                />
                <label htmlFor="recursive-sync-chk" className="text-xs text-zinc-300 cursor-pointer">
                  Sincronizar subpastas recursivamente
                </label>
              </div>

              <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3 text-[11px] text-emerald-200 flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
                <p>
                  <strong>Garantia de Não-Destruição:</strong> O JARVIS OS apenas lê os teus ficheiros locais. Nunca modificará nem apagará qualquer ficheiro original no teu disco rígido.
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsLinkFolderModalOpen(false)}
                  className="rounded-lg border border-white/[0.08] px-3.5 py-1.5 text-xs text-zinc-400 hover:bg-white/[0.05]"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={!linkFolderPathInput.trim() || isLinkingFolder}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/40 bg-cyan-500/20 px-4 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 transition disabled:opacity-50"
                >
                  <span>{isLinkingFolder ? 'A vincular...' : 'Vincular e Sincronizar'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 8. Unlink Folder Confirmation Modal                          */}
      {/* ============================================================ */}
      {folderToUnlink && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md rounded-xl border border-red-500/30 bg-[#0e161c] p-6 shadow-2xl">
            <div className="flex items-center gap-3 pb-3 border-b border-white/[0.08]">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/15 text-red-400 border border-red-500/20">
                <FolderX className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Desvincular Pasta Local</h3>
                <p className="text-xs text-zinc-400">{activeCollection?.name}</p>
              </div>
            </div>

            <div className="my-4 rounded-lg border border-white/[0.06] bg-black/30 p-3">
              <span className="text-[11px] text-zinc-500 block mb-1">Caminho da Pasta:</span>
              <p className="font-mono text-xs text-white break-all">{folderToUnlink.folder_path}</p>
            </div>

            <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3 text-[11px] text-emerald-200 flex items-start gap-2 mb-4">
              <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
              <p>
                <strong>Proteção Total de Ficheiros:</strong> Desvincular esta pasta interrompe a monitorização automática. Os teus ficheiros no computador <u>permanecem 100% intactos</u>.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={isUnlinking}
                onClick={() => setFolderToUnlink(null)}
                className="rounded-lg border border-white/[0.08] px-3.5 py-2 text-xs font-medium text-zinc-300 hover:bg-white/[0.05] transition"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={isUnlinking}
                onClick={handleUnlinkFolderConfirm}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/20 px-4 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/30 transition disabled:opacity-50 cursor-pointer"
              >
                <FolderX className="h-3.5 w-3.5" />
                <span>{isUnlinking ? 'A desvincular...' : 'Confirmar Desvinculação'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 9. Course Q&A ("Perguntar à Disciplina") Modal                */}
      {/* ============================================================ */}
      {isCourseQaModalOpen && activeCollection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md animate-in fade-in">
          <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-xl border border-purple-500/30 bg-[#0e161c] shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-white/[0.08]">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 text-purple-300">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Perguntar à Disciplina: {activeCollection.name}
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Respostas fundamentadas em todos os documentos, aulas gravadas e apontamentos com citações exatas.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsCourseQaModalOpen(false)}
                className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Question Input */}
              <form onSubmit={handleCourseQaSubmit} className="space-y-2">
                <div className="relative">
                  <textarea
                    rows={3}
                    value={courseQaQuery}
                    onChange={(e) => setCourseQaQuery(e.target.value)}
                    placeholder="O que pretendes saber sobre esta cadeira? (ex: Quais os princípios da arquitetura de software abordados nas aulas?)"
                    className="w-full rounded-lg border border-white/[0.1] bg-black/40 p-3 text-xs text-white placeholder-zinc-500 outline-none focus:border-purple-400/50"
                  />
                </div>

                {/* Quick suggestions */}
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="text-zinc-500">Sugestões rápidas:</span>
                  {[
                    'Quais são os conceitos centrais desta disciplina?',
                    'Resume os tópicos principais de todas as aulas',
                    'Que fórmulas ou metodologias são essenciais para o exame?',
                  ].map((sug, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setCourseQaQuery(sug);
                      }}
                      className="rounded bg-white/[0.04] px-2 py-0.5 text-zinc-300 hover:bg-white/[0.08] hover:text-purple-300 border border-white/5 transition"
                    >
                      {sug}
                    </button>
                  ))}
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="submit"
                    disabled={!courseQaQuery.trim() || isCourseQaLoading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-purple-400/40 bg-purple-500/20 px-4 py-2 text-xs font-semibold text-purple-200 hover:bg-purple-500/30 transition disabled:opacity-50"
                  >
                    {isCourseQaLoading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-300" />
                        <span>A sintetizar resposta com citações...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5 text-purple-300" />
                        <span>Perguntar</span>
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Result Area */}
              {courseQaResult && (
                <div className="mt-4 rounded-xl border border-white/[0.08] bg-black/30 p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2 text-xs">
                    <span className="font-semibold text-purple-300 flex items-center gap-1.5">
                      <BookOpen className="h-3.5 w-3.5" />
                      <span>Resposta da Disciplina</span>
                    </span>
                    <span className="text-zinc-500 text-[10px]">
                      {courseQaResult.sources?.length || 0} fontes consultadas
                    </span>
                  </div>

                  {/* Insufficient Evidence Warning if detected */}
                  {courseQaResult.answer.includes('INSUFFICIENT_EVIDENCE') ||
                  courseQaResult.answer.toLowerCase().includes('não foram encontradas evidências') ? (
                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-200 flex items-start gap-2">
                      <HelpCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
                      <div>
                        <p className="font-semibold">Evidência Insuficiente nos Materiais</p>
                        <p className="text-[11px] text-zinc-300 mt-0.5">
                          Os materiais indexados nesta disciplina não contêm referências conclusivas sobre esta pergunta. Vincula mais documentos ou gravações de aulas para expandir o conhecimento da cadeira.
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {/* Markdown / Text Answer */}
                  <div className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                    {courseQaResult.answer}
                  </div>

                  {/* Citations List */}
                  {courseQaResult.citations && courseQaResult.citations.length > 0 && (
                    <div className="mt-4 border-t border-white/[0.06] pt-3">
                      <span className="text-[11px] font-semibold text-zinc-400 block mb-1.5">
                        Citações e Fontes Confiáveis:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {courseQaResult.citations.map((cite, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 rounded bg-purple-500/10 px-2 py-0.5 font-mono text-[10px] text-purple-300 border border-purple-500/20"
                          >
                            <span>📎</span>
                            <span>{cite}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 10. Upload Modal with Drag & Drop                            */}
      {/* ============================================================ */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg rounded-xl border border-white/[0.12] bg-[#0e161c] p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <FileUp className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Adicionar Conteúdo de Estudo</h3>
              </div>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="rounded p-1 text-zinc-400 hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Mode selection */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 my-4">
              {[
                { id: 'file', label: 'Documento', icon: FileText },
                { id: 'video', label: 'Vídeo Local', icon: Video },
                { id: 'video_url', label: 'Vídeo Online', icon: LinkIcon },
                { id: 'text', label: 'Texto', icon: FileCode },
                { id: 'lecture', label: 'Gravar Aula', icon: Headphones },
              ].map((m) => {
                const Icon = m.icon;
                const isSel = uploadMode === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => setUploadMode(m.id as any)}
                    className={`flex flex-col items-center gap-1.5 p-2.5 rounded-lg border text-xs font-medium transition ${
                      isSel
                        ? 'border-cyan-400/40 bg-cyan-500/15 text-cyan-200'
                        : 'border-white/[0.06] bg-white/[0.02] text-zinc-400 hover:bg-white/[0.05]'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{m.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Inputs: Title & Subject */}
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-zinc-400 text-xs mb-1">Título do Material</label>
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="Nome do artigo, aula ou apresentação..."
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-1.5 text-xs text-zinc-200 outline-none focus:border-cyan-400/40"
                />
              </div>

              <div>
                <label className="block text-zinc-400 text-xs mb-1">Disciplina / Cadeira</label>
                <input
                  type="text"
                  value={uploadSubject}
                  onChange={(e) => setUploadSubject(e.target.value)}
                  placeholder="Ex: Engenharia de Software..."
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-1.5 text-xs text-zinc-200 outline-none focus:border-cyan-400/40"
                />
              </div>
            </div>

            {/* Mode-specific content */}
            {uploadMode === 'file' && (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/20 bg-white/[0.02] p-6 text-center hover:border-cyan-400/50 hover:bg-cyan-500/[0.02] transition cursor-pointer"
              >
                <UploadCloud className="h-8 w-8 text-zinc-400 mb-2" />
                <p className="text-xs font-medium text-zinc-200">
                  {selectedFile ? selectedFile.name : 'Arrasta o documento ou áudio para aqui ou clica para procurar'}
                </p>
                <p className="mt-1 text-[11px] text-zinc-500">
                  PDF, DOCX, PPTX, TXT, Markdown, PNG, JPG, MP3, WAV, M4A (máx. 100 MB)
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.pptx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.mp4,.webm,.mkv,.mov,.avi,.wmv,.m4v,.mp3,.wav,.m4a,.ogg,.flac,.aac,.wma"
                  className="hidden"
                />
              </div>
            )}

            {uploadMode === 'video' && (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center justify-center rounded-xl border border-dashed border-purple-400/30 bg-purple-500/[0.02] p-6 text-center hover:border-purple-400/60 transition cursor-pointer"
              >
                <Video className="h-8 w-8 text-purple-400 mb-2" />
                <p className="text-xs font-medium text-zinc-200">
                  {selectedFile ? selectedFile.name : 'Arrasta o ficheiro de vídeo ou áudio para aqui ou clica para procurar'}
                </p>
                <p className="mt-1 text-[11px] text-zinc-400">
                  Formatos suportados: .mp4, .webm, .mkv, .mov, .avi, .wmv, .mp3, .wav, .m4a
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  accept=".mp4,.webm,.mkv,.mov,.avi,.wmv,.m4v,.mp3,.wav,.m4a,.ogg,.flac,.aac,.wma"
                  className="hidden"
                />
              </div>
            )}

            {uploadMode === 'video_url' && (
              <div>
                <label className="block text-zinc-400 text-xs mb-1">URL do Vídeo</label>
                <input
                  type="url"
                  value={videoUrlInput}
                  onChange={(e) => setVideoUrlInput(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... ou https://.../aula.mp4"
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 p-2.5 text-xs text-zinc-200 outline-none focus:border-cyan-400/40"
                />
                <p className="mt-1.5 text-[11px] text-zinc-500">
                  O Jarvis extrairá os fluxos de áudio e visual para indexação multimodal.
                </p>
              </div>
            )}

            {uploadMode === 'text' && (
              <div>
                <label className="block text-zinc-400 text-xs mb-1">Texto ou Artigo</label>
                <textarea
                  data-testid="study-upload-textarea"
                  value={rawTextContent}
                  onChange={(e) => setRawTextContent(e.target.value)}
                  rows={6}
                  placeholder="Cole aqui o texto do artigo científico ou apontamentos..."
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 p-3 text-xs text-zinc-200 outline-none focus:border-cyan-400/40"
                />
              </div>
            )}

            {uploadMode === 'lecture' && (
              <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-xs text-purple-200">
                <p className="font-semibold mb-1">Gravação de Aula Expositiva</p>
                <p className="text-zinc-400">
                  Ao confirmar, o Jarvis ativará a captura contínua via microfone e sintetizará transcrição Whisper + Cornell Notes diretamente para a tua Biblioteca.
                </p>
              </div>
            )}

            {/* Bottom Modal Actions */}
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="rounded-lg border border-white/[0.08] px-3.5 py-1.5 text-xs text-zinc-400 hover:bg-white/[0.05]"
              >
                Cancelar
              </button>
              <button
                onClick={handleSubmitUpload}
                data-testid="study-upload-submit-btn"
                disabled={uploadMode === 'file' && !selectedFile && !uploadTitle}
                className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/40 bg-cyan-500/20 px-4 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <span>{uploadMode === 'lecture' ? 'Iniciar Gravação' : 'Processar Material'}</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* 11. Delete Document Confirmation Modal                       */}
      {/* ============================================================ */}
      {documentToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md rounded-xl border border-red-500/20 bg-[#0e161c] p-6 shadow-2xl">
            <div className="flex items-center gap-3 pb-3 border-b border-white/[0.08]">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/15 text-red-400 border border-red-500/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Eliminar Material de Estudo</h3>
                <p className="text-xs text-zinc-400">Esta ação não pode ser desfeita.</p>
              </div>
            </div>

            <div className="my-4 rounded-lg border border-white/[0.06] bg-black/30 p-3">
              <p className="text-xs font-medium text-white line-clamp-2">{documentToDelete.title}</p>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-zinc-400">
                <span className="rounded bg-white/[0.05] px-1.5 py-0.5 text-cyan-300 font-mono text-[10px]">
                  {documentToDelete.source_type}
                </span>
                <span>Disciplina: {documentToDelete.subject}</span>
                {Boolean(documentToDelete.page_count) && <span>• {documentToDelete.page_count} páginas</span>}
              </div>
            </div>

            {/* Non-destructive notice if from linked folder */}
            {(documentToDelete as any).source_origin === 'linked_folder' ||
            documentToDelete.provenance?.source_origin === 'linked_folder' ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-2.5 text-[11px] text-emerald-200 flex items-start gap-2 mb-3">
                <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
                <p>
                  <strong>Ficheiro no disco protegido:</strong> Este material provém de uma pasta local vinculada. O ficheiro original em disco <u>NÃO será apagado</u>; apenas a indexação na área de estudo será removida.
                </p>
              </div>
            ) : (
              <p className="text-xs text-zinc-400 mb-3">
                O ficheiro e todos os apontamentos, destaques e quizzes associados serão removidos da biblioteca.
              </p>
            )}

            <div className="mt-5 flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDocumentToDelete(null)}
                className="rounded-lg border border-white/[0.08] px-3.5 py-2 text-xs font-medium text-zinc-300 hover:bg-white/[0.05] transition"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/20 px-4 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/30 transition disabled:opacity-50 cursor-pointer"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>{isDeleting ? 'A eliminar...' : 'Remover da Biblioteca'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
