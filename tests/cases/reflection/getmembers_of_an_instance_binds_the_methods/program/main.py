
import inspect
class A:
    def __init__(self, action):
        self.action = action
    def method(self): pass
def action(): pass
def run():
    for name, member in inspect.getmembers(A(action)):
        member()
run()
