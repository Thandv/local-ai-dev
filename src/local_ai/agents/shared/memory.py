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
    design:        str = ""       # Designer agent output (UI/UX spec)
    research:      str = ""       # Researcher agent output
    plan:          str = ""       # Architect agent plan (also written to PLAN.md)
    files_written: list = field(default_factory=list)  # Paths written by all agents
    debug_log:     str = ""       # Debugger agent output
    test_results:  str = ""       # Tester output
    audit:         str = ""       # Auditor agent output
    review:        str = ""       # Reviewer output
    packaged:      bool = False   # Whether Packager ran successfully
    success:       bool = False   # Did tests/build pass?

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
            "packaged":    self.packaged,
        }
        (self.output_dir / "BUILD_LOG.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8"
        )

    def summary(self) -> str:
        status  = "✓ SUCCESS" if self.success else "✗ INCOMPLETE"
        packaged = "  Packaged: yes (README + git init)\n" if self.packaged else ""
        files   = "\n".join(f"  • {f}" for f in self.files_written)
        return (
            f"\n{'='*60}\n"
            f"  {status}\n"
            f"  Project : {self.output_dir}\n"
            f"{packaged}"
            f"  Files   :\n{files}\n"
            f"{'='*60}\n"
        )
