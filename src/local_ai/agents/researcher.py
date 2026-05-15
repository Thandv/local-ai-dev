"""
Researcher Agent
Analyses the user's instruction, identifies the tech stack, and gathers
real code patterns from the local reference repos.
Output: a research brief the architect and coder will use.
"""

import re
from pathlib import Path
from .shared.llm import run_agent_loop
from .shared.tools import grep_repos
from .shared.memory import Project

SYSTEM = """You are a senior software research agent.
Given a description of an app to build, your job is to:
1. Identify the best technology stack for this project
2. Note key patterns, libraries, and conventions to follow
3. Surface any important architectural decisions upfront

Be concrete and opinionated. Choose the most modern, production-ready defaults.
Keep your output structured — use headings, bullet points, and short code samples.
Do not write the actual app — only research and recommendations.
"""


def _extract_keywords(instruction: str) -> list[str]:
    stop = {"a", "an", "the", "and", "or", "with", "for", "that", "this",
            "to", "of", "in", "on", "is", "i", "want", "build", "create",
            "make", "app", "me", "my", "need", "can", "use", "using", "full"}
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", instruction.lower())
    return [w for w in words if w not in stop][:8]


def run(project: Project) -> Project:
    print("  [Researcher] Analysing instruction and gathering patterns …")

    keywords = _extract_keywords(project.instruction)
    repo_patterns = grep_repos(keywords)

    task = f"""Instruction: {project.instruction}

Reference code patterns found in top open-source projects:
{repo_patterns}

Write a research brief covering:
## Tech Stack
(languages, frameworks, libraries — be specific with versions if relevant)

## Project Structure
(recommended folder/file layout)

## Key Patterns
(authentication approach, state management, database, API style, etc.)

## Dependencies
(exact package names to install)

## Gotchas & Best Practices
(anything that commonly trips people up with this stack)
"""

    def on_call(name, args):
        print(f"    [{name}]")

    project.research = run_agent_loop(
        system=SYSTEM,
        user=task,
        tools=[],          # researcher reasons only, no file tools needed
        handlers={},
        on_tool_call=on_call,
    )

    print("  [Researcher] Done.\n")
    return project
