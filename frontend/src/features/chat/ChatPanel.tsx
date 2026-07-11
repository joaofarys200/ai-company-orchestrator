import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket, type ChatMessage } from '../../context/WebSocketContext';
import { Mic, Eye, EyeOff, Bot, User, Trash2, Send, Sparkles, AtSign } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const AVAILABLE_COMMANDS = [
  { cmd: '/review', desc: 'Audita o código na sandbox (QA Quinn)' },
  { cmd: '/refactor', desc: 'Refatora e otimiza o código sandbox (Devon)' },
  { cmd: '/theme neon', desc: 'Muda para o tema Neon Cyberpunk' },
  { cmd: '/theme cyberpunk', desc: 'Muda para o tema Retro Cyberpunk' },
  { cmd: '/theme clean', desc: 'Muda para o tema Clean HUD' },
  { cmd: '/arena ', desc: 'Compara respostas de varios modelos na Arena' },
  { cmd: '/spawn ', desc: 'Cria um subagente especialista ad-hoc' },
  { cmd: '/help', desc: 'Exibe ajuda sobre os comandos' },
];

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
    projectFiles,
    activeTemplate,
    voiceStatus,
    sendDirective,
    toggleVoice,
    clearChat,
  } = useWebSocket();

  const [inputVal, setInputVal] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [filteredCmds, setFilteredCmds] = useState(AVAILABLE_COMMANDS);
  const isHandsFree = voiceStatus !== 'offline';
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(0);

  // @ Context Picker state
  const [showAtPicker, setShowAtPicker] = useState(false);
  const [atQuery, setAtQuery] = useState('');
  const [atStartIndex, setAtStartIndex] = useState(-1);
  const [selectedAtIndex, setSelectedAtIndex] = useState(0);
  const [mentionedFiles, setMentionedFiles] = useState<string[]>([]);

  const logRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playedAudioIds = useRef<Set<string>>(new Set());
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Autoplay TTS audio when a message arrives with base64 audio
  useEffect(() => {
    const lastMsg = chatMessages[chatMessages.length - 1];
    if (lastMsg && lastMsg.audio && !playedAudioIds.current.has(lastMsg.id)) {
      playedAudioIds.current.add(lastMsg.id);
      try {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        const audioUrl = `data:audio/mp3;base64,${lastMsg.audio}`;
        audioRef.current = new Audio(audioUrl);
        audioRef.current.play().catch((err) => {
          console.warn('[TTS] Autoplay blocked or failed:', err);
        });
      } catch (e) {
        console.error('[TTS] Error playing base64 audio:', e);
      }
    }
  }, [chatMessages]);

  // Build filtered @ suggestions from projectFiles keys
  const allFileNames = Object.keys(projectFiles);
  const filteredAtFiles = atQuery
    ? allFileNames.filter((f) => f.toLowerCase().includes(atQuery.toLowerCase()))
    : allFileNames;

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart ?? val.length;
    setInputVal(val);

    // ── Command autocomplete (/…) ──────────────────────────────────────
    if (val.startsWith('/') && !showAtPicker) {
      const query = val.toLowerCase();
      const matched = AVAILABLE_COMMANDS.filter((c) => c.cmd.toLowerCase().includes(query));
      setFilteredCmds(matched);
      setShowCommands(matched.length > 0);
      setSelectedCmdIndex(0);
    } else if (!val.startsWith('/')) {
      setShowCommands(false);
    }

    // ── @ mention picker ───────────────────────────────────────────────
    // Find the last '@' before the cursor
    const textBeforeCursor = val.slice(0, cursor);
    const lastAt = textBeforeCursor.lastIndexOf('@');

    if (lastAt !== -1) {
      // Make sure there's no space between '@' and cursor (it's an active mention)
      const mentionFragment = textBeforeCursor.slice(lastAt + 1);
      if (!mentionFragment.includes(' ')) {
        setAtStartIndex(lastAt);
        setAtQuery(mentionFragment);
        setShowAtPicker(true);
        setSelectedAtIndex(0);
        setShowCommands(false);
        return;
      }
    }

    // No active '@' mention
    setShowAtPicker(false);
    setAtStartIndex(-1);
    setAtQuery('');
  };

  const selectAtFile = (fname: string) => {
    if (atStartIndex === -1) return;
    // Replace the @fragment with @filename
    const before = inputVal.slice(0, atStartIndex);
    const afterCursor = inputVal.slice(atStartIndex + 1 + atQuery.length);
    const newVal = `${before}@${fname}${afterCursor}`;
    setInputVal(newVal);
    setShowAtPicker(false);
    setAtQuery('');
    setAtStartIndex(-1);

    // Track mentioned files to show badges
    if (!mentionedFiles.includes(fname)) {
      setMentionedFiles((prev) => [...prev, fname]);
    }
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // ── @ picker navigation ────────────────────────────────────────────
    if (showAtPicker && filteredAtFiles.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedAtIndex((prev) => (prev + 1) % filteredAtFiles.length);
        return;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedAtIndex((prev) => (prev - 1 + filteredAtFiles.length) % filteredAtFiles.length);
        return;
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        selectAtFile(filteredAtFiles[selectedAtIndex]);
        return;
      } else if (e.key === 'Escape') {
        setShowAtPicker(false);
        return;
      }
    }

    // ── Command picker navigation ──────────────────────────────────────
    if (showCommands) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev + 1) % filteredCmds.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev - 1 + filteredCmds.length) % filteredCmds.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        selectCommand(filteredCmds[selectedCmdIndex].cmd);
      } else if (e.key === 'Escape') {
        setShowCommands(false);
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const selectCommand = (cmd: string) => {
    setInputVal(cmd);
    setShowCommands(false);
  };

  const handleSubmit = () => {
    const text = inputVal.trim();
    if (!text) return;
    sendDirective(text);
    setInputVal('');
    setShowCommands(false);
    setShowAtPicker(false);
    setMentionedFiles([]);
  };

  const handleToggleHandsFree = () => {
    toggleVoice(voiceStatus === 'offline');
  };

  const renderMessageContent = (msg: ChatMessage) => {
    const safeText = escapeHtml(msg.content)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br />');

    return <span dangerouslySetInnerHTML={{ __html: safeText }} />;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden select-none bg-transparent">
      
      {/* Mini control overlay */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/8 bg-white/[0.02] backdrop-blur-sm">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
          <span className="font-semibold text-gray-300">Conversa ativa</span>
          <span className="hidden sm:inline text-gray-600">{chatMessages.length} mensagens</span>
        </div>
        <button
          onClick={clearChat}
          className="text-gray-500 hover:text-rose-300 h-8 w-8 rounded-md border border-white/8 bg-white/[0.035] transition-all cursor-pointer hover:bg-white/[0.08] flex items-center justify-center"
          title="Limpar conversa"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Speech bubbles dialogue logs */}
      <div 
        ref={logRef} 
        className="flex-grow p-4 overflow-y-auto space-y-4 scroll-smooth bg-[#05070e]/35"
        style={{ scrollbarWidth: 'thin' }}
      >
        {chatMessages.length === 0 ? (
          <div className="text-gray-500 text-center py-20 text-sm flex flex-col items-center justify-center gap-3">
            <div className="h-12 w-12 rounded-md border border-white/8 bg-white/[0.035] flex items-center justify-center">
              <Bot className="w-6 h-6 text-cyan-300/70" />
            </div>
            <span className="text-gray-300 font-medium">Aguardando instrucoes por voz ou escrita.</span>
            <span className="text-gray-600 text-xs">Usa <kbd className="bg-white/[0.06] border border-white/10 px-1.5 py-0.5 rounded">@ficheiro</kbd> para referenciar codigo.</span>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {chatMessages.map((msg) => {
              const isSystem = msg.sender === 'SISTEMA';
              const isUser = msg.sender === 'CLIENTE';

              if (isSystem) {
                return (
                  <motion.div 
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={msg.id} 
                    className="text-violet-200/75 leading-relaxed text-xs text-center py-1 max-w-[84%] mx-auto"
                  >
                    <span className="text-gray-600 mr-1.5">[{msg.timestamp}]</span>
                    {msg.content}
                  </motion.div>
                );
              }

              return (
                <motion.div
                  initial={{ opacity: 0, scale: 0.96, y: 8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  key={msg.id}
                  className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full`}
                >
                  <div className={`flex flex-col max-w-[86%] gap-1.5`}>
                    
                    {/* Header bubble info */}
                    <div className={`flex items-center gap-1.5 px-1 text-[10px] text-gray-500 ${isUser ? 'justify-end' : 'justify-start'}`}>
                      {isUser ? (
                        <>
                          <span>{msg.timestamp}</span>
                          <span className="text-blue-400 font-bold uppercase">{msg.sender}</span>
                          <User className="w-2.5 h-2.5 text-blue-400" />
                        </>
                      ) : (
                        <>
                          <Bot className="w-2.5 h-2.5 text-cyan-400" />
                          <span className="text-cyan-400 font-bold uppercase">{msg.sender}</span>
                          <span className="text-[8px] text-gray-600">({msg.role})</span>
                          <span>{msg.timestamp}</span>
                        </>
                      )}
                    </div>

                    {/* Bubble body content */}
                    <div
                      className={`p-3.5 rounded-md shadow-lg border backdrop-blur-md text-sm leading-relaxed transition-all duration-300 font-sans ${
                        isUser
                          ? 'bg-sky-400/10 border-sky-300/20 text-sky-50'
                          : 'bg-white/[0.045] border-white/8 text-gray-100'
                      }`}
                    >
                      {renderMessageContent(msg)}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>

      {/* Suggestion Chips */}
      {activeTemplate?.suggestions && activeTemplate.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 py-3 border-t border-white/8 bg-white/[0.02] select-none">
          {activeTemplate.suggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => sendDirective(s.prompt)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-white/[0.04] border border-white/8 hover:bg-cyan-300/10 hover:border-cyan-300/25 text-cyan-100 transition-all cursor-pointer"
            >
              <span>{s.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Floating Style Input Console */}
      <div className="relative p-4 bg-[#080b12]/95 border-t border-white/8 backdrop-blur-md">
        
        {/* Command Autocomplete Popup */}
        <AnimatePresence>
          {showCommands && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.1 }}
              className="absolute bottom-full left-4 right-4 bg-[#080b12]/98 border border-cyan-300/25 rounded-t-md shadow-2xl z-50 max-h-48 overflow-y-auto backdrop-blur-md"
            >
              {filteredCmds.map((c, idx) => (
                <div
                  key={c.cmd}
                  onClick={() => selectCommand(c.cmd)}
                  onMouseEnter={() => setSelectedCmdIndex(idx)}
                  className={`flex flex-col p-2.5 border-b border-white/8 cursor-pointer transition-colors ${
                    idx === selectedCmdIndex ? 'bg-cyan-300/10' : 'hover:bg-white/[0.05]'
                  }`}
                >
                  <span className="font-mono text-xs font-semibold text-cyan-200">{c.cmd}</span>
                  <span className="text-[10px] text-gray-500">{c.desc}</span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* @ File Picker Popup */}
        <AnimatePresence>
          {showAtPicker && filteredAtFiles.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.1 }}
              className="absolute bottom-full left-4 right-4 bg-[#080b12]/98 border border-violet-300/25 rounded-t-md shadow-2xl z-50 max-h-48 overflow-y-auto backdrop-blur-md"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/8 text-[10px] text-gray-500">
                <AtSign className="w-3 h-3 text-violet-300" />
                <span>Referenciar ficheiro do projeto</span>
                {atQuery && <span className="text-violet-400 font-bold">"{atQuery}"</span>}
              </div>
              {filteredAtFiles.map((fname, idx) => (
                <div
                  key={fname}
                  onClick={() => selectAtFile(fname)}
                  onMouseEnter={() => setSelectedAtIndex(idx)}
                  className={`flex items-center gap-2 px-3 py-2 border-b border-white/8 cursor-pointer transition-colors ${
                    idx === selectedAtIndex ? 'bg-violet-300/10' : 'hover:bg-white/[0.05]'
                  }`}
                >
                  <span className="font-mono text-xs text-violet-200">@{fname}</span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mentioned file badges */}
        {mentionedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {mentionedFiles.map((fname) => (
              <span
                key={fname}
                className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-md bg-violet-300/10 border border-violet-300/25 text-violet-200"
              >
                <AtSign className="w-2.5 h-2.5" />
                {fname}
              </span>
            ))}
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={inputVal}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="Diz ao Jarvis o que criar... usa @ para referenciar ficheiros"
          className="w-full h-20 p-3 bg-black/35 border border-white/10 rounded-md text-sm focus:border-cyan-300/35 outline-none resize-none text-white placeholder-gray-600 shadow-inner"
        />

        <div className="flex items-center justify-between gap-3 mt-3">
          <div className="flex gap-2 min-w-0">
            <button
              onClick={handleToggleHandsFree}
              className={`flex items-center justify-center h-9 w-9 rounded-md border cursor-pointer transition-all shrink-0 ${
                voiceStatus === 'listening'
                  ? 'bg-rose-400/10 border-rose-300/35 text-rose-200 animate-pulse scale-95'
                  : 'bg-white/[0.04] border-white/10 text-gray-400 hover:bg-white/[0.08] hover:text-white'
              }`}
              title={isHandsFree ? 'Desativar Comando por Voz' : 'Ativar Comando por Voz'}
            >
              <Mic className="w-4 h-4" />
            </button>
            <button
              onClick={handleToggleHandsFree}
              className={`hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-md border text-xs font-semibold cursor-pointer transition-all ${
                isHandsFree
                  ? 'bg-emerald-300/10 border-emerald-300/25 text-emerald-200'
                  : 'bg-white/[0.04] border-white/10 text-gray-400 hover:bg-white/[0.08] hover:text-white'
              }`}
            >
              {isHandsFree ? <Eye className="w-3.5 h-3.5 animate-pulse" /> : <EyeOff className="w-3.5 h-3.5" />}
              <span>Maos livres</span>
            </button>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!inputVal.trim()}
            className="flex h-9 items-center gap-2 px-4 bg-cyan-300 hover:bg-cyan-200 disabled:bg-white/[0.04] disabled:text-gray-600 disabled:border-white/8 disabled:cursor-not-allowed border border-cyan-300/20 text-black font-semibold text-xs rounded-md cursor-pointer transition-all active:scale-98"
          >
            <span>Executar</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
