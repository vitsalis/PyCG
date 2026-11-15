from dataclasses import dataclass


class Part:
    def __init__(self, number):
        self.number = number

    def __eq__(self, other):
        return self.number == other.number

    def __lt__(self, other):
        return self.number < other.number


@dataclass(order=True)
class Version:
    part: Part


sorted([Version(Part(2)), Version(Part(1))])
