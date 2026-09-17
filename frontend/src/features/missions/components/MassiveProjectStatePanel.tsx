import React, { useState } from 'react';
import {
  Layers,
  Search,
  Activity,
  GitBranch,
  ShieldCheck,
  Zap,
  HardDrive,
  Cpu,
  RefreshCw,
  ArrowRight,
  FolderTree,
} from 'lucide-react';

export const MassiveProjectStatePanel: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<
    'overview' | 'tiers' | 'subgraph' | 'indexes' | 'planning' | 'snapshots'
  >('overview');

  const [selectedShard, setSelectedShard] = useState<string>('backend');
  const [searchSymbol, setSearchSymbol] = useState<string>('sym_api_checkout');
  const [changeObjective, setChangeObjective] = useState<string>(
    'Evolução do contrato de pagamentos e checkout multi-serviço'
  );
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [snapshotCreated, setSnapshotCreated] = useState<boolean>(false);

  const shards = [
    {
      id: 'frontend',
      name: 'Frontend Web Client',
      type: 'SERVICE',
      tier: 'WARM',
      files: 384,
      symbols: 2410,
      rev: 42,
      hash: 'a1f89c02e5b41290',
      deps: ['shared'],
    },
    {
      id: 'backend',
      name: 'Backend API & Core',
      type: 'SERVICE',
      tier: 'HOT',
      files: 512,
      symbols: 4890,
      rev: 88,
      hash: 'c4e97a18f2d33481',
      deps: ['shared'],
    },
    {
      id: 'workers',
      name: 'Async Celery Workers',
      type: 'SERVICE',
      tier: 'COLD',
      files: 96,
      symbols: 780,
      rev: 19,
      hash: 'f9011d82b4a78129',
      deps: ['shared', 'backend'],
    },
    {
      id: 'infra',
      name: 'Infrastructure & Docker',
      type: 'DOMAIN',
      tier: 'COLD',
      files: 48,
      symbols: 190,
      rev: 12,
      hash: 'd8820c41a7e23901',
      deps: ['shared'],
    },
    {
      id: 'shared',
      name: 'Shared Contracts & Schemas',
      type: 'PACKAGE',
      tier: 'WARM',
      files: 64,
      symbols: 850,
      rev: 54,
      hash: 'b7194e82d0185f44',
      deps: [],
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4 text-slate-100 bg-slate-950/80 rounded-xl border border-slate-800 shadow-2xl backdrop-blur-md">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-wide">
                Modular Project State Fabric & Massive Repository Planning
              </h2>
              <span className="rounded bg-cyan-900/50 px-2 py-0.5 text-xs font-semibold text-cyan-300 border border-cyan-700/50">
                Fase 58
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Escalabilidade Monorepo até 10M LOC com Hot/Warm/Cold Tiering, Índices Reversos em O(1) e Subgrafos Focados
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-950/60 px-2.5 py-1 text-[11px] font-medium text-emerald-400 border border-emerald-800/60">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            FABRIC_ACTIVE
          </span>
          <span className="rounded-full bg-blue-950/60 px-2.5 py-1 text-[11px] font-medium text-blue-400 border border-blue-800/60">
            SQLITE_WAL: READY
          </span>
          <span className="rounded-full bg-purple-950/60 px-2.5 py-1 text-[11px] font-medium text-purple-400 border border-purple-800/60">
            OOM_GUARD: 256MB
          </span>
        </div>
      </div>

      {/* Sub-tab Navigation */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-800 pb-2">
        {[
          { id: 'overview', label: 'Visão Geral dos Shards', icon: FolderTree },
          { id: 'tiers', label: 'Tiers & Orçamento de Memória', icon: Cpu },
          { id: 'subgraph', label: 'Subgrafo Focado (Targeted)', icon: GitBranch },
          { id: 'indexes', label: 'Índices Reversos O(1)', icon: Search },
          { id: 'planning', label: 'Planeamento de Mudança Causal', icon: Activity },
          { id: 'snapshots', label: 'Snapshots & Sentinel', icon: ShieldCheck },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                isActive
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Sub-tab 1: Overview */}
      {activeSubTab === 'overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {shards.map((s) => (
              <div
                key={s.id}
                onClick={() => setSelectedShard(s.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedShard === s.id
                    ? 'bg-slate-900 border-cyan-500/60 shadow-md'
                    : 'bg-slate-900/40 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-bold text-slate-200">{s.name}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      s.tier === 'HOT'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                        : s.tier === 'WARM'
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    }`}
                  >
                    {s.tier}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 space-y-1">
                  <div className="flex justify-between">
                    <span>Ficheiros:</span>
                    <span className="font-mono text-slate-200">{s.files}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Símbolos:</span>
                    <span className="font-mono text-slate-200">{s.symbols}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Revisão:</span>
                    <span className="font-mono text-cyan-400">r{s.rev}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span>Hash:</span>
                    <span className="font-mono text-slate-400">{s.hash}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2">
              Detalhes do Shard Selecionado: <span className="text-cyan-400">{selectedShard}</span>
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block">Tipo de Partição:</span>
                <span className="font-mono text-slate-200">
                  {shards.find((s) => s.id === selectedShard)?.type}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Dependências Inter-Shard:</span>
                <span className="font-mono text-slate-200">
                  {shards.find((s) => s.id === selectedShard)?.deps.join(', ') || 'Nenhuma (Raiz)'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Estratégia de Persistência:</span>
                <span className="text-emerald-400 font-mono">SQLite WAL Table Sharding</span>
              </div>
              <div>
                <span className="text-slate-400 block">Status de Invalidação:</span>
                <span className="text-cyan-400 font-mono">SYNCHRONIZED (0 stale)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab 2: Tiers & Memory Budget */}
      {activeSubTab === 'tiers' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-red-950/20 border border-red-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="h-4 w-4 text-red-400" />
                <h4 className="text-xs font-bold text-red-300">HOT STATE (RAM da Missão)</h4>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Símbolos e ficheiros ativamente manipulados pelo Autonomous Engineering Loop na missão atual.
              </p>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Ficheiros Ativos:</span>
                  <span className="font-mono font-bold text-red-300">8 / 500</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                  <div className="bg-red-500 h-1.5 rounded-full" style={{ width: '1.6%' }} />
                </div>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-amber-950/20 border border-amber-500/30">
              <div className="flex items-center gap-2 mb-2">
                <RefreshCw className="h-4 w-4 text-amber-400" />
                <h4 className="text-xs font-bold text-amber-300">WARM STATE (LRU Cache)</h4>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Cache determinístico em RAM com evicção automática baseada em frequência de acesso e tamanho.
              </p>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Capacidade Usada:</span>
                  <span className="font-mono font-bold text-amber-300">32.4 MB / 128 MB</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                  <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: '25.3%' }} />
                </div>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-blue-950/20 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <HardDrive className="h-4 w-4 text-blue-400" />
                <h4 className="text-xs font-bold text-blue-300">COLD STATE (SQLite WAL)</h4>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                Grafo global persistido no disco local. Não consome RAM e é carregado sob demanda via lazy loading.
              </p>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Indexado:</span>
                  <span className="font-mono font-bold text-blue-300">10,500,000 LOC</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5">
                  <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: '100%' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2">
              Proteção Ativa Contra OOM (ProjectMemoryBudgetManager)
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-slate-400 block">Limite de Ficheiros HOT:</span>
                <span className="font-mono text-slate-200">500</span>
              </div>
              <div>
                <span className="text-slate-400 block">Limite de Símbolos HOT:</span>
                <span className="font-mono text-slate-200">5,000</span>
              </div>
              <div>
                <span className="text-slate-400 block">Limite de RAM Global:</span>
                <span className="font-mono text-slate-200">256 MB</span>
              </div>
              <div>
                <span className="text-slate-400 block">Evicções Realizadas:</span>
                <span className="font-mono text-emerald-400">0 (Dentro do Budget)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab 3: Targeted Subgraph */}
      {activeSubTab === 'subgraph' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-3 bg-slate-900/60 rounded-lg border border-slate-800">
            <Search className="h-4 w-4 text-cyan-400" />
            <input
              type="text"
              value={searchSymbol}
              onChange={(e) => setSearchSymbol(e.target.value)}
              placeholder="Identificador de símbolo raiz..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={() => {
                setIsExtracting(true);
                setTimeout(() => setIsExtracting(false), 300);
              }}
              className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold transition-all shadow-sm"
            >
              {isExtracting ? 'Extraindo...' : 'Extrair Subgrafo Focado'}
            </button>
          </div>

          <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Subgrafo Resultante: <span className="font-mono text-cyan-400">{searchSymbol}</span>
              </h4>
              <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/60">
                Latência de Extração: 0.18 ms
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs mb-4">
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Consumidores Diretos O(1):</span>
                <ul className="list-disc list-inside font-mono text-cyan-300 space-y-0.5">
                  <li>sym_fe_checkout_btn</li>
                  <li>sym_worker_receipt_job</li>
                </ul>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Contratos Impactados:</span>
                <ul className="list-disc list-inside font-mono text-purple-300 space-y-0.5">
                  <li>contract_billing_v2</li>
                  <li>contract_auth_v1</li>
                </ul>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Cenários de Browser QA:</span>
                <ul className="list-disc list-inside font-mono text-emerald-300 space-y-0.5">
                  <li>qa_checkout_payment_flow</li>
                  <li>qa_receipt_modal_render</li>
                </ul>
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 rounded border border-slate-800 text-[11px] text-slate-400">
              <span className="font-semibold text-slate-300">Relação Causal Extraída:</span>
              <p className="mt-1 font-mono text-slate-300">
                backend/checkout.py (sym_api_checkout) → shared/billing.json (contract_billing_v2) → frontend/CheckoutBtn.tsx (sym_fe_checkout_btn) → Edge Browser QA
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab 4: Reverse Indexes */}
      {activeSubTab === 'indexes' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Símbolos Indexados', count: '8,130', rev: 88 },
              { label: 'Ficheiros Mapeados', count: '1,104', rev: 42 },
              { label: 'Contratos Registados', count: '48', rev: 54 },
              { label: 'Dependências Globais', count: '14,250', rev: 92 },
            ].map((idx, i) => (
              <div key={i} className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                <span className="text-[11px] text-slate-400 block">{idx.label}</span>
                <span className="text-lg font-bold font-mono text-white">{idx.count}</span>
                <span className="text-[10px] text-cyan-400 block mt-0.5">Revisão: r{idx.rev}</span>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-2">
              Demonstração de Consulta Reversa O(1)
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="pb-2">Origem</th>
                    <th className="pb-2">Índice Reverso</th>
                    <th className="pb-2">Alvos Resolvidos</th>
                    <th className="pb-2">Complexidade</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
                  <tr>
                    <td className="py-2 text-cyan-300">sym_api_checkout</td>
                    <td className="py-2 text-slate-400">symbol → consumers</td>
                    <td className="py-2">sym_fe_checkout_btn, sym_worker_job</td>
                    <td className="py-2 text-emerald-400">O(1) Hash Map</td>
                  </tr>
                  <tr>
                    <td className="py-2 text-cyan-300">backend/checkout.py</td>
                    <td className="py-2 text-slate-400">file → symbols</td>
                    <td className="py-2">sym_api_checkout, sym_validate_card</td>
                    <td className="py-2 text-emerald-400">O(1) Hash Map</td>
                  </tr>
                  <tr>
                    <td className="py-2 text-cyan-300">contract_billing_v2</td>
                    <td className="py-2 text-slate-400">contract → consumers</td>
                    <td className="py-2">frontend, workers, analytics</td>
                    <td className="py-2 text-emerald-400">O(1) Hash Map</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab 5: Change Planning */}
      {activeSubTab === 'planning' && (
        <div className="space-y-4">
          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-2">
            <label className="text-xs font-bold text-slate-300">Objetivo da Alteração:</label>
            <input
              type="text"
              value={changeObjective}
              onChange={(e) => setChangeObjective(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                ChangePlan Gerado: <span className="font-mono text-cyan-400">plan_8f21bc90</span>
              </h4>
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                BLAST RADIUS: CROSS_SERVICE
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Serviços Afetados:</span>
                <div className="flex flex-wrap gap-1">
                  <span className="px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 text-[10px]">backend</span>
                  <span className="px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300 text-[10px]">shared</span>
                  <span className="px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-300 text-[10px]">frontend</span>
                </div>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Testes Obrigatórios:</span>
                <span className="font-mono text-slate-300 text-[11px]">
                  test_service_backend, test_service_frontend, test_contract_conformance
                </span>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                <span className="text-slate-400 block mb-1">Validação de Interface (Browser):</span>
                <span className="font-mono text-cyan-300 text-[11px]">
                  qa_checkout_payment_flow (Edge Headless)
                </span>
              </div>
            </div>

            <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
              <span className="text-xs font-bold text-slate-300 block mb-1">
                Sequência de Execução Causal:
              </span>
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                <span className="text-blue-400">1. Backend API</span>
                <ArrowRight className="h-3 w-3" />
                <span className="text-purple-400">2. Contract Evolution</span>
                <ArrowRight className="h-3 w-3" />
                <span className="text-emerald-400">3. Frontend UI</span>
                <ArrowRight className="h-3 w-3" />
                <span className="text-amber-400">4. Worker Tasks</span>
                <ArrowRight className="h-3 w-3" />
                <span className="text-cyan-400">5. Browser QA</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-tab 6: Snapshots & Security */}
      {activeSubTab === 'snapshots' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 bg-slate-900/60 rounded-lg border border-slate-800">
            <div>
              <h4 className="text-xs font-bold text-slate-200">Snapshots Incrementais de Repositório</h4>
              <p className="text-[11px] text-slate-400">
                Permite reversão instantânea de estado e restauração sem reconstrução do grafo global.
              </p>
            </div>
            <button
              onClick={() => setSnapshotCreated(true)}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold transition-all shadow-sm"
            >
              Criar Snapshot Incremental
            </button>
          </div>

          {snapshotCreated && (
            <div className="p-3 bg-emerald-950/40 border border-emerald-500/40 rounded-lg text-xs text-emerald-300 flex items-center justify-between">
              <span>Snapshot snap_b921ef44 criado com sucesso! Hash: d892a011ef932188</span>
              <span className="text-[10px] text-slate-400">Timestamp: há poucos segundos</span>
            </div>
          )}

          <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800 space-y-3">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Garantias do Security Sentinel (Sovereign Authority)
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800 flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-slate-200 block">Validação Criptográfica SHA-256</span>
                  <span className="text-slate-400 text-[11px]">
                    Cada shard, contrato e ficheiro tem integridade validada; qualquer divergência gera bloqueio imediato.
                  </span>
                </div>
              </div>
              <div className="p-3 bg-slate-950/60 rounded border border-slate-800 flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-slate-200 block">Enforcement de Invariantes Económicos</span>
                  <span className="text-slate-400 text-[11px]">
                    Alterações em contratos de pagamento/billing nunca podem ser mascaradas como mudanças LOCAL.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
