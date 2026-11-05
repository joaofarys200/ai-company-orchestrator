import { useEffect } from 'react';
import { useWebSocket } from './context/WebSocketContext';
import { ChatPanel } from './features/chat';
import { HologramCore } from './features/workspace';
import { SpatialBoard } from './features/board/SpatialBoard';
import { PermissionApprovalModal } from './features/permissions';
import { X, Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const {
    chatPanelOpen,
    setChatPanelOpen,
    devPanelOpen,
    setDevPanelOpen,
    activeBoard,
    focusedCardId,
    openSpatialBoard,
    closeSpatialBoard,
    focusSpatialCard,
  } = useWebSocket();

  // Global shortcut: Ctrl+J to toggle JARVIS Chat & Central Console, Escape to unfocus card
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'j' || e.key === 'J')) {
        e.preventDefault();
        setChatPanelOpen(!chatPanelOpen);
      } else if (e.key === 'Escape' && focusedCardId) {
        focusSpatialCard(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chatPanelOpen, setChatPanelOpen, focusedCardId, focusSpatialCard]);

  // Route any legacy devPanelOpen trigger directly into the unified Spatial Board
  useEffect(() => {
    if (devPanelOpen) {
      if (!activeBoard) {
        openSpatialBoard('project');
      }
      setDevPanelOpen(false);
    }
  }, [devPanelOpen, activeBoard, openSpatialBoard, setDevPanelOpen]);

  return (
    <div className="min-h-screen bg-[#0b0b0a] text-stone-200 flex flex-col relative font-sans overflow-hidden">
      {/* ── MAIN: Ecrã espacial — Orbe central ou Quadro Espacial Interativo ── */}
      <main className="flex-grow flex items-center justify-center z-10 relative overflow-hidden">
        <AnimatePresence mode="wait">
          {activeBoard && (
            <SpatialBoard
              key={activeBoard.domain}
              board={activeBoard}
              focusedCardId={focusedCardId}
              onFocusCard={focusSpatialCard}
              onCloseBoard={closeSpatialBoard}
              onSwitchDomain={(domain) => openSpatialBoard(domain)}
            />
          )}
        </AnimatePresence>
        <HologramCore
          docked={Boolean(activeBoard)}
          onToggleBoard={() => {
            if (activeBoard) {
              closeSpatialBoard();
            } else {
              openSpatialBoard('study');
            }
          }}
        />
      </main>

      {/* ── LEFT DRAWER: Chat Panel & Consola Central ── */}
      <AnimatePresence>
        {chatPanelOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.55 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setChatPanelOpen(false)}
              className="fixed inset-0 bg-black/75 z-50 backdrop-blur-sm"
            />

            <motion.div
              initial={{ x: '-100%', opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '-100%', opacity: 0 }}
              transition={{ type: 'spring', damping: 30, stiffness: 220 }}
              className="fixed inset-y-0 left-0 w-full sm:w-[580px] md:w-[720px] lg:w-[840px] xl:w-[960px] bg-[#05070e]/98 border-r border-cyan-400/20 shadow-[24px_0_90px_rgba(0,0,0,0.85)] z-[60] flex flex-col backdrop-blur-2xl"
            >
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/8 bg-white/[0.02] shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="h-7 w-7 rounded-md border border-cyan-300/25 bg-cyan-300/10 flex items-center justify-center">
                    <Activity className="w-3.5 h-3.5 text-cyan-200" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">Assistente & Consola JARVIS</div>
                    <div className="text-[10px] text-gray-500 font-mono">Jarvis OS • Multimodal AI Workspace</div>
                  </div>
                </div>
                <button
                  onClick={() => setChatPanelOpen(false)}
                  className="text-gray-400 hover:text-white h-7 w-7 rounded-md border border-white/8 bg-white/[0.035] hover:bg-white/[0.08] transition-all cursor-pointer flex items-center justify-center"
                  title="Fechar painel"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex-grow overflow-hidden">
                <ChatPanel />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Global Human-in-the-Loop Permission Gateway Modal */}
      <PermissionApprovalModal />
    </div>
  );
}

export default App;
