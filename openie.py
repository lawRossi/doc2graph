import clause_classification as SCLF
from corenlp_util import merge_verb_phrase
import json
from itertools import chain
from datastructure import Phrase, Token
from clause_classification import CorenlpClauseClassifier


class CorenlpOpenIE():
    def __init__(self):
        self.clause_clf = CorenlpClauseClassifier()

    def process_paragraph(self, paragraph):
        """
        Extracting tuples from a paragraph.
        :param paragraph: a list of restructured sentences.
        :return:
        """
        tuples = []
        for i, sentence in enumerate(paragraph):
            for tuple_ in self.process_sentence(sentence):
                tuple_["sentenceIndex"] = i
                tuples.append(tuple_)
        return tuples

    def serialize(self, obj):
        if isinstance(obj, list):
            return " ".join(tostr(obj))
        else:
            return str(obj)

    def process_sentence(self, sentence, verbose=False):
        """
        Extracting tuples from a sentence.
        :param sentence: a restructured sentence.
        :param verbol: whether to print extracted tuples
        :return:
        """
        unprocessed = [(None, sentence)]
        tuples = []
        while unprocessed:
            sent = unprocessed[0][1]
            sent.stretch_nounphrases()
            merge_verb_phrase(sent.tree)
            sent.shrink_nounphrases()
            adverbials = sent.tree.get_adverbial()
            sent.raw_tuples = list(extract_tuples(self.clause_clf, sent))
            for t in sent.raw_tuples:
                assign_adverbial(sent.tree, adverbials, t)
                if verbose:
                    print(json.dumps(t, default=self.serialize))
            tuples.extend(sent.raw_tuples)
            unprocessed = unprocessed[1:] + sent.left + sent.right
        return tuples


def tostr(tokens):
    return [str(token) for token in tokens]


def flatten(element):
    """converting everything to list of Token"""

    if isinstance(element, Phrase):
        return [token[1] for token in element.tokens]
    if isinstance(element, Token):
        return [element]
    if isinstance(element, list):
        tokens = []
        for item in element:
            if isinstance(item, Phrase):
                tokens.extend([token[1] for token in item.tokens])
            elif isinstance(item, Token):
                tokens.append(item)
        return tokens


def assign_adverbial(tree, adverbials, tuple_):
    predicate = tuple_["V"]
    for token in flatten(predicate):
        if token.idx in adverbials:
            adverbial = [item for item in adverbials[token.idx] if len(item) > 1]
            tuple_["A"] = adverbial

    if not isinstance(predicate, list):
        idx = predicate.idx + 1
        if tree.in_coming_relation(idx) == "conj":
            parent = tree.parents[idx]
            if parent-1 in adverbials:  # pay attention to the index
                adverbial = [item for item in adverbials[parent-1] if len(item) > 1]
                min_idx = min(chain.from_iterable([[token.idx+1 for token in item] for item in adverbial]))
                max_idx = max(chain.from_iterable([[token.idx+1 for token in item] for item in adverbial]))
                if max_idx < parent-1 or min_idx > idx-1:
                    tuple_["A"] = adverbial


def record_clause(func):
    def new_func(clause_clf, sentence):
        for tuple_ in func(clause_clf, sentence):
            tuple_["clause"] = sentence.raw_sentence
            yield tuple_
    return new_func


@record_clause
def extract_tuples(clause_clf, sentence):
    """
    extracting n_tuples from a sentence
    :param sentence: plain text sentence
    :param tree: the syntax tree of the sentence
    :return:
    """
    tree = sentence.tree
    processed = []
    for index, token in tree.words.items():
        if index not in processed and token.pos.startswith('VB'):
            type_ = clause_clf.classify_clause(tree, index)
            if type_ == SCLF.SV:
                for n_tuple in extract_SV(tree, index):
                    yield n_tuple

            elif type_ == SCLF.SVO:
                for n_tuple in extract_SVO(tree, index):
                    yield n_tuple

            elif type_ == SCLF.SVC:
                sentence.object_clause = True
                for n_tuple in extract_SVC(tree, index, sentence):
                    yield n_tuple
                break  # need fix

            elif type_ == SCLF.SVOO:
                for n_tuple in extract_SVOO(tree, index):
                    yield n_tuple

            elif type_ == SCLF.SVb:
                for n_tuple in extract_SVb(tree, index):
                    yield n_tuple

            elif type_ == SCLF.SVc:
                for n_tuple in extract_SVc(tree, index, processed):
                    yield n_tuple

            elif type_ == SCLF.SVcC:
                sentence.object_clause = True
                for n_tuple in extract_SVcC(tree, index, sentence):
                    yield n_tuple
                break   # need fix

            elif type_ == SCLF.SVX:
                for n_tuple in extract_SVX(tree, index):
                    yield n_tuple


