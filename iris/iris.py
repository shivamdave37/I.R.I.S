"""Schedule Jarvis commands and supervise their workers and resources."""

import heapq
import itertools
import logging
import threading
import time

import config
from iris import agent_executor, agent_permissions, agent_planner
from iris.resources import ResourceManager
from iris.tasks import Task, TaskState


class Iris:
    """Coordinate plans, permissions, resource reservations, and task workers."""

    def __init__(self, permission_callback=None, task_timeout=60.0):
        """Create a supervisor with a scheduler thread and shared stop flag."""
        self.resources = ResourceManager()
        self.tasks = {}
        self._queue = []
        self._counter = itertools.count(1)
        self._condition = threading.Condition()
        self.stop_event = threading.Event()
        self._permission_callback = permission_callback
        self._task_timeout = task_timeout
        self._worker_threads = {}
        self._watchdog_thread = None
        self._scheduler_thread = None
        self._listeners = []
        self._control_queue = []
        self._confirmation_lock = threading.Lock()
        self._session_grants = set()
        self.start()

    def start(self):
        """Start the scheduler and watchdog once."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self.stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._schedule_loop, name="iris-scheduler", daemon=True)
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="iris-watchdog", daemon=True)
        self._scheduler_thread.start()
        self._watchdog_thread.start()

    def submit(self, command, priority=10, name=None):
        """Plan and enqueue one command, returning its task record."""
        if self.stop_event.is_set():
            raise RuntimeError("Iris is stopped")
        task_id = next(self._counter)
        task_name = name or command.strip() or "empty command"
        try:
            planned = agent_planner.plan(command)
            needed, allowed = agent_permissions.inspect(command)
            if not allowed:
                raise ValueError("The command requested an unknown resource.")
            task = Task(task_id, task_name, command, priority=priority,
                        needed_resources=needed, plan=planned["steps"],
                        estimated_time=planned["estimate_seconds"], timeout_seconds=self._task_timeout)
        except Exception as error:
            task = Task(task_id, task_name, command, priority=priority, state=TaskState.FAILED, error=str(error))
            self.tasks[task_id] = task
            return task
        self.tasks[task_id] = task
        with self._condition:
            heapq.heappush(self._queue, (priority, task.created_at, task.id))
            self._condition.notify_all()
        self._audit(task, "queued")
        return task

    def _schedule_loop(self):
        """Start the highest-priority ready task whenever its resources are free."""
        while not self.stop_event.is_set():
            with self._condition:
                self._condition.wait_for(lambda: self.stop_event.is_set() or self._queue, timeout=0.2)
                if self.stop_event.is_set():
                    break
                # Re-sort using aging so long-waiting work gradually gains priority.
                candidates = sorted(self._queue, key=lambda item: (item[0] - int((time.monotonic() - item[1]) / 30), item[1]))
                chosen = None
                for entry in candidates:
                    task = self.tasks.get(entry[2])
                    if task is None or task.state not in {TaskState.QUEUED, TaskState.WAITING}:
                        self._queue.remove(entry)
                        heapq.heapify(self._queue)
                        continue
                    if not self._permission_allowed(task):
                        self._queue.remove(entry)
                        heapq.heapify(self._queue)
                        task.state = TaskState.CANCELLED
                        task.error = "Permission denied or timed out."
                        task.finished_at = time.monotonic()
                        self._audit(task, "permission denied")
                        continue
                    if self.resources.reserve_all(task):
                        self._queue.remove(entry)
                        heapq.heapify(self._queue)
                        chosen = task
                        break
                    task.state = TaskState.WAITING
            if chosen:
                self._start_worker(chosen)
            else:
                time.sleep(0.03)

    def _permission_allowed(self, task):
        """Ask the injected permission workflow before reserving any resource."""
        if not task.needed_resources:
            return True
        if self._permission_callback is None:
            # Core mode keeps tests and fast known commands usable; Stage 5B supplies the admin gate.
            return True
        with self._confirmation_lock:
            return self._permission_callback(task)

    def _start_worker(self, task):
        """Start a daemon worker and mark the task as running."""
        task.state = TaskState.RUNNING
        if not task.started_at:
            task.started_at = time.monotonic()
        worker = threading.Thread(target=self._run_worker, args=(task,), name=f"iris-task-{task.id}", daemon=True)
        self._worker_threads[task.id] = worker
        self._audit(task, "started")
        worker.start()

    def _run_worker(self, task):
        """Run a task with exception handling and unconditional resource cleanup."""
        try:
            task.result = agent_executor.execute(task, self)
            if task.cancel_event.is_set() or self.stop_event.is_set() or task.result == "cancelled":
                task.state = TaskState.CANCELLED
            elif task.pause_event.is_set():
                task.state = TaskState.PAUSED
            else:
                task.state = TaskState.DONE
        except Exception as error:
            # A worker failure is visible to status instead of disappearing in a thread.
            task.state = TaskState.FAILED
            task.error = str(error)
            logging.exception("Iris task %s failed", task.id)
        finally:
            task.actual_time = max(0, time.monotonic() - task.started_at)
            if task.state != TaskState.PAUSED:
                self.resources.release(task)
            if task.state in {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED}:
                task.finished_at = time.monotonic()
            self._audit(task, f"finished state={task.state.value} estimate={task.estimated_time:.1f}s actual={task.actual_time:.1f}s")
            with self._condition:
                self._condition.notify_all()

    def _watchdog_loop(self):
        """Cancel overdue tasks and free their reservations."""
        while not self.stop_event.wait(0.1):
            now = time.monotonic()
            for task in list(self.tasks.values()):
                if task.state == TaskState.RUNNING and task.started_at and now - task.started_at > task.timeout_seconds:
                    task.cancel_event.set()
                    task.state = TaskState.CANCELLED
                    task.error = "Task timed out."
                    task.finished_at = now
                    self.resources.release(task)
                    self._audit(task, "timeout cancelled")

    def status(self):
        """Return a readable table of task states, resources, and timing."""
        now = time.monotonic()
        lines = ["ID | Task | State | Priority | Resources | Estimate | Elapsed"]
        for task in sorted(self.tasks.values(), key=lambda item: item.id):
            elapsed = task.actual_time if task.finished_at else max(0, now - task.started_at) if task.started_at else 0
            held = ",".join(self.resources.held_by(task.id)) or "-"
            lines.append(f"{task.id} | {task.name} | {task.state.value} | {task.priority} | {held} | {task.estimated_time:.1f}s | {elapsed:.1f}s")
        return "\n".join(lines)

    def wait(self, task_id, timeout=5):
        """Wait briefly for a task to reach a terminal or paused state."""
        deadline = time.monotonic() + timeout
        task = self.tasks.get(task_id)
        while task and task.state not in {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED, TaskState.PAUSED} and time.monotonic() < deadline:
            time.sleep(0.01)
        return task

    def stop(self, timeout=3):
        """Signal all workers to stop and join them within a bounded time."""
        self.stop_event.set()
        for task in self.tasks.values():
            if task.state in {TaskState.QUEUED, TaskState.WAITING, TaskState.RUNNING, TaskState.PAUSED}:
                task.cancel_event.set()
                task.state = TaskState.CANCELLED
                self.resources.release(task)
        with self._condition:
            self._condition.notify_all()
        deadline = time.monotonic() + timeout
        for worker in list(self._worker_threads.values()):
            worker.join(max(0, deadline - time.monotonic()))
        for thread in (self._scheduler_thread, self._watchdog_thread):
            if thread:
                thread.join(max(0, deadline - time.monotonic()))

    def _audit(self, task, event):
        """Write a task event and identifier to the configured audit log."""
        try:
            logging.info("task_id=%s | task=%r | %s", task.id, task.name, event)
        except Exception:
            pass
