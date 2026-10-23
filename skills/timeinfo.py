"""Time and date skills."""

from datetime import datetime


def tell_time():
    """Return the current local time in a readable format."""
    # Format current local time in 12-hour format with AM/PM for friendly speech/reading.
    return f"The time is {datetime.now().strftime('%I:%M %p')} .".replace(" .", ".")


def tell_date():
    """Return today's local date in a readable format."""
    # Format today's date and strip leading zeros on the day (e.g. 'October 5').
    return f"Today's date is {datetime.now().strftime('%B %d, %Y').replace(' 0', ' ')}."

