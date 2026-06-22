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

def extract_bibliography_entries(text):
    """Extract bibliography entries with their content"""
    # Look for bibliography section
    biblio_patterns = [
        r'(?:Bibliography|References|Références)[\s\S]*?(?=\n\n[A-Z]|\Z)',
        r'(?:Bibliography|References|Références)[\s\S]*$'
    ]
    
    biblio_text = None
    for pattern in biblio_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            biblio_text = match.group(0)
            break
    
    if not biblio_text:
        return []
    
    # Parse numbered entries - try multiple patterns
    entry_patterns = [
        r'\[(\d+)\]\s+([^\[]+?)(?=\n\s*\[\d+\]|\Z)',
        r'\[(\d+)\]\s+([^\n]+(?:\n[^\n]+)*?)(?=\n\s*\[\d+\]|\Z)',
    ]
    
    entries = []
    for pattern in entry_patterns:
        entries = re.findall(pattern, biblio_text, re.DOTALL)
        if entries:
            break
    
    biblio_entries = []
    for num, content in entries:
        content = content.strip()
        # Remove page numbers and artifacts
        content = re.sub(r'\d+\s*$', '', content)
        content = re.sub(r'HealthOpt.*?Bibliography.*?\d+', '', content, flags=re.DOTALL)
        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content)
        biblio_entries.append((num, content))
    
    return biblio_entries

def find_first_mention_position(entry_content, full_text):
    """Find the first position where this entry is mentioned in the text"""
    # Extract first author surname (usually first word)
    author_match = re.match(r'([A-Z][a-z]+)', entry_content)
    if not author_match:
        return float('inf')
    
    author = author_match.group(1)
    
    # Try to find year
    year_match = re.search(r'\b(19|20)\d{2}\b', entry_content)
    year = year_match.group(0) if year_match else None
    
    # Search for author + year combination (most specific)
    if year:
        pattern = rf'{author}.*?{year}|{year}.*?{author}'
        matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
        if matches:
            return matches[0].start()
    
    # Search for author name alone
    pattern = rf'\b{author}\b'
    matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
    if matches:
        # Return the first match that's not in the bibliography section
        biblio_start = full_text.lower().find('bibliography')
        for match in matches:
            if biblio_start == -1 or match.start() < biblio_start:
                return match.start()
    
    return float('inf')  # Not found

def main():
    pdf_path = r"d:\23AIBox-DFinder\thesis__1___1_ (29).pdf"
    
    print("Extracting text from PDF...")
    full_text = extract_text_from_pdf(pdf_path)
    
    print("Extracting bibliography entries...")
    biblio_entries = extract_bibliography_entries(full_text)
    print(f"Found {len(biblio_entries)} bibliography entries")
    
    print("Finding first mention positions...")
    positions = []
    for num, content in biblio_entries:
        pos = find_first_mention_position(content, full_text)
        positions.append((pos, num, content))
        print(f"[{num}] Position: {pos if pos != float('inf') else 'NOT FOUND'}")
    
    # Sort by position
    positions.sort(key=lambda x: x[0])
    
    print("\nReordered bibliography:")
    for i, (pos, num, content) in enumerate(positions, 1):
        print(f"{i}. [{num}] {content[:80]}...")
    
    # Save reordered bibliography
    output_file = r"d:\23AIBox-DFinder\reordered_by_first_mention.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("REORDERED BIBLIOGRAPHY (by first mention in thesis)\n")
        f.write("=" * 60 + "\n\n")
        for i, (pos, num, content) in enumerate(positions, 1):
            f.write(f"[{num}] {content}\n\n")
    
    print(f"\nSaved to: {output_file}")

if __name__ == "__main__":
    main()
