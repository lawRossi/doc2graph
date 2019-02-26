from corenlp_util import is_copula
from spacy_util import tokenize, extract_noun_chunks
from datastructure import Token
from operator import itemgetter
from sentence_structure import SentenceRestructurer
from corenlp_datastructure import CorenlpSentenceBuilder
from clause_detection import ClauseDetector, SpacyClauseDetector
from spacy_datastructure import SpacySentenceBuilder
from sentence_classification_spacy import SpacyClauseClassifier


class CorenlpDecomposer():
    def __init__(self):
        self.builder = CorenlpSentenceBuilder()
        clause_detector = ClauseDetector()
        self.restructurer = SentenceRestructurer(self.builder, clause_detector)

    def decompose_compound(self, sentence):
        tree = sentence.tree
        clauses = []
        idxes = sorted([idx for idx in tree.words.keys()], reverse=True)
        for idx in idxes:
            if tree.in_coming_relation(idx) == "cc":
                parent = tree.parents[idx]
                if not tree.words[parent].pos.startswith("VB"):
                    continue
                end = -1
                for idx_ in sorted(tree.children(parent)):
                    if tree.in_coming_relation(idx_) != "conj":
                        continue
                    end = max(end, idx_)
                    out_rels = tree.out_going_relations(idx_)
                    if "nsubj" in out_rels or "nsubjpass" in out_rels:
                        subtree = sorted(tree.get_subtree(idx_))
                        clause = [tree.words[node] for node in subtree if node in tree.words]
                    elif "dobj" in out_rels:
                        subtree = sorted(tree.get_subtree(idx_))
                        clause = [tree.words[node] for node in subtree if node in tree.words]
                        self.derive_copula(tree, idx_, clause)
                        has_subject = self.expand_clause(tree, clause, idx_, subtree)
                        if not has_subject:
                            continue
                    else:
                        subtree = sorted(tree.get_subtree(idx_))
                        clause = [tree.words[node] for node in subtree if node in tree.words]
                        self.derive_copula(tree, idx_, clause)
                        has_subject = self.expand_clause(tree, clause, idx_, subtree, False)
                        if not has_subject:
                            continue
                    clauses.append(clause)
                    tree.delete_subtree(subtree)
                # removing conjunction and punctuation
                for i in range(parent+1, end):
                    if tree.in_coming_relation(i) in ["cc", "punct"]:
                        del tree.words[i]
                        del tree.parents[i]
        clauses.append([item[1] for item in sorted(tree.words.items(), key=itemgetter(0))])
        return clauses

    def expand_clause(self, tree, clause, idx, subtree, subject_only=True):
        subjects = tree.get_subjects(idx)
        has_subject = len(subjects) > 0
        if not has_subject:
            return has_subject
        for node in tree.build_conjunction(subjects):
            clause.insert(0, node)
        if subject_only:
            return has_subject
        subtree_ = tree.get_subtree(tree.parents[idx], exclusion=["conj", "cc", "punct"])
        for node in sorted(subtree_):
            if node > idx and node not in subtree:
                clause.append(tree.words[node])
        return has_subject

    def derive_copula(self, tree, idx, clause):
        need_copula = False
        if tree.words[idx].pos == "VBG" or tree.words[idx].pos == "VBN":
            need_copula = True
            for child in tree.children(idx):
                if tree.dependent_relation(idx, child).startswith("aux") and is_copula(tree.words[child].word):
                    need_copula = False
                    break
        if need_copula:
            parent = tree.parents[idx]
            for child in tree.children(parent):
                if tree.dependent_relation(parent, child).startswith("aux") and is_copula(tree.words[child].word):
                    clause.insert(0, tree.words[child])
                    break

    def appositive_first(self, sentence, restructurer):
        """
        :param sentence: raw sentence
        :param restructurer:
        :return:
        """
        tokens = tokenize(sentence)
        tokens = [Token(token, None, i, i) for i, token in enumerate(tokens)]
        sent = self.builder.from_un_parsed_tokens(tokens)
        restructurer.apposition_first(sent)
        for sub_sent in sent.iter_subsentence():
            for clause in self.decompose_compound(sub_sent):
                yield clause

    def lexical_simplification_first(self, sentence, restructurer):
        """
        :param sentence: raw sentence
        :param restructurer:
        :return:
        """
        original_tokens, tokens, chunks = extract_noun_chunks(sentence)
        tokens = [Token(token[0], None, i, token[1]) for i, token in enumerate(tokens)]
        sentence = self.builder.from_un_parsed_tokens(tokens, False)
        # print(" ".join([token.word for token in sentence.tree.words.values()]))
        restructurer.extract_appositive(sentence)
        nmods = sentence.tree.get_noun_nmods()
        sentence = self.reparse(sentence, False)
        adverbials = sentence.tree.get_extra_adverbial()
        sentence = self.reparse(sentence, False)
        restructurer.restructure(sentence)
        clauses = []
        for sub_sent in sentence.iter_subsentence():
            for clause in self.decompose_compound(sub_sent):
                clauses.append(clause)
        return original_tokens, chunks, nmods, adverbials, clauses

    def compound_first(self, sentence, restructurer):
        tokens = tokenize(sentence)
        tokens = [Token(token, None, i, i) for i, token in enumerate(tokens)]
        sent = self.builder.from_un_parsed_tokens(tokens)
        clauses = list(self.decompose_compound(sent))
        if len(clauses) > 1:
            for clause in clauses:
                sent = self.builder.from_un_parsed_tokens(clause)
                for clause in self.appositive_first(sent, restructurer):
                    yield clause

    def reparse(self, sentence, merging_nouns=False, printing=False):
        left = sentence.left
        right = sentence.right
        sentence = self.builder.from_un_parsed_tokens(
            [item[1] for item in sorted(sentence.tree.words.items(), key=itemgetter(0))], merging_nouns, printing=printing
        )
        sentence.left = left
        sentence.right = right
        return sentence


