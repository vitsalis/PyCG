class Widget:
    def render(self):
        pass

def custom_render():
    pass

widget = Widget()
widget.render = custom_render
widget.render()
delattr(widget, "render")
widget.render()
