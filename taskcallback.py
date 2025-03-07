import threading

class TaskCallback:
    """通用任务回调类"""
    def __init__(self, task_id: str, task_store: dict, lock: threading.Lock):
        self.task_id = task_id
        self.task_store = task_store
        self.lock = lock
    
    def __call__(self, message: str, progress: str = None):
        with self.lock:
            if self.task_id not in self.task_store:
                return

            lines = [line.strip() for line in message.split('\n') if line.strip()]
            self.task_store[self.task_id]["logs"].extend(lines)

            if progress:
                self.task_store[self.task_id]["progress"] = progress