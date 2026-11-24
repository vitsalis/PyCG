class Report:
    def render(self):
        return self.header()


def header(self):
    pass


Report.header = header
Report().render()
