from datastructure import SyntaxTree, SentenceBuilder
import corenlp_util
import spacy_util
from collections import defaultdict


class SpacySynaxTree(SyntaxTree):
    """
    SyntaxTree for corenlp parser
    """
    def __init__(self, tokens, dependencies):
        super().__init__(tokens, dependencies)

    def get_conjunction(self, index):
        conjunctions = []
        for child in self.children(index):
            if self.dependent_relation(index, child) == "conj":
                conjunctions.append(child)
                break
        if len(conjunctions) == 1:
            index = conjunctions[0]
            while index:
                for child in self.children(index):
                    if self.dependent_relation(index, child) == "conj":
                        conjunctions.append(child)
                        index = child
                        break
                else:
                    index = None
        return conjunctions

    def expand_nounphrase(self, span):
        head = self.get_phrase_head(span)
        span_ = [item for item in span]    # copy
        for child in self.children(head):
            if self.dependent_relation(head, child) in ["amod", "det", "nummod", "quantmod", "nn", "compound", "nmod:poss"]:
                span_.extend(self.get_subtree(child))
            elif self.dependent_relation(head, child) == "prep" and self.words[child].word == "of":
                span_.extend(self.get_subtree(child))
        return span_

    def get_adverbial(self):
        adverbials = defaultdict(list)
        removals = []
        for index in self.words:
            if self.words[index].pos.startswith("VB") and self.graph.has_node(index):
                for child in self.graph.neighbors(index):
                    if self.dependent_relation(index, child) == "prep" and self.words[child].pos != "VBG" \
                            and "pobj" in self.out_going_relations(child):
                        subtree = sorted(self.get_subtree(child))
                        removals.append(subtree)
                        for item in self.derive_adverbial(child):
                            subtree_ = self.trim_subtree(item)
                            if subtree_:
                                adverbials[self.words[index].idx].append(
                                    [self.words[node] for node in sorted(subtree_)])
        for subtree in removals:
            self.delete_subtree(subtree)
        return adverbials

    def derive_adverbial(self, node):
        adverbials = self._derive_adverbial(node)
        conjunctions = self.get_conjunction(node)
        for conjunction in conjunctions:
            adverbials.extend(self._derive_adverbial(conjunction))
        return adverbials

    def _derive_adverbial(self, node):
        adverbial = []
        if self.words[node].word in ["between", "among"]:
            adverbial.append(self.get_subtree(node))
            return adverbial
        adverbial.append(self.get_subtree(node, exclusion=["conj", "cc", "punct"]))
        pobj = None
        for child in self.children(node):
            if self.dependent_relation(node, child) == "pobj":
                pobj = child
                break
        conjunctions = self.get_conjunction(pobj)
        for conj in conjunctions:
            subtree = self.get_subtree(conj, exclusion=["conj", "cc", "punct"])
            subtree.insert(0, node)
            adverbial.append(subtree)
        return adverbial

    def trim_subtree(self, subtree):
        i = 0
        n = len(subtree)
        while i < n:
            node = subtree[i]
            if self.in_coming_relation(node) == "prep":
                if self.words[node].pos == "VBG":
                    subtree = self.trim_at(subtree, node)
                    i = 0
                    n = len(subtree)
                else:
                    i += 1
            elif self.in_coming_relation(node) in ["acl", "advcl", "acl:relcl", "relcl"]:
                subtree = self.trim_at(subtree, node)
                i = 0
                n = len(subtree)
            else:
                i += 1
        return subtree

    def trim_at(self, subtree, node):
        subtree = [node for node in subtree]  # copy
        subtree_ = self.get_subtree(node)
        for node_ in subtree_:
            if node_ in subtree:
                subtree.remove(node_)
        return subtree

    def get_extra_adverbial(self):
        adverbials = defaultdict(list)
        removals = []
        for index in self.words:
            if self.words[index].pos.startswith("VB") and self.graph.has_node(index):
                n = 0
                for child in sorted(self.children(index)):
                    if self.dependent_relation(index, child) == "prep" and self.words[child].pos != "VBG" \
                            and "pobj" in self.out_going_relations(child):
                        n += 1
                        if n > 1:
                            subtree = sorted(self.get_subtree(child))
                            removals.append(subtree)
                            for item in self.derive_adverbial(child):
                                subtree_ = self.trim_subtree(item)
                                if subtree_:
                                    adverbials[self.words[index].idx].append([self.words[node] for node in subtree_])
        for sub_tree in removals:
            self.delete_subtree(sub_tree)
        return adverbials

    def get_noun_nmods(self):
        """
        retrieving nmods that modify nouns.
        :return:
        """
        nmods = defaultdict(list)
        removals = []
        for index in self.words:
            if self.words[index].pos.startswith("NN"):
                for child in self.children(index):
                    if self.dependent_relation(index, child) == "prep" and self.words[child].pos != "VBG":
                        subtree = sorted(self.get_subtree(child))
                        subtree_ = self.trim_subtree(subtree)
                        nmods[self.words[index].original_idx].append([self.words[node] for node in subtree_])
                        removals.append(subtree)  # the home to endangered animals including ...

        for sub_tree in removals:
            self.delete_subtree(sub_tree)
        return nmods


class SpacySentenceBuilder(SentenceBuilder):
    def __init__(self):
        super().__init__()
        self.syntaxtree_class = SpacySynaxTree

    def parse(self, sentence):
        return spacy_util.parse(sentence)

    def chunk_nouns(self, sentence):
        return spacy_util.chunk_nouns(sentence)

    def chunk_verbs(self, tree):
        corenlp_util.merge_verb_phrase(tree)
