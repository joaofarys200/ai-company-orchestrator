import React, { useState, useEffect, useRef } from 'react';
import { useAppSession } from '../../context/AppSessionContext';
import {
  Bot,
  User,
  Trash2,
  Sparkles,
  Terminal,
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
  Plus,
  Maximize2,
  Minimize2,
  Copy,
  Check,
  Users,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChatSidebar } from './ChatSidebar';
import { SystemConsolePanel } from './SystemConsolePanel';
import { ChatPromptInput } from './ChatPromptInput';
import { ChatAttachmentBar } from './ChatAttachmentBar';
import { ChatStudyResultCard } from './ChatStudyResultCard';
import { AgentLibrary } from '../settings/AgentLibrary';
import type { ChatMessage } from '../../protocol/websocket';
import type { ChatAttachment } from './types';

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

export const ChatPanel: React.FC = () => {
  const {
    chatMessages,
    systemLogs,
    clearSystemLogs,
    chatSessions,
    activeSessionId,
    switchChatSession,
    createNewChatSession,
    deleteChatSession,
    renameChatSession,
    promptHistory,
    projectFiles,
    activeTemplate,
    voiceStatus,
    sendDirective,
    toggleVoice,
    clearChat,
    isConnected,
    studyOperations,
    navigateToStudyTarget,
    cancelStudyOperation,
  } = useAppSession();

  const [activeTab, setActiveTab] = useState<'chat' | 'system'>('chat');
  const [showSidebar, setShowSidebar] = useState(false);
  const [isWide, setIsWide] = useState(false);
  const [agentLibraryOpen, setAgentLibraryOpen] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    try {
      navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.warn('[ChatPanel] Falha ao copiar texto:', err);
    }
  };

  const logRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioObjectUrlRef = useRef<string | null>(null);
  const playedAudioIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (audioObjectUrlRef.current) {
        URL.revokeObjectURL(audioObjectUrlRef.current);
        audioObjectUrlRef.current = null;
      }
    };
  }, []);

  // Auto-scroll to bottom of chat on new messages
  useEffect(() => {
    if (activeTab === 'chat' && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [chatMessages, activeTab]);

  // Autoplay TTS audio when a message arrives with base64 audio (Blob URL compatible with media-src 'self' blob:)
  useEffect(() => {
    const lastMsg = chatMessages[chatMessages.length - 1];
    if (lastMsg && lastMsg.audio && !playedAudioIds.current.has(lastMsg.id)) {
      playedAudioIds.current.add(lastMsg.id);
      try {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        if (audioObjectUrlRef.current) {
          URL.revokeObjectURL(audioObjectUrlRef.current);
          audioObjectUrlRef.current = null;
        }
        const binary = atob(lastMsg.audio);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'audio/mp3' });
        const audioUrl = URL.createObjectURL(blob);
        audioObjectUrlRef.current = audioUrl;
        audioRef.current = new Audio(audioUrl);
        audioRef.current.play().catch((err) => {
          console.warn('[TTS] Autoplay blocked or failed:', err);
        });
      } catch (e) {
        console.error('[TTS] Error playing audio:', e);
      }
    }
  }, [chatMessages]);

  const activeSession = chatSessions.find((s) => s.id === activeSessionId);
  const isHandsFree = voiceStatus !== 'offline';

  const handleSendMessage = (text: string, attachments: ChatAttachment[]) => {
    sendDirective(text, attachments);
  };

  const renderMessageContent = (msg: ChatMessage) => {
    let text = escapeHtml(msg.content);
    // Format markdown bold, italics, code, and newlines
    text = text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="text-cyan-200/90">$1</em>')
      .replace(
        /`([^`]+)`/g,
        '<code class="px-1.5 py-0.5 rounded bg-black/50 border border-white/10 text-cyan-300 font-mono text-xs select-text">$1</code>'
      )
      .replace(/\n/g, '<br />');

    return <span dangerouslySetInnerHTML={{ __html: text }} />;
  };

  return (
    <div className={`flex h-full w-full overflow-hidden bg-[#080c12] transition-all duration-300 ${isWide ? 'lg:min-w-[820px]' : ''}`}>
      {/* ── SIDEBAR DE HISTÓRICO DE CONVERSAS (ESTILO CHATGPT) ── */}
      <AnimatePresence>
        {showSidebar && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', damping: 28, stiffness: 220 }}
            className="h-full shrink-0 overflow-hidden z-20 border-r border-slate-800/80 bg-[#0b111a]"
          >
            <div className="w-[280px] h-full">
              <ChatSidebar
                sessions={chatSessions}
                activeSessionId={activeSessionId}
                onSelectSession={(id) => {
                  switchChatSession(id);
                  if (window.innerWidth < 640) setShowSidebar(false);
                }}
                onNewSession={() => {
                  createNewChatSession();
                  if (window.innerWidth < 640) setShowSidebar(false);
                }}
                onDeleteSession={deleteChatSession}
                onRenameSession={renameChatSession}
                onCloseSidebar={() => setShowSidebar(false)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── CONTEÚDO PRINCIPAL (CHAT OU CONSOLA CENTRAL) ── */}
      <div className="flex flex-col flex-1 h-full min-w-0 overflow-hidden bg-transparent">
        
        {/* Top Navigation & Channel Switcher */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800/80 bg-[#0b111a]/90 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {/* Sidebar Toggle Button */}
            <button
              onClick={() => setShowSidebar((prev) => !prev)}
              className={`p-1.5 rounded-md border text-xs transition-all cursor-pointer flex items-center gap-1.5 ${
                showSidebar
                  ? 'bg-sky-500/15 border-sky-400/35 text-sky-200'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-100 hover:bg-slate-800/70'
              }`}
              title={showSidebar ? 'Ocultar histórico de conversas' : 'Ver histórico de conversas (estilo ChatGPT)'}
            >
              {showSidebar ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
              <span className="hidden sm:inline font-medium text-[11px]">Histórico</span>
            </button>

            {/* Quick New Chat Button */}
            <button
              onClick={() => createNewChatSession()}
              className="p-1.5 rounded-md border border-slate-800 bg-slate-900/60 text-slate-400 hover:text-sky-200 hover:border-sky-500/30 hover:bg-slate-800/70 transition-all cursor-pointer flex items-center gap-1 text-[11px]"
              title="Nova conversa"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden md:inline font-medium">Novo chat</span>
            </button>

            {/* Channel Tabs: Conversa IA vs Consola de Sistema */}
            <div className="flex items-center rounded-lg bg-[#070b11] border border-slate-800 p-0.5 ml-1">
              <button
                onClick={() => setActiveTab('chat')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'chat'
                    ? 'bg-sky-500/15 border border-sky-400/30 text-sky-100 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Sparkles className="w-3 h-3 text-sky-400" />
                <span>Conversa IA</span>
                <span className="text-[10px] text-slate-500 font-mono">({chatMessages.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('system')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'system'
                    ? 'bg-slate-800/90 border border-slate-600/50 text-slate-100 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Terminal className="w-3 h-3 text-amber-400" />
                <span>Consola Central</span>
                <span className={`text-[10px] font-mono px-1 py-0.2 rounded ${
                  systemLogs.length > 0 ? 'bg-amber-500/15 text-amber-300' : 'text-slate-500'
                }`}>
                  {systemLogs.length}
                </span>
              </button>
            </div>
          </div>

          {/* Right Top Actions */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={() => setAgentLibraryOpen(true)}
              className="p-1.5 rounded-md border border-slate-800 bg-white/[0.03] text-slate-300 hover:text-sky-300 hover:border-sky-500/30 transition-all cursor-pointer flex items-center gap-1 text-[11px]"
              title="Biblioteca de subagentes especializados"
            >
              <Users className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">Especialistas</span>
            </button>

            {/* Width Expand Toggle */}
            <button
              onClick={() => setIsWide((prev) => !prev)}
              className="p-1.5 rounded-md border border-white/8 bg-white/[0.035] text-gray-400 hover:text-white hover:bg-white/[0.08] transition-all cursor-pointer hidden md:flex items-center justify-center"
              title={isWide ? 'Largura normal' : 'Expandir largura'}
            >
              {isWide ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>

            {/* Clear Channel Button */}
            <button
              onClick={activeTab === 'chat' ? clearChat : clearSystemLogs}
              className="p-1.5 rounded-md border border-white/8 bg-white/[0.035] text-gray-400 hover:text-rose-300 hover:bg-rose-950/30 hover:border-rose-500/30 transition-all cursor-pointer flex items-center justify-center"
              title={activeTab === 'chat' ? 'Limpar mensagens da conversa' : 'Limpar consola central'}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* ── TAB 1: CONVERSA IA (DIALOGO LIMPO + ANEXOS) ── */}
        {activeTab === 'chat' && (
          <div className="flex flex-col flex-1 h-full min-h-0 overflow-hidden">
            {/* Active Session Title Sub-header */}
            <div className="px-4 py-1.5 border-b border-slate-800/70 bg-[#0b111a]/60 flex items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-2 truncate">
                <MessageSquare className="w-3 h-3 text-sky-400 shrink-0" />
                <span className="font-semibold text-slate-200 truncate">
                  {activeSession?.title || 'Conversa ativa'}
                </span>
              </div>
              <span className="text-[10px] text-slate-500 font-mono shrink-0">
                Jarvis AI Assistant
              </span>
            </div>

            {/* Dialogue Bubbles Stream */}
            <div
              ref={logRef}
              className="flex-1 p-4 overflow-y-auto space-y-4 scroll-smooth bg-[#080c12] select-text"
              style={{ scrollbarWidth: 'thin' }}
            >
              {chatMessages.length === 0 ? (
                <div className="text-slate-500 text-center py-20 text-sm flex flex-col items-center justify-center gap-3 select-none">
                  <div className="h-14 w-14 rounded-xl border border-sky-400/20 bg-sky-500/10 flex items-center justify-center">
                    <Bot className="w-7 h-7 text-sky-300" />
                  </div>
                  <span className="text-gray-200 font-semibold text-base">Olá, em que posso ajudar hoje?</span>
                  <p className="text-gray-500 text-xs max-w-sm leading-relaxed">
                    Podes dar instruções por voz, escrever tarefas de código, anexar fotos e documentos para contexto, ou referenciar ficheiros com <kbd className="bg-white/[0.06] border border-white/10 px-1 py-0.5 rounded text-gray-300 font-mono">@ficheiro</kbd>.
                  </p>
                </div>
              ) : (
                <AnimatePresence initial={false}>
                  {chatMessages.map((msg) => {
                    const displaySender = msg.sender.toUpperCase() === 'OPENCLAW' ? 'JARVIS' : msg.sender;
                    const isSystem = displaySender === 'SISTEMA';
                    const isUser = displaySender === 'CLIENTE' || displaySender === 'USER';
                    const isMission =
                      msg.role === 'Missão' ||
                      msg.role === 'Mission' ||
                      msg.content.includes('Missão criada:') ||
                      msg.content.includes('Missão concluída:');
                    const isSafety = msg.role === 'Segurança' || msg.content.includes('⛔ Pedido recusado');
                    const isError = msg.content.includes('❌ A missão') || msg.content.includes('falhou:');

                    if (isSystem) {
                      return (
                        <motion.div
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          key={msg.id}
                          className="text-cyan-200/80 leading-relaxed text-xs text-center py-1 px-3 rounded-full bg-cyan-950/20 border border-cyan-400/10 max-w-[85%] mx-auto select-text"
                        >
                          <span className="text-gray-500 mr-1.5 font-mono">[{msg.timestamp}]</span>
                          {msg.content}
                        </motion.div>
                      );
                    }

                    return (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.97, y: 6 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        transition={{ duration: 0.18 }}
                        key={msg.id}
                        className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full group`}
                      >
                        <div className="flex flex-col max-w-[88%] gap-1.5">
                          {/* Bubble Header */}
                          <div
                            className={`flex items-center gap-1.5 px-1 text-[10px] text-gray-500 ${
                              isUser ? 'justify-end' : 'justify-start'
                            }`}
                          >
                            {isUser ? (
                              <>
                                <button
                                  onClick={() => handleCopy(msg.id, msg.content)}
                                  className="opacity-0 group-hover:opacity-100 hover:text-cyan-200 p-0.5 rounded transition-all cursor-pointer flex items-center gap-1 text-[9px] text-gray-500 hover:bg-white/10 mr-1 select-none"
                                  title="Copiar mensagem"
                                >
                                  {copiedId === msg.id ? (
                                    <>
                                      <Check className="w-2.5 h-2.5 text-emerald-400" />
                                      <span className="text-emerald-400">Copiado</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="w-2.5 h-2.5" />
                                      <span>Copiar</span>
                                    </>
                                  )}
                                </button>
                                <span className="font-mono">{msg.timestamp}</span>
                                <span className="text-sky-300 font-bold uppercase">{displaySender}</span>
                                <User className="w-3 h-3 text-sky-400" />
                              </>
                            ) : (
                              <>
                                <Bot className="w-3 h-3 text-cyan-300" />
                                <span className="text-cyan-300 font-bold uppercase">{displaySender}</span>
                                <span className="text-[9px] text-gray-500">({msg.role})</span>
                                <span className="font-mono">{msg.timestamp}</span>
                                <button
                                  onClick={() => handleCopy(msg.id, msg.content)}
                                  className="opacity-0 group-hover:opacity-100 hover:text-cyan-200 p-0.5 rounded transition-all cursor-pointer flex items-center gap-1 text-[9px] text-gray-500 hover:bg-white/10 ml-1 select-none"
                                  title="Copiar mensagem"
                                >
                                  {copiedId === msg.id ? (
                                    <>
                                      <Check className="w-2.5 h-2.5 text-emerald-400" />
                                      <span className="text-emerald-400">Copiado</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="w-2.5 h-2.5" />
                                      <span>Copiar</span>
                                    </>
                                  )}
                                </button>
                              </>
                            )}
                          </div>

                          {/* Bubble Body */}
                          <div
                            className={`p-3.5 rounded-lg shadow-sm border text-sm leading-relaxed transition-all font-sans select-text cursor-text ${
                              isUser
                                ? 'bg-sky-500/10 border-sky-400/25 text-sky-50'
                                : isSafety
                                ? 'bg-rose-950/25 border-rose-500/35 text-rose-100'
                                : isError
                                ? 'bg-red-950/25 border-red-500/35 text-red-100'
                                : isMission
                                ? 'bg-[#0f1722] border-sky-500/30 text-slate-100'
                                : 'bg-[#0f1722]/90 border-slate-800/90 text-slate-100'
                            }`}
                          >
                            {/* Attached Media/Docs in Message */}
                            {msg.attachments && msg.attachments.length > 0 && (
                              <div className="mb-2 select-none">
                                <ChatAttachmentBar attachments={msg.attachments} readOnly />
                              </div>
                            )}

                            <div className="select-text cursor-text">{renderMessageContent(msg)}</div>
                            {msg.study_card && (
                              <ChatStudyResultCard
                                card={msg.study_card}
                                liveOp={studyOperations[msg.study_card.operation_id]}
                                onNavigate={navigateToStudyTarget}
                                onCancelOperation={cancelStudyOperation}
                              />
                            )}
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              )}
            </div>

            {/* Template Suggestions */}
            {activeTemplate?.suggestions && activeTemplate.suggestions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 px-4 py-2 border-t border-white/8 bg-white/[0.015] shrink-0">
                {activeTemplate.suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendDirective(s.prompt)}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-white/[0.035] border border-white/8 hover:bg-cyan-300/10 hover:border-cyan-300/25 text-cyan-100 transition-all cursor-pointer"
                  >
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Remodeled Large Context-Aware Prompt Input */}
            <ChatPromptInput
              onSendMessage={handleSendMessage}
              promptHistory={promptHistory}
              projectFiles={projectFiles}
              isHandsFree={isHandsFree}
              voiceStatus={voiceStatus}
              onToggleHandsFree={() => toggleVoice(!isHandsFree)}
            />
          </div>
        )}

        {/* ── TAB 2: CONSOLA CENTRAL DE SISTEMA (SENTINEL & LOGS) ── */}
        {activeTab === 'system' && (
          <div className="flex-1 h-full min-h-0 overflow-hidden">
            <SystemConsolePanel
              logs={systemLogs}
              onClear={clearSystemLogs}
              isConnected={isConnected}
            />
          </div>
        )}
      </div>

      <AgentLibrary isOpen={agentLibraryOpen} onClose={() => setAgentLibraryOpen(false)} />
    </div>
  );
};
