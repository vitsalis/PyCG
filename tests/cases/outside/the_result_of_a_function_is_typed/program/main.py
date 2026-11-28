
import requests
r = requests.get("https://example.org")
r.json()
r.raise_for_status()
