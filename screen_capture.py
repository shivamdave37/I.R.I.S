"""Optional, on-demand screen capture kept only in process memory."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import io
import platform

import approval_context


MAX_SCREEN_BYTES = 4_000_000
_LATEST_FRAME = None


@dataclass(frozen=True)
class ScreenFrame:
    """An immutable screen image; it is never written to disk by this module."""

    frame_id: str
    width: int
    height: int
    png_bytes: bytes
    captured_utc: str


def _capture_frame(action, params):
    """Capture one frame in memory using the optional PyAutoGUI dependency."""
    approval_context.require(action, params)
    if platform.system() != "Windows":
        raise RuntimeError("Screen capture is supported only on Windows.")
    try:
        pyautogui = importlib.import_module("pyautogui")
        image = pyautogui.screenshot()
        width, height = image.size
        output = io.BytesIO()
        image.save(output, format="PNG")
        png_bytes = output.getvalue()
    except ImportError as error:
        raise RuntimeError("Screen tools are unavailable. Install the optional UI requirements.") from error
    except Exception as error:
        raise RuntimeError("Windows could not capture the screen.") from error
    if width <= 0 or height <= 0 or not png_bytes or len(png_bytes) > MAX_SCREEN_BYTES:
        raise RuntimeError("The screen image is empty or exceeds Iris's size limit.")
    frame_id = hashlib.sha256(png_bytes).hexdigest()
    return ScreenFrame(frame_id, int(width), int(height), png_bytes, datetime.now(timezone.utc).isoformat())


def capture_screen():
    """Capture after gateway approval and retain only the latest in-memory frame."""
    global _LATEST_FRAME
    approval_context.require("capture_screen", {})
    try:
        frame = _capture_frame("capture_screen", {})
    except RuntimeError as error:
        return f"Screen capture unavailable: {error}"
    _LATEST_FRAME = frame
    return (
        f"Captured screen {frame.frame_id[:12]} ({frame.width}x{frame.height}) in temporary memory. "
        "It was not saved. Use 'describe screen' to request a separately approved Gemini analysis."
    )


def latest_frame(frame_id=None):
    """Return the current frame only when an optional caller ID matches."""
    if _LATEST_FRAME is None or (frame_id is not None and _LATEST_FRAME.frame_id != frame_id):
        return None
    return _LATEST_FRAME


def _fresh_frame_for_ui(action, params):
    """Take the fresh local frame covered by the specific UI-action approval."""
    return _capture_frame(action, params)
