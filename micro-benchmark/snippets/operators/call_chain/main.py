class Second:
    def __call__(self):
        pass


class First:
    def __call__(self):
        return Second()


First()()()
