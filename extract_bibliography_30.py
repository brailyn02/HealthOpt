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
text = extract_text_from_pdf(pdf_path)

# Find bibliography section - look for it at the end of the document
biblio_start = text.lower().rfind('bibliography')
if biblio_start != -1:
    biblio_text = text[biblio_start:]
    print(f"Found bibliography at position {biblio_start}")
else:
    biblio_text = None
    print("Bibliography section not found")

if biblio_text:
    # Try different patterns for bibliography entries
    entry_patterns = [
        r'\[(\d+)\]\s+([^\[]+?)(?=\n\s*\[\d+\]|\Z)',
        r'\[(\d+)\]\s+([^\n]+(?:\n[^\n]+)*?)(?=\n\s*\[\d+\]|\Z)',
        r'\[(\d+)\]\s+(.+?)(?=\n\s*\[\d+\]|\Z)',
    ]
    
    entries = []
    for pattern in entry_patterns:
        entries = re.findall(pattern, biblio_text, re.DOTALL)
        if entries:
            break
    
    print(f"Found {len(entries)} bibliography entries")
    
    # Save to file
    with open(r"d:\23AIBox-DFinder\bibliography_30.txt", 'w', encoding='utf-8') as f:
        for num, content in entries:
            content = content.strip()
            # Clean up
            content = re.sub(r'\d+\s*$', '', content)
            content = re.sub(r'\s+', ' ', content)
            f.write(f"[{num}] {content}\n\n")
    
    print("Saved to: bibliography_30.txt")
    
    # Also save raw biblio text for inspection
    with open(r"d:\23AIBox-DFinder\bibliography_30_raw.txt", 'w', encoding='utf-8') as f:
        f.write(biblio_text)
    print("Saved raw bibliography to: bibliography_30_raw.txt")
else:
    print("Bibliography section not found")
