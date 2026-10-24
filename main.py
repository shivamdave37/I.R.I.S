"""Run the typed Mini Jarvis command loop."""

import logging
import os
import sys
import time

import config
import router
import voice
from dotenv import load_dotenv
from skills import memory


def _is_admin_command(command):
    """Recognize only the explicit Iris control-channel commands."""
    words = command.lower().split()
    normalized = command.lower().strip()
    return (normalized in {"status", "grants", "stop all"}
            or any(normalized.startswith(action + " ") for action in ("pause", "resume", "cancel", "revoke", "priority", "switch to")))


def _is_rules_change(command):
    """Refuse runtime requests that try to alter fixed config or safety rules."""
    normalized = router.normalize(command)
    return any(term in normalized for term in ("hard limit", "safety rule", "approved apps", "allowed resources", "configpy"))


def read_console_line(prompt, yield_if=None):
    """Read one keyboard line without starting a second stdin reader thread."""
    try:
        import msvcrt
    except ImportError:
        return input(prompt)
    print(prompt, end="", flush=True)
    line = ""
    while True:
        if not line and yield_if and yield_if():
            print()
            return None
        if msvcrt.kbhit():
            character = msvcrt.getwch()
            if character in {"\r", "\n"}:
                print()
                return line
            if character == "\003":
                raise KeyboardInterrupt
            if character == "\b":
                if line:
                    line = line[:-1]
                    print("\b \b", end="", flush=True)
            elif character in {"\x00", "\xe0"}:
                # Consume the second byte of a Windows function-key sequence.
                msvcrt.getwch()
            else:
                line += character
                print(character, end="", flush=True)
        else:
            time.sleep(0.02)


def _keyboard_input_ready():
    """Check whether the Windows console has typed input waiting."""
    try:
        import msvcrt
        return msvcrt.kbhit()
    except ImportError:
        # Non-Windows runs keep typed input available without a polling API.
        return True


def _iris_result(task, speak_replies):
    """Show completed task replies and speak them only in voice modes."""
    message = task.result if task.state.value == "DONE" else f"Task {task.id} failed: {task.error}"
    print(f"Jarvis: {message}")
    normalized = router.normalize(task.command_text)
    if speak_replies and task.result and not normalized.startswith(("explain this code", "fix this code")):
        # Explain already speaks its own short summary; fixes must stay display-only.
        voice.speak(task.result)
        voice.wait_until_done()


def run_iris(mode):
    """Run Jarvis through Iris with a separate control and permission input path."""
    from iris.iris import Iris
    from iris.console import input_broker
    from iris.permissions import PermissionManager
    from iris import wake
    from skills.learned_skills import initialize_protected_hashes

    initialize_protected_hashes()
    permission_manager = PermissionManager()
    def show_result(task):
        """Forward completed task text to the console and queued speaker."""
        _iris_result(task, mode in {"voice", "both"})

    supervisor = Iris(permission_callback=permission_manager.request, result_callback=show_result)
    supervisor.permission_manager = permission_manager
    input_broker.enabled = True
    wake_listener = wake.create_listener() if getattr(config, "WAKE_ENABLED", False) and mode != "typed" else None
    print("Iris supervision is enabled. Type or say 'status' to inspect tasks.")
    deferred_command = None
    deferred_is_typed = False

    def prompt_is_pending():
        """Check both serialized sources before waiting for another command."""
        return bool(supervisor.pending_permission_prompt() or input_broker.pending())

    try:
        while True:
            pending_console = input_broker.pending()
            if pending_console:
                request_id, prompt = pending_console
                prompt_kind = input_broker.kind(request_id)
                def console_prompt_expired():
                    """Check whether the worker stopped waiting for this input."""
                    return input_broker.pending() != pending_console
                try:
                    answer = read_console_line(prompt, console_prompt_expired)
                except (EOFError, KeyboardInterrupt):
                    input_broker.answer(request_id, None, typed=True)
                    break
                if answer is None:
                    continue
                if _is_admin_command(answer):
                    print(supervisor.handle_admin(answer))
                elif prompt_kind == "permission":
                    permission = supervisor.pending_permission_prompt()
                    if permission is None or not supervisor.answer_permission(permission[0], answer, typed=True):
                        print("That answer did not match the permission prompt. Try again or type deny for each item.")
                elif not input_broker.answer(request_id, answer, typed=True):
                    print("That prompt is no longer active.")
                continue

            try:
                if deferred_command is not None:
                    command = deferred_command
                    deferred_command = None
                    typed_command = deferred_is_typed
                    deferred_is_typed = False
                elif mode == "typed":
                    command = read_console_line("You: ", prompt_is_pending)
                    typed_command = True
                elif wake_listener is not None:
                    if _keyboard_input_ready():
                        command = read_console_line("You: ", prompt_is_pending)
                        typed_command = True
                    else:
                        wake_status, command = wake.listen_chunk(supervisor.resources, wake_listener)
                        if wake_status in {"idle", "busy"}:
                            continue
                        if wake_status == "wake":
                            voice.speak("Yes?")
                            voice.wait_until_done()
                            if not command:
                                wake_status, command = wake.listen_for_command(supervisor.resources, wake_listener)
                            if wake_status != "command" and not command:
                                print("I couldn't hear a command. Please type it.")
                                command = read_console_line("You: ", prompt_is_pending)
                                typed_command = True
                            else:
                                typed_command = False
                        else:
                            print("Wake listening failed. Please type your command.")
                            command = read_console_line("You: ", prompt_is_pending)
                            typed_command = True
                else:
                    print("Listening...")
                    listen_status, command = wake.listen_regular_command(supervisor.resources)
                    typed_command = False
                    if listen_status == "busy":
                        print("The microphone is in use. Please type your command.")
                        command = read_console_line("You: ", prompt_is_pending)
                        typed_command = True
                    elif listen_status == "error" and mode == "both":
                        print("I couldn't hear you. Please type your command.")
                        command = read_console_line("You: ", prompt_is_pending)
                        typed_command = True
                    elif listen_status == "error":
                        message = "I couldn't hear you. Please try again."
                        print(f"Jarvis: {message}")
                        voice.speak(message)
                        command = None
            except (EOFError, KeyboardInterrupt):
                print("\nJarvis: Goodbye!")
                break
            # A voice phrase is never treated as permission input.
            pending = supervisor.pending_permission_prompt()
            if pending and command and not _is_admin_command(command):
                if typed_command and supervisor.answer_permission(pending[0], command, typed=True):
                    continue
                if command.strip().lower() not in {"yes", "y", "no", "n", "once", "session", "always", "deny"}:
                    deferred_command = command
                    deferred_is_typed = typed_command
                continue
            if command is None or not command.strip():
                continue
            if router.is_exit_command(command):
                print("Jarvis: Goodbye!")
                break
            normalized = router.normalize(command)
            if _is_admin_command(normalized):
                print(supervisor.handle_admin(normalized))
                continue
            # Runtime requests cannot alter config.py or the safety limits.
            if _is_rules_change(normalized):
                print("Jarvis: Rules cannot be changed at runtime. Edit config.py and restart.")
                continue
            if normalized.startswith("queue:"):
                commands = [item.strip() for item in command.split(":", 1)[1].split(";") if item.strip()]
                for queued_command in commands:
                    memory.record_command(queued_command)
                    task = supervisor.submit(queued_command)
                    print(f"Queued task {task.id}: {task.name}")
                continue
            memory.record_command(command)
            task = supervisor.submit(command)
            print(f"Queued task {task.id}: {task.name}")
    finally:
        supervisor.stop()
        input_broker.enabled = False
        if mode in {"voice", "both"}:
            voice.wait_until_done()
        voice.shutdown()


