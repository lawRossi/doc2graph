import clause_detection
from datastructure import Token
from operator import itemgetter
from spacy_util import stem


LEFT2RIGHT_PARSE_ONCE = "left to right; parse once"
LEFT2RIGHT_PARSE_MULTIPLE = "left to righ; parse multiple"
APPOSITION_FIRST = "apposition first"


class ClauseMessage():
    def __init__(self, clause_type, mark, linking_word):
        self.clause_type = clause_type
        self.mark = mark
        self.linking_word = linking_word

    def __str__(self):
        return self.clause_type


class SentenceRestructurer():
    def __init__(self, sentence_builder, clause_detector):
        self.sentence_builder = sentence_builder
        self.clause_detector = clause_detector

    def restructure(self, sentence, strategy=LEFT2RIGHT_PARSE_ONCE):
        if strategy == LEFT2RIGHT_PARSE_ONCE:
            self.left2right_parse_once(sentence)
        elif strategy == LEFT2RIGHT_PARSE_MULTIPLE:
            self.left2right_parse_multiple(sentence)
        elif strategy == APPOSITION_FIRST:
            self.apposition_first(sentence)

    def left2right_parse_once(self, sentence):
        tree = sentence.tree
        nodes = self.clause_detector.get_potential_point(sentence)
        for node in nodes:
            if node in tree.words:
                clause_type = self.clause_detector.classify_clause(sentence, node)
                if clause_type != clause_detection.CORE:
                    self.process_clause(sentence, node, clause_type)
                    sentence.clause = " ".join([item[1].word for item in sorted(tree.words.items(), key=itemgetter(0))])
        if sentence.left:
            for _, sent in sentence.left:
                self.restructure(sent)
        if sentence.right:
            for _, sent in sentence.right:
                self.restructure(sent)

    def left2right_parse_multiple(self, sentence):
        tree = sentence.tree
        token_num = len(tree.words)
        nodes = self.clause_detector.get_potential_point(sentence)
        processed = False
        for node in nodes:
            if node in tree.words:
                clause_type = self.clause_detector.classify_clause(sentence, node)
                if clause_type != clause_detection.CORE:
                    self.process_clause(sentence, node, clause_type)
                    processed = True
                    break
        if processed and len(tree.words) != token_num:
            # re-parse the sentence
            sent = self.sentence_builder.from_un_parsed_tokens([item[1] for item in sorted(tree.words.items(), key=itemgetter(0))])
            sentence.clause = sent.clause
            sentence.tree = sent.tree
            # recursive call
            self.restructure(sent)

        if sentence.left:
            for _, sent in sentence.left:
                self.restructure(sent)
        if sentence.right:
            for _, sent in sentence.right:
                self.restructure(sent)

    def apposition_first(self, sentence):
        tree = sentence.tree
        token_num = len(tree.words)
        self.extract_appositive(sentence)
        if len(tree.words) != token_num:
            # re-parse the sentence
            sent = self.sentence_builder.from_un_parsed_tokens(
                [item[1] for item in sorted(tree.words.items(), key=itemgetter(0))])
            sentence.clause = sent.raw_sentence
            sentence.tree = sent.tree
            self.apposition_first(sentence)
        else:
            self.left2right_parse_once(sentence)

    def extract_appositive(self, sentence):
        tree = sentence.tree
        idxes = sorted([idx for idx in tree.words.keys()], reverse=True)
        for idx in idxes:
            if tree.in_coming_relation(idx) == "appos":
                parent = tree.parents[idx]
                comma_num = 0
                for i in range(parent + 1, idx):
                    if i in tree.words and tree.words[i].word == ",":
                        comma_num += 1
                if comma_num < 2:
                    subtree, clause = self.extract_appositive_clause(tree, idx)
                else:
                    subtree, clause = self.extract_appositive_clause(tree, idx, False)
                sent = self.sentence_builder.from_un_parsed_tokens(clause)
                message = ClauseMessage(clause_detection.APPOS, None, None)
                sentence.left.append((message, sent))
                tree.delete_subtree(subtree)

    def extract_appositive_clause(self, tree, idx, normal=True):
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree]
        if normal:
            conjunction = tree.get_conjunction(tree.parents[idx])
            conjunction.insert(0, tree.parents[idx])
            conjunction = tree.build_conjunction(conjunction)
            n = 0
            for i, token in enumerate(conjunction):
                if token.idx + 1 < idx:
                    n += 1
                    clause.insert(i, token)
            clause.insert(n, Token("be", "VBZ", -1, -1))
        else:  # get the nearest noun
            flag = False
            for i in range(idx-1, 0, -1):
                if i in tree.words:
                    if tree.words[i].word == ",":
                        flag = True
                    elif tree.words[i].pos.startswith("NN") and flag:
                        clause.insert(0, Token("be", "VBZ", -1, -1))
                        clause.insert(0, tree.words[i])
                        break
        return subtree, clause

    def process_clause(self, sentence, idx, clause_type):
        if clause_type == clause_detection.SUBJCL:
            self.process_subject_clause(sentence, idx)
        elif clause_type == clause_detection.OBJCL:
            self.process_object_clause(sentence, idx)
        elif clause_type == clause_detection.ACL:
            self.process_adjective_clause(sentence, idx)
        elif clause_type == clause_detection.ADVCL:
            self.process_adverb_clause(sentence, idx)
        elif clause_type == clause_detection.PARADVCL:
            self.process_paradvcl(sentence, idx)
        elif clause_type == clause_detection.PARACL:
            self.process_paracl(sentence, idx)
        elif clause_type == clause_detection.INFINITE:
            self.process_infinite(sentence, idx)
        elif clause_type == clause_detection.NN:
            self.process_noun_adjective_phrase(sentence, idx)
        elif clause_type == clause_detection.JJ:
            self.process_noun_adjective_phrase(sentence, idx)

    def process_noun_adjective_phrase(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree]
        clause[0].word = clause[0].word.lower()  # lower case
        subjects = tree.get_subjects(parent)
        if not subjects:
            return
        conjunction = tree.build_conjunction(subjects)
        for i, token in enumerate(conjunction):
            clause.insert(i, token)
        clause.insert(len(conjunction), Token("be", "VBZ", -1, -1))
        sent = self.sentence_builder.from_un_parsed_tokens(clause)
        message = ClauseMessage(clause_detection.ADVCL, None, None)
        sentence.left.append((message, sent))
        tree.delete_subtree(subtree)

    def process_subject_clause(self, sentence, idx):
        return

    def process_object_clause(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree]
        mark = None
        if clause[0].word == "that":
            del clause[0]
            mark = "that"
        message = ClauseMessage(clause_detection.OBJCL, mark, tree.words[parent])
        sent = self.sentence_builder.from_un_parsed_tokens(clause)
        sentence.right.append((message, sent))
        tree.delete_subtree(subtree)

    def process_adjective_clause(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree]
        subjects = tree.get_subjects(idx)
        mark = None
        if not subjects or len(subjects) == 1 and tree.words[subjects[0]].word in ["who", "that", "which"]:
            if subjects:
                node = clause.pop(0)
                mark = node.word
            conjunction = tree.get_conjunction(parent)
            conjunction.insert(0, parent)
            conjunction = tree.build_conjunction(conjunction)
            for i, token in enumerate(conjunction):
                if token.idx + 1 < idx:
                    clause.insert(i, token)
        else:
            mark = clause[0].word
        if len(clause) != len(tree.words):  # to avoid bad case like "Rolling created"
            message = ClauseMessage(clause_detection.ACL, mark, tree.words[parent])
            sent = self.sentence_builder.from_un_parsed_tokens(clause)
            sentence.right.append((message, sent))
            tree.delete_subtree(subtree)

    def process_adverb_clause(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree]
        mark = clause[0].word
        message = ClauseMessage(clause_detection.ADVCL, mark, tree.words[parent])
        sent = self.sentence_builder.from_un_parsed_tokens(clause)
        sentence.left.append((message, sent))
        tree.delete_subtree(subtree, True)

    def process_infinite(self, sentence, idx):
        tree = sentence.tree
        subtree = sorted(tree.get_subtree(idx))
        subtree = subtree[subtree.index(idx)-1:]
        tree.delete_subtree(subtree)

    def process_paradvcl(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree if tree.dependent_relation(idx, node) != 'mark']  # drop mark word
        clause[0].word = clause[0].word.lower()  # lower case
        mark = None
        if subtree[0] != idx:
            mark = clause[0].word
            clause.pop(0)

        subjects = tree.get_subjects(parent)
        subjects = tree.build_conjunction(subjects)
        if tree.words[idx].pos == clause_detection.VBN:
            clause.insert(0, Token("be", "VBZ", -1, -1))
            for i, token in enumerate(subjects):
                clause.insert(i, token)
        else:
            tree.words[idx].word = stem(tree.words[idx].word)
            objects = tree.get_objects(parent)
            if not objects:
                for i, token in enumerate(subjects):
                    clause.insert(i, token)
            elif idx-1 in tree.words and tree.words[idx-1].pos == clause_detection.PREP:
                token = tree.words[idx-1]
                if token.word == "by":
                    for i, token in enumerate(subjects):
                        clause.insert(i, token)
                else:
                    objects = tree.build_conjunction(objects)
                    for i, token in enumerate(objects):
                        clause.insert(i, token)
            else:
                for i, token in enumerate(subjects):
                    clause.insert(i, token)

        sent = self.sentence_builder.from_un_parsed_tokens(clause)
        message = ClauseMessage(clause_detection.ADVCL, mark, tree.words[parent])
        sentence.left.append((message, sent))
        tree.delete_subtree(subtree)

    def process_paracl(self, sentence, idx):
        tree = sentence.tree
        parent = tree.parents[idx]
        subtree = sorted(tree.get_subtree(idx))
        clause = [tree.words[node] for node in subtree if tree.dependent_relation(idx, node) != 'mark']  # drop mark word
        conjunction = tree.get_conjunction(parent)
        conjunction.insert(0, parent)
        conjunction = tree.build_conjunction(conjunction)
        for i, token in enumerate(conjunction):
            # if token.idx + 1 < idx:
            clause.insert(i, token)
        if tree.in_coming_relation(idx) == "nmod":
            for child in tree.children(idx):
                if tree.dependent_relation(idx, child) == "case" and tree.words[child].pos == "VBG":
                    idx = child
                    break
        if tree.words[idx].pos == "VBG":
            tree.words[idx].word = stem(tree.words[idx].word)
        else:
            clause.insert(len(conjunction), Token("be", "VBZ", -1, -1))
        sent = self.sentence_builder.from_un_parsed_tokens(clause)
        message = ClauseMessage(clause_detection.ACL, None, None)
        sentence.left.append((message, sent))
        tree.delete_subtree(subtree)
