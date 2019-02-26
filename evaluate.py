import re
from tuple_extraction import Element, Tuple
from spacy_util import tokenize
from itertools import chain
import pickle


def load(path):
    with open(path, encoding="utf-8") as fi:
        in_sentence = False
        documents = []
        document = []
        sentence = None
        tuples = []
        for line in fi:
            line = line.strip()
            if not line:
                if sentence is not None:
                    document.append((sentence, tuples))
                sentence = None
                in_sentence = False
                tuples = []

            elif line.startswith("======"):  # end of document
                if document:
                    if sentence:
                        document.append((sentence, tuples))
                    documents.append(document)
                    document = []
                    sentence = None
                    in_sentence = False
                    tuples = []
            else:
                if not in_sentence:  # raw sentence
                    if line.startswith("?"):  # uncertain annotation
                        sentence = line[1:]
                    else:
                        sentence = line
                    in_sentence = True
                else:  # tuple
                    negation = False
                    if line.startswith("?"):  # uncertain annotation
                        line = line[1:]
                    elif line.startswith("##"):  # implicit tuple
                        line = line[2:]
                    elif line.startswith("!"):  # negation tuple
                        line = line[1:]
                        negation = True
                    splits = list(map(str.strip, line.split(";")))
                    tuple_ = build_tuple(splits)
                    tuple_.negation = negation
                    tuples.append(tuple_)
        if document:
            if sentence:
                document.append((sentence, tuples))
                documents.append(document)
        return documents


def build_tuple(splits):
    subj, reference = process_noun(splits[0])
    word, index = split_word(subj)
    subject = Element()
    subject.word = word
    subject.word_index = index
    subject.reference = reference
    predicate = Element()
    word, index = split_word(splits[1])
    predicate.word = word
    predicate.word_index = index
    direct_object = None
    indirect_object = None
    adverbials = []
    if splits[2]:
        dobj, reference = process_noun(splits[2])
        word, index = split_word(dobj)
        direct_object = Element()
        direct_object.word = word
        direct_object.word_index = index
        direct_object.reference = reference
    if splits[3]:
        iobj, reference = process_noun(splits[3])
        word, index = split_word(iobj)
        indirect_object = Element()
        indirect_object.word = word
        indirect_object.word_index = index
        indirect_object.reference = reference
    if splits[4]:
        items = splits[4].split("||")
        for item in items:
            item = item.strip()
            word, index = split_word(item)
            adverbial = Element()
            if " " in word:
                idx = word.index(" ")
                adverbial.prep = word[:idx]
                adverbial.word = word[idx+1:]
            else:
                adverbial.word = word
            adverbial.word_index = index
            adverbials.append(adverbial)
    tuple_ = Tuple()
    tuple_.subject = subject
    tuple_.predicate = predicate
    tuple_.direct_object = direct_object
    tuple_.indirect_object = indirect_object
    tuple_.adverbial = adverbials
    return tuple_


p = re.compile("([^(]+)\((.+)\)")


def process_noun(split):
    if "(" in split:  # has reference
        subj, reference = p.findall(split)[0]
    else:
        subj = split
        reference = None
    return subj, reference


def split_word(word):
    if "|" in word:
        words, index = zip(*[split.split("|") for split in word.split(" ")])
        index = [int(idx) for idx in index]
        return " ".join(words), index
    else:
        return word, []


def compare_tuples(tuple1, tuple2, strict=True):
    if not tuple1 or not tuple2:
        return False
    if not compare_element(tuple1.subject, tuple2.subject):
        return False
    if not compare_element(tuple1.predicate, tuple2.predicate):
        return False
    if tuple1.direct_object is not None:
        if tuple2.direct_object is None or not compare_element(tuple1.direct_object, tuple2.direct_object):
            return False
    elif tuple2.direct_object is not None:
        return False
    if tuple1.indirect_object:
        if not tuple2.indirect_object or not compare_element(tuple1.indirect_object, tuple2.indirect_object):
            return False
    elif tuple2.indirect_object:
        return False
    if not strict:
        return True

    if len(tuple1.adverbial) > 0:
        if len(tuple2.adverbial) != len(tuple1.adverbial):
            return False
        for item1 in tuple1.adverbial:
            for item2 in tuple2.adverbial:
                if compare_element(item1, item2):
                    break
            else:
                return False
        return True
    elif len(tuple2.adverbial) > 0:
        return False
    return True


def compare_element(element1, element2):
    word1 = refine_word(element1.word.lower())
    word2 = refine_word(element2.word.lower())
    if word1 == word2:
        return True
    elif element1.reference:
        return element1.reference.lower() == word2
    elif element2.reference:
        return element2.reference.lower() == word1


def refine_word(word):
    word = word.replace(" 's", "'s")
    word = word.replace(" - ", "-")
    word = word.replace(" , ", ", ")
    return word


