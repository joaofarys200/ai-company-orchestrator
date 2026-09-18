import React, { useState } from 'react';
import {
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
  FileCode,
  RotateCcw,
  Zap,
  Activity,
  Layers,
  Database,
  Lock,
  GitCommit,
  Terminal,
} from 'lucide-react';

interface SafeSelfModificationPanelProps {
  missionId?: string;
}

export const SafeSelfModificationPanel: React.FC<SafeSelfModificationPanelProps> = ({
  missionId: _missionId,
}) => {
  const [activeSubtab, setActiveSubtab] = useState<string>('governance');
  const [policy, setPolicy] = useState<string>('STANDARD');

  return (
    <div className="flex h-full flex-col bg-[#0b1317] text-gray-200">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#a1bebf]/15 bg-[#0d171b] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <GitCommit className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">
                Safe Self-Modification & Transactional Implementation
              </h2>
              <span className="rounded bg-teal-500/20 px-2 py-0.5 text-xs font-semibold text-teal-300">
                FASE 65
              </span>
              <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                <ShieldCheck className="h-3 w-3" />
                TRANSACTIONAL ENGINE ACTIVE
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Governed execution, preflight baselines, AST scope enforcement, continuous verification, and deterministic rollback.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Política:</span>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              className="rounded border border-gray-700 bg-[#121e23] px-2.5 py-1 text-xs text-gray-200 focus:border-teal-500 focus:outline-none"
            >
              <option value="STRICT">STRICT</option>
              <option value="STANDARD">STANDARD</option>
              <option value="DEVELOPMENT">DEVELOPMENT</option>
              <option value="EMERGENCY_ROLLBACK">EMERGENCY_ROLLBACK</option>
            </select>
          </div>

          <button
            id="selfmod-action-start-transaction"
            className="flex items-center gap-1.5 rounded bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-500 transition-colors"
          >
            <Zap className="h-3.5 w-3.5" />
            Nova Transação
          </button>
        </div>
      </div>

      {/* 12 Scenario Subtabs */}
      <div className="flex border-b border-gray-800 bg-[#0c1417] px-6 text-xs font-semibold overflow-x-auto">
        <button
          id="selfmod-subtab-governance"
          onClick={() => setActiveSubtab('governance')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'governance'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          01. Governação & Aprovação
        </button>

        <button
          id="selfmod-subtab-preflight"
          onClick={() => setActiveSubtab('preflight')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'preflight'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <CheckCircle className="h-3.5 w-3.5" />
          02. Pré-Voo & Limpeza
        </button>

        <button
          id="selfmod-subtab-snapshot"
          onClick={() => setActiveSubtab('snapshot')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'snapshot'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Database className="h-3.5 w-3.5" />
          03. Snapshot Transacional
        </button>

        <button
          id="selfmod-subtab-patch-proposal"
          onClick={() => setActiveSubtab('patch-proposal')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'patch-proposal'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <FileCode className="h-3.5 w-3.5" />
          04. Proposta de Patch
        </button>

        <button
          id="selfmod-subtab-patch-validation"
          onClick={() => setActiveSubtab('patch-validation')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'patch-validation'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          05. Validação de Patch
        </button>

        <button
          id="selfmod-subtab-transaction-state"
          onClick={() => setActiveSubtab('transaction-state')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'transaction-state'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Layers className="h-3.5 w-3.5" />
          06. Estado da Transação
        </button>

        <button
          id="selfmod-subtab-build"
          onClick={() => setActiveSubtab('build')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'build'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Terminal className="h-3.5 w-3.5" />
          07. Build & Sintaxe
        </button>

        <button
          id="selfmod-subtab-tests"
          onClick={() => setActiveSubtab('tests')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'tests'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Activity className="h-3.5 w-3.5" />
          08. Testes & Seleção
        </button>

        <button
          id="selfmod-subtab-verification"
          onClick={() => setActiveSubtab('verification')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'verification'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <CheckCircle className="h-3.5 w-3.5" />
          09. Verificação Contínua
        </button>

        <button
          id="selfmod-subtab-architecture-rescan"
          onClick={() => setActiveSubtab('architecture-rescan')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'architecture-rescan'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Layers className="h-3.5 w-3.5" />
          10. Re-Scan Arquitetural
        </button>

        <button
          id="selfmod-subtab-rollback"
          onClick={() => setActiveSubtab('rollback')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'rollback'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          11. Rollback Determinístico
        </button>

        <button
          id="selfmod-subtab-commit-gate"
          onClick={() => setActiveSubtab('commit-gate')}
          className={`flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 transition-colors ${
            activeSubtab === 'commit-gate'
              ? 'border-teal-500 text-teal-300'
              : 'border-transparent text-gray-400 hover:text-gray-200'
          }`}
        >
          <Lock className="h-3.5 w-3.5" />
          12. Portão de Commit
        </button>
      </div>

      {/* Main Content Area */}
      <div className="p-6 space-y-6 flex-1 overflow-y-auto">
        {/* Core Invariant Card */}
        <div className="rounded-lg border border-teal-500/20 bg-[#0d181d] p-4 text-xs text-gray-300 space-y-2">
          <div className="flex items-center gap-2 font-bold text-teal-400">
            <Lock className="h-4 w-4" />
            <span>Invariantes Centrais da Fase 65</span>
          </div>
          <p className="text-gray-400">
            <strong>APPROVAL != IMPLEMENTATION</strong> e <strong>IMPLEMENTATION != COMMITTED_STATE</strong>.
            Nenhuma modificação é promovida a commit sem aprovação de governação, integridade de snapshots SHA-256,
            validação AST de escopo, re-scan arquitetural empírico e verificação contínua.
          </p>
        </div>

        {/* Dynamic Subtab Rendering */}
        {activeSubtab === 'governance' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-teal-400" />
              01. Validação de Decisão da Fase 64 (Governance Gate)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-2">
                <div className="text-gray-400 font-semibold">Decisão Autorizada</div>
                <div className="text-emerald-400 font-bold flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4" /> APPROVED_FOR_IMPLEMENTATION
                </div>
                <div className="text-gray-400">ID da Decisão: <span className="font-mono text-gray-200">dec_f64_auth_boundary</span></div>
                <div className="text-gray-400">Problema: <span className="text-gray-200">prob_coupling_01 (High Efferent Coupling)</span></div>
                <div className="text-gray-400">Alternativa Selecionada: <span className="text-gray-200">boundary_extraction</span></div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-2">
                <div className="text-gray-400 font-semibold">Assinatura Criptográfica</div>
                <div className="font-mono text-[11px] text-teal-300 break-all bg-[#091013] p-2 rounded border border-gray-800">
                  sha256: 7f8a9b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcd
                </div>
                <div className="text-emerald-400 text-xs">✓ Proveniência da Fase 64 Verificada e Válida</div>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'preflight' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-teal-400" />
              02. Pré-Voo & Verificação de Limpeza
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-1">
                <div className="text-gray-400">Limpeza do Git</div>
                <div className="text-emerald-400 font-bold">CLEAN WORKSPACE</div>
                <p className="text-gray-500 text-[11px]">0 ficheiros não confirmados</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-1">
                <div className="text-gray-400">Permissões de Ficheiro</div>
                <div className="text-emerald-400 font-bold">ALL_WRITABLE</div>
                <p className="text-gray-500 text-[11px]">Superfície alvo com escrita permitida</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-1">
                <div className="text-gray-400">Linha de Base de Testes</div>
                <div className="text-emerald-400 font-bold">BASELINE CAPTURED</div>
                <p className="text-gray-500 text-[11px]">570/570 testes no estado inicial</p>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'snapshot' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Database className="h-4 w-4 text-teal-400" />
              03. Snapshot Transacional Imutável
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Snapshot ID: <span className="font-mono text-white">snap_tx_928172</span></span>
                <span className="rounded bg-teal-500/20 px-2 py-0.5 text-teal-300 font-mono">SHA-256 FROZEN</span>
              </div>
              <div className="font-mono text-[11px] text-gray-300 bg-[#091013] p-2.5 rounded border border-gray-800">
                files_fingerprint: a81f729b4e13c88a6d4b29841f238d77e43d19028bc12a97
              </div>
              <p className="text-gray-400 text-xs">
                Contém cópias integrais de 4 ficheiros com hashes correspondentes para garantia de reversibilidade absoluta.
              </p>
            </div>
          </div>
        )}

        {activeSubtab === 'patch-proposal' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <FileCode className="h-4 w-4 text-teal-400" />
              04. Proposta de Patch Mínimo & Rollback Inverso
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs font-mono space-y-2">
              <div className="text-teal-400 font-semibold">// Forward Patch Diff (Atómico)</div>
              <div className="bg-[#091013] p-3 rounded text-gray-300 overflow-x-auto text-[11px] border border-gray-800">
                <span className="text-emerald-400">+ from .boundary import IMissionCoordinator</span><br />
                <span className="text-emerald-400">+ class DecoupledHandler(IMissionCoordinator):</span><br />
                <span className="text-gray-500">   def handle_message(self, msg: dict) -&gt; dict:</span>
              </div>
              <div className="text-amber-400 font-semibold">// Rollback Patch Inverso Pré-Sintetizado</div>
              <div className="bg-[#091013] p-3 rounded text-gray-300 overflow-x-auto text-[11px] border border-gray-800">
                <span className="text-rose-400">- from .boundary import IMissionCoordinator</span><br />
                <span className="text-rose-400">- class DecoupledHandler(IMissionCoordinator):</span>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'patch-validation' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-teal-400" />
              05. Validação de Patch (AST & Security Sentinel)
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-2">
                <div className="font-bold text-white">Análise Sintática AST</div>
                <div className="text-emerald-400 flex items-center gap-1.5 font-semibold">
                  <CheckCircle className="h-4 w-4" /> ast.parse() Concluído com Sucesso
                </div>
                <p className="text-gray-400">Zero violações de sintaxe ou imports inexistentes.</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-2">
                <div className="font-bold text-white">Security Sentinel</div>
                <div className="text-emerald-400 flex items-center gap-1.5 font-semibold">
                  <ShieldCheck className="h-4 w-4" /> Zero Padrões Destrutivos
                </div>
                <p className="text-gray-400">Proibição de rmtree, os.system, chaves privadas ou APIs externas.</p>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'transaction-state' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers className="h-4 w-4 text-teal-400" />
              06. Máquina de Estados da Transação (19 Estados)
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">Estado Atual:</span>
                <span className="rounded bg-teal-500/20 px-2 py-0.5 font-mono font-bold text-teal-300">
                  APPLIED
                </span>
                <span className="text-gray-500 font-mono text-[11px]">(tx_928172)</span>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-gray-400 overflow-x-auto py-2">
                <span className="rounded bg-gray-800 px-2 py-1">CREATED</span>
                <span>→</span>
                <span className="rounded bg-gray-800 px-2 py-1">PREFLIGHT</span>
                <span>→</span>
                <span className="rounded bg-gray-800 px-2 py-1">SNAPSHOTTED</span>
                <span>→</span>
                <span className="rounded bg-gray-800 px-2 py-1">PLANNED</span>
                <span>→</span>
                <span className="rounded bg-gray-800 px-2 py-1">PATCH_VALIDATED</span>
                <span>→</span>
                <span className="rounded bg-teal-500/30 border border-teal-500/50 text-teal-200 px-2 py-1 font-bold">APPLIED</span>
                <span>→</span>
                <span className="rounded bg-gray-900 text-gray-500 px-2 py-1">BUILDING</span>
                <span>→</span>
                <span className="rounded bg-gray-900 text-gray-500 px-2 py-1">COMMITTED</span>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'build' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Terminal className="h-4 w-4 text-teal-400" />
              07. Validação de Build & Compilação
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs font-mono space-y-2">
              <div className="text-emerald-400">✓ py_compile: backend/websocket/handlers/missions.py (0 errors)</div>
              <div className="text-emerald-400">✓ pip check: No broken requirements found</div>
              <div className="text-emerald-400">✓ Vite frontend build: 0 errors in 3.73s</div>
            </div>
          </div>
        )}

        {activeSubtab === 'tests' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Activity className="h-4 w-4 text-teal-400" />
              08. Testes & Seleção Inteligente de Impacto
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-gray-300 font-semibold">Suíte Executada: 20/20 Testes Aprovados</span>
                <span className="text-emerald-400 font-bold">0 FALHAS</span>
              </div>
              <div className="text-gray-400 text-[11px]">
                Nenhum teste ausente foi interpretado como PASS. Seleção orientada por grafo de dependência e consumidores afetados.
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'verification' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-teal-400" />
              09. Livro de Evidência Contínua (Fase 62)
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-2">
              <div className="text-gray-400">Hash de Evidência Vinculada:</div>
              <div className="font-mono text-teal-300 bg-[#091013] p-2 rounded border border-gray-800">
                ev_928172_sha256: d84a91b2c7e0984f1a23e5904bc38291a084c71829e93847
              </div>
              <div className="text-gray-400 text-[11px]">
                Vinculado a: <span className="text-white">tx_928172</span> | Snapshot: <span className="text-white">snap_tx_928172</span>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'architecture-rescan' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers className="h-4 w-4 text-teal-400" />
              10. Re-Scan Arquitetural Pós-Modificação
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-1">
                <div className="text-gray-400">Acoplamento Eferente</div>
                <div className="text-white font-bold text-sm">14 → 6 (-8)</div>
                <p className="text-emerald-400 text-[11px]">Redução real observada de 57%</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 space-y-1">
                <div className="text-gray-400">SCCs Cíclicos</div>
                <div className="text-white font-bold text-sm">3 → 2 (-1)</div>
                <p className="text-emerald-400 text-[11px]">Ciclo de dependência resolvido</p>
              </div>
            </div>
          </div>
        )}

        {activeSubtab === 'rollback' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-teal-400" />
              11. Rollback Determinístico Verificado por Hash
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-2">
              <div className="text-emerald-400 font-bold">CURRENT_HASHES == SNAPSHOT_HASHES (100% Match)</div>
              <p className="text-gray-400">
                Em caso de falha de teste ou quebra contratual, todos os ficheiros são restaurados para o hash exato do snapshot.
                Zero estado residual detectado.
              </p>
            </div>
          </div>
        )}

        {activeSubtab === 'commit-gate' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Lock className="h-4 w-4 text-teal-400" />
              12. Portão de Commit (11 Condições Obrigatórias)
            </h3>
            <div className="rounded-lg border border-gray-800 bg-[#101a1f] p-4 text-xs space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-gray-300 font-semibold">Decisão de Commit:</span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono font-bold text-emerald-300">
                  COMMIT_ELIGIBLE
                </span>
              </div>
              <div className="text-gray-400 text-[11px] grid grid-cols-1 md:grid-cols-2 gap-1 pt-2">
                <div>✓ Governação Fase 64 Válida</div>
                <div>✓ Escopo de Patch Estrito</div>
                <div>✓ Build & Sintaxe Pass</div>
                <div>✓ Testes Impactados Pass</div>
                <div>✓ Contratos Preservados</div>
                <div>✓ Comportamento Preservado</div>
                <div>✓ Verificação Contínua Concluída</div>
                <div>✓ Re-Scan Arquitetural Melhorado</div>
                <div>✓ Security Sentinel Aprovado</div>
                <div>✓ Checkpoint de Rollback Válido</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SafeSelfModificationPanel;
