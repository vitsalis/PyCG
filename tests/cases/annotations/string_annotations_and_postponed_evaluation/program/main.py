from __future__ import annotations

class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

def postponed(s: Strategy):
    s(1)
def quoted(s: "Strategy | None"):
    s(1)
def nested(s: "list['Strategy']"):
    for each in s:
        each(1)
