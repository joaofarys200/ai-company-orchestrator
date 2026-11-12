import React, { useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Brain,
  FilePlus2,
  FolderOpen,
  GraduationCap,
  HelpCircle,
  Layers,
  Mic,
  Sparkles,
  Upload,
  Video,
} from 'lucide-react';
import type { StudyCollection, StudyDocument } from './types';
import type { StudyTab } from './StudyContainer';
import { PanelEmptyState } from '../../components/ui';

export interface StudyLandingViewProps {
  documents: StudyDocument[];
  collections: StudyCollection[];
  activeDocument: StudyDocument | null;
  onSelectDocument: (doc: StudyDocument, targetTab?: StudyTab) => void;
  onNavigateTab: (tab: StudyTab) => void;
  onDropFiles?: (files: FileList) => void;
}

export const StudyLandingView: React.FC<StudyLandingViewProps> = ({
  documents,
  collections,
  activeDocument,
  onSelectDocument,
  onNavigateTab,
  onDropFiles,
}) => {
  const [dragActive, setDragActive] = useState(false);

  const sortedRecent = [...documents].sort((a, b) => {
    const aTime = a.reading_progress?.last_read_at || a.updated_at || a.created_at || '';
    const bTime = b.reading_progress?.last_read_at || b.updated_at || b.created_at || '';
    return bTime.localeCompare(aTime);
  });

  const featuredDoc = activeDocument || sortedRecent[0] || null;
  const recentDocs = sortedRecent.slice(0, 6);

  return (
    <div
      data-testid="study-landing-view"
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        if (e.dataTransfer.files?.length && onDropFiles) {
          onDropFiles(e.dataTransfer.files);
        }
      }}
      className={`h-full overflow-y-auto bg-[#080c12] p-5 md:p-6 text-slate-200 transition ${
        dragActive ? 'ring-2 ring-inset ring-sky-400/50 bg-sky-950/15' : ''
      }`}
    >
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Top Hero Row: Continue Studying + Import Dropzone */}
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,1fr)]">
          <section className="flex flex-col justify-between rounded-xl border border-slate-800/90 bg-[#0b111a] p-5">
            {featuredDoc ? (
              <>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-sky-400">
                    <BookOpen className="h-3.5 w-3.5" />
                    <span>Continuar Leitura</span>
                    <span className="rounded border border-slate-700 bg-[#080c12] px-1.5 py-0.5 text-[10px] text-slate-300">
                      {featuredDoc.source_type}
                    </span>
                  </div>
                  <h2 className="text-lg font-semibold text-slate-100 leading-snug">{featuredDoc.title}</h2>
                  <p className="text-xs text-slate-400">
                    {featuredDoc.subject || 'Sem disciplina'} · {featuredDoc.page_count || 1} pág.
                    {featuredDoc.sections?.length ? ` · ${featuredDoc.sections.length} secções` : ''}
                  </p>
                  {typeof featuredDoc.reading_progress?.progress_percent === 'number' && (
                    <div className="pt-2">
                      <div className="mb-1 flex items-center justify-between text-[11px] text-slate-400">
                        <span>Progresso de leitura</span>
                        <span className="font-mono text-sky-300">{Math.round(featuredDoc.reading_progress.progress_percent)}%</span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-sky-400 transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, featuredDoc.reading_progress.progress_percent))}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onSelectDocument(featuredDoc, 'reader')}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-500 transition cursor-pointer"
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                    <span>Abrir no Leitor</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectDocument(featuredDoc, 'generated_doc')}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 hover:bg-sky-500/20 transition cursor-pointer"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Documento IA</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectDocument(featuredDoc, 'summary')}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0f1722] px-3 py-2 text-xs font-medium text-slate-300 hover:text-white transition cursor-pointer"
                  >
                    <span>Síntese</span>
                  </button>
                </div>
              </>
            ) : (
              <div className="flex h-full flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-sky-400">
                    <GraduationCap className="h-3.5 w-3.5" />
                    <span>Jarvis Study Engine</span>
                  </div>
                  <h2 className="mt-2 text-lg font-semibold text-slate-100">Começa o teu espaço de estudo</h2>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">
                    Carrega PDFs académicos, slides, vídeos ou gravações para ler com apoio contextual local e gerar documentos, flashcards e avaliações.
                  </p>
                </div>
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => onNavigateTab('library')}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-sky-500 cursor-pointer"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    <span>Carregar Material na Biblioteca</span>
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Drag & Drop Quick Upload Card */}
          <section className="flex flex-col justify-between rounded-xl border border-dashed border-slate-700/90 bg-[#0b111a]/80 p-5">
            <div className="space-y-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-sky-400/25 bg-sky-500/10 text-sky-300">
                <FilePlus2 className="h-4.5 w-4.5" />
              </div>
              <h3 className="text-sm font-semibold text-slate-100">Importar Material ou Aula</h3>
              <p className="text-xs leading-relaxed text-slate-400">
                Arrasta PDF, DOCX, Markdown, áudio, imagens ou vídeos diretamente para aqui, ou abre a Biblioteca para ligar pastas e URLs.
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onNavigateTab('library')}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0f1722] px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-sky-400/35 hover:text-sky-200 cursor-pointer"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Abrir Biblioteca ({documents.length})</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigateTab('lectures')}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-[#0f1722] px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white cursor-pointer"
              >
                <Mic className="h-3.5 w-3.5 text-amber-400" />
                <span>Gravar Aula</span>
              </button>
            </div>
          </section>
        </div>

        {/* Practice & Study Modes Strip */}
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Praticar & Avaliar</h3>
            <span className="text-[11px] text-slate-500">Modos de aprendizagem ativa</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(
              [
                { tab: 'flashcards' as StudyTab, label: 'Estudar: Flashcards', desc: 'Revisão espaçada (SM-2) e edição', icon: Layers },
                { tab: 'active_recall' as StudyTab, label: 'Estudar: Recordação', desc: 'Questões abertas fundamentadas', icon: Brain },
                { tab: 'quiz' as StudyTab, label: 'Avaliar: Quizzes & Exame', desc: 'Testes adaptativos e transferência', icon: HelpCircle },
                { tab: 'adaptive' as StudyTab, label: 'Sessão Diária & Progresso', desc: 'Fila adaptativa e métricas de domínio', icon: Sparkles },
              ] as const
            ).map((card) => {
              const Icon = card.icon;
              return (
                <button
                  key={card.tab}
                  type="button"
                  onClick={() => onNavigateTab(card.tab)}
                  className="flex items-start gap-3 rounded-xl border border-slate-800/90 bg-[#0b111a] p-3.5 text-left transition hover:border-sky-500/35 hover:bg-[#0f1722] cursor-pointer"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-800 bg-[#080c12] text-sky-300">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-100">{card.label}</p>
                    <p className="mt-0.5 text-[11px] text-slate-400">{card.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* Collections Quick Strip (only when collections exist) */}
        {collections.length > 0 && (
          <section className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Coleções & Disciplinas ({collections.length})
              </h3>
              <button
                type="button"
                onClick={() => onNavigateTab('library')}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-300 hover:text-sky-200 cursor-pointer"
              >
                <span>Gerir na Biblioteca</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
              {collections.slice(0, 4).map((col) => (
                <button
                  key={col.collection_id}
                  type="button"
                  onClick={() => onNavigateTab('library')}
                  className="flex items-center gap-3 rounded-lg border border-slate-800/90 bg-[#0b111a] px-3.5 py-2.5 text-left hover:border-sky-500/30 hover:bg-[#0f1722] cursor-pointer"
                >
                  <FolderOpen className="h-4 w-4 shrink-0 text-sky-400" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-slate-100">{col.name}</p>
                    <p className="truncate text-[10px] text-slate-500">
                      {col.subject || 'Geral'} · {col.document_ids?.length || 0} materiais
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Recent Materials List */}
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Materiais Recentes ({documents.length})
            </h3>
            {documents.length > 0 && (
              <button
                type="button"
                onClick={() => onNavigateTab('library')}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-300 hover:text-sky-200 cursor-pointer"
              >
                <span>Ver todos na Biblioteca</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>

          {recentDocs.length === 0 ? (
            <PanelEmptyState
              icon={BookOpen}
              title="Ainda não tens materiais de estudo"
              description="Carrega um PDF, slides ou vídeo para iniciar a leitura assistida e geração documental."
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-800/90 bg-[#0b111a] divide-y divide-slate-800/70">
              {recentDocs.map((doc) => (
                <div
                  key={doc.document_id}
                  onClick={() => onSelectDocument(doc, 'reader')}
                  className="flex items-center justify-between gap-4 px-4 py-2.5 hover:bg-[#0f1722] transition cursor-pointer"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    {doc.source_type === 'VIDEO' ? (
                      <Video className="h-4 w-4 shrink-0 text-amber-400" />
                    ) : (
                      <BookOpen className="h-4 w-4 shrink-0 text-sky-400" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-semibold text-slate-100">{doc.title}</p>
                      <p className="truncate text-[11px] text-slate-500">
                        {doc.source_type} · {doc.subject || 'Sem disciplina'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectDocument(doc, 'generated_doc');
                      }}
                      className="rounded border border-slate-700 bg-[#080c12] px-2 py-1 text-[10px] font-medium text-sky-300 hover:border-sky-400/40 cursor-pointer"
                    >
                      Documento IA
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectDocument(doc, 'reader');
                      }}
                      className="rounded border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[10px] font-semibold text-sky-200 hover:bg-sky-500/20 cursor-pointer"
                    >
                      Abrir
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
