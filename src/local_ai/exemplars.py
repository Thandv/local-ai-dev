"""
Exemplar Library — few-shot examples from past successful builds.

Every time a `build-app` run finishes with SUCCESS, the Packager calls
`save_exemplar(project)` which snapshots the instruction, the plan, and a
handful of representative source files into:

    ~/.local-ai/exemplars/<timestamp>-<slug>/
        instruction.txt
        plan.md
        files/                   # up to N representative source files
            run.py
            app/__init__.py
            ...
        meta.json                # bookkeeping

On a new build, the Researcher (and through it the Coder) calls
`find_similar(instruction, k)` which keyword-matches the new instruction
against the stored exemplars and returns a compact few-shot block of the
top K matches for inclusion in the Coder's prompt.

The mechanism is simple by design — no embeddings, no vector DB:
  - Storage is plain files on disk under ~/.local-ai/exemplars/
  - Similarity is keyword overlap (Jaccard) on the instruction words
  - The exemplar block is hard-capped at ~8 KB to fit a small model's context

Privacy: exemplars live entirely on the user's machine. They're never
uploaded anywhere. A user can clear them with `rm -rf ~/.local-ai/exemplars/`.
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .agents.shared.memory import Project

EXEMPLARS_DIR = Path.home() / ".local-ai" / "exemplars"

# Max number of source files to copy per exemplar. Tuned so a typical
# small-app exemplar lands at ~10-20 KB total.
MAX_FILES_PER_EXEMPLAR  = 6

# Largest file we'll bother capturing — prefer many small files over one huge
# generated file (e.g. a 2 MB minified bundle).
MAX_FILE_BYTES          = 8_000

# Largest exemplar block (in bytes) we'll surface to the Coder. This is a
# hard cap; the few-shot block is sliced to fit.
MAX_EXEMPLAR_BLOCK_BYTES = 8_000

# Same stopword set the indexer uses for keyword extraction. Keep aligned
# manually — this list is intentionally short to avoid an external import.
_STOP = {
    "a", "an", "the", "and", "or", "with", "for", "that", "this", "to", "of",
    "in", "on", "is", "i", "want", "build", "create", "make", "app", "me",
    "my", "need", "can", "use", "using", "full", "from", "into",
}


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len] or "untitled"


def _keywords(text: str) -> set[str]:
    """Content-bearing words (≥3 chars, not stopwords) lowercased."""
    return {
        w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text or "")
        if w.lower() not in _STOP and len(w) >= 3
    }


def _similarity(a: str, b: str) -> float:
    """Jaccard similarity over keywords. Returns 0.0 if either side is empty."""
    ka, kb = _keywords(a), _keywords(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


# ── Save ──────────────────────────────────────────────────────────────────

# Source extensions we consider for inclusion in an exemplar. Mirrors the
# success-criterion set but adds a few README-style files which are also
# useful for showing a Coder what a finished project looks like.
_SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".swift", ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".hpp", ".scala",
    ".sh", ".bash", ".sql", ".html", ".css", ".vue", ".svelte",
    ".md", ".toml", ".yaml", ".yml", ".json",
}

# Things we never want to include — generated artefacts, virtualenvs, etc.
_SKIP_PARTS = {
    ".git", "venv", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".next", "target",
}


def _interesting_files(project_dir: Path) -> list[Path]:
    """Return a curated list of source files most useful as exemplar bait,
    sorted by 'representativeness' heuristics:
      1. Files at the top of the project tree first (run.py, main.py, app.py)
      2. Then smaller files (lower per-file token cost in the Coder prompt)
    """
    candidates: list[tuple[int, int, Path]] = []
    for p in project_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _SOURCE_EXTENSIONS:
            continue
        if any(part in _SKIP_PARTS for part in p.relative_to(project_dir).parts):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size == 0 or size > MAX_FILE_BYTES:
            continue
        depth = len(p.relative_to(project_dir).parts)
        # Sort key: top-level first, then by name length (proxy for "main")
        # then by size
        candidates.append((depth, size, p))

    candidates.sort(key=lambda t: (t[0], t[1]))
    return [p for _, _, p in candidates[:MAX_FILES_PER_EXEMPLAR]]


def save_exemplar(project: Project) -> Optional[Path]:
    """Snapshot a successful build into the exemplar library. Returns the
    new exemplar directory, or None if the project doesn't qualify."""
    if not project.success:
        return None
    project_dir = Path(project.output_dir)
    if not project_dir.exists():
        return None

    EXEMPLARS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug  = _slug(project.instruction)
    dest  = EXEMPLARS_DIR / f"{stamp}-{slug}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # Instruction + plan
    (dest / "instruction.txt").write_text(project.instruction, encoding="utf-8")
    plan_src = project_dir / "PLAN.md"
    if plan_src.exists():
        shutil.copy2(plan_src, dest / "plan.md")

    # Curated files
    files_dir = dest / "files"
    files_dir.mkdir()
    chosen = _interesting_files(project_dir)
    for src in chosen:
        rel = src.relative_to(project_dir)
        try:
            target = files_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        except OSError:
            continue

    # Bookkeeping
    (dest / "meta.json").write_text(json.dumps({
        "instruction": project.instruction,
        "stamp":       stamp,
        "slug":        slug,
        "n_files":     len(chosen),
        "source_dir":  str(project_dir),
    }, indent=2), encoding="utf-8")

    return dest


