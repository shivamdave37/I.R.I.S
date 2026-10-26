"""Run approved Jarvis steps cooperatively and return their final reply."""


def execute(task, iris):
    """Run the safe router step while honoring pause and cancel between steps."""
    import router
    while task.current_step < len(task.plan):
        if task.cancel_event.is_set() or iris.stop_event.is_set():  # PROTECTED
            return "cancelled"
        if not iris.pause_checkpoint(task):
            return "cancelled"
        # Execute one approved skill step, then check control flags before the next.
        task.result = router.handle(task.command_text)
        task.current_step += 1
    return task.result
