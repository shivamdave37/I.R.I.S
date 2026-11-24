# 08 — Dependencies and the test suite

## Dependencies and external services

### Python standard library

The inspected root has no dependency manifest. Source imports standard-library modules: `datetime`, `json`, `logging`, `os`, `pathlib`, `re`, `shutil`, `subprocess`, `tempfile`, `urllib`, `ipaddress`, `unicodedata`, `ast`, `keyword`, and `dataclasses`. Tests use `unittest`, `unittest.mock`, `tempfile`, `io`, and `contextlib`. Python 3.10+ is documented in README.

If these imports are unavailable, the Python installation itself is incomplete. No extra package installation is required for these modules.

### Gemini API

Gemini is an external AI service. Iris sends HTTPS requests for chat, planning, proposal drafts, and Google Search grounding. It needs internet and `GEMINI_API_KEY`; selected model is in `config.py`. Its quota, account permissions, model availability, and service uptime are external conditions. The prior live research evidence was HTTP 429 / `RESOURCE_EXHAUSTED`; this is not proof of a source-code defect by itself.

### Ollama

Ollama is an external local service application, not a Python package imported by Iris. It must be installed/running separately, with the configured model available. Iris sends only to the configured loopback endpoint. This checkout's test suite mocks it; no live service result is established here.

### Tavily

Tavily is an external search API and optional research provider added in the current uncommitted changes. It requires an account/API key, internet access, and `IRIS_RESEARCH_PROVIDER=tavily`. Code does not install a library; standard-library HTTP is used. A mocked success response verifies Iris's parser, not Tavily availability, account allowance, or current search quality. Do not assume free-credit terms remain unchanged; consult Tavily's current documentation/account page.

### Operating system and browser

Opening applications uses Windows `os.startfile` when available and a fixed `subprocess.Popen(..., shell=False)` fallback. Website opening uses Python's standard `webbrowser` module and the user's default browser. App paths are machine-specific.

## Running tests

From the project root:

```powershell
python -m unittest discover -s tests
```

Verified during preparation of this guide: **69 tests ran and passed** (`OK`, 0.302 seconds). The output includes printed plan previews because tests exercise actual planner preview behavior. The suite did not contact a live AI/search provider or launch actual apps.

## What each test file covers

### `tests/test_main.py`

- `test_handler_error_does_not_end_the_loop_or_log_exception_text`: injects a handler exception, verifies the loop remains available for the next exit request, and checks logs contain only error type rather than private detail.

### `tests/test_router.py`

- `test_natural_notepad_request_uses_approved_skill`: natural phrasing reaches the fixed app action.
- `test_opening_requires_typed_yes`: opening is gated by exact typed approval.
- `test_unknown_chat_goes_directly_to_ai_without_planner`: ordinary unknown question goes to chat, not action planning.
- `test_help_lists_implemented_capabilities`: help path works and names available capabilities.
- `test_unknown_open_target_is_not_sent_to_ai`: unknown target is refused instead of model-invented.
- `test_note_is_saved_only_after_approval`: note side effect waits for permission.
- `test_multi_action_runs_supported_steps_in_order`: supported steps keep requested order.
- `test_denial_cancels_all_steps_before_side_effects`: denial prevents execution of every side effect in a multi-action request.
- `test_and_inside_note_is_preserved_as_note_text`: parser does not split note content at ordinary “and.”
- `test_failed_multi_action_step_does_not_hide_later_result`: later independent action can be reported after an earlier failure.
- `test_end_of_input_cancels_approval`: EOF does not count as approval.
- `test_ai_text_is_returned_as_text_and_never_executed`: AI response remains text, not an executable instruction.

### `tests/test_task_planner.py`

- `test_valid_ordered_plan_has_explicit_step_status`: validated steps carry IDs/order/status.
- `test_unregistered_skill_is_rejected`: model cannot invent a skill.
- `test_invalid_parameters_and_later_dependencies_are_rejected`: schemas and earlier-only dependencies are enforced.
- `test_unapproved_targets_are_rejected`: target must be configured.
- `test_note_parameter_limit_is_checked_before_plan_execution`: overlong text is rejected at validation.
- `test_comma_separated_known_actions_run_in_order`: deterministic multi-action parsing and order.
- `test_denial_prevents_every_step`: approval denial cancels whole plan before dispatch.
- `test_approved_delete_reaches_guarded_note_function`: the approved planner path passes its explicit approval guard.
- `test_failed_step_skips_dependent_but_runs_independent_step`: dependency policy is honored.
- `test_model_plan_with_unregistered_action_fails_closed`: AI-generated unknown action runs nothing.
- `test_research_and_note_are_not_silently_combined`: user must inspect research before saving chosen wording.
- `test_search_and_delete_selected_note`: selected note search/delete path.
- `test_invalid_delete_index_preserves_notes`: invalid number does not remove data.

### `tests/test_skills.py`

