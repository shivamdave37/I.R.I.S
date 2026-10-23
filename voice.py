"""Microphone input and queued speech output for Stage 2."""

import queue
import threading


_speaker_queue = queue.Queue()
_speaker_thread = None
_speaker_lock = threading.Lock()


def _load_speech_recognition():
    """Load the microphone library only when voice input is requested."""
    import speech_recognition

    return speech_recognition


def listen():
    """Listen briefly and return recognized text or None on any mic failure."""
    try:
        speech_recognition = _load_speech_recognition()
        recognizer = speech_recognition.Recognizer()
        with speech_recognition.Microphone() as microphone:
            # Time limits let the app recover from silence and return to its loop.
            audio = recognizer.listen(microphone, timeout=5, phrase_time_limit=8)
        return recognizer.recognize_google(audio)
    except Exception:
        # Missing devices, silence, and network errors should not stop Jarvis.
        return None


def _speaker_worker():
    """Own the speech engine and process queued text on one thread."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
    except Exception:
        # Keep the worker available to drain queued messages even without audio.
        engine = None

    while True:
        text = _speaker_queue.get()
        try:
            if text is None:
                break
            if engine is not None:
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    # Keep the worker alive so a speech error does not break Jarvis.
                    pass
        finally:
            _speaker_queue.task_done()


def _start_speaker():
    """Start the single speech worker when it is not already running."""
    global _speaker_thread

    with _speaker_lock:
        if _speaker_thread is None or not _speaker_thread.is_alive():
            _speaker_thread = threading.Thread(target=_speaker_worker, daemon=True)
            _speaker_thread.start()


def speak(text):
    """Queue text for the one thread that owns the speech engine."""
    _start_speaker()
    _speaker_queue.put(str(text))


def wait_until_done():
    """Block until queued speech has finished playing."""
    _speaker_queue.join()


def shutdown():
    """Stop the speech worker cleanly after its queued speech finishes."""
    global _speaker_thread

    with _speaker_lock:
        thread = _speaker_thread
        if thread is None:
            return
        if thread.is_alive():
            # The sentinel lets the worker close its own engine after queued speech.
            _speaker_queue.put(None)

    if thread.is_alive():
        thread.join(timeout=10)

    with _speaker_lock:
        if not thread.is_alive():
            _speaker_thread = None
