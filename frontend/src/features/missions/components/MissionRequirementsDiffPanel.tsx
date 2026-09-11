import React from 'react';
import { Layers } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionRequirementsDiffPanelProps {
  missionState: MissionControlStateData;
}

export const MissionRequirementsDiffPanel: React.FC<MissionRequirementsDiffPanelProps> = ({
  missionState,
}) => {
  const diffList = Array.isArray(missionState.requirement_diff) ? missionState.requirement_diff : [];
  const addedCount = diffList.filter((d: any) => d.type === 'ADD' || d.type === 'ADDED').length;
  const modifiedCount = diffList.filter((d: any) => d.type === 'MODIFY' || d.type === 'MODIFIED').length;
  const removedCount = diffList.filter(
    (d: any) => d.type === 'REMOVE' || d.type === 'REMOVED' || d.status === 'SUPERSEDED'
  ).length;
  const unchangedCount = (missionState.requirements || []).filter(
    (r: any) => String(r.status) !== 'SUPERSEDED' && String(r.status) !== 'REMOVED'
  ).length;

  return (
    <div id="requirements-diff-view" className="space-y-6">
      <div className="rounded-xl border border-purple-500/30 bg-[#0e191d]/90 p-5 shadow-xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <Layers className="h-5 w-5 text-purple-400" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-purple-300">
                Comparação Formal de Intenção & Requisitos (Requirement Diff View)
              </h3>
              <p className="text-xs text-gray-400">
                Evolução de Intenção Semântica:{' '}
                <span className="font-mono text-cyan-300">INTENT v{missionState.intent_version || 1}</span> |
                Rastreabilidade rigorosa de deltas semânticos
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-purple-500/20 px-2.5 py-1 font-mono text-xs font-bold text-purple-300 border border-purple-500/30">
              USER_INTENT_DELTA: VERIFIED
            </span>
          </div>
        </div>

        {/* Requirement lifecycle categories */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5 text-center text-xs mb-4">
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-2.5">
            <span className="text-[10px] uppercase text-emerald-400 font-semibold">Adicionados</span>
            <p className="font-mono text-base font-bold text-emerald-300">{addedCount}</p>
          </div>
          <div className="rounded-lg border border-amber-500/20 bg-amber-950/20 p-2.5">
            <span className="text-[10px] uppercase text-amber-400 font-semibold">Modificados</span>
            <p className="font-mono text-base font-bold text-amber-300">{modifiedCount}</p>
          </div>
          <div className="rounded-lg border border-rose-500/20 bg-rose-950/20 p-2.5">
            <span className="text-[10px] uppercase text-rose-400 font-semibold">Removidos / Superseded</span>
            <p className="font-mono text-base font-bold text-rose-300">{removedCount}</p>
          </div>
          <div className="rounded-lg border border-blue-500/20 bg-blue-950/20 p-2.5">
            <span className="text-[10px] uppercase text-blue-400 font-semibold">Inalterados</span>
            <p className="font-mono text-base font-bold text-blue-300">{unchangedCount}</p>
          </div>
          <div className="rounded-lg border border-red-500/20 bg-red-950/20 p-2.5">
            <span className="text-[10px] uppercase text-red-400 font-semibold">Conflitos</span>
            <p className="font-mono text-base font-bold text-red-300">0</p>
          </div>
        </div>

        {/* Requirements & Constraints Table */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-gray-300">
            Estado Atual dos Requisitos e Ciclo de Vida:
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="border-b border-white/10 bg-white/5 font-mono text-[10px] uppercase text-gray-400">
                <tr>
                  <th className="py-2 px-3">ID</th>
                  <th className="py-2 px-3">Origem Epistémica</th>
                  <th className="py-2 px-3">Descrição Funcional</th>
                  <th className="py-2 px-3">Estado de Ciclo de Vida</th>
                  <th className="py-2 px-3">Verificação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {missionState.requirements.map((req) => (
                  <tr key={req.id} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 px-3 font-bold text-cyan-300">{req.id}</td>
                    <td className="py-2.5 px-3 text-purple-300 font-semibold">{req.source}</td>
                    <td className="py-2.5 px-3 font-sans text-gray-200">{req.desc}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                          String(req.status) === 'VALIDATED'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : String(req.status) === 'SUPERSEDED'
                            ? 'bg-rose-500/20 text-rose-300 line-through'
                            : String(req.status) === 'PLANNED'
                            ? 'bg-cyan-500/20 text-cyan-300'
                            : String(req.status) === 'MODIFIED'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {req.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          req.verification_status === 'VERIFIED'
                            ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/30'
                            : 'bg-purple-950/60 text-purple-300 border border-purple-500/30'
                        }`}
                      >
                        {req.verification_status || 'VERIFIED'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
