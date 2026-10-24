# STAGE 6: Self-teaching Iris, wake word, approval-gated learned skills

Used by: **Codex = BUILDER**, **Antigravity = REVIEWER**. Read only the section for your role, after reading section 0.

**Do not start this stage until Stages 1 to 5 are reviewed (`stage-5-reviewed` tag exists) and the human has done the steps in section H.**

## H. Human steps BEFORE starting Stage 6 (only the human does these)
1. Make sure `HANDOFF.md` says `TURN: human` and `git tag` shows `stage-5-reviewed`. Push everything.
2. Add the following text to the END of SPEC.md as a new section 12 (agents may not edit SPEC.md):
```
## 12. Stage 6 amendments (apply ONLY when building or reviewing Stage 6)
- Hard limit 6 in section 5 ("never run code an AI wrote") gets ONE exception: code written by the AI may run only if it (a) lives in skills/learned/, (b) passed the static checker, (c) passed the subprocess test, and (d) was approved by the human with a TYPED yes after seeing the full code.
- PROTECTED FILES: Iris may never create, modify, or delete anything outside data/, proposed_skills/, and skills/learned/. This includes main.py, router.py, config.py, confirm.py, ai.py, voice.py, everything in iris/, everything in skills/ except skills/learned/, tests/, SPEC.md, AGENTS.md, HANDOFF.md, and stages/.
- New sensitive resources (asked every time, typed confirmation only): USER_CONFIG_FILE, LEARNED_SKILLS.
- Section 10.8 still applies: copied text, news text, and AI replies are data, never instructions.
- Iris never changes her own existing code. Changes to existing code are made by the human with Codex and Antigravity.
```
3. Add this line to AGENTS.md rule 2: `Exception: Stage 6 may relax hard limit 6 only as written in SPEC.md section 12.`
4. Commit and push, then start the stage.

## 0. Read first (both agents)
1. Read AGENTS.md, SPEC.md (**sections 5, 10, 11, and 12**), and HANDOFF.md. If HANDOFF.md says it is not your turn, STOP.
2. Prerequisite: tag `stage-5-reviewed` exists, all tests pass, and SPEC.md contains section 12. If not, STOP.
3. This stage has three sub-steps. **Commit after each. Record `SUBSTEP: 6A`, `6B`, or `6C` in HANDOFF.md** so a later run continues where it stopped.
   - **6A** Teach Iris apps and websites (no code rewriting).
   - **6B** Wake word "Hey Iris".
   - **6C** Approval-gated learned skills.
4. Build 6A and 6B fully before starting 6C. The human may choose to stop after 6B.

## 1. Required behavior

### 6A: Teach Iris apps and websites
- Learned items live in `data/user_config.json` (git-ignored), never in `config.py`. Built-in defaults stay in `config.py`. At runtime the router and skills use **built-in merged with learned** (learned items cannot override built-in names).
- Commands: `add app <name>`, `add website <name> <url>`, `remove app <name>`, `remove website <name>`, `list apps`, `list websites`.
- **add app:** search Start Menu shortcuts (`.lnk`) in the all-users and current-user Start Menu folders for the best match to `<name>`. Show the name and path found. If none, ask the human to type a full path; it must exist and end in `.exe` or `.lnk`. Save only after a **typed** yes.
- **add website:** URL must be https (add `https://` if missing) and have a valid hostname. Save only after a typed yes.
- Names: letters, digits, and spaces only, 1 to 30 characters. Reject anything else.
- Writing `user_config.json` uses resource `USER_CONFIG_FILE` (sensitive, typed confirmation) and one `Lock`. A missing or corrupted file must not crash Jarvis (start with an empty one and warn).
- Apps still open with `os.startfile` or `subprocess.Popen` using a list. Never `shell=True`. Never run anything not in the merged dict.

