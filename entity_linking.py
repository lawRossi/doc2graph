from dbpedia_util import candidates
from corenlp_util import parse
from spacy_util import tokenize


def link(words):
    text = " ".join(words)
    mention_entities = candidates(text)
    return mention_entities


def annotate(sentences, confidence):
    text = "".join(sentences)
    mention_entities = candidates(text, confidence)
    nes_list = []
    for sentence in sentences:
        sentence = " ".join(tokenize(sentence))
        sentence = parse(sentence)[0]
        nes = sentence["nes"]
        nes_list.append(nes)
    return mention_entities, nes_list


if __name__ == "__main__":
    print(candidates("He played 15 seasons in the National Basketball Association for the Chicago Bulls and Washington Wizards.", 0.01))
