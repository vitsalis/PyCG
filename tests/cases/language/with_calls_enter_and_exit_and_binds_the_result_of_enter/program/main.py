
def f(): pass
class Lock:
    def __enter__(self):
        return f
    def __exit__(self, kind, value, traceback):
        pass
def use(lock):
    with lock as acquired:
        acquired()
use(Lock())
