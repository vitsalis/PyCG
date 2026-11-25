def lookup():
    return {}["missing"]


def on_value_error():
    pass


def on_key_error():
    pass


def on_lookup_error():
    pass


try:
    lookup()
except ValueError:
    on_value_error()
except KeyError:
    on_key_error()
except LookupError:
    on_lookup_error()
