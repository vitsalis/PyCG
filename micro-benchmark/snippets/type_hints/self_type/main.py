from typing import Self


class Builder:
    def step(self) -> Self:
        return self

    def build(self):
        pass


class FancyBuilder(Builder):
    def build(self):
        pass


FancyBuilder().step().build()
