class Point:
    def __new__(cls, x):
        return super().__new__(cls)

    def __init__(self, x):
        self.x = x


Point(1)
