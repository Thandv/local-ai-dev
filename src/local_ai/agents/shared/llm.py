"""
Multi-backend LLM client: Ollama (local) or Claude API (cloud).

Select via LOCAL_AI_MODEL env var or set_model() / --model flag:
  Ollama (default):  qwen2.5-coder:32b
  Claude (best):     claude-opus-4-7   (requires ANTHROPIC_API_KEY)

Both backends stream tokens to stdout and return the same message dict.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Optional

# ── Backend selection ─────────────────────────────────────────────────────────

OLLAMA_URL    = "http://localhost:11434/api/chat"
DEFAULT_MODEL = os.environ.get("LOCAL_AI_MODEL", "qwen2.5-coder:32b")
_ACTIVE_MODEL = DEFAULT_MODEL


def set_model(model: str):
    """Override the active model at runtime (e.g. from --model CLI flag)."""
    global _ACTIVE_MODEL
    _ACTIVE_MODEL = model


def get_model() -> str:
    return _ACTIVE_MODEL


def _is_claude(model: str) -> bool:
    return model.startswith("claude")


# ── Ollama backend ─────────────────────────────────────────────────────────────

def _ollama_chat(messages: list, tools: list, model: str, timeout: int) -> dict:
    """Streaming Ollama call. Prints tokens live; returns assembled message dict."""
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "tools":    tools or [],
        "stream":   True,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    content    = ""
    tool_calls = None
    retries    = 3
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg_chunk = chunk.get("message", {})
                    delta = msg_chunk.get("content") or ""
                    if delta:
                        print(delta, end="", flush=True)
                        content += delta
                    if msg_chunk.get("tool_calls"):
                        tool_calls = msg_chunk["tool_calls"]
                    if chunk.get("done"):
                        if content:
                            print()
                        break
            break  # success
        except urllib.error.URLError as e:
            if attempt == retries:
                print(
                    f"\n[LLM] Cannot reach Ollama after {retries} attempts — "
                    f"is it running? (`brew services start ollama`)\n{e}"
                )
                sys.exit(1)
            wait = 2 ** attempt
            print(f"\n[LLM] Connection error (attempt {attempt}/{retries}), retrying in {wait}s …")
            time.sleep(wait)

    return {"role": "assistant", "content": content, "tool_calls": tool_calls}


# ── Claude backend ─────────────────────────────────────────────────────────────

def _to_claude_messages(messages: list) -> tuple[str, list]:
    """Convert internal Ollama-format messages to Claude API format.

    System messages → top-level `system` string.
    Tool results    → user content blocks with tool_use_id.
    Assistant msgs  → content blocks (text + tool_use).
    """
    system_parts: list[str] = []
    out: list[dict] = []

    for m in messages:
        role    = m["role"]
        content = m.get("content", "")

        if role == "system":
            system_parts.append(content)

        elif role == "tool":
            block = {
                "type":        "tool_result",
                "tool_use_id": m.get("tool_use_id", "unknown"),
                "content":     content,
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})

        elif role == "assistant":
            blocks: list[dict] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in (m.get("tool_calls") or []):
                blocks.append({
                    "type":  "tool_use",
                    "id":    tc.get("id", f"call_{len(blocks)}"),
                    "name":  tc["function"]["name"],
                    "input": tc["function"].get("arguments", {}),
                })
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})

        else:  # user
            out.append({"role": "user", "content": content})

    return "\n".join(system_parts), out


def _openai_tools_to_claude(tools: list) -> list:
    return [
        {
            "name":         t["function"]["name"],
            "description":  t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in (tools or [])
        if "function" in t
    ]


def _claude_chat(messages: list, tools: list, model: str, timeout: int) -> dict:
    """Streaming Claude API call. Prints tokens live; returns normalized message dict."""
    try:
        import anthropic
    except ImportError:
        print("\n[LLM] anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n[LLM] ANTHROPIC_API_KEY not set. Export it to use the Claude backend.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    system, claude_msgs = _to_claude_messages(messages)
    claude_tools = _openai_tools_to_claude(tools)

    kwargs: dict = {
        "model":      model,
        "max_tokens": 8192,
        "messages":   claude_msgs,
    }
    if system:
        kwargs["system"] = system
    if claude_tools:
        kwargs["tools"] = claude_tools

    accumulated = ""
    tool_calls: list = []

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            accumulated += text
        final = stream.get_final_message()

    if accumulated:
        print()

    for block in final.content:
        if block.type == "tool_use":
            tool_calls.append({
                "id":       block.id,
                "function": {"name": block.name, "arguments": block.input},
            })

    return {
        "role":       "assistant",
        "content":    accumulated,
        "tool_calls": tool_calls or None,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def chat(messages: list, tools: list = None, timeout: int = 180) -> dict:
    """
    Single LLM call. Routes to Ollama or Claude based on the active model.
    Streams tokens to stdout and returns the assembled message dict:
      {"role": "assistant", "content": str, "tool_calls": list | None}
    """
    model = _ACTIVE_MODEL
    if _is_claude(model):
        return _claude_chat(messages, tools, model, timeout)
    return _ollama_chat(messages, tools, model, timeout)


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
                    obj = json.loads(content[start: i + 1])
                    if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                        calls.append({
                            "function": {"name": obj["name"], "arguments": obj["arguments"]}
                        })
                except json.JSONDecodeError:
                    pass
                start = None
    return calls or None


def run_agent_loop(
    system: str,
    user: str,
    tools: list,
    handlers: dict,
    history: list = None,
    on_tool_call=None,
) -> str:
    """
    Full agentic loop:
      1. Call the model with system + user prompt (streaming tokens to stdout)
      2. If it returns tool calls, execute them and feed results back
      3. Repeat until a plain-text response is returned

    Tool call IDs (present when using Claude) are forwarded in tool result
    messages so the Claude backend can reconstruct its conversation format.
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
            name        = call["function"]["name"]
            raw         = call["function"].get("arguments", {})
            args        = json.loads(raw) if isinstance(raw, str) else raw
            tool_use_id = call.get("id")  # present for Claude tool calls

            if on_tool_call:
                on_tool_call(name, args)

            handler = handlers.get(name)
            result  = handler(**args) if handler else f"Unknown tool: {name}"

            tool_msg: dict = {"role": "tool", "content": result}
            if tool_use_id:
                tool_msg["tool_use_id"] = tool_use_id
            messages.append(tool_msg)

    return messages[-1].get("content", "").strip()
