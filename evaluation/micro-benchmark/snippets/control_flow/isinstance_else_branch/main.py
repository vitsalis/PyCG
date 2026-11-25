class Text:
    def render(self):
        return "text"


class Image:
    def render(self):
        return "image"


def show(item):
    if not isinstance(item, Text):
        return item.render()
    return "plain"


show(Text())
show(Image())
