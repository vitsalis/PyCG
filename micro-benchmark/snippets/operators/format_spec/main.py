class Money:
    def __format__(self, spec):
        return "1.00"

    def __str__(self):
        return "1"


money = Money()
text = f"{money:.2f}"
format(money, "x")
