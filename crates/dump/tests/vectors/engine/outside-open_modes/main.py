def opened(mode):
    return open("data", mode)


text = open("data")
text.read()
binary = open("data", "rb")
binary.read()
raw = open("data", "rb", buffering=0)
raw.read()
chosen = open("data", "w", 1)
chosen.write("line")
unknown = opened(None)
