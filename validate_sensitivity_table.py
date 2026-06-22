import pandas as pd

df = pd.read_csv('D:/23AIBox-DFinder/data/drug_sensitivity_table.csv')
print(f"Total flagged drugs: {len(df)}")
print(f"\nFlag distribution:")
print(df[['cation_sensitive','vka','maoi','k_sparing','acid_dependent']].sum())

print("\n--- Cation-sensitive sample ---")
print(df[df['cation_sensitive']==1][['name','food_interaction_texts']].head(8).to_string())

print("\n--- VKA drugs ---")
print(df[df['vka']==1][['name','food_interaction_texts']].to_string())

print("\n--- MAOI drugs ---")
print(df[df['maoi']==1][['name','food_interaction_texts']].to_string())

print("\n--- K-sparing drugs ---")
print(df[df['k_sparing']==1][['name']].to_string())

print("\n--- Acid-dependent drugs ---")
print(df[df['acid_dependent']==1][['name','food_interaction_texts']].head(10).to_string())

# Check our key targets are present
targets = ['Warfarin','Ciprofloxacin','Tetracycline','Levothyroxine',
           'Phenelzine','Spironolactone','Itraconazole','Acenocoumarol']
print("\n--- Key drug lookup ---")
for t in targets:
    row = df[df['name'].str.lower() == t.lower()]
    if len(row):
        flags = row.iloc[0][['cation_sensitive','vka','maoi','k_sparing','acid_dependent']].to_dict()
        print(f"  {t}: {flags}")
    else:
        print(f"  {t}: NOT FOUND in flagged table")
