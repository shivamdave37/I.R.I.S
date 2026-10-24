TURN: builder
STAGE: 6
ROUND: 0
SUBSTEP: 6B
BUILDER NOTES: Stage 6A and 6B complete. Stage 6A commit: 6181b25. Stage 6B uses optional offline Vosk wake detection, same-phrase command recovery, an online fallback, keyboard fallback, and MIC_SPEAKER reservations for each bounded capture. Setup commit 262d478 and its merge are pushed. Full suite: 105 tests passed.
UNSURE ABOUT: Start Menu shortcut discovery and real app paths need a human session. The Vosk library is installed, but its model was not downloaded; real microphone, speaker, wake accuracy, and noisy-room behavior need a human session. Learned-skill substep 6C remains.
REVIEWER FIXED: Stage 5 review fixed _audit(None, event) silently dropping admin-only log entries; admin events now log with task_id='admin'. Added test_admin_audit_logged_without_task. Stage 5 reviewed suite: 83 tests passed. Tag: stage-5-reviewed.
REVIEWER UNRESOLVED (needs builder or human): Stage 5 SPEC 10.13 says stop all frees every resource within a few seconds, while 10.5 requires waiting for non-pausable file/Git steps. Current behavior waits two seconds, reports a still-running step, and keeps its resource locked until that worker exits. This remains documented for the human.
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): For Stage 6A, enable USE_IRIS, add a real app and website, inspect each target, approve with typed yes, restart, list, open, and remove an entry. For 6B, install/extract the documented model, enable WAKE_ENABLED, test “Hey Iris” in quiet and noisy rooms, type commands while idle, and confirm wake capture waits while a task owns MIC_SPEAKER. Earlier mic/speaker, AI providers/RSS, clipboard, GitHub login, permission flow, and stop-all checks also remain manual.
