from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
import asyncio
import httpx
import json
import os
import re
import subprocess
import time
import urllib.request
import urllib.error
import uuid
import ipaddress
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ddgs import DDGS

app = FastAPI()

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:cloud"
MAX_TOOL_ROUNDS = 5  # prevent infinite loops

sessions: dict[str, list[dict]] = {}

# --- Stats config (reads greenclaw data files directly) ---
_HOME = os.path.expanduser("~")
GREENCLAW_DIR   = os.path.expanduser(os.environ.get("GREENCLAW_DIR",   "~/greenclaw"))
SCHEDULES_DIR   = os.path.expanduser(os.environ.get("SCHEDULES_DIR",   "~/greenclaw/schedules"))
NOTES_FILE      = os.path.expanduser(os.environ.get("NOTES_FILE",      "~/notes.md"))
CC_LOG_FILE     = os.path.join(GREENCLAW_DIR, "cc_calls.jsonl")
MEMORY_DIR      = os.path.expanduser("~/.claude/projects/-home-mrgreen/memory")
SCHEDULE_STATE  = os.path.expanduser("~/.local/share/greenclaw/schedule.json")
GITHUB_REPO     = os.environ.get("GITHUB_REPO",  "mrgreen3/greenclaw")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "image_search",
            "description": (
                "Search for images on the web. Use this when the user asks to see, "
                "find, or show images of something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Image search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information, news, or facts. "
                "Use this when the user asks about recent events, people, places, "
                "or anything you are uncertain about."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch the text content of a public web page. "
                "Only use this to read a specific URL the user has provided "
                "or that appeared in search results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full HTTPS URL to fetch",
                    }
                },
                "required": ["url"],
            },
        },
    },
]


def _is_private_host(url: str) -> bool:
    """Block fetching local/private addresses."""
    match = re.match(r"https?://([^/:]+)", url)
    if not match:
        return True
    host = match.group(1)
    if host in ("localhost", "::1"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        pass
    return host.endswith(".local") or host.endswith(".internal")


def tool_image_search(query: str) -> str:
    results = DDGS().images(query, max_results=4)
    if not results:
        return "No images found."
    lines = [f"![{r.get('title', query)}]({r['image']})" for r in results if r.get("image")]
    return "\n".join(lines)


def tool_web_search(query: str) -> str:
    results = DDGS().text(query, max_results=6)
    if not results:
        return "No results found."
    lines = []
    for r in results:
        lines.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
    return "\n".join(lines)


async def tool_fetch_url(url: str) -> str:
    if not url.startswith("https://"):
        return "Error: only HTTPS URLs are allowed."
    if _is_private_host(url):
        return "Error: private/local addresses are not allowed."
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "greentea/1.0"})
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "text" not in ct and "json" not in ct:
            return "Error: non-text content type."
        text = resp.text
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000]


async def run_tool(name: str, args: dict) -> str:
    try:
        if name == "image_search":
            return tool_image_search(args.get("query", ""))
        if name == "web_search":
            return tool_web_search(args.get("query", ""))
        if name == "fetch_url":
            return await tool_fetch_url(args.get("url", ""))
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


async def ollama_once(messages: list, stream: bool = False) -> dict:
    """Single non-streaming call to Ollama. Returns parsed response dict."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "tools": TOOLS, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Stats helpers — read greenclaw data files directly (same machine)
# ---------------------------------------------------------------------------

def _parse_front_matter(text: str) -> dict:
    """Parse YAML-lite front matter from a markdown file."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def _get_system_stats() -> dict:
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        d, rem = divmod(int(secs), 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except Exception:
        uptime = "unknown"

    # CPU — two samples 0.5s apart
    cpu_pct = None
    try:
        def _cpu_times():
            with open("/proc/stat") as f:
                parts = f.readline().split()
            vals = [int(x) for x in parts[1:]]
            idle = vals[3]
            total = sum(vals)
            return idle, total
        i1, t1 = _cpu_times()
        time.sleep(0.5)
        i2, t2 = _cpu_times()
        dt = t2 - t1
        cpu_pct = round((1 - (i2 - i1) / dt) * 100, 1) if dt else 0.0
    except Exception:
        pass

    # RAM
    ram_used = ram_total = ram_pct = None
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.split()[0])
        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        used_kb  = total_kb - avail_kb
        ram_total = f"{total_kb // 1024} MB"
        ram_used  = f"{used_kb  // 1024} MB"
        ram_pct   = round(used_kb / total_kb * 100, 1) if total_kb else 0
    except Exception:
        pass

    # Disk
    disk_used = disk_total = disk_pct = None
    try:
        out = subprocess.check_output(["df", "-k", "/"], text=True).splitlines()
        parts = out[1].split()
        disk_total = f"{int(parts[1]) // 1024} MB"
        disk_used  = f"{int(parts[2]) // 1024} MB"
        disk_pct   = parts[4]
    except Exception:
        pass

    # Load
    load = None
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        load = f"{parts[0]} {parts[1]} {parts[2]}"
    except Exception:
        pass

    # Hostname
    hostname = None
    try:
        hostname = subprocess.check_output(["hostname"], text=True).strip()
    except Exception:
        pass

    return {
        "hostname": hostname,
        "uptime":   uptime,
        "cpu_pct":  cpu_pct,
        "ram_used": ram_used,
        "ram_total": ram_total,
        "ram_pct":  ram_pct,
        "disk_used": disk_used,
        "disk_total": disk_total,
        "disk_pct": disk_pct,
        "load":     load,
    }


