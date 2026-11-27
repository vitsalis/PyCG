class Meta:
    pass


class B(metaclass=Meta):
    def method(self):
        pass


vars(B)["method"](B())