def setup_logging():
    """Prepare the log file when possible without blocking startup."""
    try:
        os.makedirs("logs", exist_ok=True)
        # Use utf-8 encoding so logging non-ASCII characters on Windows does not raise errors.
        logging.basicConfig(
            filename=os.path.join("logs", "jarvis.log"),
            level=logging.INFO,
            format="%(asctime)s | %(message)s",
            encoding="utf-8",
        )
    except Exception:
        # Jarvis should remain usable even when the log folder cannot be written.
        pass


def log_action(command, result):
    """Record a command and its result while keeping logging failures harmless."""
    try:
        # Redact the configured key before writing user input or errors to disk.
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key.strip():
            api_key = api_key.strip()
            command = str(command).replace(api_key, "[REDACTED]")
            result = str(result).replace(api_key, "[REDACTED]")
        # Log command and outcome for audit and debugging purposes.
        logging.info("command=%r | result=%r", command, result)
    except Exception:
        # A logging problem must not interrupt the command loop.
        pass


def read_command(mode):
    """Read from the microphone first when the selected mode uses voice."""
    if mode == "typed":
        return input("You: ")

    # Wait so Jarvis never listens to its own speech through the microphone.
    voice.wait_until_done()
    print("Listening...")
    command = voice.listen()
    if command is not None and command.strip():
        return command
    if mode == "both":
        print("I couldn't hear you. Please type your command.")
        return input("You: ")

    # Voice-only mode retries after a short spoken prompt instead of crashing.
    message = "I couldn't hear you. Please try again."
    print(f"Jarvis: {message}")
    voice.speak(message)
    return None


def run():
    """Read commands in the configured mode and stop cleanly on exit or Ctrl+C."""
    setup_logging()
    router.user_config.initialize()
    # Normalize configured mode to lowercase and strip whitespace.
    configured_mode = getattr(config, "MODE", "both")
    mode = configured_mode.strip().lower() if isinstance(configured_mode, str) else "both"
    if mode not in {"voice", "typed", "both"}:
        print(f"Unknown MODE '{configured_mode}'. Using typed input.")
        mode = "typed"
    if getattr(config, "USE_IRIS", False):
        return run_iris(mode)
    speak_replies = mode in {"voice", "both"}
    print("Mini Jarvis is ready. Type 'exit' or 'quit' to stop.")
    try:
        while True:
            try:
                # The mode helper keeps voice and typed input behavior in one place.
                command = read_command(mode)
            except (EOFError, KeyboardInterrupt):
                # Clean exit on Ctrl+C or end-of-file stream without crashing.
                print("\nJarvis: Goodbye!")
                if speak_replies:
                    voice.speak("Goodbye!")
                log_action("<interrupted>", "stopped")
                break

            if command is None or not command.strip():
                continue

            # Keep the most recent commands without letting memory errors stop the loop.
            memory.record_command(command)
            reply = router.handle(command)
            print(f"Jarvis: {reply}")
            normalized_command = router.normalize(command)
            # A suggested fix is shown only, so do not copy the AI code into persistent logs.
            logged_reply = "AI-suggested fix displayed only; not saved." if normalized_command.startswith("fix this code") else reply
            log_action(command, logged_reply)
            # Code help already speaks a short explanation summary; fixes stay on screen only.
            should_speak_reply = not normalized_command.startswith("fix this code")
            if normalized_command.startswith("explain this code"):
                should_speak_reply = False
            if speak_replies and should_speak_reply:
                voice.speak(reply)
            # Stop loop after the goodbye reply has been queued.
            if router.is_exit_command(command):
                break
    finally:
        try:
            voice.wait_until_done()
        finally:
            voice.shutdown()



def main():
    """Start Jarvis when this file is run directly."""
    # Entry point for running the assistant from terminal.
    run()


if __name__ == "__main__":
    main()

