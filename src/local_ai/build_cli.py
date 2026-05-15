#!/usr/bin/env python3
"""
build — CLI entry point for the multi-agent app builder.

Usage:
  build "Create a todo app with FastAPI and React"
  build "Build a weather CLI tool in Python"
  build --out ~/myproject "Build a REST API for a blog"
  build --no-review "Quick Flask CRUD app"
"""

import sys
import argparse
from pathlib import Path


from local_ai import orchestrator


def main():
    parser = argparse.ArgumentParser(
        prog="build",
        description="Multi-agent AI app builder — describe an app, get working code.",
    )
    parser.add_argument(
        "instruction",
        nargs="+",
        help='What to build, e.g. "A todo app with FastAPI and React"',
    )
    parser.add_argument(
        "--out", "-o",
        metavar="DIR",
        help="Output directory (default: ~/builds/<project-name>/)",
    )
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Skip the reviewer agent (faster)",
    )

    args = parser.parse_args()
    instruction  = " ".join(args.instruction)
    output_dir   = Path(args.out).expanduser() if args.out else None
    skip_review  = args.no_review

    orchestrator.run(
        instruction=instruction,
        output_dir=output_dir,
        skip_review=skip_review,
    )


if __name__ == "__main__":
    main()
