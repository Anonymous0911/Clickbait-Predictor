from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_DATASET = Path("data/youtube_thumbnails.csv")


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["video_id", "headline", "thumbnail_url", "thumbnail_path", "label", "downloaded"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in columns} for row in rows)


def collect(api_key: str, query: str, dataset: Path, limit: int) -> int:
    parameters = urllib.parse.urlencode(
        {"part": "snippet", "q": query, "type": "video", "maxResults": limit, "key": api_key}
    )
    request = urllib.request.Request(
        f"https://www.googleapis.com/youtube/v3/search?{parameters}",
        headers={"User-Agent": "clickbait-detector/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    rows = _read_rows(dataset)
    known_ids = {row.get("video_id") for row in rows}
    added = 0
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        if not video_id or video_id in known_ids:
            continue
        rows.append(
            {
                "video_id": video_id,
                "headline": snippet.get("title", ""),
                "thumbnail_url": thumbnail.get("url", ""),
                "thumbnail_path": "",
                "label": "",
                "downloaded": "0",
            }
        )
        known_ids.add(video_id)
        added += 1
    _write_rows(dataset, rows)
    return added


def download(dataset: Path, output_dir: Path) -> int:
    rows = _read_rows(dataset)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for row in rows:
        url = row.get("thumbnail_url", "")
        video_id = row.get("video_id", "")
        if not url or not video_id or row.get("downloaded") == "1":
            continue
        target = output_dir / f"{video_id}.jpg"
        request = urllib.request.Request(url, headers={"User-Agent": "clickbait-detector/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                target.write_bytes(response.read())
        except (OSError, ValueError):
            continue
        row["thumbnail_path"] = str(target)
        row["downloaded"] = "1"
        count += 1
    _write_rows(dataset, rows)
    return count


def label(dataset: Path) -> int:
    rows = _read_rows(dataset)
    changed = 0
    for row in rows:
        if row.get("label", "").strip() in {"0", "1"}:
            continue
        print(f"\n{row.get('headline', '(untitled)')}\n{row.get('thumbnail_path', '')}")
        answer = input("Label [1 clickbait / 0 not clickbait / s skip / q quit]: ").strip().lower()
        if answer == "q":
            break
        if answer in {"0", "1"}:
            row["label"] = answer
            changed += 1
    _write_rows(dataset, rows)
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect and label YouTube thumbnails for clickbait training.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Search YouTube and append video metadata to a CSV.")
    collect_parser.add_argument("--query", required=True)
    collect_parser.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"))
    collect_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    collect_parser.add_argument("--limit", type=int, default=25)

    download_parser = subparsers.add_parser("download", help="Download thumbnails referenced by the CSV.")
    download_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    download_parser.add_argument("--output-dir", type=Path, default=Path("data/thumbnails"))

    label_parser = subparsers.add_parser("label", help="Label unreviewed rows from the terminal.")
    label_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "collect":
        if not args.api_key:
            raise SystemExit("Provide --api-key or set YOUTUBE_API_KEY.")
        print(f"Added {collect(args.api_key, args.query, args.dataset, args.limit)} videos.")
    elif args.command == "download":
        print(f"Downloaded {download(args.dataset, args.output_dir)} thumbnails.")
    else:
        print(f"Labeled {label(args.dataset)} rows.")


if __name__ == "__main__":
    main()