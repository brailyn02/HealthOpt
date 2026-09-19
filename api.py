"""
DFinder Python API Server
=========================
FastAPI wrapper around predict.py — exposes the full 4-layer pipeline
(Physicochemical + Graph Query + KGE + LightGCN) as a REST endpoint.

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000

Or install deps first:
    pip install fastapi uvicorn

Endpoints:
    GET  /health    → liveness check
    POST /predict   → { drug: str, food: str } → full DFinder result dict
"""

import os
import sys
import threading
from pathlib import Path

# Ensure workspace root is on sys.path and is the working directory
# (all predict.py imports and Path("D:/...") references depend on this)
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="DFinder API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|.*\.onrender\.com)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "DFinder API",
        "message": "API is running",
        "endpoints": ["/health", "/ready", "/predict", "/docs"],
    }


# ── DFinder instance — loaded once at startup ─────────────────────────────────
_dfinder = None
_model_loading = False
_model_error = None
_model_lock = threading.Lock()


def _load_model_worker():
    global _dfinder, _model_loading, _model_error
    try:
        print("=" * 60)
        print("  DFinder API — loading all layers...")
        print("=" * 60)
        from predict import DFinder
        model = DFinder(verbose=True)
        with _model_lock:
            _dfinder = model
            _model_error = None
        print("DFinder API ready.")
    except Exception as exc:
        with _model_lock:
            _model_error = f"{type(exc).__name__}: {exc}"
        print(f"DFinder API load failed: {_model_error}")
    finally:
        with _model_lock:
            _model_loading = False


@app.on_event("startup")
async def load_model():
    global _model_loading
    with _model_lock:
        if _dfinder is not None or _model_loading:
            return
        _model_loading = True
    threading.Thread(target=_load_model_worker, daemon=True).start()


# ── Request model ─────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    drug: str
    food: str
    language: str = "en"  # Support for 'en', 'fr', 'ar' (defaults to English)

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    with _model_lock:
        loaded = _dfinder is not None
        loading = _model_loading
        err = _model_error
    status = "ok" if loaded else ("loading" if loading else "error")
    return {
        "status": status,
        "model_loaded": loaded,
        "loading": loading,
        "ready": loaded,
        "error": err,
    }


@app.get("/ready")
def ready():
    with _model_lock:
        loaded = _dfinder is not None
        loading = _model_loading
        err = _model_error
    if not loaded:
        raise HTTPException(
            status_code=503,
            detail={"ready": False, "loading": loading, "error": err},
        )
    return {"ready": True}


@app.post("/predict")
def predict(req: PredictRequest):
    if _dfinder is None:
        with _model_lock:
            loading = _model_loading
            err = _model_error
        if err:
            raise HTTPException(status_code=503, detail=f"Model load failed: {err}")
        if loading:
            raise HTTPException(status_code=503, detail="Model still loading, retry in a moment")
        raise HTTPException(status_code=503, detail="Model unavailable")
    if not req.drug.strip() or not req.food.strip():
        raise HTTPException(status_code=422, detail="Both 'drug' and 'food' fields are required")
    result = _dfinder.predict(req.drug.strip(), req.food.strip(), language=req.language)
    return result
