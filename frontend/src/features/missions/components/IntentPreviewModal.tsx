import React from 'react';
import { Edit3, Sparkles, X, Check } from 'lucide-react';

interface IntentPreviewModalProps {
  isOpen: boolean;
  intentInputText: string;
  isAnalyzingIntent: boolean;
  isApplyingIntent: boolean;
  currentIntentPreview: any | null;
  onChangeInputText: (text: string) => void;
  onAnalyzeIntent: (presetText?: string) => void;
  onApplyIntent: () => void;
  onClose: () => void;
}

export const IntentPreviewModal: React.FC<IntentPreviewModalProps> = ({
  isOpen,
  intentInputText,
  isAnalyzingIntent,
  isApplyingIntent,
  currentIntentPreview,
  onChangeInputText,
  onAnalyzeIntent,
  onApplyIntent,
  onClose,
}) => {
  if (!isOpen) return null;

  const presets = [
    'Adiciona autenticação',
    'Não alteres a API existente',
    'Remove exportação CSV',
    'Faz com React em vez de vanilla JS',
    'Dá prioridade ao backend',
  ];

  const getImpactLevel = (impact: any): string => {
    if (typeof impact === 'object' && impact !== null) {
      return impact.level || 'LOCAL';
    }
    return String(impact || 'LOCAL');
  };

  const impactLevel = currentIntentPreview ? getImpactLevel(currentIntentPreview.impact) : 'LOCAL';

  return (
    <div
      id="intent-preview-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto"
    >
      <div className="w-full max-w-2xl rounded-xl border border-purple-500/40 bg-[#0c1518] p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2.5 text-purple-300">
            <Edit3 className="h-5 w-5" />
            <h3 className="text-base font-bold text-white">Editar Intenção / Objetivo em Runtime (Fase 37)</h3>
          </div>
          <button
            id="btn-close-intent-modal"
            onClick={onClose}
            className="text-gray-400 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="text-xs text-gray-300">
          Altere os objetivos funcionais, restrições ou abordagem da missão durante a execução. O pedido é avaliado como um <strong>Delta de Intenção</strong> formal, validado pelo Mission Gate e re-planeado com segurança de DAG.
        </p>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5">
            Instrução Semântica do Utilizador:
          </label>
          <textarea
            id="input-intent-text"
            rows={3}
            value={intentInputText}
            onChange={(e) => onChangeInputText(e.target.value)}
            placeholder="Ex: Adiciona autenticação; Não alteres a API existente; Remove exportação CSV; Faz com React em vez de vanilla JS..."
            className="w-full rounded-md border border-white/15 bg-black/60 px-3 py-2 text-xs text-white placeholder-gray-500 focus:border-purple-400 focus:outline-none"
          />
          {/* Presets */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="text-[10px] text-gray-500 self-center">Exemplos:</span>
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => {
                  onChangeInputText(preset);
                  onAnalyzeIntent(preset);
                }}
                className="rounded bg-white/5 px-2 py-0.5 text-[10px] text-gray-300 hover:bg-purple-500/20 hover:text-purple-200 border border-white/5"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        <div className="flex justify-end">
          <button
            id="btn-analyze-intent"
            disabled={isAnalyzingIntent}
            onClick={() => onAnalyzeIntent()}
            className="inline-flex items-center gap-1.5 rounded-md border border-purple-500/40 bg-purple-600/30 px-3 py-1.5 text-xs font-bold text-purple-100 hover:bg-purple-600/50 disabled:opacity-40"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>{isAnalyzingIntent ? 'A Analisar...' : 'Analisar Impacto da Intenção'}</span>
          </button>
        </div>

        {/* PREVIEW CONTENT */}
        {currentIntentPreview && (
          <div id="intent-preview-content" className="rounded-lg border border-white/10 bg-black/50 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="font-mono text-xs font-bold text-cyan-300">
                DELTA DE INTENÇÃO DETETADO: {currentIntentPreview.operation}
              </span>
              <span
                id="preview-impact-badge"
                className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                  impactLevel === 'STRUCTURAL'
                    ? 'bg-purple-500/30 text-purple-200 border border-purple-500/40'
                    : impactLevel === 'MISSION_WIDE'
                    ? 'bg-rose-500/30 text-rose-200 border border-rose-500/40'
                    : impactLevel === 'PARTIAL'
                    ? 'bg-amber-500/30 text-amber-200 border border-amber-500/40'
                    : 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/40'
                }`}
              >
                IMPACTO: {impactLevel}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
              <div className="rounded border border-white/8 bg-white/[0.02] p-2">
                <span className="text-[10px] text-gray-400">Escopo Previsto:</span>
                <p id="preview-predicted-scope" className="font-mono font-bold text-white mt-0.5">
                  {currentIntentPreview.scope || impactLevel}
                </p>
              </div>
              <div className="rounded border border-white/8 bg-white/[0.02] p-2">
                <span className="text-[10px] text-gray-400">Risco Determinístico:</span>
                <p id="preview-predicted-risk" className="font-mono font-bold text-yellow-300 mt-0.5">
                  {currentIntentPreview.risk || (impactLevel === 'STRUCTURAL' ? 'MEDIUM' : 'LOW')}
                </p>
              </div>
              <div className="rounded border border-white/8 bg-white/[0.02] p-2">
                <span className="text-[10px] text-gray-400">Tarefas Previstas:</span>
                <p id="preview-predicted-tasks" className="font-mono font-bold text-cyan-300 mt-0.5">
                  +{currentIntentPreview.tasks_affected?.length || 2} previstas
                </p>
              </div>
              <div className="rounded border border-white/8 bg-white/[0.02] p-2">
                <span className="text-[10px] text-gray-400">Ficheiros Afetados:</span>
                <p id="preview-predicted-files" className="font-mono font-bold text-purple-300 mt-0.5">
                  {currentIntentPreview.files_count || (impactLevel === 'STRUCTURAL' ? '3 direct, 2 indirect' : '1 direct')}
                </p>
              </div>
            </div>

            <div className="rounded border border-purple-500/20 bg-purple-950/20 p-2 text-[11px] text-purple-200/90 flex items-center justify-between">
              <span>Zero False Success: {currentIntentPreview.evidence_affected?.length || 1} evidência requer revalidação</span>
              <span className="font-semibold text-cyan-300">Validação Browser: Necessária</span>
            </div>

            {currentIntentPreview.requires_pause && (
              <div className="rounded border border-amber-500/30 bg-amber-950/20 p-2 text-xs text-amber-200">
                <strong>Pausa Preventiva Ativa:</strong> Como o impacto é {impactLevel}, a missão será pausada durante o replan para garantir integridade do scheduler.
              </div>
            )}

            {currentIntentPreview.conflicts && currentIntentPreview.conflicts.length > 0 && (
              <div id="preview-conflict-alert" className="rounded border border-rose-500/40 bg-rose-950/30 p-2.5 text-xs text-rose-200 space-y-1">
                <strong className="block font-bold">Conflito Detetado:</strong>
                {currentIntentPreview.conflicts.map((c: any, i: number) => (
                  <p key={i}>• {c.conflict_type || 'CONFLITO'}: {c.reason || c.description || JSON.stringify(c)}</p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-3 border-t border-white/10 pt-3">
          <button
            id="btn-cancel-intent"
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/10"
          >
            Cancelar
          </button>
          <button
            id="btn-apply-intent"
            disabled={isApplyingIntent || !currentIntentPreview}
            onClick={onApplyIntent}
            className="inline-flex items-center gap-1.5 rounded-md border border-purple-500/50 bg-purple-600 px-4 py-1.5 text-xs font-bold text-white shadow-lg hover:bg-purple-500 disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" />
            <span>
              {currentIntentPreview?.approval_status === 'CONFIRM_REQUIRED'
                ? 'Confirmar & Aplicar Alteração'
                : 'Aplicar Delta de Intenção'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
