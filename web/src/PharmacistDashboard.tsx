/**
 * PharmacistDashboard.tsx
 *
 * Point-of-sale dashboard for Algerian pharmacists. Designed for speed:
 *   - PIN-authenticated (reuses /api/professional/auth, role=pharmacist)
 *   - 3-column desktop layout, single column on tablet/mobile
 *   - Counseling scripts in FR/AR/EN with local Algerian food vocabulary
 *   - Printable / WhatsApp-shareable dietary safety slip
 *   - Real-time food check against the DFinder pipeline
 */

import React from "react";
import { Search, Pill, Plus, X, Printer, Share2, Download, Trash2, AlertTriangle, KeyRound, Globe, Sun, Moon } from "lucide-react";

type Lang = "fr" | "en" | "ar";
type ProfileRow = { id: string; role: string; name?: string; specialty?: string };

type DrugProfile = {
  ok: true;
  drug_key: string;
  trade_name: string;
  inn: string;
  pipeline_drug: string;
  drug_class: { fr: string; en: string; ar: string };
  cyp_profile: {
    substrate?: string[];
    inhibitor?: string[];
    inducer?: string[];
    notes?: { fr: string; en: string; ar: string };
  };
  counts: { high: number; medium: number; safe: number };
  top_high: Array<{ name: string; reason?: string }>;
  top_medium: Array<{ name: string; reason?: string }>;
  top_safe: Array<{ name: string; reason?: string }>;
  contraindications: Array<{ food: string; mechanism: { fr: string; en: string; ar: string } }>;
  has_detailed_profile: boolean;
  trade_query?: string;
  from_cache?: boolean;
};

type ScriptResp = {
  ok: true;
  lang: Lang;
  scripts: string[];
  warnings: Array<{ food: string; mechanism: string; severity: string }>;
};

type FoodCheck = {
  ok: true;
  drug: { key: string; trade: string; inn: string };
  food: string;
  tier: string;
  score: number;
  mechanism: string;
  source?: string;
  from_cache?: boolean;
};

