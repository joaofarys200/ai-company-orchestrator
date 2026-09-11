import React from 'react';
import { Wrench, GitBranch, Database, FileCode } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionRepairPanelProps {
  missionState: MissionControlStateData;
  onOpenInCode?: (filePath: string, line?: number) => void;
}

export const MissionRepairPanel: React.FC<MissionRepairPanelProps> = ({
  missionState,
  onOpenInCode,
}) => {
  return (
    <div className="space-y-6">
      {/* 9. REPAIR EXPLAINABILITY */}
      <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-5">
        <div className="mb-4 flex items-center gap-2.5">
          <Wrench className="h-5 w-5 text-amber-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-amber-300">
            Auto-Cura Cirúrgica (Repair Explainability: Failure → Diagnosis → Patch → Validation)
          </h3>
        </div>

        {(!missionState.repairs || missionState.repairs.length === 0) ? (
          <div className="rounded-lg border border-white/8 bg-black/20 p-4 text-xs text-gray-400">
            Nenhuma falha ocorreu nesta execução. O plano executou sem erros na primeira passagem.
          </div>
        ) : (
          (missionState.repairs || []).map((rep, idx) => (
            <div key={idx} className="space-y-3 rounded-lg border border-amber-500/20 bg-black/40 p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-rose-300">FALHA: {rep.failure_title}</span>
                <span className="font-mono text-xs text-gray-400">Duração: {rep.duration_ms}ms</span>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-3 text-xs">
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Diagnóstico:</strong>
                  <p className="mt-1 text-gray-200">{rep.diagnosis}</p>
                </div>
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Patch Aplicado:</strong>
                  <p className="mt-1 text-cyan-200">{rep.patch_description}</p>
                </div>
                <div className="rounded border border-emerald-500/20 bg-emerald-950/20 p-2.5">
                  <strong className="text-emerald-400">Validação:</strong>
                  <p className="mt-1 text-emerald-300">{rep.validation_result}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <span className="text-xs text-gray-400">Ficheiros corrigidos:</span>
                {rep.files_changed.map((f) => (
                  <button
                    key={f}
                    onClick={() => onOpenInCode && onOpenInCode(f)}
                    className="inline-flex items-center gap-1 rounded bg-amber-950/40 px-2 py-0.5 font-mono text-xs text-amber-300 hover:bg-amber-900/60"
                  >
                    <FileCode className="h-3 w-3" />
                    <span>{f}</span>
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 10. REPLAN EXPLAINABILITY */}
      <div className="rounded-xl border border-purple-500/20 bg-purple-950/10 p-5">
        <div className="mb-4 flex items-center gap-2.5">
          <GitBranch className="h-5 w-5 text-purple-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-purple-300">
            Re-planeamento Dinâmico (Replan Explainability: Old Plan → New Plan → Why)
          </h3>
        </div>

        {(!missionState.replans || missionState.replans.length === 0) ? (
          <div className="rounded-lg border border-white/8 bg-black/20 p-4 text-xs text-gray-400">
            O plano original permaneceu estável e não exigiu adaptação estrutural.
          </div>
        ) : (
          (missionState.replans || []).map((rp, idx) => (
            <div key={idx} className="space-y-3 rounded-lg border border-purple-500/20 bg-black/40 p-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white">
                  Trigger de Adaptação: <span className="font-mono text-purple-300">{rp.trigger}</span>
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Plano Anterior:</strong>
                  <p className="mt-1 text-gray-300">{rp.old_plan_summary}</p>
                </div>
                <div className="rounded border border-cyan-500/20 bg-cyan-950/20 p-2.5">
                  <strong className="text-cyan-300">Novo Plano Adaptado:</strong>
                  <p className="mt-1 text-cyan-100">{rp.new_plan_summary}</p>
                </div>
              </div>

              <p className="text-gray-300">
                <strong>Razão da Mudança:</strong> {rp.why_changed}
              </p>
            </div>
          ))
        )}
      </div>

      {/* 11. RECOVERY VISIBILITY */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-950/10 p-5">
        <div className="mb-4 flex items-center gap-2.5">
          <Database className="h-5 w-5 text-blue-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-blue-300">
            Visibilidade de Recuperação de Crash (Worker Failed → Checkpoint Found → State Restored)
          </h3>
        </div>

        {(!missionState.recoveries || missionState.recoveries.length === 0) ? (
          <div className="rounded-lg border border-white/8 bg-black/20 p-4 text-xs text-gray-400">
            Nenhuma interrupção de processo detetada. Execução concluída de forma contínua.
          </div>
        ) : (
          (missionState.recoveries || []).map((rec, idx) => (
            <div key={idx} className="space-y-3 rounded-lg border border-blue-500/20 bg-black/40 p-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-cyan-300">Checkpoint ID: {rec.checkpoint_id}</span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-bold text-emerald-300">
                  {rec.duplicate_work_prevented ? 'ZERO_WORK_DUPLICATION' : 'PARTIAL'}
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Worker Interrompido:</strong>
                  <p className="mt-1 font-mono text-rose-300">{rec.worker_failed_id}</p>
                </div>
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Tarefas Restauradas:</strong>
                  <p className="mt-1 font-mono text-cyan-300">{(rec.recovered_tasks || []).join(', ')}</p>
                </div>
                <div className="rounded border border-white/6 bg-white/[0.02] p-2.5">
                  <strong className="text-gray-400">Duração da Recuperação:</strong>
                  <p className="mt-1 font-mono text-emerald-300">{rec.recovery_duration_seconds}s</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
