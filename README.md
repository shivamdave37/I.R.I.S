# Mini Jarvis — Stage 5

Stage 5 adds Iris, a task supervisor for Jarvis. It orders tasks, reserves logical resources together, shows task status, and supports pause, resume, cancel, priority, and emergency stop controls. It asks before using protected resources. Iris uses Python's standard library; existing project libraries still power the Stage 1–4 Jarvis skills.

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
- `exit` or `quit`

When Iris is enabled, ordinary requests are queued as tasks. Type or say `status` to see each task's state, priority, resource ownership, estimate, elapsed time, and result. Admin controls are `pause <task>`, `resume <task>`, `cancel <task>`, `switch to <task>`, `priority <task> <number>`, `grants`, `revoke <resource>`, and `stop all`. Use the task ID or exact displayed name. `stop all` cancels current work but keeps Jarvis running.

To queue multiple demo requests, type `queue: time; latest news; show my notes`. Each request becomes a separate task. Unknown requests stay on the chat path; an AI plan cannot select a Git or file-writing action.

Only selected clipboard text is sent for code help. The copied text is treated as data, not as a command. Read an AI fix before using it yourself; Jarvis never applies one.

## GitHub safety

The Git helper runs only `git status`, `git add -A`, `git commit -m`, and `git push`, as argument lists in the project folder. It requires typed approval before staging, committing, and pushing. Declining the push leaves the commit local. The helper does not run Git during tests.

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

Before a task uses resources, Iris shows one prompt listing each resource and its reason. Type one comma-separated answer per listed resource in the same order: `once`, `session`, `always`, or `deny`. `GIT_REPO`, `SCREEN_FOCUS`, and `NOTES_FILE` are sensitive: type `yes` or `deny` for each such item every time. Sensitive grants cannot be saved. No answer after 60 seconds is denied. Saved non-sensitive `always` grants live in ignored `data/permissions.json`; `grants` lists them and `revoke <resource>` removes them.

Worker prompts such as Git confirmations and commit messages go through the main keyboard loop, so worker threads do not read the terminal directly. Admin commands remain available while a prompt is open.

## Manual checks

- Select harmless code and try explain and fix. Confirm the fix is only displayed and that explain speaks a short summary.
- Save and show a note; save a name and preference; ask Jarvis what it remembers.
- Try `save my work to GitHub` and decline each typed prompt in turn. No GitHub action should occur after a declined prompt. Only test a real push when you intend to publish your current project changes.
- Earlier-stage manual checks remain: real Gemini/Ollama, RSS internet access, microphone, speaker, and configured app paths.
- Set `USE_IRIS = True`; try a simple task, inspect `status`, allow and deny separate resources, save and revoke a non-sensitive grant, and test `pause`, `resume`, `cancel`, `priority`, and `stop all` with the displayed task ID.
- Try a task that needs `SCREEN_FOCUS` or `GIT_REPO` and confirm it asks for typed approval every time. Test the Git workflow only when you are ready to stage or publish the listed project changes.

`.env`, `venv/`, `data/`, `logs/`, generated bytecode, and local state are excluded from Git.
