import React, { useState, useMemo } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Users,
  FolderGit2,
  Trash2,
  Square,
  ArrowRight,
  RefreshCw,
  Search,
  WifiOff,
} from 'lucide-react';
import {
  useMissionRuntimeStore,
  missionRuntimeStore,
} from '../stores/missionRuntimeStore';
import { useWebSocket } from '../../../context/WebSocketContext';
import type { MissionData } from '../../../protocol/websocket';

interface MissionListViewProps {
  onOpenMission: (missionId: string, projectId?: string) => void;
  selectedProjectId?: string;
  onSelectProject?: (projectId: string) => void;
}

function formatRelativeTime(dateStringOrTimestamp?: string | number): string {
  if (!dateStringOrTimestamp) return 'desconhecido';
  const time =
    typeof dateStringOrTimestamp === 'number'
      ? dateStringOrTimestamp
      : Date.parse(dateStringOrTimestamp);
  if (isNaN(time)) return 'agora';

  const diffSec = Math.max(0, Math.floor((Date.now() - time) / 1000));
  if (diffSec < 5) return 'há instantes';
  if (diffSec < 60) return `há ${diffSec}s`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `há ${diffHours}h`;
  return `há ${Math.floor(diffHours / 24)}d`;
}

export const MissionListView: React.FC<MissionListViewProps> = ({
  onOpenMission,
  selectedProjectId,
  onSelectProject,
}) => {
  const store = useMissionRuntimeStore();
  const { projects, deleteMission, cancelMissionExecution, getMissions } = useWebSocket();

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTabFilter, setActiveTabFilter] = useState<'ALL' | 'ACTIVE' | 'TERMINAL'>('ALL');
  const [missionToDelete, setMissionToDelete] = useState<MissionData | null>(null);
  const [cancellingMissions, setCancellingMissions] = useState<Set<string>>(new Set());

  // Available projects mapping (id -> name)
  const projectMap = useMemo(() => {
    const map: Record<string, string> = {};
    projects.forEach((p) => {
      map[p.project_id] = p.project_name || p.project_id;
    });
    return map;
  }, [projects]);

  // Current project filter
  const currentProjectFilter = selectedProjectId || store.filterProjectId || 'ALL';

  // Filter missions
  const filteredMissions = useMemo(() => {
    let list = store.missions;

    // Filter by project
    if (currentProjectFilter !== 'ALL') {
      list = list.filter((m) => m.project_id === currentProjectFilter);
    }

    // Filter by state tab
    if (activeTabFilter === 'ACTIVE') {
      list = list.filter((m) =>
        ['RUNNING', 'CANCELLING', 'PLANNING', 'REPAIRING'].includes((m.status || '').toUpperCase())
      );
    } else if (activeTabFilter === 'TERMINAL') {
      list = list.filter((m) =>
        ['COMPLETED', 'CANCELLED', 'FAILED', 'BLOCKED'].includes((m.status || '').toUpperCase())
      );
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (m) =>
          m.title.toLowerCase().includes(q) ||
          m.objective.toLowerCase().includes(q) ||
          (m.project_name && m.project_name.toLowerCase().includes(q)) ||
          m.project_id.toLowerCase().includes(q)
      );
    }

    return list;
  }, [store.missions, currentProjectFilter, activeTabFilter, searchQuery]);

  const handleStop = (mission: MissionData) => {
    const execId = mission.execution_id || 'exec_default';
    setCancellingMissions((prev) => new Set(prev).add(mission.mission_id));
    cancelMissionExecution(mission.mission_id, execId, mission.project_id);
  };

  const confirmDelete = () => {
    if (!missionToDelete) return;
    deleteMission(missionToDelete.mission_id, missionToDelete.project_id);
    setMissionToDelete(null);
  };

  const renderStatusBadge = (mission: MissionData) => {
    const status = (mission.status || 'DRAFT').toUpperCase();
    const isCancelling = status === 'CANCELLING' || cancellingMissions.has(mission.mission_id);

    if (isCancelling) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-300">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
          A cancelar…
        </span>
      );
    }

    switch (status) {
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-0.5 text-xs font-medium text-cyan-300">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Em execução
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            Concluída
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-500/30 bg-zinc-500/10 px-2.5 py-0.5 text-xs font-medium text-zinc-400">
            <XCircle className="h-3 w-3 text-zinc-400" />
            Cancelada
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-0.5 text-xs font-medium text-rose-300">
            <AlertTriangle className="h-3 w-3 text-rose-400" />
            Falhou
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-600/30 bg-zinc-800/40 px-2.5 py-0.5 text-xs font-medium text-zinc-300">
            {status}
          </span>
        );
    }
  };

  const renderLiveStatus = (mission: MissionData) => {
    const isRunning = ['RUNNING', 'CANCELLING'].includes((mission.status || '').toUpperCase());
    const isStale = missionRuntimeStore.isStale(mission);

    if (isRunning) {
      if (isStale) {
        return (
          <span
            className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400/90"
            title="Nenhum evento recente recebido deste processo em execução"
          >
            <AlertTriangle className="h-3 w-3 text-amber-400" />
            Sem atualizações recentes
          </span>
        );
      }
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-cyan-400">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
          Live · {formatRelativeTime(store.lastEventAt[mission.mission_id] || mission.updated_at)}
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-zinc-400">
        <Clock className="h-3 w-3 text-zinc-500" />
        {formatRelativeTime(mission.updated_at || mission.completed_at || mission.created_at)}
      </span>
    );
  };

  return (
    <div className="flex h-full flex-col bg-[#0b1015] text-zinc-200">
      {/* 1. TOP BAR: TITLE, FILTERS & CONNECTION STATUS */}
      <div className="border-b border-white/[0.08] bg-[#0e161c]/80 px-6 py-4 backdrop-blur-md">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 shadow-sm">
                <Activity className="h-4 w-4" />
              </div>
              <h1 className="text-base font-semibold tracking-tight text-white">
                Missões do Workspace
              </h1>
              {/* Connection Pill */}
              <div className="ml-2 flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-[11px]">
                {store.connectionState === 'CONNECTED' ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    <span className="text-zinc-300">Conectado</span>
                  </>
                ) : store.connectionState === 'RECONNECTING' ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-ping" />
                    <span className="text-amber-300">A reconectar…</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3 w-3 text-rose-400" />
                    <span className="text-rose-300">Offline</span>
                  </>
                )}
                {store.isSyncing && (
                  <span className="ml-1 text-[10px] text-cyan-400 animate-pulse">· Syncing…</span>
                )}
              </div>
            </div>
            <p className="mt-1 text-xs text-zinc-400">
              Acompanhamento canónico em tempo real de execuções autónomas por projeto.
            </p>
          </div>

          {/* Quick controls: Project selector & refresh */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Project Filter Selector */}
            <div className="flex items-center rounded-lg border border-white/[0.08] bg-black/40 px-2.5 py-1 text-xs">
              <FolderGit2 className="mr-1.5 h-3.5 w-3.5 text-zinc-400" />
              <span className="mr-2 text-zinc-500">Projeto:</span>
              <select
                value={currentProjectFilter}
                onChange={(e) => {
                  const val = e.target.value;
                  if (onSelectProject) onSelectProject(val);
                  missionRuntimeStore.setFilterProjectId(val);
                }}
                className="bg-transparent font-medium text-zinc-200 outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-[#0e161c] text-zinc-200">
                  Todos os Projetos
                </option>
                {projects.map((p) => (
                  <option key={p.project_id} value={p.project_id} className="bg-[#0e161c] text-zinc-200">
                    {p.project_name || p.project_id}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => getMissions(currentProjectFilter)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-xs text-zinc-300 transition hover:border-white/20 hover:text-white"
              title="Sincronizar Missões"
            >
              <RefreshCw className="h-3.5 w-3.5 text-zinc-400" />
              <span>Sincronizar</span>
            </button>
          </div>
        </div>

        {/* 2. SECONDARY FILTER & SEARCH BAR */}
        <div className="mt-3.5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-white/[0.05] pt-3">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTabFilter('ALL')}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                activeTabFilter === 'ALL'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Todas ({store.missions.length})
            </button>
            <button
              onClick={() => setActiveTabFilter('ACTIVE')}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                activeTabFilter === 'ACTIVE'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Em Curso
            </button>
            <button
              onClick={() => setActiveTabFilter('TERMINAL')}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                activeTabFilter === 'TERMINAL'
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Histórico
            </button>
          </div>

          <div className="relative min-w-[220px]">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Pesquisar por título ou objetivo…"
              className="w-full rounded-md border border-white/[0.08] bg-black/40 pl-8 pr-3 py-1 text-xs text-zinc-200 placeholder-zinc-500 outline-none transition focus:border-cyan-500/40"
            />
          </div>
        </div>
      </div>

      {/* 3. MISSION LIST TABLE / CARDS */}
      <div className="flex-1 overflow-y-auto p-6">
        {filteredMissions.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.08] bg-white/[0.01] p-8 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.04] text-zinc-500 mb-3">
              <Activity className="h-5 w-5" />
            </div>
            <p className="text-sm font-medium text-zinc-300">Nenhuma missão encontrada</p>
            <p className="mt-1 text-xs text-zinc-500 max-w-sm">
              {currentProjectFilter !== 'ALL'
                ? `Não existem missões registadas para o projeto "${projectMap[currentProjectFilter] || currentProjectFilter}".`
                : 'Inicie uma nova missão no Workspace para acompanhar a execução autónoma.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredMissions.map((mission) => {
              const pName =
                mission.project_name ||
                projectMap[mission.project_id] ||
                mission.project_id;
              const isRunning = ['RUNNING', 'CANCELLING'].includes(
                (mission.status || '').toUpperCase()
              );
              const isTerminal = ['COMPLETED', 'CANCELLED', 'FAILED'].includes(
                (mission.status || '').toUpperCase()
              );
              const isCancelling =
                mission.status === 'CANCELLING' || cancellingMissions.has(mission.mission_id);
              const progressPct = Math.round(Number(mission.progress || 0));

              return (
                <div
                  key={mission.mission_id}
                  className="group relative rounded-xl border border-white/[0.08] bg-[#0e151b]/80 p-4 transition hover:border-white/20 hover:bg-[#121c24]/90 shadow-sm"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    {/* LEFT: Project / Mission Identity */}
                    <div className="min-w-0 flex-1 cursor-pointer" onClick={() => onOpenMission(mission.mission_id, mission.project_id)}>
                      {/* Explicit Project Breadcrumb */}
                      <div className="mb-1.5 flex items-center gap-2 text-xs">
                        <span className="inline-flex items-center gap-1 rounded bg-white/[0.05] px-2 py-0.5 font-medium text-cyan-300 border border-white/5">
                          <FolderGit2 className="h-3 w-3 text-cyan-400" />
                          {pName}
                        </span>
                        <span className="text-zinc-600">/</span>
                        <span className="font-mono text-[11px] text-zinc-500">
                          {mission.mission_id}
                        </span>
                        {mission.execution_id && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="font-mono text-[10px] text-zinc-500">
                              exec: {mission.execution_id}
                            </span>
                          </>
                        )}
                      </div>

                      {/* Title & Objective */}
                      <h2 className="text-sm font-semibold text-white group-hover:text-cyan-200 transition-colors truncate">
                        {mission.title || 'Missão Sem Título'}
                      </h2>
                      {mission.objective && (
                        <p className="mt-0.5 text-xs text-zinc-400 line-clamp-1">
                          {mission.objective}
                        </p>
                      )}
                    </div>

                    {/* CENTER: Status & Progress */}
                    <div className="flex flex-wrap items-center gap-6 lg:border-l lg:border-r lg:border-white/[0.06] lg:px-6">
                      {/* Status */}
                      <div className="min-w-[110px]">
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">
                          Estado
                        </div>
                        {renderStatusBadge(mission)}
                      </div>

                      {/* Progress */}
                      <div className="min-w-[130px]">
                        <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
                          <span>Progresso</span>
                          <span className="font-mono font-semibold text-cyan-300">
                            {progressPct}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300"
                            style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
                          />
                        </div>
                      </div>

                      {/* Agents & Stage */}
                      <div className="min-w-[90px]">
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">
                          Agentes
                        </div>
                        <div className="flex items-center gap-1 text-xs text-zinc-300">
                          <Users className="h-3.5 w-3.5 text-zinc-400" />
                          <span>
                            {mission.current_stage || (mission.status === 'RUNNING' ? '3 agentes' : 'Equipa')}
                          </span>
                        </div>
                      </div>

                      {/* Live / Staleness */}
                      <div className="min-w-[120px]">
                        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">
                          Última Atualização
                        </div>
                        {renderLiveStatus(mission)}
                      </div>
                    </div>

                    {/* RIGHT: Safe Lifecycle Action Controls */}
                    <div className="flex items-center gap-2 shrink-0">
                      {/* RUNNING: Stop execution button */}
                      {isRunning && (
                        <button
                          type="button"
                          disabled={isCancelling}
                          onClick={() => handleStop(mission)}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                            isCancelling
                              ? 'border-amber-500/30 bg-amber-500/10 text-amber-300 cursor-not-allowed'
                              : 'border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 hover:border-rose-500/50'
                          }`}
                          title="Interromper cooperativamente a execução desta missão"
                        >
                          <Square className="h-3 w-3" />
                          <span>{isCancelling ? 'A cancelar…' : 'Parar'}</span>
                        </button>
                      )}

                      {/* TERMINAL: Remove from history button */}
                      {isTerminal && (
                        <button
                          type="button"
                          onClick={() => setMissionToDelete(mission)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700/60 bg-white/[0.02] px-2.5 py-1.5 text-xs text-zinc-400 transition hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300"
                          title="Remover permanentemente esta missão do histórico"
                        >
                          <Trash2 className="h-3 w-3" />
                          <span>Remover</span>
                        </button>
                      )}

                      {/* View details button */}
                      <button
                        type="button"
                        onClick={() => onOpenMission(mission.mission_id, mission.project_id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-300 transition hover:bg-cyan-500/20 hover:border-cyan-500/40"
                      >
                        <span>Abrir</span>
                        <ArrowRight className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. EXPLICIT MODAL: REMOVE FROM HISTORY CONFIRMATION */}
      {missionToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md rounded-xl border border-white/10 bg-[#0d1419] p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400 mb-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-500/10 border border-rose-500/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <h2 className="text-base font-semibold text-white">Remover do histórico?</h2>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed mb-4">
              Esta ação remove a missão <strong className="text-white">"{missionToDelete.title}"</strong> ({missionToDelete.mission_id}) do histórico do projeto <strong className="text-cyan-300">"{missionToDelete.project_name || projectMap[missionToDelete.project_id] || missionToDelete.project_id}"</strong>. A execução já terminou.
            </p>

            <div className="rounded-lg border border-white/5 bg-black/30 p-3 text-[11px] text-zinc-400 mb-5">
              O registo da missão e os ficheiros de estado associados serão expurgados. Esta operação é irreversível.
            </div>

            <div className="flex items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setMissionToDelete(null)}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-white/[0.08]"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className="rounded-lg border border-rose-500/40 bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/30 hover:border-rose-500/60"
              >
                Confirmar Remoção
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
