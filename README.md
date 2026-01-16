

# 🌌 Project VENUS: Virtual Entity for Natural and User Support

**A 100% Private, Offline, Voice-Controlled Bridge between ESP32, Local AI, Windows, and IoT.**

Project VENUS allows you to control your Windows PC and Smart Home devices using a **Xiaozhi ESP32** device, completely offline. By hosting the "Brain" (DeepSeek/Ollama) and the "Server" locally, no voice data ever leaves your network.

---

## 🏗 Architecture

The system bridges three distinct worlds to ensure privacy and speed:

1. 
**The Hardware World:** Your ESP32 device acts as the microphone and speaker.


2. 
**The Brain World:** A local server converts speech to text and uses **DeepSeek** (via Ollama) to make decisions.


3. 
**The Action World:** Your commands are executed on Windows (e.g., "Open Calculator") or IoT devices (e.g., "Turn on Lights").



---

## 🚀 Prerequisites

* **Hardware:** Xiaozhi ESP32 Device (or compatible ESP32-S3 board).
* **OS:** Windows 10/11.
* **Software:**
* [Docker Desktop](https://www.docker.com/products/docker-desktop/)
* [Ollama](https://ollama.com/)
* [Python 3.10+](https://www.python.org/)

![Uploading Untitled diagram-2026-01-16-101208.png…]()



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
