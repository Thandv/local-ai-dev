"""Tests for the exemplar library."""

import json
from pathlib import Path
import pytest

from local_ai import exemplars
from local_ai.agents.shared.memory import Project


@pytest.fixture
def exemplars_dir(tmp_path, monkeypatch):
    """Redirect EXEMPLARS_DIR to a tmp path so tests don't touch
    ~/.local-ai/exemplars/."""
    redirected = tmp_path / "exemplars"
    monkeypatch.setattr(exemplars, "EXEMPLARS_DIR", redirected)
    return redirected


def _make_completed_project(tmp_path: Path, instruction: str,
                            files: dict[str, str] | None = None) -> Project:
    """Build a fake completed Project on disk with PLAN.md + N source files."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = Project(instruction=instruction, output_dir=tmp_path)
    project.success = True
    (tmp_path / "PLAN.md").write_text("# PLAN\n\nSome plan.\n", encoding="utf-8")
    files = files or {"main.py": "def main():\n    print('hi')\n",
                       "app/__init__.py": "from .main import main\n"}
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return project


# ── Keyword extraction + similarity ──────────────────────────────────────

def test_keywords_filters_stopwords():
    kws = exemplars._keywords("Build me a FastAPI todo app with SQLite")
    assert "fastapi" in kws
    assert "todo" in kws
    assert "sqlite" in kws
    # Stopwords stripped
    assert "build" not in kws
    assert "me" not in kws
    assert "a" not in kws
    assert "with" not in kws


def test_similarity_identical_is_one():
    # Words must be ≥3 chars to count toward similarity
    assert exemplars._similarity("alpha beta gamma", "alpha beta gamma") == 1.0


def test_similarity_disjoint_is_zero():
    assert exemplars._similarity("alpha beta", "gamma delta") == 0.0


def test_similarity_partial_overlap():
    # 2 shared / 4 total = 0.5 (Jaccard)
    s = exemplars._similarity("alphaword betaword gammaword",
                               "alphaword betaword deltaword")
    assert 0.49 <= s <= 0.51, f"expected ~0.5, got {s}"


def test_similarity_handles_empty():
    assert exemplars._similarity("", "anything") == 0.0
    assert exemplars._similarity("anything", "") == 0.0


# ── save_exemplar ─────────────────────────────────────────────────────────

def test_save_exemplar_skips_unsuccessful_project(tmp_path, exemplars_dir):
    """A failed build should not be saved."""
    project = _make_completed_project(tmp_path, "instruction text")
    project.success = False
    result = exemplars.save_exemplar(project)
    assert result is None
    assert not exemplars_dir.exists() or not list(exemplars_dir.iterdir())


def test_save_exemplar_writes_expected_layout(tmp_path, exemplars_dir):
    project = _make_completed_project(
        tmp_path, "build me a FastAPI todo app",
        files={"main.py": "x = 1\n",
               "app/routes.py": "def get_todos(): pass\n"},
    )
    dest = exemplars.save_exemplar(project)
    assert dest is not None
    assert dest.exists()
    assert (dest / "instruction.txt").exists()
    assert (dest / "plan.md").exists()
    assert (dest / "files").exists()
    assert (dest / "meta.json").exists()

    # Files are copied with paths preserved
    assert (dest / "files" / "main.py").exists()
    assert (dest / "files" / "app" / "routes.py").exists()


def test_save_exemplar_meta_json_round_trips(tmp_path, exemplars_dir):
    project = _make_completed_project(tmp_path, "instruction X")
    dest = exemplars.save_exemplar(project)
    meta = json.loads((dest / "meta.json").read_text())
    assert meta["instruction"] == "instruction X"
    assert "stamp" in meta
    assert "n_files" in meta
    assert meta["n_files"] >= 1


def test_save_exemplar_ignores_skip_dirs(tmp_path, exemplars_dir):
    """Files under .git/, venv/, node_modules/ etc. are not copied."""
    project = _make_completed_project(
        tmp_path, "test",
        files={"main.py": "x=1\n",
               ".git/HEAD": "ref: refs/heads/main\n",
               "venv/lib/site.py": "junk\n",
               "node_modules/foo/index.js": "junk\n"},
    )
    dest = exemplars.save_exemplar(project)
    files_dir = dest / "files"
    assert (files_dir / "main.py").exists()
    assert not (files_dir / ".git" / "HEAD").exists()
    assert not (files_dir / "venv" / "lib" / "site.py").exists()
    assert not (files_dir / "node_modules" / "foo" / "index.js").exists()


def test_save_exemplar_caps_file_count(tmp_path, exemplars_dir):
    """Only MAX_FILES_PER_EXEMPLAR files are kept."""
    files = {f"src{i}.py": f"# file {i}\nx = {i}\n"
             for i in range(20)}
    project = _make_completed_project(tmp_path, "many files", files=files)
    dest = exemplars.save_exemplar(project)
    kept = list((dest / "files").rglob("*.py"))
    assert len(kept) <= exemplars.MAX_FILES_PER_EXEMPLAR


def test_save_exemplar_skips_files_over_size_limit(tmp_path, exemplars_dir):
    huge = "x" * (exemplars.MAX_FILE_BYTES + 1000)
    small = "y = 1\n"
    project = _make_completed_project(
        tmp_path, "test",
        files={"huge.py": huge, "small.py": small},
    )
    dest = exemplars.save_exemplar(project)
    assert (dest / "files" / "small.py").exists()
    assert not (dest / "files" / "huge.py").exists()


# ── find_similar ──────────────────────────────────────────────────────────

def test_find_similar_returns_empty_when_no_library(tmp_path, exemplars_dir):
    """No exemplars on disk → no matches, no crash."""
    assert exemplars.find_similar("anything") == []


def test_find_similar_ranks_by_keyword_overlap(tmp_path, exemplars_dir, monkeypatch):
    # Build 3 exemplars with different instructions
    instr_match  = "build a FastAPI todo with SQLite and JWT auth"
    instr_mid    = "build a Flask blog with SQLAlchemy"
    instr_off    = "react frontend for landing page"

    for i, instr in enumerate([instr_match, instr_mid, instr_off]):
        p = _make_completed_project(tmp_path / f"p{i}", instr)
        exemplars.save_exemplar(p)

    results = exemplars.find_similar("FastAPI todo with SQLite and JWT", k=3)
    assert len(results) >= 1
    # Highest-similarity match should be the FastAPI one
    top_sim, top_path = results[0]
    top_instruction = (top_path / "instruction.txt").read_text()
    assert "FastAPI" in top_instruction or "fastapi" in top_instruction.lower()


def test_find_similar_respects_min_similarity(tmp_path, exemplars_dir):
    project = _make_completed_project(tmp_path, "unrelated alpha beta gamma")
    exemplars.save_exemplar(project)
    # New instruction shares no content words
    results = exemplars.find_similar("delta epsilon zeta", min_similarity=0.5)
    assert results == []


def test_find_similar_caps_at_k(tmp_path, exemplars_dir):
    for i in range(5):
        p = _make_completed_project(
            tmp_path / f"p{i}",
            "build a FastAPI todo todo todo unique-keyword-{i}".format(i=i),
        )
        exemplars.save_exemplar(p)
    results = exemplars.find_similar("FastAPI todo", k=2)
    assert len(results) <= 2


# ── render_exemplars_block ────────────────────────────────────────────────

def test_render_exemplars_block_empty_when_no_matches(tmp_path, exemplars_dir):
    assert exemplars.render_exemplars_block("anything") == ""


def test_render_exemplars_block_includes_instruction_and_plan(tmp_path, exemplars_dir):
    project = _make_completed_project(
        tmp_path, "build a FastAPI todo app with SQLite",
    )
    exemplars.save_exemplar(project)
    block = exemplars.render_exemplars_block(
        "FastAPI todo app with SQLite database", k=1,
    )
    assert "Past build" in block
    assert "similarity" in block.lower()
    assert "FastAPI todo" in block
    assert "Plan summary" in block


def test_render_exemplars_block_respects_max_bytes(tmp_path, exemplars_dir):
    # Create an exemplar with very long files
    files = {f"f{i}.py": "x = 'y' * 100\n" * 200 for i in range(6)}
    project = _make_completed_project(
        tmp_path, "huge build with many keywords todo app fastapi", files=files,
    )
    exemplars.save_exemplar(project)
    block = exemplars.render_exemplars_block(
        "huge build with many keywords todo app fastapi", k=1, max_bytes=2000,
    )
    assert len(block) <= 2100  # slight tolerance for the "truncated" message


# ── Maintenance ───────────────────────────────────────────────────────────

def test_clear_exemplars(tmp_path, exemplars_dir):
    project = _make_completed_project(tmp_path, "anything")
    exemplars.save_exemplar(project)
    assert exemplars.count_exemplars() == 1
    exemplars.clear_exemplars()
    assert exemplars.count_exemplars() == 0


def test_count_exemplars_empty(tmp_path, exemplars_dir):
    assert exemplars.count_exemplars() == 0


# ── End-to-end: save → find ──────────────────────────────────────────────

def test_round_trip_save_find_render(tmp_path, exemplars_dir):
    """A complete save → find → render flow returns the right exemplar."""
    project = _make_completed_project(
        tmp_path, "todo app with FastAPI SQLite and JWT auth",
        files={"main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
    )
    saved = exemplars.save_exemplar(project)
    assert saved is not None

    block = exemplars.render_exemplars_block(
        "FastAPI todo app with JWT", k=1,
    )
    assert "FastAPI" in block or "fastapi" in block.lower()
    # The Coder will see a small code excerpt
    assert "main.py" in block
