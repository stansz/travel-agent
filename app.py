#!/usr/bin/env python3
"""Travel Agent Chat — FastAPI backend with Pi agent (travel-only, no coding tools)."""

import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Travel Agent")

PI_CMD = "pi"
PI_PROVIDER = os.environ.get("PI_PROVIDER", "zai")
PI_MODEL = os.environ.get("PI_MODEL", "glm-5-turbo")
PI_SKILL = "/app/web/pi-skill.md"

# Load skill content for system prompt
with open(PI_SKILL) as f:
    TRAVEL_SYSTEM_PROMPT = f.read()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(HTML_PAGE)


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    try:
        result = await run_pi(message)
        return JSONResponse({"reply": result})
    except Exception as e:
        return JSONResponse({"reply": f"Sorry, something went wrong: {e}"})


async def run_pi(message: str) -> str:
    """Invoke Pi agent — coding tools stripped, travel skill loaded."""
    cmd = [
        PI_CMD,
        "--provider", PI_PROVIDER,
        "--model", PI_MODEL,
        "--no-session",
        "--no-builtin-tools",
        "--no-skills",
        "--tools", "bash",
        "--system-prompt", TRAVEL_SYSTEM_PROMPT,
        "-p",
        message,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        return "Sorry, the travel search took too long. Please try a more specific query."

    return stdout.decode("utf-8", errors="replace").strip() or "I couldn't find any results for that query."


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Travel Agent ✈️</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f172a; color: #e2e8f0;
  display: flex; flex-direction: column; height: 100vh;
}
header {
  background: #1e293b; padding: 16px 24px;
  border-bottom: 1px solid #334155;
  display: flex; align-items: center; gap: 12px;
}
header h1 { font-size: 20px; font-weight: 600; }
header span { font-size: 24px; }
#chat {
  flex: 1; overflow-y: auto; padding: 20px 24px;
  display: flex; flex-direction: column; gap: 16px;
}
.msg { max-width: 75%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; }
.msg.user { align-self: flex-end; background: #2563eb; color: #fff; }
.msg.agent { align-self: flex-start; background: #1e293b; border: 1px solid #334155; }
.msg.agent h1, .msg.agent h2, .msg.agent h3 { margin: 8px 0 4px; font-size: 1em; }
.msg.agent ul, .msg.agent ol { padding-left: 20px; margin: 4px 0; }
.msg.agent li { margin: 2px 0; }
.msg.agent code {
  background: #0f172a; padding: 1px 6px; border-radius: 4px;
  font-size: 0.9em; font-family: 'SF Mono', Monaco, monospace;
}
.msg.agent pre {
  background: #0f172a; padding: 8px 12px; border-radius: 8px;
  overflow-x: auto; margin: 4px 0; font-size: 0.85em;
}
.msg.loading { align-self: flex-start; color: #64748b; font-style: italic; }
#input-area {
  padding: 16px 24px; background: #1e293b;
  border-top: 1px solid #334155; display: flex; gap: 12px;
}
#input-area input {
  flex: 1; padding: 12px 16px; border-radius: 8px;
  border: 1px solid #334155; background: #0f172a; color: #e2e8f0;
  font-size: 15px; outline: none;
}
#input-area input:focus { border-color: #2563eb; }
#input-area button {
  padding: 12px 24px; border-radius: 8px; border: none;
  background: #2563eb; color: #fff; font-size: 15px; font-weight: 600;
  cursor: pointer;
}
#input-area button:hover { background: #1d4ed8; }
#input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
.preset-buttons {
  padding: 8px 24px; display: flex; gap: 8px; flex-wrap: wrap;
}
.preset-buttons button {
  padding: 6px 14px; border-radius: 16px; border: 1px solid #334155;
  background: transparent; color: #94a3b8; font-size: 13px; cursor: pointer;
  white-space: nowrap;
}
.preset-buttons button:hover { background: #1e293b; border-color: #2563eb; color: #e2e8f0; }
</style>
</head>
<body>
<header>
  <span>✈️</span>
  <h1>Travel Agent</h1>
  <span style="font-size:11px;color:#64748b;margin-left:auto">powered by Z.AI · Pi</span>
</header>
<div id="chat">
  <div class="msg agent">
    👋 Hi! I'm your AI travel assistant. I can help with:<br><br>
    ✈️ <b>Flight prices & status</b> from Vancouver<br>
    🏨 <b>Hotel search</b> at your destination<br>
    🌤️ <b>Weather forecasts</b><br>
    ⚠️ <b>Travel advisories</b> (Canadian government)<br>
    💱 <b>Currency conversion</b><br>
    🔌 <b>Power plugs & emergency numbers</b><br>
    🗣️ <b>Translation & travel phrases</b><br><br>
    What can I help you plan?
  </div>
</div>
<div class="preset-buttons" id="presets">
  <button onclick="ask('Show me YVR flight deals')">🎫 YVR Deals</button>
  <button onclick="ask('Weather in Bangkok this week')">🌤️ Bangkok Weather</button>
  <button onclick="ask('Travel advisory for Thailand')">⚠️ Thailand Advisory</button>
  <button onclick="ask('Flights from YVR to Tokyo under $1000')">🇯🇵 Tokyo Flights</button>
  <button onclick="ask('What power plugs and currency does Japan use?')">🔌 Japan Info</button>
</div>
<div id="input-area">
  <input type="text" id="input" placeholder="Ask about flights, weather, advisories..."
         onkeypress="if(event.key=='Enter') send()" autofocus>
  <button id="send-btn" onclick="send()">Send</button>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btn = document.getElementById('send-btn');

function addMsg(text, role) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = text.replace(/\\n/g, '<br>');
  div.innerHTML = div.innerHTML
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^\\* (.+)$/gm, '• $1')
    .replace(/^- (.+)$/gm, '• $1');
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function send() {
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  btn.disabled = true;
  addMsg(msg, 'user');
  const loading = addMsg('Thinking...', 'loading');

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await resp.json();
    loading.remove();
    addMsg(data.reply || 'No response', 'agent');
  } catch(e) {
    loading.remove();
    addMsg('Error: ' + e.message, 'agent');
  }
  btn.disabled = false;
  input.focus();
}

function ask(q) { input.value = q; send(); }
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)
