def audit():
    pass


def deny():
    pass


def check():
    raise PermissionError("denied")
    audit()


def request():
    try:
        check()
    except PermissionError:
        deny()


request()
