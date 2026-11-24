# 09 — Viva question bank and revision

Answers are phrased so you can speak them naturally. The deeper notes help you understand rather than memorize.

## Project and design

### 1. What problem does Iris solve?
**Speak:** “Iris brings a few routine desktop tasks and conversational questions into one typed terminal assistant, while requiring approval before consequential actions.”
**Deeper:** Its scope is intentionally limited to fixed skills, not general computer control. **Where:** overview, `task_planner.py`.
**Follow-up:** What is outside the current scope? Voice, GUI, arbitrary screen control, arbitrary code execution.

### 2. Why did you choose Python?
**Speak:** “Python is readable for a prototype and provides standard libraries for JSON, paths, HTTP, process launching, logging, and testing.”
**Deeper:** This checkout declares no third-party package manifest; its inspected imports are standard library. **Where:** all modules.
**Follow-up:** Does Python itself provide Gemini? No, Iris sends HTTP requests to Gemini's API.

### 3. Why split the project into modules?
**Speak:** “Each module has a focused responsibility: terminal loop, planning, concrete skills, AI communication, configuration, and proposal records.”
**Deeper:** It helps locate bugs and test behavior independently, although a new skill must be wired into more than one place. **Where:** architecture diagram.
**Follow-up:** What is a downside? More interfaces/import relationships to maintain.

### 4. What makes Iris more than a chatbot?
**Speak:** “It has fixed Python actions, local notes, a validated task plan, and user approvals, in addition to chat.”
**Deeper:** The language model does not directly execute actions. The local planner and registered functions control execution. **Where:** `task_planner.py`.
**Follow-up:** Is Iris a fully autonomous AI agent? No.

## Python and execution flow

### 5. What happens after a command is typed?
**Speak:** “`main.run` reads it, `router.handle` forwards it to `task_planner.handle`, the planner recognizes or asks the model for a plan, validates it, previews it, gets approvals, and dispatches fixed skills.”
**Where:** `main.py`, `router.py`, `task_planner.py`.
**Follow-up:** Which module prints the plan? `task_planner._describe_plan` output path.

### 6. What is a function parameter versus argument?
**Speak:** “A parameter is the input name in a function definition; an argument is the actual value passed at the call.”
**Example:** `search_notes(query)` has parameter `query`; `search_notes("milk")` passes argument `"milk"`.
**Follow-up:** What does `return` do? Sends a value back and exits the function.

### 7. Why use a dataclass for `PlanStep`?
**Speak:** “It groups the fields that describe one step and generates routine initialization code.”
**Deeper:** Each step tracks name, skill, parameters, dependencies, permission, status, and result. **Where:** `task_planner.py`.
**Follow-up:** Why `default_factory=list`? It gives each instance its own list.

### 8. What is the difference between a list and a dictionary here?
**Speak:** “A list keeps an ordered sequence of steps or notes; a dictionary maps named keys to values such as skill parameters.”
**Follow-up:** Why is parameter key equality checked? To reject missing and unexpected inputs.

### 9. What is an exception?
**Speak:** “It is Python's way to signal that an operation failed, such as reading invalid JSON or timing out.”
**Deeper:** `try/except` lets Iris return controlled errors; `finally` cleans temporary files even when a write fails. **Where:** `skills.py`, `ai.py`, `main.py`.
**Follow-up:** Why not catch every error silently? It could hide failures and claim success.

### 10. Why use `Path(__file__)`?
**Speak:** “It derives project paths from the module location rather than the terminal's current folder.”
**Where:** `config.py`.
**Follow-up:** Does that make every path portable? No, the configured Chrome path is machine-specific.

## Planning, approvals, and safety

### 11. How does Iris choose an action?
**Speak:** “Known wording is parsed locally. Ambiguous action wording can be sent to the configured model for JSON, but Iris validates the skill and arguments against local rules.”
**Where:** `task_planner._deterministic_plan`, `_model_plan`, `validate_plan`.
**Follow-up:** What if AI invents `delete_everything`? Validation rejects it.

### 12. Why validate the full plan before execution?
**Speak:** “So an invalid later step cannot be discovered after an earlier side effect has already happened.”
**Follow-up:** Does this prevent every partial task? It prevents partial work due to validation/approval denial, but runtime failures after execution starts can still produce partial results.

### 13. How does typed approval work?
**Speak:** “The user must type exactly `yes`, ignoring case and surrounding whitespace; any other answer denies.”
**Where:** `task_planner._approval`.
**Follow-up:** Does voice approval work? No.

### 14. What happens if one multi-step approval is denied?
**Speak:** “The denied step is marked denied, remaining steps skipped, and the execution phase is not entered.”
**Evidence:** `tests/test_phase5_integration.py` uses a unique marker and temporary notes storage.
**Follow-up:** What happens after execution has begun and one step fails? Dependent steps skip; independent steps can continue.

### 15. How is note deletion protected?
**Speak:** “The planner asks for approval, then passes `approved=True`; the note function refuses direct deletion without that flag and validates the index.”
**Where:** `task_planner.py`, `skills.delete_note`.
**Follow-up:** Can the function prevent every other program from editing the file? No.

### 16. Is the proposal workflow self-modification?
**Speak:** “No. It creates and validates an inert proposal record, but never runs or registers generated code.”
**Where:** `skill_development.py`.
**Follow-up:** Why not run the static-approved code? Static checks are not an OS sandbox, so the implementation deliberately avoids execution.

### 17. Is Iris perfectly secure?
**Speak:** “No. It uses safeguards like allowlists, typed approval, validation, path checks, and bounded requests, but trusted-code bugs and environment risks remain.”
**Follow-up:** Give an example limitation. A correct HTTPS URL can still lead to false or harmful content.

## APIs and testing

