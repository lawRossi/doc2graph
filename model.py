from tuple_extraction import openie, restructurer
from tuple_extraction import build_tuple
import pickle


def chunk(sentence):
    pass


def load_data(path):
    with open(path, encoding="utf-8") as fi:
        sentences = []
        sentence = []
        for line in fi:
            line = line.strip()
            if not line:
                if sentence:
                    sentences.append(sentence)
                    sentence = []
                continue
            if line[0].isdigit():
                splits = line.split("\t")
                sentence.append(splits)
    data = []
    for sentence in sentences:
        try:
            words = [item[1] for item in sentence]
            pos = [item[4] for item in sentence]
            dependencies = []
            for item in sentence:
                if item[7] == "nsubj:pass":
                    item[7] = "nsubjpass"
                dependencies.append((int(item[6]), int(item[0]), item[7]))
            data.append({"words": words, "pos_tags": pos, "dependencies": dependencies})
        except:
            print("error")
    return data


def generate_positive_samples():
    sentences = load_data("data/UD_English-EWT-r1.4/en-ud-dev.conllu")
    samples = []
    for sentence in sentences[120:125]:
        sample = {"sentence": sentence}
        sentence_ = Sentence.from_parsing_result(sentence)
        restructurer.apposition_first(sentence_)
        sample["tuples"] = list(openie.process_sentence(sentence_))
        samples.append(sample)
    with open("data/positive_tuples.pkl", "wb") as fo:
        pickle.dump(samples, fo)


if __name__ == "__main__":
    generate_positive_samples()
    with open("data/positive_tuples.pkl", "rb") as fi:
        samples = pickle.load(fi)
        for sentence in samples:
            for tuple_ in sentence["tuples"]:
                print(tuple_["clause"])
                print(build_tuple(tuple_))
