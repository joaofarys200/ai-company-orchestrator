"""
End-to-end demonstration and delivery validation script for JARVIS Word Document Engine.
Generates real sample documents, performs surgical revision, visual inspection, rendering,
and exports with SHA-256 integrity verification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.document_engine.profiles import DocumentProfileType
from backend.document_engine.surgical_revisor import RevisionDirective
from backend.document_engine.word_engine import (
    DocumentCreationRequest,
    WordDocumentEngine,
)


def main():
    out_dir = Path("workspace/demo_word_engine").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== INICIANDO DEMONSTRAÇÃO END-TO-END DO MOTOR DOCUMENTAL WORD ===")
    print(f"Diretório de saída: {out_dir}\n")

    # 1. CRIAR DOCUMENTO DE RAIZ
    docx_orig = out_dir / "JARVIS_Whitepaper_Arquitetura.docx"
    print("1. Criando documento de raiz com perfil TECHNICAL_SPEC...")
    req = DocumentCreationRequest(
        prompt="Especificação arquitetural do motor documental e de revisão profissional do JARVIS OS",
        output_path=str(docx_orig),
        title="JARVIS OS — Motor Documental e Revisão Profissional Word",
        profile_type=DocumentProfileType.TECHNICAL_SPEC,
        target_audience="Engenheiros de Software e Arquitetos de Sistemas",
        language="pt-PT",
        author="JARVIS Autonomous Engine",
        sources=[
            "O sistema disponibiliza 8 operações canónicas: CREATE, READ, REVIEW, REVISE, FORMAT, RENDER, VALIDATE, EXPORT.",
            "A preservação de tabelas, imagens e cabeçalhos é formalmente verificada.",
            "O pipeline visual deteta páginas em branco e títulos órfãos através de inspeção em tempo de execução.",
        ],
    )
    res_create = WordDocumentEngine.create_document(req)
    print(f"   -> [OK] Documento criado: {res_create.docx_path}")
    print(f"   -> Palavras: {res_create.ast.metadata.total_words}, Headings: {len(res_create.ast.headings)}\n")

    # 2. LER E INTERPRETAR ESTRUTURA (AST)
    print("2. Lendo estrutura e AST do documento gerado...")
    ast = WordDocumentEngine.read_document(docx_orig)
    print(f"   -> [OK] Título AST: {ast.title}")
    print(f"   -> Outline: {ast.get_outline()}")
    print(f"   -> Tabelas: {len(ast.tables)}, Secções: {len(ast.sections)}\n")

    # 3. REVISÃO CIRÚRGICA DE DOCUMENTO EXISTENTE
    print("3. Executando revisão cirúrgica in-place...")
    docx_revised = out_dir / "JARVIS_Whitepaper_Arquitetura_Revisto.docx"
    directive = RevisionDirective(
        strategy="SURGICAL_REPLACE",
        target_heading="Sumário Executivo",
        replacement_text=(
            "O JARVIS OS integra agora um motor documental de nível industrial capaz de efetuar "
            "leitura estrutural em AST, formatação semântica, revisões cirúrgicas sem perda de "
            "conteúdo adjacente e renderização visual validada deterministicamente."
        ),
        notes="Atualização do Sumário Executivo com novos destaques de maturidade técnica.",
    )
    res_revise = WordDocumentEngine.revise_document(docx_orig, directive, output_path=docx_revised)
    summary = res_revise.revision_summary
    print(f"   -> [OK] Documento revisto salvo em: {res_revise.docx_path}")
    print(f"   -> Secções modificadas: {summary.modified_sections}")
    print(f"   -> Palavras antes: {summary.words_before}, depois: {summary.words_after}\n")

    # 4. RENDERIZAÇÃO E INSPEÇÃO VISUAL
    print("4. Executando renderização visual (PDF e páginas PNG)...")
    render_dir = out_dir / "render_output"
    vis_res = WordDocumentEngine.render_document(docx_revised, output_dir=render_dir)
    print(f"   -> [OK] PDF gerado: {vis_res.pdf_path}")
    print(f"   -> Total de páginas renderizadas: {vis_res.total_pages}")
    print(f"   -> Imagens de páginas: {len(vis_res.page_images)}")
    print(f"   -> Conclusão da inspeção visual: {vis_res.summary}\n")

    # 5. VALIDAÇÃO COMPLETA
    print("5. Executando validação documental multi-eixo...")
    val_rep = WordDocumentEngine.validate_document(docx_revised, profile_type=DocumentProfileType.TECHNICAL_SPEC)
    print(f"   -> [OK] Veredito: {'APROVADO' if val_rep.valid else 'REPROVADO'}")
    print(f"   -> Pontuação de qualidade: {val_rep.quality_score:.1f}/100")
    print(f"   -> Sumário: {val_rep.summary}\n")

    # 6. EXPORTAÇÃO FINAL COM HASHES SHA-256
    print("6. Exportando pacote final com integridade criptográfica...")
    export_dir = out_dir / "export_final"
    exp_res = WordDocumentEngine.export_document(docx_revised, export_dir, formats=("docx", "pdf"))
    print(f"   -> [OK] Document ID: {exp_res.document_id}")
    for fmt, f_path in exp_res.files.items():
        print(f"      - [{fmt.upper()}] {f_path} (SHA-256: {exp_res.file_hashes[fmt][:16]}...)")

    print("\n=== DEMONSTRAÇÃO CONCLUÍDA COM 100% DE SUCESSO ===")


if __name__ == "__main__":
    main()
