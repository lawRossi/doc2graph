ACL = "acl"
ACL_RELCL = "acl:relcl"
RELCL = "relcl"
ADVCL = "advcl"
CCOMP = "ccomp"
XCOMP = "xcomp"
NSUBJ = "nsubj"
NSUBPASS = "nsubjpass"
CSUBJ = "csubj"
PUNCT = "punct"
POBJ = "pobj"
CASE = "case"
DEP = "dep"
NMOD = "nmod"

VBN = "VBN"
VB = "VB"
VBG = "VBG"
DOBJ = "dobj"
APPOS = "appos"
VBD = "VBD"
NN = "NN"
JJ = "JJ"
PREP = "IN"
TO = "to"

CORE = "CORE"
OBJCL = "OBJCL"
APPOSCL = "APPOSCL"
SUBJCL = "SUBJCL"
PARADVCL = "PARADVCL"
PARACL = "PARACL"
INFINITE = "INFINITE"


class ClauseDetector():
    def get_potential_point(self, sentence):
        """
        collecting potential words where decomposition should take place
        :param sentence:
        :return:
        """
        tree = sentence.tree
        points = []
        for idx in tree.words:
            if tree.in_coming_relation(idx) in [ADVCL, ACL, ACL_RELCL, RELCL, APPOS, CCOMP, CSUBJ, XCOMP, NMOD]:
                points.append(idx)
        return points

    def classify_clause(self, sentence, root):
        tree = sentence.tree
        token = tree.words[root]
        parent = tree.parents[root]
        out_rels = tree.out_going_relations(root)

        if tree.in_coming_relation(root) == APPOS and tree.words[parent].pos.startswith(NN):
            return APPOS

        elif tree.in_coming_relation(root) == ADVCL:
            if (token.pos == VBG or token.pos == VBN) and NSUBPASS not in out_rels and NSUBJ not in out_rels:
                return PARADVCL   # the boy, waving his arms, cried
            elif root-1 in tree.words and tree.words[root-1].word == TO:
                return INFINITE
            elif NSUBJ in out_rels or NSUBPASS in out_rels:
                return ADVCL

        elif tree.in_coming_relation(root) in [ACL, ACL_RELCL, RELCL]:
            if (token.pos == VBG or token.pos == VBN) and NSUBPASS not in out_rels and NSUBJ not in out_rels:
                return PARACL   # the boy, waving his arms, cried
            elif root-1 in tree.words and tree.words[root-1].word == TO:
                return INFINITE
            elif parent < root:
                return ACL

        elif tree.in_coming_relation(root) == CCOMP:
            if NSUBPASS in out_rels or NSUBJ in out_rels:
                if DOBJ not in tree.out_going_relations(parent):
                    parent = tree.words[parent]
                    if parent.pos.startswith(NN):
                        return APPOSCL
                    else:
                        return OBJCL
            elif tree.words[root].pos.startswith(NN):
                return NN
            elif tree.words[root].pos == JJ:
                return JJ

        elif tree.in_coming_relation(root) == XCOMP:
            if (tree.words[root].pos == VBG or tree.words[root].pos == VBN) and root > parent:
                for idx in range(parent+1, root):
                    if idx in tree.words and tree.words[idx].word == ",":
                        return PARADVCL

        elif tree.in_coming_relation(root) == CSUBJ:
            return SUBJCL

        elif tree.in_coming_relation(root) == NMOD:
            for child in tree.children(root):
                if tree.dependent_relation(root, child) == CASE and tree.words[child].pos == VBG:
                    if tree.words[parent].pos.startswith("NN"):
                        return PARACL
                    elif tree.words[parent].pos.startswith("VB"):
                        return PARADVCL
        return CORE


class SpacyClauseDetector():
    def get_potential_point(self, sentence):
        """
        collecting potential words where decomposition should take place
        :param sentence:
        :return:
        """
        tree = sentence.tree
        points = []
        for idx in tree.words:
            if tree.in_coming_relation(idx) in [ADVCL, ACL, ACL_RELCL, RELCL, APPOS, CCOMP, CSUBJ]:
                points.append(idx)
            elif tree.in_coming_relation(idx) == PREP and tree.words[idx].pos == VBG:
                points.append(idx)
        return points

    def classify_subtree(self, sentence, root):
        tree = sentence.tree
        token = tree.words[root]
        parent = tree.parents[root]
        out_rels = tree.out_going_relations(root)

        if tree.in_coming_relation(root) == APPOS and tree.words[parent].pos.startswith(NN):
            return APPOS

        elif tree.in_coming_relation(root) == ADVCL:
            if (token.pos == VBG or token.pos == VBN) and NSUBPASS not in out_rels and NSUBJ not in out_rels:
                return PARADVCL  # the boy, waving his arms, cried
            elif root - 1 in tree.words and tree.words[root - 1].word == TO:
                return INFINITE
            elif NSUBJ in out_rels or NSUBPASS in out_rels:
                return ADVCL
            elif tree.words[root].pos.startswith(NN):  # for spacy
                return NN
            elif tree.words[root].pos == JJ:  # for spacy
                return JJ

        elif tree.in_coming_relation(root) in [ACL, ACL_RELCL, RELCL]:
            if (token.pos == VBG or token.pos == VBN) and NSUBPASS not in out_rels and NSUBJ not in out_rels:
                return PARACL  # the boy, waving his arms, cried
            elif root - 1 in tree.words and tree.words[root - 1].word == TO:
                return INFINITE
            elif parent < root:
                return ACL

        elif tree.in_coming_relation(root) == CCOMP:
            if NSUBPASS in out_rels or NSUBJ in out_rels:
                if DOBJ not in tree.out_going_relations(parent):
                    parent = tree.words[parent]
                    if parent.pos.startswith(NN):
                        return APPOSCL
                    else:
                        return OBJCL

        elif tree.in_coming_relation(root) == CSUBJ:
            return SUBJCL

        elif tree.in_coming_relation(root) == PREP and tree.words[root].pos == "VBG":
            parent = tree.parents[root]
            if tree.words[parent].pos.startswith("NN"):
                return PARACL
            elif tree.words[parent].pos.startswith("VB"):
                return PARADVCL
        return CORE
