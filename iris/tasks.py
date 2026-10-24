"""Shared task records and lifecycle states for Iris."""

from dataclasses import dataclass, field
from enum import Enum
import threading
import time


class TaskState(Enum):
    """Possible states for one supervised Jarvis task."""

    QUEUED = "QUEUED"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Task:
    """Keep a task's request, plan, timing, and cooperative controls together."""

    id: int
    name: str
    command_text: str
    priority: int = 10
    state: TaskState = TaskState.QUEUED
    needed_resources: list = field(default_factory=list)
    plan: list = field(default_factory=list)
    estimated_time: float = 1.0
    actual_time: float = 0.0
    created_at: float = field(default_factory=time.monotonic)
    authorized_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    current_step: int = 0
    result: str = ""
    error: str = ""
    timeout_seconds: float = 60.0
    permission_waiting: bool = False
    pause_event: threading.Event = field(default_factory=threading.Event)
    cancel_event: threading.Event = field(default_factory=threading.Event)
