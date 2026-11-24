import sched

def clock():
    return 0

def wait(seconds):
    pass

def action():
    pass

scheduler = sched.scheduler(clock, wait)
scheduler.enter(0, 1, action)
scheduler.run()
