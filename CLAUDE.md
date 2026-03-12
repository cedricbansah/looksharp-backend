# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

See [docs/project-overview.md](docs/project-overview.md).

---

## Common Commands

See [docs/common-commands.md](docs/common-commands.md).

---

## Architecture

See [docs/architecture.md](docs/architecture.md).

---

## Key Patterns

See [docs/key-patterns.md](docs/key-patterns.md).

---

## Testing Conventions

See [docs/testing-conventions.md](docs/testing-conventions.md).

---

## Environment Variables

See [docs/environment-variables.md](docs/environment-variables.md).



## Code Writing Rules

1. **Before writing any code, describe your approach and wait for approval.** Always ask clarifying questions before writing any code if requirements are ambiguous.

2. **If a task requires changes to more than 3 files, stop and break it into smaller tasks first.**

3. **After writing code, list what could break and suggest tests to cover it.**

4. **When there's a bug, start by writing a test that reproduces it, then fix it until the test passes.**

5. **Every time I correct you, add a new rule to the CLAUDE.md file so it never happens again.**

6. **Never assume data values exist - always verify from source.** Before using any data (page titles, route names, config values, etc.), read the actual source file that defines them. Don't guess or assume.

7. **Update lessons.md IMMEDIATELY after any correction.** This is non-negotiable and happens BEFORE continuing with other work. The workflow is: receive correction → update lessons.md → update CLAUDE.md if needed → continue task.

8. **Announce skill invocations in output.** When invoking a skill (e.g., `senior-frontend`, `code-reviewer`), explicitly mention it in the response so the user knows what tools are being used.

9. **Document all bug fixes in lessons.md.** After fixing any bug reported by the user, add an entry to the "Bug Fixes" section in `tasks/lessons.md` with: date, bug description/error message, root cause, fix applied, and file(s) changed.

---

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how
