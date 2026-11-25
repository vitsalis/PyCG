class Task:
    def ready(self):
        return True

    def run(self):
        pass


def is_ready(task):
    return task.ready()


for task in filter(is_ready, [Task()]):
    task.run()
