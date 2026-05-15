# Local AI Dev Suite

A fully local AI-powered development environment — 11-stage autonomous app builder, interactive vibe coder, and quick coding assistant.
Runs entirely on your machine. No API keys. No cloud. No data leaves your device.

---

## Install (one binary, any platform)

Download the binary for your platform from the [latest release](../../releases/latest):

| Platform | Binary |
|----------|--------|
| macOS | `local-ai-setup-macos` |
| Linux | `local-ai-setup-linux` |
| Windows | `local-ai-setup-windows.exe` |

**macOS / Linux**
```bash
chmod +x local-ai-setup-macos   # or local-ai-setup-linux
./local-ai-setup-macos
```

**Windows (PowerShell)**
```powershell
.\local-ai-setup-windows.exe
```

The installer handles everything:
- Installs [Ollama](https://ollama.com) (local LLM server)
- Downloads `qwen2.5-coder:7b` (~4.7 GB coding model)
- Installs the Python package and all dependencies
- Clones 14 curated open-source repos as coding references
- Registers the `vibe`, `build-app`, `ai`, and `ai-index` commands

---

## Commands

| Command | What it does |
|---------|-------------|
| `build-app "..."` | 11-stage autonomous pipeline: idea → production-ready app package |
| `vibe` | Interactive AI coding session in any directory |
| `ai` | Quick one-off coding question or task |
| `ai-index` | Update the 14 reference repos |

---

## The Autonomous App Builder

`build-app` runs 11 specialist agents in sequence. Give it a plain-English description; it produces a fully documented, deployable application.

### Quick start

```bash
# Basic build
build-app "Create a REST API for a todo list with FastAPI and SQLite"

# Use a template
build-app --template saas "Project management tool with teams and billing"
build-app --template api  "Weather data aggregator with caching"
build-app --template fullstack "E-commerce store with inventory management"

# Control the output
build-app --out ~/myproject "A Next.js blog with markdown and RSS"
build-app --interactive "A SaaS dashboard"   # review PLAN.md before coding starts
build-app --no-review --no-audit "Quick Flask prototype"  # skip stages for speed
```

### The 11-stage pipeline

```
Your idea
    │
    ▼
┌────────────┐
│  Designer  │  Writes DESIGN.md — screens, component tree, theme tokens
└─────┬──────┘
      ▼
┌────────────┐
│ Researcher │  Identifies tech stack, greps 14 reference repos for patterns
└─────┬──────┘
      ▼
┌────────────┐
│  Architect │  Designs full file tree + API routes → writes PLAN.md
└─────┬──────┘
      ▼
┌────────────┐
│  Migrator  │  Generates DB schema, Alembic/Prisma migrations, seed data
└─────┬──────┘
      ▼
┌────────────┐
│    Coder   │  Writes every source file, installs dependencies
└─────┬──────┘
      ▼
┌────────────┐
│  Debugger  │  Runs startup checks, fixes errors in a loop (up to 5×)
└─────┬──────┘
      ▼
┌────────────┐
│   Tester   │  Writes + runs tests, auto-fixes failures (up to 3×)
└─────┬──────┘
      ▼
┌────────────┐
│  Auditor   │  Security scan (bandit/npm audit), fixes critical issues → SECURITY.md
└─────┬──────┘
      ▼
┌────────────┐
│   DevOps   │  Writes Dockerfile, docker-compose, GitHub Actions CI, Makefile
└─────┬──────┘
      ▼
┌────────────┐
│  Reviewer  │  Final quality pass → writes REVIEW.md
└─────┬──────┘
      ▼
┌────────────┐
│  Packager  │  Writes README, generates openapi.yaml, runs git init + first commit
└────────────┘
      │
      ▼
~/builds/<project>/
```

### Output files

Every build produces:

```
~/builds/<project>/
  DESIGN.md        ← UI/UX spec (screens, components, theme)
  PLAN.md          ← architecture and file tree
  SECURITY.md      ← security audit findings and fixes
  REVIEW.md        ← final code review
  README.md        ← full project documentation
  openapi.yaml     ← API spec (if applicable)
  Dockerfile       ← production container
  docker-compose.yml
  .env.example     ← all required environment variables
  .github/
    workflows/
      ci.yml       ← GitHub Actions CI/CD
  Makefile         ← dev, test, build, docker-run targets
  BUILD_LOG.json   ← pipeline metadata and checkpoint state
  <source files>   ← the actual application
```

### All CLI flags

```
build-app [instruction]

Workflow:
  --interactive, -i     Pause after PLAN.md so you can review before coding starts
  --resume <dir>        Continue a previous build from its last completed stage
  --fix <dir>           Run the Debugger on an existing build to fix a known error
    --error "msg"         Error text to inject into the Debugger context

Templates (prepend a canned instruction):
  --template saas       SaaS app with auth, billing, dashboard, landing page
  --template api        REST API with JWT, CRUD, rate limiting, OpenAPI docs
  --template dashboard  Data dashboard with charts, filters, CSV export
  --template cli        CLI tool with subcommands, rich output, config file
  --template fullstack  FastAPI + React + PostgreSQL + Docker

Output:
  --out, -o <dir>       Write to a specific directory instead of ~/builds/

Skip individual stages (faster builds, less complete output):
  --no-designer         Skip DESIGN.md generation
  --no-debug            Skip startup error checking
  --no-devops           Skip Dockerfile / CI generation
  --no-audit            Skip security scan
  --no-package          Skip README / git init
  --no-review           Skip final code review
```

### Resume and fix broken builds

If a build fails halfway or you run it out of disk space, resume exactly where it stopped:

```bash
# Pick up from the last completed stage
build-app --resume ~/builds/my-app-1430

# Fix a known runtime error without rerunning the full pipeline
build-app --fix ~/builds/my-app-1430 --error "ModuleNotFoundError: No module named 'uvicorn'"
```

---

## The Vibe Coder

```bash
cd ~/myproject
vibe
```

An interactive AI coding session in your current directory. The vibe coder reads your files, writes new ones, runs commands, and fixes bugs through plain English.

```
You: Add JWT auth to the /users endpoint
You: Write pytest tests for the auth flow
You: The login endpoint is returning 422 — fix it
You: Refactor the database models to use async SQLAlchemy
You: clear   ← reset conversation
You: exit    ← quit
```

---

## Reference Repos

Both `build-app` and `vibe` search 14 curated open-source repos for real working patterns at query time — no vector DB, just fast `grep`:

`fastapi` · `starlette` · `flask` · `django` · `sqlalchemy` · `pydantic` ·
`next.js` · `react` · `vite` · `shadcn/ui` · `tailwindcss` · `prisma` · `trpc` · `zustand`

Add more repos by editing `repos.json` and running `ai-index`.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen2.5-Coder 7B (local, via Ollama) |
| Code retrieval | grep over 14 cloned repos (no vector DB) |
| Runtime | Python 3.10+ |
| Distribution | PyInstaller single-file binary |
| CI/CD | GitHub Actions (builds macOS + Linux + Windows on tag push) |

---

## Development

**Requirements:** Python 3.10+, Git

```bash
git clone https://github.com/Thandv/local-ai-dev
cd local-ai-dev

# Install in dev mode
make install          # pip install -e .

# Run the test suite
python -m pytest      # 322 tests, all offline (no Ollama required)

# Build a binary for your current platform
make binary           # → dist/local-ai-setup
```

### Running tests

The full test suite runs offline — Ollama is never contacted. `run_agent_loop` is mocked at each agent's module namespace so tests are fast and deterministic.

```bash
python -m pytest              # run everything
python -m pytest tests/test_agents.py -v    # just agent tests
python -m pytest tests/test_orchestrator.py # just orchestrator tests
python -m pytest -k "retry"   # filter by name
```

Test coverage:

| File | Tests | What's covered |
|------|-------|---------------|
| `test_memory.py` | 38 | Project dataclass, save\_log, summary, files\_written |
| `test_tools.py` | 58 | All 5 tool implementations, schemas, HANDLERS |
| `test_llm.py` | 35 | \_extract\_tool\_calls, run\_agent\_loop, chat |
| `test_orchestrator.py` | 48 | Stage selection, skip flags, resume, fix(), checkpoints |
| `test_build_cli.py` | 43 | All flag combinations, templates, --resume, --fix |
| `test_agents.py` | 66 | All 11 agents, retry loops, cross-agent contracts |
| `test_indexer.py` | 20 | clone\_or\_update, build\_index, limit, failure handling |

---

## Repo Structure

```
local-ai-dev/
  src/local_ai/
    agents/
      shared/
        llm.py           ← Ollama client + agentic tool-call loop
        tools.py         ← shared tool implementations and schemas
        memory.py        ← Project state object passed through pipeline
      designer.py        ← UI/UX spec → DESIGN.md
      researcher.py      ← tech stack + pattern research
      architect.py       ← project design + PLAN.md
      migrator.py        ← DB schema, migrations, seed data
      coder.py           ← source file generation
      debugger.py        ← startup error detection + fix loop
      tester.py          ← test writing + auto-fix loop
      auditor.py         ← security scan → SECURITY.md
      devops.py          ← Dockerfile, CI, Makefile
      reviewer.py        ← quality review + REVIEW.md
      packager.py        ← README, openapi.yaml, git init
    orchestrator.py      ← pipeline coordinator (resume, fix, skip)
    vibe.py              ← interactive coding session
    agent.py             ← simple one-off agent
    indexer.py           ← reference repo cloner
    build_cli.py         ← build-app CLI entry point
    repos.json           ← curated reference repo list
  tests/
    conftest.py          ← shared fixtures
    test_memory.py
    test_tools.py
    test_llm.py
    test_orchestrator.py
    test_build_cli.py
    test_agents.py
    test_indexer.py
  scripts/
    setup_installer.py   ← cross-platform installer (PyInstaller entry point)
  .github/workflows/
    release.yml          ← smoke test → 3-platform binary builds → GitHub Release
  Makefile
  pyproject.toml
```

---

## Releasing a new version

```bash
git tag v2.1.0
git push origin v2.1.0
```

GitHub Actions runs the smoke test, then builds `local-ai-setup-macos`, `local-ai-setup-linux`, and `local-ai-setup-windows.exe` in parallel and attaches them to the release.

---

## License

MIT
