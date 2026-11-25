import ext

def get_client():
    return ext.connect()

get_client().send()
