import os, sys
PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, PROJECT_ROOT)
from services.study_service import StudyService
import json

svc = StudyService(workspace_root=PROJECT_ROOT)
doc = svc.ingest_document(
    file_path_or_content="data/study/sample_paper_attention.pdf",
    filename="sample_paper_attention.pdf",
    source_type="PDF"
)

print(f"Doc ID: {doc.document_id}")
print(f"Title: {doc.title}")
print(f"Pages: {doc.page_count}")
print(f"Language: {doc.language}")
print(f"Sections count: {len(doc.sections)}")
for s in doc.sections:
    print(f"  - {s['title']} (p. {s['page_start']}-{s['page_end']}, {len(s['paragraphs'])} paras)")

print(f"Media count: {len(doc.media)}")
for m in doc.media:
    print(f"  - {m['title']} ({m['media_type']}, p. {m['page_number']})")

print(f"Glossary count: {len(doc.glossary)}")
for g in doc.glossary[:5]:
    print(f"  - {g['term']} -> {g['translation']}")

print("\n--- GROUNDING TESTS ---")
# A) Supported
res_a = svc.verify_grounding(doc.document_id, "Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task.")
print("A) Supported claim status:", res_a["status"])
print("   Citation:", res_a.get("citation"))

# B) Unsupported
res_b = svc.verify_grounding(doc.document_id, "A cotação do barril de petróleo Brent atingiu máximos históricos em 1973 durante o embargo da OPEP.")
print("B) Unsupported claim status:", res_b["status"])

# C) Inferred
res_c = svc.verify_grounding(doc.document_id, "O modelo Transformer pode potencialmente ser estendido a dados biomédicos e sinais sonoros contínuos.")
print("C) Inferred claim status:", res_c["status"])

# D) Contradicted
res_d = svc.verify_grounding(doc.document_id, "The Transformer model relies fundamentally on recurrent LSTM layers for sequence alignment.")
print("D) Contradicted claim status:", res_d["status"])
print("   Citation:", res_d.get("citation"))

# Ask Paper checks
print("\n--- ASK PAPER CHECKS ---")
ask_sup = svc.ask_paper(doc.document_id, "What is the BLEU score of Transformer on English-to-German?")
print("Supported question answer:", ask_sup["answer"][:120], "...")
print("Supported sources:", ask_sup["sources"])
print("Supported status:", ask_sup["status"])

ask_unsup = svc.ask_paper(doc.document_id, "Qual foi a receita líquida anual da petroleira Saudi Aramco?")
print("Unsupported question answer:", ask_unsup["answer"])
print("Unsupported status:", ask_unsup["status"])
print("Unsupported sources:", ask_unsup["sources"])
