

# 🌌 Project VENUS: Virtual Entity for Natural and User Support

**A 100% Private, Offline, Voice-Controlled Bridge between ESP32, Local AI, Windows, and IoT.**

Project VENUS allows you to control your Windows PC and Smart Home devices using a **Xiaozhi ESP32** device, completely offline. By hosting the "Brain" (DeepSeek/Ollama) and the "Server" locally, no voice data ever leaves your network.

---

## 🏗 Architecture

The system bridges three distinct worlds to ensure privacy and speed:

 
1.**The Hardware World:** Your ESP32 device acts as the microphone and speaker.



2.**The Brain World:** A local server converts speech to text and uses **DeepSeek** (via Ollama) to make decisions.


 
3.**The Action World:** Your commands are executed on Windows (e.g., "Open Calculator") or IoT devices (e.g., "Turn on Lights").


---

## 🚀 Prerequisites

* **Hardware:** Xiaozhi ESP32 Device (or compatible ESP32-S3 board).
* **OS:** Windows 10/11.
* **Software:**
* [Docker Desktop](https://www.docker.com/products/docker-desktop/)
* [Ollama](https://ollama.com/)
* [Python 3.10+](https://www.python.org/)


<img width="4143" height="5855" alt="Untitled diagram-2026-01-16-101208" src="https://github.com/user-attachments/assets/53ffed11-9bc4-4a60-ae02-4aeacb0808dd" />



## 📥 Installation Guide

### Step 1: Set up the "Brain" (Offline AI)

We use Ollama to run the AI model locally, ensuring no data goes to the cloud.

1. Download and install **Ollama**.
2. Open **PowerShell** and pull the DeepSeek model:
```powershell
ollama run deepseek-r1
# Or use deepseek-v3 depending on your hardware capability

```



*Result: You now have an offline AI brain running on port 11434.* 



### Step 2: Set up the Local Server

This docker container replaces the cloud server, handling the WebSocket connection from your ESP32.

1. Ensure Docker Desktop is running.
2. Run the following command in PowerShell:
```powershell
docker run -d --name xiaozhi-server -p 8000:8000 -p 8081:8081 xinnan-tech/xiaozhi-esp32-server

```



*Note: Ensure the server config points to your local Ollama instance (usually auto-detected or set in `config.yaml`).* 



### Step 3: Set up the "Hands" (Windows MCP)

This tool allows the AI to control your mouse, keyboard, and applications.

1. Install the Windows automation tool via pip:
```powershell
pip install windows-mcp

```



*This installs the core tool, but we need a bridge to connect it to the AI.* 



---

## 🌉 Step 4: The Bridge Script (The Coordinator)

This script connects the **Xiaozhi Server** to **Windows MCP**. It listens for tool calls from the AI and executes them on your PC.

1. Create a file named `mcp_bridge.py`.
2. Paste the following code:

```python
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

```


---

## ⚙️ Step 5: Configure Hardware (ESP32)

Finally, point your physical device to talk to your laptop instead of the internet.

1. Connect your ESP32 to your PC via USB.
2. Open the **Xiaozhi Config Page** (via its WiFi hotspot `Xiaozhi-Config` or serial tool).


3. Locate the **Server Endpoint** setting.
4. Change it from `wss://api.xiaozhi.me` to:
```text
ws://YOUR_LAPTOP_IP:8000

```



*(Find your IP by running `ipconfig` in PowerShell. Example: `192.168.1.15`)*.



---

## 🏠 IoT Integration (Home Assistant)

Project VENUS also supports controlling smart home devices alongside Windows apps.

To enable IoT control (e.g., "Turn on the lights"):

1. Ensure you have **Home Assistant** running locally.
2. Utilize the [Xiaozhi MCP Home Assistant Integration](https://github.com/mac8005/xiaozhi-mcp-ha).
3. Add the Home Assistant MCP server to your `mcp_bridge.py` logic to route "light" or "switch" commands to HA instead of Windows.



## 🛠️HARDWARE CONNECTIONS


![ChatBot AI Xiaozhi schematic](https://github.com/user-attachments/assets/5003dc0f-f44f-4114-9178-8a62c28ad930)



![Untitled presentation](https://github.com/user-attachments/assets/f89a7bc5-e1c4-45d9-88cd-9179a6a2e062)



---


## 🎮 Usage

1. **Start the Bridge:**
```powershell
python mcp_bridge.py

```


2. **Speak to your Device:**
* "Open Calculator." -> *Opens Windows Calculator*.


* "Turn on the studio lights." -> *Triggers Home Assistant*.




3. **Enjoy:** The entire process happens over your **Local WiFi**. Unplugging the internet router will not stop the system from working.


## 🚀 Future Roadmap
- [ ] Add support for Mac/Linux MCP.
- [ ] Integrate Spotify API for music control.
- [ ] Create a custom 3D printed case for the ESP32.
