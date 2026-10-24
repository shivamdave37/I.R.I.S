"""Route worker input prompts through the one main-loop keyboard reader."""

import itertools
import queue
import threading


class InputBroker:
    """Keep task prompts serialized and prevent worker threads reading stdin."""

    def __init__(self):
        """Create a queue for pending prompts and a prompt identifier counter."""
        self._requests = queue.Queue()
        self._counter = itertools.count(1)
        self._lock = threading.Lock()
        self._active = None
        self.enabled = False

    def request(self, prompt, timeout=60):
        """Wait for the main loop to collect one typed answer."""
        request = {"id": next(self._counter), "prompt": prompt, "event": threading.Event(), "answer": None}
        self._requests.put(request)
        if not request["event"].wait(timeout):
            return None
        return request["answer"]

    def pending(self):
        """Return the current keyboard prompt or promote the next queued prompt."""
        with self._lock:
            if self._active is None:
                try:
                    self._active = self._requests.get_nowait()
                except queue.Empty:
                    return None
            return self._active["id"], self._active["prompt"]

    def answer(self, request_id, text, typed=True):
        """Complete the active prompt using the main loop's typed response."""
        with self._lock:
            if self._active is None or self._active["id"] != request_id or not typed:
                return False
            self._active["answer"] = text
            self._active["event"].set()
            self._active = None
            return True

    def cancel_all(self):
        """Wake every blocked worker so shutdown cannot leave stdin waiters behind."""
        with self._lock:
            requests = []
            if self._active:
                requests.append(self._active)
                self._active = None
            while True:
                try:
                    requests.append(self._requests.get_nowait())
                except queue.Empty:
                    break
            for request in requests:
                request["answer"] = None
                request["event"].set()


input_broker = InputBroker()


def request_input(prompt, timeout=60):
    """Use the central keyboard broker in Iris mode and normal input otherwise."""
    if input_broker.enabled:
        return input_broker.request(prompt, timeout)
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None
