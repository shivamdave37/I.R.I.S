# Mini Jarvis — Stage 1

Stage 1 is a typed Windows assistant. It opens approved websites and applications, tells the local time and date, and exits on request. Voice, AI chat, news, notes, GitHub actions, and Iris are later stages.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer

Stage 1 uses only the Python standard library, so there are no packages to install yet. Keep later packages inside a virtual environment.

## Setup and run

1. Open this folder in a terminal.
2. (Optional) Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Run Jarvis:

   ```powershell
   python main.py
   ```

Type a command at the `You:` prompt. Press Ctrl+C, or type `exit` or `quit`, to stop.

## Commands

- `open youtube`, `open google`, or `open github`
- `open vscode`, `open chrome`, `open notepad`, or `open codex`
- `time` or `what's the time`
- `date` or `what's the date`
- `exit` or `quit`

Only names listed in `config.py` can be opened. Before opening VS Code, Chrome, or Codex, check and edit the app paths in `config.py` for your computer. The sample VS Code and Codex paths contain `YOUR_USERNAME`; Jarvis will ask you to fix a sample path instead of trying to run it. Notepad can use the Windows `notepad.exe` command.

Unknown commands receive “I don't know that yet.” The `.env.example` file is included for the later AI stage; Stage 1 does not read an API key.

## Tests

Run the Stage 1 unit tests with:

```powershell
python -m unittest discover tests
```

Tests mock browser and app launching, so they do not open real programs or websites.

## Logs

Jarvis writes command and result entries to `logs/jarvis.log`. If it cannot create or write the log, it continues running. The `logs/` folder is ignored by Git.
