class Outer:
    class Inner:
        def __init__(self):
            pass

        def work(self):
            pass

    def make(self):
        return self.Inner()


Outer().make().work()
