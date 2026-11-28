DEBUG = False
LEVEL: int = 2
NAME = "quiet"

def trace(): pass
def report(): pass
def loud(): pass
def other(): pass

def run():
    if DEBUG:
        trace()
    if LEVEL > 1:
        report()
    if NAME == "loud":
        loud()
    else:
        other()

class Handler:
    def handle(self):
        if not DEBUG:
            return other()
        trace()
