"""
fix_all_smiles.py — repair all wrong/invalid SMILES in north_african_food_drug_interactions.txt
Verified against PubChem CIDs.
"""
import re

FILE = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"

with open(FILE, encoding="utf-8") as f:
    text = f.read()

original_len = len(text)
fixes = []

# ─── helper ───────────────────────────────────────────────────────────────────
def fix(old, new, desc):
    global text
    count = text.count(old)
    if count == 0:
        print(f"  [WARN] NOT FOUND: {desc}")
        return
    text = text.replace(old, new)
    fixes.append((desc, count))
    print(f"  [OK] {count}× replaced: {desc}")

# ══════════════════════════════════════════════════════════════════════════════
# 1. URIC ACID — all 11 instances (CID=0 → CID 1175)
#    Bad:  C12C(=O)NC(=O)NC1=C(NC(=O)N2)O  (split over 2 rows)
#    Good: C12=C(NC(=O)N1)NC(=O)NC2=O       (CID 1175)
# ══════════════════════════════════════════════════════════════════════════════

# variant A — single-space before pipe on row1
fix(
    "| C12C(=O)NC(=O)NC1=C(NC(=O) |\n   |                           | N2)O                         |",
    "| C12=C(NC(=O)N1)NC(=O)NC2=O  |",
    "Uric Acid (2→1 row, variant A)"
)

# variant A2 — slight spacing difference
fix(
    "| C12C(=O)NC(=O)NC1=C(NC(=O) |\n   |                           | N2)O                        |",
    "| C12=C(NC(=O)N1)NC(=O)NC2=O  |",
    "Uric Acid (2→1 row, variant A2)"
)

# variant B — double-space before pipe on row1 (wider table)
fix(
    "| C12C(=O)NC(=O)NC1=C(NC(=O)  |\n   |                           | N2)O                         |",
    "| C12=C(NC(=O)N1)NC(=O)NC2=O  |",
    "Uric Acid (2→1 row, variant B)"
)

