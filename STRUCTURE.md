# HealthOpt Project Structure

This document explains every folder, file, and dataset in this repository, including data provenance, what each component does, and what is excluded from GitHub and why.

---

## Overview

**HealthOpt** is a personalized drug-food interaction (DFI) prediction and nutritional safety platform. It is organized into three modules:

### Module 1 — Drug-Food Interaction Predictive Engine
The core prediction system. Takes a drug and a food as input and returns an interaction risk score, confidence tier, and mechanistic explanation. Built as a 4-layer pipeline where each layer adds mechanistic depth:

| Layer | Name | Method | Data |
|-------|------|---------|------|
| 0 | Physicochemical / Clinical Safety Gate | Rule-based CYP450 + pharmacokinetics | `data/food_content_table.csv`, `data/drug_sensitivity_table.csv` |
| 1 | Graph Query (HKG) | Heterogeneous knowledge graph, enzyme overlap | `data/processed_hkg/` |
| 2 | Mechanistic KGE | RotatE knowledge graph embedding | `data/mechanistic_kge/` |
| 3 | LightGCN Collaborative Filtering | Graph neural network on interaction matrix | `DFinder-main/data/unified-DFI/` |

Fusion rule (piecewise, LightGCN score drives blending):
```
LGN >= 0.98  →  trust LGN only
LGN >= 0.90  →  0.80 × LGN + 0.20 × Mech
LGN >= 0.70  →  0.70 × LGN + 0.30 × Mech
else         →  0.35 × LGN + 0.65 × Mech
```

Confidence tiers: **HIGH** ≥ 0.70 · **MEDIUM** ≥ 0.45 · **LOW** ≥ 0.20 · **INSUFFICIENT**

### Module 2 — Blood Biomarker Deficiency Prediction
Takes a user's blood test values (ferritin, hemoglobin, calcium, B12, vitamin D, etc.) and predicts nutrient deficiencies using LightGBM models trained on NHANES survey data. Generates personalized nutritional recommendations ("virtual medications"). Lives in `mon_projet_nutrition/`.

### Module 3 — Hormonal Risk Adjustment
Adjusts Module 1's interaction risk tier based on the user's menstrual cycle phase. CYP enzyme activity varies across the cycle; this module applies learned modifiers to refine drug-food risk scores for female users. Lives in `MODELE 3/`.

### Web Application
The `web/` folder contains the full-stack application (Express/TypeScript backend + React/Vite frontend) that exposes all three modules to end users. Includes professional dashboards for doctors, pharmacists, and nutritionists.

### Wrapper A — Algerian Drug Name Resolver
Maps Algerian/Arabic trade names to INN generic drug names (`drug_resolver.py`, `algerian_brand_map.csv`, `algerian_drugs.csv`) so users can enter local brand names.

### Wrapper B — Food Decomposition Pipeline
Resolves a food input (including complex dishes, North African foods, or branded products) into its constituent bioactive compounds so they can be queried against the knowledge graph. Runs in priority order:
1. **NA seed lookup** — checks `data/na_dish_compounds.json` for curated Algerian/North African dishes
2. **FooDB lookup** — queries pre-processed FooDB compound tables via `foodb_lookup.py`
3. **LLM decompose** — falls back to LLM-based ingredient decomposition via `llm_decompose.py` if the food is not found in either database

Compound IDs are then resolved to graph entities via `compound_resolver.py`. The food context parser also handles modifiers like "without cheese" or "tomato only" to suppress irrelevant compound warnings.

---

## Root-Level Files

### Module 1 — Prediction Engine

