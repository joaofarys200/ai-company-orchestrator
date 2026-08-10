import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../context/WebSocketContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, MessageSquare, Terminal, Mic, MicOff, Info } from 'lucide-react';

export const HologramCore: React.FC = () => {
  const {
    systemStatus,
    voiceStatus,
    chatPanelOpen,
    setChatPanelOpen,
    devPanelOpen,
    setDevPanelOpen,
    toggleVoice,
    isConnected,
  } = useWebSocket();

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

  // Define responsive color themes for each app status
  const getTheme = () => {
    if (voiceStatus === 'listening') {
      return {
        hex: '#10b981', // emerald
        rgba: 'rgba(16, 185, 129, 0.15)',
        glow: 'shadow-[0_0_35px_rgba(16,185,129,0.4)]',
        glowRgb: 'rgba(16, 185, 129, 0.45)',
        border: 'border-emerald-500/40',
        text: 'text-emerald-400',
        coreBg: 'from-[#022c22]/90 via-[#020617]/95 to-[#05070e]/98'
      };
    }
    if (voiceStatus === 'transcribing') {
      return {
        hex: '#f59e0b', // amber
        rgba: 'rgba(245, 158, 11, 0.15)',
        glow: 'shadow-[0_0_35px_rgba(245,158,11,0.4)]',
        glowRgb: 'rgba(245, 158, 11, 0.45)',
        border: 'border-amber-500/40',
        text: 'text-amber-400',
        coreBg: 'from-[#78350f]/80 via-[#020617]/95 to-[#05070e]/98'
      };
    }
    if (systemStatus === 'PROCESSING') {
      return {
        hex: '#d99a6c', // terracotta
        rgba: 'rgba(217, 154, 108, 0.15)',
        glow: 'shadow-[0_0_40px_rgba(217,154,108,0.32)]',
        glowRgb: 'rgba(217, 154, 108, 0.34)',
        border: 'border-orange-300/35',
        text: 'text-orange-200',
        coreBg: 'from-[#3a2117]/80 via-[#141311]/95 to-[#0b0b0a]/98'
      };
    }
    if (systemStatus === 'ONLINE') {
      return {
        hex: '#d99a6c', // terracotta
        rgba: 'rgba(217, 154, 108, 0.12)',
        glow: 'shadow-[0_0_30px_rgba(217,154,108,0.24)]',
        glowRgb: 'rgba(217, 154, 108, 0.28)',
        border: 'border-orange-300/30',
        text: 'text-orange-200',
        coreBg: 'from-[#2a1c15]/80 via-[#141311]/95 to-[#0b0b0a]/98'
      };
    }
    return {
      hex: '#64748b', // slate/offline
      rgba: 'rgba(100, 116, 139, 0.1)',
      glow: 'shadow-[0_0_15px_rgba(100,116,139,0.15)]',
      glowRgb: 'rgba(100, 116, 139, 0.15)',
      border: 'border-slate-500/20',
      text: 'text-slate-500',
      coreBg: 'from-[#0f172a]/80 via-[#020617]/95 to-[#05070e]/98'
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

  // Generate dynamic compass/HUD ticks
  const ticks = Array.from({ length: 60 }).map((_, idx) => {
    const angle = idx * 6; // 360 / 60 = 6 degrees
    const isMajor = idx % 5 === 0;
    return (
      <line
        key={idx}
        x1="180"
        y1="38"
        x2="180"
        y2={isMajor ? "48" : "43"}
        stroke={isMajor ? theme.hex : theme.hex}
        strokeWidth={isMajor ? 1.5 : 0.8}
        opacity={isMajor ? 0.6 : 0.2}
        transform={`rotate(${angle} 180 180)`}
      />
    );
  });

  // Generate dynamic compass dots
  const compassDots = Array.from({ length: 12 }).map((_, idx) => {
    const angle = idx * 30; // 360 / 12 = 30 degrees
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

  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 relative z-10 w-full select-none">
      
      {/* ── CENTRAL HUD GRAPHIC CONTAINER ── */}
      <div className="relative w-[360px] h-[360px] flex items-center justify-center rounded-full">
        
        {/* Dynamic Glowing Halo behind core */}
        <div className={`absolute w-44 h-44 rounded-full transition-all duration-700 bg-transparent ${theme.glow} -z-10`} />

        {/* 1. Compass / Ticks / Dots Ring (Rotating slowly) */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0 w-full h-full flex items-center justify-center pointer-events-none"
        >
          <svg width="360" height="360" viewBox="0 0 360 360" className="absolute">
            {/* Outer Dotted ring track */}
            <circle cx="180" cy="180" r="152" stroke={theme.hex} strokeWidth="0.5" fill="none" strokeDasharray="2 8" opacity="0.15" />
            
            {/* Grid circle ticks */}
            {ticks}
            {compassDots}
          </svg>
        </motion.g>

        {/* 2. Technical Ticks & Cardinal Markers */}
        <svg width="360" height="360" viewBox="0 0 360 360" className="absolute pointer-events-none">
          {/* Main crosshair lines */}
          <line x1="180" y1="12" x2="180" y2="22" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
          <line x1="180" y1="338" x2="180" y2="348" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
          <line x1="12" y1="180" x2="22" y2="180" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
          <line x1="338" y1="180" x2="348" y2="180" stroke={theme.hex} strokeWidth="1.5" opacity="0.7" />
          
          {/* Inner ring track */}
          <circle cx="180" cy="180" r="112" stroke={theme.hex} strokeWidth="0.8" fill="none" opacity="0.2" />
        </svg>

        {/* 3. Outer Concentric Arcs (Rotating in opposite directions) */}
        <svg width="360" height="360" viewBox="0 0 360 360" className="absolute pointer-events-none">
          {/* Main bold white arc (Bottom-Left in reference image) */}
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

          {/* Thin colored arc (Top-Right in reference image) */}
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

          {/* Tiny orbiting dot */}
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

        {/* 4. SOLID CENTRAL CORE CIRCLE */}
        <motion.div
          animate={voiceStatus === 'listening' ? { scale: [1, 1.04, 1] } : { scale: 1 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          className={`w-44 h-44 rounded-full bg-[#05070e] border border-white/10 flex flex-col items-center justify-center relative z-10 transition-all duration-700 shadow-2xl`}
          style={{
            boxShadow: `0 0 35px ${theme.glowRgb}, inset 0 0 20px ${theme.rgba}`
          }}
        >
          {/* Inner thin border layer */}
          <div className="absolute inset-1.5 rounded-full border border-white/5 pointer-events-none" />

          {/* Rotating tech rings inside core */}
          <motion.div
            animate={{ rotate: -360 }}
            transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
            className="absolute inset-4 rounded-full border border-dashed border-white/5 pointer-events-none"
          />
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            className={`absolute inset-6 rounded-full border-t border-b border-r border-transparent pointer-events-none`}
            style={{ borderTopColor: theme.hex, borderBottomColor: theme.hex, opacity: 0.4 }}
          />

          {/* JARVIS Text Center */}
          <span className="font-sans text-[22px] font-light tracking-[0.22em] text-white font-bold ml-[0.22em] z-10">
            JARVIS
          </span>

          {/* Tiny center pulsing core dot */}
          <motion.div
            animate={{ scale: [1, 1.6, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2.5, repeat: Infinity }}
            className={`w-1.5 h-1.5 rounded-full mt-3 ${
              voiceStatus === 'listening' ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' :
              voiceStatus === 'transcribing' ? 'bg-amber-400 shadow-[0_0_8px_#f59e0b]' :
              systemStatus === 'PROCESSING' ? 'bg-orange-300 shadow-[0_0_8px_#d99a6c]' :
              'bg-orange-300 shadow-[0_0_8px_#d99a6c]'
            }`}
          />
        </motion.div>

      </div>

      {/* ── STATUS LABEL & CLOCK ── */}
      <div className="mt-8 text-center select-none flex flex-col items-center z-10">
        <motion.div
          animate={{ opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 3, repeat: Infinity }}
          className={`font-mono text-[11px] tracking-[0.25em] ${theme.text} font-bold uppercase transition-colors duration-500`}
        >
          {getStatusText()}
        </motion.div>
        
        {/* Tech Pill Clock */}
        <div className="mt-4.5 py-1.5 px-4 rounded-full bg-[#05070e]/80 border border-white/5 inline-flex items-center gap-3 backdrop-blur-md">
          <div className="font-mono text-sm text-gray-200 tracking-widest font-semibold">{timeStr}</div>
          <div className="w-[1px] h-3 bg-white/10" />
          <div className="font-mono text-[9px] text-gray-500 tracking-wider uppercase">{dateStr.split(' // ')[0]}</div>
        </div>
      </div>

      {/* ── FLOATING BOTTOM HUD DOCK ── */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-5 px-5 py-2.5 bg-[#05070e]/75 border border-white/5 rounded-full backdrop-blur-lg shadow-[0_10px_30px_rgba(0,0,0,0.5)] transition-all">
        {/* Globe Connection Indicator */}
        <button
          onClick={() => {
            setShowStatusAlert(true);
            setTimeout(() => setShowStatusAlert(false), 3000);
          }}
          className={`relative p-2 rounded-full hover:bg-white/5 transition-all text-gray-500 hover:text-white cursor-pointer`}
          title={isConnected ? "WebSocket Conectado (Porta 8001)" : "WebSocket Desconectado"}
        >
          <Globe className={`w-4.5 h-4.5 transition-colors ${isConnected ? 'text-emerald-400 drop-shadow-[0_0_4px_rgba(16,185,129,0.5)]' : 'text-rose-500'}`} />
          {isConnected && (
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          )}
        </button>

        <div className="w-[1px] h-4 bg-white/10" />

        {/* Chat Drawer Toggle button */}
        <button
          onClick={() => setChatPanelOpen(!chatPanelOpen)}
          className={`p-2 rounded-full hover:bg-white/5 transition-all cursor-pointer ${
            chatPanelOpen ? 'text-orange-200 drop-shadow-[0_0_4px_rgba(217,154,108,0.42)]' : 'text-gray-400 hover:text-white'
          }`}
          title="Abrir Chat (ou diz 'abre o chat')"
        >
          <MessageSquare className="w-4.5 h-4.5" />
        </button>

        {/* Dev Panel Toggle button */}
        <button
          onClick={() => setDevPanelOpen(!devPanelOpen)}
          className={`p-2 rounded-full hover:bg-white/5 transition-all cursor-pointer ${
            devPanelOpen ? 'text-orange-200 drop-shadow-[0_0_4px_rgba(217,154,108,0.42)]' : 'text-gray-400 hover:text-white'
          }`}
          title="Abrir Painel Dev (ou diz 'painel dev')"
        >
          <Terminal className="w-4.5 h-4.5" />
        </button>

        {/* Microphone Toggle (Auto VAD indicator) */}
        <button
          onClick={() => toggleVoice(voiceStatus === 'offline')}
          className={`p-2 rounded-full hover:bg-white/5 transition-all cursor-pointer ${
            voiceStatus !== 'offline' ? 'text-emerald-400 drop-shadow-[0_0_4px_rgba(16,185,129,0.5)]' : 'text-gray-500 hover:text-white'
          }`}
          title={voiceStatus !== 'offline' ? "Microfone VAD Ativo" : "Microfone VAD Inativo"}
        >
          {voiceStatus !== 'offline' ? <Mic className="w-4.5 h-4.5" /> : <MicOff className="w-4.5 h-4.5" />}
        </button>

        <div className="w-[1px] h-4 bg-white/10" />

        {/* Info button */}
        <button
          className="p-2 rounded-full hover:bg-white/5 transition-all text-gray-400 hover:text-white cursor-pointer"
          title="Jarvis OS v1.0.0"
        >
          <Info className="w-4.5 h-4.5" />
        </button>

        {/* Connection status notification pop-up */}
        <AnimatePresence>
          {showStatusAlert && (
            <motion.div
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute bottom-14 left-1/2 -translate-x-1/2 px-3.5 py-1.5 rounded-lg bg-[#05070e] border border-white/10 text-gray-300 text-[10px] font-mono whitespace-nowrap shadow-xl"
            >
              {isConnected ? "LIGAÇÃO ESTÁVEL: WS 8001" : "SEM SINAL DE BACKEND"}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

    </div>
  );
};
