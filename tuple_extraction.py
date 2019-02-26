import gevent
# from gevent import monkey
# monkey.patch_all()

from sentence_structure import SentenceRestructurer
from corenlp_util import parse
from openie import CorenlpOpenIE, flatten
from sentence_decomposition import CorenlpDecomposer, SpacyDecomposer
from spacy_util import tokenize
from corenlp_datastructure import CorenlpSentenceBuilder
from datastructure import Tuple, Element
from clause_detection import ClauseDetector, SpacyClauseDetector

from openie_spacy import SpacyOpenIE
from spacy_datastructure import SpacySentenceBuilder


builder = CorenlpSentenceBuilder()
clause_detector = ClauseDetector()
restructurer = SentenceRestructurer(builder, clause_detector)
openie = CorenlpOpenIE()
decomposer = CorenlpDecomposer()


# builder = SpacySentenceBuilder()
# clause_detector = SpacyClauseDetector()
# restructurer = SentenceRestructurer(builder, clause_detector)
# openie = SpacyOpenIE()


def build_tuple(tuple_):
    new_tuple = Tuple()
    new_tuple.clause_type = tuple_["category"]
    if "S" in tuple_:
        new_tuple.subject = build_element(tuple_["S"])
    if "V" in tuple_:
        new_tuple.predicate = build_element(tuple_["V"], predicate=True)
    elif "Vc" in tuple_:
        new_tuple.predicate = build_element(tuple_["Vc"], predicate=True)
    elif "P" in tuple_:
        new_tuple.predicate = build_element(tuple_["P"], predicate=True)

    if "O" in tuple_:
        new_tuple.direct_object = build_element(tuple_["O"])
    elif "dO" in tuple_:
        new_tuple.direct_object = build_element(tuple_["dO"])
        new_tuple.indirect_object = build_element(tuple_["iO"])
    elif "P" in tuple_:
        new_tuple.direct_object = build_element(tuple_["P"])

    if "A" in tuple_ and tuple_["A"]:
        new_tuple.adverbial = [build_element(item, adverbial=True) for item in tuple_["A"]]

    return new_tuple


def build_element(item, predicate=False, adverbial=False):
    item = flatten(item)
    element = Element()
    word = " ".join([token.word for token in item])
    if not adverbial:
        element.word = word
    else:
        index = word.index(" ")
        element.prep = word[:index]
        element.word = word[index+1:]
    if not predicate:
        element.word_index = [token.original_idx for token in item]
    else:  # predicate may contain word that are not in the original sentence
        element.word_index = [token.original_idx if token.original_idx != -1 else -1 for token in item]

    return element


def is_overlapped(element1, element2):
    if element1 == element2:
        return False
    elif element1.prep is None or element2.prep is None:
        if element1.word == element2.word:
            return False
    word_index1 = set(element1.word_index)
    word_index2 = set(element2.word_index)
    if -1 in word_index1:   # predicate may contain word not in original text
        word_index1.remove(-1)
    if -1 in word_index2:
        word_index2.remove(-1)
    intersection = word_index1.intersection(word_index2)
    return len(intersection) > 0


def reconstruct_tuple(tuple_, tokens, chunks, nmods, adverbials):
    reconstruct_element(tuple_.subject, tokens, chunks, nmods)
    if tuple_.direct_object:
        reconstruct_element(tuple_.direct_object, tokens, chunks, nmods)
    if tuple_.indirect_object:
        reconstruct_element(tuple_.indirect_object, tokens, chunks, nmods)

    for idx in tuple_.predicate.word_index:
        if idx in adverbials:
            for adverbial in adverbials[idx]:
                element = Element()
                element.word_index = [token.original_idx for token in adverbial]
                tuple_.adverbial.append(element)
            break

    if tuple_.adverbial:
        for item in tuple_.adverbial:
            reconstruct_element(item, tokens, chunks, nmods, True)


def reconstruct_element(element, tokens, chunks, nmods, adverbial=False):
    for idx in element.word_index:
        processed = False
        if idx in nmods:
            element.word_index.extend([token.original_idx for nmod in nmods[idx] for token in nmod])
            processed = True
        if processed:
            break
    word_index = [idx for idx in element.word_index]
    for idx in element.word_index:
        for _, chk in chunks:
            if idx + 1 in chk:
                word_index.extend([idx_-1 for idx_ in chk])
                break

    element.word_index = list(sorted(set(word_index)))
    element.word = " ".join(tokens[idx] for idx in element.word_index)
    if adverbial:
        if " " in element.word:
            idx = element.word.index(" ")
            element.prep = element.word[:idx]
            element.word = element.word[idx+1:]


def extract_tuples_with_lexical_simplification(sentence):
    tokens, chunks, nmods, adverbials, clauses = decomposer.lexical_simplification_first(sentence, restructurer)
    for clause in clauses:
        # text = " ".join(token.word for token in clause)
        # print(text)
        sent = builder.from_un_parsed_tokens(clause)
        for tuple_ in openie.process_sentence(sent):
            tuple_ = build_tuple(tuple_)
            tuple_.predicate.sentence = sentence  # recording the raw sentence in the predicate
            reconstruct_tuple(tuple_, tokens, chunks, nmods, adverbials)
            yield tuple_


def extract_tuples(sentence):
    raw_sentence = sentence
    sentence = " ".join(tokenize(sentence))
    sentence = builder.from_raw_senence(sentence)
    restructurer.apposition_first(sentence)
    for tuple_ in openie.process_sentence(sentence):
        tuple_ = build_tuple(tuple_)
        tuple_.predicate.sentence = raw_sentence  # recording the raw sentence in the predicate
        yield tuple_


def extract_from_raw_sentence(sentence):
    raw_sentence = sentence
    sentence = " ".join(tokenize(sentence))
    sentence = builder.from_raw_senence(sentence)
    for tuple_ in openie.process_sentence(sentence):
        tuple_ = build_tuple(tuple_)
        tuple_.predicate.sentence = raw_sentence  # recording the raw sentence in the predicate
        yield tuple_


def process_document(document, simplification=False):
    if simplification:
        jobs = [gevent.spawn(extract_tuples_with_lexical_simplification, sentence) for sentence in document]
    else:
        jobs = [gevent.spawn(extract_from_raw_sentence, sentence) for sentence in document]
    gevent.joinall(jobs)
    for job in jobs:
        for tuple_ in job.value:
            yield tuple_


if __name__ == "__main__":
    # tuples = []
    # for paragraph in paragraphs[:5]:
    #     tuples.extend(process_paragraph(paragraph))
    # paragraphs = ["he was talking and laughing", "he was shot and killed", "he was given a pen"]
    # paragraphs = ["he moved in 1999 and died", "he moved and died in 1999", "he moved in 1999 and died in 2000"]
    # for paragraph in paragraphs:
    #     for tuple_ in extract_tuples(paragraph):
    #         print(tuple_)
    for tuple_ in extract_tuples_with_lexical_simplification("He received national attention in 2004 with his March primary win, his well-received July Democratic National Convention keynote address, and his landslide November election to the Senate."):
        print(tuple_)
