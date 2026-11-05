import sys
sys.path.insert(0, ".")
import os
import json
import time
import pathlib
from services.study_ai_engine import generate_complete_study_bundle
from services.study_service import StudyService

os.environ["STUDY_FORCE_LIVE_LLM"] = "1"
os.environ["OLLAMA_MODEL"] = "qwen3.5:9b"

service = StudyService()
doc_id = "doc_c778709e44f8"
doc = service.get_document(doc_id)
if not doc:
    print(f"Document {doc_id} not found!")
    sys.exit(1)

print(f"Starting live generation for: {doc.title} ({doc.source_type}, {doc.page_count} pages)")
t0 = time.time()
bundle = service._refresh_document_study_bundle(doc)
elapsed = time.time() - t0

telem = doc.metadata.get("generation_telemetry", {})
gen_mode = doc.metadata.get("generation_mode")
gr = telem.get("grounding_ratio")
tps = telem.get("tokens_per_sec")
total_tokens = telem.get("output_tokens")
summaries = doc.metadata.get("summaries", {})
quick = summaries.get("quick", [])
study = summaries.get("study", [])
detailed = summaries.get("detailed", [])
cornell = doc.metadata.get("cornell_notes", {})
cues = cornell.get("cue_column", [])

result = {
    "document_id": doc_id,
    "title": doc.title,
    "elapsed_seconds": round(elapsed, 2),
    "generation_mode": gen_mode,
    "grounding_ratio": gr,
    "tokens_per_sec": tps,
    "output_tokens": total_tokens,
    "quick_points_count": len(quick),
    "study_sections_count": len(study),
    "detailed_blocks_count": len(detailed),
    "cornell_cues_count": len(cues),
    "sample_quick": quick[:2],
    "sample_cornell_cue": cues[0] if cues else None,
}

out_file = pathlib.Path("audit/study_engine_quality/benchmark_it_consumerization.json")
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print("=== BENCHMARK RESULT ===")
print(json.dumps(result, indent=2, ensure_ascii=False))

