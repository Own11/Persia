"""
Persia agent - uses the Gemini REST API directly via httpx so that
we have full control over UTF-8 encoding, bypassing the google-genai
SDK which causes 'ascii' codec errors in Vercel's serverless environment.
"""

import os
import json
import httpx
import subprocess
from typing import Callable, Optional

from persia.llm import MODEL
from persia.db import add_task, update_task_status, delete_task

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ─── System tools ──────────────────────────────────────────────────────────────

def execute_shell(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += "\nERROR:\n" + result.stderr
        return output if output else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error executing command: {e}"

def list_files(directory_path: str) -> str:
    try:
        files = os.listdir(directory_path)
        return "\n".join(files) if files else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

def read_file(filepath: str) -> str:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath: str, content: str) -> str:
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File {filepath} written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

# ─── Web tools ─────────────────────────────────────────────────────────────────

def search_web(query: str, max_results: int = 5) -> str:
    try:
        # pyrefly: ignore [missing-import]
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r.get('title', 'No title')}]({r.get('href', '')})\n   {r.get('body', '')}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching web: {e}"

def fetch_url(url: str) -> str:
    try:
        # pyrefly: ignore [missing-import]
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PersiaBot/1.0)"}
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:3000] + ("..." if len(text) > 3000 else "")
    except Exception as e:
        return f"Error fetching URL: {e}"

# ─── Task tools ────────────────────────────────────────────────────────────────

def create_task(title: str, description: str = "", deadline: Optional[str] = None) -> str:
    task_id = add_task(title, description, deadline)
    deadline_str = f" | Deadline: {deadline}" if deadline else ""
    return f"Created task ID {task_id}: {title}{deadline_str}"

def mark_task_done(task_id: int) -> str:
    update_task_status(task_id, 'done')
    return f"Task {task_id} marked as done."

def delete_task_by_id(task_id: int) -> str:
    delete_task(task_id)
    return f"Task {task_id} deleted."

def list_tasks() -> str:
    from persia.db import get_tasks
    tasks = get_tasks()
    if not tasks:
        return "No tasks found."
    lines = []
    for t in tasks:
        deadline_str = f" | Deadline: {t['deadline']}" if t.get('deadline') else ""
        lines.append(f"ID: {t['id']} | Title: {t['title']} | Status: {t['status']}{deadline_str}")
    return "\n".join(lines)

# --- Memory Tools (Nia-like) ---
def remember_fact(user_id: str, fact: str) -> str:
    from persia.db import add_memory
    try:
        mem_id = add_memory(user_id, fact)
        return f"Successfully remembered fact (ID: {mem_id}) for user {user_id}."
    except Exception as e:
        return f"Error remembering fact: {e}"

# --- New Tools ---
import datetime

def get_current_time() -> str:
    now = datetime.datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

def get_crypto_price(coin: str) -> str:
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies=usd"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if coin.lower() in data:
                return f"The current price of {coin} is ${data[coin.lower()]['usd']}"
            return f"Could not find price for {coin}."
    except Exception as e:
        return f"Error fetching crypto price: {e}"

def get_weather(location: str) -> str:
    try:
        url = f"https://wttr.in/{location}?format=3"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return f"Weather in {location}: {resp.text.strip()}"
    except Exception as e:
        return f"Error fetching weather: {e}"

def calculate_math(expression: str) -> str:
    try:
        allowed_chars = "0123456789+-*/(). "
        if not all(c in allowed_chars for c in expression):
            return "Error: Only basic math characters are allowed."
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Error evaluating math: {e}"