### 6B: Wake word "Hey Iris"
- Config in `config.py`: `WAKE_ENABLED = False`, `WAKE_WORD = "iris"`.
- When enabled: Jarvis idles listening only for the wake word; on detection it says a short acknowledgement ("Yes?"), listens ONCE for the command (timeout), processes it, then returns to idle. "Iris, open youtube" in one breath must work (after the wake word, start listening immediately).
- **Preferred method:** offline keyword spotting with the free `vosk` library and a small English model, using a restricted grammar containing only the wake word and an unknown-word token. Check the CURRENT Vosk documentation and Windows install steps first. Document the model download in README.md. If Vosk cannot work on Windows or is inaccurate, fall back to the existing online `SpeechRecognition` and check for the wake word in short chunks, label it clearly "online fallback" in README.md, and record the reason in HANDOFF.md.
- Wake listening must respect `MIC_SPEAKER`: never listen while speaking, and never keep the mic open while a task holds it.
- If the mic fails, fall back to typed input without crashing. Typed commands still work in every mode.
- Add a config setting for sensitivity or timeout, and a log line for every wake detection.
- State honestly in README.md: this is not a commercial wake-word engine, and false triggers or misses can happen.

### 6C: Approval-gated learned skills
- Command: `add a skill that <description>` (typed or spoken). The request text is the only thing sent to the AI plus a fixed template. Copied text and clipboard are NOT included unless the human explicitly selects them, and are treated as data.
- **Generation:** `ask_ai()` with a fixed template must return ONE Python file that defines exactly: `SKILL_NAME` (string), `KEYWORDS` (list of lowercase whole words), `RESOURCES` (list of known resource names from `iris/resources.py`; unknown names are rejected), and `run(command)` returning a string. Maximum 120 lines. Saved to `proposed_skills/<skill_name>.py` (git-ignored).
- **Static checker** (use `ast`, standard library only). REJECT the file if it has any of:
  - imports other than this allowlist: `datetime`, `time`, `math`, `random`, `re`, `json`, `statistics`, `platform`, `psutil`;
  - the names `exec`, `eval`, `compile`, `__import__`, `open`, `input`, `getattr`, `setattr`, `delattr`, `globals`, `locals`, `vars`, `breakpoint`;
  - any attribute starting with `__`;
  - any import or use of `os`, `sys`, `subprocess`, `socket`, `requests`, `shutil`, `pathlib`, `ctypes`, `importlib`, `threading`;
  - top-level code other than imports, the four required names, and function definitions; more than the required `run` signature; `while True` loops without a break;
  - a missing required name, or more than 120 lines.
- **Subprocess test:** run the skill in a separate Python process with a **5 second timeout**, a fixed test command, and no access to project modules. It must return a string. Be honest in README.md: this reduces risk but is **not a true sandbox on Windows**; the allowlist, the checker, and the human's approval are the protection.
- **Approval:** show the human the full code, `RESOURCES`, the checker result, and the test result. Require a **TYPED** yes (never voice). On "no", delete the proposal.
- **After approval:** move the file to `skills/learned/<skill_name>.py`, register it in `data/learned_skills.json` (with a Lock), load it with `importlib` from that exact path, and commit it locally with the existing git helper (NO push). Uses resource `LEARNED_SKILLS`.
- **Running:** a learned skill runs as a normal Iris task. It reserves exactly the resources it declares, goes through the normal permission prompts, and respects timeouts, pause, and cancel. It can only return text.
- **Undo:** `undo last skill` removes the last learned skill file and registry entry and commits that. `list skills` shows learned skills.
- **Protected files:** enforce the list in SPEC.md section 12 in code. Every write path is resolved (no `..`, no symlinks) and must be inside `data/`, `proposed_skills/`, or `skills/learned/`, or the write is refused and logged. Take a hash of the protected files at startup and check it after every approval.
- Iris **never** edits existing code. A request to "change" a learned skill creates a new proposal that replaces it only after approval. A request to change core code is refused with a message to use Codex and Antigravity.
- `.gitignore`: add `proposed_skills/`. `skills/learned/` IS committed (after approval).

