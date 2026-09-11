import React from 'react';
import { ShieldCheck, FileCode, ExternalLink } from 'lucide-react';
import type { MissionControlStateData } from '../../../protocol/websocket';

interface MissionEvidenceLedgerPanelProps {
  missionState: MissionControlStateData;
  onOpenInCode?: (filePath: string, line?: number) => void;
}

export const MissionEvidenceLedgerPanel: React.FC<MissionEvidenceLedgerPanelProps> = ({
  missionState,
  onOpenInCode,
}) => {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
              Livro de Evidências Físicas (Physical Evidence Ledger)
            </h3>
          </div>
          <span className="text-xs text-gray-400">SIMULATED = 0 (100% Mensurado)</span>
        </div>

        <div className="space-y-3">
          {(missionState.evidence || []).map((ev, idx) => (
            <div
              key={idx}
              className="flex flex-col gap-3 rounded-lg border border-white/8 bg-black/40 p-4 transition-all hover:border-emerald-500/30 lg:flex-row lg:items-center lg:justify-between"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-300">
                    {ev.status}
                  </span>
                  <span className="font-mono text-xs font-bold text-white">{ev.type}</span>
                  <span className="text-xs text-gray-400">Fonte: {ev.source}</span>
                </div>
                <div className="mt-2 text-xs text-gray-300">
                  {Object.entries(ev.details || {}).map(([k, v]) => (
                    <span key={k} className="mr-4 inline-block">
                      <strong className="text-gray-400">{k}:</strong>{' '}
                      <span className="text-cyan-200">{String(v)}</span>
                    </span>
                  ))}
                </div>
              </div>
              <span className="font-mono text-[11px] text-gray-500">Timestamp: {ev.timestamp}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Artifacts with Monaco navigation */}
      <div className="rounded-xl border border-[#a1bebf]/15 bg-[#0e191d]/80 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCode className="h-5 w-5 text-cyan-300" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-200">
              Artefactos Gerados & Navegação para Código (Code Intelligence)
            </h3>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {(missionState.artifacts || []).map((art) => (
            <div key={art.path} className="rounded-lg border border-white/8 bg-black/40 p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-cyan-300">{art.name}</span>
                <span className="rounded bg-white/5 px-2 py-0.5 text-[10px] text-gray-400">{art.type}</span>
              </div>
              <p className="mt-2 text-xs text-gray-300">{art.summary}</p>
              <button
                onClick={() => onOpenInCode && onOpenInCode(art.path, art.line_target)}
                className="mt-3 inline-flex items-center gap-1.5 rounded border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                <span>Abrir no Monaco (L{art.line_target || 1})</span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
