from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
import httpx
import json
import uuid
import ipaddress
import re
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
    # Hostname — block obvious local names
    return host.endswith(".local") or host.endswith(".internal")


def tool_image_search(query: str) -> str:
    results = DDGS().images(query, max_results=4)
    if not results:
        return "No images found."
    # Return markdown image tags — marked.js renders these as <img>
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
    # Strip HTML tags
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


@app.get("/")
async def index():
    html = _jinja_env.get_template("index.html").render()
    return HTMLResponse(content=html)


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

        # Tool loop: non-streaming until model stops calling tools
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

                # status event — frontend shows as dim pill, not in bubble
                query = args.get("query") or args.get("url") or ""
                yield f"event: status\ndata: {json.dumps(name + ': ' + query)}\n\n"

                tool_result = await run_tool(name, args)
                history.append({"role": "tool", "content": tool_result})

                # Emit tool result directly so images appear immediately,
                # regardless of whether the model chooses to echo them
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
