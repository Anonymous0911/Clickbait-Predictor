from dataclasses import dataclass


# Same field names as clickbait_model's dataclasses; never import that module in tests.
@dataclass
class FakeSignals:
    curiosity_gap: float
    sensational_wording: float
    excessive_capitalization: float
    question_style: float
    exclamation_emphasis: float


@dataclass
class FakeResult:
    label: str
    clickbait_probability: float
    not_clickbait_probability: float
    confidence: float
    headline_probability: float
    thumbnail_probability: float
    signals: FakeSignals


class FakeDetector:
    def __init__(self):
        self.calls = 0

    def predict(self, rows):
        self.calls += 1
        results = []
        for row in rows:
            p = 0.9 if "believe" in row["headline"] else 0.1
            results.append(
                FakeResult(
                    label="clickbait" if p >= 0.5 else "not_clickbait",
                    clickbait_probability=p,
                    not_clickbait_probability=1.0 - p,
                    confidence=max(p, 1.0 - p),
                    headline_probability=p,
                    thumbnail_probability=0.5,
                    signals=FakeSignals(0.2, 0.3, 0.1, 0.0, 0.4),
                )
            )
        return results
