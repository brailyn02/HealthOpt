"""
FastAPI wrapper for DFinder prediction service
Exposes predict.py functionality as HTTP API on port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import sys
import traceback

# Import the DFinder predictor
from predict import DFinder

# Initialize FastAPI app
app = FastAPI(
    title="DFinder API",
    description="Drug-Food Interaction Predictor",
    version="1.0"
)

# Add CORS middleware to allow requests from localhost:3002
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DFinder (this loads all models on startup)
print("[FastAPI] Initializing DFinder...")
try:
    df = DFinder(verbose=True)
    print("[FastAPI] DFinder initialized successfully")
except Exception as e:
    print(f"[FastAPI] ERROR initializing DFinder: {e}")
    traceback.print_exc()
    sys.exit(1)


class PredictRequest(BaseModel):
    drug: str
    food: str
    language: str = "en"


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "DFinder",
        "version": "1.0",
        "models_loaded": True,
        "ready": True
    }


@app.post("/predict")
async def predict(request: PredictRequest):
    """
    Predict drug-food interaction
    
    Args:
        drug: Drug name
        food: Food name
        language: Language code (en, fr, ar)
    
    Returns:
        Prediction result with confidence, mechanism, and explanations
    """
    try:
        result = df.predict(request.drug, request.food, language=request.language)
        return result
    except Exception as e:
        print(f"[FastAPI] Prediction error for {request.drug} × {request.food}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-predict")
async def batch_predict(pairs: list[dict]):
    """
    Batch predict multiple drug-food pairs
    
    Args:
        pairs: List of {drug, food, language} dicts
    
    Returns:
        List of prediction results
    """
    try:
        results = []
        for pair in pairs:
            result = df.predict(
                pair.get("drug", ""),
                pair.get("food", ""),
                language=pair.get("language", "en")
            )
            results.append(result)
        return results
    except Exception as e:
        print(f"[FastAPI] Batch prediction error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("[FastAPI] Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
