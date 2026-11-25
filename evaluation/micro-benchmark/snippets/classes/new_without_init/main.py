class Token:
    def __new__(cls, value):
        instance = super().__new__(cls)
        instance.value = value
        return instance

    def text(self):
        return str(self.value)


Token(3).text()
