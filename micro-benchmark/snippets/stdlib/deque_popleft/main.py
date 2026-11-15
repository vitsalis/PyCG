from collections import deque


def func1():
    pass


def func2():
    pass


queue = deque()
queue.append(func1)
queue.appendleft(func2)
while queue:
    queue.popleft()()
