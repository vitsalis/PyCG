def by_age(person):
    return person[1]

def by_name(person):
    return person[0]

def youngest(people):
    return min(people, key=by_age)

def last_by_name(people):
    return max(people, key=by_name)

people = [("ann", 3), ("bob", 1)]
youngest(people)
last_by_name(people)
