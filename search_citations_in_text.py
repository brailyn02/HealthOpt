import re
import pypdf

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

pdf_path = r"d:\23AIBox-DFinder\thesis__1___1_ (30).pdf"
print("Extracting text from PDF...")
full_text = extract_text_from_pdf(pdf_path)

# Find bibliography section start
biblio_start = full_text.lower().find('bibliography')
if biblio_start == -1:
    biblio_start = len(full_text)

print(f"Bibliography starts at position: {biblio_start}")
print(f"Total text length: {len(full_text)}")

# Search for specific terms and their first mention
search_terms = [
    ('FooDrugs', r'\bfoofrugs\b'),
    ('DrugBank', r'\bdrugbank\b'),
    ('FooDB', r'\bfoodb\b'),
    ('POMELO', r'\bpomelo\b'),
    ('DFinder', r'\bdfinder\b'),
    ('LightGCN', r'\blightgcn\b'),
    ('RotatE', r'\brotate\b'),
    ('BPR', r'\bbpr\b'),
    ('RDKit', r'\brdkit\b'),
    ('NHANES', r'\bnhanes\b'),
    ('KNHANES', r'\bknhanes\b'),
    ('FoodData', r'\bfooddata\b'),
    ('ChEMBL', r'\bchembl\b'),
    ('PubChem', r'\bpubchem\b'),
    ('Lexicomp', r'\blexicomp\b'),
    ('Micromedex', r'\bmicromedex\b'),
    ('PharmGKB', r'\bpharmgkb\b'),
    ('Ministere', r'\bministere\b'),
    ('Guengerich', r'\bguengerich\b'),
    ('He', r'\bhe\b'),
    ('Sun', r'\bsun\b'),
    ('Rendle', r'\brendle\b'),
    ('Landrum', r'\blandrum\b'),
    ('Schwartz', r'\bschwartz\b'),
    ('Pennell', r'\bpennell\b'),
    ('Wishart', r'\bwishart\b'),
    ('Madera', r'\bmadera\b'),
    ('Soldin', r'\bsoldin\b'),
    ('Kashuba', r'\bkashuba\b'),
    ('Lee', r'\blee\b'),
    ('Husain', r'\bhusain\b'),
    ('Zdrazil', r'\bzdrazil\b'),
    ('Bisht', r'\bbisht\b'),
    ('Franconi', r'\bfranconi\b'),
    ('Kim', r'\bkim\b'),
    ('Thurnham', r'\bthurnham\b'),
    ('WHO', r'\bwho\b'),
    ('IOM', r'\biom\b'),
    ('ADA', r'\bada\b'),
    ('Chen', r'\bchen\b'),
    ('Luo', r'\bluo\b'),
    ('Crockett', r'\bcrockett\b'),
    ('Reimers', r'\breimers\b'),
    ('PubMed', r'\bpubmed\b'),
    ('Lacruz', r'\blacruz\b'),
    ('Rogers', r'\brogers\b'),
]

print("\nFirst mention positions:")
print("="*60)

positions = []
for name, pattern in search_terms:
    matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
    first_pos = None
    for match in matches:
        if match.start() < biblio_start:
            first_pos = match.start()
            break
    if first_pos:
        positions.append((first_pos, name))
        print(f"{name:15s}: Position {first_pos}")
    else:
        print(f"{name:15s}: NOT FOUND")

# Sort by position
positions.sort(key=lambda x: x[0])

print("\n" + "="*60)
print("Order by first mention:")
print("="*60)
for i, (pos, name) in enumerate(positions, 1):
    print(f"{i}. {name} (position {pos})")
