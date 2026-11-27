
def actual(): pass
def __getattr__(name):
    return actual
globals()
if False:
    def absent(): pass
