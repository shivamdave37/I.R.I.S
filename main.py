"""Run the typed Mini Jarvis command loop."""

import logging
import os

import router


def setup_logging():
    """Prepare the log file when possible without blocking startup."""
    try:
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            filename=os.path.join("logs", "jarvis.log"),
            level=logging.INFO,
            format="%(asctime)s | %(message)s",
        )
    except Exception:
        # Jarvis should remain usable even when the log folder cannot be written.
        pass


def log_action(command, result):
    """Record a command and its result while keeping logging failures harmless."""
    try:
        logging.info("command=%r | result=%r", command, result)
    except Exception:
        # A logging problem must not interrupt the command loop.
        pass


def run():
    """Read typed commands and stop cleanly on exit or Ctrl+C."""
    setup_logging()
    print("Mini Jarvis is ready. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            command = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nJarvis: Goodbye!")
            log_action("<interrupted>", "stopped")
            break

        if not command.strip():
            continue

        reply = router.handle(command)
        print(f"Jarvis: {reply}")
        log_action(command, reply)
        if router.is_exit_command(command):
            break


def main():
    """Start Jarvis when this file is run directly."""
    run()


if __name__ == "__main__":
    main()
