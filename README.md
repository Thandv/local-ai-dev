# Local AI Dev Suite

A fully local AI-powered development environment — vibe coder, multi-agent app builder, and coding assistant.
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
chmod +x local-ai-setup-macos
./local-ai-setup-macos
```

**Windows (PowerShell)**
```powershell
.\local-ai-setup-windows.exe
```

The installer handles everything:
- Installs [Ollama](https://ollama.com) (local LLM server)
- Downloads `qwen2.5-coder:7b` (~4.7 GB coding model)
- Installs the Python package
- Clones 14 curated open-source repos as coding references
- Registers the `vibe`, `build-app`, `ai`, and `ai-index` commands

---

## What's Inside

| Command | What it does |
|---------|-------------|
| `build-app "..."` | Multi-agent pipeline: describe an app → get working code |
| `vibe` | Interactive AI coding session in any directory |
| `ai` | Quick coding Q&A |
| `ai-index` | Update the 14 reference repos |

---

## Build the installer yourself

**Requirements:** Python 3.10+, Git

```bash
git clone https://github.com/YOUR_USERNAME/local-ai-dev
cd local-ai-dev

# Install in dev mode
make install

# Build a binary for your current platform
make binary
# → dist/local-ai-setup  (or .exe on Windows)
```

---

## The Multi-Agent Builder

```bash
build-app "Create a REST API for a todo list using FastAPI with SQLite"
build-app "Build a React expense tracker with charts and local storage"
build-app "Write a Python CLI tool that converts CSV to JSON"
build-app --out ~/myproject "A Next.js blog with markdown and RSS"
build-app --no-review "A quick Flask CRUD app"
```

Five specialist agents collaborate on every build:

```
Your idea
    │
    ▼
┌─────────────┐
│  Researcher │  Identifies tech stack, greps 14 reference repos
└──────┬──────┘
       ▼
┌─────────────┐
│  Architect  │  Designs file structure + API → writes PLAN.md
└──────┬──────┘
       ▼
┌─────────────┐
│    Coder    │  Writes every source file, installs deps
└──────┬──────┘
       ▼
┌─────────────┐
│   Tester    │  Writes + runs tests, auto-fixes failures (3 attempts)
└──────┬──────┘
       ▼
┌─────────────┐
│  Reviewer   │  Security + quality check → writes REVIEW.md
└─────────────┘
       │
       ▼
  ~/builds/<project>/
```

Output every time:
```
~/builds/<project>/
  PLAN.md        ← architecture plan
  REVIEW.md      ← code review report
  BUILD_LOG.json ← pipeline metadata
  <source files> ← the actual app
```

---

## The Vibe Coder

```bash
cd ~/myproject
vibe
```

```
You: Add JWT auth to the /users endpoint
You: Write pytest tests for the auth flow
You: The login endpoint returns 422 — fix it
You: Refactor the database models to use async SQLAlchemy
You: clear   ← reset conversation
You: exit    ← quit
```

The vibe coder reads your existing files, writes new ones, runs commands, and fixes bugs — all through plain English.

---

## Reference Repos

The agents search these 14 repos for real patterns when you ask them to build something:

`fastapi` · `starlette` · `flask` · `django` · `sqlalchemy` · `pydantic` ·
`next.js` · `react` · `vite` · `shadcn/ui` · `tailwindcss` · `prisma` · `trpc` · `zustand`

Add more repos by editing `repos.json` and running `ai-index`.

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen2.5-Coder 7B (local, via Ollama) |
| Code retrieval | grep over 14 cloned repos |
| Runtime | Python 3.10+ |
| Tested on | Apple M2, Ubuntu 22.04, Windows 11 |

---

## Repo Structure

```
local-ai-dev/
  src/local_ai/
    agents/
      shared/
        llm.py          ← Ollama client + agentic tool loop
        tools.py        ← shared tool implementations
        memory.py       ← project state between agents
      researcher.py     ← tech stack + pattern research
      architect.py      ← project design + PLAN.md
      coder.py          ← source file generation
      tester.py         ← test writing + auto-fix loop
      reviewer.py       ← quality review + REVIEW.md
    orchestrator.py     ← pipeline coordinator
    vibe.py             ← interactive session
    agent.py            ← simple one-off agent
    indexer.py          ← repo cloner
    build_cli.py        ← build-app CLI
    repos.json          ← curated repo list
  scripts/
    setup_installer.py  ← cross-platform installer (PyInstaller entry)
  .github/workflows/
    release.yml         ← builds binaries for all 3 platforms on tag push
  Makefile              ← build targets
  pyproject.toml        ← package definition
```

---

## Releasing a new version

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions builds `local-ai-setup-macos`, `local-ai-setup-linux`, and `local-ai-setup-windows.exe` automatically and attaches them to the release.

---

## License

MIT
