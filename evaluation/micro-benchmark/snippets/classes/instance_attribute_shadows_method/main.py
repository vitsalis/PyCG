def quiet():
    pass


class Speaker:
    def speak(self):
        pass


loud = Speaker()
muted = Speaker()
muted.speak = quiet
muted.speak()
