class A:
    def act(self):
        pass

class B:
    def act(self):
        pass

def run(f):
    f()

b = B()
run(A().act)