### 18. How is the API key protected?
**Speak:** “It is read from the process environment or local `.env`, excluded from Git, sent in a header, and not intentionally printed in responses/logs.”
**Follow-up:** Does `.gitignore` remove a key already committed? No; previously tracked secrets require history/security remediation.

### 19. What happens when Gemini quota is exhausted?
**Speak:** “For HTTP 429, Iris returns quota guidance and no research findings. It does not repeatedly retry.”
**Where:** `ai._research_with...`, `research_web`, and tests.
**Follow-up:** Can code remove an account quota restriction? No; that needs provider account/project action.

### 20. How does Ollama differ from Gemini?
**Speak:** “Ollama is a local service restricted to loopback; Gemini is a remote hosted API requiring a key and internet.”
**Follow-up:** Does Ollama search the web? No, the code reports that research is unavailable through Ollama.

### 21. What is a mock?
**Speak:** “A mock replaces a real dependency with a controlled fake during a test.”
**Deeper:** It prevents opening actual apps or spending API credits and lets the test assert the expected call. **Where:** `tests/`.
**Follow-up:** What can a mock not prove? That the real external service works now.

### 22. What does an assertion do?
**Speak:** “It checks a condition; if false, unittest marks the test as failed.”
**Example:** `assertEqual(search_reply, "No matching notes.")` checks a denied plan left no matching note.
**Follow-up:** Do assertions change production behavior? No, tests execute them separately.

### 23. Why can all tests pass while live research fails?
**Speak:** “Most research tests mock the provider response. They verify parsing and error handling but not real credentials, quota, or current service availability.”
**Where:** `tests/test_research.py`.
**Follow-up:** What is the current live evidence? Gemini Search previously returned 429; Tavily live success is unverified.

### 24. What does the 69-test result mean?
**Speak:** “All 69 discovered tests passed in the run, so those covered scenarios passed; it does not guarantee all real-world behavior.”
**Follow-up:** Exact command? `python -m unittest discover -s tests`.

## Limitations and future work

### 25. What are the current limitations?
**Speak:** “The action list is fixed, there is no GUI/voice/screen control, app paths are machine-specific, and external AI/search may be unavailable or quota-limited.”
**Follow-up:** Can Iris modify itself? No, proposal records stay inactive.

### 26. What would you improve with another month?
**Speak:** “I would first reconcile capability/help wording, add clearer typed result types instead of classifying errors by text prefixes, and then verify an optional search provider live with consent.”
**Deeper:** This is future work, not current functionality. **Where:** known limitations in planner/help/research.
**Follow-up:** Why not jump straight to arbitrary computer control? It would greatly enlarge the safety and testing problem.

### 27. Explain the `open Notepad` flow.
**Speak:** “The parser recognizes `notepad`, confirms it is allowlisted, builds an `open_target` step, shows a preview, asks typed yes, and calls `skills.open_approved`.”
**Follow-up:** What if the path is missing? The skill returns a clear not-found message.

### 28. Explain a note write.
**Speak:** “The note text is validated, approved, added to a list parsed from JSON, then written to a temporary file and atomically replaced into `data/notes.json`.”
**Follow-up:** Why keep notes separate from chat history? Notes are explicit persistent user data; chat history is temporary context.

### 29. Explain an API request.
**Speak:** “Iris builds a JSON payload, creates an HTTPS POST request with headers, sets a timeout, limits response size, decodes JSON, and validates the returned shape.”
**Follow-up:** What if the response is malformed? A controlled error is returned; no fake findings are shown.

### 30. How would you explain one line in your own words?
**Suggested answer pattern:** “This expression takes [input], checks/transforms it using [Python feature], then returns/updates [value]. It is needed because [reason]. If removed, [specific effect].”
**Follow-up:** Demonstrate on `set(params) != exact` in `_validate_step`.

## Glossary

- **Allowlist:** explicit collection of permitted choices.
- **API:** rules and endpoints that let programs communicate.
- **Argument:** actual value passed to a function.
- **Atomic replacement:** replace a file in one filesystem operation so readers are less likely to observe a partial file.
- **Dataclass:** Python decorator that generates common data-container methods.
- **Dependency:** a step that must succeed before another step can run.
- **Environment variable:** process-level configuration value.
- **Exception:** signal that an operation failed.
- **HTTP 429:** server response indicating too many requests or a usage/quota restriction; exact meaning depends on provider response details.
- **JSON:** text format for lists, objects, strings, numbers, Booleans, and null.
- **Mock:** controlled substitute used by a test.
- **Module:** one Python source file.
- **Parameter:** named input in a function definition.
- **Schema:** expected structure and field rules for data.
- **Side effect:** change outside a function's returned value, such as writing a note or opening an app.
- **Untrusted input:** data that must be validated and must not control privileged behavior by itself.

## Final revision checklist

- [ ] I can explain the problem statement in my own words.
- [ ] I can draw the path `main → router → task_planner → skills/ai`.
- [ ] I can distinguish local parsing, model planning, validation, approval, and execution.
- [ ] I can explain list/dictionary/function/exception/path/JSON/API/mock using Iris examples.
- [ ] I can explain note write and denied multi-step workflows.
- [ ] I can say exactly what the tests verify and what they do not.
- [ ] I can state honestly that live Tavily search is not verified and Gemini research encountered quota exhaustion.
- [ ] I can explain that skill proposals stay inert.
- [ ] I can name at least three limitations and three realistic next improvements.

## End-of-guide exercise

Without looking at the guide, explain this chain in two minutes: “User asks to research a subject; Iris previews the request and asks permission; provider returns sources; Iris formats only supported output; quota/network errors produce no invented result.” Then check `task_planner.py`, `skills.py`, and `ai.py` to correct any missing module/function names.
