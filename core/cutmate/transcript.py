from dataclasses import asdict, dataclass, replace


@dataclass
class Word:
    word: str
    start: float
    end: float
    prob: float | None = None


@dataclass
class Transcript:
    language: str
    words: list[Word]
    backend: str

    def to_json(self) -> dict:
        return {"language": self.language, "backend": self.backend, "words": [asdict(w) for w in self.words]}

    @classmethod
    def from_json(cls, d: dict) -> "Transcript":
        return cls(d["language"], [Word(**w) for w in d["words"]], d["backend"])

    def text(self) -> str:
        return " ".join(w.word for w in self.words)

    def suspects(self, max_len: float = 1.0) -> list[Word]:
        """Words longer than max_len — usually a stumble + retake the model collapsed into one word."""
        return [w for w in self.words if w.end - w.start > max_len]

    def shifted(self, offset: float) -> "Transcript":
        return replace(self, words=[replace(w, start=round(w.start + offset, 3), end=round(w.end + offset, 3))
                                    for w in self.words])
