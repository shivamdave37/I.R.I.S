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
- `find file report.pdf` or `search folders named invoices` searches only configured roots; `open result 1` opens one listed result after showing its exact path and asking permission
- `what time is it`, `what is the date`
- `add task Buy coffee`, `tasks` or `show tasks`, `complete task 1`, and `delete task 1`
- `set timer for 5 minutes`, `remind me in 10 minutes to take a break`, and `timers`
- `system status` or `specs`, `battery`
- `weather in London` or `weather`
- `read clipboard` and `copy to clipboard: text`
- `note buy milk`, `show notes`, `search notes for milk`, and `delete note 1`
- `research Python 3.14 changes` (Gemini Search or Tavily; requires approval and a configured search key)
- `capture screen` captures one screen only after typed approval; it stays in process memory and is not saved
- `describe screen` or `describe screen <question>` asks for a separate approval before sending the current image to Gemini
- `click 120 220` clicks an accessible UI target at that point after a fresh-screen check and its own approval
- `type at 300,200: hello` replaces text in an accessible, non-password Windows Edit field after its own approval
- `propose skill greeting for return a short greeting` creates an inert development proposal
- `approve proposal greeting v1` records approval for manual integration; it does not activate code
- `withdraw proposal greeting v1` records a reversible withdrawal and keeps the proposal history
- Any other question is sent directly to Gemini or Ollama
- `exit`

Iris previews the plan, parameters, dependencies, and required approvals. Every state-changing action is approved separately immediately before dispatch; approval for one action never applies to another. Denial prevents that action and skips the remaining plan. The gateway fails closed if a skill or approval policy is missing or invalid, and guarded state-changing skill functions reject direct calls outside the gateway. App and website targets come only from `config.py`. AI-generated plans cannot add skills or authorize themselves. The AI cannot cause shell commands or generated code to execute. Plans run in their listed order; if a step fails, dependent steps are skipped while independent steps continue and appear in the final summary. Ordinary notes stay in `data/notes.json`; no conversation is silently saved as memory.

File search is limited to `config.FILE_SEARCH_ROOTS`, initially the current user's `Documents` folder. Add another root there deliberately if needed; Iris does not scan the whole disk. Search matches names only, skips hidden entries and links/junctions, limits depth, examined entries, and displayed results, and never reads file contents. `open result N` can select only the latest search's numbered result; Iris revalidates the path and asks approval for that exact file or folder immediately before requesting Windows to open it. The launch request is not proof that the application opened successfully. File search/opening is Windows-only for the launch step.

### Optional screen and UI controls

Screen features require Windows and the optional packages in `requirements-ui.txt`. Install them only if you want these features:

```powershell
python -m pip install -r requirements-ui.txt
```

`capture screen` asks before each capture and retains only the latest PNG in process memory. `describe screen` asks again before sending that image to Gemini; the prompt warns that the image leaves the laptop and may incur API usage charges. Screen text is untrusted content and cannot create or approve actions. The image is not added to chat history or notes. Ollama is not supported for image analysis in this build.

UI interaction is deliberately narrow: clicks work only for named UI Automation buttons, links, menu items, or tabs; text replacement works only for a named, accessible, non-password Edit control. The initial process allowlist is limited to Notepad and Calculator; browsers and unknown apps are refused. Each click or text operation gets its own approval and checks that the captured screen and target identity have not changed. Iris refuses controls marked as password fields and blocks recognizable security, payment, financial, and destructive prompts based on accessible labels. Windows accessibility data varies by app and can omit labels, so this is not a guarantee that every sensitive prompt can be detected. Do not use Iris to operate password, payment, financial, security, or destructive system prompts; handle those manually. If the target cannot be safely identified, the operation is refused. A submitted UI action does not prove the application changed as intended.

The screen and UI modules load only when a screen command is used; ordinary CLI commands work without the optional packages. These Python checks are application safeguards, not an OS security boundary against malicious code already executing in the same process.

AI-assisted task planning uses one stateless provider request and a fixed JSON shape. Iris rejects malformed plans, unknown skills, extra or missing parameters, invalid targets, invalid dependencies, and plans longer than eight steps before execution. Provider HTTP requests have a 30-second timeout and a 1 MB response limit. Web-research results cannot be automatically converted into notes; inspect the cited report first, then ask Iris to save the exact wording you choose.

Web research can use Gemini Search grounding or Tavily Search. Gemini uses `GEMINI_API_KEY`; Tavily uses `TAVILY_API_KEY` and `IRIS_RESEARCH_PROVIDER=tavily` in the local `.env`. Tavily's free Researcher plan currently provides 1,000 API credits per month without a credit card; a basic search uses one credit, and requests stop when the free allowance is exhausted unless you choose a paid plan. Tavily returns an LLM-generated answer alongside real search results; Iris displays the answer only when it also receives valid HTTPS source URLs. See Tavily's [pricing](https://www.tavily.com/pricing) and [Search API docs](https://docs.tavily.com/documentation/api-reference/endpoint/search). Gemini's Google Search grounding remains available with the existing Gemini key and has its own quota and pricing; see Google's [grounding documentation](https://ai.google.dev/gemini-api/docs/google-search) and [pricing](https://ai.google.dev/gemini-api/docs/pricing). Ollama remains a local chat provider and does not perform web search.

Skill development is a proposal workflow, not self-modification. Iris can ask the configured model to draft a one-function pure-Python proposal, check its metadata and a restricted syntax tree, show the code and static-check result, then ask typed approval before saving it under `skill_proposals/`. Proposal versions and approval/withdrawal events are retained. Candidate code is never imported, run, or added to `task_planner.py`'s trusted skill schemas. This environment does not provide a verified OS-level sandbox for generated code, so runtime proposal tests are deliberately not run; approval records intent for a developer to review and integrate manually. A withdrawal preserves the proposal record and logs the rollback event.

Chat history is temporary in memory and is capped at ten messages. Notes are stored in the ignored `data/notes.json`; keyword search is case-insensitive, and deleting a numbered note requires typed approval. Invalid or malformed notes data is reported and left untouched. Logs save a generic outcome label only, not message text or API keys.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests mock AI calls and app launching. They do not verify your Gemini key, internet connection, Ollama installation, or Windows application paths.

## Current limits

This is a constrained terminal assistant, not a general computer-use agent. Screen description and UI control are optional and limited to the fixed actions listed above. It does not continuously monitor the screen, control every app, execute proposed code, or use a multi-agent planner. Live research and live vision must be tested with the selected provider account before relying on them.

## Beginner flow

`main.py` reads one line. `router.py` hands requests to `task_planner.py`, which makes deterministic plans or asks the AI for a constrained proposal. `skills.py` performs approved actions, manages notes, and starts bounded research. `ai.py` handles chat, planning, Gemini or Tavily web research, and inert proposal generation. `skill_development.py` validates and stores proposals without running them. `skill_proposals/` is the untrusted proposal and audit folder created when needed. `config.py` contains app, website, and model settings. Tests mock AI, web responses, and app launches; they do not make live web requests.
