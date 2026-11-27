
class Base:
    def run(self):
        s = super()
class Other:
    pass
Base.run(Other())
