from evaluate import load, merge_documents
from tuple_extraction import extract_from_raw_sentence, extract_tuples_with_lexical_simplification
from tuple_extraction import extract_tuples
from graph import annotate_documents, annotate_graph, join_optimize
from tuple_extraction import process_document
from sentence_decomposition import lexical_simplification_first
import time
from collections import defaultdict
from tuple_extraction import restructurer
import pickle


def extract_tuples_from_raw_sentence(source_path, save_path):
    documents = load(source_path)
    documents_ = []
    with open(save_path, "w", encoding="utf-8") as fo:
        for document in documents:
            doc = [sent for sent, _ in document]
            sentence_tuples = defaultdict(list)
            for tuple_ in process_document(doc, False):
                sentence_tuples[tuple_.predicate.sentence].append(tuple_)
            document_ = []
            for sent in doc:
                tuples = sentence_tuples.get(sent)
                if tuples is None:
                    tuples = []
                document_.append((sent, tuples))
            documents_.append(document_)
        with open(save_path, "wb") as fo:
            pickle.dump(documents_, fo)


def extract_tuples_with_simplification(source_path, save_path):
    documents = load(source_path)
    documents_ = []
    with open(save_path, "w", encoding="utf-8") as fo:
        for document in documents:
            doc = [sent for sent, _ in document]
            sentence_tuples = defaultdict(list)
            for tuple_ in process_document(doc, True):
                sentence_tuples[tuple_.predicate.sentence].append(tuple_)
            document_ = []
            for sent in doc:
                tuples = sentence_tuples.get(sent)
                if tuples is None:
                    tuples = []
                document_.append((sent, tuples))
            documents_.append(document_)
        with open(save_path, "wb") as fo:
            pickle.dump(documents_, fo)


def annotate_documents_(source_path, save_path):
    documents = load(source_path)
    annotate_documents(documents, save_path)


if __name__ == "__main__":
    extract_tuples_from_raw_sentence("data/extraction_raw.txt", "data/tuples_spacy_raw.pkl")
    # extract_tuples_with_simplification("data/wiki_sentences_extraction.txt", "data/tuples_lexical.pkl")

    # with open("data/tuples_raw.pkl", "rb") as fi:
    #     documents1 = pickle.load(fi)
    #
    # with open("data/tuples_lexical.pkl", "rb") as fi:
    #     documents2 = pickle.load(fi)
    #
    # documents = merge_documents(documents1, documents2)
    # annotate_graph(documents, "data/annotated_docs.txt", "data/graph.pkl", semantic_graph=True)
    # join_optimize(documents, "data/graph.pkl", "data/tuples_refined.txt", 0.1, 0.2, 12)
    # join_optimize(documents, "data/graph.pkl", "data/graph1.pkl", 0.1, 0.2, 12, dump_graph=True)

    # documents = load("data/wiki_sentences_extraction.txt")
    # with open("data/clauses.txt", "w", encoding="utf-8") as fo:
    #     for document in documents:
    #         for sent, _ in document:
    #             original_tokens, chunks, nmods, adverbials, clauses = lexical_simplification_first(sent, restructurer)
    #             for clause in clauses:
    #                 fo.write(" ".join([token.word for token in clause]) + "\n")
    #             fo.write("\n")
    #         fo.write("==================\n")

    # original_tokens, chunks, nmods, adverbials, clauses = lexical_simplification_first(sentence, restructurer)
    # print(original_tokens)
    # print(chunks)
    # for key, values in adverbials.items():
    #     for value in values:
    #         print(" ".join([item.word for item in value]))


