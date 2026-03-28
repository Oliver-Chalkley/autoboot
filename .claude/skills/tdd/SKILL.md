---
name: tdd
description: Enforce the TDD planning and verification cycle
---

# TDD Workflow Commands

## `/plan`
Create a planning document for a new feature.

1. Create a markdown file at `docs/plans/<feature-name>.md`
2. Define the exact function signature with type hints
3. List 3-5 edge cases (empty input, wrong types, large files, etc.)
4. Do NOT write any implementation code yet

## `/verify`
Run the production-readiness checklist:

1. Run `uv run pytest`
2. Run `uv run ruff check .`
3. Run `uv run pyright`
4. Check Google-style docstrings on all new public functions

Provide a Pass/Fail summary for each check.
