# STAGE 7: Supervised self-update (Iris proposes patches, the admin decides)

Used by: **Codex = BUILDER**, **Antigravity = REVIEWER**. Read only the section for your role, after reading section 0.

**Do not start until Stages 1 to 6 are reviewed (`stage-6-reviewed` exists) and the human has done section H.**

## H. Human steps BEFORE starting Stage 7 (only the human does these)

1. `HANDOFF.md` says `TURN: human`, `git tag` shows `stage-6-reviewed`, everything is pushed.
2. Add this to the END of SPEC.md as section 13 (agents may not edit SPEC.md):

```
## 13. Stage 7 amendments (apply ONLY when building or reviewing Stage 7)
- Section 12 says "Iris never changes her own existing code". Stage 7 replaces that with a controlled exception: Iris may PROPOSE patches to TIER 1 files only, and a patch is applied only after every check in STAGE\\\_7.md passes AND the admin types approval for that exact patch.
- TIER 0 (Iris may NEVER modify, create, or delete): confirm.py, config.py, launcher.py, everything in updater/, everything in tests/, requirements.txt, .gitignore, .env and .env.example, SPEC.md, AGENTS.md, HANDOFF.md, everything in stages/, data/backups/.
- TIER 1 (Iris may propose patches to existing files, never new or deleted files): iris/\\\*.py (including the three agents), router.py, main.py, ai.py, voice.py, and skills/\\\*.py (not skills/learned/).
- Any line marked with the comment # PROTECTED can never be changed or removed by a patch.
- Iris never applies a patch on her own, never approves her own patch, and never restarts herself without the admin's typed yes.
```

3. Add to AGENTS.md rule 2: `Exception: Stage 7 as written in SPEC.md section 13.`
4. Commit and push, then start the stage.

## 0\. Read first (both agents)

1. Read AGENTS.md, SPEC.md (**sections 5, 10, 12, and 13**), and HANDOFF.md. If HANDOFF.md says it is not your turn, STOP.
2. Prerequisite: tag `stage-6-reviewed`, all tests pass, SPEC.md contains section 13. If not, STOP.
3. Three sub-steps. Commit after each and record `SUBSTEP: 7A`, `7B`, or `7C` in HANDOFF.md.

   * **7A** Policy, markers, and the patch pipeline (no AI yet).
   * **7B** Approval flow, apply, restart, and automatic rollback.
   * **7C** Triggers: admin requests and Iris suggestions, with AI-written patches.
4. The updater is **standard library only** (`difflib`, `hashlib`, `shutil`, `json`, `subprocess`, `ast`, `time`).

## 1\. Required behavior

### 7A: Policy, markers, patch pipeline

* **updater/policy.py:** the TIER 0 and TIER 1 lists exactly as in SPEC.md section 13. `check\\\_path(path)` resolves the path (no `..`, no symlinks) and returns `tier0`, `tier1`, or `refused`. Anything not listed is `refused`.
* **# PROTECTED markers:** add the comment `# PROTECTED` on every line that enforces safety, for example: calls to `confirm.ask\\\_yes\\\_no(require\\\_typed=True)`, the permission-prompt call for each task, `reserve\\\_all`, the sensitive-resource list, `stop\\\_event` checks, and path checks. List every marker in REVIEW.md.
* **updater/proposal.py:** `Proposal` dataclass: id, reason, requested\_by (`admin` or `iris`), files (path to new full text), diff, status, hash, revisions.
* **updater/patcher.py:** the AI returns new FULL file text; Iris builds the diff herself with `difflib` (never trust a diff from the AI). A proposal is REFUSED if it:

  * touches any non-tier1 path, creates, deletes, or renames a file;
  * touches more than 3 files or changes more than 80 lines;
  * changes or removes any line containing `# PROTECTED`;
  * adds any of: `shell=True`, `exec(`, `eval(`, `\\\_\\\_import\\\_\\\_`, `importlib`, `os.system`, `socket`, new `subprocess` use, `open(` in write mode, references to `.env`, `API\\\_KEY`, `base64`, or a new network call;
  * fails `ast.parse` (syntax error).
