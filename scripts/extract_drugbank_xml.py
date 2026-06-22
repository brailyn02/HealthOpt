"""
Extract from DrugBank full database.xml:
  File 1: drugbank_food_pairs.csv   — one row per food-interaction sentence per drug
  File 2: drugbank_drug_smiles.csv  — SMILES for every drug (foods not in DrugBank)
  File 3: drugbank_dfi_enzymes.csv  — enzymes/targets for drugs that have food-interactions,
                                       with action types
Uses iterparse for memory-efficient processing of the 1.8 GB file.
"""
import xml.etree.ElementTree as ET
import csv
from pathlib import Path

XML_PATH = Path(r'd:/23AIBox-DFinder/full database.xml')
OUT_DIR   = Path(r'd:/23AIBox-DFinder/generated')
OUT_DIR.mkdir(exist_ok=True)

NS = 'http://www.drugbank.ca'

def tag(name):
    return f'{{{NS}}}{name}'

# Output files
f_pairs   = open(OUT_DIR / 'drugbank_food_pairs.csv',   'w', newline='', encoding='utf-8')
f_smiles  = open(OUT_DIR / 'drugbank_drug_smiles.csv',  'w', newline='', encoding='utf-8')
f_enzymes = open(OUT_DIR / 'drugbank_dfi_enzymes.csv',  'w', newline='', encoding='utf-8')

w_pairs   = csv.writer(f_pairs)
w_smiles  = csv.writer(f_smiles)
w_enzymes = csv.writer(f_enzymes)

w_pairs.writerow(['drugbank_id','drug_name','food_interaction_text'])
w_smiles.writerow(['drugbank_id','drug_name','drug_type','smiles'])
w_enzymes.writerow(['drugbank_id','drug_name','food_interaction_text',
                    'protein_type','protein_name','gene_name','actions'])

def extract_text(el, subtag):
    child = el.find(tag(subtag))
    return child.text.strip() if child is not None and child.text else ''

def extract_actions(el):
    """Get comma-joined actions list from an enzyme/target/carrier/transporter element."""
    actions_el = el.find(tag('actions'))
    if actions_el is None:
        return ''
    actions = [a.text.strip() for a in actions_el.findall(tag('action')) if a.text]
    return ', '.join(actions)

def extract_polypeptide_info(el):
    """Return (protein_name, gene_name) from polypeptide child."""
    poly = el.find(tag('polypeptide'))
    if poly is None:
        return '', ''
    pname = extract_text(poly, 'name')
    gname = extract_text(poly, 'gene-name')
    return pname, gname

drug_count   = 0
fi_count     = 0
smiles_count = 0
enzyme_count = 0

print("Parsing... (1.8 GB — this will take a few minutes)")

context = ET.iterparse(str(XML_PATH), events=('end',))

for event, elem in context:
    if elem.tag != tag('drug'):
        continue
    # Skip nested <drug> tags inside drug-interactions
    # Primary drugs are direct children of <drugbank> root
    # Check for primary drugbank-id
    db_ids = elem.findall(tag('drugbank-id'))
    primary_id = ''
    for id_el in db_ids:
        if id_el.get('primary') == 'true':
            primary_id = id_el.text.strip() if id_el.text else ''
            break
    if not primary_id or not primary_id.startswith('DB'):
        elem.clear()
        continue

    drug_type = elem.get('type', '')
    drug_name_el = elem.find(tag('name'))
    drug_name = drug_name_el.text.strip() if drug_name_el is not None and drug_name_el.text else ''

    drug_count += 1
    if drug_count % 1000 == 0:
        print(f"  Processed {drug_count} drugs | food-pairs: {fi_count} | smiles: {smiles_count}")

    # ── File 1 + 3: food-interactions ─────────────────────────────────────────
    food_texts = []
    fi_el = elem.find(tag('food-interactions'))
    if fi_el is not None:
        for fi in fi_el.findall(tag('food-interaction')):
            text = fi.text.strip() if fi.text else ''
            if text:
                food_texts.append(text)
                w_pairs.writerow([primary_id, drug_name, text])
                fi_count += 1

    # ── File 2: SMILES ─────────────────────────────────────────────────────────
    smiles_val = ''
    calc_el = elem.find(tag('calculated-properties'))
    if calc_el is not None:
        for prop in calc_el.findall(tag('property')):
            kind_el = prop.find(tag('kind'))
            if kind_el is not None and kind_el.text == 'SMILES':
                val_el = prop.find(tag('value'))
                if val_el is not None and val_el.text:
                    smiles_val = val_el.text.strip()
                    break
    # Also try experimental-properties if no calculated
    if not smiles_val:
        exp_el = elem.find(tag('experimental-properties'))
        if exp_el is not None:
            for prop in exp_el.findall(tag('property')):
                kind_el = prop.find(tag('kind'))
                if kind_el is not None and kind_el.text == 'SMILES':
                    val_el = prop.find(tag('value'))
                    if val_el is not None and val_el.text:
                        smiles_val = val_el.text.strip()
                        break
    w_smiles.writerow([primary_id, drug_name, drug_type, smiles_val])
    if smiles_val:
        smiles_count += 1

    # ── File 3: enzymes/targets for drugs that have food-interactions ──────────
    if food_texts:
        for food_text in food_texts:
            # Enzymes
            enzymes_el = elem.find(tag('enzymes'))
            if enzymes_el is not None:
                for enz in enzymes_el.findall(tag('enzyme')):
                    pname, gname = extract_polypeptide_info(enz)
                    actions = extract_actions(enz)
                    if pname or gname:
                        w_enzymes.writerow([primary_id, drug_name, food_text,
                                            'enzyme', pname, gname, actions])
                        enzyme_count += 1
            # Targets
            targets_el = elem.find(tag('targets'))
            if targets_el is not None:
                for tgt in targets_el.findall(tag('target')):
                    pname, gname = extract_polypeptide_info(tgt)
                    actions = extract_actions(tgt)
                    if pname or gname:
                        w_enzymes.writerow([primary_id, drug_name, food_text,
                                            'target', pname, gname, actions])
                        enzyme_count += 1
            # Transporters
            trans_el = elem.find(tag('transporters'))
            if trans_el is not None:
                for tr in trans_el.findall(tag('transporter')):
                    pname, gname = extract_polypeptide_info(tr)
                    actions = extract_actions(tr)
                    if pname or gname:
                        w_enzymes.writerow([primary_id, drug_name, food_text,
                                            'transporter', pname, gname, actions])
                        enzyme_count += 1
            # Carriers
            carriers_el = elem.find(tag('carriers'))
            if carriers_el is not None:
                for ca in carriers_el.findall(tag('carrier')):
                    pname, gname = extract_polypeptide_info(ca)
                    actions = extract_actions(ca)
                    if pname or gname:
                        w_enzymes.writerow([primary_id, drug_name, food_text,
                                            'carrier', pname, gname, actions])
                        enzyme_count += 1

    elem.clear()

f_pairs.close()
f_smiles.close()
f_enzymes.close()

print(f"\n=== Done ===")
print(f"Total drugs processed      : {drug_count}")
print(f"Food interaction sentences : {fi_count}  → drugbank_food_pairs.csv")
print(f"Drugs with SMILES          : {smiles_count}  → drugbank_drug_smiles.csv")
print(f"Enzyme/target rows (DFI)   : {enzyme_count}  → drugbank_dfi_enzymes.csv")
print(f"\nOutput folder: {OUT_DIR}")