| File | Purpose |
|------|---------|
| `predict.py` | Core prediction engine — `HealthOpt` class with `predict()` and `batch_predict()`. Orchestrates all 4 layers and the piecewise fusion. |
| `api.py` | **Production** FastAPI server (131 lines). Background-thread model loading, `/health`, `/ready`, `/predict` endpoints. Use this one in production. |
| `fastapi_server.py` | Earlier, simpler FastAPI server (113 lines). Kept for reference; `api.py` supersedes it. |
| `lightgcn_inference.py` | Layer 3 — loads and runs the LightGCN model from `DFinder-main/code/checkpoints/`. |
| `mech_kge_inference.py` | Layer 2 — runs RotatE inference over `data/mechanistic_kge/`. |
| `graph_query.py` | Layer 1 — queries the HKG for enzyme-level drug-food overlap using `data/processed_hkg/`. |
| `physicochemical.py` | Layer 0 — CYP450 rule engine; reads `data/food_content_table.csv` and `data/drug_sensitivity_table.csv`. |
| `drug_resolver.py` | Wrapper A — maps Algerian/Arabic trade names to INN generics. Also loads `DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv`. |
| `compound_resolver.py` | Resolves food compound names to canonical IDs for graph lookup. |
| `foodb_lookup.py` | Looks up food compound content from pre-processed FooDB data. |
| `llm_decompose.py` | Decomposes a dish name into constituent ingredients using an LLM (fallback when FooDB misses). |
| `translator.py` | `create_dual_view()` — produces both a simple patient-facing and a technical clinician-facing explanation for each prediction. |
| `algerian_brand_map.csv` | Algerian trade names → INN generics (Wrapper A). Curated from national formulary data. |
| `algerian_drugs.csv` | Full list of drugs registered in Algeria with metadata (Wrapper A). |
| `dfi_interactions_from_keysentences.csv` | Benchmark dataset — DFI pairs extracted via NLP from the FooDrugs database and PubMed sentences. Used for evaluation only. |

### Module 2 — Blood Biomarker Inference

| File | Purpose |
|------|---------|
| `model2_infer.py` | Loads LightGBM/joblib models from `mon_projet_nutrition/models/` and predicts biomarker deficiencies from blood panel values. |

---

## `data/` — Module 1 Pre-processed Inputs

