import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  Sparkles,
  Search,
  Bookmark,
  Send,
  PanelRightClose,
  PanelRightOpen,
  FastForward,
  Rewind,
  Eye,
  Clock,
  Image as ImageIcon
} from 'lucide-react';
import type {
  StudyDocument,
  StudyReadingNote,
  StudyHighlight,
  ExplanationLevel,
  VideoTranscriptSegment,
  VideoChapter,
  VideoKeyframe,
  VideoSearchResult
} from './types';
import { useWebSocket } from '../../context/WebSocketContext';

export interface StudyVideoReaderViewProps {
  document: StudyDocument;
  onUpdateProgress?: (page: number, section: string, percent: number) => void;
  onSaveHighlight?: (page: number, text: string, color?: string) => void;
  onSaveNote?: (page: number, text: string, note: string) => void;
  readingNotes?: StudyReadingNote[];
  highlights?: StudyHighlight[];
  onTranslate?: (text: string) => Promise<string>;
  onExplain?: (
    text: string,
    level: ExplanationLevel
  ) => Promise<{ literal: string; simple: string; context_importance: string }>;
  onAskVideo?: (query: string, timestamp?: number) => Promise<{ answer: string; sources: string[]; evidence_status?: string; frame_ref?: string }>;
  onExplainMoment?: (timestamp: number) => Promise<{ explanation: string; topic: string; frame_id?: string; timestamp_str: string }>;
  onExplainVisual?: (timestamp: number) => Promise<{ visual_type: string; explanation: string; frame_id?: string; timestamp_str: string }>;
}

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00:00';
  const total = Math.floor(seconds);
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hrs > 0) {
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

export const StudyVideoReaderView: React.FC<StudyVideoReaderViewProps> = ({
  document,
  onUpdateProgress,
  onSaveHighlight: _onSaveHighlight,
  onSaveNote,
  readingNotes = [],
  highlights: _highlights = [],
  onTranslate,
  onExplain,
  onAskVideo,
  onExplainMoment,
  onExplainVisual,
}) => {
  const { sendClientMessage } = useWebSocket();

  // Video Element Ref
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoContainerRef = useRef<HTMLDivElement | null>(null);
  const transcriptContainerRef = useRef<HTMLDivElement | null>(null);

  // Video State
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(() => {
    const meta = document.metadata as any;
    return meta?.video?.duration_seconds || meta?.duration_seconds || 0;
  });
  const [volume, setVolume] = useState<number>(1);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [autoScrollTranscript, setAutoScrollTranscript] = useState<boolean>(true);

  // Video Data from metadata
  const videoMeta = (document.metadata as any)?.video || {};
  const transcriptSegments: VideoTranscriptSegment[] = useMemo(() => {
    const raw =
      videoMeta?.transcript_segments ||
      videoMeta?.transcript?.segments ||
      videoMeta?.transcript ||
      (document.metadata as any)?.transcript_segments ||
      [];
    if (!Array.isArray(raw)) return [];
    return raw.map((s: any, idx: number) => ({
      id: s.id ?? s.segment_id ?? idx + 1,
      start: Number(s.start ?? s.start_time ?? 0),
      end: Number(s.end ?? s.end_time ?? 0),
      text: s.text || '',
      confidence: s.confidence,
      words: s.words,
    }));
  }, [videoMeta, document]);

  const chapters: VideoChapter[] = useMemo(() => {
    const raw = videoMeta?.chapters || (document.metadata as any)?.chapters || [];
    if (!Array.isArray(raw)) return [];
    return raw.map((c: any) => ({
      title: c.title || '',
      start_time: Number(c.start_time ?? c.start_seconds ?? 0),
      end_time: Number(c.end_time ?? c.end_seconds ?? 0),
      summary: c.summary || '',
      key_concepts: c.key_concepts || [],
    }));
  }, [videoMeta, document]);

  const keyframes: VideoKeyframe[] = useMemo(() => {
    return videoMeta?.keyframes || (document.metadata as any)?.keyframes || [];
  }, [videoMeta, document]);

  // Sidebar / Assistant State
  const [assistantPanelOpen, setAssistantPanelOpen] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'transcript' | 'chapters' | 'visuals' | 'ask' | 'notes'>('transcript');

  // Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<VideoSearchResult[]>([]);

  // Q&A / Ask the Video
  const [chatMessages, setChatMessages] = useState<Array<{
    sender: 'user' | 'jarvis';
    text: string;
    timestamp?: number;
    timestampStr?: string;
    frameId?: string;
    evidenceStatus?: string;
  }>>([
    {
      sender: 'jarvis',
      text: 'Olá! Sou o assistente multimodal do Jarvis. Podes perguntar qualquer coisa sobre os conceitos, demonstrações ou diagramas deste vídeo.',
    }
  ]);
  const [askInput, setAskInput] = useState<string>('');
  const [isAsking, setIsAsking] = useState<boolean>(false);

  // Contextual Assistant Result
  const [contextActionLoading, setContextActionLoading] = useState<boolean>(false);
  const [activeContextResult, setActiveContextResult] = useState<{
    type: 'moment' | 'visual' | 'translation' | 'explanation';
    title: string;
    content: string;
    timestamp?: number;
    timestampStr?: string;
    frameId?: string;
    details?: string[];
  } | null>(null);

  // Note creation at current moment
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [newNoteText, setNewNoteText] = useState<string>('');

  // Initial resume from saved progress
  useEffect(() => {
    const savedTime = (document.reading_progress as any)?.scroll_position ||
      (document.metadata as any)?.video_progress?.current_timestamp || 0;
    if (savedTime > 0 && videoRef.current) {
      videoRef.current.currentTime = savedTime;
      setCurrentTime(savedTime);
    }
  }, [document]);

  // Current Chapter lookup
  const currentChapter = useMemo(() => {
    return chapters.find(c => currentTime >= c.start_time && currentTime <= c.end_time);
  }, [chapters, currentTime]);

  // Current Transcript Segment lookup
  const currentSegment = useMemo(() => {
    return transcriptSegments.find(s => currentTime >= s.start && currentTime <= s.end);
  }, [transcriptSegments, currentTime]);

  // Auto-scroll transcript container when segment changes
  useEffect(() => {
    if (!autoScrollTranscript || !transcriptContainerRef.current || !currentSegment) return;
    const el = window.document.getElementById(`segment-${currentSegment.id}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentSegment, autoScrollTranscript]);

  // Handle Play/Pause
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }, []);

  // Handle Seek
  const handleSeek = (seconds: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = Math.max(0, Math.min(seconds, duration || 999999));
    setCurrentTime(seconds);
  };

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA'].includes(target?.tagName)) return;

      if (e.key === ' ' || e.key === 'k') {
        e.preventDefault();
        togglePlay();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handleSeek(currentTime - 5);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleSeek(currentTime + 5);
      } else if (e.key === 'm') {
        e.preventDefault();
        setIsMuted(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentTime, togglePlay]);

  // Sync mute state to video
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = isMuted;
    }
  }, [isMuted]);

  // Sync playback rate
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  // Debounced progress saver
  const lastSavedTimeRef = useRef<number>(0);
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const now = videoRef.current.currentTime;
    setCurrentTime(now);

    // Save every 5 seconds or upon significant change
    if (Math.abs(now - lastSavedTimeRef.current) >= 5) {
      lastSavedTimeRef.current = now;
      const progressPercent = duration > 0 ? (now / duration) * 100 : 0;
      if (onUpdateProgress) {
        onUpdateProgress(1, currentChapter?.title || 'Geral', progressPercent);
      }
      if (sendClientMessage) {
        sendClientMessage({
          type: 'study_update_video_progress',
          document_id: document.document_id,
          timestamp: now,
          progress_percent: progressPercent,
        });
      }
    }
  };

  // Handle Fullscreen
  const toggleFullscreen = () => {
    if (!videoContainerRef.current) return;
    if (!isFullscreen) {
      if (videoContainerRef.current.requestFullscreen) {
        videoContainerRef.current.requestFullscreen();
      }
    } else {
      if (window.document.exitFullscreen) {
        window.document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  };

  // Search Transcript
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const q = searchQuery.toLowerCase();
    const hits: VideoSearchResult[] = [];
    transcriptSegments.forEach(seg => {
      if (seg.text.toLowerCase().includes(q)) {
        hits.push({
          segment_id: seg.id,
          start: seg.start,
          end: seg.end,
          timestamp_str: formatTime(seg.start),
          text: seg.text,
        });
      }
    });
    setSearchResults(hits);
  }, [searchQuery, transcriptSegments]);

  // Contextual Action: O que está a acontecer aqui?
  const handleExplainMoment = async () => {
    setContextActionLoading(true);
    try {
      if (onExplainMoment) {
        const res = await onExplainMoment(currentTime);
        setActiveContextResult({
          type: 'moment',
          title: `O que está a acontecer? (${formatTime(currentTime)})`,
          content: res.explanation,
          timestamp: currentTime,
          timestampStr: res.timestamp_str,
          frameId: res.frame_id,
        });
      } else {
        // Fallback explanation from local context
        const txt = currentSegment?.text || 'Sem fala registada neste timestamp.';
        setActiveContextResult({
          type: 'moment',
          title: `O que está a acontecer? (${formatTime(currentTime)})`,
          content: `No timestamp ${formatTime(currentTime)}, o vídeo foca em: "${txt}". ${currentChapter ? `Inserido no capítulo "${currentChapter.title}".` : ''}`,
          timestamp: currentTime,
          timestampStr: formatTime(currentTime),
        });
      }
    } catch (err: any) {
      console.error('Error explaining moment:', err);
    } finally {
      setContextActionLoading(false);
    }
  };

  // Contextual Action: Explicar o que está no ecrã
  const handleExplainVisual = async () => {
    setContextActionLoading(true);
    try {
      if (onExplainVisual) {
        const res = await onExplainVisual(currentTime);
        setActiveContextResult({
          type: 'visual',
          title: `Análise Visual (${formatTime(currentTime)})`,
          content: res.explanation,
          timestamp: currentTime,
          timestampStr: res.timestamp_str,
          frameId: res.frame_id,
        });
      } else {
        const nearestFrame = keyframes.reduce((prev, curr) => {
          return Math.abs(curr.timestamp - currentTime) < Math.abs(prev.timestamp - currentTime) ? curr : prev;
        }, keyframes[0]);
        setActiveContextResult({
          type: 'visual',
          title: `Análise Visual (${formatTime(currentTime)})`,
          content: nearestFrame ? `Quadro visual capturado com confiança ${(nearestFrame.confidence * 100).toFixed(0)}%. ${nearestFrame.is_slide ? 'Identificado como diapositivo/slide de apresentação.' : 'Quadro de demonstração.'}` : 'Sem análise visual detalhada para este timestamp.',
          timestamp: currentTime,
          timestampStr: formatTime(currentTime),
          frameId: nearestFrame?.frame_id,
        });
      }
    } catch (err: any) {
      console.error('Error explaining visual:', err);
    } finally {
      setContextActionLoading(false);
    }
  };

  // Contextual Action: Traduzir segmento para PT-PT
  const handleTranslateSegment = async (text: string, timestamp: number) => {
    setContextActionLoading(true);
    try {
      if (onTranslate) {
        const trans = await onTranslate(text);
        setActiveContextResult({
          type: 'translation',
          title: `Tradução PT-PT (${formatTime(timestamp)})`,
          content: trans,
          timestamp: timestamp,
          timestampStr: formatTime(timestamp),
        });
      } else {
        setActiveContextResult({
          type: 'translation',
          title: `Tradução PT-PT (${formatTime(timestamp)})`,
          content: text,
          timestamp: timestamp,
          timestampStr: formatTime(timestamp),
        });
      }
    } catch (err: any) {
      console.error('Error translating:', err);
    } finally {
      setContextActionLoading(false);
    }
  };

  // Contextual Action: Explicar conceito do segmento
  const handleExplainSegment = async (text: string, timestamp: number) => {
    setContextActionLoading(true);
    try {
      if (onExplain) {
        const exp = await onExplain(text, 'Intermédio');
        setActiveContextResult({
          type: 'explanation',
          title: `Explicação Conceitual (${formatTime(timestamp)})`,
          content: exp.simple || exp.literal,
          details: [exp.context_importance].filter(Boolean),
          timestamp: timestamp,
          timestampStr: formatTime(timestamp),
        });
      } else {
        setActiveContextResult({
          type: 'explanation',
          title: `Explicação Conceitual (${formatTime(timestamp)})`,
          content: `Conceito em análise: "${text}". Relevante para a consolidação pedagógica do tema.`,
          timestamp: timestamp,
          timestampStr: formatTime(timestamp),
        });
      }
    } catch (err: any) {
      console.error('Error explaining segment:', err);
    } finally {
      setContextActionLoading(false);
    }
  };

  // Save Note / Moment
  const handleSaveMomentNote = () => {
    if (!newNoteText.trim()) return;
    const txt = newNoteText.trim();
    if (onSaveNote) {
      onSaveNote(1, currentSegment?.text || `Momento @ ${formatTime(currentTime)}`, txt);
    }
    if (sendClientMessage) {
      sendClientMessage({
        type: 'study_save_video_note',
        document_id: document.document_id,
        timestamp: currentTime,
        note_text: txt,
        selected_text: currentSegment?.text,
      });
    }
    setNewNoteText('');
    setIsAddingNote(false);
    setActiveTab('notes');
  };

  // Ask the Video handler
  const handleAskSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!askInput.trim() || isAsking) return;
    const q = askInput.trim();
    setAskInput('');
    setChatMessages(prev => [...prev, { sender: 'user', text: q }]);
    setIsAsking(true);

    try {
      if (onAskVideo) {
        const res = await onAskVideo(q, currentTime);
        setChatMessages(prev => [
          ...prev,
          {
            sender: 'jarvis',
            text: res.answer,
            timestamp: currentTime,
            timestampStr: formatTime(currentTime),
            evidenceStatus: res.evidence_status,
            frameId: res.frame_ref,
          }
        ]);
      } else {
        // Local synthesis answer
        const hits = transcriptSegments.filter(s => s.text.toLowerCase().includes(q.toLowerCase()));
        let reply = '';
        let hitTs: number | undefined;
        let hitStr: string | undefined;

        if (hits.length > 0) {
          hitTs = hits[0].start;
          hitStr = formatTime(hits[0].start);
          reply = `Com base no vídeo aos ${hitStr}, o apresentador refere: "${hits[0].text}".`;
        } else if (currentSegment) {
          hitTs = currentSegment.start;
          hitStr = formatTime(currentSegment.start);
          reply = `No contexto atual (${hitStr}), o foco é "${currentSegment.text}".`;
        } else {
          reply = 'Não foram encontradas menções diretas a esse termo na transcrição deste vídeo.';
        }

        setChatMessages(prev => [
          ...prev,
          {
            sender: 'jarvis',
            text: reply,
            timestamp: hitTs,
            timestampStr: hitStr,
            evidenceStatus: hits.length > 0 ? 'OBSERVED' : 'INSUFFICIENT_EVIDENCE',
          }
        ]);
      }
    } catch (err: any) {
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'jarvis',
          text: `Erro ao consultar vídeo: ${err?.message || 'Falha de comunicação'}`,
        }
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  const videoStreamUrl = `/api/study/document/${document.document_id}/video`;

  return (
    <div data-testid="study-video-reader-view" className="flex h-full flex-col bg-[#0b1015] text-zinc-200 overflow-hidden">
      {/* 1. Header Bar */}
      <div className="flex h-12 items-center justify-between border-b border-white/[0.08] bg-[#0e161c] px-4 shrink-0">
        <div className="flex items-center gap-3 overflow-hidden">
          <span className="flex items-center gap-1.5 rounded bg-purple-500/10 px-2 py-0.5 text-xs font-semibold text-purple-300 border border-purple-500/20">
            <span>VIDEO</span>
          </span>
          <h2 className="truncate text-xs font-semibold text-white sm:text-sm" title={document.title}>
            {document.title}
          </h2>
          {currentChapter && (
            <span className="hidden sm:inline-flex items-center gap-1 rounded bg-white/[0.04] px-2 py-0.5 text-xs text-zinc-400 border border-white/5 truncate max-w-xs">
              <span className="text-zinc-500">Capítulo:</span> {currentChapter.title}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAssistantPanelOpen(!assistantPanelOpen)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition cursor-pointer ${
              assistantPanelOpen
                ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-200'
                : 'border-white/10 bg-white/[0.04] text-zinc-400 hover:text-white'
            }`}
            title="Alternar Painel Jarvis"
          >
            {assistantPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            <span className="hidden sm:inline">Assistente Jarvis</span>
          </button>
        </div>
      </div>

      {/* 2. Main Content Split View */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Column: Video Player & Subtitles & Timeline (Dominant) */}
        <div className="flex flex-1 flex-col overflow-y-auto bg-black p-4">
          <div
            ref={videoContainerRef}
            className="group relative flex flex-col justify-center rounded-xl overflow-hidden bg-[#05080b] border border-white/10 shadow-2xl"
          >
            {/* HTML5 Video Element */}
            <video
              ref={videoRef}
              data-testid="study-video-player"
              src={videoStreamUrl}
              onClick={togglePlay}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={() => {
                if (videoRef.current && videoRef.current.duration) {
                  setDuration(videoRef.current.duration);
                }
              }}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              className="max-h-[68vh] w-full object-contain cursor-pointer"
              playsInline
            />

            {/* In-Video Active Subtitle Overlay */}
            {currentSegment && (
              <div className="pointer-events-none absolute bottom-14 left-0 right-0 flex justify-center px-6">
                <p className="max-w-2xl rounded-lg bg-black/80 px-4 py-1.5 text-center text-xs sm:text-sm font-medium text-white shadow-lg backdrop-blur-md border border-white/10">
                  {currentSegment.text}
                </p>
              </div>
            )}

            {/* Custom Control Overlay (visible on hover or paused) */}
            <div className={`absolute bottom-0 left-0 right-0 flex flex-col bg-gradient-to-t from-black/90 via-black/60 to-transparent p-3 transition-opacity duration-200 ${
              isPlaying ? 'opacity-0 group-hover:opacity-100' : 'opacity-100'
            }`}>
              {/* Progress Scrubber */}
              <div className="relative mb-2 flex items-center">
                <input
                  type="range"
                  min={0}
                  max={duration || 100}
                  step={0.1}
                  value={currentTime}
                  onChange={(e) => handleSeek(parseFloat(e.target.value))}
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-white/20 accent-cyan-400 hover:h-2 transition-all"
                  aria-label="Progresso do vídeo"
                />
                {/* Visual Keyframe markers along timeline */}
                {keyframes.map(kf => {
                  if (!duration) return null;
                  const leftPct = (kf.timestamp / duration) * 100;
                  return (
                    <div
                      key={kf.frame_id}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSeek(kf.timestamp);
                      }}
                      title={`${kf.is_slide ? 'Diapositivo' : 'Quadro'} @ ${kf.timestamp_str}`}
                      className={`absolute top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full cursor-pointer transition-transform hover:scale-150 ${
                        kf.is_slide ? 'bg-amber-400' : 'bg-cyan-400'
                      }`}
                      style={{ left: `${leftPct}%` }}
                    />
                  );
                })}
              </div>

              {/* Bottom Controls Bar */}
              <div className="flex items-center justify-between text-xs text-zinc-300">
                <div className="flex items-center gap-3">
                  <button
                    onClick={togglePlay}
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-white hover:bg-white/20 transition cursor-pointer"
                    title={isPlaying ? 'Pausar (Espaço)' : 'Reproduzir (Espaço)'}
                  >
                    {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 fill-current ml-0.5" />}
                  </button>

                  <button
                    onClick={() => handleSeek(currentTime - 5)}
                    className="flex h-7 w-7 items-center justify-center rounded text-zinc-400 hover:text-white transition"
                    title="Recuar 5s (←)"
                  >
                    <Rewind className="h-3.5 w-3.5" />
                  </button>

                  <button
                    onClick={() => handleSeek(currentTime + 5)}
                    className="flex h-7 w-7 items-center justify-center rounded text-zinc-400 hover:text-white transition"
                    title="Avançar 5s (→)"
                  >
                    <FastForward className="h-3.5 w-3.5" />
                  </button>

                  {/* Volume Control */}
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setIsMuted(!isMuted)}
                      className="text-zinc-400 hover:text-white"
                      title={isMuted ? 'Ativar som (m)' : 'Silenciar (m)'}
                    >
                      {isMuted || volume === 0 ? <VolumeX className="h-4 w-4 text-red-400" /> : <Volume2 className="h-4 w-4" />}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={isMuted ? 0 : volume}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        setVolume(v);
                        setIsMuted(v === 0);
                        if (videoRef.current) videoRef.current.volume = v;
                      }}
                      className="w-16 h-1 accent-cyan-400 cursor-pointer"
                      aria-label="Volume"
                    />
                  </div>

                  {/* Time indicator */}
                  <div className="font-mono text-zinc-300">
                    <span className="text-white font-semibold">{formatTime(currentTime)}</span>
                    <span className="text-zinc-500 mx-1">/</span>
                    <span className="text-zinc-400">{formatTime(duration)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {/* Speed Selector */}
                  <select
                    value={playbackSpeed}
                    onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
                    className="rounded bg-black/60 border border-white/10 px-2 py-1 text-[11px] text-zinc-200 cursor-pointer hover:border-white/20"
                    aria-label="Velocidade de reprodução"
                  >
                    <option value={0.75}>0.75x</option>
                    <option value={1}>1.0x</option>
                    <option value={1.25}>1.25x</option>
                    <option value={1.5}>1.5x</option>
                    <option value={2}>2.0x</option>
                  </select>

                  {/* Fullscreen Button */}
                  <button
                    onClick={toggleFullscreen}
                    className="text-zinc-400 hover:text-white transition cursor-pointer"
                    title={isFullscreen ? 'Sair de ecrã inteiro' : 'Ecrã inteiro'}
                  >
                    {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Contextual Actions Toolbar (Directly under video) */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/[0.08] bg-[#0e161c] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                data-testid="study-btn-explain-moment"
                onClick={handleExplainMoment}
                disabled={contextActionLoading}
                className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-400/20 cursor-pointer disabled:opacity-50"
                title="Explicar o que está a acontecer neste exato momento"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>O que está a acontecer aqui?</span>
              </button>

              <button
                data-testid="study-btn-explain-visual"
                onClick={handleExplainVisual}
                disabled={contextActionLoading}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs font-semibold text-amber-200 transition hover:bg-amber-400/20 cursor-pointer disabled:opacity-50"
                title="Analisar slides, gráficos, diagramas ou código presentes no ecrã"
              >
                <Eye className="h-3.5 w-3.5" />
                <span>Explicar o que está no ecrã</span>
              </button>

              <button
                onClick={() => setIsAddingNote(!isAddingNote)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-400/20 cursor-pointer"
                title="Criar anotação associada a este timestamp"
              >
                <Bookmark className="h-3.5 w-3.5" />
                <span>Guardar momento</span>
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
              <Clock className="h-3.5 w-3.5 text-cyan-400" />
              <span>Timestamp: {formatTime(currentTime)}</span>
            </div>
          </div>

          {/* New Moment Note Input Form (if toggled) */}
          {isAddingNote && (
            <div className="mt-2 rounded-xl border border-emerald-400/30 bg-[#0e1c16] p-3 animate-in fade-in">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-emerald-300">
                  Nova anotação aos {formatTime(currentTime)}
                </span>
                <button
                  onClick={() => setIsAddingNote(false)}
                  className="text-xs text-zinc-400 hover:text-white"
                >
                  Cancelar
                </button>
              </div>
              <textarea
                value={newNoteText}
                onChange={(e) => setNewNoteText(e.target.value)}
                placeholder="Escreve uma nota explicativa sobre este diagrama, conceito ou demonstração..."
                className="w-full h-16 rounded-lg bg-black/40 border border-emerald-400/20 p-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-400"
              />
              <div className="mt-2 flex justify-end">
                <button
                  onClick={handleSaveMomentNote}
                  disabled={!newNoteText.trim()}
                  className="rounded-lg bg-emerald-500 px-3 py-1 text-xs font-semibold text-black hover:bg-emerald-400 disabled:opacity-50 cursor-pointer"
                >
                  Guardar Anotação
                </button>
              </div>
            </div>
          )}

          {/* Context Result Popout Banner */}
          {activeContextResult && (
            <div className="mt-3 rounded-xl border border-cyan-400/30 bg-[#0a1820] p-4 text-xs shadow-lg">
              <div className="flex items-center justify-between pb-2 border-b border-white/10 mb-2">
                <div className="flex items-center gap-2 text-cyan-300 font-semibold">
                  <Sparkles className="h-4 w-4" />
                  <span>{activeContextResult.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (activeContextResult.timestamp !== undefined) {
                        handleSeek(activeContextResult.timestamp);
                      }
                    }}
                    className="font-mono text-[11px] text-cyan-400 hover:underline"
                  >
                    ⏱️ {activeContextResult.timestampStr}
                  </button>
                  <button
                    onClick={() => setActiveContextResult(null)}
                    className="text-zinc-500 hover:text-white font-bold px-1"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <p className="text-zinc-200 whitespace-pre-wrap leading-relaxed">
                {activeContextResult.content}
              </p>

              {activeContextResult.details && activeContextResult.details.length > 0 && (
                <div className="mt-2 pt-2 border-t border-white/5 text-zinc-400 italic">
                  {activeContextResult.details.map((d, i) => (
                    <p key={i}>• {d}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Jarvis Assistant Panel */}
        {assistantPanelOpen && (
          <aside className="flex w-96 flex-col border-l border-white/[0.08] bg-[#0c1217] shrink-0">
            {/* Panel Tabs */}
            <div className="flex border-b border-white/[0.08] bg-[#0e161c] px-2 text-xs">
              <button
                onClick={() => setActiveTab('transcript')}
                className={`flex-1 py-2.5 text-center font-medium border-b-2 transition ${
                  activeTab === 'transcript'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Transcrição
              </button>
              <button
                onClick={() => setActiveTab('chapters')}
                className={`flex-1 py-2.5 text-center font-medium border-b-2 transition ${
                  activeTab === 'chapters'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Capítulos
              </button>
              <button
                onClick={() => setActiveTab('visuals')}
                className={`flex-1 py-2.5 text-center font-medium border-b-2 transition ${
                  activeTab === 'visuals'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Slides ({keyframes.length})
              </button>
              <button
                onClick={() => setActiveTab('ask')}
                className={`flex-1 py-2.5 text-center font-medium border-b-2 transition ${
                  activeTab === 'ask'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Perguntar
              </button>
              <button
                onClick={() => setActiveTab('notes')}
                className={`flex-1 py-2.5 text-center font-medium border-b-2 transition ${
                  activeTab === 'notes'
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Notas
              </button>
            </div>

            {/* TAB 1: Transcrição & Pesquisa Temporal */}
            {activeTab === 'transcript' && (
              <div className="flex flex-1 flex-col overflow-hidden">
                {/* Search Bar */}
                <div className="border-b border-white/[0.08] p-2 bg-[#090e12]">
                  <div className="relative flex items-center">
                    <Search className="absolute left-2.5 h-3.5 w-3.5 text-zinc-400" />
                    <input
                      type="text"
                      data-testid="study-transcript-search-input"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Pesquisar termo na transcrição..."
                      className="w-full rounded-lg bg-white/[0.04] pl-8 pr-8 py-1.5 text-xs text-white placeholder-zinc-500 border border-white/5 focus:outline-none focus:border-cyan-400/50"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="absolute right-2 text-xs text-zinc-500 hover:text-white"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  {searchQuery && (
                    <div className="mt-1 flex items-center justify-between text-[11px] text-zinc-400 px-1">
                      <span>{searchResults.length} ocorrência(s) encontrada(s)</span>
                    </div>
                  )}
                </div>

                {/* Auto-scroll toggle bar */}
                <div className="flex items-center justify-between px-3 py-1.5 text-[11px] text-zinc-500 bg-[#0e161c] border-b border-white/5">
                  <span>Sincronização com o leitor</span>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoScrollTranscript}
                      onChange={(e) => setAutoScrollTranscript(e.target.checked)}
                      className="accent-cyan-400"
                    />
                    <span>Seguir vídeo</span>
                  </label>
                </div>

                {/* Transcript Segments List */}
                <div
                  ref={transcriptContainerRef}
                  data-testid="study-transcript-list"
                  className="flex-1 overflow-y-auto p-3 space-y-2"
                >
                  {transcriptSegments.length === 0 ? (
                    <div className="p-6 text-center text-xs text-zinc-500">
                      Nenhuma transcrição disponível para este vídeo.
                    </div>
                  ) : (
                    transcriptSegments.map((segment) => {
                      const isCurrent = currentTime >= segment.start && currentTime <= segment.end;
                      const isMatchedSearch = searchQuery && segment.text.toLowerCase().includes(searchQuery.toLowerCase());

                      return (
                        <div
                          key={segment.id}
                          id={`segment-${segment.id}`}
                          data-testid={`transcript-segment-${segment.id}`}
                          onClick={() => handleSeek(segment.start)}
                          className={`group rounded-lg p-2.5 text-xs transition cursor-pointer border ${
                            isCurrent
                              ? 'bg-cyan-500/10 border-cyan-400/40 text-cyan-100 shadow-sm'
                              : isMatchedSearch
                              ? 'bg-amber-500/10 border-amber-400/30 text-amber-100'
                              : 'bg-white/[0.02] border-white/[0.04] text-zinc-300 hover:bg-white/[0.05] hover:border-white/10'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-[11px] font-semibold text-cyan-400 group-hover:underline">
                              {formatTime(segment.start)}
                            </span>
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleTranslateSegment(segment.text, segment.start);
                                }}
                                className="rounded px-1.5 py-0.5 text-[10px] bg-white/10 text-zinc-300 hover:text-white"
                                title="Traduzir para PT-PT"
                              >
                                Traduzir
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleExplainSegment(segment.text, segment.start);
                                }}
                                className="rounded px-1.5 py-0.5 text-[10px] bg-white/10 text-cyan-300 hover:text-white"
                                title="Explicar conceito"
                              >
                                Explicar
                              </button>
                            </div>
                          </div>
                          <p className="leading-relaxed">{segment.text}</p>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: Capítulos */}
            {activeTab === 'chapters' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {chapters.length === 0 ? (
                  <div className="p-6 text-center text-xs text-zinc-500">
                    Nenhum capítulo detetado para este vídeo.
                  </div>
                ) : (
                  chapters.map((ch, idx) => {
                    const isCurrent = currentTime >= ch.start_time && currentTime <= ch.end_time;
                    return (
                      <div
                        key={idx}
                        onClick={() => handleSeek(ch.start_time)}
                        className={`rounded-lg p-3 text-xs transition cursor-pointer border ${
                          isCurrent
                            ? 'bg-cyan-500/10 border-cyan-400/40 text-cyan-100'
                            : 'bg-white/[0.02] border-white/[0.04] text-zinc-300 hover:bg-white/[0.05]'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-white">{ch.title}</span>
                          <span className="font-mono text-[11px] text-cyan-400">
                            {formatTime(ch.start_time)}
                          </span>
                        </div>
                        {ch.summary && <p className="text-zinc-400 text-[11px] mt-1">{ch.summary}</p>}
                        {ch.key_concepts && ch.key_concepts.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {ch.key_concepts.map((c, i) => (
                              <span key={i} className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-zinc-400">
                                {c}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* TAB 3: Visuals & Diapositivos */}
            {activeTab === 'visuals' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {keyframes.length === 0 ? (
                  <div className="p-6 text-center text-xs text-zinc-500">
                    Nenhum quadro visual ou slide indexado.
                  </div>
                ) : (
                  keyframes.map((kf) => (
                    <div
                      key={kf.frame_id}
                      onClick={() => handleSeek(kf.timestamp)}
                      className="group overflow-hidden rounded-lg border border-white/[0.08] bg-[#090e12] p-2 transition hover:border-cyan-400/40 cursor-pointer"
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="font-mono text-cyan-400 text-[11px]">
                          ⏱️ {kf.timestamp_str}
                        </span>
                        <span className={`rounded px-1.5 py-0.2 text-[10px] font-medium ${
                          kf.is_slide ? 'bg-amber-500/20 text-amber-300' : 'bg-cyan-500/20 text-cyan-300'
                        }`}>
                          {kf.is_slide ? 'Slide Detetado' : 'Keyframe'}
                        </span>
                      </div>
                      {/* Image snapshot */}
                      <div className="relative aspect-video w-full rounded bg-black/60 overflow-hidden flex items-center justify-center">
                        {kf.image_path ? (
                          <img
                            src={`/api/study/document/${document.document_id}/media/${kf.frame_id}`}
                            alt={kf.frame_id}
                            className="h-full w-full object-contain"
                            onError={(e) => {
                              // Fallback display if media endpoint not ready
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          <div className="flex flex-col items-center justify-center text-zinc-600">
                            <ImageIcon className="h-6 w-6" />
                            <span className="text-[10px] mt-1">{kf.frame_id}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* TAB 4: Perguntar ao Vídeo (Q&A com Citações Temporais) */}
            {activeTab === 'ask' && (
              <div className="flex flex-1 flex-col overflow-hidden">
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {chatMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={`flex flex-col text-xs ${
                        msg.sender === 'user' ? 'items-end' : 'items-start'
                      }`}
                    >
                      <div
                        className={`max-w-[88%] rounded-xl p-3 leading-relaxed ${
                          msg.sender === 'user'
                            ? 'bg-cyan-600 text-white'
                            : 'bg-white/[0.04] border border-white/[0.08] text-zinc-200'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{msg.text}</p>

                        {/* Citation Pill */}
                        {msg.timestamp !== undefined && (
                          <div className="mt-2 flex items-center gap-1.5 pt-1 border-t border-white/10 text-[10px]">
                            <button
                              onClick={() => handleSeek(msg.timestamp!)}
                              className="font-mono text-cyan-300 hover:underline flex items-center gap-1"
                            >
                              <Clock className="h-3 w-3" />
                              <span>Salto temporal: {msg.timestampStr}</span>
                            </button>
                            {msg.evidenceStatus && (
                              <span className="rounded bg-white/10 px-1 text-zinc-400">
                                {msg.evidenceStatus}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {isAsking && (
                    <div className="flex items-center gap-2 text-xs text-zinc-400 italic">
                      <Sparkles className="h-3.5 w-3.5 text-cyan-400 animate-spin" />
                      <span>O Jarvis está a consultar o vídeo e frames...</span>
                    </div>
                  )}
                </div>

                {/* Chat Input */}
                <form
                  onSubmit={handleAskSubmit}
                  className="border-t border-white/[0.08] p-2 bg-[#090e12] flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={askInput}
                    onChange={(e) => setAskInput(e.target.value)}
                    placeholder="Pergunta sobre este vídeo..."
                    className="flex-1 rounded-lg bg-white/[0.04] px-3 py-1.5 text-xs text-white placeholder-zinc-500 border border-white/5 focus:outline-none focus:border-cyan-400/50"
                  />
                  <button
                    type="submit"
                    disabled={!askInput.trim() || isAsking}
                    className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-600 text-white hover:bg-cyan-500 transition disabled:opacity-50"
                  >
                    <Send className="h-3.5 w-3.5" />
                  </button>
                </form>
              </div>
            )}

            {/* TAB 5: Notas & Momentos Guardados */}
            {activeTab === 'notes' && (
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {readingNotes.length === 0 ? (
                  <div className="p-6 text-center text-xs text-zinc-500">
                    Ainda não guardaste momentos nem notas neste vídeo.
                  </div>
                ) : (
                  readingNotes.map((note) => (
                    <div
                      key={note.note_id}
                      className="rounded-lg border border-white/[0.08] bg-[#090e12] p-3 text-xs"
                    >
                      <div className="flex items-center justify-between text-zinc-400 mb-1 text-[11px]">
                        <span className="font-semibold text-emerald-300">Nota de Estudo</span>
                        <span>{new Date(note.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className="text-zinc-200 font-medium mb-1">{note.note}</p>
                      {note.selection && (
                        <p className="text-zinc-400 italic text-[11px] bg-white/[0.02] p-1.5 rounded">
                          "{note.selection}"
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
};
