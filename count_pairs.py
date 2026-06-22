from pathlib import Path
files=[
 Path(r'd:/23AIBox-DFinder/train(kaggle).txt'),
 Path(r'd:/23AIBox-DFinder/train_final.txt'),
 Path(r'd:/23AIBox-DFinder/DFinder-main/data/pubmed-DFI/data/train.txt'),
 Path(r'd:/23AIBox-DFinder/DFinder-main/data/pubmed-DFI/data/train_neg.txt'),
 Path(r'd:/23AIBox-DFinder/DFinder-main/data/drugbank-DFI/data/train.txt'),
 Path(r'd:/23AIBox-DFinder/DFinder-main/data/drugbank-DFI/data/train_neg.txt'),
]
print('file,lines,positives')
for p in files:
    if not p.exists():
        print(p.name,'MISSING')
        continue
    text=p.read_text(encoding='utf-8').strip()
    if not text:
        print(p.name,0,0)
        continue
    lines=text.splitlines()
    total_lines=len(lines)
    pos=0
    for L in lines:
        toks=L.split()
        if len(toks)>1:
            pos += len(toks)-1
    print(p.name, total_lines, pos)
