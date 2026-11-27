
import requests
session = requests.Session()
session.get_redirect_target(session.get("u"))
session.get("u").headers.get("Content-Type")
class Client(requests.Session):
    pass
Client().get("u")
