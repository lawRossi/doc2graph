from corenlp_util import is_copula
from clause_classification import ClauseClassifier

SV = "SV"
SP = "SP"
SPO = "SPO"
SPX = "SPX"
SPA = "SPA"
SPOA = "SPOA"
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

ATTR = "attr"
DOBJ = "dobj"
NSUBJ = "nsubj"
IOBJ = "iobj"
XCOMP = "xcomp"
ACOMP = "acomp"
PREP = "prep"
CCOMP = "ccomp"
COP = "cop"
AUXPASS = "auxpass"
EXPL = "expl"
AUX = "aux"
CONJ = "conj"
OPRD = "oprd"


class SpacyClauseClassifier(ClauseClassifier):
    def classify_clause(self, tree, index):
        in_relation = tree.in_coming_relation(index)
        if is_copula(tree.words[index].word):
            if AUX == in_relation or AUXPASS == in_relation:
                return None
            out_relations = tree.out_going_relations(index)
            if tree.get_subjects(index) and CCOMP in out_relations:
                return SVcC
            if tree.get_subjects(index) and XCOMP in out_relations:
                return SVcX
            if ATTR in out_relations and EXPL in out_relations:   # there be
                return SVb

        out_relations = tree.out_going_relations(index)
        conj = None
        conj_objects = None
        in_relation = tree.in_coming_relation(index)
        if in_relation == CONJ:
            conj = tree.parents[index]
            conj_objects = tree.get_objects(conj)

        if tree.get_subjects(index) and ATTR in out_relations:
            return SVc

        if tree.get_subjects(index) and DOBJ in out_relations and IOBJ in out_relations:
            return SVOO

        if tree.get_subjects(index) and DOBJ in out_relations and OPRD in out_relations:
            return SVOC

        if tree.get_subjects(index) and DOBJ in out_relations:
            return SVO
        elif conj and conj_objects and min(conj_objects) > index:
            return SVO

        if tree.get_subjects(index) and DOBJ not in out_relations and XCOMP in out_relations:  #
            return SVX

        if tree.get_subjects(index) and DOBJ not in out_relations and CCOMP in out_relations:  #
            return SVC

        if OPRD in out_relations and tree.get_subjects(index):
            return SVX

        if DOBJ not in out_relations and tree.get_subjects(index):
            return SV
