
class Handler:
    def on_open(self):
        return "open"

    def ON_CLOSE(self):
        return "close"


def dispatch(handler, event):
    lowered = ("ON_" + event).lower()
    raised = ("on_" + event).upper()
    getattr(handler, lowered)()
    getattr(handler, raised)()


dispatch(Handler(), "open")
