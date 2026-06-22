"""
Phase 7 - Compound Resolver

Two-branch resolution for bioactive compounds returned by the LLM:

  Branch A (KGE-direct):  compound name exists in mech_entity2id.txt
                          -> no API call, use existing KGE scoring directly
                          -> covers ~982 common bioactives (Capsaicin, Quercetin,
                             Caffeine, Allicin, Curcumin, Naringenin, EGCG ...)

  Branch B (PubChem-LGN): compound not in KGE vocab
                          -> PubChem lookup -> SMILES -> Morgan fingerprint
                          -> used for LightGCN fingerprint similarity scoring

  Branch none:            compound unresolvable -> skip silently

Usage:
    from compound_resolver import CompoundResolver

    cr = CompoundResolver()
    cr.resolve("Capsaicin")
    # -> {"branch": "kge", "name": "Capsaicin", "entity_id": 312}

    cr.resolve("Bergamottin")
    # -> {"branch": "kge", "name": "Bergamottin", "entity_id": 87}

    cr.resolve("SomeObscureCompound")
    # -> {"branch": "lgn", "name": "SomeObscureCompound", "smiles": "C...",
    #     "fingerprint": <np.ndarray shape (2048,)>}
    # or {"branch": "none", "name": "SomeObscureCompound"}
"""

import numpy as np
from pathlib import Path

ROOT       = Path(__file__).resolve().parent
ENTITY2ID  = ROOT / "data" / "mechanistic_kge" / "mech_entity2id.txt"


class CompoundResolver:
    """
    Resolves compound names to KGE entity IDs (Branch A) or
    PubChem fingerprints (Branch B).

    Loaded once and reused for all queries.
    """

    def __init__(self, verbose: bool = True):
        # Load KGE entity vocabulary
        self._kge_vocab: dict[str, int] = {}
        with open(ENTITY2ID, encoding="utf-8") as f:
            lines = f.readlines()

        # First line may be the count — skip if it's a bare integer
        start = 1 if lines[0].strip().isdigit() else 0
        for line in lines[start:]:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                name, idx = parts
                self._kge_vocab[name.strip()] = int(idx)

        # Case-insensitive lookup index: lower -> original-cased name
        self._kge_lower: dict[str, str] = {
            k.lower(): k for k in self._kge_vocab
        }

        if verbose:
            print(f"CompoundResolver: {len(self._kge_vocab):,} KGE entities loaded")

    # ── Public API ────────────────────────────────────────────────────────────
    def resolve(self, name: str) -> dict:
        """
        Resolve a compound name to its scoring branch.

        Returns one of:
            {"branch": "kge",  "name": name, "entity_id": int}
            {"branch": "lgn",  "name": name, "smiles": str,
             "fingerprint": np.ndarray}
            {"branch": "none", "name": name}
        """
        # Branch A: KGE vocab (exact, then case-insensitive)
        if name in self._kge_vocab:
            return {"branch": "kge", "name": name,
                    "entity_id": self._kge_vocab[name]}

        lower = name.strip().lower()
        if lower in self._kge_lower:
            canonical = self._kge_lower[lower]
            return {"branch": "kge", "name": canonical,
                    "entity_id": self._kge_vocab[canonical]}

        # Branch B: PubChem -> SMILES -> fingerprint
        return self._pubchem_resolve(name)

    def resolve_list(self, names: list[str]) -> list[dict]:
        """Resolve a list of compound names, skipping 'none' branches."""
        results = []
        for n in names:
            r = self.resolve(n)
            if r["branch"] != "none":
                results.append(r)
        return results

    def is_in_kge(self, name: str) -> bool:
        """Return True if the compound name exists in the KGE entity vocab."""
        return name in self._kge_vocab or name.lower() in self._kge_lower

    # ── PubChem branch ────────────────────────────────────────────────────────
    @staticmethod
    def _pubchem_resolve(name: str) -> dict:
        try:
            import pubchempy as pcp
            from rdkit import Chem
            from rdkit.Chem import AllChem
            from rdkit.DataStructs import ConvertToNumpyArray

            compounds = pcp.get_compounds(name, "name")
            if not compounds:
                return {"branch": "none", "name": name}

            smiles = compounds[0].smiles
            if not smiles:
                return {"branch": "none", "name": name}

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return {"branch": "none", "name": name}

            gen     = AllChem.GetMorganGenerator(radius=2, fpSize=2048)
            fp      = gen.GetFingerprint(mol)
            fp_arr  = np.zeros(2048, dtype=np.float32)
            ConvertToNumpyArray(fp, fp_arr)
            return {
                "branch"      : "lgn",
                "name"        : name,
                "smiles"      : smiles,
                "fingerprint" : fp_arr,
            }

        except Exception:
            return {"branch": "none", "name": name}


# ── CLI / quick test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    cr = CompoundResolver()
    test_compounds = [
        "Capsaicin",
        "Naringenin",
        "Bergamottin",
        "Allicin",
        "Curcumin",
        "Quercetin",
        "Caffeine",
        "Menthol",
        "Thymoquinone",
        "SomeCompoundNotInKGE",
    ]
    print(f"\n{'Compound':<35}  Branch   Entity ID / Note")
    print("-" * 70)
    for c in test_compounds:
        r = cr.resolve(c)
        if r["branch"] == "kge":
            detail = f"entity_id={r['entity_id']}"
        elif r["branch"] == "lgn":
            detail = f"fp shape={r['fingerprint'].shape}, SMILES={r['smiles'][:40]}..."
        else:
            detail = "unresolvable"
        print(f"{c:<35}  {r['branch']:<6}   {detail}")
