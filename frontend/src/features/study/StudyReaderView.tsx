import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import 'pdfjs-dist/web/pdf_viewer.css';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Sparkles,
  Languages,
  FileText,
  Highlighter,
  MessageSquarePlus,
  Send,
  Image as ImageIcon,
  Table as TableIcon,
  Compass,
  Copy,
  Check,
  PanelRightClose,
  PanelRightOpen,
  BookOpen,
  HelpCircle,
  List
} from 'lucide-react';
import type {
  StudyDocument,
  StudySection,
  StudyMedia,
  StudyReadingNote,
  StudyHighlight,
  ExplanationLevel
} from './types';

// Configure pdf.js worker using ESM URL
if (typeof window !== 'undefined' && 'Worker' in window) {
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url
    ).toString();
  } catch (err) {
    console.warn('[StudyReader] Failed to initialize PDF.js worker URL:', err);
  }
}

export interface StudyReaderViewProps {
  document: StudyDocument;
  onUpdateProgress?: (page: number, section: string, percent: number) => void;
  onSaveHighlight?: (page: number, text: string, color?: string) => void;
  onSaveNote?: (page: number, text: string, note: string) => void;
  readingNotes?: StudyReadingNote[];
  highlights?: StudyHighlight[];
  onAskPaper?: (query: string) => Promise<{ answer: string; sources: string[] }>;
  onTranslate?: (text: string) => Promise<string>;
  onExplain?: (
    text: string,
    level: ExplanationLevel
  ) => Promise<{ literal: string; simple: string; context_importance: string }>;
  onSummarizeSection?: (sectionId: string) => Promise<{
    main_idea: string;
    key_points: string[];
    terms: string[];
    doubts: string[];
  }>;
  onExplainMedia?: (mediaId: string) => Promise<string>;
  onGetDocumentFile?: () => Promise<{ contentBase64?: string; filename?: string; error?: string }>;
}

// ---------------------------------------------------------------------------
// Single PDF Page Renderer Component
// ---------------------------------------------------------------------------
interface PageRendererProps {
  pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  onVisible: (pageNumber: number) => void;
}

