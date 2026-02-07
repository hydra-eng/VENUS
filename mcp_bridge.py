import asyncio
import websockets
import json
import subprocess
import sys
import os
import requests
import time

# ================= ⚙️ CONFIGURATION ZONE ⚙️ =================
# 1. YOUR XIAOZHI CLOUD URL (Copy from Dashboard)
MCP_ENDPOINT = "  "

# 2. YOUR HOME ASSISTANT DETAILS (Leave empty if not using HA)
HA_URL = "http://192.168.1.XX:8123" 
HA_TOKEN = "Bearer eyJhbG..." 

# ============================================================

# Home Assistant Tool Definition
HA_TOOLS_INJECTION = [
    {
        "name": "ha_control",
        "description": "Control Smart Home devices via Home Assistant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID (e.g., light.studio, switch.fan)"},
                "action": {"type": "string", "description": "turn_on, turn_off, toggle"}
            },
            "required": ["entity_id", "action"]
        }
    }
]

def execute_ha(params):
    """Helper to call Home Assistant API"""
    if "Bearer" not in HA_TOKEN: return "Error: Check HA_TOKEN format."
    try:
        entity, action = params.get("entity_id"), params.get("action")
        domain = entity.split(".")[0]
        url = f"{HA_URL}/api/services/{domain}/{action}"
        headers = {"Authorization": HA_TOKEN, "Content-Type": "application/json"}
        resp = requests.post(url, json={"entity_id": entity}, headers=headers, timeout=3)
        return f"Home Assistant: {entity} -> {action} ({resp.status_code})"
    except Exception as e:
        return f"HA Error: {e}"

async def run_bridge():
    print("\n🚀 VENUS SYSTEM ONLINE (Stable v2.0)")
    print(f"🔗 Target: {MCP_ENDPOINT[:30]}...")

    # 1. Start Windows MCP (Quiet Mode)
    env = os.environ.copy()
    env["FASTMCP_NO_BANNER"] = "1" 
    env["FASTMCP_QUIET"] = "1"
    
    # Keep the tool process alive globally
    process = subprocess.Popen(
        [sys.executable, "-m", "windows_mcp"], 
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
        text=True, bufsize=0, env=env
    )
    print("💻 Windows Tool: Running.")

    # Reconnection Loop
    while True:
        try:
            print("⏳ Connecting to Cloud...")
            # PING INTERVAL 10s = Aggressive Keep-alive
            async with websockets.connect(MCP_ENDPOINT, ping_interval=10, ping_timeout=10) as ws:
                print("✅ CLOUD CONNECTED! Ready.")
                
                # Reset Handshake state
                handshake_done = False

                # Task A: Read from Windows -> Send to Cloud
                async def windows_to_cloud():
                    nonlocal handshake_done
                    while True:
                        line = await asyncio.to_thread(process.stdout.readline)
                        if not line: break
                        
                        # Filter junk logs
                        if not line.strip().startswith('{'): continue
                        
                        try:
                            data = json.loads(line)
                            
                            # CRITICAL: Always inject HA tools into the Tool List
                            if "result" in data and "tools" in data["result"]:
                                print("💉 Injecting Tools (Re-Handshake)...")
                                data["result"]["tools"].extend(HA_TOOLS_INJECTION)
                                line = json.dumps(data)
                                handshake_done = True
                            
                            await ws.send(line)
                        except: pass

                # Task B: Read from Cloud -> Route to Windows OR Home Assistant
                async def cloud_to_windows():
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            # Handle Ping (Keepalive)
                            if data.get("method") == "ping":
                                await ws.send(json.dumps({"jsonrpc": "2.0", "result": "pong", "id": data.get("id")}))
                                continue

                            # ROUTING LOGIC
                            if data.get("method") == "tools/call":
                                tool_name = data["params"]["name"]
                                
                                # Route 1: Home Assistant
                                if tool_name == "ha_control":
                                    print(f"🏠 HA Action: {data['params']['arguments']}")
                                    res_txt = await asyncio.to_thread(execute_ha, data["params"]["arguments"])
                                    
                                    # Reply to Cloud manually
                                    resp = {"jsonrpc": "2.0", "id": data["id"], "result": {"content": [{"type": "text", "text": res_txt}]}}
                                    await ws.send(json.dumps(resp))
                                    continue 

                                # Route 2: Windows MCP
                                print(f"💻 Windows Action: {tool_name}")

                            # Forward standard packets to Windows MCP
                            json_str = json.dumps(data) + "\n"
                            process.stdin.write(json_str)
                            
                        except Exception as e:
                            print(f"❌ Routing Error: {e}")

                # Heartbeat Task (Visual indicator)
                async def visual_heartbeat():
                    while True:
                        await asyncio.sleep(10)
                        print(".", end="", flush=True)

                # Run everything until connection drops
                await asyncio.gather(windows_to_cloud(), cloud_to_windows(), visual_heartbeat())

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
            print("\n⚠️ Connection lost. Reconnecting in 2s...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"\n❌ Critical Error: {e}. Restarting...")
            await asyncio.sleep(2)

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try: asyncio.run(run_bridge())
    except KeyboardInterrupt: print("\n🛑 System Offline.")
