import React, { useState, useEffect } from 'react';
import { useAppSession } from '../../context/AppSessionContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, MessageSquare, Mic, MicOff, BookOpen, Code2, Database, Shield } from 'lucide-react';

interface HologramCoreProps {
  docked?: boolean;
  onToggleBoard?: () => void;
}

export const HologramCore: React.FC<HologramCoreProps> = ({
  docked = false,
  onToggleBoard,
}) => {
  const {
    systemStatus,
    voiceStatus,
    chatPanelOpen,
    setChatPanelOpen,
    toggleVoice,
    isConnected,
    activeBoard,
    openSpatialBoard,
    closeSpatialBoard,
  } = useAppSession();

  const [timeStr, setTimeStr] = useState('00:00:00');
  const [dateStr, setDateStr] = useState('STANDBY // READY');
  const [showStatusAlert, setShowStatusAlert] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('pt-PT', { hour12: false }));

      const options: Intl.DateTimeFormatOptions = { weekday: 'short', day: '2-digit', month: 'short' };
      setDateStr(now.toLocaleDateString('pt-PT', options).toUpperCase() + ' // JARVIS OS');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const getTheme = () => {
    if (voiceStatus === 'listening') {
      return {
        hex: '#10b981',
        rgba: 'rgba(16, 185, 129, 0.15)',
        glow: 'shadow-[0_0_35px_rgba(16,185,129,0.4)]',
        glowRgb: 'rgba(16, 185, 129, 0.45)',
        border: 'border-emerald-500/40',
        text: 'text-emerald-400',
        coreBg: 'from-[#022c22]/90 via-[#020617]/95 to-[#05070e]/98',
      };
    }
    if (voiceStatus === 'transcribing') {
      return {
        hex: '#f59e0b',
        rgba: 'rgba(245, 158, 11, 0.15)',
        glow: 'shadow-[0_0_35px_rgba(245,158,11,0.4)]',
        glowRgb: 'rgba(245, 158, 11, 0.45)',
        border: 'border-amber-500/40',
        text: 'text-amber-400',
        coreBg: 'from-[#78350f]/80 via-[#020617]/95 to-[#05070e]/98',
      };
    }
    if (systemStatus === 'PROCESSING') {
      return {
        hex: '#d99a6c',
        rgba: 'rgba(217, 154, 108, 0.15)',
        glow: 'shadow-[0_0_40px_rgba(217,154,108,0.32)]',
        glowRgb: 'rgba(217, 154, 108, 0.34)',
        border: 'border-orange-300/35',
        text: 'text-orange-200',
        coreBg: 'from-[#3a2117]/80 via-[#141311]/95 to-[#0b0b0a]/98',
      };
    }
    if (systemStatus === 'ONLINE') {
      return {
        hex: '#d99a6c',
        rgba: 'rgba(217, 154, 108, 0.12)',
        glow: 'shadow-[0_0_30px_rgba(217,154,108,0.24)]',
        glowRgb: 'rgba(217, 154, 108, 0.28)',
        border: 'border-orange-300/30',
        text: 'text-orange-200',
        coreBg: 'from-[#2a1c15]/80 via-[#141311]/95 to-[#0b0b0a]/98',
      };
    }
    return {
      hex: '#64748b',
      rgba: 'rgba(100, 116, 139, 0.1)',
      glow: 'shadow-[0_0_15px_rgba(100,116,139,0.15)]',
      glowRgb: 'rgba(100, 116, 139, 0.15)',
      border: 'border-slate-500/20',
      text: 'text-slate-500',
      coreBg: 'from-[#0f172a]/80 via-[#020617]/95 to-[#05070e]/98',
    };
  };

  const theme = getTheme();

  const getStatusText = () => {
    if (voiceStatus === 'listening') return 'JARVIS ESCUTANDO (VAD)...';
    if (voiceStatus === 'transcribing') return 'WHISPER A TRANSCREVER...';
    if (systemStatus === 'PROCESSING') return 'A COORDENAR ENXAME DE AGENTES...';
    if (systemStatus === 'ONLINE') return 'SISTEMA OPERACIONAL // AGUARDANDO';
    return 'SISTEMA DESCONECTADO';
  };

  const ticks = Array.from({ length: 60 }).map((_, idx) => {
    const angle = idx * 6;
    const isMajor = idx % 5 === 0;
    return (
      <line
        key={idx}
        x1="180"
        y1="38"
        x2="180"
        y2={isMajor ? '48' : '43'}
        stroke={theme.hex}
        strokeWidth={isMajor ? 1.5 : 0.8}
        opacity={isMajor ? 0.6 : 0.2}
        transform={`rotate(${angle} 180 180)`}
      />
    );
  });

  const compassDots = Array.from({ length: 12 }).map((_, idx) => {
    const angle = idx * 30;
    return (
      <circle
        key={idx}
        cx="180"
        cy="28"
        r="1.5"
        fill={idx % 3 === 0 ? '#ffffff' : theme.hex}
        opacity={idx % 3 === 0 ? 0.75 : 0.35}
        transform={`rotate(${angle} 180 180)`}
      />
    );
  });

  const handleBoardToggle = () => {
    if (onToggleBoard) {
      onToggleBoard();
      return;
    }
    if (activeBoard) {
      closeSpatialBoard();
    } else {
      openSpatialBoard('study');
    }
  };

  return (
    <>
      <motion.div
        layout
        transition={{ type: 'spring', damping: 26, stiffness: 210 }}
        onClick={docked ? handleBoardToggle : undefined}
        title={docked ? 'Clica no Orbe para descansar o Quadro Espacial e voltar ao centro' : undefined}
        className={
          docked
            ? 'fixed bottom-20 right-6 z-40 flex flex-col items-center justify-center select-none cursor-pointer group'
            : 'flex flex-col items-center justify-center py-12 px-6 relative z-10 w-full select-none'
        }
      >
        <motion.div
          layoutId="jarvis-hologram-orb"
          animate={{ scale: docked ? 0.34 : 1 }}
          transition={{ type: 'spring', damping: 26, stiffness: 210 }}
          className={`relative w-[360px] h-[360px] flex items-center justify-center rounded-full ${
            docked ? '-m-[118px]' : ''
          }`}
        >
          <div className={`absolute w-44 h-44 rounded-full transition-all duration-700 bg-transparent ${theme.glow} -z-10`} />

          <motion.g
            animate={{ rotate: 360 }}
            transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
            className="absolute inset-0 w-full h-full flex items-center justify-center pointer-events-none"
          >
            <svg width="360" height="360" viewBox="0 0 360 360" className="absolute">
              <circle cx="180" cy="180" r="152" stroke={theme.hex} strokeWidth="0.5" fill="none" strokeDasharray="2 8" opacity="0.15" />
              {ticks}
              {compassDots}
            </svg>
          </motion.g>

          <svg width="360" height="360" viewBox="0 0 360 360" className="absolute pointer-events-none">
            <line x1="180" y1="12" x2="180" y2="22" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
            <line x1="180" y1="338" x2="180" y2="348" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
            <line x1="12" y1="180" x2="22" y2="180" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
            <line x1="338" y1="180" x2="348" y2="180" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
            <circle cx="180" cy="180" r="112" stroke={theme.hex} strokeWidth="0.8" fill="none" opacity="0.2" />
          </svg>

          <svg width="360" height="360" viewBox="0 0 360 360" className="absolute pointer-events-none">
            <motion.circle
              cx="180"
              cy="180"
              r="124"
              stroke="rgba(255, 255, 255, 0.85)"
              strokeWidth="2.5"
              fill="none"
              strokeLinecap="round"
              strokeDasharray="140 650"
              animate={{ rotate: 360 }}
              transition={{ duration: 32, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '180px 180px' }}
            />

            <motion.circle
              cx="180"
              cy="180"
              r="124"
              stroke={theme.hex}
              strokeWidth="1.2"
              fill="none"
              strokeLinecap="round"
              strokeDasharray="90 690"
              animate={{ rotate: -360 }}
              transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '180px 180px' }}
            />

            <motion.circle
              cx="180"
              cy="56"
              r="3"
              fill="#ffffff"
              className="shadow-lg"
              animate={{ rotate: 360 }}
              transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '180px 180px' }}
            />
          </svg>

          <motion.div
            animate={voiceStatus === 'listening' ? { scale: [1, 1.04, 1] } : { scale: 1 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            className="w-44 h-44 rounded-full bg-[#05070e] border border-white/10 flex flex-col items-center justify-center relative z-10 transition-all duration-700 shadow-2xl"
            style={{
              boxShadow: `0 0 35px ${theme.glowRgb}, inset 0 0 20px ${theme.rgba}`,
            }}
          >
            <div className="absolute inset-1.5 rounded-full border border-white/5 pointer-events-none" />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-4 rounded-full border border-dashed border-white/5 pointer-events-none"
            />
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-6 rounded-full border-t border-b border-r border-transparent pointer-events-none"
              style={{ borderTopColor: theme.hex, borderBottomColor: theme.hex, opacity: 0.4 }}
            />

            <span className="font-sans text-[22px] font-light tracking-[0.22em] text-white font-bold ml-[0.22em] z-10">
              JARVIS
            </span>

            <motion.div
              animate={{ scale: [1, 1.6, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2.5, repeat: Infinity }}
              className={`w-1.5 h-1.5 rounded-full mt-3 ${
                voiceStatus === 'listening'
                  ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]'
                  : voiceStatus === 'transcribing'
                    ? 'bg-amber-400 shadow-[0_0_8px_#f59e0b]'
                    : 'bg-orange-300 shadow-[0_0_8px_#d99a6c]'
              }`}
            />
          </motion.div>
        </motion.div>

        {!docked && (
          <div className="mt-8 text-center select-none flex flex-col items-center z-10">
            <motion.div
              animate={{ opacity: [0.7, 1, 0.7] }}
              transition={{ duration: 3, repeat: Infinity }}
              className={`font-mono text-[11px] tracking-[0.25em] ${theme.text} font-bold uppercase transition-colors duration-500`}
            >
              {getStatusText()}
            </motion.div>

            <div className="mt-4.5 py-1.5 px-4 rounded-full bg-[#05070e]/80 border border-white/5 inline-flex items-center gap-3 backdrop-blur-md">
              <div className="font-mono text-sm text-gray-200 tracking-widest font-semibold">{timeStr}</div>
              <div className="w-[1px] h-3 bg-white/10" />
              <div className="font-mono text-[9px] text-gray-500 tracking-wider uppercase">{dateStr.split(' // ')[0]}</div>
            </div>
          </div>
        )}
      </motion.div>

      {/* ── FLOATING BOTTOM HUD DOCK (Direct Spatial Domain Triggers) ── */}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 sm:gap-4 px-4 py-2 bg-[#05070e]/85 border border-white/10 rounded-full backdrop-blur-xl shadow-[0_12px_35px_rgba(0,0,0,0.65)] transition-all">
        <button
          onClick={() => {
            setShowStatusAlert(true);
            setTimeout(() => setShowStatusAlert(false), 3000);
          }}
          className="relative p-2 rounded-full hover:bg-white/5 transition-all text-gray-500 hover:text-white cursor-pointer"
          title={isConnected ? 'Tauri IPC Conectado' : 'Runtime Desconectado'}
        >
          <Globe className={`w-4 h-4 transition-colors ${isConnected ? 'text-emerald-400' : 'text-rose-500'}`} />
          {isConnected && (
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          )}
        </button>

        <div className="w-[1px] h-4 bg-white/10" />

        {/* Estudos */}
        <button
          onClick={() => (activeBoard?.domain === 'study' ? closeSpatialBoard() : openSpatialBoard('study'))}
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
            activeBoard?.domain === 'study'
              ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
          title="Quadro de Estudos & Aulas"
        >
          <BookOpen className="w-4 h-4" />
          <span className="hidden sm:inline">Estudos</span>
        </button>

        {/* Projetos & Código */}
        <button
          onClick={() => (activeBoard?.domain === 'project' ? closeSpatialBoard() : openSpatialBoard('project'))}
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
            activeBoard?.domain === 'project'
              ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
          title="Quadro de Projetos, Editor de Código & Live Preview"
        >
          <Code2 className="w-4 h-4" />
          <span className="hidden sm:inline">Projetos</span>
        </button>

        {/* Obsidian Vault */}
        <button
          onClick={() => (activeBoard?.domain === 'obsidian' ? closeSpatialBoard() : openSpatialBoard('obsidian'))}
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
            activeBoard?.domain === 'obsidian'
              ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
          title="Quadro do Obsidian Knowledge Vault"
        >
          <Database className="w-4 h-4" />
          <span className="hidden sm:inline">Obsidian</span>
        </button>

        {/* Sentinel */}
        <button
          onClick={() => (activeBoard?.domain === 'sentinel' ? closeSpatialBoard() : openSpatialBoard('sentinel'))}
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
            activeBoard?.domain === 'sentinel'
              ? 'bg-[#d99a6c]/25 text-[#f3c39f] border border-[#d99a6c]/45'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
          title="Quadro de Segurança Sentinel"
        >
          <Shield className="w-4 h-4" />
          <span className="hidden sm:inline">Sentinel</span>
        </button>

        <div className="w-[1px] h-4 bg-white/10" />

        {/* Chat IA Drawer */}
        <button
          onClick={() => setChatPanelOpen(!chatPanelOpen)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
            chatPanelOpen
              ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
          title="Abrir Chat & Consola IA (Ctrl+J)"
        >
          <MessageSquare className="w-4 h-4" />
          <span className="hidden sm:inline">Chat IA</span>
        </button>

        {/* Microphone Toggle */}
        <button
          onClick={() => toggleVoice(voiceStatus === 'offline')}
          className={`p-2 rounded-full hover:bg-white/5 transition-all cursor-pointer ${
            voiceStatus !== 'offline' ? 'text-emerald-400' : 'text-gray-500 hover:text-white'
          }`}
          title={voiceStatus !== 'offline' ? 'Comando de Voz Ativo' : 'Ativar Comandos por Voz'}
        >
          {voiceStatus !== 'offline' ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
        </button>

        <AnimatePresence>
          {showStatusAlert && (
            <motion.div
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute bottom-14 left-1/2 -translate-x-1/2 px-3.5 py-1.5 rounded-lg bg-[#05070e] border border-white/10 text-gray-300 text-[10px] font-mono whitespace-nowrap shadow-xl"
            >
              {isConnected ? 'LIGAÇÃO ESTÁVEL: TAURI IPC' : 'SEM SINAL DE BACKEND'}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
};
