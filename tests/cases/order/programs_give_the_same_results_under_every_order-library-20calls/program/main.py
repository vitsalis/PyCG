
import contextlib
import heapq
import logging
import threading
class Worker(threading.Thread):
    def run(self):
        self.step()
    def step(self): pass
class Item:
    def __lt__(self, other): pass
class Handler(logging.Handler):
    def emit(self, record):
        record.getMessage()
class Resource:
    def __enter__(self): return self
    def __exit__(self, *args): pass
Worker().start()
heapq.heappush([], Item())
logging.getLogger("x").addHandler(Handler())
with contextlib.ExitStack() as stack:
    stack.enter_context(Resource())
