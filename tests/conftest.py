"""
Shared fixtures for all test modules.

Key design decisions:
- All tests are fully offline: Ollama is never contacted.
- run_agent_loop is mocked at the source module level so every agent that
  imports it gets the mock automatically.
- Fixtures expose a `make_project` factory so tests can create Projects in
  isolated tmp directories.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_ai.agents.shared.memory import Project


# ── Project factory ───────────────────────────────────────────────────────────

@pytest.fixture
def make_project(tmp_path):
    """Return a factory that creates a fresh Project in a temp directory."""
    def _factory(instruction="Build a test app", subdir=None):
        out = tmp_path / (subdir or "build")
        out.mkdir(parents=True, exist_ok=True)
        return Project(instruction=instruction, output_dir=out)
    return _factory


@pytest.fixture
def project(make_project):
    """A single ready-to-use Project in a temp directory."""
    return make_project()


# ── LLM mock ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm(monkeypatch):
    """
    Patches run_agent_loop so no HTTP call is made.
    Returns the mock object so tests can configure return_value / side_effect.
    """
    m = MagicMock(return_value="Agent completed successfully.")
    monkeypatch.setattr("local_ai.agents.shared.llm.run_agent_loop", m)
    return m


@pytest.fixture
def mock_chat(monkeypatch):
    """
    Patches the low-level chat() function.
    Default: returns a plain text response with no tool calls.
    """
    def _default_chat(messages, tools=None, timeout=180):
        return {"role": "assistant", "content": "Test response.", "tool_calls": None}

    m = MagicMock(side_effect=_default_chat)
    monkeypatch.setattr("local_ai.agents.shared.llm.chat", m)
    return m


# ── Fake repos directory ──────────────────────────────────────────────────────

@pytest.fixture
def fake_repos_dir(tmp_path):
    """
    Creates a minimal fake repos directory with two 'repos', each containing
    a small Python file so grep_repos has something to find.
    """
    repos = tmp_path / "repos"
    for repo_name, keyword, content in [
        ("fastapi-repo", "router", "from fastapi import APIRouter\nrouter = APIRouter()\n"),
        ("react-repo",   "useState", "import { useState } from 'react';\n"),
    ]:
        p = repos / repo_name
        p.mkdir(parents=True)
        (p / "main.py").write_text(content)
    return repos
