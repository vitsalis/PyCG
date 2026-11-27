
import ext
def f(): pass
def g(): pass

import asyncio
async def work():
    return f
async def main():
    await asyncio.gather(work(), work())
    task = asyncio.create_task(work())
    await asyncio.wait_for(task, 1)
    (await work())()
asyncio.run(main())
asyncio.new_event_loop().run_until_complete(main())
