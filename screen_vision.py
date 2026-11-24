"""Send an approved ephemeral screen frame to the configured vision provider."""

import os

import approval_context
import ai
import config
import screen_capture


def configuration_status():
    """Check provider/key availability without returning or displaying key data."""
    if not ai._load_env_file():
        return "Screen analysis is unavailable because the local provider settings could not be read safely."
    provider = os.environ.get("IRIS_AI_PROVIDER", config.AI_PROVIDER).strip().lower()
    if provider != "gemini":
        return "Screen analysis is unavailable: the configured provider does not support Iris's vision workflow."
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        return "Screen analysis is not configured. Add GEMINI_API_KEY to the local .env file."
    return ""


def analyze_screen(frame_id, question, approved_frame=None):
    """Describe one current frame; the screenshot is never saved by this module."""
    params = {"frame_id": frame_id, "question": question}
    approval_context.require("analyze_screen", params)
    frame = approved_frame or screen_capture.latest_frame(frame_id)
    if frame is not None and frame.frame_id != frame_id:
        frame = None
    if frame is None:
        return "Screen analysis failed: that capture is no longer available. Capture the screen again."
    unavailable = configuration_status()
    if unavailable:
        return unavailable
    return ai.describe_screen(frame.png_bytes, question)
