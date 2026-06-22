import requests, time

compounds = [
    ('Benzo[a]pyrene', 9153),
    ('Sucrose', 5988),
    ('Uric Acid', 1175),
    ('6-Gingerol', 442793),
    ('Apigenin', 5280443),
    ('Carvone', 16724),
    ('EPA', 446284),
    ('Linoleic Acid', 5280450),
    ('Alpha-Linolenic Acid', 5280934),
    ('Quercetin', 5280343),
    ('Allicin', 65036),
    ('Sesamin', 72307),
    ('Lycopene', 446925),
    ('Beta-Carotene', 5280489),
    ('Naringenin', 932),
    ('Maltose', 6255),
    ('Tripalmitin', 68441),
    ('Acrylamide', 6579),
]

for name, cid in compounds:
    r = requests.get(
        f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/SMILES,MolecularFormula/JSON',
        timeout=10
    )
    if r.status_code == 200:
        p = r.json()['PropertyTable']['Properties'][0]
        smi = p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES", "N/A")
        mf  = p.get("MolecularFormula", "?")
        print(f'{name} (CID {cid}): {smi} [{mf}]')
    else:
        print(f'{name}: ERROR {r.status_code}')
    time.sleep(0.3)
