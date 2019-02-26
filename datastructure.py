import networkx as nx
from copy import copy
from itertools import chain
import time
import re

TOKEN = "TOKEN"
NOUN = "NOUN"


class Token():
    def __init__(self, word, pos, idx, original_idx):
        self.word = word
        self.pos = pos
        self.idx = idx                    # the index in the current clause
        self.original_idx = original_idx  # original index in the sentence

    def __str__(self):
        return self.word

    def type(self):
        return TOKEN


class Phrase(Token):
    def __init__(self, tokens, head, in_edges, out_edges=None, type_=NOUN):
        word = " ".join([token.word for _, token in tokens])
        pos = head.pos
        idx = head.idx
        self.tokens = tokens
        self.head = head          # the head word of the phrase
        self.in_edges = in_edges  # edges in side the phrase
        self.out_edges = out_edges  # the edges that connects a word out of the phrase
        self.type_ = type_
        super().__init__(word, pos, idx, idx)

    def type(self):
        return self.type_


class SyntaxTree():
    def __init__(self, tokens, dependencies):
        self.graph = nx.DiGraph()
        self.parents = {}
        for dependencie in dependencies:
            gov, dep, rel = dependencie
            if rel == "ROOT" or rel == "root":
                self.root = dep
                self.parents[dep] = 0
            else:
                self.graph.add_edge(gov, dep, relation=rel)
                self.parents[dep] = gov
        self.word_count = len(tokens)
        self.words = {i+1: token for i, token in enumerate(tokens)}
        self.noun_phrases = []
        self.verb_phrases = []

    def get_conjunction(self, index):
        raise NotImplementedError

    def build_conjunction(self, conjunction):
        if len(conjunction) == 1:
            return [self.words[conjunction[0]]]
        elif len(conjunction) >= 2:
            start = min(conjunction)
            end = max(conjunction)
            return [self.words[idx] for idx in range(start, end+1) if idx in self.words]
        else:
            return []

    def children(self, parent):
        if self.graph.has_node(parent):
            return list(self.graph.neighbors(parent))
        return []

    def dependent_relation(self, gov, dep):
        if self.graph.has_edge(gov, dep):
            return self.graph.edges[gov, dep]["relation"]
        return None

    def out_going_relations(self, index):
        if index == 0 or not self.graph.has_node(index):
            return []
        relations = [self.dependent_relation(index, child) for child in self.children(index)]
        return relations

    def in_coming_relation(self, index):
        if not self.graph.has_node(index):
            return None
        if index == self.root:
            return "ROOT"
        if index not in self.parents or not self.graph.has_node(self.parents[index]):
            return None
        else:
            return self.dependent_relation(self.parents[index], index)

    def merge_noun_phrases(self, spans):
        """
        Merging noun phrases to a node.
        :param spans: a list of noun phrase span
        :return:
        """
        for span in spans:
            if len(span) > 1:
                head = self.get_phrase_head(span)  # getting head word of the phrase
                if not head:
                    continue
                min_ = min(span)
                max_ = max(span)
                # recording dependency edges in order to recover the syntax structure
                in_edges = []
                for item in range(min_, max_+1):
                    if item != head:
                        parent = self.parents[item]
                        in_edges.append((parent, item, self.dependent_relation(parent, item)))
                tokens = [(i, self.words[i]) for i in range(min_, max_+1)]  # tracking the original index of the tokens
                phrase = Phrase(tokens, self.words[head], in_edges)
                self.noun_phrases.append(phrase)
                self.shrink_nounphrase(phrase)

    def shrink_nounphrase(self, phrase):
        for idx, token in phrase.tokens:
            if token != phrase.head and self.graph.has_node(idx):
                self.graph.remove_node(idx)
                del self.words[idx]
                del self.parents[idx]
            elif token == phrase.head:
                self.words[idx] = phrase

    def stretch_nounphrases(self):
        for phrase in self.noun_phrases:
            for idx, token in phrase.tokens:
                self.words[idx] = token
            for edge in phrase.in_edges:
                self.graph.add_edge(edge[0], edge[1], relation=edge[2])
                self.parents[edge[1]] = edge[0]

    def get_phrase_head(self, span):
        min_ = min(span)
        max_ = max(span)
        span_range = range(min_, max_ + 1)
        head = None
        for item in span_range:
            if item not in self.parents:  # invalid, may be merged by verb phrase(eg. be the son of)
                return None
            if self.parents[item] not in span_range:
                if head is None:
                    head = item
                else:   # invalid, a phrase has only one head
                    return None
        return head

    def expand_nounphrase(self, span):
        yield NotImplementedError

    def shrink_nounphrases(self):
        for phrase in self.noun_phrases:
            self.shrink_nounphrase(phrase)

    def merge_verb_phrase(self, chunk):
        """
        Merging a verb phrase into a node
        """
        root = None
        min_ = min(chunk)
        max_ = max(chunk)
        span_range = range(min_, max_ + 1)
        nodes_with_outedges = []
        for item in span_range:
            if item not in self.parents:
                return
            if self.parents[item] not in span_range:
                if root is not None:  # invalid span
                    return
                root = item
            else:
                for child in self.children(item):
                    if child not in span_range:
                        nodes_with_outedges.append(item)
                        break
        if len(nodes_with_outedges) > 1:  # invalid phrase
            return
        # recording dependency edges in order to recover the syntax structure
        if nodes_with_outedges:
            node = nodes_with_outedges[0]
            for child in self.children(node):
                rel = self.dependent_relation(node, child)
                self.parents[child] = root
                self.graph.add_edge(root, child, relation=rel)
        tokens = [(i, self.words[i]) for i in range(min_, max_ + 1)]
        phrase = Phrase(tokens, self.words[root], None, None, "VERB")
        self.words[root] = phrase

    def get_subtree(self, index, exclusion=None):
        nodes = []
        unvisited = [index]
        while unvisited:
            node = unvisited.pop()
            if exclusion is not None and self.in_coming_relation(node) in exclusion:
                continue
            nodes.append(node)
            unvisited.extend(self.graph.neighbors(node))
        return nodes

    def get_subjects(self, index):
        subjects = self._get_subjects(index)
        if not subjects:
            if self.in_coming_relation(index) == "conj":
                subjects = self._get_subjects(self.parents[index])
        return subjects

    def _get_subjects(self, index):
        subjects = []
        if not self.graph.has_node(index):
            return subjects
        for child in self.graph.neighbors(index):
            rel = self.dependent_relation(index, child)
            if rel == "nsubj" or rel == "nsubjpass":
                subjects.append(child)
                subjects.extend(self.get_conjunction(child))
                break
        return subjects

    def get_objects(self, index):
        objects = []
        for child in self.graph.neighbors(index):
            if self.dependent_relation(index, child) == "dobj":
                objects.append(child)
                objects.extend(self.get_conjunction(child))
        return objects

    def delete_subtree(self, subtree, drop_following_comma=False):
        idxes = []
        for node in subtree:
            if node in self.words:
                if hasattr(self.words[node], "tokens"):
                    idxes.extend([token[1].idx + 1 for token in self.words[node].tokens])
                else:
                    idxes.append(self.words[node].idx + 1)
                del self.words[node]
                del self.parents[node]
                self.graph.remove_node(node)
        if not idxes:
            return
        start = min(idxes)
        idx = start - 1
        if idx in self.words and self.words[idx].word == ",":
            del self.words[idx]
            del self.parents[idx]
            self.graph.remove_node(idx)
        if drop_following_comma:
            end = max(idxes)
            idx = end + 1
            if idx in self.words and self.words[idx].word == ",":
                del self.words[idx]
                del self.parents[idx]
                self.graph.remove_node(idx)


