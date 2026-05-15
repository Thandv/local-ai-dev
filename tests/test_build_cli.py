"""
Tests for build_cli.py — argument parsing and CLI dispatch.

Covers: TEMPLATES content, all argument combinations, --fix, --resume,
        --template prefix, error cases, skip flags passed to orchestrator.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from local_ai.build_cli import TEMPLATES


# ── TEMPLATES constant ────────────────────────────────────────────────────────

class TestTemplates:
    def test_all_five_templates_exist(self):
        assert set(TEMPLATES.keys()) == {"saas", "api", "dashboard", "cli", "fullstack"}

    @pytest.mark.parametrize("key", ["saas", "api", "dashboard", "cli", "fullstack"])
    def test_template_values_are_nonempty_strings(self, key):
        assert isinstance(TEMPLATES[key], str)
        assert len(TEMPLATES[key]) > 10

    def test_saas_template_mentions_auth(self):
        assert "auth" in TEMPLATES["saas"].lower() or "login" in TEMPLATES["saas"].lower()

    def test_api_template_mentions_jwt(self):
        assert "jwt" in TEMPLATES["api"].lower() or "auth" in TEMPLATES["api"].lower()

    def test_fullstack_template_mentions_both_backend_and_frontend(self):
        t = TEMPLATES["fullstack"].lower()
        assert ("fastapi" in t or "backend" in t) and ("react" in t or "frontend" in t)


# ── Argument parsing helpers ──────────────────────────────────────────────────

def run_main(args: list, mock_orch=None):
    """Invoke build_cli.main() with sys.argv patched to args."""
    if mock_orch is None:
        mock_orch = MagicMock()
    with patch("sys.argv", ["build-app"] + args), \
         patch("local_ai.build_cli.orchestrator", mock_orch):
        from local_ai import build_cli
        build_cli.main()
    return mock_orch


# ── Normal build mode ─────────────────────────────────────────────────────────

class TestNormalBuild:
    def test_single_word_instruction(self, tmp_path):
        m = MagicMock()
        run_main(["hello"], m)
        m.run.assert_called_once()
        kwargs = m.run.call_args[1]
        assert kwargs["instruction"] == "hello"

    def test_multi_word_instruction_joined(self, tmp_path):
        m = MagicMock()
        run_main(["Build", "a", "REST", "API"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["instruction"] == "Build a REST API"

    def test_out_flag_sets_output_dir(self, tmp_path):
        m = MagicMock()
        run_main(["hello", "--out", str(tmp_path)], m)
        kwargs = m.run.call_args[1]
        assert kwargs["output_dir"] == tmp_path

    def test_no_out_flag_passes_none(self):
        m = MagicMock()
        run_main(["hello"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["output_dir"] is None

    def test_no_review_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-review"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_review"] is True

    def test_no_debug_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-debug"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_debug"] is True

    def test_no_devops_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-devops"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_devops"] is True

    def test_no_audit_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-audit"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_audit"] is True

    def test_no_package_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-package"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_package"] is True

    def test_no_designer_flag(self):
        m = MagicMock()
        run_main(["hello", "--no-designer"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_designer"] is True

    def test_interactive_flag(self):
        m = MagicMock()
        run_main(["hello", "--interactive"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["interactive"] is True

    def test_no_flags_defaults_all_false(self):
        m = MagicMock()
        run_main(["hello"], m)
        kwargs = m.run.call_args[1]
        for key in ("skip_review", "skip_debug", "skip_devops", "skip_audit",
                    "skip_package", "skip_designer", "interactive"):
            assert kwargs[key] is False, f"{key} should default to False"

    def test_all_skip_flags_combined(self):
        m = MagicMock()
        run_main(["hello", "--no-review", "--no-debug", "--no-devops",
                  "--no-audit", "--no-package", "--no-designer"], m)
        kwargs = m.run.call_args[1]
        for key in ("skip_review", "skip_debug", "skip_devops",
                    "skip_audit", "skip_package", "skip_designer"):
            assert kwargs[key] is True


# ── Template mode ─────────────────────────────────────────────────────────────

class TestTemplateModeCliParsing:
    @pytest.mark.parametrize("tpl", ["saas", "api", "dashboard", "cli", "fullstack"])
    def test_template_prepends_canned_text(self, tpl):
        m = MagicMock()
        run_main(["--template", tpl, "with extras"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["instruction"].startswith(TEMPLATES[tpl])
        assert "with extras" in kwargs["instruction"]

    def test_template_without_extra_instruction(self):
        m = MagicMock()
        run_main(["--template", "api"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["instruction"] == TEMPLATES["api"]

    def test_no_instruction_no_template_raises(self):
        with pytest.raises(SystemExit):
            run_main([])


# ── --resume mode ─────────────────────────────────────────────────────────────

class TestResumeModeCliParsing:
    def test_resume_calls_run_with_resume_dir(self, tmp_path):
        m = MagicMock()
        run_main(["--resume", str(tmp_path)], m)
        m.run.assert_called_once()
        kwargs = m.run.call_args[1]
        assert kwargs["resume_dir"] == tmp_path

    def test_resume_with_additional_instruction(self, tmp_path):
        m = MagicMock()
        run_main(["--resume", str(tmp_path), "extra context"], m)
        kwargs = m.run.call_args[1]
        assert "extra context" in kwargs["instruction"]

    def test_resume_forwards_skip_flags(self, tmp_path):
        m = MagicMock()
        run_main(["--resume", str(tmp_path), "--no-review", "--no-debug"], m)
        kwargs = m.run.call_args[1]
        assert kwargs["skip_review"] is True
        assert kwargs["skip_debug"] is True

    def test_resume_does_not_call_fix(self, tmp_path):
        m = MagicMock()
        run_main(["--resume", str(tmp_path)], m)
        m.fix.assert_not_called()


# ── --fix mode ─────────────────────────────────────────────────────────────────

class TestFixModeCliParsing:
    def test_fix_calls_orchestrator_fix(self, tmp_path):
        m = MagicMock()
        run_main(["--fix", str(tmp_path)], m)
        m.fix.assert_called_once()

    def test_fix_passes_build_dir(self, tmp_path):
        m = MagicMock()
        run_main(["--fix", str(tmp_path)], m)
        kwargs = m.fix.call_args[1]
        assert kwargs["build_dir"] == tmp_path

    def test_fix_passes_error_string(self, tmp_path):
        m = MagicMock()
        run_main(["--fix", str(tmp_path), "--error", "ModuleNotFoundError: app"], m)
        kwargs = m.fix.call_args[1]
        assert "ModuleNotFoundError" in kwargs["error"]

    def test_fix_empty_error_defaults_to_empty_string(self, tmp_path):
        m = MagicMock()
        run_main(["--fix", str(tmp_path)], m)
        kwargs = m.fix.call_args[1]
        assert kwargs["error"] == ""

    def test_fix_does_not_call_run(self, tmp_path):
        m = MagicMock()
        run_main(["--fix", str(tmp_path)], m)
        m.run.assert_not_called()


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_instruction_with_special_chars(self):
        m = MagicMock()
        run_main(["Build", "a", "REST", "API", "with", "auth!"], m)
        kwargs = m.run.call_args[1]
        assert "auth!" in kwargs["instruction"]

    def test_very_long_instruction(self):
        m = MagicMock()
        long_words = ["word"] * 50
        run_main(long_words, m)
        kwargs = m.run.call_args[1]
        assert "word" in kwargs["instruction"]

    def test_out_dir_expanded_with_tilde(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        m = MagicMock()
        run_main(["hello", "--out", "~/myproject"], m)
        kwargs = m.run.call_args[1]
        assert str(tmp_path) in str(kwargs["output_dir"])
