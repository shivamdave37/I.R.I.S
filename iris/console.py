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
        request = self.create_request(prompt)
        self.enqueue(request)
        return self.wait_for_answer(request, timeout)

    def create_request(self, prompt, kind="confirmation"):
        """Create a typed prompt record before making it visible to the input loop."""
        return {"id": next(self._counter), "prompt": prompt, "kind": kind, "event": threading.Event(), "answer": None}

    def enqueue(self, request):
        """Add a prepared prompt to the shared confirmation queue."""
        self._requests.put(request)

    def wait_for_answer(self, request, timeout=60):
        """Wait a bounded time for the main loop to answer a prepared request."""
        if not request["event"].wait(timeout):
            self._remove_request(request["id"])
            return None
        return request["answer"]

    def kind(self, request_id):
        """Return the active prompt kind so the main loop can route its answer."""
        with self._lock:
            if self._active and self._active["id"] == request_id:
                return self._active["kind"]
        return None

    def _remove_request(self, request_id):
        """Remove an expired prompt so the main loop cannot display stale input."""
        with self._lock:
            if self._active and self._active["id"] == request_id:
                self._active = None
                return
            kept = []
            while True:
                try:
                    request = self._requests.get_nowait()
                except queue.Empty:
                    break
                if request["id"] != request_id:
                    kept.append(request)
            for request in kept:
                self._requests.put(request)

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
