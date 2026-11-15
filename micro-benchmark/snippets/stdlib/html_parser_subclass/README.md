`HTMLParser.feed` calls the method `handle_starttag` of a subclass. The input has no comment, so the parser does not call `handle_comment`.
There is no edge to `main.LinkParser.handle_comment`.
