import operator

class Task:
    def run(self):
        pass

    def skip(self):
        pass

get_run = operator.attrgetter("run")
get_run(Task())()