def expand_phrase(extract_func):
    def extract(*args, **kwargs):
        tree = args[0]
        tuples = extract_func(*args, **kwargs)
        for tuple_ in tuples:
            tuple_["S"] = expand_element(tree, tuple_["S"])
            tuple_["V"] = expand_predicate(tree, tuple_["V"])
            if "O" in tuple_:
                tuple_["O"] = expand_element(tree, tuple_["O"])
            if "P" in tuple_:
                tuple_["P"] = expand_element(tree, tuple_["P"])
            if "iO" in tuple_:
                tuple_["iO"] = expand_element(tree, tuple_["iO"])
            if "dO" in tuple_:
                tuple_["dO"] = expand_element(tree, tuple_["dO"])
            yield tuple_
    return extract


def expand_element(tree, element):
    span = [element.idx+1]
    expanded_span = tree.expand_nounphrase(span)
    if len(expanded_span) > len(span):
        new_elemnt = [tree.words[item] for item in sorted(expanded_span) if item in tree.words]
        return new_elemnt
    else:
        return element


def expand_predicate(tree, element):
    if isinstance(element, list):
        return element
    idx = element.idx + 1
    element_ = [element]
    for child in tree.children(idx):
        if tree.dependent_relation(idx, child) in ["aux", "auxpass"] and tree.words[child].word not in ["did", "do"]:
            element_.append(tree.words[child])
    else:
        if tree.words[idx].pos == "VBG" or tree.words[idx].pos == "VBN" and tree.in_coming_relation(idx) == "conj":
            parent = tree.parents[idx]
            for child in tree.children(parent):
                if tree.dependent_relation(parent, child) in ["aux", "auxpass"] and tree.words[child].word not in ["did", "do"]:
                    element_.append(tree.words[child])
    if len(element_) > 1:
        return sorted(element_, key=lambda token: token.idx)
    else:
        return element


@expand_phrase
def extract_SVC(tree, index, sentence):
    if "neg" in tree.out_going_relations(index):
        negative = True
    else:
        negative = False

    subjects = tree.get_subjects(index)
    if sentence.right:
        sentence.right[0][1].stretch_nounphrases()
        merge_verb_phrase(sentence.right[0][1].tree)
        sentence.right[0][1].shrink_nounphrases()
        C = list(extract_tuples(sentence.right[0][1]))
        for subject in subjects:
            n_tuple = {}
            n_tuple["category"] = SCLF.SVC
            n_tuple["S"] = tree.words[subject]
            n_tuple["V"] = tree.words[index]
            n_tuple["C"] = C
            n_tuple["N"] = negative
            yield n_tuple


@expand_phrase
def extract_SVcC(tree, index, sentence):
    if "neg" in tree.out_going_relations(tree.parents[index]):
        negative = True
    else:
        negative = False

    if len(tree.get_subjects(index)) != 0:
        subjects = tree.get_subjects(index)
    else:
        subjects = tree.get_subjects(tree.parents[index])

    if sentence.right:
        C = list(extract_tuples(sentence.right[0][1]))
        if "auxpass" in tree.in_coming_relation(index):  # it is known that
            if subjects:
                n_tuple = {}
                n_tuple["category"] = SCLF.SVcC
                n_tuple["S"] = tree.words[subjects[0]]
                n_tuple["V"] = [tree.words[index], tree.words[tree.parents[index]]]
                n_tuple["C"] = C
                n_tuple["N"] = negative
                yield n_tuple
        else:
            for subject in subjects:
                n_tuple = {}
                n_tuple["category"] = SCLF.SVcC
                n_tuple["S"] = tree.words[subject]
                n_tuple["V"] = tree.words[index]
                n_tuple["C"] = C
                n_tuple["N"] = negative
                yield n_tuple


def extract_SVOC(tree, index):
    pass


@expand_phrase
def extract_SV(tree, index):
    if "neg" in tree.out_going_relations(index):
        negative = True
    else:
        negative = False

    subjects = tree.get_subjects(index)

    for subject in subjects:
        n_tuple = {}
        n_tuple["S"] = tree.words[subject]
        n_tuple["V"] = tree.words[index]
        n_tuple["N"] = negative
        n_tuple["category"] = SCLF.SV
        yield n_tuple


