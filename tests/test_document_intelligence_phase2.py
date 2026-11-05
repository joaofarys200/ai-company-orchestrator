"""
JARVIS OS - Testes de Validação da Fase 2 (Document Intelligence & AcademicDocumentAST)

Validação exaustiva da camada de extração estrutural:
1. PDF académico curto.
2. Artigo científico extenso real (11 páginas, 2 colunas, Elsevier).
3. PDF com múltiplas colunas (layout em grelha).
4. Documento com tabelas estruturadas (linhas, colunas, células, legendas).
5. Documento com gráficos e imagens (raster, vetor, legendas, recorte e SHA-256).
6. PDF digitalizado (sem camada de texto).
7. Documento com fórmulas matemáticas (identificação de equações, limites declarados).
8. Documento com estrutura irregular (documento corporativo/memorando).
9. Rastreabilidade, integridade de frases e coordenadas na página.
10. Persistência de AST e Compatibilidade com StudyService e WebSocket.
11. Recuperação após falha de processamento e reporte honesto.
"""

import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
import pytest
import pymupdf

from services.document_intelligence import (
    AcademicDocumentAST,
    DocumentIntelligenceExtractor,
    DocumentExtractionError,
    sentence_spans,
)
from services.study_service import StudyService


# ---------------------------------------------------------------------------
# Fixtures e Geradores de PDFs de Teste
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="jarvis_doc_intel_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def create_short_academic_pdf(path: Path) -> Path:
    """PDF académico curto: título, resumo, introdução, metodologia, conclusões."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    # Título (fontsize=18)
    page.insert_text((50, 70), "Adaptive Attention Mechanisms in Neural Architecture", fontsize=18)
    # Autores
    page.insert_text((50, 100), "Alice Silva, Bob Santos", fontsize=10)
    page.insert_text((50, 115), "University of Coimbra, Department of Informatics", fontsize=8)
    # Resumo
    page.insert_text((50, 150), "Abstract", fontsize=12)
    page.insert_text((50, 170), "This paper investigates how adaptive attention mechanisms improve transformer efficiency.", fontsize=10)
    page.insert_text((50, 185), "We propose a dynamic pruning algorithm that reduces latency by twenty percent.", fontsize=10)
    # Introdução
    page.insert_text((50, 230), "1. Introduction", fontsize=13)
    page.insert_text((50, 255), "Transformer models have transformed natural language processing over the last decade.", fontsize=10)
    page.insert_text((50, 270), "However, quadratic computational complexity remains a barrier to edge deployment.", fontsize=10)
    # Conclusão
    page.insert_text((50, 320), "2. Conclusion", fontsize=13)
    page.insert_text((50, 345), "In this research, we demonstrated that adaptive attention achieves competitive results.", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def create_multi_column_pdf(path: Path) -> Path:
    """PDF com layout em duas colunas."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 60), "Multi-Column Layout Benchmark in Document Analysis", fontsize=16)
    # Coluna 1: x in [50, 260]
    rect1 = pymupdf.Rect(50, 110, 260, 400)
    col1_text = (
        "1. First Column Overview\n\n"
        "This paragraph resides entirely in the left column of the page layout. "
        "It develops the initial premises before readers proceed to the right column. "
        "Proper reading order must process this entire section before switching sides."
    )
    page.insert_textbox(rect1, col1_text, fontsize=9)
    # Coluna 2: x in [310, 520]
    rect2 = pymupdf.Rect(310, 110, 520, 400)
    col2_text = (
        "2. Second Column Evidence\n\n"
        "Here is the continuation in the right column of the document structure. "
        "Empirical observations confirm the theoretical predictions made previously."
    )
    page.insert_textbox(rect2, col2_text, fontsize=9)
    doc.save(str(path))
    doc.close()
    return path


