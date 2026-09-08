from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from clickbait_model import ClickbaitDetector


class ExplainableSignalsResponse(BaseModel):
    curiosity_gap: float
    sensational_wording: float
    excessive_capitalization: float
    question_style: float
    exclamation_emphasis: float


class PredictResponse(BaseModel):
    label: str
    clickbait_probability: float
    not_clickbait_probability: float
    confidence: float
    headline_probability: float
    thumbnail_probability: float
    signals: ExplainableSignalsResponse


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    text_encoder: str
    vision_encoder: str
    fusion: str


def create_app(model_path: str | Path | None = None) -> FastAPI:
    detector: ClickbaitDetector | None = None

    def resolve_model_path() -> str | Path | None:
        return model_path or os.getenv("CLICKBAIT_MODEL_PATH")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal detector
        resolved_path = resolve_model_path()
        if resolved_path and Path(resolved_path).exists():
            detector = ClickbaitDetector.load(resolved_path)
        yield

    app = FastAPI(title="Clickbait AI API", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            model_loaded=detector is not None,
            text_encoder="DistilBERT",
            vision_encoder="CLIP",
            fusion="Logistic regression on modality probabilities",
        )

    @app.post("/predict", response_model=PredictResponse)
    async def predict(
        headline: str = Form(default=""),
        thumbnail: UploadFile | None = File(default=None),
    ) -> PredictResponse:
        if detector is None:
            raise HTTPException(status_code=503, detail="Model is not loaded. Set CLICKBAIT_MODEL_PATH to a trained .joblib file.")

        temporary_path: Path | None = None
        if thumbnail is not None:
            suffix = Path(thumbnail.filename or ".jpg").suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
                temporary_file.write(await thumbnail.read())
                temporary_path = Path(temporary_file.name)
        try:
            result = detector.predict([{"headline": headline, "thumbnail_path": temporary_path}])[0]
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return PredictResponse(
            label=result.label,
            clickbait_probability=result.clickbait_probability,
            not_clickbait_probability=result.not_clickbait_probability,
            confidence=result.confidence,
            headline_probability=result.headline_probability,
            thumbnail_probability=result.thumbnail_probability,
            signals=ExplainableSignalsResponse(**vars(result.signals)),
        )

    return app


app = create_app()
