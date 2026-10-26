# Iris task-planning foundation

Iris is a local Python terminal assistant. Known requests go to fixed Python skills. For an ambiguous action request, the configured AI can suggest a JSON task plan; Iris validates every step against a local skill registry before it displays or runs anything. Ordinary questions still go straight to chat.

## Run it

Use Python 3.10 or newer. From this folder:

```powershell
python main.py
```

For Gemini, copy `.env.example` to `.env` and add your key as `GEMINI_API_KEY=...`. The `.env` file is ignored by Git. To use Ollama instead, set `IRIS_AI_PROVIDER=ollama` in `.env`, start Ollama, and pull the model named in `config.py`. Iris only sends Ollama requests to a local loopback address; chat text is not sent to a remote Ollama host.

## Commands

- `help` or `what can you do`
- `open Notepad`, `can you open Notepad`, `open Chrome`, `open YouTube`
- `open YouTube, tell me the time, and note study Python tomorrow` previews and runs multiple supported steps in order
- `what time is it`, `what is the date`
- `note buy milk`, `show notes`, `search notes for milk`, and `delete note 1`
- `research Python 3.14 changes` (Gemini Search grounding; requires the Gemini provider and API key)
- `propose skill greeting for return a short greeting` creates an inert development proposal
- `approve proposal greeting v1` records approval for manual integration; it does not activate code
- `withdraw proposal greeting v1` records a reversible withdrawal and keeps the proposal history
- Any other question is sent directly to Gemini or Ollama
- `exit`

Iris previews the plan, parameters, dependencies, and required approvals. It asks for typed `yes` before opening an approved app or website, saving or deleting a note, sending a web-research query, or asking the AI to draft a skill. For a multi-action request, it collects required approvals before starting; if any is declined, no steps run. App and website targets come only from `config.py`. Unknown open targets and unknown AI-proposed skills are refused. The AI cannot cause shell commands or generated code to execute. Plans run in their listed order; if a step fails, dependent steps are skipped while independent steps continue and appear in the final summary. Ordinary notes stay in `data/notes.json`; no conversation is silently saved as memory.

AI-assisted task planning uses one stateless provider request and a fixed JSON shape. Iris rejects malformed plans, unknown skills, extra or missing parameters, invalid targets, invalid dependencies, and plans longer than eight steps before execution. Provider HTTP requests have a 30-second timeout and a 1 MB response limit. Web-research results cannot be automatically converted into notes; inspect the cited report first, then ask Iris to save the exact wording you choose.

Web research reuses the existing `GEMINI_API_KEY` and the Gemini `generateContent` Google Search grounding tool. There is no additional Python dependency or account change. It reports the AI-written summary separately from source URLs, supported claim snippets, and an uncertainty note. It refuses to present a summary without HTTPS sources returned in Gemini's grounding metadata. Ollama has no web-search connection in this project, so research needs `AI_PROVIDER = "gemini"` (or `IRIS_AI_PROVIDER=gemini`) and a working Gemini key. Gemini Search has separate quotas and may incur charges after the applicable free allowance; check Google's [grounding documentation](https://ai.google.dev/gemini-api/docs/google-search) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) before using it.

Skill development is a proposal workflow, not self-modification. Iris can ask the configured model to draft a one-function pure-Python proposal, check its metadata and a restricted syntax tree, show the code and static-check result, then ask typed approval before saving it under `skill_proposals/`. Proposal versions and approval/withdrawal events are retained. Candidate code is never imported, run, or added to `task_planner.py`'s trusted skill schemas. This environment does not provide a verified OS-level sandbox for generated code, so runtime proposal tests are deliberately not run; approval records intent for a developer to review and integrate manually. A withdrawal preserves the proposal record and logs the rollback event.

Chat history is temporary in memory and is capped at ten messages. Notes are stored in the ignored `data/notes.json`; keyword search is case-insensitive, and deleting a numbered note requires typed approval. Invalid or malformed notes data is reported and left untouched. Logs save a generic outcome label only, not message text or API keys.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests mock AI calls and app launching. They do not verify your Gemini key, internet connection, Ollama installation, or Windows application paths.

## Current limits

This is a safe foundation, not a general computer-use agent. Iris currently supports only the fixed actions listed above. She does not inspect screens, control arbitrary apps, execute proposed code, or use a multi-agent planner. Research depends on Gemini Search grounding and must be live-tested with your account before relying on it.

## Beginner flow

`main.py` reads one line. `router.py` hands requests to `task_planner.py`, which makes deterministic plans or asks the AI for a constrained proposal. `skills.py` performs approved actions, manages notes, and starts bounded research. `ai.py` handles chat, planning, grounded Gemini Search, and inert proposal generation. `skill_development.py` validates and stores proposals without running them. `skill_proposals/` is the untrusted proposal and audit folder created when needed. `config.py` contains app, website, and model settings. Tests mock AI, web responses, and app launches; they do not make live web requests.
