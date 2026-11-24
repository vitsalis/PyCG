class AppError(Exception):
    def __init__(self, code):
        super().__init__(f"code {code}")
        self.code = code


try:
    raise AppError(3)
except AppError:
    pass
