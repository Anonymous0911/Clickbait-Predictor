# Clickbait Detector

Full-stack multimodal clickbait detector for article headlines and video thumbnails.

## What it uses

- The headline or title text.
- The thumbnail image, if you provide one.
- DistilBERT for headline language embeddings.
- CLIP for thumbnail visual embeddings.
- Separate headline and thumbnail classifiers plus a fusion classifier.
- FastAPI REST API and React + Vite frontend.
- Explainable signals for curiosity gaps, sensational wording, capitalization, questions, and exclamation emphasis.

## Data format

Create a CSV with at least these columns:

- `headline`: article headline or video title.
- `label`: `1` for clickbait, `0` for not clickbait.

Optional columns:

- `thumbnail_path`: local path to the thumbnail image.
- `title`, `text`, `thumbnail`, `image_path`, `target`, `is_clickbait` are also accepted by the code.

Example:

```csv
headline,thumbnail_path,label
You will not believe what happened next,examples/thumb1.jpg,1
Local city council approves new budget,examples/thumb2.jpg,0
```

## Install

```bash
pip install -r requirements.txt
```

## Streamlit frontend

```bash
streamlit run streamlit_app.py
```

Set the saved model path in the sidebar after training, or keep the default `artifacts/clickbait_detector.joblib`.

## Full-stack app

Train a model first:

```bash
python train.py --data data/clickbait_100_data.csv data/indian_train.csv --output artifacts/clickbait_detector.joblib
```

Multiple CSV files can be supplied together. The trainer accepts `headline`/`label` as well as common YouTube dataset names such as `title`/`isClickbait` and `Video Title`/`isClickbait`:

```bash
python train.py --data data/clickbait_100_data.csv data/out.csv --output artifacts/clickbait_detector.joblib
```

The Indian headline dataset can be added to the training set in the same way. Keep `indian_test.csv` separate for future evaluation:

```bash
python train.py --data data/clickbait_100_data.csv data/indian_train.csv --output artifacts/clickbait_detector.joblib
```

Start the FastAPI backend:

```powershell
$env:CLICKBAIT_MODEL_PATH="artifacts/clickbait_detector.joblib"
uvicorn api:app --reload
```

### Authentication and SQL Server

1. Open `database.sql` in SQL Server Management Studio and execute it against the SQL Server instance. It creates the `clickbait` database, `Users`, and `PredictionHistory` tables, plus the initial admin account.
2. Install dependencies with `pip install -r requirements.txt` so the `pyodbc` SQL Server driver is available.
3. Set the connection string and a private token secret before starting the API:

```powershell
$env:CLICKBAIT_DB_CONNECTION="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=clickbait;Trusted_Connection=yes;TrustServerCertificate=yes"
$env:CLICKBAIT_JWT_SECRET="replace-with-a-long-random-secret"
```

The initial administrator credentials are `admin` / `admin1109`. Change this password after the first login. New users must use passwords with at least 4 characters. Visitors can continue as guests, while signed-in users get saved prediction history and profile controls for history and password changes. Admin users can also access `/admin/users` and `/admin/history`.

In a second terminal, install and start the React frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and sends multipart requests to `http://localhost:8000/predict`. The API returns fused probability, confidence, separate DistilBERT and CLIP probabilities, and explainable signal scores.

## Train

```bash
python train.py --data data/clickbait_100_data.csv data/indian_train.csv --output artifacts/clickbait_detector.joblib
```

## Build a thumbnail dataset

The reference project workflow is available through `youtube_pipeline.py`. It uses the YouTube Data API for metadata collection, so set `YOUTUBE_API_KEY` or pass `--api-key` for the first step:

```powershell
$env:YOUTUBE_API_KEY="your-key"
python youtube_pipeline.py collect --query "top 10 mysteries" --dataset data/youtube_thumbnails.csv
python youtube_pipeline.py download --dataset data/youtube_thumbnails.csv --output-dir data/thumbnails
python youtube_pipeline.py label --dataset data/youtube_thumbnails.csv
python train.py --data data/youtube_thumbnails.csv --output artifacts/youtube_detector.joblib
```

You can also run `streamlit run streamlit_app.py` and use the thumbnail labeling workspace to review one image at a time. Labels are stored as `1` for clickbait and `0` for not clickbait.

## Browser extension template

Start the API locally, then load the `extension` folder as an unpacked extension from `chrome://extensions` or `edge://extensions`. The content script sends sufficiently large page images to `/predict` and places a small verdict badge over each image. The template is intentionally limited to localhost and does not upload images to a third-party service.

## Predict

Headline only:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "This one weird trick changed everything"
```

Headline plus thumbnail:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "Breaking update from the city" --thumbnail examples/thumb.jpg
```

## Notes

This project is a model template. It needs a labeled dataset to train a useful classifier.
