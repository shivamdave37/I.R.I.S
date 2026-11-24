# 10 — Exact source-explanation coverage tracker

This tracker separates function-level explanations already delivered from the remaining literal line-by-line teaching requested. Counts below are `Get-Content | Measure-Object -Line` results from the inspected working tree on 27 October 2026. If source changes, rerun the count before continuing. No application source was edited to create this guide.

## Python source — explained by module/function; literal annotated lines remain

| File | Current lines | Current coverage | Literal numbered source blocks |
|---|---:|---|---|
| `main.py` | 42 | Startup, logging, loop, error/exit flow explained | Remaining: annotate lines 1–42 |
| `router.py` | 99 | Public path and each legacy helper's role described at module level | Remaining: annotate lines 1–99, especially unused private helpers |
| `config.py` | 20 | Paths, provider/model settings, allowlists explained | Remaining: annotate lines 1–20 |
| `task_planner.py` | 347 | Constants, dataclass, parser, validation, approval, execution, summary described by function | Remaining: annotate lines 1–347 |
| `ai.py` | 403 | Environment loading, HTTP, providers, formatting, research, proposal generation described by function | Remaining: annotate lines 1–403 |
| `skills.py` | 156 | Date/time, opening, note paths/CRUD, research described by function | Remaining: annotate lines 1–156 |
| `skill_development.py` | 203 | AST policy, storage, proposal, approval, withdrawal described by function | Remaining: annotate lines 1–203 |

## Tests — every discovered test method is named and its purpose summarized

All eight test files and each `test_...` method are described in [08-dependencies-and-tests.md](08-dependencies-and-tests.md). Literal numbered explanations of each test setup/assertion line remain:

| File | Current lines | Remaining literal explanation |
|---|---:|---|
| `tests/test_ai.py` | 110 | Lines 1–110 |
| `tests/test_main.py` | 21 | Lines 1–21 |
| `tests/test_phase5_integration.py` | 69 | Lines 1–69 |
| `tests/test_research.py` | 164 | Lines 1–164 |
| `tests/test_router.py` | 88 | Lines 1–88 |
| `tests/test_skill_development.py` | 107 | Lines 1–107 |
| `tests/test_skills.py` | 55 | Lines 1–55 |
| `tests/test_task_planner.py` | 137 | Lines 1–137 |

## Exact remaining scope

The remaining annotated source/test excerpts cover 2,021 current Python lines in total (1,270 application lines and 751 test lines). This is too much to present accurately as one short chapter; continue in separate, numbered sections in this order: `main.py`/`router.py`/`config.py`, `task_planner.py`, `ai.py`, `skills.py`/`skill_development.py`, then tests grouped by the table above. For each block, quote a small excerpt from the current repository, number the lines, explain syntax/data flow/side effects immediately below, and update this table only after that block is complete.

Other requested sections—project overview, architecture, concepts, current workflows, safety boundaries, dependencies, test-method purpose, viva preparation, glossary, and learning exercises—are present in guide chapters 00–09. The current project facts must be refreshed if source or provider configuration changes.
