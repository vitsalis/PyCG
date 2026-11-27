
class Thing:
    def run(self): pass
def __getattr__(name):
    return Thing
