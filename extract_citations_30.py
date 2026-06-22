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

def find_citations(text):
    """Find all citations in the text and their order of appearance"""
    # Common citation patterns: [1], [1,2], etc.
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

pdf_path = r"d:\23AIBox-DFinder\thesis__1___1_ (30).pdf"

print("Extracting text from PDF...")
text = extract_text_from_pdf(pdf_path)

print("Finding citations in order of appearance...")
citations = find_citations(text)
print(f"Found {len(citations)} unique citations:")
print(citations)

# Save citation order
with open(r"d:\23AIBox-DFinder\citation_order_30.txt", 'w', encoding='utf-8') as f:
    for citation in citations:
        f.write(f"{citation}\n")

print(f"\nSaved citation order to: citation_order_30.txt")
