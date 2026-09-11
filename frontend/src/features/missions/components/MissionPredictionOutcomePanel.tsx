import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  TrendingUp,
  Layers,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface MissionPredictionOutcomePanelProps {
  outcome: any | null;
  predictionReport?: any | null;
}

export const MissionPredictionOutcomePanel: React.FC<MissionPredictionOutcomePanelProps> = ({
  outcome,
  predictionReport,
}) => {
  const [selectedMatch, setSelectedMatch] = useState<any | null>(null);

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
  const matchedTasks = outcome.matched_tasks || [];
  const missedTasks = outcome.missed_tasks || [];
  const unexpectedTasks = outcome.unexpected_tasks || [];
  const causalMatches = outcome.task_causal_matches || [];
  const rootCauses = outcome.task_mismatches_by_root_cause || {};
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

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'MATCHED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'MISSED':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      case 'OVERPREDICTED':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default:
        return 'bg-gray-700/20 text-gray-300 border-gray-600/30';
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
                Telemetria de Calibração: Previsão vs Realidade Observada (Fase 39.2)
              </h3>
              <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                {outcome.outcome_id}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-300">
              Precisão & Recall empíricos com <strong>reconciliação causal de tarefas</strong> e classificação de causas-raiz de desvios.
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
          <span className="text-[10px] text-gray-500">ações alinhadas</span>
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
                <th className="py-2 px-3">Delta / Alinhamento</th>
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
                <td className="py-2 px-3 font-sans text-white">Tarefas (DAG Actions)</td>
                <td className="py-2 px-3 text-purple-300">{matchedTasks.length + missedTasks.length} previstas</td>
                <td className="py-2 px-3 text-cyan-300">{matchedTasks.length + unexpectedTasks.length} observadas</td>
                <td className="py-2 px-3 text-emerald-400">
                  {unexpectedTasks.length > 0 ? (
                    <span className="text-yellow-400">+{unexpectedTasks.length} não previstas</span>
                  ) : missedTasks.length > 0 ? (
                    <span className="text-orange-400">-{missedTasks.length} não executadas</span>
                  ) : (
                    <span className="text-emerald-400">100% Reconciliado</span>
                  )}
                </td>
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

      {/* Causal Match & Root Cause Breakdown */}
      <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Correspondência Causal de Tarefas (Causal Match & Root Cause)
            </h4>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {causalMatches.length} mapeamentos avaliados
          </span>
        </div>

        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {causalMatches.length === 0 ? (
            <p className="text-xs text-gray-500">Nenhum registo de correspondência causal.</p>
          ) : (
            causalMatches.map((cm: any, idx: number) => {
              const isSelected = selectedMatch === idx;
              return (
                <div
                  key={idx}
                  onClick={() => setSelectedMatch(isSelected ? null : idx)}
                  className={`rounded-lg border p-2.5 text-xs transition-all cursor-pointer space-y-1.5 ${
                    isSelected
                      ? 'border-cyan-500/60 bg-cyan-950/20'
                      : 'border-white/5 bg-white/[0.02] hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {isSelected ? <ChevronDown className="h-3.5 w-3.5 text-cyan-400" /> : <ChevronRight className="h-3.5 w-3.5 text-gray-400" />}
                      <span className="font-semibold text-white">
                        {cm.predicted_task_id ? `Prevista: ${cm.predicted_task_id}` : `Observada: ${cm.actual_task_id}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={`rounded border px-1.5 py-0.2 text-[9px] font-mono uppercase ${getStatusBadge(cm.match_status)}`}>
                        {cm.match_status}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400">
                    <span>Requisito: <strong className="text-gray-300">{cm.source_requirement || 'N/A'}</strong></span>
                    <span>Categoria: <strong className="text-cyan-300">{cm.category || 'Coding'}</strong></span>
                  </div>

                  {cm.root_cause && (
                    <div className="text-[10px] text-orange-300 bg-orange-950/30 border border-orange-500/20 rounded px-2 py-0.5 font-mono">
                      Causa-Raiz: {cm.root_cause}
                    </div>
                  )}

                  {isSelected && cm.causal_trace && (
                    <div className="mt-2 rounded bg-black/40 border border-white/10 p-2 text-[10px] space-y-1 font-mono text-gray-300">
                      <div className="text-cyan-400 uppercase font-bold">Rastreabilidade Causal:</div>
                      {cm.causal_trace.requirement && <div>→ Requisito: {cm.causal_trace.requirement}</div>}
                      {cm.causal_trace.rationale && <div>→ Rationale: {cm.causal_trace.rationale}</div>}
                      {cm.causal_trace.validation_policy && <div>→ Política: {cm.causal_trace.validation_policy}</div>}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Root Causes Summary Table if any mismatches */}
      {Object.keys(rootCauses).length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-2">
          <h5 className="text-xs font-bold text-white uppercase tracking-wider">
            Distribuição de Causas-Raiz de Desvios (Taxonomia Formal)
          </h5>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {Object.entries(rootCauses).map(([cause, count], i) => (
              <div key={i} className="rounded border border-white/5 bg-white/[0.02] p-2 flex items-center justify-between">
                <span className="font-mono text-cyan-300">{cause}</span>
                <span className="rounded bg-white/10 px-2 py-0.5 font-bold text-white">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Breakdown: Matched vs Missed vs Unexpected Files */}
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

        {/* Missed */}
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

        {/* Unexpected */}
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