const PageRenderer: React.FC<PageRendererProps> = ({
  pdfDoc,
  pageNumber,
  scale,
  onVisible,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const renderTaskRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 612,
    height: 792,
  });

  // Track page visibility using IntersectionObserver
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
            onVisible(pageNumber);
          }
        }
      },
      { threshold: [0.2, 0.4, 0.6] }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [pageNumber, onVisible]);

  // Render Canvas and Text Layer
  useEffect(() => {
    let isCancelled = false;

    const renderPage = async () => {
      try {
        const page = await pdfDoc.getPage(pageNumber);
        if (isCancelled) return;

        const viewport = page.getViewport({ scale });
        setDimensions({ width: viewport.width, height: viewport.height });

        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        if (renderTaskRef.current) {
          try {
            renderTaskRef.current.cancel();
          } catch {
            // ignore cancellation
          }
        }

        const renderTask = page.render({
          canvasContext: ctx,
          viewport,
          canvas,
        });
        renderTaskRef.current = renderTask;

        await renderTask.promise;
        if (isCancelled) return;

        // Render TextLayer for high-fidelity native text selection
        const textLayerDiv = textLayerRef.current;
        if (textLayerDiv) {
          textLayerDiv.innerHTML = '';
          textLayerDiv.style.width = `${Math.floor(viewport.width)}px`;
          textLayerDiv.style.height = `${Math.floor(viewport.height)}px`;
          textLayerDiv.style.setProperty('--scale-factor', `${scale}`);

          const textContent = await page.getTextContent();
          if (isCancelled) return;

          const textLayer = new pdfjsLib.TextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport,
          });
          await textLayer.render();
        }
      } catch (err: any) {
        if (err?.name !== 'RenderingCancelledException') {
          console.warn(`[StudyReader] Error rendering page ${pageNumber}:`, err);
        }
      }
    };

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // ignore
        }
      }
    };
  }, [pdfDoc, pageNumber, scale]);

  return (
    <div
      ref={containerRef}
      id={`pdf-page-${pageNumber}`}
      data-page-number={pageNumber}
      className="pdf-page-container relative mx-auto my-4 bg-white shadow-2xl rounded-sm transition-all select-text border border-neutral-800/20"
      style={{
        width: `${dimensions.width}px`,
        height: `${dimensions.height}px`,
      }}
    >
      <canvas ref={canvasRef} className="block w-full h-full" />
      <div
        ref={textLayerRef}
        className="textLayer absolute inset-0 select-text pointer-events-auto"
      />
      <div className="absolute bottom-2 right-3 rounded bg-black/60 px-2 py-0.5 text-[10px] font-mono text-gray-300 pointer-events-none">
        p. {pageNumber}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main StudyReaderView Component
// ---------------------------------------------------------------------------
export const StudyReaderView: React.FC<StudyReaderViewProps> = ({
  document,
  onUpdateProgress,
  onSaveHighlight,
  onSaveNote,
  readingNotes = [],
  highlights = [],
  onAskPaper,
  onTranslate,
  onExplain,
  onSummarizeSection,
  onExplainMedia,
  onGetDocumentFile,
}) => {
  // PDF State
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState<number>(document.page_count || 1);
  const [pdfLoading, setPdfLoading] = useState<boolean>(true);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Navigation & Scale State
  const [currentPage, setCurrentPage] = useState<number>(
    document.reading_progress?.current_page || 1
  );
  const [zoomPercent, setZoomPercent] = useState<number>(100);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [sidebarTab, setSidebarTab] = useState<'thumbnails' | 'sections' | 'media'>('sections');
  const [assistantPanelOpen, setAssistantPanelOpen] = useState<boolean>(true);
  const [assistantTab, setAssistantTab] = useState<'assist' | 'ask' | 'media' | 'notes'>('assist');

  // Text Selection & Floating Micro-Toolbar
  const [floatingToolbar, setFloatingToolbar] = useState<{
    text: string;
    x: number;
    y: number;
  } | null>(null);
  const [activeSelectedText, setActiveSelectedText] = useState<string>('');

  // Assistant Content State
  const [isAssistantLoading, setIsAssistantLoading] = useState<boolean>(false);
  const [contextResult, setContextResult] = useState<{
    type: 'translation' | 'explanation' | 'summary' | 'media';
    title: string;
    original?: string;
    translation?: string;
    explanation?: { literal: string; simple: string; context_importance: string };
    summary?: { main_idea: string; key_points: string[]; terms: string[]; doubts: string[] };
    mediaText?: string;
    pageNumber?: number;
  } | null>(null);
  const [explanationLevel, setExplanationLevel] = useState<ExplanationLevel>('Académico');

  // Note creation modal state
  const [noteDialogOpen, setNoteDialogOpen] = useState<boolean>(false);
  const [noteDialogText, setNoteDialogText] = useState<string>('');
  const [noteInputContent, setNoteInputContent] = useState<string>('');

  // Ask Paper Q&A State
  const [askQuery, setAskQuery] = useState<string>('');
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [qaHistory, setQaHistory] = useState<Array<{ query: string; answer: string; sources: string[] }>>([]);

  // Copied feedback
  const [copied, setCopied] = useState<boolean>(false);

  // Viewport Container Ref
  const viewerContainerRef = useRef<HTMLDivElement | null>(null);

  // Active section calculation
  const currentSection = useMemo(() => {
    if (!document.sections || document.sections.length === 0) return null;
    const matches = document.sections.filter(
      (sec) => currentPage >= sec.page_start && currentPage <= sec.page_end
    );
    return matches.length > 0 ? matches[matches.length - 1] : document.sections[0];
  }, [document.sections, currentPage]);

  // Load PDF Document (WebSocket base64 -> HTTP Streaming -> Fallback)
  useEffect(() => {
    let isCancelled = false;
    setPdfLoading(true);
    setPdfError(null);

    const loadPdf = async () => {
      try {
        let pdfData: Uint8Array | null = null;

        // Strategy 1: WebSocket binary payload via onGetDocumentFile
        if (onGetDocumentFile) {
          try {
            const fileRes = await onGetDocumentFile();
            if (fileRes?.contentBase64) {
              const binary = atob(fileRes.contentBase64);
              const bytes = new Uint8Array(binary.length);
              for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
              }
              pdfData = bytes;
            }
          } catch {
            // Fallback to HTTP
          }
        }

        // Strategy 2: HTTP Streaming endpoint from backend sandbox_service
        if (!pdfData) {
          const urlsToTry = [
            `http://localhost:8000/api/study/document/${document.document_id}/file`,
            `/api/study/document/${document.document_id}/file`,
          ];
          for (const url of urlsToTry) {
            try {
              const res = await fetch(url);
              if (res.ok) {
                const buffer = await res.arrayBuffer();
                pdfData = new Uint8Array(buffer);
                break;
              }
            } catch {
              // Try next
            }
          }
        }

        if (isCancelled) return;

        if (pdfData && pdfData.length > 0) {
          const loadingTask = pdfjsLib.getDocument({
            data: pdfData,
            cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/cmaps/',
            cMapPacked: true,
          });
          const doc = await loadingTask.promise;
          if (isCancelled) return;

          setPdfDoc(doc);
          setNumPages(doc.numPages);
          setPdfLoading(false);
          return;
        }

        // If no binary PDF found, we enter semantic fallback mode
        setPdfLoading(false);
      } catch (err: any) {
        if (!isCancelled) {
          console.warn('[StudyReader] PDF load error:', err);
          setPdfError(err?.message || 'Erro ao carregar o ficheiro PDF.');
          setPdfLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      isCancelled = true;
    };
  }, [document.document_id, onGetDocumentFile]);

  // Handle page visibility change and update progress
  const handlePageVisible = useCallback(
    (page: number) => {
      setCurrentPage(page);
      if (onUpdateProgress) {
        const total = numPages > 0 ? numPages : 1;
        const percent = Math.min(100, Math.round((page / total) * 100));
        const secTitle = currentSection ? currentSection.title : `Página ${page}`;
        onUpdateProgress(page, secTitle, percent);
      }
    },
    [numPages, currentSection, onUpdateProgress]
  );

  // Jump to specific page
  const scrollToPage = useCallback((pageNum: number) => {
    const target = Math.max(1, Math.min(pageNum, numPages));
    setCurrentPage(target);
    const el = window.document.getElementById(`pdf-page-${target}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [numPages]);

  // Jump to section
  const scrollToSection = useCallback(
    (sec: StudySection) => {
      scrollToPage(sec.page_start);
    },
    [scrollToPage]
  );

  // Listen to Text Selection in PDF Viewport
  const handleViewportMouseUp = useCallback(() => {
    // Short delay to allow window.getSelection() to settle
    setTimeout(() => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setFloatingToolbar(null);
        return;
      }
      const rawText = selection.toString();
      const text = rawText.trim();
      if (text.length < 2) {
        setFloatingToolbar(null);
        return;
      }

      try {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
          setFloatingToolbar(null);
          return;
        }

        // Check if selection is within the viewer container
        const viewerEl = viewerContainerRef.current;
        if (viewerEl && !viewerEl.contains(range.commonAncestorContainer)) {
          setFloatingToolbar(null);
          return;
        }

        setActiveSelectedText(text);
        setFloatingToolbar({
          text,
          x: Math.max(16, rect.left + rect.width / 2),
          y: Math.max(10, rect.top - 8),
        });
      } catch {
        setFloatingToolbar(null);
      }
    }, 20);
  }, []);

  // Dismiss toolbar on scroll
  const handleScroll = useCallback(() => {
    if (floatingToolbar) {
      setFloatingToolbar(null);
    }
  }, [floatingToolbar]);

  // Contextual Action: Translate strictly selected text
  const handleTranslateSelection = async (textToTranslate?: string) => {
    const text = textToTranslate || activeSelectedText;
    if (!text) return;
    setFloatingToolbar(null);
    setAssistantPanelOpen(true);
    setAssistantTab('assist');
    setIsAssistantLoading(true);

    try {
      let translation = '';
      if (onTranslate) {
        translation = await onTranslate(text);
      } else {
        translation = `Tradução académica: ${text}`;
      }

      setContextResult({
        type: 'translation',
        title: 'Tradução Contextual (PT-PT)',
        original: text,
        translation,
        pageNumber: currentPage,
      });
    } catch (err: any) {
      setContextResult({
        type: 'translation',
        title: 'Tradução Contextual (PT-PT)',
        original: text,
        translation: 'Erro ao processar a tradução contextual.',
        pageNumber: currentPage,
      });
    } finally {
      setIsAssistantLoading(false);
    }
  };

  // Contextual Action: Explain strictly selected text
  const handleExplainSelection = async (level: ExplanationLevel = 'Académico', textToExplain?: string) => {
    const text = textToExplain || activeSelectedText;
    if (!text) return;
    setFloatingToolbar(null);
    setExplanationLevel(level);
    setAssistantPanelOpen(true);
    setAssistantTab('assist');
    setIsAssistantLoading(true);

    try {
      if (onExplain) {
        const explanation = await onExplain(text, level);
        setContextResult({
          type: 'explanation',
          title: `Explicação (${level})`,
          original: text,
          explanation,
          pageNumber: currentPage,
        });
      } else {
        setContextResult({
          type: 'explanation',
          title: `Explicação (${level})`,
          original: text,
          explanation: {
            literal: text,
            simple: `Em termos simples: ${text}`,
            context_importance: 'Fundamentação metodológica essencial do artigo.',
          },
          pageNumber: currentPage,
        });
      }
    } catch (err: any) {
      setContextResult({
        type: 'explanation',
        title: `Explicação (${level})`,
        original: text,
        explanation: {
          literal: text,
          simple: 'Não foi possível gerar a explicação.',
          context_importance: '',
        },
        pageNumber: currentPage,
      });
    } finally {
      setIsAssistantLoading(false);
    }
  };

  // Contextual Action: Summarize Current Section
  const handleSummarizeSection = async () => {
    if (!currentSection) return;
    setFloatingToolbar(null);
    setAssistantPanelOpen(true);
    setAssistantTab('assist');
    setIsAssistantLoading(true);

    try {
      if (onSummarizeSection) {
        const sum = await onSummarizeSection(currentSection.section_id);
        setContextResult({
          type: 'summary',
          title: `Resumo: ${currentSection.title}`,
          summary: sum,
          pageNumber: currentPage,
        });
      } else {
        setContextResult({
          type: 'summary',
          title: `Resumo: ${currentSection.title}`,
          summary: {
            main_idea: `A secção ${currentSection.title} estabelece o rigor empírico do estudo.`,
            key_points: [
              'Formalização experimental através de métricas de referência.',
              'Adoção de dados empíricos com validação estatística.',
            ],
            terms: ['Baseline', 'Ablation Study', 'Significance'],
            doubts: ['Quais as condições sob dados não balanceados?'],
          },
          pageNumber: currentPage,
        });
      }
    } catch {
      // ignore
    } finally {
      setIsAssistantLoading(false);
    }
  };

  // Contextual Action: Highlight selected text
  const handleHighlightSelection = (color: string = '#fef08a') => {
    if (!activeSelectedText || !onSaveHighlight) return;
    onSaveHighlight(currentPage, activeSelectedText, color);
    setFloatingToolbar(null);
  };

  // Contextual Action: Open Note Dialog
  const handleOpenNoteDialog = () => {
    setNoteDialogText(activeSelectedText);
    setNoteInputContent('');
    setNoteDialogOpen(true);
    setFloatingToolbar(null);
  };

  const handleSaveNoteSubmit = () => {
    if (!noteInputContent.trim() || !onSaveNote) return;
    onSaveNote(currentPage, noteDialogText, noteInputContent.trim());
    setNoteDialogOpen(false);
    setNoteInputContent('');
    setNoteDialogText('');
  };

  // Action: Ask Paper Submit
  const handleAskPaperSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!askQuery.trim() || isAsking) return;
    const query = askQuery.trim();
    setIsAsking(true);

    try {
      if (onAskPaper) {
        const res = await onAskPaper(query);
        setQaHistory((prev) => [...prev, { query, answer: res.answer, sources: res.sources }]);
      } else {
        setQaHistory((prev) => [
          ...prev,
          {
            query,
            answer: `Com base em "${document.title}", o método proposto aborda este ponto através da extração semântica e validação quantitativa.`,
            sources: [`p. ${currentPage}`, `§ ${currentSection?.title || 'Methodology'}`],
          },
        ]);
      }
      setAskQuery('');
    } catch {
      setQaHistory((prev) => [
        ...prev,
        {
          query,
          answer: 'Não foi possível obter resposta no momento.',
          sources: ['N/A'],
        },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  // Action: Explain Media (Figure / Table)
  const handleExplainMedia = async (media: StudyMedia) => {
    setAssistantPanelOpen(true);
    setAssistantTab('assist');
    setIsAssistantLoading(true);

    try {
      if (onExplainMedia) {
        const text = await onExplainMedia(media.media_id);
        setContextResult({
          type: 'media',
          title: `Interpretação: ${media.title || (media.media_type === 'table' ? 'Tabela' : 'Figura')}`,
          mediaText: text,
          pageNumber: media.page_number,
        });
      } else {
        setContextResult({
          type: 'media',
          title: `Interpretação: ${media.title || (media.media_type === 'table' ? 'Tabela' : 'Figura')}`,
          mediaText: media.explanation || (
            media.evidence_status === 'OBSERVED'
              ? 'Figura verificada no artigo: ilustra o comportamento comparativo entre os modelos.'
              : 'INSUFFICIENT_EVIDENCE: Detalhes visuais da imagem requerem resolução adicional.'
          ),
          pageNumber: media.page_number,
        });
      }
    } finally {
      setIsAssistantLoading(false);
    }
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentScale = (zoomPercent / 100) * 1.35;

  return (
    <div className="flex h-full w-full overflow-hidden bg-[#0d1217] text-gray-200">
      {/* ============================================================ */}
      {/* MAIN READER AREA (70% PDF CANVAS + TOP CONTROLS)            */}
      {/* ============================================================ */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0 border-r border-[#a1bebf]/15">
        {/* Compact PDF Navigation Bar */}
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[#a1bebf]/15 bg-[#0f171f] px-4 py-2 shrink-0 z-20">
          {/* Left: Sidebar Toggle, Document Title, Language */}
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className={`rounded p-1.5 transition ${
                sidebarOpen ? 'bg-cyan-500/20 text-cyan-300' : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
              title="Alternar barra lateral"
            >
              <List className="h-4 w-4" />
            </button>

            <span className="text-xs font-semibold text-white truncate max-w-[200px] sm:max-w-xs md:max-w-sm" title={document.title}>
              {document.title}
            </span>

            {document.language?.toLowerCase() === 'en' && (
              <span className="rounded bg-sky-400/10 px-1.5 py-0.5 text-[10px] font-medium text-sky-300 border border-sky-400/20 flex items-center gap-1 shrink-0">
                <Languages className="h-3 w-3" /> EN
              </span>
            )}
          </div>

          {/* Center: Page Navigation Controls */}
          <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-black/40 px-2 py-1">
            <button
              onClick={() => scrollToPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="p-1 text-gray-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition"
              title="Página anterior"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            <div className="flex items-center gap-1 text-xs">
              <span className="text-gray-400">Pág.</span>
              <input
                type="number"
                min={1}
                max={numPages}
                value={currentPage}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val)) scrollToPage(val);
                }}
                className="w-10 rounded border border-white/15 bg-black/60 px-1 py-0.5 text-center text-xs text-white focus:border-cyan-400 focus:outline-none"
              />
              <span className="text-gray-400">/ {numPages}</span>
            </div>

            <button
              onClick={() => scrollToPage(currentPage + 1)}
              disabled={currentPage >= numPages}
              className="p-1 text-gray-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition"
              title="Página seguinte"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* Right: Zoom & Layout Controls */}
          <div className="flex items-center gap-2">
            <div className="flex items-center rounded-lg border border-white/10 bg-black/40 px-1 py-0.5">
              <button
                onClick={() => setZoomPercent((z) => Math.max(50, z - 15))}
                className="p-1 text-gray-400 hover:text-white transition"
                title="Diminuir Zoom"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="w-12 text-center font-mono text-[11px] text-gray-300">
                {zoomPercent}%
              </span>
              <button
                onClick={() => setZoomPercent((z) => Math.min(200, z + 15))}
                className="p-1 text-gray-400 hover:text-white transition"
                title="Aumentar Zoom"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoomPercent(100)}
                className="ml-1 rounded px-1.5 py-0.5 text-[10px] text-gray-400 hover:bg-white/10 hover:text-white transition"
                title="Repor Zoom 100%"
              >
                100%
              </button>
            </div>

            {/* Toggle Assistant Panel Button */}
            <button
              id="study-toggle-assistant-btn"
              onClick={() => setAssistantPanelOpen((v) => !v)}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                assistantPanelOpen
                  ? 'border-cyan-500/30 bg-cyan-500/15 text-cyan-300 shadow-sm'
                  : 'border-white/10 bg-black/40 text-gray-400 hover:text-white'
              }`}
              title="Alternar Painel Assistente Jarvis"
            >
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Assistente</span>
              {assistantPanelOpen ? (
                <PanelRightClose className="h-3.5 w-3.5 opacity-70" />
              ) : (
                <PanelRightOpen className="h-3.5 w-3.5 opacity-70" />
              )}
            </button>
          </div>
        </header>

        {/* Section Navigation Strip */}
        {document.sections && document.sections.length > 0 && (
          <nav
            aria-label="Navegação de secções do artigo"
            className="flex items-center gap-2 overflow-x-auto border-b border-[#a1bebf]/10 bg-[#0b1016] px-4 py-1.5 scrollbar-none shrink-0 z-10"
          >
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider shrink-0 flex items-center gap-1">
              <Compass className="h-3 w-3 text-cyan-400" /> Secções:
            </span>
            {document.sections.map((sec) => {
              const isCurrent = currentSection?.section_id === sec.section_id;
              return (
                <button
                  key={sec.section_id}
                  onClick={() => scrollToSection(sec)}
                  className={`px-2.5 py-0.5 rounded text-xs whitespace-nowrap transition font-medium ${
                    isCurrent
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                  }`}
                >
                  {sec.title}
                </button>
              );
            })}
          </nav>
        )}

        {/* Reader Body: Sidebar + PDF Pages Viewport */}
        <div className="flex flex-1 overflow-hidden relative min-h-0">
          {/* Left Collapsible Strip: Sections / Thumbnails / Media */}
          {sidebarOpen && (
            <aside className="w-56 shrink-0 border-r border-[#a1bebf]/10 bg-[#0b1016] flex flex-col z-10">
              <div className="flex items-center border-b border-white/10 p-1 text-xs">
                <button
                  onClick={() => setSidebarTab('sections')}
                  className={`flex-1 py-1.5 font-medium rounded transition ${
                    sidebarTab === 'sections'
                      ? 'bg-cyan-500/20 text-cyan-300'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Índice
                </button>
                <button
                  onClick={() => setSidebarTab('thumbnails')}
                  className={`flex-1 py-1.5 font-medium rounded transition ${
                    sidebarTab === 'thumbnails'
                      ? 'bg-cyan-500/20 text-cyan-300'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Páginas
                </button>
                {document.media && document.media.length > 0 && (
                  <button
                    onClick={() => setSidebarTab('media')}
                    className={`flex-1 py-1.5 font-medium rounded transition ${
                      sidebarTab === 'media'
                        ? 'bg-cyan-500/20 text-cyan-300'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Fig/Tab
                  </button>
                )}
              </div>

              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {sidebarTab === 'sections' && (
                  <div className="space-y-1">
                    {document.sections && document.sections.length > 0 ? (
                      document.sections.map((sec) => (
                        <button
                          key={sec.section_id}
                          onClick={() => scrollToSection(sec)}
                          className={`w-full text-left rounded p-2 text-xs transition ${
                            currentSection?.section_id === sec.section_id
                              ? 'bg-cyan-500/15 text-cyan-300 font-semibold border-l-2 border-cyan-400'
                              : 'text-gray-300 hover:bg-white/5'
                          }`}
                        >
                          <div className="truncate">{sec.title}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">
                            Páginas {sec.page_start} - {sec.page_end}
                          </div>
                        </button>
                      ))
                    ) : (
                      <p className="p-3 text-xs text-gray-500">Nenhuma secção detetada.</p>
                    )}
                  </div>
                )}

                {sidebarTab === 'thumbnails' && (
                  <div className="space-y-2">
                    {Array.from({ length: numPages }).map((_, i) => {
                      const pNum = i + 1;
                      const isCurr = currentPage === pNum;
                      return (
                        <button
                          key={pNum}
                          onClick={() => scrollToPage(pNum)}
                          className={`w-full text-center rounded p-2 text-xs border transition ${
                            isCurr
                              ? 'border-cyan-400/60 bg-cyan-950/30 text-cyan-300 font-semibold'
                              : 'border-white/10 bg-black/40 text-gray-400 hover:border-white/30'
                          }`}
                        >
                          <div className="h-16 flex items-center justify-center border border-dashed border-white/10 rounded mb-1 bg-white/[0.02]">
                            <FileText className="h-6 w-6 opacity-40" />
                          </div>
                          <span>Página {pNum}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {sidebarTab === 'media' && (
                  <div className="space-y-2">
                    {document.media && document.media.map((m) => (
                      <button
                        key={m.media_id}
                        onClick={() => {
                          scrollToPage(m.page_number);
                          handleExplainMedia(m);
                        }}
                        className="w-full text-left rounded border border-white/10 bg-black/30 p-2 text-xs hover:border-cyan-400/40 transition"
                      >
                        <div className="flex items-center gap-1.5 font-semibold text-gray-200 mb-1">
                          {m.media_type === 'table' ? (
                            <TableIcon className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <ImageIcon className="h-3.5 w-3.5 text-cyan-400" />
                          )}
                          <span className="truncate">{m.title || 'Figura/Tabela'}</span>
                        </div>
                        <div className="text-[10px] text-gray-500">Pág. {m.page_number}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </aside>
          )}

          {/* Central PDF Canvas Viewport */}
          <main
            ref={viewerContainerRef}
            onMouseUp={handleViewportMouseUp}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto overflow-x-auto bg-[#181d24] p-4 sm:p-6 relative select-text"
          >
            {pdfLoading && (
              <div className="flex h-96 flex-col items-center justify-center gap-3 text-cyan-400">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                <p className="text-xs text-gray-400">A carregar o artigo científico em alta resolução...</p>
              </div>
            )}

            {/* Error fallback alert */}
            {Boolean(pdfError) && (
              <div className="max-w-2xl mx-auto my-4 rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-300">
                <h4 className="font-semibold mb-1">Aviso de Leitura do Ficheiro</h4>
                <p className="text-gray-300 mb-2">{pdfError}</p>
                <p className="text-[11px] text-gray-400">
                  A carregar a camada semântica com layout de alta densidade.
                </p>
              </div>
            )}

            {/* Native PDF Pages Continuous Vertical Rendering */}
            {Boolean(pdfDoc) && !pdfLoading ? (
              <div className="flex flex-col items-center select-text">
                {Array.from({ length: numPages }).map((_, idx) => (
                  <PageRenderer
                    key={idx + 1}
                    pdfDoc={pdfDoc!}
                    pageNumber={idx + 1}
                    scale={currentScale}
                    onVisible={handlePageVisible}
                  />
                ))}
              </div>
            ) : (
              !pdfLoading && (
                /* High-fidelity Semantic Paper Presentation (when binary PDF is unavailable) */
                <div className="max-w-3xl mx-auto bg-[#0f171f] rounded-lg border border-white/10 p-8 shadow-2xl space-y-6">
                  <header className="border-b border-white/10 pb-6">
                    <h1 className="text-xl font-bold text-white tracking-tight leading-snug">
                      {document.title}
                    </h1>
                    {Boolean(document.metadata?.authors) && (
                      <p className="mt-2 text-xs text-gray-400">
                        {String(document.metadata.authors)}
                      </p>
                    )}
                    {Boolean(document.metadata?.abstract) && (
                      <div className="mt-4 rounded-md border border-cyan-400/20 bg-cyan-950/20 p-4">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-cyan-400 mb-1">
                          Abstract
                        </h4>
                        <p className="text-xs text-gray-300 leading-relaxed">
                          {String(document.metadata.abstract)}
                        </p>
                      </div>
                    )}
                  </header>

                  {/* Render Paragraphs */}
                  <div className="space-y-4">
                    {document.extracted_text ? (
                      <div className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap select-text">
                        {document.extracted_text}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400">Nenhum texto disponível para este artigo.</p>
                    )}
                  </div>
                </div>
              )
            )}
          </main>

          {/* Floating Contextual Micro-Toolbar on Text Selection */}
          {Boolean(floatingToolbar) && (
            <div
              id="study-selection-toolbar"
              className="fixed z-50 flex items-center gap-1 rounded-lg border border-cyan-500/40 bg-[#0f1722]/95 px-2 py-1.5 shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 pointer-events-auto"
              style={{
                top: `${floatingToolbar!.y}px`,
                left: `${floatingToolbar!.x}px`,
                transform: 'translate(-50%, -100%)',
              }}
            >
              <button
                id="study-toolbar-translate-btn"
                onClick={() => handleTranslateSelection()}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-cyan-300 hover:bg-cyan-500/20 transition"
                title="Traduzir excerto selecionado para Português (PT-PT)"
              >
                <Languages className="h-3.5 w-3.5 text-cyan-400" />
                <span>Traduzir</span>
              </button>

              <div className="h-4 w-px bg-white/20" />

              <button
                id="study-toolbar-explain-academic-btn"
                onClick={() => handleExplainSelection('Académico')}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-amber-300 hover:bg-amber-500/20 transition"
                title="Explicar conceito ao nível académico"
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-400" />
                <span>Explicar</span>
              </button>

              <div className="h-4 w-px bg-white/20" />

              <button
                id="study-toolbar-summarize-btn"
                onClick={handleSummarizeSection}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20 transition"
                title="Resumir a secção atual do artigo"
              >
                <FileText className="h-3.5 w-3.5 text-emerald-400" />
                <span>Resumir</span>
              </button>

              <div className="h-4 w-px bg-white/20" />

              <button
                id="study-toolbar-highlight-btn"
                onClick={() => handleHighlightSelection()}
                className="p-1 rounded text-yellow-300 hover:bg-yellow-400/20 transition"
                title="Destacar texto"
              >
                <Highlighter className="h-3.5 w-3.5" />
              </button>

              <button
                id="study-toolbar-note-btn"
                onClick={handleOpenNoteDialog}
                className="p-1 rounded text-purple-300 hover:bg-purple-400/20 transition"
                title="Adicionar anotação de página"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ============================================================ */}
      {/* RIGHT ASSISTANT PANEL: JARVIS COMPANION (~30% WIDTH)         */}
      {/* ============================================================ */}
      {assistantPanelOpen && (
        <aside
          id="study-assistant-panel"
          className="w-80 md:w-96 shrink-0 flex flex-col bg-[#0e141c] border-l border-[#a1bebf]/15 transition-all z-20"
        >
          {/* Assistant Header & Mode Tabs */}
          <header className="border-b border-white/10 p-3 bg-[#0b1016]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
                <Sparkles className="h-4 w-4 text-cyan-400" />
                <span>Assistente Jarvis</span>
              </div>
              <button
                onClick={() => setAssistantPanelOpen(false)}
                className="rounded p-1 text-gray-400 hover:text-white hover:bg-white/10 transition"
                title="Fechar painel Jarvis"
              >
                <PanelRightClose className="h-4 w-4" />
              </button>
            </div>

            <nav aria-label="Navegação do assistente" className="flex items-center rounded-lg border border-white/10 bg-black/40 p-0.5 text-xs">
              <button
                onClick={() => setAssistantTab('assist')}
                className={`flex-1 py-1 text-center font-medium rounded transition ${
                  assistantTab === 'assist'
                    ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Assistência
              </button>
              <button
                onClick={() => setAssistantTab('ask')}
                className={`flex-1 py-1 text-center font-medium rounded transition ${
                  assistantTab === 'ask'
                    ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Perguntar
              </button>
              <button
                onClick={() => setAssistantTab('media')}
                className={`flex-1 py-1 text-center font-medium rounded transition ${
                  assistantTab === 'media'
                    ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Figuras
              </button>
              <button
                onClick={() => setAssistantTab('notes')}
                className={`flex-1 py-1 text-center font-medium rounded transition ${
                  assistantTab === 'notes'
                    ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Notas ({readingNotes.length})
              </button>
            </nav>
          </header>

          {/* Assistant Body Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Loading Indicator */}
            {isAssistantLoading && (
              <div className="flex items-center gap-2 rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-3 text-xs text-cyan-300">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                <span>A analisar o artigo com rigor científico...</span>
              </div>
            )}

            {/* TAB 1: CONTEXT ASSISTANCE (Translation, Explanation, Summary) */}
            {assistantTab === 'assist' && (
              contextResult ? (
                <div className="space-y-4 animate-in fade-in duration-200">
                  {/* Result Header Badge */}
                  <div className="flex items-center justify-between">
                    <span className="rounded-full bg-cyan-500/15 border border-cyan-500/30 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-300 uppercase tracking-wider">
                      {contextResult.title}
                    </span>
                    {contextResult.pageNumber && (
                      <span className="text-[10px] text-gray-500 font-mono">
                        Pág. {contextResult.pageNumber}
                      </span>
                    )}
                  </div>

                  {/* Original English Text Block */}
                  {Boolean(contextResult.original) && (
                    <div className="rounded-md border border-white/10 bg-black/40 p-3">
                      <div className="flex items-center justify-between text-[10px] font-semibold uppercase text-gray-500 mb-1">
                        <span>Original (EN)</span>
                      </div>
                      <p className="text-xs text-gray-300 italic leading-relaxed">
                        "{contextResult.original}"
                      </p>
                    </div>
                  )}

                  {/* Translation Result Card */}
                  {contextResult.type === 'translation' && Boolean(contextResult.translation) && (
                    <div className="rounded-md border border-cyan-400/30 bg-cyan-950/20 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-cyan-400">
                          Tradução Contextual (PT-PT)
                        </span>
                        <button
                          onClick={() => handleCopyText(contextResult.translation!)}
                          className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-white transition"
                        >
                          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                          <span>{copied ? 'Copiado' : 'Copiar'}</span>
                        </button>
                      </div>
                      <p className="text-xs text-white leading-relaxed font-sans">
                        {contextResult.translation}
                      </p>
                      <div className="pt-2 border-t border-cyan-400/10 text-[10px] text-gray-400">
                        Nota: Termos científicos, acrónimos e fórmulas preservados.
                      </div>
                    </div>
                  )}

                  {/* Explanation Result Card with 3 Level Toggle */}
                  {contextResult.type === 'explanation' && Boolean(contextResult.explanation) && (
                    <div className="rounded-md border border-amber-400/30 bg-amber-950/20 p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-amber-300">
                          Nível de Explicação
                        </span>
                        <div className="flex rounded border border-white/10 bg-black/40 p-0.5 text-[10px]">
                          {(['Básico', 'Intermédio', 'Académico'] as ExplanationLevel[]).map((lvl) => (
                            <button
                              key={lvl}
                              onClick={() => handleExplainSelection(lvl, contextResult.original)}
                              className={`px-2 py-0.5 rounded transition ${
                                explanationLevel === lvl
                                  ? 'bg-amber-500/20 text-amber-300 font-semibold'
                                  : 'text-gray-400 hover:text-gray-200'
                              }`}
                            >
                              {lvl}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="text-xs text-gray-200 leading-relaxed">
                          {contextResult.explanation!.simple}
                        </div>
                        {Boolean(contextResult.explanation!.context_importance) && (
                          <div className="rounded bg-black/30 p-2 text-[11px] text-gray-400 border border-white/5">
                            <span className="font-semibold text-amber-200/80">Relevância: </span>
                            {contextResult.explanation!.context_importance}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Section Summary Result Card */}
                  {contextResult.type === 'summary' && Boolean(contextResult.summary) && (
                    <div className="rounded-md border border-emerald-400/30 bg-emerald-950/20 p-4 space-y-3">
                      <div>
                        <h4 className="text-xs font-semibold text-emerald-400 mb-1">Ideia Principal</h4>
                        <p className="text-xs text-gray-200 leading-relaxed">
                          {contextResult.summary!.main_idea}
                        </p>
                      </div>

                      {contextResult.summary!.key_points.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-emerald-400 mb-1">Pontos-Chave</h4>
                          <ul className="list-disc pl-4 space-y-1 text-xs text-gray-300">
                            {contextResult.summary!.key_points.map((pt, i) => (
                              <li key={i}>{pt}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {contextResult.summary!.terms.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-emerald-400 mb-1">Termos Relevantes</h4>
                          <div className="flex flex-wrap gap-1">
                            {contextResult.summary!.terms.map((t, i) => (
                              <span
                                key={i}
                                className="rounded bg-emerald-400/10 px-1.5 py-0.5 text-[10px] text-emerald-300 border border-emerald-400/20"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Media Interpretation Result Card */}
                  {contextResult.type === 'media' && Boolean(contextResult.mediaText) && (
                    <div className="rounded-md border border-sky-400/30 bg-sky-950/20 p-4 space-y-2">
                      <p className="text-xs text-gray-200 leading-relaxed">
                        {contextResult.mediaText}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                /* Default State when no selection has been analyzed yet */
                <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-center space-y-3">
                  <div className="flex h-10 w-10 mx-auto items-center justify-center rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                    <BookOpen className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white">Leitura Ativa & Contextual</h4>
                    <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                      Seleciona qualquer frase ou parágrafo no documento para traduzir diretamente para Português (PT-PT), pedir explicações em 3 níveis ou resumir a secção.
                    </p>
                  </div>
                  {currentSection && (
                    <button
                      onClick={handleSummarizeSection}
                      className="w-full rounded-md border border-cyan-500/30 bg-cyan-500/10 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-500/20 transition"
                    >
                      Resumir secção atual ({currentSection.title})
                    </button>
                  )}
                </div>
              )
            )}

            {/* TAB 2: ASK PAPER (RAG Q&A with Citations) */}
            {assistantTab === 'ask' && (
              <div className="space-y-4">
                <form onSubmit={handleAskPaperSubmit} className="space-y-2">
                  <label className="text-xs font-medium text-gray-300 block">
                    Pergunta sobre o artigo:
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={askQuery}
                      onChange={(e) => setAskQuery(e.target.value)}
                      placeholder="Qual a metodologia utilizada?..."
                      className="flex-1 rounded-md border border-white/15 bg-black/50 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={isAsking || !askQuery.trim()}
                      className="rounded-md bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-40 transition"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </form>

                {/* Q&A History */}
                <div className="space-y-3">
                  {qaHistory.length > 0 ? (
                    qaHistory.map((item, idx) => (
                      <div key={idx} className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2 text-xs">
                        <div className="font-semibold text-cyan-300 flex items-center gap-1.5">
                          <HelpCircle className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                          <span>{item.query}</span>
                        </div>
                        <p className="text-gray-200 leading-relaxed pl-5">
                          {item.answer}
                        </p>
                        {item.sources && item.sources.length > 0 && (
                          <div className="pl-5 pt-1 flex flex-wrap gap-1">
                            {item.sources.map((src, sIdx) => (
                              <span key={sIdx} className="rounded bg-white/5 border border-white/10 px-1.5 py-0.5 text-[10px] font-mono text-gray-400">
                                {src}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-gray-500 text-center py-6">
                      Ainda não colocou nenhuma questão sobre este artigo.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: MEDIA (Figures & Tables) */}
            {assistantTab === 'media' && (
              <div className="space-y-3">
                {document.media && document.media.length > 0 ? (
                  document.media.map((media) => (
                    <div
                      key={media.media_id}
                      className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-semibold text-white">
                          {media.media_type === 'table' ? (
                            <TableIcon className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <ImageIcon className="h-3.5 w-3.5 text-cyan-400" />
                          )}
                          <span>{media.title || (media.media_type === 'table' ? 'Tabela' : 'Figura')}</span>
                        </div>
                        <span className="text-[10px] text-gray-500 font-mono">Pág. {media.page_number}</span>
                      </div>

                      {media.caption && (
                        <p className="text-[11px] text-gray-400 italic leading-snug">
                          {media.caption}
                        </p>
                      )}

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[10px] font-mono text-cyan-300">
                          {media.evidence_status}
                        </span>
                        <button
                          onClick={() => handleExplainMedia(media)}
                          className="rounded border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-[11px] font-medium text-cyan-300 hover:bg-cyan-400/20 transition"
                        >
                          Interpretar
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-500 text-center py-6">
                    Nenhuma figura ou tabela identificada neste documento.
                  </p>
                )}
              </div>
            )}

            {/* TAB 4: NOTES & HIGHLIGHTS */}
            {assistantTab === 'notes' && (
              <div className="space-y-3">
                {readingNotes.length > 0 || highlights.length > 0 ? (
                  <>
                    {readingNotes.map((note) => (
                      <div key={note.note_id} className="rounded-lg border border-purple-500/20 bg-purple-950/10 p-3 text-xs space-y-1">
                        <div className="flex items-center justify-between text-[10px] text-purple-300 font-medium">
                          <span>Anotação • Pág. {note.page}</span>
                          <span>{note.created_at}</span>
                        </div>
                        {note.selection && (
                          <p className="text-[11px] text-gray-400 italic line-clamp-2">
                            "{note.selection}"
                          </p>
                        )}
                        <p className="text-gray-200 font-sans">{note.note}</p>
                      </div>
                    ))}

                    {highlights.map((hl) => (
                      <div key={hl.highlight_id} className="rounded-lg border border-yellow-500/20 bg-yellow-950/10 p-2.5 text-xs">
                        <div className="text-[10px] text-yellow-300 font-medium mb-1">
                          Destaque • Pág. {hl.page}
                        </div>
                        <p className="text-gray-200 italic">"{hl.selected_text}"</p>
                      </div>
                    ))}
                  </>
                ) : (
                  <p className="text-xs text-gray-500 text-center py-6">
                    Ainda não guardou destaques ou notas neste artigo.
                  </p>
                )}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* ============================================================ */}
      {/* NOTE DIALOG MODAL                                            */}
      {/* ============================================================ */}
      {noteDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-white/15 bg-[#101720] p-5 shadow-2xl space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4 text-cyan-400" />
              <span>Adicionar Anotação de Estudo</span>
            </h3>

            {Boolean(noteDialogText) && (
              <div className="rounded bg-black/40 p-2.5 text-xs text-gray-400 italic border border-white/5 line-clamp-3">
                "{noteDialogText}"
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">A sua anotação:</label>
              <textarea
                value={noteInputContent}
                onChange={(e) => setNoteInputContent(e.target.value)}
                placeholder="Escreve aqui o teu apontamento ou questão sobre esta passagem..."
                rows={4}
                className="w-full rounded-md border border-white/15 bg-black/60 p-2.5 text-xs text-white placeholder-gray-500 focus:border-cyan-400 focus:outline-none"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setNoteDialogOpen(false)}
                className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-gray-400 hover:text-white"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveNoteSubmit}
                disabled={!noteInputContent.trim()}
                className="rounded-md bg-cyan-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-40"
              >
                Guardar Anotação
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
