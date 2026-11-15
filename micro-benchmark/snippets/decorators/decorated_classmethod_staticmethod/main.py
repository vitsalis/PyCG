def traced(func):
    def wrapper(*args):
        return func(*args)

    return wrapper


class Tool:
    @classmethod
    @traced
    def build(cls):
        pass

    @traced
    @staticmethod
    def helper():
        pass


Tool.build()
Tool.helper()
