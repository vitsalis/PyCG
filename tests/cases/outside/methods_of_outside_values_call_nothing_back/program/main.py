
import asyncio
import concurrent.futures
def tick(): pass
def job(): pass
def done(future): pass
async def start():
    loop = asyncio.get_running_loop()
    loop.call_soon(tick)
    loop.time().is_integer()
    executor = concurrent.futures.ThreadPoolExecutor()
    future = executor.submit(job)
    future.add_done_callback(done)
    future.result()
