def beep():
    pass


def flash():
    pass


class Alarm:
    def configure(self):
        self.signal = beep

    def trigger(self):
        self.signal()


alarm = Alarm()
alarm.configure()
alarm.trigger()
alarm.extra = flash
alarm.extra()
