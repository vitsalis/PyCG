
def work(): pass
class Cache:
    __slots__ = ("_store", "__self__")
    def __init__(self):
        self._store = work
    def __getattr__(self, name):
        return work
    def run(self):
        self._store()
        self.__self__
Cache().run()
