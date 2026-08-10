import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_gemini_tools():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("GEMINI_API_KEY not found in .env")
        return
        
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply in Portuguese."},
            {"role": "user", "content": "Cria um ficheiro de notas chamado teste.txt"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Writes content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "The name of the file"
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to write"
                            }
                        },
                        "required": ["filename", "content"]
                    }
                }
            }
        ],
        "temperature": 0.2
    }
    
    try:
        print("Sending request with tools to Gemini OpenAI compatibility layer...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload, headers=headers)
        print("Status code:", res.status_code)
        if res.status_code == 200:
            print("Response:", json.dumps(res.json(), indent=2))
        else:
            print("Error response:", res.text)
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gemini_tools())
