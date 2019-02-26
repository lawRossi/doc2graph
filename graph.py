import data
from datastructure import Node, Graph
import random
import networkx as nx
from entity_linking import annotate
import pickle
from itertools import combinations
from itertools import chain
from tuple_extraction import Tuple
import numpy as np
import sklearn.preprocessing as pp
from dbpedia_util import semantic_relatedness
from collections import defaultdict
from evaluate import load


def annotate_tuple(tuple, mention_entities, nes):
    annotate_element(tuple.subject, mention_entities, nes)
    if tuple.direct_object:
        annotate_element(tuple.direct_object, mention_entities, nes)
    if tuple.indirect_object:
        annotate_element(tuple.indirect_object, mention_entities, nes)
    if tuple.adverbial:
        for item in tuple.adverbial:
            annotate_element(item, mention_entities, nes)


def annotate_element(element, mention_entities, nes):
    word = element.word
    if pronoun_type(word) is None:
        if word in mention_entities:
            element.entity = mention_entities[word]
        elif word.startswith("the") or word.startswith("The"):
            word_ = word[3:].strip()
            if word_ in mention_entities:
                element.entity = mention_entities[word_]
        if word in nes:
            element.ne_type = nes[word]

        elif word.startswith("the") or word.startswith("The"):
            word_ = word[3:].strip()
            if word_ in nes:
                element.ne_type = nes[word_]


def pronoun_type(word):
    if word.lower() in ["he", "him", "his", "she", "her"]:
        return "PERSON"
    elif word.lower() in ["it", "its"]:
        return "OTHER"
    else:
        return None


def annotate_documents(documents, save_path):
    annotated_docs = []
    for i, document in enumerate(documents):
        print(i)
        sentences = [sent for sent, _ in document]
        doc = annotate(sentences, 0.05)
        annotated_docs.append(doc)
    with open(save_path, "wb") as fo:
        pickle.dump(annotated_docs, fo)


def derive_first_level_graph(graph):
    nodes = graph.nodes()
    first_level_nodes = []
    for node in nodes:
        if nodes[node]["type"] == Node.Noun and nodes[node]["name"] not in first_level_nodes:
                first_level_nodes.append(nodes[node]["name"])
        elif nodes[node]["type"] == Node.PREDICATE and node not in first_level_nodes:
            first_level_nodes.append(node)
    n = len(first_level_nodes)
    W = np.zeros((n, n))
    v = np.zeros((n, 1))
    for i, node in enumerate(first_level_nodes):
        v[i, 0] = 1

    for node in nodes:
        if nodes[node]["type"] == Node.PREDICATE:
            i = first_level_nodes.index(node)
            for child in graph.neighbors(node):
                if nodes[child]["type"] == Node.Noun:
                    j = first_level_nodes.index(nodes[child]["name"])
                    W[i, j] = W[j, i] = 1
    W = pp.normalize(W, axis=0, norm="l1")
    return first_level_nodes, v, W


def derive_second_level_graph(graph):
    nodes = graph.nodes()
    nouns = []
    noun_candidates = defaultdict(list)
    for node in nodes:
        if nodes[node]["type"] == "Noun":
            candidates = [child for child in graph.neighbors(node) if nodes[child]["type"] == "Entity"]
            if candidates:
                noun = nodes[node]["name"]
                if noun not in nouns:
                    nouns.append(noun)
                if noun not in noun_candidates:
                    noun_candidates[noun].extend(candidates)
                else:  # merging candidates
                    for candidate in candidates:
                        if candidate not in noun_candidates[noun]:
                            noun_candidates[noun].append(candidate)
    enrolled_nodes = [noun for noun in nouns]
    enrolled_nodes.extend(chain.from_iterable(noun_candidates.values()))
    n = len(enrolled_nodes)
    W = np.zeros((n, n))
    for i, noun in enumerate(nouns):
        for candidate in noun_candidates[noun]:
            i = enrolled_nodes.index(noun)
            j = enrolled_nodes.index(candidate)
            W[j, i] = nodes[candidate]["value"]["finalScore"]

    for i, j in combinations(range(len(nouns)), 2):
        for cand1 in noun_candidates[nouns[i]]:
            for cand2 in noun_candidates[nouns[j]]:
                if cand1 != cand2:
                    idx1 = enrolled_nodes.index(cand1)
                    idx2 = enrolled_nodes.index(cand2)
                    uri1 = str(nodes[cand1]["value"]["uri"])
                    uri2 = str(nodes[cand2]["value"]["uri"])
                    W[idx1, idx2] = W[idx2, idx1] = semantic_relatedness(uri1, uri2)
    W = pp.normalize(W, axis=0, norm="l1")
    return nouns, noun_candidates, enrolled_nodes, W


