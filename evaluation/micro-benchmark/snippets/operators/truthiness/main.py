class Flag:
    def __bool__(self):
        return False

    def __len__(self):
        return 1


class Queue:
    def __len__(self):
        return 0


if Flag():
    pass

if not Queue():
    pass
