
import typing
from typing import Protocol
class Logger(Protocol):
    def log(self):
        self.flush()
    def flush(self): pass
class Sink(typing.Protocol):
    def log(self):
        self.flush()
    def flush(self): pass
class FileLogger(Logger):
    def flush(self): pass
