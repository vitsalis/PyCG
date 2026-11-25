def risky():
    raise ValueError("bad")


def safe():
    pass


def on_risky_error():
    pass


def after_risky():
    pass


def on_safe_error():
    pass


def after_safe():
    pass


def cleanup():
    pass


try:
    risky()
except ValueError:
    on_risky_error()
else:
    after_risky()
finally:
    cleanup()

try:
    safe()
except ValueError:
    on_safe_error()
else:
    after_safe()
finally:
    cleanup()