# ── Find similar + format ─────────────────────────────────────────────────

def _list_exemplars() -> list[Path]:
    if not EXEMPLARS_DIR.exists():
        return []
    return [p for p in EXEMPLARS_DIR.iterdir() if p.is_dir()]


def find_similar(instruction: str, k: int = 2, min_similarity: float = 0.10
                 ) -> list[tuple[float, Path]]:
    """Return up to k exemplars sorted by similarity (highest first).
    Only exemplars with similarity ≥ min_similarity are included."""
    scored: list[tuple[float, Path]] = []
    for ex_dir in _list_exemplars():
        instr_file = ex_dir / "instruction.txt"
        if not instr_file.exists():
            continue
        try:
            past_instruction = instr_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        sim = _similarity(instruction, past_instruction)
        if sim >= min_similarity:
            scored.append((sim, ex_dir))
    scored.sort(key=lambda t: -t[0])
    return scored[:k]


def render_exemplars_block(instruction: str, k: int = 2,
                            max_bytes: int = MAX_EXEMPLAR_BLOCK_BYTES) -> str:
    """Build the few-shot block the Coder will see. Returns "" if there are
    no similar exemplars."""
    matches = find_similar(instruction, k=k)
    if not matches:
        return ""

    parts: list[str] = []
    for sim, ex_dir in matches:
        try:
            past_instruction = (ex_dir / "instruction.txt").read_text(encoding="utf-8")
        except OSError:
            continue
        parts.append(f"### Past build (similarity {sim:.2f})")
        parts.append(f"**Instruction:** {past_instruction.strip()}")
        plan_md = ex_dir / "plan.md"
        if plan_md.exists():
            try:
                plan_text = plan_md.read_text(encoding="utf-8")[:2000]
                parts.append(f"**Plan summary:**\n```\n{plan_text}\n```")
            except OSError:
                pass
        # Up to 3 representative files per exemplar in the block (keep it lean)
        files_dir = ex_dir / "files"
        if files_dir.exists():
            file_list = sorted(files_dir.rglob("*"))
            shown = 0
            for f in file_list:
                if not f.is_file() or shown >= 3:
                    continue
                try:
                    body = f.read_text(encoding="utf-8", errors="ignore")[:1500]
                except OSError:
                    continue
                rel = f.relative_to(files_dir)
                parts.append(f"**`{rel}`** (excerpt):\n```\n{body}\n```")
                shown += 1
        parts.append("")  # blank line between exemplars

    block = "\n".join(parts)
    if len(block) > max_bytes:
        block = block[:max_bytes] + f"\n[exemplars truncated to {max_bytes} bytes]"
    return block


# ── Maintenance ───────────────────────────────────────────────────────────

def clear_exemplars():
    """Remove the entire exemplar library. Used by `ai-index --reset-exemplars`
    (not yet wired up) and by tests."""
    if EXEMPLARS_DIR.exists():
        shutil.rmtree(EXEMPLARS_DIR)


def count_exemplars() -> int:
    return len(_list_exemplars())
