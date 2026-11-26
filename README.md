# Baitbuster

A clickbait detector for headlines and optional thumbnail images. A Django + DRF backend serves a React frontend. A Celery worker runs the ML model, and everything runs in Docker Compose.

## First-time setup

```bash
cp .env.example .env
docker compose up
```

The first worker start downloads about 1 GB of DistilBERT and CLIP weights into the `hf-cache` volume. It's ready when the worker logs `Model loaded (version ...)`. Later starts reuse the cache.

To use the Django admin, make a staff user:

```bash
docker compose exec web python manage.py createsuperuser
```

## Daily use

```bash
docker compose up -d     # start
docker compose stop      # stop, keeps data
docker compose logs -f worker
```

- The worker doesn't auto-reload code. After editing `backend/scans/tasks.py` or `backend/scans/inference.py` (or pulling changes to them), run `docker compose restart worker`.
- Site: http://localhost:5173
- Django admin: http://localhost:5173/admin/ (proxied) or http://localhost:8000/admin/
- Health check: http://localhost:8000/api/health

Containers: `db` (Postgres 17), `redis` (Celery queue, result cache, throttle counters), `web` (Django), `worker` (Celery, holds the model), `frontend` (Vite dev server, proxies `/api`, `/admin` and `/static` to Django).

Guest scans are tied to the browser session. Signing in or registering moves them to the account. So if someone signs in on a browser that holds another person's guest session, they take over those guest scans. That's by design.

## Tests

```bash
docker compose run --rm web pytest
```

Tests use a fake detector and Celery eager mode, so they never load the model.

## Getting a new model

`origin` is our fork and `upstream` is the ML teammate's repo.

```bash
git pull upstream main
docker compose restart worker
```

The model version is the first 12 hex characters of the joblib file's SHA-256. The worker stamps each answer with the version of the model it loaded, and the answer is cached and saved under that stamp, so a new model never serves old cached results.

## Windows

Clone the repo inside WSL2 (not under `C:\`), or Vite's hot reload won't see your edits.

## Train a model (outside Docker)

Training data must contain:

- `headline`: article headline or video title.
- `label`: `1` for clickbait and `0` for non-clickbait.

You may also include `thumbnail_path` with a local image path.

```bash
# pip install -r requirements.txt first
python train.py --data data/clickbait_100_data.csv data/IndiaCLICKBAITdata.csv --output artifacts/clickbait_detector.joblib
```

Multiple CSV files can be passed to `--data`. The trainer also supports common title and label column names used by the included datasets.

## Predict from the command line (outside Docker)

Headline only:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "This one weird trick changed everything"
```

Headline with a thumbnail:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "Breaking update from the city" --thumbnail path/to/thumbnail.jpg
```

<!-- The included model files are examples. Train the model with a representative labeled dataset for meaningful predictions. -->
