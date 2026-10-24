"""Run approved Jarvis steps cooperatively and return their final reply."""


def execute(task, iris):
    """Run the safe router step while honoring pause and cancel between steps."""
    import router
    while task.current_step < len(task.plan):
        if task.cancel_event.is_set() or iris.stop_event.is_set():
            return "cancelled"
        while task.pause_event.is_set() and not task.cancel_event.is_set() and not iris.stop_event.is_set():
            # A timed wait lets resume and cancel controls wake the cooperative worker.
            task.cancel_event.wait(0.05)
        if task.cancel_event.is_set() or iris.stop_event.is_set():
            return "cancelled"
        # One user command remains one action even when a planner returns several steps.
        if task.current_step == 0:
            task.result = router.handle(task.command_text)
        task.current_step += 1
    return task.result
