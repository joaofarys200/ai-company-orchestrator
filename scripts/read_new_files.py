import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

sandbox_dir = r"c:\Users\joaor\Desktop\ai-company-orchestrator\sandbox_dir"

for filename in ["index.html", "styles.css"]:
    filepath = os.path.join(sandbox_dir, filename)
    if os.path.exists(filepath):
        print(f"=== {filename} ===")
        with open(filepath, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print(f"File not found: {filename}")
