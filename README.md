# Mini Jarvis — Stage 2

Stage 2 adds voice input and spoken replies to the typed Windows assistant. It opens approved websites and applications, tells the local time and date, and exits on request. AI chat, news, notes, GitHub actions, and Iris are later stages.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer

Install packages inside the project's virtual environment.

## Setup and run

1. Open this folder in a terminal.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install the project packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Run Jarvis:

   ```powershell
   python main.py
   ```

In the default `both` mode, Jarvis listens first and falls back to typed input if it cannot recognize speech. Set `MODE` in `config.py` to `voice` or `typed` to select one input mode. Replies are printed in every mode; voice and both modes also speak replies. Press Ctrl+C, or say/type `exit` or `quit`, to stop.

## Commands

- `open youtube`, `open google`, or `open github`
- `open vscode`, `open chrome`, `open notepad`, or `open codex`
- `time` or `what's the time`
- `date` or `what's the date`
- `exit` or `quit`

Only names listed in `config.py` can be opened. Before opening VS Code, Chrome, or Codex, check and edit the app paths in `config.py` for your computer. The sample VS Code and Codex paths contain `YOUR_USERNAME`; Jarvis will ask you to fix a sample path instead of trying to run it. Notepad can use the Windows `notepad.exe` command.

Unknown commands receive “I don't know that yet.” The `.env.example` file is included for the later AI stage; Stage 2 does not read an API key.

## Microphone troubleshooting on Windows

- Check that Windows microphone privacy settings allow desktop apps to use the microphone, and select the intended input device as the Windows default.
- PyAudio is included in `requirements.txt`. If installation fails, copy the error message into the chat before trying a different audio library or installing system build tools.
- Speech recognition uses Google's online recognition service, so voice input needs an internet connection. Silence, microphone errors, and recognition/network failures return to typed input in `both` mode.
- `pyttsx3` speaks offline using the installed Windows speech engine. Check Windows sound output and volume if no speech is audible.

## Tests

Run the unit tests with:

```powershell
python -m unittest discover tests
```

Tests mock browser, app, microphone, and speaker behavior, so they do not open real programs or use audio hardware.

## Logs

Jarvis writes command and result entries to `logs/jarvis.log`. If it cannot create or write the log, it continues running. The `logs/` folder is ignored by Git.
