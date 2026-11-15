def compute():
    return 1


class Settings:
    value = compute()


def build():
    class Local:
        size = compute()

    return Local


build()