- `test_add_and_show_notes_round_trip`: note serialization/readback.
- `test_corrupt_note_shape_is_not_overwritten`: malformed JSON structure is preserved and reported.
- `test_redirected_note_path_fails_closed`: unsafe path redirection is refused.
- `test_configured_app_launch_uses_fixed_path_without_shell`: app starts from allowlisted path without shell interpretation.
- `test_website_launch_uses_configured_url`: website opens with configured URL.
- `test_unapproved_app_never_launches`: unknown app fails closed.

### `tests/test_ai.py`

- `test_gemini_question_uses_one_model_request`: chat uses one mocked provider call.
- `test_provider_failure_is_clear_and_not_kept_in_history`: error message and history cleanup.
- `test_unknown_provider_does_not_call_a_model`: invalid setting does not initiate a request.
- `test_gemini_maps_assistant_role_to_model_and_keeps_key_out_of_url`: request role mapping and key placement.
- `test_missing_gemini_key_is_clear_and_does_not_call_network`: no-key behavior without network.
- `test_configured_key_in_chat_is_not_sent_to_provider`: key-containing content is refused.
- `test_gemini_rate_limit_has_a_specific_message`: HTTP 429 becomes a quota/rate limit message.
- `test_ollama_refuses_non_loopback_service`: remote Ollama address is refused.
- `test_ollama_missing_service_has_a_clear_message`: unavailable local endpoint is handled.
- `test_successful_ai_reply_that_looks_like_error_is_still_chat`: valid user-visible text is not confused with a skill error.
- `test_provider_setting_is_loaded_before_provider_selection`: `.env` provider choice is read before selecting service.
- `test_http_request_has_a_finite_timeout`: request includes bounded timeout.

### `tests/test_research.py`

- `test_successful_grounded_response_separates_summary_claims_and_sources`: Gemini research summary, citation mapping, and links are formatted separately.
- `test_malformed_response_and_missing_sources_do_not_claim_research`: invalid structure/source absence withholds findings.
- `test_ollama_provider_reports_search_unavailable_without_network`: local chat provider does not pretend it can search.
- `test_tavily_returns_generated_answer_with_https_sources`: mock response formats answer and safe sources.
- `test_tavily_missing_key_fails_without_request`: missing credentials stop before network call.
- `test_tavily_without_https_sources_does_not_claim_research`: unsafe/missing sources block claims.
- `test_tavily_provider_errors_are_marked_as_failed_plan_steps`: provider failure propagates into task status.
- `test_missing_gemini_key_has_a_clear_message_without_network`: no-key behavior for research.
- `test_timeout_and_http_errors_are_reported_without_fake_sources`: network/status errors never fabricate findings.
- `test_http_429_gives_quota_guidance_without_exposing_provider_body`: quota message is safe and redacted.
- `test_research_prompt_treats_webpage_content_as_untrusted_data`: instruction boundary is in prompt.
- `test_invalid_research_query_is_rejected_before_provider`: bad length rejected before request.
- `test_provider_response_size_is_bounded`: oversized data rejected.
- `test_research_output_is_only_returned_as_data`: research result is returned as text/data and not executed.

### `tests/test_skill_development.py`

- `test_simple_pure_proposal_passes_static_checks`: small approved AST shape passes.
- `test_imports_process_access_and_invalid_metadata_are_rejected`: dangerous syntax and bad names fail validation.
- `test_invalid_python_is_not_validated_or_executed`: syntax error stays inert.
- `test_valid_draft_is_displayed_then_saved_as_inert_version`: display, approval, and inert version record.
- `test_denied_save_leaves_no_proposal_file`: declined consent does not persist.
- `test_failed_static_validation_does_not_save_generated_code`: invalid candidate is not stored.
- `test_manual_approval_is_recorded_but_never_activates_code`: approval event does not register/execute code.
- `test_withdrawal_records_rollback_without_erasing_history`: withdrawal records event while retaining proposal.
- `test_tampered_proposal_fails_revalidation`: changed stored source is rejected on read.

### `tests/test_phase5_integration.py`

- `test_terminal_workflow_uses_temp_notes_and_denies_side_effects`: integrates startup, help, note lifecycle, denial, search, and exit using temp storage and mocked app launch.
- `test_denied_open_and_note_plan_does_not_persist_unique_marker`: regression test proves denied multi-step open/note plan does not create the unique note; app launch is mocked.

## What 69 passing tests establish—and do not

They establish that these tested code paths behaved as expected with the test fixtures and mocks at the time the command ran. They do not establish that Gemini/Tavily currently accept the account, that quotas remain, that Ollama is installed, that the real microphone/speaker/browser/app path works, or that every possible input is correct. A mock is a controlled substitute, not a live provider.

## Recap questions

1. Why does the suite use temporary folders? To avoid altering real notes.
2. Why mock network calls? To make tests repeatable and avoid credits/network dependence.
3. What does a 69-test pass tell you? Covered cases pass, not universal correctness.
4. Which tests protect denied note writes? Router and phase-five integration tests.
5. Which service has not been live-verified by these tests? Gemini Search/Tavily/Ollama network behavior.
