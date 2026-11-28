
class Pending:
    def __await__(self):
        yield
class Manager:
    async def __aenter__(self): return self
    def __aexit__(self, *args): return Pending()
class Unbound:
    def __aenter__(self): return Pending()
    async def __aexit__(self, *args): pass
class Sync:
    def __enter__(self): return Pending()
    def __exit__(self, *args): return Pending()
async def bound():
    async with Manager() as manager:
        pass
async def unbound():
    async with Unbound():
        pass
def sync():
    with Sync():
        pass
