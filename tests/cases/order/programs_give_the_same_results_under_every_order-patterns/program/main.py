
import handlers
def base():
    return Base
class Base:
    def on_open(self): pass
class Handler(base()):
    def on_close(self): pass
    def __init__(self):
        self.on_extra = handlers.cmd_start
    def dispatch(self, event, kind):
        getattr(self, "on_" + event)()
        getattr(self, "on_%s" % kind)()
        getattr(handlers, f"cmd_{event}")()
        getattr(self, converted(event).lower())()
        getattr(handlers, converted(kind).upper().lower())()
def converted(kind):
    return "ON_" + kind
def late(self): pass
Handler.on_late = late
Handler.On_Mixed = late
def first():
    Handler().dispatch(second(), None)
def second():
    return "close"
