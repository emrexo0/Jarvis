"""
JARVIS v2 – Hands (tools the model can call)
No-command architecture: the model decides what to do and calls these.
"""
import os
import subprocess
import webbrowser
import time
import platform
from pathlib import Path
from urllib.parse import quote_plus

from .config import logger, TEMP_DIR

# Optional automation
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.15
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    pyautogui = None

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed to open URL: {e}"


def open_youtube(query: str = "") -> str:
    """Open YouTube, optionally with a search."""
    if query:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    else:
        url = "https://www.youtube.com"
    return open_url(url)


def open_application(name: str) -> str:
    """Try to launch a common application by name."""
    system = platform.system()
    name_lower = name.lower().strip()
    mapping = {
        "chrome": ["chrome", "google-chrome", "google chrome"],
        "firefox": ["firefox"],
        "edge": ["msedge", "microsoft-edge"],
        "notepad": ["notepad"],
        "calculator": ["calc", "gnome-calculator", "calculator"],
        "terminal": ["cmd", "gnome-terminal", "konsole", "xterm"],
        "explorer": ["explorer", "nautilus", "dolphin"],
        "spotify": ["spotify"],
        "discord": ["discord"],
        "vscode": ["code", "code.cmd"],
        "steam": ["steam"],
    }
    candidates = mapping.get(name_lower, [name_lower])
    for cand in candidates:
        try:
            if system == "Windows":
                subprocess.Popen(cand, shell=True)
            else:
                subprocess.Popen([cand], start_new_session=True)
            return f"Launched {cand}"
        except Exception:
            continue
    # Fallback: try the raw name
    try:
        subprocess.Popen(name, shell=True)
        return f"Attempted to launch {name}"
    except Exception as e:
        return f"Could not launch {name}: {e}"


def type_text(text: str, interval: float = 0.03) -> str:
    """Type text using the keyboard (requires focus on target window)."""
    if not HAS_PYAUTOGUI:
        return "pyautogui not installed – cannot type. Install with: pip install pyautogui"
    try:
        pyautogui.write(text, interval=interval)
        return f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}"
    except Exception as e:
        return f"Typing failed: {e}"


def press_key(key: str) -> str:
    """Press a single key or hotkey (e.g. 'enter', 'ctrl+c')."""
    if not HAS_PYAUTOGUI:
        return "pyautogui not installed"
    try:
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return f"Pressed {key}"
    except Exception as e:
        return f"Key press failed: {e}"


def click_at(x: int, y: int, button: str = "left") -> str:
    """Click at absolute screen coordinates."""
    if not HAS_PYAUTOGUI:
        return "pyautogui not installed"
    try:
        pyautogui.click(x, y, button=button)
        return f"Clicked {button} at ({x}, {y})"
    except Exception as e:
        return f"Click failed: {e}"


def move_mouse(x: int, y: int) -> str:
    if not HAS_PYAUTOGUI:
        return "pyautogui not installed"
    try:
        pyautogui.moveTo(x, y, duration=0.25)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Move failed: {e}"


def screenshot_to_file(filename: str = None) -> str:
    """Take a full-screen screenshot and save it. Returns path."""
    if not HAS_PYAUTOGUI:
        # Fallback with PIL
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            path = filename or os.path.join(TEMP_DIR, f"screen_{int(time.time())}.png")
            img.save(path)
            return path
        except Exception as e:
            return f"Screenshot failed: {e}"
    try:
        path = filename or os.path.join(TEMP_DIR, f"screen_{int(time.time())}.png")
        pyautogui.screenshot(path)
        return path
    except Exception as e:
        return f"Screenshot failed: {e}"


def web_search(query: str, max_results: int = 6) -> str:
    """Search the web and return a short summary of results."""
    results = []
    if HAS_DDGS:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(f"- {r.get('title', '')}: {r.get('href', '')}\n  {r.get('body', '')[:120]}")
        except Exception as e:
            logger.warning(f"DDGS search error: {e}")
    if not results and HAS_REQUESTS:
        try:
            # Very light fallback
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json"
            resp = requests.get(url, timeout=8)
            data = resp.json()
            if data.get("AbstractText"):
                results.append(data["AbstractText"])
            for t in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(t, dict) and t.get("Text"):
                    results.append(t["Text"])
        except Exception:
            pass
    if not results:
        return f"No search results for '{query}'. (Install duckduckgo-search for better results)"
    return f"Search results for '{query}':\n" + "\n".join(results)


def get_system_info() -> str:
    """Return basic system information."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    return (
        f"CPU: {cpu}% | RAM: {mem.percent}% used "
        f"({mem.used // (1024**3)} / {mem.total // (1024**3)} GB) | "
        f"OS: {platform.system()} {platform.release()}"
    )


def run_shell(command: str, timeout: int = 15) -> str:
    """Run a shell command (use carefully). Returns stdout+stderr."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip()[:2000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Shell error: {e}"


# Tool registry that the Brain can expose to the model
TOOL_DEFINITIONS = [
    {
        "name": "open_url",
        "description": "Open any website URL in the default browser.",
        "parameters": {"url": "string – full or partial URL"}
    },
    {
        "name": "open_youtube",
        "description": "Open YouTube. Optionally search for a query.",
        "parameters": {"query": "string – optional search terms"}
    },
    {
        "name": "open_application",
        "description": "Launch a desktop application (chrome, notepad, terminal, spotify, vscode…).",
        "parameters": {"name": "string – application name"}
    },
    {
        "name": "type_text",
        "description": "Type text on the keyboard (target window must be focused).",
        "parameters": {"text": "string"}
    },
    {
        "name": "press_key",
        "description": "Press a key or hotkey (enter, ctrl+c, alt+tab, etc.).",
        "parameters": {"key": "string"}
    },
    {
        "name": "click_at",
        "description": "Click at absolute screen coordinates (x, y).",
        "parameters": {"x": "int", "y": "int", "button": "left|right (optional)"}
    },
    {
        "name": "move_mouse",
        "description": "Move mouse cursor to coordinates.",
        "parameters": {"x": "int", "y": "int"}
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the entire screen and save it. Returns the file path.",
        "parameters": {}
    },
    {
        "name": "web_search",
        "description": "Search the internet and return a summary of results.",
        "parameters": {"query": "string"}
    },
    {
        "name": "system_info",
        "description": "Get current CPU, RAM and OS information.",
        "parameters": {}
    },
    {
        "name": "run_shell",
        "description": "Execute a short shell command and return its output.",
        "parameters": {"command": "string"}
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Dispatch a tool call from the model."""
    name = name.lower().strip()
    try:
        if name == "open_url":
            return open_url(args.get("url", ""))
        if name == "open_youtube":
            return open_youtube(args.get("query", ""))
        if name == "open_application":
            return open_application(args.get("name", ""))
        if name == "type_text":
            return type_text(args.get("text", ""))
        if name == "press_key":
            return press_key(args.get("key", "enter"))
        if name == "click_at":
            return click_at(int(args.get("x", 0)), int(args.get("y", 0)),
                            args.get("button", "left"))
        if name == "move_mouse":
            return move_mouse(int(args.get("x", 0)), int(args.get("y", 0)))
        if name == "screenshot":
            return screenshot_to_file()
        if name == "web_search":
            return web_search(args.get("query", ""))
        if name == "system_info":
            return get_system_info()
        if name == "run_shell":
            return run_shell(args.get("command", ""))
        return f"Unknown tool: {name}"
    except Exception as e:
        logger.exception(f"Tool {name} crashed")
        return f"Tool error: {e}"
