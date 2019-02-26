# from spacy_util import parse
from nlp_util import parse
from spacy_util import chunk
from syntax_tree import Sentence, print_sentence
from sentence_structure import SentenceRestructurer, LEFT2RIGHT_PARSE_MULTIPLE, APPOSITION_FIRST


if __name__ == "__main__":
    Sentence.build(chunk, None, parse)
    restructurer = SentenceRestructurer(Sentence)
    with open("data/sentence_restructure_case.txt", encoding="utf-8") as fi:
        for line in fi:
            sentence = line.strip()
            if not sentence:
                continue
            sent = parse(sentence)[0]
            sent = Sentence.from_parsing_result(sent)
            restructurer.restructure(sent, APPOSITION_FIRST)
            print_sentence(sent)
            print()

    # sentence = "Being a musician, he has a good taste for music."
    # sent = parse(sentence)[0]
    # sent = Sentence.from_parsing_result(sent)
    # restructurer.restructure(sent)
    # print_sentence(sent)
    # print()