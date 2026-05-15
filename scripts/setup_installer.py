#!/usr/bin/env python3
"""
local-ai-setup — Cross-platform installer for the Local AI Dev Suite.

When built with PyInstaller this becomes a single executable binary.
Run it on macOS, Linux, or Windows and it sets everything up automatically:

  - Installs Ollama
  - Pulls the coding model (qwen2.5-coder:7b)
  - Installs the local-ai-dev Python package
  - Clones 14 curated reference repos
  - Registers global shell commands

Usage:
  ./local-ai-setup            (macOS / Linux)
  local-ai-setup.exe          (Windows)
  ./local-ai-setup --dry-run  (preview what would be done)
  ./local-ai-setup --model qwen2.5-coder:14b  (larger model)
"""

import sys
import os
import platform
import subprocess
import shutil
import argparse
import json
import urllib.request
import tempfile
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

NO_COLOUR = not sys.stdout.isatty() or platform.system() == "Windows"

def c(text, code):
    return text if NO_COLOUR else f"\033[{code}m{text}\033[0m"

def ok(msg):   print(c(f"  ✓ {msg}", "32"))
def info(msg): print(c(f"  → {msg}", "36"))
def warn(msg): print(c(f"  ! {msg}", "33"))
def err(msg):  print(c(f"  ✗ {msg}", "31"))
def head(msg): print(f"\n{c(msg, '1;34')}")

# ── Platform detection ────────────────────────────────────────────────────────

OS      = platform.system()   # Darwin / Linux / Windows
ARCH    = platform.machine()  # arm64 / x86_64 / AMD64
IS_MAC  = OS == "Darwin"
IS_LIN  = OS == "Linux"
IS_WIN  = OS == "Windows"

INSTALL_DIR = Path.home() / "Claude"
REPOS_DIR   = Path.home() / ".local-ai" / "repos"
MODEL       = "qwen2.5-coder:7b"

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, check=True, capture=False, **kwargs):
    kw = dict(shell=True, text=True, **kwargs)
    if capture:
        kw["capture_output"] = True
    result = subprocess.run(cmd, **kw)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    return result


def cmd_exists(name):
    return shutil.which(name) is not None


def pip_install(*packages):
    run(f"{sys.executable} -m pip install --quiet {' '.join(packages)}")

# ── Step functions ────────────────────────────────────────────────────────────

def check_python():
    head("Checking Python")
    v = sys.version_info
    if v < (3, 10):
        err(f"Python 3.10+ required (you have {v.major}.{v.minor})")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def check_git():
    head("Checking Git")
    if not cmd_exists("git"):
        err("Git not found. Install from https://git-scm.com")
        sys.exit(1)
    r = run("git --version", capture=True)
    ok(r.stdout.strip())


def install_ollama(dry_run=False):
    head("Installing Ollama")
    if cmd_exists("ollama"):
        r = run("ollama --version", capture=True)
        ok(f"Ollama already installed: {r.stdout.strip()}")
        return

    if dry_run:
        info("[dry-run] Would install Ollama")
        return

    if IS_MAC:
        if cmd_exists("brew"):
            info("Installing via Homebrew …")
            run("brew install ollama")
        else:
            info("Downloading Ollama for macOS …")
            _download_and_run_ollama_mac()
    elif IS_LIN:
        info("Installing via official script …")
        run("curl -fsSL https://ollama.com/install.sh | sh")
    elif IS_WIN:
        info("Downloading Ollama installer for Windows …")
        _install_ollama_windows()
    else:
        warn(f"Unknown OS: {OS}. Download Ollama manually from https://ollama.com")
        return

    ok("Ollama installed")


def _download_and_run_ollama_mac():
    url = "https://ollama.com/download/Ollama-darwin.zip"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "ollama.zip"
        info(f"Downloading {url} …")
        urllib.request.urlretrieve(url, zip_path)
        run(f"unzip -q {zip_path} -d {tmp}")
        app = Path(tmp) / "Ollama.app"
        if app.exists():
            run(f"cp -r {app} /Applications/Ollama.app")
            ok("Ollama.app installed to /Applications")


