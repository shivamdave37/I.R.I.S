# Iris learning guide

This guide describes the repository as inspected on 27 October 2026. It includes the current, uncommitted Tavily research changes in `ai.py`, `task_planner.py`, `.env.example`, `README.md`, and research/AI tests. Those changes were already present; this guide did not edit them.

## Coverage checklist

- [x] Project inventory and current behavior: [00-project-overview.md](00-project-overview.md)
- [x] Architecture and module responsibilities: [01-architecture.md](01-architecture.md)
- [x] Python concepts seen in source and tests: [02-python-concepts.md](02-python-concepts.md)
- [x] Function/module-level source explanation, part 1: `main.py`, `router.py`, `config.py`: [03-entry-routing-config.md](03-entry-routing-config.md)
- [x] Function/module-level source explanation, part 2: `task_planner.py`: [04-task-planner.md](04-task-planner.md)
- [x] Function/module-level source explanation, part 3: `ai.py`: [05-ai-and-research.md](05-ai-and-research.md)
- [x] Function/module-level source explanation, part 4: `skills.py`, `skill_development.py`: [06-skills-and-proposals.md](06-skills-and-proposals.md)
- [x] User workflows and data flow: [07-workflows-and-safety.md](07-workflows-and-safety.md)
- [x] Dependencies and testing: [08-dependencies-and-tests.md](08-dependencies-and-tests.md)
- [x] Viva bank, glossary, recap, and exercises: [09-viva-and-revision.md](09-viva-and-revision.md)
- [x] Complete Python libraries and modules catalog: [11-python-libraries-and-modules.md](11-python-libraries-and-modules.md)

## Honest line-coverage note

This first pass gives a detailed module/function and behavior explanation, and names every discovered test method. It does **not yet** reproduce each source line in numbered blocks or explain every token/punctuation mark in isolation. That remaining literal line-by-line work is tracked by exact current line counts and files in [10-coverage-tracker.md](10-coverage-tracker.md). Blank lines and formatting-only punctuation have no independent behavior, but meaningful source lines still need individual annotated excerpts to satisfy the full request.

## Repository facts and boundaries

The root contains seven Python modules (`main.py`, `router.py`, `task_planner.py`, `skills.py`, `ai.py`, `skill_development.py`, `config.py`) and eight unittest files. There is no `requirements.txt`, `pyproject.toml`, `setup.py`, or Pipfile in the inspected root. `SPEC.md`, `HANDOFF.md`, and `AGENTS.md` were not present in the current checkout. The project uses standard-library modules and makes HTTPS requests with `urllib`; no third-party package is declared in this checkout.

The local `.env` exists but was deliberately not opened. Its content is not reproduced. `.env` is ignored by Git; `.env.example` contains blank placeholders. Current test evidence is 69 passing tests from `python -m unittest discover -s tests`; tests are mostly mocked and do not prove a live provider, account quota, microphone, speakers, or personal Windows application path works.

## Files in this guide

Read in order. Start with the overview, then architecture, Python basics, and the source guides. Later files follow whole workflows and finish with exam practice.