# variant C — narrow left column (dishes 57-62)
fix(
    "| C12C(=O)NC(=O)NC1=C(NC(=O)  |\n   |                        | N2)O                         |",
    "| C12=C(NC(=O)N1)NC(=O)NC2=O  |",
    "Uric Acid (2→1 row, variant C)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 2. ALLICIN WRONG INSTANCES
#    L3347: O=S(=O)(CC=C)CC=C  → diallyl sulfone (CID 159797) → allicin CID 65036
#    L5515: O=S(CC=C)CC=C      → diallyl sulfoxide (CID 161032) → allicin CID 65036
#    Correct allicin: C=CCSS(=O)CC=C  (CID 65036)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| O=S(=O)(CC=C)CC=C            |",
    "| C=CCSS(=O)CC=C               |",
    "Allicin diallyl-sulfone → true allicin (L3347)"
)
fix(
    "| O=S(CC=C)CC=C                |",
    "| C=CCSS(=O)CC=C               |",
    "Allicin diallyl-sulfoxide → true allicin (L5515)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 3. CARVONE (CID=0 → CID 16724)
#    Bad:  O=C1CC(=C(C)C)CC(=C1)C
#    Good: CC1=CC[C@@H](CC1=O)C(=C)C  (CID 16724)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| O=C1CC(=C(C)C)CC(=C1)C     |",
    "| CC1=CC[C@@H](CC1=O)C(=C)C  |",
    "Carvone wrong ring → correct (L1552)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 4. APIGENIN — 3 instances of wrong SMILES
#    (a) L1545: naringenin O=C1CC(c2ccc(O)cc2)Oc3cc(O)cc(O)c13 (CID 932)
#    (b) L5303 & L5361: chalcone O=C1CC(=CC2=CC(O)=CC(O)=C12)c3ccc(O)cc3 (CID=0)
#    Correct apigenin: C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O)O)O (CID 5280443)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| O=C1CC(c2ccc(O)cc2)Oc3cc   |\n   |                           | (O)cc(O)c13                  |",
    "| C1=CC(=CC=C1C2=CC(=O)       |\n   |                           | C3=C(C=C(C=C3O2)O)O)O        |",
    "Apigenin naringenin→apigenin (L1545, Harira)"
)
fix(
    "| O=C1CC(=CC2=CC(O)=CC(O)=C12) |\n   |                        | c3ccc(O)cc3                  |",
    "| C1=CC(=CC=C1C2=CC(=O)        |\n   |                        | C3=C(C=C(C=C3O2)O)O)O        |",
    "Apigenin chalcone→apigenin (L5303/L5361)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 5. EPA — wrong chain length C22:5 DPA → correct C20:5 EPA
#    Bad:  CCCCC/C=C\C/C=C\C/C=C\C/C=C\C/C=C\CCC(=O)O  (C22:5 DPA)
#    Good: CC/C=C\C/C=C\C/C=C\C/C=C\C/C=C\CCCC(=O)O     (C20:5 EPA)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| CCCCC/C=C\\C/C=C\\C/C=C\\      |\n   |                           | C/C=C\\C/C=C\\CCC(=O)O        |",
    "| CC/C=C\\C/C=C\\C/C=C\\C/C=C\\   |\n   |                           | C/C=C\\CCCC(=O)O              |",
    "EPA DPA→EPA (L1829)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 6. LINOLEIC ACID — C19:2 → correct C18:2
#    Bad:  CCCCCC/C=C\C/C=C\CCCCCCCC(=O)O  (C19:2)
#    Good: CCCCC/C=C\C/C=C\CCCCCCCC(=O)O   (C18:2, CID 5280450)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| CCCCCC/C=C\\C/C=C\\CCCCCCCC  |",
    "| CCCCC/C=C\\C/C=C\\CCCCCCCC   |",
    "Linoleic Acid C19→C18 (L3760)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 7. ALPHA-LINOLENIC ACID (ALA) — 2 instances
#    (a) L3903: CCC/C=C\... → C19:3; fix to CC/C=C\... C18:3
#    (b) L4688: OC(=O)CCC... reverse orient → C21; fix to standard C18:3
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| CCC/C=C\\C/C=C\\C/C=C\\CCCCCC  |",
    "| CC/C=C\\C/C=C\\C/C=C\\CCCCCC   |",
    "ALA C19→C18 row1 (L3903)"
)
fix(
    "| OC(=O)CCC/C=C\\C/C=C\\C/C=C\\ |\n   |                           | CCCCCCCCC                    |",
    "| CC/C=C\\C/C=C\\C/C=C\\CCCCCC   |\n   |                           | CC(=O)O                      |",
    "ALA reverse-orientation C21→C18 (L4688)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 8. QUERCETIN — gossypetin-like CID→ correct quercetin CID 5280343
#    Bad:  OC1=CC(=C2C(=O)C=C(OC2=C1O)c3ccc(O)c(O)c3)O
#    Good: C1=CC(=C(C=C1C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)O)O)O (CID 5280343)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| OC1=CC(=C2C(=O)C=C(OC2=C1O) |\n   |                        | c3ccc(O)c(O)c3)O            |",
    "| C1=CC(=C(C=C1C2=C(C(=O)      |\n   |                        | C3=C(C=C(C=C3O2)O)O)O)O)O   |",
    "Quercetin gossypetin→quercetin (L5287)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 9. BENZO[a]PYRENE — anthracene (3-ring) → benzo[a]pyrene (5-ring, CID 9153)
#    Bad:  C1=CC2=C(C=C1)C=C3C=CC=CC3=C2
#    Good: C1=CC=C2C3=C4C(=CC=C3)C5=CC=CC=C5C4=CC2=C1
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| C1=CC2=C(C=C1)C=C3C=CC=CC3  |\n   |                           | =C2                          |",
    "| C1=CC=C2C3=C4C(=CC=C3)C5=CC |\n   |                           | =CC=C5C4=CC2=C1              |",
    "Benzo[a]pyrene anthracene→5-ring PAH (L312)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 10. SUCROSE (Mesfouf L14) — wrong molecule → correct sucrose CID 5988
#     Bad:  C(C1C(C(C(C(O1)OC2(C(C(C(O2)CO)O)O)CO)O)O)O)O  (CID 1115)
#     Good: same format as L431 sucrose
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| C(C1C(C(C(C(O1)OC2(C(C(C(  |\n   |                           | O2)CO)O)O)CO)O)O)O)O         |",
    "| OC[C@H]1O[C@@](CO)(O[C@@H]  |\n   |                           | 2[C@@H](O)[C@H](O)[C@@H](O) |\n   |                           | [C@H]2O)[C@@H](O)[C@@H]1O   |",
    "Sucrose wrong→correct CID 5988 (L838)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 11. 6-GINGEROL — CID=0 → CID 442793
#     Bad:  CCCCCC(CC(=O)CC1=CC(=C(C=C1)OC)O)O  (2 rows)
#     Good: CCCCC[C@@H](CC(=O)CCC1=CC(=C(C=C1)O)OC)O (CID 442793)
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| CCCCCC(CC(=O)CC1=CC(=C(C=  |\n   |                           | C1)OC)O)O                    |",
    "| CCCCC[C@@H](CC(=O)CCC1=CC   |\n   |                           | (=C(C=C1)O)OC)O              |",
    "6-Gingerol wrong chain+ring → correct (L1155)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 12. SESAMIN abbrev — ERROR 400 (invalid SMILES) → correct CID 72307
#     Bad:  C1OC2=CC(=CC=C2)CC3CC(=O)OC4=CC=C(C=C34)OC  (invalid)
#     Good: C1[C@H]2[C@H](CO[C@@H]2C3=CC4=C(C=C3)OCO4)[C@H](O1)C5=CC6=C(C=C5)OCO6
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| C1OC2=CC(=CC=C2)CC3CC(=O)   |\n   |                           | OC4=CC=C(C=C34)OC           |",
    "| C1[C@H]2[C@H](CO[C@@H]2     |\n   |                           | C3=CC4=C(C=C3)OCO4)[C@H](O1)|\n   |                           | C5=CC6=C(C=C5)OCO6           |",
    "Sesamin invalid→correct CID 72307 (L2591)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 13. MALTOSE rep. — glucose (CID 5793) mislabelled as maltose → correct maltose CID 6255
#     Bad:  OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O  (glucose, 2 rows in table)
#     The exact 2 rows are:
#       row1: OC[C@H]1OC(O)[C@H](O)
#       row2: [C@@H](O)[C@@H]1O
#     Good: partial maltose disaccharide 2-row
#     PubChem CID 6255: C([C@@H]1[C@H]([C@@H]([C@H]([C@H](O1)O[C@@H]2[C@H](O[C@H]([C@@H]([C@H]2O)O)O)CO)O)O)O)O
# ══════════════════════════════════════════════════════════════════════════════
# The maltose-labeled glucose appears ONLY in Tamina (L37) as "Maltose rep."
# It's in the context: "SMILES (Maltose rep.):\n   | OC[C@H]1OC(O)[C@H](O)  "
# However the same glucose SMILES appears many times as "Glucose unit" or "starch fragment"
# So we need to match SPECIFICALLY the "Maltose rep." label context.
text = re.sub(
    r"(\| SMILES \(Maltose rep\.\):\s+\|\n   \|                           \|) OC\[C@H\]1OC\(O\)\[C@H\]\(O\)\s+\|\n   \|                           \| \[C@@H\]\(O\)\[C@@H\]1O\s+\|",
    r"\1 C([C@@H]1[C@H]([C@@H]([C@H](       |\n   |                           | [C@H](O1)O[C@@H]2[C@H](O    |\n   |                           | [C@H]([C@@H]([C@H]2O)O)O)CO)|\n   |                           | O)O)O)O                      |",
    text
)

# ══════════════════════════════════════════════════════════════════════════════
# 14. LYCOPENE — all simplified/truncated versions → full CID 446925
#     Bad patterns:
#       a) "CC(=CCC/C(=C\CCC=C(C)C)/C)C"  (just 4 isoprene units — geranyl fragment)
#       b) "CC(=CCC=C(C)C=CC=C(C)CCC=C(C)C=CC=C(C)CCC=C(C)C)C"  (truncated C40)
#     Good: full lycopene over 3 rows
#     PubChem CID 446925: CC(=CCC/C(=C/C=C/C(=C/C=C/C(=C/C=C/C=C(/C=C/C=C(/C=C/C=C(/CCC=C(C)C)\C)\C)\C)/C)/C)/C)C
# ══════════════════════════════════════════════════════════════════════════════

# Full lycopene in table (3 rows within standard column width ~28 chars)
LYCO_CORRECT = (
    "| CC(=CCC/C(=C/C=C/C(=C/C=C/  |\n"
    "   |                           | C(=C/C=C/C=C(/C=C/C=C(/C=C/ |\n"
    "   |                           | C=C(/CCC=C(C)C)\\C)\\C)\\C)/C)/C)/C)C |"
)
# same for narrower column (dishes 57+)
LYCO_CORRECT_NARROW = (
    "| CC(=CCC/C(=C/C=C/C(=C/C=C/  |\n"
    "   |                        | C(=C/C=C/C=C(/C=C/C=C(/C=C/ |\n"
    "   |                        | C=C(/CCC=C(C)C)\\C)\\C)\\C)/C)/C)/C)C |"
)

# (a) short 2-row fragment in narrow column (dishes 57/58)
fix(
    "| CC(=CCC/C(=C\\CCC=C(C)C)     |\n   |                        | /C)C                         |",
    LYCO_CORRECT_NARROW,
    "Lycopene 4-unit fragment → full C40 (dishes 57/58)"
)

# (b) truncated C40 in standard column (dish 38 Douwara)
fix(
    "| CC(=CCC=C(C)C=CC=C(C)CCC=C  |\n   |                           | (C)C=CC=C(C)CCC=C(C)C)C     |",
    LYCO_CORRECT.replace("   |                           |", "   |                           |"),
    "Lycopene truncated C40 → full (dish 38)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 15. BETA-CAROTENE — severely truncated → full CID 5280489
#     Bad:  CC(=CCC=C(C)CCC=C(C)CCC=C(C)C)C  (just ~10 of 40 carbons)
#     Good: CC1=C(C(CCC1)(C)C)/C=C/C(=C/C=C/C(=C/C=C/C=C(/C=C/C=C(/C=C/C2=C(CCCC2(C)C)C)\C)\C)/C)/C
# ══════════════════════════════════════════════════════════════════════════════
BCAROTENE = (
    "CC1=C(C(CCC1)(C)C)/C=C/C(=C/C=C/C(=C/C=C/C=C(/C=C/C=C(/C=C/"
    "C2=C(CCCC2(C)C)C)\\C)\\C)/C)/C"
)
# In Biri dish 60 (narrow column)
fix(
    "| CC(=CCC=C(C)CCC=C(C)         |\n   |                        | CCC=C(C)C)C                  |",
    "| CC1=C(C(CCC1)(C)C)/C=C/C(=C/ |\n   |                        | C=C/C(=C/C=C/C=C(/C=C/C=C(/ |\n   |                        | C=C/C2=C(CCCC2(C)C)C)\\C)\\C) |\n   |                        | /C)/C                        |",
    "Beta-Carotene truncated → full CID 5280489 (Biri)"
)

# ══════════════════════════════════════════════════════════════════════════════
# 16. TRIPALMITIN — truncated with "..." → full structure CID 68441
#     Bad:  CCCCCCCCCCCCCCCC(=O)OC...
#     Good: CCCCCCCCCCCCCCCC(=O)OCC(COC(=O)CCCCCCCCCCCCCCC)OC(=O)CCCCCCCCCCCCCCC
# ══════════════════════════════════════════════════════════════════════════════
fix(
    "| CCCCCCCCCCCCCCCC(=O)OC...    |",
    "| CCCCCCCCCCCCCCCC(=O)OCC(     |\n   |                           | COC(=O)CCCCCCCCCCCCCCC)      |\n   |                           | OC(=O)CCCCCCCCCCCCCCC        |",
    "Tripalmitin truncated → full glycerol triester (L3368)"
)

# ══════════════════════════════════════════════════════════════════════════════
# print report
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"Original size: {original_len} chars")
print(f"Modified size: {len(text)} chars")
print(f"\nFixes applied ({len(fixes)}):")
for desc, count in fixes:
    print(f"  {count}× {desc}")

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(text)
print(f"\nFile written. ✓")
