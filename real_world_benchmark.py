import pandas as pd
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime

# --- Clinical Benchmarks ---
# Based on the provided clinical data.
# We define expected outcomes for specific scenarios.
REAL_WORLD_BENCHMARKS = [
    {
        "name": "Warfarin (CYP2C9) Stability",
        "drug": "warfarin",
        "phase": "luteale",
        "expected_range_pct": (-5, 5),
        "description": "Warfarin metabolism is stable. Risk change should be minimal (< 5%)."
    },
    {
        "name": "Lamotrigine (UGT1A4) Natural Cycle Stability",
        "drug": "lamotrigine",
        "phase": "ovulation",
        "expected_range_pct": (-5, 5),
        "description": "Lamotrigine is stable in a natural cycle. Risk change should be minimal (< 5%)."
    },
    {
        "name": "Diazepam (CYP2C19) Stability",
        "drug": "diazepam",
        "phase": "folliculaire",
        "expected_range_pct": (-5, 5),
        "description": "Diazepam clearance is stable. Risk change should be minimal (< 5%)."
    },
    {
        "name": "Caffeine (CYP1A2) Luteal Inhibition",
        "drug": "caffeine",
        "phase": "luteale",
        "expected_range_pct": (-30, -20),
        "description": "Caffeine clearance is reduced by ~25% in the luteal phase."
    }
]

def load_models_and_encoders():
    """Loads all necessary model and encoder .pkl files."""
    models_dir = Path(__file__).resolve().parent / "MODELE 3" / "models"
    try:
        models = {
            "regressor": joblib.load(models_dir / "hormonal_risk_regressor.pkl"),
            "classifier": joblib.load(models_dir / "hormonal_risk_classifier.pkl"),
            "cyp_predictor": joblib.load(models_dir / "cyp_predictor.pkl"),
            "le_drug": joblib.load(models_dir / "le_drug.pkl"),
            "le_phase": joblib.load(models_dir / "le_phase.pkl"),
        }

        # Quick visibility on whether we're benchmarking fresh or stale artifacts.
        print(f"Loaded artifacts from: {models_dir}")
        for name in [
            "hormonal_risk_regressor.pkl",
            "hormonal_risk_classifier.pkl",
            "cyp_predictor.pkl",
            "le_drug.pkl",
            "le_phase.pkl",
        ]:
            p = models_dir / name
            if p.exists():
                ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  - {name}: {ts}")

        return models
    except FileNotFoundError as e:
        print(f"❌ Error loading model: {e}. Make sure the models are trained and located in 'MODELE 3/models/'.")
        return None

def run_benchmark(models):
    """Runs the model against the defined clinical benchmarks."""
    print("--- Running Real-World Clinical Benchmark ---")
    
    if not models:
        print("Aborting benchmark due to model loading failure.")
        return

    results = []
    
    # Create a DataFrame from our benchmark cases
    benchmark_data = []
    for b in REAL_WORLD_BENCHMARKS:
        # Add average hormone levels for the phase to satisfy model input shape
        # These are representative values and don't need to be exact for this test.
        if b['phase'] == 'luteale':
            hormones = {'estrogen_pg_ml': 150, 'progesterone_ng_ml': 10, 'lh_mui_ml': 5, 'fsh_mui_ml': 5}
        elif b['phase'] == 'ovulation':
            hormones = {'estrogen_pg_ml': 250, 'progesterone_ng_ml': 1, 'lh_mui_ml': 40, 'fsh_mui_ml': 15}
        else: # folliculaire / default
            hormones = {'estrogen_pg_ml': 100, 'progesterone_ng_ml': 0.5, 'lh_mui_ml': 8, 'fsh_mui_ml': 8}
        
        benchmark_data.append({
            "drug": b["drug"],
            "phase": b["phase"],
            **hormones
        })
    benchmark_df = pd.DataFrame(benchmark_data)

    # Encode the categorical features
    try:
        benchmark_df['drug_enc'] = models['le_drug'].transform(benchmark_df['drug'])
        benchmark_df['phase_enc'] = models['le_phase'].transform(benchmark_df['phase'])
    except ValueError as e:
        print(f"❌ Error encoding features: {e}. A drug or phase in the benchmark is not in the model's vocabulary.")
        return

    # Select features for prediction - MUST match the training features
    features = [
        'drug_enc', 
        'phase_enc', 
        'estrogen_pg_ml', 
        'progesterone_ng_ml', 
        'lh_mui_ml', 
        'fsh_mui_ml'
    ]
    X_benchmark = benchmark_df[features]

    # Predict risk adjustment percentage using Model A (Regressor)
    predictions_pct = models['regressor'].predict(X_benchmark)

    # Evaluate each benchmark
    for i, benchmark in enumerate(REAL_WORLD_BENCHMARKS):
        prediction = predictions_pct[i]
        min_expected, max_expected = benchmark["expected_range_pct"]
        
        is_pass = min_expected <= prediction <= max_expected
        
        results.append({
            "name": benchmark["name"],
            "prediction_pct": prediction,
            "expected_range_pct": f"{min_expected}% to {max_expected}%",
            "status": "✅ PASS" if is_pass else "❌ FAIL",
            "description": benchmark["description"]
        })

    # Print the report
    print("\n--- Benchmark Report ---")
    for res in results:
        print(f"\n▶️  Test: {res['name']}")
        print(f"   - Description: {res['description']}")
        print(f"   - Model Prediction: {res['prediction_pct']:.2f}%")
        print(f"   - Expected Range: {res['expected_range_pct']}")
        print(f"   - Status: {res['status']}")
    
    print("\n--- End of Report ---\n")
    
    # Return True if all benchmarks passed
    return all('PASS' in r['status'] for r in results)


if __name__ == "__main__":
    loaded_models = load_models_and_encoders()
    run_benchmark(loaded_models)
