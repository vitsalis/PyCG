import html.parser

def record(item):
    pass

class LinkParser(html.parser.HTMLParser):
    def handle_starttag(self, tag, attrs):
        record(tag)

    def handle_comment(self, data):
        pass

LinkParser().feed("<a href='x'>link</a>")