def _install_ollama_windows():
    url = "https://ollama.com/download/OllamaSetup.exe"
    dest = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    info(f"Downloading {url} …")
    urllib.request.urlretrieve(url, dest)
    info("Running installer (follow the prompts) …")
    run(f'"{dest}" /S', check=False)


def start_ollama(dry_run=False):
    head("Starting Ollama")
    if dry_run:
        info("[dry-run] Would start Ollama service")
        return

    r = run("ollama list", capture=True, check=False)
    if r.returncode == 0:
        ok("Ollama is running")
        return

    if IS_MAC:
        run("brew services start ollama", check=False)
    elif IS_LIN:
        run("systemctl --user start ollama", check=False)
    elif IS_WIN:
        run('start "" "C:\\Program Files\\Ollama\\ollama.exe" serve', check=False)

    import time
    time.sleep(3)
    ok("Ollama started")


def pull_model(model, dry_run=False):
    head(f"Pulling model: {model}")
    if dry_run:
        info(f"[dry-run] Would pull {model}")
        return

    r = run("ollama list", capture=True)
    if model in r.stdout:
        ok(f"{model} already downloaded")
        return

    info(f"Downloading {model} (this may take a few minutes) …")
    run(f"ollama pull {model}")
    ok(f"{model} ready")


def install_package(dry_run=False):
    head("Installing local-ai-dev package")
    if dry_run:
        info("[dry-run] Would install Python package")
        return

    # If running as a PyInstaller bundle, the source is bundled with us
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)  # type: ignore
        package_src = bundle_dir / "package"
        if package_src.exists():
            info(f"Installing from bundle into {INSTALL_DIR} …")
            if INSTALL_DIR.exists():
                shutil.rmtree(INSTALL_DIR)
            shutil.copytree(package_src, INSTALL_DIR)
            ok(f"Installed to {INSTALL_DIR}")
            return

    # Running from source — pip install from current directory
    info("Installing from source …")
    src = Path(__file__).parent.parent
    run(f"{sys.executable} -m pip install --quiet -e {src}")
    ok("Package installed")


def clone_repos(repos_json_path=None, dry_run=False):
    head("Cloning reference repos")

    if repos_json_path is None:
        # Look for repos.json relative to the install dir or bundle
        candidates = [
            INSTALL_DIR / "repos.json",
            Path(__file__).parent.parent / "src" / "local_ai" / "repos.json",
        ]
        if getattr(sys, "frozen", False):
            candidates.insert(0, Path(sys._MEIPASS) / "repos.json")  # type: ignore
        repos_json_path = next((p for p in candidates if p.exists()), None)

    if repos_json_path is None:
        warn("repos.json not found — skipping repo clone")
        return

    repos = json.loads(Path(repos_json_path).read_text())["repos"]
    info(f"Cloning {len(repos)} repos into {REPOS_DIR} …")

    if dry_run:
        for r in repos:
            info(f"  [dry-run] Would clone {r['url']}")
        return

    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    ok_count, fail = 0, []

    for repo_info in repos:
        url  = repo_info["url"]
        name = url.split("/")[-1]
        dest = REPOS_DIR / name

        if (dest / ".git").exists():
            info(f"  updating {name} …")
            r = subprocess.run(["git", "-C", str(dest), "pull", "--ff-only", "--quiet"],
                               capture_output=True)
        else:
            info(f"  cloning  {name} …")
            r = subprocess.run(["git", "clone", "--depth=1", "--quiet", url, str(dest)],
                               capture_output=True)

        if r.returncode == 0:
            ok_count += 1
        else:
            fail.append(name)

    ok(f"{ok_count} repos ready")
    if fail:
        warn(f"Failed: {', '.join(fail)} — re-run `ai-index` to retry")


