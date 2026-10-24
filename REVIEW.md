# Stage 3 Review Pack

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
├── SPEC.md
├── ai.py
├── config.py
├── main.py
├── requirements.txt
├── router.py
├── voice.py
├── skills/
│   ├── __init__.py
│   ├── apps.py
│   ├── news.py
│   ├── timeinfo.py
│   └── web.py
└── tests/
    ├── test_ai.py
    ├── test_news.py
    ├── test_router.py
    └── test_voice.py
```

## What the files do

- `config.py` holds voice mode, AI provider/model settings, the RSS feed URL, and approved websites/apps.
- `ai.py` sends chat text through Gemini or local Ollama, keeps the last ten conversation messages, and handles missing keys, quotas, and provider failures.
- `router.py` keeps known commands on direct skill paths, routes unknown questions to AI, and routes news phrases to the RSS skill.
- `skills/news.py` fetches and formats up to five RSS headlines with a friendly failure response.
- `main.py` runs the command loop, voice modes, and redacted command logging.
- `voice.py` handles microphone input and queued spoken replies.
- `skills/apps.py`, `skills/web.py`, and `skills/timeinfo.py` implement the approved app, website, and time/date commands.
- `tests/` tests routing, AI provider behavior, and RSS handling using mocks.
- `.env.example` shows the required key variable with a placeholder only; `.env` is ignored.
- `requirements.txt` lists the voice, AI, dotenv, request, and feed parsing packages.
- `AGENTS.md`, `HANDOFF.md`, `PROMPTS.md`, and `SPEC.md` define collaboration, stage requirements, and the current handoff.

## Run and test

Install packages in the project virtual environment with `python -m pip install -r requirements.txt`. Copy `.env.example` to `.env`, add a free key from Google AI Studio for Gemini, and start with `python main.py`. Tests: `python -m unittest discover tests`.

For Ollama, install it from [ollama.com](https://ollama.com), run `ollama run gemma3:1b`, then set `AI_PROVIDER = "ollama"` in `config.py`. `AI_FALLBACK_PROVIDER` can optionally name the other provider for quota fallback.

## Stage 3 behavior and known checks

- Unknown requests reach the configured AI provider; known app, website, time, and date commands bypass AI.
- `news` and `latest news` fetch up to five items from the configured public RSS feed.
- Provider and RSS tests use mocks. No real API key or network request is used by the test suite.
- Real Gemini chat requires a human-created `.env` key. Free-tier quotas apply; do not send sensitive content.
- Microphone/speaker behavior and app paths remain hardware-specific from earlier stages.

## Reviewer findings

### Stage 1
- Collapsed repeated spaces, fixed punctuation-only fallback and `None` handling, checked browser launch failures, used UTF-8 logging, and expanded router tests.

### Stage 2
- Enforced listening/speaking exclusivity, ignored empty speech, recovered from pyttsx3 loop errors, handled empty recognition, normalized mode casing, and expanded voice tests. The reviewed suite had 27 passing tests.

### Stage 3 builder notes
- Added Gemini and Ollama behind `ask_ai()`, a ten-message conversation window, quota-only optional fallback, configured-key log redaction, and an RSS skill with a five-headline cap.
- Chosen Gemini model: `gemini-3.5-flash-lite`; local Ollama model: `gemma3:1b`.
- Stage 3 tests mock both AI providers and the RSS request; real provider/feed checks are listed in `HANDOFF.md`.

### Stage 3 reviewer findings
- **Chat history integrity on failed turns**: Fixed `ai.ask_ai()` to roll back unfulfilled user messages from `CHAT_HISTORY` when an API query fails (missing key, quota limit, network error), ensuring the history only records complete, successful user-assistant turns.
- **Example API key placeholder check**: Added detection for example placeholder keys (`your_key_here`) in `.env` so Jarvis provides a clear setup reminder instead of triggering an invalid API call.
- **HTML entity decoding in news titles**: Added `html.unescape()` in `skills/news.py` so entities like `&amp;` and `&#39;` in RSS headlines are decoded cleanly for spoken and printed output.
- **Conversational news routing**: Added `"whats the news"`, `"what is the news"`, and `"tell me the news"` to `router.py` direct routing so natural queries do not fall through to the AI.
- **Key redaction in logs**: Added whitespace stripping guard before key redaction in `main.py` to prevent replacing whitespace if the key environment variable is blank.
- **Unit test suite expansion**: Added 4 unit tests covering chat history rollback on provider error, placeholder key detection, RSS HTML entity unescaping, and news query variations (42 tests total across test suite, all passing).

