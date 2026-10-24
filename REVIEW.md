# Stage 5 Review Pack

## Folder structure

```text
.
├── .env.example
├── .gitignore
├── AGENTS.md
├── HANDOFF.md
├── PROMPTS.md
├── README.md
├── REVIEW.md
├── STAGE_6.md              # Human-authored future plan
├── STAGE_7.md              # Human-authored future plan
├── SPEC.md
├── ai.py
├── confirm.py
├── config.py
├── main.py
├── requirements.txt
├── router.py
├── voice.py
├── iris/
│   ├── __init__.py
│   ├── agent_executor.py
│   ├── agent_permissions.py
│   ├── agent_planner.py
│   ├── console.py
│   ├── demo.py
│   ├── iris.py
│   ├── permissions.py
│   ├── resources.py
│   └── tasks.py
├── skills/
│   ├── __init__.py
│   ├── apps.py
│   ├── code_helper.py
│   ├── github_tools.py
│   ├── memory.py
│   ├── news.py
│   ├── notes.py
│   ├── timeinfo.py
│   └── web.py
└── tests/
    ├── test_ai.py
    ├── test_iris.py
    ├── test_news.py
    ├── test_router.py
    ├── test_stage4.py
    └── test_voice.py
```

`STAGE_6.md` and `STAGE_7.md` are user-authored untracked planning files in the project root. They are intentionally excluded from the Stage 4 builder commit.

## What the files do

- `config.py` stores approved apps and websites, AI settings, and the fixed project/data folder paths.
- `main.py` runs the typed/voice loop, records command history, prints results, and speaks replies when the selected mode uses speech.
- `router.py` routes built-in commands to the matching skill and sends other questions to `ai.ask_ai()`.
- `confirm.py` accepts explicit yes/no responses and can require keyboard input.
- `ai.py` talks to Gemini or Ollama through one function and keeps a short chat history.
- `voice.py` handles microphone input and the single queued speech thread.
- `skills/code_helper.py` sends only the selected clipboard text for an explanation or suggested fix. It never writes or runs suggested code.
- `skills/github_tools.py` runs only the approved Git commands in the project folder and asks for typed approval before staging, committing, and pushing.
- `skills/notes.py` saves and reads `data/notes.txt` with a file lock.
- `skills/memory.py` stores a name, preferences, and the latest 20 commands in `data/memory.json` with a file lock; it redacts the configured Gemini key from command history.
- `skills/news.py`, `skills/apps.py`, `skills/web.py`, and `skills/timeinfo.py` implement news, approved app/site opening, and time/date behavior.
- `tests/` has offline unit tests for voice, routing, AI/news, Stage 4 helpers, and Iris.
- `iris/tasks.py` stores task data and the fixed lifecycle states.
- `iris/resources.py` atomically reserves or releases Iris's logical resources.
- `iris/agent_permissions.py` selects required resources using fixed Python rules.
- `iris/agent_planner.py` plans known commands with fixed rules and accepts only validated chat plans from AI for unknown requests.
- `iris/agent_executor.py` sends commands through the existing router and checks pause/cancel flags between steps.
- `iris/iris.py` schedules tasks by priority with aging, starts and watches workers, reports status, and handles admin controls.
- `iris/permissions.py` prompts for resource approvals and persists non-sensitive grants under ignored `data/permissions.json`.
- `iris/console.py` routes worker prompts through the main keyboard loop.
- `iris/demo.py` demonstrates deadlock prevention, priority aging, and pause/resume.
- `.env.example` contains only the key placeholder; `.env`, local state, and dependencies are ignored.

## Run and test

Install packages into the project virtual environment with `python -m pip install -r requirements.txt`, copy `.env.example` to `.env`, add a private Gemini API key if using Gemini, then run `python main.py`. Set `USE_IRIS = True` in `config.py` to enable Iris; `False` keeps the earlier direct route. Run tests with `python -m unittest discover tests` and the demo with `python -m iris.demo`.

## Stage 5 behavior and human checks

