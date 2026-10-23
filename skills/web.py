"""Website opening skill."""

import webbrowser

import config


def open_website(name):
    """Open a website only when its name is in the approved settings."""
    url = config.WEBSITES.get(name)
    if url is None:
        return f"I can't open {name}; it is not in the approved website list."

    try:
        webbrowser.open(url)
        return f"Opening {name}."
    except Exception:
        return f"I couldn't open {name}. Please check your default browser."
