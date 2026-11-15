class Button:
    pass

def on_click():
    pass

button = Button()
setattr(button, "callback", on_click)
button.callback()
