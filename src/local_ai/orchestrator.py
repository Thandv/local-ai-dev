"""
Orchestrator — runs the full agent pipeline:
  Researcher → Architect → Coder → Tester → Reviewer

Coordinates all agents, manages project state, and prints progress.
"""

import sys
import re
import time
from pathlib import Path
from datetime import datetime

# Add the Claude folder to the path so agents can be imported


from local_ai.agents.shared.memory import Project
from local_ai.agents import researcher, architect, coder, tester, reviewer

BUILDS_DIR = Path.home() / "builds"


def _slugify(text: str) -> str:
    """Turn an instruction into a safe directory name."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    slug = slug.strip("-")[:40]
    ts   = datetime.now().strftime("%H%M")
    return f"{slug}-{ts}"


def _header(title: str):
    width = 58
    print(f"\n{'─'*width}")
    print(f"  {title}")
    print(f"{'─'*width}")


def run(instruction: str, output_dir: Path = None, skip_review: bool = False) -> Project:
    """
    Run the full pipeline for a given instruction.

    Args:
        instruction:  Plain-English description of the app to build
        output_dir:   Where to write files (default: ~/builds/<slug>/)
        skip_review:  Skip the reviewer agent (faster, less thorough)
    Returns:
        Completed Project object
    """
    if not output_dir:
        output_dir = BUILDS_DIR / _slugify(instruction)

    output_dir.mkdir(parents=True, exist_ok=True)

    project = Project(instruction=instruction, output_dir=output_dir)

    print(f"\n{'='*60}")
    print(f"  Building: {instruction}")
    print(f"  Output  : {output_dir}")
    print(f"{'='*60}")

    stages = [
        ("Research",    researcher.run),
        ("Architecture", architect.run),
        ("Code",        coder.run),
        ("Tests",       tester.run),
    ]
    if not skip_review:
        stages.append(("Review", reviewer.run))

    for i, (label, agent_fn) in enumerate(stages, 1):
        _header(f"Stage {i}/{len(stages)}: {label}")
        t0 = time.time()
        try:
            project = agent_fn(project)
        except Exception as e:
            print(f"\n  [ERROR in {label}]: {e}")
            import traceback
            traceback.print_exc()
            print("  Continuing to next stage …\n")
        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s")

    project.save_log()
    print(project.summary())
    return project
