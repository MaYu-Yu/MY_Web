import random
def get_random():
    temp = [i for i in range(1, 10000)]
    random.shuffle(temp)
    for i in temp:
        yield str(i)