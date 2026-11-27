class Seq:
    def __len__(self): return 0
match Seq():
    case []:
        pass
