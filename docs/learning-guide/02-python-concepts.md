# 02 — Python concepts used in Iris

This chapter teaches concepts visible in the checked-in source and tests, not a general Python syllabus.

## Names, values, and types

`config.py` assigns names such as `AI_PROVIDER = "gemini"`. The name is a variable; the string is its value. Iris also uses integers for note indexes and limits, Booleans for checks, lists for plan steps and notes, tuples for fixed pairs, sets for required key names, and dictionaries for configuration and JSON-shaped data.

Example from `config.py`:

```python
APPS = {"notepad": "notepad.exe", "calculator": "calc.exe"}
```

The braces create a dictionary. A key such as `"notepad"` maps to a value such as `"notepad.exe"`. `APPS.get(key)` safely returns `None` when a key is missing; direct `APPS[key]` would raise `KeyError`.

**Common mistake:** confusing `"False"` (a non-empty string, therefore true in an `if`) with `False` (a Boolean value).

## Strings and string methods

Commands and results are strings. Methods such as `.strip()`, `.lower()`, `.casefold()`, `.split()`, `.startswith()`, and `.format`-style f-strings clean or display them. `casefold()` is a stronger lowercase operation intended for case-insensitive text comparison.

Example: `answer.strip().casefold() == "yes"` accepts `YES` or surrounding spaces but rejects phrases like `yes please`. The exact-match rule makes consent less ambiguous.

**Common mistake:** calling `str.strip()` does not remove every internal space; it only removes whitespace at the ends.

## Lists, tuples, sets, and dictionaries

- A **list** is ordered and changeable: `_HISTORY`, `steps`, and notes use lists.
- A **tuple** is ordered and usually used here for fixed pairs: a parsed `(skill_name, params)` result.
- A **set** stores unique values and is used for schema key comparison, such as `set(params) == expected`.
- A **dictionary** maps names to values and represents plan JSON, provider payloads, and settings.

The exact key-set comparison is useful because it rejects both missing and unexpected parameters.

## Conditions, Boolean expressions, and operators

`if`, `elif`, and `else` choose a path. `and` requires both sides to be true; `or` needs one; `not` reverses a Boolean. `==` compares values, `!=` means unequal, `in` tests membership, and `is` tests object identity (used mainly for `None`). Parentheses make complex conditions easier to read.

Example: `if target not in config.APPS and target not in config.WEBSITES:` refuses a target unless it is in one of the two allowlists.

**Common mistake:** use `==` to compare values; `is` is not a general equality operator.

## Loops and comprehensions

`for` loops iterate over plan steps, JSON fields, search results, or file lines. `while True` keeps `main.run()` accepting commands until a `break`. A comprehension builds a collection in one expression, for example `[(index, note) for ... if ...]` in note search. Read a comprehension as “make this value for each item that meets this condition.”

**Common mistake:** an infinite `while True` needs a reachable `break`, or the application never exits normally.

## Functions, parameters, arguments, return values, scope

`def function_name(parameter):` creates reusable behavior. The parameter is the local input name; the argument is the value supplied at a call site. `return` sends a value back to the caller and ends that function. Variables created inside a function normally belong to that function's local scope.

Example: `def search_notes(query):` accepts the caller's search word, finds matches, and returns a formatted string. It does not print the answer itself; `main.run()` eventually prints it.

Default argument example: `def handle(command, input_fn=input):` lets production use `input`, while tests inject a fake function. The default is evaluated when the function is defined, a detail to remember when tests patch `builtins.input` later.

## Imports and modules

`import json` loads a module under the name `json`; `from pathlib import Path` imports one name directly; `import urllib.error` allows exception names such as `urllib.error.HTTPError`. Imports let the project split responsibilities and reuse Python's standard library.

**Common mistake:** circular imports can cause partially initialized modules. Here `task_planner` imports `skills` and `ai`; those modules do not import `task_planner` back.

## Classes and dataclasses

`@dataclass` decorates the `PlanStep` class. It generates routine methods such as initialization and representation from its fields (`step_id`, `skill`, `params`, and statuses). `PlanStep(...)` creates an object. A field default factory (`field(default_factory=list)`) creates a fresh list for each instance; using `depends_on=[]` directly as a default could accidentally share one list between objects.

No custom class hierarchy is used in the inspected application.

