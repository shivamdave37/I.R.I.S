"""Listen for the configured wake word without overlapping Iris audio tasks."""

import json
import logging
import os
import re

import config
from iris.tasks import Task
import voice


def create_listener():
    """Load the offline Vosk model or select the documented online fallback."""
    if not getattr(config, "WAKE_ENABLED", False):
        return {"enabled": False, "offline": False, "model": None}
    try:
        import vosk
        if not os.path.isdir(config.WAKE_MODEL_PATH):
            raise FileNotFoundError("Vosk model folder is missing")
        model = vosk.Model(config.WAKE_MODEL_PATH)
        print("Wake word: offline Vosk detection is ready.")
        return {"enabled": True, "offline": True, "model": model}
    except Exception as error:
        logging.warning("Vosk wake detection unavailable: %s", type(error).__name__)
        print("Vosk is unavailable; using the online fallback for wake-word detection.")
        return {"enabled": True, "offline": False, "model": None}


def _reserve_microphone(resource_manager):
    """Reserve the microphone and speaker together for one short listen."""
    task = Task(-1, "wake listener", "wake listener", needed_resources=["MIC_SPEAKER"])
    if not resource_manager.reserve_all(task):
        return None
    return task


def _capture(resource_manager, timeout, phrase_limit):
    """Capture one bounded phrase only while Iris owns the audio resource."""
    voice.wait_until_done()
    task = _reserve_microphone(resource_manager)
    if task is None:
        return "busy", None
    try:
        audio = voice.capture_audio_chunk(timeout=timeout, phrase_time_limit=phrase_limit)
    finally:
        resource_manager.release(task)
    if audio is False:
        return "error", None
    if audio is None:
        return "idle", None
    return "audio", audio


def _recognized_text(audio, listener, grammar=None):
    """Recognize captured audio with the loaded offline model."""
    import vosk
    raw_audio = audio.get_raw_data(convert_rate=16000, convert_width=2)
    recognizer = (vosk.KaldiRecognizer(listener["model"], 16000, grammar)
                 if grammar else vosk.KaldiRecognizer(listener["model"], 16000))
    if recognizer.AcceptWaveform(raw_audio):
        result = recognizer.Result()
    else:
        result = recognizer.FinalResult()
    try:
        return json.loads(result).get("text", "").lower().strip()
    except (TypeError, ValueError):
        return ""


def _after_wake_word(text):
    """Return any same-phrase command after the configured wake word."""
    words = text.split()
    wake_word = config.WAKE_WORD.lower().strip()
    try:
        position = words.index(wake_word)
    except ValueError:
        return ""
    return " ".join(words[position + 1:]).strip()


def _has_wake_word(text):
    """Match the configured wake word as a whole word."""
    return bool(re.search(r"\b" + re.escape(config.WAKE_WORD.strip().lower()) + r"\b", text or ""))


def listen_chunk(resource_manager, listener):
    """Check one audio chunk for the wake word and an optional same-phrase command."""
    status, audio = _capture(resource_manager, config.WAKE_CHUNK_TIMEOUT, config.WAKE_PHRASE_LIMIT)
    if status != "audio":
        return status, ""
    if listener["offline"]:
        try:
            grammar = json.dumps([config.WAKE_WORD.lower(), "[unk]"])
            wake_text = _recognized_text(audio, listener, grammar)
            if not _has_wake_word(wake_text):
                return "idle", ""
            # Re-decode this same phrase freely so a command after “Iris” is not lost.
            phrase_text = _recognized_text(audio, listener)
            if not _has_wake_word(phrase_text):
                phrase_text = wake_text
        except Exception as error:
            logging.warning("Vosk recognition failed: %s", type(error).__name__)
            print("Vosk recognition failed; using the online fallback.")
            listener["offline"] = False
            phrase_text = voice.recognize_audio(audio) or ""
            if not _has_wake_word(phrase_text):
                return "idle", ""
    else:
        phrase_text = voice.recognize_audio(audio) or ""
        if not _has_wake_word(phrase_text):
            return "idle", ""
    logging.info("wake_word_detected=%s", config.WAKE_WORD.lower())
    return "wake", _after_wake_word(phrase_text)


def listen_for_command(resource_manager, listener):
    """Listen once for a command after the acknowledgement, using the selected recognizer."""
    status, audio = _capture(resource_manager, config.WAKE_COMMAND_TIMEOUT, config.WAKE_COMMAND_LIMIT)
    if status != "audio":
        return status, ""
    if listener["offline"]:
        try:
            return "command", _recognized_text(audio, listener)
        except Exception as error:
            logging.warning("Vosk command recognition failed: %s", type(error).__name__)
            print("Vosk recognition failed; using the online fallback.")
            listener["offline"] = False
    command = voice.recognize_audio(audio)
    return ("command", command or "") if command else ("error", "")


def listen_regular_command(resource_manager):
    """Capture a normal voice command only when Iris can reserve the audio resource."""
    voice.wait_until_done()
    task = _reserve_microphone(resource_manager)
    if task is None:
        return "busy", ""
    try:
        command = voice.listen()
    finally:
        resource_manager.release(task)
    return ("command", command) if command else ("error", "")
