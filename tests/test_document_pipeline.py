import sys, os
sys.path.insert(0, os.path.abspath("."))

import unittest
from workspace.document_pipeline import DocumentPipeline, DocumentProvenanceManifest


class TestDocumentPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_10_stage_document_generation(self):
        pipeline = DocumentPipeline(output_dir="workspace/test_generated_docs")
        file_path, manifest = await pipeline.generate_document(
            title="Analise de Mercado Fintech 2026",
            topic="Tendencias em APIs de Pagamento e Seguranca",
        )

        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(manifest.validation["sources_checked"])
        self.assertTrue(manifest.validation["claims_checked"])
        self.assertTrue(manifest.validation["completeness_checked"])
        self.assertTrue(manifest.validation["technical_review_passed"])
        self.assertTrue(len(manifest.sha256_fingerprint) == 64)
        self.assertGreaterEqual(len(manifest.sections), 5)


if __name__ == "__main__":
    unittest.main()
