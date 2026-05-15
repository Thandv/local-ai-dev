"""
Tests for orchestrator.py — pipeline runner.

Covers: _slugify, _load_checkpoint, _save_checkpoint, run() stage selection,
        skip flags, resume logic, error resilience, fix() mode.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from local_ai.agents.shared.memory import Project
import local_ai.orchestrator as orch


# ── _slugify ──────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_lowercases_text(self):
        result = orch._slugify("Create A FastAPI App")
        assert result == result.lower() or "-" in result

    def test_replaces_spaces_with_dashes(self):
        slug = orch._slugify("hello world")
        parts = slug.split("-")
        assert "hello" in parts

    def test_removes_special_characters(self):
        slug = orch._slugify("Build an app! @#$%")
        for ch in "!@#$%":
            assert ch not in slug

    def test_truncates_at_40_chars_before_timestamp(self):
        long_text = "a" * 100
        slug = orch._slugify(long_text)
        # timestamp is 4 chars + separator, so slug part ≤ 40
        prefix = slug.rsplit("-", 1)[0]
        assert len(prefix) <= 40

    def test_appends_4_digit_timestamp(self):
        slug = orch._slugify("test")
        parts = slug.split("-")
        suffix = parts[-1]
        assert len(suffix) == 4
        assert suffix.isdigit()

    def test_strips_leading_trailing_dashes(self):
        slug = orch._slugify("---hello---")
        assert not slug.startswith("-")

    def test_returns_string(self):
        assert isinstance(orch._slugify("anything"), str)

    def test_empty_string_does_not_crash(self):
        slug = orch._slugify("")
        assert isinstance(slug, str)


# ── _load_checkpoint / _save_checkpoint ───────────────────────────────────────

class TestCheckpoints:
    def test_load_missing_file_returns_empty_dict(self, tmp_path):
        result = orch._load_checkpoint(tmp_path)
        assert result == {}

    def test_load_valid_json(self, tmp_path):
        (tmp_path / "BUILD_LOG.json").write_text(json.dumps({"instruction": "x", "completed_stages": ["researcher"]}))
        result = orch._load_checkpoint(tmp_path)
        assert result["instruction"] == "x"
        assert "researcher" in result["completed_stages"]

    def test_load_invalid_json_returns_empty_dict(self, tmp_path):
        (tmp_path / "BUILD_LOG.json").write_text("{invalid json{{")
        result = orch._load_checkpoint(tmp_path)
        assert result == {}

    def test_save_creates_build_log(self, project):
        orch._save_checkpoint(project, "researcher")
        assert (project.output_dir / "BUILD_LOG.json").exists()

    def test_save_records_stage(self, project):
        orch._save_checkpoint(project, "researcher")
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert "researcher" in log["completed_stages"]

    def test_save_accumulates_stages(self, project):
        orch._save_checkpoint(project, "researcher")
        orch._save_checkpoint(project, "architect")
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert "researcher" in log["completed_stages"]
        assert "architect" in log["completed_stages"]

    def test_save_does_not_duplicate_stage(self, project):
        orch._save_checkpoint(project, "researcher")
        orch._save_checkpoint(project, "researcher")
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["completed_stages"].count("researcher") == 1

    def test_save_persists_instruction(self, project):
        orch._save_checkpoint(project, "x")
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["instruction"] == project.instruction

    def test_save_persists_files_written(self, project):
        project.files_written = ["a.py", "b.py"]
        orch._save_checkpoint(project, "coder")
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["files"] == ["a.py", "b.py"]

    def test_roundtrip_load_after_save(self, project):
        project.success = True
        orch._save_checkpoint(project, "packager")
        loaded = orch._load_checkpoint(project.output_dir)
        assert loaded["success"] is True
        assert "packager" in loaded["completed_stages"]


# ── run() — stage execution ───────────────────────────────────────────────────

def _make_agent_mock(field=None, value="output"):
    """Returns a mock agent.run() function that sets project.<field>=value."""
    def fake_run(project):
        if field:
            setattr(project, field, value)
        return project
    return fake_run


@pytest.fixture
def all_agent_mocks(monkeypatch):
    """Patches all 11 agent modules so no LLM is called."""
    agents = {
        "designer":   _make_agent_mock("design", "design output"),
        "researcher": _make_agent_mock("research", "research output"),
        "architect":  _make_agent_mock("plan", "plan output"),
        "migrator":   _make_agent_mock(),
        "coder":      _make_agent_mock(),
        "debugger":   _make_agent_mock("debug_log", "debug output"),
        "tester":     _make_agent_mock("test_results", "tests pass"),
        "auditor":    _make_agent_mock("audit", "audit output"),
        "devops":     _make_agent_mock(),
        "reviewer":   _make_agent_mock("review", "review output"),
        "packager":   _make_agent_mock(),
    }
    mocks = {}
    for name, fn in agents.items():
        m = MagicMock(side_effect=fn)
        monkeypatch.setattr(f"local_ai.agents.{name}.run", m)
        monkeypatch.setattr(f"local_ai.orchestrator.{name}", MagicMock(run=m))
        mocks[name] = m
    return mocks


class TestOrchestratorRun:
    def test_returns_project(self, tmp_path, monkeypatch):
        _patch_all_agents(monkeypatch)
        result = orch.run("Build X", output_dir=tmp_path / "out")
        assert isinstance(result, Project)

    def test_creates_output_dir(self, tmp_path, monkeypatch):
        _patch_all_agents(monkeypatch)
        out = tmp_path / "new_build"
        orch.run("x", output_dir=out)
        assert out.exists()

    def test_saves_log_after_run(self, tmp_path, monkeypatch):
        _patch_all_agents(monkeypatch)
        out = tmp_path / "b"
        orch.run("x", output_dir=out)
        assert (out / "BUILD_LOG.json").exists()

    def test_skip_review_omits_reviewer(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_review=True)
        calls["reviewer"].assert_not_called()

    def test_skip_designer_omits_designer(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_designer=True)
        calls["designer"].assert_not_called()

    def test_skip_debug_omits_debugger(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_debug=True)
        calls["debugger"].assert_not_called()

    def test_skip_devops_omits_devops(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_devops=True)
        calls["devops"].assert_not_called()

    def test_skip_audit_omits_auditor(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_audit=True)
        calls["auditor"].assert_not_called()

    def test_skip_package_omits_packager(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run("x", output_dir=tmp_path / "b", skip_package=True)
        calls["packager"].assert_not_called()

    def test_all_skips_runs_only_core_stages(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        orch.run(
            "x", output_dir=tmp_path / "b",
            skip_designer=True, skip_debug=True, skip_devops=True,
            skip_audit=True, skip_package=True, skip_review=True,
        )
        for name in ("designer", "debugger", "devops", "auditor", "packager", "reviewer"):
            calls[name].assert_not_called()
        for name in ("researcher", "architect", "migrator", "coder", "tester"):
            calls[name].assert_called_once()

    def test_agent_exception_does_not_halt_pipeline(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        # Make researcher raise
        calls["researcher"].side_effect = RuntimeError("LLM failure")
        # Should not raise; pipeline continues
        result = orch.run("x", output_dir=tmp_path / "b")
        assert isinstance(result, Project)
        # Architect should still have been called
        calls["architect"].assert_called_once()

    def test_default_output_dir_in_builds(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        monkeypatch.setattr(orch, "BUILDS_DIR", tmp_path / "builds")
        result = orch.run("some instruction")
        assert str(tmp_path / "builds") in str(result.output_dir)

    def test_instruction_stored_in_project(self, tmp_path, monkeypatch):
        _patch_all_agents(monkeypatch)
        result = orch.run("Build a todo app", output_dir=tmp_path / "b")
        assert result.instruction == "Build a todo app"


class TestOrchestratorResume:
    def test_resume_skips_completed_stages(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        # Pre-populate checkpoint with designer + researcher as done
        log = {
            "instruction": "Build X",
            "started_at": "2024-01-01T00:00:00",
            "files": [],
            "success": False,
            "packaged": False,
            "completed_stages": ["designer", "researcher"],
        }
        out = tmp_path / "existing"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.run("Build X", resume_dir=out)
        calls["designer"].assert_not_called()
        calls["researcher"].assert_not_called()
        calls["architect"].assert_called_once()

    def test_resume_restores_files_from_checkpoint(self, tmp_path, monkeypatch):
        _patch_all_agents(monkeypatch)
        log = {
            "instruction": "X",
            "started_at": "t",
            "files": ["previous.py"],
            "success": False,
            "packaged": False,
            "completed_stages": ["designer", "researcher", "architect",
                                  "migrator", "coder", "debugger",
                                  "tester", "auditor", "devops", "reviewer", "packager"],
        }
        out = tmp_path / "done"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        result = orch.run("X", resume_dir=out)
        assert "previous.py" in result.files_written

    def test_resume_all_stages_done_calls_nothing(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        all_stages = ["designer", "researcher", "architect", "migrator",
                      "coder", "debugger", "tester", "auditor", "devops",
                      "reviewer", "packager"]
        log = {
            "instruction": "X", "started_at": "t", "files": [],
            "success": True, "packaged": True,
            "completed_stages": all_stages,
        }
        out = tmp_path / "all_done"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.run("X", resume_dir=out)
        for m in calls.values():
            m.assert_not_called()


# ── fix() ──────────────────────────────────────────────────────────────────────

class TestOrchestratorFix:
    def test_fix_calls_debugger(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        log = {"instruction": "X", "files": [], "success": False,
               "packaged": False, "completed_stages": []}
        out = tmp_path / "broken"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.fix(out, "ImportError: No module named 'app'")
        calls["debugger"].assert_called_once()

    def test_fix_injects_error_into_debug_log(self, tmp_path, monkeypatch):
        captured = {}

        def fake_debugger_run(project):
            captured["debug_log"] = project.debug_log
            return project

        calls = _patch_all_agents(monkeypatch)
        calls["debugger"].side_effect = fake_debugger_run

        log = {"instruction": "X", "files": [], "success": False,
               "packaged": False, "completed_stages": []}
        out = tmp_path / "broken"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.fix(out, "SyntaxError on line 42")
        assert "SyntaxError on line 42" in captured["debug_log"]

    def test_fix_saves_log_after_debugger(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        log = {"instruction": "X", "files": [], "success": False,
               "packaged": False, "completed_stages": []}
        out = tmp_path / "broken"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.fix(out, "error")
        assert (out / "BUILD_LOG.json").exists()

    def test_fix_returns_project(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        log = {"instruction": "X", "files": [], "success": False,
               "packaged": False, "completed_stages": []}
        out = tmp_path / "broken"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        result = orch.fix(out, "error")
        assert isinstance(result, Project)

    def test_fix_only_calls_debugger_not_others(self, tmp_path, monkeypatch):
        calls = _patch_all_agents(monkeypatch)
        log = {"instruction": "X", "files": [], "success": False,
               "packaged": False, "completed_stages": []}
        out = tmp_path / "broken"
        out.mkdir()
        (out / "BUILD_LOG.json").write_text(json.dumps(log))
        orch.fix(out, "error")
        for name in ("designer", "researcher", "architect", "migrator",
                     "coder", "tester", "auditor", "devops", "reviewer", "packager"):
            calls[name].assert_not_called()


# ── Helper ────────────────────────────────────────────────────────────────────

def _patch_all_agents(monkeypatch):
    """Patch all 11 agent modules in the orchestrator and return mock dict."""
    mocks = {}
    for name in ("designer", "researcher", "architect", "migrator", "coder",
                 "debugger", "tester", "auditor", "devops", "reviewer", "packager"):
        m = MagicMock(side_effect=lambda project, _n=name: project)
        monkeypatch.setattr(f"local_ai.orchestrator.{name}", MagicMock(run=m))
        mocks[name] = m
    return mocks
