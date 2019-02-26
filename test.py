# spacy
from openie_spacy import SpacyOpenIE as OpenIE
from sentence_classification_spacy import classify_clause_type
from spacy_util import parse
from nlp_util import split_sentence


# corenlp
# from nlp_util import parse
# from openie import CorenlpOpenIE as OpenIE

# from sentence_classification import classify_clause_type


from nlp_util import merge_verb_phrase
from spacy_util import chunk
from syntax_tree import Sentence, print_sentence
from sentence_structure import SentenceRestructurer


Sentence.build(chunking_func=chunk, chunking_verb_func=merge_verb_phrase, parsing_func=parse)


# def test_sentence():
#     with open("sentence.txt") as fi:
#         for line in fi:
#             line = line.strip()
#             if line:
#                 sentence, type_ = line.strip().split("||")
#                 sentence = parse(sentence.strip())[0]
#                 sentence = Sentence.from_parsing_result(sentence)
#
#                 for word in sentence.tree.words.values():
#                     print(word)
#                 print()
#                 sentence.stretch_nounphrases()
#                 for word in sentence.tree.words.values():
#                     print(word)
#                 print()
#
#                 sentence.shrink_nounphrases()
#                 for word in sentence.tree.words.values():
#                     print(word)
#                 print("***********************")


# def test_sentence_classification():
#     with open("sentence.txt") as fi:
#         for line in fi:
#             try:
#                 sentence, type_ = line.strip().split("||")
#                 sentence = parse(sentence.strip())[0]
#                 sentence = Sentence.from_parsing_result(sentence, False)
#                 for i, token in sentence.tree.words.items():
#                     if token.pos.startswith("VB"):
#                         pred_type = classify_clause_type(sentence.tree, i)
#                         if pred_type == type_.strip():
#                             break
#                         else:
#                             print(type_)
#                             print(sentence)
#                             break
#             except:
#                 import traceback
#                 traceback.print_exc()


def test_openie():
    paragraphs = []
    with open("data/samples.txt", encoding="utf-8") as fi:
        paragraph = []
        for line in fi:
            line = line.strip()
            if line:
                paragraph.append(line)
            else:
                if paragraph:
                    paragraphs.append("\n".join(paragraph))
                    paragraph = []
    if paragraph:
        paragraphs.append("\n".join(paragraph))

    restructurer = SentenceRestructurer(Sentence)
    openie = OpenIE(Sentence)
    for paragraph in paragraphs:
        for sent in paragraph.split("\n"):
            print("***raw sentence: %s" % sent)
            sentence = parse(sent)[0]
            sentence = Sentence.from_parsing_result(sentence)
            restructurer.restructure(sentence)
            print("***simplified sentences:")
            for subsent in sentence.iter_subsentence():
                print(subsent)
            print("***extracted tuples:")
            openie.process_sentence(sentence, True)
            print()

# def test_sentence_breakdown():
#     sentences = ["he was famous when he was young.", "when he was young, he was famous.",
#                  "he was a student until he was 12 years old", "The boy who is clever is a student.",
#                  "The boy, who was a student, was famous.", "The boy holding a gun is his brother.",
#                  "The boy killed is his brother", "Born in Beijing, he left Beijing in 1999.",
#                  "He moved to Beijing, where he got married.", "The boy went in the room, waving his arms.",
#                  "he said he would come.", "It' said he would come.", "His father Tom is famous.",
#                  "His father, Tom, is famous.", "He cried as soon as he arrived.", "he cried the moment he arrived"]
#
#     decomposer = SentenceDecomposer(Sentence)
#     for sentence in sentences:
#         print(sentence)
#         sentence = parse(sentence)[0]
#         sentence = Sentence.from_parsing_result(sentence)
#         sentence = decomposer.break_down(sentence)
#         print_sentence(sentence)

