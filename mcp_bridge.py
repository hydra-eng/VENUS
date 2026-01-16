import asyncio
import websockets
import json
import subprocess
import os

# CONFIGURATION
# Connects to your local Docker container from Step 2
SERVER_URL = "ws://localhost:8000/v1/mcp/endpoint?token=YOUR_LOCAL_TOKEN"

async def run_bridge():
    print(f"Connecting to {SERVER_URL}...")
    async with websockets.connect(SERVER_URL) as ws:
        print("✅ Connected to Xiaozhi Server Socket!")
        
        # Start Windows-MCP in the background
        process = subprocess.Popen(
            ["python", "-m", "windows_mcp"], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            text=True, 
            bufsize=0
        )

        async for message in ws:
            data = json.loads(message)
            
            # If the server asks to "Call Tool"
            if data.get("method") == "tools/call":
                print(f"🤖 AI Requesting Action: {data['params']['name']}")
                
                # 1. Forward to Windows-MCP (Write to Stdio)
                json_str = json.dumps(data) + "\n"
                process.stdin.write(json_str)
                
                # 2. Read Response from Windows-MCP
                result = process.stdout.readline()
                
                # 3. Send Result back to Socket
                await ws.send(result)
                print("Sent result back to Server.")

if __name__ == "__main__":
    asyncio.run(run_bridge())
