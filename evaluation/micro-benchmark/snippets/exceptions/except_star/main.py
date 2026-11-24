def on_value():
    pass


def on_type():
    pass


def on_key():
    pass


def run():
    raise ExceptionGroup("batch", [ValueError("a"), TypeError("b")])


try:
    run()
except* ValueError:
    on_value()
except* TypeError:
    on_type()
except* KeyError:
    on_key()