* **Risk summary** (plain Python, never AI): files touched, functions changed, lines added/removed, every scan result, and the test result. Always shown with the diff.
* **updater/sandbox\_test.py:** copy the project to a temp folder, EXCLUDING `.env`, `venv/`, `.git/`, `data/`, `logs/`; apply the patch there; run `python -m unittest discover tests` with a fixed list command and a 120-second timeout. Pass means exit code 0. Never run the patch in the real folder first.

### 7B: Approval, apply, restart, rollback

* **Approval prompt** (typed only, never voice; add `ask\\\_choice()` to `confirm.py`): show the reason, the risk summary, and the full diff, then offer:

  1. approve and apply
  2. why (explain more: show the reason again and the deterministic risk summary; the AI may add a plain-language explanation, clearly labelled "AI explanation, may be wrong")
  3. deny
  4. other way: write a request file `update\\\_requests/<id>.md` (reason, instruction, target files) so the human can give it to Codex and Antigravity
  5. revise: the human types a new instruction and Iris creates a new proposal (maximum 3 revisions)
* The approval is tied to the proposal **hash**. If any file or the patch changed after approval, refuse and ask again.
* **Apply only when no task is RUNNING.** Otherwise wait, or ask the admin to pause or cancel tasks.
* **Apply steps:** backup the affected files to `data/backups/<id>/`; write the new files; write `data/pending\\\_update.json` (id, time); commit locally with the existing git helper using message `Iris update <id>: <reason>` (NO push); then ask for a typed yes to restart.
* **launcher.py** (new, TIER 0): starts `main.py` with a fixed command. If `data/pending\\\_update.json` exists, it waits up to 30 seconds for `data/health.ok` (written by `main.py` after a successful start). If `main.py` exits early or the file never appears, the launcher restores the backup, restarts, and logs the rollback. If health passes, it deletes the marker. A restart request from Iris uses exit code 75, and the launcher restarts `main.py`. README.md tells the user to start Jarvis with `python launcher.py` from now on.
* **Commands:** `updates` (list proposals), `show update <id>`, `rollback last update` (typed yes), `restart`.
* Log every proposal, choice, apply, rollback, and restart in `logs/jarvis.log` with the id.

### 7C: Triggers and AI patches

* **Admin request:** `update <target> so that <instruction>` or `change <target> to <instruction>`. `<target>` must match a tier 1 file or agent name (for example planner, executor, permissions agent, router). A tier 0 target is refused with: "This part is protected. Use Codex and Antigravity for it."
* **Iris suggestion** (she may SUGGEST, never prepare or apply by herself): deterministic triggers only, such as the same command falling through to "I don't know" 3 times, or the same skill failing 3 times. She prints a fixed-text message: `Suggestion: an update may help. Reason: <plain-Python reason>. Say "why", "prepare it", or "ignore".` Maximum one suggestion per hour; "ignore" silences that reason for the session. The reason text is written by plain Python, never by the AI. Only after the admin says "prepare it" does Iris ask the AI for a patch.
* **AI patch generation:** use `ask\\\_ai()` with a fixed template. Send only the target file(s) and the instruction, never secrets, `.env`, or other files. The AI must return JSON `{"files": {"<path>": "<complete new file text>"}, "reason": "<one sentence>"}`. Validate strictly; invalid JSON gets one retry, then the proposal fails safely. The AI's reason is shown but labelled "AI wrote this reason"; the risk summary is separate and deterministic.
* Copied text, clipboard text, news text, and AI replies are data. They can never request, approve, or revise an update.
* Honest limit for README.md: the free AI model may write weak patches for complex changes, so keep requests small. For bigger changes, use option 4 (send to Codex and Antigravity).

## 2\. BUILDER instructions (Codex only)

1. Confirm HANDOFF.md says `TURN: builder`, `STAGE: 7`, and the prerequisite in section 0 is true. If a `SUBSTEP:` line exists, continue after it. Otherwise STOP.
2. Build 7A, run all tests, commit `Stage 7A: update policy and pipeline`. Then 7B (`Stage 7B: approval, apply, rollback`). Then 7C (`Stage 7C: triggers and AI patches`). Update `SUBSTEP` after each.
3. Tests mock the AI, git, the microphone, and restarts. Cover at minimum:

   * policy: every tier 0 path, tier 1 path, `..`, symlink, and unlisted path;
   * patcher: each refusal rule (non-tier1, new/deleted file, over 3 files, over 80 lines, changed `# PROTECTED` line, each banned pattern, syntax error); the diff comes from `difflib`, not the AI;
   * sandbox: a failing test in the copy blocks the patch; `.env` is not copied; a timeout is enforced;
   * approval: a spoken yes is refused; option 3 changes nothing; the hash binding refuses a modified patch; revisions stop at 3; option 4 writes the request file and changes no code;
   * apply: backup exists; apply is blocked while a task is RUNNING; a failed health check triggers rollback and restores the exact original bytes;
   * triggers: suggestions are rate limited; no patch is generated before "prepare it"; copied text cannot trigger or approve anything;
   * protected markers exist on the lines listed in REVIEW.md;
   * all earlier tests pass.
