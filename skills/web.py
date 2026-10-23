"""Website opening skill."""

import webbrowser

import config


def open_website(name):
    """Open a website only when its name is in the approved settings."""
    url = config.WEBSITES.get(name)
    # Strictly refuse any website not explicitly approved in settings.
    if url is None:
        return f"I can't open {name}; it is not in the approved website list."

    try:
        # Standard library webbrowser.open returns True on success and False on failure.
        success = webbrowser.open(url)
        if success is False:
            return f"I couldn't open {name}. Please check your default browser."
        return f"Opening {name}."
    except Exception:
        # Catch browser invocation errors so Jarvis keeps running safely.
        return f"I couldn't open {name}. Please check your default browser."

