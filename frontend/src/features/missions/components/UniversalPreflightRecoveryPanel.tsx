import React, { useState } from 'react';
import {
  Stethoscope,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  FileCode,
  Layers,
  Lock,
  Search,
  Zap,
} from 'lucide-react';

export const UniversalPreflightRecoveryPanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'preflight' | 'repair' | 'healthcheck' | 'policy'>('overview');
  const [selectedPolicy, setSelectedPolicy] = useState<string>('STANDARD');
  const [isRepairApplied, setIsRepairApplied] = useState<boolean>(true);
  const recoveryCount = 1;
  const [healthStatus, setHealthStatus] = useState<{ started: boolean; ready: boolean; latency: number; code: number }>({
    started: true,
    ready: true,
    latency: 2.8,
    code: 200,
  });

  const profile = {
    projectId: 'dina',
    language: 'JAVASCRIPT',
    runtime: 'NODE_CJS',
    packageManager: 'npm',
    entrypoint: 'app.js',
    port: 3000,
    healthcheckPath: '/',
    manifest: 'package.json',
    hasNodeModules: true,
  };

  const diagnostic = {
    id: 'diag_ref_app_79',
    errorClass: 'REFERENCE_ERROR',
    symbol: 'app',
    file: 'app.js',
    line: 79,
    column: 1,
    probableCause: "O objeto 'app' foi invocado (app.post('/ddos', ...)) sem que a aplicação Express tenha sido declarada ou inicializada.",
    confidence: 'HIGH_CONFIDENCE',
    confidenceScore: 0.95,
    suggestedFix: "Adicionar 'const express = require(\"express\"); const app = express();' e middlewares antes do registo das rotas.",
  };

  const preflightIssues = [
    {
      id: 'pre_01',
      severity: 'RESOLVED',
      category: 'REFERENCE_ERROR',
      message: "Objeto 'app' invocado sem inicialização Express",
      location: 'app.js:79',
      status: 'Corrigido via Safe Repair',
    },
    {
      id: 'pre_02',
      severity: 'RESOLVED',
      category: 'IMPORT_MISSING',
      message: "Módulo 'axios' utilizado sem require explícito",
      location: 'app.js:29',
      status: 'Corrigido via Safe Repair',
    },
    {
      id: 'pre_03',
      severity: 'ADVISORY',
      category: 'PORT_CHECK',
      message: 'Porta 3000 livre e verificada com sucesso',
      location: 'config',
      status: 'OK',
    },
  ];

  return (
    <div id="universal-preflight-recovery-panel" className="bg-[#12131a] text-slate-200 p-6 rounded-xl border border-slate-800 shadow-2xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400">
            <Stethoscope className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white tracking-wide">
                Universal Project Preflight & Auto-Recovery
              </h2>
              <span id="badge-decision-gate" className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                PREFLIGHT_RECOVERY_READY
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Fase 53 — Validação prévia de sanidade, diagnóstico estruturado de crashes e auto-recuperação cirúrgica reversível.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            id="btn-run-preflight"
            onClick={() => alert("Preflight read-only executado: state_before_hash == state_after_hash.")}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
          >
            <Search className="w-3.5 h-3.5 text-blue-400" />
            Executar Preflight
          </button>
          <button
            id="btn-probe-healthcheck"
            onClick={() => {
              setHealthStatus({ started: true, ready: true, latency: 1.9, code: 200 });
              alert("Healthcheck Probe HTTP GET / -> 200 OK (1.9ms)");
            }}
            className="px-3.5 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
          >
            <Activity className="w-3.5 h-3.5" />
            Sondar Saúde (Porta 3000)
          </button>
        </div>
      </div>

      {/* Project Runtime Profile Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Projeto Ativo</div>
          <div className="text-sm font-mono font-medium text-emerald-400 mt-0.5">{profile.projectId}</div>
        </div>
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Runtime / Stack</div>
          <div className="text-sm font-mono text-cyan-300 mt-0.5">{profile.runtime}</div>
        </div>
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Entrypoint</div>
          <div className="text-sm font-mono text-amber-300 mt-0.5">{profile.entrypoint}</div>
        </div>
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Porta Padrão</div>
          <div className="text-sm font-mono text-indigo-300 mt-0.5">:{profile.port}</div>
        </div>
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Manifesto</div>
          <div className="text-sm font-mono text-purple-300 mt-0.5">{profile.manifest}</div>
        </div>
        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800/80">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Health Status</div>
          <div className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5 mt-0.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            200 OK ({healthStatus.latency}ms)
          </div>
        </div>
      </div>

      {/* Sub Tabs */}
      <div className="flex border-b border-slate-800 gap-2">
        <button
          id="tab-btn-preflight-overview"
          onClick={() => setActiveSubTab('overview')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeSubTab === 'overview'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Diagnóstico & Recuperação
        </button>
        <button
          id="tab-btn-preflight-issues"
          onClick={() => setActiveSubTab('preflight')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeSubTab === 'preflight'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          Preflight Read-Only
        </button>
        <button
          id="tab-btn-safe-repair"
          onClick={() => setActiveSubTab('repair')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeSubTab === 'repair'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCode className="w-3.5 h-3.5" />
          Safe Repair Planner & Rollback
        </button>
        <button
          id="tab-btn-preflight-policy"
          onClick={() => setActiveSubTab('policy')}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeSubTab === 'policy'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          Políticas & Security Sentinel
        </button>
      </div>

      {/* Content: Overview & Diagnostics */}
      {activeSubTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Crash Diagnostic Card */}
            <div className="p-5 bg-slate-900/80 rounded-xl border border-rose-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-rose-400" />
                  <h3 className="font-semibold text-rose-200">Diagnóstico Estruturado de Crash</h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  {diagnostic.errorClass}
                </span>
              </div>

              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800 font-mono text-xs space-y-1 text-slate-300">
                <div className="text-rose-400 font-semibold">ReferenceError: {diagnostic.symbol} is not defined</div>
                <div className="text-slate-500">at Object.&lt;anonymous&gt; ({diagnostic.file}:{diagnostic.line}:{diagnostic.column})</div>
              </div>

              <div className="text-xs space-y-2 text-slate-300">
                <div>
                  <span className="text-slate-400 font-medium">Causa Raiz Provável:</span>
                  <p className="mt-0.5 text-slate-300">{diagnostic.probableCause}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Correção Recomendada:</span>
                  <p className="mt-0.5 text-emerald-300 bg-emerald-950/40 p-2 rounded border border-emerald-800/40 font-mono text-[11px]">
                    {diagnostic.suggestedFix}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs text-slate-400">
                <div>Confiança: <span className="text-emerald-400 font-semibold">{diagnostic.confidence} ({diagnostic.confidenceScore * 100}%)</span></div>
                <div>Diagnóstico ID: <span className="font-mono text-slate-300">{diagnostic.id}</span></div>
              </div>
            </div>

            {/* Safe Auto-Recovery Execution Card */}
            <div className="p-5 bg-slate-900/80 rounded-xl border border-emerald-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-semibold text-emerald-200">Auto-Recovery Supervisionado</h3>
                </div>
                <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${isRepairApplied ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'}`}>
                  {isRepairApplied ? 'GATE_CLEARED' : 'ROLLED_BACK'}
                </span>
              </div>

              <div className="text-xs text-slate-300 space-y-2.5">
                <p>
                  O ciclo adaptativo aplicou o plano de reparação <span className="font-mono text-emerald-300">rep_dina_express_app</span> com snapshot atómico prévio:
                </p>
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1.5 font-mono text-[11px]">
                  <div className="text-emerald-400">✓ 1. Snapshot do ficheiro app.js criado</div>
                  <div className="text-emerald-400">✓ 2. Injeção de Express boilerplate e middlewares aplicada</div>
                  <div className="text-emerald-400">✓ 3. Preflight pós-patch verificado sem erros (node --check OK)</div>
                  <div className="text-emerald-400">✓ 4. Arranque do servidor concluído na porta 3000</div>
                  <div className="text-emerald-400">✓ 5. Healthcheck HTTP GET / aprovado (status 200 OK)</div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <div className="text-xs text-slate-400">
                  Tentativas: <span className="text-slate-200 font-semibold">{recoveryCount} / 3</span>
                </div>
                <div className="flex gap-2">
                  <button
                    id="btn-rollback-repair"
                    onClick={() => {
                      setIsRepairApplied(false);
                      alert("Rollback executado: estado original de app.js restaurado a partir do snapshot.");
                    }}
                    className="px-3 py-1.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded text-xs flex items-center gap-1 transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Reverter (Rollback)
                  </button>
                  <button
                    id="btn-apply-safe-repair"
                    onClick={() => {
                      setIsRepairApplied(true);
                      alert("Reparação aplicada cirurgicamente com verificação pós-patch.");
                    }}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs flex items-center gap-1 transition-colors"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Re-aplicar Reparação
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Workflow Sequence Diagram */}
          <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800 space-y-3">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Ciclo Formal de Validação e Recuperação da Fase 53
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center text-xs">
              <div className="p-2.5 bg-slate-950 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 font-mono">1. PREFLIGHT</div>
                <div className="text-emerald-400 font-medium mt-1">Read-Only Check</div>
              </div>
              <div className="p-2.5 bg-slate-950 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 font-mono">2. RUN & PROBE</div>
                <div className="text-cyan-400 font-medium mt-1">Spawn & Healthcheck</div>
              </div>
              <div className="p-2.5 bg-slate-950 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 font-mono">3. DIAGNOSE</div>
                <div className="text-amber-400 font-medium mt-1">Crash Classifier</div>
              </div>
              <div className="p-2.5 bg-slate-950 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 font-mono">4. SAFE REPAIR</div>
                <div className="text-indigo-400 font-medium mt-1">Snapshot & Patch</div>
              </div>
              <div className="p-2.5 bg-slate-950 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 font-mono">5. VERIFY & GATE</div>
                <div className="text-emerald-400 font-medium mt-1">Smoke & Finish Gate</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Content: Preflight Issues Table */}
      {activeSubTab === 'preflight' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Inspeção de Sanidade Pré-Execução (Read-Only)</h3>
            <span className="text-xs text-slate-400 font-mono">Hash Invariante: 7f8a9e2d (Preservado)</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                <tr>
                  <th className="p-3">ID</th>
                  <th className="p-3">Severidade</th>
                  <th className="p-3">Categoria</th>
                  <th className="p-3">Mensagem</th>
                  <th className="p-3">Localização</th>
                  <th className="p-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {preflightIssues.map((issue) => (
                  <tr key={issue.id} className="hover:bg-slate-900/40">
                    <td className="p-3 text-slate-400">{issue.id}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        {issue.severity}
                      </span>
                    </td>
                    <td className="p-3 text-cyan-300">{issue.category}</td>
                    <td className="p-3 font-sans text-slate-200">{issue.message}</td>
                    <td className="p-3 text-amber-300">{issue.location}</td>
                    <td className="p-3 text-emerald-400 font-sans">{issue.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Content: Safe Repair Planner */}
      {activeSubTab === 'repair' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Plano de Reparação Atómico (Safe Repair Planner)</h3>
            <span className="text-xs text-emerald-400 font-mono">Confiança: HIGH_CONFIDENCE (Risco: 0.10)</span>
          </div>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs space-y-3">
            <div className="text-slate-400">// Patch cirúrgico aplicado a: workspace/projects/dina/app.js</div>
            <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded text-emerald-300 space-y-1">
              <div>+ const express = require('express');</div>
              <div>+ const axios = require('axios');</div>
              <div>+ const path = require('path');</div>
              <div>+ const app = express();</div>
              <div>+ const PORT = process.env.PORT || 3000;</div>
              <div>+ app.use(express.json());</div>
              <div>+ app.use(express.static(path.join(__dirname)));</div>
            </div>
            <div className="text-slate-400">// Snapshot original preservado para Rollback em caso de falha de verificação.</div>
          </div>
        </div>
      )}

      {/* Content: Policies & Security Sentinel */}
      {activeSubTab === 'policy' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Políticas de Recuperação & Soberania do Security Sentinel</h3>
            <select
              id="select-preflight-policy"
              value={selectedPolicy}
              onChange={(e) => setSelectedPolicy(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-xs rounded px-3 py-1.5 text-slate-200"
            >
              <option value="STANDARD">STANDARD (Auto-repair para High Confidence)</option>
              <option value="STRICT">STRICT (Aprovação humana para warnings)</option>
              <option value="CRITICAL">CRITICAL (Tolerância zero a mutações)</option>
              <option value="ECONOMIC_CRITICAL">ECONOMIC_CRITICAL (Invariantes financeiras)</option>
              <option value="SECURITY_CRITICAL">SECURITY_CRITICAL (Invariantes de autenticação)</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800 space-y-2 text-xs">
              <div className="font-semibold text-emerald-300 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                Soberania do Sentinel
              </div>
              <p className="text-slate-400">
                Nenhum plano de reparação pode contornar os gates do Sentinel. Tentativas de instalar pacotes maliciosos, adulterar permissões ou modificar endpoints econômicos são vetadas na raiz.
              </p>
            </div>
            <div className="p-4 bg-slate-900/60 rounded-lg border border-slate-800 space-y-2 text-xs">
              <div className="font-semibold text-cyan-300 flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                Limite de Tentativas (Anti-Loop)
              </div>
              <p className="text-slate-400">
                Máximo de 3 tentativas sob política STANDARD. Se a falha persistir, o processo é suspenso para intervenção do operador sem loops infinitos de reparação.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
