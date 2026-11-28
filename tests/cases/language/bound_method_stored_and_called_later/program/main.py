
class Greeter:
    def greet(self):
        self.helper()
    def helper(self): pass
def keep(callback):
    return callback
saved = keep(Greeter().greet)
saved()