class SpacyDecomposer(CorenlpDecomposer):
    def __init__(self):
        super().__init__()
        self.builder = CorenlpSentenceBuilder()
        clause_detector = ClauseDetector()
        self.restructurer = SentenceRestructurer(self.builder, clause_detector)

    def decompose_compound(self, sentence):
        tree = sentence.tree
        clauses = []
        idxes = sorted([idx for idx in tree.words.keys()], reverse=True)
        for idx in idxes:
            if tree.words[idx].pos.startswith("VB") and tree.in_coming_relation(idx) == "conj":
                parent = tree.parents[idx]
                end = -1
                end = max(end, idx_)
                out_rels = tree.out_going_relations(idx_)
                if "nsubj" in out_rels or "nsubjpass" in out_rels:
                    subtree = sorted(tree.get_subtree(idx_))
                    clause = [tree.words[node] for node in subtree if node in tree.words]
                elif "dobj" in out_rels:
                    subtree = sorted(tree.get_subtree(idx_))
                    clause = [tree.words[node] for node in subtree if node in tree.words]
                    self.derive_copula(tree, idx_, clause)
                    has_subject = self.expand_clause(tree, clause, idx_, subtree)
                    if not has_subject:
                        continue
                else:
                    subtree = sorted(tree.get_subtree(idx_))
                    clause = [tree.words[node] for node in subtree if node in tree.words]
                    self.derive_copula(tree, idx_, clause)
                    has_subject = self.expand_clause(tree, clause, idx_, subtree, False)
                    if not has_subject:
                        continue
                clauses.append(clause)
                tree.delete_subtree(subtree)
                # removing conjunction and punctuation
                for i in range(parent+1, end):
                    if tree.in_coming_relation(i) in ["cc", "punct"]:
                        del tree.words[i]
                        del tree.parents[i]
        clauses.append([item[1] for item in sorted(tree.words.items(), key=itemgetter(0))])
        return clauses


if __name__ == "__main__":
    # decompose("data/paragraph.txt", "data/sentence_decompositions.txt")
    # extract_tuples("data/sentence_decompositions.txt", "data/sentences_with_tuples.pkl")
    # sentence = " ".join(tokenize("The festival was traditionally a time to honour deities as well as ancestors. "))
    # sentence = " ".join(tokenize("In 2018, the first day of the Lunar New Year was on Friday, 16 February, initiating the year of the Dog."))
    # sentence = " ".join(tokenize("Observances traditionally take place from the evening preceding the first day of the year to the Lantern Festival, held on the 15th day of the year."))
    sentence = " ".join(tokenize("He received national attention in 2004 with his March primary win, his well-received July Democratic National Convention keynote address, and his landslide November election to the Senate."))
    # for comb in decompose_sentence(sentence, True):
    #     for clause in comb:
    #         print(" ".join([token.word for token in clause]))
    #     print()