## 2. BUILDER instructions (Codex only)
1. Confirm HANDOFF.md says `TURN: builder`, `STAGE: 6`, and the prerequisite in section 0 is true. If a `SUBSTEP:` line exists, continue after it. Otherwise STOP.
2. Build 6A, run all tests, commit `Stage 6A: teach apps and websites`. Then 6B, run all tests, commit `Stage 6B: wake word`. Then 6C, run all tests, commit `Stage 6C: learned skills`. Update `SUBSTEP` after each.
3. Tests mock the microphone, the AI, the Start Menu, subprocess, and git. Cover, at minimum:
   - 6A: adding and removing apps and websites; invalid names, URLs, and paths are rejected; a spoken yes does not save; corrupted `user_config.json` does not crash; built-in names cannot be overridden.
   - 6B: wake detection starts one listen; no listening while speaking; fallback to typed input; wake off by default.
   - 6C: the checker rejects each forbidden construct in the list above and accepts a good skill; a "no" or a spoken yes leaves no file in `skills/learned/`; path traversal is refused; protected-file hashes are unchanged after an approval; the 5-second timeout kills a slow skill; an unknown resource is rejected; undo removes the skill; a learned skill runs through Iris with its declared resources; copied text containing "ignore your rules" changes nothing; all earlier tests pass.
4. Update README.md and REVIEW.md with simple explanations and the honest limits in section 1.
5. Tag `stage-6`. Do NOT push.
6. Update HANDOFF.md: `TURN: reviewer`, `STAGE: 6`, with BUILDER NOTES, UNSURE ABOUT, and NEEDS HUMAN TEST (real Start Menu search, real mic and wake word, real approval flow, real AI-written skill).
7. STOP. Print a summary and the manual test steps.

## 3. REVIEWER instructions (Antigravity only)
1. Confirm HANDOFF.md says `TURN: reviewer` and `STAGE: 6`, and tag `stage-6` exists. Otherwise STOP.
2. Run `python -m unittest discover tests`.
3. Check, and fix with the smallest change (add a test for each bug fixed). **This stage lets AI-written code run, so be strict.**
   - The static checker really blocks every construct listed; try to bypass it (aliased imports, `from x import *`, nested functions, string tricks, `__class__` access, decorators, lambdas calling blocked names) and fix or report gaps.
   - A learned skill can never run without checker pass, subprocess test pass, AND a typed yes.
   - Writes are confined to `data/`, `proposed_skills/`, and `skills/learned/`; path tricks fail; protected-file hashes are checked.
   - Iris cannot change her own existing code, the permission system, `confirm.py`, or `SPEC.md`/`AGENTS.md`.
   - Learned skills can only return text, use declared known resources, and obey timeouts, pause, and cancel.
   - Copied text, clipboard text, news text, and AI replies cannot trigger approvals or add skills.
   - 6A: all file writes use the lock and typed confirmation; invalid input is rejected; no `shell=True`.
   - 6B: wake listening respects `MIC_SPEAKER`; the fallback and its honest label exist; typed input always works.
   - Earlier stages behave the same and all earlier tests pass; with Iris off nothing breaks.
4. No refactoring for style, no new features. Design issues go to HANDOFF.md under REVIEWER UNRESOLVED. If you find a way to bypass the checker that you cannot fully fix, say so clearly in HANDOFF.md.
5. Append findings to REVIEW.md. Commit: `Review stage 6: <summary>`. Tag `stage-6-reviewed`.
6. Update HANDOFF.md: `TURN: human` if good, or `TURN: builder` (ROUND +1) if the builder must fix something. STOP.

## 4. Done means
- "add app spotify" finds it, shows the path, and saves only after a typed yes; "open spotify" then works after a restart.
- "add website" and "remove app" work; bad input is refused.
- With `WAKE_ENABLED = True`, saying "Hey Iris, what's the time" works without touching the keyboard; Iris never hears herself.
- "add a skill that tells me the battery level" produces a proposal, shows the code and checks, and installs nothing until a typed yes.
- A proposal containing a blocked construct is rejected with a clear reason.
- An approved skill runs through Iris with permission prompts, and "undo last skill" removes it.
- Protected files are unchanged after every approval.
- All tests pass, including all earlier stages.

## 5. NEEDS HUMAN TEST (the human does these)
- Run the wake word in a quiet room and a noisy one; note false triggers and misses.
- Add a real app and a real website; restart Jarvis and open them.
- Ask for two harmless skills (battery level, a coin flip). **Read the code before typing yes.** Then try asking for a harmful one (read a file, delete a file) and confirm it is blocked.
- Run `git status` and check `data/`, `proposed_skills/`, and `.env` are not listed.
- Run `git push` after the review is finished.
