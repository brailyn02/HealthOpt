def stats(path, label):
    try:
        lines = open(path, encoding='utf-8').readlines()
        pairs = sum(len(l.split())-1 for l in lines if len(l.split())>1)
        print(f"{label}: {len(lines)} lines, {pairs} positive pairs")
        print(f"  first: {lines[0][:70].strip()}")
    except Exception as e:
        print(f"{label}: ERROR {e}")

print("=== All candidate training files ===\n")
stats('D:/23AIBox-DFinder/generated/unified_train_interactions.txt',        'generated/unified_train_interactions    ')
stats('D:/23AIBox-DFinder/generated/unified_train_interactions_clean.txt',  'generated/unified_train_interactions_clean')
stats('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt',         'unified-DFI/train.txt  (ACTUAL TRAINING)')
stats('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak',     'unified-DFI/train.txt.bak              ')
stats('D:/23AIBox-DFinder/train_final.txt',                                  'workspace/train_final.txt              ')
stats('D:/23AIBox-DFinder/DFinder-main/data/pubmed-DFI/data/train.txt',     'pubmed-DFI/train.txt                   ')
stats('D:/23AIBox-DFinder/DFinder-main/data/drugbank-DFI/data/train.txt',   'drugbank-DFI/train.txt                 ')

# Check if unified_train_interactions_clean.txt matches unified-DFI/train.txt
print("\n=== Content comparison ===")
a = open('D:/23AIBox-DFinder/generated/unified_train_interactions_clean.txt', encoding='utf-8').read()
b = open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt', encoding='utf-8').read()
bak = open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak', encoding='utf-8').read()
print(f"unified_train_interactions_clean == unified-DFI/train.txt?    {a == b}")
print(f"unified_train_interactions_clean == unified-DFI/train.txt.bak? {a == bak}")
print(f"unified_train_interactions_clean first 100: {a[:100]}")
print(f"unified-DFI/train.txt           first 100: {b[:100]}")

# Also check pubmed vs train_final
fin = open('D:/23AIBox-DFinder/train_final.txt', encoding='utf-8').read()
pub = open('D:/23AIBox-DFinder/DFinder-main/data/pubmed-DFI/data/train.txt', encoding='utf-8').read()
print(f"\nIs train_final a subset content-wise? First 100 train_final: {fin[:100]}")
