
import ext
def f(): pass
def g(): pass

class Plain:
    def __init__(self):
        super().__init__()
        super().missing()
Plain()
