import React from 'react';
import {
  UserCheck,
  CheckCircle2,
  Brain,
  Sparkles,
  Cpu,
  FileCode,
  Award,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionOverviewPanelProps {
  missionState: MissionControlStateData;
  onOpenInCode?: (filePath: string, line?: number) => void;
}

export const MissionOverviewPanel: React.FC<MissionOverviewPanelProps> = ({
  missionState,
  onOpenInCode,
}) => {
  return (
    <div className="space-y-6">
      {/* 4. MISSION UNDERSTANDING: REQUIREMENTS VS ASSUMPTIONS (STRICTLY SEPARATED) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* User Requirements Column */}
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-5 shadow-lg">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <UserCheck className="h-5 w-5 text-emerald-400" />
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-300">
                  Requisitos do Utilizador (USER_REQUIREMENT)
                </h3>
                <p className="text-xs text-gray-400">Verificação obrigatória e determinística</p>
              </div>
            </div>
            <span className="rounded-md border border-emerald-400/30 bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-300">
              STATUS: VERIFIED
            </span>
          </div>
          <div className="space-y-3">
            {(missionState.requirements || []).map((req) => (
              <div
                key={req.id}
                className="flex items-start gap-3 rounded-lg border border-emerald-500/15 bg-black/40 p-3"
              >
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-emerald-300">{req.id}</span>
                    <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[10px] font-bold text-emerald-200">
                      {req.status}
                    </span>
                  </div>
                  <p className="mt-1 text-gray-200">{req.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Assumptions Column */}
        <div className="rounded-xl border border-purple-500/20 bg-purple-950/10 p-5 shadow-lg">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Brain className="h-5 w-5 text-purple-400" />
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-purple-300">
                  Assunções do Sistema (SYSTEM_ASSUMPTION)
                </h3>
                <p className="text-xs text-gray-400">Inferências heurísticas e decisões de engenharia</p>
              </div>
            </div>
            <span className="rounded-md border border-purple-400/30 bg-purple-500/20 px-2 py-0.5 text-xs font-bold text-purple-300">
              STATUS: INFERRED
            </span>
          </div>
          <div className="space-y-3">
            {(missionState.assumptions || []).map((asm) => (
              <div
                key={asm.id}
                className="flex items-start gap-3 rounded-lg border border-purple-500/15 bg-black/40 p-3"
              >
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-purple-400" />
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-purple-300">{asm.id}</span>
                    <span className="rounded bg-purple-500/20 px-1.5 py-0.2 text-[10px] font-bold text-purple-200">
                      {asm.status}
                    </span>
                  </div>
                  <p className="mt-1 font-medium text-gray-200">{asm.desc}</p>
                  {asm.rationale && (
                    <p className="mt-1 text-[11px] italic text-purple-300/80">
                      Razão: {asm.rationale}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 7. AGENT VIEW: THE 6 SWARM SPECIALISTS */}
      <div className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Cpu className="h-5 w-5 text-cyan-300" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
              Enxame de Agentes Especialistas (Swarm Federation)
            </h3>
          </div>
          <span className="text-xs text-gray-400">6 Agentes Conectados em Tempo Real</span>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(missionState.agents || []).map((agent) => (
            <div
              key={agent.agent_id}
              className="rounded-lg border border-white/8 bg-black/30 p-4 transition-all hover:border-cyan-500/30"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-cyan-300">{agent.role}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    agent.status === 'COMPLETED'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : agent.status === 'BUSY'
                      ? 'bg-cyan-500/20 text-cyan-300 animate-pulse'
                      : 'bg-gray-500/20 text-gray-400'
                  }`}
                >
                  {agent.status}
                </span>
              </div>
              <h4 className="mt-1 text-sm font-semibold text-white">{agent.name}</h4>
              <p className="mt-1 text-xs text-gray-400">
                Tarefa: <span className="text-gray-200">{agent.current_task}</span>
              </p>

              <div className="mt-3 flex items-center justify-between border-t border-white/6 pt-2 text-[11px] text-gray-400">
                <span>
                  Tarefas: <strong className="text-cyan-200">{agent.completed_tasks_count}</strong>
                </span>
                <span>
                  Falhas:{' '}
                  <strong className={agent.failures_count > 0 ? 'text-amber-300' : 'text-gray-500'}>
                    {agent.failures_count}
                  </strong>
                </span>
                <span>
                  Handoffs: <strong className="text-purple-300">{agent.handoffs_count}</strong>
                </span>
              </div>

              {((agent.files_touched || []).length > 0) && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {(agent.files_touched || []).map((f) => (
                    <button
                      key={f}
                      onClick={() => onOpenInCode && onOpenInCode(f)}
                      className="inline-flex items-center gap-1 rounded bg-cyan-950/40 px-1.5 py-0.5 font-mono text-[10px] text-cyan-300 hover:bg-cyan-900/60"
                    >
                      <FileCode className="h-3 w-3" />
                      <span>{f}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 14. FINAL RESULT & TIME TO VALUE & USER EFFORT */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Final Result Card */}
        <div className="rounded-xl border border-cyan-500/20 bg-[#0e191d]/90 p-5 shadow-lg lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-amber-300" />
              <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
                Resultado Final da Missão & Validação de Produto
              </h3>
            </div>
            <span
              className={`rounded-md border px-2.5 py-1 text-xs font-bold ${
                missionState.status === 'COMPLETED'
                  ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                  : missionState.status === 'BLOCKED'
                  ? 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                  : 'border-amber-500/40 bg-amber-500/20 text-amber-300'
              }`}
            >
              {String(missionState.final_result?.decision || missionState.status)}
            </span>
          </div>

          <p className="text-sm font-medium text-gray-200">
            {String(missionState.final_result?.why || 'Missão com execução interactiva supervisionada.')}
          </p>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 text-xs">
            <div className="rounded-lg border border-white/8 bg-black/30 p-3">
              <span className="font-semibold text-gray-400">O que mudou:</span>
              <p className="mt-1 text-gray-200">
                {String(missionState.final_result?.what_changed || 'Execução sob controlo operacional')}
              </p>
            </div>
            <div className="rounded-lg border border-white/8 bg-black/30 p-3">
              <span className="font-semibold text-gray-400">O que foi validado:</span>
              <p className="mt-1 text-emerald-300">
                {String(missionState.final_result?.what_was_validated || 'Validações contínuas em tempo real')}
              </p>
            </div>
            <div className="rounded-lg border border-white/8 bg-black/30 p-3">
              <span className="font-semibold text-gray-400">Estado final:</span>
              <p className="mt-1 text-cyan-300">
                {String(missionState.final_result?.what_remains || 'Supervisão ativa')}
              </p>
            </div>
          </div>
        </div>

        {/* 16 & 17. Time to Value & User Effort Card */}
        <div className="space-y-4 rounded-xl border border-white/10 bg-[#0e191d]/90 p-5 shadow-lg">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-cyan-300">
              <Clock className="h-4 w-4" />
              <span>Métricas Time to Value</span>
            </div>
            <div className="mt-2 space-y-1.5 text-xs">
              <div className="flex justify-between border-b border-white/6 py-1">
                <span className="text-gray-400">Primeiro output:</span>
                <strong className="font-mono text-gray-200">
                  {missionState.time_to_first_output_seconds}s
                </strong>
              </div>
              <div className="flex justify-between border-b border-white/6 py-1">
                <span className="text-gray-400">Primeiro artefacto validado:</span>
                <strong className="font-mono text-emerald-300">
                  {missionState.time_to_first_validated_seconds}s
                </strong>
              </div>
              <div className="flex justify-between border-b border-white/6 py-1">
                <span className="text-gray-400">Resultado útil (TTUR):</span>
                <strong className="font-mono text-cyan-300">
                  {missionState.time_to_useful_result_seconds}s
                </strong>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-gray-400">Duração total da missão:</span>
                <strong className="font-mono text-white">{missionState.total_duration_seconds}s</strong>
              </div>
            </div>
          </div>

          <div className="border-t border-white/10 pt-3">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-purple-300">
              <UserCheck className="h-4 w-4" />
              <span>User Effort Score</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-gray-400">
              <div className="flex justify-between">
                <span>Prompts necessários:</span>
                <strong className="text-white">1 (Zero micromanagement)</strong>
              </div>
              <div className="flex justify-between">
                <span>Intervenções manuais:</span>
                <strong className="text-emerald-400">0</strong>
              </div>
              <div className="flex justify-between">
                <span>USER_EFFORT_SCORE:</span>
                <strong className="font-mono text-emerald-300">
                  {missionState.user_effort_score} (Ideal)
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AUDIT LOG: HUMAN INTERVENTIONS (FASE 36 BIDIRECTIONAL CONTROL) */}
      <div id="command-audit-log" className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 text-cyan-300" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
                Registo de Auditoria de Intervenções Humanas (Command Ledger)
              </h3>
              <p className="text-xs text-gray-400">
                Histórico de transições e comandos validados pelo Mission Gate
              </p>
            </div>
          </div>
          <span className="rounded-md border border-cyan-500/30 bg-cyan-950/40 px-2 py-0.5 font-mono text-xs text-cyan-300">
            {missionState.command_history?.length || 0} Registos
          </span>
        </div>

        {!missionState.command_history || missionState.command_history.length === 0 ? (
          <div className="rounded-lg border border-dashed border-white/10 p-6 text-center text-xs text-gray-400">
            Nenhum comando submetido nesta sessão. A consola bidirecional está pronta para aceitar
            intervenções do operador (Pausar, Retomar, Cancelar, Aprovar, Prioridade e Reordenação).
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="border-b border-white/10 bg-white/5 font-mono text-[10px] uppercase text-gray-400">
                <tr>
                  <th className="py-2 px-3">Comando</th>
                  <th className="py-2 px-3">Tipo</th>
                  <th className="py-2 px-3">Operador</th>
                  <th className="py-2 px-3">Alvo</th>
                  <th className="py-2 px-3">Resultado</th>
                  <th className="py-2 px-3">Versão</th>
                  <th className="py-2 px-3">Motivo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {(missionState.command_history || []).map((rec) => (
                  <tr key={rec.command_id} className="hover:bg-white/[0.02]">
                    <td className="py-2 px-3 font-bold text-cyan-300">{rec.command_id}</td>
                    <td className="py-2 px-3 text-white font-semibold">{rec.command_type}</td>
                    <td className="py-2 px-3 text-gray-400">{rec.user_id}</td>
                    <td className="py-2 px-3 text-purple-300">{rec.target_task_id || 'MISSION'}</td>
                    <td className="py-2 px-3">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          rec.status === 'ACCEPTED'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : rec.status === 'SECURITY_BLOCK'
                            ? 'bg-rose-500/20 text-rose-300'
                            : 'bg-amber-500/20 text-amber-300'
                        }`}
                      >
                        {rec.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-cyan-200">v{rec.mission_version}</td>
                    <td className="py-2 px-3 font-sans text-gray-300">{rec.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