@expand_phrase
def extract_SVO(tree, index):
    if "neg" in tree.out_going_relations(index):
        negative = True
    else:
        negative = False

    subjects = tree.get_subjects(index)
    objects = tree.get_objects(index)
    for subject in subjects:
        for object in objects:
            n_tuple = {}
            n_tuple["S"] = tree.words[subject]
            n_tuple["V"] = tree.words[index]
            n_tuple["O"] = tree.words[object]
            n_tuple["N"] = negative
            n_tuple["category"] = SCLF.SVO
            yield n_tuple


@expand_phrase
def extract_SVOO(tree, index):
    if "neg" in tree.out_going_relations(index):
        negative = True
    else:
        negative = False

    subjects = tree.get_subjects(index)
    dobj,iobj = get_idobj(tree, index)

    dobjects = []
    iobjects = []
    for obj in dobj:
        dobjects.append(tree.words[obj])
        conjunctions = tree.get_conjunction(obj)
        for conjunction in conjunctions:
            dobjects.append(tree.words[conjunction])

    for obj in iobj:
        iobjects.append(tree.words[obj])
        conjunctions = tree.get_conjunction(obj)
        for conjunction in conjunctions:
            iobjects.append(tree.words[conjunction])
    for subject in subjects:
        for dobject in dobjects:
            for iobject in iobjects:
                n_tuple = {}
                n_tuple["S"] = tree.words[subject]
                n_tuple["V"] = tree.words[index]
                n_tuple["dO"] = dobject
                n_tuple["iO"] = iobject
                n_tuple["N"] = negative
                n_tuple["category"] = SCLF.SVOO
                yield n_tuple


@expand_phrase
def extract_SVc(tree, index, processed):
    parent = tree.parents[index]
    subjects = tree.get_subjects(parent)
    conjunctions = tree.get_conjunction(parent)
    conjunctions.append(parent)
    processed.append(parent)
    for subject in subjects:
        for conjunction in conjunctions:
            if tree.words[conjunction].pos.startswith('VB'):
                continue
            if conjunction != parent and 'cop' in tree.out_going_relations(conjunction):   # he is a boy and is a student
                continue
            n_tuple = {}
            n_tuple["S"] = tree.words[subject]
            n_tuple["V"] = tree.words[index]
            n_tuple["P"] = tree.words[conjunction]
            n_tuple["category"] = SCLF.SVc
            yield n_tuple


def extract_SVb(tree, index):
    return []


def get_idobj(tree, index):
    iobj = []
    dobj = []
    for child in tree.graph.neighbors(index):
        if tree.dependent_relation(index, child) == "dobj":
            dobj.append(child)

        elif tree.dependent_relation(index, child) == "iobj":
            iobj.append(child)

    return dobj, iobj


def get_pass(tree, index):
    nodes = []
    for child in tree.graph.neighbors(index):
        if tree.dependent_relation(index, child) == "nsubjpass":
            nodes.append(index)
        elif tree.dependent_relation(index, child) == "auxpass":
            nodes.append(child)
    return nodes


def is_negative(tree, index): # neither...nor... need fix
    for child in tree.graph.neighbors(index):
        if tree.words[child] == 'neither':
            return True
    return False


@expand_phrase
def extract_SVX(tree, index):
    if "neg" in tree.out_going_relations(index):
        negative = True
    else:
        negative = False
    for child in tree.graph.neighbors(index):
        if tree.dependent_relation(index, child) == "xcomp" and tree.words[child].pos.startswith("VB"):
            phrase = [tree.words[idx] for idx in range(index, child+1) if idx in tree.words]
            subjects = tree.get_subjects(index)
            objects = tree.get_objects(child)
            for subject in subjects:
                n_tuple = {"category": "SVX", "S": tree.words[subject], "V": phrase, "N": negative}
                if objects:
                    for object in objects:
                        n_tuple["O"] = tree.words[object]
                        yield n_tuple
                else:
                    yield n_tuple
        elif tree.dependent_relation(index, child) == "xcomp" and tree.words[child].pos.startswith("NN"):
            subjects = tree.get_subjects(index)
            objects = [child] + tree.get_conjunction(child)
            for subject in subjects:
                n_tuple = {"category": "SVX", "S": tree.words[subject], "V": tree.words[index], "N": negative}
                for object in objects:
                    n_tuple["O"] = tree.words[object]
                    yield n_tuple


if __name__ == "__main__":
    sentences = ["he was the son of Li", "he gave a talk at the meeting", "he gave up smoking", "he was called LL",
                 "he started to learn English", "he started learning English", "he was invited to attend the meeting",
                 "he walked in the room, waving his arms", "he was waving his arms",
                 "traits be using both existing species and fossils",
                 "Existing patterns of biodiversity have been shaped both by speciation and by extinction.",
                 "his hearing began to deteriorate", "he was thought to be a good teacher",
                 "he was considered a good teacher"]
