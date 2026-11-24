import operator

class Task:
    def run(self, times):
        pass

    def skip(self):
        pass

call_run = operator.methodcaller("run", 1)
call_run(Task())
