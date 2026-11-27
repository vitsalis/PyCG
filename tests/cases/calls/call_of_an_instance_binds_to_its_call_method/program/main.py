
class Handler:
    def __call__(self, event): pass
def fire(handler):
    handler()
fire(Handler())
