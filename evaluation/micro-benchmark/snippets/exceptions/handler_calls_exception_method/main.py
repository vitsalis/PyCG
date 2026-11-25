class AppError(Exception):
    def report(self):
        pass


class DbError(AppError):
    def report(self):
        pass


class NetError(AppError):
    def report(self):
        pass


def query():
    raise DbError


try:
    query()
except AppError as error:
    error.report()
