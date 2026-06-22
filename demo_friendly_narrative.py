#!/usr/bin/env python3
"""
Demo: LLM-Generated Friendly Narratives for Drug-Food Interactions

This script shows how the Phase 7 LLM (Qwen3-235B via OpenRouter) generates
warm, actionable explanations from technical interaction data.
"""

from llm_decompose import llm_friendly_narrative, llm_decompose

def demo():
    print("=" * 80)
    print("DEMO: LLM-Generated Friendly Narratives")
    print("=" * 80)
    
    # Example 1: Iron × Pizza (Chelation Risk)
    print("\n📋 EXAMPLE 1: Ferrous Sulfate × Pizza")
    print("-" * 80)
    
    drug = "Ferrous Sulfate (Iron)"
    food = "Pizza"
    mechanism = "Chelation of ferrous iron by calcium and fiber in pizza crust"
    risk_level = "HIGH"
    metaphor = "Mineral Magnet"
    bioactives = llm_decompose(food, verbose=False)
    
    print(f"Drug: {drug}")
    print(f"Food: {food}")
    print(f"Mechanism: {mechanism}")
    print(f"Risk Level: {risk_level}")
    print(f"Metaphor: {metaphor}")
    print(f"Bioactives: {bioactives[:5]}..." if len(bioactives) > 5 else f"Bioactives: {bioactives}")
    
    print("\n🤖 LLM Generating Friendly Narrative...")
    narrative = llm_friendly_narrative(
        drug_name=drug,
        food_name=food,
        mechanism=mechanism,
        risk_level=risk_level,
        metaphor=metaphor,
        bioactives=bioactives,
        verbose=False
    )
    
    print("\n✅ FRIENDLY NARRATIVE OUTPUT:")
    print(f"\n❓ What is happening?")
    print(f"   {narrative.get('what_is_happening', 'N/A')}")
    
    print(f"\n💙 Why it matters for you:")
    print(f"   {narrative.get('why_it_matters', 'N/A')}")
    
    print(f"\n✅ How to fix it:")
    for tip in narrative.get('how_to_fix_it', []):
        print(f"   • {tip}")
    
    print(f"\n⏰ When to act:")
    print(f"   {narrative.get('when_to_act', 'N/A')}")
    
    # Example 2: Grapefruit × Statin (CYP3A4 Inhibition)
    print("\n" + "=" * 80)
    print("\n📋 EXAMPLE 2: Simvastatin × Grapefruit Juice")
    print("-" * 80)
    
    drug2 = "Simvastatin"
    food2 = "Grapefruit Juice"
    mechanism2 = "CYP3A4 inhibition by naringenin and bergamottin"
    risk_level2 = "HIGH"
    metaphor2 = "Liver Traffic Jam"
    bioactives2 = llm_decompose(food2, verbose=False)
    
    print(f"Drug: {drug2}")
    print(f"Food: {food2}")
    print(f"Mechanism: {mechanism2}")
    print(f"Risk Level: {risk_level2}")
    print(f"Metaphor: {metaphor2}")
    print(f"Bioactives: {bioactives2[:5]}..." if len(bioactives2) > 5 else f"Bioactives: {bioactives2}")
    
    print("\n🤖 LLM Generating Friendly Narrative...")
    narrative2 = llm_friendly_narrative(
        drug_name=drug2,
        food_name=food2,
        mechanism=mechanism2,
        risk_level=risk_level2,
        metaphor=metaphor2,
        bioactives=bioactives2,
        verbose=False
    )
    
    print("\n✅ FRIENDLY NARRATIVE OUTPUT:")
    print(f"\n❓ What is happening?")
    print(f"   {narrative2.get('what_is_happening', 'N/A')}")
    
    print(f"\n💙 Why it matters for you:")
    print(f"   {narrative2.get('why_it_matters', 'N/A')}")
    
    print(f"\n✅ How to fix it:")
    for tip in narrative2.get('how_to_fix_it', []):
        print(f"   • {tip}")
    
    print(f"\n⏰ When to act:")
    print(f"   {narrative2.get('when_to_act', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("✅ Demo complete. See how LLM makes technical output friendly!\n")


if __name__ == "__main__":
    try:
        demo()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
