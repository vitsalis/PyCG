import sys


def log(message, stream=sys.stderr):
    stream.write(message)


sys.stdout.write("started\n")
log("done\n")
