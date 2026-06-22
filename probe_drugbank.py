import xml.etree.ElementTree as ET

NS = 'http://www.drugbank.ca'
TARGETS = {'itraconazole', 'levofloxacin', 'ferrous sulfate', 'ketoconazole', 'atazanavir', 'iron'}

context = ET.iterparse('D:/23AIBox-DFinder/full database.xml', events=('end',))
found = 0

for event, elem in context:
    # Main drug entries have a 'type' attribute (small molecule / biotech)
    # Inner <drug> references inside <drug-interactions> do NOT
    is_main_drug = (elem.tag == f'{{{NS}}}drug' and 'type' in elem.attrib)

    if is_main_drug:
        name_el = elem.find(f'{{{NS}}}name')
        name = (name_el.text or '').strip() if name_el is not None else ''

        if name.lower() in TARGETS:
            print(f'\n=== {name} ===')

            # All direct child tag names
            tags = [c.tag.replace(f'{{{NS}}}', '') for c in elem]
            print(f'  children: {tags}')

            # food-interactions
            fi = elem.find(f'{{{NS}}}food-interactions')
            if fi is not None:
                items = list(fi)
                print(f'  food-interactions ({len(items)} items):')
                for c in items[:10]:
                    tag = c.tag.replace(f'{{{NS}}}', '')
                    print(f'    [{tag}] {c.text}')
            else:
                print('  food-interactions: NOT FOUND')

            # mechanism-of-action
            moa = elem.find(f'{{{NS}}}mechanism-of-action')
            if moa is not None:
                print(f'  moa (first 300): {(moa.text or "")[:300]}')

            # groups
            grps = elem.find(f'{{{NS}}}groups')
            if grps is not None:
                print(f'  groups: {[g.text for g in grps]}')

            found += 1

    # For the probe we skip elem.clear() — we break after 4 finds so
    # memory stays manageable. Production parser will handle this differently.
    # no early break — scan full file to find all targets

print(f'\nDone. Found {found} target drugs (of {len(TARGETS)} searched).')

