import os

paths = {
    "unified-DFI/train.txt":         "D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt",
    "unified-DFI/train.txt.bak":     "D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak",
    "unified-DFI/test.txt":          "D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/test.txt",
    "train_final.txt (workspace)":   "D:/23AIBox-DFinder/train_final.txt",
    "drug_id_map.csv":               "D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv",
    "food_id_map.csv":               "D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv",
}

for label, path in paths.items():
    if os.path.exists(path):
        with open(path) as f:
            lines = f.readlines()
        print(f"{label}: {len(lines)} lines | first: {lines[0][:80].strip()}")
    else:
        print(f"{label}: NOT FOUND")

# Are unified-DFI/train.txt and workspace train_final.txt the same?
print()
with open("D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt") as f:
    uni = f.read()
with open("D:/23AIBox-DFinder/train_final.txt") as f:
    fin = f.read()
print(f"train.txt == train_final.txt? {uni[:500] == fin[:500]}")
print(f"train.txt size: {len(uni)} chars | train_final.txt size: {len(fin)} chars")

# Also check train.txt.bak vs current train.txt
if os.path.exists("D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak"):
    with open("D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak") as f:
        bak = f.read()
    print(f"\ntrain.txt same as .bak? {uni == bak}")
    print(f".bak size: {len(bak)} chars")
