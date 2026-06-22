import sys
sys.path.insert(0, 'D:/23AIBox-DFinder')
from llm_decompose import llm_decompose

for food in ["Pizza", "Spinach", "Dairy Milk", "Dates"]:
    result = llm_decompose(food)
    print(f"{food:20s} -> {result}")
