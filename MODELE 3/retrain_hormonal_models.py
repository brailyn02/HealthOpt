import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _load_training_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    drug_df = pd.read_csv(DATA_DIR / "drug_hormonal_risk.csv")
    hormone_df = pd.read_csv(DATA_DIR / "hormone_profiles.csv")
    cyp_df = pd.read_csv(DATA_DIR / "cyp_modulation.csv")

    # Add LH/FSH for the 6-feature risk models.
    hormone_feats = hormone_df[["patient_id", "cycle_day", "lh_mui_ml", "fsh_mui_ml"]]
    drug_df = drug_df.merge(hormone_feats, on=["patient_id", "cycle_day"], how="left")
    cyp_df = cyp_df.merge(hormone_feats, on=["patient_id", "cycle_day"], how="left")

    # Ensure no NaN in numeric model features.
    for col in ["lh_mui_ml", "fsh_mui_ml"]:
        drug_df[col] = drug_df[col].fillna(drug_df[col].median())
        cyp_df[col] = cyp_df[col].fillna(cyp_df[col].median())

    return drug_df, cyp_df


def train_model_a(drug_df: pd.DataFrame) -> xgb.XGBRegressor:
    le_drug = LabelEncoder()
    le_phase = LabelEncoder()
    le_enzyme = LabelEncoder()

    df = drug_df.copy()
    df["dominant_enzyme"] = df["dominant_enzyme"].fillna("None")

    df["drug_enc"] = le_drug.fit_transform(df["drug"])
    df["phase_enc"] = le_phase.fit_transform(df["phase"])
    df["enzyme_enc"] = le_enzyme.fit_transform(df["dominant_enzyme"])

    features = [
        "drug_enc",
        "phase_enc",
        "estrogen_pg_ml",
        "progesterone_ng_ml",
        "lh_mui_ml",
        "fsh_mui_ml",
    ]

    X = df[features]
    y = df["risk_adjustment_pct"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200,
        learning_rate=0.07,
        max_depth=7,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    print("Model A")
    print(f"  MAE: {mean_absolute_error(y_test, pred):.3f}")
    print(f"  R2 : {r2_score(y_test, pred):.4f}")

    joblib.dump(model, MODELS_DIR / "hormonal_risk_regressor.pkl")
    joblib.dump(le_drug, MODELS_DIR / "le_drug.pkl")
    joblib.dump(le_phase, MODELS_DIR / "le_phase.pkl")
    joblib.dump(le_enzyme, MODELS_DIR / "le_enzyme.pkl")

    return model


def train_model_b(drug_df: pd.DataFrame) -> xgb.XGBClassifier:
    le_drug = joblib.load(MODELS_DIR / "le_drug.pkl")
    le_phase = joblib.load(MODELS_DIR / "le_phase.pkl")

    df = drug_df.copy()
    df["drug_enc"] = le_drug.transform(df["drug"])
    df["phase_enc"] = le_phase.transform(df["phase"])

    features = [
        "drug_enc",
        "phase_enc",
        "estrogen_pg_ml",
        "progesterone_ng_ml",
        "lh_mui_ml",
        "fsh_mui_ml",
    ]

    X = df[features]
    y = df["risk_category"].astype(str)

    le_risk = LabelEncoder()
    y_enc = le_risk.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    model = xgb.XGBClassifier(
        objective="multi:softmax",
        num_class=len(le_risk.classes_),
        n_estimators=140,
        learning_rate=0.08,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    print("Model B")
    print(f"  Accuracy: {accuracy_score(y_test, pred):.4f}")

    joblib.dump(model, MODELS_DIR / "hormonal_risk_classifier.pkl")
    joblib.dump(le_risk, MODELS_DIR / "le_risk.pkl")

    return model


def train_model_c(cyp_df: pd.DataFrame) -> MultiOutputRegressor:
    features = ["estrogen_pg_ml", "progesterone_ng_ml", "lh_mui_ml", "fsh_mui_ml"]
    targets = [c for c in cyp_df.columns if c.endswith("_modulation_pct")]

    X = cyp_df[features]
    y = cyp_df[targets]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    base = GradientBoostingRegressor(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=5,
        random_state=42,
    )
    model = MultiOutputRegressor(base, n_jobs=-1)
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    print("Model C")
    print(f"  Mean MAE: {np.mean(mean_absolute_error(y_test, pred, multioutput='raw_values')):.3f}")
    print(f"  Mean R2 : {np.mean(r2_score(y_test, pred, multioutput='raw_values')):.4f}")

    joblib.dump(model, MODELS_DIR / "cyp_predictor.pkl")

    return model


def main() -> None:
    drug_df, cyp_df = _load_training_data()

    train_model_a(drug_df)
    train_model_b(drug_df)
    train_model_c(cyp_df)

    print("\nSaved artifacts:")
    for p in sorted(MODELS_DIR.glob("*.pkl")):
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
