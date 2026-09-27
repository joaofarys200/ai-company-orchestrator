import React, { useState, useRef } from 'react';
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
  Link as LinkIcon
} from 'lucide-react';
import type { StudyDocument, SourceType } from './types';

interface StudyLibraryViewProps {
  documents: StudyDocument[];
  onOpenDocument: (docId: string, initialTab?: 'reader' | 'summary' | 'notes' | 'quiz') => void;
  onUpload: (payload: {
    filename: string;
    content_base64?: string;
    content_text?: string;
    subject: string;
    source_type?: SourceType;
    title?: string;
  }) => void;
  onRefresh?: () => void;
  isUploading?: boolean;
  uploadStatus?: string;
  onStartLectureRecording?: () => void;
  isRecording?: boolean;
  onStopRecording?: () => void;
}

export const StudyLibraryView: React.FC<StudyLibraryViewProps> = ({
  documents,
  onOpenDocument,
  onUpload,
  onRefresh,
  isUploading = false,
  uploadStatus = '',
  onStartLectureRecording,
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);

  // Upload modal form state
  const [uploadSubject, setUploadSubject] = useState<string>('Inteligência Artificial');
  const [uploadTitle, setUploadTitle] = useState<string>('');
  const [uploadMode, setUploadMode] = useState<'file' | 'video' | 'video_url' | 'text' | 'lecture'>('file');
  const [videoUrlInput, setVideoUrlInput] = useState<string>('');
  const [rawTextContent, setRawTextContent] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredDocs = documents.filter((doc) => {
    const title = (doc.title || '').toLowerCase();
    const subject = (doc.subject || '').toLowerCase();
    const q = searchQuery.toLowerCase();
    const matchesSearch = title.includes(q) || subject.includes(q);

    if (!matchesSearch) return false;

    if (filterType === 'ALL') return true;
    if (filterType === 'DOCS') return ['PDF', 'DOCX', 'PPTX', 'TXT', 'MARKDOWN'].includes(doc.source_type);
    if (filterType === 'VIDEO') return doc.source_type === 'VIDEO';
    if (filterType === 'IMAGES') return doc.source_type === 'IMAGE';
    if (filterType === 'AUDIO') return doc.source_type === 'AUDIO';
    if (filterType === 'LECTURES') return doc.source_type === 'LECTURE_AUDIO';
    if (filterType === 'NOTES') return doc.source_type === 'NOTE';
    return true;
  });

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

  const handleSubmitUpload = () => {
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
        subject: uploadSubject || 'Geral',
        source_type: 'VIDEO',
        title: baseTitle,
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
        subject: uploadSubject || 'Geral',
        source_type: 'TXT',
        title: baseTitle,
      });
      setIsUploadModalOpen(false);
      setRawTextContent('');
      setSelectedFile(null);
      setUploadTitle('');
      return;
    }

    if (!selectedFile) return;

    const ext = selectedFile.name.split('.').pop()?.toLowerCase() || '';
    const isVideo = ['mp4', 'webm', 'mkv', 'mov', 'avi'].includes(ext);

    const reader = new FileReader();
    reader.onload = () => {
      const resultStr = reader.result as string;
      const commaIdx = resultStr.indexOf(',');
      const b64 = commaIdx !== -1 ? resultStr.substring(commaIdx + 1).trim() : resultStr.trim();
      onUpload({
        filename: selectedFile.name,
        content_base64: b64,
        subject: uploadSubject || 'Geral',
        source_type: isVideo ? 'VIDEO' : undefined,
        title: uploadTitle || selectedFile.name,
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
      {/* 1. Header & Actions */}
      <div className="border-b border-white/[0.08] bg-[#0e161c]/90 px-6 py-4 backdrop-blur-md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
                <BookOpen className="h-4 w-4" />
              </div>
              <h1 className="text-base font-semibold tracking-tight text-white">
                Biblioteca de Estudo
              </h1>
              <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-xs text-zinc-400">
                {documents.length} materiais
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-400">
              Repositório central de artigos científicos, diapositivos, imagens, transcrições e notas.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                id="study-refresh-library-btn"
                onClick={onRefresh}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-300 transition hover:bg-white/[0.08] hover:text-white cursor-pointer shadow-sm"
                title="Atualizar Catálogo"
              >
                <RotateCw className="h-3.5 w-3.5" />
                <span>Atualizar</span>
              </button>
            )}
            <button
              onClick={() => setIsUploadModalOpen(true)}
              data-testid="study-upload-doc-btn"
              className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/40 bg-cyan-500/15 px-3.5 py-2 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-500/25 shadow-sm cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>+ Adicionar conteúdo</span>
            </button>
          </div>
        </div>

        {/* 2. Filters & Search Bar */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-2">
          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="mr-1 text-zinc-500 flex items-center gap-1">
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
                className={`rounded-md px-2.5 py-1 transition ${
                  filterType === f.id
                    ? 'bg-cyan-400/15 text-cyan-200 border border-cyan-400/30 font-medium'
                    : 'text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[240px] flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Pesquisar por título ou disciplina..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-full rounded-lg border border-white/[0.08] bg-black/40 pl-8 pr-3 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-cyan-400/40"
            />
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

      {/* 3. Materials Grid / List */}
      <div className="flex-1 overflow-y-auto p-6">
        {filteredDocs.length === 0 ? (
          <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.08] bg-white/[0.01] p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.04] text-zinc-500 mb-3">
              <BookOpen className="h-6 w-6" />
            </div>
            <p className="text-sm font-semibold text-zinc-300">
              Começa por carregar um artigo, vídeo, slides ou gravação.
            </p>
            <p className="mt-1 text-xs text-zinc-500 max-w-md">
              Adiciona um artigo científico em PDF, vídeo explicativo (.mp4, .webm), imagem, áudio ou nota de texto para iniciar a aprendizagem multimodal.
            </p>
            <button
              onClick={() => setIsUploadModalOpen(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/20 transition"
            >
              <FileUp className="h-4 w-4" />
              <span>Carregar Primeiro Material</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {filteredDocs.map((doc) => {
              const progressPct = Math.round(doc.reading_progress?.progress_percent || 0);
              const isEn = (doc.language || 'en').toLowerCase().startsWith('en');
              const isVideo = doc.source_type === 'VIDEO';
              const videoDuration = (doc.metadata as any)?.video?.duration_seconds || (doc.metadata as any)?.duration_seconds;
              const videoDurationStr = videoDuration ? `${Math.floor(videoDuration / 60)}:${Math.floor(videoDuration % 60).toString().padStart(2, '0')}` : null;
              const lastWatched = (doc.metadata as any)?.video_progress?.last_watched_at;

              return (
                <div
                  key={doc.document_id}
                  className="group relative flex flex-col justify-between rounded-xl border border-white/[0.08] bg-[#0e151b]/80 p-5 transition hover:border-white/20 hover:bg-[#121c24]/90 shadow-sm"
                >
                  <div>
                    {/* Top Row: Type & Language & Pages / Duration */}
                    <div className="flex items-center justify-between gap-2 mb-2 text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className={`flex items-center gap-1 rounded px-2 py-0.5 font-medium border ${
                          isVideo ? 'bg-purple-500/10 text-purple-300 border-purple-500/20' : 'bg-white/[0.05] text-cyan-300 border-white/5'
                        }`}>
                          {getSourceIcon(doc.source_type)}
                          <span>{doc.source_type}</span>
                        </span>
                        <span className="rounded bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 border border-white/5">
                          {isEn ? 'English' : 'Português'}
                        </span>
                      </div>
                      {isVideo ? (
                        <span className="text-[11px] text-zinc-400 font-mono">
                          ⏱️ {videoDurationStr || 'Vídeo'}
                        </span>
                      ) : (
                        <span className="text-[11px] text-zinc-500">
                          {doc.page_count} {doc.page_count === 1 ? 'página' : 'páginas'}
                        </span>
                      )}
                    </div>

                    {/* Title & Subject */}
                    <h2
                      onClick={() => onOpenDocument(doc.document_id, 'reader')}
                      className="text-sm font-semibold text-white group-hover:text-cyan-200 transition-colors cursor-pointer line-clamp-2"
                      title={doc.title}
                    >
                      {doc.title}
                    </h2>
                    <p className="mt-1 text-xs text-zinc-400 flex items-center gap-1">
                      <span className="text-zinc-500">Disciplina:</span> {doc.subject}
                    </p>

                    {/* Reading / Watching Progress */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="text-zinc-500">{isVideo ? 'Visualização' : 'Progresso de Leitura'}</span>
                        <span className="font-mono text-zinc-300">
                          {progressPct}% {isVideo ? 'assistido' : ''}
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className={`h-full transition-all duration-300 rounded-full ${isVideo ? 'bg-purple-400' : 'bg-cyan-400'}`}
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                      {isVideo && lastWatched && (
                        <p className="mt-1 text-[10px] text-zinc-500 font-mono">
                          Última visualização: {new Date(lastWatched).toLocaleDateString('pt-PT')}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Bottom Controls */}
                  <div className="mt-5 pt-3 border-t border-white/[0.06] flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <Clock className="h-3 w-3" />
                      <span>{new Date(doc.updated_at || doc.created_at).toLocaleDateString('pt-PT')}</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => onOpenDocument(doc.document_id, 'summary')}
                        className="rounded-md px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition"
                        title="Ver Resumo e Argument Map"
                      >
                        Resumo
                      </button>
                      <button
                        onClick={() => onOpenDocument(doc.document_id, 'quiz')}
                        className="rounded-md px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition"
                        title="Fazer Quiz"
                      >
                        Quiz
                      </button>
                      <button
                        onClick={() => onOpenDocument(doc.document_id, 'reader')}
                        className="inline-flex items-center gap-1 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20 transition cursor-pointer"
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

      {/* 4. Upload Modal with Drag & Drop */}
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

            {/* Subject & Title */}
            <div className="space-y-3 text-xs mb-4">
              <div>
                <label className="block text-zinc-400 mb-1">Disciplina / Unidade Curricular</label>
                <input
                  type="text"
                  value={uploadSubject}
                  onChange={(e) => setUploadSubject(e.target.value)}
                  placeholder="ex: Inteligência Artificial, Engenharia de Software..."
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-1.5 text-zinc-200 outline-none focus:border-cyan-400/40"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1">Título Personalizado (Opcional)</label>
                <input
                  type="text"
                  data-testid="study-upload-title-input"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="ex: Aula Teórica Raft Consensus ou Artigo SOTA"
                  className="w-full rounded-lg border border-white/[0.08] bg-black/40 px-3 py-1.5 text-zinc-200 outline-none focus:border-cyan-400/40"
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
                  {selectedFile ? selectedFile.name : 'Arrasta o documento para aqui ou clica para procurar'}
                </p>
                <p className="mt-1 text-[11px] text-zinc-500">
                  PDF, DOCX, PPTX, TXT, Markdown, PNG, JPG (máx. 100 MB)
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.pptx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp"
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
                  {selectedFile ? selectedFile.name : 'Arrasta o ficheiro de vídeo para aqui ou clica para procurar'}
                </p>
                <p className="mt-1 text-[11px] text-zinc-400">
                  Formatos suportados: .mp4, .webm, .mkv, .mov, .avi
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  accept=".mp4,.webm,.mkv,.mov,.avi"
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
    </div>
  );
};