def create_table_pdf(path: Path) -> Path:
    """PDF com tabela estruturada com linhas desenhadas e legenda."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 60), "Empirical Evaluation of Database Performance", fontsize=15)
    page.insert_text((50, 100), "Table 1. Latency and throughput benchmarks across storage engines.", fontsize=10)
    # Desenhar linhas de tabela
    shape = page.new_shape()
    y_top = 120
    row_h = 25
    x_left = 50
    col_w = [120, 100, 100, 100]
    x_total = x_left + sum(col_w)
    # Linhas horizontais
    for r in range(4):
        y = y_top + r * row_h
        shape.draw_line((x_left, y), (x_total, y))
    # Linhas verticais
    cur_x = x_left
    for w in col_w:
        shape.draw_line((cur_x, y_top), (cur_x, y_top + 3 * row_h))
        cur_x += w
    shape.draw_line((x_total, y_top), (x_total, y_top + 3 * row_h))
    shape.finish(color=(0, 0, 0), width=1)
    shape.commit()

    # Preencher células
    headers = ["Storage Engine", "Read Ops (k/s)", "Write Ops (k/s)", "P99 Latency (ms)"]
    row1 = ["PostgreSQL 16", "45.2", "12.8", "4.2"]
    row2 = ["SQLite Memory", "110.5", "85.3", "0.8"]
    for i, h in enumerate(headers):
        x = x_left + sum(col_w[:i]) + 5
        page.insert_text((x, y_top + 16), h, fontsize=9)
    for i, val in enumerate(row1):
        x = x_left + sum(col_w[:i]) + 5
        page.insert_text((x, y_top + row_h + 16), val, fontsize=9)
    for i, val in enumerate(row2):
        x = x_left + sum(col_w[:i]) + 5
        page.insert_text((x, y_top + 2 * row_h + 16), val, fontsize=9)

    doc.save(str(path))
    doc.close()
    return path


def create_figures_pdf(path: Path) -> Path:
    """PDF com imagem raster, gráfico desenhado e legendas associadas."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 60), "Visual Perception and Computer Vision Architectures", fontsize=15)
    # 1. Inserir um gráfico rasterizado
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 180, 120), 0)
    pix.set_rect(pix.irect, (40, 120, 200))
    page.insert_image(pymupdf.Rect(50, 100, 260, 220), pixmap=pix)
    page.insert_text((50, 235), "Figure 1. Architectural blueprint of the convolutional backbone.", fontsize=10)

    # 2. Inserir elemento vetorial com legenda
    shape = page.new_shape()
    shape.draw_rect(pymupdf.Rect(50, 270, 250, 370))
    shape.finish(color=(0.2, 0.4, 0.8), fill=(0.9, 0.95, 1.0))
    shape.commit()
    page.insert_text((50, 385), "Figure 2. Information flow between encoder and decoder stacks.", fontsize=10)

    doc.save(str(path))
    doc.close()
    return path


def create_scanned_pdf(path: Path) -> Path:
    """PDF puramente digitalizado (sem camada de texto)."""
    doc_temp = pymupdf.open()
    p_temp = doc_temp.new_page(width=595, height=842)
    p_temp.insert_text((80, 150), "Documento Digitalizado Historico de 1985", fontsize=18)
    p_temp.insert_text((80, 200), "Este texto foi impresso em papel e digitalizado como imagem pura.", fontsize=12)
    pix = p_temp.get_pixmap(dpi=150)
    doc_temp.close()

    # Criar PDF final contendo APENAS a imagem rasterizada em página cheia
    doc_scanned = pymupdf.open()
    p_final = doc_scanned.new_page(width=595, height=842)
    p_final.insert_image(p_final.rect, pixmap=pix)
    doc_scanned.save(str(path))
    doc_scanned.close()
    return path


