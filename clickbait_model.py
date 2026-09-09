from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import joblib
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from transformers import CLIPModel, CLIPProcessor, DistilBertModel, DistilBertTokenizer


def _batch(items: Sequence, batch_size: int) -> Iterable[Sequence]:
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _normalize_text(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip()


def _normalize_path(value) -> Path | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    return path if path.exists() else None


@dataclass
class ExplainableSignals:
    curiosity_gap: float
    sensational_wording: float
    excessive_capitalization: float
    question_style: float
    exclamation_emphasis: float


@dataclass
class PredictionResult:
    label: str
    clickbait_probability: float
    not_clickbait_probability: float
    confidence: float
    headline_probability: float
    thumbnail_probability: float
    signals: ExplainableSignals


class ClickbaitDetector:
    """Multimodal clickbait detector using DistilBERT, CLIP, and learned fusion."""

    def __init__(
        self,
        text_model_name: str = "distilbert-base-uncased",
        vision_model_name: str = "openai/clip-vit-base-patch32",
        device: str | None = None,
        batch_size: int = 8,
    ):
        self.text_model_name = text_model_name
        self.vision_model_name = vision_model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self.tokenizer = DistilBertTokenizer.from_pretrained(text_model_name)
        self.text_encoder = DistilBertModel.from_pretrained(text_model_name).to(self.device)
        self.text_encoder.eval()
        self.image_processor = CLIPProcessor.from_pretrained(vision_model_name)
        self.image_encoder = CLIPModel.from_pretrained(vision_model_name).to(self.device)
        self.image_encoder.eval()
        self.text_embedding_dim = int(self.text_encoder.config.dim)
        self.image_embedding_dim = int(self.image_encoder.config.projection_dim)
        self.text_classifier: LogisticRegression | None = None
        self.image_classifier: LogisticRegression | None = None
        self.fusion_classifier: LogisticRegression | None = None

    def fit(self, rows) -> "ClickbaitDetector":
        records = self._to_records(rows)
        headlines = [self._pick_headline(record) for record in records]
        thumbnails = [self._pick_thumbnail(record) for record in records]
        labels = np.asarray([self._pick_label(record) for record in records], dtype=np.int64)
        text_features = self._encode_texts(headlines)
        image_features = self._encode_images(thumbnails)

        self.text_classifier = LogisticRegression(max_iter=2000, class_weight="balanced")
        self.image_classifier = LogisticRegression(max_iter=2000, class_weight="balanced")
        self.fusion_classifier = LogisticRegression(max_iter=2000, class_weight="balanced")
        self.text_classifier.fit(text_features, labels)
        self.image_classifier.fit(image_features, labels)
        self.fusion_classifier.fit(self._modality_features(text_features, image_features), labels)
        return self

    def predict_proba(self, rows) -> np.ndarray:
        self._require_classifiers()
        records = self._to_records(rows)
        headlines = [self._pick_headline(record) for record in records]
        thumbnails = [self._pick_thumbnail(record) for record in records]
        text_features = self._encode_texts(headlines)
        image_features = self._encode_images(thumbnails)
        return self.fusion_classifier.predict_proba(self._modality_features(text_features, image_features))

    def predict(self, rows, threshold: float = 0.5) -> list[PredictionResult]:
        self._require_classifiers()
        records = self._to_records(rows)
        headlines = [self._pick_headline(record) for record in records]
        thumbnails = [self._pick_thumbnail(record) for record in records]
        text_features = self._encode_texts(headlines)
        image_features = self._encode_images(thumbnails)
        headline_probabilities = self.text_classifier.predict_proba(text_features)[:, 1]
        thumbnail_probabilities = self.image_classifier.predict_proba(image_features)[:, 1]
        fusion_probabilities = self.fusion_classifier.predict_proba(
            self._modality_features(text_features, image_features)
        )[:, 1]

        results: list[PredictionResult] = []
        for index, probability in enumerate(fusion_probabilities):
            probability = float(probability)
            results.append(
                PredictionResult(
                    label="clickbait" if probability >= threshold else "not_clickbait",
                    clickbait_probability=probability,
                    not_clickbait_probability=1.0 - probability,
                    confidence=max(probability, 1.0 - probability),
                    headline_probability=float(headline_probabilities[index]),
                    thumbnail_probability=float(thumbnail_probabilities[index]),
                    signals=self.explain(headlines[index], thumbnails[index]),
                )
            )
        return results

    def explain(self, headline: str, thumbnail: Path | None = None) -> ExplainableSignals:
        text = _normalize_text(headline)
        words = text.split()
        lower_text = text.lower()
        curiosity_terms = ("you won't believe", "you will not believe", "what happened next", "secret", "revealed", "shocking")
        sensational_terms = ("breaking", "urgent", "insane", "amazing", "scandal", "exposed", "destroyed", "viral", "incredible")
        curiosity = min(1.0, sum(term in lower_text for term in curiosity_terms) / 2.0)
        sensational = min(1.0, sum(term in lower_text for term in sensational_terms) / 3.0)
        capital_words = sum(word.isalpha() and len(word) > 2 and word.isupper() for word in words)
        capitalization = min(1.0, capital_words / max(1, len(words)) * 2.0)
        question_style = 1.0 if text.rstrip().endswith("?") else 0.0
        exclamation_emphasis = min(1.0, text.count("!") / 2.0)

        if thumbnail is not None:
            try:
                image = np.asarray(Image.open(thumbnail).convert("RGB"))
                visual_intensity = min(1.0, float(image.std(axis=(0, 1)).mean()) / 64.0)
                exclamation_emphasis = min(1.0, exclamation_emphasis * 0.8 + visual_intensity * 0.2)
            except OSError:
                pass
        return ExplainableSignals(curiosity, sensational, capitalization, question_style, exclamation_emphasis)

    def save(self, path: str | Path) -> None:
        self._require_classifiers()
        joblib.dump(
            {
                "text_model_name": self.text_model_name,
                "vision_model_name": self.vision_model_name,
                "batch_size": self.batch_size,
                "text_classifier": self.text_classifier,
                "image_classifier": self.image_classifier,
                "fusion_classifier": self.fusion_classifier,
            },
            Path(path),
        )

    @classmethod
    def load(cls, path: str | Path, device: str | None = None) -> "ClickbaitDetector":
        payload = joblib.load(Path(path))
        detector = cls(
            text_model_name=payload["text_model_name"],
            vision_model_name=payload["vision_model_name"],
            device=device,
            batch_size=payload["batch_size"],
        )
        detector.text_classifier = payload["text_classifier"]
        detector.image_classifier = payload["image_classifier"]
        detector.fusion_classifier = payload["fusion_classifier"]
        return detector

    def _encode_texts(self, headlines: Sequence[str]) -> np.ndarray:
        features: list[np.ndarray] = []
        for batch in _batch(list(headlines), self.batch_size):
            inputs = self.tokenizer(list(batch), return_tensors="pt", padding=True, truncation=True, max_length=128)
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.no_grad():
                hidden = self.text_encoder(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1)
                embeddings = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=-1)
            features.append(embeddings.cpu().numpy())
        return np.vstack(features).astype(np.float32)

    def _encode_images(self, thumbnails: Sequence[Path | None]) -> np.ndarray:
        features = np.zeros((len(thumbnails), self.image_embedding_dim), dtype=np.float32)
        valid_indices: list[int] = []
        valid_images: list[Image.Image] = []
        for index, thumbnail in enumerate(thumbnails):
            if thumbnail is None:
                continue
            try:
                valid_indices.append(index)
                valid_images.append(Image.open(thumbnail).convert("RGB"))
            except OSError:
                continue
        cursor = 0
        for batch in _batch(valid_images, self.batch_size):
            inputs = self.image_processor(images=list(batch), return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.no_grad():
                embeddings = self.image_encoder.get_image_features(**inputs)
                if not isinstance(embeddings, torch.Tensor):
                    embeddings = embeddings.pooler_output
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=-1)
            size = len(batch)
            features[valid_indices[cursor : cursor + size]] = embeddings.cpu().numpy()
            cursor += size
        return features

    def _modality_features(self, text_features: np.ndarray, image_features: np.ndarray) -> np.ndarray:
        text_probability = self.text_classifier.predict_proba(text_features)[:, 1] if self.text_classifier else np.zeros(len(text_features))
        image_probability = self.image_classifier.predict_proba(image_features)[:, 1] if self.image_classifier else np.zeros(len(image_features))
        return np.column_stack([text_probability, image_probability])

    def _to_records(self, rows) -> list[Mapping]:
        if hasattr(rows, "to_dict"):
            records = list(rows.to_dict(orient="records"))
        elif isinstance(rows, Mapping):
            records = [rows]
        else:
            records = list(rows)
        if not records:
            raise ValueError("No rows were provided.")
        return records

    def _pick_headline(self, record: Mapping) -> str:
        for key in ("headline", "title", "text"):
            if key in record:
                return _normalize_text(record[key])
        return ""

    def _pick_thumbnail(self, record: Mapping) -> Path | None:
        for key in ("thumbnail_path", "thumbnail", "image_path"):
            if key in record:
                return _normalize_path(record[key])
        return None

    def _pick_label(self, record: Mapping) -> int:
        for key in ("label", "target", "is_clickbait"):
            if key in record:
                value = record[key]
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in {"1", "true", "yes", "clickbait"}:
                        return 1
                    if normalized in {"0", "false", "no", "not_clickbait"}:
                        return 0
                return int(bool(value))
        raise ValueError("Training rows must contain a label, target, or is_clickbait field.")

    def _require_classifiers(self) -> None:
        if self.text_classifier is None or self.image_classifier is None or self.fusion_classifier is None:
            raise RuntimeError("The detector has not been trained yet.")
