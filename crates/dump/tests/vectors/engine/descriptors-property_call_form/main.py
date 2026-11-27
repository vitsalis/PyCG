class Temperature:
    def __init__(self):
        self._celsius = 0

    def get_celsius(self):
        return self._celsius

    def set_celsius(self, value):
        self._celsius = value

    def del_celsius(self):
        self._celsius = 0

    celsius = property(get_celsius, set_celsius, del_celsius)


temperature = Temperature()
temperature.celsius = 20
temperature.celsius
