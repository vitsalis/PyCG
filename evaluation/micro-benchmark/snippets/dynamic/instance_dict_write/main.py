class Widget:
    def render(self):
        pass

def custom_render():
    pass

widget = Widget()
widget.__dict__["render"] = custom_render
widget.render()
