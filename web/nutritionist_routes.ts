/**
 * nutritionist_routes.ts — Nutritionist Dashboard backend.
 *
 * Endpoints (auth: role=nutritionist via /api/professional/auth):
 *   GET  /api/nutritionist/patient-context
 *   POST /api/nutritionist/meal-check
 *   GET  /api/nutritionist/weekly-nutrients
 *   GET  /api/nutritionist/safe-substitutes
 *   POST /api/nutritionist/optimize-meal
 *   POST /api/nutritionist/decompose-dish
 *   POST /api/nutritionist/export-meal-plan
 *   GET  /api/nutritionist/usage
 *   POST /api/nutritionist/upgrade-interest
 *
 * Tables created on register: food_nutrients, food_substitute_groups,
 * dish_recipes, nutritionist_meal_cache, nutritionist_usage,
 * nutritionist_upgrade_interest.
 */
import type express from "express";
import { FOODS, SUB_GROUPS, DISH_RECIPES, FOOD_TO_GROUPS, SYNERGY_RULES, FAST_TIERS } from "./nutritionist_data";

const defaultDfinderApiBase =
  process.env.NODE_ENV === "production" ? "https://healthopt-api.onrender.com" : "http://localhost:8000";
const dfinderApiBase = (process.env.DFINDER_API_URL || defaultDfinderApiBase).replace(/\/$/, "");

type Tier = "HIGH" | "MEDIUM" | "LOW" | "SAFE";
type ProfileLite = { id: string; role: string; name?: string; specialty?: string };
type Lang = "fr" | "en" | "ar";

export type NutritionistDeps = {
  app: express.Express;
  db: any;
  verifyNutritionist: (req: any) => ProfileLite | null;
  ai?: any;
};

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}
function normalizeDishKey(s: string): string {
  return String(s || "").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9 ]/g, "").trim().replace(/\s+/g, "_");
}

function vitaminKTier(perDay: number, anticoag: boolean): Tier {
  if (anticoag) return perDay > 250 ? "HIGH" : perDay > 150 ? "MEDIUM" : "LOW";
  return perDay < 20 ? "MEDIUM" : "LOW";
}
function ironTier(perDay: number, deficient: boolean): Tier {
  if (deficient) return perDay < 8 ? "HIGH" : perDay < 14 ? "MEDIUM" : "LOW";
  return perDay > 45 ? "MEDIUM" : "LOW";
}
function calciumTier(perDay: number, levothyrox: boolean): Tier {
  if (levothyrox && perDay > 1500) return "MEDIUM";
  return perDay > 2500 ? "MEDIUM" : "LOW";
}
function vitDTier(perDay: number, deficient: boolean): Tier {
  return deficient && perDay < 600 ? "MEDIUM" : "LOW";
}
function b12Tier(perDay: number, metformin: boolean): Tier {
  return metformin && perDay < 2.4 ? "MEDIUM" : "LOW";
}

