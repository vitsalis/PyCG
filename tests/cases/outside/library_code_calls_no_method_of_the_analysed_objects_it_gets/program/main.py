
import contextlib
import heapq
import logging
import math
import threading
class Worker(threading.Thread):
    def run(self): pass
class Resource:
    def __enter__(self): return self
    def __exit__(self, *args): pass
class Item:
    def __lt__(self, other): pass
    def __trunc__(self): return 0
class Handler(logging.Handler):
    def emit(self, record): pass
def use():
    Worker().start()
    with contextlib.ExitStack() as stack:
        stack.enter_context(Resource())
    heapq.heappush([], Item())
    math.trunc(Item())
    logging.getLogger("x").addHandler(Handler())