def validate_by_lexical(sentence, tuples):
    sentence_ = " ".join(tokenize(sentence))
    tuples_ = []
    for tuple_ in tuples:
        if tuple_.subject.word not in sentence and tuple_.subject.word not in sentence_:
            continue
        if tuple_.direct_object:
            if tuple_.direct_object.word not in sentence and tuple_.direct_object.word not in sentence_:
                continue
        if tuple_.indirect_object:
            if tuple_.indirect_object.word not in sentence and tuple_.indirect_object.word not in sentence_:
                continue
        tuples_.append(tuple_)
    return tuples_


def merge_documents(documents1, documents2):
    # merging extractions
    assert len(documents1) == len(documents2)
    documents = []
    for doc1, doc2 in zip(documents1, documents2):
        assert len(doc1) == len(doc2)
        document = []
        for (sent1, tuples1), (sent2, tuples2) in zip(doc1, doc2):
            assert sent1 == sent2
            tuples = [tuple_ for tuple_ in tuples1]
            for tuple2 in tuples2:
                tuple_ = None
                merged_tuple = None
                for tuple1 in tuples:
                    # if compare_tuples(tuple1, tuple2):
                    #     break
                    tuple_ = merge_tuples(tuple1, tuple2)
                    if tuple_ is not None:
                        merged_tuple = tuple1
                        break
                if tuple_ is not None:
                    tuples.remove(merged_tuple)
                    tuples.append(tuple_)
                else:
                    tuples.append(tuple2)

            tuples = validate_by_lexical(sent1, tuples)
            document.append((sent1, tuples))
        documents.append(document)
    return documents


def tuples2triples(tuples):
    return list(chain.from_iterable([tuple_.to_triples() for tuple_ in tuples]))


def compare_triple(triple1, triple2):
    subject1 = refine_word(triple1[0].word).lower()
    subject2 = refine_word(triple2[0].word).lower()
    if subject1 != subject2:
        return False
    if triple1[1].word != triple2[1].word:
        return False
    element1 = refine_word(triple1[2].word).lower() if triple1[2] is not None else None
    element2 = refine_word(triple2[2].word).lower() if triple2[2] is not None else None
    if element1 != element2:
        return False
    if triple1[3] != triple2[3]:
        return False
    return True


def evaluate_triple(gold_documents, documents):
    gold_totgal = 0
    extracted_total = 0
    correct = 0
    assert len(gold_documents) == len(documents)
    for doc1, doc2 in zip(gold_documents, documents):
        assert len(doc1) == len(doc2)
        for (sent1, tuples1), (sent2, tuples2) in zip(doc1, doc2):
            assert sent1 == sent2
            triples1 = tuples2triples(tuples1)
            triples2 = tuples2triples(tuples2)
            gold_totgal += len(triples1)
            extracted_total += len(triples2)
            for triple2 in triples2:
                for triple1 in triples1:
                    if compare_triple(triple1, triple2):
                        correct += 1
                        break
    print(correct, extracted_total)
    recall = correct / gold_totgal
    precision = correct / extracted_total
    f1 = 2 * recall * precision / (recall + precision)
    print(f"recall: {recall:.3f}")
    print(f"precision: {precision:.3f}")
    print(f"f1: {f1:.3f}")


def merge_tuples(tuple1, tuple2):
    to_merge = False
    if tuple1.subject == tuple2.subject and tuple1.predicate == tuple2.predicate:
        to_merge = True
    if tuple1.direct_object is not None and tuple2.direct_object is not None:
        if tuple1.direct_object != tuple2.direct_object:
            to_merge = False
    elif tuple1.direct_object is not None or tuple2.direct_object is not None:
        to_merge = False
    if tuple1.indirect_object is not None and tuple2.indirect_object is not None:
        if tuple1.indirect_object != tuple2.indirect_object:
            to_merge = False
    elif tuple1.indirect_object is not None or tuple2.indirect_object is not None:
        to_merge = False
    if not to_merge:
        return None
    triples1 = tuple1.to_triples()
    triples2 = tuple2.to_triples()
    for triple2 in triples2:
        for triple1 in triples1:
            if Tuple.compare_triple(triple1, triple2):
                break
        else:
            triples1.append(triple2)
    tuple_ = Tuple()
    for triple in triples1:
        if tuple_.predicate is None:
            tuple_.predicate = triple[1]
        label = triple[3]
        if label == "dobj":
            tuple_.subject = triple[0]
            tuple_.direct_object = triple[2]
        if label == "iobj":
            tuple_.subject = triple[0]
            tuple_.indirect_object = triple[2]
        if label is None:
            tuple_.subject = triple[0]
        elif triple[2] not in tuple_.adverbial:
            tuple_.subject = triple[0]
            tuple_.adverbial.append(triple[2])
    return tuple_


if __name__ == "__main__":
    documents1 = load("data/wiki_sentences_extraction.txt")
    # documents2 = load("data/tuples_raw.txt")
    with open("data/tuples_spacy_raw.pkl", "rb") as fi:
        documents2 = pickle.load(fi)
    documents3 = load("data/tuples_lexical.txt")
    documents4 = load("data/tuples_refined.txt")
    documents = merge_documents(documents2, documents3)
    evaluate_triple(documents1, documents)
