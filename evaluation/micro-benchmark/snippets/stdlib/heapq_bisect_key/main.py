import bisect
import heapq

def priority(task):
    return task[0]

heapq.nsmallest(1, [(2, "b"), (1, "a")], key=priority)
bisect.bisect([(1, "a")], 1, key=priority)
