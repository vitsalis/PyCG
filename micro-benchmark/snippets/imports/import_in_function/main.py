def load():
    import plugin
    plugin.activate()

def run():
    from plugin import deactivate
    deactivate()

load()
run()
