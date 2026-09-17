import React, { useState } from 'react';
import {
  Wrench,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Layers,
  Lock,
  Search,
  TrendingUp,
} from 'lucide-react';

export const VerifiedRepairSynthesisPanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'root_cause' | 'candidates' | 'impact' | 'proof' | 'security_rollback'>('root_cause');
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>('rep_cand_express_decl');
  const [isPatchApplied, setIsPatchApplied] = useState<boolean>(true);
  const [hasRegression, setHasRegression] = useState<boolean>(false);
  const [isRolledBack, setIsRolledBack] = useState<boolean>(false);

  const hypothesis = {
    causeId: 'cause_dina_app_scope',
    failureId: 'fail_ref_app_79',
    category: 'RUNTIME_SCOPE_ERROR',
    evidence: "O identificador 'app' foi invocado (app.post('/ddos', ...)) sem instanciação de framework HTTP.",
    sourceLocations: ['app.js:79', 'app.js:29'],
    confidence: 0.95,
    supportingObservations: [
      "Invocação de método de rota sem declaração do objeto 'app'.",
      'Inexistência de require(\'express\') prévio no cabeçalho do ficheiro.',
      'Stack trace indica ReferenceError síncrono durante module compile.',
    ],
    contradictingObservations: [
      'Nenhuma declaração prévia de const app ou mock encontrada no escopo.',
    ],
    predictedEffect: "Instanciar Express e declarar 'app' resolverá a falha de inicialização sem alterar lógica de rotas.",
  };

  const candidates = [
    {
      id: 'rep_cand_express_decl',
      name: 'DECLARATIVE_EXPRESS_BOILERPLATE',
      rank: 1,
      score: 0.92,
      confidence: 0.95,
      risk: 0.10,
      minimality: 0.88,
      linesAdded: 7,
      linesRemoved: 0,
      files: ['app.js'],
      rationale: 'Sintetiza instanciação formal Express, body-parser e listener HTTP na porta configurada.',
      status: 'RECOMMENDED_OPTIMAL',
    },
    {
      id: 'rep_cand_modular_import',
      name: 'MODULAR_APP_IMPORT',
      rank: 2,
      score: 0.74,
      confidence: 0.75,
      risk: 0.25,
      minimality: 0.95,
      linesAdded: 1,
      linesRemoved: 0,
      files: ['app.js'],
      rationale: 'Importa instância de app a partir de ficheiro modular existente (app_instance.js).',
      status: 'SECONDARY_OPTION',
    },
    {
      id: 'rep_cand_mock_stub',
      name: 'ARCHITECTURAL_MOCK_STUB',
      rank: 3,
      score: 0.42,
      confidence: 0.50,
      risk: 0.65,
      minimality: 0.96,
      linesAdded: 1,
      linesRemoved: 0,
      files: ['app.js'],
      rationale: 'Substitui chamadas de rota por mock em memória sem binding de socket real (alto risco comportamental).',
      status: 'HIGH_RISK_REJECTED',
    },
  ];

  const impact = {
    predictedFiles: ['app.js'],
    predictedSymbols: ['express', 'app', 'PORT'],
    predictedTasks: ['TSK_PREFLIGHT_STARTUP_VERIFY', 'TSK_HEALTHCHECK_SMOKE'],
    predictedContracts: ['API_ROOT_ENDPOINT', 'API_DDOS_ROUTE'],
    predictedConsumers: ['web_frontend', 'external_api_clients'],
    predictedRisk: 0.10,
    confidence: 0.95,
    behaviorChanges: [
      'Processo transita de crash imediato para listener contínuo em socket HTTP.',
      'Rotas /ddos tornam-se responsivas e capazes de processar payloads JSON.',
    ],
  };

  const proof = {
    proofId: 'prf_54_dina_verified',
    repairId: selectedCandidateId,
    failureId: hypothesis.failureId,
    rootCause: hypothesis.category,
    patchHash: 'patch_8f19e4a02c',
    beforeHash: 'state_dina_c0192e',
    afterHash: isRolledBack ? 'state_dina_c0192e' : 'state_dina_b48fa1',
    originalFailureResolved: !isRolledBack,
    preflightPassed: !isRolledBack,
    startupPassed: !isRolledBack,
    healthcheckPassed: !isRolledBack,
    behaviorResult: hasRegression ? 'INSUFFICIENT_EVIDENCE' : 'PROVEN_COMPATIBLE_WITHIN_SCOPE',
    regressionResult: hasRegression ? 'REGRESSION_DETECTED' : 'REGRESSION_FREE_WITHIN_SCOPE',
    coverage: 0.96,
    rollbackVerified: true,
    proofResult: isRolledBack
      ? 'REPAIR_REJECTED'
      : hasRegression
      ? 'REPAIR_REJECTED'
      : 'REPAIR_PROVEN',
    scope: 'LOCAL_MODULE_HTTP_RUNTIME',
  };

  return (
    <div id="verified-repair-synthesis-panel" className="bg-[#12131a] text-slate-200 p-6 rounded-xl border border-slate-800 shadow-2xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg text-cyan-400">
            <Wrench className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white tracking-wide">
                Verified Repair Synthesis & Patch Validation
              </h2>
              <span id="badge-decision-gate" className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                VERIFIED_REPAIR_SYNTHESIS_READY
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Fase 54 — Síntese de reparações com prova causal, ranking multi-critério, validação anti-regressão e rollback verificado.
            </p>
          </div>
        </div>

        {/* Global Action Badges */}
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-slate-800/80 border border-slate-700 rounded-lg text-xs font-medium text-slate-300">
            Projeto: <strong className="text-white">dina</strong>
          </span>
          <span className={`px-3 py-1 rounded-lg text-xs font-semibold border ${
            isPatchApplied ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' : 'bg-slate-700 text-slate-300 border-slate-600'
          }`}>
            {isPatchApplied ? 'Patch Ativo' : 'Estado Original'}
          </span>
          <span className={`px-3 py-1 rounded-lg text-xs font-semibold border ${
            proof.proofResult === 'REPAIR_PROVEN'
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
          }`}>
            {proof.proofResult}
          </span>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3 overflow-x-auto">
        <button
          id="tab-btn-root-cause"
          onClick={() => setActiveSubTab('root_cause')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeSubTab === 'root_cause'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          1. Causa Raiz & Evidência
        </button>
        <button
          id="tab-btn-candidates"
          onClick={() => setActiveSubTab('candidates')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeSubTab === 'candidates'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          2. Candidatos & Ranking
        </button>
        <button
          id="tab-btn-impact"
          onClick={() => setActiveSubTab('impact')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeSubTab === 'impact'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          3. Análise de Impacto
        </button>
        <button
          id="tab-btn-proof"
          onClick={() => setActiveSubTab('proof')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeSubTab === 'proof'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          4. Prova Formal de Reparação
        </button>
        <button
          id="tab-btn-security-rollback"
          onClick={() => setActiveSubTab('security_rollback')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeSubTab === 'security_rollback'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
              : 'bg-slate-900/60 text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          5. Sentinel & Rollback
        </button>
      </div>

      {/* Tab 1: Root Cause Hypothesis & Evidence */}
      {activeSubTab === 'root_cause' && (
        <div id="section-root-cause" className="space-y-4">
          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                Hipótese de Causa Raiz Estruturada
              </span>
              <span className="text-xs text-slate-400 font-mono">
                ID: {hypothesis.causeId} (Confiança: {(hypothesis.confidence * 100).toFixed(0)}%)
              </span>
            </div>
            <p className="text-sm font-medium text-white mt-2">{hypothesis.evidence}</p>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-emerald-400 font-semibold block mb-1">✓ Observações de Suporte:</span>
                <ul className="list-disc list-inside space-y-1 text-slate-300">
                  {hypothesis.supportingObservations.map((obs, idx) => (
                    <li key={idx}>{obs}</li>
                  ))}
                </ul>
              </div>
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-amber-400 font-semibold block mb-1">⚠ Observações Contraditórias:</span>
                <ul className="list-disc list-inside space-y-1 text-slate-300">
                  {hypothesis.contradictingObservations.map((obs, idx) => (
                    <li key={idx}>{obs}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
              <span>Locais afetados: <strong className="text-slate-200">{hypothesis.sourceLocations.join(', ')}</strong></span>
              <span>Efeito previsto: <strong className="text-slate-200">{hypothesis.predictedEffect}</strong></span>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Candidate Matrix & Multi-Criteria Ranking */}
      {activeSubTab === 'candidates' && (
        <div id="section-candidates" className="space-y-4">
          <div className="overflow-x-auto border border-slate-800 rounded-lg">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-3">Rank</th>
                  <th className="p-3">Estratégia de Reparação</th>
                  <th className="p-3">Score</th>
                  <th className="p-3">Confiança</th>
                  <th className="p-3">Risco</th>
                  <th className="p-3">Minimalidade</th>
                  <th className="p-3">Linhas</th>
                  <th className="p-3">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {candidates.map((cand) => (
                  <tr
                    key={cand.id}
                    className={`hover:bg-slate-800/40 transition-colors ${
                      selectedCandidateId === cand.id ? 'bg-cyan-500/10' : ''
                    }`}
                  >
                    <td className="p-3 font-bold text-cyan-400">#{cand.rank}</td>
                    <td className="p-3">
                      <div className="font-semibold text-white">{cand.name}</div>
                      <div className="text-[11px] text-slate-400">{cand.rationale}</div>
                    </td>
                    <td className="p-3 font-mono font-bold text-emerald-400">{cand.score.toFixed(2)}</td>
                    <td className="p-3">{(cand.confidence * 100).toFixed(0)}%</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        cand.risk <= 0.15 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {(cand.risk * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="p-3">{(cand.minimality * 100).toFixed(0)}%</td>
                    <td className="p-3 text-slate-400">+{cand.linesAdded} / -{cand.linesRemoved}</td>
                    <td className="p-3">
                      <button
                        id={`btn-select-cand-${cand.id}`}
                        onClick={() => setSelectedCandidateId(cand.id)}
                        className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
                          selectedCandidateId === cand.id
                            ? 'bg-cyan-500 text-black'
                            : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                        }`}
                      >
                        {selectedCandidateId === cand.id ? 'Selecionado' : 'Selecionar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Ex-Ante Predictive Impact */}
      {activeSubTab === 'impact' && (
        <div id="section-impact" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg">
              <span className="text-xs font-semibold text-cyan-400 block mb-2">Ficheiros & Símbolos Previstos</span>
              <div className="space-y-1 text-xs">
                <div>Ficheiros: <strong className="text-white">{impact.predictedFiles.join(', ')}</strong></div>
                <div>Símbolos: <strong className="text-white">{impact.predictedSymbols.join(', ')}</strong></div>
                <div>Risco Estimado: <strong className="text-emerald-400">{(impact.predictedRisk * 100).toFixed(0)}% (Baixo)</strong></div>
              </div>
            </div>
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg">
              <span className="text-xs font-semibold text-cyan-400 block mb-2">Tarefas & Contratos Afetados</span>
              <div className="space-y-1 text-xs">
                <div>Tarefas: <strong className="text-white">{impact.predictedTasks.join(', ')}</strong></div>
                <div>Contratos: <strong className="text-white">{impact.predictedContracts.join(', ')}</strong></div>
                <div>Consumers: <strong className="text-white">{impact.predictedConsumers.join(', ')}</strong></div>
              </div>
            </div>
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg">
              <span className="text-xs font-semibold text-cyan-400 block mb-2">Modificações Comportamentais</span>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-300">
                {impact.behaviorChanges.map((change, idx) => (
                  <li key={idx}>{change}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Formal Repair Proof Ledger */}
      {activeSubTab === 'proof' && (
        <div id="section-proof" className="space-y-4">
          <div className="p-5 bg-slate-900/60 border border-slate-800 rounded-lg space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <span className="text-xs text-slate-400 uppercase font-semibold">Registo Oficial de Prova de Reparação</span>
                <div className="text-base font-bold text-white font-mono mt-0.5">{proof.proofId}</div>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
                proof.proofResult === 'REPAIR_PROVEN'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
              }`}>
                {proof.proofResult}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-slate-400 block mb-1">Resolução do Erro</span>
                <span className="font-semibold text-emerald-400">
                  {proof.originalFailureResolved ? 'ORIGINAL_FAILURE_RESOLVED' : 'ORIGINAL_FAILURE_NOT_RESOLVED'}
                </span>
              </div>
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-slate-400 block mb-1">Preflight Pós-Patch</span>
                <span className="font-semibold text-emerald-400">{proof.preflightPassed ? 'APROVADO (0 Erros)' : 'FALHOU'}</span>
              </div>
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-slate-400 block mb-1">Prova Comportamental</span>
                <span className="font-semibold text-emerald-400">{proof.behaviorResult}</span>
              </div>
              <div className="p-3 bg-black/40 border border-slate-800/80 rounded-lg">
                <span className="text-slate-400 block mb-1">Ausência de Regressão</span>
                <span className={`font-semibold ${hasRegression ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {proof.regressionResult}
                </span>
              </div>
            </div>

            {/* Cryptographic Lineage Proof */}
            <div className="p-3 bg-black/60 border border-slate-800/80 rounded-lg font-mono text-xs text-slate-300 space-y-1">
              <div>before_state_hash: <span className="text-cyan-300">{proof.beforeHash}</span></div>
              <div>patch_hash:        <span className="text-amber-300">{proof.patchHash}</span></div>
              <div>after_state_hash:  <span className="text-emerald-300">{proof.afterHash}</span></div>
              <div>scope:             <span className="text-slate-400">{proof.scope}</span></div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: Sentinel Sovereignty & Verifiable Rollback */}
      {activeSubTab === 'security_rollback' && (
        <div id="section-security-rollback" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg space-y-2">
              <span className="text-xs font-semibold text-cyan-400 block">Soberania do Security Sentinel</span>
              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Código Remoto Malicioso: <strong>Vetado Unilateralmente</strong></span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Package Poisoning em package.json: <strong>Bloqueado</strong></span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Mutações em Lógica Económica: <strong>Requer Revisão Humana</strong></span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Rebaixamento de Autenticação/Auth: <strong>Bloqueado</strong></span>
                </li>
              </ul>
            </div>

            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg space-y-2">
              <span className="text-xs font-semibold text-cyan-400 block">Rollback Verificável com Prova de Estado</span>
              <p className="text-xs text-slate-300">
                Garante restauração exata byte-a-byte: <code className="text-cyan-300 font-mono">state_after_rollback_hash == state_before_hash</code>.
              </p>
              <div className="pt-2 flex items-center gap-2">
                <button
                  id="btn-verify-rollback"
                  onClick={() => {
                    setIsRolledBack(!isRolledBack);
                    setIsPatchApplied(isRolledBack);
                  }}
                  className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  {isRolledBack ? 'Restaurar Patch Aprovado' : 'Simular Rollback Atómico'}
                </button>
                <button
                  id="btn-trigger-regression-test"
                  onClick={() => setHasRegression(!hasRegression)}
                  className="px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {hasRegression ? 'Remover Regressão' : 'Induzir Regressão Lateral'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
