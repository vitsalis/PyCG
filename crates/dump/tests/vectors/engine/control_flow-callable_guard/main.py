class Job:
    def __call__(self):
        return 1

    def describe(self):
        return "job"


class Note:
    def describe(self):
        return "note"


def run(item):
    if callable(item):
        return item.describe()
    return None


def show(item):
    if not callable(item):
        return item.describe()
    return None


for item in (Job(), Note()):
    run(item)
    show(item)
