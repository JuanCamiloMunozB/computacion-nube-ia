"""Servicio de inferencia de churn -- Unidad 5, Grupo 3."""

import json as _json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import FEATURE_ORDER, ClienteInput, HealthOutput, PrediccionOutput


MODEL_GCS_URI = os.getenv("MODEL_GCS_URI", "")
MODEL_LOCAL_PATH = os.getenv("MODEL_LOCAL_PATH", "/tmp/model.joblib")
MODEL_VERSION = os.getenv("MODEL_VERSION", "u4_g03_mdl_20260918_xgboost")
UMBRAL_DECISION = float(os.getenv("UMBRAL_DECISION", "0.5"))


class StructuredFormatter(logging.Formatter):
    """Emite JSON para que Cloud Logging indexe los campos de cada evento."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(record, "json_fields"):
            payload.update(record.json_fields)
        return _json.dumps(payload, default=str)


def _init_logger() -> logging.Logger:
    log = logging.getLogger("churn-api")
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    log.handlers = [handler]
    log.propagate = False
    return log


logger = _init_logger()


class ModelState:
    def __init__(self) -> None:
        self.modelo = None
        self.error: str | None = None
        self.loaded_at: datetime | None = None

    def is_ready(self) -> bool:
        return self.modelo is not None and self.error is None


def _descargar_de_gcs(gcs_uri: str, destino: str) -> str:
    from google.cloud import storage

    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"MODEL_GCS_URI mal formado: {gcs_uri}")
    bucket_name, _, blob_path = gcs_uri.removeprefix("gs://").partition("/")
    storage.Client().bucket(bucket_name).blob(blob_path).download_to_filename(destino)
    return destino


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga el modelo una sola vez al arrancar el proceso."""
    state = ModelState()
    app.state.model = state
    try:
        ruta = MODEL_LOCAL_PATH
        if MODEL_GCS_URI and not Path(ruta).exists():
            ruta = _descargar_de_gcs(MODEL_GCS_URI, MODEL_LOCAL_PATH)
        state.modelo = joblib.load(ruta)
        state.loaded_at = datetime.now(timezone.utc)
        logger.info(
            "startup_model_loaded",
            extra={"json_fields": {
                "model_version": MODEL_VERSION,
                "gcs_uri": MODEL_GCS_URI,
                "n_features": len(FEATURE_ORDER),
                "umbral": UMBRAL_DECISION,
            }},
        )
    except Exception as exc:
        state.error = str(exc)
        logger.error(
            "startup_model_load_failed",
            extra={"json_fields": {"error": str(exc), "gcs_uri": MODEL_GCS_URI}},
        )
    yield
    app.state.model = None


app = FastAPI(
    title="Churn API - Grupo 3",
    version="1.0.0",
    description="Servicio de predicción de churn con el modelo ganador de U4.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthOutput)
def health(request: Request) -> HealthOutput:
    """Indica si el proceso terminó de cargar el modelo y está listo."""
    state: ModelState | None = getattr(request.app.state, "model", None)
    if state is None or not state.is_ready():
        detalle = state.error if state else "modelo aún no cargado"
        raise HTTPException(status_code=503, detail=detalle)
    return HealthOutput(status="ok", model_loaded=True, model_version=MODEL_VERSION)


@app.post("/predict", response_model=PrediccionOutput)
def predict(cliente: ClienteInput, request: Request) -> PrediccionOutput:
    """Predice churn; el contrato inválido es rechazado automáticamente con 422."""
    state: ModelState | None = getattr(request.app.state, "model", None)
    if state is None or not state.is_ready():
        logger.error(
            "predict_model_unavailable",
            extra={"json_fields": {"error": state.error if state else "state=None"}},
        )
        raise HTTPException(status_code=503, detail="Modelo no disponible")

    try:
        vector = cliente.to_feature_vector()
        proba = float(state.modelo.predict_proba([vector])[0][1])
    except Exception as exc:
        logger.error(
            "predict_error",
            extra={"json_fields": {"customer_id": cliente.customer_id, "error": str(exc)}},
        )
        raise HTTPException(status_code=500, detail="Error interno al generar la predicción.")

    resultado = PrediccionOutput(
        customer_id=cliente.customer_id,
        customer_risk_score=round(proba, 4),
        predicted_churn=bool(proba >= UMBRAL_DECISION),
        model_version=MODEL_VERSION,
        predicted_at=datetime.now(timezone.utc),
        requested_by=request.headers.get("x-goog-authenticated-user-email", "unknown"),
        source="api_single",
        input_file=None,
    )
    logger.info(
        "predict_ok",
        extra={"json_fields": {
            "input": cliente.model_dump(mode="json"),
            "output": resultado.model_dump(mode="json"),
        }},
    )
    return resultado


@app.exception_handler(RequestValidationError)
async def log_422(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Registra los rechazos de contrato como eventos estructurados."""
    logger.warning(
        "predict_422",
        extra={"json_fields": {"errors": exc.errors(), "path": request.url.path}},
    )
    return JSONResponse(
        status_code=422,
        content={"detail": _json.loads(_json.dumps(exc.errors(), default=str))},
    )
