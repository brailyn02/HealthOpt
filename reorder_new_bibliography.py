import re

# Citation order from the thesis (from previous extraction)
citation_order = ['1', '8', '9', '10', '11', '12', '13', '18', '20', '21', '22', '28', '29', '30', '31', '15', '2', '37', '38', '3', '16', '19', '39', '33', '34', '35', '36', '4', '26', '5', '6', '7', '14', '17', '23', '24', '25', '27', '32']

# Read the bibliography entries from the text file (original PDF extraction)
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

print(f"Found {len(biblio_dict)} bibliography entries from PDF")

# New bibliography provided by user
new_bibliography = r"""\begin{thebibliography}{99}
\addcontentsline{toc}{chapter}{Bibliography}

\bibitem{MinisterePharmaceutique}
Ministère de l'Industrie Pharmaceutique, Algérie,
``Nomenclature Nationale des Produits Pharmaceutiques,''
[Online]. Available: \url{https://www.miph.gov.dz/}

\bibitem{Guengerich1999}
F. P. Guengerich,
``Cytochrome P450 3A4: Regulation and Role in Drug Metabolism,''
\textit{Annual Review of Pharmacology and Toxicology}, vol.~39, pp.~1--17, 1999.
[Online]. Available: \url{https://doi.org/10.1146/annurev.pharmtox.39.1.1}

\bibitem{He2020}
X. He, K. Deng, X. Wang, Y. Li, Y. Zhang, and M. Wang,
``LightGCN: Simplifying and Powering Graph Convolution Network for Recommendation,''
in \textit{Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR '20)},
New York, NY, USA: ACM, 2020, pp.~639--648.
[Online]. Available: \url{https://doi.org/10.1145/3397271.3401063}

\bibitem{sun2019rotate}
Z. Sun, Z.-H. Deng, J.-Y. Nie, and J. Tang,
``RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space,''
in \textit{7th International Conference on Learning Representations (ICLR 2019)},
OpenReview.net, 2019.
[Online]. Available: \url{https://arxiv.org/abs/1902.10197}

\bibitem{Rendle2009}
S. Rendle, C. Freudenthaler, Z. Gantner, and L. Schmidt-Thieme,
``BPR: Bayesian Personalized Ranking from Implicit Feedback,''
in \textit{Proceedings of the Twenty-Fifth Conference on Uncertainty in Artificial Intelligence (UAI '09)},
AUAI Press, 2009, pp.~452--461.
[Online]. Available: \url{https://arxiv.org/abs/1205.2618}

\bibitem{RDKit}
G. Landrum et al.,
``RDKit: Open-source cheminformatics,''
[Online]. Available: \url{https://www.rdkit.org/}

\bibitem{Schwartz2003}
J. B. Schwartz,
``The influence of sex on pharmacokinetics,''
\textit{Clinical Pharmacokinetics}, vol.~42, no.~2, pp.~107--121, 2003.
[Online]. Available: \url{https://doi.org/10.2165/00003088-200342020-00001}

\bibitem{Pennell2004}
P.~B. Pennell \textit{et al.},
``The impact of pregnancy and childbirth on the metabolism of lamotrigine,''
\textit{Neurology}, vol.~62, no.~2, pp.~292--295, 2004.
[Online]. Available: \url{https://doi.org/10.1212/01.wnl.0000103286.47129.f8}

\bibitem{Wishart2018db}
D. S. Wishart et al.,
``DrugBank 5.0: a major update to the DrugBank database for 2018,''
\textit{Nucleic Acids Research}, vol.~46, no.~D1, pp.~D1074--D1082, 2018.
[Online]. Available: \url{https://go.drugbank.com/}

\bibitem{Madera2022}
N. Madera-Salcedo et al.,
``POMELO: A Comprehensive Database and Search Engine for Plant Metabolites and Their Interactions with Drugs,''
\textit{J. Chemical Information and Modeling}, vol.~62, 2022.

\bibitem{Wishart2018foodb}
D. S. Wishart et al.,
``FooDB: The Food Database,''
\textit{Nucleic Acids Research}, 2018.
[Online]. Available: \url{https://foodb.ca/}

\bibitem{Lexicomp2026}
Lexicomp,
``Lexi-Drugs Online Database,''
UpToDate Lexidrug, Wolters Kluwer Health, Inc., Riverwoods, IL, 2026.
[Online]. Available: \url{https://online.lexi.com}

\bibitem{Micromedex2026}
IBM Micromedex,
``Micromedex DrugRef Database,''
Truven Health Analytics, IBM Watson Health, Greenwood Village, CO, 2026.
[Online]. Available: \url{https://www.micromedexsolutions.com}

\bibitem{DrugsDotCom2026}
Drugs.com,
``Drugs.com Drug Information Database,''
Drug Site Trust, Auckland, New Zealand, 2026.
[Online]. Available: \url{https://www.drugs.com}

\bibitem{Soldin2009}
O. P. Soldin and D. R. Mattison,
``Sex differences in pharmacokinetics and pharmacodynamics,''
\textit{Clinical Pharmacokinetics}, vol.~48, no.~3, pp.~143--157, 2009.
[Online]. Available: \url{https://doi.org/10.2165/00003088-200948030-00001}

\bibitem{Kashuba1998}
A. D. M. Kashuba and A. N. Nafziger,
``Physiological changes during the menstrual cycle and their effects on the pharmacokinetics and pharmacodynamics of drugs,''
\textit{Clinical Pharmacokinetics}, vol.~34, no.~3, pp.~203--218, Mar. 1998.
[Online]. Available: \url{https://doi.org/10.2165/00003088-199834030-00003}

\bibitem{Lee2023}
H. Lee et al.,
``Construction of a corpus for drug–food interaction extraction from biomedical literature,''
\textit{Database}, vol. 2023, baad075, 2023.
[Online]. Available: \url{https://github.com/ccadd-snu/corpus-for-DFI-extraction/}

\bibitem{Husain2023}
S. Husain,
``Drug-Food Interactions Dataset,''
Kaggle, 2023.
[Online]. Available: \url{https://www.kaggle.com/datasets/shayanhusain/drug-food-interactions-dataset}

\bibitem{chembl2023}
B.~Zdrazil, E.~Felix, F.~Hunter, et al.,
``The ChEMBL Database in 2023: a drug discovery platform spanning multiple bioactivity data types and time periods,''
\textit{Nucleic Acids Research}, vol.~51, no.~D1, pp.~D1180--D1192, 2023.
[Online]. Available: \url{https://doi.org/10.1093/nar/gkac1047}

\bibitem{Bisht2024}
N. Bisht,
``Menstrual Cycle Data (FedCycleData),''
Kaggle, 2024.
[Online]. Available: \url{https://www.kaggle.com/datasets/nikitabisht/menstrual-cycle-data}

\bibitem{Franconi2014}
F. Franconi and I. Campesi,
``Pharmacogenomics, pharmacokinetics and pharmacodynamics: interaction with biological differences between men and women,''
\textit{British Journal of Pharmacology}, vol.~171, no.~3, pp.~580--594, Feb. 2014.
[Online]. Available: \url{https://doi.org/10.1111/bph.12362}

\bibitem{Kim2023}
S. Kim, J. Chen, T. Cheng, et al.,
``PubChem 2023 update,''
\textit{Nucleic Acids Research}, vol.~51, no.~D1, pp.~D1373--D1380, 2023.
[Online]. Available: \url{https://pubchem.ncbi.nlm.nih.gov}

\bibitem{Thurnham2010}
D. I. Thurnham, L. D. McCabe, S. Haldar, F. T. Wieringa, C. A. Northrop-Clewes, and G. P. McCabe,
``Adjusting plasma ferritin concentrations to remove the effects of subclinical inflammation in the assessment of iron deficiency,''
\textit{The American Journal of Clinical Nutrition}, vol.~92, no.~3, pp.~546--555, 2010.
[Online]. Available: \url{https://doi.org/10.3945/ajcn.2010.29284}

\bibitem{WHO2011}
World Health Organization,
``Serum ferritin concentrations for the assessment of iron status and iron deficiency in populations,''
Geneva: World Health Organization, 2011.
[Online]. Available: \url{https://apps.who.int/iris/handle/10665/85843}

\bibitem{IOM2011}
Institute of Medicine (US) Committee to Review Dietary Reference Intakes for Vitamin D and Calcium,
``Dietary Reference Intakes for Calcium and Vitamin D,''
A. C. Ross, C. L. Taylor, A. L. Yaktine, and H. B. Del Valle, Eds.
Washington, DC: National Academies Press, 2011.
[Online]. Available: \url{https://doi.org/10.17226/13050}

\bibitem{ADA2023}
American Diabetes Association Professional Practice Committee,
``Standards of Care in Diabetes---2023,''
\textit{Diabetes Care}, vol.~46, no.~Supp.~1, pp.~S1--S291, 2023.
[Online]. Available: \url{https://doi.org/10.2337/dc23-S001}

\bibitem{Chen2006}
Y.-C. Chen et al.,
``Poor correlation between 6$\beta$-hydroxycortisol:cortisol molar ratios and midazolam clearance as measure of hepatic CYP3A activity,''
\textit{British Journal of Clinical Pharmacology}, vol.~62, no.~2, pp.~188--195, 2006.
[Online]. Available: \url{https://doi.org/10.1111/j.1365-2125.2006.02700.x}

\bibitem{Luo2023}
T. Luo, Z. Lu, J. Zhang, et al.,
``DFinder: A novel end-to-end graph-based deep learning method to identify drug-food interactions,''
\textit{Briefings in Bioinformatics}, vol.~24, no.~2, 2023.

\bibitem{NHANES}
National Center for Health Statistics,
``National Health and Nutrition Examination Survey (NHANES),''
CDC, 1999--2023.
[Online]. Available: \url{https://www.cdc.gov/nchs/nhanes/}

\bibitem{KNHANES}
Korea Centers for Disease Control and Prevention,
``Korea National Health and Nutrition Examination Survey (KNHANES),''
2007--2016.
[Online]. Available: \url{https://knhanes.kdca.go.kr/}

\bibitem{USDA}
U.S. Department of Agriculture,
``FoodData Central,''
Agricultural Research Service.
[Online]. Available: \url{https://fdc.nal.usda.gov/}

\bibitem{Crockett2020}
J. Crockett, D. Critchley, B. Tayo, and G. Morrison,
``A phase 1, randomized, pharmacokinetic trial of the effect of different meal compositions, whole milk, and alcohol on cannabidiol exposure and safety in healthy subjects,''
\textit{Epilepsia}, vol.~61, no.~2, pp.~269--277, Feb. 2020.
[Online]. Available: \url{https://doi.org/10.1111/epi.16419}

\bibitem{Reimers2005}
A. Reimers, G. Helde, and E. Brodtkorb,
``Ethinyl estradiol, not progestogens, reduces lamotrigine serum concentrations,''
\textit{Epilepsia}, vol.~46, no.~9, pp.~1414--1417, Sept. 2005.
[Online]. Available: \url{https://doi.org/10.1111/j.1528-1167.2005.10105.x}

\bibitem{PubMed}
National Library of Medicine (US),
``PubMed,''
National Center for Biotechnology Information.
[Online]. Available: \url{https://pubmed.ncbi.nlm.nih.gov/}

\bibitem{Lacruz2023}
B. Lacruz-Pleguezuelos et al.,
``FooDrugs: a comprehensive food--drug interactions database with text documents and transcriptional data,''
\textit{Database}, vol. 2023, baad075, 2023.
[Online]. Available: \url{https://imdeafoodcompubio.com/}

\bibitem{FooDrugsWeb}
IMDEA Food CompuBio,
``FooDrugs: a bioinformatic tool to research potential food--drug interactions,''
[Online]. Available: \url{https://imdeafoodcompubio.com/}

\bibitem{PharmGKB}
M. Whirl-Carrillo \textit{et al.},
``An evidence-based framework for evaluating pharmacogenomics knowledge for personalized medicine,''
\textit{Clinical Pharmacology \& Therapeutics}, vol.~110, no.~3, pp.~563--572, Sept. 2021.
[Online]. Available: \url{https://doi.org/10.1002/cpt.2350}
\bibitem{Rogers2010}
D.~Rogers and M.~Hahn,
``Extended-connectivity fingerprints,''
\textit{Journal of Chemical Information and Modeling}, vol.~50, no.~5, pp.~742--754, 2010.
[Online]. Available: \url{https://doi.org/10.1021/ci100050t}

\end{thebibliography}"""

