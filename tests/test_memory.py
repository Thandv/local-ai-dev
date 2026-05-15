"""
Tests for agents/shared/memory.py — Project dataclass.

Covers: field defaults, save_log, summary, files_written accumulation.
"""

import json
import pytest
from pathlib import Path
from local_ai.agents.shared.memory import Project


# ── Construction ──────────────────────────────────────────────────────────────

class TestProjectConstruction:
    def test_required_fields_stored(self, tmp_path):
        p = Project(instruction="Build X", output_dir=tmp_path)
        assert p.instruction == "Build X"
        assert p.output_dir == tmp_path

    def test_default_string_fields_are_empty(self, tmp_path):
        p = Project(instruction="x", output_dir=tmp_path)
        assert p.design == ""
        assert p.research == ""
        assert p.plan == ""
        assert p.debug_log == ""
        assert p.test_results == ""
        assert p.audit == ""
        assert p.review == ""

    def test_default_bool_fields(self, tmp_path):
        p = Project(instruction="x", output_dir=tmp_path)
        assert p.packaged is False
        assert p.success is False

    def test_files_written_starts_empty(self, tmp_path):
        p = Project(instruction="x", output_dir=tmp_path)
        assert p.files_written == []

    def test_files_written_is_independent_per_instance(self, tmp_path):
        p1 = Project(instruction="x", output_dir=tmp_path / "a")
        p2 = Project(instruction="y", output_dir=tmp_path / "b")
        p1.files_written.append("foo.py")
        assert p2.files_written == []

    def test_started_at_is_set(self, tmp_path):
        p = Project(instruction="x", output_dir=tmp_path)
        assert p.started_at
        assert "T" in p.started_at  # ISO 8601 contains T separator

    def test_instruction_preserved_exactly(self, tmp_path):
        inst = "Build a  REST API  with spaces"
        p = Project(instruction=inst, output_dir=tmp_path)
        assert p.instruction == inst

    def test_output_dir_can_be_nested(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        p = Project(instruction="x", output_dir=nested)
        assert p.output_dir == nested

    def test_empty_instruction_allowed(self, tmp_path):
        p = Project(instruction="", output_dir=tmp_path)
        assert p.instruction == ""


# ── save_log ──────────────────────────────────────────────────────────────────

class TestSaveLog:
    def test_creates_build_log_json(self, project):
        project.save_log()
        log_path = project.output_dir / "BUILD_LOG.json"
        assert log_path.exists()

    def test_log_contains_instruction(self, project):
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["instruction"] == project.instruction

    def test_log_contains_started_at(self, project):
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["started_at"] == project.started_at

    def test_log_reflects_success_false(self, project):
        project.success = False
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["success"] is False

    def test_log_reflects_success_true(self, project):
        project.success = True
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["success"] is True

    def test_log_reflects_packaged(self, project):
        project.packaged = True
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["packaged"] is True

    def test_log_contains_files_written(self, project):
        project.files_written = ["a.py", "b.py"]
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["files"] == ["a.py", "b.py"]

    def test_log_creates_output_dir_if_missing(self, tmp_path):
        missing = tmp_path / "new" / "nested"
        p = Project(instruction="x", output_dir=missing)
        p.save_log()
        assert (missing / "BUILD_LOG.json").exists()

    def test_log_is_valid_json(self, project):
        project.save_log()
        text = (project.output_dir / "BUILD_LOG.json").read_text()
        parsed = json.loads(text)
        assert isinstance(parsed, dict)

    def test_log_overwrites_on_second_save(self, project):
        project.success = False
        project.save_log()
        project.success = True
        project.save_log()
        log = json.loads((project.output_dir / "BUILD_LOG.json").read_text())
        assert log["success"] is True


# ── summary ───────────────────────────────────────────────────────────────────

class TestSummary:
    def test_success_shows_checkmark(self, project):
        project.success = True
        assert "✓ SUCCESS" in project.summary()

    def test_failure_shows_cross(self, project):
        project.success = False
        assert "✗ INCOMPLETE" in project.summary()

    def test_output_dir_in_summary(self, project):
        assert str(project.output_dir) in project.summary()

    def test_files_listed_in_summary(self, project):
        project.files_written = ["src/main.py", "README.md"]
        s = project.summary()
        assert "src/main.py" in s
        assert "README.md" in s

    def test_packaged_line_shown_when_true(self, project):
        project.packaged = True
        assert "Packaged" in project.summary()

    def test_packaged_line_absent_when_false(self, project):
        project.packaged = False
        assert "Packaged" not in project.summary()

    def test_summary_returns_string(self, project):
        assert isinstance(project.summary(), str)

    def test_summary_with_empty_files(self, project):
        project.files_written = []
        # Should not raise
        s = project.summary()
        assert "✗ INCOMPLETE" in s

    def test_summary_contains_separator_lines(self, project):
        assert "=" * 10 in project.summary()


# ── files_written accumulation ────────────────────────────────────────────────

class TestFilesWritten:
    def test_append_single_file(self, project):
        project.files_written.append("foo.py")
        assert "foo.py" in project.files_written

    def test_extend_multiple_files(self, project):
        project.files_written.extend(["a.py", "b.py", "c.ts"])
        assert len(project.files_written) == 3

    def test_no_dedup_by_default(self, project):
        project.files_written.append("dup.py")
        project.files_written.append("dup.py")
        assert project.files_written.count("dup.py") == 2

    def test_files_written_survives_save_log(self, project):
        project.files_written = ["kept.py"]
        project.save_log()
        assert project.files_written == ["kept.py"]
