"""
Shared Ollama LLM client used by all agents.
Handles the tool-call loop: call model → execute tools → repeat until done.
"""

import json
import urllib.request
import urllib.error
import sys
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "qwen2.5-coder:7b"


def chat(messages: list, tools: list = None, timeout: int = 180) -> dict:
    """Single Ollama chat call. Returns the raw message dict."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": tools or [],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())["message"]
    except urllib.error.URLError as e:
        print(f"\n[LLM] Cannot reach Ollama — is it running? (`brew services start ollama`)\n{e}")
        sys.exit(1)


def _extract_tool_calls(content: str) -> Optional[list]:
    """Pull tool-call JSON objects that some models embed in the content field."""
    if not content:
        return None
    calls, depth, start = [], 0, None
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(content[start : i + 1])
                    if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                        calls.append({
                            "function": {"name": obj["name"], "arguments": obj["arguments"]}
                        })
                except json.JSONDecodeError:
                    pass
                start = None
    return calls or None


def run_agent_loop(system: str, user: str, tools: list, handlers: dict,
                   history: list = None, on_tool_call=None) -> str:
    """
    Full agentic loop:
      1. Call model with system + user prompt
      2. If it returns tool calls, execute them and feed results back
      3. Repeat until a plain text response is returned

    Args:
        system:      System prompt for this agent
        user:        User message / task
        tools:       Tool definitions (list of dicts)
        handlers:    {tool_name: callable(**args) -> str}
        history:     Optional prior message history to continue from
        on_tool_call: Optional callback(name, args) for progress logging
    Returns:
        Final text reply from the model
    """
    messages = list(history or [])
    messages.insert(0, {"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    MAX_ROUNDS = 20
    for _ in range(MAX_ROUNDS):
        msg = chat(messages, tools=tools)
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or _extract_tool_calls(msg.get("content", ""))

        if not tool_calls:
            return msg.get("content", "").strip()

        for call in tool_calls:
            name = call["function"]["name"]
            raw  = call["function"].get("arguments", {})
            args = json.loads(raw) if isinstance(raw, str) else raw

            if on_tool_call:
                on_tool_call(name, args)

            handler = handlers.get(name)
            result  = handler(**args) if handler else f"Unknown tool: {name}"
            messages.append({"role": "tool", "content": result})

    return messages[-1].get("content", "").strip()
