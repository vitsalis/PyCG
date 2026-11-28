from inspect import iscoroutine


class Result:
    def close(self):
        return None


async def compute():
    return 1


def release(value):
    if iscoroutine(value):
        value.close()


release(compute())
release(Result())
