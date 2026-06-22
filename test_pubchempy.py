import pubchempy as pcp

print("=" * 70)
print("TESTING PUBCHEMPY WITH YOUR FORMAT")
print("=" * 70)
print()

smiles_list = [
    "CCOC(=O)N[C@@H]1CC[C@@H]2[C@@H](C1)C[C@@H]3[C@H]([C@H]2/C=C/C4=NC=C(C=C4)C5=CC(=CC=C5)F)[C@H](OC3=O)C", # Drug 51
    "C1CN(P(=O)(OC1)NCCCl)CCCl" # Drug 487
]

for i, smiles in enumerate(smiles_list):
    print(f"[{i+1}] Testing SMILES: {smiles[:50]}...")
    try:
        compounds = pcp.get_compounds(smiles, namespace='smiles')
        print(f"    Found {len(compounds)} compound(s)")
        
        for j, compound in enumerate(compounds):
            print(f"    Compound {j+1}:")
            print(f"      CID: {compound.cid}")
            print(f"      Name: {compound.iupac_name if hasattr(compound, 'iupac_name') and compound.iupac_name else 'N/A'}")
            if compound.synonyms:
                print(f"      Synonym 1: {compound.synonyms[0]}")
            else:
                print(f"      Synonyms: None")
            print()
    except Exception as e:
        print(f"    Error: {e}")
    print()

print("=" * 70)
print("✓ TEST COMPLETE")
print("=" * 70)
