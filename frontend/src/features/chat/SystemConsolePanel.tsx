import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Terminal, Shield, Wifi, AlertTriangle, Trash2, Copy, Search, Pause, Play, CheckCircle2, Cpu } from 'lucide-react';
import type { SystemLogEntry, LogCategory } from './types';

interface SystemConsolePanelProps {
  logs: SystemLogEntry[];
  onClear: () => void;
  isConnected: boolean;
}

export const SystemConsolePanel: React.FC<SystemConsolePanelProps> = ({
  logs,
  onClear,
  isConnected,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<LogCategory>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const consoleBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when new logs arrive if enabled
  useEffect(() => {
    if (autoScroll && consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (selectedCategory !== 'ALL' && log.category !== selectedCategory) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          log.message.toLowerCase().includes(q) ||
          log.category.toLowerCase().includes(q) ||
          log.timestamp.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [logs, selectedCategory, searchQuery]);

  const countsByCategory = useMemo(() => {
    const counts: Record<string, number> = { ALL: logs.length };
    logs.forEach((log) => {
      counts[log.category] = (counts[log.category] || 0) + 1;
    });
    return counts;
  }, [logs]);

  const handleCopyLogs = async () => {
    try {
      const text = filteredLogs
        .map((l) => `[${l.timestamp}] [${l.category}] ${l.message}`)
        .join('\n');
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn('Failed to copy logs:', err);
    }
  };

  const getLogStyle = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-rose-400 bg-rose-950/20 border-rose-500/20';
      case 'warning':
        return 'text-amber-300 bg-amber-950/20 border-amber-500/20';
      case 'benign':
        return 'text-emerald-300/80 bg-emerald-950/15 border-emerald-500/15';
      case 'success':
        return 'text-emerald-300 bg-emerald-950/25 border-emerald-500/20';
      default:
        return 'text-cyan-200/90 bg-white/[0.02] border-white/5';
    }
  };

  const getCategoryBadge = (category: LogCategory) => {
    switch (category) {
      case 'ORCHESTRATOR':
        return 'bg-blue-900/40 text-blue-300 border-blue-500/30';
      case 'SENTINEL':
        return 'bg-purple-900/40 text-purple-300 border-purple-500/30';
      case 'WEBSOCKET':
        return 'bg-cyan-900/40 text-cyan-300 border-cyan-500/30';
      case 'SECURITY':
        return 'bg-rose-900/40 text-rose-300 border-rose-500/30';
      case 'PROJECT':
        return 'bg-amber-900/40 text-amber-300 border-amber-500/30';
      default:
        return 'bg-white/10 text-gray-300 border-white/10';
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#03060c] select-text">
      {/* Console Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-white/8 bg-white/[0.02] shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-300">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-white tracking-wide">Consola Central de Sistema</span>
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-950/40 border border-emerald-500/30 text-emerald-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Stream
              </span>
            </div>
            <p className="text-[10px] text-gray-500 font-mono">
              Sentinel, infraestrutura e telemetria isolados da conversa
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setAutoScroll((prev) => !prev)}
            className={`h-7 px-2.5 rounded text-[11px] font-medium border flex items-center gap-1.5 transition-all cursor-pointer ${
              autoScroll
                ? 'bg-cyan-950/40 border-cyan-500/30 text-cyan-200'
                : 'bg-white/[0.04] border-white/8 text-gray-400 hover:text-white'
            }`}
            title={autoScroll ? 'Pausar auto-scroll' : 'Ativar auto-scroll'}
          >
            {autoScroll ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span className="hidden sm:inline">{autoScroll ? 'Pausar Scroll' : 'Seguir'}</span>
          </button>

          <button
            onClick={handleCopyLogs}
            disabled={filteredLogs.length === 0}
            className="h-7 px-2.5 rounded text-[11px] font-medium border border-white/8 bg-white/[0.04] text-gray-300 hover:text-white hover:bg-white/[0.08] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 transition-all cursor-pointer"
            title="Copiar logs visíveis"
          >
            {copied ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span className="hidden sm:inline">{copied ? 'Copiado!' : 'Copiar'}</span>
          </button>

          <button
            onClick={onClear}
            disabled={logs.length === 0}
            className="h-7 px-2 rounded text-[11px] font-medium border border-white/8 bg-white/[0.04] text-gray-400 hover:text-rose-300 hover:bg-rose-950/20 hover:border-rose-500/30 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1 transition-all cursor-pointer"
            title="Limpar consola"
          >
            <Trash2 className="w-3 h-3" />
            <span className="hidden sm:inline">Limpar</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="px-4 py-2 border-b border-white/8 bg-black/40 flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div className="flex flex-wrap items-center gap-1">
          {(
            [
              { id: 'ALL', label: 'Todos', icon: Terminal },
              { id: 'ORCHESTRATOR', label: 'Orquestrador', icon: Cpu },
              { id: 'SENTINEL', label: 'Sentinel', icon: Shield },
              { id: 'WEBSOCKET', label: 'Rede/WS', icon: Wifi },
              { id: 'SECURITY', label: 'Segurança', icon: AlertTriangle },
              { id: 'PROJECT', label: 'Projeto', icon: Terminal },
            ] as const
          ).map((cat) => {
            const count = countsByCategory[cat.id] || 0;
            const active = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`h-6 px-2 rounded text-[11px] font-mono border transition-all cursor-pointer flex items-center gap-1.5 ${
                  active
                    ? 'bg-purple-950/50 border-purple-400/40 text-purple-200 font-semibold'
                    : 'bg-white/[0.02] border-white/5 text-gray-400 hover:text-white hover:bg-white/[0.05]'
                }`}
              >
                <span>{cat.label}</span>
                <span className={`text-[10px] ${active ? 'text-purple-300' : 'text-gray-600'}`}>({count})</span>
              </button>
            );
          })}
        </div>

        <div className="relative min-w-[160px] max-w-[240px] flex-1 sm:flex-initial">
          <Search className="w-3 h-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtrar eventos..."
            className="w-full h-6 pl-7 pr-2 text-[11px] bg-black/60 border border-white/10 rounded text-gray-200 placeholder-gray-600 outline-none focus:border-purple-400/30 font-mono"
          />
        </div>
      </div>

      {/* Log Stream Output */}
      <div
        className="flex-1 p-3 overflow-y-auto space-y-1 font-mono text-[11px] leading-relaxed scroll-smooth"
        style={{ scrollbarWidth: 'thin' }}
      >
        {filteredLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center py-16 text-gray-500">
            <Terminal className="w-8 h-8 text-gray-600 mb-2" />
            <p className="text-gray-400 text-xs font-semibold">Consola limpa ou sem eventos correspondentes</p>
            <p className="text-gray-600 text-[11px] mt-1 max-w-sm">
              Eventos de monitorização do Sentinel e estados do WebSocket surgirão aqui em tempo real.
            </p>
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`flex items-start gap-2 p-1.5 rounded border transition-colors ${getLogStyle(log.level)}`}
            >
              <span className="text-gray-500 text-[10px] shrink-0 font-semibold select-none">
                [{log.timestamp}]
              </span>
              <span
                className={`text-[9px] px-1 py-0.2 rounded border uppercase tracking-wider shrink-0 select-none ${getCategoryBadge(
                  log.category
                )}`}
              >
                {log.category}
              </span>
              <span className="break-all flex-1 select-text cursor-text">{log.message}</span>
            </div>
          ))
        )}
        <div ref={consoleBottomRef} />
      </div>

      {/* Console Bottom Status Footer */}
      <div className="px-4 py-2 border-t border-white/8 bg-[#020408] text-[10px] font-mono text-gray-500 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-rose-400'}`}
          />
          <span>{isConnected ? 'Runtime IPC Nativo (Tauri)' : 'Desconectado'}</span>
          <span>•</span>
          <span>{logs.length} eventos registados</span>
        </div>
        <span className="text-gray-600 hidden sm:inline">JarvisOS Central Telemetry Core</span>
      </div>
    </div>
  );
};