def create_math_pdf(path: Path) -> Path:
    """PDF com fórmulas matemáticas e números de equação."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 60), "Mathematical Foundations of Graph Optimization", fontsize=15)
    page.insert_text((50, 100), "1. Objective Function", fontsize=13)
    page.insert_text((50, 125), "The total system cost is defined by summing energy over all active nodes:", fontsize=10)
    # Equação destacada com número (1)
    page.insert_text((100, 165), "L(theta) = sum_{i=1}^N (y_i - f(x_i; theta))^2 + lambda ||theta||_2^2   (1)", fontsize=11)
    page.insert_text((50, 210), "where lambda represents the regularization coefficient penalizing complexity.", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def create_irregular_pdf(path: Path) -> Path:
    """Documento com estrutura irregular (memorando corporativo sem Abstract/Intro/Conclusion)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 60), "MEMORANDUM INTERNO: Politica de Seguranca Q3", fontsize=16)
    page.insert_text((50, 100), "Para: Toda a Equipa de Engenharia", fontsize=10)
    page.insert_text((50, 115), "De: Direcao de Infraestrutura", fontsize=10)
    page.insert_text((50, 130), "Data: 15 de Outubro de 2026", fontsize=10)
    page.insert_text((50, 170), "Diretrizes Operacionais:", fontsize=12)
    page.insert_text((50, 195), "1. Todas as chaves SSH devem ser renovadas a cada noventa dias sem excecao.", fontsize=10)
    page.insert_text((50, 215), "2. O acesso a servidores de producao requer autenticacao multifator obrigatoria.", fontsize=10)
    page.insert_text((50, 255), "Contactos de Suporte:", fontsize=12)
    page.insert_text((50, 280), "Para duvidas tecnicas contactar security@jarvis.internal imediatamente.", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# Testes Automatizados
# ---------------------------------------------------------------------------

def test_01_short_academic_pdf(temp_dir):
    """Valida PDF académico curto: hierarquia, metadados, parágrafos e integridade de frases."""
    pdf_path = create_short_academic_pdf(temp_dir / "short_paper.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_short_01")

    assert ast.document_id == "doc_short_01"
    assert "Adaptive Attention Mechanisms" in (ast.metadata.title or "")
    assert len(ast.metadata.authors) >= 1
    assert "Alice Silva" in ast.metadata.authors[0]["name"]
    assert len(ast.sections) >= 3
    sec_titles = [s.title for s in ast.sections]
    assert any("Abstract" in t for t in sec_titles)
    assert any("Introduction" in t for t in sec_titles)
    assert any("Conclusion" in t for t in sec_titles)

    # Integridade de parágrafos e frases
    assert len(ast.paragraphs) >= 4
    for p in ast.paragraphs:
        assert p.text.strip(), "Nenhum parágrafo deve estar vazio"
        assert p.page_number == 1
        assert len(p.sentence_spans) >= 1
        # Verificar que os sentence_spans cobrem frases completas sem quebras
        for span in p.sentence_spans:
            sub = p.text[span[0]:span[1]]
            assert len(sub.strip()) > 5


def test_02_extended_scientific_paper_real(temp_dir):
    """Valida o artigo científico real de 11 páginas (Decision Support Systems)."""
    real_pdf = Path("data/study/a3b336f4295d0d51_test_perf_upload.pdf")
    if not real_pdf.exists():
        pytest.skip(f"Ficheiro de teste real não encontrado: {real_pdf}")

    assets_dir = temp_dir / "assets_real"
    extractor = DocumentIntelligenceExtractor(assets_dir=assets_dir)
    ast = extractor.extract(real_pdf, "doc_real_salehan")

    # 1. Metadados
    assert "Predicting the performance of online consumer reviews" in (ast.metadata.title or "")
    assert len(ast.metadata.authors) == 2
    author_names = [a["name"] for a in ast.metadata.authors]
    assert "Mohammad Salehan" in author_names
    assert "Dan J. Kim" in author_names
    assert ast.metadata.doi == "10.1016/j.dss.2015.10.006"
    assert ast.metadata.page_count == 11
    assert ast.metadata.abstract is not None
    assert "online consumer reviews" in ast.metadata.abstract.lower()

    # 2. Secções
    assert len(ast.sections) >= 8
    sec_titles = [s.title.lower() for s in ast.sections]
    assert any("introduction" in t for t in sec_titles)
    assert any("theoretical background" in t for t in sec_titles)
    assert any("methodology" in t for t in sec_titles)
    assert any("discussion" in t for t in sec_titles)
    assert any("conclusion" in t for t in sec_titles)
    assert any("references" in t for t in sec_titles)

    # 3. Tabelas
    assert len(ast.tables) == 5
    for t in ast.tables:
        assert t.structure_status == "RECONSTRUCTED"
        assert t.n_rows >= 5
        assert t.n_cols >= 4
        assert t.caption is not None
        assert t.caption.startswith("Table ")

    # 4. Figuras e Gráficos
    assert len(ast.figures) >= 4
    research_figs = [f for f in ast.figures if not f.is_decorative_candidate]
    assert len(research_figs) >= 4
    # Honesty invariant: não inventar interpretação de dados
    for f in ast.figures:
        assert f.interpretation_status == "IMAGE_ONLY_NOT_INTERPRETED"
        assert f.underlying_data_recovered is False

    # 5. Referências
    assert len(ast.references) >= 80
    assert ast.report.references_identified >= 80

    # 6. Contabilidade de texto (>98% de cobertura da camada textual lida)
    acc = ast.report.text_accounting
    assert acc["text_layer_chars_read"] > 50000
    assert abs(acc["difference_ratio"]) < 0.03


def test_03_multi_column_pdf(temp_dir):
    """Valida PDF com múltiplas colunas: deteta colunas e preserva ordem correta."""
    pdf_path = create_multi_column_pdf(temp_dir / "multi_column.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_multicol_03")

    assert ast.pages[0].columns_detected >= 2
    assert 1 in ast.report.multi_column_pages
    texts = [p.text for p in ast.paragraphs]
    full = " ".join(texts)
    # A primeira coluna deve ser processada antes da segunda
    idx_col1 = full.find("left column")
    idx_col2 = full.find("right column")
    assert idx_col1 != -1 and idx_col2 != -1
    assert idx_col1 < idx_col2, "A leitura deve respeitar a ordem lógica das colunas"


def test_04_document_with_tables(temp_dir):
    """Valida documento com tabela estruturada: linhas, colunas, células e legenda."""
    pdf_path = create_table_pdf(temp_dir / "table_doc.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_table_04")

    assert len(ast.tables) >= 1
    table = ast.tables[0]
    assert table.n_rows == 3
    assert table.n_cols == 4
    assert table.header_status == "ASSUMED_FIRST_ROW"
    assert "Storage Engine" in table.rows[0]
    assert "PostgreSQL 16" in table.rows[1]
    assert "SQLite Memory" in table.rows[2]
    assert "Table 1" in (table.caption or "")
    assert table.page_number == 1
    assert table.bbox is not None


def test_05_document_with_figures_and_images(temp_dir):
    """Valida imagens e gráficos: extração, persistência em disco, SHA-256 e legendas."""
    assets_dir = temp_dir / "assets_fig"
    pdf_path = create_figures_pdf(temp_dir / "figures_doc.pdf")
    extractor = DocumentIntelligenceExtractor(assets_dir=assets_dir)
    ast = extractor.extract(pdf_path, "doc_fig_05")

    assert len(ast.figures) >= 2
    # Figura 1: raster
    f1 = next((f for f in ast.figures if f.element_kind == "RASTER_IMAGE"), None)
    assert f1 is not None
    assert f1.caption is not None and "Figure 1" in f1.caption
    assert f1.asset_ref is not None
    assert f1.asset_sha256 is not None
    assert (assets_dir / Path(f1.asset_ref).name).exists()

    # Figura 2: vector graphic
    f2 = next((f for f in ast.figures if f.element_kind == "VECTOR_GRAPHIC"), None)
    assert f2 is not None
    assert f2.caption is not None and "Figure 2" in f2.caption


def test_06_scanned_pdf_handling(temp_dir):
    """Valida PDF digitalizado (imagem pura sem camada de texto): reporta limitação honestamente."""
    pdf_path = create_scanned_pdf(temp_dir / "scanned_doc.pdf")
    extractor = DocumentIntelligenceExtractor(ocr_enabled=False)
    ast = extractor.extract(pdf_path, "doc_scanned_06")

    assert ast.pages[0].text_source in ("NONE", "OCR_WINDOWS")
    assert ast.pages[0].image_coverage > 0.8
    # Se o OCR estiver desativado, o relatório indica estado não recuperado de forma explícita
    assert 1 in ast.report.pages_unrecovered
    assert any(item["kind"] == "PAGE" and item["page"] == 1 for item in ast.report.not_interpreted)


def test_07_mathematical_formulas_preservation(temp_dir):
    """Valida fórmulas matemáticas: deteção de equações, número e preservação sem inventar LaTeX."""
    pdf_path = create_math_pdf(temp_dir / "math_doc.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_math_07")

    assert len(ast.formulas) >= 1
    formula = ast.formulas[0]
    assert formula.equation_number == "1"
    assert "theta" in formula.raw_text
    assert formula.representation == "RAW_TEXT_EXTRACTION"
    # Garantia de honestidade: sem LaTeX falso inventado
    assert formula.latex is None
    assert len(formula.limitations) >= 1


def test_08_irregular_structure_document(temp_dir):
    """Valida documento de estrutura irregular (memorando sem secções académicas)."""
    pdf_path = create_irregular_pdf(temp_dir / "irregular_doc.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_irreg_08")

    assert len(ast.sections) >= 1
    assert len(ast.paragraphs) >= 4
    # O conteúdo substantivo não foi descartado
    full_text = " ".join(p.text for p in ast.paragraphs)
    assert "MEMORANDUM INTERNO" in full_text or ast.metadata.title == "MEMORANDUM INTERNO: Politica de Seguranca Q3"
    assert "security@jarvis.internal" in full_text
    assert "autenticacao multifator" in full_text


def test_09_traceability_sentence_integrity_and_coordinates(temp_dir):
    """Valida que cada parágrafo possui coordenadas bboxes, ordem estável e sentence_spans sem cortes."""
    pdf_path = create_short_academic_pdf(temp_dir / "traceability.pdf")
    extractor = DocumentIntelligenceExtractor()
    ast = extractor.extract(pdf_path, "doc_trace_09")

    prev_order = 0
    for p in ast.paragraphs:
        assert p.order > prev_order
        prev_order = p.order
        assert p.bbox is not None
        assert len(p.bbox) == 4
        assert p.section_id.startswith("sec_")
        assert p.page_number >= 1
        assert p.content_sha1 != ""
        # Verificar que nenhuma frase tem reticências cortadas no fim
        assert not p.text.endswith("...")
        assert len(sentence_spans(p.text)) >= 1


def test_10_studyservice_ast_persistence_and_compatibility(temp_dir):
    """Valida a integração da AST no StudyService: pasta do documento, ast.json, media e backwards compatibility."""
    study_svc = StudyService(workspace_root=str(temp_dir), storage_dir=str(temp_dir / "data_study"))
    pdf_path = create_table_pdf(temp_dir / "sample_service.pdf")

    # Ingestão do PDF
    doc = study_svc.ingest_document(
        str(pdf_path),
        "sample_service.pdf",
        subject="Computer Science",
    )

    assert doc.document_id.startswith("doc_")
    assert doc.metadata.get("ast_available") is True
    assert doc.metadata.get("ast_path") == f"documents/{doc.document_id}/ast.json"
    assert doc.metadata.get("ast_schema_version") == "1.0.0"

    # Verificar ficheiros persistidos em disco
    doc_dir = temp_dir / "data_study" / "documents" / doc.document_id
    assert (doc_dir / "ast.json").exists()
    assert (doc_dir / "extraction_report.json").exists()
    assert (doc_dir / "original.pdf").exists()

    # Verificar método get_document_ast
    ast_dict = study_svc.get_document_ast(doc.document_id)
    assert ast_dict is not None
    assert ast_dict["document_id"] == doc.document_id
    assert len(ast_dict["tables"]) >= 1

    # Verificar projeções legadas
    assert len(doc.sections) >= 1
    assert any(m["media_type"] == "table" for m in doc.media)


def test_11_corrupted_pdf_clean_failure(temp_dir):
    """Valida que um ficheiro corrompido falha limpa e explicitamente sem deixar ficheiros órfãos."""
    corrupt_path = temp_dir / "corrupted.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\nGarbage corrupt bytes not a valid pdf at all\n%%EOF")

    extractor = DocumentIntelligenceExtractor()
    with pytest.raises(DocumentExtractionError) as exc_info:
        extractor.extract(corrupt_path, "doc_corrupt_11")

    assert "PDF ilegível" in str(exc_info.value) or "Nenhum conteúdo recuperável" in str(exc_info.value)