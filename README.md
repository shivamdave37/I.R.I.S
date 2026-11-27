# I.R.I.S — Intelligent Resident Interactive System
### *A Secure, Hardware-Aware, and Self-Learning Desktop AI Assistant*

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2011-0078D6.svg)](https://www.microsoft.com/windows)
[![Tests](https://img.shields.io/badge/tests-163%20passed-brightgreen.svg)](tests/)
[![Security](https://img.shields.io/badge/governance-Action%20Gateway%20%7C%20Sandbox-success.svg)](#security--governance)
[![Architecture](https://img.shields.io/badge/architecture-Zero--Bloat%20%7C%20Fail--Closed-orange.svg)](#architectural-overview)

---

## 🌟 Introduction

**I.R.I.S** (**I**ntelligent **R**esident **I**nteractive **S**ystem) is a local, privacy-respecting desktop assistant engineered specifically for **Windows**. 

Unlike modern "black-box" agent frameworks that blindly execute terminal commands or run arbitrary code, Iris is built on a **Zero-Trust, Human-Gated architecture**:
* **Deterministic By Default**: Standard requests (time, notes, apps, timers, battery, weather) run instantly with zero cloud latency.
* **Fail-Closed Action Gateway**: No file is written, no app launched, and no state changed without an explicit user confirmation prompt (`yes`/`no`).
* **Hardware-Aware Self-Correction**: Understands the physical machine (CPU, 32GB RAM, integrated GPU) and actively reflects upon and corrects AI responses if a model hallucinates Linux commands (`sudo`, `apt`) or incompatible CUDA code.
* **Dynamic Trial Skills (Self-Learning)**: Allows users to teach Iris new desktop skills on-the-fly (`add this to tr: ...`). Iris drafts the Python code, verifies it via an **AST Security Sandbox**, quarantines execution, and indexes it into a **sub-2-millisecond fast-retrieval pathway**.

---

## 🏛️ Architectural Overview

```
                                    +-----------------------+
                                    |     User Terminal     |
                                    +-----------+-----------+
                                                |
                                                v
                                    +-----------------------+
                                    |       router.py       |
                                    +-----------+-----------+
                                                |
                                                v
                                    +-----------------------+
                                    |    task_planner.py    |
                                    +-----+-----------+-----+
                                          |           |
            (Known deterministic command) |           | (Ambiguous / General Task)
                                          v           v
                    +-----------------------+       +-----------------------+
                    |  Deterministic Plan   |       |   ai.py (Gemini/Ollama|
                    +-----------+-----------+       +-----------+-----------+
                                |                               |
                                +---------------+---------------+
                                                |
                                                v
                                    +-----------------------+
                                    |   action_gateway.py   |  <--- [Type 'yes' to approve]
                                    |  (Single-Use Grants)  |
                                    +-----------+-----------+
                                                |
                        +-----------------------+-----------------------+
                        |                                               |
                        v                                               v
            +-----------------------+                       +-----------------------+
            |       skills.py       |                       |   dynamic_skills.py   |
            |  (Verified Built-ins) |                       | (Fast Cache < 2ms)    |
            +-----------------------+                       +-----------+-----------+
                                                                        |
                                                                        v
                                                            +-----------------------+
                                                            |   sandbox_runner.py   |
                                                            | (AST Analysis + Subp) |
                                                            +-----------------------+
```

### The 4 Core Principles
1. **Zero Silent Side-Effects**: The AI model is treated as an untrusted advisor. It can propose steps in JSON, but cannot authorize or execute them.
2. **Single-Use Capability Grants**: Approvals are snapshot-isolated. Approving Step 1 never grants permission for Step 2.
3. **AST-Enforced Sandbox**: Trial code cannot import `socket`, `winreg`, `ctypes`, access `.env` keys, or call `eval()`/`exec()`.
4. **Offline Resilience**: Runs completely offline using local system skills or local Ollama models; Gemini and Tavily are used only when external grounded research or vision is requested.

---

## 🚀 Key Features

### 1. Dynamic Trial Skills & Self-Learning
Teach Iris new abilities directly in chat using natural keywords:
* **Add a Skill**: `add this to tr: open spotify` or `add this to trial chrome_account for open first account in chrome`
* **Safety Boundary Check**: If a requested skill requires forbidden actions (e.g., `add this to tr: scan network ports`), Iris **refuses** with an explanatory reason.
* **Fast-Retrieval Pathway (< 2ms)**: Queries are indexed in `data/temp_skills/registry.json`. Running `open spotify` or `run trial open_spotify` executes in under 2ms.
* **Typo Tolerance**: If you misspell a skill name (`run trial opne_edge`), the built-in SequenceMatcher auto-corrects to `open_edge`.
* **Lifecycle Management**:
  * List skills: `trial skills`
  * Promote to permanent: `promote trial <name>`
  * Delete from cache: `delete trial <name>`

### 2. Device Profiling & Reflection Loop
* **Hardware Detection (`device_profile.py`)**: Detects Windows 11 Home, 12th Gen Intel Core i5, 32GB RAM, and Intel Iris Xe GPU.
* **Self-Correction Loop (`solution_verifier.py`)**: Catches:
  * Linux package managers (`sudo apt`, `yum`, `brew`) $\rightarrow$ rewrites to Windows PowerShell or winget.
  * Incompatible GPU libraries (`torch.cuda`, CUDA compute) $\rightarrow$ rewrites for Intel CPU / OpenVINO / DirectML.
  * Oversized models exceeding RAM limits $\rightarrow$ warns and recommends lightweight alternatives.

### 3. Desktop Automation & File Search
* **Safe Local File Search**: Multi-root indexed search across `Desktop`, `Documents`, `Downloads`, and `OneDrive` without scanning sensitive system drives.
* **App Allowlist**: Quick-launch trusted apps (`notepad`, `calculator`, `paint`) and websites (`youtube`, `github`, `google`).

### 4. Productivity Tools
* **Encrypted Notes**: `note <text>`, `show notes`, `search notes for <query>`, `delete note <index>`.
* **To-Do Tasks**: `add task <text>`, `tasks`, `complete task <index>`, `delete task <index>`.
* **Timers & Reminders**: `set timer for 5 minutes: check oven`, `remind me in 10 minutes to take a break`.
* **Clipboard Manager**: `read clipboard` and `copy to clipboard: <text>`.
* **System Specs & Battery**: `system status`, `specs`, and `battery`.
* **Live Weather**: `weather in London` or `weather`.

### 5. Grounded Research & Vision
* **Verifiable Web Search**: Grounded Google Search (Gemini) or Tavily API returning verified HTTPS citations.
* **AI Screen Vision**: Captures a temporary, in-memory screenshot (`capture screen`) and sends it to Gemini Vision (`describe screen`) with explicit privacy disclosures.

---

## 💻 Command Reference Cheat Sheet

| Category | Command Example | What It Does |
| :--- | :--- | :--- |
| **Trial Skills** | `add this to tr: open spotify` | Creates, validates, and stores a trial skill in the sandbox. |
| **Trial Skills** | `run trial open_spotify` | Runs a trial skill inside the quarantined sandbox. |
| **Trial Skills** | `trial skills` | Displays all registered dynamic skills, IDs, tags, and run counts. |
| **Trial Skills** | `delete trial open_spotify` | Permanently deletes a trial skill from cache and disk. |
| **App Launch** | `open notepad` / `open youtube` | Launches an approved application or website. |
| **Search Files** | `search files report.pdf` | Searches across Documents, Desktop, Downloads, and OneDrive. |
| **Search Files** | `open result 1` | Opens the selected search result after user approval. |
| **Notes** | `note buy groceries` | Saves a note to `data/notes.json`. |
| **Notes** | `show notes` / `search notes milk` | Lists or searches saved notes. |
| **Tasks** | `add task finish report` | Adds an item to the active to-do list. |
| **Tasks** | `tasks` / `complete task 1` | Shows active tasks or marks task #1 completed. |
| **Timers** | `set timer for 10 minutes` | Runs an asynchronous countdown timer with audio chime. |
| **System** | `system status` / `specs` | Displays CPU, 32GB RAM load, and drive capacity. |
| **System** | `battery` | Checks real-time battery level and charging status. |
| **Vision** | `capture screen` | Captures desktop to temporary memory. |
| **Vision** | `describe screen` | Sends captured frame to Gemini Vision after approval. |
| **Research** | `research quantum computing` | Grounded search with HTTPS source citations. |
| **General Chat**| Any general question | Direct chat with hardware reflection loop. |

---

## 🔒 Security & Governance

Iris operates under a **Fail-Closed Security Architecture**:

```
+-------------------------------------------------------------+
|                     Action Gateway Checks                   |
+-------------------------------------------------------------+
| 1. Is the action registered in ACTION_POLICIES?             |
| 2. Does it change local state?                              |
|    - If YES: Display exact parameters & ask typed 'yes'.   |
| 3. Are parameters snapshot-isolated (JSON copied)?          |
| 4. Is the single-use token valid?                           |
| 5. Dispatch -> Invalidate token immediately.                |
+-------------------------------------------------------------+
```

### Sandbox Restrictions (`sandbox_runner.py`)
Dynamic trial skills execute inside isolated worker processes with:
* **Stripped Environment**: Environment variables (including `GEMINI_API_KEY`) are cleared (`env={}`).
* **AST Pre-flight Analysis**: Syntax trees are parsed before execution. Blocked features include:
  * Dynamic execution: `eval`, `exec`, `compile`, `__import__`, `globals()`, `locals()`.
  * Networking: `socket`, `http.server`, `ftplib`, `smtplib`, `telnetlib`.
  * Low-level bypasses: `ctypes`, `winreg` (Windows Registry tampering).
* **Strict 5.0-Second Timeout**: Infinite loops or hanging calls are terminated automatically.

---

## 📦 Tech Stack & Python Modules

Iris uses **Python 3.10+** and relies almost entirely on Python's built-in standard library for maximum speed and security:

* **AST & Code Analysis**: `ast`, `hashlib`, `contextvars`
* **Process & System**: `subprocess`, `ctypes`, `pathlib`, `platform`, `threading`, `winsound`
* **Zero-Dependency Networking**: `urllib.request`, `ipaddress`, `webbrowser`
* **Data & Intelligence**: `json`, `re`, `difflib` (fuzzy matching), `dataclasses`
* **Optional GUI Extensions (`requirements-ui.txt`)**:
  * `pyautogui` (in-memory screenshotting)
  * `pywinauto` (accessible UI automation)

*(For a deep dive, see [`docs/learning-guide/11-python-libraries-and-modules.md`](file:///c:/Users/shiva/OneDrive/Desktop/I.R.I.S/docs/learning-guide/11-python-libraries-and-modules.md))*

---

## 🛠️ Installation & Quickstart

### Prerequisites
* **Windows 10 or 11**
* **Python 3.10 or newer**

### 1. Clone or Open the Repository
```powershell
cd c:\Users\shiva\OneDrive\Desktop\I.R.I.S
```

### 2. Configure Environment (Optional for Cloud AI)
Copy the example settings:
```powershell
copy .env.example .env
```
Open `.env` and add your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
IRIS_AI_PROVIDER=gemini
# Optional Tavily search provider:
TAVILY_API_KEY=your_tavily_key_here
```
*(Note: If you do not have an API key, Iris works locally with local commands, notes, timers, trial skills, and local Ollama).*

### 3. Install Optional UI Dependencies (Optional)
If you wish to use desktop screen vision and UI clicking:
```powershell
python -m pip install -r requirements-ui.txt
```

### 4. Run Iris
```powershell
python main.py
```

---

## 🧪 Verification & Automated Testing

Iris includes an extensive suite of **163 automated unit tests** verifying action gateway policies, AST sandboxing, file security, fuzzy matching, and task planning:

```powershell
python -m unittest discover -s tests -v
```

All 163 tests run in under 2 seconds:
```
Ran 163 tests in 1.602s
OK (skipped=2)
```

---

## 📁 Project Structure

```
I.R.I.S/
├── action_gateway.py        # Central authorization gateway & single-use execution tokens
├── ai.py                    # Stateless Gemini / Ollama / Tavily provider interface
├── approval_context.py      # Thread-safe capability grant context manager
├── config.py                # App allowlists, search roots, and AI model settings
├── device_profile.py        # Native Windows hardware profiling (RAM, CPU, GPU, OS)
├── dynamic_skills.py        # Trial skills cache, registry indexing, and <2ms fast retrieval
├── sandbox_runner.py        # Quarantined subprocess execution & AST safety analyzer
├── solution_verifier.py     # Self-correction loop (catches Linux commands, CUDA, RAM overload)
├── router.py                # Command normalizer and top-level request router
├── task_planner.py          # Deterministic command planner and plan validator
├── skills.py                # Core trusted skills (notes, tasks, timers, files, weather)
├── screen_capture.py        # In-memory RAM screen capture
├── screen_vision.py         # Image formatting and Gemini Vision integration
├── ui_automation.py         # Accessible Windows UI target validation and interaction
├── main.py                  # Terminal interactive loop and privacy-safe event logger
├── data/
│   ├── notes.json           # Local notes store
│   └── temp_skills/         # Isolated staging cache for trial skills
│       └── registry.json    # Fast-retrieval index (<2ms lookup)
├── docs/
│   ├── FLOWCHART.md         # Architecture and lifecycle diagrams
│   └── learning-guide/      # Complete educational revision & learning curriculum
├── tests/                   # 163 unit tests covering the entire system
└── requirements-ui.txt      # Optional packages for screen capture and UI automation
```

---

## 📜 License & Acknowledgments

Built with native Python for high performance, uncompromising security, and privacy on Windows. Designed to demonstrate robust agentic AI governance, deterministic task planning, and quarantined self-learning architectures.