const T: Record<Lang, Record<string, string>> = {
  fr: {
    title: "Tableau de bord Pharmacien",
    subtitle: "Conseil rapide au comptoir — scan, scripts, fiche sécurité.",
    signInTitle: "Accès Pharmacien",
    signInSub: "Saisissez votre PIN à 6 chiffres.",
    pin: "PIN",
    enter: "Entrer",
    authFailed: "PIN invalide.",
    column1: "Scanner d'ordonnance",
    column2: "Script de conseil",
    column3: "Fiche sécurité",
    searchDrug: "Médicament (nom commercial ou DCI)",
    searchPh: "ex. Sintrom, Tahor, Glucophage",
    addAnother: "Ajouter un médicament",
    clearNew: "Nouveau patient",
    classBadge: "Classe",
    cyp: "Profil CYP450",
    counts: "Aliments classés",
    high: "ÉLEVÉ",
    medium: "MOYEN",
    safe: "FAIBLE / SÛR",
    selectedDrugs: "Médicaments sélectionnés",
    foodCheckTitle: "Vérifier un aliment",
    foodCheckPh: "ex. couscous, épinards, thé à la menthe",
    foodCheckBtn: "Vérifier",
    counselTitle: "À dire au patient",
    warningsTitle: "Avertissements critiques",
    contra: "CONTRE-INDICATION",
    avoidTitle: "À ÉVITER",
    safeTitle: "À PRÉFÉRER",
    consistent: "Garder la consommation de légumes verts CONSTANTE — pas zéro.",
    pharmacist: "Pharmacien",
    pharmacy: "Pharmacie",
    print: "Imprimer",
    whatsapp: "Envoyer (WhatsApp)",
    pdf: "Télécharger PDF",
    notFound: "Aucun médicament détaillé correspondant. Vérifier l'orthographe ou la notice.",
    noDrugYet: "Sélectionnez un médicament pour générer le script.",
    poweredBy: "Pipeline DFinder + base 2 663 noms commerciaux",
    role: "Rôle pharmacien",
  },
  en: {
    title: "Pharmacist Dashboard",
    subtitle: "Counter-side counseling — scan, scripts, safety slip.",
    signInTitle: "Pharmacist Access",
    signInSub: "Enter your 6-digit PIN.",
    pin: "PIN",
    enter: "Enter",
    authFailed: "Invalid PIN.",
    column1: "Prescription Scanner",
    column2: "Counseling Script",
    column3: "Safety Slip",
    searchDrug: "Medication (trade name or INN)",
    searchPh: "e.g. Sintrom, Tahor, Glucophage",
    addAnother: "Add another medication",
    clearNew: "New patient",
    classBadge: "Class",
    cyp: "CYP450 Profile",
    counts: "Food risk summary",
    high: "HIGH",
    medium: "MEDIUM",
    safe: "LOW / SAFE",
    selectedDrugs: "Selected medications",
    foodCheckTitle: "Check a food",
    foodCheckPh: "e.g. couscous, spinach, mint tea",
    foodCheckBtn: "Check",
    counselTitle: "Tell the patient",
    warningsTitle: "Critical warnings",
    contra: "CONTRAINDICATION",
    avoidTitle: "AVOID",
    safeTitle: "SAFE",
    consistent: "Keep green vegetable intake CONSISTENT — not zero.",
    pharmacist: "Pharmacist",
    pharmacy: "Pharmacy",
    print: "Print",
    whatsapp: "Send (WhatsApp)",
    pdf: "Download PDF",
    notFound: "No detailed match. Check spelling or the leaflet.",
    noDrugYet: "Select a medication to generate the script.",
    poweredBy: "DFinder pipeline + 2,663 trade-name database",
    role: "Pharmacist role",
  },
  ar: {
    title: "لوحة الصيدلي",
    subtitle: "نصائح سريعة عند الكاونتر — مسح، نصوص، بطاقة سلامة.",
    signInTitle: "دخول الصيدلي",
    signInSub: "أدخل رمز PIN المكون من 6 أرقام.",
    pin: "PIN",
    enter: "دخول",
    authFailed: "PIN غير صحيح.",
    column1: "ماسح الوصفات",
    column2: "نص النصيحة",
    column3: "بطاقة السلامة",
    searchDrug: "الدواء (الاسم التجاري أو DCI)",
    searchPh: "مثل: Sintrom, Tahor, Glucophage",
    addAnother: "إضافة دواء آخر",
    clearNew: "مريض جديد",
    classBadge: "الصنف",
    cyp: "ملف CYP450",
    counts: "تصنيف الأطعمة",
    high: "مرتفع",
    medium: "متوسط",
    safe: "منخفض / آمن",
    selectedDrugs: "الأدوية المختارة",
    foodCheckTitle: "تحقق من طعام",
    foodCheckPh: "مثل: كسكسي، سبانخ، أتاي بالنعناع",
    foodCheckBtn: "تحقق",
    counselTitle: "ما يقال للمريض",
    warningsTitle: "تحذيرات حرجة",
    contra: "موانع استعمال",
    avoidTitle: "تجنّب",
    safeTitle: "آمن",
    consistent: "حافظ على كمية الخضار الخضراء ثابتة — ليست صفر.",
    pharmacist: "الصيدلي",
    pharmacy: "الصيدلية",
    print: "طباعة",
    whatsapp: "إرسال (واتساب)",
    pdf: "تحميل PDF",
    notFound: "لا توجد معلومات مفصلة. تأكد من التهجئة أو راجع النشرة.",
    noDrugYet: "اختر دواء لتوليد النص.",
    poweredBy: "أنبوب DFinder + قاعدة 2,663 اسم تجاري",
    role: "صلاحية صيدلي",
  },
};

function tierColor(tier: string): string {
  const t = (tier || "").toUpperCase();
  if (t === "HIGH") return "bg-rose-100 text-rose-800 border-rose-200";
  if (t === "MEDIUM") return "bg-amber-100 text-amber-800 border-amber-200";
  if (t === "LOW") return "bg-emerald-100 text-emerald-800 border-emerald-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
}

