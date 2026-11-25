class Peek:
    def __init__(self):
        self.left = 2

    def __iter__(self):
        return self

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return self.left


class Job:
    def __init__(self):
        self.done = False

    def run(self):
        self.done = True


def drain(numbers):
    for number in numbers:
        pass


def work(job):
    if job is not None:
        job.run()
