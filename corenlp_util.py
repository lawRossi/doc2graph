# -*- coding:utf-8 -*-
from pycorenlp import StanfordCoreNLP
import re
from nltk import RegexpParser

#nlp = StanfordCoreNLP('http://localhost:9000/')
nlp = StanfordCoreNLP("http://corenlp.run/")

grammar = """
    V: {<VB.*><PR>?<IN|TO>?}
    W: {<NN*|JJ|RB.*|PRP.*|DT>}
    P: {<IN|TO|PR>}
    VP2: {<V><P>}
    VP3: {<V><W>+<P>}
    VP1: {<V>}
"""

vp_parser = RegexpParser(grammar)


def clean(word):
    if "(" in word:
        word = word[:word.find("(")]
    return word


def analyze(sentence):
    output = nlp.annotate(sentence, properties={
        'annotators': 'tokenize,ssplit,pos,parse,depparse,coref',
        'tokenize.whitespace': True,
        'outputFormat': 'json'
    })
    return convert_sentence(output["sentences"])


def tokenize(text):
    # if isinstance(text, unicode):
    #     text = text.encode('utf-8', errors="ignore")
    output = nlp.annotate(text, properties={
        'annotators': 'tokenize,ssplit',
        'outputFormat': 'json'
    })

    return [[token["word"] for token in sentence["tokens"]] for sentence in output["sentences"]]


def split_sentence(text):
    output = nlp.annotate(text, properties={
        'annotators': 'ssplit',
        'outputFormat': 'json'
    })
    return to_raw_sentences(output["sentences"])


def to_raw_sentences(parsed_sentences):
    sentences = []
    for sentence in parsed_sentences:
        words = [token["word"] for token in sentence["tokens"]]
        if ";" not in words:
            sentences.append(" ".join(words))
            continue
        while ";" in words:
            index = words.index(";")
            sentences.append(" ".join(words[:index+1]))
            words = words[index+1:]
        sentences.append(" ".join(words))

    return sentences


def is_copula(verb):
    return verb in ["is", "am", "are", "was", "were", "be", "been", "being"]


def analyze_(sentence):
    output = nlp.annotate(sentence, properties={
        'annotators': 'tokenize,ssplit,pos,parse,depparse,ner',
        'tokenize.whitespace': True,
        'outputFormat': 'json'
    })
    return output


def parse_and_coref_resolution(paragraph):
    result = analyze_(paragraph)
    sentences = result["sentences"]
    sentence_lens = [len(sentence["tokens"]) for sentence in sentences]
    coref_clusters = []
    for cluster in result["corefs"].values():
        coref_cluster = {}
        corefs = []
        for item in cluster:
            start = item["startIndex"] - 1
            end = item["endIndex"] - 1
            offset = sum(sentence_lens[:item["sentNum"] - 1])
            mention = (offset+start, offset+end-1)
            if mention[-1] == "," or mention[-1] == "":
                mention = mention[:-1]
            if item["isRepresentativeMention"]:
                coref_cluster["mention"] = mention
            else:
                # if item["text"].lower() in ["he", "she", "it", "his", "her", "its", "him", "they", "them"]:
                corefs.append(mention)
        coref_cluster["corefs"] = corefs
        coref_clusters.append(coref_cluster)

    return convert_sentence(sentences), clusters2mapping(coref_clusters)


def clusters2mapping(coref_clusters):
    coref_mapping = {}
    for cluster in coref_clusters:
        for coref in cluster["corefs"]:
            coref_mapping[coref] = cluster["mention"]
    return coref_mapping


def parse(text):
    result = analyze_(text)
    sentences = result["sentences"]
    return convert_sentence(sentences)


def convert_sentence(sentences):
    result = []
    for sentence in sentences:
        words = [token["word"] for token in sentence["tokens"]]
        pos_tags = [token["pos"] for token in sentence["tokens"]]
        dependencies = [(dep["governor"], dep["dependent"], dep["dep"]) for dep in sentence["basicDependencies"]]
        if "entitymentions" in sentence:
            nes = {}
            for mention in sentence["entitymentions"]:
                nes[mention["text"]] = mention["ner"]
            result.append({"words": words, "pos_tags": pos_tags, "dependencies": dependencies, "nes": nes})
        else:
            result.append({"words": words, "pos_tags": pos_tags, "dependencies": dependencies})
    return result


position_pattern = re.compile("<(\d+)>")


def chunk_verb(words, tags):
    words = ["%s<%d>" % (word, i+1) for i, word in enumerate(words)]
    tree = vp_parser.parse(list(zip(words, tags)))
    for subtree in tree.subtrees():
        if subtree.label().startswith("VP"):
            leaves = subtree.leaves()
            if len(leaves) > 1:
                positions = sorted([int(position_pattern.search(word).group(1)) for word, _ in leaves])
                if subtree.label() == "VP3":
                    del(positions[-1])
                yield positions


def merge_verb_phrase(tree):
    # merge verb phrase that match some pattern
    # tokens = sorted(tree.words.items(), key=lambda item: item[0])
    # words, tags = zip(*[(token.word, token.pos) for (idx, token) in tokens])
    # chunks = chunk_verb(words, tags)
    # for chunk in chunks:
    #     tree.merge_verb_phrase(chunk)

    # merge something like 'began to learn', 'started learning'
    chunks = []
    for index, token in tree.words.items():
        if token.pos.startswith("VB"):
            chunk = []
            for child in tree.graph.neighbors(index):
                # case like 'start to learn'
                if tree.dependent_relation(index, child) == "xcomp" and tree.words[child].pos.startswith("VB") \
                        and not tree.get_subjects(child):
                    # avoid the case like "he walked in the room, waving his flag
                    # avoid the case like "he said he would come"
                    if "," not in [tree.words[i].word for i in range(index, child) if i in tree.words]:
                        chunk.extend(range(index, child + 1))
                else:
                    rel = tree.dependent_relation(index, child)
                    # case like give up
                    # if rel.startswith("compound") or rel == "auxpass" or rel == "aux" or rel == "ptr":
                    if rel.startswith("compound") or rel == "ptr":
                        if tree.words[child].word not in ["do", "did", "does"]:
                            chunk.append(child)
            if chunk:
                if index not in chunk:
                    chunk.append(index)
                chunks.append(sorted(chunk))

    for chunk in chunks:
        tree.merge_verb_phrase(chunk)


def convert_corefs(words, corefs):
    corefs_ = {}
    for pos in corefs:
        ref = corefs[pos]
        ref_word = " ".join([words[idx] for idx in range(ref[0], ref[1] + 1)])
        if pos[0] == pos[1] and words[pos[0]].lower() in ["it", "he", "she", "him", "her", "they", "them"]:
            corefs_[pos] = ref_word
    return corefs_


if __name__ == "__main__":
    # para = "Kite and Tim are students . They are good friends"
    # sentences, corefs = parse_and_coref_resolution(para)
    # print(corefs)
    pass