import mailer

def fake_send():
    pass

mailer.send = fake_send
mailer.notify()
