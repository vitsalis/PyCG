
import asyncio
async def use():
    (await asyncio.create_subprocess_exec("ls")).wait()
