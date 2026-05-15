"""
Tests for all 11 agents — designer, researcher, architect, migrator, coder,
debugger, tester, auditor, devops, reviewer, packager.

Strategy:
- run_agent_loop is patched in *each agent's own module namespace* (not the
  source module) because each agent does `from .shared.llm import run_agent_loop`,
  creating a local reference that must be mocked where it is used.
- No HTTP calls are made; Ollama is never contacted.
- Retry logic in debugger/tester is tested via side_effect sequences.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_ai.agents.shared.memory import Project


# ── Shared helper ─────────────────────────────────────────────────────────────

def _patch(agent_module):
    """Return the correct patch target for run_agent_loop in this agent."""
    return f"{agent_module.__name__}.run_agent_loop"


def run_with_mock_llm(agent_module, project, llm_return="Agent completed."):
    with patch(_patch(agent_module), return_value=llm_return) as mock_loop:
        result = agent_module.run(project)
    return result, mock_loop


# ══════════════════════════════════════════════════════════════════════════════
# Designer
# ══════════════════════════════════════════════════════════════════════════════

class TestDesignerAgent:
    def test_returns_project(self, project):
        from local_ai.agents import designer
        result, _ = run_with_mock_llm(designer, project)
        assert isinstance(result, Project)

    def test_populates_design_field(self, project):
        from local_ai.agents import designer
        result, _ = run_with_mock_llm(designer, project, "Design spec output")
        assert result.design == "Design spec output"

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import designer
        _, mock_loop = run_with_mock_llm(designer, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_design(self, project):
        from local_ai.agents import designer
        _, mock_loop = run_with_mock_llm(designer, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("design", "screen", "component", "ui"))

    def test_user_prompt_includes_instruction(self, project):
        from local_ai.agents import designer
        project.instruction = "unique_design_instruction_xyz"
        _, mock_loop = run_with_mock_llm(designer, project)
        user = mock_loop.call_args[1]["user"]
        assert "unique_design_instruction_xyz" in user

    def test_tracks_design_md_if_written(self, project):
        from local_ai.agents import designer
        (project.output_dir / "DESIGN.md").write_text("content")
        result, _ = run_with_mock_llm(designer, project)
        assert any("DESIGN.md" in f for f in result.files_written)

    def test_does_not_track_missing_design_md(self, project):
        from local_ai.agents import designer
        result, _ = run_with_mock_llm(designer, project)
        assert not any("DESIGN.md" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# Researcher
# ══════════════════════════════════════════════════════════════════════════════

class TestResearcherAgent:
    def test_returns_project(self, project):
        from local_ai.agents import researcher
        result, _ = run_with_mock_llm(researcher, project)
        assert isinstance(result, Project)

    def test_populates_research_field(self, project):
        from local_ai.agents import researcher
        result, _ = run_with_mock_llm(researcher, project, "Research brief text")
        assert result.research == "Research brief text"

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import researcher
        _, mock_loop = run_with_mock_llm(researcher, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_stack(self, project):
        from local_ai.agents import researcher
        _, mock_loop = run_with_mock_llm(researcher, project)
        system = mock_loop.call_args[1]["system"]
        assert "stack" in system.lower() or "research" in system.lower()

    def test_user_prompt_includes_instruction(self, project):
        from local_ai.agents import researcher
        project.instruction = "researcher_unique_xyz"
        _, mock_loop = run_with_mock_llm(researcher, project)
        user = mock_loop.call_args[1]["user"]
        assert "researcher_unique_xyz" in user


# ══════════════════════════════════════════════════════════════════════════════
# Architect
# ══════════════════════════════════════════════════════════════════════════════

class TestArchitectAgent:
    def test_returns_project(self, project):
        from local_ai.agents import architect
        result, _ = run_with_mock_llm(architect, project)
        assert isinstance(result, Project)

    def test_populates_plan_field(self, project):
        from local_ai.agents import architect
        result, _ = run_with_mock_llm(architect, project, "Architecture plan")
        assert result.plan == "Architecture plan"

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import architect
        _, mock_loop = run_with_mock_llm(architect, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_architect(self, project):
        from local_ai.agents import architect
        _, mock_loop = run_with_mock_llm(architect, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("architect", "plan", "structure", "file tree"))

    def test_tracks_plan_md_if_written(self, project):
        from local_ai.agents import architect
        (project.output_dir / "PLAN.md").write_text("plan content")
        result, _ = run_with_mock_llm(architect, project)
        assert any("PLAN.md" in f for f in result.files_written)

    def test_user_includes_output_dir(self, project):
        from local_ai.agents import architect
        _, mock_loop = run_with_mock_llm(architect, project)
        user = mock_loop.call_args[1]["user"]
        assert str(project.output_dir) in user


# ══════════════════════════════════════════════════════════════════════════════
# Migrator
# ══════════════════════════════════════════════════════════════════════════════

class TestMigratorAgent:
    def test_returns_project(self, project):
        from local_ai.agents import migrator
        result, _ = run_with_mock_llm(migrator, project)
        assert isinstance(result, Project)

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import migrator
        _, mock_loop = run_with_mock_llm(migrator, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_database(self, project):
        from local_ai.agents import migrator
        _, mock_loop = run_with_mock_llm(migrator, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("database", "migration", "schema", "model"))

    def test_uses_research_and_plan_in_user_prompt(self, project):
        from local_ai.agents import migrator
        project.research = "research_context_abc"
        project.plan = "plan_context_def"
        _, mock_loop = run_with_mock_llm(migrator, project)
        user = mock_loop.call_args[1]["user"]
        assert "research_context_abc" in user
        assert "plan_context_def" in user


# ══════════════════════════════════════════════════════════════════════════════
# Coder
# ══════════════════════════════════════════════════════════════════════════════

class TestCoderAgent:
    def test_returns_project(self, project):
        from local_ai.agents import coder
        result, _ = run_with_mock_llm(coder, project)
        assert isinstance(result, Project)

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import coder
        _, mock_loop = run_with_mock_llm(coder, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_complete_files(self, project):
        from local_ai.agents import coder
        _, mock_loop = run_with_mock_llm(coder, project)
        system = mock_loop.call_args[1]["system"]
        assert "complete" in system.lower() or "todo" in system.lower()

    def test_user_includes_output_dir(self, project):
        from local_ai.agents import coder
        _, mock_loop = run_with_mock_llm(coder, project)
        user = mock_loop.call_args[1]["user"]
        assert str(project.output_dir) in user

    def test_tracked_write_appends_to_files_written(self, project):
        from local_ai.agents import coder

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](str(project.output_dir / "main.py"), "code here")
            return "Done."

        with patch(_patch(coder), side_effect=fake_loop):
            result = coder.run(project)
        assert any("main.py" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# Debugger
# ══════════════════════════════════════════════════════════════════════════════

class TestDebuggerAgent:
    def test_returns_project(self, project):
        from local_ai.agents import debugger
        result, _ = run_with_mock_llm(debugger, project, "App starts cleanly.")
        assert isinstance(result, Project)

    def test_populates_debug_log(self, project):
        from local_ai.agents import debugger
        result, _ = run_with_mock_llm(debugger, project, "No errors found.")
        assert result.debug_log == "No errors found."

    def test_no_retry_on_clean_output(self, project):
        from local_ai.agents import debugger
        with patch(_patch(debugger), return_value="All OK.") as m:
            debugger.run(project)
        assert m.call_count == 1

    def test_retries_on_traceback_in_output(self, project):
        from local_ai.agents import debugger
        responses = [
            "Traceback (most recent call last): ImportError: no module",
            "Fixed! App starts cleanly.",
        ]
        with patch(_patch(debugger), side_effect=responses) as m:
            debugger.run(project)
        assert m.call_count == 2

    def test_retries_up_to_max_attempts(self, project):
        from local_ai.agents import debugger
        from local_ai.agents.debugger import MAX_ATTEMPTS
        always_error = "Error: something broke every time"
        with patch(_patch(debugger), return_value=always_error) as m:
            debugger.run(project)
        assert m.call_count == MAX_ATTEMPTS + 1

    def test_stops_retrying_when_clean(self, project):
        from local_ai.agents import debugger
        responses = [
            "Traceback: ImportError",
            "Traceback: TypeError",
            "App starts successfully.",
        ]
        with patch(_patch(debugger), side_effect=responses) as m:
            debugger.run(project)
        assert m.call_count == 3


# ══════════════════════════════════════════════════════════════════════════════
# Tester
# ══════════════════════════════════════════════════════════════════════════════

class TestTesterAgent:
    def test_returns_project(self, project):
        from local_ai.agents import tester
        result, _ = run_with_mock_llm(tester, project, "3 passed")
        assert isinstance(result, Project)

    def test_populates_test_results(self, project):
        from local_ai.agents import tester
        result, _ = run_with_mock_llm(tester, project, "5 passed, 0 failed")
        assert result.test_results == "5 passed, 0 failed"

    def test_success_set_true_on_passing_output(self, project):
        from local_ai.agents import tester
        with patch(_patch(tester), return_value="3 passed"):
            result = tester.run(project)
        assert result.success is True

    def test_success_set_true_on_ok_output(self, project):
        from local_ai.agents import tester
        with patch(_patch(tester), return_value="All tests OK"):
            result = tester.run(project)
        assert result.success is True

    def test_fix_attempted_on_failed_output(self, project):
        from local_ai.agents import tester
        responses = ["FAILED: AssertionError", "3 passed"]
        with patch(_patch(tester), side_effect=responses) as m:
            tester.run(project)
        assert m.call_count == 2

    def test_tracked_write_appends_to_files(self, project):
        from local_ai.agents import tester

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](str(project.output_dir / "tests" / "test_app.py"), "test code")
            return "passed"

        with patch(_patch(tester), side_effect=fake_loop):
            result = tester.run(project)
        assert any("test_app.py" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# Auditor
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditorAgent:
    def test_returns_project(self, project):
        from local_ai.agents import auditor
        result, _ = run_with_mock_llm(auditor, project)
        assert isinstance(result, Project)

    def test_populates_audit_field(self, project):
        from local_ai.agents import auditor
        result, _ = run_with_mock_llm(auditor, project, "No critical issues found.")
        assert result.audit == "No critical issues found."

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import auditor
        _, mock_loop = run_with_mock_llm(auditor, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_security(self, project):
        from local_ai.agents import auditor
        _, mock_loop = run_with_mock_llm(auditor, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("security", "vulnerability", "audit", "injection"))

    def test_tracked_write_tracked(self, project):
        from local_ai.agents import auditor

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](str(project.output_dir / "SECURITY.md"), "sec report")
            return "Audit complete."

        with patch(_patch(auditor), side_effect=fake_loop):
            result = auditor.run(project)
        assert any("SECURITY.md" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# DevOps
# ══════════════════════════════════════════════════════════════════════════════

class TestDevOpsAgent:
    def test_returns_project(self, project):
        from local_ai.agents import devops
        result, _ = run_with_mock_llm(devops, project)
        assert isinstance(result, Project)

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import devops
        _, mock_loop = run_with_mock_llm(devops, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_docker(self, project):
        from local_ai.agents import devops
        _, mock_loop = run_with_mock_llm(devops, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("docker", "dockerfile", "ci", "makefile"))

    def test_tracked_write_tracked(self, project):
        from local_ai.agents import devops

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](str(project.output_dir / "Dockerfile"), "FROM python:3.11")
            return "DevOps files written."

        with patch(_patch(devops), side_effect=fake_loop):
            result = devops.run(project)
        assert any("Dockerfile" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# Reviewer
# ══════════════════════════════════════════════════════════════════════════════

class TestReviewerAgent:
    def test_returns_project(self, project):
        from local_ai.agents import reviewer
        result, _ = run_with_mock_llm(reviewer, project)
        assert isinstance(result, Project)

    def test_populates_review_field(self, project):
        from local_ai.agents import reviewer
        result, _ = run_with_mock_llm(reviewer, project, "Code looks good.")
        assert result.review == "Code looks good."

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import reviewer
        _, mock_loop = run_with_mock_llm(reviewer, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_review_criteria(self, project):
        from local_ai.agents import reviewer
        _, mock_loop = run_with_mock_llm(reviewer, project)
        system = mock_loop.call_args[1]["system"]
        assert any(kw in system.lower() for kw in ("security", "correctness", "review", "quality"))

    def test_test_results_included_in_user_prompt(self, project):
        from local_ai.agents import reviewer
        project.test_results = "unique_test_result_abc"
        _, mock_loop = run_with_mock_llm(reviewer, project)
        user = mock_loop.call_args[1]["user"]
        assert "unique_test_result_abc" in user

    def test_tracked_write_does_not_duplicate(self, project):
        from local_ai.agents import reviewer
        existing = str(project.output_dir / "main.py")
        project.files_written = [existing]

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](existing, "updated")
            return "Done."

        with patch(_patch(reviewer), side_effect=fake_loop):
            result = reviewer.run(project)
        assert result.files_written.count(existing) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Packager
# ══════════════════════════════════════════════════════════════════════════════

class TestPackagerAgent:
    def test_returns_project(self, project):
        from local_ai.agents import packager
        result, _ = run_with_mock_llm(packager, project)
        assert isinstance(result, Project)

    def test_sets_packaged_true(self, project):
        from local_ai.agents import packager
        result, _ = run_with_mock_llm(packager, project)
        assert result.packaged is True

    def test_calls_run_agent_loop(self, project):
        from local_ai.agents import packager
        _, mock_loop = run_with_mock_llm(packager, project)
        mock_loop.assert_called_once()

    def test_system_prompt_mentions_readme(self, project):
        from local_ai.agents import packager
        _, mock_loop = run_with_mock_llm(packager, project)
        system = mock_loop.call_args[1]["system"]
        assert "readme" in system.lower() or "git" in system.lower()

    def test_plan_included_in_user_prompt(self, project):
        from local_ai.agents import packager
        project.plan = "unique_plan_content_xyz"
        _, mock_loop = run_with_mock_llm(packager, project)
        user = mock_loop.call_args[1]["user"]
        assert "unique_plan_content_xyz" in user

    def test_tracked_write_tracked(self, project):
        from local_ai.agents import packager

        def fake_loop(system, user, tools, handlers, **kwargs):
            handlers["write_file"](str(project.output_dir / "README.md"), "# Project")
            return "Packaged."

        with patch(_patch(packager), side_effect=fake_loop):
            result = packager.run(project)
        assert any("README.md" in f for f in result.files_written)


# ══════════════════════════════════════════════════════════════════════════════
# Cross-agent contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentContracts:
    @pytest.mark.parametrize("module_name", [
        "designer", "researcher", "architect", "migrator", "coder",
        "debugger", "tester", "auditor", "devops", "reviewer", "packager",
    ])
    def test_agent_has_run_function(self, module_name):
        import importlib
        mod = importlib.import_module(f"local_ai.agents.{module_name}")
        assert callable(getattr(mod, "run", None))

    @pytest.mark.parametrize("module_name", [
        "designer", "researcher", "architect", "migrator", "coder",
        "debugger", "tester", "auditor", "devops", "reviewer", "packager",
    ])
    def test_agent_run_accepts_project(self, module_name, project):
        import importlib
        mod = importlib.import_module(f"local_ai.agents.{module_name}")
        with patch(f"local_ai.agents.{module_name}.run_agent_loop", return_value="ok"):
            result = mod.run(project)
        assert isinstance(result, Project)

    @pytest.mark.parametrize("module_name", [
        "designer", "researcher", "architect", "migrator", "coder",
        "debugger", "tester", "auditor", "devops", "reviewer", "packager",
    ])
    def test_agent_does_not_clear_files_written(self, module_name, project):
        import importlib
        mod = importlib.import_module(f"local_ai.agents.{module_name}")
        project.files_written = ["pre_existing.py"]
        with patch(f"local_ai.agents.{module_name}.run_agent_loop", return_value="ok"):
            result = mod.run(project)
        assert "pre_existing.py" in result.files_written
