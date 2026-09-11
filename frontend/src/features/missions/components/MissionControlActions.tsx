import React from 'react';
import { Edit3, Pause, Play, AlertOctagon } from 'lucide-react';
import type { MissionControlStatus } from '../../../protocol/websocket';

interface MissionControlActionsProps {
  status: MissionControlStatus;
  isSubmittingCommand: boolean;
  onEditGoal: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
}

export const MissionControlActions: React.FC<MissionControlActionsProps> = ({
  status,
  isSubmittingCommand,
  onEditGoal,
  onPause,
  onResume,
  onCancel,
}) => {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-black/40 p-1.5">
      {status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-edit-goal"
          disabled={isSubmittingCommand || status === 'BLOCKED'}
          onClick={onEditGoal}
          className="inline-flex items-center gap-1.5 rounded-md border border-purple-500/40 bg-purple-500/20 px-3 py-1.5 text-xs font-bold text-purple-200 transition-all hover:bg-purple-500/30 disabled:opacity-50 shadow-sm"
          title="Editar ou refinar intenção/objetivo em runtime (Fase 37)"
        >
          <Edit3 className="h-3.5 w-3.5" />
          <span>Alterar Intenção</span>
        </button>
      )}

      {status !== 'PAUSED' && status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-pause"
          disabled={isSubmittingCommand || status === 'BLOCKED'}
          onClick={onPause}
          className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/20 px-3 py-1.5 text-xs font-bold text-amber-200 transition-all hover:bg-amber-500/30 disabled:opacity-50 shadow-sm"
          title="Suspender trabalho com segurança de checkpoint"
        >
          <Pause className="h-3.5 w-3.5" />
          <span>Pausar</span>
        </button>
      )}

      {status === 'PAUSED' && (
        <button
          id="mission-cmd-resume"
          disabled={isSubmittingCommand}
          onClick={onResume}
          className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/20 px-3 py-1.5 text-xs font-bold text-emerald-200 transition-all hover:bg-emerald-500/30 disabled:opacity-50 shadow-sm"
          title="Retomar execução do checkpoint"
        >
          <Play className="h-3.5 w-3.5" />
          <span>Retomar</span>
        </button>
      )}

      {status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-cancel"
          disabled={isSubmittingCommand}
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/20 px-3 py-1.5 text-xs font-bold text-rose-200 transition-all hover:bg-rose-500/30 disabled:opacity-50 shadow-sm"
          title="Cancelar missão irreversivelmente com auditoria"
        >
          <AlertOctagon className="h-3.5 w-3.5" />
          <span>Cancelar</span>
        </button>
      )}
    </div>
  );
};
