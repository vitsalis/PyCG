class Formatter:
    def clean(text):
        return text.strip()

    clean = staticmethod(clean)

    def run(self, text):
        return self.clean(text)


Formatter.clean(" a ")
Formatter().run(" b ")
