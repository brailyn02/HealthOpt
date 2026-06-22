import sys
sys.path.insert(0, "D:/23AIBox-DFinder")
from predict import DFinder

df = DFinder(verbose=False)

test_pairs = [
    ("Warfarin",      "Spinach"),
    ("Phenelzine",    "Aged Cheese"),
    ("Ciprofloxacin", "Milk"),
    ("Metformin",     "Grapefruit"),
    ("Lisinopril",    "Banana"),
    ("Itraconazole",  "Milk"),
    ("Aspirin",       "Lemon"),
    ("Aspirin",       "Orange"),
    ("Aspirin",       "Grapefruit"),
]

print(f"\n{'Drug':<20} {'Food':<20} {'Conf':<12} {'Flags':<30} Phys Warnings")
print("-" * 110)
for drug, food in test_pairs:
    r = df.predict(drug, food)
    pw = r.get("physicochemical_warnings", [])
    pw_str = ", ".join(f"{w['rule']}[{w['severity']}]" for w in pw) if pw else "(none)"
    flags_str = "|".join(r["flags"]) if r["flags"] else "—"
    print(f"{drug:<20} {food:<20} {r['confidence']:<12} {flags_str:<30} {pw_str}")
