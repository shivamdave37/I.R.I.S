# AGENTS.md: rules for every coding agent in this repo

This file is read by BOTH OpenAI Codex and Google Antigravity. The human owner is the **admin**. SPEC.md is the source of truth for what to build. HANDOFF.md says whose turn it is.

## 1. Roles
- **OpenAI Codex = BUILDER.** Builds one stage at a time from SPEC.md.
- **Google Antigravity = REVIEWER.** Checks, tests, and fixes the stage the builder just finished. It never adds features or starts the next stage.
- If you are not sure which agent you are, or the human's prompt says otherwise, STOP and ask.

## 2. One agent at a time
- Before doing anything, read SPEC.md, then HANDOFF.md.
- If HANDOFF.md says it is not your turn, stop and tell the human. Do not work.
- Exception: Stage 6 may relax hard limit 6 only as written in SPEC.md section 12.
- Never edit files at the same time as the other agent.

## 3. Rules for BOTH agents
1. Never edit SPEC.md or AGENTS.md. Only the human does.
2. Never change or remove the hard limits in SPEC.md section 5, or the AI safety rules in section 10.8.
3. Work only inside this project folder.
4. Never create, print, log, or commit API keys or the contents of .env. Never commit .env, venv/, data/, logs/.
5. Never use shell=True. Never build a shell command from user text, copied text, or AI output. Use fixed commands only.
6. Never run code that an AI model wrote.
7. Do not install anything outside the project's virtual environment.
8. Ask the human before: deleting files, moving files, adding a library not named in SPEC.md, or anything outside the folder.
9. Do not force-push or rewrite git history.
10. Keep the code simple and beginner-readable: one-line docstring on every function, comments that explain WHY, no clever tricks, no classes or threading before the stage that needs them.
11. If something in SPEC.md is unclear, impossible on Windows, or contradicts itself, STOP and ask the human. Do not guess.
12. You cannot test the microphone, speakers, screen, or the human's app paths. List those under "NEEDS HUMAN TEST" instead of claiming they work.

## 4. BUILDER procedure (Codex)
1. Read the stage prompt from the human. Build ONLY that stage.
2. Write unit tests (standard `unittest`) for every "Done means" item of the stage that can be tested without hardware. Mock anything that opens apps, browsers, the mic, the network, or git.
3. Run `python -m unittest discover tests`. Fix every failure.
4. Update README.md and REVIEW.md (see section 6).
5. Commit with the message "Stage N: <short summary>" and create the git tag `stage-N`.
6. Update HANDOFF.md: `TURN: reviewer`, add your notes and your "unsure about" list.
7. STOP. Print a short summary and the manual test steps for the human.

## 5. REVIEWER procedure (Antigravity)
1. Read SPEC.md, REVIEW.md, and HANDOFF.md. Review ONLY the current stage.
2. Run `python -m unittest discover tests`.
3. Check every "Done means" item of the stage, the hard limits (section 5), and the AI safety rules (section 10.8) against the real code. Also look for: wrong imports, mismatched names, crashes on empty input, unhandled exceptions, secrets in code or git history, files outside the allowed folders, and code that is too complex for a beginner.
4. Fix bugs with the SMALLEST change that works. Add a test for each bug you fix. Do not refactor for style. Do not add features.
5. If a fix needs a design change, or you disagree with the spec, do not fix it. List it in HANDOFF.md for the human.
6. Commit with the message "Review stage N: <short summary>" and create the git tag `stage-N-reviewed`.
7. Update HANDOFF.md using the template in section 7, then STOP.

## 6. REVIEW.md must contain (builder updates it, reviewer appends)
- Current folder structure
- What each file does, in simple words
- How to run and test the current stage
- Known problems or things the builder was unsure about
- Reviewer findings and what was fixed

## 7. HANDOFF.md template
```
TURN: builder | reviewer | human
STAGE: N
ROUND: 0 | 1 | 2
BUILDER NOTES: ...
UNSURE ABOUT: ...
REVIEWER FIXED: ...
REVIEWER UNRESOLVED (needs builder or human): ...
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): ...
```
Set `TURN: human` when the stage is finished or a limit is hit.

## 8. Round limit
For each stage there are at most **2 rounds** of builder then reviewer. If a problem is still unresolved after round 2, set `TURN: human` and explain it clearly. Do not loop.
