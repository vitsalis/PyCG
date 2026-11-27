
class Cache:
    def get(self): pass
    def set(self): pass
    def clear(self): pass
class Proxy:
    def __init__(self, cache): self.cache = cache
    def run(self, name): getattr(self.cache, name)()
def renamed(): pass
renamed.__name__ = "clear"
def use(proxy):
    for command in (Cache.set, Cache().get):
        proxy.run(command.__name__)
    proxy.run(renamed.__name__)
    (lambda: None).__name__.upper()
use(Proxy(Cache()))
