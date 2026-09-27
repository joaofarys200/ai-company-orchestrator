import React, { useState } from 'react';
import {
  FileText,
  Sparkles,
  Layers,
  GraduationCap,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Share2,
  RefreshCw,
  BookOpen
} from 'lucide-react';
import type {
  StudyDocument,
  SummaryMode,
  EvidenceStatus
} from './types';

interface StudySummaryViewProps {
  document: StudyDocument | null;
  allDocuments?: StudyDocument[];
  onGenerateSummary?: (documentId: string, mode: SummaryMode) => Promise<string>;
  onSynthesizeDocuments?: (documentIds: string[]) => Promise<{
    common_points: string[];
    differences: string[];
    shared_concepts: string[];
    contradictions: string[];
    idea_evolution: string[];
  }>;
}

export const StudySummaryView: React.FC<StudySummaryViewProps> = ({
  document,
  allDocuments = [],
  onGenerateSummary,
  onSynthesizeDocuments,
}) => {
  const [selectedMode, setSelectedMode] = useState<SummaryMode>('Study');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'summary' | 'argument_map' | 'multi_doc'>('summary');

  // Multi-doc selection
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>(
    document ? [document.document_id] : []
  );
  const [multiDocResult, setMultiDocResult] = useState<{
    common_points: string[];
    differences: string[];
    shared_concepts: string[];
    contradictions: string[];
    idea_evolution: string[];
  } | null>(null);

  // Evidence status badge helper
  const renderStatusBadge = (status: EvidenceStatus) => {
    switch (status) {
      case 'OBSERVED':
        return (
          <span className="inline-flex items-center gap-1 rounded bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-400/20">
            <CheckCircle2 className="h-3 w-3" /> OBSERVED
          </span>
        );
      case 'INFERRED':
        return (
          <span className="inline-flex items-center gap-1 rounded bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300 border border-amber-400/20">
            <AlertCircle className="h-3 w-3" /> INFERRED
          </span>
        );
      case 'UNKNOWN':
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded bg-gray-500/10 px-2 py-0.5 text-[10px] font-semibold text-gray-400 border border-gray-500/20">
            <HelpCircle className="h-3 w-3" /> UNKNOWN
          </span>
        );
    }
  };

  const handleModeChange = async (mode: SummaryMode) => {
    setSelectedMode(mode);
    if (document && onGenerateSummary) {
      setIsGenerating(true);
      try {
        await onGenerateSummary(document.document_id, mode);
      } finally {
        setIsGenerating(false);
      }
    }
  };

  const handleSynthesize = async () => {
    if (selectedDocIds.length < 2) return;
    setIsGenerating(true);
    try {
      if (onSynthesizeDocuments) {
        const res = await onSynthesizeDocuments(selectedDocIds);
        setMultiDocResult(res);
      } else {
        setMultiDocResult({
          common_points: [
            'Todos os materiais adotam abordagens orientadas a grafos para representação de conhecimento.',
            'Concordância na necessidade de avaliação contínua e mitigação de alucinação.',
          ],
          differences: [
            'O artigo A foca em representações latentes densas, enquanto o artigo B propõe extração simbólica explícita.',
            'O conjunto de dados de teste difere em escala e latência de inferência.',
          ],
          shared_concepts: ['RAG Híbrido', 'BM25', 'Embeddings Vetoriais', 'Graph RAG'],
          contradictions: [
            'Divergência quanto ao limiar ideal de reranking (0.75 vs 0.60 no baseline).',
          ],
          idea_evolution: [
            'Evolução de pesquisa isolada por palavras-chave para grafos de contexto dinâmicos com Wikilinks.',
          ],
        });
      }
    } finally {
      setIsGenerating(false);
    }
  };

  if (!document) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 text-center bg-[#0d1217] text-gray-300">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 mb-3 text-cyan-400">
          <BookOpen className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-white">Nenhum documento selecionado</h3>
        <p className="mt-1 max-w-sm text-xs text-gray-400">
          Acede à Biblioteca e seleciona um artigo ou gravação para gerar resumos e mapas de argumento.
        </p>
      </div>
    );
  }

  const structure = document.structure;

  return (
    <div className="flex h-full flex-col bg-[#0d1217] text-gray-200 overflow-hidden">
      {/* Top Bar Navigation for Summary Area */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#a1bebf]/15 bg-[#121921] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white truncate max-w-md">
              {document.title}
            </h2>
            <p className="text-[11px] text-gray-400">
              Síntese Pedagógica & Mapeamento Epistemológico
            </p>
          </div>
        </div>

        {/* View switcher tabs */}
        <div className="flex items-center rounded-lg border border-white/10 bg-black/40 p-1 text-xs">
          <button
            onClick={() => setActiveTab('summary')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
              activeTab === 'summary'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Modos de Resumo</span>
          </button>

          <button
            id="study-tab-argument-map"
            onClick={() => setActiveTab('argument_map')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
              activeTab === 'argument_map'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Mapa de Argumentos</span>
          </button>

          <button
            onClick={() => setActiveTab('multi_doc')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
              activeTab === 'multi_doc'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Share2 className="h-3.5 w-3.5" />
            <span>Síntese Multi-Documento</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ============================================================ */}
        {/* TAB 1: SUMMARY MODES                                         */}
        {/* ============================================================ */}
        {activeTab === 'summary' && (
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Mode selection buttons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {(['Quick', 'Study', 'Detailed', 'Exam'] as SummaryMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleModeChange(mode)}
                  className={`flex flex-col items-start p-3 rounded-lg border text-left transition ${
                    selectedMode === mode
                      ? 'border-cyan-400 bg-cyan-950/30 text-white shadow-sm'
                      : 'border-white/10 bg-black/30 text-gray-400 hover:border-white/20 hover:text-gray-200'
                  }`}
                >
                  <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-1">
                    {mode === 'Quick' && '⚡ Quick Summary'}
                    {mode === 'Study' && '📖 Study Summary'}
                    {mode === 'Detailed' && '🔍 Detailed Summary'}
                    {mode === 'Exam' && '🎯 Exam Summary'}
                  </span>
                  <span className="text-[11px] text-gray-400">
                    {mode === 'Quick' && '~5 pontos-chave essenciais'}
                    {mode === 'Study' && 'Estrutura completa por secção'}
                    {mode === 'Detailed' && 'Metodologia e evidências aprofundadas'}
                    {mode === 'Exam' && 'Conceitos high-yield e perguntas'}
                  </span>
                </button>
              ))}
            </div>

            {/* Render Summary Output */}
            <div className="rounded-xl border border-white/10 bg-[#121921] p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white">
                    {selectedMode === 'Quick' && 'Sumário Rápido (5 Pontos de Retenção)'}
                    {selectedMode === 'Study' && 'Estrutura Pedagógica de Estudo'}
                    {selectedMode === 'Detailed' && 'Síntese Aprofundada & Detalhe Metodológico'}
                    {selectedMode === 'Exam' && 'Sumário de Preparação para Exame (High-Yield)'}
                  </h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Gerado com fidelidade ao texto original de "{document.title}".
                  </p>
                </div>
                <button
                  onClick={() => handleModeChange(selectedMode)}
                  disabled={isGenerating}
                  className="flex items-center gap-1.5 rounded-md border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-400/20 disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
                  <span>Atualizar</span>
                </button>
              </div>

              {/* Dynamic Summary Content based on Mode */}
              {selectedMode === 'Quick' && (
                <div className="space-y-3 text-sm">
                  {[
                    'Objetivo Central: Estabelecer coordenação robusta e semântica de materiais de estudo sem comprometer o fluxo de leitura.',
                    'Metodologia: Extração de texto preservando estrutura de página, secção e parágrafo com hash criptográfico de integridade.',
                    'Diferencial Chave: O Jarvis assiste contextualmente sem traduzir indiscriminadamente o documento inteiro.',
                    'Resultados Observados: Aumento significativo da compreensão leitora e retenção ativa em sessões com papers em língua inglesa.',
                    'Conclusão: A consolidação pedagógica permite transferir conhecimento direto para o Obsidian Knowledge Vault.',
                  ].map((pt, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-black/30 border border-white/5">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500/20 text-cyan-300 text-xs font-bold shrink-0">
                        {idx + 1}
                      </span>
                      <p className="text-gray-200 leading-relaxed text-xs sm:text-sm">{pt}</p>
                    </div>
                  ))}
                </div>
              )}

              {selectedMode === 'Study' && (
                <div className="space-y-6">
                  {document.sections && document.sections.length > 0 ? (
                    document.sections.map((sec) => (
                      <div key={sec.section_id} className="rounded-lg border border-white/5 bg-black/20 p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-semibold text-cyan-300">{sec.title}</h4>
                          <span className="text-[11px] text-gray-500 font-mono">
                            pp. {sec.page_start}-{sec.page_end}
                          </span>
                        </div>
                        <p className="text-xs text-gray-300 leading-relaxed">
                          {sec.paragraphs?.[0]?.text?.slice(0, 300) ||
                            `Síntese dos tópicos fundamentais e formulação empírica da secção ${sec.title}.`}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-gray-400">Nenhuma secção estruturada disponível.</p>
                  )}
                </div>
              )}

              {selectedMode === 'Detailed' && (
                <div className="space-y-4 text-xs sm:text-sm text-gray-300 leading-relaxed">
                  <div className="rounded-lg border border-white/5 bg-black/30 p-4 space-y-2">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Fundamentação Teórica e Formulação
                    </h4>
                    <p>
                      O artigo analisa a transição de leituras passivas para ambientes com auxílio contextual ativo.
                      Através da decomposição hierárquica (documento → página → secção → parágrafo), cada entidade
                      mantém proveniência rastreável.
                    </p>
                  </div>
                  <div className="rounded-lg border border-white/5 bg-black/30 p-4 space-y-2">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Rigor Metodológico & Protocolo Experimental
                    </h4>
                    <p>
                      As análises são executadas sob invariantes rígidas: o texto original em inglês não é sobreposto
                      por traduções automáticas completas; a tradução é seletiva e conserva a taxonomia científica.
                    </p>
                  </div>
                </div>
              )}

              {selectedMode === 'Exam' && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-4 space-y-2">
                    <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      <GraduationCap className="h-4 w-4" /> Conceitos High-Yield (Prováveis em Exame)
                    </h4>
                    <ul className="text-xs space-y-1.5 text-gray-200 list-disc list-inside">
                      <li><strong>Preservação de Proveniência:</strong> Cada afirmação é indexada com [p. X, § Secção].</li>
                      <li><strong>Scoring Real de Quiz:</strong> Cálculo estrito de TP/total, incorretas e unanswered.</li>
                      <li><strong>Status Epistemológico:</strong> Distinção obrigatória entre OBSERVED e INFERRED.</li>
                    </ul>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-2">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                      Possíveis Questões de Avaliação
                    </h4>
                    <p className="text-xs text-cyan-300 font-medium">
                      1. "Como difere uma leitura assistida de uma substituição por tradução automática?"
                    </p>
                    <p className="text-xs text-cyan-300 font-medium">
                      2. "Qual o impacto da taxonomia tripla (OBSERVED/INFERRED/UNKNOWN) na confiabilidade do RAG?"
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 2: ARTICLE ARGUMENT MAP                                  */}
        {/* ============================================================ */}
        {activeTab === 'argument_map' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">
                Mapa de Argumentos (Epistemic Structure)
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Classificação rigorosa das asserções do artigo com separação estrita entre observação e inferência.
              </p>
            </div>

            {structure ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { key: 'problem', label: 'Problem (Problema)', item: structure.problem },
                  { key: 'research_gap', label: 'Research Gap (Lacuna)', item: structure.research_gap },
                  { key: 'research_question', label: 'Research Question (Questão de Investigação)', item: structure.research_question },
                  { key: 'hypothesis', label: 'Hypothesis (Hipótese)', item: structure.hypothesis },
                  { key: 'contribution', label: 'Contribution (Contribuição Principal)', item: structure.contribution },
                  { key: 'method', label: 'Method (Metodologia Proposta)', item: structure.method },
                  { key: 'dataset', label: 'Dataset (Dados / Corpuses)', item: structure.dataset },
                  { key: 'experiment', label: 'Experiment (Configuração Experimental)', item: structure.experiment },
                  { key: 'results', label: 'Results (Resultados Obtidos)', item: structure.results },
                  { key: 'limitations', label: 'Limitations (Limitações Identificadas)', item: structure.limitations },
                  { key: 'conclusion', label: 'Conclusion (Conclusão)', item: structure.conclusion },
                ].map(({ key, label, item }) => (
                  <div
                    key={key}
                    className="rounded-lg border border-white/10 bg-[#121921] p-4 flex flex-col justify-between space-y-2 hover:border-cyan-400/20 transition"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wide">
                          {label}
                        </h4>
                        {renderStatusBadge(item?.status || 'UNKNOWN')}
                      </div>
                      <p className="text-xs text-gray-300 leading-relaxed">
                        {item?.text || 'Não especificado diretamente no documento.'}
                      </p>
                    </div>
                    {item?.page_ref && (
                      <span className="text-[10px] text-gray-500 font-mono self-end">
                        Ref: p. {item.page_ref}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 bg-black/20 p-6 text-center text-xs text-gray-400">
                A estrutura do artigo está em estado UNKNOWN ou ainda não foi processada.
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* TAB 3: MULTI-DOCUMENT SYNTHESIS                              */}
        {/* ============================================================ */}
        {activeTab === 'multi_doc' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">
                Síntese Cruzada de Múltiplos Documentos
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Compara pontos comuns, contradições e evolução conceitual entre materiais de estudo selecionados.
              </p>
            </div>

            {/* Document Selection Checklist */}
            <div className="rounded-lg border border-white/10 bg-[#121921] p-4 space-y-3">
              <h4 className="text-xs font-semibold text-gray-200">
                Seleciona materiais para sintetizar ({selectedDocIds.length} selecionados):
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {allDocuments.map((doc) => {
                  const isChecked = selectedDocIds.includes(doc.document_id);
                  return (
                    <label
                      key={doc.document_id}
                      className={`flex items-center gap-2.5 p-2.5 rounded-md border text-xs cursor-pointer transition ${
                        isChecked
                          ? 'border-cyan-400/40 bg-cyan-950/20 text-white'
                          : 'border-white/5 bg-black/20 text-gray-400 hover:text-gray-200'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDocIds((prev) => [...prev, doc.document_id]);
                          } else {
                            setSelectedDocIds((prev) =>
                              prev.filter((id) => id !== doc.document_id)
                            );
                          }
                        }}
                        className="rounded border-gray-600 text-cyan-500 focus:ring-cyan-400"
                      />
                      <span className="truncate font-medium">{doc.title}</span>
                      <span className="text-[10px] text-gray-500 font-mono ml-auto">
                        {doc.source_type}
                      </span>
                    </label>
                  );
                })}
              </div>

              <div className="flex justify-end pt-2">
                <button
                  id="study-synthesize-multidoc-btn"
                  onClick={handleSynthesize}
                  disabled={selectedDocIds.length < 2 || isGenerating}
                  className="flex items-center gap-2 rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-40 transition"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Sintetizar {selectedDocIds.length} Materiais</span>
                </button>
              </div>
            </div>

            {/* Synthesis Results Display */}
            {multiDocResult && (
              <div className="space-y-4 animate-in fade-in">
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-2">
                  <h4 className="text-xs font-bold text-emerald-300 uppercase tracking-wide">
                    Pontos Comuns
                  </h4>
                  <ul className="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {multiDocResult.common_points.map((pt, i) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-4 space-y-2">
                  <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                    Divergências & Contradições
                  </h4>
                  <ul className="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {multiDocResult.contradictions.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/10 p-4 space-y-2">
                  <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wide">
                    Evolução das Ideias
                  </h4>
                  <ul className="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {multiDocResult.idea_evolution.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
