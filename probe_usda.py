import pandas as pd

base = 'D:/23AIBox-DFinder/FoodData_Central_foundation_food_csv_2025-04-24'

# 1. Check nutrient table
n = pd.read_csv(f'{base}/nutrient.csv')
print("nutrient.csv columns:", n.columns.tolist())
print(f"Total nutrients: {len(n)}\n")

targets = ['calcium', 'vitamin k', 'iron', 'potassium', 'magnesium',
           'zinc', 'tyramine', 'phylloquinone', 'menaquinone']
mask = n['name'].str.lower().str.contains('|'.join(targets), na=False)
print("Target nutrients found:")
print(n[mask][['id','name','unit_name']].to_string())

# 2. Check food.csv structure
print("\n\nfood.csv columns:")
f = pd.read_csv(f'{base}/food.csv', nrows=5)
print(f.columns.tolist())
print(f.head(3).to_string())

# 3. Check food_nutrient.csv structure
print("\n\nfood_nutrient.csv columns:")
fn = pd.read_csv(f'{base}/food_nutrient.csv', nrows=5)
print(fn.columns.tolist())
print(fn.head(3).to_string())

# 4. How many unique foods?
foods_full = pd.read_csv(f'{base}/food.csv')
print(f"\nTotal foods in food.csv: {len(foods_full)}")
print("Sample food names:", foods_full['description'].head(10).tolist())
