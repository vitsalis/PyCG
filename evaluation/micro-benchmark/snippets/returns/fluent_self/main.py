def func1():
    pass

def func2():
    pass

class Pipeline:
    def __init__(self):
        self.steps = []

    def add(self, step):
        self.steps.append(step)
        return self

    def run(self):
        for step in self.steps:
            step()

Pipeline().add(func1).add(func2).run()
