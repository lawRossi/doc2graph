import sentence_classification_spacy as SCLF
from sentence_classification_spacy import SpacyClauseClassifier
from openie import tostr
from corenlp_util import merge_verb_phrase
import json
from openie import extract_SV, extract_SVO, extract_SVOO
from openie import extract_SVC, extract_SVcC
from openie import record_clause, expand_phrase, assign_adverbial


class SpacyOpenIE():
    def __init__(self):
        self.clause_clf = SpacyClauseClassifier()

    def serialize(self, obj):
        if isinstance(obj, list):
            return " ".join(tostr(obj))
        else:
            return str(obj)

    def process_paragraph(self, paragraph, verbose=False):
        """
        Extracting tuples from a paragraph.

        :param paragraph: a list of restructured sentences.
        :return:
        """
        for i, sentence in enumerate(paragraph):
            for tuple_ in self.process_sentence(sentence, verbose):
                tuple_["sentenceIndex"] = i

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
                for n_tuple in extract_SVc(tree, index):
                    yield n_tuple

            elif type_ == SCLF.SVcC:
                sentence.object_clause = True
                for n_tuple in extract_SVcC(tree, index, sentence):
                    yield n_tuple
                break   # need fix

            elif type_ == SCLF.SVX:
                for n_tuple in extract_SVX(tree, index):
                    yield n_tuple


@expand_phrase
def extract_SVc(tree, index):
    if "neg" in tree.out_going_relations(tree.parents[index]):
        negative = True
    else:
        negative = False
    subjects = tree.get_subjects(index)
    objects = []
    for child in tree.children(index):
        if tree.dependent_relation(index, child) == SCLF.ATTR:
            objects = [child] + tree.get_conjunction(child)
            break
    for subject in subjects:
        for object in objects:
            n_tuple = {}
            n_tuple["category"] = SCLF.SVc
            n_tuple["S"] = tree.words[subject]
            n_tuple["V"] = tree.words[index]
            n_tuple["P"] = tree.words[object]
            n_tuple["N"] = negative
            yield n_tuple


def extract_SVOC(tree, index):
    pass


def extract_SVcX(tree, index):
    pass

def extract_SVb(tree, index):
    return []


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
        elif tree.dependent_relation(index, child) == "oprd" and tree.words[child].pos.startswith("NN"):
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
                 "his "]
    # sentence = parse("he started to learn English")
    # sent = Sentence(sentence[0], False, merging_verb=True)
    # tree = sent.tree
    # for idx, token in tree.words.items():
    #     print(token.word)
    # print()
