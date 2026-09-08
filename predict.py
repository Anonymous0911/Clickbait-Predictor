from __future__ import annotations

import argparse

from clickbait_model import ClickbaitDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict whether an article or video is clickbait.")
    parser.add_argument("--model", required=True, help="Path to a saved clickbait detector.")
    parser.add_argument("--headline", default="", help="The article headline or video title.")
    parser.add_argument("--thumbnail", default="", help="Optional thumbnail image path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    detector = ClickbaitDetector.load(args.model)
    row = {"headline": args.headline, "thumbnail_path": args.thumbnail or None}
    result = detector.predict([row])[0]
    print({
        "label": result.label,
        "clickbait_probability": round(result.clickbait_probability, 4),
        "not_clickbait_probability": round(result.not_clickbait_probability, 4),
        "confidence": round(result.confidence, 4),
        "headline_probability": round(result.headline_probability, 4),
        "thumbnail_probability": round(result.thumbnail_probability, 4),
        "signals": vars(result.signals),
    })


if __name__ == "__main__":
    main()

