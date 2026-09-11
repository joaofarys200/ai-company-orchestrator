import React from 'react';
import {
  Sparkles,
  AlertTriangle,
  FileCode,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  Info,
  Clock,
  Layers,
  HelpCircle,
} from 'lucide-react';

interface MissionPredictedImpactPanelProps {
  prediction: any | null;
  onApplyPrediction?: () => void;
  isApplying?: boolean;
}

export const MissionPredictedImpactPanel: React.FC<MissionPredictedImpactPanelProps> = ({
  prediction,
  onApplyPrediction,
  isApplying = false,
}) => {
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
  const assumptions = prediction.assumptions || [];
  const uncertainties = prediction.uncertainties || [];
  const causalChains = prediction.causal_chains || [];

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

  return (
    <div id="predicted-impact-panel" className="space-y-5">
      {/* Top Banner: Scope & Risk */}
      <div className="rounded-xl border border-purple-500/30 bg-gradient-to-r from-purple-950/30 via-[#0d1418] to-cyan-950/20 p-5 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-400" />
              <h3 className="text-base font-bold text-white">
                Simulação Preditiva de Impacto (Fase 39)
              </h3>
              <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-mono text-purple-300">
                {prediction.simulation_marker || 'SIMULATION_ONLY'}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-300">
              Estimativa determinística do impacto gerada <strong>sem mutação</strong> do estado operacional.
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
            <span>Confiança Estrutural:</span>
            <strong className="text-white">
              {Math.round((prediction.confidence || 0.85) * 100)}%
            </strong>
          </div>
        </div>
      </div>

      {/* Grid of Predicted Quantities */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-3 text-center">
          <span className="text-[11px] uppercase tracking-wider text-gray-400">Tarefas Previstas</span>
          <div id="stat-predicted-tasks" className="mt-1 text-xl font-bold text-cyan-300">
            {tasks.length}
          </div>
          <span className="text-[10px] text-gray-500">ações no DAG</span>
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
          <div className="flex items-center gap-2 border-b border-white/10 pb-2">
            <FileCode className="h-4 w-4 text-purple-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Ficheiros Potencialmente Afetados
            </h4>
          </div>
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
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

        {/* Predicted Tasks */}
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-3">
          <div className="flex items-center gap-2 border-b border-white/10 pb-2">
            <Layers className="h-4 w-4 text-cyan-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Plano de Tarefas Hipotético (DAG)
            </h4>
          </div>
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {tasks.length === 0 ? (
              <p className="text-xs text-gray-500">Nenhuma tarefa adicional necessária.</p>
            ) : (
              tasks.map((t: any, idx: number) => (
                <div
                  key={idx}
                  className="rounded-lg border border-white/5 bg-white/[0.02] p-2 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">{t.title}</span>
                    <span className="rounded bg-cyan-500/20 px-1.5 py-0.2 text-[9px] font-mono text-cyan-300">
                      {t.action}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-400">{t.description}</p>
                  <div className="flex items-center justify-between text-[10px] text-gray-500">
                    <span>Agente: {t.predicted_owner}</span>
                    <span>Status: {t.status}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Assumptions & Uncertainties */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-2">
          <div className="flex items-center gap-2 text-yellow-300 text-xs font-bold uppercase tracking-wider">
            <Info className="h-4 w-4" />
            <span>Suposições do Modelo (Assumptions)</span>
          </div>
          <ul className="space-y-1.5 text-xs text-gray-300 list-disc list-inside">
            {assumptions.map((a: any, idx: number) => (
              <li key={idx}>
                <span className="text-gray-400">[{a.category}]:</span> {a.statement}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-2">
          <div className="flex items-center gap-2 text-orange-300 text-xs font-bold uppercase tracking-wider">
            <AlertTriangle className="h-4 w-4" />
            <span>Incertezas & Avisos</span>
          </div>
          {uncertainties.length === 0 ? (
            <p className="text-xs text-gray-400">Nenhuma incerteza estrutural crítica detetada.</p>
          ) : (
            <ul className="space-y-1.5 text-xs text-gray-300 list-disc list-inside">
              {uncertainties.map((u: string, idx: number) => (
                <li key={idx} className="text-orange-200/90">
                  {u}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Causal Explanation Chain */}
      {causalChains.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#0d1418] p-4 space-y-2">
          <div className="flex items-center gap-2 text-purple-300 text-xs font-bold uppercase tracking-wider">
            <HelpCircle className="h-4 w-4" />
            <span>Causalidade Explicativa ("Porque é que estes ficheiros foram previstos?")</span>
          </div>
          <div className="space-y-2 text-xs">
            {causalChains.map((c: any, idx: number) => (
              <div key={idx} className="rounded bg-white/5 p-2.5 flex items-center gap-3">
                <span className="font-semibold text-white">{c.origin}</span>
                <ArrowRight className="h-4 w-4 text-purple-400 shrink-0" />
                <span className="font-mono text-cyan-300 text-[11px]">{c.path}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Apply Action Bar if callback provided */}
      {onApplyPrediction && (
        <div className="flex items-center justify-between rounded-xl border border-purple-500/40 bg-purple-950/20 p-4">
          <div>
            <h5 className="text-xs font-bold text-white">Aplicar Alteração com Base nesta Previsão</h5>
            <p className="text-[11px] text-gray-400">
              A submissão ativará o Mission Gate, pausará com segurança caso necessário e atualizará o plano.
            </p>
          </div>
          <button
            id="btn-apply-predicted-impact"
            onClick={onApplyPrediction}
            disabled={isApplying}
            className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 px-4 py-2 text-xs font-bold text-white shadow-lg hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50"
          >
            <CheckCircle2 className="h-4 w-4" />
            {isApplying ? 'A Aplicar...' : 'Confirmar & Aplicar'}
          </button>
        </div>
      )}
    </div>
  );
};
