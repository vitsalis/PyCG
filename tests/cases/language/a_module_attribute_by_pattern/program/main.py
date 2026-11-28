
import commands
def run(name):
    getattr(commands, "cmd_" + name)()
