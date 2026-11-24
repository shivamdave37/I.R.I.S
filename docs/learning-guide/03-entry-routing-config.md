# 03 — Entry point, router, and configuration

## `main.py`

### Purpose

This file starts the program only when run directly (`python main.py`). It owns the interactive loop and keeps user text out of the log.

### Imports and logging

`import logging` supplies the standard logging system. `import config` provides the log folder path; `import router` provides request handling.

`setup_logging()` first tries to create `logs/` and configure an INFO-level UTF-8 file log at `logs/iris.log`. The format starts with a timestamp and then the message. If directory/file setup raises `OSError`, logging falls back to `CRITICAL`, so normal INFO messages are suppressed. The fallback keeps startup from failing solely because logs cannot be written.

### `run()` line-by-line behavior

1. `setup_logging()` configures logging before the loop.
2. The greeting is printed.
3. `while True` begins a repeated command cycle.
4. `input("You: ")` reads one line. `EOFError` means input ended (for example, closed stdin); `KeyboardInterrupt` means Ctrl+C. Both print goodbye and break.
5. The router call is in a second `try`. Ctrl+C during handling exits. Any other exception is logged only by exception type, then converted to a generic response. Its detail and the original command are not logged.
6. `print(f"Iris: {reply}")` displays the returned value.
7. A generic event label is logged; user content and secrets are intentionally omitted.
8. `router.normalize(command).rstrip(".!?")` recognizes exit words despite case, whitespace, or final punctuation. If matched, the loop breaks.

`if __name__ == "__main__": run()` is Python's direct-execution guard. Importing `main` in tests does not automatically launch the interactive loop.

**Failure not caught here:** `setup_logging()` handles `OSError`, but unusual failures outside that type may still escape. A process crash or power failure can also stop the loop.

## `router.py`

### Current public behavior

The imports include `re`, `config`, `skills`, `ai`, and `task_planner`. The current public `handle(command, input_fn=input)` simply returns `task_planner.handle(command, input_fn)`. This is the path the application uses.

`normalize(text)` turns a value into a string, substitutes an empty string for false-like input, strips outer whitespace, lowercases, and collapses repeated whitespace. `main.py` uses it for exit detection.

### Legacy private helpers

The file also contains `_open_target`, `_approval`, `_single_command`, `_is_known_local_command`, `_multi_action_parts`, and `_approval_for_command`. These are older/direct-routing helpers. They implement matching and approval logic, but current public `handle()` does not call them. Do not describe them as the active plan executor. Their imports may look necessary for those private functions, but most are not needed by the current public path.

This is a maintainability observation, not a claim that the application uses two routing systems at once. The planner is the active path. The older code is potentially confusing because it duplicates related logic.

## `config.py`

`Path(__file__).resolve().parent` identifies the directory containing `config.py`, independent of the current terminal directory. `DATA_FOLDER` and `LOG_FOLDER` are joined from that root. This helps local files stay in the project.

Settings define Gemini as the default AI provider, a Gemini model name, the local Ollama model, and the Ollama URL `http://127.0.0.1:11434/api/chat`. The URL is a loopback address; `ai.py` validates this before sending Ollama text.

`APPS` maps approved names to app executable paths. `WEBSITES` maps approved names to fixed HTTPS addresses. The planner checks target membership before `skills.open_approved()` acts. The Chrome path shown is a specific Windows installation path and may not exist on another computer. Notepad and Calculator names can resolve through Windows path lookup.

There is no API key in `config.py`; secrets are loaded at runtime from environment variables or `.env`.

## Safe example trace

Input `help` reaches `main.run` → `router.handle` → `task_planner.handle` → `_deterministic_plan` → `_parse_local` → a `help` `PlanStep` → `_execute` → `_run_step` → `skills.help_text` → return string → `main.run` prints it. No external provider is needed for this deterministic path.

## Viva prompts

- Why use `Path(__file__)` instead of the terminal's current folder? It makes project-relative data paths stable.
- Why catch an error in the loop? To keep one failed request from terminating Iris.
- Is `router._single_command()` used by the current public API? No; public `handle()` delegates to the planner.
- Why use app and website allowlists? They limit the target strings that can reach the opener.
