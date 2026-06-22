/**
 * NutritionistDashboard.tsx
 *
 * Two-panel meal-planning workspace for nutritionists. Every food placed
 * onto the weekly grid is cross-checked in real time against the linked
 * patient's medications (manual + Model-2 virtual signals). Mounted at
 * /nutritionist-dashboard, reuses /api/professional/auth with role=nutritionist.
 */

import React from "react";
import {
  AlertTriangle, KeyRound, Globe, Sun, Moon, Plus, X, Printer, Save,
  Wand2, Download, Users, Activity, ChefHat, FlaskConical, Sparkles,
} from "lucide-react";

type Lang = "fr" | "en" | "ar";
type Tier = "HIGH" | "MEDIUM" | "LOW" | "SAFE";
type ProfileRow = { id: string; role: string; name?: string };

type Medication = { key: string; trade: string; inn: string; source: "manual" | "virtual"; severity?: string };
type VMSignal = { drug_name: string; public_label: string; signal_key: string; signal_reason: string; severity: string };
type SynergyAlert = { id: string; severity: string; title: Record<Lang, string>; advice: Record<Lang, string[]> };

type PatientContext = {
  patientId: string;
  medications: Medication[];
  virtualSignals: VMSignal[];
  cycle: any | null;
  lastBloodTest: string | null;
  alerts: SynergyAlert[];
};

type FlaggedItem = {
  food: string;
  foodName: string;
  drug: string;
  tier: Tier;
  mechanism: string;
  day?: string;
  slot?: string;
};

type NutrientResult = {
  totals: { vitamin_k_mcg: number; iron_mg: number; vitamin_d_iu: number; calcium_mg: number; b12_mcg: number };
  perDay: { vitamin_k_mcg: number; iron_mg: number; vitamin_d_iu: number; calcium_mg: number; b12_mcg: number };
  tiers: { vitamin_k: Tier; iron: Tier; vitamin_d: Tier; calcium: Tier; b12: Tier };
  patientContext: { hasAnticoag: boolean; onLevothyrox: boolean; onMetformin: boolean; ironDeficient: boolean; vitDDeficient: boolean };
};

type UsageInfo = { patientsLinked: number; patientsLimit: number; exportsThisMonth: number; exportsLimit: number; atPatientLimit: boolean; atExportLimit: boolean };

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
const SLOTS = ["Breakfast", "Lunch", "Dinner", "Snacks"] as const;
type Day = (typeof DAYS)[number];
type Slot = (typeof SLOTS)[number];
type MealPlan = Record<Day, Record<Slot, string[]>>;

const emptyPlan = (): MealPlan => {
  const p: any = {};
  for (const d of DAYS) {
    p[d] = {};
    for (const s of SLOTS) p[d][s] = [];
  }
  return p as MealPlan;
};

const T: Record<Lang, Record<string, string>> = {
  fr: {
    title: "Tableau de bord Nutritionniste",
    subtitle: "Planification de repas — saine ET pharmacologiquement sûre",
    signInTitle: "Connexion nutritionniste",
    signInSub: "Code PIN professionnel (4–6 chiffres).",
    pin: "PIN", enter: "Entrer", poweredBy: "Propulsé par HealthOpt",
    selectPatient: "Sélectionner un patient",
    noPatient: "Aucun patient sélectionné",
    medications: "Médicaments en cours",
    deficiencies: "Carences détectées (Modèle 2)",
    cyclePhase: "Phase du cycle",
    lastTest: "Dernier bilan",
    requestLab: "Demander un bilan",
    weeklyPlan: "Plan hebdomadaire",
    breakfast: "Petit-déj.", lunch: "Déjeuner", dinner: "Dîner", snacks: "Collations",
    addFood: "+ ajouter un aliment",
    enterFood: "Saisir un aliment ou un plat (couscous, chorba...)",
    decomposing: "Décomposition...",
    nutrients: "Apports hebdomadaires",
    synergyTitle: "Synergies bio-marqueurs",
    feed: "Interactions détectées",
    safetyScore: "Score de sécurité",
    optimize: "Optimiser automatiquement",
    optimizing: "Optimisation...",
    savePlan: "Enregistrer le plan",
    planSaved: "Plan hebdomadaire enregistré.",
    planSavedNoFoods: "Plan enregistré. Ajoutez au moins un aliment pour activer l'analyse du score.",
    export: "Exporter le plan (PDF)",
    safeSubs: "Substituts sûrs",
    upgradeBanner: "Vous avez atteint la limite gratuite.",
    upgradeCta: "Passer à Pro — 2 900 DZD/mois",
    consistent: "Maintenir un apport en légumes verts CONSTANT.",
    noFlag: "Aucune interaction détectée pour le moment.",
    emptyPlan: "Construisez le plan à gauche pour voir les interactions ici.",
    noPatientYet: "Sélectionnez un patient pour commencer.",
    avoid: "Éviter",
  },
  en: {
    title: "Nutritionist Dashboard",
    subtitle: "Meal planning that is both healthy AND pharmacologically safe",
    signInTitle: "Nutritionist sign-in",
    signInSub: "Professional PIN (4–6 digits).",
    pin: "PIN", enter: "Sign in", poweredBy: "Powered by HealthOpt",
    selectPatient: "Select a patient",
    noPatient: "No patient selected",
    medications: "Current medications",
    deficiencies: "Detected deficiencies (Model 2)",
    cyclePhase: "Cycle phase",
    lastTest: "Last lab update",
    requestLab: "Request lab update",
    weeklyPlan: "Weekly plan",
    breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snacks: "Snacks",
    addFood: "+ add food",
    enterFood: "Type a food or dish (couscous, chorba...)",
    decomposing: "Decomposing...",
    nutrients: "Weekly nutrient totals",
    synergyTitle: "Biomarker synergy alerts",
    feed: "Flagged interactions",
    safetyScore: "Safety score",
    optimize: "Optimize automatically",
    optimizing: "Optimizing...",
    savePlan: "Save plan",
    planSaved: "Weekly plan saved.",
    planSavedNoFoods: "Plan saved. Add at least one food item to activate score analysis.",
    export: "Export plan (PDF)",
    safeSubs: "Safe substitutes",
    upgradeBanner: "You've reached the free-tier limit.",
    upgradeCta: "Upgrade to Pro — 2,900 DZD/month",
    consistent: "Keep green-vegetable intake CONSISTENT day to day.",
    noFlag: "No interactions detected yet.",
    emptyPlan: "Build the plan on the left to see interactions here.",
    noPatientYet: "Select a patient to begin.",
    avoid: "Avoid",
  },
  ar: {
    title: "لوحة أخصائي التغذية",
    subtitle: "تخطيط وجبات صحية وآمنة دوائياً",
    signInTitle: "تسجيل الدخول",
    signInSub: "الرمز المهني (4–6 أرقام).",
    pin: "PIN", enter: "دخول", poweredBy: "بدعم من HealthOpt",
    selectPatient: "اختر مريضاً",
    noPatient: "لم يتم اختيار مريض",
    medications: "الأدوية الحالية",
    deficiencies: "النواقص المكتشفة (النموذج 2)",
    cyclePhase: "مرحلة الدورة",
    lastTest: "آخر تحليل",
    requestLab: "طلب تحليل",
    weeklyPlan: "الخطة الأسبوعية",
    breakfast: "فطور", lunch: "غداء", dinner: "عشاء", snacks: "وجبات خفيفة",
    addFood: "+ إضافة",
    enterFood: "اكتب طعاماً أو طبقاً (كسكسي، شربة...)",
    decomposing: "جاري التفكيك...",
    nutrients: "الإجمالي الأسبوعي للعناصر",
    synergyTitle: "تنبيهات التآزر الحيوي",
    feed: "تفاعلات مرصودة",
    safetyScore: "درجة الأمان",
    optimize: "تحسين تلقائي",
    optimizing: "جاري التحسين...",
    savePlan: "حفظ الخطة",
    planSaved: "تم حفظ الخطة الأسبوعية.",
    planSavedNoFoods: "تم حفظ الخطة. أضف عنصراً غذائياً واحداً على الأقل لتفعيل تحليل درجة الأمان.",
    export: "تصدير الخطة (PDF)",
    safeSubs: "بدائل آمنة",
    upgradeBanner: "وصلت إلى حد الباقة المجانية.",
    upgradeCta: "ترقية إلى Pro — 2,900 د.ج/شهر",
    consistent: "حافظ على كمية الخضار الخضراء ثابتة.",
    noFlag: "لا توجد تفاعلات مرصودة.",
    emptyPlan: "ابنِ الخطة على اليسار لمشاهدة التفاعلات.",
    noPatientYet: "اختر مريضاً للبدء.",
    avoid: "تجنّب",
  },
};

