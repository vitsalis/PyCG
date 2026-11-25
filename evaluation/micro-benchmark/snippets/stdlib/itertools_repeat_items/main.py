import itertools


class Task:
    def run(self):
        pass


for task in itertools.repeat(Task(), 2):
    task.run()
