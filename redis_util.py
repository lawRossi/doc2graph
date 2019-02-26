import redis

r = redis.Redis()

NEIGHBOUR = "NEIGHBOUR"
RELATION = "RELATION"
NIL = "_NIL_"
HEADS = "HEADS"
TAILS = "TAILS"


def cache_neighbours(uri, neighours):
    key = NEIGHBOUR+uri
    if neighours:
        r.sadd(key, *neighours)
    else:
        r.sadd(key, NIL)


def get_cached_neighbours(uri):
    neighbours = [item.decode("utf-8") for item in r.smembers(NEIGHBOUR+uri)]
    if not neighbours:
        return neighbours
    if neighbours[0] == NIL:
        return None
    return neighbours


def cache_relations(uri1, uri2, relations):
    key = NEIGHBOUR+uri1+"-"+uri2
    if relations:
        r.sadd(key, *relations)
    else:
        r.sadd(key, NIL)


def get_cached_relations(uri1, uri2):
    relations = [item.decode("utf-8") for item in r.smembers(NEIGHBOUR+uri1+"-"+uri2)]
    if not relations:
        return relations
    if relations[0] == NIL:
        return None
    return relations


def cache_relation_heads(relation, tail, heads):
    key = HEADS + relation + "-" + tail
    r.sadd(key, *heads)


def get_cached_relation_heads(relation, tail):
    key = HEADS + relation + "-" + tail
    heads = [item.decode("utf-8") for item in r.smembers(key)]
    return heads


def cache_relation_tails(relation, head, tails):
    key = TAILS + relation + "-" + head
    r.sadd(key, *tails)


def get_cached_relation_tails(relation, head):
    key = TAILS + relation + "-" + head
    tails = [item.decode("utf-8") for item in r.smembers(key)]
    return tails


if __name__ == "__main__":
    for key in r.keys("NEIGHBOUR*"):
        r.delete(key)