const tierDot = (t: Tier) =>
  t === "HIGH" ? "bg-rose-500" : t === "MEDIUM" ? "bg-amber-500" : t === "LOW" ? "bg-emerald-500" : "bg-slate-300";
const tierBadge = (t: Tier) =>
  t === "HIGH" ? "bg-rose-100 text-rose-800 border-rose-200" :
  t === "MEDIUM" ? "bg-amber-100 text-amber-800 border-amber-200" :
  t === "LOW" ? "bg-emerald-100 text-emerald-800 border-emerald-200" :
  "bg-slate-100 text-slate-700 border-slate-200";

function gradeFromScore(s: number): string {
  if (s >= 90) return "A";
  if (s >= 78) return "B";
  if (s >= 60) return "C";
  return "D";
}

export default function NutritionistDashboard() {
  const [lang, setLang] = React.useState<Lang>(() => {
    const s = localStorage.getItem("healthopt.lang");
    return s === "fr" || s === "en" || s === "ar" ? (s as Lang) : "fr";
  });
  const [darkMode, setDarkMode] = React.useState<boolean>(() => localStorage.getItem("healthopt.theme") === "dark");
  React.useEffect(() => { localStorage.setItem("healthopt.theme", darkMode ? "dark" : "light"); }, [darkMode]);
  React.useEffect(() => { localStorage.setItem("healthopt.lang", lang); }, [lang]);
  const tr = (k: string) => T[lang][k] || T.fr[k] || k;
  const themeRoot = darkMode ? "theme-dark" : "";

  const [token, setToken] = React.useState<string>(() => localStorage.getItem("healthopt.professional.token") || "");
  const [profile, setProfile] = React.useState<ProfileRow | null>(() => {
    const raw = localStorage.getItem("healthopt.professional.profile");
    try {
      const p = raw ? JSON.parse(raw) : null;
      return p && (p.role || "").toLowerCase() === "nutritionist" ? p : null;
    } catch { return null; }
  });

  const [pin, setPin] = React.useState("");
  const [authBusy, setAuthBusy] = React.useState(false);
  const [authErr, setAuthErr] = React.useState("");

  const signIn = async () => {
    setAuthErr(""); setAuthBusy(true);
    try {
      const r = await fetch("/api/professional/auth", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pin.trim(), role: "nutritionist" }),
      });
      if (!r.ok) { const j = await r.json().catch(() => ({})); setAuthErr(j.detail || `HTTP ${r.status}`); return; }
      const j = await r.json();
      const nextProfile = j.professional || j.profile;
      if (!j.token || !nextProfile || (nextProfile.role || "").toLowerCase() !== "nutritionist") { setAuthErr("Forbidden — nutritionist role required."); return; }
      setToken(j.token); setProfile(nextProfile);
      localStorage.setItem("healthopt.professional.token", j.token);
      localStorage.setItem("healthopt.professional.profile", JSON.stringify(nextProfile));
    } catch (e: any) { setAuthErr(String(e?.message || e)); }
    finally { setAuthBusy(false); }
  };
  const signOut = () => {
    setToken(""); setProfile(null); setPin("");
    localStorage.removeItem("healthopt.professional.token");
    localStorage.removeItem("healthopt.professional.profile");
    window.location.href = "/professional-login";
  };
  const authHeaders = (): Record<string, string> => ({ "Content-Type": "application/json", Authorization: `Bearer ${token}` });

  // ── Linked patients & current patient ────────────────────────────────
  const [linkedPatients, setLinkedPatients] = React.useState<Array<{ id: string; name?: string }>>([]);
  const [selectedPatientId, setSelectedPatientId] = React.useState("");
  const [shareCode, setShareCode] = React.useState("");
  const [patientAlias, setPatientAlias] = React.useState("");
  const [selectedAlias, setSelectedAlias] = React.useState("");
  const [renameBusy, setRenameBusy] = React.useState(false);
  const [linkBusy, setLinkBusy] = React.useState(false);
  const [linkNotice, setLinkNotice] = React.useState<{ type: "success" | "error"; text: string } | null>(null);
  const [context, setContext] = React.useState<PatientContext | null>(null);
  const [usage, setUsage] = React.useState<UsageInfo | null>(null);

  const reloadLinkedPatients = React.useCallback(async () => {
    if (!profile?.id) return [] as Array<{ id: string; name?: string }>;
    const r = await fetch(`/api/professional/patients/${encodeURIComponent(profile.id)}`, { headers: authHeaders() });
    if (!r.ok) return [] as Array<{ id: string; name?: string }>;
    const j = await r.json();
    const list: any[] = j.patients || j.linked || [];
    const norm = list.map((p) => ({ id: String(p.patient_id || p.id || p.patient_user_id || p.user_id || ""), name: p.patient_name || p.name || p.email }));
    setLinkedPatients(norm);
    return norm;
  }, [profile?.id, token]);

  React.useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const norm = await reloadLinkedPatients();
        if (norm.length > 0 && !selectedPatientId) setSelectedPatientId(norm[0].id);
      } catch {}
      try {
        const u = await fetch("/api/nutritionist/usage", { headers: authHeaders() });
        if (u.ok) setUsage(await u.json());
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, reloadLinkedPatients]);

  React.useEffect(() => {
    if (!selectedPatientId) {
      setSelectedAlias("");
      return;
    }
    const current = linkedPatients.find((p) => p.id === selectedPatientId);
    setSelectedAlias(current?.name || "");
  }, [selectedPatientId, linkedPatients]);

  const renameSelectedPatient = async () => {
    if (!selectedPatientId) {
      setLinkNotice({ type: "error", text: "Select a patient first." });
      return;
    }
    setRenameBusy(true);
    setLinkNotice(null);
    try {
      const r = await fetch("/api/professional/link-patient/update", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ patientId: selectedPatientId, patientAlias: selectedAlias.trim() }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(String(j?.detail || `HTTP ${r.status}`));
      await reloadLinkedPatients();
      setLinkNotice({ type: "success", text: "Patient name updated." });
    } catch (e: any) {
      setLinkNotice({ type: "error", text: String(e?.message || e) });
    } finally {
      setRenameBusy(false);
    }
  };

  const linkPatient = async () => {
    if (!shareCode.trim()) {
      setLinkNotice({ type: "error", text: "Share code is required." });
      return;
    }
    setLinkBusy(true);
    setLinkNotice(null);
    try {
      const r = await fetch("/api/professional/link-patient", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ shareCode: shareCode.trim(), patientAlias: patientAlias.trim() || undefined }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(String(j?.detail || `HTTP ${r.status}`));
      }
      const refreshed = await reloadLinkedPatients();
      if (j?.patientId) {
        setSelectedPatientId(String(j.patientId));
      } else if (refreshed.length > 0) {
        setSelectedPatientId(refreshed[0].id);
      }
      setShareCode("");
      setPatientAlias("");
      setLinkNotice({ type: "success", text: "Patient linked successfully." });
    } catch (e: any) {
      setLinkNotice({ type: "error", text: String(e?.message || e) });
    } finally {
      setLinkBusy(false);
    }
  };

  React.useEffect(() => {
    if (!token || !selectedPatientId) { setContext(null); return; }
    (async () => {
      try {
        const r = await fetch(`/api/nutritionist/patient-context?patientId=${encodeURIComponent(selectedPatientId)}`, { headers: authHeaders() });
        if (r.ok) setContext(await r.json());
        else setContext(null);
      } catch { setContext(null); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPatientId, token]);

  // ── Meal plan state ──────────────────────────────────────────────────
  const [plan, setPlan] = React.useState<MealPlan>(() => emptyPlan());
  const [flagged, setFlagged] = React.useState<FlaggedItem[]>([]);
  const [nutrients, setNutrients] = React.useState<NutrientResult | null>(null);
  const [saveNotice, setSaveNotice] = React.useState<string>("");
  const [decomposingCell, setDecomposingCell] = React.useState<string>("");
  const [optimizing, setOptimizing] = React.useState(false);
  const [substitutions, setSubstitutions] = React.useState<Array<{ from: string; to: string; reason: string }>>([]);
  const [highlightSwap, setHighlightSwap] = React.useState<Record<string, "from" | "to" | undefined>>({});
  const [subSuggestions, setSubSuggestions] = React.useState<{ open: string; items: any[] } | null>(null);
  const [draftByCell, setDraftByCell] = React.useState<Record<string, string>>({});
  const cellKey = (d: Day, s: Slot) => `${d}::${s}`;

  const allFoods = React.useMemo(() => {
    const out: string[] = [];
    for (const d of DAYS) for (const s of SLOTS) for (const f of plan[d][s]) out.push(f);
    for (const d of DAYS) for (const s of SLOTS) {
      const draft = String(draftByCell[cellKey(d, s)] || "").trim();
      if (draft) out.push(draft);
    }
    return out;
  }, [plan, draftByCell]);

  const planStorageKey = React.useMemo(
    () => (selectedPatientId ? `healthopt.nutritionist.plan.${selectedPatientId}` : ""),
    [selectedPatientId],
  );

  React.useEffect(() => {
    if (!planStorageKey) {
      setPlan(emptyPlan());
      return;
    }
    try {
      const raw = localStorage.getItem(planStorageKey);
      if (!raw) {
        setPlan(emptyPlan());
        return;
      }
      const parsed = JSON.parse(raw) as MealPlan;
      setPlan(parsed);
    } catch {
      setPlan(emptyPlan());
    }
  }, [planStorageKey]);

  React.useEffect(() => {
    if (!planStorageKey) return;
    try {
      localStorage.setItem(planStorageKey, JSON.stringify(plan));
    } catch {
      // ignore storage failure
    }
  }, [plan, planStorageKey]);

  const savePlan = () => {
    if (!planStorageKey) return;
    try {
      const nextPlan: MealPlan = JSON.parse(JSON.stringify(plan));
      let addedDrafts = 0;
      for (const d of DAYS) {
        for (const s of SLOTS) {
          const draft = String(draftByCell[cellKey(d, s)] || "").trim();
          if (!draft) continue;
          nextPlan[d][s].push(draft);
          addedDrafts += 1;
        }
      }
      setPlan(nextPlan);
      setDraftByCell({});
      localStorage.setItem(planStorageKey, JSON.stringify(nextPlan));
      const committedFoods = DAYS.flatMap((d) => SLOTS.flatMap((s) => nextPlan[d][s]));
      setSaveNotice(committedFoods.length > 0 || addedDrafts > 0 ? tr("planSaved") : tr("planSavedNoFoods"));
      window.setTimeout(() => setSaveNotice(""), 1800);
    } catch {
      setSaveNotice("Unable to save plan.");
      window.setTimeout(() => setSaveNotice(""), 1800);
    }
  };

  // Bulk meal-check (debounced) ─────────────────────────────────────────
  const checkTimerRef = React.useRef<number | null>(null);
  React.useEffect(() => {
    if (!selectedPatientId || !context || allFoods.length === 0) {
      setFlagged([]); setNutrients(null);
      return;
    }
    if (checkTimerRef.current) window.clearTimeout(checkTimerRef.current);
    checkTimerRef.current = window.setTimeout(async () => {
      // Build flat list with day/slot tags for UI attribution
      const itemsWithCtx: Array<{ food: string; day: Day; slot: Slot }> = [];
      for (const d of DAYS) for (const s of SLOTS) for (const f of plan[d][s]) itemsWithCtx.push({ food: f, day: d, slot: s });
      for (const d of DAYS) for (const s of SLOTS) {
        const draft = String(draftByCell[cellKey(d, s)] || "").trim();
        if (draft) itemsWithCtx.push({ food: draft, day: d, slot: s });
      }
      const uniqueFoods = Array.from(new Set(itemsWithCtx.map((x) => x.food)));

      try {
        const r = await fetch("/api/nutritionist/meal-check", {
          method: "POST", headers: authHeaders(),
          body: JSON.stringify({ patientId: selectedPatientId, foods: uniqueFoods, lang }),
        });
        if (r.ok) {
          const j = await r.json();
          const flat: FlaggedItem[] = [];
          for (const row of (j.results || []) as FlaggedItem[]) {
            const hit = itemsWithCtx.find((x) => x.food.toLowerCase() === row.food.toLowerCase() || x.food.toLowerCase() === row.foodName.toLowerCase());
            flat.push({ ...row, day: hit?.day, slot: hit?.slot });
          }
          setFlagged(flat);
        }
      } catch {}
      try {
        const url = `/api/nutritionist/weekly-nutrients?patientId=${encodeURIComponent(selectedPatientId)}&foods=${encodeURIComponent(uniqueFoods.join(","))}`;
        const r = await fetch(url, { headers: authHeaders() });
        if (r.ok) setNutrients(await r.json());
      } catch {}
    }, 300);
    return () => { if (checkTimerRef.current) window.clearTimeout(checkTimerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFoods, selectedPatientId, context, lang, draftByCell, plan]);

  const addFoodToCell = async (d: Day, s: Slot, raw: string, clearDraft = true) => {
    const text = raw.trim(); if (!text) return;
    setDecomposingCell(cellKey(d, s));
    const cellId = cellKey(d, s);
    let toAdd: string[] = [text];
    // Commit immediately so the score updates right away.
    setPlan((p) => {
      const next = { ...p, [d]: { ...p[d], [s]: [...p[d][s], text] } };
      return next;
    });
    try {
      const r = await fetch("/api/nutritionist/decompose-dish", {
        method: "POST", headers: authHeaders(), body: JSON.stringify({ dish: text }),
      });
      if (r.ok) {
        const j = await r.json();
        if (Array.isArray(j.components) && j.components.length > 0) {
          toAdd = j.components;
          setPlan((p) => {
            const next = JSON.parse(JSON.stringify(p)) as MealPlan;
            const idx = next[d][s].lastIndexOf(text);
            if (idx >= 0) next[d][s].splice(idx, 1, ...toAdd);
            return next;
          });
        }
      }
    } catch {}
    if (clearDraft) setDraftByCell((m) => ({ ...m, [cellKey(d, s)]: "" }));
    setDecomposingCell("");
  };

  const removeFoodFromCell = (d: Day, s: Slot, idx: number) => {
    setPlan((p) => {
      const arr = [...p[d][s]];
      arr.splice(idx, 1);
      return { ...p, [d]: { ...p[d], [s]: arr } };
    });
  };

  // ── Safety score ─────────────────────────────────────────────────────
  const score = React.useMemo(() => {
    const hi = flagged.filter((f) => f.tier === "HIGH").length;
    const med = flagged.filter((f) => f.tier === "MEDIUM").length;
    const raw = 100 - hi * 8 - med * 2;
    const value = Math.max(0, Math.min(100, raw));
    return { value, grade: gradeFromScore(value), hi, med };
  }, [flagged]);

  // ── Optimize ─────────────────────────────────────────────────────────
  const runOptimize = async () => {
    if (!selectedPatientId || allFoods.length === 0) return;
    setOptimizing(true);
    try {
      const r = await fetch("/api/nutritionist/optimize-meal", {
        method: "POST", headers: authHeaders(),
        body: JSON.stringify({ patientId: selectedPatientId, foods: allFoods }),
      });
      if (!r.ok) { setOptimizing(false); return; }
      const j = await r.json();
      const subs: Array<{ from: string; to: string; reason: string }> = j.substitutions || [];
      setSubstitutions(subs);

      // Animate swaps one by one
      for (const sub of subs) {
        setHighlightSwap((m) => ({ ...m, [sub.from]: "from" }));
        await new Promise((res) => setTimeout(res, 220));
        setPlan((p) => {
          const next: MealPlan = JSON.parse(JSON.stringify(p));
          for (const d of DAYS) for (const s of SLOTS) {
            next[d][s] = next[d][s].map((f) => (f === sub.from ? sub.to : f));
          }
          return next;
        });
        setHighlightSwap((m) => ({ ...m, [sub.to]: "to" }));
        await new Promise((res) => setTimeout(res, 200));
      }
      setTimeout(() => setHighlightSwap({}), 800);
    } catch {}
    setOptimizing(false);
  };

  // ── Export ───────────────────────────────────────────────────────────
  const runExport = async () => {
    if (!selectedPatientId) return;
    try {
      const r = await fetch("/api/nutritionist/export-meal-plan", {
        method: "POST", headers: authHeaders(),
        body: JSON.stringify({ patientId: selectedPatientId, plan, lang }),
      });
      if (!r.ok) return;
      const j = await r.json();
      const w = window.open("", "_blank");
      if (w) {
        w.document.write(j.html);
        w.document.close();
        setTimeout(() => { try { w.focus(); w.print(); } catch {} }, 250);
      }
      // refresh usage banner
      try { const u = await fetch("/api/nutritionist/usage", { headers: authHeaders() }); if (u.ok) setUsage(await u.json()); } catch {}
    } catch {}
  };

  // ── Substitutes lookup ───────────────────────────────────────────────
  const showSubstitutes = async (foodKey: string) => {
    if (!selectedPatientId) return;
    setSubSuggestions({ open: foodKey, items: [] });
    try {
      const r = await fetch(`/api/nutritionist/safe-substitutes?patientId=${encodeURIComponent(selectedPatientId)}&food=${encodeURIComponent(foodKey)}`, { headers: authHeaders() });
      if (r.ok) {
        const j = await r.json();
        setSubSuggestions({ open: foodKey, items: j.substitutes || [] });
      }
    } catch {}
  };
  const applySub = (from: string, to: string) => {
    setPlan((p) => {
      const next: MealPlan = JSON.parse(JSON.stringify(p));
      for (const d of DAYS) for (const s of SLOTS) {
        next[d][s] = next[d][s].map((f) => (f === from ? to : f));
      }
      return next;
    });
    setSubSuggestions(null);
  };

  const requestLab = async () => {
    if (!selectedPatientId) return;
    try {
      await fetch(`/api/referral-status?userId=${encodeURIComponent(selectedPatientId)}`, { headers: authHeaders() });
      alert(tr("requestLab") + " ✓");
    } catch {}
  };

  // ── Per-food tier lookup for chip coloring ───────────────────────────
  const tierForFood = (foodKey: string): Tier => {
    let worst: Tier = "SAFE";
    for (const f of flagged) {
      if (f.food.toLowerCase() === foodKey.toLowerCase() || f.foodName.toLowerCase() === foodKey.toLowerCase()) {
        if (f.tier === "HIGH") return "HIGH";
        if (f.tier === "MEDIUM") worst = "MEDIUM";
        else if (f.tier === "LOW" && worst === "SAFE") worst = "LOW";
      }
    }
    return worst;
  };

  // ── Auth gate ────────────────────────────────────────────────────────
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
            <button type="button" onClick={() => setDarkMode((p) => !p)} className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs border border-slate-200 bg-white text-slate-700">
              {darkMode ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}{darkMode ? "Dark" : "Light"}
            </button>
          </div>
          <p className="text-sm text-slate-600 mb-4 flex items-center gap-1"><KeyRound className="w-3.5 h-3.5" /> {tr("signInSub")}</p>
          <div className="flex gap-2 mb-4">
            {(["fr", "en", "ar"] as Lang[]).map((l) => (
              <button key={l} onClick={() => setLang(l)} className={`px-3 py-1.5 rounded-md text-sm border ${lang === l ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"}`}>{l.toUpperCase()}</button>
            ))}
          </div>
          <label className="block text-sm font-medium text-slate-700 mb-1">{tr("pin")}</label>
          <input value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 6))} type="password" inputMode="numeric" maxLength={6} placeholder="••••" className="w-full px-3 py-2 border border-slate-300 rounded-md text-lg tracking-widest text-center" onKeyDown={(e) => { if (e.key === "Enter") void signIn(); }} />
          {authErr ? <div className="text-rose-600 text-sm mt-2">{authErr}</div> : null}
          <button onClick={() => void signIn()} disabled={authBusy || pin.length < 4} className="mt-4 w-full px-3 py-2 bg-emerald-600 disabled:bg-slate-300 text-white rounded-md font-medium">
            {tr("enter")}
          </button>
          <div className="mt-4 text-[11px] text-slate-500">{tr("poweredBy")}</div>
        </div>
      </div>
    );
  }

  // ── Main UI ──────────────────────────────────────────────────────────
  return (
    <div className={`${themeRoot} min-h-screen bg-slate-50 text-slate-900`} style={{ fontSize: 16 }}>
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-[1500px] mx-auto px-4 py-3 flex items-center justify-between gap-4">
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
              <Globe className="w-3.5 h-3.5" />{profile.name || "Nutritionist"}
            </div>
            <input
              value={patientAlias}
              onChange={(e) => setPatientAlias(e.target.value)}
              placeholder="Patient nickname (optional)"
              className="px-2 py-1 text-xs rounded border border-slate-300 bg-white min-w-[180px]"
            />
            <input
              value={shareCode}
              onChange={(e) => setShareCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="Share code"
              inputMode="numeric"
              maxLength={6}
              className="px-2 py-1 text-xs rounded border border-slate-300 bg-white w-24"
            />
            <button
              type="button"
              onClick={() => void linkPatient()}
              disabled={linkBusy || shareCode.length < 6}
              className="px-2 py-1 text-xs rounded border border-emerald-300 bg-emerald-50 text-emerald-700 disabled:opacity-50"
            >
              {linkBusy ? "Linking..." : "Link patient"}
            </button>
            <select value={selectedPatientId} onChange={(e) => setSelectedPatientId(e.target.value)} className="px-2 py-1 text-sm rounded border border-slate-300 bg-white">
              <option value="">{tr("selectPatient")}</option>
              {linkedPatients.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
            </select>
            <input
              value={selectedAlias}
              onChange={(e) => setSelectedAlias(e.target.value)}
              placeholder="Rename selected patient"
              className="px-2 py-1 text-xs rounded border border-slate-300 bg-white min-w-[170px]"
            />
            <button
              type="button"
              onClick={() => void renameSelectedPatient()}
              disabled={renameBusy || !selectedPatientId}
              className="px-2 py-1 text-xs rounded border border-sky-300 bg-sky-50 text-sky-700 disabled:opacity-50"
            >
              {renameBusy ? "Saving..." : "Save name"}
            </button>
            <div className="flex gap-1">
              {(["fr", "en", "ar"] as Lang[]).map((l) => (
                <button key={l} onClick={() => setLang(l)} className={`px-2 py-1 text-xs rounded border ${lang === l ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"}`}>{l.toUpperCase()}</button>
              ))}
            </div>
            <button type="button" onClick={() => setDarkMode((p) => !p)} className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-slate-200 bg-white text-slate-700">
              {darkMode ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}{darkMode ? "Dark" : "Light"}
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
        {usage && (usage.atPatientLimit || usage.atExportLimit) ? (
          <div className="max-w-[1500px] mx-auto px-4 pb-2 text-xs flex items-center justify-between gap-3 text-amber-800 bg-amber-50 border border-amber-200 rounded mt-1 mx-4 px-3 py-1.5">
            <span><Sparkles className="inline w-3.5 h-3.5 mr-1" />{tr("upgradeBanner")} ({usage.patientsLinked}/{usage.patientsLimit} patients · {usage.exportsThisMonth}/{usage.exportsLimit} exports)</span>
            <button onClick={async () => { try { await fetch("/api/nutritionist/upgrade-interest", { method: "POST", headers: authHeaders(), body: JSON.stringify({ tier: "pro" }) }); } catch {} }} className="px-2 py-1 rounded bg-amber-600 text-white">{tr("upgradeCta")}</button>
          </div>
        ) : null}
      </header>

      {linkNotice ? (
        <div className="max-w-[1500px] mx-auto px-4 pt-2">
          <div className={`text-xs rounded border px-3 py-2 ${linkNotice.type === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
            {linkNotice.text}
          </div>
        </div>
      ) : null}

      <main className="max-w-[1500px] mx-auto px-4 py-4">
        {!selectedPatientId ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-500 shadow-sm">
            <Users className="w-10 h-10 mx-auto mb-2 text-slate-400" />
            {linkedPatients.length === 0 ? "No linked patients yet." : tr("noPatientYet")}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[55fr_45fr] gap-4">
            {/* LEFT PANEL */}
            <div className="space-y-4">
              {/* A — Patient context */}
              <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700 flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5" /> Patient
                  </h2>
                  {context?.lastBloodTest ? <span className="text-[11px] text-slate-500">{tr("lastTest")}: {context.lastBloodTest.slice(0, 10)}</span> : null}
                </div>
                {!context ? (
                  <div className="text-sm text-slate-500">…</div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("medications")}</div>
                      <div className="flex flex-wrap gap-1.5">
                        {context.medications.length === 0 ? <span className="text-xs text-slate-500">—</span> :
                          context.medications.map((m, i) => (
                            <span key={i} className={`text-xs px-2 py-0.5 rounded-full border ${m.source === "virtual" ? "bg-violet-50 border-violet-200 text-violet-800" : "bg-slate-100 border-slate-200 text-slate-700"}`} title={m.inn}>
                              {m.trade}{m.inn && m.inn !== m.trade ? <span className="ml-1 opacity-60">({m.inn})</span> : null}
                            </span>
                          ))}
                      </div>
                    </div>
                    {context.virtualSignals.length > 0 ? (
                      <div>
                        <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-1">{tr("deficiencies")}</div>
                        <ul className="text-sm space-y-0.5">
                          {context.virtualSignals.map((s, i) => (
                            <li key={i} className="text-violet-800">• {s.public_label} <span className="text-xs text-slate-500">{s.signal_reason}</span></li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {context.cycle ? (
                      <div className="text-xs text-slate-600">
                        <span className="font-semibold text-slate-700">{tr("cyclePhase")}:</span> {context.cycle.phase || "—"}
                        <span className="text-slate-500 italic ml-1">(literature-based note; not patient-specific)</span>
                      </div>
                    ) : null}
                    <button onClick={requestLab} className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-100">
                      <FlaskConical className="w-3.5 h-3.5" /> {tr("requestLab")}
                    </button>
                  </div>
                )}
              </section>

              {/* C — Synergy alerts (top 3) */}
              {context && context.alerts.length > 0 ? (
                <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
                  <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700 flex items-center gap-1.5 mb-2">
                    <AlertTriangle className="w-3.5 h-3.5" /> {tr("synergyTitle")}
                  </h2>
                  <div className="space-y-2">
                    {context.alerts.map((a) => (
                      <div key={a.id} className="border-2 rounded-md p-3 border-[#fda4af] bg-[#ffffff] text-[#7f1d1d]">
                        <div className="text-xs uppercase font-bold tracking-wide text-[#b91c1c]">{a.severity}</div>
                        <div className="text-[15px] font-semibold mt-1 text-[#0f172a]">{a.title[lang] || a.title.en}</div>
                        <ul className="mt-1 space-y-0.5 text-sm text-[#0f172a]">
                          {(a.advice[lang] || a.advice.en).map((line, i) => (
                            <li key={i}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              {/* B — Meal plan builder */}
              <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm overflow-x-auto">
                <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700 flex items-center gap-1.5 mb-3">
                  <ChefHat className="w-3.5 h-3.5" /> {tr("weeklyPlan")}
                </h2>
                <table className="w-full border-collapse" style={{ minWidth: 760 }}>
                  <thead>
                    <tr>
                      <th className="text-left text-[11px] font-bold uppercase tracking-wider text-slate-500 pb-2 pr-2">&nbsp;</th>
                      {DAYS.map((d) => (
                        <th key={d} className="text-center text-[11px] font-bold uppercase tracking-wider text-slate-500 pb-2 px-1">{d}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {SLOTS.map((s) => (
                      <tr key={s}>
                        <td className="align-top text-[12px] font-semibold text-slate-700 py-1.5 pr-2">{tr(s.toLowerCase())}</td>
                        {DAYS.map((d) => {
                          const ck = cellKey(d, s);
                          return (
                            <td key={d} className="align-top p-1 border border-slate-200" style={{ minHeight: 60, minWidth: 100 }}>
                              <div className="flex flex-wrap gap-1 mb-1">
                                {plan[d][s].map((f, i) => {
                                  const tier = tierForFood(f);
                                  const hl = highlightSwap[f];
                                  const animClass = hl === "from" ? "ring-2 ring-rose-400" : hl === "to" ? "ring-2 ring-emerald-400" : "";
                                  return (
                                    <span key={i} className={`inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-full border ${tierBadge(tier)} ${animClass}`}>
                                      <span className={`inline-block rounded-full ${tierDot(tier)}`} style={{ width: 10, height: 10 }} />
                                      {f}
                                      <button onClick={() => removeFoodFromCell(d, s, i)} className="opacity-50 hover:opacity-100"><X className="w-2.5 h-2.5" /></button>
                                      {tier === "HIGH" ? (
                                        <button onClick={() => showSubstitutes(f)} className="text-rose-700 underline" title={tr("safeSubs")}>→</button>
                                      ) : null}
                                    </span>
                                  );
                                })}
                              </div>
                              <input
                                value={draftByCell[ck] || ""}
                                onChange={(e) => setDraftByCell((m) => ({ ...m, [ck]: e.target.value }))}
                                onKeyDown={(e) => { if (e.key === "Enter") void addFoodToCell(d, s, (draftByCell[ck] || "")); }}
                                onBlur={() => { if ((draftByCell[ck] || "").trim()) void addFoodToCell(d, s, (draftByCell[ck] || "")); }}
                                placeholder={decomposingCell === ck ? tr("decomposing") : tr("addFood")}
                                disabled={decomposingCell === ck}
                                className="w-full text-[11px] px-1.5 py-0.5 border border-slate-200 rounded bg-white"
                              />
                              <button
                                type="button"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => void addFoodToCell(d, s, (draftByCell[ck] || ""))}
                                disabled={decomposingCell === ck || !(draftByCell[ck] || "").trim()}
                                className="mt-1 inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-700 disabled:opacity-40"
                              >
                                <Plus className="w-3 h-3" /> Add
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Weekly nutrient totals */}
                {nutrients ? (
                  <div className="mt-4">
                    <div className="text-[11px] uppercase font-bold tracking-[0.12em] text-slate-700 mb-2">{tr("nutrients")}</div>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
                      <NutrientCard label="Vit K" value={`${nutrients.totals.vitamin_k_mcg} mcg`} sub={`${nutrients.perDay.vitamin_k_mcg}/day`} tier={nutrients.tiers.vitamin_k} />
                      <NutrientCard label="Iron" value={`${nutrients.totals.iron_mg} mg`} sub={`${nutrients.perDay.iron_mg}/day`} tier={nutrients.tiers.iron} />
                      <NutrientCard label="Vit D" value={`${nutrients.totals.vitamin_d_iu} IU`} sub={`${nutrients.perDay.vitamin_d_iu}/day`} tier={nutrients.tiers.vitamin_d} />
                      <NutrientCard label="Calcium" value={`${nutrients.totals.calcium_mg} mg`} sub={`${nutrients.perDay.calcium_mg}/day`} tier={nutrients.tiers.calcium} />
                      <NutrientCard label="B12" value={`${nutrients.totals.b12_mcg} mcg`} sub={`${nutrients.perDay.b12_mcg}/day`} tier={nutrients.tiers.b12} />
                    </div>
                  </div>
                ) : null}
              </section>
            </div>

            {/* RIGHT PANEL */}
            <div className="space-y-4">
              {/* E — Safety score / actions */}
              <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700">{tr("safetyScore")}</h2>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-5xl font-extrabold text-slate-900 tabular-nums">{allFoods.length === 0 ? "100" : score.value}</div>
                  <div>
                    <div className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${
                      allFoods.length === 0 ? "bg-sky-100 text-sky-800" :
                      score.grade === "A" ? "bg-emerald-100 text-emerald-800" :
                      score.grade === "B" ? "bg-amber-100 text-amber-800" :
                      score.grade === "C" ? "bg-orange-100 text-orange-800" : "bg-rose-100 text-rose-800"
                    }`}>{allFoods.length === 0 ? "READY" : score.grade}</div>
                    <div className="text-xs text-slate-500 mt-1">{allFoods.length === 0 ? "No meal entries yet. Add foods to start interaction scoring." : `${score.hi} HIGH · ${score.med} MEDIUM`}</div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button onClick={savePlan} disabled={!selectedPatientId} className="flex items-center justify-center gap-1 px-3 py-2 border border-slate-300 disabled:opacity-50 rounded-md text-sm font-medium hover:bg-slate-100">
                    <Save className="w-4 h-4" />{tr("savePlan")}
                  </button>
                  <button onClick={runOptimize} disabled={optimizing || allFoods.length === 0} className="flex items-center justify-center gap-1 px-3 py-2 bg-emerald-600 disabled:bg-slate-300 text-white rounded-md text-sm font-medium">
                    <Wand2 className="w-4 h-4" />{optimizing ? tr("optimizing") : tr("optimize")}
                  </button>
                  <button onClick={runExport} disabled={allFoods.length === 0} className="flex items-center justify-center gap-1 px-3 py-2 border border-slate-300 disabled:opacity-50 rounded-md text-sm font-medium hover:bg-slate-100">
                    <Download className="w-4 h-4" />{tr("export")}
                  </button>
                </div>
                {saveNotice ? <div className="mt-2 text-xs text-emerald-700">{saveNotice}</div> : null}
                {allFoods.length > 0 ? (
                  <div className="mt-2 text-[11px] text-slate-500">
                    Score basis: 100 - (HIGH x 8) - (MEDIUM x 2), calculated from current foods against this patient's medications.
                  </div>
                ) : (
                  <div className="mt-2 text-[11px] text-slate-500">
                    Weekly plan is saved and ready. Add at least one food item to activate live interaction-based scoring.
                  </div>
                )}
                {substitutions.length > 0 ? (
                  <div className="mt-3 text-xs text-slate-600">
                    <div className="font-semibold text-slate-700 mb-1">Substitutions applied:</div>
                    <ul className="space-y-0.5">
                      {substitutions.map((s, i) => (
                        <li key={i}>• <span className="line-through opacity-60">{s.from}</span> → <span className="text-emerald-700 font-medium">{s.to}</span></li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </section>

              {/* D — Live feed */}
              <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
                <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-700 mb-3">{tr("feed")}</h2>
                {allFoods.length === 0 ? (
                  <div className="text-sm text-slate-500">{tr("emptyPlan")}</div>
                ) : flagged.length === 0 ? (
                  <div className="text-sm text-emerald-700 flex items-center gap-1"><span className="inline-block rounded-full bg-emerald-500" style={{ width: 10, height: 10 }} /> {tr("noFlag")}</div>
                ) : (
                  <ul className="space-y-2">
                    {flagged.sort((a, b) => (a.tier === "HIGH" ? -1 : 1) - (b.tier === "HIGH" ? -1 : 1)).map((f, i) => (
                      <li key={i} className={`rounded-md border p-2 ${tierBadge(f.tier)}`}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="text-[13px] font-semibold">
                              <span className={`inline-block rounded-full mr-1 align-middle ${tierDot(f.tier)}`} style={{ width: 10, height: 10 }} />
                              {f.foodName} × {f.drug}
                              {f.day ? <span className="ml-1 text-[10px] opacity-70">({f.day} {f.slot})</span> : null}
                            </div>
                            <div className="text-xs mt-0.5 opacity-90">{f.mechanism}</div>
                          </div>
                          {f.tier === "HIGH" ? (
                            <button onClick={() => showSubstitutes(f.food)} className="text-[11px] underline whitespace-nowrap">{tr("safeSubs")}</button>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        )}
      </main>

      {/* Substitutes modal */}
      {subSuggestions ? (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setSubSuggestions(null)}>
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-semibold text-slate-900">{tr("safeSubs")} — {subSuggestions.open}</div>
              <button onClick={() => setSubSuggestions(null)} className="p-1 hover:bg-slate-100 rounded"><X className="w-4 h-4" /></button>
            </div>
            {subSuggestions.items.length === 0 ? (
              <div className="text-sm text-slate-500">—</div>
            ) : (
              <ul className="space-y-2">
                {subSuggestions.items.map((s: any, i: number) => (
                  <li key={i} className="flex items-center justify-between gap-3 p-2 border border-slate-200 rounded-md">
                    <div>
                      <div className="text-sm font-medium text-slate-900">{s.name} {s.region === "NA" ? <span className="ml-1 text-[10px] bg-emerald-100 text-emerald-700 px-1 rounded">NA</span> : null}</div>
                      <div className="text-xs text-slate-500">{s.reason}</div>
                    </div>
                    <button onClick={() => applySub(subSuggestions.open, s.food_key)} className="text-xs px-2 py-1 rounded bg-emerald-600 text-white inline-flex items-center gap-1"><Plus className="w-3 h-3" />Apply</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function NutrientCard({ label, value, sub, tier }: { label: string; value: string; sub: string; tier: Tier }) {
  const cls = tier === "HIGH" ? "bg-rose-50 border-rose-200" :
              tier === "MEDIUM" ? "bg-amber-50 border-amber-200" : "bg-emerald-50 border-emerald-200";
  const txt = tier === "HIGH" ? "text-rose-700" :
              tier === "MEDIUM" ? "text-amber-700" : "text-emerald-700";
  return (
    <div className={`rounded-lg p-2 border ${cls}`}>
      <div className={`text-[10px] uppercase ${txt}`}>{label}</div>
      <div className={`text-base font-bold ${txt}`}>{value}</div>
      <div className="text-[10px] text-slate-500">{sub}</div>
    </div>
  );
}