class SpacySyntaxTree(SyntaxTree):
    def __init__(self, tokens, dependencies):
        super().__init__(tokens, dependencies)

    def get_conjunction(self, index):
        conjunctions = []
        while index is not None:
            for child in self.children(index):
                if self.dependent_relation(index, child) == "conj":
                    conjunctions.append(child)
                    index = child
                    break
            else:
                index = None
        return conjunctions


class SentenceBuilder():
    def __init__(self):
        self.syntaxtree_class = None

    def build(self, tokens, dependencies, merging_noun=True, merging_verb=False):
        """
        :param tokens:         the token list of the sentence
        :param dependencies:   the dependency parsing result of the sentence
        :param merging_noun:   indicate whether noun phrases are chunked
        :param merging_verb:   indicate whether verb phrases are chunked
        """
        tree = self.syntaxtree_class(tokens, dependencies)
        if merging_verb:  # chunk verb phrases
            self.chunk_verbs(tree)
        raw_sentence = " ".join(token.word for token in tokens)
        if merging_noun:  # chunk noun phrases
            chunks = list(self.chunk_nouns(raw_sentence))
            tree.merge_noun_phrases(chunks)
        return Sentence(raw_sentence, tree)

    def from_raw_senence(self, sentence, merging_noun=True, merging_verb=False):
        sentence = self.parse(sentence)[0]
        return self.from_parsing_result(sentence, merging_noun, merging_verb)

    def from_parsing_result(self, sentence, merging_noun=True, merging_verb=False):
        words = sentence["words"]
        pos_tags = sentence["pos_tags"]
        tokens = []
        for i, (word, pos) in enumerate(zip(words, pos_tags)):
            tokens.append(Token(word, pos, i, i))
        dependencies = sentence["dependencies"]
        return self.build(tokens, dependencies, merging_noun, merging_verb)

    def from_un_parsed_tokens(self, tokens, merging_noun=True, merging_verb=False, printing=False):
        sentence = " ".join([token.word for token in tokens])
        if printing:
            print(sentence)
        # flatten phrases
        tokens_ = []
        for i in range(len(tokens)):
            if isinstance(tokens[i], Phrase):
                for _, token in tokens[i].tokens:
                    tokens_.append(copy(token))
            else:
                tokens_.append(copy(tokens[i]))
        tokens = tokens_

        result = self.parse(sentence)
        sentence = result[0]
        for i, pos in enumerate(sentence["pos_tags"]):
            tokens[i].pos = pos  # reassign pos tag
            tokens[i].idx = i  # reassign the index in the current clause

        dependencies = sentence["dependencies"]
        if printing:
            print(dependencies)
        return self.build(tokens, dependencies, merging_noun, merging_verb)

    def parse(self, sentence):
        raise NotImplementedError

    def chunk_nouns(self, sentence):
        raise NotImplementedError

    def chunk_verbs(self, tree):
        raise NotImplementedError


