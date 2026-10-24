# Mini Jarvis — Stage 6 builder implementation complete; review pending

Stage 6 has three parts: 6A adds user-approved apps and websites, 6B adds wake-word listening, and 6C adds approval-gated learned skills. Iris remains the task supervisor from Stage 5. Stage 6C is implemented by the builder; reviewer approval and human hardware checks are still pending.

## Setup and run

Use Python 3.10 or newer on Windows 10/11. From this project folder:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your private Gemini key to `.env` if `AI_PROVIDER = "gemini"`, then run:

```powershell
python main.py
```

`config.py` has `USE_IRIS = False` by default, so Jarvis starts in Stage 4 mode. Set it to `True` to use the Iris task queue and permission prompts. Set `MODE = "typed"` to use only keyboard input, or keep `both` for voice plus typed permission answers.

Gemini free-tier quotas apply. Avoid sensitive information in chat because free-tier prompts and responses may be used to improve Google's products. Never commit or share `.env`.

Jarvis defaults to `MODE = "both"`: it listens first and falls back to typed input. Set `MODE` in `config.py` to `typed` or `voice` if preferred. Current provider settings remain in `config.py`.

For local AI chat, install [Ollama](https://ollama.com), run `ollama run gemma3:1b`, then set `AI_PROVIDER = "ollama"` in `config.py`. The model downloads on first use. No Gemini key is needed for Ollama.

## Commands

- `open youtube`, `open google`, `open github`
- `open vscode`, `open chrome`, `open notepad`, `open codex`
- `time` / `what's the time`; `date` / `what's the date`
- `news`, `latest news`, or `tell me the news`
- Ask any other question to chat with the selected AI provider
- `explain this code`: select code in another app, then ask Jarvis. It copies the selection and prints the explanation; voice modes also speak a short summary.
- `fix this code`: select code, then ask Jarvis. It displays an AI suggestion only; Jarvis does not paste, save, or run it.
- `take a note <text>` and `show my notes`
- `my name is <name>`, `remember I prefer <preference>`, and `what do you remember about me`
- `save my work to GitHub`: Jarvis shows the changed files, asks for typed approval to stage, requests a commit message and typed approval, then asks for a separate typed approval before pushing.
- `add app <name>` and `add website <name> <url>`: Iris finds or validates the target, shows it, and saves only after typed approval. App and website names can use letters, numbers, and spaces.
- `remove app <name>` and `remove website <name>`: show the learned entry and remove it only after typed approval.
- `list apps` and `list websites`: show built-in and learned entries.
- `open <learned name>`: open an app or website that you added and approved.
- `add a skill that <description>`: ask AI to propose a small Python skill. Read the full code and resource list; type `yes` to allow its isolated test, then read the result and type a second `yes` to install and make a local commit.
- `change skill <name> that <description>`: create a replacement proposal; it uses the same checker, two typed approvals, and local commit.
- `list skills`, a learned skill's keyword, and `undo last skill` manage installed skills. Undo is also a local commit and never pushes.
- If enabled, say `Hey Iris` followed by a command to wake Jarvis. With offline Vosk ready, a command after the wake word in the same phrase is recognized from that phrase.
- `exit` or `quit`

Set `USE_IRIS = True` in `config.py` to use the Stage 6 task, permission, and learned app flows. User app and website entries are stored in the ignored `data/user_config.json`; missing or damaged settings start empty and produce a warning. Learned entries cannot replace built-in names. Adding an app searches the current-user and all-users Start Menu shortcuts first; if no shortcut matches, Jarvis asks for an existing `.exe` or `.lnk` path.

Wake word is off by default. To enable it, set both `USE_IRIS = True` and `WAKE_ENABLED = True`; keep the model folder at `models/vosk-model-small-en-in-0.4`. Install Vosk inside the project environment with `python -m pip install vosk`, then download and extract the [small Indian English Vosk model](https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip). This model is 36 MB and is listed under Apache 2.0 on the [official Vosk model list](https://alphacephei.com/vosk/models). Extract it so the folder contains the model's `am` and `conf` subfolders at `models/vosk-model-small-en-in-0.4`. The microphone is used for short chunks and released between them so Iris tasks can reserve `MIC_SPEAKER`. If Vosk or its model is unavailable, Jarvis prints that it is using an **online fallback** and checks short chunks with the existing online recognizer. That fallback sends microphone audio to Google's speech service. A microphone failure returns to typed input. Wake detection is not a commercial keyword engine; false triggers and misses can happen.

When Iris is enabled, ordinary requests are queued as tasks. Type or say `status` to see each task's state, priority, resource ownership, estimate, elapsed time, and result. Admin controls are `pause <task>`, `resume <task>`, `cancel <task>`, `switch to <task>`, `priority <task> <number>`, `grants`, `revoke <resource>`, and `stop all`. Use the task ID or exact displayed name. `stop all` cancels current work but keeps Jarvis running. If a blocked or non-pausable step is still finishing, Iris keeps its resource reserved until the worker exits and reports that it is still finishing.

To queue multiple demo requests, type `queue: time; latest news; show my notes`. Each request becomes a separate task. Unknown requests stay on the chat path; an AI plan cannot select a Git or file-writing action.

Only selected clipboard text is sent for code help. The copied text is treated as data, not as a command. Read an AI fix before using it yourself; Jarvis never applies one.

## GitHub safety

The Git helper runs only `git status`, `git add -A`, `git commit -m`, and `git push`, as argument lists in the project folder. It requires typed approval before staging, committing, and pushing. Declining the push leaves the commit local. The helper does not run Git during tests.

The learned-skill helper is separate and narrower: after Iris grants typed `LEARNED_SKILLS` and `GIT_REPO` permissions and you give both typed skill approvals, it stages only `skills/learned/<skill>.py` and `data/learned_skills.json`, makes a fixed local commit, and never pushes. It refuses to commit when unrelated files are already staged.

## Learned-skill safety

Candidates must pass a standard-library AST checker, use only the documented import list, define the required metadata and `run(command)`, and stay under 120 lines. The complete code, declared resources, and checker result are shown before the first typed approval. A fixed `test` command runs in a separate Python process with a five-second timeout; its result is shown before the second typed approval. Installed skills run in a separate bounded process too, return text only, and reserve their declared Iris resources. Protected project files are hashed at Iris startup and checked after each approval.

The subprocess test reduces risk but is **not a true Windows sandbox**: it runs with the Windows account's normal permissions. The allowlist, static checker, resource prompts, and your two typed approvals are the protection. Read all candidate code before approving it. Do not ask a learned skill to read files or perform system changes; Iris skills cannot change existing project code.

## Local notes and memory

Notes are appended to `data/notes.txt`. Name, preferences, and the latest 20 commands are saved in `data/memory.json`. These files and the `data/` folder are ignored by Git. The configured Gemini key is redacted from command history and rejected if included in a commit message.

## Tests

Run all tests with:

```powershell
python -m unittest discover tests
```

Run the repeatable deadlock, starvation-aging, and pause/resume demonstrations with:

```powershell
python -m iris.demo
```

Tests mock clipboard, AI, confirmation, and Git behavior. They do not interact with a real selection, microphone, GitHub login, or push.

## Microphone and speaker troubleshooting

Check Windows microphone privacy settings and the default input device. Voice recognition needs internet. `pyttsx3` uses the installed Windows speech engine; check the selected output device and volume if replies are not audible. If PyAudio installation fails, keep the error and ask before trying another audio library or installing build tools.

Jarvis records command outcomes in `logs/jarvis.log` when logging is available. Suggested code fixes are excluded from persistent logs. API keys are redacted from logs and command history.

## Iris permissions

Before a task uses resources, Iris shows one prompt listing each resource and its reason. Type one comma-separated answer per listed resource in the same order: `once`, `session`, `always`, or `deny`. `GIT_REPO`, `SCREEN_FOCUS`, `NOTES_FILE`, `USER_CONFIG_FILE`, and `LEARNED_SKILLS` are sensitive: type `yes` or `deny` for each such item every time. Sensitive grants cannot be saved. No answer after 60 seconds is denied. Saved non-sensitive `always` grants live in ignored `data/permissions.json`; `grants` lists them and `revoke <resource>` removes them.

Worker prompts such as Git confirmations and commit messages go through the main keyboard loop, so worker threads do not read the terminal directly. Admin commands remain available while a prompt is open.

## Manual checks

- Select harmless code and try explain and fix. Confirm the fix is only displayed and that explain speaks a short summary.
- Save and show a note; save a name and preference; ask Jarvis what it remembers.
- Try `save my work to GitHub` and decline each typed prompt in turn. No GitHub action should occur after a declined prompt. Only test a real push when you intend to publish your current project changes.
- Earlier-stage manual checks remain: real Gemini/Ollama, RSS internet access, microphone, speaker, and configured app paths.
- Set `USE_IRIS = True`; try a simple task, inspect `status`, allow and deny separate resources, save and revoke a non-sensitive grant, and test `pause`, `resume`, `cancel`, `priority`, and `stop all` with the displayed task ID.
- Try a task that needs `SCREEN_FOCUS` or `GIT_REPO` and confirm it asks for typed approval every time. Test the Git workflow only when you are ready to stage or publish the listed project changes.
- With Iris enabled, add a real app and website, check their target before typing yes, restart Jarvis, list them, and open them. Try an invalid name and URL, and remove one learned entry.
- For learned skills, first type a harmless request such as `add a skill that flips a coin`. Review all code and resources before the first typed `yes`; review the isolated test result before the second typed `yes`. Check that the local commit contains only the skill and registry, and confirm no push occurs. Then try `list skills`, its keyword, and `undo last skill`. The checker/subprocess test is not a true Windows sandbox.
- Quiet-room/noisy-room wake-word behavior, false triggers, and misses need human testing. Also test the online fallback only if Vosk is unavailable.
- For wake mode, also type commands while it is idle and try an Iris task that needs `MIC_SPEAKER`; wake capture should wait until that task releases it.

`.env`, `venv/`, `data/`, `logs/`, generated bytecode, and local state are excluded from Git.
