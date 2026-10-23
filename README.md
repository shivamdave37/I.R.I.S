# Mini Jarvis — Stage 3

Stage 3 adds AI chat and five-headline news to the voice-capable Windows assistant. It can still open approved websites and apps, tell the local time and date, and exit on request. Notes, GitHub actions, and Iris are later stages.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Internet for Gemini, RSS news, and online speech recognition; Ollama chat runs locally

## Setup and run

1. Open this folder in a terminal.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`. Create a free Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey), then put it in `.env` as `GEMINI_API_KEY=your_real_key`. Never paste the key into chat or commit `.env`.
5. Run Jarvis:

   ```powershell
   python main.py
   ```

`config.py` defaults to `AI_PROVIDER = "gemini"` and model `gemini-3.5-flash-lite`. The free Gemini tier has usage limits and Google may use free-tier prompts and responses to improve its products; do not send sensitive information. `AI_FALLBACK_PROVIDER` is `None` by default. Set it to `"ollama"` if you want a local fallback after Gemini reports a rate or quota limit.

### Local Ollama option

Install Ollama from [ollama.com](https://ollama.com), then open PowerShell and run:

```powershell
ollama run gemma3:1b
```

This downloads and starts the small `gemma3:1b` model. In `config.py`, set `AI_PROVIDER = "ollama"`. Ollama must be running locally at the configured `OLLAMA_URL` (`http://localhost:11434/api/chat`). No Gemini key is needed for Ollama.

## Commands

- `open youtube`, `open google`, or `open github`
- `open vscode`, `open chrome`, `open notepad`, or `open codex`
- `time` / `what's the time`; `date` / `what's the date`
- `news` or `latest news` (fetches up to five headlines from the configured BBC RSS feed)
- Ask any other question to chat with the selected AI provider
- `exit` or `quit`

Only names listed in `config.py` can be opened. Check the VS Code, Chrome, and Codex paths for your computer. In `both` mode, Jarvis listens first, then falls back to typed input if it cannot recognize speech. Set `MODE` in `config.py` to `voice` or `typed` to choose one input mode. Replies are printed in every mode; voice and both modes also speak replies.

## Microphone troubleshooting

- Check Windows microphone privacy settings and the default input device.
- If PyAudio installation fails, share the exact error before trying another audio library or installing system build tools.
- Speech recognition uses an online service and needs internet. Silence, microphone errors, and recognition/network failures return to typed input in `both` mode.
- `pyttsx3` speaks offline using the installed Windows speech engine.

## Tests

Run all unit tests with:

```powershell
python -m unittest discover tests
```

Tests mock the AI providers and RSS network request; they do not use a real API key, network, microphone, or speaker.

## Logs and privacy

Jarvis writes command and result entries to `logs/jarvis.log` and redacts the configured Gemini key. If the log cannot be written, the assistant continues. `.env`, logs, and the virtual environment are ignored by Git. AI providers receive the chat text and the fixed assistant instructions, not `.env` contents or local files. The news skill requests only the configured public RSS feed.
