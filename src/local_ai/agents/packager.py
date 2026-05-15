"""
Packager Agent
Final stage: writes a comprehensive README.md, generates an OpenAPI spec
for API projects, initialises git with an initial commit, and prints a
clean handoff summary.
"""

from .shared.llm import run_agent_loop
from .shared.tools import READ_FILE, WRITE_FILE, LIST_FILES, RUN_COMMAND, HANDLERS
from .shared.memory import Project

SYSTEM = """You are a senior technical writer and project handoff specialist.

Your job is to package a completed application for handoff to a developer.

1. **README.md** — write a genuinely useful README that includes:
   - Project name + one-line description
   - Tech stack (as a bullet list or badges)
   - Architecture overview with a Mermaid diagram (flowchart or C4 component)
   - Prerequisites (exact versions needed)
   - Setup instructions: clone → install deps → copy .env.example → run migrations → start
   - API reference table (method | path | auth required | description) if applicable
   - Development workflow (run tests, add a feature, code style)
   - Deployment instructions (Docker, cloud platform from the devops config)
   - Licence placeholder

2. **openapi.yaml** — only if this is an API project:
   - Generate from route definitions using read_file to inspect the routes
   - Include all endpoints, request/response schemas, and auth (Bearer/APIKey)

3. **Git initialisation** — run in the output directory:
   - `git init`
   - `git add .`
   - `git commit -m "feat: initial generated application"`

4. Print a clean handoff summary: what was built, how to run it, what's next.

Read source files before writing — make the README accurate, not boilerplate.
"""


def run(project: Project) -> Project:
    print("  [Packager] Writing docs, initialising git, packaging …")

    out = str(project.output_dir)
    files_ctx = "\n".join(project.files_written) if project.files_written else "(see output dir)"

    task = f"""Project: {project.instruction}
Output directory: {out}

Files in the project:
{files_ctx}

Architecture plan summary:
{project.plan[:2000] if project.plan else 'See PLAN.md'}

Review / audit notes:
{((project.review or '') + ' ' + (project.audit or ''))[:1500] or 'None'}

1. Read the key source files to understand what was built (routes, models, components)
2. Write a comprehensive README.md at {out}/README.md
3. If this is an API, generate {out}/openapi.yaml from the route definitions
4. Run: git init && git add . && git commit -m "feat: initial generated application" in {out}
5. Print a handoff summary: what was built, how to run it, deployment steps
"""

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

    run_agent_loop(
        system=SYSTEM,
        user=task,
        tools=tools,
        handlers=handlers,
        on_tool_call=on_call,
    )

    project.files_written.extend(written)
    project.packaged = True
    print("  [Packager] Done.\n")
    return project
