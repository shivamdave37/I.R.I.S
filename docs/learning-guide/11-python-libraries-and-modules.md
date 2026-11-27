# 11 — Python Libraries and Modules in Iris

This guide provides a comprehensive breakdown of all external packages and Python standard library modules utilized across the Iris intelligent desktop assistant, their purpose, and where they appear in the source code.

---

## Architectural Philosophy: Zero-Bloat and Security

Unlike many modern AI agent frameworks that require dozens of heavy external dependencies, Iris was engineered under a **strict minimal-dependency and security-first model**:
1. **No External Framework Bloat**: Iris avoids heavy orchestrators (such as LangChain or AutoGen). AI communication, planning, routing, and execution are implemented natively with pure Python.
2. **Standard Library as First Choice**: Whenever standard library utilities exist (`urllib`, `ast`, `subprocess`, `ctypes`, `pathlib`), they are used instead of third-party pip packages.
3. **Optional UI Extensions**: Third-party packages are strictly isolated to optional UI automation features (`requirements-ui.txt`). Non-GUI terminal interactions, dynamic sandbox skills, notes, search, and AI chat run completely with zero third-party packages.

---

## 1. External / Third-Party Dependencies

These packages are declared in [`requirements-ui.txt`](file:///c:/Users/shiva/OneDrive/Desktop/I.R.I.S/requirements-ui.txt) and are imported dynamically only when UI automation or screen analysis is actively requested:

| Package | Purpose in Iris | Source File | Notes |
| :--- | :--- | :--- | :--- |
| **`pyautogui`** | Takes screenshots of the visible desktop on demand. | `screen_capture.py` | Captured frames are held in memory (`io.BytesIO`) and converted to PNG bytes; never written to disk. |
| **`pywinauto`** | Inspects accessible UI trees (buttons, text boxes, windows) on Windows. | `ui_automation.py` | Validates target UI elements before performing click or type actions. |

---

## 2. Core Python Standard Library Modules

### A. Security, Sandboxing, and Dynamic Code Analysis

* **`ast` (Abstract Syntax Tree)**
  * **Where used**: `sandbox_runner.py`, `dynamic_skills.py`
  * **Purpose**: Inspects untrusted Python code before execution. Iris parses code into a syntax tree and walks every node to detect and block banned operations (`eval`, `exec`, `compile`, `__import__`, `globals`, `locals`, `ctypes`, `winreg`, `socket`) and secrets access (`.env`, `GEMINI_API_KEY`).
* **`hashlib`**
  * **Where used**: `screen_capture.py`, `ui_automation.py`
  * **Purpose**: Computes SHA-256 cryptographic hashes for screen frames and UI targets to produce immutable `frame_id` values, ensuring actions cannot execute if the screen has changed.
* **`contextvars` & `contextlib`**
  * **Where used**: `approval_context.py`, `action_gateway.py`
  * **Purpose**: Enforces thread-safe, single-use approval capability tokens. A state-changing action cannot execute unless a valid grant context manager is active.

---

### B. Operating System, Process Execution, and Hardware Profiling

* **`subprocess`**
  * **Where used**: `sandbox_runner.py`, `dynamic_skills.py`, `skills.py`
  * **Purpose**: Executes trial skills inside an isolated subprocess with stripped environment variables (`env={}`), non-blocking execution, and a strict 5.0-second timeout. Also launches approved Windows applications without shell injection risks (`shell=False`).
* **`pathlib.Path`**
  * **Where used**: `config.py`, `dynamic_skills.py`, `skills.py`, `sandbox_runner.py`
  * **Purpose**: Secure object-oriented filesystem paths. Prevents directory traversal attacks (`../`) by validating path parents and resolving paths safely.
* **`ctypes` & `ctypes.wintypes`**
  * **Where used**: `device_profile.py`, `ui_automation.py`
  * **Purpose**: Calls native Windows C-APIs (`kernel32.dll`) directly to query hardware specs (installed RAM, battery status via `GetSystemPowerStatus`) and process handles.
* **`platform`**
  * **Where used**: `device_profile.py`, `solution_verifier.py`, `screen_capture.py`
  * **Purpose**: Detects host OS, architecture (Windows 11 AMD64), and machine attributes.
* **`threading`**
  * **Where used**: `skills.py`
  * **Purpose**: Runs background countdown timers and reminder alerts without freezing the main terminal input loop.
* **`tempfile` & `shutil`**
  * **Where used**: `sandbox_runner.py`, `tests/`
  * **Purpose**: Manages ephemeral sandboxed directories during trial skill execution and test suite lifecycle cleanup.
* **`winsound`**
  * **Where used**: `skills.py`
  * **Purpose**: Plays native Windows system beeps and alert chimes when a countdown timer finishes.
* **`os` & `sys`**
  * **Where used**: Across the entire project
  * **Purpose**: Reads environment variables, handles process exit codes, and resolves system path variables (`%ProgramFiles%`, `%LocalAppData%`).

---

### C. Networking, AI Services, and Web Retrieval

* **`urllib.request`, `urllib.error`, `urllib.parse`**
  * **Where used**: `ai.py`
  * **Purpose**: Performs lightweight, native HTTPS REST calls to **Google Gemini** (chat, vision, search grounding) and **Tavily** search APIs. Eliminates heavy external HTTP libraries (`requests`, `httpx`).
* **`ipaddress`**
  * **Where used**: `ai.py`
  * **Purpose**: Validates loopback safety when connecting to local Ollama endpoints (`http://127.0.0.1:11434/api/chat`), ensuring user prompts are never sent to non-loopback network addresses.
* **`webbrowser`**
  * **Where used**: `skills.py`, `dynamic_skills.py`
  * **Purpose**: Opens approved websites (`youtube`, `github`, `google`) and synthesized web trial skills directly in the user's default browser.

---

### D. Data Structures, Text Processing, and Fuzzy Matching

* **`json`**
  * **Where used**: `ai.py`, `task_planner.py`, `action_gateway.py`, `dynamic_skills.py`
  * **Purpose**: Serializes and parses structured AI task plans, dynamic skill registry files (`registry.json`), and parameter payloads.
* **`re` (Regular Expressions)**
  * **Where used**: `task_planner.py`, `router.py`, `dynamic_skills.py`
  * **Purpose**: Core deterministic parser for command recognition, intent extraction, parameter matching, and safety boundary pattern enforcement.
* **`difflib`**
  * **Where used**: `skills.py`, `dynamic_skills.py`
  * **Purpose**: Provides fuzzy string matching (`SequenceMatcher`). Enables nearest-match app selection and typo-tolerant trial skill execution (e.g., auto-resolving `opne_edge` $\rightarrow$ `open_edge`).
* **`dataclasses`**
  * **Where used**: `task_planner.py`, `action_gateway.py`, `dynamic_skills.py`, `device_profile.py`, `sandbox_runner.py`
  * **Purpose**: Generates strongly-typed, memory-efficient data classes (`PlanStep`, `ActionPolicy`, `DynamicSkillEntry`, `DeviceProfile`, `SandboxResult`).
* **`datetime` & `time`**
  * **Where used**: `skills.py`, `dynamic_skills.py`, `sandbox_runner.py`
  * **Purpose**: Calculates current system time, dates, timer countdowns, execution durations, and registry timestamps.
* **`io` & `base64`**
  * **Where used**: `screen_capture.py`, `ai.py`
  * **Purpose**: Converts in-memory screenshot images into base64-encoded PNG payloads for Gemini 1.5/2.0 Vision analysis.
* **`unicodedata`**
  * **Where used**: `ai.py`, `ui_automation.py`
  * **Purpose**: Sanitizes untrusted strings and removes ANSI terminal escape codes.

---

### E. Auditing, Diagnostics, and Unit Testing

* **`logging`**
  * **Where used**: `main.py`, `skills.py`
  * **Purpose**: Records high-level operational outcomes in `logs/iris.log` without persisting private user prompts, conversation text, or API credentials.
* **`unittest` & `unittest.mock`**
  * **Where used**: `tests/`
  * **Purpose**: Complete test framework driving **163 automated unit tests** across the entire project with zero external dependencies.

---

## 3. Quick-Reference Matrix

| Category | Module / Library | Type | Key Responsibility in Iris |
| :--- | :--- | :--- | :--- |
| **Vision** | `pyautogui` | External (pip) | In-memory desktop screen capture |
| **Automation** | `pywinauto` | External (pip) | Windows UI accessibility element control |
| **Security** | `ast` | Standard Library | Sandbox syntax tree & safety boundary analysis |
| **Security** | `hashlib` | Standard Library | Cryptographic SHA-256 frame integrity |
| **Security** | `contextvars` | Standard Library | Ephemeral per-action execution authorization grants |
| **Sandbox** | `subprocess` | Standard Library | Isolated, timed execution of trial skills |
| **System** | `ctypes` | Standard Library | Native Windows kernel hardware/battery queries |
| **System** | `pathlib` | Standard Library | Safe filesystem path validation |
| **System** | `threading` | Standard Library | Non-blocking countdown timers and reminders |
| **System** | `winsound` | Standard Library | Windows audio notification alerts |
| **AI / Web** | `urllib` | Standard Library | Zero-dependency HTTPS calls to Gemini & Tavily |
| **AI / Web** | `ipaddress` | Standard Library | Loopback validation for local Ollama service |
| **AI / Web** | `webbrowser` | Standard Library | Launching verified websites in default browser |
| **Parsing** | `json` | Standard Library | AI task plan & dynamic skill metadata serialization |
| **Parsing** | `re` | Standard Library | Deterministic command routing & boundary checks |
| **Intelligence**| `difflib` | Standard Library | Typo tolerance & fuzzy matching algorithms |
| **Data Models**| `dataclasses` | Standard Library | Typed domain structures |
| **Testing** | `unittest` | Standard Library | Automated regression verification (163 tests) |
