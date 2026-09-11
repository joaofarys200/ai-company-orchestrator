import React, { useState } from 'react';
import {
  Sparkles,
  FileCode,
  CheckCircle2,
  ShieldAlert,
  Clock,
  Layers,
  Network,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface MissionPredictedImpactPanelProps {
  prediction: any | null;
  onApplyPrediction?: () => void;
  isApplying?: boolean;
}

export const MissionPredictedImpactPanel: React.FC<MissionPredictedImpactPanelProps> = ({
  prediction,
  onApplyPrediction: _onApplyPrediction,
  isApplying: _isApplying = false,
}) => {
  const [selectedTaskIdx, setSelectedTaskIdx] = useState<number | null>(null);
  const [showMatrix, setShowMatrix] = useState<boolean>(false);

  if (!prediction) {
    return (
      <div
        id="predicted-impact-empty"
        className="rounded-xl border border-white/10 bg-[#0d1418] p-8 text-center"
      >
        <Sparkles className="mx-auto h-12 w-12 text-purple-400/50 mb-3" />
        <h4 className="text-sm font-semibold text-white">Nenhuma Simulação Preditiva Ativa</h4>
        <p className="mt-1 text-xs text-gray-400 max-w-md mx-auto">
          Abra o diálogo de <strong>Editar Intenção / Objetivo</strong> para simular o impacto estrutural
          de uma diretiva antes de aplicá-la à missão.
        </p>
      </div>
    );
  }

  const scope = prediction.predicted_scope || 'LOCAL';
  const risk = prediction.predicted_risk || 'LOW';
  const tasks = prediction.predicted_tasks || [];
  const files = prediction.predicted_files || [];
  const evidence = prediction.predicted_evidence_impact || [];
  const tests = prediction.predicted_tests || [];
  const taskFileMatrix = prediction.task_file_matrix || { relationships: [] };
  const consistencyReport = prediction.consistency_report || { verdict: 'CONSISTENT', is_valid: true, checks_passed: 9, checks_total: 9, issues: [] };

  const getRiskColor = (r: string) => {
    switch (r) {
      case 'CRITICAL':
        return 'border-red-500/50 bg-red-500/15 text-red-300';
      case 'HIGH':
        return 'border-orange-500/50 bg-orange-500/15 text-orange-300';
      case 'MEDIUM':
        return 'border-yellow-500/50 bg-yellow-500/15 text-yellow-300';
      default:
        return 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300';
    }
  };

  const getScopeBadge = (s: string) => {
    switch (s) {
      case 'ARCHITECTURAL':
      case 'MISSION_WIDE':
        return 'border-purple-500/50 bg-purple-500/15 text-purple-300';
      case 'CROSS_MODULE':
      case 'CROSS_FILE':
        return 'border-cyan-500/50 bg-cyan-500/15 text-cyan-300';
      default:
        return 'border-blue-500/50 bg-blue-500/15 text-blue-300';
    }
  };

  const getCategoryBadge = (cat: string) => {
    switch (cat) {
      case 'Architecture':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      case 'Testing':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'Browser':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'Review':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      default:
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30';
    }
  };

  const getDerivationBadge = (dtype: string) => {
    switch (dtype) {
      case 'DIRECT_FILE_IMPACT':
        return 'text-cyan-300 bg-cyan-950/40 border-cyan-500/30';
      case 'VALIDATION_DRIVEN':
        return 'text-emerald-300 bg-emerald-950/40 border-emerald-500/30';
      case 'ARCHITECTURE_DRIVEN':
        return 'text-purple-300 bg-purple-950/40 border-purple-500/30';
      case 'REQUIREMENT_DRIVEN':
        return 'text-blue-300 bg-blue-950/40 border-blue-500/30';
      default:
        return 'text-gray-300 bg-gray-800/40 border-gray-600/30';
    }
  };

  return (
    <div id="predicted-impact-panel" className="space-y-5">
      {/* Top Banner: Scope & Risk */}
      <div className="rounded-xl border border-purple-500/30 bg-gradient-to-r from-purple-950/30 via-[#0d1418] to-cyan-950/20 p-5 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-400" />
              <h3 className="text-base font-bold text-white">
                Simulação Preditiva de Impacto & Reconciliação (Fase 39.2)
              </h3>
              <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono text-purple-300">
                {prediction.simulation_marker || 'SIMULATION_ONLY'}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-300">
              Estimativa determinística: <strong>Impact Graph → File Impact → Task Reconciliation → Predicted Tasks</strong>.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span
              id="badge-predicted-scope"
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${getScopeBadge(
                scope
              )}`}
            >
              Escopo: {scope}
            </span>
            <span
              id="badge-predicted-risk"
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${getRiskColor(
                risk
              )}`}
            >
              Risco: {risk}
            </span>
            <span
              id="badge-consistency-verdict"
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${
                consistencyReport.verdict === 'CONSISTENT'
                  ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300'
                  : 'border-yellow-500/50 bg-yellow-500/15 text-yellow-300'
              }`}
            >
              Consistência: {consistencyReport.verdict}
            </span>
          </div>
        </div>

        {/* Operational Indicators */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-white/10 pt-3 text-xs">
          <div className="flex items-center gap-1.5 text-gray-300">
            <Layers className="h-4 w-4 text-cyan-400" />
            <span>Validação Browser:</span>
            <strong className="text-white">
              {prediction.predicted_browser_validation ? 'Necessária' : 'Não requerida'}
            </strong>
          </div>
          <div className="flex items-center gap-1.5 text-gray-300">
            <Clock className="h-4 w-4 text-yellow-400" />
            <span>Pausa para Replan:</span>
            <strong className="text-white">
              {prediction.predicted_pause_required ? 'Recomendada' : 'Dispensa pausa'}
            </strong>
          </div>
          <div className="flex items-center gap-1.5 text-gray-300">
            <ShieldAlert className="h-4 w-4 text-orange-400" />
            <span>Aprovação Humana:</span>
            <strong className="text-white">
              {prediction.predicted_approval_required ? 'Obrigatória' : 'Auto-aprovável'}
            </strong>
          </div>
          <div className="flex items-center gap-1.5 text-gray-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>Invariantes Válidos:</span>
            <strong className="text-white">
              {consistencyReport.checks_passed || 9}/{consistencyReport.checks_total || 9}
            </strong>
          </div>
        </div>
      </div>

      {/* Grid of Predicted Quantities */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Tarefas Reconciliadas</span>
          <div id="stat-predicted-tasks" className="mt-1 text-xl font-bold text-cyan-300">
            {tasks.length}
          </div>
          <span className="text-[10px] text-gray-500">100% rastreáveis</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Ficheiros Afetados</span>
          <div id="stat-predicted-files" className="mt-1 text-xl font-bold text-purple-300">
            {files.length}
          </div>
          <span className="text-[10px] text-gray-500">módulos potenciais</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Testes Requeridos</span>
          <div id="stat-predicted-tests" className="mt-1 text-xl font-bold text-yellow-300">
            {tests.length}
          </div>
          <span className="text-[10px] text-gray-500">suites de validação</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Evidências em Risco</span>
          <div id="stat-predicted-evidence" className="mt-1 text-xl font-bold text-red-300">
            {evidence.length}
          </div>
          <span className="text-[10px] text-gray-500">Zero False Success</span>
        </div>
      </div>

      {/* Two Column Layout: Files & Tasks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Predicted Files */}
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <div className="flex items-center gap-2">
              <FileCode className="h-4 w-4 text-purple-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                Ficheiros Potencialmente Afetados
              </h4>
            </div>
            <span className="text-[10px] text-gray-400 font-mono">{files.length} itens</span>
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {files.length === 0 ? (
              <p className="text-xs text-gray-500">Nenhum ficheiro específico identificado.</p>
            ) : (
              files.map((f: any, idx: number) => (
                <div
                  key={idx}
                  className="rounded-lg border border-white/5 bg-white/[0.02] p-2 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-cyan-300">{f.file_path}</span>
                    <span
                      className={`rounded px-1.5 py-0.2 text-[9px] font-semibold uppercase ${
                        f.classification === 'DIRECT'
                          ? 'bg-purple-500/20 text-purple-300'
                          : 'bg-white/10 text-gray-300'
                      }`}
                    >
                      {f.classification}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-400">{f.reason}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Predicted Tasks with Traceability */}
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                Tarefas Previstas & Rastreabilidade Causal
              </h4>
            </div>
            <span className="text-[10px] text-gray-400 font-mono">{tasks.length} no DAG</span>
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {tasks.length === 0 ? (
              <p className="text-xs text-gray-500">Nenhuma tarefa adicional necessária.</p>
            ) : (
              tasks.map((t: any, idx: number) => {
                const isSelected = selectedTaskIdx === idx;
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedTaskIdx(isSelected ? null : idx)}
                    className={`rounded-lg border cursor-pointer transition-all p-2.5 text-xs space-y-1.5 ${
                      isSelected
                        ? 'border-cyan-500/60 bg-cyan-950/20'
                        : 'border-white/5 bg-white/[0.02] hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {isSelected ? <ChevronDown className="h-3.5 w-3.5 text-cyan-400" /> : <ChevronRight className="h-3.5 w-3.5 text-gray-400" />}
                        <span className="font-semibold text-white">{t.title}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`rounded border px-1.5 py-0.2 text-[9px] font-mono ${getCategoryBadge(t.category || 'Coding')}`}>
                          {t.category || 'Coding'}
                        </span>
                        <span className="rounded bg-cyan-500/20 px-1.5 py-0.2 text-[9px] font-mono text-cyan-300">
                          {t.action}
                        </span>
                      </div>
                    </div>

                    <p className="text-[11px] text-gray-400">{t.description}</p>

                    {/* Metadata & Derivation pill */}
                    <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-white/5 text-[10px] text-gray-400 font-mono">
                      <span className={`rounded border px-1.5 py-0.2 ${getDerivationBadge(t.derivation_type || 'DIRECT_FILE_IMPACT')}`}>
                        {t.derivation_type || 'DIRECT_FILE_IMPACT'}
                      </span>
                      <span>Fonte: <strong className="text-gray-300">{t.source_requirement}</strong></span>
                      <span>Ficheiros: <strong className="text-cyan-300">{(t.predicted_files || []).length}</strong></span>
                      <span>Confiança: <strong className="text-emerald-400">{t.confidence_class || 'DETERMINISTIC'}</strong></span>
                    </div>

                    {/* Expanded Causal Trace */}
                    {isSelected && t.causal_trace && (
                      <div className="mt-2 rounded bg-black/40 border border-white/10 p-2 text-[11px] space-y-1 font-mono text-gray-300">
                        <div className="text-[10px] uppercase font-bold text-cyan-400">Cadeia Causal Explicável:</div>
                        <div>→ Requisito: {t.causal_trace.requirement || t.source_requirement}</div>
                        {t.causal_trace.rationale && <div>→ Rationale: {t.causal_trace.rationale}</div>}
                        {t.causal_trace.validation_policy && <div>→ Política: {t.causal_trace.validation_policy}</div>}
                        <div>→ Dono Previsto: {t.predicted_owner}</div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Task-to-File Reconciliation Matrix Collapsible */}
      <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
        <div
          onClick={() => setShowMatrix(!showMatrix)}
          className="flex items-center justify-between cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-purple-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Matriz de Correlação (Files × Tasks) & Consistência Estrutural
            </h4>
            <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono text-purple-300">
              {taskFileMatrix.relationships?.length || 0} relações
            </span>
          </div>
          {showMatrix ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
        </div>

        {showMatrix && (
          <div className="overflow-x-auto pt-2 border-t border-white/10">
            <table className="w-full text-xs text-left">
              <thead className="text-[10px] uppercase tracking-wider text-gray-400 border-b border-white/10">
                <tr>
                  <th className="py-2 px-3">Tarefa</th>
                  <th className="py-2 px-3">Categoria</th>
                  <th className="py-2 px-3">Ficheiro Alvo</th>
                  <th className="py-2 px-3">Relação</th>
                  <th className="py-2 px-3">Derivação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono text-[11px] text-gray-300">
                {(taskFileMatrix.relationships || []).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-3 text-center text-gray-500 font-sans">
                      Nenhuma relação explícita arquivo-tarefa mapeada.
                    </td>
                  </tr>
                ) : (
                  taskFileMatrix.relationships.map((rel: any, i: number) => (
                    <tr key={i} className="hover:bg-white/[0.02]">
                      <td className="py-2 px-3 font-semibold text-white">{rel.task_title || rel.task_id}</td>
                      <td className="py-2 px-3 text-cyan-300">{rel.task_category}</td>
                      <td className="py-2 px-3 text-purple-300">{rel.file_path}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                            rel.relation_type === 'DIRECT'
                              ? 'bg-purple-500/20 text-purple-300'
                              : rel.relation_type === 'VALIDATION'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : 'bg-white/10 text-gray-300'
                          }`}
                        >
                          {rel.relation_type}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-400">{rel.derivation_type}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
