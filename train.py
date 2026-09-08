from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from clickbait_model import ClickbaitDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a clickbait detector from labeled headlines and thumbnails.")
    parser.add_argument("--data", required=True, help="Path to a CSV file with headline and label or clickbait columns.")
    parser.add_argument("--output", default="artifacts/clickbait_detector.joblib", help="Where to save the trained model.")
    parser.add_argument("--text-model-name", default="distilbert-base-uncased", help="Hugging Face DistilBERT model name.")
    parser.add_argument("--vision-model-name", default="openai/clip-vit-base-patch32", help="Hugging Face CLIP model name.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the train/test split.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size during training.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.data)

    if "label" not in frame.columns and "clickbait" in frame.columns:
        frame = frame.rename(columns={"clickbait": "label"})

    required_columns = {"headline", "label"}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

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

