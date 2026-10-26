"""Run Iris's simple typed terminal assistant."""

import logging

import config
import router


def setup_logging():
    """Create a local log that records outcomes without saving chat contents."""
    try:
        config.LOG_FOLDER.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=config.LOG_FOLDER / "iris.log",
            level=logging.INFO,
            format="%(asctime)s | %(message)s",
            encoding="utf-8",
        )
    except OSError:
        logging.basicConfig(level=logging.CRITICAL)


def run():
    """Keep reading commands until the user exits or input ends."""
    setup_logging()
    print("Iris is ready. Type 'help' to see supported commands; 'exit' to stop.")
    while True:
        try:
            command = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nIris: Goodbye!")
            break
        try:
            reply = router.handle(command)
        except KeyboardInterrupt:
            print("\nIris: Goodbye!")
            break
        except Exception as error:
            # Keep the assistant available and avoid logging user text or provider details.
            logging.error("request failed; error_type=%s", type(error).__name__)
            reply = f"I hit an internal error ({type(error).__name__}). Iris is still running."
        print(f"Iris: {reply}")
        # Store only a short event label, never chat text or secrets.
        logging.info("request handled; reply_type=%s", "goodbye" if reply == "Goodbye!" else "response")
        if router.normalize(command).rstrip(".!?") in {"exit", "quit", "goodbye"}:
            break


if __name__ == "__main__":
    run()
