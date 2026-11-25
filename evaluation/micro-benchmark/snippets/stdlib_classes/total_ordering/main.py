import functools


@functools.total_ordering
class Version:
    def __init__(self, number):
        self.number = number

    def __eq__(self, other):
        return self.number == other.number

    def __lt__(self, other):
        return self.number < other.number


Version(2) > Version(1)
