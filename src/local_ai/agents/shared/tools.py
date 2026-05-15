"""
Shared tool implementations and Ollama tool-schema definitions.
All agents import from here so tool behaviour is consistent.
"""

import subprocess
import glob as _glob
from pathlib import Path
from typing import Optional

MAX_OUTPUT = 10_000  # chars — truncate large outputs


# ── Implementations ───────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {path}"
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT] + f"\n[truncated — {len(text)} chars total]"
        return text
    except Exception as e:
        return f"Error reading {path}: {e}"


def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written: {path} ({len(content)} chars)"


def list_files(pattern: str) -> str:
    matches = _glob.glob(pattern, recursive=True)
    return "\n".join(sorted(matches)) if matches else f"No files matching: {pattern}"


def run_command(command: str, working_dir: Optional[str] = None) -> str:
    cwd = Path(working_dir).expanduser() if working_dir else Path.cwd()
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=120
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n[truncated]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"
    except Exception as e:
        return f"Error: {e}"


def search_code(pattern: str, directory: str = ".") -> str:
    try:
        result = subprocess.run(
            ["grep", "-rn", "-i",
             "--include=*.py", "--include=*.ts", "--include=*.tsx",
             "--include=*.js", "--include=*.jsx", "--include=*.json",
             "--include=*.css", "--include=*.html", "--include=*.md",
             pattern, directory],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout
        if not out.strip():
            return f"No matches for '{pattern}' in {directory}"
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n[truncated]"
        return out
    except Exception as e:
        return f"Error: {e}"


def grep_repos(keywords: list, repos_dir: str = None) -> str:
    """Search cloned reference repos for patterns matching any of the keywords."""
    import re
    repos = Path(repos_dir or Path.home() / ".local-ai" / "repos")
    if not repos.exists():
        return "No reference repos found. Run: ai-index"

    skip = {"node_modules", ".git", "__pycache__", ".next", "dist", "build",
            ".venv", "venv", "test_", "_test", ".min.", "migration"}

    snippets, seen = [], set()
    for kw in keywords[:5]:
        if len(snippets) >= 6:
            break
        try:
            r = subprocess.run(
                ["grep", "-rl", "--include=*.py", "--include=*.ts",
                 "--include=*.tsx", "--include=*.js", "-i", kw, str(repos)],
                capture_output=True, text=True, timeout=5
            )
            for fpath in r.stdout.splitlines():
                if fpath in seen or len(snippets) >= 6:
                    break
                if any(s in fpath for s in skip):
                    continue
                seen.add(fpath)
                lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").splitlines()
                start = next((max(0, i - 3) for i, l in enumerate(lines)
                              if kw.lower() in l.lower()), 0)
                chunk = "\n".join(lines[start : start + 35])
                repo  = Path(fpath).relative_to(repos).parts[0]
                rel   = "/".join(Path(fpath).relative_to(repos).parts[1:])
                snippets.append(f"### {repo} / {rel}\n```\n{chunk}\n```")
        except Exception:
            continue

    return "\n\n".join(snippets) if snippets else "No relevant patterns found in reference repos."


# ── Tool schemas (Ollama format) ──────────────────────────────────────────────

def make_tool(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
    }


READ_FILE   = make_tool("read_file",   "Read a file's contents.",
                        {"path": {"type": "string"}}, ["path"])

WRITE_FILE  = make_tool("write_file",  "Write content to a file (creates dirs).",
                        {"path": {"type": "string"}, "content": {"type": "string"}},
                        ["path", "content"])

LIST_FILES  = make_tool("list_files",  "List files matching a glob pattern.",
                        {"pattern": {"type": "string"}}, ["pattern"])

RUN_COMMAND = make_tool("run_command", "Run a shell command and return output.",
                        {"command": {"type": "string"},
                         "working_dir": {"type": "string", "description": "Optional CWD"}},
                        ["command"])

SEARCH_CODE = make_tool("search_code", "Search for a pattern across source files.",
                        {"pattern": {"type": "string"},
                         "directory": {"type": "string", "description": "Directory to search"}},
                        ["pattern"])


HANDLERS = {
    "read_file":   read_file,
    "write_file":  write_file,
    "list_files":  list_files,
    "run_command": run_command,
    "search_code": search_code,
}
