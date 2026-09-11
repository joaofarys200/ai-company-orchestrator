import React from 'react';
import { AlertOctagon } from 'lucide-react';

interface CancelConfirmModalProps {
  isOpen: boolean;
  cancelReason: string;
  onChangeReason: (reason: string) => void;
  onConfirm: () => void;
  onDismiss: () => void;
}

export const CancelConfirmModal: React.FC<CancelConfirmModalProps> = ({
  isOpen,
  cancelReason,
  onChangeReason,
  onConfirm,
  onDismiss,
}) => {
  if (!isOpen) return null;

  return (
    <div
      id="cancel-confirm-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-md rounded-xl border border-rose-500/30 bg-[#0f191d] p-6 shadow-2xl">
        <div className="flex items-center gap-3 text-rose-400">
          <AlertOctagon className="h-6 w-6" />
          <h3 className="text-base font-bold text-white">Confirmar Cancelamento de Missão</h3>
        </div>
        <p className="mt-2 text-xs text-gray-300">
          O cancelamento é uma operação cooperativa irrevogável. A execução será interrompida e o histórico e evidências serão preservados no registo de auditoria.
        </p>
        <div className="mt-4">
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">
            Motivo do cancelamento:
          </label>
          <input
            id="input-cancel-reason"
            type="text"
            value={cancelReason}
            onChange={(e) => onChangeReason(e.target.value)}
            placeholder="Ex: Interrupção solicitada pelo utilizador para repriorização"
            className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs text-white placeholder-gray-500 focus:border-rose-400 focus:outline-none"
          />
        </div>
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            id="btn-dismiss-cancel"
            onClick={onDismiss}
            className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/10"
          >
            Voltar
          </button>
          <button
            id="btn-confirm-cancel"
            onClick={onConfirm}
            className="rounded-md border border-rose-500/50 bg-rose-600 px-4 py-1.5 text-xs font-bold text-white shadow-lg hover:bg-rose-500"
          >
            Confirmar Cancelamento
          </button>
        </div>
      </div>
    </div>
  );
};
