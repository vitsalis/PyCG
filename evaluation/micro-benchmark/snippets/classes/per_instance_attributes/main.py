def save():
    pass


def load():
    pass


class Button:
    def __init__(self, action):
        self.action = action

    def click(self):
        self.action()


save_button = Button(save)
load_button = Button(load)
save_button.click()
