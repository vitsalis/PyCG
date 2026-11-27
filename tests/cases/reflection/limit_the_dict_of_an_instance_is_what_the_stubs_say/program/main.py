
class Job:
    def __init__(self, action):
        self.action = action
    def run(self): pass
def build(): pass
def by_values():
    for value in Job(build).__dict__.values():
        value()
def by_vars():
    vars(Job(build))["action"]()
def of_the_class():
    vars(Job)["run"](Job(build))
by_values()
by_vars()
of_the_class()
