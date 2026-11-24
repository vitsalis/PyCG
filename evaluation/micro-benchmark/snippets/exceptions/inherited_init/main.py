class ConfigError(Exception):
    pass


def load():
    raise ConfigError("missing key")


try:
    load()
except ConfigError:
    pass
