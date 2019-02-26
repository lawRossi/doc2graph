from corenlp_util import is_copula


SV = "SV"
SP = "SP"
SPO = "SPO"
SPA = "SPA"
SPOA = "SPOA"
SPX = "SPX"
SVA = "SVA"
SVO = "SVO"
SVOO = "SVOO"
SVOOA = "SVOOA"
SVOA = "SVOA"
SVOC = "SVOC"
SVC = "SVC"
SVX = "SVX"
SVc = "SVc"
SVcC = "SVcC"
SVcO = "SVcO"
SVcA = "SVcA"
SVcX = "SVcX"
SVb = "SVb"

DOBJ = "dobj"
NSUBJ = "nsubj"
IOBJ = "iobj"
XCOMP = "xcomp"
NMOD = "nmod"
CCOMP = "ccomp"
COP = "cop"
AUXPASS = "auxpass"
EXPL = "expl"
AUX = "aux"
CONJ = "conj"


class ClauseClassifier():
    def classify_clause(self, tree, index):
        raise NotImplementedError


class CorenlpClauseClassifier(ClauseClassifier):
    def classify_clause(self, tree, index):
        if is_copula(tree.words[index].word):
            in_relation = tree.in_coming_relation(index)
            if COP == in_relation:
                return SVc

            if AUX == in_relation or AUXPASS == in_relation:
                return None

            out_relations = tree.out_going_relations(index)
            if tree.get_subjects(index) and CCOMP in out_relations:
                return SVcC
            if tree.get_subjects(index) and XCOMP in out_relations:
                return SVcX
            if tree.get_subjects(index) and EXPL in out_relations:   # there be
                return SVb

        out_relations = tree.out_going_relations(index)
        conj = None
        conj_objects = None

        if tree.get_subjects(index) and DOBJ in out_relations and IOBJ in out_relations:
            return SVOO

        if tree.get_subjects(index) and DOBJ in out_relations and XCOMP in out_relations:
            return SVOC

        if tree.get_subjects(index) and DOBJ in out_relations:
            return SVO
        elif conj and conj_objects and min(conj_objects) > index:
            return SVO

        if tree.get_subjects(index) and DOBJ not in out_relations and XCOMP in out_relations:  #
            return SVX

        if tree.get_subjects(index) and DOBJ not in out_relations and CCOMP in out_relations:  #
            return SVC

        if DOBJ not in out_relations and tree.get_subjects(index):
            return SV
