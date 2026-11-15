def prepare():
    return 1


def release():
    pass


def never():
    pass


def compute():
    try:
        return prepare()
    finally:
        release()
    never()


compute()
