import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Paperclip,
  Image as ImageIcon,
  History,
  AtSign,
  Mic,
  X,
  Upload,
  AlertCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ChatAttachment } from './types';
import { ChatAttachmentBar, formatFileSize } from './ChatAttachmentBar';

interface ChatPromptInputProps {
  onSendMessage: (text: string, attachments: ChatAttachment[]) => void;
  promptHistory: string[];
  projectFiles: { [filename: string]: string };
  isHandsFree: boolean;
  voiceStatus: string;
  onToggleHandsFree: () => void;
  availableCommands?: Array<{ cmd: string; desc: string }>;
  placeholder?: string;
}

const DEFAULT_COMMANDS = [
  { cmd: '/review', desc: 'Audita o código na sandbox (QA Quinn)' },
  { cmd: '/refactor', desc: 'Refatora e otimiza o código sandbox (Devon)' },
  { cmd: '/theme neon', desc: 'Muda para o tema Neon Cyberpunk' },
  { cmd: '/theme clean', desc: 'Muda para o tema Clean HUD' },
  { cmd: '/help', desc: 'Exibe ajuda sobre os comandos' },
];

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const MAX_DOC_SIZE_BYTES = 2.5 * 1024 * 1024; // 2.5MB

export const ChatPromptInput: React.FC<ChatPromptInputProps> = ({
  onSendMessage,
  promptHistory,
  projectFiles,
  isHandsFree,
  voiceStatus,
  onToggleHandsFree,
  availableCommands = DEFAULT_COMMANDS,
  placeholder = 'Diz ao Jarvis o que analisar, criar ou executar... podes anexar fotos, documentos ou usar @ficheiro',
}) => {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [historyIndex, setHistoryIndex] = useState<number>(-1);

  // Command & @mention autocompletion state
  const [showCommands, setShowCommands] = useState(false);
  const [filteredCmds, setFilteredCmds] = useState(availableCommands);
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(0);

  const [showAtPicker, setShowAtPicker] = useState(false);
  const [atQuery, setAtQuery] = useState('');
  const [atStartIndex, setAtStartIndex] = useState(-1);
  const [selectedAtIndex, setSelectedAtIndex] = useState(0);
  const [mentionedFiles, setMentionedFiles] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 96), 240)}px`;
    }
  }, [text]);

  const allFileNames = Object.keys(projectFiles);
  const filteredAtFiles = atQuery
    ? allFileNames.filter((f) => f.toLowerCase().includes(atQuery.toLowerCase()))
    : allFileNames;

  const filteredHistory = promptHistory
    .filter((p) => p.toLowerCase().includes(historySearch.toLowerCase()))
    .slice(-30)
    .reverse();

  // Helper to read file and convert to ChatAttachment
  const processFileToAttachment = async (file: File): Promise<ChatAttachment | null> => {
    const isImage = file.type.startsWith('image/');
    const id = `att_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

    if (isImage && file.size > MAX_IMAGE_SIZE_BYTES) {
      setUploadError(`Imagem "${file.name}" excede o limite de ${formatFileSize(MAX_IMAGE_SIZE_BYTES)}.`);
      return null;
    }
    if (!isImage && file.size > MAX_DOC_SIZE_BYTES) {
      setUploadError(`Ficheiro "${file.name}" excede o limite seguro de ${formatFileSize(MAX_DOC_SIZE_BYTES)}.`);
      return null;
    }

    return new Promise((resolve) => {
      const reader = new FileReader();

      if (isImage) {
        reader.onload = () => {
          resolve({
            id,
            name: file.name,
            type: 'image',
            size: file.size,
            mimeType: file.type || 'image/png',
            dataUrl: String(reader.result),
            tokenEstimate: 750, // standard multimodal vision token budget estimate
          });
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(file);
      } else {
        reader.onload = () => {
          const content = String(reader.result || '');
          resolve({
            id,
            name: file.name,
            type: file.name.match(/\.(ts|tsx|js|jsx|py|json|html|css|rs|go)$/i) ? 'code' : 'document',
            size: file.size,
            mimeType: file.type || 'text/plain',
            textContent: content,
            tokenEstimate: Math.ceil(content.length / 3.8),
          });
        };
        reader.onerror = () => resolve(null);
        reader.readAsText(file);
      }
    });
  };

  const handleFilesAdded = async (fileList: FileList | File[]) => {
    setUploadError(null);
    const files = Array.from(fileList);
    const newAttachments: ChatAttachment[] = [];

    for (const f of files) {
      const att = await processFileToAttachment(f);
      if (att) newAttachments.push(att);
    }

    if (newAttachments.length > 0) {
      setAttachments((prev) => [...prev, ...newAttachments]);
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const filesToProcess: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) filesToProcess.push(file);
      }
    }

    if (filesToProcess.length > 0) {
      e.preventDefault();
      handleFilesAdded(filesToProcess);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(e.dataTransfer.files);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart ?? val.length;
    setText(val);
    setHistoryIndex(-1);

    // Command autocomplete (/…)
    if (val.startsWith('/') && !showAtPicker) {
      const query = val.toLowerCase();
      const matched = availableCommands.filter((c) => c.cmd.toLowerCase().includes(query));
      setFilteredCmds(matched);
      setShowCommands(matched.length > 0);
      setSelectedCmdIndex(0);
    } else if (!val.startsWith('/')) {
      setShowCommands(false);
    }

    // @ mention picker
    const textBeforeCursor = val.slice(0, cursor);
    const lastAt = textBeforeCursor.lastIndexOf('@');
    if (lastAt !== -1) {
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

    setShowAtPicker(false);
    setAtStartIndex(-1);
    setAtQuery('');
  };

  const selectAtFile = (fname: string) => {
    if (atStartIndex === -1) return;
    const before = text.slice(0, atStartIndex);
    const afterCursor = text.slice(atStartIndex + 1 + atQuery.length);
    const newVal = `${before}@${fname} ${afterCursor}`;
    setText(newVal);
    setShowAtPicker(false);
    setAtQuery('');
    setAtStartIndex(-1);
    if (!mentionedFiles.includes(fname)) {
      setMentionedFiles((prev) => [...prev, fname]);
    }
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Navigate @ mentions
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

    // Navigate commands
    if (showCommands && filteredCmds.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev + 1) % filteredCmds.length);
        return;
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCmdIndex((prev) => (prev - 1 + filteredCmds.length) % filteredCmds.length);
        return;
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        setText(filteredCmds[selectedCmdIndex].cmd);
        setShowCommands(false);
        return;
      } else if (e.key === 'Escape') {
        setShowCommands(false);
        return;
      }
    }

    // Navigate Prompt History using ArrowUp / ArrowDown when at boundary
    if (!showCommands && !showAtPicker && promptHistory.length > 0) {
      const cursor = textareaRef.current?.selectionStart ?? 0;
      const isAtBeginning = cursor === 0;

      if (e.key === 'ArrowUp' && (isAtBeginning || text.trim() === '')) {
        e.preventDefault();
        const nextIdx = historyIndex + 1;
        if (nextIdx < promptHistory.length) {
          const item = promptHistory[promptHistory.length - 1 - nextIdx];
          setHistoryIndex(nextIdx);
          setText(item);
        }
        return;
      } else if (e.key === 'ArrowDown' && historyIndex >= 0) {
        e.preventDefault();
        const prevIdx = historyIndex - 1;
        if (prevIdx >= 0) {
          const item = promptHistory[promptHistory.length - 1 - prevIdx];
          setHistoryIndex(prevIdx);
          setText(item);
        } else {
          setHistoryIndex(-1);
          setText('');
        }
        return;
      }
    }

    // Submit on Enter (without shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const cleanText = text.trim();
    if (!cleanText && attachments.length === 0) return;

    onSendMessage(cleanText, attachments);
    setText('');
    setAttachments([]);
    setMentionedFiles([]);
    setShowCommands(false);
    setShowAtPicker(false);
    setHistoryIndex(-1);
    setUploadError(null);
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative p-3.5 bg-[#070a13] border-t border-white/8 transition-all ${
        isDragging ? 'ring-2 ring-cyan-400/60 bg-cyan-950/20' : ''
      }`}
    >
      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".txt,.md,.json,.py,.ts,.tsx,.js,.jsx,.csv,.html,.css,.yml,.yaml,.sql,.pdf"
        onChange={(e) => e.target.files && handleFilesAdded(e.target.files)}
        className="hidden"
      />
      <input
        ref={imageInputRef}
        type="file"
        multiple
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        onChange={(e) => e.target.files && handleFilesAdded(e.target.files)}
        className="hidden"
      />

      {/* Drag & drop overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-40 bg-[#060a15]/90 border-2 border-dashed border-cyan-400 flex flex-col items-center justify-center gap-2 backdrop-blur-xs">
          <Upload className="w-8 h-8 text-cyan-300 animate-bounce" />
          <span className="text-sm font-semibold text-cyan-100">
            Larga ficheiros ou imagens para anexar como contexto
          </span>
          <span className="text-xs text-gray-400">Suporta código, documentos e imagens</span>
        </div>
      )}

      {/* Upload Error Banner */}
      {uploadError && (
        <div className="mb-2 p-2 rounded bg-rose-950/40 border border-rose-500/30 text-rose-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
            <span>{uploadError}</span>
          </div>
          <button onClick={() => setUploadError(null)} className="text-gray-400 hover:text-white">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Active Attachments Bar */}
      {attachments.length > 0 && (
        <div className="mb-2.5">
          <ChatAttachmentBar attachments={attachments} onRemove={handleRemoveAttachment} />
        </div>
      )}

      {/* Mentioned Files Badges */}
      {mentionedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {mentionedFiles.map((fname) => (
            <span
              key={fname}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-violet-300/10 border border-violet-300/25 text-violet-200"
            >
              <AtSign className="w-2.5 h-2.5" />
              {fname}
            </span>
          ))}
        </div>
      )}

      {/* Command Autocomplete Dropdown */}
      <AnimatePresence>
        {showCommands && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute bottom-full left-4 right-4 bg-[#080c18] border border-cyan-300/25 rounded-t-md shadow-2xl z-50 max-h-48 overflow-y-auto backdrop-blur-md"
          >
            {filteredCmds.map((c, idx) => (
              <div
                key={c.cmd}
                onClick={() => {
                  setText(c.cmd);
                  setShowCommands(false);
                }}
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

      {/* @ File Picker Dropdown */}
      <AnimatePresence>
        {showAtPicker && filteredAtFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="absolute bottom-full left-4 right-4 bg-[#080c18] border border-violet-300/25 rounded-t-md shadow-2xl z-50 max-h-48 overflow-y-auto backdrop-blur-md"
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

      {/* Main Expansive Input Area */}
      <div className="relative rounded-lg border border-white/10 bg-black/45 focus-within:border-cyan-300/40 focus-within:ring-1 focus-within:ring-cyan-300/20 transition-all shadow-inner">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={placeholder}
          rows={3}
          className="w-full min-h-[96px] max-h-[240px] p-3 text-sm text-gray-100 placeholder-gray-500 outline-none resize-none bg-transparent leading-relaxed"
          style={{ scrollbarWidth: 'thin' }}
        />

        {/* Input Bottom Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2 border-t border-white/5 bg-white/[0.015]">
          <div className="flex items-center gap-1">
            {/* Attach Document */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center h-8 w-8 rounded text-gray-400 hover:text-cyan-200 hover:bg-white/[0.08] transition-all cursor-pointer"
              title="Anexar documento ou código"
            >
              <Paperclip className="w-4 h-4" />
            </button>

            {/* Attach Photo / Image */}
            <button
              onClick={() => imageInputRef.current?.click()}
              className="flex items-center justify-center h-8 w-8 rounded text-gray-400 hover:text-cyan-200 hover:bg-white/[0.08] transition-all cursor-pointer"
              title="Adicionar foto ou imagem para contexto"
            >
              <ImageIcon className="w-4 h-4" />
            </button>

            {/* Prompt History Quick Selector */}
            <button
              onClick={() => setShowHistoryModal((prev) => !prev)}
              className={`flex items-center justify-center h-8 w-8 rounded transition-all cursor-pointer ${
                showHistoryModal
                  ? 'bg-cyan-300/15 text-cyan-200'
                  : 'text-gray-400 hover:text-cyan-200 hover:bg-white/[0.08]'
              }`}
              title="Histórico de prompts anteriores (ou usa Seta Cima)"
            >
              <History className="w-4 h-4" />
            </button>

            {/* Project File Reference Trigger */}
            <button
              onClick={() => {
                setText((prev) => `${prev}@`);
                textareaRef.current?.focus();
              }}
              className="flex items-center justify-center h-8 w-8 rounded text-gray-400 hover:text-violet-200 hover:bg-white/[0.08] transition-all cursor-pointer"
              title="Referenciar ficheiro do projeto (@)"
            >
              <AtSign className="w-4 h-4" />
            </button>

            {/* Voice Command */}
            <button
              onClick={onToggleHandsFree}
              className={`flex items-center justify-center h-8 w-8 rounded transition-all cursor-pointer ${
                voiceStatus === 'listening'
                  ? 'bg-rose-500/20 text-rose-300 animate-pulse'
                  : isHandsFree
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : 'text-gray-400 hover:text-white hover:bg-white/[0.08]'
              }`}
              title={isHandsFree ? 'Comando por voz ativo' : 'Ativar comando por voz'}
            >
              <Mic className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-600 hidden sm:inline">
              <kbd className="px-1 py-0.5 rounded bg-white/[0.06] border border-white/10">Shift+Enter</kbd> nova linha
            </span>

            {/* Submit Directive Button */}
            <button
              onClick={handleSubmit}
              disabled={!text.trim() && attachments.length === 0}
              className="flex items-center gap-2 h-8 px-4 rounded-md bg-cyan-300 hover:bg-cyan-200 disabled:opacity-40 disabled:cursor-not-allowed text-black font-semibold text-xs transition-all cursor-pointer shadow-[0_2px_12px_rgba(103,232,249,0.18)] active:scale-98"
            >
              <span>Executar</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* History Modal Popup */}
      <AnimatePresence>
        {showHistoryModal && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="absolute bottom-full left-4 right-4 bg-[#080d1a] border border-cyan-400/25 rounded-lg shadow-2xl p-3 z-50 max-h-72 flex flex-col backdrop-blur-xl"
          >
            <div className="flex items-center justify-between pb-2 border-b border-white/8 mb-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-200">
                <History className="w-3.5 h-3.5 text-cyan-300" />
                <span>Histórico de pedidos anteriores</span>
              </div>
              <button
                onClick={() => setShowHistoryModal(false)}
                className="text-gray-400 hover:text-white p-1 rounded"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <input
              type="text"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              placeholder="Pesquisar pedidos anteriores..."
              className="w-full h-7 px-2 text-xs bg-black/60 border border-white/10 rounded text-gray-200 placeholder-gray-600 outline-none mb-2"
            />

            <div className="flex-1 overflow-y-auto space-y-1" style={{ scrollbarWidth: 'thin' }}>
              {filteredHistory.length === 0 ? (
                <div className="text-center py-6 text-gray-500 text-xs">
                  Nenhum pedido anterior registado.
                </div>
              ) : (
                filteredHistory.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setText(item);
                      setShowHistoryModal(false);
                      textareaRef.current?.focus();
                    }}
                    className="p-2 rounded bg-white/[0.025] hover:bg-cyan-300/10 border border-white/5 hover:border-cyan-300/25 cursor-pointer text-xs text-gray-300 hover:text-cyan-100 transition-all font-mono truncate"
                  >
                    {item}
                  </div>
                ))
              )}
            </div>
            <div className="text-[10px] text-gray-500 pt-2 border-t border-white/8 text-center font-mono">
              Dica: Também podes usar as teclas Seta Cima/Baixo na caixa de texto.
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
