class Modulus:
    def __rpow__(self, base, mod=None):
        return 0

pow(2, Modulus(), 5)
