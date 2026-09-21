import React, { useState, useMemo } from 'react';
import {
  CheckCircle2,
  Circle,
  AlertCircle,
  Search,
  ChevronRight,
  X,
  ArrowUp,
  ArrowDown,
  Check,
  Flag,
  User,
  ShieldCheck,
} from 'lucide-react';
import type { MissionControlTaskData, CommandType } from '../../../protocol/websocket';

interface MissionTasksViewProps {
  tasks: MissionControlTaskData[];
  onSendCommand: (
    cmdType: CommandType,
    taskId?: string | null,
    payload?: Record<string, any>,
    reason?: string
  ) => void;
  isSubmittingCommand?: boolean;
}

export const MissionTasksView: React.FC<MissionTasksViewProps> = ({
  tasks,
  onSendCommand,
  isSubmittingCommand,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      const matchesSearch =
        t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.owner && t.owner.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchesSearch) return false;
      if (filterStatus === 'ALL') return true;
      return t.status === filterStatus;
    });
  }, [tasks, searchQuery, filterStatus]);

  const selectedTask = useMemo(
    () => tasks.find((t) => t.id === selectedTaskId) || null,
    [tasks, selectedTaskId]
  );

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'DONE':
        return <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />;
      case 'IN_PROGRESS':
        return (
          <div className="h-4 w-4 shrink-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
        );
      case 'BLOCKED':
        return <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />;
      default:
        return <Circle className="h-4 w-4 text-gray-600 shrink-0" />;
    }
  };

  const getPriorityBadge = (priority?: string) => {
    switch (priority) {
      case 'HIGH':
        return (
          <span className="rounded border border-rose-500/20 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-bold text-rose-300">
            ALTA
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
            MÉDIA
          </span>
        );
      default:
        return (
          <span className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-bold text-gray-400">
            BAIXA
          </span>
        );
    }
  };

  return (
    <div className="relative flex h-full gap-4 max-w-7xl mx-auto overflow-hidden">
      {/* MAIN TASK LIST */}
      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-white/8 bg-white/[0.02]">
        {/* TOOLBAR: SEARCH & FILTER PILLS */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/6 p-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Pesquisar tarefas..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-md border border-white/8 bg-black/25 py-1.5 pl-8 pr-3 text-xs text-gray-200 placeholder-gray-500 outline-none focus:border-cyan-400/30"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1 overflow-x-auto">
            {[
              { id: 'ALL', label: 'Todas', count: tasks.length },
              { id: 'IN_PROGRESS', label: 'Em curso', count: tasks.filter((t) => t.status === 'IN_PROGRESS').length },
              { id: 'DONE', label: 'Concluídas', count: tasks.filter((t) => t.status === 'DONE').length },
              { id: 'PENDING', label: 'Pendentes', count: tasks.filter((t) => t.status === 'PENDING').length },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterStatus(f.id)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  filterStatus === f.id
                    ? 'bg-cyan-500/15 text-cyan-200 font-semibold border border-cyan-400/30'
                    : 'text-gray-400 hover:bg-white/[0.04] hover:text-gray-200'
                }`}
              >
                <span>{f.label}</span>
                <span className="text-[10px] text-gray-500 font-mono">({f.count})</span>
              </button>
            ))}
          </div>
        </div>

        {/* TASK ROWS */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {filteredTasks.length === 0 ? (
            <div className="py-12 text-center text-xs text-gray-500">Nenhuma tarefa encontrada.</div>
          ) : (
            filteredTasks.map((task) => {
              const isSelected = selectedTaskId === task.id;
              return (
                <div
                  key={task.id}
                  onClick={() => setSelectedTaskId(task.id)}
                  className={`group flex items-center justify-between gap-3 rounded-md border p-3 text-xs transition-all cursor-pointer ${
                    isSelected
                      ? 'border-cyan-400/40 bg-cyan-950/20'
                      : 'border-white/5 bg-white/[0.015] hover:border-white/15 hover:bg-white/[0.035]'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    {getStatusIcon(task.status)}
                    <span className="font-mono text-[11px] font-semibold text-gray-400 shrink-0">
                      {task.id}
                    </span>
                    <span className="truncate text-gray-200 group-hover:text-white font-medium">
                      {task.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {task.owner && (
                      <span className="flex items-center gap-1 rounded bg-white/5 px-2 py-0.5 text-[11px] text-gray-300">
                        <User className="h-3 w-3 text-gray-400" />
                        <span>{task.owner}</span>
                      </span>
                    )}

                    {getPriorityBadge(task.priority)}

                    <ChevronRight className="h-3.5 w-3.5 text-gray-500 group-hover:text-gray-300 transition-colors" />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* DETAIL DRAWER (SIDE PANEL) */}
      {selectedTask && (
        <div className="w-80 sm:w-96 flex flex-col rounded-lg border border-white/8 bg-[#0c1318] p-4 shrink-0 overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-white/6 mb-4">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-cyan-300">{selectedTask.id}</span>
              {getPriorityBadge(selectedTask.priority)}
            </div>
            <button
              onClick={() => setSelectedTaskId(null)}
              className="rounded p-1 text-gray-400 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-4 flex-1 text-xs">
            <div>
              <h3 className="text-sm font-semibold text-white">{selectedTask.title}</h3>
              <div className="mt-2 flex items-center gap-2 text-gray-400">
                <span>Estado:</span>
                <span className="font-bold text-gray-200">{selectedTask.status}</span>
              </div>
            </div>

            {selectedTask.owner && (
              <div className="rounded-md border border-white/6 bg-white/[0.02] p-2.5">
                <span className="text-gray-400">Agente Responsável:</span>
                <p className="mt-0.5 font-medium text-white">{selectedTask.owner}</p>
              </div>
            )}

            {selectedTask.evidence && (
              <div className="rounded-md border border-emerald-500/20 bg-emerald-950/20 p-2.5">
                <div className="flex items-center gap-1.5 text-emerald-300 font-semibold mb-1">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Evidência de Execução</span>
                </div>
                <p className="text-gray-300">{selectedTask.evidence}</p>
              </div>
            )}

            {/* OPERATOR ACTIONS FOR THIS TASK */}
            <div className="pt-4 border-t border-white/6 space-y-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                Ações do Operador
              </span>

              <div className="grid grid-cols-2 gap-2">
                {selectedTask.status !== 'DONE' && (
                  <button
                    disabled={isSubmittingCommand}
                    onClick={() =>
                      onSendCommand('APPROVE', selectedTask.id, {}, `Aprovação manual da tarefa ${selectedTask.id}`)
                    }
                    className="flex items-center justify-center gap-1.5 rounded-md border border-emerald-400/30 bg-emerald-400/10 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-400/20 transition-colors disabled:opacity-50"
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>Aprovar</span>
                  </button>
                )}

                <button
                  disabled={isSubmittingCommand}
                  onClick={() =>
                    onSendCommand(
                      'CHANGE_PRIORITY',
                      selectedTask.id,
                      { new_priority: selectedTask.priority === 'HIGH' ? 'LOW' : 'HIGH' },
                      `Alterar prioridade de ${selectedTask.id}`
                    )
                  }
                  className="flex items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] py-1.5 text-xs font-semibold text-gray-300 hover:bg-white/[0.08] hover:text-white transition-colors disabled:opacity-50"
                >
                  <Flag className="h-3.5 w-3.5" />
                  <span>{selectedTask.priority === 'HIGH' ? 'Baixar Prio' : 'Prioridade Alta'}</span>
                </button>
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  disabled={isSubmittingCommand}
                  onClick={() =>
                    onSendCommand('REORDER', selectedTask.id, { direction: 'UP' }, `Mover tarefa ${selectedTask.id} acima`)
                  }
                  className="flex-1 flex items-center justify-center gap-1 rounded-md border border-white/10 bg-white/[0.02] py-1 text-xs text-gray-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                  <span>Subir</span>
                </button>
                <button
                  disabled={isSubmittingCommand}
                  onClick={() =>
                    onSendCommand('REORDER', selectedTask.id, { direction: 'DOWN' }, `Mover tarefa ${selectedTask.id} abaixo`)
                  }
                  className="flex-1 flex items-center justify-center gap-1 rounded-md border border-white/10 bg-white/[0.02] py-1 text-xs text-gray-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                  <span>Descer</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MissionTasksView;
