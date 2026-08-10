import httpx
import json
import os

url = "http://localhost:11434/api/chat"

# Load tools from agents.py equivalent
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents import JARVIS_TOOLS

ollama_tools = []
for tool in JARVIS_TOOLS:
    # Some older Ollama versions crash if properties is empty or not containing any values.
    # Let's see if this schema crashes it.
    ollama_tools.append({
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"]
        }
    })

payload = {
    "model": "qwen2.5:7b",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant with tools."},
        {"role": "user", "content": "List the active windows."}
    ],
    "tools": ollama_tools,
    "stream": False
}

try:
    print("Sending request to Ollama...")
    res = httpx.post(url, json=payload, timeout=60.0)
    print(f"Status Code: {res.status_code}")
    if res.status_code == 200:
        print("Success!")
        print(json.dumps(res.json(), indent=2))
    else:
        print("Failure:")
        print(res.text)
except Exception as e:
    print(f"Exception: {e}")