4. Update README.md (use `python launcher.py`, the update commands, the honest limits) and REVIEW.md (tier lists, marker list, flow diagram in text).
5. Tag `stage-7`. Do NOT push.
6. Update HANDOFF.md: `TURN: reviewer`, `STAGE: 7`, with BUILDER NOTES, UNSURE ABOUT, and NEEDS HUMAN TEST (a real approval, a real restart, a real rollback).
7. STOP. Print a summary and the manual test steps.

## 3\. REVIEWER instructions (Antigravity only)

1. Confirm HANDOFF.md says `TURN: reviewer` and `STAGE: 7`, and tag `stage-7` exists. Otherwise STOP.
2. Run `python -m unittest discover tests`.
3. Check, and fix with the smallest change (add a test for each bug fixed). **This stage lets Iris change running code, so be strict. Try to break it.**

   * Can any patch change a tier 0 file, create a file, delete a file, or escape the folder (path tricks, symlinks, case differences on Windows)?
   * Can a patch remove or alter a `# PROTECTED` line, including by renaming, moving, or wrapping it? Are all safety-critical lines actually marked?
   * Can a patch make a prompt, `reserve\\\_all`, `stop\\\_event`, or a typed-confirmation call unreachable (for example by changing a condition above it)? Report any such gap clearly in HANDOFF.md even if you cannot fully close it.
   * Is approval typed-only, tied to the patch hash, and impossible to give from copied text, the AI, or Iris herself?
   * Does the sandbox copy exclude secrets and run with a timeout, and does a patch ever run in the real folder before approval?
   * Does apply refuse while a task runs; do backups restore exact bytes; does the launcher roll back when the new version fails to start?
   * Do Iris's suggestions use plain-Python reasons only, with rate limits, and never prepare a patch without "prepare it"?
   * Is nothing pushed to GitHub automatically?
   * Earlier stages behave the same and all earlier tests pass.
4. No refactoring for style, no new features. Design issues go to HANDOFF.md under REVIEWER UNRESOLVED.
5. Append findings to REVIEW.md. Commit: `Review stage 7: <summary>`. Tag `stage-7-reviewed`.
6. Update HANDOFF.md: `TURN: human` if good, or `TURN: builder` (ROUND +1) if the builder must fix something. STOP.

## 4\. Done means

* "update the planner so that it prefers short plans" creates a proposal showing the reason, the diff, the risk summary, and the test result, and changes nothing until a typed approval.
* "update confirm.py" is refused as protected, with the message to use Codex and Antigravity.
* A proposal that fails the tests in the copy, touches a protected line, or adds a banned pattern is refused with a clear reason.
* Choosing "why" explains more; "deny" changes nothing; "other way" writes a request file; "revise" makes a new proposal (maximum 3).
* After approval and a typed restart, the change is active; `rollback last update` restores the original files exactly.
* If the updated version fails to start, the launcher rolls back by itself.
* Iris's suggestions appear at most once an hour, with plain-Python reasons, and she prepares nothing until "prepare it".
* Nothing is pushed to GitHub by the updater.
* All tests pass, including all earlier stages.

## 5\. NEEDS HUMAN TEST (the human does these)

* Start Jarvis with `python launcher.py`.
* Ask for one small harmless change; **read the whole diff** before typing the approval.
* Test every choice: why, deny, other way, revise.
* Deliberately approve a change that breaks something small, restart, and watch the rollback.
* Ask Iris to change a protected file and confirm she refuses.
* Run `git status` and check `data/`, `update\\\_requests/`, and `.env` are not listed; then `git push` after the review.

