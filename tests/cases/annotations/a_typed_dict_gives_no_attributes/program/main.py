
from typing import TypedDict
class Handler:
    def run(self): pass
class Config(TypedDict):
    handler: Handler
def use(cfg: Config):
    cfg.handler.run()
