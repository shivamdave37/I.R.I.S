# 07 — Workflows and safety boundaries

## 1. Startup and exit

Run `python main.py` from the project folder. `main.run()` configures logs, prints readiness, and loops. Type `exit`, `quit`, or `goodbye`; Ctrl+C and end-of-input also exit. Tests mock input and logging; they do not prove behavior under every Windows console condition.

## 2. Help, date, and time

These known phrases are parsed locally by `_parse_local`; planner validates a zero-parameter skill and dispatches to `skills.help_text`, `tell_time`, or `tell_date`. No model request is required. Time/date use the computer's local timezone/clock.

## 3. Opening an app or website

Example: `open Notepad`. The local parser normalizes the target and checks `config.APPS` or `config.WEBSITES`. The plan preview names the target and approval. Exact typed `yes` permits `_run_step()` to call `skills.open_approved()`. This only attempts a configured path/URL; real application presence and default browser are machine-specific.

## 4. Notes

`note buy milk` creates a `save_note` step. Planner validates text and asks permission. `skills.add_note()` checks path and existing JSON, appends, and atomically writes under `data/notes.json`. `show notes` lists; `search notes for milk` finds case-insensitive substrings; `delete note 1` requires planner approval and the skill's `approved=True` guard. Tests use temporary data directories; do not use real user notes as test fixtures.

## 5. Multi-step planning and approvals

Known steps are locally split only at recognized command boundaries. The plan is fully validated and previewed before action. All ordinary permissions are requested before any step executes. Denying any one approval marks it denied, skips remaining steps, and runs nothing. After execution begins, failed prerequisite steps cause dependent steps to skip; unrelated steps may continue. Final summary lists statuses.

Example denial trace: `open Notepad and note IRIS_MARKER` → preview two steps → answer `no` to first prompt → `open_target [denied]`, `save_note [skipped]`, and no notes file change. This behavior is covered by a unique-marker integration regression test using temporary storage and mocked app launch.

## 6. Gemini/Ollama chat and planning

An ordinary unknown question goes to `ai.ask()` directly. `IRIS_AI_PROVIDER` chooses Gemini or Ollama, with `config.AI_PROVIDER` as default. Gemini needs a key; Ollama needs a running local service and configured model. When an action phrase is ambiguous, the AI may return a plan JSON; `task_planner` validates it and rejects unknown names/arguments before any action. Chat text is not a command channel.

## 7. Live research

Use a supported deterministic phrase such as `research Python 3.14 changes`. The planner requires approval, then `skills.research_web()` calls `ai.research_web()`. `IRIS_RESEARCH_PROVIDER` selects Gemini or Tavily; absent that, AI provider/default applies. Gemini requires `GEMINI_API_KEY`; Tavily requires `TAVILY_API_KEY` and `IRIS_RESEARCH_PROVIDER=tavily`. The output must contain valid HTTPS URLs before a summary is presented. A 429 is reported without a retry; the actual service quota must be addressed outside the code.

**Verified status:** response formatting and error cases are tested with mocks. Gemini previously returned quota exhaustion. Tavily has not been live-tested in this guide. Therefore, do not claim live web research currently succeeds.

## 8. Skill proposals

The proposal request first needs planner approval. AI returns inert source text; AST checks inspect structure; Iris shows the proposal and asks another exact typed yes to save it. A later approval records permission for manual integration, not runtime activation. Runtime tests are explicitly not run because no isolated sandbox is provided.

## Safety design: what it protects and what it does not

| Mechanism | Helps protect against | Does not prove/protect against |
|---|---|---|
| Fixed skill schema and explicit dispatch | Model inventing a new callable action | Bugs in trusted Python skills |
| Exact typed approval | Accidental/ambiguous approval | Another person at the keyboard, compromised process, or misleading plan wording |
| Full-plan validation first | Partial work before a later malformed step is found | External side effects after execution begins |
| Dependency status checks | Running a step whose prerequisite failed | Every semantic dependency being correctly declared |
| App/site allowlist | Arbitrary target strings | Wrong configured path or malicious content opened in a browser |
| HTTPS URL/source validation | Obvious unsafe/malformed source links | Truth or quality of page content |
| Response-size/time bounds | Indefinite wait and oversized body | Provider outages, quota, all network attacks |
| Temporary atomic note writes | Common partial-write problems | Disk loss, all filesystem races, backup/recovery |
| Proposal AST checks + never-run policy | Accidental execution of generated code | Inactive draft being correct/useful, or a human making a poor manual integration |
| Secret files ignored and generic logs | Accidental tracking/logging | Secret exposure by unrelated tools or user behavior |

Iris is not “perfectly secure.” It is a prototype with defense-in-depth safeguards. Its safety depends on the correctness of trusted code and the environment.

### Recap and exercise

Trace `open YouTube and note meeting Friday` through parser, preview, approvals, execution, and final response. Then change one approval answer to `no`. Predict which functions do not run. Correct result: after any denial during the pre-approval loop, no side-effect function is dispatched.
