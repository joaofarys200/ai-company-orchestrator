import React, { useState, useMemo } from 'react';
import { Play } from 'lucide-react';

export const MissionAppPreviewPanel: React.FC = () => {
  const [expenses, setExpenses] = useState<
    Array<{ id: number; desc: string; amount: number; cat: string }>
  >([
    { id: 1, desc: 'Almoço de Equipa', amount: 42.5, cat: 'Alimentação' },
    { id: 2, desc: 'Passe Navegante Metropolitano', amount: 40.0, cat: 'Transporte' },
    { id: 3, desc: 'Assinatura Técnica Cloud', amount: 19.99, cat: 'Educação' },
  ]);
  const [newDesc, setNewDesc] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [newCat, setNewCat] = useState('Alimentação');
  const [selectedCatFilter, setSelectedCatFilter] = useState('TODAS');

  const filteredExpenses = useMemo(() => {
    if (selectedCatFilter === 'TODAS') return expenses;
    return expenses.filter((e) => e.cat === selectedCatFilter);
  }, [expenses, selectedCatFilter]);

  const totalExpenseSum = useMemo(() => {
    return filteredExpenses.reduce((acc, curr) => acc + curr.amount, 0);
  }, [filteredExpenses]);

  const handleAddExpense = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDesc.trim() || !newAmount) return;
    const val = parseFloat(newAmount);
    if (isNaN(val) || val <= 0) return;

    setExpenses((prev) => [
      ...prev,
      {
        id: Date.now(),
        desc: newDesc.trim(),
        amount: val,
        cat: newCat,
      },
    ]);
    setNewDesc('');
    setNewAmount('');
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-cyan-500/30 bg-[#0e191d]/90 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Play className="h-5 w-5 text-cyan-400" />
              Aplicação Gerada Pelo JARVIS: Gestor de Despesas Pessoais
            </h3>
            <p className="text-xs text-gray-400">
              Validação em tempo real: funcionalidade imediata, cálculo de totais e filtros.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300">
              ONLINE & PRONTO
            </span>
          </div>
        </div>

        {/* Expense App GUI */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Add Expense Form */}
          <div className="rounded-lg border border-white/10 bg-black/40 p-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-300">Nova Despesa</h4>
            <form onSubmit={handleAddExpense} className="mt-3 space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-gray-400">Descrição:</label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Ex: Café, Livro..."
                  className="mt-1 w-full rounded border border-white/10 bg-black/60 px-2.5 py-1.5 text-xs text-white placeholder-gray-600 focus:border-cyan-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-gray-400">Valor (€):</label>
                <input
                  type="number"
                  step="0.01"
                  value={newAmount}
                  onChange={(e) => setNewAmount(e.target.value)}
                  placeholder="0.00"
                  className="mt-1 w-full rounded border border-white/10 bg-black/60 px-2.5 py-1.5 text-xs text-white placeholder-gray-600 focus:border-cyan-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-gray-400">Categoria:</label>
                <select
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                  className="mt-1 w-full rounded border border-white/10 bg-black/60 px-2.5 py-1.5 text-xs text-white focus:border-cyan-400 focus:outline-none"
                >
                  <option value="Alimentação">Alimentação</option>
                  <option value="Transporte">Transporte</option>
                  <option value="Educação">Educação</option>
                  <option value="Lazer">Lazer</option>
                  <option value="Saúde">Saúde</option>
                </select>
              </div>
              <button
                type="submit"
                className="w-full rounded bg-cyan-600 px-3 py-2 text-xs font-bold text-white transition-all hover:bg-cyan-500"
              >
                + Adicionar Despesa
              </button>
            </form>
          </div>

          {/* Expenses List & Live Totals */}
          <div className="space-y-4 lg:col-span-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Filtrar Categoria:</span>
                {['TODAS', 'Alimentação', 'Transporte', 'Educação'].map((c) => (
                  <button
                    key={c}
                    onClick={() => setSelectedCatFilter(c)}
                    className={`rounded px-2.5 py-1 text-xs font-semibold ${
                      selectedCatFilter === c
                        ? 'bg-cyan-500/30 text-cyan-200 border border-cyan-400/40'
                        : 'bg-white/5 text-gray-400 hover:bg-white/10'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <div className="rounded-md border border-cyan-400/30 bg-cyan-950/40 px-3 py-1.5 text-right">
                <span className="text-[10px] uppercase text-gray-400">Total Acumulado</span>
                <p className="font-mono text-base font-bold text-cyan-200">
                  {totalExpenseSum.toFixed(2)} €
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {filteredExpenses.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between rounded-lg border border-white/8 bg-black/40 px-4 py-2.5 text-xs transition-all hover:border-cyan-500/20"
                >
                  <div className="flex items-center gap-3">
                    <span className="rounded bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-300">
                      {item.cat}
                    </span>
                    <span className="font-semibold text-white">{item.desc}</span>
                  </div>
                  <span className="font-mono font-bold text-emerald-300">
                    {item.amount.toFixed(2)} €
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
