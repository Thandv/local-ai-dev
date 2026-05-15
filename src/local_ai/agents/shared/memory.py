"""
Project memory — the shared state object passed through the agent pipeline.
Each agent reads from and writes to this object.
"""

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json


@dataclass
class Project:
    instruction: str              # Original user instruction
    output_dir: Path              # Where all files are written

    # Populated by each agent in sequence
    research:     str = ""        # Research agent output
    plan:         str = ""        # Architect agent plan (also written to PLAN.md)
    files_written: list = field(default_factory=list)  # Paths written by coder
    test_results: str = ""        # Tester output
    review:       str = ""        # Reviewer output
    success:      bool = False    # Did everything pass?

    # Metadata
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def save_log(self):
        """Persist pipeline log to output_dir/BUILD_LOG.json."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        log = {
            "instruction": self.instruction,
            "started_at":  self.started_at,
            "files":       self.files_written,
            "success":     self.success,
        }
        (self.output_dir / "BUILD_LOG.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8"
        )

    def summary(self) -> str:
        status = "✓ SUCCESS" if self.success else "✗ INCOMPLETE"
        files  = "\n".join(f"  • {f}" for f in self.files_written)
        return (
            f"\n{'='*60}\n"
            f"  {status}\n"
            f"  Project : {self.output_dir}\n"
            f"  Files   :\n{files}\n"
            f"{'='*60}\n"
        )