- Clipboard code is treated as data; fixes are displayed only. Explain prints the full text and queues a short spoken summary.
- Notes and memory are stored under the ignored `data/` folder.
- Git tests mock subprocesses. They verify fixed list arguments and confirmation gates, not a real GitHub login or push.
- Real clipboard selection, speech, and GitHub push need the human's Windows session.
- Stage 3's real Gemini, Ollama, live RSS, and offline behavior remain human checks.
- Iris reserves all requested resources in one locked operation; the AI planner cannot select a Git or file-writing skill for an unknown request.
- Task execution is serialized so worker prompts share one input path. Resource ownership and priority selection remain managed by Iris.
- Sensitive `GIT_REPO`, `SCREEN_FOCUS`, and `NOTES_FILE` approvals require typed approval every time. Non-sensitive session and always grants use `data/permissions.json`.
- The demo and tests ran in the project's virtual environment. Real voice devices, app paths, Gemini/Ollama/RSS services, clipboard selection, and GitHub login/push still require a human check.
- To keep interactive Git confirmations, permission answers, and admin commands on one keyboard path, Iris starts one task at a time. The resource manager still supports atomic ownership of independent resources; adding concurrent task workers would need a shared UI loop that preserves this prompt guarantee.
- Unknown or complex user requests use one validated `chat` plan step. Multi-action commands are queued as separate tasks with `queue:` until a later version defines safe step arguments.

## Reviewer findings

### Stage 1
- The reviewer fixed repeated-space matching, punctuation-only fallback, `None` input handling, browser-launch reporting, and UTF-8 logging.

### Stage 2
- The reviewer enforced mic/speaker exclusivity, filtered empty speech, recovered the speech worker from engine errors, handled silence, normalized mode casing, and expanded tests. The reviewed suite had 27 passing tests.

### Stage 3
- The reviewer rolled back failed user messages from chat history, rejected the placeholder API key, decoded RSS HTML entities, routed conversational news phrases, guarded blank-key redaction, and expanded tests. The reviewed suite had 42 passing tests and no unresolved items.

### Stage 4 builder notes
- Added clipboard explain/fix commands, typed yes/no confirmation, notes, name/preferences and 20-command memory, and a fixed Git command flow with separate typed approvals.
- Fix suggestions are not pasted, run, or written to disk/logs. API keys are redacted from persistent command history and rejected in commit messages.
- Stage 4 unit tests mock AI, clipboard, confirmation, persistence paths, and Git subprocesses. The builder suite passed 58 tests.
- Manual testing still needs an actual Windows selection and optional GitHub login/push.

### Stage 4 reviewer findings
- Made explanation speech respect `MODE`, so typed mode stays silent while voice modes speak a short summary.
- Handled EOF/Ctrl+C at the commit-message prompt so interruption does not escape the command loop.
- Git failures return a safe, useful status without echoing raw remote errors that could contain credentials. Git action logs include only the fixed action and exit code.
- Confirmed suggested fixes are not pasted, run, saved, or included in persistent logs; clipboard content is only sent to `ask_ai()` as data.
- Confirmed Git execution uses only list arguments for `status`, `add`, `commit`, and `push`, with a fixed project working directory and typed approval before mutations.
- Verified `.env` is not tracked and found no API-key-shaped string in source/history search.
- Full suite: 60 tests passed. Real clipboard, microphone/speaker, and GitHub login/push checks remain for the human.

### Stage 5 builder and Codex self-review findings

- Added task records, a priority queue with aging, atomic resource reservation, task workers, timeouts, status output, pause/resume/cancel, and emergency stop.
- Added fixed resource reasons, typed per-resource approval, 60-second denial, session and saved non-sensitive grants, revoke, audit log entries, and one keyboard broker for worker prompts.
- Unknown requests stay on the chat path. AI plan output is checked as JSON and cannot select Git, file writing, or runtime rule changes.
- Kept `USE_IRIS = False` as the default, so Stage 4 remains the default until the human enables Iris in `config.py`.
- Full suite: 81 tests passed. `python -m iris.demo` showed the forced naive deadlock, successful all-at-once reservations, aging, and pause/resume from step 1.
- Codex did this self-review because Antigravity is unavailable. No real microphone/speaker, app path, API provider, RSS, clipboard, or GitHub authentication check was claimed.
