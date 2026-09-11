import React from 'react';
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronRight,
  GitCommit,
  X,
} from 'lucide-react';
import type {
  MissionControlStateData,
  MissionControlEventData,
  CommandType,
} from '../../../protocol/websocket';

interface MissionTaskGraphPanelProps {
  missionState: MissionControlStateData;
  deduplicatedEvents: MissionControlEventData[];
  expandedEventId: string | null;
  onToggleExpandEvent: (eventId: string) => void;
  onSendCommand: (
    cmdType: CommandType,
    taskId?: string | null,
    payload?: Record<string, any>,
    reason?: string
  ) => void;
}

export const MissionTaskGraphPanel: React.FC<MissionTaskGraphPanelProps> = ({
  missionState,
  deduplicatedEvents,
  expandedEventId,
  onToggleExpandEvent,
  onSendCommand,
}) => {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
              Grafo de Execução Topológico (TaskGraph DAG)
            </h3>
            <p className="text-xs text-gray-400">Ordenação estrita por dependências causais</p>
          </div>
          <span className="rounded-md border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 font-mono text-xs font-semibold text-cyan-200">
            {(missionState.tasks || []).length} Tarefas Mapeadas
          </span>
        </div>

        <div className="space-y-3">
          {(missionState.tasks || []).map((tsk, idx) => (
            <div
              key={tsk.id}
              id={`task-card-${tsk.id}`}
              className="flex flex-col gap-3 rounded-lg border border-white/8 bg-black/40 p-4 transition-all hover:border-cyan-500/30 lg:flex-row lg:items-center lg:justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-cyan-500/20 font-mono text-xs font-bold text-cyan-300">
                  {idx + 1}
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-cyan-300">{tsk.id}</span>
                    <span className="rounded bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-gray-300">
                      Responsável: {tsk.owner}
                    </span>
                    <span className="rounded bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-gray-300">
                      Estado: {tsk.status}
                    </span>
                    {/* Priority dropdown */}
                    <div className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                      <span>Prioridade:</span>
                      <select
                        id={`select-priority-${tsk.id}`}
                        value={tsk.priority || 'NORMAL'}
                        onChange={(e) =>
                          onSendCommand(
                            'CHANGE_PRIORITY',
                            tsk.id,
                            { new_priority: e.target.value },
                            `Prioridade de ${tsk.id} alterada para ${e.target.value}`
                          )
                        }
                        className="rounded border border-amber-500/30 bg-black/60 px-1 py-0.5 text-[10px] font-bold text-amber-200 focus:outline-none"
                      >
                        <option value="CRITICAL">CRITICAL</option>
                        <option value="HIGH">HIGH</option>
                        <option value="NORMAL">NORMAL</option>
                        <option value="LOW">LOW</option>
                      </select>
                    </div>
                  </div>
                  <h4 className="mt-1 text-sm font-semibold text-white">{tsk.title}</h4>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs">
                {/* Reorder Buttons */}
                <div className="flex items-center gap-1">
                  <button
                    id={`btn-reorder-up-${tsk.id}`}
                    disabled={idx === 0}
                    onClick={() =>
                      onSendCommand('REORDER', tsk.id, { direction: 'UP' }, `Subir posição de ${tsk.id}`)
                    }
                    className="rounded border border-white/10 bg-white/5 p-1 text-gray-300 hover:bg-cyan-500/20 hover:text-cyan-200 disabled:opacity-30"
                    title="Subir posição topológica"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    id={`btn-reorder-down-${tsk.id}`}
                    disabled={idx === missionState.tasks.length - 1}
                    onClick={() =>
                      onSendCommand('REORDER', tsk.id, { direction: 'DOWN' }, `Descer posição de ${tsk.id}`)
                    }
                    className="rounded border border-white/10 bg-white/5 p-1 text-gray-300 hover:bg-cyan-500/20 hover:text-cyan-200 disabled:opacity-30"
                    title="Descer posição topológica"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="text-gray-400">
                  <span>Dependências: </span>
                  {tsk.dependencies.length > 0 ? (
                    <span className="font-mono text-purple-300">{tsk.dependencies.join(', ')}</span>
                  ) : (
                    <span className="text-gray-500">Nenhuma (Root)</span>
                  )}
                </div>
                <div className="text-gray-400">
                  <span>Duração: </span>
                  <strong className="font-mono text-gray-200">{tsk.duration_seconds}s</strong>
                </div>
                <div className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-emerald-300 font-semibold text-[11px]">
                  {tsk.evidence}
                </div>

                {/* Approval Section for PENDING_APPROVAL tasks */}
                {(tsk.status === 'PENDING_APPROVAL' || tsk.approval_status === 'PENDING_APPROVAL') && (
                  <div
                    id={`task-approval-${tsk.id}`}
                    className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/20 px-2.5 py-1"
                  >
                    <span className="text-[11px] font-bold text-amber-200">Requer Aprovação:</span>
                    <button
                      id={`btn-approve-${tsk.id}`}
                      onClick={() =>
                        onSendCommand(
                          'APPROVE',
                          tsk.id,
                          { decision: 'APPROVE' },
                          `Aprovação concedida para ${tsk.id}`
                        )
                      }
                      className="inline-flex items-center gap-1 rounded bg-emerald-600 px-2 py-0.5 text-[11px] font-bold text-white hover:bg-emerald-500"
                    >
                      <Check className="h-3 w-3" />
                      <span>Aprovar</span>
                    </button>
                    <button
                      id={`btn-reject-${tsk.id}`}
                      onClick={() =>
                        onSendCommand(
                          'APPROVE',
                          tsk.id,
                          { decision: 'REJECT' },
                          `Rejeição aplicada para ${tsk.id}`
                        )
                      }
                      className="inline-flex items-center gap-1 rounded bg-rose-600 px-2 py-0.5 text-[11px] font-bold text-white hover:bg-rose-500"
                    >
                      <X className="h-3 w-3" />
                      <span>Rejeitar</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 18 & 19. MISSION TIMELINE (CHRONOLOGICAL & DEDUPLICATED) */}
      <div className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitCommit className="h-5 w-5 text-purple-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
              Timeline Cronológica de Eventos Determinísticos
            </h3>
          </div>
          <span className="text-xs text-gray-400">
            {(deduplicatedEvents || []).length} Eventos únicos (Deduplicação Ativa)
          </span>
        </div>

        <div className="relative pl-6 before:absolute before:bottom-0 before:left-2.5 before:top-2 before:w-0.5 before:bg-white/10">
          {(deduplicatedEvents || []).map((ev) => {
            const isExpanded = expandedEventId === ev.event_id;
            return (
              <div key={ev.event_id} className="relative mb-4 last:mb-0">
                <div className="absolute -left-6 top-1 h-3 w-3 rounded-full border-2 border-cyan-400 bg-black" />
                <div
                  onClick={() => onToggleExpandEvent(ev.event_id)}
                  className="cursor-pointer rounded-lg border border-white/8 bg-black/40 p-3 transition-all hover:border-cyan-500/30"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-cyan-300">{ev.event_id}</span>
                      <span className="rounded bg-purple-500/20 px-1.5 py-0.2 text-[10px] font-bold text-purple-200">
                        {ev.agent}
                      </span>
                      <span className="text-xs font-semibold text-white">{ev.title}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span className="font-mono text-[11px]">
                        {new Date(ev.timestamp * 1000).toLocaleTimeString()}
                      </span>
                      {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 border-t border-white/8 pt-3 text-xs text-gray-300">
                      <p>
                        <strong>Tipo de Evento:</strong>{' '}
                        <span className="font-mono text-cyan-300">{ev.type}</span>
                      </p>
                      <p className="mt-1">
                        <strong>Fase:</strong> {ev.stage}
                      </p>
                      {ev.details && Object.keys(ev.details).length > 0 && (
                        <div className="mt-2 rounded bg-black/60 p-2 font-mono text-[11px]">
                          <pre className="text-gray-300">{JSON.stringify(ev.details, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
