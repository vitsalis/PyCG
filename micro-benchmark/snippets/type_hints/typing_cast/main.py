from typing import cast


class Base:
    def run(self):
        pass


class Impl(Base):
    def run(self):
        pass


def execute(obj: object) -> None:
    cast(Base, obj).run()


execute(Impl())
