TURN: builder
STAGE: 6
ROUND: 0
SUBSTEP: 6A
BUILDER NOTES: Stage 6A complete: approved apps/websites can be added, listed, removed, and opened from the merged built-in/user lists. Setup commit 262d478 and its merge are pushed. Stage 6A suite: 96 tests passed.
UNSURE ABOUT: Start Menu shortcut discovery and real Windows app paths need a human session. Wake-word and learned-skill substeps remain to be built.
REVIEWER FIXED: Stage 5 review fixed _audit(None, event) silently dropping admin-only log entries; admin events now log with task_id='admin'. Added test_admin_audit_logged_without_task. Stage 5 reviewed suite: 83 tests passed. Tag: stage-5-reviewed.
REVIEWER UNRESOLVED (needs builder or human): Stage 5 SPEC 10.13 says stop all frees every resource within a few seconds, while 10.5 requires waiting for non-pausable file/Git steps. Current behavior waits two seconds, reports a still-running step, and keeps its resource locked until that worker exits. This remains documented for the human.
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): For Stage 6A, enable USE_IRIS, add a real app and website, inspect each target, approve with typed yes, restart, list, open, and remove an entry. Test Start Menu matches and a typed full path. Earlier mic/speaker, AI providers/RSS, clipboard, GitHub login, permission flow, and stop-all checks also remain manual.
