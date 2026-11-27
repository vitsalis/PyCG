a = 'plain', "double", '''triple
line''', """dq"""
b = '\n\t\\\'\"\a\b\f\v\r', '\0\7\77\777\1234', '\x41\x7f\xff'
c = 'é\U0001F600\N{BULLET}\N{LATIN SMALL LETTER E WITH ACUTE}', '𐏿'
d = '\d\8\9\%', 'a\
b', r'raw\n\x41\N{X}', R"\""
e = 'con' "cat" '''ena''' r'\tion'
f = b'bytes', b'\x00\xff\n\\', b'\777\400\1', br'\x41', b'\N{X}\u1234', b'a' b'b'
g = 'é', 'ü€😀', u'u-prefix'
h = '', '\ud800\udfff', '\U0000d800'
