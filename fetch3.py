import requests, time
cids = [('Sucrose', 5988), ('Maltose', 6255), ('6-Gingerol', 442793)]
for name, cid in cids:
    r = requests.get(f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/IsomericSMILES,IUPACName/JSON', timeout=15)
    p = r.json()['PropertyTable']['Properties'][0]
    smi = p['IsomericSMILES']
    iupac = p['IUPACName']
    print(f'{name} CID={cid}')
    print(f'  SMILES: {smi}')
    print(f'  IUPAC:  {iupac}')
    print()
    time.sleep(0.4)
