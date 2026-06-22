import pandas as pd

df = pd.read_csv("validation_splits/phase5_fusion_results.csv")

_LGN_HIGH_CONF_TH   = 0.90
_LGN_MEDIUM_CONF_TH = 0.65
_GRAPH_MAX = 30.0
_KGE_MAX   = 115.0
_MECH_HKG_W = 0.65
_MECH_KGE_W = 0.35
_TH_MEDIUM = 0.45
_TH_LOW    = 0.20
_LGN_STRONG_CONFIRM = 0.98

def _mech_support(g, k):
    ng = min(float(g or 0) / _GRAPH_MAX, 1.0)
    nk = min(float(k or 0) / _KGE_MAX,   1.0)
    return min(_MECH_HKG_W * ng + _MECH_KGE_W * nk, 1.0)

def _piecewise_fusion(l, m):
    l = max(0.0, min(float(l), 1.0))
    m = max(0.0, min(float(m), 1.0))
    if l >= _LGN_STRONG_CONFIRM:
        return l
    signals = []
    if l > 0: signals.append((l, 0.70))
    if m > 0: signals.append((m, 0.30))
    if not signals: return 0.0
    ws = sum(s*w*s for s,w in signals)
    ww = sum(w*s   for s,w in signals)
    return max(0.0, min(ws/ww, 1.0)) if ww > 0 else 0.0

def assign_tier(f, gf, kf, l, l0=False):
    if l0: return "HIGH"
    mech = bool(gf) or bool(kf)
    if (bool(gf) and bool(kf)) or l >= _LGN_HIGH_CONF_TH: return "HIGH"
    if f >= _TH_MEDIUM or (mech and l >= 0.5) or l >= _LGN_MEDIUM_CONF_TH: return "MEDIUM"
    if f >= _TH_LOW or mech or l >= 0.5: return "LOW"
    return "INSUFFICIENT"

df.rename(columns={"drug":"drug_name","food":"food_name"}, inplace=True)
df["fusion_C3"] = df.apply(lambda r: _piecewise_fusion(r.lgn_score, _mech_support(r.graph_score, r.kge_score)), axis=1)
df["tier_C4"]   = df.apply(lambda r: assign_tier(r.fusion_C3, r.graph_found, r.kge_found, r.lgn_score), axis=1)

high = df[df.tier_C4 == "HIGH"][["drug_name","food_name","lgn_score","fusion_C3","graph_found","kge_found","truth"]].copy()
high = high.sort_values("lgn_score", ascending=False)

print(f"HIGH tier pairs: {len(high)}\n")
print(high.to_string(index=False))
