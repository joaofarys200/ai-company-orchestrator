import React from 'react';
import { Brain } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionWhyCausalPanelProps {
  missionState: MissionControlStateData;
}

export const MissionWhyCausalPanel: React.FC<MissionWhyCausalPanelProps> = ({
  missionState,
}) => {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-cyan-500/20 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center gap-3">
          <div className="rounded-lg bg-cyan-500/20 p-2 text-cyan-300">
            <Brain className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Porque é que o JARVIS fez isto? (Why Panel)
            </h3>
            <p className="text-xs text-gray-400">
              Transparência causal completa: cada ação está vinculada a um requisito, origem e evidência
              tangível.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {(missionState.why_items || []).map((item, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-white/10 bg-black/40 p-4 transition-all hover:border-cyan-500/40"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-cyan-300">AÇÃO #{idx + 1}</span>
                <span
                  className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                    item.source === 'USER_REQUIREMENT'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : item.source === 'AUTONOMOUS_REPAIR_LOOP'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                  }`}
                >
                  ORIGEM: {item.source}
                </span>
              </div>

              <h4 className="mt-2 text-sm font-bold text-white">{item.action}</h4>

              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 text-xs">
                <div className="rounded-md border border-white/6 bg-white/[0.02] p-3">
                  <span className="font-semibold text-gray-400">Motivo / Causa Primária:</span>
                  <p className="mt-1 text-gray-200">{item.reason}</p>
                </div>
                <div className="rounded-md border border-white/6 bg-white/[0.02] p-3">
                  <span className="font-semibold text-gray-400">Evidência Factual:</span>
                  <p className="mt-1 text-cyan-200">{item.evidence}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
