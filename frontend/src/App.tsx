import React from 'react';
import { useWebSocket } from './context/WebSocketContext';
import { ChatPanel } from './features/chat';
import { AgentLibrary } from './features/settings';
import { HologramCore, WorkspaceViewer } from './features/workspace';
import { X, Users, BookOpen, Activity, ChevronDown, PanelRightClose } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';

const TEMPLATE_OPTIONS = [
  { value: 'builder_swarm', label: 'Builder Swarm' },
  { value: 'operator_swarm', label: 'Operator Swarm' },
  { value: 'creator_swarm', label: 'Creator Swarm' },
  { value: 'growth_swarm', label: 'Growth Swarm' },
  { value: 'research_swarm', label: 'Research Swarm' },
];

function App() {
  const {
    isConnected,
    activeTemplate,
    selectTemplate,
    chatPanelOpen,
    setChatPanelOpen,
    devPanelOpen,
    setDevPanelOpen,
  } = useWebSocket();

  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isTeamOpen, setIsTeamOpen] = useState(false);

  const handleTemplateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    selectTemplate(e.target.value);
  };

  return (
    <div className="min-h-screen bg-[#0b0b0a] text-stone-200 flex flex-col relative font-sans overflow-hidden">

      {/* ── MAIN: Ecrã completamente limpo — só o hologram ── */}
      <main className="flex-grow flex items-center justify-center z-10 relative overflow-hidden">
        <HologramCore />
      </main>

      {/* ── LEFT DRAWER: Chat Panel (aberto via comando de voz) ── */}
      <AnimatePresence>
        {chatPanelOpen && (
          <>
            {/* Backdrop semitransparente — clicável para fechar */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setChatPanelOpen(false)}
              className="fixed inset-0 bg-black/70 z-30 backdrop-blur-sm"
            />

            {/* Gaveta deslizante da ESQUERDA */}
            <motion.div
              initial={{ x: '-100%', opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '-100%', opacity: 0 }}
              transition={{ type: 'spring', damping: 30, stiffness: 220 }}
              className="fixed inset-y-0 left-0 w-full sm:w-[520px] lg:w-[560px] bg-[#05070e]/96 border-r border-white/8 shadow-[18px_0_70px_rgba(0,0,0,0.55)] z-40 flex flex-col backdrop-blur-2xl"
            >
              {/* Header da gaveta */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/8 bg-white/[0.025]">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-md border border-violet-300/20 bg-violet-300/10 flex items-center justify-center">
                    <Activity className="w-4 h-4 text-violet-200" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-white">Conversa ativa</div>
                    <div className="text-xs text-gray-500">Jarvis OS</div>
                  </div>
                </div>
                <button
                  onClick={() => setChatPanelOpen(false)}
                  className="text-gray-500 hover:text-white h-9 w-9 rounded-md border border-white/8 bg-white/[0.035] hover:bg-white/[0.08] transition-all cursor-pointer flex items-center justify-center"
                  title="Fechar chat"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Chat ocupa o resto */}
              <div className="flex-grow overflow-hidden">
                <ChatPanel />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── RIGHT DRAWER: Developer Panel (via /dev ou voice futuramente) ── */}
      <AnimatePresence>
        {devPanelOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              exit={{ opacity: 0 }}
              onClick={() => setDevPanelOpen(false)}
              className="fixed inset-0 bg-black/60 z-30 backdrop-blur-xs"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.98, y: 18 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: 18 }}
              transition={{ type: 'spring', damping: 28, stiffness: 210 }}
              className="fixed inset-0 sm:inset-2 bg-[#05070e]/97 border border-white/8 shadow-[0_24px_90px_rgba(0,0,0,0.62)] z-40 flex flex-col backdrop-blur-2xl sm:rounded-lg overflow-hidden"
            >
              <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-white/8 bg-white/[0.025] shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="relative h-8 w-8 rounded-md border border-cyan-300/20 bg-cyan-300/10 flex items-center justify-center">
                    <Activity className="w-4 h-4 text-cyan-200" />
                    <span
                      className={`absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full border-2 border-[#090b12] ${
                        isConnected ? 'bg-emerald-400' : 'bg-rose-400'
                      }`}
                    />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-white truncate">Workspace</div>
                    <div className="hidden text-xs text-gray-500 truncate sm:block">Projetos, alterações e missões</div>
                  </div>
                </div>
                <div className="flex min-w-0 items-center gap-2">
                  <select
                    value={activeTemplate?.template_name || 'builder_swarm'}
                    onChange={handleTemplateChange}
                    className="hidden h-9 max-w-44 px-3 bg-black/35 border border-white/10 rounded-md text-gray-200 outline-none focus:border-cyan-300/40 cursor-pointer text-xs md:block"
                  >
                    {TEMPLATE_OPTIONS.map((template) => (
                      <option key={template.value} value={template.value}>
                        {template.label}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => setIsTeamOpen((current) => !current)}
                    className={`flex h-9 items-center justify-center gap-2 border px-2.5 text-xs font-medium rounded-md transition-all cursor-pointer ${
                      isTeamOpen
                        ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-100'
                        : 'border-white/8 bg-white/[0.035] text-gray-400 hover:bg-white/[0.07] hover:text-white'
                    }`}
                    aria-expanded={isTeamOpen}
                    title="Ver equipa"
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>{activeTemplate?.agents?.length || 0}</span>
                    <ChevronDown className={`w-3 h-3 transition-transform ${isTeamOpen ? 'rotate-180' : ''}`} />
                  </button>
                  <button
                    onClick={() => setIsLibraryOpen(true)}
                    className="flex h-9 items-center justify-center gap-2 px-2.5 border border-white/8 bg-white/[0.035] hover:bg-white/[0.07] text-gray-300 hover:text-white font-medium text-xs rounded-md transition-all cursor-pointer"
                    title="Abrir biblioteca"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span className="hidden lg:inline">Biblioteca</span>
                  </button>
                  <button
                    onClick={() => setDevPanelOpen(false)}
                    className="flex h-9 w-9 items-center justify-center border border-white/8 bg-white/[0.035] hover:bg-white/[0.08] text-gray-400 hover:text-white rounded-md transition-all cursor-pointer"
                    title="Fechar painel"
                  >
                    <PanelRightClose className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {isTeamOpen && activeTemplate?.agents && activeTemplate.agents.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-2 overflow-y-auto px-4 py-2 border-b border-white/8 text-xs shrink-0 max-h-28">
                  {activeTemplate.agents.map((agent) => (
                    <div key={agent.id} className="flex items-center gap-2.5 px-3 py-2 bg-white/[0.035] border border-white/8 rounded-md min-w-0">
                      <div className="w-7 h-7 rounded-md bg-cyan-300/10 border border-cyan-300/15 flex items-center justify-center">
                        <Activity className="w-3.5 h-3.5 text-cyan-200" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-semibold text-white truncate">{agent.name}</span>
                        <span className="text-gray-500 truncate">{agent.role}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex-grow overflow-hidden p-2 min-h-0">
                <WorkspaceViewer />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Agent Library */}
      <AgentLibrary isOpen={isLibraryOpen} onClose={() => setIsLibraryOpen(false)} />
    </div>
  );
}

export default App;
