
import requests
with requests.Session() as session:
    session.get("https://example.org").json()
