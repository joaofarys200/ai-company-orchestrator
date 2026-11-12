"""
Regressão Stage 5 — Segmentação Académica (Abreviaturas) & Truncagem em Fronteira Semântica.
"""

from services.study_ai_engine import (
    build_extractive_study_bundle,
    rank_salient_sentences,
    split_clean_sentences,
    truncate_at_boundary,
)


def test_split_clean_sentences_preserves_academic_abbreviations():
    sample = (
        "Unidade Curricular: Gestão de Projetos (Mestrado 2.º Ano) | Docente: Prof. João Varajão (DSI — Univ. Minho). "
        "Referencial principal: ISO 21500 e Tab. 16 para estimativa de recursos (cf. Cap. 3 e Fig. 2). "
        "Curva S do EVM: comparação entre PV, AC e EV na Status Date e projeção futura do Desvio de Custo (EAC vs. BAC) ao longo de 2.5 meses."
    )
    sents = split_clean_sentences(sample)
    assert len(sents) == 3
    assert "Docente: Prof. João Varajão (DSI — Univ. Minho)." in sents[0]
    assert not any(s.strip().endswith("Prof.") for s in sents)
    assert not any(s.strip().endswith("vs.") for s in sents)
    assert "EAC vs. BAC" in sents[2]
    assert "2.5 meses." in sents[2]


def test_truncate_at_boundary_never_leaves_broken_parentheses_or_abbreviations():
    long_text = (
        "O EVM cruza em simultâneo Âmbito, Tempo e Custo com base em dados financeiros objetivos "
        "(evitando a ilusão de gastar menos apenas porque se trabalhou ou entregou menos). "
        "Curva S do EVM: comparação entre PV, AC e EV na Status Date e projeção futura do Desvio de Custo (EAC vs. BAC)."
    )
    out = truncate_at_boundary(long_text, max_len=190)
    assert len(out) <= 191
    assert not out.endswith("vs.")
    assert not out.endswith("Prof.")
    assert out.count("(") <= out.count(")")


def test_extractive_bundle_no_abrupt_docente_prof_or_eac_vs_cuts():
    text = (
        "Unidade Curricular: Gestão de Projetos (Mestrado 2.º Ano) | Docente: Prof. João Varajão (DSI — Univ. Minho).\n\n"
        "Conceito, Curva S do EVM, Métricas Base, Variâncias, Índices e Previsão (ISO 21508:2018).\n"
        "O EVM cruza em simultâneo Âmbito, Tempo e Custo com base em dados financeiros objetivos. "
        "Na introdução, o docente menciona ETC e TCPI como métricas complementares de controlo. "
        "Curva S do EVM: comparação entre PV, AC e EV na Status Date e projeção futura do Desvio de Custo (EAC vs. BAC)."
    )
    sections = [
        {
            "section_id": "sec_1",
            "title": "Início do documento",
            "page_start": 1,
            "page_end": 1,
            "paragraphs": [
                {"text": "Unidade Curricular: Gestão de Projetos (Mestrado 2.º Ano) | Docente: Prof. João Varajão (DSI — Univ. Minho)."}
            ],
        },
        {
            "section_id": "sec_2",
            "title": "Curva S do EVM (ISO 21508:2018)",
            "page_start": 11,
            "page_end": 11,
            "paragraphs": [
                {
                    "text": (
                        "O EVM cruza em simultâneo Âmbito, Tempo e Custo com base em dados financeiros objetivos. "
                        "Curva S do EVM: comparação entre PV, AC e EV na Status Date e projeção futura do Desvio de Custo (EAC vs. BAC)."
                    )
                }
            ],
        },
    ]

    bundle = build_extractive_study_bundle(
        title="Gestão de Projetos",
        subject="Gestão",
        source_type="PDF",
        text=text,
        sections=sections,
        document_id="doc_test_seg",
    )

    all_texts = list(bundle["summaries"]["quick"])
    all_texts.extend(sec["summary"] for sec in bundle["summaries"]["study"])
    all_texts.extend(blk["text"] for blk in bundle["summaries"]["detailed"])
    all_texts.extend(cue["idea"] for cue in bundle["cornell_notes"]["cue_column"])

    for t in all_texts:
        assert not t.strip().endswith("Prof."), f"Quebra abrupta em abreviatura: {t!r}"
        assert not t.strip().endswith("(EAC vs."), f"Quebra abrupta em EAC vs.: {t!r}"
        assert t.count("(") <= t.count(")"), f"Parêntese por fechar: {t!r}"

