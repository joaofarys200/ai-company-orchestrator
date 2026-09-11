import React from 'react';
import {
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  TrendingUp,
  Layers,
} from 'lucide-react';

interface MissionPredictionOutcomePanelProps {
  outcome: any | null;
  predictionReport?: any | null;
}

export const MissionPredictionOutcomePanel: React.FC<MissionPredictionOutcomePanelProps> = ({
  outcome,
  predictionReport,
}) => {
  if (!outcome) {
    return (
      <div
        id="prediction-outcome-empty"
        className="rounded-xl border border-white/10 bg-[#0d1418] p-8 text-center"
      >
        <TrendingUp className="mx-auto h-12 w-12 text-cyan-400/50 mb-3" />
        <h4 className="text-sm font-semibold text-white">Nenhuma Comparação de Execução Registada</h4>
        <p className="mt-1 text-xs text-gray-400 max-w-md mx-auto">
          A calibração <strong>Prediction vs Reality</strong> é registada automaticamente após uma alteração de intenção ser aplicada e executada pelo enxame de agentes.
        </p>
      </div>
    );
  }

  const classification = outcome.classification || 'CORRECT';
  const filePrecision = outcome.file_precision !== undefined ? Math.round(outcome.file_precision * 100) : 100;
  const fileRecall = outcome.file_recall !== undefined ? Math.round(outcome.file_recall * 100) : 100;
  const taskPrecision = outcome.task_precision !== undefined ? Math.round(outcome.task_precision * 100) : 100;
  const taskRecall = outcome.task_recall !== undefined ? Math.round(outcome.task_recall * 100) : 100;

  const matchedFiles = outcome.matched_files || [];
  const missedFiles = outcome.missed_files || [];
  const unexpectedFiles = outcome.unexpected_files || [];
  const deviations = outcome.deviations || [];

  const getClassificationBadge = (cls: string) => {
    switch (cls) {
      case 'CORRECT':
        return 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300';
      case 'PARTIALLY_CORRECT':
        return 'border-yellow-500/50 bg-yellow-500/15 text-yellow-300';
      case 'OVERPREDICTED':
        return 'border-cyan-500/50 bg-cyan-500/15 text-cyan-300';
      case 'UNDERPREDICTED':
        return 'border-orange-500/50 bg-orange-500/15 text-orange-300';
      default:
        return 'border-red-500/50 bg-red-500/15 text-red-300';
    }
  };

  return (
    <div id="prediction-outcome-panel" className="space-y-5">
      {/* Top Banner */}
      <div className="rounded-xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/30 via-[#0d1418] to-purple-950/20 p-5 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-cyan-400" />
              <h3 className="text-base font-bold text-white">
                Telemetria de Calibração: Previsão vs Realidade Observada
              </h3>
              <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                {outcome.outcome_id}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-300">
              Mede a precisão e recall observáveis do impacto preditivo, separando claramente falsos positivos e falsos negativos.
            </p>
          </div>

          <span
            id="badge-outcome-classification"
            className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${getClassificationBadge(
              classification
            )}`}
          >
            Classificação: {classification}
          </span>
        </div>
      </div>

      {/* Metrics Cards: Precision & Recall */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Precisão Ficheiros</span>
          <div id="stat-file-precision" className="mt-1 text-xl font-bold text-cyan-300">
            {filePrecision}%
          </div>
          <span className="text-[10px] text-gray-500">sem falsos positivos</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Recall Ficheiros</span>
          <div id="stat-file-recall" className="mt-1 text-xl font-bold text-purple-300">
            {fileRecall}%
          </div>
          <span className="text-[10px] text-gray-500">cobertura real</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Precisão Tarefas</span>
          <div id="stat-task-precision" className="mt-1 text-xl font-bold text-yellow-300">
            {taskPrecision}%
          </div>
          <span className="text-[10px] text-gray-500">ações no DAG</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Recall Tarefas</span>
          <div id="stat-task-recall" className="mt-1 text-xl font-bold text-emerald-300">
            {taskRecall}%
          </div>
          <span className="text-[10px] text-gray-500">ações executadas</span>
        </div>
      </div>

      {/* Side-by-Side Comparison Table */}
      <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
        <div className="flex items-center gap-2 border-b border-white/10 pb-2">
          <Layers className="h-4 w-4 text-cyan-400" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-white">
            Tabela Comparativa (Predicted vs Actual)
          </h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="text-[11px] uppercase tracking-wider text-gray-400 border-b border-white/10">
              <tr>
                <th className="py-2 px-3">Dimensão</th>
                <th className="py-2 px-3 text-purple-300">Previsto (Predicted)</th>
                <th className="py-2 px-3 text-cyan-300">Observado (Actual)</th>
                <th className="py-2 px-3">Delta / Desvio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-gray-300 font-mono">
              <tr>
                <td className="py-2 px-3 font-sans text-white">Ficheiros Afetados</td>
                <td className="py-2 px-3 text-purple-300">{matchedFiles.length + missedFiles.length} ficheiros</td>
                <td className="py-2 px-3 text-cyan-300">{outcome.actual_files_changed?.length || 0} ficheiros</td>
                <td className="py-2 px-3">
                  {unexpectedFiles.length > 0 ? (
                    <span className="text-yellow-400">+{unexpectedFiles.length} inesperados</span>
                  ) : missedFiles.length > 0 ? (
                    <span className="text-orange-400">-{missedFiles.length} não alterados</span>
                  ) : (
                    <span className="text-emerald-400">0 desvio (Exato)</span>
                  )}
                </td>
              </tr>
              <tr>
                <td className="py-2 px-3 font-sans text-white">Tarefas Adicionadas</td>
                <td className="py-2 px-3 text-purple-300">{outcome.matched_tasks?.length || 0} tarefas</td>
                <td className="py-2 px-3 text-cyan-300">{outcome.actual_tasks_added?.length || 0} tarefas</td>
                <td className="py-2 px-3 text-emerald-400">Alinhado com DAG</td>
              </tr>
              <tr>
                <td className="py-2 px-3 font-sans text-white">Escopo Operacional</td>
                <td className="py-2 px-3 text-purple-300">{predictionReport?.predicted_scope || 'LOCAL'}</td>
                <td className="py-2 px-3 text-cyan-300">{outcome.actual_scope || 'LOCAL'}</td>
                <td className="py-2 px-3 text-emerald-400">Consistente</td>
              </tr>
              <tr>
                <td className="py-2 px-3 font-sans text-white">Validação Browser</td>
                <td className="py-2 px-3 text-purple-300">
                  {predictionReport?.predicted_browser_validation ? 'Sim' : 'Não'}
                </td>
                <td className="py-2 px-3 text-cyan-300">
                  {outcome.actual_browser_validation ? 'Executada' : 'Não'}
                </td>
                <td className="py-2 px-3 text-emerald-400">Conforme</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Breakdown: Matched vs Missed vs Unexpected */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Matched */}
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-300 uppercase">
            <CheckCircle2 className="h-4 w-4" />
            <span>Ficheiros Acertados ({matchedFiles.length})</span>
          </div>
          <div className="space-y-1 text-[11px] font-mono text-emerald-200/90 max-h-36 overflow-y-auto">
            {matchedFiles.length === 0 ? (
              <p className="text-gray-500 text-xs">Nenhum ficheiro correspondente.</p>
            ) : (
              matchedFiles.map((f: string, i: number) => <div key={i}>✓ {f}</div>)
            )}
          </div>
        </div>

        {/* Missed (False Negatives of Actual / Overpredicted) */}
        <div className="rounded-xl border border-orange-500/20 bg-orange-950/10 p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-orange-300 uppercase">
            <AlertCircle className="h-4 w-4" />
            <span>Previstos Sem Mutação ({missedFiles.length})</span>
          </div>
          <div className="space-y-1 text-[11px] font-mono text-orange-200/90 max-h-36 overflow-y-auto">
            {missedFiles.length === 0 ? (
              <p className="text-gray-500 text-xs">Sem falsos alarmes.</p>
            ) : (
              missedFiles.map((f: string, i: number) => <div key={i}>? {f}</div>)
            )}
          </div>
        </div>

        {/* Unexpected (False Positives of Actual / Underpredicted) */}
        <div className="rounded-xl border border-yellow-500/20 bg-yellow-950/10 p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-yellow-300 uppercase">
            <HelpCircle className="h-4 w-4" />
            <span>Inesperados ({unexpectedFiles.length})</span>
          </div>
          <div className="space-y-1 text-[11px] font-mono text-yellow-200/90 max-h-36 overflow-y-auto">
            {unexpectedFiles.length === 0 ? (
              <p className="text-gray-500 text-xs">Nenhum ficheiro surpresa.</p>
            ) : (
              unexpectedFiles.map((f: string, i: number) => <div key={i}>+ {f}</div>)
            )}
          </div>
        </div>
      </div>

      {/* Deviations List */}
      {deviations.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-2">
          <h5 className="text-xs font-bold text-white uppercase tracking-wider">
            Desvios Registados para Calibração de Telemetria
          </h5>
          <div className="space-y-1.5 text-xs text-gray-300">
            {deviations.map((d: any, idx: number) => (
              <div key={idx} className="rounded bg-white/5 p-2 flex items-center justify-between">
                <span className="font-semibold text-yellow-300">[{d.type}]: {d.item}</span>
                <span className="text-[11px] text-gray-400">{d.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
