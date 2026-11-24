class property:
    def __init__(self, fget):
        self.fget = fget


class cached(property):
    pass


class Page:
    @cached
    def title(self):
        return "t"


page = Page()
page.title
