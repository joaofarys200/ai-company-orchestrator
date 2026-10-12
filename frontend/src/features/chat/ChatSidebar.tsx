import React, { useState, useMemo } from 'react';
import { Plus, MessageSquare, Trash2, Search, Calendar, ChevronLeft, Edit2, Check, X } from 'lucide-react';
import type { ChatSession } from './types';
import { formatSessionGroupDate } from './chatSessionStorage';

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, newTitle: string) => void;
  onCloseSidebar?: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  onCloseSidebar,
}) => {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const filteredSessions = useMemo(() => {
    return sessions.filter((s) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        s.title.toLowerCase().includes(q) ||
        s.messages.some((m) => m.content.toLowerCase().includes(q))
      );
    });
  }, [sessions, search]);

  const groupedSessions = useMemo(() => {
    const groups: { [group: string]: ChatSession[] } = {};
    filteredSessions.forEach((s) => {
      const g = formatSessionGroupDate(s.updatedAt || s.createdAt);
      if (!groups[g]) groups[g] = [];
      groups[g].push(s);
    });
    return groups;
  }, [filteredSessions]);

  const handleStartRename = (s: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditingTitle(s.title);
  };

  const handleSaveRename = (s: ChatSession, e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    if (editingTitle.trim()) {
      onRenameSession(s.id, editingTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const groupOrder = ['Hoje', 'Ontem', 'Últimos 7 dias', 'Últimos 30 dias', 'Anteriores'];

  return (
    <div className="flex flex-col h-full w-full bg-[#050811] border-r border-white/8 select-none">
      {/* Top Header & New Chat Button */}
      <div className="p-3 border-b border-white/8 space-y-2.5 shrink-0 bg-white/[0.015]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-300 tracking-wide uppercase">
            Conversas Anteriores
          </span>
          {onCloseSidebar && (
            <button
              onClick={onCloseSidebar}
              className="p-1 text-gray-500 hover:text-white rounded hover:bg-white/[0.05] transition-all cursor-pointer"
              title="Fechar barra lateral"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* New Chat Primary Action Button */}
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 h-9 px-3 rounded-md bg-cyan-300 hover:bg-cyan-200 text-black font-semibold text-xs transition-all shadow-[0_2px_12px_rgba(103,232,249,0.15)] cursor-pointer active:scale-98"
        >
          <Plus className="w-4 h-4" />
          <span>Novo chat</span>
        </button>

        {/* Search Field */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Pesquisar conversas..."
            className="w-full h-8 pl-8 pr-3 text-xs bg-black/40 border border-white/10 rounded-md text-gray-200 placeholder-gray-600 outline-none focus:border-cyan-300/35 transition-all"
          />
        </div>
      </div>

      {/* Sessions Grouped List */}
      <div
        className="flex-1 overflow-y-auto p-2 space-y-4"
        style={{ scrollbarWidth: 'thin' }}
      >
        {sessions.length === 0 ? (
          <div className="text-center py-12 px-4 text-gray-500 text-xs">
            <MessageSquare className="w-7 h-7 mx-auto text-gray-600 mb-2" />
            <p className="text-gray-400 font-medium">Sem conversas anteriores</p>
            <p className="text-gray-600 text-[11px] mt-1">
              Inicia uma conversa para ela ficar registada aqui.
            </p>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="text-center py-10 px-4 text-gray-500 text-xs">
            <Search className="w-6 h-6 mx-auto text-gray-600 mb-1.5" />
            <p className="text-gray-400">Nenhum resultado para "{search}"</p>
          </div>
        ) : (
          groupOrder.map((group) => {
            const groupList = groupedSessions[group];
            if (!groupList || groupList.length === 0) return null;

            return (
              <div key={group} className="space-y-1">
                <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold tracking-wider text-gray-500 uppercase">
                  <Calendar className="w-3 h-3 text-gray-600" />
                  <span>{group}</span>
                </div>

                {groupList.map((session) => {
                  const isActive = session.id === activeSessionId;
                  const isEditing = editingId === session.id;

                  return (
                    <div
                      key={session.id}
                      onClick={() => onSelectSession(session.id)}
                      className={`group relative flex items-center justify-between gap-2 px-2.5 py-2 rounded-md cursor-pointer transition-all text-xs border ${
                        isActive
                          ? 'bg-cyan-950/35 border-cyan-400/30 text-cyan-50 font-medium shadow-sm'
                          : 'bg-white/[0.015] border-transparent text-gray-400 hover:text-gray-100 hover:bg-white/[0.045] hover:border-white/5'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <MessageSquare
                          className={`w-3.5 h-3.5 shrink-0 ${
                            isActive ? 'text-cyan-300' : 'text-gray-500 group-hover:text-gray-300'
                          }`}
                        />

                        {isEditing ? (
                          <div
                            className="flex items-center gap-1 flex-1 min-w-0"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              type="text"
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveRename(session, e);
                                if (e.key === 'Escape') setEditingId(null);
                              }}
                              autoFocus
                              className="w-full h-6 px-1.5 text-xs bg-black/80 border border-cyan-400/50 rounded text-white outline-none"
                            />
                            <button
                              onClick={(e) => handleSaveRename(session, e)}
                              className="p-1 text-emerald-400 hover:text-emerald-300"
                            >
                              <Check className="w-3 h-3" />
                            </button>
                            <button
                              onClick={handleCancelRename}
                              className="p-1 text-gray-400 hover:text-white"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-col min-w-0">
                            <span className="truncate leading-snug">{session.title}</span>
                            <span className="text-[10px] text-gray-600 font-mono">
                              {session.messages.length} msg
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Action buttons on hover / active */}
                      {!isEditing && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                          <button
                            onClick={(e) => handleStartRename(session, e)}
                            className="p-1 text-gray-500 hover:text-cyan-200 rounded hover:bg-white/[0.08] transition-all"
                            title="Renomear conversa"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteSession(session.id);
                            }}
                            className="p-1 text-gray-500 hover:text-rose-300 rounded hover:bg-rose-950/30 transition-all"
                            title="Eliminar conversa"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>

      {/* Footer info */}
      <div className="p-3 border-t border-white/8 bg-black/20 text-[10px] text-gray-600 font-mono text-center shrink-0">
        <span>{sessions.length} conversas salvas localmente</span>
      </div>
    </div>
  );
};
