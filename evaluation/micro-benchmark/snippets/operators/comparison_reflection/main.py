class Version:
    def __lt__(self, other):
        return True

    def __gt__(self, other):
        return False


class Release:
    pass


Release() > Version()
