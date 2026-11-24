# 05 — `ai.py`: chat, plans, and web research

## Purpose and imports

`ai.py` is the network/service boundary. It imports JSON, IP-address validation, environment/path utilities, standard-library HTTP request/error tools, Unicode cleanup, and project `config`. No external HTTP package is imported. `SYSTEM_PROMPT` says chat can answer but cannot control the computer. `PLANNER_PROMPT` describes the exact JSON format, registered actions, limits, and unsafe capabilities that must not be proposed. `SKILL_PROPOSAL_PROMPT` requests inert constrained source text. `_HISTORY` is a temporary process-memory list.

## `_load_env_file()`

Finds `.env` under `config.PROJECT_FOLDER`, not the shell's current working directory. If absent, returns success so ordinary environment variables can still work. It rejects symlinks and resolved paths outside the project. It reads UTF-8 lines, skips blanks/comments/malformed lines, splits the first `=`, and loads only a fixed allowlist of variable names if the process environment does not already have a value. It never prints loaded values. File and encoding errors return `False`.

**Teaching point:** the environment variable supplied by the operating system takes precedence over `.env` because only missing/empty process variables are filled.

## `_request_json(url, payload, headers=None, max_bytes=1000000)`

Serializes a dictionary as UTF-8 JSON, creates a POST request with JSON content type plus provider headers, and calls `urlopen` with a 30-second timeout. It reads at most one megabyte plus one byte; if the response exceeds the limit it raises `ValueError`. It decodes UTF-8 and parses JSON. This shared helper bounds time and response size, but DNS/TLS/provider behavior still depends on the real environment.

## Gemini chat: `_ask_gemini`

Reads `GEMINI_API_KEY`; if absent returns a clear setup message. It converts internal `user`/`assistant` history to Gemini's `user`/`model` role form. It builds the model endpoint from `config.GEMINI_MODEL`, URL-encodes the model name, and sends the key in `x-goog-api-key`, not in the URL. It extracts candidate text and rejects empty or malformed responses. It maps 429 to a rate-limit message, 401/403 to key/account access, 404 to model configuration, other HTTP errors to a generic status, network/timeout failures to a connection message, and malformed data to an unexpected-response message. The response body and key are not shown.

## Ollama chat: `_ask_ollama`

Parses `config.OLLAMA_URL` and accepts only `http`, an IP address that is loopback, no username/password, and the exact `/api/chat` path. It sends system/user messages, model name, and `stream=False`. It extracts `message.content` and maps missing service/model/malformed response to clear messages. This is local Ollama chat, not web search. It was not verified against a live Ollama server in this guide.

## `ask(message)`

Rejects empty input and unsafe `.env` reads; appends the user text to `_HISTORY`; caps history to ten items; checks whether the configured Gemini key appears in any conversation text and refuses if so; selects `IRIS_AI_PROVIDER` or the configured default; calls Gemini or Ollama; and on failure removes the just-added user entry. On success it stores the assistant response and caps history again. The history disappears when Iris exits and is not the notes database.

## `plan_request(message)`

Requires nonempty text, loads environment, refuses if the key appears in the request, chooses the configured chat provider, wraps the user's request in a reminder to treat it as data, and calls the model using `PLANNER_PROMPT`. Provider errors become `RuntimeError`; the planner later validates the text. This is one stateless model request: it does not use the chat history.

## Output cleanup and Gemini research formatting

`_safe_display_text(value)` removes control characters except newline and tab. `_format_grounded_research(result)` extracts Gemini candidate text and grounding metadata. It requires a nonempty bounded summary and a list of source chunks. Each URL must be a reasonably short HTTPS URL with a hostname, no credentials, whitespace, or control characters. It limits displayed sources, maps grounding chunk indices to source numbers, adds claim/source references if valid, reports search queries if provided, and labels uncertainty. If structure/sources are missing or invalid, it returns an error without presenting findings as grounded.

These checks improve display hygiene and source attribution; they do not independently prove that a webpage's claims are true or unbiased.

## Tavily research formatting and request

`_format_tavily_research(result)` requires a dictionary-like response with string answer and result list. It accepts only valid HTTPS source URLs, sanitizes title/content/answer, limits results, and refuses to show the generated answer if no valid HTTPS source exists. The answer is explicitly labeled AI-written and uncertainty is disclosed.

`_research_with_tavily(query, api_key)` sends a POST to `https://api.tavily.com/search` with basic depth, at most five results, generated answer enabled, and raw content disabled. The API key is in `Authorization: Bearer ...`. It maps 401/403, 429, plan limits 432/433, other statuses, timeout/network failures, and malformed results to safe messages. It does not retry, which avoids repeating quota requests.

## `research_web(query)`

Validates query length (3–500 characters), loads environment, chooses `IRIS_RESEARCH_PROVIDER` first, then `IRIS_AI_PROVIDER`, then `config.AI_PROVIDER`. For Tavily, it requires `TAVILY_API_KEY`, refuses a query containing that key, and calls the Tavily helper. Unknown providers fail clearly. For Gemini, it requires `GEMINI_API_KEY`, refuses a query containing it, sends a Google Search-grounded Gemini request, and maps quota/auth/model/network/response errors. It returns formatted actual provider response data or an error; it must not be described as successful live research unless that call succeeds with sources.

## Skill-proposal generation and history reset

`generate_skill_proposal(name, purpose)` validates nonempty metadata and length, prevents key leakage in purpose, selects Gemini or Ollama, requests text under a restrictive prompt, and returns source as inert text. `skill_development.py` performs static validation and storage; this function does not execute the generated source. `clear_history()` empties the temporary history list.

## Current evidence and limitations

Automated tests mock HTTP requests and validate parsing/error messages, including Gemini 429 and Tavily success-shaped responses. Current code includes Tavily as an optional provider, but a mocked response is not a live search. Live Tavily still requires the user to configure their own key and account allowance. Gemini Search previously returned HTTP 429 / `RESOURCE_EXHAUSTED`; do not keep retrying quota failures. No live research success is established by this guide.

### Recap and viva questions

1. Why is Ollama URL restricted to loopback? To avoid sending local chat to an arbitrary remote host.
2. Where is the Gemini key placed? In a request header.
3. Why are web results treated as untrusted? Retrieved text may be incorrect or contain manipulative instructions.
4. Why cap provider response bytes? To bound memory and reject oversized results.
5. Does Tavily's mock test prove live search? No.