def _get_cc_stats() -> dict:
    today_str = time.strftime("%Y-%m-%d")
    week_ago  = time.time() - 7 * 86400
    today_count = week_count = 0
    recent_prompts: list[str] = []

    if os.path.exists(CC_LOG_FILE):
        try:
            with open(CC_LOG_FILE) as f:
                lines = f.readlines()
            for line in lines:
                try:
                    r = json.loads(line)
                    ts = r.get("ts", "")
                    prompt = r.get("prompt", "").strip()
                    # Strip injected context blocks
                    prompt = re.sub(r"^\[Current date.*?\]\s*", "", prompt, flags=re.DOTALL)
                    prompt = re.sub(r"--- long-term memory ---.*?---", "", prompt, flags=re.DOTALL)
                    prompt = re.sub(r"--- recent conversation ---.*", "", prompt, flags=re.DOTALL).strip()
                    if ts.startswith(today_str):
                        today_count += 1
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts)
                        if dt.timestamp() >= week_ago:
                            week_count += 1
                    except Exception:
                        pass
                    if prompt:
                        recent_prompts.append(prompt[:100])
                except Exception:
                    continue
            recent_prompts = recent_prompts[-6:][::-1]
        except Exception:
            pass

    return {
        "today": today_count,
        "week":  week_count,
        "recent_prompts": recent_prompts,
    }


def _get_memory_vault() -> dict:
    if not os.path.isdir(MEMORY_DIR):
        return {"count": 0, "total_kb": 0, "files": []}
    files = []
    total = 0
    for fn in sorted(os.listdir(MEMORY_DIR)):
        if not fn.endswith(".md") or fn == "MEMORY.md":
            continue
        path = os.path.join(MEMORY_DIR, fn)
        try:
            size = os.path.getsize(path)
            total += size
            files.append({"name": fn[:-3], "kb": round(size / 1024, 1)})
        except OSError:
            pass
    return {"count": len(files), "total_kb": round(total / 1024, 1), "files": files}


def _get_schedules() -> list:
    if not os.path.isdir(SCHEDULES_DIR):
        return []
    state = {}
    if os.path.exists(SCHEDULE_STATE):
        try:
            with open(SCHEDULE_STATE) as f:
                state = json.load(f)
        except Exception:
            pass
    scheds = []
    for fn in sorted(os.listdir(SCHEDULES_DIR)):
        if not fn.endswith(".md"):
            continue
        try:
            with open(os.path.join(SCHEDULES_DIR, fn)) as f:
                meta = _parse_front_matter(f.read())
            name = meta.get("name") or fn[:-3]
            sched_time = meta.get("schedule", "")
            last_ran = state.get(name, "")
            # Shorten last_ran to date+time
            if last_ran and "T" in last_ran:
                last_ran = last_ran[:16].replace("T", " ")
            scheds.append({"name": name, "time": sched_time, "last_ran": last_ran})
        except Exception:
            continue
    return scheds


def _get_notes() -> list:
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-6:][::-1]
    except Exception:
        return []


def _get_github_issues() -> list:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues?state=open&per_page=10"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "greentea/1.0")
        if GITHUB_TOKEN:
            req.add_header("Authorization", f"token {GITHUB_TOKEN}")
        with urllib.request.urlopen(req, timeout=8) as r:
            items = json.loads(r.read())
        return [
            {"number": i["number"], "title": i["title"], "url": i["html_url"]}
            for i in items
            if "pull_request" not in i
        ]
    except Exception:
        return []


def _gather_all_stats() -> dict:
    return {
        "system":    _get_system_stats(),
        "cc":        _get_cc_stats(),
        "memory":    _get_memory_vault(),
        "schedules": _get_schedules(),
        "notes":     _get_notes(),
        "issues":    _get_github_issues(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    html = _jinja_env.get_template("index.html").render()
    return HTMLResponse(content=html)


@app.get("/stats")
async def stats():
    data = await asyncio.to_thread(_gather_all_stats)
    return JSONResponse(content=data)


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id") or str(uuid.uuid4())

    if session_id not in sessions:
        sessions[session_id] = []

    sessions[session_id].append({"role": "user", "content": message})

    async def generate():
        history = sessions[session_id]

        for _ in range(MAX_TOOL_ROUNDS):
            result = await ollama_once(history)
            msg = result.get("message", {})
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                content = msg.get("content", "")
                if content:
                    history.append({"role": "assistant", "content": content})
                    for word in content.split(" "):
                        yield f"data: {json.dumps(word + ' ')}\n\n"
                yield "data: [DONE]\n\n"
                return

            history.append(msg)

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                query = args.get("query") or args.get("url") or ""
                yield f"event: status\ndata: {json.dumps(name + ': ' + query)}\n\n"

                tool_result = await run_tool(name, args)
                history.append({"role": "tool", "content": tool_result})

                if name == "image_search" and tool_result and not tool_result.startswith("Error"):
                    yield f"event: tool_result\ndata: {json.dumps(tool_result)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/clear")
async def clear(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "")
    sessions.pop(session_id, None)
    return JSONResponse(status_code=200, content={"cleared": session_id})


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_server:app", host="0.0.0.0", port=8766, reload=False)
