class Job:
    def __init__(self, action):
        self.action = action

def build():
    pass

vars(Job(build))["action"]()
