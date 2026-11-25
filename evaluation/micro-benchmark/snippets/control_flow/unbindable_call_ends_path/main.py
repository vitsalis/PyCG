def warn(major, minor, cause, fix):
    return None


def cleanup():
    return None


def start():
    warn(0, 13, "unsupported")
    cleanup()


try:
    start()
except TypeError:
    pass
