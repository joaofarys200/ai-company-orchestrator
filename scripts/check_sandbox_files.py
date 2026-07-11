import os
import time

sandbox_dir = r"c:\Users\joaor\Desktop\ai-company-orchestrator\sandbox_dir"

for filename in ["index.html", "styles.css", "app.js"]:
    filepath = os.path.join(sandbox_dir, filename)
    if os.path.exists(filepath):
        stat = os.stat(filepath)
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
        size = stat.st_size
        print(f"File: {filename}")
        print(f"  Modified: {mtime}")
        print(f"  Size: {size} bytes")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"  First 200 chars: {repr(content[:200])}")
    else:
        print(f"File not found: {filename}")