# Parse new LaTeX bibitems
latex_entries = []
parts = re.split(r'\\bibitem\{', new_bibliography)
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

print(f"Found {len(latex_dict)} new LaTeX bibitems")

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
        if 'Kasarinaite' in biblio_clean:
            # No Kasarinaite in new bibliography, skip
            continue
        if 'Stricker' in biblio_clean:
            # No Stricker in new bibliography, skip
            continue
        if 'Franconi' in biblio_clean and 'Franconi' in latex_clean:
            best_match = key
            break
        if 'Kim' in biblio_clean and 'PubChem' in biblio_clean and 'Kim' in latex_clean:
            best_match = key
            break
        if 'Crockett' in biblio_clean and 'Crockett' in latex_clean:
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

# Add any remaining bibitems that weren't in the citation order
for key, data in latex_dict.items():
    if key not in seen_keys:
        print(f"Adding uncited entry: {key}")
        output += f"\\bibitem{{{key}}}\n"
        output += data['original'] + "\n\n"

output += "\\end{thebibliography}"

# Save
with open(r"d:\23AIBox-DFinder\reordered_bibliography_latex.tex", 'w', encoding='utf-8') as f:
    f.write(output)

print(f"\nSaved reordered LaTeX bibliography to: reordered_bibliography_latex.tex")
