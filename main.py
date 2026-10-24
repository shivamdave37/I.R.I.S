"""Run the typed Mini Jarvis command loop."""

import logging
import os

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

    permission_manager = PermissionManager()
    def show_result(task):
        """Forward completed task text to the console and queued speaker."""
        _iris_result(task, mode in {"voice", "both"})

    supervisor = Iris(permission_callback=permission_manager.request, result_callback=show_result)
    supervisor.permission_manager = permission_manager
    input_broker.enabled = True
    print("Iris supervision is enabled. Type or say 'status' to inspect tasks.")
    try:
        while True:
            pending_console = input_broker.pending()
            if pending_console:
                request_id, prompt = pending_console
                try:
                    answer = input(prompt)
                except (EOFError, KeyboardInterrupt):
                    input_broker.answer(request_id, None, typed=True)
                    break
                if _is_admin_command(answer):
                    print(supervisor.handle_admin(answer))
                elif not input_broker.answer(request_id, answer, typed=True):
                    print("That prompt is no longer active.")
                continue
            pending = supervisor.pending_permission_prompt()
            if pending:
                task_id, _ = pending
                try:
                    # Permission answers are typed so spoken voices cannot approve sensitive work.
                    answer = input(f"Permission choices for task {task_id}: ")
                except (EOFError, KeyboardInterrupt):
                    supervisor.answer_permission(task_id, "deny", typed=True)
                    break
                if _is_admin_command(answer):
                    print(supervisor.handle_admin(answer))
                elif not supervisor.answer_permission(task_id, answer, typed=True):
                    print("That answer did not match the permission prompt. Try again or type deny for each item.")
                continue

            try:
                command = read_command(mode)
            except (EOFError, KeyboardInterrupt):
                print("\nJarvis: Goodbye!")
                break
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

