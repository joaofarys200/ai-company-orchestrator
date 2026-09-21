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
    <div className="flex items-center gap-2">
      {status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-edit-goal"
          disabled={isSubmittingCommand || status === 'BLOCKED'}
          onClick={onEditGoal}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-gray-200 transition-colors hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
          title="Editar ou refinar intenção/objetivo da missão"
        >
          <Edit3 className="h-3.5 w-3.5 text-gray-400" />
          <span>Alterar intenção</span>
        </button>
      )}

      {status !== 'PAUSED' && status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-pause"
          disabled={isSubmittingCommand || status === 'BLOCKED'}
          onClick={onPause}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-gray-200 transition-colors hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
          title="Suspender trabalho com segurança de checkpoint"
        >
          <Pause className="h-3.5 w-3.5 text-gray-400" />
          <span>Pausar</span>
        </button>
      )}

      {status === 'PAUSED' && (
        <button
          id="mission-cmd-resume"
          disabled={isSubmittingCommand}
          onClick={onResume}
          className="inline-flex items-center gap-1.5 rounded-md border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1.5 text-xs font-medium text-emerald-200 transition-colors hover:bg-emerald-400/20 disabled:opacity-40"
          title="Retomar execução do checkpoint"
        >
          <Play className="h-3.5 w-3.5 text-emerald-300" />
          <span>Retomar</span>
        </button>
      )}

      {status !== 'COMPLETED' && status !== 'CANCELLED' && (
        <button
          id="mission-cmd-cancel"
          disabled={isSubmittingCommand}
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/20 bg-rose-500/10 px-2.5 py-1.5 text-xs font-medium text-rose-300 transition-colors hover:border-rose-500/40 hover:bg-rose-500/20 disabled:opacity-40"
          title="Cancelar missão irreversivelmente"
        >
          <AlertOctagon className="h-3.5 w-3.5 text-rose-400" />
          <span>Cancelar</span>
        </button>
      )}
    </div>
  );
};