export default function PharmacistDashboard() {
  const [lang, setLang] = React.useState<Lang>(() => {
    const saved = localStorage.getItem("healthopt.lang");
    return saved === "fr" || saved === "en" || saved === "ar" ? (saved as Lang) : "fr";
  });
  const [darkMode, setDarkMode] = React.useState<boolean>(() => {
    return localStorage.getItem("healthopt.theme") === "dark";
  });
  const tr = (k: string) => T[lang][k] || T.fr[k] || k;
  React.useEffect(() => {
    localStorage.setItem("healthopt.theme", darkMode ? "dark" : "light");
  }, [darkMode]);
  const themeRoot = darkMode ? "theme-dark" : "";

  const [token, setToken] = React.useState<string>(() => localStorage.getItem("healthopt.professional.token") || "");
  const [profile, setProfile] = React.useState<ProfileRow | null>(() => {
    const raw = localStorage.getItem("healthopt.professional.profile");
    try {
      const p = raw ? JSON.parse(raw) : null;
      return p && (p.role || "").toLowerCase() === "pharmacist" ? p : null;
    } catch {
      return null;
    }
  });
  const [authPin, setAuthPin] = React.useState("");
  const [authLoading, setAuthLoading] = React.useState(false);
  const [authNotice, setAuthNotice] = React.useState("");

  const [pharmacyName, setPharmacyName] = React.useState<string>(() => localStorage.getItem("healthopt.pharmacy") || "");
  React.useEffect(() => {
    localStorage.setItem("healthopt.lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  React.useEffect(() => {
    localStorage.setItem("healthopt.pharmacy", pharmacyName);
  }, [pharmacyName]);

  // ── Drug search/autocomplete ────────────────────────────────────────────
  const [search, setSearch] = React.useState("");
  const [suggestions, setSuggestions] = React.useState<Array<{ brand_name: string; pipeline_drug: string }>>([]);
  const [showSugg, setShowSugg] = React.useState(false);
  const debounceRef = React.useRef<number | null>(null);

  const [selectedDrugs, setSelectedDrugs] = React.useState<DrugProfile[]>([]);
  const [activeDrugIndex, setActiveDrugIndex] = React.useState<number>(0);

  const activeDrug = selectedDrugs[activeDrugIndex] || null;

  const [scripts, setScripts] = React.useState<ScriptResp | null>(null);

  // Food quick-check
  const [foodQuery, setFoodQuery] = React.useState("");
  const [foodResult, setFoodResult] = React.useState<FoodCheck | null>(null);
  const [foodLoading, setFoodLoading] = React.useState(false);

  const authHeaders = React.useCallback(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  // Auth
  const submitAuth = async () => {
    setAuthLoading(true);
    setAuthNotice("");
    try {
      const res = await fetch("/api/professional/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "pharmacist", pin: authPin }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload?.detail || tr("authFailed"));
      const nextProfile = payload.professional as ProfileRow;
      if ((nextProfile?.role || "").toLowerCase() !== "pharmacist") {
        throw new Error(tr("authFailed"));
      }
      setProfile(nextProfile);
      setToken(String(payload?.token || ""));
      localStorage.setItem("healthopt.professional.token", String(payload?.token || ""));
      localStorage.setItem("healthopt.professional.profile", JSON.stringify(nextProfile));
    } catch (e: any) {
      setAuthNotice(e?.message || tr("authFailed"));
    } finally {
      setAuthLoading(false);
    }
  };

  const signOut = () => {
    setProfile(null);
    setToken("");
    localStorage.removeItem("healthopt.professional.token");
    localStorage.removeItem("healthopt.professional.profile");
    window.location.href = "/professional-login";
  };

  // Drug autocomplete
  React.useEffect(() => {
    if (!search.trim()) {
      setSuggestions([]);
      return;
    }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await fetch(`/api/trade-names/search?q=${encodeURIComponent(search.trim())}`, {
          headers: authHeaders(),
        });
        const arr = await res.json().catch(() => []);
        setSuggestions(Array.isArray(arr) ? arr.slice(0, 12) : []);
      } catch {
        setSuggestions([]);
      }
    }, 150);
  }, [search, authHeaders]);

  // Load scripts when active drug changes / language toggle
  React.useEffect(() => {
    if (!activeDrug) {
      setScripts(null);
      return;
    }
    void (async () => {
      try {
        const res = await fetch(
          `/api/pharmacist/counseling-script/${encodeURIComponent(activeDrug.drug_key)}?lang=${lang}`,
          { headers: authHeaders() },
        );
        const payload = await res.json().catch(() => null);
        if (payload?.ok) setScripts(payload as ScriptResp);
        else setScripts(null);
      } catch {
        setScripts(null);
      }
    })();
  }, [activeDrug?.drug_key, lang, authHeaders]);

  const fetchDrugProfile = async (trade: string) => {
    try {
      const res = await fetch(`/api/pharmacist/drug-profile/${encodeURIComponent(trade)}`, {
        headers: authHeaders(),
      });
      if (!res.ok) return null;
      return (await res.json()) as DrugProfile;
    } catch {
      return null;
    }
  };

  const selectSuggestion = async (s: { brand_name: string; pipeline_drug: string }) => {
    setShowSugg(false);
    setSearch("");
    const profile = await fetchDrugProfile(s.brand_name);
    if (!profile) return;
    setSelectedDrugs((prev) => {
      const exists = prev.findIndex((p) => p.drug_key === profile.drug_key);
      if (exists >= 0) {
        setActiveDrugIndex(exists);
        return prev;
      }
      const next = [...prev, profile];
      setActiveDrugIndex(next.length - 1);
      return next;
    });
  };

  const submitFreeform = async () => {
    if (!search.trim()) return;
    const profile = await fetchDrugProfile(search.trim());
    if (!profile) return;
    setSelectedDrugs((prev) => {
      const exists = prev.findIndex((p) => p.drug_key === profile.drug_key);
      if (exists >= 0) {
        setActiveDrugIndex(exists);
        return prev;
      }
      const next = [...prev, profile];
      setActiveDrugIndex(next.length - 1);
      return next;
    });
    setSearch("");
    setShowSugg(false);
  };

  const removeDrug = (idx: number) => {
    setSelectedDrugs((prev) => prev.filter((_, i) => i !== idx));
    if (activeDrugIndex >= idx) {
      setActiveDrugIndex((p) => Math.max(0, p - 1));
    }
  };

  const clearAll = () => {
    setSelectedDrugs([]);
    setActiveDrugIndex(0);
    setScripts(null);
    setFoodQuery("");
    setFoodResult(null);
    setSearch("");
  };

  const checkFood = async () => {
    if (!activeDrug || !foodQuery.trim()) return;
    setFoodLoading(true);
    try {
      const res = await fetch(
        `/api/pharmacist/food-check?drug=${encodeURIComponent(activeDrug.drug_key)}&food=${encodeURIComponent(foodQuery.trim())}`,
        { headers: authHeaders() },
      );
      const payload = await res.json().catch(() => null);
      setFoodResult(payload as FoodCheck);
    } finally {
      setFoodLoading(false);
    }
  };

  // Safety slip
  const generateSlip = async (action: "print" | "whatsapp" | "pdf") => {
    if (!activeDrug) return;
    const res = await fetch("/api/pharmacist/safety-slip", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        drugId: activeDrug.drug_key,
        pharmacistName: profile?.name || tr("pharmacist"),
        pharmacyName: pharmacyName || tr("pharmacy"),
        lang,
      }),
    });
    const payload = await res.json().catch(() => null);
    if (!payload?.ok) return;
    if (action === "whatsapp") {
      window.open(payload.whatsappUrl, "_blank", "noopener");
      return;
    }
    const w = window.open("", "_blank", "noopener,width=420,height=620");
    if (!w) return;
    w.document.open();
    w.document.write(payload.html);
    w.document.close();
    if (action === "print") {
      // Wait for the content to be fully rendered before triggering print.
      setTimeout(() => {
        try {
          w.focus();
          w.print();
        } catch {
          // ignore
        }
      }, 250);
    }
    // For "pdf" we rely on the user choosing "Save as PDF" in the print dialog.
    if (action === "pdf") {
      setTimeout(() => {
        try {
          w.focus();
          w.print();
        } catch {
          // ignore
        }
      }, 250);
    }
  };

  // ── Auth gate ───────────────────────────────────────────────────────────
  if (!profile || !token) {
    return (
      <div className={`${themeRoot} min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12`}>
        <div className="w-full max-w-md bg-white rounded-2xl shadow-md border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center">
                <img src="/logo.png" alt="HealthOpt" className="w-7 h-7 object-contain" />
              </div>
              <h1 className="text-xl font-semibold text-slate-900">{tr("signInTitle")}</h1>
            </div>
            <button
              type="button"
              onClick={() => setDarkMode((p) => !p)}
              title={darkMode ? "Light" : "Dark"}
              className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs border border-slate-200 bg-white text-slate-700"
            >
              {darkMode ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
              {darkMode ? "Dark" : "Light"}
            </button>
          </div>
          <p className="text-sm text-slate-600 mb-4 flex items-center gap-1"><KeyRound className="w-3.5 h-3.5" /> {tr("signInSub")}</p>
          <div className="flex gap-2 mb-4">
            {(["fr", "en", "ar"] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-3 py-1.5 rounded-md text-sm border ${
                  lang === l
                    ? "bg-slate-900 text-white border-slate-900"
                    : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                }`}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium text-slate-700 mb-1">{tr("pin")}</label>
          <input
            type="password"
            inputMode="numeric"
            value={authPin}
            onChange={(e) => setAuthPin(e.target.value)}
            placeholder="123456"
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-base focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
          {authNotice ? <div className="mt-3 text-sm text-rose-600">{authNotice}</div> : null}
          <button
            onClick={submitAuth}
            disabled={authLoading || !authPin}
            className="mt-4 w-full bg-slate-900 text-white py-2 rounded-md text-base font-medium disabled:opacity-50"
          >
            {tr("enter")}
          </button>
          <div className="mt-4 text-[11px] text-slate-500">{tr("poweredBy")}</div>
        </div>
      </div>
    );
  }

  // ── Main UI ─────────────────────────────────────────────────────────────
  return (
    <div className={`${themeRoot} min-h-screen bg-slate-50 text-slate-900`} style={{ fontSize: 16 }}>
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center shadow-sm">
              <img src="/logo.png" alt="HealthOpt" className="w-8 h-8 object-contain" />
            </div>
            <div>
              <div className="text-lg font-semibold leading-tight text-slate-900 tracking-tight">{tr("title")}</div>
              <div className="text-xs text-slate-500">{tr("subtitle")}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center gap-1 text-xs text-slate-500 px-2 py-1 rounded bg-slate-100 border border-slate-200">
              <Globe className="w-3.5 h-3.5" />
              {profile.name || tr("pharmacist")}
            </div>
            <input
              value={pharmacyName}
              onChange={(e) => setPharmacyName(e.target.value)}
              placeholder={tr("pharmacy")}
              className="hidden md:block px-2 py-1 text-sm border border-slate-300 rounded-md w-44"
            />
            <div className="flex gap-1">
              {(["fr", "en", "ar"] as Lang[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  className={`px-2 py-1 text-xs rounded border ${
                    lang === l
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                  }`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setDarkMode((p) => !p)}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-slate-200 bg-white text-slate-700 hover:border-slate-400"
              title={darkMode ? "Light" : "Dark"}
            >
              {darkMode ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
              {darkMode ? "Dark" : "Light"}
            </button>
            <button
              onClick={signOut}
              title="Sign out and return to role selection"
              className={`inline-flex items-center gap-2 rounded-full px-4 py-2 border text-sm ${darkMode ? 'border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'}`}
            >
              <KeyRound size={16} />
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Body — 3 columns on lg+, single column below */}
      <main className="max-w-[1400px] mx-auto px-4 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-[35fr_40fr_25fr] gap-4">
          {/* COLUMN 1 — Scanner */}
          <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700">{tr("column1")}</h2>
              <button
                onClick={clearAll}
                className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-slate-200 hover:bg-slate-100"
                title={tr("clearNew")}
              >
                <Trash2 className="w-3.5 h-3.5" />
                {tr("clearNew")}
              </button>
            </div>

            {/* Search */}
            <label className="block text-sm font-medium text-slate-700 mb-1">{tr("searchDrug")}</label>
            <div className="relative">
              <div className="flex items-center gap-2 border border-slate-300 rounded-lg px-3 py-2 bg-white focus-within:ring-2 focus-within:ring-slate-400">
                <Search className="w-4 h-4 text-slate-400" />
                <input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setShowSugg(true);
                  }}
                  onFocus={() => setShowSugg(true)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void submitFreeform();
                  }}
                  placeholder={tr("searchPh")}
                  className="flex-1 outline-none text-base bg-transparent"
                />
              </div>
              {showSugg && suggestions.length > 0 ? (
                <ul className="absolute z-10 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-72 overflow-auto">
                  {suggestions.map((s, i) => (
                    <li key={`${s.brand_name}-${i}`}>
                      <button
                        onClick={() => void selectSuggestion(s)}
                        className="w-full text-left px-3 py-2 hover:bg-slate-50"
                      >
                        <div className="font-medium text-slate-900">{s.brand_name}</div>
                        <div className="text-xs text-slate-500">({s.pipeline_drug})</div>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            {/* Selected drugs (polypharmacy) */}
            {selectedDrugs.length > 0 ? (
              <div className="mt-4">
                <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("selectedDrugs")}</div>
                <div className="flex flex-wrap gap-2">
                  {selectedDrugs.map((d, i) => (
                    <button
                      key={d.drug_key + i}
                      onClick={() => setActiveDrugIndex(i)}
                      className={`group inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm border ${
                        i === activeDrugIndex
                          ? "bg-slate-900 text-white border-slate-900"
                          : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                      }`}
                    >
                      <Pill className="w-3.5 h-3.5" />
                      {d.trade_name}
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          removeDrug(i);
                        }}
                        className="ml-1 opacity-60 hover:opacity-100"
                      >
                        <X className="w-3 h-3" />
                      </span>
                    </button>
                  ))}
                  <button
                    onClick={() => {
                      const el = document.querySelector<HTMLInputElement>("input[placeholder]");
                      el?.focus();
                    }}
                    className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded-full border border-dashed border-slate-300 text-slate-500 hover:bg-slate-50"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    {tr("addAnother")}
                  </button>
                </div>
              </div>
            ) : null}

            {/* Active drug detail */}
            {activeDrug ? (
              <div className="mt-4 space-y-3">
                <div className="border-l-2 border-slate-900 pl-3">
                  <div className="text-base font-bold text-slate-900 tracking-tight">
                    {activeDrug.trade_name}
                    <span className="ml-2 text-sm font-normal text-slate-500">({activeDrug.inn})</span>
                  </div>
                  <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-slate-700">
                    {tr("classBadge")}: {activeDrug.drug_class[lang]}
                  </span>
                </div>

                <div>
                  <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("cyp")}</div>
                  <div className="text-sm text-slate-700 space-y-0.5">
                    {activeDrug.cyp_profile.substrate?.length ? (
                      <div>
                        <span className="font-medium">substrate:</span> {activeDrug.cyp_profile.substrate.join(", ")}
                      </div>
                    ) : null}
                    {activeDrug.cyp_profile.inhibitor?.length ? (
                      <div>
                        <span className="font-medium">inhibitor:</span> {activeDrug.cyp_profile.inhibitor.join(", ")}
                      </div>
                    ) : null}
                    {activeDrug.cyp_profile.inducer?.length ? (
                      <div>
                        <span className="font-medium">inducer:</span> {activeDrug.cyp_profile.inducer.join(", ")}
                      </div>
                    ) : null}
                    {activeDrug.cyp_profile.notes?.[lang] ? (
                      <div className="text-slate-500 italic">{activeDrug.cyp_profile.notes[lang]}</div>
                    ) : null}
                  </div>
                </div>

                <div>
                  <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("counts")}</div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-lg p-2 border border-rose-200 bg-rose-50">
                      <div className="text-[10px] uppercase text-rose-700">{tr("high")}</div>
                      <div className="text-lg font-bold text-rose-700">{activeDrug.counts.high}</div>
                    </div>
                    <div className="rounded-lg p-2 border border-amber-200 bg-amber-50">
                      <div className="text-[10px] uppercase text-amber-700">{tr("medium")}</div>
                      <div className="text-lg font-bold text-amber-700">{activeDrug.counts.medium}</div>
                    </div>
                    <div className="rounded-lg p-2 border border-emerald-200 bg-emerald-50">
                      <div className="text-[10px] uppercase text-emerald-700">{tr("safe")}</div>
                      <div className="text-lg font-bold text-emerald-700">{activeDrug.counts.safe}</div>
                    </div>
                  </div>
                </div>

                {!activeDrug.has_detailed_profile ? (
                  <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
                    {tr("notFound")}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="mt-4 text-sm text-slate-500">{tr("noDrugYet")}</div>
            )}

            {/* Food quick check */}
            <div className="mt-5 pt-4 border-t border-slate-200">
              <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("foodCheckTitle")}</div>
              <div className="flex gap-2">
                <input
                  value={foodQuery}
                  onChange={(e) => setFoodQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void checkFood();
                  }}
                  placeholder={tr("foodCheckPh")}
                  disabled={!activeDrug}
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-base disabled:bg-slate-100"
                />
                <button
                  onClick={() => void checkFood()}
                  disabled={!activeDrug || !foodQuery.trim() || foodLoading}
                  className="px-3 py-2 bg-slate-900 text-white rounded-md text-sm font-medium disabled:opacity-50"
                >
                  {tr("foodCheckBtn")}
                </button>
              </div>
              {foodResult ? (
                <div className={`mt-2 p-2 text-sm rounded-md border ${tierColor(foodResult.tier)}`}>
                  <div className="font-medium">
                    {foodResult.food} × {foodResult.drug.trade}: {foodResult.tier}
                  </div>
                  {foodResult.mechanism ? <div className="text-xs mt-0.5 opacity-80">{foodResult.mechanism}</div> : null}
                </div>
              ) : null}
            </div>
          </section>

          {/* COLUMN 2 — Counseling */}
          <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700">{tr("column2")}</h2>
            </div>

            {!activeDrug ? (
              <div className="text-sm text-slate-500">{tr("noDrugYet")}</div>
            ) : (
              <>
                <h3 className="text-base font-bold text-slate-900 mb-3 pb-2 border-b border-slate-200">{tr("counselTitle")}</h3>
                <ul className="space-y-2">
                  {(scripts?.scripts || []).map((line, i) => (
                    <li key={i} className="flex items-start gap-2 text-[15px] leading-snug">
                      <span className="text-emerald-600 mt-0.5">✓</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>

                {(scripts?.warnings?.length || 0) > 0 ? (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-rose-700 mb-1 flex items-center gap-1">
                      <AlertTriangle className="w-4 h-4" />
                      {tr("warningsTitle")}
                    </h3>
                    <div className="space-y-2">
                      {/* Critical warnings stay red-on-white in both themes (per spec) */}
                      {scripts!.warnings.map((w, i) => (
                        <div
                          key={i}
                          className="border-2 border-[#fda4af] bg-[#ffffff] rounded-md p-3 text-[#7f1d1d]"
                        >
                          <div className="text-xs uppercase font-bold tracking-wide text-[#b91c1c]">
                            ⛔ {tr("contra")}
                          </div>
                          <div className="text-[15px] font-semibold mt-1 text-[#0f172a]">
                            {activeDrug.trade_name} × {w.food}
                          </div>
                          <div className="text-sm mt-1 text-[#991b1b]">{w.mechanism}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </section>

          {/* COLUMN 3 — Safety slip */}
          <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700">{tr("column3")}</h2>
            </div>

            {!activeDrug ? (
              <div className="text-sm text-slate-500">{tr("noDrugYet")}</div>
            ) : (
              <>
                {/* Slip preview deliberately stays LIGHT in both themes — it's a printable card. */}
                <div className="border-2 rounded-xl p-3 bg-[#ffffff] border-[#0f172a] text-[#0f172a]">
                  <div className="flex items-center justify-between border-b border-dashed border-[#cbd5e1] pb-2 mb-2">
                    <div className="flex items-center gap-1.5">
                      <img src="/logo.png" alt="HealthOpt" className="w-5 h-5 object-contain" />
                      <div className="font-extrabold tracking-wide text-[#0f172a]">HealthOpt</div>
                    </div>
                    <div className="text-[10px] uppercase text-[#64748b]">
                      {lang === "fr" ? "Carte Sécurité Alimentaire" : lang === "ar" ? "بطاقة سلامة غذائية" : "Dietary Safety Card"}
                    </div>
                  </div>
                  <div className="text-lg font-bold text-[#0f172a]">{activeDrug.trade_name}</div>
                  <div className="text-xs text-[#64748b] mb-2">{activeDrug.inn}</div>

                  <div className="text-[11px] uppercase font-semibold text-[#b91c1c] mt-1">{tr("avoidTitle")}</div>
                  {activeDrug.top_high.slice(0, 3).map((f) => (
                    <div key={f.name} className="text-sm text-[#b91c1c]">🚫 {f.name}</div>
                  ))}
                  {activeDrug.top_high.length === 0 ? (
                    <div className="text-xs text-[#94a3b8]">—</div>
                  ) : null}

                  <div className="text-[11px] uppercase font-semibold text-[#15803d] mt-2">{tr("safeTitle")}</div>
                  {activeDrug.top_safe.slice(0, 3).map((f) => (
                    <div key={f.name} className="text-sm text-[#15803d]">✓ {f.name}</div>
                  ))}
                  {activeDrug.top_safe.length === 0 ? (
                    <div className="text-xs text-[#94a3b8]">—</div>
                  ) : null}

                  <div className="mt-3 p-2 bg-[#f8fafc] border-l-2 border-[#0f172a] text-[13px] text-[#0f172a]">
                    {tr("consistent")}
                  </div>
                  <div className="mt-3 text-[11px] text-[#64748b]">
                    <div>
                      <strong className="text-[#0f172a]">{profile?.name || tr("pharmacist")}</strong>
                    </div>
                    <div>{pharmacyName || tr("pharmacy")}</div>
                    <div>{new Date().toISOString().slice(0, 10)}</div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-2">
                  <button
                    onClick={() => void generateSlip("print")}
                    className="flex items-center justify-center gap-2 px-3 py-2 bg-slate-900 text-white rounded-md text-sm font-medium"
                  >
                    <Printer className="w-4 h-4" />
                    {tr("print")}
                  </button>
                  <button
                    onClick={() => void generateSlip("whatsapp")}
                    className="flex items-center justify-center gap-2 px-3 py-2 bg-emerald-600 text-white rounded-md text-sm font-medium"
                  >
                    <Share2 className="w-4 h-4" />
                    {tr("whatsapp")}
                  </button>
                  <button
                    onClick={() => void generateSlip("pdf")}
                    className="flex items-center justify-center gap-2 px-3 py-2 bg-white text-slate-900 border border-slate-300 rounded-md text-sm font-medium hover:bg-slate-50"
                  >
                    <Download className="w-4 h-4" />
                    {tr("pdf")}
                  </button>
                </div>
              </>
            )}
          </section>
        </div>

        <div className="mt-4 text-[11px] text-slate-500 text-center">{tr("poweredBy")}</div>
      </main>
    </div>
  );
}
