"""Show deadlock prevention, priority aging, and cooperative pause/resume."""

import threading
import time
from unittest.mock import patch

from iris.iris import Iris, effective_priority
from iris.resources import ResourceManager
from iris.tasks import Task, TaskState


def naive_deadlock_demo():
    """Force two demo threads to wait on resources in opposite order."""
    first_lock = threading.Lock()
    second_lock = threading.Lock()
    both_started = threading.Barrier(2)

    def take_in_order(first, second):
        """Hold one resource before attempting the resource held by the peer."""
        with first:
            both_started.wait(timeout=1)
            second.acquire()

    first_thread = threading.Thread(target=take_in_order, args=(first_lock, second_lock), daemon=True)
    second_thread = threading.Thread(target=take_in_order, args=(second_lock, first_lock), daemon=True)
    first_thread.start()
    second_thread.start()
    first_thread.join(timeout=0.1)
    second_thread.join(timeout=0.1)
    if first_thread.is_alive() and second_thread.is_alive():
        print("Naive mode: deadlock detected; both demo tasks are stuck.")
    else:
        print("Naive mode: the forced deadlock did not occur.")


def iris_reservation_demo():
    """Run two demo requests using Iris's all-at-once resource reservation."""
    manager = ResourceManager()
    finished = []

    def reserve_and_release(task):
        """Wait until both required resources can be reserved together."""
        while not manager.reserve_all(task):
            time.sleep(0.01)
        finished.append(task.name)
        manager.release(task)

    first = Task(101, "Task A", "", needed_resources=["GIT_REPO", "NOTES_FILE"])
    second = Task(102, "Task B", "", needed_resources=["NOTES_FILE", "GIT_REPO"])
    threads = [threading.Thread(target=reserve_and_release, args=(task,), daemon=True) for task in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
    print("Iris mode: both tasks completed without holding one resource while waiting for another." if len(finished) == 2 else "Iris mode: demo timed out.")


def starvation_demo():
    """Display how waiting time raises the effective priority of older work."""
    new_priority = effective_priority(10, 0)
    waiting_priority = effective_priority(10, 300)
    print(f"A new task with priority 10 scores {new_priority}; after 5 minutes it scores {waiting_priority}.")
    print("Aging lowers the score of waiting work so it can move ahead of newer tasks.")


def pause_resume_demo():
    """Pause a two-step demo task, release resources, and resume its saved step."""
    entered = threading.Event()
    release_first_step = threading.Event()
    supervisor = Iris(task_timeout=5)

    def demo_action(command):
        """Slow the first fixed demo action so the pause request lands between steps."""
        if not entered.is_set():
            entered.set()
            release_first_step.wait(1)
        return "Demo step complete."

    planned = {"steps": ["chat", "chat"], "resources": ["API_QUOTA"], "estimate_seconds": 2}
    try:
        with patch("iris.agent_planner.plan", return_value=planned), patch("router.handle", side_effect=demo_action):
            task = supervisor.submit("pause resume demo")
            entered.wait(1)
            supervisor.pause(task.id)
            release_first_step.set()
            deadline = time.monotonic() + 2
            while task.state != TaskState.PAUSED and time.monotonic() < deadline:
                time.sleep(0.01)
            released = not supervisor.resources.held_by(task.id)
            step = task.current_step
            supervisor.resume(task.id)
            supervisor.wait(task.id, 2)
            print(f"Pause/resume mode: paused at step {step}, resources released={released}, final state={task.state.value}.")
    finally:
        release_first_step.set()
        supervisor.stop()


def main():
    """Run every repeatable Iris demonstration in order."""
    naive_deadlock_demo()
    iris_reservation_demo()
    starvation_demo()
    pause_resume_demo()


if __name__ == "__main__":
    main()
