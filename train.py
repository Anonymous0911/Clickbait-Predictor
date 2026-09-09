from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from clickbait_model import ClickbaitDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a clickbait detector from labeled headlines and thumbnails.")
    parser.add_argument(
        "--data",
        required=True,
        nargs="+",
        help="One or more CSV files with headline/title and label/isClickbait columns.",
    )
    parser.add_argument("--output", default="artifacts/clickbait_detector.joblib", help="Where to save the trained model.")
    parser.add_argument("--text-model-name", default="distilbert-base-uncased", help="Hugging Face DistilBERT model name.")
    parser.add_argument("--vision-model-name", default="openai/clip-vit-base-patch32", help="Hugging Face CLIP model name.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the train/test split.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size during training.")
    return parser.parse_args()


def load_training_frame(paths: list[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        column_aliases = {
            "title": "headline",
            "Video Title": "headline",
            "isClickbait": "label",
            "is_clickbait": "label",
            "clickbait": "label",
        }
        frame = frame.rename(columns={key: value for key, value in column_aliases.items() if key in frame.columns})
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    required_columns = {"headline", "label"}
    missing = sorted(required_columns - set(combined.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    combined = combined.dropna(subset=["headline", "label"])
    combined["headline"] = combined["headline"].astype(str).str.strip()
    combined["label"] = combined["label"].astype(int)
    if combined["label"].nunique() < 2:
        raise ValueError("Training data must contain both label 0 (not clickbait) and label 1 (clickbait).")
    return combined


def main() -> None:
    args = parse_args()
    frame = load_training_frame(args.data)

    train_frame, validation_frame = train_test_split(
        frame,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=frame["label"] if frame["label"].nunique() > 1 else None,
    )

    detector = ClickbaitDetector(
        text_model_name=args.text_model_name,
        vision_model_name=args.vision_model_name,
        batch_size=args.batch_size,
    )
    detector.fit(train_frame)

    validation_probabilities = detector.predict_proba(validation_frame)[:, 1]
    validation_predictions = (validation_probabilities >= 0.5).astype(int)
    validation_labels = validation_frame["label"].astype(int).to_numpy()

    accuracy = accuracy_score(validation_labels, validation_predictions)
    print(f"Validation accuracy: {accuracy:.4f}")

    if len(set(validation_labels)) > 1:
        auc = roc_auc_score(validation_labels, validation_probabilities)
        print(f"Validation ROC-AUC: {auc:.4f}")

    print(classification_report(validation_labels, validation_predictions, digits=4))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detector.save(output_path)
    print(f"Saved model to {output_path}")


if __name__ == "__main__":
    main()

