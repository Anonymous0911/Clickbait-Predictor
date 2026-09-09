from __future__ import annotations

import tempfile
import os
from pathlib import Path

import streamlit as st

from clickbait_model import ClickbaitDetector


st.set_page_config(page_title="Clickbait Detector", page_icon="🧠", layout="wide")


@st.cache_resource
def load_detector(model_path: str) -> ClickbaitDetector:
    return ClickbaitDetector.load(model_path)


def write_uploaded_thumbnail(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".png"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(uploaded_file.getbuffer())
    temp_file.flush()
    temp_file.close()
    return Path(temp_file.name)


def clear_inputs() -> None:
    st.session_state["headline"] = ""
    st.session_state["thumbnail"] = None


st.markdown(
    """
    <style>
        .stApp {
            background: radial-gradient(circle at top, #1f2937 0%, #0f172a 45%, #020617 100%);
            color: #e5e7eb;
        }
        .hero {
            padding: 2.5rem 2rem 1rem 2rem;
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85));
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
        }
        .hero h1 {
            font-size: 3rem;
            margin-bottom: 0.25rem;
        }
        .hero p {
            color: #cbd5e1;
            font-size: 1.05rem;
        }
        .metric-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.18);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>Clickbait Detector</h1>
        <p>Paste a headline or title, optionally upload a thumbnail, and get a clickbait score.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

artifacts_dir = Path(__file__).resolve().parent / "artifacts"
default_model = artifacts_dir / "clickbait_detector.joblib"
if not default_model.exists():
    default_model = artifacts_dir / "youtube_detector.joblib"
model_path = Path(os.getenv("CLICKBAIT_MODEL_PATH", str(default_model)))
headline = st.text_area(
    "Headline or title",
    height=120,
    placeholder="Enter an article headline or video title...",
    key="headline",
)
thumbnail = st.file_uploader("Thumbnail image", type=["png", "jpg", "jpeg", "webp"], key="thumbnail")

col1, col2 = st.columns([1, 1])
with col1:
    predict_clicked = st.button("Predict", use_container_width=True)
with col2:
    st.button("Clear", use_container_width=True, on_click=clear_inputs)

if predict_clicked:
    if not headline.strip() and thumbnail is None:
        st.warning("Please enter a headline or upload a thumbnail image before predicting.")
    elif not model_path:
        st.error("Set a model path first.")
    elif not Path(model_path).exists():
        st.error(f"Model not found: {model_path}")
    else:
        detector = load_detector(model_path)
        thumbnail_path = write_uploaded_thumbnail(thumbnail) if thumbnail is not None else None
        try:
            result = detector.predict(
                [
                    {
                        "headline": headline,
                        "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
                    }
                ]
            )[0]
        finally:
            if thumbnail_path is not None and thumbnail_path.exists():
                thumbnail_path.unlink(missing_ok=True)

        score = result.clickbait_probability
        st.subheader("Result")
        left, right = st.columns(2)
        with left:
            st.markdown(
                f"<div class='metric-card'><h3 style='margin:0;'>Label</h3><p style='font-size:1.4rem;margin:0.3rem 0 0 0;'>{result.label}</p></div>",
                unsafe_allow_html=True,
            )
        with right:
            st.markdown(
                f"<div class='metric-card'><h3 style='margin:0;'>Clickbait probability</h3><p style='font-size:1.4rem;margin:0.3rem 0 0 0;'>{score:.2%}</p></div>",
                unsafe_allow_html=True,
            )

        st.progress(score)
        st.caption(f"Not clickbait probability: {result.not_clickbait_probability:.2%}")
