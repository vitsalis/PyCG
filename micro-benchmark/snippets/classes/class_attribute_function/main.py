def describe(owner):
    pass


class Widget:
    show = describe
    scale = lambda self, factor: factor * 2


Widget.show(None)
widget = Widget()
widget.show()
widget.scale(3)
