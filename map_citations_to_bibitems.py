import re

# Citation order from the thesis (from first script)
citation_order = ['1', '8', '9', '10', '11', '12', '13', '18', '20', '21', '22', '28', '29', '30', '31', '15', '2', '37', '38', '3', '16', '19', '39', '33', '34', '35', '36', '4', '26', '5', '6', '7', '14', '17', '23', '24', '25', '27', '32']

# Read the bibliography entries from the text file
with open(r"d:\23AIBox-DFinder\reordered_bibliography.txt", 'r', encoding='utf-8') as f:
    biblio_text = f.read()

# Parse bibliography entries
entry_pattern = r'\[(\d+)\]\s+([^\[]+?)(?=\n\s*\[\d+\]|\Z)'
entries = re.findall(entry_pattern, biblio_text, re.DOTALL)

biblio_dict = {}
for num, content in entries:
    content = content.strip()
    # Clean up
    content = re.sub(r'\d+\s*$', '', content)
    content = re.sub(r'HealthOpt.*?Bibliography.*?\d+', '', content, flags=re.DOTALL)
    content = re.sub(r'\s+', ' ', content)
    biblio_dict[num] = content

print(f"Found {len(biblio_dict)} bibliography entries")

# Read the LaTeX bibliography
with open(r"d:\23AIBox-DFinder\original_bibliography_latex.tex", 'r', encoding='utf-8') as f:
    latex_text = f.read()

# Parse LaTeX bibitems - split by bibitem
latex_entries = []
parts = re.split(r'\\bibitem\{', latex_text)
for part in parts[1:]:  # Skip first empty part
    match = re.match(r'([^}]+)\}(.+)', part, re.DOTALL)
    if match:
        key = match.group(1)
        content = match.group(2).strip()
        # Remove trailing \end{thebibliography} if present
        content = re.sub(r'\\end\{thebibliography\}.*$', '', content, flags=re.DOTALL)
        latex_entries.append((key, content))

latex_dict = {}
for key, content in latex_entries:
    content = content.strip()
    # Clean up for comparison
    content_clean = re.sub(r'\s+', ' ', content)
    content_clean = re.sub(r'[~\-\{\}\$\\]', ' ', content_clean)
    content_clean = re.sub(r'\s+', ' ', content_clean)
    latex_dict[key] = {'original': content, 'clean': content_clean}

print(f"Found {len(latex_dict)} LaTeX bibitems")

# Map citation numbers to bibitem keys by content matching
citation_to_bibitem = {}

for citation_num in citation_order:
    if citation_num not in biblio_dict:
        print(f"Warning: Citation [{citation_num}] not in bibliography")
        continue
    
    biblio_content = biblio_dict[citation_num]
    # Clean for comparison
    biblio_clean = re.sub(r'\s+', ' ', biblio_content)
    biblio_clean = re.sub(r'[–—\-]', ' ', biblio_clean)
    biblio_clean = re.sub(r'\s+', ' ', biblio_clean)
    
    # Try to find matching LaTeX entry
    best_match = None
    best_score = 0
    
    for key, data in latex_dict.items():
        latex_clean = data['clean']
        
        # Simple matching: check if first author name matches
        biblio_author = biblio_clean.split()[0] if biblio_clean.split() else ''
        latex_author = latex_clean.split()[0] if latex_clean.split() else ''
        
        # Handle special cases
        if 'Bisht' in biblio_clean and 'Bisht' in latex_clean:
            best_match = key
            break
        if 'Agriculture' in biblio_clean and 'Agriculture' in latex_clean:
            best_match = key
            break
        
        if biblio_author.lower() == latex_author.lower():
            # Check year
            biblio_year = re.search(r'\b(19|20)\d{2}\b', biblio_clean)
            latex_year = re.search(r'\b(19|20)\d{2}\b', latex_clean)
            
            if biblio_year and latex_year:
                if biblio_year.group(0) == latex_year.group(0):
                    best_match = key
                    break
            else:
                best_match = key
                break
    
    if best_match:
        citation_to_bibitem[citation_num] = best_match
        print(f"[{citation_num}] -> {best_match}")
    else:
        print(f"Warning: No match found for citation [{citation_num}]")
        print(f"  Biblio content: {biblio_content[:100]}...")

# Now reorder the LaTeX bibliography
print("\n" + "="*60)
print("REORDERED LATEX BIBLIOGRAPHY")
print("="*60)

output = "\\begin{thebibliography}{99}\n"
output += "\\addcontentsline{toc}{chapter}{Bibliography}\n\n"

seen_keys = set()
for citation_num in citation_order:
    if citation_num in citation_to_bibitem:
        key = citation_to_bibitem[citation_num]
        if key not in seen_keys:
            output += f"\\bibitem{{{key}}}\n"
            output += latex_dict[key]['original'] + "\n\n"
            seen_keys.add(key)
        else:
            print(f"Skipping duplicate: [{citation_num}] -> {key}")
    else:
        print(f"Skipping citation [{citation_num}] - no match")

output += "\\end{thebibliography}"

# Save
with open(r"d:\23AIBox-DFinder\reordered_bibliography_latex.tex", 'w', encoding='utf-8') as f:
    f.write(output)

print(f"\nSaved reordered LaTeX bibliography to: reordered_bibliography_latex.tex")