def random_walk_with_restart(W, v, gamma):
    c = 1 - gamma
    I = np.identity(v.shape[0])
    r = gamma * np.linalg.inv(I - c * W).dot(v)
    return r


def score_tuple(graph, predicate, noun_nodes, v):
    score = 0
    n = 0
    for neighbor in graph.neighbors(predicate):
        if graph.nodes[neighbor]["type"] == Node.Noun:
            if neighbor in noun_nodes:
                score += v[noun_nodes.index(neighbor), 0]
                n += 1
    return score / n


def reconstruct_tuple(graph, predicate):
    tuple_ = Tuple()
    nodes = graph.nodes()
    tuple_.predicate = nodes[predicate]["value"]
    tuple_.adverbial = []
    for neighbor in graph.neighbors(predicate):
        if graph.edges[predicate, neighbor]["relation"] == "subj":
            tuple_.subject = nodes[neighbor]["value"]
        elif graph.edges[predicate, neighbor]["relation"] == "dobj":
            tuple_.direct_object = nodes[neighbor]["value"]
        elif graph.edges[predicate, neighbor]["relation"] == "iobj":
            tuple_.indirect_object = nodes[neighbor]["value"]
        else:
            tuple_.adverbial.append((nodes[neighbor]["value"]))

    return tuple_


def refine_graph(graph):
    removal = []
    for node in graph.nodes:
        if graph.nodes[node]["type"] == Node.PREDICATE:
            for neighbor in graph.neighbors(node):
                if graph.edges[node, neighbor]["relation"] == "subj":
                    break
            else:
                removal.append(node)
        else:
            predecessors = list(graph.predecessors(node))
            if not predecessors:
                removal.append(node)
            else:
                type_ = graph.nodes[predecessors[0]]["type"]
                if graph.nodes[node] == Node.Noun and type_ != Node.PREDICATE:
                    removal.append(node)
                elif graph.nodes[node] == Node.Entity and type_ != Node.Noun:
                    removal.append(node)
    for item in removal:
        graph.remove_node(item)


def collect_tuples(graph):
    tuples = []
    for node in graph.nodes:
        if graph.nodes[node]["type"] == Node.PREDICATE:
            tuple_ = reconstruct_tuple(graph, node)
            if tuple_.subject is not None:
                tuples.append(tuple_)
    return tuples


def get_collision_subgraph(graph):
    subgraph = nx.Graph()
    for u, v in graph.edges:
        if graph.edges[u, v]["relation"] == "collision":
            subgraph.add_edge(u, v)
    return subgraph


def get_maximal_indipendent_set(subgraph, weights, k=5):
    minimal_weight = 1.e-5
    maximal_set = None
    max_score = 0
    for i in range(k):
        subgraph_ = subgraph.copy()
        nodes = [node for node in subgraph_.nodes]
        independent_set = []
        while len(nodes) > 0:
            weights_ = [weights[node] if weights[node] > minimal_weight else minimal_weight for node in nodes]
            v = random.choices(nodes, weights_)[0]
            independent_set.append(v)
            removal = list(subgraph_.neighbors(v))
            for u in removal:
                subgraph_.remove_node(u)
            subgraph_.remove_node(v)
            nodes = [node for node in subgraph_.nodes]
        score = sum([weights[node] for node in independent_set])
        if score > max_score:
            max_score = score
            maximal_set = independent_set
    return maximal_set