class Sentence():
    def __init__(self, raw_sentence, tree):
        self.raw_sentence = raw_sentence
        self.tree = tree
        self.left = []
        self.right = []
        self.raw_tuples = []   # the extracted raw tuples

    def __str__(self):
        return self.raw_sentence

    def stretch_nounphrases(self):
        self.tree.stretch_nounphrases()

    def shrink_nounphrases(self):
        self.tree.shrink_nounphrases()

    def iter_subsentence(self):
        un_visited = [self]
        while un_visited:
            current = un_visited.pop(0)
            yield current
            un_visited.extend([item[1] for item in current.left])
            un_visited.extend([item[1] for item in current.right])

    def print_sentence(self):
        for item in self.left:
            print(item[0])
            item[1].print_sentence()
        print(self)
        for item in self.right:
            print(item[0])
            item[1].print_sentence()


class Tuple:
    def __init__(self):
        self.subject = None
        self.predicate = None
        self.direct_object = None
        self.indirect_object = None
        self.adverbial = []
        self.clause_type = None
        self.negation = False

    def to_word(self, element, with_index=False):
        if not element:
            return ""
        word = element.word
        if element.prep:
            word = element.prep + " " + word
        if not with_index:
            return word
        return " ".join("%s|%d" % (w, idx) for w, idx in zip(word.split(" "), element.word_index))

    def to_dict(self):
        d = {
            "subject": str(self.subject),
            "predicate": str(self.predicate),
            "direct_object": str(self.direct_object) if self.direct_object else None,
            "indirect_object": str(self.indirect_object) if self.indirect_object else None,
            "adverbial": [str(item) for item in self.adverbial],
            "clause": self.sentence.clause if self.sentence is not None else None,
            "clause_type": self.clause_type,
        }
        return d

    @staticmethod
    def compare_list(list1, list2):
        if len(list1) == len(list2):
            for item in list1:
                if item not in list2:
                    return False
            return True
        return False

    def collect_elements(self):
        elements = [self.subject, self.predicate]
        if self.direct_object:
            elements.append(self.direct_object)
        if self.indirect_object:
            elements.append(self.indirect_object)
        if self.adverbial:
            elements.extend(self.adverbial)
        return elements

    def to_triples(self):
        triples = []
        if self.direct_object:
            triples.append((self.subject, self.predicate, self.direct_object, "dobj"))
        if self.indirect_object:
            triples.append((self.subject, self.predicate, self.indirect_object, "iobj"))
        if self.adverbial:
            for item in self.adverbial:
                if hasattr(item, "prep"):
                    triples.append((self.subject, self.predicate, item, item.prep))
                else:
                    triples.append((self.subject, self.predicate, item))
        elif self.direct_object is None:
            triples.append((self.subject, self.predicate, None, None))
        return triples

    def __str__(self):
        return "%s; %s; %s; %s; %s" % (
            self.to_word(self.subject), self.to_word(self.predicate), self.to_word(self.direct_object),
            self.to_word(self.indirect_object), "||".join([self.to_word(item) for item in self.adverbial])
        )

    def to_str(self):
        return "%s; %s; %s; %s; %s" % (
            self.to_word(self.subject, True), self.to_word(self.predicate, True), self.to_word(self.direct_object, True),
            self.to_word(self.indirect_object, True), "||".join([self.to_word(item, True) for item in self.adverbial])
        )

    def __eq__(self, other):
        if other is None:
            return False
        if self.subject is not None and other.subject is not None:
            if not self.subject == other.subject:
                return False
        else:
            return False
        if self.predicate is not None and other.predicate is not None:
            if not self.predicate == other.predicate:
                return False
        else:
            return False
        if self.direct_object is not None and other.direct_object is not None:
            if not self.direct_object == other.direct_object:
                return False
        elif self.direct_object is not None or other.direct_object is not None:
            return False
        if self.indirect_object is not None and other.indirect_object is not None:
            if not self.indirect_object == other.indirect_object:
                return False
        elif self.indirect_object is not None or other.indirect_object is not None:
            return False
        if len(self.adverbial) > 0 and len(other.adverbial) > 0:
            if not Tuple.compare_list(self.adverbial, other.adverbial):
                return False
            return True
        if not self.adverbial and not other.adverbial:
            return True
        else:
            return False

    def __hash__(self):
        elements = []
        elements.append(self.subject.word if self.subject else "")
        elements.append(self.predicate.word if self.predicate else "")
        elements.append(self.direct_object.word if self.direct_object else "")
        elements.append(self.indirect_object.word if self.indirect_object else "")
        elements.extend([item.word for item in self.adverbial])
        return hash(";".join(elements))

    @staticmethod
    def compare_triple(triple1, triple2):
        subject1 = Tuple.refine_word(triple1[0].word).lower()
        subject2 = Tuple.refine_word(triple2[0].word).lower()
        if subject1 != subject2:
            return False
        if triple1[1].word != triple2[1].word:
            return False
        element1 = Tuple.refine_word(triple1[2].word).lower() if triple1[2] is not None else None
        element2 = Tuple.refine_word(triple2[2].word).lower() if triple2[2] is not None else None
        if element1 != element2:
            return False
        if triple1[3] != triple2[3]:
            return False
        return True

    @staticmethod
    def refine_word(word):
        word = word.replace(" 's", "'s")
        word = word.replace(" - ", "-")
        word = word.replace(" , ", ", ")
        return word


