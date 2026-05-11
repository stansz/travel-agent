#!/usr/bin/env python3
"""Travel Agent Chat — FastAPI backend with Pi agent (travel-only, no coding tools)."""

import asyncio
import os
import urllib.parse

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from docx import Document
from docx.shared import Pt, Inches
import io
import re

app = FastAPI(title="Travel Agent")

PI_CMD = "pi"
PI_PROVIDER = os.environ.get("PI_PROVIDER", "zai")
PI_MODEL = os.environ.get("PI_MODEL", "glm-5-turbo")
PI_SKILL = "/app/web/pi-skill.md"
HIMALAYA = os.environ.get("HIMALAYA", "himalaya")

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


@app.post("/email")
async def email(request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    to = body.get("to", "").strip()
    if not text or not to:
        return JSONResponse({"error": "Missing text or email address"}, status_code=400)

    try:
        await send_email(text, to)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/download")
async def download(text: str = Query(""), fmt: str = Query("md")):
    if not text:
        return PlainTextResponse("No content", status_code=400)

    if fmt == "docx":
        docx_bytes = markdown_to_docx(text)
        headers = {"Content-Disposition": "attachment; filename=travel-info.docx"}
        return Response(docx_bytes, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)
    else:
        headers = {"Content-Disposition": "attachment; filename=travel-info.md"}
        return PlainTextResponse(text, media_type="text/markdown", headers=headers)


def markdown_to_docx(md_text: str) -> bytes:
    """Convert Markdown to a simple DOCX with basic formatting."""
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    for line in md_text.split('\n'):
        if line.startswith('### '):
            p = doc.add_heading(line[4:], level=3)
        elif line.startswith('## '):
            p = doc.add_heading(line[3:], level=2)
        elif line.startswith('# '):
            p = doc.add_heading(line[2:], level=1)
        elif line.startswith('|') and '|' in line[1:]:
            # Skip table formatting lines, just add as text for now
            if '---' in line.replace('|', '').replace('-', '').replace(' ', ''):
                continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if cells:
                doc.add_paragraph('  •  '.join(cells))
        elif line.strip().startswith(('• ', '- ', '* ')):
            doc.add_paragraph(line.strip(), style='List Bullet')
        elif line.strip().startswith(('1. ', '2. ', '3. ')):
            doc.add_paragraph(line.strip(), style='List Number')
        elif line.strip():
            # Bold/italic conversion
            p = doc.add_paragraph()
            parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                elif part.startswith('*') and part.endswith('*'):
                    run = p.add_run(part[1:-1])
                    run.italic = True
                else:
                    p.add_run(part)
        else:
            doc.add_paragraph()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def run_pi(message: str) -> str:
    cmd = [
        PI_CMD, "--provider", PI_PROVIDER, "--model", PI_MODEL,
        "--no-session", "--no-builtin-tools", "--no-skills",
        "--tools", "bash", "--system-prompt", TRAVEL_SYSTEM_PROMPT,
        "--thinking", "off", "-p", message,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        return "Sorry, the travel search took too long. Please try a more specific query."
    return stdout.decode("utf-8", errors="replace").strip() or "I couldn't find any results for that query."


async def send_email(text: str, to: str) -> None:
    """Send markdown email via himalaya CLI."""
    subject = "Travel Info"
    # Try to extract a title from the first heading
    first_line = text.strip().split("\n")[0]
    if first_line.startswith("#"):
        subject = first_line.lstrip("#").strip()[:80]
    elif first_line.startswith("**") and "**" in first_line[2:]:
        subject = first_line.strip("*").strip()[:80]

    proc = await asyncio.create_subprocess_exec(
        HIMALAYA, "write",
        "--subject", subject,
        "--header", "Content-Type: text/markdown; charset=utf-8",
        to,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(input=text.encode("utf-8")), timeout=30)
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or "Unknown error"
        raise RuntimeError(f"Himalaya failed: {err}")


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Travel Agent ✈️</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; flex-direction: column; height: 100vh; }
header { background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 12px; }
header h1 { font-size: 20px; font-weight: 600; }
header span { font-size: 24px; }
#chat { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
.msg { max-width: 75%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; position: relative; }
.msg.user { align-self: flex-end; background: #2563eb; color: #fff; }
.msg.agent { align-self: flex-start; background: #1e293b; border: 1px solid #334155; }
.msg.agent h1, .msg.agent h2, .msg.agent h3 { margin: 8px 0 4px; font-size: 1em; }
.msg.agent ul, .msg.agent ol { padding-left: 20px; margin: 4px 0; }
.msg.agent li { margin: 2px 0; }
.msg.agent code { background: #0f172a; padding: 1px 6px; border-radius: 4px; font-size: 0.9em; font-family: 'SF Mono', Monaco, monospace; }
.msg.agent pre { background: #0f172a; padding: 8px 12px; border-radius: 8px; overflow-x: auto; margin: 4px 0; font-size: 0.85em; }
.msg.loading { align-self: flex-start; color: #64748b; font-style: italic; }
.msg-actions { margin-top: 10px; display: flex; gap: 8px; opacity: 0; transition: opacity 0.2s; }
.msg:hover .msg-actions, .msg-actions.show { opacity: 1; }
.msg-btn { padding: 4px 10px; border-radius: 6px; border: 1px solid #334155; background: transparent; color: #64748b; font-size: 12px; cursor: pointer; transition: all 0.15s; }
.msg-btn:hover { background: #1e293b; border-color: #2563eb; color: #e2e8f0; }
.msg-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.email-popup { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 10; align-items: center; justify-content: center; }
.email-popup.open { display: flex; }
.email-popup-inner { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; width: 340px; }
.email-popup-inner input { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 14px; margin: 8px 0; }
.email-popup-inner button { padding: 8px 16px; border-radius: 8px; border: none; font-size: 13px; cursor: pointer; margin-right: 8px; }
.email-popup-inner .send-btn { background: #2563eb; color: #fff; }
.email-popup-inner .cancel-btn { background: #334155; color: #94a3b8; }
#input-area { padding: 16px 24px; background: #1e293b; border-top: 1px solid #334155; display: flex; gap: 12px; }
#input-area input { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; outline: none; }
#input-area input:focus { border-color: #2563eb; }
#input-area button { padding: 12px 24px; border-radius: 8px; border: none; background: #2563eb; color: #fff; font-size: 15px; font-weight: 600; cursor: pointer; }
#input-area button:hover { background: #1d4ed8; }
#input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
.preset-buttons { padding: 8px 24px; display: flex; gap: 8px; flex-wrap: wrap; }
.preset-buttons button { padding: 6px 14px; border-radius: 16px; border: 1px solid #334155; background: transparent; color: #94a3b8; font-size: 13px; cursor: pointer; white-space: nowrap; }
.preset-buttons button:hover { background: #1e293b; border-color: #2563eb; color: #e2e8f0; }
.toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #2563eb; color: #fff; padding: 10px 20px; border-radius: 8px; font-size: 14px; z-index: 100; opacity: 0; transition: opacity 0.3s; }
.toast.show { opacity: 1; }
</style>
</head>
<body>
<header><span>✈️</span><h1>Travel Agent</h1><span style="font-size:11px;color:#64748b;margin-left:auto">powered by Z.AI · Pi</span></header>
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
  <input type="text" id="input" placeholder="Ask about flights, weather, advisories..." onkeypress="if(event.key=='Enter') send()" autofocus>
  <button id="send-btn" onclick="send()">Send</button>
</div>
<div class="email-popup" id="emailPopup">
  <div class="email-popup-inner">
    <div style="color:#e2e8f0;font-weight:600;margin-bottom:4px;">✉️ Email this info</div>
    <input type="email" id="emailAddr" placeholder="you@example.com">
    <div style="margin-top: 12px;">
      <button class="send-btn" onclick="doEmail()">Send</button>
      <button class="cancel-btn" onclick="closeEmail()">Cancel</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btn = document.getElementById('send-btn');
let emailTargetText = '';

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
  
  if (role === 'agent' && text.length > 10) {
    const rawText = text;
    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = '<button class="msg-btn" title="Download as Markdown" onclick="downloadMd(this)">📥 .md</button> <button class="msg-btn" title="Download as Word Doc" onclick="downloadDocx(this)">📄 .docx</button> <button class="msg-btn" title="Email this" onclick="promptEmail(this)">✉️ Email</button>';
    actions.dataset.text = rawText;
    div.appendChild(actions);
  }
  
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
    const resp = await fetch('/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const data = await resp.json();
    loading.remove();
    addMsg(data.reply || 'No response', 'agent');
  } catch(e) { loading.remove(); addMsg('Error: '+e.message, 'agent'); }
  btn.disabled = false;
  input.focus();
}

function downloadMd(btn) {
  const text = btn.parentElement.dataset.text;
  const blob = new Blob([text], {type:'text/markdown'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'travel-info.md'; a.click();
  URL.revokeObjectURL(url);
}

async function downloadDocx(btn) {
  const text = btn.parentElement.dataset.text;
  const resp = await fetch('/download?fmt=docx&text=' + encodeURIComponent(text));
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'travel-info.docx'; a.click();
  URL.revokeObjectURL(url);
}

function promptEmail(btn) {
  emailTargetText = btn.parentElement.dataset.text;
  document.getElementById('emailPopup').classList.add('open');
  document.getElementById('emailAddr').focus();
}

function closeEmail() { document.getElementById('emailPopup').classList.remove('open'); }

async function doEmail() {
  const addr = document.getElementById('emailAddr').value.trim();
  if (!addr) return;
  closeEmail();
  const popup = document.getElementById('emailPopup');
  try {
    const resp = await fetch('/email', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:emailTargetText,to:addr})});
    const data = await resp.json();
    toast(data.ok ? 'Email sent! ✉️' : 'Failed: ' + (data.error||'unknown'));
  } catch(e) { toast('Error: '+e.message); }
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

function ask(q) { input.value = q; send(); }
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)
