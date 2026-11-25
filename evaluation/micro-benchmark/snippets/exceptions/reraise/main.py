def parse():
    raise ValueError("bad")


def log():
    pass


def recover():
    pass


def run():
    try:
        parse()
    except ValueError:
        log()
        raise


try:
    run()
except ValueError:
    recover()
