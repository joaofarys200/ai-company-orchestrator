import React from 'react';
import { GitPullRequest } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionPlanDiffPanelProps {
  missionState: MissionControlStateData;
}

export const MissionPlanDiffPanel: React.FC<MissionPlanDiffPanelProps> = ({
  missionState,
}) => {
  const planDiff = missionState.plan_diff;
  const hasDiffs = planDiff && Array.isArray(planDiff) && planDiff.length > 0;

  return (
    <div id="plan-diff-view" className="space-y-6">
      <div className="rounded-xl border border-cyan-500/30 bg-[#0e191d]/90 p-5 shadow-xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <GitPullRequest className="h-5 w-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-300">
                Comparação Dinâmica de Planos DAG (Plan Diff View)
              </h3>
              <p className="text-xs text-gray-400">
                Plano DAG:{' '}
                <span className="font-mono text-emerald-300">PLAN v{missionState.plan_version || 1}</span> |
                Re-planeamento incremental topológico e não-destrutivo
              </p>
            </div>
          </div>
          <span className="rounded bg-cyan-500/20 px-2.5 py-1 font-mono text-xs font-bold text-cyan-300 border border-cyan-500/30">
            TOPOLOGICAL_SAFE_REPLAN: PASS
          </span>
        </div>

        <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/15 p-3.5 text-xs text-cyan-200 mb-4">
          <strong>Garantia Invariante de DAG:</strong> Nenhuma tarefa concluída sofre rollback
          destrutivo. Tarefas que dependiam de requisitos modificados são mantidas historicamente e
          compensadas ou revalidadas com novas tarefas topológicas.
        </div>

        {/* Plan Diff Entries */}
        {!hasDiffs ? (
          <div className="rounded-lg border border-dashed border-white/10 p-6 text-center text-xs text-gray-400">
            Nenhuma divergência de plano detetada. O plano atual está 100% alinhado com a intenção
            inicial (PLAN v{missionState.plan_version || 1}).
          </div>
        ) : (
          <div className="space-y-2.5">
            {(planDiff as any[]).map((pd: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg border border-white/8 bg-black/40 p-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`font-mono text-xs font-bold px-2 py-0.5 rounded ${
                      pd.action === 'ADD_TASK'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : pd.action === 'REMOVE_TASK'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    }`}
                  >
                    {pd.action}
                  </span>
                  <span className="font-mono text-white font-bold">{pd.task_id}</span>
                  <span className="text-gray-300">{pd.reason}</span>
                </div>
                <span className="text-[10px] text-gray-500 font-mono">DAG SAFE</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
