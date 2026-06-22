import re
import pypdf
from collections import OrderedDict

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with open(pdf_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def find_citations(text):
    """Find all citations in the text and their order of appearance"""
    # Common citation patterns: [1], [1,2], (Smith, 2020), etc.
    # Assuming numeric citations like [1], [2], etc.
    citation_pattern = r'\[(\d+)\]'
    citations = re.findall(citation_pattern, text)
    
    # Get unique citations in order of appearance
    seen = set()
    ordered_citations = []
    for citation in citations:
        if citation not in seen:
            seen.add(citation)
            ordered_citations.append(citation)
    
    return ordered_citations

def extract_bibliography(text):
    """Extract the bibliography section from the text"""
    # Look for bibliography/references section
    biblio_patterns = [
        r'(?:Bibliography|References|Références)[\s\S]*?(?=\n\n[A-Z]|\Z)',
        r'(?:Bibliography|References|Références)[\s\S]*$'
    ]
    
    for pattern in biblio_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    return None

def parse_bibliography_entries(biblio_text):
    """Parse individual bibliography entries"""
    # Pattern to match numbered entries like [1], [2], etc.
    entry_pattern = r'\[(\d+)\]\s+([^\[]+)'
    entries = re.findall(entry_pattern, biblio_text)
    
    biblio_dict = {}
    for num, content in entries:
        biblio_dict[num] = content.strip()
    
    return biblio_dict

def main():
    pdf_path = r"d:\23AIBox-DFinder\thesis__1___1_ (29).pdf"
    
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    
    print("Finding citations in order of appearance...")
    citations = find_citations(text)
    print(f"Found {len(citations)} unique citations: {citations[:20]}...")
    
    print("Extracting bibliography section...")
    biblio_text = extract_bibliography(text)
    if biblio_text:
        print(f"Bibliography section found (length: {len(biblio_text)})")
        
        print("Parsing bibliography entries...")
        biblio_entries = parse_bibliography_entries(biblio_text)
        print(f"Found {len(biblio_entries)} bibliography entries")
        
        # Save reordered bibliography
        print("\nReordering bibliography by citation order...")
        reordered_biblio = []
        for citation in citations:
            if citation in biblio_entries:
                reordered_biblio.append(f"[{citation}] {biblio_entries[citation]}")
            else:
                print(f"Warning: Citation [{citation}] not found in bibliography")
        
        # Save to file
        output_file = r"d:\23AIBox-DFinder\reordered_bibliography.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("REORDERED BIBLIOGRAPHY (by order of appearance)\n")
            f.write("=" * 60 + "\n\n")
            for i, entry in enumerate(reordered_biblio, 1):
                f.write(f"{entry}\n\n")
        
        print(f"\nReordered bibliography saved to: {output_file}")
        print(f"Total entries: {len(reordered_biblio)}")
    else:
        print("Bibliography section not found!")

if __name__ == "__main__":
    main()
