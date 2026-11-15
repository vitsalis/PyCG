from typing import Protocol


class Greeter(Protocol):
    def greet(self) -> str: ...


class English:
    def greet(self) -> str:
        return "hello"


class French:
    def greet(self) -> str:
        return "bonjour"


def welcome(greeter: Greeter) -> str:
    return greeter.greet()


welcome(English())
