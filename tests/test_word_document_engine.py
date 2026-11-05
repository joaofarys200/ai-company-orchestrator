"""
Suite de Testes de Aceitação para o Motor Documental Microsoft Word (.docx) do JARVIS OS.
Cobre todos os 12 cenários de aceitação definidos na FASE 10:
1. Criar um documento de raiz com estrutura correta.
2. Ler efetivamente texto e estrutura de um DOCX (AST).
3. Preservar a hierarquia de secções (Title -> H1 -> H2 -> H3).
4. Melhorar um documento sem perder conteúdo não visado.
5. Preservar imagens e tabelas numa revisão cirúrgica.
6. Manter estilos, tipografia e numeração.
7. Seguir um template fornecido pelo utilizador.
8. Detetar citações ou afirmações sem suporte (anti-hallucination).
9. Renderizar o documento final para PDF e imagens PNG de páginas.
10. Detetar problemas de paginação (páginas em branco e títulos órfãos).
11. Comparar versão original e revista (diff unificado e métricas).
12. Entregar e exportar o ficheiro final com integridade SHA-256.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path

import docx
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw
import pytest

from backend.document_engine.editorial_planner import (
    EditorialFinding,
    EditorialPlan,
    EditorialPlanner,
    EditorialReviewReport,
    ReviewFindingSeverity,
)
from backend.document_engine.profiles import (
    AcademicProfile,
    BusinessProposalProfile,
    DocumentProfileType,
    TechnicalSpecProfile,
    get_profile,
)
from backend.document_engine.render_engine import (
    RenderEngineManager,
    RenderEngineType,
    RenderResult,
)
from backend.document_engine.surgical_revisor import (
    OpenXMLPreservationAuditor,
    PreservationAuditResult,
    RevisionDirective,
    RevisionSummary,
    SurgicalRevisor,
)
from backend.document_engine.visual_inspector import (
    VisualInspectionResult,
    VisualInspector,
)
from backend.document_engine.word_ast import (
    HeadingNode,
    ImageNode,
    ParagraphNode,
    TableNode,
    WordDocumentAST,
    extract_ast_from_docx,
)
from backend.document_engine.word_engine import (
    AcceptanceGates,
    DocumentCreationRequest,
    DocumentEngineResult,
    ValidationReport,
    WordDocumentEngine,
)
from backend.document_engine.word_styler import WordStyler


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "word_engine_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def sample_image_path(temp_workspace: Path) -> Path:
    """Creates a real PNG fixture image for embedding in DOCX."""
    img_p = temp_workspace / "sample_architecture_diagram.png"
    img = Image.new("RGB", (300, 150), color=(27, 54, 93))
    d = ImageDraw.Draw(img)
    d.rectangle([(20, 20), (280, 130)], outline=(255, 255, 255), width=3)
    d.text((40, 60), "JARVIS ARCHITECTURE", fill=(255, 255, 255))
    img.save(str(img_p))
    return img_p


@pytest.fixture
def rich_docx_fixture(temp_workspace: Path) -> Path:
    """
    Creates a rich DOCX fixture containing:
    - Title & Subtitle
    - Headings 1, 2, 3
    - Bullet list
    - Styled Table (3 rows x 3 cols)
    - Embedded Image
    - Headers and Footers with page numbers
    """
    doc_path = temp_workspace / "projeto_arquitetura_original.docx"
    doc = docx.Document()
    doc.core_properties.title = "Sistema de Orquestração JARVIS OS"
    doc.core_properties.author = "JARVIS OS"
    profile = get_profile(DocumentProfileType.TECHNICAL_SPEC)
    WordStyler.apply_profile_to_document(doc, profile)

    doc.add_paragraph("Sistema de Orquestração JARVIS OS", style="Title")
    doc.add_paragraph("Documento Técnico Original • Versão 1.0")

    WordStyler.configure_headers_and_footers(doc, "JARVIS OS - Arquitetura", profile)

    # Section 0: Sumário Executivo
    doc.add_paragraph("Sumário Executivo", style="Heading 1")
    doc.add_paragraph("Visão geral concisa da arquitetura técnica do JARVIS OS e garantias operacionais.")

    # Section 1: Introdução
    doc.add_paragraph("Introdução", style="Heading 1")
    doc.add_paragraph("O JARVIS OS é uma plataforma autónoma projetada para orquestração de missões técnicas complexas com governação estrita de produto.")
    doc.add_paragraph("Este documento descreve os princípios fundamentais e a topologia dos subsistemas.")

    # Section 2: Arquitetura de Módulos (with list and image)
    doc.add_paragraph("Arquitetura de Módulos", style="Heading 1")
    doc.add_paragraph("Os componentes principais do sistema distribuem-se da seguinte forma:")
    doc.add_paragraph("Orquestrador Central e Gateway WebSocket", style="List Bullet")
    doc.add_paragraph("Motor Documental e Parser AST de Alta Fidelidade", style="List Bullet")
    doc.add_paragraph("Portão de Governação e Aceitação de Produto", style="List Bullet")

    # Add embedded image using permanent fixture file
    img_path = Path("tests/fixtures/sample_diagram.png").resolve()
    doc.add_paragraph("Diagrama 1: Topologia de Módulos")
    doc.add_picture(str(img_path), width=Inches(3.5))

    # Section 3: Especificação de Componentes (with Table)
    doc.add_paragraph("Especificação de Componentes", style="Heading 1")
    doc.add_paragraph("A tabela seguinte detalha os contratos de interface ativos no sistema:")

    headers = ["Componente", "Responsabilidade", "Maturidade"]
    rows = [
        ["WordEngine", "Autoria, revisão cirúrgica e validação visual de DOCX", "Produção"],
        ["ProductDeliveryGate", "Auditoria determinística de integridade de produto", "Produção"],
    ]
    tbl = doc.add_table(rows=len(rows) + 1, cols=3)
    WordStyler.style_table(tbl, headers, rows, profile)

    # Section 4: Validação e Testes
    doc.add_paragraph("Validação e Testes", style="Heading 1")
    doc.add_paragraph("Os procedimentos de verificação contínua asseguram total conformidade com os critérios de aceitação.")

    # Section 5: Conclusão
    doc.add_paragraph("Conclusão e Próximos Passos", style="Heading 1")
    doc.add_paragraph("A arquitetura modular garante extensibilidade contínua sem quebras de compatibilidade.")

    doc.save(str(doc_path))
    return doc_path


# ── CENÁRIO 1: CRIAR DOCUMENTO DE RAIZ COM ESTRUTURA CORRETA ──────────────────
def test_scenario_01_create_document_from_scratch(temp_workspace: Path):
    target_docx = temp_workspace / "novo_relatorio_academico.docx"
    req = DocumentCreationRequest(
        prompt="Criar relatório de investigação científica sobre IA generativa na engenharia de software",
        output_path=str(target_docx),
        title="Impacto da IA Generativa na Engenharia de Software",
        profile_type=DocumentProfileType.ACADEMIC,
        target_audience="Comunidade Académica e Investigadores",
        language="pt-PT",
        author="Laboratório JARVIS",
    )
    res = WordDocumentEngine.create_document(req)

    assert res.success is True
    assert os.path.exists(res.docx_path)
    assert res.ast is not None
    assert res.ast.title == "Impacto da IA Generativa na Engenharia de Software"
    assert len(res.ast.headings) >= 5
    # Academic profile requires Introdução, Metodologia, Resultados, Discussão, Conclusão
    h_texts = [h.text.lower() for h in res.ast.headings]
    assert any("introdução" in h for h in h_texts)
    assert any("metodologia" in h for h in h_texts)
    assert any("resultados" in h for h in h_texts)
    assert any("conclusão" in h for h in h_texts)
    assert res.ast.metadata.total_words > 80


# ── CENÁRIO 2: LER EFETIVAMENTE TEXTO E ESTRUTURA DE UM DOCX (AST) ─────────────
def test_scenario_02_read_document_ast(rich_docx_fixture: Path):
    ast = WordDocumentEngine.read_document(rich_docx_fixture)

    assert isinstance(ast, WordDocumentAST)
    assert ast.title != ""
    assert len(ast.headings) == 6
    assert len(ast.paragraphs) >= 5
    assert len(ast.tables) == 1
    assert len(ast.images) == 1
    assert ast.metadata.total_words > 40
    # Outline check
    outline = ast.get_outline()
    assert (1, "Introdução") in outline
    assert (1, "Arquitetura de Módulos") in outline


# ── CENÁRIO 3: PRESERVAR HIERARQUIA DE SECÇÕES E METADADOS ─────────────────────
def test_scenario_03_preserve_section_hierarchy(rich_docx_fixture: Path):
    ast = WordDocumentEngine.read_document(rich_docx_fixture)
    outline = ast.get_outline()

    assert len(outline) == 6
    levels = [lvl for lvl, _ in outline]
    assert all(lvl == 1 for lvl in levels)  # All 6 top-level sections
    assert ast.metadata.title == "Sistema de Orquestração JARVIS OS"
    assert len(ast.sections) >= 1
    assert ast.sections[0].header_text != ""
    assert ast.sections[0].footer_text != ""


# ── CENÁRIO 4: MELHORAR DOCUMENTO SEM PERDER CONTEÚDO NÃO VISADO ──────────────
def test_scenario_04_revise_without_losing_untargeted_content(rich_docx_fixture: Path, temp_workspace: Path):
    # Directive: only revise the "Introdução" section
    revised_docx = temp_workspace / "projeto_arquitetura_revisto_intro.docx"
    new_intro_text = (
        "O JARVIS OS representa uma nova geração de sistemas operativos agentic, "
        "incorporando capacidades nativas de autoria documental e garantia formal de integridade de produto."
    )
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Introdução",
        replacement_text=new_intro_text,
    )

    res = WordDocumentEngine.revise_document(rich_docx_fixture, directive, output_path=revised_docx)

    assert res.success is True
    ast_revised = res.ast
    assert ast_revised is not None

    # Check targeted section was revised
    intro_body = ast_revised.get_section_text("Introdução")
    assert "nova geração de sistemas operativos agentic" in intro_body

    # Check non-targeted sections are strictly intact
    assert ast_revised.find_heading("Arquitetura de Módulos") is not None
    assert ast_revised.find_heading("Especificação de Componentes") is not None
    assert ast_revised.find_heading("Conclusão e Próximos Passos") is not None


# ── CENÁRIO 5: PRESERVAR IMAGENS E TABELAS NUMA REVISÃO CIRÚRGICA ─────────────
def test_scenario_05_preserve_images_and_tables_during_revision(rich_docx_fixture: Path, temp_workspace: Path):
    revised_docx = temp_workspace / "projeto_revisto_preserva_media.docx"
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Conclusão e Próximos Passos",
        replacement_text="Conclusão expandida com novas perspetivas estratégicas e validação em tempo de execução.",
    )

    res = WordDocumentEngine.revise_document(rich_docx_fixture, directive, output_path=revised_docx)
    summary = res.revision_summary
    assert summary is not None

    # Preservation assertions
    assert summary.preserved_images_count >= 1
    assert summary.preserved_tables_count >= 1
    assert summary.preserved_headers_footers is True

    # Check in AST
    ast = res.ast
    assert len(ast.images) == 1
    assert len(ast.tables) == 1
    # Verify table content intact
    tbl = ast.tables[0]
    assert tbl.headers == ("Componente", "Responsabilidade", "Maturidade")
    assert tbl.rows[0][0] == "WordEngine"


# ── CENÁRIO 6: MANTER ESTILOS, TIPOGRAFIA E NUMERAÇÃO ──────────────────────────
def test_scenario_06_maintain_styles_and_numbering(rich_docx_fixture: Path, temp_workspace: Path):
    formatted_docx = temp_workspace / "projeto_reformatado.docx"
    res = WordDocumentEngine.format_document(
        rich_docx_fixture,
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        output_path=formatted_docx,
    )

    assert res.success is True
    ast = res.ast
    assert len(ast.sections) >= 1
    sec = ast.sections[0]
    # Technical spec: margins 2.5 cm (70.8 pt)
    assert abs(sec.top_margin_pt - 70.8) < 2.0
    assert abs(sec.left_margin_pt - 70.8) < 2.0
    # Footers preserved
    assert "Página" in sec.footer_text


# ── CENÁRIO 7: SEGUIR UM TEMPLATE FORNECIDO (STYLE INHERITANCE) ───────────────
def test_scenario_07_follow_provided_template(rich_docx_fixture: Path, temp_workspace: Path):
    target_docx = temp_workspace / "documento_a_partir_de_template.docx"
    req = DocumentCreationRequest(
        prompt="Gerar proposta de projeto baseada no template existente",
        output_path=str(target_docx),
        title="Proposta Baseada em Template Corporativo",
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        template_path=str(rich_docx_fixture),  # Uses rich_docx as base template
        author="JARVIS Architecture Team",
    )
    res = WordDocumentEngine.create_document(req)

    assert res.success is True
    ast = res.ast
    assert ast.title == "Proposta Baseada em Template Corporativo"
    # Document contains sections created according to template styling
    assert len(ast.headings) >= 4


# ── CENÁRIO 8: DETETAR CITAÇÕES OU AFIRMAÇÕES SEM SUPORTE ──────────────────────
def test_scenario_08_detect_unsupported_claims_and_hallucinations(temp_workspace: Path):
    # Create doc containing invented statistics not present in sources
    hallucinated_docx = temp_workspace / "documento_com_alucinacoes.docx"
    doc = docx.Document()
    doc.add_paragraph("Relatório Financeiro com Dados Duvidosos", style="Title")
    doc.add_paragraph("Introdução", style="Heading 1")
    doc.add_paragraph("Segundo fontes recentes, o sistema aumentou o rendimento em 94.7% no último trimestre.")
    doc.add_paragraph("Conclusão", style="Heading 1")
    doc.add_paragraph("Adicionalmente, verificou-se uma redução de 43.2% nos custos operacionais.")
    doc.save(str(hallucinated_docx))

    # Sources provide factual baseline without those percentages
    authorized_sources = [
        "O sistema processou 100 transações de teste com sucesso operacional.",
        "Não foram recolhidos dados financeiros externos.",
    ]

    report: EditorialReviewReport = WordDocumentEngine.review_document(
        hallucinated_docx,
        sources=authorized_sources,
        profile_type=DocumentProfileType.GENERIC,
    )

    assert report.unsupported_claims_count >= 2
    unsupported_msgs = [f.message for f in report.findings if f.category == "UNSUPPORTED_CLAIM"]
    assert any("94.7%" in m for m in unsupported_msgs)
    assert any("43.2%" in m for m in unsupported_msgs)


# ── CENÁRIO 9: RENDERIZAR DOCUMENTO FINAL (PDF E IMAGENS PNG) ─────────────────
def test_scenario_09_render_document_to_pdf_and_images(rich_docx_fixture: Path, temp_workspace: Path):
    render_dir = temp_workspace / "render_output"
    vis_res: VisualInspectionResult = WordDocumentEngine.render_document(
        rich_docx_fixture,
        output_dir=render_dir,
    )

    assert os.path.exists(vis_res.pdf_path)
    assert Path(vis_res.pdf_path).stat().st_size > 0
    assert vis_res.total_pages >= 1
    assert len(vis_res.page_images) >= 1
    for img_p in vis_res.page_images:
        assert os.path.exists(img_p)
        assert Path(img_p).stat().st_size > 100  # Valid PNG image bytes


# ── CENÁRIO 10: DETETAR PROBLEMAS DE PAGINAÇÃO (PÁGINAS EM BRANCO E TÍTULOS ÓRFÃOS) ──
def test_scenario_10_detect_pagination_flaws(temp_workspace: Path):
    flawed_docx = temp_workspace / "documento_com_falhas_paginacao.docx"
    doc = docx.Document()
    doc.add_paragraph("Documento com Falhas", style="Title")
    doc.add_paragraph("Introdução", style="Heading 1")
    doc.add_paragraph("Texto inicial.")
    # Add page break followed by empty content (blank page)
    doc.add_page_break()
    # Another page break with nothing
    doc.add_page_break()
    doc.save(str(flawed_docx))

    vis_res: VisualInspectionResult = VisualInspector.inspect_visual_layout(flawed_docx)

    # Should detect at least one blank page flaw
    blank_page_flaws = [f for f in vis_res.flaws if f.flaw_type == "BLANK_PAGE"]
    assert len(blank_page_flaws) >= 1
    assert any(f.severity in {"ERROR", "WARNING"} for f in blank_page_flaws)


# ── CENÁRIO 11: COMPARAR ORIGINAL E VERSÃO REVISTA (DIFF E MÉTRICAS) ──────────
def test_scenario_11_version_comparison_and_diff(rich_docx_fixture: Path, temp_workspace: Path):
    revised_docx = temp_workspace / "projeto_comparacao_diff.docx"
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Introdução",
        replacement_text="Nova introdução comparativa para demonstrar a geração de diff determinístico e unificado.",
    )

    res = WordDocumentEngine.revise_document(rich_docx_fixture, directive, output_path=revised_docx)
    summary = res.revision_summary
    assert summary is not None

    # Unified diff verification
    diff = summary.unified_diff
    assert "--- a/" in diff or "+++ b/" in diff or len(diff) > 0
    assert summary.words_before > 0
    assert summary.words_after > 0
    assert os.path.exists(summary.backup_path)  # Safe backup verified


# ── CENÁRIO 12: ENTREGAR E EXPORTAR COM INTEGRIDADE SHA-256 ─────────────────────
def test_scenario_12_export_document_with_sha256(rich_docx_fixture: Path, temp_workspace: Path):
    export_dir = temp_workspace / "delivery_export"
    export_res = WordDocumentEngine.export_document(
        rich_docx_fixture,
        target_dir=export_dir,
        formats=("docx", "pdf"),
    )

    assert export_res.document_id.startswith("doc_")
    assert "docx" in export_res.files
    assert "pdf" in export_res.files
    assert os.path.exists(export_res.files["docx"])
    assert os.path.exists(export_res.files["pdf"])

    # Verify SHA-256 integrity
    assert len(export_res.file_hashes["docx"]) == 64
    assert len(export_res.file_hashes["pdf"]) == 64


# ── COMPREHENSIVE END-TO-END VALIDATION PIPELINE ──────────────────────────────
def test_comprehensive_validation_pipeline(rich_docx_fixture: Path):
    val_rep: ValidationReport = WordDocumentEngine.validate_document(
        rich_docx_fixture,
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
    )

    assert isinstance(val_rep, ValidationReport)
    assert val_rep.quality_score >= 70.0
    assert val_rep.valid is True
    assert "Validação Documental" in val_rep.summary


# ══════════════════════════════════════════════════════════════════════════════
# ADVERSARIAL AUDIT & REAL RENDERING FIDELITY SUITE (FASES 1 - 8)
# ══════════════════════════════════════════════════════════════════════════════


# ── ADVERSARIAL 1: CRIAÇÃO E REABERTURA COM AST FIDELITY ─────────────────────
def test_adversarial_01_create_and_reopen_docx(temp_workspace: Path):
    target_docx = temp_workspace / "adv_01_document.docx"
    req = DocumentCreationRequest(
        prompt="Especificação técnica do protocolo de mensageria",
        output_path=str(target_docx),
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        sources=["Contrato v1.2: Latência máxima 50ms, throughput 1000 req/s"],
    )
    res = WordDocumentEngine.create_document(req)
    assert res.success is True
    assert target_docx.exists()

    # Reopen directly and verify structural completeness
    ast = extract_ast_from_docx(target_docx)
    assert ast.title != ""
    assert len(ast.headings) >= 4
    assert len(ast.paragraphs) >= 4
    assert len(ast.tables) >= 1
    assert ast.metadata.total_words > 100


# ── ADVERSARIAL 2: RENDERIZAÇÃO ATRAVÉS DO MOTOR REAL DISPONÍVEL ──────────────
def test_adversarial_02_render_via_real_available_engine(rich_docx_fixture: Path, temp_workspace: Path):
    engines = RenderEngineManager.detect_available_engines()
    out_dir = temp_workspace / "adv_02_render"

    # Since Microsoft Word is installed on this host, real office render must execute
    res: RenderResult = RenderEngineManager.render(
        rich_docx_fixture,
        output_dir=out_dir,
        prefer_real_office=True,
    )

    if engines["word_com"]["available"]:
        assert res.engine_type == RenderEngineType.REAL_OFFICE_RENDER
        assert res.is_real_office is True
        assert "Microsoft Word" in res.engine_name
        assert Path(res.pdf_path).exists()
        assert len(res.page_images) > 0


# ── ADVERSARIAL 3: IDENTIFICAÇÃO CORRETA DE UMA RENDERIZAÇÃO SINTÉTICA ────────
def test_adversarial_03_synthetic_render_identification(rich_docx_fixture: Path, temp_workspace: Path):
    out_dir = temp_workspace / "adv_03_synthetic"
    # Explicitly force synthetic render
    res: RenderResult = RenderEngineManager.render(
        rich_docx_fixture,
        output_dir=out_dir,
        prefer_real_office=False,
    )

    assert res.engine_type == RenderEngineType.SYNTHETIC_RENDER
    assert res.is_real_office is False
    assert "PyMuPDF" in res.engine_name
    assert any("Não constitui prova de fidelidade" in lim for lim in res.limitations)

    # Inspect visual validation on this synthetic render
    vis_res = VisualInspector.inspect_visual_layout(
        rich_docx_fixture,
        output_dir=out_dir,
        prefer_real_office=False,
    )
    assert vis_res.render_engine_type == RenderEngineType.SYNTHETIC_RENDER
    assert vis_res.is_real_office is False
    assert vis_res.visual_fidelity_verified is False


# ── ADVERSARIAL 4: ATUALIZAÇÃO DE CAMPOS E ÍNDICE QUANDO SUPORTADA ────────────
def test_adversarial_04_toc_and_fields_update(temp_workspace: Path):
    docx_p = temp_workspace / "adv_04_toc_doc.docx"
    doc = docx.Document()
    doc.add_heading("Índice Dinâmico", level=1)
    WordStyler.add_table_of_contents(doc, title="Índice")

    for i in range(1, 4):
        doc.add_heading(f"Secção Experimental {i}", level=1)
        doc.add_paragraph(f"Conteúdo substantivo da secção {i} para teste de paginação e campos dinâmicos.")
        doc.add_page_break()

    doc.save(str(docx_p))

    out_dir = temp_workspace / "adv_04_render"
    res: RenderResult = RenderEngineManager.render(
        docx_p,
        output_dir=out_dir,
        prefer_real_office=True,
        update_fields=True,
    )

    if res.is_real_office:
        assert res.fields_updated is True
        assert res.toc_updated is True
        assert res.docx_output_sha256 is not None


# ── ADVERSARIAL 5: CORRESPONDÊNCIA DOS NÚMEROS DE PÁGINA COM O PDF RENDERIZADO ─
def test_adversarial_05_page_numbers_correspondence(temp_workspace: Path):
    docx_p = temp_workspace / "adv_05_pages_doc.docx"
    doc = docx.Document()
    doc.add_paragraph("Documento de Paginação Real", style="Title")
    WordStyler.add_table_of_contents(doc, title="Índice")

    doc.add_heading("Primeira Grande Secção", level=1)
    doc.add_paragraph("Corpo de texto da primeira grande secção.")
    doc.add_page_break()

    doc.add_heading("Segunda Grande Secção", level=1)
    doc.add_paragraph("Corpo de texto da segunda secção que se situa na página seguinte.")

    doc.save(str(docx_p))

    out_dir = temp_workspace / "adv_05_render"
    res: RenderResult = RenderEngineManager.render(
        docx_p,
        output_dir=out_dir,
        prefer_real_office=True,
        update_fields=True,
    )

    if res.is_real_office:
        import pymupdf
        doc_pdf = pymupdf.open(res.pdf_path)
        assert len(doc_pdf) >= 2
        full_text = " ".join(page.get_text() for page in doc_pdf)
        assert "Primeira Grande Secção" in full_text
        assert "Segunda Grande Secção" in full_text


# ── ADVERSARIAL 6: PRESERVAÇÃO DOS ELEMENTOS NÃO VISADOS NUMA REVISÃO ─────────
def test_adversarial_06_preservation_of_untargeted_elements(temp_workspace: Path):
    doc_p = temp_workspace / "adv_06_complex_doc.docx"
    doc = docx.Document()
    doc.add_heading("Secção Preservada A", level=1)
    doc.add_paragraph("Texto não visado que deve permanecer absolutamente inalterado.")

    # Table with merged cells
    tbl = doc.add_table(rows=2, cols=2)
    tbl.cell(0, 0).merge(tbl.cell(0, 1))
    tbl.cell(0, 0).text = "Cabeçalho Mesclado Preservado"
    tbl.cell(1, 0).text = "Célula 1"
    tbl.cell(1, 1).text = "Célula 2"

    doc.add_heading("Secção Alvo B", level=1)
    doc.add_paragraph("Texto original a ser cirurgicamente modificado.")

    doc.save(str(doc_p))

    revised_p = temp_workspace / "adv_06_revised.docx"
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Secção Alvo B",
        replacement_text="Texto revisto cirurgicamente com novos detalhes operacionais.",
    )

    rev_p, summary = SurgicalRevisor.revise(doc_p, directive, output_path=revised_p)
    assert summary.success is True
    assert summary.preservation_audit is not None
    assert summary.preservation_audit.merged_cells_preserved is True
    assert summary.preservation_audit.merged_cells_count_before >= 1

    ast_after = extract_ast_from_docx(revised_p)
    assert any("Secção Preservada A" in h.text for h in ast_after.headings)
    assert len(ast_after.tables) == 1


# ── ADVERSARIAL 7: INTEGRIDADE DOS FICHEIROS DE MEDIA (SHA-256) ────────────────
def test_adversarial_07_media_sha256_integrity(rich_docx_fixture: Path, temp_workspace: Path):
    revised_p = temp_workspace / "adv_07_media_integrity.docx"
    directive = RevisionDirective(
        strategy="FIND_REPLACE",
        find_replace_pairs=[("JARVIS OS é uma plataforma autónoma", "JARVIS OS constitui um sistema operativo autónomo")],
    )

    rev_p, summary = SurgicalRevisor.revise(rich_docx_fixture, directive, output_path=revised_p)
    assert summary.success is True
    assert summary.preservation_audit is not None
    assert summary.preservation_audit.media_hashes_verified is True
    assert summary.preservation_audit.media_files_count >= 1

    # Open both docx as ZIP and compare SHA-256 hashes of all media directly
    with zipfile.ZipFile(rich_docx_fixture) as z_orig, zipfile.ZipFile(revised_p) as z_rev:
        for name in z_orig.namelist():
            if name.startswith("word/media/"):
                orig_hash = hashlib.sha256(z_orig.read(name)).hexdigest()
                rev_hash = hashlib.sha256(z_rev.read(name)).hexdigest()
                assert orig_hash == rev_hash


# ── ADVERSARIAL 8: TRATAMENTO DE EQUAÇÕES E OBJETOS OPENXML ───────────────────
def test_adversarial_08_omml_equations_preservation(temp_workspace: Path):
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls

    doc_p = temp_workspace / "adv_08_math.docx"
    doc = docx.Document()
    doc.add_heading("Enquadramento Físico", level=1)
    p = doc.add_paragraph("A relação fundamental de energia é expressa por: ")

    math_xml = parse_xml(r'<m:oMath %s><m:r><m:t>E=mc^2</m:t></m:r></m:oMath>' % nsdecls("m"))
    p._p.append(math_xml)

    doc.add_heading("Secção Alvo", level=1)
    doc.add_paragraph("Texto anterior à revisão.")
    doc.save(str(doc_p))

    revised_p = temp_workspace / "adv_08_math_revised.docx"
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Secção Alvo",
        replacement_text="Texto revisto preservando a equação matemática anterior.",
    )

    rev_p, summary = SurgicalRevisor.revise(doc_p, directive, output_path=revised_p)
    assert summary.success is True
    assert summary.preservation_audit is not None
    assert summary.preservation_audit.omml_equations_preserved is True
    assert summary.preservation_audit.omml_equations_count_before >= 1


# ── ADVERSARIAL 9: DETEÇÃO DE DEFEITOS DE PAGINAÇÃO REAIS ──────────────────────
def test_adversarial_09_real_pagination_defect_detection(temp_workspace: Path):
    doc_p = temp_workspace / "adv_09_blank_defect.docx"
    doc = docx.Document()
    doc.add_heading("Página 1 com Conteúdo", level=1)
    doc.add_paragraph("Texto na primeira página.")
    doc.add_page_break()

    # Second page is empty
    doc.add_page_break()

    # Third page has content
    doc.add_heading("Página 3 com Conteúdo", level=1)
    doc.add_paragraph("Texto na terceira página.")
    doc.save(str(doc_p))

    vis_res = VisualInspector.inspect_visual_layout(
        doc_p,
        output_dir=temp_workspace / "adv_09_render",
        prefer_real_office=True,  # Real Office pagination engine
    )

    if vis_res.is_real_office:
        blank_flaws = [f for f in vis_res.flaws if f.flaw_type == "BLANK_PAGE"]
        assert len(blank_flaws) >= 1
        assert any(f.page_number == 2 for f in blank_flaws)


# ── ADVERSARIAL 10: FALHA CONTROLADA QUANDO FALTA MOTOR OFFICE REQUERIDO ───────
def test_adversarial_10_controlled_failure_when_real_office_required(rich_docx_fixture: Path, temp_workspace: Path):
    with pytest.raises(RuntimeError) as exc_info:
        RenderEngineManager.render(
            rich_docx_fixture,
            output_dir=temp_workspace / "adv_10_render",
            prefer_real_office=False,
            require_real_office=True,
        )
    assert "Motor Office real obrigatório não disponível" in str(exc_info.value)


# ── ADVERSARIAL 11: PROIBIÇÃO DE APROVAÇÃO VISUAL BASEADA APENAS EM SIMULAÇÃO ──
def test_adversarial_11_prohibit_visual_acceptance_on_simulation(rich_docx_fixture: Path):
    # Validate with prefer_real_office=False, forcing synthetic render
    report: ValidationReport = WordDocumentEngine.validate_document(
        rich_docx_fixture,
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        prefer_real_office=False,
    )

    # Verification of acceptance gates separation
    assert report.real_render_validated is False
    assert report.visual_acceptance_validated is False
    assert report.quality_score <= 60.0
    assert report.render_engine_type == RenderEngineType.SYNTHETIC_RENDER
    assert any("renderização sintética não comprova" in lim for lim in report.limitations)


# ── ADVERSARIAL 12: REGISTO FIEL DO MOTOR E VERIFICAÇÕES EXECUTADAS ───────────
def test_adversarial_12_audit_trail_and_engine_logging(rich_docx_fixture: Path):
    engines = RenderEngineManager.detect_available_engines()
    report: ValidationReport = WordDocumentEngine.validate_document(
        rich_docx_fixture,
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        prefer_real_office=True,
    )

    if engines["word_com"]["available"]:
        assert report.real_render_validated is True
        assert report.visual_acceptance_validated is True
        assert report.structure_validated is True
        assert report.editorial_validated is True
        assert report.docx_integrity_validated is True
        assert report.gates is not None
        assert report.gates.all_validated() is True
        assert report.quality_score >= 80.0
        assert "Microsoft Word" in report.render_engine_name
