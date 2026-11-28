
import contextlib
import typing
class Manager(contextlib.AbstractAsyncContextManager):
    async def __aexit__(self, *args): pass
    def tick(self): pass
class Plain(contextlib.AbstractContextManager):
    def __exit__(self, *args): pass
    def tick(self): pass
def asynchronous(m: typing.AsyncContextManager[int]):
    m.tick()
def stub_name(m: contextlib.AbstractAsyncContextManager):
    m.tick()
def synchronous(m: typing.ContextManager[int]):
    m.tick()