## Exceptions and defensive paths

`try` marks code that may fail. `except SomeError` catches that particular kind; a broad `except Exception` catches most ordinary errors and should be used only where the program has a safe fallback. `raise` reports a validation failure to a caller. `finally` runs cleanup whether the main operation succeeds or fails.

Note writing uses `finally` to remove a temporary file. Planner execution catches a step exception and marks only that step failed. `main.run()` catches an unexpected request exception so one broken request does not end the whole loop.

**Common mistake:** catching every exception and then pretending the operation succeeded. Iris uses explicit failed states/messages in its main workflows, but error classification by returned text has limitations.

## Paths, files, and operating-system behavior

`pathlib.Path` builds paths by joining components with `/` in Python syntax; it is not a literal slash command. `Path.resolve()` canonicalizes a path. `is_symlink()` detects a link. `mkdir(..., exist_ok=True)` creates directories if needed. `os.replace()` atomically replaces a target on the same filesystem. `tempfile.mkstemp()` creates a unique temporary file.

These are used for notes and proposal records. Atomic replacement reduces the chance of leaving a partially written note file, but it is not a backup system and cannot protect against every disk failure.

## JSON

JSON is a text format for lists and dictionaries. `json.loads()` parses JSON text into Python values; `json.dumps()` converts Python values to JSON text. The notes file is a JSON list of strings; AI plans and API bodies are JSON objects.

JSON does not preserve Python-specific types such as sets or dataclass objects automatically. The code builds plain dictionaries/lists before serializing.

## Environment variables and secrets

`os.environ.get("GEMINI_API_KEY", "")` reads a process environment variable and uses an empty string as the fallback. `_load_env_file()` reads only named variables from the project `.env` file. The key is passed in an HTTP header, not printed in the URL. `.env` is ignored by Git; `.env.example` is a placeholder template.

**Common mistake:** logging the entire exception or request object can expose credentials. Iris usually returns generic provider messages and does not include provider response bodies.

## Regular expressions

`re.fullmatch()` requires the entire input to match a pattern. `re.sub()` removes a known phrase prefix. `re.split()` separates only recognized command boundaries. Raw strings prefixed with `r` make backslashes easier to use in regex patterns.

Example: a digits-only pattern for a note number prevents arbitrary text from being interpreted as an index.

**Common mistake:** splitting every occurrence of the word `and` would corrupt note text such as “salt and pepper.” The planner uses lookahead patterns and checks that every resulting segment is a supported command.

## Type checks and `None`

The program validates external/model JSON at runtime with `isinstance()`. `None` represents no result, such as an unrecognized local parse. `isinstance(value, bool)` is checked before integer validation for note index/version because Python treats `bool` as a subclass of `int`; otherwise `True` might be accepted as note 1.

There are few/no formal type annotations in the application. The validations are runtime checks, not static type checking.

## HTTP and APIs

`urllib.request.Request` builds a request; `urlopen(..., timeout=30)` sends it; the response bytes are bounded before UTF-8 decoding and JSON parsing. Gemini uses a key header. Tavily uses a bearer authorization header. Ollama is restricted to an HTTP loopback URL so its request remains on the local machine.

An HTTP status such as 429 is an error response from the service. Iris maps it to a clear quota/rate-limit message and does not fabricate results. A successful HTTP status alone is not enough: response shape and source URLs are validated too.

## Unit tests, mocks, and temporary folders

`unittest.TestCase` groups tests. A method named `test_...` is discovered by unittest. `self.assertEqual()` fails the test if two values differ. `unittest.mock.patch()` replaces a function or setting temporarily. `TemporaryDirectory()` gives a test isolated scratch storage that is cleaned up after the context ends.

Mocks avoid opening real applications, spending API credits, or depending on the network. Their limitation is equally important: they test Iris's reaction to a simulated response, not the actual external service.

## Features not found

The inspected project does not use custom async/await code, generators, a thread pool, decorators other than `@dataclass`, or a GUI framework. The `@dataclass` line is the only application decorator observed. Do not claim these are project features in a viva.

### Recap and practice

Explain one example of each: a dictionary in config, a list in a plan, a function return in `skills.py`, a caught exception in `ai.py`, and a mock in a test. Try changing a temporary copy of a test input, not production data, and predict the result before running it.
