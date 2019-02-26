import spacy
from spacy.tokens import Doc
from collections import defaultdict
from spacy.lemmatizer import Lemmatizer
from spacy.lang.en import LEMMA_INDEX, LEMMA_EXC, LEMMA_RULES


class WhitespaceTokenizer(object):
    """
    a custom white space based tokenizer
    """
    def __init__(self, vocab):
        self.vocab = vocab

    def __call__(self, text):
        words = text.split(' ')
        # All tokens 'own' a subsequent space character in this tokenizer
        spaces = [True] * len(words)
        return Doc(self.vocab, words=words, spaces=spaces)


nlp = spacy.load('en_core_web_sm')
# nlp.tokenizer = WhitespaceTokenizer(nlp.vocab)  # hook custom tokenizer


def tokenize(sentence):
    sent = nlp(sentence)
    return [token.text for token in sent]


def split_sentence(text):
    doc = nlp(text)
    sentences = [" ".join([token.text for token in sent]) for sent in doc.sents]
    return sentences


def parse(text):
    """
    Analyzing the text, including splitting sentence, tokenizing, pos-tagging and parsing.

    :param text: the raw text

    :return:
    """
    result = []
    doc = nlp(text)
    for sent in doc.sents:
        words = [token.text for token in sent]
        pos_tags = [token.tag_ for token in sent]
        nes = {}
        for ent in doc.ents:
            nes[ent.text] = ent.label_
        dependencies = []
        for i, token in enumerate(sent):
            if token.dep_ == "dative":
                dependencies.append((token.head.i+1, i+1, "iobj"))
            else:
                dependencies.append((token.head.i+1, i+1, token.dep_))
        result.append({"words": words, "pos_tags": pos_tags, "dependencies": dependencies, "nes": nes})
    return result


def chunk_nouns(sentence):
    sent = nlp(sentence)
    for ck in sent.noun_chunks:
        yield [item.i+1 for item in ck]


def extract_noun_chunks(sentence):
    sent = nlp(sentence)
    chunks = []
    tokens = [token for token in sent]
    covered = []
    heads = []
    for ck in sent.noun_chunks:
        span = [item.i + 1 for item in ck]
        if len(span) > 1:
            covered.extend(span)
            for item in span:
                if tokens[item-1].head.i + 1 not in span:
                    chunks.append((item, span))
                    heads.append(item)
                    break
    tokens_ = []
    for token in tokens:
        idx = token.i + 1
        if idx in covered and idx not in heads and token.dep_ not in ["det", "poss"]:
            continue
        tokens_.append(token)
    tokens = [token.text for token in tokens]
    kept_tokens = [(token.text, token.i) for token in tokens_]
    return tokens, kept_tokens, chunks


def stem(verb):
    lemmatizer = Lemmatizer(LEMMA_INDEX, LEMMA_EXC, LEMMA_RULES)
    lemma = lemmatizer(verb, 'VERB')
    return lemma[0]


if __name__ == "__main__":
    print(stem("initializing"))
    print(stem("standing"))
    print(stem("celebrating"))
