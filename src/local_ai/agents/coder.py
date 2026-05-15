"""
Coder Agent
Reads PLAN.md and writes every source file for the project.
Uses tools: read_file, write_file, list_files, run_command.
"""

from pathlib import Path
from .shared.llm import run_agent_loop
from .shared.tools import READ_FILE, WRITE_FILE, LIST_FILES, RUN_COMMAND, HANDLERS
from .shared.memory import Project

SYSTEM = """You are an expert software engineer who writes complete, production-quality code.

You will be given a project plan (PLAN.md) and must implement every file it specifies.

Rules:
- Write COMPLETE files — no TODOs, no placeholders, no "add your code here"
- Every file must be immediately runnable / importable
- Use modern, idiomatic patterns for the chosen stack
- Include all necessary imports
- Handle errors gracefully at system boundaries
- After writing all source files, install dependencies with run_command
- Do not write test files — a separate agent handles that

Start by reading PLAN.md, then implement each file in order.
"""


def run(project: Project) -> Project:
    print("  [Coder] Reading plan and writing source files …")

    out = str(project.output_dir)

    task = f"""Project: {project.instruction}

Output directory: {out}

Read the plan at {out}/PLAN.md then implement every file it describes.
Write all files into {out}/.
After writing the source files, install all required dependencies
(e.g. `pip install -r requirements.txt` or `npm install`) using run_command
with working_dir set to {out}.

Do NOT write test files — they will be handled separately.
"""

    # Intercept write_file to track created files
    written = []

    def tracked_write(path: str, content: str) -> str:
        result = HANDLERS["write_file"](path, content)
        written.append(path)
        return result

    handlers = {
        "read_file":   HANDLERS["read_file"],
        "write_file":  tracked_write,
        "list_files":  HANDLERS["list_files"],
        "run_command": HANDLERS["run_command"],
    }
    tools = [READ_FILE, WRITE_FILE, LIST_FILES, RUN_COMMAND]

    def on_call(name, args):
        if name == "write_file":
            print(f"    [write] {args.get('path', '')}")
        elif name == "run_command":
            print(f"    [run]   {args.get('command', '')[:80]}")
        else:
            print(f"    [{name}]")

    result = run_agent_loop(
        system=SYSTEM,
        user=task,
        tools=tools,
        handlers=handlers,
        on_tool_call=on_call,
    )

    project.files_written.extend(written)
    print("  [Coder] Done.\n")
    return project
