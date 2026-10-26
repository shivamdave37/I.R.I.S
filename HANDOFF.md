TURN: builder
STAGE: 7
ROUND: 0
SUBSTEP: 7A
BUILDER NOTES: Stage 6 review is complete (127 tests passed; tag stage-6-reviewed). The human confirmed the Stage 6A website add-and-restart check passed. Stage 7 setup is committed and pushed; the backup-location conflict is resolved: the fixed updater apply/rollback workflow alone may create, restore, and clean data/backups, while patch proposals must refuse that TIER 0 path. The human's Iris-enabled config setting is preserved. The full test suite passes with test-only USE_IRIS default isolation.
UNSURE ABOUT: Stage 7's TIER 0 launcher.py owns restarts and rollback; real Windows restart/health behavior needs a human test. Stage 6 manual checks for microphone/wake, learned-skill approvals, and earlier integrations remain pending. The requested Iris desktop interface is a separate feature after Stage 7.
REVIEWER FIXED: Stage 6 reviewer fixed runtime class creation through type(), added a test, verified Stage 6 safety boundaries, and tagged stage-6-reviewed. Full suite: 127 tests passed.
REVIEWER UNRESOLVED (needs builder or human): Stage 6 learned-skill subprocesses are not a true Windows sandbox; the human must read each candidate before approval. Stage 5 stop-all behavior still waits for a non-pausable step to finish.
NEEDS HUMAN TEST (mic, speakers, app paths, clipboard, GitHub login): Stage 7 manual checks are in STAGE_7.md section 5: launch via launcher.py, review proposals, exercise each choice, observe rollback, confirm protected targets are refused, and verify nothing auto-pushes. Stage 6 wake word/devices, learned skills, real app paths, and earlier AI/news/clipboard/GitHub checks remain pending except the website persistence check the human completed.
