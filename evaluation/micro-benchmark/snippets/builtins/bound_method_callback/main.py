class Scorer:
    def score(self, word):
        return len(word)

scorer = Scorer()
sorted(["bb", "a"], key=scorer.score)
