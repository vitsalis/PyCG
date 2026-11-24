from typing import NewType

UserId = NewType("UserId", int)


def lookup(user_id: UserId) -> None:
    pass


lookup(UserId(5))
