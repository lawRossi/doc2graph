import spotlight
from collections import defaultdict
from SPARQLWrapper import SPARQLWrapper, JSON
from redis_util import get_cached_neighbours, cache_neighbours, get_cached_relations, cache_relations
from redis_util import get_cached_relation_heads, cache_relation_heads
from redis_util import get_cached_relation_tails, cache_relation_tails


base_url = "http://model.dbpedia-spotlight.org/en/"
# base_url = "https://api.dbpedia-spotlight.org/en/"
# base_url = "http://116.56.143.18:2222/rest/"


def annotate(text, confidence=0.4):
    try:
        annotations = spotlight.annotate(base_url+"annotate", text, confidence=confidence)
        mention_entity = {}
        for annotation in annotations:
            mention_entity[annotation["surfaceForm"]] = annotation
        return mention_entity
    except:
        return {}


def candidates(text, confidence=0.1):
    try:
        print(text)
        annotations = spotlight.candidates(base_url+"candidates", text, confidence=confidence)
        mention_candidates = defaultdict(list)
        for annotation in annotations:
            name = annotation["name"]
            if name not in mention_candidates:
                resource = annotation["resource"]
                if isinstance(resource, list):
                    mention_candidates[name] = resource
                else:
                    mention_candidates[name] = [resource]
            else:
                uris = [resource["uri"] for resource in mention_candidates[name]]
                resource = annotation["resource"]
                if not isinstance(resource, list):
                    resource = [resource]
                for item in resource:
                    if item["uri"] not in uris:
                        mention_candidates[name].append(item)
        return mention_candidates
    except spotlight.SpotlightException:
        return {}


def dbpediauri2wikipageid(uri):
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
        SELECT ?page_id
        WHERE {<http://dbpedia.org/resource/%s> dbo:wikiPageID ?page_id}
    """ % uri)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    result = results["results"]["bindings"][0]
    page_id = result["page_id"]["value"]
    wikipedia_urlprefix = "https://en.wikipedia.org/?curid="
    return wikipedia_urlprefix + page_id


def get_neighbour(uri):
    neighbours = get_cached_neighbours(uri)
    if neighbours is None:
        return []
    if neighbours:
        return neighbours
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
            SELECT ?neighbour
            WHERE {
                {
                <http://dbpedia.org/resource/%s> ?relation ?neighbour .
                ?neighbour rdf:type <http://www.w3.org/2002/07/owl#Thing> .
                } UNION
                {
                ?neighbour ?relation <http://dbpedia.org/resource/%s> .
                ?neighbour rdf:type <http://www.w3.org/2002/07/owl#Thing> .
                }
            }
        """ % (uri, uri))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    neighbours = [result["neighbour"]["value"] for result in results["results"]["bindings"]]
    index = len("http://dbpedia.org/resource/")
    neighbours = [neighbour[index:] for neighbour in neighbours]
    cache_neighbours(uri, neighbours)
    return neighbours


def get_relations(uri1, uri2):
    relations = get_cached_relations(uri1, uri2)
    if relations is None:
        return []
    if relations:
        return relations
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
                SELECT ?relation
                WHERE {
                    <http://dbpedia.org/resource/%s> ?relation <http://dbpedia.org/resource/%s> .
                }
            """ % (uri1, uri2))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    relations = [result["relation"]["value"] for result in results["results"]["bindings"]]
    cache_relations(uri1, uri2, relations)
    return relations


def get_relation_heads(relation, uri):
    heads = get_cached_relation_heads(relation, uri)
    if heads:
        return heads
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
                    SELECT ?head
                    WHERE {
                        ?head <%s> <http://dbpedia.org/resource/%s> .
                    }
                """ % (relation, uri))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    heads = [result["head"]["value"] for result in results["results"]["bindings"]]
    index = len("http://dbpedia.org/resource/")
    heads = [head[index:] for head in heads]
    cache_relation_heads(relation, uri, heads)
    return heads


def get_relation_tails(relation, uri):
    tails = get_cached_relation_tails(relation, uri)
    if tails:
        return tails
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
                        SELECT ?tail
                        WHERE {
                             <http://dbpedia.org/resource/%s> <%s> ?tail .
                        }
                    """ % (uri, relation))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    tails = [result["tail"]["value"] for result in results["results"]["bindings"]]
    index = len("http://dbpedia.org/resource/")
    tails = [tail[index:] for tail in tails]
    cache_relation_tails(relation, uri, tails)
    return tails


def get_path_count(uri1, uri2):
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setQuery("""
                    SELECT (count(?mid) as ?length)
                    WHERE {
                        {
                         <http://dbpedia.org/resource/%s> ?rel1 ?mid .
                         ?mid ?rel2 <http://dbpedia.org/resource/%s> .
                         } UNION
                         {
                         <http://dbpedia.org/resource/%s> ?rel3 ?mid .
                         ?mid ?rel4 <http://dbpedia.org/resource/%s> .
                         }
                    }
                """ % (uri1, uri2, uri2, uri1))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    length = [result["length"]["value"] for result in results["results"]["bindings"]][0]
    return length


def semantic_relatedness(uri1, uri2):
    relations1 = get_relations(uri1, uri2)
    relatedness1 = 0
    for relation in relations1:
        heads = get_relation_heads(relation, uri2)
        tails = get_relation_tails(relation, uri1)
        relatedness1 += 2 / (len(heads) + len(tails))

    relations2 = get_relations(uri2, uri1)
    relatedness2 = 0
    for relation in relations2:
        heads = get_relation_heads(relation, uri1)
        tails = get_relation_tails(relation, uri2)
        relatedness2 += 2 / (len(heads) + len(tails))
    return max(relatedness1, relatedness2)


if __name__ == "__main__":
    text = """
    Observances traditionally take place from the evening preceding the first day of the year to the Lantern Festival, held on the 15th day of the year.
    """
    # print(annotate(text))
    # mention_candidates = candidates(text, 0.1)
    # for name in mention_candidates:
    #     print(name, " ".join([item["uri"] for item in mention_candidates[name]]))

    # print(dbpediauri2wikipageid("Alt-Berlin"))
    # print(get_neighbour("Alt-Berlin"))
    # for relation in get_relations("Alt-Berlin", "Berlin"):
    #     print(get_relation_heads(relation, "Berlin"))
    #     print(get_relation_tails(relation, "Alt-Berlin"))
    # print(semantic_relatedness("Alt-Berlin", "Berlin"))
    # print(get_relations("Chinese_New_Year", "Korean_New_Year"))
    print(get_path_count("Berlin", "Germany"))

