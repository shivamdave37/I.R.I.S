"""Run the typed Mini Jarvis command loop."""

import logging
import os

import config
import router
import voice
from dotenv import load_dotenv


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

            reply = router.handle(command)
            print(f"Jarvis: {reply}")
            log_action(command, reply)
            if speak_replies:
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