class Element:
    def __init__(self):
        self.word = ""
        self.word_index = []
        self.sentence = None   # for recording the raw sentence
        self.entity = None     # for entity linking
        self.reference = None  # for co-reference resolution
        self.prep = None       # for adverbial
        self.ne_type = None    # for ner

    def __eq__(self, other):
        if other is not None:
            if self.prep is None and other.prep is None:
                return self.word.lower() == other.word.lower()
            elif self.prep is None or other.prep is None:
                return False
            else:
                return self.word.lower() == other.word.lower() and self.prep.lower() == other.prep.lower()
        return False

    def __str__(self):
        if not self.prep:
            return self.word
        else:
            return self.prep + " " + self.word

    def is_overlaped(self, other):
        if not other:
            return False
        if self == other:
            return False
        if self.prep is not None and other.prep is None or self.prep is None and other.prep is not None:
            if self.word.lower() == other.word.lower():
                return False
        word_index1 = set(self.word_index)
        word_index2 = set(other.word_index)
        intersection = word_index1.intersection(word_index2)
        return len(intersection) > 0


class Node():
    Noun = "Noun"
    PREDICATE = "Predicate"
    Entity = "Entity"
    current_id = int(time.time()*1000)

    def __init__(self, value, type_, sentence_index=None):
        self.value = value
        self.type = type_
        self.sentence_index = sentence_index
        if self.type == self.Noun or self.type == self.PREDICATE:
            self.name = value.word
        else:
            self.name = value["uri"]
        self.node_id = self.generate_id()

    def generate_id(self):
        if self.type == self.PREDICATE:
            _id = int(Node.current_id)  # breaking reference
            Node.current_id += 1
        elif self.type == self.Entity:
            _id = "Entity:" + str(self.value["uri"])
        else:
            if self.sentence_index:
                if self.value.prep:
                    word = self.value.prep + " " + self.value.word
                else:
                    word = self.value.word
                _id = "%s:%d-%d" % (word, self.sentence_index, min(self.value.word_index))
            else:
                _id = self.value.word
        return _id

    def __hash__(self):
        return self.node_id


