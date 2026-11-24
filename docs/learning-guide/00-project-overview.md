# 00 — What Iris is

## Project in one sentence

Iris is a typed terminal assistant that maps supported requests to a small set of fixed Python skills, asks typed approval before consequential actions, and can use Gemini or local Ollama for chat and constrained planning. Its research workflow can use Gemini Search or the optional Tavily Search integration. It is not a general-purpose autonomous computer operator.

## Problem statement

People repeatedly perform small desktop tasks—opening a known application or website, checking the date or time, keeping notes, and asking questions. Switching between separate tools adds friction. Iris explores a single text interface for a limited set of those tasks while keeping the action set explicit and asking before side effects.

**College-ready problem statement:** Users often need to move between a conversational assistant and simple desktop utilities to complete routine information and organization tasks. A general chatbot can answer questions, but its answer alone does not safely perform local actions or preserve user-selected notes. The project therefore investigates a modular Python assistant that accepts typed requests, routes known requests to predefined skills, previews multi-step actions, obtains explicit approval for consequential work, and reports success or failure. The system is intentionally bounded: model output is treated as data and cannot create arbitrary executable actions.

## Abstract

Iris is a modular, command-line personal assistant implemented in Python. It supports help, local date and time, a small allowlist of applications and websites, JSON-backed notes, keyword search and approved deletion, provider-backed chat, constrained task planning, bounded web research, and inert skill proposals. Known commands are parsed locally. Ambiguous action requests may be sent to a configured AI provider, but the returned JSON is validated against a fixed skill schema before execution. Side-effecting actions require typed approval. Notes are stored locally, while chat history is temporary in memory. Automated tests exercise routing, validation, permissions, storage, error paths, and provider formatting, usually with mocks. The project demonstrates modular design and safety boundaries; live web service availability and machine-specific app paths remain environment-dependent.

## Objectives

1. Offer a simple typed terminal loop.
2. Keep command handling, planning, capabilities, AI calls, and configuration in separate modules.
3. Support a limited, inspectable registry of local actions.
4. Require typed approval before launching, writing/deleting notes, searching the web, or creating proposals.
5. Validate an entire task plan before any of its steps run.
6. Store user-requested notes safely and recover without overwriting malformed data.
7. Present sourced research only when the provider returns valid HTTPS source URLs.
8. Use tests to check expected behavior and regression cases.

## Features and evidence status

| Feature | Code status | What evidence means |
|---|---|---|
| Terminal loop and clean exit | Implemented | Unit tests cover the loop with mocked input and exceptions. |
| Help, date, time | Implemented | Deterministic local Python functions. |
| Open app/site | Implemented for allowlisted entries | Launch calls are mocked in tests; a real app path/browser is machine-dependent. |
| Notes, list/search/delete | Implemented | Tests use temporary directories; real notes in `data/` are runtime data. |
| Deterministic multi-step plans | Implemented for recognized syntax | Planner tests validate ordering, denial, failure, and dependency behavior. |
| AI-assisted plan interpretation | Implemented with strict validation | Tests can mock provider responses; safety depends on local validation too. |
| Gemini chat | Implemented | Earlier project history reports a successful chat; this guide did not make a live call. |
| Ollama chat/planning | Implemented for loopback URL | Service/model availability was not verified live here. |
| Gemini Search grounding | Implemented | Prior live request returned HTTP 429 / quota exhaustion; successful current live research is not established. |
| Tavily Search | Implemented in current uncommitted changes | Requires `TAVILY_API_KEY` and provider selection; tests mock the HTTP request. Live Tavily success is not verified. |
| Skill proposal | Implemented as inert proposal storage | Code is statically checked and displayed, not executed or automatically installed. |
| GUI / voice / screen control | Absent from current source inventory | No GUI, microphone, speaker, or screen-control implementation exists in the inspected root. |
| Self-update of trusted source | Absent | Proposals do not activate code; no updater pipeline exists in current source. |
| Multiple autonomous agents | Absent | There are modules and a planner, not a set of separately trained autonomous agents. |

## Scope and limitations

**In scope:** terminal input, fixed allowlisted actions, simple notes, one configured AI chat/planning provider, and bounded research providers.

**Out of scope today:** arbitrary app control, screen understanding, voice, GUI, unrestricted shell commands, arbitrary code execution, background agent teams, and automatic self-modification. Iris does not learn from notes as a person would; note search is a string match. AI providers can be unavailable, rate-limited, or configured incorrectly. The actual app executable path and default browser depend on the user's Windows setup.

## Why it is more than a basic chatbot—and why it is still limited

A basic chatbot only returns text. Iris also has a deterministic router/planner, a fixed skill registry, typed approval, local note storage, and an execution summary. However, the model itself does not directly operate the computer. The model may interpret a request or answer a question; the local program decides whether the model's proposed skill and parameters are allowed.

## Methodology

The program receives typed text, tries deterministic local parsing, and sends only unresolved action-like requests to the constrained planner. It validates schema and parameters, previews the resulting plan, requests approvals, then calls fixed Python functions. Provider output and external web content are treated as untrusted input. Tests replace network and app effects with mocks or temporary storage.

## Conclusion

Iris is a useful prototype for learning modular Python, command parsing, JSON, HTTP integration, permissions, and unit testing. Its strongest design choice is a narrow action boundary: an AI response is not itself executable authority. The project should be presented as a bounded assistant foundation rather than a finished general AI agent.

### Recap

Iris combines chat with a small number of real Python actions. The trusted code, not the AI response, controls what can execute.

### Check yourself

1. What does Iris do that a plain chat response does not?
2. Why is an allowlist useful?
3. What does a passing mocked test fail to prove?
4. Is skill proposal code active in the trusted registry?
5. Which research provider has not been live-verified?

**Answers:** 1. It can call fixed skills after validation/approval. 2. It limits possible targets. 3. Real network/account/device behavior. 4. No. 5. Tavily in this checkout; Gemini Search previously hit quota.
