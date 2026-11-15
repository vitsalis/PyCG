class Money:
    def __format__(self, spec):
        return "1.00"

message = format(Money(), "x")
