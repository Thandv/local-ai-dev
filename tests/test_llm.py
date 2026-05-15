"""
Tests for agents/shared/llm.py — LLM client and agent loop.

Covers: _extract_tool_calls (positive, negative, edge), run_agent_loop
        (no tools, tool calls, unknown handler, MAX_ROUNDS, history),
        chat (happy path, URLError).
"""

import json
import sys
import pytest
from unittest.mock import MagicMock, patch, call

from local_ai.agents.shared.llm import _extract_tool_calls, run_agent_loop, chat

MAX_ROUNDS = 20  # matches the constant in llm.py


# ── _extract_tool_calls ───────────────────────────────────────────────────────

class TestExtractToolCalls:
    def test_none_input_returns_none(self):
        assert _extract_tool_calls(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_tool_calls("") is None

    def test_plain_text_returns_none(self):
        assert _extract_tool_calls("Hello, here is your answer.") is None

    def test_extracts_single_valid_call(self):
        content = '{"name": "read_file", "arguments": {"path": "/tmp/x.py"}}'
        result = _extract_tool_calls(content)
        assert result is not None
        assert len(result) == 1
        assert result[0]["function"]["name"] == "read_file"
        assert result[0]["function"]["arguments"]["path"] == "/tmp/x.py"

    def test_extracts_multiple_calls(self):
        c1 = '{"name": "read_file", "arguments": {"path": "a.py"}}'
        c2 = '{"name": "write_file", "arguments": {"path": "b.py", "content": "x"}}'
        result = _extract_tool_calls(f"{c1} some text {c2}")
        assert result is not None
        assert len(result) == 2
        names = {r["function"]["name"] for r in result}
        assert names == {"read_file", "write_file"}

    def test_dict_without_name_ignored(self):
        content = '{"key": "value", "other": 123}'
        assert _extract_tool_calls(content) is None

    def test_dict_with_name_but_no_arguments_ignored(self):
        content = '{"name": "foo"}'
        assert _extract_tool_calls(content) is None

    def test_malformed_json_not_extracted(self):
        content = '{"name": "tool", "arguments": {missing_quote: true}}'
        result = _extract_tool_calls(content)
        assert result is None

    def test_nested_json_inner_object_ignored(self):
        # Outer has name+arguments but inner doesn't — only outer should be extracted
        content = '{"name": "outer_tool", "arguments": {"inner": {"key": "val"}}}'
        result = _extract_tool_calls(content)
        assert result is not None
        assert len(result) == 1
        assert result[0]["function"]["name"] == "outer_tool"

    def test_text_around_json_ignored(self):
        content = 'Some preamble {"name": "list_files", "arguments": {"pattern": "*.py"}} trailing'
        result = _extract_tool_calls(content)
        assert result is not None
        assert result[0]["function"]["name"] == "list_files"

    def test_arguments_can_be_empty_dict(self):
        content = '{"name": "run_command", "arguments": {}}'
        result = _extract_tool_calls(content)
        assert result is not None
        assert result[0]["function"]["arguments"] == {}

    def test_string_values_in_arguments_preserved(self):
        content = '{"name": "write_file", "arguments": {"path": "x.py", "content": "hello"}}'
        result = _extract_tool_calls(content)
        assert result[0]["function"]["arguments"]["content"] == "hello"

    def test_unbalanced_braces_returns_none(self):
        assert _extract_tool_calls("{{{broken") is None


# ── run_agent_loop ────────────────────────────────────────────────────────────

class TestRunAgentLoop:
    def _make_text_response(self, text="Done."):
        return {"role": "assistant", "content": text, "tool_calls": None}

    def _make_tool_response(self, name, args):
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": args}}],
        }

    def test_immediate_text_response(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("All done!")]
        result = run_agent_loop("sys", "user", [], {})
        assert result == "All done!"

    def test_strips_whitespace_from_response(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("  hello  \n")]
        result = run_agent_loop("sys", "user", [], {})
        assert result == "hello"

    def test_tool_call_then_text(self, mock_chat):
        handler = MagicMock(return_value="file contents")
        mock_chat.side_effect = [
            self._make_tool_response("read_file", {"path": "x.py"}),
            self._make_text_response("Read successfully."),
        ]
        result = run_agent_loop("sys", "user", [], {"read_file": handler})
        assert result == "Read successfully."
        handler.assert_called_once_with(path="x.py")

    def test_multiple_tool_calls_in_sequence(self, mock_chat):
        handler_a = MagicMock(return_value="result_a")
        handler_b = MagicMock(return_value="result_b")
        mock_chat.side_effect = [
            self._make_tool_response("tool_a", {}),
            self._make_tool_response("tool_b", {}),
            self._make_text_response("done"),
        ]
        run_agent_loop("s", "u", [], {"tool_a": handler_a, "tool_b": handler_b})
        assert handler_a.call_count == 1
        assert handler_b.call_count == 1

    def test_unknown_tool_returns_error_string_to_model(self, mock_chat):
        """An unknown tool name should not crash — it returns an error string as the tool result."""
        mock_chat.side_effect = [
            self._make_tool_response("unknown_tool", {}),
            self._make_text_response("ok"),
        ]
        result = run_agent_loop("s", "u", [], {})
        assert result == "ok"

    def test_string_arguments_are_json_decoded(self, mock_chat):
        handler = MagicMock(return_value="ok")
        mock_chat.side_effect = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "h", "arguments": '{"path": "decoded.py"}'}}],
            },
            self._make_text_response("done"),
        ]
        run_agent_loop("s", "u", [], {"h": handler})
        handler.assert_called_once_with(path="decoded.py")

    def test_on_tool_call_callback_invoked(self, mock_chat):
        handler = MagicMock(return_value="r")
        mock_chat.side_effect = [
            self._make_tool_response("my_tool", {"x": 1}),
            self._make_text_response("done"),
        ]
        cb = MagicMock()
        run_agent_loop("s", "u", [], {"my_tool": handler}, on_tool_call=cb)
        cb.assert_called_once_with("my_tool", {"x": 1})

    def test_history_prepended_before_system(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("ok")]
        history = [{"role": "user", "content": "prior turn"}]
        run_agent_loop("sys", "new user msg", [], {}, history=history)
        messages_sent = mock_chat.call_args[0][0]
        assert messages_sent[0]["role"] == "system"
        assert any(m["content"] == "prior turn" for m in messages_sent)

    def test_content_based_tool_call_fallback(self, mock_chat):
        """When tool_calls is None but content has embedded JSON, it should still execute."""
        handler = MagicMock(return_value="result")
        call_json = '{"name": "my_tool", "arguments": {"k": "v"}}'
        mock_chat.side_effect = [
            {"role": "assistant", "content": call_json, "tool_calls": None},
            self._make_text_response("done"),
        ]
        result = run_agent_loop("s", "u", [], {"my_tool": handler})
        assert result == "done"
        handler.assert_called_once()

    def test_max_rounds_terminates_loop(self, mock_chat):
        """If the model never stops calling tools, MAX_ROUNDS caps the loop."""
        def endless_tool(*args, **kwargs):
            return "looping"

        mock_chat.side_effect = [
            {
                "role": "assistant",
                "content": "x",
                "tool_calls": [{"function": {"name": "t", "arguments": {}}}],
            }
        ] * (MAX_ROUNDS + 5)
        result = run_agent_loop("s", "u", [], {"t": endless_tool})
        assert isinstance(result, str)
        assert mock_chat.call_count <= MAX_ROUNDS + 1

    def test_system_prompt_inserted_first(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("ok")]
        run_agent_loop("MY_SYSTEM", "user msg", [], {})
        messages = mock_chat.call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "MY_SYSTEM"

    def test_user_message_appended_after_system(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("ok")]
        run_agent_loop("sys", "USER_MSG", [], {})
        messages = mock_chat.call_args[0][0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("USER_MSG" in m["content"] for m in user_msgs)

    def test_tools_forwarded_to_chat(self, mock_chat):
        mock_chat.side_effect = [self._make_text_response("ok")]
        tools = [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {}}}]
        run_agent_loop("s", "u", tools, {})
        # tools is passed as keyword arg to chat()
        assert mock_chat.call_args.kwargs.get("tools") == tools


# ── chat ──────────────────────────────────────────────────────────────────────

class TestChat:
    def test_successful_response_returned(self):
        fake_message = {"role": "assistant", "content": "hello", "tool_calls": None}
        fake_body = json.dumps({"message": fake_message}).encode()

        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            result = chat([{"role": "user", "content": "hi"}])

        assert result == fake_message

    def test_url_error_calls_sys_exit(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(SystemExit):
                chat([{"role": "user", "content": "hi"}])

    def test_payload_includes_model(self):
        fake_body = json.dumps({"message": {"role": "assistant", "content": "x"}}).encode()
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            chat([])

        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode())
        assert "model" in payload
        assert isinstance(payload["model"], str)

    def test_payload_includes_messages(self):
        fake_body = json.dumps({"message": {"role": "assistant", "content": "x"}}).encode()
        messages = [{"role": "user", "content": "test message"}]
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            chat(messages)

        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode())
        assert payload["messages"] == messages

    def test_stream_is_false(self):
        fake_body = json.dumps({"message": {"role": "assistant", "content": "x"}}).encode()
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_body
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            chat([])

        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode())
        assert payload["stream"] is False
