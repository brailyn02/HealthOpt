"""
Parse na_interaction_verification_v3.txt → data/na_dish_compounds.json
Extracts all bioactive compounds per dish (all verdict types).
"""
import re, json, pathlib

SRC  = pathlib.Path(__file__).parent / "na_interaction_verification_v3.txt"
DEST = pathlib.Path(__file__).parent / "data" / "na_dish_compounds.json"
DEST.parent.mkdir(exist_ok=True)

# ── regex helpers ─────────────────────────────────────────────────────────────
DISH_RE   = re.compile(r"^Dish \d+:\s*(.+)$")
# line has compound+arrow pattern (preceded by verdict prefix + whitespace)
INTER_RE  = re.compile(r"^\s+[✓~?].+?\s{2,}(.+?)\s{2,}→")

def clean_compound(raw: str) -> list[str]:
    """Split composite labels and strip decorative parentheticals."""
    raw = raw.strip()
    # remove trailing parenthetical descriptions like "(Almonds)", "(Saffron)", etc.
    # but keep the compound name before it
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    # split on ' + ' first (preserves labels like 'L-Arginine + Vitamin E')
    parts = re.split(r"\s*\+\s*", raw)
    cleaned = []
    for p in parts:
        p = p.strip()
        # strip remaining inline parentheticals
        p = re.sub(r"\s*\([^)]*\)", "", p).strip()
        # skip pure-label artefacts (all caps short descriptors without letters pattern)
        if p and len(p) >= 2:
            cleaned.append(p)
    return cleaned

# ── parse ─────────────────────────────────────────────────────────────────────
dishes: dict[str, list[str]] = {}   # canonical_name → [compound, ...]
current_dish = None

with open(SRC, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")

        m = DISH_RE.match(line)
        if m:
            current_dish = m.group(1).strip()
            if current_dish not in dishes:
                dishes[current_dish] = []
            continue

        if current_dish is None:
            continue

        m = INTER_RE.match(line)
        if m:
            compound_raw = m.group(1).strip()
            for c in clean_compound(compound_raw):
                if c not in dishes[current_dish]:
                    dishes[current_dish].append(c)

# ── build output: lowercase keys for lookup + pretty display ──────────────────
output: dict[str, list[str]] = {}
for dish, compounds in dishes.items():
    key = dish.lower()
    output[key] = compounds

# ── save ──────────────────────────────────────────────────────────────────────
with open(DEST, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Saved {len(output)} dishes → {DEST}")
for name, comps in sorted(output.items()):
    print(f"  {name!r:40s} {len(comps):3d} compounds")
