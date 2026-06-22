"""
check_plant_interactions.py
Searches interaction databases for medicinal plants and reports
all drug interactions found.
Sources searched:
  1. generated/drugbank_drug_food_named.csv   (DrugBank curated)
  2. dfi_interactions_from_keysentences.csv   (PubMed text-mined)
  3. foodrugs_interactions.csv               (text-mining corpus)
"""

import csv
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Plant definitions ─────────────────────────────────────────────────────────
# Each entry: (display_name, [search_keywords_lowercase])
PLANTS = [
    ("Medicago sativa (Alfalfa)",              ["alfalfa", "medicago sativa"]),
    ("Aloe vera",                              ["aloe vera", "aloe"]),
    ("Momordica charantia (Bitter Melon)",     ["bitter melon", "momordica"]),
    ("Berberis vulgaris (Barberry)",           ["barberry", "berberis"]),
    ("Citrus × aurantium (Bitter Orange)",     ["bitter orange", "citrus aurantium"]),
    ("Vaccinium (genus) (Blueberry/Bilberry)", ["blueberry", "bilberry", "vaccinium"]),
    ("Apium graveolens (Celery)",              ["celery", "apium graveolens"]),
    ("Matricaria chamomilla (Chamomile)",      ["chamomile", "matricaria"]),
    ("Capsicum frutescens (Hot Pepper)",       ["capsicum frutescens", "hot pepper"]),
    ("Syzygium aromaticum (Clove)",            ["clove", "syzygium"]),
    ("Sambucus nigra (Elderberry)",            ["elderberry", "sambucus"]),
    ("Trigonella foenum-graecum (Fenugreek)",  ["fenugreek", "trigonella"]),
    ("Morinda citrifolia (Noni)",              ["noni", "morinda"]),
    ("Rosmarinus officinalis (Rosemary)",      ["rosemary", "rosmarinus"]),
    ("Salvia officinalis (Sage)",              ["sage", "salvia officinalis"]),
    ("Thymus vulgaris (Thyme)",                ["thyme", "thymus vulgaris"]),
    ("Mentha x piperita (Peppermint)",         ["peppermint", "mentha"]),
    ("Linum usitatissimum (Flaxseed)",         ["flaxseed", "flax seed", "linseed", "linum"]),
    ("Carica papaya (Papaya)",                 ["papaya", "carica papaya"]),
    ("Allium sativum (Garlic)",                ["garlic", "allium sativum"]),
    ("Ginkgo biloba (Ginkgo)",                 ["ginkgo"]),
    ("Panax ginseng (Ginseng)",                ["panax ginseng", "ginseng"]),
    ("Panax quinquefolius (American Ginseng)", ["american ginseng", "panax quinquefolius"]),
    ("Psidium guajava (Guava)",                ["guava", "psidium"]),
    ("Glycyrrhiza glabra (Licorice Root)",     ["licorice", "glycyrrhiza"]),
    ("Nasturtium officinale (Watercress)",     ["watercress", "nasturtium officinale"]),
    ("Ferula assa-foetida (Asafoetida)",       ["asafoetida", "ferula"]),
    ("Angelica sinensis (Dong Quai)",          ["dong quai", "angelica sinensis"]),
    ("Zingiber officinale (Ginger)",           ["ginger", "zingiber"]),
    ("Crataegus monogyna (Hawthorn)",          ["hawthorn", "crataegus"]),
    ("Crataegus laevigata (Hawthorn)",         ["hawthorn", "crataegus"]),
    ("Taraxacum officinale (Dandelion)",       ["dandelion", "taraxacum"]),
    ("Vaccinium myrtillus (Bilberry)",         ["bilberry", "vaccinium myrtillus"]),
    ("Vaccinium macrocarpon (Cranberry)",      ["cranberry", "vaccinium macrocarpon"]),
    ("Vitis vinifera (Grape)",                 ["vitis vinifera", "grape seed", "grapeseed", "grape extract"]),
    ("Triticum aestivum (Wheatgrass)",         ["wheatgrass", "triticum"]),
    ("Capsicum annuum (Cayenne Pepper)",       ["cayenne", "capsicum annuum"]),
    ("Arctium lappa (Burdock)",                ["burdock", "arctium"]),
    ("Astragalus propinquus",                  ["astragalus"]),
    ("Curcuma longa (Turmeric)",               ["turmeric", "curcuma"]),
    ("Citrus limon (Lemon)",                   ["citrus limon"]),
    ("Nelumbo nucifera (Lotus)",               ["lotus", "nelumbo"]),
    ("Origanum vulgare (Oregano)",             ["oregano", "origanum"]),
    ("Euterpe oleracea (Acai)",                ["acai", "euterpe"]),
    ("Hibiscus sabdariffa",                    ["hibiscus"]),
    ("Althaea officinalis (Marshmallow)",      ["marshmallow", "althaea"]),
    ("Calendula officinalis (Marigold)",       ["marigold", "calendula"]),
    ("Ocimum tenuiflorum (Holy Basil)",        ["holy basil", "ocimum tenuiflorum"]),
    ("Satureja hortensis (Summer Savory)",     ["summer savory", "satureja"]),
    ("Amorphophallus konjac (Konjac)",         ["konjac", "amorphophallus"]),
    ("Silybum marianum (Milk Thistle)",        ["milk thistle", "silybum"]),
    ("Senegalia senegal (Gum Arabic)",         ["gum arabic", "senegalia"]),
    ("Trifolium pratense (Red Clover)",        ["red clover", "trifolium"]),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def match_plant(text, keywords):
    t = text.lower()
    return any(kw in t for kw in keywords)


def drugbank_interactions():
    """Returns dict: plant_display_name -> set of drug names"""
    path = os.path.join(BASE, "generated", "drugbank_drug_food_named.csv")
    results = defaultdict(set)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            food = row["food_name"]
            drug = row["drug_name"]
            for display, keywords in PLANTS:
                if match_plant(food, keywords):
                    results[display].add(drug)
    return results


def pubmed_interactions():
    """Returns dict: plant_display_name -> list of (drug, evidence_level, modality, sentence)"""
    path = os.path.join(BASE, "dfi_interactions_from_keysentences.csv")
    results = defaultdict(list)
    seen = defaultdict(set)  # deduplicate by (plant, drug, sentence)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            food = row.get("food", "")
            drug = row.get("drug", "")
            evidence = row.get("evidence_level", "")
            modality = row.get("modality", "")
            sentence = row.get("interaction_sentence", "")
            for display, keywords in PLANTS:
                if match_plant(food, keywords):
                    key = (drug.lower(), sentence[:80])
                    if key not in seen[display]:
                        seen[display].add(key)
                        results[display].append({
                            "drug": drug,
                            "food_raw": food,
                            "evidence": evidence,
                            "modality": modality,
                            "sentence": sentence,
                        })
    return results


def foodrug_interactions():
    """Returns dict: plant_display_name -> set of drug names (text-mined corpus)"""
    path = os.path.join(BASE, "foodrugs_interactions.csv")
    results = defaultdict(set)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            food = row.get("food", "")
            drug = row.get("drug", "")
            for display, keywords in PLANTS:
                if match_plant(food, keywords):
                    results[display].add(drug)
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading DrugBank interactions…")
    db_hits = drugbank_interactions()
    print("Loading PubMed key-sentence interactions…")
    pm_hits = pubmed_interactions()
    print("Loading text-mining corpus interactions…")
    tm_hits = foodrug_interactions()

    report_path = os.path.join(BASE, "medicinal_plants_interactions.txt")
    lines = []
    lines.append("=" * 78)
    lines.append("  MEDICINAL PLANT – DRUG INTERACTION REPORT")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Sources:")
    lines.append("  [DB] DrugBank curated food-drug pairs   (drugbank_drug_food_named.csv)")
    lines.append("  [PM] PubMed text-mined key sentences    (dfi_interactions_from_keysentences.csv)")
    lines.append("  [TM] Text-mining corpus                 (foodrugs_interactions.csv)")
    lines.append("")

    total_plants_with_hits = 0

    # Deduplicate plants by display name (Hawthorn appears twice)
    seen_display = set()
    unique_plants = []
    for display, keywords in PLANTS:
        if display not in seen_display:
            seen_display.add(display)
            unique_plants.append((display, keywords))

    for display, _ in unique_plants:
        db = sorted(db_hits.get(display, set()))
        pm = pm_hits.get(display, [])
        tm = sorted(tm_hits.get(display, set()))

        if not db and not pm and not tm:
            continue

        total_plants_with_hits += 1
        lines.append("─" * 78)
        lines.append(f"  PLANT: {display}")
        lines.append("─" * 78)

        if db:
            lines.append(f"\n  [DB] DrugBank — {len(db)} drug(s):")
            for d in db:
                lines.append(f"       • {d}")

        if pm:
            lines.append(f"\n  [PM] PubMed key-sentences — {len(pm)} interaction record(s):")
            for rec in pm:
                lines.append(f"       Drug      : {rec['drug']}")
                lines.append(f"       Food ref  : {rec['food_raw']}")
                lines.append(f"       Evidence  : {rec['evidence']}  |  Modality: {rec['modality']}")
                lines.append(f"       Sentence  : {rec['sentence'][:200]}")
                lines.append("")

        if tm:
            lines.append(f"\n  [TM] Text-mining corpus — {len(tm)} drug(s):")
            for d in tm:
                lines.append(f"       • {d}")

        lines.append("")

    lines.append("=" * 78)
    lines.append(f"  SUMMARY: {total_plants_with_hits} / {len(unique_plants)} plants had at least one matched interaction.")
    lines.append("=" * 78)

    report = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nDone. Report written to: {report_path}")
    print(f"Plants with interactions: {total_plants_with_hits} / {len(unique_plants)}")


if __name__ == "__main__":
    main()
