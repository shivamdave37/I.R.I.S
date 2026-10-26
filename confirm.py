"""Read explicit confirmations from the keyboard or voice input."""

import voice


def ask_choice(question, choices):
    """Return one exact typed choice from a short fixed list."""
    print(question)
    try:
        from iris.console import request_input
        answer = request_input("Choice: ")
    except (EOFError, KeyboardInterrupt):
        return None
    if answer is None:
        return None
    answer = str(answer).strip().lower()
    return answer if answer in choices else None


def ask_yes_no(question, require_typed=False):
    """Return True only for an explicit yes answer from an allowed input source."""
    print(f"{question} (yes/no)")
    try:
        # Sensitive actions must use the keyboard so nearby speech cannot approve them.
        if require_typed:  # PROTECTED
            from iris.console import request_input
            answer = request_input("You: ")
        else:
            answer = voice.listen()
        if answer is None and not require_typed:
            # Typed fallback keeps confirmation usable when voice recognition times out.
            answer = input("You: ")
    except (EOFError, KeyboardInterrupt):
        return False

    if answer is None:
        return False
    return str(answer).strip().lower() in {"yes", "y"}
