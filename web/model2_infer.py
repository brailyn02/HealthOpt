import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import joblib
except Exception as exc:  # pragma: no cover
    print(json.dumps({"ok": False, "error": f"joblib import failed: {exc}"}))
    raise SystemExit(0)


def _read_input() -> dict:
    try:
        raw = input()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _get_feature_cols(label: str, metrics: dict, model) -> list:
    cols = metrics.get(label, {}).get("feature_cols")
    if isinstance(cols, list) and cols:
        return cols
    if hasattr(model, "feature_names_in_"):
        try:
            return list(model.feature_names_in_)
        except Exception:
            return []
    return []


def _coerce_num(v):
    if v is None:
        return np.nan
    try:
        return float(v)
    except Exception:
        return np.nan


def _build_row(feature_cols: list, snapshot: dict) -> dict:
    row = {c: np.nan for c in feature_cols}

    aliases = {
        "ferritin": ["ferritin", "ferritine"],
        "hemoglobin": ["hemoglobin", "hemoglobine"],
        "vitaminD": ["vitaminD", "vitD", "vitd", "vitd_25oh"],
        "b12": ["b12", "vitB12", "vitb12", "vitB_12"],
        "folate": ["folate", "folate_serique", "folate_serum"],
        "calcium": ["calcium"],
        "magnesium": ["magnesium"],
        "zinc": ["zinc"],
        "iode_urinaire": ["iode_urinaire", "iodine_urinary"],
        "albumine": ["albumine", "albumin"],
        "tsh": ["tsh"],
        "glycemie_jejun": ["glycemie_jejun", "fasting_glucose"],
        "hba1c": ["hba1c", "hbA1c"],
        "triglycerides": ["triglycerides"],
        "ldl": ["ldl"],
        "ratio_albumine_creatinine": ["ratio_albumine_creatinine", "acr"],
    }

    # Inject direct exact-match keys first.
    for k, v in snapshot.items():
        if k in row:
            row[k] = _coerce_num(v)

    # Inject known aliases.
    for _, keys in aliases.items():
        present_val = None
        for key in keys:
            if key in snapshot and snapshot.get(key) is not None:
                present_val = _coerce_num(snapshot.get(key))
                break
        if present_val is None:
            continue
        for key in keys:
            if key in row:
                row[key] = present_val

    return row


def _predict_prob(model, df: pd.DataFrame):
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(df)
        if probs.ndim == 2 and probs.shape[1] >= 2:
            return float(probs[0, 1])
        return float(probs.ravel()[0])
    if hasattr(model, "decision_function"):
        score = float(model.decision_function(df)[0])
        return float(1.0 / (1.0 + np.exp(-score)))
    pred = model.predict(df)
    return float(pred[0])


def main():
    payload = _read_input()
    snapshot = payload.get("snapshot", {}) if isinstance(payload, dict) else {}

    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent
    models_dir = root / "mon_projet_nutrition" / "models"
    metrics_path = root / "mon_projet_nutrition" / "reports" / "best_metrics_v15.json"

    if not models_dir.exists() or not metrics_path.exists():
        print(json.dumps({"ok": False, "error": "model directories not found"}))
        return

    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"failed to read metrics: {exc}"}))
        return

    predictions = {}
    model_files = sorted(models_dir.glob("label_*_best.joblib"))

    for mf in model_files:
        label = mf.name.replace("_best.joblib", "")
        try:
            model = joblib.load(mf)
            feature_cols = _get_feature_cols(label, metrics, model)
            if not feature_cols:
                predictions[label] = {
                    "ok": False,
                    "error": "feature columns unavailable",
                    "model_file": str(mf),
                }
                continue

            row = _build_row(feature_cols, snapshot)
            df = pd.DataFrame([row], columns=feature_cols)
            prob = _predict_prob(model, df)

            m = metrics.get(label, {})
            threshold = float(m.get("seuil_decision", 0.5))
            predictions[label] = {
                "ok": True,
                "prob": prob,
                "threshold": threshold,
                "positive": prob >= threshold,
                "test_auc": m.get("test_auc"),
                "gap": m.get("gap"),
                "status": m.get("statut"),
                "model_file": str(mf),
            }
        except Exception as exc:
            predictions[label] = {
                "ok": False,
                "error": str(exc),
                "model_file": str(mf),
            }

    print(json.dumps({"ok": True, "predictions": predictions}))


if __name__ == "__main__":
    main()
