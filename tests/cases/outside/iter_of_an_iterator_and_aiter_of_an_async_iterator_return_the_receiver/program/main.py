
import collections.abc
def f(): pass
class Items(collections.abc.Iterator):
    def __next__(self): return f
class Steps(collections.abc.Generator):
    def __next__(self): return f
    def send(self, value): return f
    def throw(self, *args): pass
class Stream(collections.abc.AsyncIterator):
    async def __anext__(self): return f
class Rows(collections.abc.Sequence):
    def __getitem__(self, index): pass
    def __len__(self): return 0
    def __next__(self): return f
def items():
    for item in Items():
        item()
def steps():
    for step in Steps():
        step()
def explicit():
    Items().__iter__().__next__()
async def stream():
    async for item in Stream():
        item()
    await Stream().__aiter__().__anext__()
def rows():
    for row in Rows():
        row()
