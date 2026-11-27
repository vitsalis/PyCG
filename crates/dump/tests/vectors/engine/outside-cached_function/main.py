from urllib.parse import urlsplit

parts = urlsplit("https://example.org/path")
parts.geturl()
