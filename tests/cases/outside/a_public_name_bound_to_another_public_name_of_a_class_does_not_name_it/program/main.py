import asyncio

selector = asyncio.SelectorEventLoop()
selector.close()
proactor = asyncio.ProactorEventLoop()
proactor.close()
default = asyncio.EventLoop()
default.stop()