class Graph():
    def __init__(self, tuples_list=None):
        if not tuples_list:
            return
        self.graph = nx.DiGraph()
        tuples_list_ = self.wrap(tuples_list, True)
        for i, t in enumerate(chain.from_iterable(tuples_list_)):
            self.add_node(t.subject)
            self.add_node(t.predicate)
            self.graph.add_edge(t.predicate.node_id, t.subject.node_id, relation="subj")
            if t.direct_object:
                self.add_node(t.direct_object)
                self.graph.add_edge(t.predicate.node_id, t.direct_object.node_id, relation="dobj")
            if t.indirect_object:
                self.add_node(t.indirect_object)
                self.graph.add_edge(t.predicate.node_id, t.indirect_object.node_id, relation="iobj")
            for item in t.adverbial:
                if item.value.prep is not None:
                    self.add_node(item)
                    self.graph.add_edge(t.predicate.node_id, item.node_id, relation=item.value.prep)
        for tuples in tuples_list_:
            self.check_collision(tuples)

    def build_semantic_graph(self, tuples_list):
        self.graph = nx.DiGraph()
        tuples_list_ = self.wrap(tuples_list)
        for i, t in enumerate(chain.from_iterable(tuples_list_)):
            triples = t.to_triples()
            for i, triple in enumerate(triples):
                if len(triple) == 4:
                    subject, predicate, element, label = triple
                else:
                    subject, predicate, element = triple
                    label = element.value.prep
                predicate_id = str(predicate.node_id) + "#%d" % i
                self.add_node(subject)
                self.graph.add_node(predicate_id, name=predicate.name, type=predicate.type, value=predicate)
                self.graph.add_edge(predicate_id, subject.node_id, relation="subj")
                if element is not None and label is not None:
                    self.add_node(element)
                    self.graph.add_edge(predicate_id, element.node_id, relation=label)
        for tuples in tuples_list_:
            self.check_collision(tuples)

    def wrap(self, tuples_list, merging_nouns=False):
        """
        Wrapping elements of tuples to nodes.
        :param tuples_list: a list of tuples
        """
        tuples_list_ = []
        for i, tuples in enumerate(tuples_list):
            tuples_ = []
            sentence_index = i if not merging_nouns else None
            for tuple_ in tuples:
                tuple_copy = Tuple()
                tuple_copy.subject = self.wrap_element(tuple_.subject, Node.Noun, sentence_index)
                tuple_copy.predicate = self.wrap_element(tuple_.predicate, Node.PREDICATE, sentence_index)
                tuple_copy.direct_object = self.wrap_element(tuple_.direct_object, Node.Noun, sentence_index)
                tuple_copy.indirect_object = self.wrap_element(tuple_.indirect_object, Node.Noun, sentence_index)
                if tuple_.adverbial:
                    adverbial = []
                    for item in tuple_.adverbial:
                        adverbial.append(self.wrap_element(item, Node.Noun, sentence_index))
                    tuple_copy.adverbial = adverbial
                tuples_.append(tuple_copy)
            tuples_list_.append(tuples_)
        return tuples_list_

    def wrap_element(self, element, type_, sentence_index):
        if element is None:
            return None
        if element.entity:
            entity = []
            for item in element.entity:
                if isinstance(item, Node):
                    continue
                entity.append(Node(item, Node.Entity))
            element.entity = entity
        return Node(element, type_, sentence_index)

    def check_collision(self, tuples):
        for i in range(len(tuples)):
            for j in range(i+1, len(tuples)):
                elements1 = tuples[i].collect_elements()
                elements2 = tuples[j].collect_elements()
                for element1 in elements1:
                    for element2 in elements2:
                        if element1.value.is_overlaped(element2.value):
                            if element1.node_id in self.graph:
                                nodes1 = [element1.node_id]
                            else:
                                nodes1 = self.match_nodes(element1.node_id)
                            if element2.node_id in self.graph:
                                nodes2 = [element2.node_id]
                            else:
                                nodes2 = self.match_nodes(element2.node_id)
                            for node1 in nodes1:
                                for node2 in nodes2:
                                    self.graph.add_edge(node1, node2, relation="collision")

    def match_nodes(self, node_id):
        p = re.compile(str(node_id) + "\#\d+")
        nodes = []
        for node in self.graph.nodes():
            if isinstance(node, str) and p.match(node):
                nodes.append(node)
        return nodes

    def add_node(self, element):
        if not self.graph.has_node(element.node_id):
            self.graph.add_node(element.node_id, name=element.name, type=element.type, value=element)
            if hasattr(element.value, "entity") and element.value.entity:
                for e in element.value.entity:
                    if not self.graph.has_node(e.node_id):
                        self.graph.add_node(e.node_id, name=e.name, type=e.type, value=e.value)
                    self.graph.add_edge(element.node_id, e.node_id, relation="means")

    def add_reference_edges(self, node):
        if node.value.reference:
            for item in node.value.reference:
                node_id1 = node.node_id
                node_id2 = item
                if self.graph.has_node(node_id2):
                    self.graph.add_edge(node_id1, node_id2, relation="same_as")

    def merge_triples(self):
        nodes = list(self.graph.nodes())
        for node in nodes:
            if self.graph.nodes[node]["type"] == Node.PREDICATE:
                predicate = self.graph.nodes[node]["value"]
                if not self.graph.has_node(predicate.node_id):
                    self.graph.add_node(predicate.node_id, name=predicate.name, type=predicate.type, value=predicate)
                for child in self.graph.neighbors(node):
                    self.graph.add_edge(predicate.node_id, child, relation=self.graph.edges[node, child]["relation"])
                self.graph.remove_node(node)
