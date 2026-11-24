import functools


def load():
    return [1]


class lazy(functools.cached_property):
    pass


class Report:
    @lazy
    def data(self):
        return load()


def show(report):
    return report.data


show(Report())
