import functools


class Logger:
    def log(self, level, message):
        pass


logger = Logger()
warn = functools.partial(logger.log, "warning")
warn("disk full")