def register_commands(dry_run=False):
    head("Registering shell commands")

    if IS_WIN:
        _register_windows(dry_run)
    else:
        _register_unix(dry_run)


def _register_unix(dry_run):
    bins = {
        "vibe":      f"{sys.executable} -m local_ai.vibe",
        "ai":        f"{sys.executable} -m local_ai.agent",
        "ai-index":  f"{sys.executable} -m local_ai.indexer",
        "build-app": f"{sys.executable} -m local_ai.build_cli",
    }
    # Prefer /usr/local/bin if writable, else ~/.local/bin
    bin_dir = Path("/usr/local/bin")
    if not os.access(bin_dir, os.W_OK):
        bin_dir = Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

    for name, cmd in bins.items():
        dest = bin_dir / name
        if dry_run:
            info(f"  [dry-run] Would write {dest}")
            continue
        dest.write_text(f"#!/bin/bash\n{cmd} \"$@\"\n")
        dest.chmod(0o755)
        ok(f"  {name} → {dest}")

    # Remind about PATH if using ~/.local/bin
    if str(bin_dir) == str(Path.home() / ".local" / "bin"):
        shell_rc = Path.home() / (".zshrc" if IS_MAC else ".bashrc")
        line = f'\nexport PATH="$HOME/.local/bin:$PATH"\n'
        existing = shell_rc.read_text() if shell_rc.exists() else ""
        if ".local/bin" not in existing:
            if not dry_run:
                shell_rc.write_text(existing + line)
            info(f"Added ~/.local/bin to PATH in {shell_rc.name} — restart your shell")


def _register_windows(dry_run):
    import winreg  # type: ignore

    scripts_dir = Path(sys.executable).parent / "Scripts"
    bins = {
        "vibe.cmd":      f"@{sys.executable} -m local_ai.vibe %*\n",
        "ai.cmd":        f"@{sys.executable} -m local_ai.agent %*\n",
        "ai-index.cmd":  f"@{sys.executable} -m local_ai.indexer %*\n",
        "build-app.cmd": f"@{sys.executable} -m local_ai.build_cli %*\n",
    }
    for name, content in bins.items():
        dest = scripts_dir / name
        if dry_run:
            info(f"  [dry-run] Would write {dest}")
            continue
        dest.write_text(content)
        ok(f"  {name} → {dest}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="local-ai-setup",
        description="Install the Local AI Dev Suite on this machine",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be done without making changes")
    parser.add_argument("--model", default=MODEL,
                        help=f"Ollama model to pull (default: {MODEL})")
    parser.add_argument("--skip-repos", action="store_true",
                        help="Skip cloning reference repos")
    parser.add_argument("--skip-model", action="store_true",
                        help="Skip pulling the model")
    args = parser.parse_args()

    print(c("\n  Local AI Dev Suite — Installer", "1;36"))
    print(f"  Platform : {OS} {ARCH}")
    print(f"  Python   : {sys.version.split()[0]}")
    print(f"  Install  : {INSTALL_DIR}")
    if args.dry_run:
        print(c("  Mode     : DRY RUN (no changes will be made)", "33"))

    check_python()
    check_git()
    install_ollama(args.dry_run)
    start_ollama(args.dry_run)

    if not args.skip_model:
        pull_model(args.model, args.dry_run)

    install_package(args.dry_run)

    if not args.skip_repos:
        clone_repos(dry_run=args.dry_run)

    register_commands(args.dry_run)

    print(c("\n  ✓ Setup complete!\n", "1;32"))
    print("  Commands available:")
    print("    vibe       — interactive AI coding session")
    print("    build-app  — multi-agent app builder")
    print("    ai         — quick coding assistant")
    print("    ai-index   — update reference repos\n")
    if not args.dry_run:
        print("  Try it:  build-app \"Create a todo app with FastAPI\"\n")


if __name__ == "__main__":
    main()
