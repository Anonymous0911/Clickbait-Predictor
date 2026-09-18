# Clickbait Detector

A multimodal clickbait detector for headlines and optional thumbnail images. It includes a training script, command-line prediction, a Streamlit interface, and a FastAPI backend with a React frontend.

## Setup

```bash
pip install -r requirements.txt
```

## Train a model

Training data must contain:

- `headline`: article headline or video title.
- `label`: `1` for clickbait and `0` for non-clickbait.

You may also include `thumbnail_path` with a local image path.

```bash
python train.py --data data/clickbait_100_data.csv data/indian_train.csv --output artifacts/clickbait_detector.joblib
```

Multiple CSV files can be passed to `--data`. The trainer also supports common title and label column names used by the included datasets.

## Run the application

### Streamlit

```bash
streamlit run streamlit_app.py
```

The app uses `artifacts/clickbait_detector.joblib` by default. Set `CLICKBAIT_MODEL_PATH` to use another model file.

### FastAPI and React

Start the API:

```powershell
$env:CLICKBAIT_MODEL_PATH="artifacts/clickbait_detector.joblib"
uvicorn api:app --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The API runs at `http://localhost:8000` and the frontend at `http://localhost:5173`.

## Predict from the command line

Headline only:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "This one weird trick changed everything"
```

Headline with a thumbnail:

```bash
python predict.py --model artifacts/clickbait_detector.joblib --headline "Breaking update from the city" --thumbnail path/to/thumbnail.jpg
```

<!-- The included model files are examples. Train the model with a representative labeled dataset for meaningful predictions. -->