def un_wrap_tuple(tuple_):
    t = Tuple()
    if isinstance(tuple_.subject, Node):
        t.subject = tuple_.subject.value
    else:
        t.subject = tuple_.subject
    if isinstance(tuple_.predicate, Node):
        t.predicate = tuple_.predicate.value
    else:
        t.predicate = tuple_.predicate
    if isinstance(tuple_.direct_object, Node):
        t.direct_object = tuple_.direct_object.value
    else:
        t.direct_object = tuple_.direct_object
    if isinstance(tuple_.indirect_object, Node):
        t.indirect_object = tuple_.indirect_object.value
    else:
        t.indirect_object = tuple_.indirect_object
    adverbial = []
    for item in tuple_.adverbial:
        if isinstance(item, Node):
            adverbial.append(item.value)
        else:
            adverbial.append(item)
    t.adverbial = adverbial
    return t


def annotate_graph(documents, annoated_docs_path, save_path, semantic_graph=True):
    with open(annoated_docs_path, "rb") as fi:
        annotated_docs = pickle.load(fi)
    graphs = []
    for i, document in enumerate(documents):
        all_tuples = []
        mention_entities, nes_list = annotated_docs[i]
        for (sent, tuples), nes in zip(document, nes_list):
            for tuple_ in tuples:
                annotate_tuple(tuple_, mention_entities, nes)
                tuple_.sentence = sent
            all_tuples.append(tuples)
        print(sum(map(len, all_tuples)))
        if semantic_graph:
            graph = Graph()
            graph.build_semantic_graph(all_tuples)
        else:
            graph = Graph(all_tuples)
        graphs.append(graph)

    with open(save_path, "wb") as fo:
        pickle.dump(graphs, fo)


def propagation(graph, gamma1=0.3, gamma2=0.1):
    first_level_nodes, v1, W1 = derive_first_level_graph(graph)
    nouns, noun_candidates, enrolled_nodeds, W2 = derive_second_level_graph(graph)
    v1 = v1 / v1.sum()
    r1 = random_walk_with_restart(W1, v1, gamma1)
    v1 = r1

    v2 = np.zeros((W2.shape[0], 1))
    for i, node in enumerate(first_level_nodes):
        if node in nouns:
            v2[nouns.index(node), 0] = v1[i, 0]
    v2 = v2 / v2.sum()
    r2 = random_walk_with_restart(W2, v2, gamma2)

    entity_mapping = {}
    for noun in nouns:
        max_score = 0
        for node in noun_candidates[noun]:
            score = r2[enrolled_nodeds.index(node), 0] * graph.nodes[node]["value"]["finalScore"]
            if score > max_score:
                max_score = score
                entity_mapping[noun] = node
        v1[first_level_nodes.index(noun)] *= max_score

    v1 = random_walk_with_restart(W1, v1, gamma1)

    return first_level_nodes, v1, entity_mapping


