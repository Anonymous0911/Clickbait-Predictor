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
python train.py --data data/train.csv --output artifacts/clickbait_detector.joblib
```

Start the FastAPI backend:

```powershell
$env:CLICKBAIT_MODEL_PATH="artifacts/clickbait_detector.joblib"
uvicorn api:app --reload
```

In a second terminal, install and start the React frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and sends multipart requests to `http://localhost:8000/predict`. The API returns fused probability, confidence, separate DistilBERT and CLIP probabilities, and explainable signal scores.

## Train

```bash
python train.py --data data/train.csv --output artifacts/clickbait_detector.joblib
```

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
