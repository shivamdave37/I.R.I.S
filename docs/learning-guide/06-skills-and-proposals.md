# 06 — Skills and inert skill development

## `skills.py`: fixed capabilities

The module imports `datetime` for local time/date; `json` for notes; `os`, `shutil`, `subprocess`, and `tempfile` for paths/processes/temporary files; `webbrowser` for websites; and Iris `ai` and `config`.

### Date and time

`tell_time()` calls `datetime.now().astimezone()` so the displayed time uses the machine's local timezone, then formats a 12-hour clock. `tell_date()` similarly formats weekday, month, day, and year. These functions have no network or disk side effects.

### Help

`help_text()` returns a fixed description string. **Observed mismatch:** its current text says research is Gemini Search, while the working tree now also supports Tavily. The wrapper `skills.research_web()` docstring also names Gemini Search only. README and planner permission wording are broader. This guide records the inconsistency without changing application source.

### `open_approved(name)`

Case-folds and strips the target. If the name is a configured website, it passes the fixed URL to `webbrowser.open(new=2)` and reports whether the browser accepted it. Otherwise it looks up a fixed app path; unknown names are refused. It resolves a command using `shutil.which()` or an existing path. If missing, it returns a useful message. On Windows it uses `os.startfile`; on other platforms it calls `subprocess.Popen([resolved], shell=False)`. User text never becomes a shell command. Real launch behavior depends on the machine and was mocked in tests.

### Notes: `add_note(text)`

Requires nonempty string. It selects `data/notes.json`, verifies a safe path, and loads existing JSON if present. Existing content must be a list containing only strings; malformed data is left unchanged. It appends the note, creates the data directory, uses `mkstemp` in that directory, writes JSON to the temporary path, then `os.replace()` atomically installs it. A `finally` block removes any leftover temp file. OS errors return a failure message. This is an append-only note action, gated by planner approval.

### Notes: reading, writing, and path safety

`_read_notes(path)` returns an empty list when the file is absent, a validated list on success, or `None` on parse/shape/read error. Returning `None` distinguishes broken storage from no notes.

`_write_notes(path, notes)` repeats the safe temp-write-and-replace process and returns a Boolean. `_notes_path_is_safe(path)` resolves project/data/file paths and rejects symlinks and targets outside the project. Path checks reduce redirection risks but are not a complete operating-system sandbox; filesystem races and platform behavior remain possible.

`show_notes()` verifies path, reads notes, reports damaged data, or numbers the notes beginning at one. `search_notes(query)` validates a nonempty query, uses `casefold()` substring matching, preserves original note numbering, and returns matching lines or “No matching notes.”

### `delete_note(index, approved=False)`

The function refuses unless the caller passes `approved=True`; it validates a positive integer, rejects Boolean values, checks safe path and note data, rejects an out-of-range index, removes one list element at `index - 1`, writes the remaining list safely, and returns a deletion message. The planner obtains user approval and only then calls it with `approved=True`. The explicit parameter guard is defense in depth; direct callers cannot accidentally delete by omitting consent.

### `research_web(query)`

Validates the 3–500 character query, strips it, then delegates to `ai.research_web()`. The skill does not make an HTTP request itself. Its current docstring is stale in calling the provider Gemini Search, because AI integration now supports Tavily too.

## `skill_development.py`: propose, inspect, record; never activate

### Policy constants and AST

It imports `ast` to parse syntax without executing it, datetime for UTC timestamps, JSON/path/regex/name helpers, `ai` for inert draft text, and `config` for the project folder. `PROPOSALS_FOLDER` is inside the project. `MAX_SOURCE_LENGTH` bounds proposal size. `RESERVED_NAMES` prevents conflicts with existing capabilities. `SAFE_BUILTINS` and `ALLOWED_NODES` form a small syntax allowlist.

### `validate_proposal(name, purpose, source)`

Calls metadata validation; requires nonempty bounded source and only allowed control characters; parses with `ast.parse`; requires exactly one synchronous function named `skill_<name>` without decorators; requires exactly one required argument named `request`; requires a one-line docstring; walks every AST node and rejects node types outside the allowlist, dangerous names, and calls other than selected pure built-ins. Returns a static-check success description. It does **not** run the function.

Static syntax restrictions reduce risk but are not a guarantee that code is harmless in every Python/runtime context. The key safety boundary is that proposal source is never imported or executed.

### Metadata and storage helpers

`_validate_metadata()` restricts names to lowercase letters/digits/underscore, rejects keywords/reserved names, bounds purpose length, and rejects control characters.

`_safe_folder()` resolves storage and requires it to remain inside the project without being a symlink. `_proposal_path()` validates components before building a versioned JSON filename. `_append_event()` appends one JSON event line and refuses unsafe folders/symlinked audit files. `_next_version()` scans existing matching filenames and chooses the next integer instead of overwriting. `_strip_code_fence()` removes only one complete optional Python Markdown fence.

### `create_proposal(name, purpose, input_fn=input)`

Validates user metadata before sending it to AI, obtains draft source, strips a code fence, statically validates, and returns an error without saving when any check fails. It prints the draft and checks, explicitly states runtime tests were not run because no isolated sandbox exists, and requests exact typed `yes`. If denied, nothing is saved. If approved, it creates a versioned JSON record with source, purpose, checks, status, and UTC timestamp using exclusive file creation (`"x"`, which refuses overwrite), then writes an audit event. A record is marked awaiting human review and not active.

Possible partial state: the proposal file may be written before audit append fails; code reports that the draft remains inactive. It does not claim a clean rollback of that partial record.

### Read, approve, withdraw

`read_proposal()` builds the safe path, refuses symlinks/nonfiles, parses JSON, revalidates the current source and metadata, checks name/version match, and returns the record or `None`. It never imports source.

`approve_for_manual_integration()` re-reads/revalidates, displays the exact proposal and checks, states runtime tests were not run, asks typed yes, and records an approval event. Its return explicitly says the proposal remains inactive. This is a recorded human decision, not installation.

`withdraw_proposal()` verifies that a valid record exists, asks typed yes, then appends a withdrawal event. It retains the original proposal record for audit/history rather than deleting it.

## Example proposal workflow

The user asks “propose skill greeting for return a short greeting.” The planner validates the fixed proposal skill and asks permission. `skill_development.create_proposal()` sends name/purpose to the configured provider, receives inert text, checks its AST, displays it, then asks a second approval to save. Later approval records manual integration approval only. No dynamic skill is registered, and no generated function is run.

### Recap

`skills.py` contains executable approved capabilities. `skill_development.py` handles untrusted draft text as data, validates and stores it, and never activates it.

### Check yourself

1. Why use `shell=False` and a one-item process argument list?
2. Why use `os.replace()` for notes?
3. What does a malformed note JSON file cause?
4. Does proposal approval install code?
5. Why is AST parsing not execution?

**Answers:** 1. Avoid shell interpretation of user text. 2. Reduce partial-write risk. 3. A safe error; data stays untouched. 4. No. 5. AST parsing builds a syntax tree representation; it does not call the function.