def join_optimize(documents, source_path, save_path, lambda1, lambda2, K, dump_graph=False):
    with open(source_path, "rb") as fi:
        graphs = pickle.load(fi)
    documents_ = []
    n = len(documents)
    for index in range(n):
        graph = graphs[index].graph
        first_level_nodes, v, entity_mapping = propagation(graph, lambda1, lambda2)
        subgraph = get_collision_subgraph(graph)
        weights = {}
        for node in subgraph.nodes():
            if graph.nodes[node]["type"] == Node.PREDICATE:
                weights[node] = v[first_level_nodes.index(node), 0]
            else:
                weights[node] = v[first_level_nodes.index(graph.nodes[node]["name"]), 0]
        independent_set = get_maximal_indipendent_set(subgraph, weights, K)
        for node in subgraph.nodes():
            if node not in independent_set:
                if not graph.has_node(node):
                    continue
                if graph.nodes[node]["type"] == Node.PREDICATE:
                    graph.remove_node(node)
                else:
                    predecessors = list(graph.predecessors(node))
                    if predecessors:
                        graph.remove_node(predecessors[0])
                    graph.remove_node(node)
        for node in graph.nodes():
            if graph.nodes[node]["type"] == Node.Noun:
                name = graph.nodes[node]["name"]
                if name not in entity_mapping:
                    continue
                entity = entity_mapping[name]
                for child in list(graph.neighbors(node)):
                    if graph.nodes[child]["type"] == Node.Entity and child != entity:
                        graph.remove_edge(node, child)
        graphs[index].merge_triples()
        refine_graph(graph)
        tuples = collect_tuples(graph)
        sentence_tuples = defaultdict(list)
        for tuple_ in tuples:
            tuple_ = un_wrap_tuple(tuple_)
            sentence_tuples[tuple_.predicate.sentence].append(tuple_)
        document = documents[index]
        sentences = [sentence for sentence, _ in document]
        document_ = []
        for sentence in sentences:
            tuples = sentence_tuples.get(sentence)
            if tuples is None:
                tuples = []
            document_.append((sentence, tuples))
        documents_.append(document_)

    if not dump_graph:
        with open(save_path, "w", encoding="utf-8") as fo:
            for document in documents_:
                for sentence, tuples in document:
                    fo.write(sentence + "\n")
                    for tuple_ in tuples:
                        raw_tuple = tuple_.to_str()
                        fo.write(raw_tuple+"\n")
                    fo.write("\n")
                fo.write("======================\n")
    else:
        with open(save_path, "wb") as fo:
            pickle.dump(graphs, fo)


if __name__ == "__main__":
    # documents = load("data/tuples_refined.txt")
    # annotate_graph(documents, "data/annotated_docs.txt", "data/graph1.pkl", semantic_graph=False)

    with open("data/graph1.pkl", "rb") as fi:
        graphs = pickle.load(fi)
    data.write_graph_to_neo4j(graphs[1])

    # documents_ = []
    # for index in range(11):
    #     print(index)
    #     graph = graphs[index].graph
    #     noun_nodes, v = propagation2(graph, 0.5, 0.1)
    #     print("??")
    #     subgraph = get_collision_subgraph(graph)
    #     weights = {}
    #     for node in subgraph.nodes():
    #         weights[node] = v[noun_nodes.index(graph.nodes[node]["name"]), 0]
    #     independent_set = get_maximal_indipendent_set(subgraph, weights, 11)
    #     for node in subgraph.nodes():
    #         if node not in independent_set:
    #             graph.remove_node(node)
    #
    #     tuples = collect_tuples(graph)
    #     document = documents[index]
    #     sentences = [sentence for sentence, _ in document]
    #     sentence_tuples = defaultdict(list)
    #     for tuple_ in tuples:
    #         sentence_tuples[sentences[tuple_.predicate.sentence_index]].append(un_wrap_tuple(tuple_))
    #     document_ = [(sentence, sentence_tuples[sentence]) for sentence in sentences]
    #     documents_.append(document_)
    #
    # with open("data/tuples_refined.txt", "w", encoding="utf-8") as fo:
    #     for document in documents_:
    #         for sentence, tuples in document:
    #             fo.write(sentence + "\n")
    #             for tuple_ in tuples:
    #                 raw_tuple = tuple_.to_str()
    #                 fo.write(raw_tuple+"\n")
    #             fo.write("\n")
    #         fo.write("======================\n")

    # documents = load("data/tuples_refined.txt")
    # tuples_list = [tuples for _, tuples in documents[0]]
    # graph = Graph(tuples_list,True)
    # write_graph_to_neo4j(graph)