export function registerNutritionistRoutes(deps: NutritionistDeps): void {
  const { app, db, verifyNutritionist, ai } = deps;

  db.exec(`
    CREATE TABLE IF NOT EXISTS food_nutrients (
      food_key TEXT PRIMARY KEY, name_fr TEXT, name_en TEXT, name_ar TEXT,
      category TEXT, vitamin_k_mcg REAL DEFAULT 0, iron_mg REAL DEFAULT 0,
      vitamin_d_iu REAL DEFAULT 0, calcium_mg REAL DEFAULT 0, b12_mcg REAL DEFAULT 0,
      region TEXT DEFAULT 'GL'
    );
    CREATE TABLE IF NOT EXISTS food_substitute_groups (
      group_key TEXT NOT NULL, food_key TEXT NOT NULL, rank INTEGER DEFAULT 0,
      PRIMARY KEY (group_key, food_key)
    );
    CREATE TABLE IF NOT EXISTS dish_recipes (
      dish_key TEXT PRIMARY KEY, name_fr TEXT, name_en TEXT, name_ar TEXT,
      components TEXT NOT NULL, source TEXT DEFAULT 'manual'
    );
    CREATE TABLE IF NOT EXISTS nutritionist_meal_cache (
      drug_key TEXT, food_key TEXT, tier TEXT, score REAL DEFAULT 0,
      mechanism TEXT, cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (drug_key, food_key)
    );
    CREATE TABLE IF NOT EXISTS nutritionist_usage (
      nutritionist_id TEXT PRIMARY KEY, patients_linked INTEGER DEFAULT 0,
      exports_this_month INTEGER DEFAULT 0,
      period_start TEXT DEFAULT (date('now','start of month')),
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS nutritionist_upgrade_interest (
      id INTEGER PRIMARY KEY AUTOINCREMENT, nutritionist_id TEXT NOT NULL,
      tier TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
  `);

  const seedFood = db.prepare(
    `INSERT INTO food_nutrients (food_key, name_fr, name_en, name_ar, category,
      vitamin_k_mcg, iron_mg, vitamin_d_iu, calcium_mg, b12_mcg, region)
     VALUES (@food_key, @name_fr, @name_en, @name_ar, @category,
       @vitamin_k_mcg, @iron_mg, @vitamin_d_iu, @calcium_mg, @b12_mcg, @region)
     ON CONFLICT(food_key) DO UPDATE SET
       name_fr=excluded.name_fr, name_en=excluded.name_en, name_ar=excluded.name_ar,
       category=excluded.category, vitamin_k_mcg=excluded.vitamin_k_mcg,
       iron_mg=excluded.iron_mg, vitamin_d_iu=excluded.vitamin_d_iu,
       calcium_mg=excluded.calcium_mg, b12_mcg=excluded.b12_mcg, region=excluded.region`,
  );
  const seedGroup = db.prepare(
    `INSERT INTO food_substitute_groups (group_key, food_key, rank) VALUES (?, ?, ?)
     ON CONFLICT(group_key, food_key) DO UPDATE SET rank=excluded.rank`,
  );
  const seedRecipe = db.prepare(
    `INSERT INTO dish_recipes (dish_key, name_fr, name_en, name_ar, components, source)
     VALUES (?, ?, ?, ?, ?, 'manual')
     ON CONFLICT(dish_key) DO UPDATE SET components=excluded.components`,
  );
  const tx = db.transaction(() => {
    for (const f of FOODS) seedFood.run(f);
    for (const gk of Object.keys(SUB_GROUPS)) {
      const foods: string[] = SUB_GROUPS[gk] || [];
      foods.forEach((fk: string, idx: number) => seedGroup.run(gk, fk, idx));
    }
    for (const dk of Object.keys(DISH_RECIPES)) {
      const rec = DISH_RECIPES[dk];
      seedRecipe.run(dk, rec.name_fr, rec.name_en, rec.name_ar, JSON.stringify(rec.components));
    }
  });
  tx();
  console.log(`Nutritionist KB seeded: ${FOODS.length} foods, ${Object.keys(SUB_GROUPS).length} groups, ${Object.keys(DISH_RECIPES).length} dishes.`);

  // ── Helpers ────────────────────────────────────────────────────────────
  const pickName = (row: any, lang: Lang) => String(row[`name_${lang}`] || row.name_en || row.food_key || "");

  function getPatientLink(proId: string, patientId: string): boolean {
    const row = db.prepare("SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?").get(proId, patientId);
    return !!row;
  }
  function getMeds(userId: string) {
    const out: Array<{ key: string; trade: string; inn: string; source: "manual" | "virtual"; severity?: string }> = [];
    try {
      const p = db.prepare("SELECT daily_medications FROM profile_by_user WHERE user_id = ?").get(userId) as any;
      for (const d of String(p?.daily_medications || "").split(",").map((s: string) => s.trim()).filter(Boolean)) {
        out.push({ key: d.toLowerCase(), trade: d, inn: d, source: "manual" });
      }
    } catch {}
    try {
      const vm = db.prepare("SELECT drug_name, public_label, severity FROM virtual_medications WHERE user_id = ? AND is_active = 1").all(userId) as any[];
      for (const v of vm) out.push({ key: String(v.drug_name || v.public_label || "").toLowerCase(), trade: String(v.public_label || v.drug_name || ""), inn: String(v.drug_name || ""), source: "virtual", severity: String(v.severity || "") });
    } catch {}
    const seen = new Set<string>();
    return out.filter((m) => m.key && !seen.has(m.key) && (seen.add(m.key), true));
  }
  function getVMSignals(userId: string) {
    try {
      return db.prepare("SELECT drug_name, public_label, signal_key, signal_reason, severity FROM virtual_medications WHERE user_id = ? AND is_active = 1").all(userId) as any[];
    } catch { return []; }
  }
  function findFood(q: string): any | null {
    const n = q.trim().toLowerCase();
    if (!n) return null;
    const ex = db.prepare("SELECT * FROM food_nutrients WHERE food_key = ?").get(n);
    if (ex) return ex;
    const like = `%${n}%`;
    return db.prepare("SELECT * FROM food_nutrients WHERE LOWER(name_fr) LIKE ? OR LOWER(name_en) LIKE ? OR name_ar LIKE ? LIMIT 1").get(like, like, `%${q.trim()}%`);
  }
  function fastTier(drug: string, foodKey: string, lang: Lang = "en"): { tier: Tier; score: number; mechanism: string } | null {
    const d = drug.toLowerCase(), f = foodKey.toLowerCase();
    for (const r of FAST_TIERS) {
      if (r.drug.test(d) && r.food.test(f)) {
        return { tier: r.tier, score: r.tier === "HIGH" ? 0.85 : r.tier === "MEDIUM" ? 0.5 : 0.2, mechanism: (r as any)[lang] || r.en };
      }
    }
    return null;
  }
  function cacheGet(drug: string, food: string) {
    const r = db.prepare("SELECT tier, score, mechanism FROM nutritionist_meal_cache WHERE drug_key=? AND food_key=?").get(drug.toLowerCase(), food.toLowerCase()) as any;
    return r ? { tier: r.tier as Tier, score: Number(r.score || 0), mechanism: String(r.mechanism || "") } : null;
  }
  function cachePut(drug: string, food: string, tier: Tier, score: number, mech: string) {
    db.prepare(`INSERT INTO nutritionist_meal_cache (drug_key, food_key, tier, score, mechanism, cached_at)
      VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(drug_key, food_key) DO UPDATE SET tier=excluded.tier, score=excluded.score, mechanism=excluded.mechanism, cached_at=excluded.cached_at`)
      .run(drug.toLowerCase(), food.toLowerCase(), tier, score, mech);
  }
  async function callPredict(drug: string, food: string, lang: Lang): Promise<{ tier: Tier; score: number; mechanism: string } | null> {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3500);
      const r = await fetch(`${dfinderApiBase}/predict`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ drug, food, language: lang }), signal: ctrl.signal,
      });
      clearTimeout(t);
      if (!r.ok) return null;
      const p: any = await r.json();
      const rt = String(p.confidence || p.tier || "LOW").toUpperCase();
      const tier: Tier = (rt === "HIGH" || rt === "MEDIUM" || rt === "LOW" || rt === "SAFE") ? (rt as Tier) : "LOW";
      return { tier, score: Number(p.score || 0), mechanism: String(p.explanation || p.mechanism || "") };
    } catch { return null; }
  }

  function ensureAuth(req: any, res: any): ProfileLite | null {
    const pro = verifyNutritionist(req);
    if (!pro) { res.status(401).json({ ok: false, detail: "Unauthorized." }); return null; }
    if ((pro.role || "").toLowerCase() !== "nutritionist") { res.status(403).json({ ok: false, detail: "Forbidden — nutritionist role required." }); return null; }
    return pro;
  }

  // ── /patient-context ───────────────────────────────────────────────────
  app.get("/api/nutritionist/patient-context", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.query.patientId || "").trim();
    if (!patientId) return res.status(400).json({ ok: false, detail: "patientId required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    const meds = getMeds(patientId);
    const vmSignals = getVMSignals(patientId);
    let cycle: any = null; try { cycle = db.prepare("SELECT * FROM cycle_logs WHERE user_id = ? ORDER BY start_date DESC LIMIT 1").get(patientId); } catch {}
    let last: any = null; try { last = db.prepare("SELECT date FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(patientId); } catch {}
    const alerts: any[] = [];
    for (const rule of SYNERGY_RULES) {
      const hitDrug = meds.find((m) => rule.drug_match.test(m.key + " " + m.trade + " " + m.inn));
      if (!hitDrug) continue;
      const hitSignal = rule.lab_signals.some((rx) => rx.source === ".*" || vmSignals.some((s) => rx.test(s.signal_key + " " + s.public_label)));
      if (hitSignal) alerts.push({ id: rule.id, severity: rule.severity, title: rule.title, advice: rule.advice });
    }
    alerts.sort((a, b) => (a.severity === "HIGH" ? -1 : 0) - (b.severity === "HIGH" ? -1 : 0));
    res.json({ ok: true, patientId, medications: meds, virtualSignals: vmSignals, cycle, lastBloodTest: last?.date || null, alerts: alerts.slice(0, 3) });
  });

  // ── /meal-check ────────────────────────────────────────────────────────
  app.post("/api/nutritionist/meal-check", async (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.body?.patientId || "").trim();
    const foods: string[] = Array.isArray(req.body?.foods) ? req.body.foods.map(String) : [];
    const lang: Lang = (req.body?.lang === "fr" || req.body?.lang === "ar") ? req.body.lang : "en";
    if (!patientId || foods.length === 0) return res.status(400).json({ ok: false, detail: "patientId and foods[] required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    const meds = getMeds(patientId);
    if (meds.length === 0) return res.json({ ok: true, results: [], note: "No medications on record." });
    const results: any[] = []; const seen = new Set<string>();
    for (const fr of foods) {
      const row = findFood(fr);
      const fk = row?.food_key || fr.trim().toLowerCase();
      const fn = row ? pickName(row, lang) : fr;
      for (const m of meds) {
        const dk = `${m.key}::${fk}`;
        if (seen.has(dk)) continue; seen.add(dk);
        const fast = fastTier(m.key, fk, lang) || fastTier(m.trade, fk, lang) || fastTier(m.inn, fk, lang);
        if (fast) { results.push({ food: fk, foodName: fn, drug: m.trade, tier: fast.tier, mechanism: fast.mechanism }); continue; }
        const c = cacheGet(m.key, fk);
        if (c) { results.push({ food: fk, foodName: fn, drug: m.trade, tier: c.tier, mechanism: c.mechanism, fromCache: true }); continue; }
        const py = await callPredict(m.inn || m.trade, fn, lang);
        if (py) { cachePut(m.key, fk, py.tier, py.score, py.mechanism); results.push({ food: fk, foodName: fn, drug: m.trade, tier: py.tier, mechanism: py.mechanism }); }
        else results.push({ food: fk, foodName: fn, drug: m.trade, tier: "SAFE", mechanism: "" });
      }
    }
    const flagged = results.filter((r) => r.tier === "HIGH" || r.tier === "MEDIUM" || (r.tier === "LOW" && r.mechanism));
    res.json({ ok: true, results: flagged, totalChecked: results.length });
  });

  // ── /weekly-nutrients ──────────────────────────────────────────────────
  app.get("/api/nutritionist/weekly-nutrients", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.query.patientId || "").trim();
    const foodsParam = String(req.query.foods || "");
    if (!patientId) return res.status(400).json({ ok: false, detail: "patientId required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    const foods = foodsParam.split(",").map((s) => s.trim()).filter(Boolean);
    const meds = getMeds(patientId); const vm = getVMSignals(patientId);
    const anti = meds.some((m) => /warfarin|acenocoum|sintrom|coumadin/i.test(m.key + m.trade + m.inn));
    const lvt = meds.some((m) => /levothyrox|levotiron|berlthyrox|euthyrox/i.test(m.key + m.trade + m.inn));
    const met = meds.some((m) => /metform|glucophage|diaguanid/i.test(m.key + m.trade + m.inn));
    const ironDef = vm.some((s) => /iron|ferrit/i.test(s.signal_key + " " + s.public_label));
    const vdDef = vm.some((s) => /vitamin.?d|cholecalciferol/i.test(s.signal_key + " " + s.public_label));
    let vk = 0, fe = 0, vd = 0, ca = 0, b12 = 0; const breakdown: any[] = [];
    for (const f of foods) {
      const r: any = findFood(f); if (!r) continue;
      vk += r.vitamin_k_mcg || 0; fe += r.iron_mg || 0; vd += r.vitamin_d_iu || 0; ca += r.calcium_mg || 0; b12 += r.b12_mcg || 0;
      breakdown.push({ food: r.food_key, vk: r.vitamin_k_mcg, fe: r.iron_mg, vd: r.vitamin_d_iu, ca: r.calcium_mg, b12: r.b12_mcg });
    }
    const d = 7;
    res.json({
      ok: true,
      totals: { vitamin_k_mcg: +(vk).toFixed(1), iron_mg: +(fe).toFixed(1), vitamin_d_iu: Math.round(vd), calcium_mg: Math.round(ca), b12_mcg: +(b12).toFixed(1) },
      perDay: { vitamin_k_mcg: +(vk / d).toFixed(1), iron_mg: +(fe / d).toFixed(1), vitamin_d_iu: Math.round(vd / d), calcium_mg: Math.round(ca / d), b12_mcg: +(b12 / d).toFixed(1) },
      tiers: { vitamin_k: vitaminKTier(vk / d, anti), iron: ironTier(fe / d, ironDef), vitamin_d: vitDTier(vd / d, vdDef), calcium: calciumTier(ca / d, lvt), b12: b12Tier(b12 / d, met) },
      patientContext: { hasAnticoag: anti, onLevothyrox: lvt, onMetformin: met, ironDeficient: ironDef, vitDDeficient: vdDef },
      breakdown,
    });
  });

  // ── /safe-substitutes ──────────────────────────────────────────────────
  app.get("/api/nutritionist/safe-substitutes", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.query.patientId || "").trim();
    const foodQ = String(req.query.food || "").trim();
    if (!patientId || !foodQ) return res.status(400).json({ ok: false, detail: "patientId and food required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    const tgt: any = findFood(foodQ); if (!tgt) return res.json({ ok: true, substitutes: [] });
    const groups = FOOD_TO_GROUPS[tgt.food_key] || [];
    if (groups.length === 0) return res.json({ ok: true, substitutes: [] });
    const meds = getMeds(patientId);
    const cands: string[] = Array.from(new Set(groups.flatMap((g: string) => SUB_GROUPS[g] || []))).filter((fk: string) => fk !== tgt.food_key);
    const worstFor = (fk: string): Tier => {
      let w: Tier = "LOW";
      for (const m of meds) {
        const ft = fastTier(m.key, fk) || fastTier(m.trade, fk) || fastTier(m.inn, fk);
        if (ft && (ft.tier === "HIGH" || (ft.tier === "MEDIUM" && w === "LOW"))) w = ft.tier;
      }
      return w;
    };
    const origWorst = worstFor(tgt.food_key);
    const subs: any[] = [];
    for (const fk of cands) {
      const w = worstFor(fk);
      const safer = (w === "LOW" && origWorst !== "LOW") || (w === "MEDIUM" && origWorst === "HIGH") || origWorst === "LOW";
      if (!safer) continue;
      const row: any = db.prepare("SELECT * FROM food_nutrients WHERE food_key=?").get(fk);
      if (!row) continue;
      subs.push({ food_key: row.food_key, name: pickName(row, "en"), region: row.region, tier: w, reason: w === "LOW" ? "Lower interaction tier" : "Reduced interaction tier" });
    }
    subs.sort((a, b) => {
      if (a.region === "NA" && b.region !== "NA") return -1;
      if (a.region !== "NA" && b.region === "NA") return 1;
      if (a.tier !== b.tier) return a.tier === "LOW" ? -1 : 1;
      return 0;
    });
    res.json({ ok: true, original: { food_key: tgt.food_key, name: pickName(tgt, "en") }, substitutes: subs.slice(0, 4) });
  });

  // ── /optimize-meal ─────────────────────────────────────────────────────
  app.post("/api/nutritionist/optimize-meal", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.body?.patientId || "").trim();
    const foods: string[] = Array.isArray(req.body?.foods) ? req.body.foods.map(String) : [];
    if (!patientId || foods.length === 0) return res.status(400).json({ ok: false, detail: "patientId and foods[] required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    const meds = getMeds(patientId);
    const subs: any[] = []; const out: string[] = [];
    for (const f of foods) {
      const row: any = findFood(f); if (!row) { out.push(f); continue; }
      let worst: Tier = "LOW", mech = "";
      for (const m of meds) {
        const ft = fastTier(m.key, row.food_key) || fastTier(m.trade, row.food_key) || fastTier(m.inn, row.food_key);
        if (ft && ft.tier === "HIGH") { worst = "HIGH"; mech = ft.mechanism; break; }
        if (ft && ft.tier === "MEDIUM" && worst === "LOW") { worst = "MEDIUM"; mech = ft.mechanism; }
      }
      if (worst !== "HIGH") { out.push(row.food_key); continue; }
      const groupsForFood: string[] = FOOD_TO_GROUPS[row.food_key] || [];
      const cands: string[] = Array.from(new Set(groupsForFood.flatMap((g: string) => SUB_GROUPS[g] || []))).filter((fk: string) => fk !== row.food_key);
      let chosen: string | null = null;
      for (const fk of cands) {
        let cw: Tier = "LOW";
        for (const m of meds) {
          const ft = fastTier(m.key, fk) || fastTier(m.trade, fk) || fastTier(m.inn, fk);
          if (ft && ft.tier !== "LOW" && ft.tier !== "SAFE") { cw = ft.tier; break; }
        }
        if (cw === "LOW") {
          const r: any = db.prepare("SELECT region FROM food_nutrients WHERE food_key=?").get(fk);
          if (r?.region === "NA") { chosen = fk; break; }
          if (!chosen) chosen = fk;
        }
      }
      if (chosen) { subs.push({ from: row.food_key, to: chosen, reason: mech }); out.push(chosen); }
      else out.push(row.food_key);
    }
    res.json({ ok: true, originalFoods: foods, optimizedFoods: out, substitutions: subs });
  });

  // ── /decompose-dish ────────────────────────────────────────────────────
  app.post("/api/nutritionist/decompose-dish", async (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const dish = String(req.body?.dish || "").trim();
    if (!dish) return res.status(400).json({ ok: false, detail: "dish required" });
    const key = normalizeDishKey(dish);
    const exact = db.prepare("SELECT * FROM dish_recipes WHERE dish_key = ?").get(key) as any;
    if (exact) return res.json({ ok: true, dish, components: JSON.parse(exact.components), source: exact.source });
    const like = `%${dish.toLowerCase().replace(/[%_]/g, "")}%`;
    const partial = db.prepare("SELECT * FROM dish_recipes WHERE LOWER(name_en) LIKE ? OR LOWER(name_fr) LIKE ? OR name_ar LIKE ? LIMIT 1").get(like, like, `%${dish}%`) as any;
    if (partial) return res.json({ ok: true, dish, components: JSON.parse(partial.components), source: partial.source });
    if (ai && process.env.GEMINI_API_KEY) {
      try {
        const known = FOODS.map((f) => f.food_key).join(", ");
        const prompt = `Decompose this North African/Mediterranean dish into pharmacologically relevant components.\nDish: "${dish}"\nUse ONLY these food_keys: ${known}\nReturn JSON: {"components": ["food_key", ...]} max 8. Omit water and salt.`;
        const r = await ai.models.generateContent({
          model: "gemini-2.0-flash",
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { responseMimeType: "application/json" },
        });
        const text = r.response?.text?.() || r.text || "";
        const m = text.match(/\{[\s\S]*\}/);
        if (m) {
          const obj = JSON.parse(m[0]);
          const comps = (Array.isArray(obj.components) ? obj.components : [])
            .filter((c: any) => typeof c === "string" && FOODS.some((f) => f.food_key === c));
          if (comps.length > 0) {
            db.prepare("INSERT INTO dish_recipes (dish_key, name_fr, name_en, name_ar, components, source) VALUES (?, ?, ?, ?, ?, 'gemini') ON CONFLICT(dish_key) DO UPDATE SET components=excluded.components, source='gemini'")
              .run(key, dish, dish, dish, JSON.stringify(comps));
            return res.json({ ok: true, dish, components: comps, source: "gemini" });
          }
        }
      } catch {}
    }
    res.json({ ok: true, dish, components: [], source: "unknown" });
  });

  // ── /export-meal-plan ──────────────────────────────────────────────────
  app.post("/api/nutritionist/export-meal-plan", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const patientId = String(req.body?.patientId || "").trim();
    const plan: any = req.body?.plan || {};
    const lang: Lang = (req.body?.lang === "fr" || req.body?.lang === "ar") ? req.body.lang : "en";
    if (!patientId) return res.status(400).json({ ok: false, detail: "patientId required" });
    if (!getPatientLink(pro.id, patientId)) return res.status(403).json({ ok: false, detail: "Patient not linked." });
    db.prepare(`INSERT INTO nutritionist_usage (nutritionist_id, patients_linked, exports_this_month, period_start, updated_at)
      VALUES (?, 0, 1, date('now','start of month'), CURRENT_TIMESTAMP)
      ON CONFLICT(nutritionist_id) DO UPDATE SET
        exports_this_month = CASE WHEN period_start = date('now','start of month') THEN exports_this_month + 1 ELSE 1 END,
        period_start = date('now','start of month'),
        updated_at = CURRENT_TIMESTAMP`).run(pro.id);
    const meds = getMeds(patientId);
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const slots = ["Breakfast", "Lunch", "Dinner", "Snacks"];
    const today = new Date().toISOString().slice(0, 10);
    const headTitle = lang === "fr" ? "Plan alimentaire personnalisé" : lang === "ar" ? "خطة غذائية شخصية" : "Personalized Meal Plan";
    const disclaimer = lang === "fr" ? "Généré par HealthOpt — à titre indicatif. Confirmez auprès du médecin."
      : lang === "ar" ? "تم إنشاؤها بواسطة HealthOpt — للاسترشاد فقط. استشر طبيبك." : "Generated by HealthOpt — for reference only. Confirm with physician.";
    let rows = "";
    for (const slot of slots) {
      let r = `<tr><th style="text-align:left;padding:6px;background:#f1f5f9;">${slot}</th>`;
      for (const d of days) {
        const items: string[] = Array.isArray(plan?.[d]?.[slot]) ? plan[d][slot] : [];
        const inner = items.length ? items.map((it) => `<div style="font-size:11px;line-height:1.3">${escapeHtml(it)}</div>`).join("") : "&mdash;";
        r += `<td style="border:1px solid #e2e8f0;padding:6px;vertical-align:top;min-width:90px;">${inner}</td>`;
      }
      rows += r + "</tr>";
    }
    const medList = meds.map((m) => `<li>${escapeHtml(m.trade)} <span style="color:#64748b">(${escapeHtml(m.inn)})</span></li>`).join("");
    const headDays = days.map((d) => `<th style="background:#f1f5f9;padding:6px;font-size:11px;">${d}</th>`).join("");
    const qr = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent("https://healthopt.app")}`;
    const html = `<!doctype html>
<html lang="${lang}" dir="${lang === "ar" ? "rtl" : "ltr"}">
<head><meta charset="utf-8"/><title>${headTitle}</title>
<style>
body{font-family:'Segoe UI',Tahoma,sans-serif;color:#0f172a;padding:20px}
h1{font-size:18px;margin:0 0 6px}
h2{font-size:13px;margin:18px 0 6px;color:#334155;text-transform:uppercase;letter-spacing:.08em}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #e2e8f0}
.footer{margin-top:18px;font-size:10px;color:#64748b;border-top:1px dashed #cbd5e1;padding-top:8px}
.header{display:flex;justify-content:space-between;align-items:flex-start}
</style></head>
<body>
<div class="header">
<div><div style="font-weight:800;font-size:14px;">HealthOpt</div><h1>${headTitle}</h1>
<div style="font-size:11px;color:#475569;">${today} &middot; ${escapeHtml(pro.name || "")}</div></div>
<img src="${qr}" alt="QR" width="80" height="80"/></div>
<h2>${lang === "fr" ? "Médicaments actuels" : lang === "ar" ? "الأدوية الحالية" : "Current medications"}</h2>
<ul style="margin:4px 0 0 16px;padding:0;font-size:12px;">${medList || `<li style="color:#94a3b8">&mdash;</li>`}</ul>
<h2>${lang === "fr" ? "Plan hebdomadaire" : lang === "ar" ? "الخطة الأسبوعية" : "Weekly plan"}</h2>
<table><thead><tr><th style="background:#f1f5f9;padding:6px;font-size:11px;">&nbsp;</th>${headDays}</tr></thead><tbody>${rows}</tbody></table>
<div class="footer">${disclaimer}</div>
</body></html>`;
    res.json({ ok: true, html });
  });

  // ── /usage ─────────────────────────────────────────────────────────────
  app.get("/api/nutritionist/usage", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const row = db.prepare("SELECT * FROM nutritionist_usage WHERE nutritionist_id = ?").get(pro.id) as any;
    const c = (db.prepare("SELECT COUNT(1) AS c FROM professional_patient_links WHERE professional_id = ?").get(pro.id) as any)?.c || 0;
    const currentPeriod = new Date().toISOString().slice(0, 8) + "01";
    const inPeriod = row && String(row.period_start || "") === currentPeriod;
    res.json({
      ok: true,
      patientsLinked: c,
      patientsLimit: 2,
      exportsThisMonth: inPeriod ? Number(row.exports_this_month || 0) : 0,
      exportsLimit: 1,
      atPatientLimit: c >= 2,
      atExportLimit: (inPeriod ? Number(row.exports_this_month || 0) : 0) >= 1,
    });
  });

  // ── /upgrade-interest ──────────────────────────────────────────────────
  app.post("/api/nutritionist/upgrade-interest", (req, res) => {
    const pro = ensureAuth(req, res); if (!pro) return;
    const tier = String(req.body?.tier || "pro").trim().toLowerCase();
    db.prepare("INSERT INTO nutritionist_upgrade_interest (nutritionist_id, tier) VALUES (?, ?)").run(pro.id, tier);
    res.json({ ok: true });
  });
}
