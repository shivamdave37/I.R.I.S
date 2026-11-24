# 04 — `task_planner.py`: the action-control center

## File purpose and imports

The module docstring says it validates fixed-skill plans and runs approved steps. It imports `dataclass`/`field` for the step record, `json` for model plans, `re` for parsing, and Iris modules `ai`, `config`, `skills`, and `skill_development` for external interpretation, allowlists, fixed actions, and inert proposals.

## Limits and registries

`MAX_STEPS = 8` bounds plan length. `MAX_NOTE_LENGTH = 2000` limits saved-note text at planning validation. `SKILL_PERMISSIONS` maps consequential skill names to human-readable permission descriptions. `SKILL_SCHEMAS` maps every known skill to the exact set of required parameter names; an empty set means no parameters. `ACTION_WORDS` contains phrases that make an otherwise ambiguous request look like an attempted task, so it goes to constrained planning instead of ordinary chat.

The two registries are security-relevant: the model may suggest names, but it cannot add entries to them at runtime.

## `PlanStep` dataclass

Fields are: `step_id`, selected `skill`, parameter dictionary, earlier-step IDs in `depends_on`, permission text, status initially `pending`, and result initially empty. `field(default_factory=list)` gives each step its own dependency list. The status is updated as execution proceeds.

## Input cleanup and deterministic parsing

### `_normalized(text)`

Converts null/false-like input to an empty string, otherwise to text; strips ends, lowercases, splits on whitespace, and joins with one space. This makes matching tolerant of capitalization and extra spaces.

### `_open_target(text)`

Normalizes, removes polite request prefixes using `re.sub`, then requires the full remaining phrase to match a supported open verb and one target. It strips punctuation around the extracted target. Returning `None` means the phrase did not match.

### `_known_parts(command)`

Tries explicit comma/and/then separators. Regex lookaheads split before command-like words rather than every word “and.” The function accepts a split only when every segment can already be parsed by `_parse_local`; otherwise it returns an empty list and leaves the full phrase intact.

### `_parse_local(command)`

Uses normalized exact phrase sets for time, date, help, and list-notes. Regex patterns extract search text, note number, research query, proposal name/purpose, proposal action/name/version, and note text. `_open_target()` recognizes opening; only names in `config.APPS` or `config.WEBSITES` become `open_target`. A syntactically openable but unknown target becomes an internal `unsupported_open` marker, which is reported without asking AI to invent a new path. Unknown non-open phrases return `None`.

The parser returns `(skill_name, params)` data; it does not itself launch or write anything.

## Validation functions

### `_validate_step(step_data, index, prior_ids)`

This is the main boundary for one step. It requires exactly four outer keys: `id`, `skill`, `params`, and `depends_on`. IDs must follow sequential names (`step_1`, `step_2`, ...). Skill must exist in `SKILL_SCHEMAS`. Parameters must be a dictionary and dependencies a list. Dependencies must refer only to earlier step IDs and may not repeat.

Then the function compares the actual parameter keys with the registered exact schema. It validates target allowlisting; text types, non-empty strings, and maximum lengths; query length; proposal name format and purpose length; positive proposal version and note index; and the special Boolean-versus-integer case (`bool` is an `int` subclass in Python). It builds a human-readable permission string for sensitive skills and returns a `PlanStep`.

Potential limitation: schemas and checks are manually maintained; a new skill must be added in the registry, validation, preview/permission logic as needed, and `_run_step` dispatch.

### `validate_plan(payload)`

Requires a dictionary with only a `steps` list, one to eight items, and validates each in order while extending the set of valid earlier IDs. It refuses a plan containing both `research_web` and `save_note`, so Iris does not save AI research automatically. Returns a list of validated `PlanStep` objects. A `ValueError` is the fail-closed result for malformed plans.

### `_unique_object(pairs)`

Used by JSON parsing to reject repeated keys. Normal JSON decoding can otherwise keep one duplicate value and hide ambiguity. It raises `ValueError` on a repeated field.

### `_model_plan(command)`

Calls `ai.plan_request`, requires text, trims it, optionally strips one Markdown JSON fence, parses JSON with `_unique_object`, then calls `validate_plan`. AI output remains untrusted until all these checks succeed.

### `_deterministic_plan(command)`

Uses known segments or the full input, parses every segment locally, rejects too many steps, returns `None` when any phrase is unknown, and reports unsupported open targets as a special tuple. If all local parses are supported, it builds step IDs in order and validates each before returning the list.

### `_looks_like_task(command)`

Normalizes text and checks whether any action phrase from `ACTION_WORDS` appears. This distinguishes likely action attempts from plain questions. It is a heuristic, not a language-understanding model.

## Approval, preview, execution

### `_approval(action, input_fn)`

Calls the injected input function with an approval prompt; EOF or Ctrl+C denies. Only a string whose stripped, case-folded value is exactly `yes` approves. “y”, spoken text, or other input does not.

### `_describe_plan(steps)`

Builds a preview string containing order, skill, parameters, dependency names, and whether approval is needed. It does not perform any action.

### `_run_step(step, input_fn)`

Uses explicit branches to dispatch each known skill to a fixed function. It passes only validated named parameters. It never uses `eval`, generated Python, or a shell command. An unrecognized skill raises `ValueError` as a final defensive check.

### `_execute(steps, input_fn)`

First it asks for all ordinary approvals before beginning side effects. If any approval is declined, it marks the denied step and all still-pending steps skipped and returns a cancelled summary. `after-preview:` actions ask for a second, specialized approval inside `skill_development.py` after displaying exact content.

After approvals, it maps step IDs to objects. A step whose dependency did not succeed becomes skipped. Otherwise status changes `pending → running → succeeded/failed/denied`. It runs the fixed dispatch, converts result to text, and classifies known error prefixes as failure. Exceptions mark the step failed; app-launch failure is phrased with its target, while other failures expose only the exception type. Independent steps can continue after a failure; dependent ones cannot.

**Design caveat:** success/failure classification depends partly on string prefixes. If a skill's error wording changes without updating this list, a failure might be mislabeled. This is a viva-worthy limitation.

### `_summary(steps, cancelled=False)`

Formats each result with its status and counts succeeded, failed, and skipped steps. On denial it explicitly says no steps were run. On normal completion it reports counts. The summary is a report, not proof that an external side effect truly happened.

### `handle(command, input_fn=input)`

The public planner entry point normalizes empty and exit requests; tries deterministic parsing; turns validation errors into a safe message; refuses unsupported open targets; and handles unknown phrases in two ways. Plain questions go to `ai.ask()` directly. Action-like unknown phrases go through `_model_plan()`. If model planning or validation fails, it returns an error and runs no steps. A valid plan is previewed, executed, and summarized. For one successful step it returns only that step's result for a simpler user experience.

## Safe trace

For `open Notepad and note study Python tomorrow`, local parsing creates two steps. Both are validated and displayed. The app-open permission and note-save permission are requested before either side effect starts. If the first answer is `no`, the opener is not called and the note step is skipped. If both are `yes`, the opener and note writer are dispatched in order.

### Recap and questions

1. Why does the model not select arbitrary Python code? Its output must be JSON using fixed schemas.
2. Why validate the full plan before executing? To prevent a later invalid step from being discovered after an earlier side effect.
3. Why do dependent steps skip after prerequisite failure? They may not make sense without that result.
4. Can independent steps continue? Yes, by current execution policy.
5. What makes approval exact? Only typed, case-insensitive `yes` after trimming.

**Exercise:** Given a fake plan with an unknown skill, list which validation check rejects it and whether any skill should run. Correct answer: skill membership rejects it before preview/execution; no skill runs.
