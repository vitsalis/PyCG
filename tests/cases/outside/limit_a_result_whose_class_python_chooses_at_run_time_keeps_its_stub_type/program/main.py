
import asyncio
import importlib.resources
from xml.sax import make_parser
def cb(): pass
async def run():
    asyncio.get_running_loop().call_later(1, cb)
    asyncio.new_event_loop().stop()
def parse(stream):
    make_parser().parse(stream)
def data():
    importlib.resources.files("pkg").joinpath("x.bin").open("rb").read()
