"""Schedule Jarvis commands and supervise their workers and resources."""

import heapq
import itertools
import logging
import os
import threading
import time

import config
from iris import agent_executor, agent_permissions, agent_planner
from iris.resources import ResourceManager
from iris.tasks import Task, TaskState


def effective_priority(priority, wait_seconds):
    """Improve a waiting task's score by one point per thirty seconds."""
    return max(0, int(priority) - int(max(0, wait_seconds) / 30))


class Iris:
    """Coordinate plans, permissions, resource reservations, and task workers."""

    def __init__(self, permission_callback=None, task_timeout=60.0, result_callback=None):
        """Create a supervisor with a scheduler thread and shared stop flag."""
        self.resources = ResourceManager()
        self.tasks = {}
        self._queue = []
        self._counter = itertools.count(1)
        self._condition = threading.Condition()
        self.stop_event = threading.Event()
        self._permission_callback = permission_callback
        self._result_callback = result_callback
        self._task_timeout = task_timeout
        self._worker_threads = {}
        self._watchdog_thread = None
        self._scheduler_thread = None
        self._listeners = []
        self._control_queue = []
        self._confirmation_lock = threading.Lock()
        self._session_grants = set()
        self._permission_results = set()
        self.permission_manager = None
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
        task_name = self._safe_task_name(name or command.strip() or "empty command")
        try:
            needed, allowed = agent_permissions.inspect(command)
            if not allowed:
                raise ValueError("The command requested an unknown resource.")
            planned = agent_planner.plan(command)
            # Keep Agent 1's fixed requirements and include any validated extra needs from Agent 2.
            needed = sorted(set(needed) | set(planned["resources"]))
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

    @staticmethod
    def _safe_task_name(name):
        """Redact the configured provider key before a command is displayed or logged."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            secret = os.getenv("GEMINI_API_KEY")
            if secret:
                return str(name).replace(secret, "[REDACTED]")
        except Exception:
            pass
        return str(name)

    def _schedule_loop(self):
        """Start the highest-priority ready task whenever its resources are free."""
        while not self.stop_event.is_set():
            with self._condition:
                self._condition.wait_for(lambda: self.stop_event.is_set() or self._queue, timeout=0.2)
                if self.stop_event.is_set():
                    break
                # One active task keeps every stdin confirmation in the single prompt queue.
                if any(task.state == TaskState.RUNNING for task in self.tasks.values()):
                    self._condition.wait(timeout=0.1)
                    continue
                # Re-sort using aging so long-waiting work gradually gains priority.
                candidates = sorted(self._queue, key=lambda item: (effective_priority(item[0], time.monotonic() - item[1]), item[1]))
                chosen = None
                for entry in candidates:
                    task = self.tasks.get(entry[2])
                    if task is None or task.state not in {TaskState.QUEUED, TaskState.WAITING}:
                        self._queue.remove(entry)
                        heapq.heapify(self._queue)
                        continue
                    self._queue.remove(entry)
                    heapq.heapify(self._queue)
                    chosen = task
                    break
            if chosen:
                # Permission waits happen outside the scheduler lock so admin controls stay live.
                if chosen.id not in self._permission_results:
                    if not self._permission_allowed(chosen):
                        if chosen.state == TaskState.CANCELLED or chosen.cancel_event.is_set():
                            continue
                        chosen.state = TaskState.CANCELLED
                        chosen.error = "Permission denied or timed out."
                        chosen.finished_at = time.monotonic()
                        self._audit(chosen, "permission denied")
                        continue
                    self._permission_results.add(chosen.id)
                    chosen.authorized_at = time.monotonic()
                if chosen.state == TaskState.CANCELLED or chosen.cancel_event.is_set():
                    continue
                if self.resources.reserve_all(chosen):
                    self._start_worker(chosen)
                else:
                    chosen.state = TaskState.WAITING
                    with self._condition:
                        heapq.heappush(self._queue, (chosen.priority, chosen.created_at, chosen.id))
                        self._condition.wait(timeout=0.03)
            else:
                time.sleep(0.03)

    def _permission_allowed(self, task):
        """Ask the injected permission workflow before reserving any resource."""
        if not task.needed_resources:
            return True
        if self._permission_callback is None:
            # Core mode keeps tests and fast known commands usable; Stage 5B supplies the admin gate.
            return True
        try:
            with self._confirmation_lock:
                return self._permission_callback(task)
        except Exception as error:
            self._audit(task, f"permission workflow failed safely: {type(error).__name__}")
            return False

    def pending_permission_prompt(self):
        """Expose the active permission request to the main input loop."""
        if self.permission_manager is None:
            return None
        return self.permission_manager.pending_prompt()

    def answer_permission(self, task_id, text, typed=True):
        """Pass the admin's typed permission choices to the single active prompt."""
        if self.permission_manager is None:
            return False
        return self.permission_manager.answer(task_id, text, typed)

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
            task.error = self._safe_task_name(str(error))
            logging.error("Iris task %s failed with %s", task.id, type(error).__name__)
        finally:
            task.actual_time = max(0, time.monotonic() - task.started_at)
            if task.state in {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED}:
                task.finished_at = time.monotonic()
            self._audit(task, f"finished state={task.state.value} estimate={task.estimated_time:.1f}s actual={task.actual_time:.1f}s")
            if self._result_callback and task.state in {TaskState.DONE, TaskState.FAILED}:
                try:
                    self._result_callback(task)
                except Exception as error:
                    logging.error("Iris result callback failed for task %s with %s", task.id, type(error).__name__)
            # Hold resources through queued speech so another task cannot overlap the speaker.
            self.resources.release(task)
            with self._condition:
                self._condition.notify_all()

    def _watchdog_loop(self):
        """Cancel overdue tasks and free their reservations."""
        while not self.stop_event.wait(0.1):
            now = time.monotonic()
            for task in list(self.tasks.values()):
                if (task.state == TaskState.WAITING and task.authorized_at
                        and now - task.authorized_at > task.timeout_seconds):
                    task.cancel_event.set()
                    task.state = TaskState.CANCELLED
                    task.error = "Task timed out while waiting for resources."
                    task.finished_at = now
                    self.resources.release(task)
                    self._audit(task, "resource wait timeout cancelled")
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
            if task.result or task.error:
                lines.append(f"  Result: {task.result or task.error}")
        return "\n".join(lines)

    def wait(self, task_id, timeout=5):
        """Wait briefly for a task to reach a terminal or paused state."""
        deadline = time.monotonic() + timeout
        task = self.tasks.get(task_id)
        while task and task.state not in {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED, TaskState.PAUSED} and time.monotonic() < deadline:
            time.sleep(0.01)
        return task

    def pause(self, task_id):
        """Request a cooperative pause for a queued or running task."""
        task = self.tasks.get(task_id)
        if task is None or task.state not in {TaskState.QUEUED, TaskState.WAITING, TaskState.RUNNING}:
            return "Task not found or cannot be paused."
        task.pause_event.set()
        if task.state in {TaskState.QUEUED, TaskState.WAITING}:
            task.state = TaskState.PAUSED
        self._audit(task, "admin pause")
        return f"Pause requested for task {task_id}."

    def resume(self, task_id):
        """Resume a paused task after reacquiring all resources atomically."""
        task = self.tasks.get(task_id)
        if task is None or task.state != TaskState.PAUSED:
            return "Task is not paused."
        if not self.resources.reserve_all(task):
            return "Task is waiting for its resources."
        task.cancel_event.clear()
        task.pause_event.clear()
        task.state = TaskState.RUNNING
        worker = self._worker_threads.get(task.id)
        if worker is None or not worker.is_alive():
            task.state = TaskState.QUEUED
            with self._condition:
                heapq.heappush(self._queue, (task.priority, task.created_at, task.id))
                self._condition.notify_all()
        self._audit(task, "admin resume")
        return f"Resumed task {task_id}."

    def cancel(self, task_id):
        """Cancel a task cooperatively and release resources when safe."""
        task = self.tasks.get(task_id)
        if task is None or task.state in {TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED}:
            return "Task not found or already finished."
        task.cancel_event.set()
        from iris.console import input_broker
        input_broker.cancel_all()
        if task.state != TaskState.RUNNING:
            task.state = TaskState.CANCELLED
            task.finished_at = time.monotonic()
            self.resources.release(task)
        self._audit(task, "admin cancel")
        return f"Cancelled task {task_id}."

    def pause_checkpoint(self, task):
        """Release resources while paused and wait cooperatively for resume or cancel."""
        if not task.pause_event.is_set():
            return not task.cancel_event.is_set() and not self.stop_event.is_set()
        self.resources.release(task)
        task.state = TaskState.PAUSED
        self._audit(task, f"paused at step {task.current_step}")
        while task.pause_event.is_set() and not task.cancel_event.is_set() and not self.stop_event.is_set():
            # The short wait lets an admin resume or stop the worker without busy looping.
            task.cancel_event.wait(0.05)
        return not task.cancel_event.is_set() and not self.stop_event.is_set()

    def set_priority(self, task_id, priority):
        """Update a queued task's priority without changing the global rules."""
        task = self.tasks.get(task_id)
        if task is None or task.state not in {TaskState.QUEUED, TaskState.WAITING}:
            return "Only queued tasks can change priority."
        task.priority = max(0, min(int(priority), 100))
        with self._condition:
            self._queue = [entry for entry in self._queue if entry[2] != task_id]
            heapq.heapify(self._queue)
            heapq.heappush(self._queue, (task.priority, task.created_at, task.id))
            self._condition.notify_all()
        self._audit(task, f"admin priority={task.priority}")
        return f"Task {task_id} priority is {task.priority}."

    def stop_all(self):
        """Emergency-cancel every active task while keeping Iris available."""
        workers_to_wait = []
        for task in self.tasks.values():
            if task.state in {TaskState.QUEUED, TaskState.WAITING, TaskState.RUNNING, TaskState.PAUSED}:
                task.cancel_event.set()
                task.state = TaskState.CANCELLED
                task.finished_at = time.monotonic()
                worker = self._worker_threads.get(task.id)
                if worker and worker.is_alive():
                    workers_to_wait.append(worker)
                else:
                    self.resources.release(task)
                self._audit(task, "admin stop all")
        from iris.console import input_broker
        input_broker.cancel_all()
        with self._condition:
            self._queue.clear()
            self._condition.notify_all()
        deadline = time.monotonic() + 2
        for worker in workers_to_wait:
            worker.join(max(0, deadline - time.monotonic()))
        if any(worker.is_alive() for worker in workers_to_wait):
            return "Stop requested; a blocking step is still finishing. Jarvis is still running."
        return "All tasks cancelled and resources released; Jarvis is still running."

    def handle_admin(self, command):
        """Handle only the fixed high-priority control command grammar."""
        parts = command.lower().split()
        if command.strip().lower() == "status":
            self._audit(None, "admin status")
            return self.status()
        if command.strip().lower() == "stop all":
            return self.stop_all()
        if command.strip().lower() == "grants":
            grants = self.permission_manager.grants() if self.permission_manager else []
            self._audit(None, "admin grants")
            return "Saved permissions: " + (", ".join(grants) if grants else "none")
        if len(parts) == 2 and parts[0] == "revoke" and self.permission_manager:
            removed = self.permission_manager.revoke(parts[1].upper())
            return "Permission revoked." if removed else "No saved permission for that resource."
        for action in ("pause", "resume", "cancel"):
            if command.lower().startswith(action + " "):
                task_id = self._resolve_task_id(command[len(action):].strip())
                return getattr(self, action)(task_id) if task_id else "Task not found."
        if command.lower().startswith("priority "):
            target, separator, value = command[len("priority "):].rpartition(" ")
            task_id = self._resolve_task_id(target.strip())
            if separator and task_id and value.lstrip("-").isdigit():
                return self.set_priority(task_id, int(value))
        if command.lower().startswith("switch to "):
            target_id = self._resolve_task_id(command[len("switch to "):].strip())
            if not target_id:
                return "Task not found."
            for task in self.tasks.values():
                if task.state == TaskState.RUNNING and task.id != target_id:
                    self.pause(task.id)
                    deadline = time.monotonic() + 2
                    while task.state == TaskState.RUNNING and time.monotonic() < deadline:
                        time.sleep(0.02)
            target = self.tasks.get(target_id)
            if target and target.state == TaskState.PAUSED:
                return self.resume(target_id)
            return self.set_priority(target_id, 0)
        return "Unknown admin command. Rules cannot be changed at runtime."

    def _resolve_task_id(self, identifier):
        """Find a task by its numeric id or exact case-insensitive name."""
        if identifier.isdigit() and int(identifier) in self.tasks:
            return int(identifier)
        for task in self.tasks.values():
            if task.name.lower() == identifier.lower():
                return task.id
        return None

    def stop(self, timeout=3):
        """Signal all workers to stop and join them within a bounded time."""
        self.stop_event.set()
        from iris.console import input_broker
        input_broker.cancel_all()
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
