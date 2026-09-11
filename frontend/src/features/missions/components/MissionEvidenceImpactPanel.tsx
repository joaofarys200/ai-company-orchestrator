import React from 'react';
import { ShieldAlert } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionEvidenceImpactPanelProps {
  missionState: MissionControlStateData;
}

export const MissionEvidenceImpactPanel: React.FC<MissionEvidenceImpactPanelProps> = ({
  missionState,
}) => {
  const evidenceImpact = missionState.evidence_impact;
  const hasImpact = evidenceImpact && Array.isArray(evidenceImpact) && evidenceImpact.length > 0;

  return (
    <div id="evidence-impact-view" className="space-y-6">
      <div className="rounded-xl border border-amber-500/30 bg-[#0e191d]/90 p-5 shadow-xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="h-5 w-5 text-amber-400" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-amber-300">
                Rastreio de Impacto em Evidências (Evidence Invalidation Tracker)
              </h3>
              <p className="text-xs text-gray-400">
                Princípio Zero False Success: Evidência histórica nunca é apagada; é marcada como
                SUPERSEDED_BY_INTENT_VERSION e requer revalidação
              </p>
            </div>
          </div>
          <span className="rounded bg-amber-500/20 px-2.5 py-1 font-mono text-xs font-bold text-amber-300 border border-amber-500/30">
            ZERO_FALSE_SUCCESS: ACTIVE
          </span>
        </div>

        {!hasImpact ? (
          <div className="rounded-lg border border-dashed border-white/10 p-6 text-center text-xs text-gray-400">
            Todas as evidências recolhidas permanecem válidas para a versão corrente de intenção
            (INTENT v{missionState.intent_version || 1}). Nenhuma invalidação detetada.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="border-b border-white/10 bg-white/5 font-mono text-[10px] uppercase text-gray-400">
                <tr>
                  <th className="py-2 px-3">Evidência</th>
                  <th className="py-2 px-3">Estado</th>
                  <th className="py-2 px-3">Válida na Versão</th>
                  <th className="py-2 px-3">Substituída na Versão</th>
                  <th className="py-2 px-3">Revalidação Requerida?</th>
                  <th className="py-2 px-3">Motivo de Invalidação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {(evidenceImpact as any[]).map((ei: any, idx: number) => (
                  <tr key={idx} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 px-3 font-bold text-cyan-300">{ei.evidence_id}</td>
                    <td className="py-2.5 px-3">
                      <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-300">
                        {ei.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-cyan-200">v{ei.source_intent_version}</td>
                    <td className="py-2.5 px-3 text-purple-300">v{ei.current_intent_version}</td>
                    <td className="py-2.5 px-3">
                      <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                        {ei.revalidation_required ? 'SIM (OBRIGATÓRIA)' : 'NÃO'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-gray-300">{ei.reason}</td>
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