### `data/food_content_table.csv` — Layer 0 input
Compound content per food item (mg/100g). **Generated from** the raw USDA FoodData Central export (`FoodData_Central_foundation_food_csv_2025-04-24/` — excluded from GitHub). Source: [USDA FoodData Central](https://fdc.nal.usda.gov/).

### `data/drug_sensitivity_table.csv` — Layer 0 input
CYP enzyme sensitivity and pharmacokinetic flags per drug. **Source:** DrugBank (requires license — see `scripts/extract_drugbank_xml.py`). The raw DrugBank XML (`full database.xml`, 1.9 GB) is excluded from GitHub.

### `data/na_dish_compounds.json`
North African / Algerian dish compound lookup table. Curated manually to seed the food bridge pipeline before FooDB or LLM fallback.

### `data/llm_food_cache.json`
Cache of LLM-generated food decompositions (dish → ingredients). Persisted to avoid redundant API calls.

### `data/processed_hkg/` — Layer 1 inputs

The Heterogeneous Knowledge Graph (HKG) encodes drug-enzyme, food-compound, and compound-enzyme relationships.

| File | Contents |
|------|---------|
| `hkg_triplets.tsv` | All HKG edges: (head, relation, tail) |
| `hkg_drug_cyp_edges.csv` | Drug → CYP enzyme inhibition/induction edges |
| `hkg_compound_cyp_edges.csv` | Food compound → CYP enzyme modulation edges |
| `hkg_food_compound_edges.csv` | Food → constituent compound edges |
| `kge_input/entity2id.txt` | Entity-to-integer ID mapping for HKG training |
| `kge_input/relation2id.txt` | Relation-to-integer ID mapping |
| `kge_input/train.txt`, `test.txt`, `valid.txt` | HKG train/test/validation splits |

**Provenance:** Built by `scripts/build_hkg_triplets.py` and `scripts/prepare_hkg_training.py` from DrugBank XML, FooDB (Compound.csv, Content.csv — excluded), and nutrient-drug-enzyme annotations (`scripts/add_nutrient_drug_enz_edges.py`).

### `data/mechanistic_kge/` — Layer 2 inputs

RotatE knowledge graph embedding trained on the HKG to score novel drug-food-enzyme triples.

| File | Contents |
|------|---------|
| `mech_best.pt` | Best RotatE checkpoint (**tracked via Git LFS**) |
| `mech_ep50.pt` … `mech_ep300.pt` | Intermediate epoch checkpoints (Git LFS) |
| `mech_entity_embeddings.npy` | Learned entity embedding matrix (Git LFS) |
| `mech_relation_embeddings.npy` | Learned relation embedding matrix (Git LFS) |
| `lgn_drug_embeddings.npy` | Drug embeddings from LightGCN, reused in Layer 2 fusion (Git LFS) |
| `lgn_food_embeddings.npy` | Food embeddings from LightGCN (Git LFS) |
| `mech_entity2id.txt` | Entity ID mapping for mechanistic KGE |
| `mech_relation2id.txt` | Relation ID mapping |
| `mech_triplets.tsv` | All mechanistic training triples |
| `mech_train.txt`, `mech_test.txt`, `mech_valid.txt` | Train/test/validation splits |
| `mech_train.tsv`, `mech_test.tsv`, `mech_valid.tsv` | TSV versions of the above |

**Training scripts:**
- `train_mech_kge.py` — main RotatE training script for Layer 2. Trains on `data/mechanistic_kge/mech_train.txt`, saves checkpoints to `data/mechanistic_kge/mech_ep*.pt` and final best model to `mech_best.pt`.
- `train_kge.py` — earlier/alternative KGE training script (kept for reference).
- `modal_train.py` — version adapted for cloud training on Modal.com (used when local GPU was insufficient).

**Provenance:** Trained with RotatE on the HKG triplets. Data preparation is in `scripts/prepare_hkg_training.py`.

---

## `DFinder-main/` — Module 1 Layer 3 LightGCN Base

This folder contains the original open-source LightGCN codebase that Module 1's Layer 3 is built on. It is kept intact because `lightgcn_inference.py` and `drug_resolver.py` reference paths inside it directly.

### `DFinder-main/code/` — Layer 3 Training Code

| File | Purpose |
|------|---------|
| `main.py` | **Entry point for training and evaluation.** Run this to train LightGCN: `python main.py --dataset unified-DFI --layer 3 --dim 64` |
| `model.py` | LightGCN model definition — graph convolution layers, embedding propagation |
| `DNN.py` | Deep Neural Network baseline model — used alongside LightGCN for comparison/ablation; also contributes to the drug/food feature encoding |
| `Procedure.py` | Training loop, BPR loss computation, evaluation procedure (Recall, NDCG) |
| `dataloader.py` | Loads `train.txt`, `test.txt`, builds the sparse interaction graph and adjacency matrix (`s_pre_adj_mat.npz`) |
| `parse.py` | Argument parser — all hyperparameters (layers, embedding dim, learning rate, batch size, epochs) |
| `world.py` | Global config and device setup |
| `register.py` | Model and dataset registry |
| `utils.py` | Utility functions (metrics, early stopping, logging) |
| `eval_only.py` | Runs evaluation on a saved checkpoint without retraining |
| `save_finetune_results.py` | Saves fine-tuning results to file |

### `DFinder-main/code/checkpoints/`
| File | Contents |
|------|---------|
| `lgn-unified-DFI-3-64.pth.tar` | Trained LightGCN checkpoint — 3 layers, 64 embedding dim (**Git LFS**) |

### `DFinder-main/data/unified-DFI/` — Layer 3 training data

**Provenance of `train.txt`** (the core interaction matrix):

The unified training set was built from scratch via an 8-stage pipeline:

1. **PubMed NLP corpus**: Initial drug-food interaction pairs extracted from raw NLP sentences (PubMed abstracts).
2. **Kaggle DFI + Pomelo**: Aggregation into a unified drug/food entity space from the Kaggle DFI dataset and the Pomelo DFI database.
3. **DrugBank XML + FooDrugs**: Integration of drug-level DFI metadata from DrugBank enzyme entries and FooDrugs.
4. **PubChem API + FooDB**: Lookup and unification of chemical structures, producing clean canonical interactions.
5. **Algerian corpus integration**: Integration of Algerian-specific drug-food pairs and regional dietary edges.
6. **Cross-source validation**: Deduplication and coverage analysis across all five sources.
7. **SMILES mapping completion**: Completion of chemical structure (SMILES) mapping via PubChem API.
8. **Train/test partitioning + regional dietary edges**: Splitting into train/test/validation and addition of North African dietary edge triplets.

Build scripts are in `scripts/build_unified_interactions.py` and `scripts/build_unified_all.py`.

| File | Contents |
|------|---------|
| `train.txt` | Training interaction pairs (drug_id, food_id, label) |
| `test.txt` | Test interaction pairs |
| `train_neg.txt` | Negative (non-interaction) pairs for training |
| `train.txt.bak` | Backup of train.txt before last rebuild |
| `id_maps/drug_id_map.csv` | Maps drug entity strings → integer IDs (used by `drug_resolver.py`) |
| `id_maps/food_id_map.csv` | Maps food entity strings → integer IDs (used by `predict.py`) |
| `feature_extra/unified_drug_feature_extra.npy` | Drug feature matrix (fingerprints etc.) — Git LFS |
| `feature_extra/unified_drug_feature_extra.txt` | Text version / mapping |
| `feature_extra/unified_food_feature_extra.npy` | Food feature matrix — Git LFS |
| `feature_extra/unified_food_feature_extra.txt` | Text version / mapping |
| `feature_extra/unified_food_feature_extra.filled.npy` | Version with imputed missing values — Git LFS |
| `s_pre_adj_mat.npz` | Pre-computed sparse adjacency matrix for LightGCN — Git LFS |

---

## `MODELE 3/` — Module 3: Hormonal Risk Adjustment

Adjusts Module 1's interaction risk tier based on the user's menstrual cycle phase via CYP enzyme activity modifiers.

### `MODELE 3/models/` (all `.pkl` — tracked via Git LFS)
| File | Purpose |
|------|---------|
| `cyp_predictor.pkl` | Predicts CYP enzyme activity level from cycle phase + drug class |
| `cyp_scaler.pkl` | Feature scaler for CYP predictor |
| `hormonal_risk_classifier.pkl` | Classifies DFI risk tier given hormonal context |
| `hormonal_risk_regressor.pkl` | Regresses a continuous risk score |
| `le_drug.pkl`, `le_enzyme.pkl`, `le_phase.pkl`, `le_risk.pkl`, `le_phase_cyp.pkl` | Label encoders for categorical features |
| `hormonal_scaler.pkl` | Feature scaler for hormonal risk model |

### `MODELE 3/data/`
| File | Source |
|------|--------|
| `cyp_modulation.csv` | CYP enzyme activity modulation factors by cycle phase (literature-derived) |
| `drug_hormonal_risk.csv` | Drug class → baseline hormonal risk mapping |
| `hormone_profiles.csv` | Estrogen/progesterone level profiles by cycle phase |

### Other files
- `HealthOpt_Modele3_Hormonal_v2.ipynb` — training notebook
- `retrain_hormonal_models.py` — retraining script
- `validation/`, `validation_kaggle/` — validation results

---

## `mon_projet_nutrition/` — Module 2: Blood Biomarker Prediction

Predicts nutrient deficiencies from blood panel values (ferritin, hemoglobin, calcium, B12, vitamin D, etc.) and generates nutritional supplement recommendations.

### `mon_projet_nutrition/models/` (all `.pkl`/`.joblib` — Git LFS)
| File | Target biomarker |
|------|-----------------|
| `label_ferritine_LightGBM.pkl` | Ferritin (iron stores) |
| `label_hemoglobine_LightGBM.pkl` | Hemoglobin (anemia) |
| `label_calcium_best.joblib` | Calcium |
| `label_hba1c_LightGBM.pkl` | HbA1c (glycemic control) |
| `label_tsh_best.joblib` | TSH (thyroid) |
| *(and others for B12, vitamin D, magnesium, zinc, folate, etc.)* | |

### `mon_projet_nutrition/data/` — **EXCLUDED FROM GITHUB** (1.2 GB)
NHANES (National Health and Nutrition Examination Survey) raw `.xpt` survey data files from 1999–2023. Large public datasets — download directly from [CDC NHANES](https://www.cdc.gov/nchs/nhanes/index.htm). Also contains KNHANES (Korean NHANES) data.

### `mon_projet_nutrition/reports/`
- `best_metrics_v15.json` — final model metrics per biomarker
- `resultats_entrainement_v14.pdf` — training results report

---

## `web/` — Web Application

Full-stack application exposing all three modules to end users.

| Path | Contents |
|------|---------|
| `server.ts` | Express/TypeScript backend — calls Module 1 API at `http://localhost:8000/predict`, manages SQLite database, custom JWT auth (HS256), PIN hashing (HMAC-SHA256) |
| `src/` | React/Vite frontend source |
| `healthopt.db` | SQLite database (WAL mode) — **excluded from GitHub** (runtime state) |
| `dist/` | Built frontend — **excluded from GitHub** (run `npm run build`) |
| `node_modules/` | Dependencies — **excluded** (run `npm install`) |

The professional portal includes doctor, pharmacist, and nutritionist dashboards with patient share codes.

---

## `generated/` — Module 1 Pipeline Build Artifacts

Intermediate files produced by the data pipeline scripts in `scripts/`. These serve as checkpoints between pipeline stages.

| File | Produced by | Contents |
|------|------------|---------|
| `drugbank_dfi_enzymes.csv` | `extract_drugbank_xml.py` | Drug-enzyme pairs from DrugBank XML |
| `drugbank_drug_food_named.csv` | `extract_drugbank_xml.py` | Named drug-food interaction pairs |
| `drugbank_drug_smiles.csv` | `extract_drugbank_xml.py` | Drug SMILES strings from DrugBank |
| `drugbank_food_pairs.csv` | `extract_drugbank_xml.py` | Food interaction metadata |
| `foodb_drug_smiles.csv` | `merge_foodb_interactions.py` | Drug SMILES from FooDB lookup |
| `foodb_food_smiles.csv` | `merge_foodb_interactions.py` | Food compound SMILES |
| `pomelo_drug_smiles.csv` | `merge_pomelo_interactions.py` | Drug SMILES from Pomelo |
| `pomelo_food_smiles.csv` | `merge_pomelo_interactions.py` | Food SMILES from Pomelo |
| `unified_drug_master.txt` | `build_unified_interactions.py` | Canonical drug entity list |
| `unified_food_master.txt` | `build_unified_interactions.py` | Canonical food entity list |
| `unified_interactions.txt` | `build_unified_interactions.py` | All merged interaction pairs (pre-split) |
| `unified_train_interactions.txt` | `build_unified_all.py` | Final training interactions |
| `food_id_remap.csv` | `build_unified_all.py` | Food ID remapping table (old → new IDs) |
| `unified_drugs.tsv`, `unified_foods.tsv` | `build_unified_all.py` | Final canonical entity lists |

---

## `scripts/` — Module 1 Data Pipeline Build Scripts

Scripts that build all Module 1 datasets from scratch. Run in this order to reproduce the data:

1. `extract_drugbank_xml.py` — Parse DrugBank XML → `generated/drugbank_*.csv`
2. `merge_foodb_interactions.py` — FooDB tables → `generated/foodb_*.csv`
3. `merge_pomelo_interactions.py` — Pomelo → `generated/pomelo_*.csv`
4. `merge_drugbank_interactions.py` — Reconcile DrugBank interactions
5. `lookup_food_smiles_pubchem.py` — PubChem API SMILES completion
6. `enrich_food_features_foodb.py` — Add FooDB compound features
7. `build_unified_interactions.py` — Merge all sources → `generated/unified_*.txt`
8. `add_na_food_triplets.py` — Add North African dietary edges
9. `add_nutrient_drug_enz_edges.py` — Add nutrient-enzyme edges to HKG
10. `build_hkg_triplets.py` — Build HKG → `data/processed_hkg/`
11. `prepare_hkg_training.py` — Prepare HKG train/test splits
12. `build_unified_all.py` — Final pipeline → `DFinder-main/data/unified-DFI/train.txt`
13. `prepare_dfinder_data.py` — Prepare final Layer 3 inputs

---

## `validation_splits/` — Module 1 Evaluation Results

| File | Contents |
|------|---------|
| `validation_unseen.csv` | 889 held-out drug-food pairs (never seen during training) |
| `validation_test_split.csv` | Standard test split |
| `phase2_graph_query_results.csv` | Layer 1 scores on validation set |
| `phase3_lgn_scores.csv` | Layer 3 LightGCN scores on validation set |
| `phase4_kge_scores.csv` | Layer 2 KGE scores on validation set |
| `phase5_fusion_results.csv` | Final piecewise fusion scores on validation set |
| `layer_scores_by_pair.csv` | Per-pair scores across all layers |
| `layer_scores_by_pair_norm.csv` | Normalized version |

---

## `ablation_results/` — Ablation Study

Systematic ablation removing one layer at a time to measure each layer's contribution to Module 1.

| File | Contents |
|------|---------|
| `ablation_table.csv` | AUC/F1 for each layer combination |
| `fusion_ablation_results.csv` | Ablation of fusion strategies |
| `ablation_summary.txt` | Human-readable summary |
| `wrapper_b_vs_manual62*` | Comparison: automated Wrapper B vs. 62 manual pairs |
| `layer0_retrofitted.csv` | Layer 0 results retrofitted to the full validation set |

---

## Raw Source Data (Excluded from GitHub)

These files are too large for GitHub or require a license. Obtain them separately to reproduce the pipeline from scratch.

| File / Folder | Size | Source | Why Excluded |
|--------------|------|--------|-------------|
| `chembl_36_sqlite/` | ~28 GB | [ChEMBL](https://www.ebi.ac.uk/chembl/db_schema) | Far exceeds GitHub limits |
| `chembl_36_chemreps.txt` | ~725 MB | ChEMBL | Exceeds GitHub 100 MB limit |
| `full database.xml` | ~1.9 GB | [DrugBank](https://go.drugbank.com/releases/latest) | License required + size |
| `FoodData_Central_foundation_food_csv_2025-04-24/` | ~28 MB | [USDA FoodData Central](https://fdc.nal.usda.gov/download-foods) | Regenerated by scripts |
| `Content.csv`, `Compound.csv`, `Food.csv` | ~1–3 GB total | [FooDB](https://foodb.ca/downloads) | Size |
| `mon_projet_nutrition/data/` | ~1.2 GB | [CDC NHANES](https://www.cdc.gov/nchs/nhanes/) | Size; public data, download directly |
| `checkpoints_backup/` | ~1.3 GB | Local | Redundant backup |
| `dfinder-deploy.tar.gz` | variable | Local | Deploy artifact |
| `blood tests/` | small | Personal | **Private medical documents** |
| `web/healthopt.db` | runtime | Runtime | Database state |

---

## Git LFS — Binary Model Files

The following file types are tracked via Git LFS (not stored as regular Git objects):

```
*.pth.tar  *.pth  *.pt   # PyTorch checkpoints (Modules 1 & 3)
*.pkl      *.joblib       # Scikit-learn / LightGBM models (Modules 2 & 3)
*.npy      *.npz          # NumPy arrays and sparse matrices (Module 1)
```

To clone with model weights: `git lfs pull`

To set up LFS tracking on a fresh clone: `git lfs install`

---

## How to Run

### 1. Install dependencies
```bash
pip install fastapi uvicorn torch numpy scikit-learn lightgbm
cd web && npm install
```

### 2. Start Module 1 API
```bash
python api.py
# Starts on http://localhost:8000
# GET /health — check loading status
# GET /ready  — 503 until models are loaded
# POST /predict — main prediction endpoint
```

### 3. Start the web app
```bash
cd web
npm run dev    # development
npm run build  # production build
```

### 4. Reproduce the datasets (optional)
Requires: DrugBank XML license, FooDB download, USDA FoodData Central download, ChEMBL SQLite (optional).
Run `scripts/` in the order listed above.
