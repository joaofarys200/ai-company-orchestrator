import json
import pathlib

p = pathlib.Path("data/study/documents.json")
if not p.exists():
    print("NO_DOCUMENTS_FILE")
    exit(0)

docs = json.loads(p.read_text(encoding="utf-8"))
print(f"TOTAL_DOCUMENTS={len(docs)}")
for doc_id, d in docs.items():
    meta = d.get("metadata", {})
    telem = meta.get("generation_telemetry", {})
    sums = meta.get("summaries", {})
    quick_cnt = len(sums.get("quick", [])) if isinstance(sums.get("quick"), list) else 0
    study_cnt = len(sums.get("study", [])) if isinstance(sums.get("study"), list) else 0
    det = sums.get("detailed", [])
    det_cnt = len(det) if isinstance(det, list) else (1 if det else 0)
    cornell_cues = len((meta.get("cornell_notes") or {}).get("cue_column", []))
    gen_mode = str(meta.get("generation_mode", "NONE"))
    stype = str(d.get("source_type", "UNKNOWN"))
    model = str(telem.get("model", "none"))
    gr = str(telem.get("grounding_ratio", "N/A"))
    title = str(d.get("title", ""))[:40]
    print(f"[{doc_id}] {stype:6s} | {gen_mode:19s} | {model:10s} | gr={gr:5s} | q={quick_cnt:2d} s={study_cnt:2d} d={det_cnt:2d} c={cornell_cues:2d} | {title}")

