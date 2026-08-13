import asyncio
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.abspath("."))

from workspace.document_pipeline import DocumentPipeline, DocumentProvenanceManifest
from workspace.document_pipeline.quality_evaluator import DocumentQualityEvaluator

DOCUMENT_TYPES = [
    ("DOC01_TECHNICAL_REPORT", "Relatório Técnico de Arquitetura Distribuída"),
    ("DOC02_MARKET_ANALYSIS", "Análise de Mercado SaaS B2B na Europa"),
    ("DOC03_SOFTWARE_DOCS", "Documentação do Motor de Execução JARVIS"),
    ("DOC04_FUNCTIONAL_SPEC", "Especificação Funcional de Gateway de Pagamentos"),
    ("DOC05_FINANCIAL_REPORT", "Relatório Financeiro e Análise de CAC/LTV"),
    ("DOC06_API_DOCUMENTATION", "Documentação de Endpoints REST e GraphQL"),
    ("DOC07_COMMERCIAL_PROPOSAL", "Proposta Comercial para Integração Enterprise"),
    ("DOC08_COMPETITOR_MATRIX", "Matriz de Comparação Competitiva de IA Agents"),
    ("DOC09_MULTI_SOURCE_REPORT", "Relatório de Tendências de RAG e AST Patching"),
    ("DOC10_WHITEPAPER_20PAGES", "Whitepaper sobre Sistemas Autónomos Anti-Fabricação"),
    ("DOC11_SECURITY_AUDIT", "Auditoria de Segurança e Isolamento de Secrets"),
    ("DOC12_DATA_COMPLIANCE", "Manual de Conformidade GDPR e Proteção de Dados"),
    ("DOC13_PRODUCT_ROADMAP", "Roadmap Estratégico de Autonomia e Computador"),
    ("DOC14_DISASTER_RECOVERY", "Plano de Recuperação de Desastres e Watchdog"),
    ("DOC15_DATABASE_SCHEMA", "Dicionário de Dados e Índices SQLite WAL"),
    ("DOC16_DEPLOYMENT_GUIDE", "Guia de Deployment e Sandbox Playwright"),
    ("DOC17_PERFORMANCE_METRICS", "Benchmarking de Latência e Model Harness"),
    ("DOC18_USER_ONBOARDING", "Manual de Boas-Vindas e Tutoriais Interativos"),
    ("DOC19_CASE_STUDY", "Estudo de Caso: Conversão e Aquisição de Leads"),
    ("DOC20_EXECUTIVE_BRIEF", "Sumário Executivo para o Conselho de Administração"),
]


async def run_doc_benchmark(doc_id: str, title: str) -> dict[str, Any]:
    pipeline = DocumentPipeline(output_dir="workspace/generated_docs_benchmark")
    file_path, manifest = await pipeline.generate_document(
        title=title,
        topic=f"Pesquisa aprofundada para {title}",
    )
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    score = DocumentQualityEvaluator.evaluate_document(content, manifest)
    assert score.requirement_coverage_pct >= 80.0
    assert score.factuality_pct >= 90.0
    return {
        "id": doc_id,
        "title": title,
        "coverage": f"{score.requirement_coverage_pct}%",
        "factuality": f"{score.factuality_pct}%",
        "grade": score.overall_quality_grade,
        "status": "PASS",
    }


async def main():
    print("================================================================================")
    print("       JARVIS OS — DOCUMENT QUALITY & AUDIT BENCHMARK (DOC01 - DOC20)")
    print("================================================================================")

    for doc_id, title in DOCUMENT_TYPES:
        t0 = time.time()
        res = await run_doc_benchmark(doc_id, title)
        elapsed = round(time.time() - t0, 4)
        print(f"[{res['id']}] -> GRADE: {res['grade']} | COV: {res['coverage']} | FACT: {res['factuality']} ({elapsed}s)")

    print("\n>>> DOCUMENT QUALITY BENCHMARK COMPLETED: 20/20 PASS <<<")


if __name__ == "__main__":
    asyncio.run(main())
