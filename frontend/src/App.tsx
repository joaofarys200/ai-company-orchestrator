import { useEffect, useState } from 'react';
import { useWebSocket } from './context/WebSocketContext';
import { ChatPanel } from './features/chat';
import { HologramCore, WorkspaceViewer } from './features/workspace';
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
    studyNavigationTarget,
    setActiveDomain,
  } = useWebSocket();

  const [dismissedNavNonce, setDismissedNavNonce] = useState<number | null>(null);
  const fullWorkspaceNavActive = Boolean(
    studyNavigationTarget && dismissedNavNonce !== studyNavigationTarget.nonce
  );
  const workspaceOpen = Boolean(activeBoard) || fullWorkspaceNavActive;

  // Global shortcut: Ctrl+J to toggle JARVIS Chat & Central Console, Escape to unfocus
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

  // Route any legacy devPanelOpen trigger directly into the unified Workspace shell
  useEffect(() => {
    if (devPanelOpen) {
      if (!activeBoard) {
        openSpatialBoard('project');
      } else {
        setActiveDomain('project');
      }
      setDevPanelOpen(false);
    }
  }, [devPanelOpen, activeBoard, openSpatialBoard, setActiveDomain, setDevPanelOpen]);

  return (
    <div className="h-screen w-screen bg-[#080c12] text-slate-200 flex flex-col relative font-sans overflow-hidden">
      <main className="flex-1 min-h-0 flex relative overflow-hidden">
        <AnimatePresence mode="wait">
          {workspaceOpen ? (
            <motion.div
              key="unified-workspace"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16 }}
              className="h-full w-full overflow-hidden"
            >
              <WorkspaceViewer
                onClose={() => {
                  closeSpatialBoard();
                  if (studyNavigationTarget) {
                    setDismissedNavNonce(studyNavigationTarget.nonce);
                  }
                }}
              />
            </motion.div>
          ) : (
            <motion.div
              key="standby-orb"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16 }}
              className="flex flex-1 items-center justify-center overflow-hidden"
            >
              <HologramCore
                docked={false}
                onToggleBoard={() => openSpatialBoard('study')}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Left Drawer: Full Chat Panel & Consola Central */}
      <AnimatePresence>
        {chatPanelOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.55 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setChatPanelOpen(false)}
              className="fixed inset-0 bg-black/75 z-[55] backdrop-blur-sm"
            />

            <motion.div
              initial={{ x: '-100%', opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '-100%', opacity: 0 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="fixed inset-y-0 left-0 w-full sm:w-[580px] md:w-[720px] lg:w-[840px] xl:w-[960px] bg-[#080c12]/98 border-r border-slate-800 shadow-[24px_0_90px_rgba(0,0,0,0.85)] z-[60] flex flex-col backdrop-blur-2xl"
            >
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800/80 bg-[#0b111a] shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="h-7 w-7 rounded-md border border-sky-400/25 bg-sky-500/10 flex items-center justify-center">
                    <Activity className="w-3.5 h-3.5 text-sky-300" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-100">Assistente & Consola JARVIS</div>
                    <div className="text-[10px] text-slate-400 font-mono">Jarvis OS • Unified Workspace</div>
                  </div>
                </div>
                <button
                  onClick={() => setChatPanelOpen(false)}
                  className="text-slate-400 hover:text-slate-100 h-7 w-7 rounded-md border border-slate-800 bg-slate-900/70 hover:bg-slate-800 transition-all cursor-pointer flex items-center justify-center"
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
