"""
Live agent activation and frontend protocol integration test
"""

import asyncio
import json
import websockets

WS_URL = "ws://127.0.0.1:8001/?token=local-dev-token"

async def test_live_agent():
    print(f"[*] Connecting to JARVIS WebSocket: {WS_URL}")
    async with websockets.connect(WS_URL) as ws:
        print("[+] Connected successfully!")

        # 1. Send directive to activate the agent orchestrator
        directive = {
            "type": "directive",
            "text": "Olá JARVIS, lista os agentes disponíveis e faz um teste de diagnóstico ao sistema."
        }
        print(f"[*] Sending directive: {directive['text']}")
        await ws.send(json.dumps(directive))

        # 2. Collect messages for 8 seconds
        messages_received = []
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 8:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(raw)
                msg_type = data.get("type", "unknown")
                messages_received.append(data)
                
                if msg_type == "chat":
                    sender = data.get("sender", "UNKNOWN")
                    role = data.get("role", "")
                    content = data.get("content", "")
                    print(f"\n[CHAT from {sender} ({role})]:\n{content}")
                elif msg_type == "system":
                    print(f"[SYSTEM]: {data.get('content', '')}")
                elif msg_type == "state":
                    print(f"[STATE]: {data.get('value', '')}")
                else:
                    print(f"[EVENT ({msg_type})]: {str(data)[:100]}...")
            except asyncio.TimeoutError:
                continue

        print(f"\n[+] Total messages received from backend/agent: {len(messages_received)}")
        assert len(messages_received) > 0, "No messages received from backend"

if __name__ == "__main__":
    asyncio.run(test_live_agent())
