import functools


def load():
    return [1]


class Report:
    @functools.cached_property
    def data(self):
        return load()


report = Report()
report.data
report.data