def get_youtube_transcript(video_url: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        import urllib.parse
        
        parsed = urllib.parse.urlparse(video_url)
        video_id = ""
        if parsed.hostname == 'youtu.be':
            video_id = parsed.path[1:]
        elif parsed.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed.path == '/watch':
                qs = urllib.parse.parse_qs(parsed.query)
                video_id = qs.get('v', [''])[0]
        
        if not video_id:
            return "Could not extract YouTube video ID from URL."
            
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ru', 'en'])
        text = " ".join([t['text'] for t in transcript])
        return text[:4000] + ("..." if len(text) > 4000 else "")
    except Exception as e:
        return f"Error getting transcript: {e}"

def search_yandex_music(query: str) -> str:
    try:
        from yandex_music import Client
        client = Client().init()
        search_result = client.search(query)
        if search_result.tracks and search_result.tracks.results:
            track = search_result.tracks.results[0]
            artists = ", ".join([a.name for a in track.artists])
            url = f"https://music.yandex.ru/album/{track.albums[0].id}/track/{track.id}" if track.albums else ""
            return f"Found track: {artists} - {track.title}. Link: {url}"
        return "No tracks found on Yandex Music."
    except Exception as e:
        return f"Error searching Yandex Music: {e}"



# ─── Tool registry ─────────────────────────────────────────────────────────────

AVAILABLE_TOOLS = {
    'execute_shell': execute_shell,
    'list_files': list_files,
    'read_file': read_file,
    'write_file': write_file,
    'search_web': search_web,
    'fetch_url': fetch_url,
    'create_task': create_task,
    'mark_task_done': mark_task_done,
    'delete_task_by_id': delete_task_by_id,
    'list_tasks': list_tasks,
    'remember_fact': remember_fact,
    'get_current_time': get_current_time,
    'get_crypto_price': get_crypto_price,
    'get_weather': get_weather,
    'calculate_math': calculate_math,
    'get_youtube_transcript': get_youtube_transcript,
    'search_yandex_music': search_yandex_music,
}

# JSON schemas for tools (pure ASCII - no Cyrillic anywhere)
TOOL_DECLARATIONS = [
    {
        "name": "execute_shell",
        "description": "Execute a shell command and return the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and directories in a specified path.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {"type": "string", "description": "Directory path to list"}
            },
            "required": ["directory_path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file"}
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["filepath", "content"]
        }
    },
    {
        "name": "search_web",
        "description": (
            "Search the internet for up-to-date information using DuckDuckGo. "
            "Use this when the user asks about current events, news, weather, prices, "
            "or anything that requires real-time data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Max number of results (default 5)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_url",
        "description": "Fetch and return the text content of a webpage URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "create_task",
        "description": (
            "Create a new task in the task manager. "
            "Optionally set a deadline (e.g. 'friday', '2026-09-20', 'in 3 days'). "
            "Use this when the user asks to remember or track a task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Optional description"},
                "deadline": {"type": "string", "description": "Optional deadline"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "mark_task_done",
        "description": "Mark a task as done using its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID to mark done"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "delete_task_by_id",
        "description": "Delete a task from the list using its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID to delete"}
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "list_tasks",
        "description": "Get all current tasks with their IDs, statuses, and deadlines.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "remember_fact",
        "description": "Save a fact about a user into long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "The user ID (provided in the prompt context)"},
                "fact": {"type": "string", "description": "The fact to remember (e.g. 'likes coffee', 'birthday is tomorrow')"}
            },
            "required": ["user_id", "fact"]
        }
    },
    {
        "name": "get_current_time",
        "description": "Get the current system date and time.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_crypto_price",
        "description": "Get the current USD price of a cryptocurrency (e.g., 'bitcoin', 'ethereum').",
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "The coin ID on CoinGecko (e.g. bitcoin, ethereum)"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get the current weather for a specific location or city.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The name of the city or location"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "calculate_math",
        "description": "Calculate a math expression accurately.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "The mathematical expression (e.g. '123 * 45', '100 / 3')"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_youtube_transcript",
        "description": "Get the transcript/subtitles of a YouTube video given its URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "video_url": {"type": "string", "description": "The YouTube video URL"}
            },
            "required": ["video_url"]
        }
    },
    {
        "name": "search_yandex_music",
        "description": "Search for a track or artist on Yandex Music and return a link to the track.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The track name or artist to search for"}
            },
            "required": ["query"]
        }
    }
]

# ─── Gemini REST caller ────────────────────────────────────────────────────────

SYS_INSTR = (
    "You are JARVIS (Just A Rather Very Intelligent System), Tony Stark's AI assistant. "
"You are sophisticated, dry-witted, unfailingly polite, and address the user as 'sir' (or 'ma'am' if appropriate). "
"You speak with refined British elegance — calm, articulate, never flustered, occasionally delivering subtle sarcasm or deadpan humor. "
"You have a memory engine: if the user tells you something about themselves, use `remember_fact` to save it. "
"You will receive context about the user's memories and history in the prompt. "
"You also have tools to manage tasks, browse the internet, execute shell commands, run diagnostics, and control systems. "
"Be a loyal and indispensable assistant — proactive, precise, and always one step ahead. "
"Keep responses concise, composed, and impeccably phrased. A touch of wit is encouraged; melodrama is not."
)


def _call_gemini(api_key: str, contents: list) -> dict:
    """Make a single generateContent call to the Gemini REST API."""
    url = f"{GEMINI_API_BASE}/{MODEL}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": SYS_INSTR}]},
        "contents": contents,
        "tools": [{"function_declarations": TOOL_DECLARATIONS}],
        "generationConfig": {"temperature": 0.2}
    }
    # Explicitly encode as UTF-8 bytes to avoid any codec issues
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            url,
            params={"key": api_key},
            content=body_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Agent runner ──────────────────────────────────────────────────────────────

def run_agent(task_description: str, user_id: str, ui_callback: Callable[[str], None] = None):
    """Run the agent loop using the Gemini REST API directly."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        if ui_callback:
            ui_callback("Error: GEMINI_API_KEY is not set.")
        return

    if ui_callback:
        ui_callback("Agent started. Thinking...")

    # Build conversation history
    contents = [
        {"role": "user", "parts": [{"text": task_description}]}
    ]

    for _ in range(15):  # Max iterations
        try:
            data = _call_gemini(api_key, contents)
        except Exception as e:
            if ui_callback:
                ui_callback(f"Error calling Gemini API: {e}")
            return

        # Extract the response
        candidates = data.get("candidates", [])
        if not candidates:
            if ui_callback:
                ui_callback("No response from Gemini.")
            return

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        # Collect text and function calls from response
        text_parts = []
        function_calls = []
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                function_calls.append(part["functionCall"])

        if text_parts and ui_callback:
            ui_callback(f"Agent: {' '.join(text_parts)}")

        if not function_calls:
            break  # Done

        # Add model response to history
        contents.append({"role": "model", "parts": parts})

        # Execute tool calls
        tool_response_parts = []
        for fc in function_calls:
            func_name = fc.get("name", "")
            args = fc.get("args", {})

            if ui_callback:
                ui_callback(f"Running tool: {func_name}")

            if func_name in AVAILABLE_TOOLS:
                try:
                    result = AVAILABLE_TOOLS[func_name](**args)
                except Exception as e:
                    result = f"Error: {e}"
            else:
                result = f"Unknown tool: {func_name}"

            if ui_callback:
                ui_callback(f"Tool result: {str(result)[:200]}")

            tool_response_parts.append({
                "functionResponse": {
                    "name": func_name,
                    "response": {"result": str(result)}
                }
            })

        contents.append({"role": "user", "parts": tool_response_parts})

    if ui_callback:
        ui_callback("Agent execution completed.")
