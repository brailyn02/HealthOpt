import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { createHmac, randomUUID } from "crypto";
import fs from "fs";
import { spawnSync } from "child_process";
import Database from "better-sqlite3";
import { GoogleGenAI, Type } from "@google/genai";
import { inflateRawSync, inflateSync } from "zlib";
import { registerPharmacistRoutes } from "./pharmacist_routes";
import { registerNutritionistRoutes } from "./nutritionist_routes";

const sqliteBusyTimeoutMs = Number(process.env.SQLITE_BUSY_TIMEOUT_MS || 10000);
const sqlitePath = "healthopt.db";

function openHealthyDatabase(): Database.Database {
  const db = new Database(sqlitePath, { timeout: sqliteBusyTimeoutMs });
  const integrity = db.pragma("integrity_check", { simple: true }) as unknown;
  if (String(integrity || "").toLowerCase() !== "ok") {
    throw new Error(`SQLite integrity_check failed: ${String(integrity)}`);
  }
  return db;
}

let db: Database.Database;
try {
  db = openHealthyDatabase();
} catch (error) {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const backupPath = `${sqlitePath}.corrupt.${stamp}`;
  try {
    if (fs.existsSync(sqlitePath)) {
      fs.copyFileSync(sqlitePath, backupPath);
      fs.unlinkSync(sqlitePath);
      console.error(`Backed up corrupted SQLite DB to ${backupPath}`);
    }
  } catch (backupError) {
    console.error("Failed to back up corrupted SQLite DB:", backupError);
  }
  console.error("Recreating SQLite database after corruption detection:", error);
  db = new Database(sqlitePath, { timeout: sqliteBusyTimeoutMs });
}
db.pragma("journal_mode = WAL");
db.pragma("synchronous = NORMAL");
db.pragma("foreign_keys = ON");
db.pragma("temp_store = MEMORY");
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

// Prevent unhandled promise rejections from crashing the server
process.on("unhandledRejection", (reason, promise) => {
  console.error("Unhandled Rejection:", reason instanceof Error ? reason.message : reason);
  if (reason instanceof Error && reason.stack) {
    console.error("Stack:", reason.stack);
  }
});

process.on("uncaughtException", (error) => {
  console.error("Uncaught Exception:", error);
  process.exit(1);
});

const USER_COOKIE = "healthopt_uid";
const FREE_DAILY_SCAN_LIMIT = 3;

const BLOOD_BIOMARKER_FIELDS = [
  "ferritin",
  "hemoglobin",
  "vitaminD",
  "calcium",
  "b12",
  "magnesium",
  "zinc",
  "folate",
  "iode_urinaire",
  "albumine",
  "tsh",
  "glycemie_jejun",
  "hba1c",
  "triglycerides",
  "ldl",
  "ratio_albumine_creatinine",
] as const;

const BLOOD_FIELD_ALIASES: Record<BiomarkerField, string[]> = {
  ferritin: ["ferritin", "ferritine", "ferritinemie"],
  hemoglobin: ["hemoglobin", "hemoglobine", "hgb"],
  vitaminD: ["vitamin d", "vitamine d", "25 hydroxyvitamine d", "25-hydroxyvitamine d", "25 oh vitamine d"],
  calcium: ["calcium"],
  b12: ["vitamin b12", "vit b12", "b12", "cobalamine"],
  magnesium: ["magnesium"],
  zinc: ["zinc"],
  folate: ["folate", "acide folique", "folates"],
  iode_urinaire: ["iode urinaire", "iode_urinaire"],
  albumine: ["albumine"],
  tsh: ["tsh", "tsh 3eme generation", "tsh 3e generation", "thyroid stimulating hormone"],
  glycemie_jejun: ["glycemie a jeun", "glycemie jeun", "glucose a jeun", "fasting glucose"],
  hba1c: [
    "hba1c",
    "hemoglobine glycosylee",
    "hemoglobine glycosyle",
    "hemoglobine glyquee",
    "hemoglobin glycosylated",
    "glycohemoglobine",
    "a1c",
  ],
  triglycerides: ["triglycerides"],
  ldl: ["ldl", "cholesterol ldl", "cholesterol-ldl", "cholesterol ldl"],
  ratio_albumine_creatinine: ["ratio albumine creatinine", "albumine creatinine", "acr"],
};

type BiomarkerField = typeof BLOOD_BIOMARKER_FIELDS[number];

type DeficiencySignal = {
  key: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  reason: string;
  virtualDrug: string;
  publicLabel: string;
};

type Model2LabelPrediction = {
  ok: boolean;
  prob?: number;
  threshold?: number;
  positive?: boolean;
  test_auc?: number;
  gap?: number;
  status?: string;
  error?: string;
};

type Model2InferenceResult = {
  integrated: boolean;
  runnerOk: boolean;
  runnerError?: string;
  predictions: Record<string, Model2LabelPrediction>;
};

type DrugClassAlternative = {
  class_label: string;
  members: string[];
  algerian_trade_names: Record<string, string[]>;
  cyp_primary: string[];
  therapeutic_note: string;
  cross_class_options: Array<{
    target_class_id: string;
    clinical_condition: string;
    cross_class_note: string;
  }>;
};

const DRUG_CLASS_ALTERNATIVES: Record<string, DrugClassAlternative> = {
  anticoagulant_vka: {
    class_label: "VKA Anticoagulant",
    members: ["warfarin", "acenocoumarol", "phenprocoumon"],
    algerian_trade_names: {
      warfarin: ["Coumadine"],
      acenocoumarol: ["Sintrom"],
      phenprocoumon: ["Marcoumar"],
    },
    cyp_primary: ["CYP2C9"],
    therapeutic_note: "All VKAs require INR monitoring. Switching requires careful dose titration and bridge therapy. Consult haematology before substitution.",
    cross_class_options: [
      {
        target_class_id: "anticoagulant_doac",
        clinical_condition: "Patient has documented dietary non-adherence or high Vitamin K food intake",
        cross_class_note: "VKA → DOAC is a valid clinical pathway for eligible patients. Requires specialist evaluation, renal function check, and bridging protocol.",
      },
    ],
  },
  anticoagulant_doac: {
    class_label: "DOAC Anticoagulant",
    members: ["apixaban", "rivaroxaban", "dabigatran", "edoxaban"],
    algerian_trade_names: {
      apixaban: ["Eliquis"],
      rivaroxaban: ["Xarelto"],
      dabigatran: ["Pradaxa"],
      edoxaban: ["Lixiana"],
    },
    cyp_primary: ["CYP3A4"],
    therapeutic_note: "DOACs have fewer food interactions than VKAs. No routine INR monitoring required.",
    cross_class_options: [],
  },
  statin: {
    class_label: "Statin (HMG-CoA reductase inhibitor)",
    members: ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "fluvastatin", "pitavastatin"],
    algerian_trade_names: {
      atorvastatin: ["Tahor", "Lipitor"],
      simvastatin: ["Zocor", "Lodales"],
      rosuvastatin: ["Crestor"],
      pravastatin: ["Elisor", "Vasten"],
      fluvastatin: ["Lescol"],
      pitavastatin: ["Livalo"],
    },
    cyp_primary: ["CYP3A4"],
    therapeutic_note: "Pravastatin and rosuvastatin are least CYP3A4-dependent — better choice for patients consuming grapefruit or CYP3A4-inhibiting foods regularly.",
    cross_class_options: [],
  },
  ppi: {
    class_label: "Proton Pump Inhibitor",
    members: ["omeprazole", "pantoprazole", "lansoprazole", "esomeprazole", "rabeprazole"],
    algerian_trade_names: {
      omeprazole: ["Mopral", "Zoltum"],
      pantoprazole: ["Inipomp", "Eupantol"],
      lansoprazole: ["Lanzopral"],
      esomeprazole: ["Inexium"],
      rabeprazole: ["Pariet"],
    },
    cyp_primary: ["CYP2C19"],
    therapeutic_note: "Rabeprazole is least CYP2C19-dependent — better fit for patients on multiple CYP2C19-sensitive drugs.",
    cross_class_options: [],
  },
  ace_inhibitor: {
    class_label: "ACE Inhibitor",
    members: ["lisinopril", "enalapril", "captopril", "ramipril", "perindopril", "fosinopril"],
    algerian_trade_names: {
      lisinopril: ["Zestril", "Prinivil"],
      ramipril: ["Triatec"],
      perindopril: ["Coversyl"],
      enalapril: ["Renitec"],
      captopril: ["Capoten"],
      fosinopril: ["Staril"],
    },
    cyp_primary: [],
    therapeutic_note: "ACE inhibitors share a class-wide potassium overload risk with high-K diets. Switching within class does not resolve this. Consider ARB class for dietary K+ concerns.",
    cross_class_options: [
      {
        target_class_id: "arb",
        clinical_condition: "Patient has high dietary potassium intake or documented ACE inhibitor-related dietary conflict",
        cross_class_note: "ARBs carry lower K+ accumulation risk than ACE inhibitors in most patients. Class switch requires clinical assessment.",
      },
    ],
  },
  arb: {
    class_label: "Angiotensin Receptor Blocker",
    members: ["losartan", "valsartan", "irbesartan", "olmesartan", "telmisartan", "candesartan"],
    algerian_trade_names: {
      losartan: ["Cozaar", "Lortaan"],
      valsartan: ["Nisis", "Tareg"],
      irbesartan: ["Aprovel"],
      olmesartan: ["Olmetec"],
      telmisartan: ["Micardis"],
      candesartan: ["Atacand"],
    },
    cyp_primary: ["CYP2C9"],
    therapeutic_note: "ARBs generally lower K+ accumulation risk than ACE inhibitors. Similar efficacy profile for most hypertension indications.",
    cross_class_options: [],
  },
  ssri: {
    class_label: "SSRI Antidepressant",
    members: ["fluoxetine", "sertraline", "paroxetine", "escitalopram", "citalopram", "fluvoxamine"],
    algerian_trade_names: {
      fluoxetine: ["Prozac"],
      sertraline: ["Zoloft"],
      paroxetine: ["Deroxat"],
      escitalopram: ["Seroplex", "Lexapro"],
      citalopram: ["Seropram"],
      fluvoxamine: ["Floxyfral"],
    },
    cyp_primary: ["CYP2D6", "CYP2C19", "CYP3A4"],
    therapeutic_note: "SSRIs vary significantly in CYP inhibition profile. Escitalopram and sertraline have the fewest CYP interactions — better choice for polypharmacy patients.",
    cross_class_options: [],
  },
  fluoroquinolone: {
    class_label: "Fluoroquinolone Antibiotic",
    members: ["ciprofloxacin", "ofloxacin", "levofloxacin", "moxifloxacin"],
    algerian_trade_names: {
      ciprofloxacin: ["Ciflox", "Ciprobay"],
      ofloxacin: ["Tarivid"],
      levofloxacin: ["Tavanic"],
      moxifloxacin: ["Avelox"],
    },
    cyp_primary: ["CYP1A2"],
    therapeutic_note: "All fluoroquinolones chelate with divalent cations (Ca2+, Mg2+, Fe2+, Zn2+). This is a class-wide interaction — switching within class does not resolve it. Use dietary timing instead.",
    cross_class_options: [],
  },
  biguanide: {
    class_label: "Biguanide Antidiabetic",
    members: ["metformin"],
    algerian_trade_names: {
      metformin: ["Glucophage", "Stagid"],
    },
    cyp_primary: [],
    therapeutic_note: "No intra-class alternatives exist. If GI food interactions are problematic, consider extended-release formulation (Glucophage XR) — better GI tolerability with meals.",
    cross_class_options: [],
  },
};

declare global {
  namespace Express {
    interface Request {
      userId?: string;
    }
  }
}

function getCookieValue(cookieHeader: string | undefined, cookieName: string): string | null {
  if (!cookieHeader) return null;
  const parts = cookieHeader.split(";").map((v) => v.trim());
  const prefix = `${cookieName}=`;
  const raw = parts.find((p) => p.startsWith(prefix));
  if (!raw) return null;
  const value = raw.slice(prefix.length);
  return value ? decodeURIComponent(value) : null;
}

function resolveUserId(req: express.Request, res: express.Response): string {
  const fromHeader = typeof req.headers["x-user-id"] === "string" ? req.headers["x-user-id"].trim() : "";
  const fromCookie = getCookieValue(req.headers.cookie, USER_COOKIE) || "";
  const existingId = fromHeader || fromCookie;
  if (existingId) return existingId;

  const generated = randomUUID();
  res.setHeader(
    "Set-Cookie",
    `${USER_COOKIE}=${encodeURIComponent(generated)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000`
  );
  return generated;
}

function ensureColumn(table: string, columnDef: string) {
  try {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${columnDef}`);
  } catch (error) {
    const msg = String((error as Error).message || "").toLowerCase();
    if (!msg.includes("duplicate column name")) throw error;
  }
}

// Initialize Database
db.exec(`
  CREATE TABLE IF NOT EXISTS blood_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    date TEXT DEFAULT CURRENT_TIMESTAMP,
    ferritin REAL,
    hemoglobin REAL,
    vitaminD REAL,
    calcium REAL,
    b12 REAL,
    magnesium REAL,
    zinc REAL,
    folate REAL,
    iode_urinaire REAL,
    albumine REAL,
    tsh REAL,
    glycemie_jejun REAL,
    hba1c REAL,
    triglycerides REAL,
    ldl REAL,
    ratio_albumine_creatinine REAL
  );

  CREATE TABLE IF NOT EXISTS cycle_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    start_date TEXT,
    duration INTEGER DEFAULT 28,
    period_length INTEGER DEFAULT 5
  );

  CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    gender TEXT DEFAULT 'female',
    daily_medications TEXT DEFAULT ''
  );

  INSERT OR IGNORE INTO profile (id, gender, daily_medications) VALUES (1, 'female', '');

  CREATE TABLE IF NOT EXISTS interaction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    drug TEXT,
    food TEXT,
    tier TEXT,
    score REAL,
    mechanism TEXT,
    consumed INTEGER DEFAULT 0,
    consumed_at TEXT
  );

  CREATE TABLE IF NOT EXISTS profile_by_user (
    user_id TEXT PRIMARY KEY,
    gender TEXT DEFAULT 'female',
    age INTEGER,
    daily_medications TEXT DEFAULT '',
    plan TEXT DEFAULT 'free'
  );

  CREATE TABLE IF NOT EXISTS auth_accounts (
    email TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    plan TEXT DEFAULT 'free',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS user_auth_link (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    linked_at TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS scan_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    scanned_at TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS virtual_medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    public_label TEXT NOT NULL,
    signal_key TEXT NOT NULL,
    signal_reason TEXT,
    severity TEXT DEFAULT 'MEDIUM',
    source_model TEXT DEFAULT 'model2_clinical_v1',
    is_active INTEGER DEFAULT 1,
    is_hidden INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, signal_key)
  );

  CREATE TABLE IF NOT EXISTS professional_accounts (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    pin_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    specialty TEXT DEFAULT '',
    linked_patients TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS professional_patient_links (
    professional_id TEXT NOT NULL,
    patient_user_id TEXT NOT NULL,
    patient_alias TEXT,
    linked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (professional_id, patient_user_id)
  );

  CREATE TABLE IF NOT EXISTS patient_share_codes (
    user_id TEXT PRIMARY KEY,
    share_code TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
`);

// Additional tables for clinicians, labs, referrals, and pharmacy counseling
db.exec(`
  CREATE TABLE IF NOT EXISTS clinicians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    license TEXT,
    contact TEXT
  );

  CREATE TABLE IF NOT EXISTS labs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    address TEXT,
    city TEXT,
    lat REAL,
    lon REAL,
    partnership INTEGER DEFAULT 0,
    discount_code TEXT,
    contact TEXT
  );

  CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    recommended_tests TEXT,
    lab_id INTEGER,
    status TEXT DEFAULT 'pending'
  );

  CREATE TABLE IF NOT EXISTS counseling_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pharmacist_id TEXT,
    user_id TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    trade_name TEXT,
    generic_name TEXT,
    advice TEXT,
    language TEXT
  );

  CREATE TABLE IF NOT EXISTS user_referral_dismissals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    trigger_type TEXT,
    dismissed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    snoozed_until TEXT
  );
`);

try {
  const count = db.prepare("SELECT COUNT(1) AS c FROM professional_accounts").get() as any;
  if (!count || Number(count.c || 0) === 0) {
    const insert = db.prepare(
      "INSERT INTO professional_accounts (id, role, pin_hash, name, specialty, linked_patients) VALUES (?, ?, ?, ?, ?, ?)"
    );
    insert.run("doctor-demo", "doctor", hashProfessionalPin("123456"), "Demo Doctor", "Internal Medicine", "[]");
    insert.run("pharmacist-demo", "pharmacist", hashProfessionalPin("234567"), "Demo Pharmacist", "Clinical Pharmacy", "[]");
    insert.run("nutritionist-demo", "nutritionist", hashProfessionalPin("345678"), "Demo Nutritionist", "Clinical Nutrition", "[]");
  }
} catch (e) {
  console.error("Failed to seed professional accounts", e);
}

// Seed a few partner labs if none exist (small, static for now)
try {
  const count = db.prepare("SELECT COUNT(1) AS c FROM labs").get();
  if (!count || Number(count.c || 0) === 0) {
    const insert = db.prepare(
      `INSERT INTO labs (name, address, city, lat, lon, partnership, discount_code, contact) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    );
    insert.run('Laboratoire El Kheir Constantine', 'Rue Didouche Mourad', 'Constantine', 36.365, 6.614, 1, 'HOPT-CON-10', '021-000-111');
    insert.run('Laboratoire El Djazaïr', 'Algiers Centre', 'Algiers', 36.7538, 3.0588, 1, 'HOPT-ALG-10', '021-000-222');
    insert.run('Laboratoire Oran Santé', 'Oran Main St', 'Oran', 35.6971, -0.6308, 1, 'HOPT-ORN-10', '021-000-333');
  }
} catch (e) {
  console.error('Failed to seed labs', e);
}

// Load Algerian trade-name CSV into memory for fast pharmacy lookup
let tradeNameIndex: Array<{brand_name:string;inn_raw:string;inn_normalized:string;pipeline_drug:string;match_type:string}> = [];
try {
  const candidatePaths = [
    path.join(process.cwd(), 'algerian_brand_map.csv'),
    path.join(process.cwd(), '..', 'algerian_brand_map.csv'),
  ];
  const csvPath = candidatePaths.find((p) => fs.existsSync(p));
  if (csvPath) {
    const raw = fs.readFileSync(csvPath, 'utf-8');
    const lines = raw.split(/\r?\n/).filter(Boolean);
    const header = lines.shift() || '';
    for (const line of lines) {
      const parts = line.split(',');
      if (parts.length < 5) continue;
      tradeNameIndex.push({
        brand_name: parts[0].trim(),
        inn_raw: parts[1].trim(),
        inn_normalized: parts[2].trim(),
        pipeline_drug: parts[3].trim(),
        match_type: parts[4].trim(),
      });
    }
  }
} catch (e) {
  console.error('Failed to load trade name CSV', e);
}

function haversineDistanceKm(lat1:number, lon1:number, lat2:number, lon2:number) {
  const toRad = (v:number) => (v * Math.PI) / 180;
  const R = 6371; // km
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}
// Register extra routes (pharmacy, referrals) inside server startup
function registerExtraRoutes(app: any) {
  // Pharmacy: trade-name search
  app.get('/api/trade-names/search', (req: any, res: any) => {
    const q = String(req.query.q || '').trim().toLowerCase();
    if (!q) return res.json([]);
    const matches = tradeNameIndex.filter((t) => t.brand_name.toLowerCase().includes(q) || t.pipeline_drug.toLowerCase().includes(q));
    res.json(matches.slice(0, 25));
  });

  // Pharmacy: quick scan endpoint
  app.post('/api/pharmacy/scan', (req: any, res: any) => {
    const trade = String(req.body?.tradeName || '').trim();
    if (!trade) return res.status(400).json({ detail: 'Missing tradeName' });
    const found = tradeNameIndex.find((t) => t.brand_name.toLowerCase() === trade.toLowerCase()) || tradeNameIndex.find((t) => trade.toLowerCase().includes(t.brand_name.toLowerCase())) || null;
    if (!found) return res.status(404).json({ detail: 'Not found' });
    res.json({ trade: found.brand_name, generic: found.pipeline_drug || found.inn_normalized, match_type: found.match_type });
  });

  // Pharmacy: record counseling event
  app.post('/api/pharmacy/counsel', (req: any, res: any) => {
    const pharmacistId = String(req.body?.pharmacistId || '');
    const userId = String(req.body?.userId || req.userId || '');
    const tradeName = String(req.body?.tradeName || '');
    const genericName = String(req.body?.genericName || '');
    const advice = String(req.body?.advice || '');
    const language = String(req.body?.language || 'fr');
    try {
      db.prepare(`INSERT INTO counseling_events (pharmacist_id, user_id, trade_name, generic_name, advice, language) VALUES (?, ?, ?, ?, ?, ?)`)
        .run(pharmacistId, userId, tradeName, genericName, advice, language);
      res.json({ ok: true });
    } catch (e) {
      console.error('Failed to record counseling event', e);
      res.status(500).json({ error: 'failed' });
    }
  });

  // Labs: nearby partner labs
  app.get('/api/referrals/nearby', (req: any, res: any) => {
    const lat = Number(req.query.lat || '');
    const lon = Number(req.query.lon || '');
    const radiusKm = Number(req.query.radius_km || '50');
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return res.status(400).json({ detail: 'Missing lat/lon' });
    try {
      const labs = db.prepare('SELECT * FROM labs WHERE partnership = 1').all() as any[];
      const annotated = labs.map((l) => ({ ...l, distance_km: haversineDistanceKm(lat, lon, Number(l.lat || 0), Number(l.lon || 0)) }));
      const filtered = annotated.filter((a) => Number(a.distance_km) <= radiusKm).sort((a, b) => a.distance_km - b.distance_km);
      res.json(filtered.slice(0, 20));
    } catch (e) {
      console.error('Failed to query labs', e);
      res.status(500).json({ error: 'failed' });
    }
  });

  // Create referral (assigns nearest partner lab if lat/lon provided)
  app.post('/api/referrals/create', (req: any, res: any) => {
    const userId = String(req.body?.userId || req.userId || '');
    const reason = String(req.body?.reason || '');
    const tests = Array.isArray(req.body?.recommended_tests) ? req.body.recommended_tests.join(', ') : String(req.body?.recommended_tests || '');
    const lat = Number(req.body?.lat || '');
    const lon = Number(req.body?.lon || '');
    try {
      let labId: number | null = null;
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        const labs = db.prepare('SELECT * FROM labs WHERE partnership = 1').all() as any[];
        const nearest = labs.map((l) => ({ ...l, distance_km: haversineDistanceKm(lat, lon, Number(l.lat || 0), Number(l.lon || 0)) })).sort((a, b) => a.distance_km - b.distance_km)[0];
        if (nearest) labId = nearest.id;
      }
      const info = db.prepare('INSERT INTO referrals (user_id, reason, recommended_tests, lab_id) VALUES (?, ?, ?, ?)').run(userId, reason, tests, labId as any);
      res.json({ ok: true, referral_id: info.lastInsertRowid, lab_id: labId });
    } catch (e) {
      console.error('Failed to create referral', e);
      res.status(500).json({ error: 'failed' });
    }
  });

  // Helper: create referral programmatically
  function createReferralRecord(userId: string, reason: string, recommendedTests: string[], lat?: number, lon?: number) {
    try {
      let labId: number | null = null;
      if (Number.isFinite(lat || NaN) && Number.isFinite(lon || NaN)) {
        const labs = db.prepare('SELECT * FROM labs WHERE partnership = 1').all() as any[];
        const nearest = labs.map((l) => ({ ...l, distance_km: haversineDistanceKm(lat || 0, lon || 0, Number(l.lat || 0), Number(l.lon || 0)) })).sort((a, b) => a.distance_km - b.distance_km)[0];
        if (nearest) labId = nearest.id;
      }
      const tests = Array.isArray(recommendedTests) ? recommendedTests.join(', ') : String(recommendedTests || '');
      const info = db.prepare('INSERT INTO referrals (user_id, reason, recommended_tests, lab_id) VALUES (?, ?, ?, ?)').run(userId, reason, tests, labId as any);
      return { ok: true, referral_id: info.lastInsertRowid, lab_id: labId };
    } catch (e) {
      console.error('createReferralRecord failed', e);
      return { ok: false, error: String(e) };
    }
  }

  // Check triggers and create referrals if needed for a user
  app.post('/api/referrals/check', (req: any, res: any) => {
    const userId = String(req.body?.userId || req.userId || '');
    const lat = typeof req.body?.lat === 'number' ? Number(req.body.lat) : Number(req.body?.lat || '');
    const lon = typeof req.body?.lon === 'number' ? Number(req.body.lon) : Number(req.body?.lon || '');
    if (!userId) return res.status(400).json({ detail: 'Missing userId' });

    try {
      const now = Date.now();
      const resultActions: any[] = [];

      // Time-based trigger: check latest blood test age for users on high-risk virtual meds
      const vmRows = db.prepare('SELECT drug_name, public_label, severity FROM virtual_medications WHERE user_id = ? AND is_active = 1').all(userId) as any[];
      if (vmRows && vmRows.length > 0) {
        const latestTest = db.prepare("SELECT date FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(userId) as any;
        let ageDays = null;
        if (latestTest?.date) {
          ageDays = Math.floor((now - new Date(latestTest.date).getTime()) / (1000 * 60 * 60 * 24));
        }

        for (const vm of vmRows) {
          const drug = String(vm.drug_name || '').toLowerCase();
          const severity = String(vm.severity || '').toUpperCase();
          // For anticoagulants (acenocoumarol / sintrom) recommend PT/INR if blood data older than 90 days
          if (drug.includes('acenocoumarol') || drug.includes('sintrom') || drug.includes('warfarin') || drug.includes('acenocoumarol')) {
            const thresholdDays = 90; // 3 months
            if (!ageDays || ageDays >= thresholdDays) {
              const r = createReferralRecord(userId, 'Stale INR data for anticoagulant therapy', ['Prothrombin time (PT/INR)'], Number.isFinite(lat) ? lat : undefined, Number.isFinite(lon) ? lon : undefined);
              resultActions.push({ trigger: 'time_based_inr', ageDays, severity, created: r });
            }
          }

          // For virtual nutrient signals, e.g., Iron or Ferritin, recommend ferritin if older than 180 days
          if (String(vm.public_label || '').toLowerCase().includes('iron') || String(vm.signal_key || '').toLowerCase().includes('ferrit')) {
            const thresholdDays = 180;
            if (!ageDays || ageDays >= thresholdDays) {
              const r = createReferralRecord(userId, 'Stale iron marker data', ['Ferritin'], Number.isFinite(lat) ? lat : undefined, Number.isFinite(lon) ? lon : undefined);
              resultActions.push({ trigger: 'time_based_iron', ageDays, severity, created: r });
            }
          }
        }
      }

      // Frequency-based trigger: recent interaction history suggesting deficiency risk
      // Count interactions in last 30 days that mention iron/ferritin in mechanism or food
      const since30 = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
      const rows = db.prepare('SELECT food, mechanism, timestamp FROM interaction_history WHERE user_id = ? AND timestamp >= ?').all(userId, since30) as any[];
      const ironMatches = (rows || []).filter(r => {
        const text = String((r.food || '') + ' ' + (r.mechanism || '')).toLowerCase();
        return /iron|ferrit|ferritine|ferro|ferrous|hemoglobin/.test(text);
      });
      if (ironMatches.length >= 5) {
        const r = createReferralRecord(userId, 'Potential iron deficiency trend based on recent interactions', ['Ferritin', 'Hemoglobin'], Number.isFinite(lat) ? lat : undefined, Number.isFinite(lon) ? lon : undefined);
        resultActions.push({ trigger: 'freq_iron', count: ironMatches.length, created: r });
      }

      // Generic high-interaction trigger: 5+ HIGH-tier interactions in 30 days -> suggest comprehensive panel
      const highTierCount = (rows || []).filter(r => String(r.tier || '').toUpperCase() === 'HIGH').length;
      if (highTierCount >= 5) {
        const r = createReferralRecord(userId, 'High-frequency risky interactions detected', ['Ferritin', 'Prothrombin time (PT/INR)', 'Full blood panel'], Number.isFinite(lat) ? lat : undefined, Number.isFinite(lon) ? lon : undefined);
        resultActions.push({ trigger: 'freq_high_tier', count: highTierCount, created: r });
      }

      res.json({ ok: true, actions: resultActions });
    } catch (e) {
      console.error('referrals.check failed', e);
      res.status(500).json({ ok: false, error: String(e) });
    }
  });

  // New: summary-only referral status endpoint (no DB writes)
  const referralStatusHandler = (req: any, res: any) => {
    const userId = String(req.query?.userId || req.userId || '');
    if (!userId) return res.status(400).json({ detail: 'Missing userId' });

    try {
      const now = Date.now();
      const actions: any[] = [];

      // Latest blood test age
      const latestTest = db.prepare("SELECT date FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(userId) as any;
      let ageDays: number | null = null;
      if (latestTest?.date) ageDays = Math.floor((now - new Date(latestTest.date).getTime()) / (1000 * 60 * 60 * 24));

      // Helper: check whether a biomarker column exists and was ever filled
      function biomarkerEverFilled(userIdLocal: string, col: string) {
        try {
          const cols = db.prepare("PRAGMA table_info('blood_tests')").all() as any[];
          const found = cols.find(c => String(c.name || '').toLowerCase() === col.toLowerCase());
          if (!found) return false;
          const q = db.prepare(`SELECT COUNT(1) AS c FROM blood_tests WHERE user_id = ? AND (${col} IS NOT NULL AND ${col} != '')`).get(userIdLocal) as any;
          return Number(q?.c || 0) > 0;
        } catch (e) {
          return false;
        }
      }

      // Helper: check snooze/dismissals for a trigger key
      function isSnoozed(userIdLocal: string, triggerKey: string) {
        try {
          const row = db.prepare("SELECT snoozed_until FROM user_referral_dismissals WHERE user_id = ? AND trigger_type = ? ORDER BY dismissed_at DESC LIMIT 1").get(userIdLocal, triggerKey) as any;
          if (!row || !row.snoozed_until) return false;
          const until = new Date(row.snoozed_until).getTime();
          return until > Date.now();
        } catch (e) {
          return false;
        }
      }

      // Time-based: stale >180 days for any user
      if (!ageDays || ageDays >= 180) {
        const key = 'stale_biomarkers_180';
        if (!isSnoozed(userId, key)) actions.push({ trigger: key, ageDays, recommended_tests: ['Ferritin', 'Vitamin D', 'B12'] });
      }

      // Read virtual and manual meds separately and form a combined normalized set for deduping
      const vmRows = db.prepare('SELECT drug_name, public_label, severity FROM virtual_medications WHERE user_id = ? AND is_active = 1').all(userId) as any[];
      const profile = db.prepare('SELECT daily_medications FROM profile_by_user WHERE user_id = ?').get(userId) as any;
      const dailyList = String(profile?.daily_medications || '').split(',').map((s: string) => s.trim()).filter(Boolean);

      const vmSet = new Set((vmRows || []).map(r => String(r.drug_name || '').toLowerCase()));
      const dailySet = new Set((dailyList || []).map((s: string) => String(s || '').toLowerCase()));
      const combinedDrugs = Array.from(new Set([...vmSet, ...dailySet]));

      // Time-based: stale >90 days when user has any high-risk medication (virtual OR manual)
      const highRiskKeywords = ['warfarin', 'sintrom', 'acenocoumarol', 'tahor', 'atorvastatin', 'simvastatin', 'cyclosporine'];
      const hasHighRisk = combinedDrugs.some(d => highRiskKeywords.some(k => d.includes(k)));
      if (hasHighRisk && (!ageDays || ageDays >= 90)) {
        const key = 'stale_biomarkers_90_highrisk';
        if (!isSnoozed(userId, key)) actions.push({ trigger: key, ageDays, recommended_tests: ['Prothrombin time (PT/INR)', 'Vitamin K', 'Ferritin'] });
      }

      // Frequency-based: interactions in last 30 days (group by drug, MEDIUM/HIGH only)
      const since30 = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
      const rows = db.prepare('SELECT drug, tier, timestamp FROM interaction_history WHERE user_id = ? AND timestamp >= ?').all(userId, since30) as any[];
      const countsByDrug: Record<string, number> = {};
      for (const r of (rows || [])) {
        const tier = String(r.tier || '').toUpperCase();
        if (tier === 'HIGH' || tier === 'MEDIUM') {
          const d = String(r.drug || 'unknown').toLowerCase();
          countsByDrug[d] = (countsByDrug[d] || 0) + 1;
        }
      }

      for (const [drug, count] of Object.entries(countsByDrug)) {
        if (count >= 5) {
          const normalizedDrug = drug.toLowerCase();
          const triggerKey = `high_interaction_frequency:${normalizedDrug}`;
          if (isSnoozed(userId, triggerKey) || isSnoozed(userId, 'high_interaction_frequency')) continue;
          let recommended = ['Ferritin', 'Vitamin D', 'B12'];
          if (/warfarin|sintrom|acenocoumarol/.test(normalizedDrug)) recommended = ['Prothrombin time (PT/INR)', 'Vitamin K', 'Ferritin'];
          if (/tahor|atorvastatin|simvastatin/.test(normalizedDrug)) recommended = ['Liver enzymes', 'CPK', 'Vitamin D'];
          if (/iron|ferrous|ferrous sulfate/.test(normalizedDrug)) recommended = ['Ferritin', 'Hemoglobin', 'Transferrin'];
          actions.push({ trigger: 'high_interaction_frequency', trigger_key: triggerKey, drug: normalizedDrug, count, recommended_tests: recommended });
        }
      }

      // Generic high-tier 5+ in 30 days
      const highTierCount = (rows || []).filter(r => String(r.tier || '').toUpperCase() === 'HIGH').length;
      if (highTierCount >= 5) {
        const key = 'freq_high_tier';
        if (!isSnoozed(userId, key)) actions.push({ trigger: key, count: highTierCount, recommended_tests: ['Ferritin', 'Vitamin D', 'B12'] });
      }

      // Missing critical biomarker: check combined drugs and use explicit mapping
      const medBiomarkerMap: Record<string, string[]> = {
        // Anticoagulants
        'warfarin': ['prothrombin_time', 'vitamin_k', 'ferritin'],
        'sintrom': ['prothrombin_time', 'vitamin_k', 'ferritin'],
        'acenocoumarol': ['prothrombin_time', 'vitamin_k', 'ferritin'],
        // Statins
        'tahor': ['liver_enzymes', 'cpk', 'vitamin_d'],
        'atorvastatin': ['liver_enzymes', 'cpk', 'vitamin_d'],
        'simvastatin': ['liver_enzymes', 'cpk', 'vitamin_d'],
        // Immunosuppressant
        'cyclosporine': ['liver_enzymes'],
        // Iron supplements (generic)
        'ferrous': ['ferritin', 'hemoglobin', 'transferrin']
      };

      for (const medRaw of combinedDrugs) {
        const med = String(medRaw || '').toLowerCase();
        for (const [key, bioList] of Object.entries(medBiomarkerMap)) {
          if (med.includes(key)) {
            const missing = bioList.filter(b => !biomarkerEverFilled(userId, b));
            if (missing.length > 0) {
              const triggerKey = `missing_biomarker:${key}`;
              if (isSnoozed(userId, triggerKey) || isSnoozed(userId, 'missing_biomarker')) continue;
              actions.push({ trigger: 'missing_biomarker', trigger_key: triggerKey, drug: med, missing, recommended_tests: missing.map(x => x.replace(/_/g, ' ')) });
            }
          }
        }
      }

      res.json({ ok: true, actions, lastTestDate: latestTest?.date || null, daysSinceLastTest: ageDays });
    } catch (e) {
      console.error('referral-status failed', e);
      res.status(500).json({ ok: false, error: String(e) });
    }
  };

  app.get('/api/referral-status', referralStatusHandler);
  app.get('/api/referral_status', referralStatusHandler);

  // Record a dismissal/snooze for a referral action (defaults to 30 days)
  app.post('/api/referrals/dismiss', (req: any, res: any) => {
    const userId = req.userId || '';
    const triggerType = String(req.body?.trigger_type || req.body?.triggerKey || '').trim();
    const days = Number(req.body?.snooze_days || 30);
    if (!userId || !triggerType) return res.status(400).json({ ok: false, detail: 'Missing userId or trigger_type' });
    try {
      const until = new Date(Date.now() + Math.max(1, days) * 24 * 60 * 60 * 1000).toISOString();
      db.prepare("INSERT INTO user_referral_dismissals (user_id, trigger_type, dismissed_at, snoozed_until) VALUES (?, ?, CURRENT_TIMESTAMP, ?)").run(userId, triggerType, until);
      res.json({ ok: true, trigger_type: triggerType, snoozed_until: until });
    } catch (e) {
      console.error('Failed to record dismissal', e);
      res.status(500).json({ ok: false, error: String(e) });
    }
  });
}

ensureColumn("blood_tests", "user_id TEXT");
ensureColumn("blood_tests", "iode_urinaire REAL");
ensureColumn("blood_tests", "albumine REAL");
ensureColumn("blood_tests", "tsh REAL");
ensureColumn("blood_tests", "glycemie_jejun REAL");
ensureColumn("blood_tests", "hba1c REAL");
ensureColumn("blood_tests", "triglycerides REAL");
ensureColumn("blood_tests", "ldl REAL");
ensureColumn("blood_tests", "ratio_albumine_creatinine REAL");
ensureColumn("professional_patient_links", "patient_alias TEXT");
ensureColumn("cycle_logs", "user_id TEXT");
ensureColumn("cycle_logs", "period_length INTEGER DEFAULT 5");
ensureColumn("interaction_history", "user_id TEXT");
ensureColumn("interaction_history", "consumed INTEGER DEFAULT 0");
ensureColumn("interaction_history", "consumed_at TEXT");
ensureColumn("profile_by_user", "plan TEXT DEFAULT 'free'");
ensureColumn("profile_by_user", "age INTEGER");
ensureColumn("virtual_medications", "source_model TEXT DEFAULT 'model2_clinical_v1'");
ensureColumn("virtual_medications", "is_hidden INTEGER DEFAULT 1");
ensureColumn("virtual_medications", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP");

db.exec(`
  CREATE INDEX IF NOT EXISTS idx_blood_tests_user_date ON blood_tests(user_id, date);
  CREATE INDEX IF NOT EXISTS idx_cycle_logs_user_date ON cycle_logs(user_id, start_date);
  CREATE INDEX IF NOT EXISTS idx_interaction_history_user_time ON interaction_history(user_id, timestamp);
  CREATE INDEX IF NOT EXISTS idx_scan_usage_user_time ON scan_usage(user_id, scanned_at);
  CREATE INDEX IF NOT EXISTS idx_user_auth_email ON user_auth_link(email);
  CREATE INDEX IF NOT EXISTS idx_virtual_meds_user_active ON virtual_medications(user_id, is_active);
`);

const todayKeySql = "strftime('%Y-%m-%d', 'now', 'localtime')";

function getUserAuth(userId: string): { authenticated: boolean; email: string | null; plan: string } {
  let link: any = null;
  try {
    link = db.prepare("SELECT email FROM user_auth_link WHERE user_id = ?").get(userId) as any;
  } catch (error) {
    console.error("Auth lookup failed; falling back to anonymous user state:", error);
  }
  if (!link?.email) {
    let row: any = null;
    try {
      row = db.prepare("SELECT plan FROM profile_by_user WHERE user_id = ?").get(userId) as any;
    } catch (error) {
      console.error("Profile lookup failed; defaulting plan=free:", error);
    }
    return {
      authenticated: false,
      email: null,
      plan: String(row?.plan || "free").toLowerCase(),
    };
  }

  let account: any = null;
  try {
    account = db.prepare("SELECT email, plan FROM auth_accounts WHERE email = ?").get(link.email) as any;
  } catch (error) {
    console.error("Account lookup failed; defaulting to unauthenticated state:", error);
  }
  if (!account?.email) {
    return { authenticated: false, email: null, plan: "free" };
  }

  return {
    authenticated: true,
    email: String(account.email),
    plan: String(account.plan || "free").toLowerCase(),
  };
}

function getUserPlan(userId: string): string {
  let profileRow: any = null;
  try {
    profileRow = db.prepare("SELECT plan FROM profile_by_user WHERE user_id = ?").get(userId) as any;
  } catch (error) {
    console.error("Plan lookup failed in profile_by_user; falling back to auth plan:", error);
  }
  const profilePlan = String(profileRow?.plan || "").toLowerCase();
  if (profilePlan === "pro" || profilePlan === "free") return profilePlan;
  return getUserAuth(userId).plan;
}

function getLatestCycleContext(userId: string) {
  const row = db.prepare("SELECT start_date, duration, period_length FROM cycle_logs WHERE user_id = ? ORDER BY start_date DESC LIMIT 1").get(userId) as any;
  if (!row?.start_date || !row?.duration) {
    return { active: false, day: null, phase: null };
  }

  const startDate = new Date(row.start_date);
  const today = new Date();
  const duration = Math.max(1, Number(row.duration) || 28);
  const elapsedDays = Math.floor((today.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  const cycleDay = ((elapsedDays % duration) + duration) % duration + 1;
  const normalized = cycleDay / duration * 28;

  const phase = normalized <= 5 ? 'menstruation'
    : normalized <= 13 ? 'folliculaire'
    : normalized <= 16 ? 'ovulation'
    : 'luteale';

  return {
    active: true,
    day: cycleDay,
    phase,
    duration,
    period_length: Math.max(1, Number(row?.period_length) || 5),
  };
}

function getLatestBloodSnapshot(userId: string) {
  const row = db.prepare("SELECT * FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(userId) as any;
  const snapshot: Record<string, number | null> = {};

  for (const field of BLOOD_BIOMARKER_FIELDS) snapshot[field] = null;

  for (const field of BLOOD_BIOMARKER_FIELDS) {
    const raw = row?.[field];
    if (raw === null || raw === undefined || raw === "") continue;
    const n = Number(raw);
    if (!Number.isNaN(n)) snapshot[field] = n;
  }

  return snapshot;
}

function evaluateModel2Signals(snapshot: Record<string, number | null>): DeficiencySignal[] {
  const out: DeficiencySignal[] = [];
  const ferritin = snapshot.ferritin;
  const hemoglobin = snapshot.hemoglobin;
  const vitaminD = snapshot.vitaminD;
  const b12 = snapshot.b12;
  const folate = snapshot.folate;
  const calcium = snapshot.calcium;
  const magnesium = snapshot.magnesium;
  const zinc = snapshot.zinc;
  const iode = snapshot.iode_urinaire;

  // Model-2 runtime bridge: clinical thresholds aligned to your notebook labels.
  if ((ferritin !== null && ferritin < 30) || (hemoglobin !== null && hemoglobin < 12)) {
    const severe = (ferritin !== null && ferritin < 15) || (hemoglobin !== null && hemoglobin < 10);
    out.push({
      key: "label_ferritine",
      severity: severe ? "HIGH" : "MEDIUM",
      reason: `Low iron context from ferritin=${ferritin ?? "NA"}, hemoglobin=${hemoglobin ?? "NA"}`,
      virtualDrug: "ferrous sulfate",
      publicLabel: "Iron Support",
    });
  }

  if (vitaminD !== null && vitaminD < 20) {
    out.push({
      key: "label_vitD",
      severity: vitaminD < 12 ? "HIGH" : "MEDIUM",
      reason: `Vitamin D low (vitaminD=${vitaminD})`,
      virtualDrug: "cholecalciferol",
      publicLabel: "Vitamin D Support",
    });
  }

  if (b12 !== null && b12 < 200) {
    out.push({
      key: "label_vitB12",
      severity: b12 < 150 ? "HIGH" : "MEDIUM",
      reason: `Vitamin B12 low (b12=${b12})`,
      virtualDrug: "cyanocobalamin",
      publicLabel: "Vitamin B12 Support",
    });
  }

  if (folate !== null && folate < 4) {
    out.push({
      key: "label_folate_serique",
      severity: folate < 3 ? "HIGH" : "MEDIUM",
      reason: `Folate low (folate=${folate})`,
      virtualDrug: "folic acid",
      publicLabel: "Folate Support",
    });
  }

  if (calcium !== null && calcium < 8.5) {
    out.push({
      key: "label_calcium",
      severity: calcium < 8.0 ? "HIGH" : "MEDIUM",
      reason: `Calcium low (calcium=${calcium})`,
      virtualDrug: "calcium carbonate",
      publicLabel: "Calcium Support",
    });
  }

  if (magnesium !== null && magnesium < 1.7) {
    out.push({
      key: "label_magnesium",
      severity: magnesium < 1.4 ? "HIGH" : "MEDIUM",
      reason: `Magnesium low (magnesium=${magnesium})`,
      virtualDrug: "magnesium oxide",
      publicLabel: "Magnesium Support",
    });
  }

  if (zinc !== null && zinc < 70) {
    out.push({
      key: "label_zinc",
      severity: zinc < 60 ? "HIGH" : "MEDIUM",
      reason: `Zinc low (zinc=${zinc})`,
      virtualDrug: "zinc sulfate",
      publicLabel: "Zinc Support",
    });
  }

  if (iode !== null && iode < 100) {
    out.push({
      key: "label_iode_urinaire",
      severity: iode < 50 ? "HIGH" : "MEDIUM",
      reason: `Iodine low (iode_urinaire=${iode})`,
      virtualDrug: "potassium iodide",
      publicLabel: "Iodine Support",
    });
  }

  return out;
}

function model2PredictionPassesQuality(p: Model2LabelPrediction): boolean {
  if (!p.ok) return false;
  const auc = typeof p.test_auc === "number" ? p.test_auc : 0;
  const gap = typeof p.gap === "number" ? p.gap : 1;
  const status = String(p.status || "").toUpperCase();

  if (status.includes("OVERFIT")) return false;
  if (auc < 0.75) return false;
  if (gap > 0.12) return false;
  return true;
}

function runModel2Inference(snapshot: Record<string, number | null>): Model2InferenceResult {
  const scriptCandidates = [
    path.join(process.cwd(), "model2_infer.py"),
    path.join(process.cwd(), "web", "model2_infer.py"),
  ];
  const scriptPath = scriptCandidates.find((p) => fs.existsSync(p));
  if (!scriptPath) {
    return {
      integrated: true,
      runnerOk: false,
      runnerError: "model2_infer.py not found",
      predictions: {},
    };
  }

  const payload = JSON.stringify({ snapshot });
  const candidates = [
    { cmd: process.env.PYTHON_EXECUTABLE || "python", args: [scriptPath] },
    { cmd: "py", args: ["-3", scriptPath] },
  ];

  for (const c of candidates) {
    try {
      const proc = spawnSync(c.cmd, c.args, {
        input: payload,
        encoding: "utf-8",
        timeout: 10000,
      });

      if (proc.error) continue;
      if (proc.status !== 0 && !proc.stdout) continue;

      const raw = String(proc.stdout || "").trim();
      if (!raw) continue;

      const parsed = JSON.parse(raw) as any;
      const preds = (parsed?.predictions || {}) as Record<string, Model2LabelPrediction>;
      const okCount = Object.values(preds).filter((p) => p?.ok).length;
      return {
        integrated: true,
        runnerOk: Boolean(parsed?.ok) && okCount > 0,
        runnerError: okCount > 0 ? parsed?.error : (parsed?.error || "No compatible model2 artifacts could run"),
        predictions: preds,
      };
    } catch {
      // Try next executable candidate.
    }
  }

  return {
    integrated: true,
    runnerOk: false,
    runnerError: "No working Python runtime for model2 inference",
    predictions: {},
  };
}

function mergeMlSignals(baseSignals: DeficiencySignal[], ml: Model2InferenceResult): DeficiencySignal[] {
  const out = [...baseSignals];
  const byKey = new Map(out.map((s) => [s.key, s]));

  const labelToDrug: Record<string, { virtualDrug: string; publicLabel: string; reason: string }> = {
    label_folate_serique: { virtualDrug: "folic acid", publicLabel: "Folate Support", reason: "ML folate-risk positive" },
    label_calcium: { virtualDrug: "calcium carbonate", publicLabel: "Calcium Support", reason: "ML calcium-risk positive" },
    label_iode_urinaire: { virtualDrug: "potassium iodide", publicLabel: "Iodine Support", reason: "ML iodine-risk positive" },
  };

  for (const [label, pred] of Object.entries(ml.predictions || {})) {
    const mapping = labelToDrug[label];
    if (!mapping) continue;
    if (!pred?.positive) continue;
    if (!model2PredictionPassesQuality(pred)) continue;

    const prob = typeof pred.prob === "number" ? pred.prob : 0;
    const severity: "LOW" | "MEDIUM" | "HIGH" = prob >= 0.8 ? "HIGH" : (prob >= 0.65 ? "MEDIUM" : "LOW");

    const signal: DeficiencySignal = {
      key: label,
      severity,
      reason: `${mapping.reason}; prob=${prob.toFixed(3)} auc=${pred.test_auc ?? "NA"} gap=${pred.gap ?? "NA"}`,
      virtualDrug: mapping.virtualDrug,
      publicLabel: mapping.publicLabel,
    };

    if (byKey.has(label)) {
      byKey.set(label, signal);
    } else {
      byKey.set(label, signal);
    }
  }

  return Array.from(byKey.values());
}

function refreshVirtualMedications(userId: string, signals: DeficiencySignal[]) {
  const activeKeys = new Set(signals.map((s) => s.key));

  const upsert = db.prepare(`
    INSERT INTO virtual_medications (user_id, drug_name, public_label, signal_key, signal_reason, severity, is_active, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id, signal_key) DO UPDATE SET
      drug_name = excluded.drug_name,
      public_label = excluded.public_label,
      signal_reason = excluded.signal_reason,
      severity = excluded.severity,
      is_active = 1,
      updated_at = CURRENT_TIMESTAMP
  `);

  for (const signal of signals) {
    upsert.run(
      userId,
      signal.virtualDrug,
      signal.publicLabel,
      signal.key,
      signal.reason,
      signal.severity,
    );
  }

  const current = db.prepare("SELECT signal_key FROM virtual_medications WHERE user_id = ? AND is_active = 1").all(userId) as Array<{ signal_key: string }>;
  for (const row of current) {
    if (!activeKeys.has(row.signal_key)) {
      db.prepare("UPDATE virtual_medications SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND signal_key = ?").run(userId, row.signal_key);
    }
  }
}

function getActiveVirtualMeds(userId: string) {
  return db.prepare(
    "SELECT drug_name, public_label, signal_key, signal_reason, severity FROM virtual_medications WHERE user_id = ? AND is_active = 1"
  ).all(userId) as Array<{
    drug_name: string;
    public_label: string;
    signal_key: string;
    signal_reason: string;
    severity: "LOW" | "MEDIUM" | "HIGH";
  }>;
}

type ProfessionalRole = "doctor" | "pharmacist" | "nutritionist";

type ProfessionalAccountRow = {
  id: string;
  role: ProfessionalRole;
  pin_hash: string;
  name: string;
  specialty: string;
  linked_patients: string | null;
};

const PROFESSIONAL_JWT_SECRET = process.env.PROFESSIONAL_JWT_SECRET || process.env.JWT_SECRET || "healthopt-professional-mvp";

function base64UrlEncode(input: Buffer | string): string {
  return Buffer.from(input).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(input: string): Buffer {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "===".slice((normalized.length + 3) % 4);
  return Buffer.from(padded, "base64");
}

function hashProfessionalPin(pin: string, salt = randomUUID().replace(/-/g, "")) {
  const hash = createHmac("sha256", salt).update(pin).digest("hex");
  return `sha256$${salt}$${hash}`;
}

function verifyProfessionalPin(pin: string, pinHash: string): boolean {
  const parts = String(pinHash || "").split("$");
  if (parts.length !== 3 || parts[0] !== "sha256") return false;
  const [, salt, hash] = parts;
  const candidate = createHmac("sha256", salt).update(pin).digest("hex");
  return candidate === hash;
}

function signProfessionalJwt(payload: Record<string, any>): string {
  const header = { alg: "HS256", typ: "JWT" };
  const now = Math.floor(Date.now() / 1000);
  const body = { ...payload, iat: now, exp: now + 24 * 60 * 60 };
  const unsigned = `${base64UrlEncode(JSON.stringify(header))}.${base64UrlEncode(JSON.stringify(body))}`;
  const signature = createHmac("sha256", PROFESSIONAL_JWT_SECRET).update(unsigned).digest();
  return `${unsigned}.${base64UrlEncode(signature)}`;
}

function verifyProfessionalJwt(token: string): Record<string, any> | null {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) return null;
  const [headerPart, payloadPart, signaturePart] = parts;
  try {
    const expected = createHmac("sha256", PROFESSIONAL_JWT_SECRET).update(`${headerPart}.${payloadPart}`).digest();
    if (base64UrlEncode(expected) !== signaturePart) return null;
    const payload = JSON.parse(base64UrlDecode(payloadPart).toString("utf8")) as Record<string, any>;
    if (payload?.exp && Number(payload.exp) < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch (_error) {
    return null;
  }
}

function getProfessionalAccountById(id: string): ProfessionalAccountRow | null {
  const row = db.prepare("SELECT id, role, pin_hash, name, specialty, linked_patients FROM professional_accounts WHERE id = ?").get(id) as any;
  return row || null;
}

function getProfessionalFromRequest(req: express.Request): ProfessionalAccountRow | null {
  const header = String(req.headers.authorization || req.headers["x-professional-token"] || "").trim();
  const token = header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : header;
  if (!token) return null;
  const payload = verifyProfessionalJwt(token);
  if (!payload?.sub) return null;
  const account = getProfessionalAccountById(String(payload.sub));
  if (!account) return null;
  if (payload.role && String(payload.role) !== String(account.role)) return null;
  return account;
}

function syncProfessionalLinkedPatients(professionalId: string) {
  try {
    const rows = db.prepare("SELECT patient_user_id FROM professional_patient_links WHERE professional_id = ? ORDER BY linked_at DESC").all(professionalId) as any[];
    const linked = Array.from(new Set(rows.map((row) => String(row.patient_user_id || "").trim()).filter(Boolean)));
    db.prepare("UPDATE professional_accounts SET linked_patients = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?").run(JSON.stringify(linked), professionalId);
  } catch (error) {
    console.error("Failed to sync professional linked patients:", error);
  }
}

function getPatientDisplayName(userId: string): string {
  try {
    const auth = db.prepare("SELECT email FROM user_auth_link WHERE user_id = ?").get(userId) as any;
    if (auth?.email) return String(auth.email);
  } catch (error) {
    console.error("Failed to resolve patient display name:", error);
  }
  return userId;
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function maskDrugName(text: string, drug: string, replacement: string): string {
  if (!text) return text;
  const re = new RegExp(escapeRegex(drug), "ig");
  return text.replace(re, replacement);
}

function toFoodNutrientNotice(food: string, nutrientLabel: string, reason: string, explanation: string): string {
  const nutrient = nutrientLabel.replace(/\s*Support\s*$/i, "").trim();
  const sanitized = String(explanation || "")
    .replace(/food\s*[-/]\s*drug/ig, "food-nutrient")
    .replace(/drug\s*[-/]\s*food/ig, "food-nutrient")
    .replace(/\bdrug\b/ig, "nutrient")
    .replace(/\bmedication\b/ig, "nutrient support");

  return `Food-nutrient interaction (${nutrient}): ${food} can change your ${nutrient.toLowerCase()} support effect. ${sanitized} Context: ${reason}.`;
}

function buildVirtualNutrientSimpleView(
  nutrientLabel: string,
  food: string,
  reason: string,
  tier: string,
  triggerDetails?: { compounds: string[]; signals: string[] } | null,
  noTriggerAfterContext?: boolean,
): any {
  const nutrient = nutrientLabel.replace(/\s*Support\s*$/i, "").trim();
  const lowerNutrient = nutrient.toLowerCase();
  const urgency = String(tier || "").toUpperCase() === "HIGH"
    ? "HIGH PRIORITY"
    : (String(tier || "").toUpperCase() === "MEDIUM" ? "MEDIUM PRIORITY" : "LOW PRIORITY");

  const compounds = Array.isArray(triggerDetails?.compounds) ? triggerDetails!.compounds.filter(Boolean) : [];
  const signals = Array.isArray(triggerDetails?.signals) ? triggerDetails!.signals.filter(Boolean) : [];
  const triggerLine = compounds.length > 0
    ? `Active trigger compound(s) in this food context: ${compounds.join(", ")}${signals.length > 0 ? ` (signal: ${signals.join(", ")})` : ""}.`
    : null;

  const noTriggerLine = noTriggerAfterContext
    ? "After applying your food context (for example without/no/only), no active trigger compound was detected for this nutrient pathway."
    : null;

  return {
    metaphor: `${nutrient} Deficiency Context`,
    friendly_narrative: {
      what_is_happening: noTriggerAfterContext
        ? `${food} does not show an active trigger against ${lowerNutrient} correction after applying your specified food context.`
        : `${food} may reduce how effectively your body restores ${lowerNutrient} in your current deficiency context.${triggerLine ? ` ${triggerLine}` : ""}`,
      ...(noTriggerAfterContext ? {} : {
        why_it_matters: `Because your recent blood profile indicates ${lowerNutrient} deficiency context, this food pattern may slow nutritional recovery.`,
        how_to_fix_it: [
          `Take ${food} away from ${lowerNutrient}-support timing when possible.`,
          `Prioritize foods that improve ${lowerNutrient} utilization around your main support window.`,
          ...(triggerLine ? [`Focus on reducing the trigger source in this meal: ${compounds.join(", ")}.`] : []),
        ],
        when_to_act: `${urgency} - adjust meal timing to protect ${lowerNutrient} correction.`,
      }),
    },
    user_explanation: noTriggerAfterContext
      ? `${food} currently shows no active trigger against ${lowerNutrient} deficiency correction under your specified context.${noTriggerLine ? ` ${noTriggerLine}` : ""}`
      : `${food} can negatively affect ${lowerNutrient} deficiency correction in your current context.${triggerLine ? ` ${triggerLine}` : ""}`,
    what_to_do: noTriggerAfterContext
      ? `No strict timing action is required from this food context for ${lowerNutrient} right now.`
      : `Adjust food timing and meal composition to improve ${lowerNutrient} recovery.`
  };
}

function addTriggerDetailsToSimpleView(simpleView: any, py: any, food: string): any {
  if (!simpleView || typeof simpleView !== "object") return simpleView;

  const warnings: any[] = Array.isArray(py?.physicochemical_warnings) ? py.physicochemical_warnings : [];
  if (!warnings.length) return simpleView;

  const compounds = Array.from(new Set(
    warnings
      .map((w: any) => String(w?.trigger_compound || "").trim())
      .filter(Boolean)
  ));
  const signals = Array.from(new Set(
    warnings
      .map((w: any) => String(w?.food_signal || "").trim())
      .filter(Boolean)
  ));

  if (!compounds.length) return simpleView;

  const hasCalciumSignal = compounds.some((c) => /calcium|ca2\+/i.test(c))
    || signals.some((s) => /calcium_/i.test(s));

  const likelySource = hasCalciumSignal
    ? " Likely source in this meal: cheese/dairy calcium content."
    : "";

  const triggerSentence = ` Active trigger compound(s): ${compounds.join(", ")}${signals.length ? ` (signal: ${signals.join(", ")})` : ""}.${likelySource}`;

  const out = { ...simpleView };
  if (out.friendly_narrative && typeof out.friendly_narrative === "object") {
    out.friendly_narrative = {
      ...out.friendly_narrative,
      what_is_happening: `${String(out.friendly_narrative.what_is_happening || `This interaction was detected for ${food}.`)}${triggerSentence}`.trim(),
    };
  } else {
    out.user_explanation = `${String(out.user_explanation || out.explanation || `This interaction was detected for ${food}.`)}${triggerSentence}`.trim();
  }

  const existingCompounds = out.compounds_identified && typeof out.compounds_identified === "object"
    ? out.compounds_identified
    : { bioactive: [], nutritional: [] };

  const nutritional = Array.isArray(existingCompounds.nutritional) ? [...existingCompounds.nutritional] : [];
  for (const c of compounds) {
    if (!nutritional.some((n: any) => String(n?.name || n).toLowerCase() === c.toLowerCase())) {
      nutritional.push({ name: c });
    }
  }

  out.compounds_identified = {
    ...existingCompounds,
    nutritional,
  };

  return out;
}

function tierToRank(tier: string): number {
  const t = String(tier || "").toUpperCase();
  if (t === "INFO") return 0;
  if (t === "LOW") return 1;
  if (t === "MEDIUM") return 2;
  if (t === "HIGH") return 3;
  return -1;
}

function rankToTier(rank: number): string {
  if (rank <= 0) return "INFO";
  if (rank === 1) return "LOW";
  if (rank === 2) return "MEDIUM";
  return "HIGH";
}

function adjustTierForModifier(originalTier: string, modifier: number): string {
  const base = tierToRank(originalTier);
  if (base < 0) return String(originalTier || "INSUFFICIENT").toUpperCase();

  // Match requested behavior: strong CYP3A4 increase upgrades risk tier.
  if (modifier > 1.154) return rankToTier(Math.min(3, base + 1));
  if (modifier < 0.9) return rankToTier(Math.max(0, base - 1));
  return rankToTier(base);
}

function buildCyclePkAdjustment(
  cycleContext: { active: boolean; day: number | null; phase: string | null },
  enzymes: string[],
  baseTier: string,
  age: number | null,
  drug: string,
  food: string,
) {
  if (!cycleContext?.active || !cycleContext.phase) return null;

  const normalized = (enzymes || []).map((e) => String(e || "").toUpperCase());
  const tracked: Record<string, { weight: number; aliases: string[]; phaseModifiers: Record<string, number> }> = {
    CYP3A4: {
      weight: 10,
      aliases: ["CYP3A4"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.08, ovulation: 1.45, luteale: 1.18 },
    },
    ABCB1: {
      weight: 8,
      aliases: ["ABCB1", "P-GP", "PGP", "MDR1"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.04, ovulation: 1.16, luteale: 1.1 },
    },
    CYP2D6: {
      weight: 8,
      aliases: ["CYP2D6"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.05, ovulation: 1.22, luteale: 1.12 },
    },
    CYP2C19: {
      weight: 7,
      aliases: ["CYP2C19"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.05, ovulation: 1.2, luteale: 1.1 },
    },
    CYP2C9: {
      weight: 7,
      aliases: ["CYP2C9"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.04, ovulation: 1.18, luteale: 1.09 },
    },
    CYP1A2: {
      weight: 6,
      aliases: ["CYP1A2"],
      phaseModifiers: { menstruation: 1.0, folliculaire: 1.02, ovulation: 1.12, luteale: 1.06 },
    },
  };

  const detected = Object.entries(tracked)
    .filter(([, cfg]) => cfg.aliases.some((alias) => normalized.some((e) => e.includes(alias))))
    .map(([enzyme, cfg]) => ({
      enzyme,
      weight: cfg.weight,
      modifier: cfg.phaseModifiers[String(cycleContext.phase)] ?? 1.0,
    }));

  if (detected.length === 0) return null;

  const totalWeight = detected.reduce((acc, item) => acc + item.weight, 0);
  const modifier = totalWeight > 0
    ? detected.reduce((acc, item) => acc + item.modifier * item.weight, 0) / totalWeight
    : 1.0;

  const originalTier = String(baseTier || "LOW").toUpperCase();
  const adjustedTier = adjustTierForModifier(originalTier, modifier);
  const ageText = age !== null ? ` Age ${age}.` : "";
  const enzymeListText = detected.map((item) => item.enzyme).join(", ");
  const lead = [...detected].sort((a, b) => Math.abs(b.modifier - 1) * b.weight - Math.abs(a.modifier - 1) * a.weight)[0];

  const note = `Our AI responsible for Hormonal pharmacokinetic risk adjustment estimates a combined ${(modifier * 100 - 100).toFixed(0)}% shift vs baseline across ${enzymeListText} during ${cycleContext.phase} phase (cycle day ${cycleContext.day ?? "NA"}). Main driver: ${lead.enzyme} (${(lead.modifier * 100 - 100).toFixed(0)}%). ${drug} × ${food} risk is adjusted from ${originalTier} to ${adjustedTier}.${ageText}`;

  return {
    enzymes: detected,
    combined_modifier: modifier,
    original_tier: originalTier,
    adjusted_tier: adjustedTier,
    phase: cycleContext.phase,
    cycle_day: cycleContext.day,
    age,
    note,
  };
}

function mergeCycleContextIntoSimpleView(simpleView: any, cycleNote: string): any {
  if (!simpleView) return simpleView;
  const merged = { ...simpleView };
  if (merged?.friendly_narrative && typeof merged.friendly_narrative === "object") {
    merged.friendly_narrative = {
      ...merged.friendly_narrative,
      why_it_matters: `${String(merged.friendly_narrative.why_it_matters || "")} ${cycleNote}`.trim(),
    };
  } else {
    merged.user_explanation = `${String(merged.user_explanation || merged.explanation || "")} ${cycleNote}`.trim();
  }
  return merged;
}

function buildCycleNoteForUser(
  cyclePkAdjustment: any,
  hormonalWordingPolicy: any,
): string | null {
  if (!cyclePkAdjustment) return null;

  const mode = String(hormonalWordingPolicy?.mode || "").toLowerCase();
  const adjustedTier = String(cyclePkAdjustment?.adjusted_tier || "").toUpperCase();
  const originalTier = String(cyclePkAdjustment?.original_tier || "").toUpperCase();
  const dominantEnzyme = String(
    hormonalWordingPolicy?.dominant_enzyme
    || cyclePkAdjustment?.enzymes?.[0]?.enzyme
    || "CYP pathway",
  );

  if (mode === "secondary_modifier_only") {
    const phase = String(cyclePkAdjustment?.phase || "current");
    const enzymes = (cyclePkAdjustment?.enzymes || [])
      .map((e: any) => String(e?.enzyme || "").trim())
      .filter(Boolean)
      .slice(0, 3);
    const enzymeText = enzymes.length > 0 ? enzymes.join(", ") : "key liver transport and metabolism enzymes";
    return `During ${phase} phase, activity of ${enzymeText} can shift and slightly change how strongly this interaction behaves.`;
  }

  if (mode === "tier_confirmed" || adjustedTier === originalTier) {
    return `Hormonal phase confirms current ${adjustedTier || originalTier || "risk"} tier.`;
  }

  return `Hormonal phase adjustment: ${originalTier} -> ${adjustedTier}. Dominant enzyme signal: ${dominantEnzyme}.`;
}

function normalizeLabText(text: string): string {
  return String(text || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[\u00a0\t]+/g, " ")
    .replace(/[‐‑–—-]+/g, "-")
    .toLowerCase();
}

function parseNumericValue(rawValue: string): number | null {
  const cleaned = String(rawValue || "").trim().replace(/[^0-9,.-]/g, "");
  if (!cleaned) return null;
  const normalized = cleaned.replace(/,(?=\d)/g, ".");
  const value = Number.parseFloat(normalized);
  return Number.isFinite(value) ? value : null;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const FIELD_PLAUSIBLE_RANGES: Partial<Record<BiomarkerField, { min: number; max: number }>> = {
  ferritin: { min: 1, max: 5000 },
  hemoglobin: { min: 2, max: 25 },
  vitaminD: { min: 1, max: 300 },
  calcium: { min: 0.1, max: 25 },
  b12: { min: 10, max: 5000 },
  magnesium: { min: 0.1, max: 20 },
  zinc: { min: 0.1, max: 1000 },
  folate: { min: 0.1, max: 100 },
  iode_urinaire: { min: 1, max: 20000 },
  albumine: { min: 1, max: 100 },
  tsh: { min: 0.001, max: 100 },
  glycemie_jejun: { min: 0.1, max: 50 },
  hba1c: { min: 3.5, max: 20 },
  triglycerides: { min: 0.05, max: 30 },
  ldl: { min: 0.05, max: 15 },
  ratio_albumine_creatinine: { min: 0, max: 5000 },
};

const FIELD_UNIT_HINTS: Partial<Record<BiomarkerField, RegExp>> = {
  ferritin: /(ng\/?ml|ug\/?l|µg\/?l)/,
  hemoglobin: /(g\/?dl|g\/?l)/,
  vitaminD: /(ng\/?ml|nmol\/?l)/,
  calcium: /(mg\/?dl|mmol\/?l|g\/?l)/,
  b12: /(pg\/?ml|pmol\/?l)/,
  magnesium: /(mg\/?dl|mmol\/?l|mg\/?l)/,
  zinc: /(ug\/?dl|µg\/?dl|mg\/?l|umol\/?l|µmol\/?l)/,
  folate: /(ng\/?ml|nmol\/?l)/,
  iode_urinaire: /(ug\/?l|µg\/?l|mcg\/?l)/,
  albumine: /(g\/?l|g\/?dl|mg\/?dl)/,
  tsh: /(ui\/?ml|u?iu\/?ml|miu\/?l|mu\/?l)/,
  glycemie_jejun: /(g\/?l|mg\/?dl|mmol\/?l)/,
  hba1c: /(%|mmol\/?mol)/,
  triglycerides: /(g\/?l|mg\/?dl|mmol\/?l)/,
  ldl: /(g\/?l|mg\/?dl|mmol\/?l)/,
  ratio_albumine_creatinine: /(mg\/?g|mg\/?mmol)/,
};

function isPlausibleFieldValue(field: BiomarkerField, value: number): boolean {
  const range = FIELD_PLAUSIBLE_RANGES[field];
  if (!range) return true;
  return value >= range.min && value <= range.max;
}

function shouldSkipCandidate(field: BiomarkerField, preContext: string, token: string, postContext: string): boolean {
  const around = `${token} ${postContext.slice(0, 24)}`;

  if (field === "tsh" && /(?:eme|e)\s*generation/.test(around)) {
    return true;
  }

  if (field === "folate" && /\b(vitamine?\s*b12|vitamin\s*b12|cobalamine|\bb12\b)\b/.test(preContext)) {
    return true;
  }

  if (field === "hba1c" && /^\s*%\s*-\s*\d/.test(postContext)) {
    return true;
  }

  if (field === "hba1c" && !/[.,]/.test(token)) {
    return true;
  }

  return false;
}

function decodePdfLiteralString(value: string): string {
  let decoded = String(value || "");
  decoded = decoded
    .replace(/\\([nrtbf()\\])/g, (_match, escapedChar) => {
      switch (escapedChar) {
        case "n": return "\n";
        case "r": return "\r";
        case "t": return "\t";
        case "b": return "\b";
        case "f": return "\f";
        case "(": return "(";
        case ")": return ")";
        case "\\": return "\\";
        default: return escapedChar;
      }
    })
    .replace(/\\([0-7]{1,3})/g, (_match, octal) => String.fromCharCode(Number.parseInt(octal, 8)));
  return decoded;
}

function decodePdfHexString(hexText: string): string {
  const cleaned = String(hexText || "").replace(/\s+/g, "");
  if (!cleaned || cleaned.length % 2 !== 0) return "";

  const bytes = Buffer.from(cleaned, "hex");
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    const swapped = Buffer.alloc(bytes.length - 2);
    for (let index = 2; index + 1 < bytes.length; index += 2) {
      swapped[index - 2] = bytes[index + 1];
      swapped[index - 1] = bytes[index];
    }
    return swapped.toString("utf16le");
  }

  return bytes.toString("latin1");
}

function extractTextFromPdfStream(streamBuffer: Buffer): string {
  const decodedParts: string[] = [];
  const candidates = [streamBuffer];

  try {
    candidates.unshift(inflateSync(streamBuffer));
  } catch {
    try {
      candidates.unshift(inflateRawSync(streamBuffer));
    } catch {
      // Keep the original stream bytes if decompression fails.
    }
  }

  for (const candidate of candidates) {
    const streamText = candidate.toString("latin1");

    for (const literalMatch of streamText.matchAll(/\((?:\\.|[^\\()])*\)/g)) {
      const rawLiteral = literalMatch[0].slice(1, -1);
      const decoded = decodePdfLiteralString(rawLiteral).trim();
      if (decoded.length > 0) {
        decodedParts.push(decoded);
      }
    }

    for (const hexMatch of streamText.matchAll(/<([0-9A-Fa-f\s]+)>/g)) {
      const decoded = decodePdfHexString(hexMatch[1]).trim();
      if (decoded.length > 0) {
        decodedParts.push(decoded);
      }
    }
  }

  return decodedParts.join("\n");
}

function extractTextFromPdfBuffer(pdfBuffer: Buffer): string {
  const streamTexts: string[] = [];
  const streamMarker = Buffer.from("stream");
  const endStreamMarker = Buffer.from("endstream");

  let searchIndex = 0;
  while (searchIndex < pdfBuffer.length) {
    const streamIndex = pdfBuffer.indexOf(streamMarker, searchIndex);
    if (streamIndex === -1) break;

    let dataStart = streamIndex + streamMarker.length;
    while (dataStart < pdfBuffer.length && (pdfBuffer[dataStart] === 0x20 || pdfBuffer[dataStart] === 0x0d || pdfBuffer[dataStart] === 0x0a)) {
      dataStart += 1;
    }

    const endIndex = pdfBuffer.indexOf(endStreamMarker, dataStart);
    if (endIndex === -1) break;

    let streamBuffer = pdfBuffer.slice(dataStart, endIndex);
    while (streamBuffer.length > 0 && (streamBuffer[streamBuffer.length - 1] === 0x0d || streamBuffer[streamBuffer.length - 1] === 0x0a || streamBuffer[streamBuffer.length - 1] === 0x00)) {
      streamBuffer = streamBuffer.subarray(0, streamBuffer.length - 1);
    }

    const extracted = extractTextFromPdfStream(streamBuffer).trim();
    if (extracted.length > 0) {
      streamTexts.push(extracted);
    }

    searchIndex = endIndex + endStreamMarker.length;
  }

  if (streamTexts.length === 0) {
    return pdfBuffer.toString("latin1");
  }

  return streamTexts.join("\n");
}

function extractFieldFromText(field: BiomarkerField, text: string, aliases: string[]): number | null {
  const normalized = normalizeLabText(text);
  let bestValue: number | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;

  for (const alias of aliases) {
    const normalizedAlias = normalizeLabText(alias);
    const aliasRegex = new RegExp(`\\b${escapeRegExp(normalizedAlias)}\\b`, "g");
    let match: RegExpExecArray | null = null;

    while ((match = aliasRegex.exec(normalized)) !== null) {
      const aliasIndex = match.index;
      const aliasEnd = aliasIndex + normalizedAlias.length;
      const localContext = normalized.slice(aliasIndex, Math.min(normalized.length, aliasEnd + 80));

      // Avoid mapping HbA1c/glycated hemoglobin labels into plain hemoglobin.
      if (field === "hemoglobin" && /(hba1c|a1c|glycos|glyquee|glyquee)/.test(localContext)) {
        continue;
      }

      const tail = normalized.slice(aliasEnd, Math.min(normalized.length, aliasEnd + 220));
      // Collect and score all nearby numeric candidates instead of taking the first hit.
      const numberRegex = /(?:^|[^a-z0-9])([-+]?\d+(?:[.,]\d+)?)/g;
      let numericMatch: RegExpExecArray | null = null;

      while ((numericMatch = numberRegex.exec(tail)) !== null) {
        const token = numericMatch[1] || "";
        const leading = (numericMatch[0].length - token.length);
        const tokenStart = numericMatch.index + Math.max(0, leading);
        const tokenEnd = tokenStart + token.length;

        const preContext = tail.slice(Math.max(0, tokenStart - 90), tokenStart);
        const postContext = tail.slice(tokenEnd, Math.min(tail.length, tokenEnd + 70));

        if (shouldSkipCandidate(field, preContext, token, postContext)) {
          continue;
        }

        const numericValue = parseNumericValue(token);
        if (numericValue === null) continue;
        if (!isPlausibleFieldValue(field, numericValue)) continue;

        let score = 0;
        score -= tokenStart / 120;
        if (/[.]{4,}\s*$/.test(preContext)) score += 1.5;

        const unitHint = FIELD_UNIT_HINTS[field];
        if (unitHint && unitHint.test(postContext)) score += 2.5;

        if (score > bestScore) {
          bestScore = score;
          bestValue = numericValue;
        }
      }
    }
  }

  return bestValue;
}

function extractBloodFieldsFromText(text: string): Partial<Record<BiomarkerField, number>> {
  const result: Partial<Record<BiomarkerField, number>> = {};
  for (const field of BLOOD_BIOMARKER_FIELDS) {
    const aliases = BLOOD_FIELD_ALIASES[field] || [];
    const value = extractFieldFromText(field, text, aliases);
    if (value !== null) {
      result[field] = value;
    }
  }
  return result;
}

async function extractBloodFieldsFromPdfBuffer(pdfBuffer: Buffer) {
  const text = extractTextFromPdfBuffer(pdfBuffer);
  const localFields = extractBloodFieldsFromText(text);
  const localCount = Object.keys(localFields).length;

  if (localCount > 0) {
    return localFields;
  }

  if (!process.env.GEMINI_API_KEY) {
    return localFields;
  }

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: [
        {
          parts: [
            { inlineData: { data: pdfBuffer.toString("base64"), mimeType: "application/pdf" } },
            { text: "Extract blood test biomarkers from this PDF. Return ONLY a JSON object with these keys: ferritin, hemoglobin, vitaminD, vitD, calcium, b12, vitB12, magnesium, zinc, folate, folate_serique, iode_urinaire, albumine, tsh, glycemie_jejun, hba1c, triglycerides, ldl, ratio_albumine_creatinine. Map French and English lab labels to these fields, including ferritine, hemoglobine, Hb, Hgb, vitamin D, 25-OH vitamin D, vit B12, folates, albumin, glycémie à jeun, and ACR. Use null if not found. Values should be numbers." }
          ]
        }
      ],
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            ferritin: { type: Type.NUMBER },
            hemoglobin: { type: Type.NUMBER },
            vitaminD: { type: Type.NUMBER },
            vitD: { type: Type.NUMBER },
            calcium: { type: Type.NUMBER },
            b12: { type: Type.NUMBER },
            vitB12: { type: Type.NUMBER },
            magnesium: { type: Type.NUMBER },
            zinc: { type: Type.NUMBER },
            folate: { type: Type.NUMBER },
            folate_serique: { type: Type.NUMBER },
            iode_urinaire: { type: Type.NUMBER },
            albumine: { type: Type.NUMBER },
            tsh: { type: Type.NUMBER },
            glycemie_jejun: { type: Type.NUMBER },
            hba1c: { type: Type.NUMBER },
            triglycerides: { type: Type.NUMBER },
            ldl: { type: Type.NUMBER },
            ratio_albumine_creatinine: { type: Type.NUMBER },
          }
        }
      }
    });

    const rawText = String(response.text || "").trim();
    const jsonText = rawText.match(/\{[\s\S]*\}$/)?.[0] || rawText;
    const remoteFields = JSON.parse(jsonText) as Partial<Record<BiomarkerField, number>>;
    return { ...remoteFields, ...localFields };
  } catch (error) {
    console.warn("Gemini fallback unavailable for PDF extraction:", error);
    return localFields;
  }
}

function escapePdfText(value: string): string {
  return String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}

function wrapPdfLine(value: string, maxWidth = 95): string[] {
  const words = String(value || "").split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxWidth) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
  }
  if (current) lines.push(current);
  return lines;
}

function buildSimplePdfFromLines(lines: string[]): Buffer {
  const pageLineLimit = 46;
  const chunks: string[][] = [];
  for (let i = 0; i < lines.length; i += pageLineLimit) {
    chunks.push(lines.slice(i, i + pageLineLimit));
  }
  if (chunks.length === 0) chunks.push(["No content."]);

  const objects: string[] = [""];
  objects[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[2] = "";
  objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";

  const pageIds: number[] = [];
  for (const chunk of chunks) {
    const streamLines = [
      "BT",
      "/F1 10 Tf",
      "50 760 Td",
      "14 TL",
      ...chunk.flatMap((line) => [`(${escapePdfText(line)}) Tj`, "T*"]),
      "ET",
    ];
    const stream = streamLines.join("\n");
    const contentObj = objects.push(`<< /Length ${Buffer.byteLength(stream, "utf8")} >>\nstream\n${stream}\nendstream`) - 1;
    const pageObj = objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentObj} 0 R >>`) - 1;
    pageIds.push(pageObj);
  }

  objects[2] = `<< /Type /Pages /Count ${pageIds.length} /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] >>`;

  let out = "%PDF-1.4\n";
  const offsets: number[] = [0];
  for (let i = 1; i < objects.length; i += 1) {
    offsets[i] = Buffer.byteLength(out, "utf8");
    out += `${i} 0 obj\n${objects[i]}\nendobj\n`;
  }

  const xrefStart = Buffer.byteLength(out, "utf8");
  out += `xref\n0 ${objects.length}\n`;
  out += "0000000000 65535 f \n";
  for (let i = 1; i < objects.length; i += 1) {
    out += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  out += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;

  return Buffer.from(out, "utf8");
}

async function startServer() {
  const app = express();
  const preferredPort = Number(process.env.PORT || 3000);
  const hmrPort = Number(process.env.VITE_HMR_PORT || 24679);

  app.use(express.json({ limit: '10mb' }));
  app.use((req, res, next) => {
    req.userId = resolveUserId(req, res);
    next();
  });

  // --- API Routes ---

  // Register extra routes (pharmacy, referrals)
  registerExtraRoutes(app);

  // Register pharmacist dashboard routes (point-of-sale flow). Reuses the
  // existing professional auth/JWT system: only requests with role=pharmacist
  // pass through.
  registerPharmacistRoutes({
    app,
    db,
    tradeNameIndex,
    verifyPharmacist: (req: any) => {
      const pro = getProfessionalFromRequest(req);
      if (!pro) return null;
      return { id: pro.id, role: pro.role, name: pro.name, specialty: pro.specialty };
    },
  });

  // Register nutritionist dashboard routes. Same auth pattern: only requests
  // with role=nutritionist pass through. Reuses the FastAPI /predict pipeline
  // in bulk meal-check mode and Gemini for unknown dish decomposition.
  registerNutritionistRoutes({
    app,
    db,
    ai,
    verifyNutritionist: (req: any) => {
      const pro = getProfessionalFromRequest(req);
      if (!pro) return null;
      return { id: pro.id, role: pro.role, name: pro.name, specialty: pro.specialty };
    },
  });

  // Fallback referral-status route mounted directly on the main app.
  // This ensures banner logic remains available even if extra routes are not registered for any reason.
  app.get('/api/referral-status', (req: any, res: any) => {
    const userId = String(req.query?.userId || req.userId || '');
    if (!userId) return res.status(400).json({ detail: 'Missing userId' });

    try {
      const now = Date.now();
      const actions: any[] = [];
      const latestTest = db.prepare("SELECT date FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(userId) as any;
      let ageDays: number | null = null;
      if (latestTest?.date) ageDays = Math.floor((now - new Date(latestTest.date).getTime()) / (1000 * 60 * 60 * 24));

      if (!ageDays || ageDays >= 180) {
        actions.push({ trigger: 'stale_biomarkers_180', ageDays, recommended_tests: ['Ferritin', 'Vitamin D', 'B12'] });
      }

      const vmRows = db.prepare('SELECT drug_name FROM virtual_medications WHERE user_id = ? AND is_active = 1').all(userId) as any[];
      const profile = db.prepare('SELECT daily_medications FROM profile_by_user WHERE user_id = ?').get(userId) as any;
      const dailyList = String(profile?.daily_medications || '').split(',').map((s: string) => s.trim().toLowerCase()).filter(Boolean);
      const vmList = (vmRows || []).map((r: any) => String(r.drug_name || '').toLowerCase());
      const combined = Array.from(new Set([...dailyList, ...vmList]));

      const highRiskKeywords = ['warfarin', 'sintrom', 'acenocoumarol', 'tahor', 'atorvastatin', 'simvastatin', 'cyclosporine'];
      const hasHighRisk = combined.some((d) => highRiskKeywords.some((k) => d.includes(k)));
      if (hasHighRisk && (!ageDays || ageDays >= 90)) {
        actions.push({ trigger: 'stale_biomarkers_90_highrisk', ageDays, recommended_tests: ['Prothrombin time (PT/INR)', 'Vitamin K', 'Ferritin'] });
      }

      function biomarkerEverFilled(col: string) {
        try {
          const cols = db.prepare("PRAGMA table_info('blood_tests')").all() as any[];
          if (!cols.find((c) => String(c.name || '').toLowerCase() === col.toLowerCase())) return false;
          const q = db.prepare(`SELECT COUNT(1) AS c FROM blood_tests WHERE user_id = ? AND (${col} IS NOT NULL AND ${col} != '')`).get(userId) as any;
          return Number(q?.c || 0) > 0;
        } catch {
          return false;
        }
      }

      const medBiomarkerMap: Record<string, string[]> = {
        warfarin: ['prothrombin_time', 'vitamin_k', 'ferritin'],
        sintrom: ['prothrombin_time', 'vitamin_k', 'ferritin'],
        acenocoumarol: ['prothrombin_time', 'vitamin_k', 'ferritin'],
        tahor: ['liver_enzymes', 'cpk', 'vitamin_d'],
        atorvastatin: ['liver_enzymes', 'cpk', 'vitamin_d'],
        simvastatin: ['liver_enzymes', 'cpk', 'vitamin_d'],
        ferrous: ['ferritin', 'hemoglobin', 'transferrin']
      };

      for (const med of combined) {
        for (const [key, markers] of Object.entries(medBiomarkerMap)) {
          if (!med.includes(key)) continue;
          const missing = markers.filter((m) => !biomarkerEverFilled(m));
          if (missing.length > 0) {
            actions.push({ trigger: 'missing_biomarker', trigger_key: `missing_biomarker:${key}`, drug: med, missing, recommended_tests: missing.map((m) => m.replace(/_/g, ' ')) });
          }
        }
      }

      res.json({ ok: true, actions, lastTestDate: latestTest?.date || null, daysSinceLastTest: ageDays });
    } catch (e) {
      console.error('fallback referral-status failed', e);
      res.status(500).json({ ok: false, error: String(e) });
    }
  });

  app.get("/api/auth/status", (req, res) => {
    const auth = getUserAuth(req.userId || "");
    res.json(auth);
  });

  app.post("/api/auth/signup", (req, res) => {
    const email = String(req.body?.email || "").trim().toLowerCase();
    const password = String(req.body?.password || "");
    if (!email || !password) {
      return res.status(400).json({ detail: "Email and password are required." });
    }

    const exists = db.prepare("SELECT email FROM auth_accounts WHERE email = ?").get(email);
    if (exists) {
      return res.status(409).json({ detail: "Account already exists. Please sign in." });
    }

    db.prepare("INSERT INTO auth_accounts (email, password, plan) VALUES (?, ?, 'free')").run(email, password);
    db.prepare("INSERT INTO user_auth_link (user_id, email) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET email = excluded.email").run(req.userId, email);

    res.json({ status: "ok", authenticated: true, email, plan: "free" });
  });

  app.post("/api/auth/signin", (req, res) => {
    const email = String(req.body?.email || "").trim().toLowerCase();
    const password = String(req.body?.password || "");
    if (!email || !password) {
      return res.status(400).json({ detail: "Email and password are required." });
    }

    const account = db.prepare("SELECT email, password, plan FROM auth_accounts WHERE email = ?").get(email) as any;
    if (!account || String(account.password) !== password) {
      return res.status(401).json({ detail: "Invalid credentials." });
    }

    db.prepare("INSERT INTO user_auth_link (user_id, email) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET email = excluded.email").run(req.userId, email);
    res.json({ status: "ok", authenticated: true, email, plan: String(account.plan || "free") });
  });

  app.post("/api/auth/signout", (req, res) => {
    db.prepare("DELETE FROM user_auth_link WHERE user_id = ?").run(req.userId);
    res.json({ status: "ok", authenticated: false });
  });

  app.post("/api/professional/auth", (req, res) => {
    const role = String(req.body?.role || "doctor").trim().toLowerCase() as ProfessionalRole;
    const pin = String(req.body?.pin || "").trim();
    if (!pin) {
      return res.status(400).json({ ok: false, detail: "PIN is required." });
    }

    const rows = db.prepare("SELECT id, role, pin_hash, name, specialty, linked_patients FROM professional_accounts WHERE role = ?").all(role) as ProfessionalAccountRow[];
    const match = rows.find((row) => verifyProfessionalPin(pin, row.pin_hash));
    if (!match) {
      return res.status(401).json({ ok: false, detail: "Invalid PIN." });
    }

    const token = signProfessionalJwt({ sub: match.id, role: match.role, name: match.name, specialty: match.specialty });
    res.json({
      ok: true,
      token,
      expires_in: 24 * 60 * 60,
      professional: {
        id: match.id,
        role: match.role,
        name: match.name,
        specialty: match.specialty,
        linked_patients: JSON.parse(String(match.linked_patients || "[]") || "[]"),
      },
    });
  });

  app.post("/api/professional/share-code", (req, res) => {
    try {
      const patientId = String(req.userId || "").trim();
      if (!patientId) {
        return res.status(401).json({ ok: false, detail: "Missing patient context." });
      }

      let shareCode = "";
      for (let attempt = 0; attempt < 12; attempt += 1) {
        const candidate = String(Math.floor(100000 + Math.random() * 900000));
        const existing = db.prepare("SELECT user_id FROM patient_share_codes WHERE share_code = ?").get(candidate) as any;
        if (!existing || String(existing.user_id || "") === patientId) {
          shareCode = candidate;
          break;
        }
      }
      if (!shareCode) {
        return res.status(500).json({ ok: false, detail: "Unable to generate share code." });
      }

      const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      db.prepare(
        `INSERT INTO patient_share_codes (user_id, share_code, expires_at, created_at)
         VALUES (?, ?, ?, CURRENT_TIMESTAMP)
         ON CONFLICT(user_id) DO UPDATE SET share_code = excluded.share_code, expires_at = excluded.expires_at, created_at = CURRENT_TIMESTAMP`
      ).run(patientId, shareCode, expiresAt);

      res.json({ ok: true, shareCode, expiresAt });
    } catch (error) {
      console.error("[share-code] Error:", error);
      return res.status(500).json({ ok: false, detail: String((error as any)?.message || "Failed to generate share code") });
    }
  });

  app.post("/api/professional/link-patient", (req, res) => {
    const professional = getProfessionalFromRequest(req);
    if (!professional) {
      return res.status(401).json({ ok: false, detail: "Unauthorized." });
    }

    const shareCode = String(req.body?.shareCode || "").trim();
    const patientAlias = String(req.body?.patientAlias || "").trim();
    if (!shareCode) {
      return res.status(400).json({ ok: false, detail: "Share code is required." });
    }

    const codeRow = db.prepare("SELECT user_id, expires_at FROM patient_share_codes WHERE share_code = ?").get(shareCode) as any;
    if (!codeRow) {
      return res.status(404).json({ ok: false, detail: "Share code not found." });
    }
    if (new Date(String(codeRow.expires_at || "")).getTime() < Date.now()) {
      return res.status(410).json({ ok: false, detail: "Share code expired." });
    }

    db.prepare(
      `INSERT INTO professional_patient_links (professional_id, patient_user_id, patient_alias, linked_at)
       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
       ON CONFLICT(professional_id, patient_user_id) DO UPDATE SET
         patient_alias = COALESCE(NULLIF(excluded.patient_alias, ''), professional_patient_links.patient_alias),
         linked_at = CURRENT_TIMESTAMP`
    ).run(professional.id, String(codeRow.user_id), patientAlias || null);
    syncProfessionalLinkedPatients(professional.id);

    // Return the effective display name so the frontend can update immediately
    const linkRow = db.prepare('SELECT patient_alias FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?').get(professional.id, String(codeRow.user_id)) as any;
    const displayName = (linkRow && linkRow.patient_alias) ? linkRow.patient_alias : getPatientDisplayName(String(codeRow.user_id));
    return res.json({ ok: true, patientId: String(codeRow.user_id), displayName });

    res.json({ ok: true, professionalId: professional.id, patientId: String(codeRow.user_id), patientAlias });
  });

  // Update alias for a linked patient
  app.post('/api/professional/link-patient/update', (req, res) => {
    const professional = getProfessionalFromRequest(req);
    if (!professional) return res.status(401).json({ ok: false, detail: 'Unauthorized.' });
    const patientId = String(req.body?.patientId || '').trim();
    const patientAlias = String(req.body?.patientAlias || '').trim();
    if (!patientId) return res.status(400).json({ ok: false, detail: 'patientId is required.' });
    const link = db.prepare('SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?').get(professional.id, patientId);
    if (!link) return res.status(403).json({ ok: false, detail: 'Patient not linked.' });
    db.prepare('UPDATE professional_patient_links SET patient_alias = ? WHERE professional_id = ? AND patient_user_id = ?').run(patientAlias || null, professional.id, patientId);
    syncProfessionalLinkedPatients(professional.id);
    return res.json({ ok: true, patientId, patientAlias });
  });

  // Unlink / delete a linked patient
  app.delete('/api/professional/link-patient/:patientId', (req, res) => {
    const professional = getProfessionalFromRequest(req);
    if (!professional) return res.status(401).json({ ok: false, detail: 'Unauthorized.' });
    const patientId = String(req.params.patientId || '').trim();
    if (!patientId) return res.status(400).json({ ok: false, detail: 'patientId is required.' });
    const link = db.prepare('SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?').get(professional.id, patientId);
    if (!link) return res.status(403).json({ ok: false, detail: 'Patient not linked.' });
    db.prepare('DELETE FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?').run(professional.id, patientId);
    syncProfessionalLinkedPatients(professional.id);
    return res.json({ ok: true, patientId });
  });

  app.get("/api/professional/patients/:doctorId", (req, res) => {
    const professional = getProfessionalFromRequest(req);
    const doctorId = String(req.params.doctorId || "").trim();
    if (!professional || professional.id !== doctorId) {
      return res.status(403).json({ ok: false, detail: "Forbidden." });
    }

    const links = db.prepare("SELECT patient_user_id, patient_alias, linked_at FROM professional_patient_links WHERE professional_id = ? ORDER BY linked_at DESC").all(professional.id) as any[];
    const since30 = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    const since7 = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

    const patients = links.map((link) => {
      const patientId = String(link.patient_user_id || "");
      const profile = db.prepare("SELECT gender, age, daily_medications, plan FROM profile_by_user WHERE user_id = ?").get(patientId) as any;
      const interactions30 = db.prepare("SELECT tier, timestamp FROM interaction_history WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp DESC").all(patientId, since30) as any[];
      const high7 = db.prepare("SELECT COUNT(1) AS c FROM interaction_history WHERE user_id = ? AND timestamp >= ? AND UPPER(tier) = 'HIGH'").get(patientId, since7) as any;
      const blood = db.prepare("SELECT date FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(patientId) as any;
      const latestInteraction = interactions30[0]?.timestamp || null;
      const lastBloodDate = String(blood?.date || "") || null;
      const lastActive = [latestInteraction, lastBloodDate].filter(Boolean).sort().slice(-1)[0] || latestInteraction || lastBloodDate || null;
      const bloodAgeDays = lastBloodDate ? Math.floor((Date.now() - new Date(lastBloodDate).getTime()) / (1000 * 60 * 60 * 24)) : null;
      const dominantRank = interactions30.reduce((worst, row) => Math.max(worst, tierToRank(String(row?.tier || "INSUFFICIENT"))), -1);
      // If no interactions recorded, show "—" instead of "INFO"
      const dominantTier = interactions30.length === 0 ? "—" : rankToTier(Math.max(0, dominantRank));
      const alertStatus = Number(high7?.c || 0) >= 3 || bloodAgeDays === null || bloodAgeDays > 180
        ? "RED"
        : (dominantTier === "MEDIUM" || (bloodAgeDays !== null && bloodAgeDays >= 90) ? "YELLOW" : "GREEN");
      const cycleContext = getLatestCycleContext(patientId);
      const displayName = String(link.patient_alias || "") || getPatientDisplayName(patientId);

      return {
        patient_id: patientId,
        patient_name: displayName,
        last_active: lastActive,
        dominant_tier: dominantTier,
        total_interactions_30d: interactions30.length,
        high_interactions_7d: Number(high7?.c || 0),
        last_blood_test_date: lastBloodDate,
        blood_age_days: bloodAgeDays,
        cycle_phase: cycleContext?.phase || null,
        alert_status: alertStatus,
        plan: String(profile?.plan || "free"),
        gender: String(profile?.gender || "female"),
        age: profile?.age ?? null,
        daily_medications: String(profile?.daily_medications || ""),
        linked_at: link.linked_at || null,
      };
    });

    res.json({
      ok: true,
      professional: { id: professional.id, role: professional.role, name: professional.name, specialty: professional.specialty },
      patients,
    });
  });

  app.get("/api/professional/patient/:patientId/timeline", (req, res) => {
    const professional = getProfessionalFromRequest(req);
    const patientId = String(req.params.patientId || "").trim();
    if (!professional) {
      return res.status(401).json({ ok: false, detail: "Unauthorized." });
    }
    const link = db.prepare("SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?").get(professional.id, patientId);
    if (!link) {
      return res.status(403).json({ ok: false, detail: "Patient not linked." });
    }

    const since90 = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString();
    const interactions = db.prepare(
      `SELECT id, timestamp, drug, food, tier, score, mechanism, consumed, consumed_at
       FROM interaction_history
       WHERE user_id = ? AND timestamp >= ?
       ORDER BY timestamp ASC`
    ).all(patientId, since90) as any[];
    const bloodRows = db.prepare(
      `SELECT date, ferritin, hemoglobin, vitaminD, calcium, b12, magnesium, zinc, folate, iode_urinaire, albumine, tsh, glycemie_jejun, hba1c, triglycerides, ldl, ratio_albumine_creatinine
       FROM blood_tests
       WHERE user_id = ? AND date >= ?
       ORDER BY date ASC`
    ).all(patientId, since90) as any[];

    const cycle = db.prepare("SELECT start_date, duration, period_length FROM cycle_logs WHERE user_id = ? ORDER BY start_date DESC LIMIT 1").get(patientId) as any;
    const rangeStart = new Date(since90);
    const rangeEnd = new Date();
    const cycleBands: Array<{ start: string; end: string; phase: string; color: string }> = [];
    if (cycle?.start_date && cycle?.duration) {
      const cycleStart = new Date(cycle.start_date);
      const duration = Math.max(20, Number(cycle.duration) || 28);
      const periodLength = Math.max(2, Number(cycle.period_length) || 5);
      const follicularLength = Math.max(1, Math.min(12, duration - periodLength - 10));
      const ovulatoryLength = Math.max(1, Math.min(3, duration - periodLength - follicularLength - 1));
      const phases = [
        { key: "menstrual", days: periodLength, color: "rgba(244, 63, 94, 0.12)" },
        { key: "follicular", days: follicularLength, color: "rgba(16, 185, 129, 0.10)" },
        { key: "ovulatory", days: ovulatoryLength, color: "rgba(99, 102, 241, 0.12)" },
        { key: "luteal", days: Math.max(1, duration - periodLength - follicularLength - ovulatoryLength), color: "rgba(249, 115, 22, 0.10)" },
      ];
      const cursor = new Date(cycleStart);
      cursor.setHours(0, 0, 0, 0);
      while (cursor < rangeEnd) {
        let phaseCursor = new Date(cursor);
        for (const phase of phases) {
          const phaseStart = new Date(phaseCursor);
          const phaseEnd = new Date(phaseCursor);
          phaseEnd.setDate(phaseEnd.getDate() + phase.days);
          if (phaseEnd > rangeStart && phaseStart < rangeEnd) {
            cycleBands.push({ start: phaseStart.toISOString(), end: phaseEnd.toISOString(), phase: phase.key, color: phase.color });
          }
          phaseCursor = phaseEnd;
        }
        cursor.setDate(cursor.getDate() + duration);
      }
    }

    const biomarkerSeries = bloodRows.map((row) => {
      const markers = [
        ["prothrombin_time", row?.prothrombin_time],
        ["ferritin", row?.ferritin],
        ["hemoglobin", row?.hemoglobin],
        ["vitaminD", row?.vitaminD],
        ["b12", row?.b12],
        ["folate", row?.folate],
      ] as Array<[string, any]>;
      const marker = markers.find(([, value]) => value !== null && value !== undefined && value !== "");
      return {
        date: row.date,
        label: marker ? marker[0] : null,
        value: marker ? Number(marker[1]) : null,
        ferritin: row.ferritin ?? null,
        hemoglobin: row.hemoglobin ?? null,
        vitaminD: row.vitaminD ?? null,
        b12: row.b12 ?? null,
        folate: row.folate ?? null,
      };
    });

    const points = interactions.map((row) => ({
      id: row.id,
      date: row.timestamp,
      type: "interaction",
      drug: row.drug,
      food: row.food,
      score: Number(row.score || 0),
      tier: String(row.tier || "INSUFFICIENT").toUpperCase(),
      severity: tierToRank(String(row.tier || "INSUFFICIENT")),
      mechanism_flag: String(row.mechanism || "").includes("CLINICAL") ? "CLINICAL_RULE_CONFIRMED" : (String(row.mechanism || "").includes("HIDDEN") ? "HIDDEN_MECHANISM" : "VITAMIN_K_ANTAGONISM"),
      consumed: Number(row.consumed || 0),
      consumed_at: row.consumed_at || null,
    }));

    res.json({
      ok: true,
      patientId,
      cycle,
      cycle_bands: cycleBands,
      interactions: points,
      biomarker_series: biomarkerSeries,
    });
  });

  // Return active virtual medications / model2 signals for a given patient (professional access)
  app.get('/api/professional/patient/:patientId/virtual-medications', (req: any, res: any) => {
    const professional = getProfessionalFromRequest(req);
    const patientId = String(req.params.patientId || '').trim();
    if (!professional) return res.status(401).json({ ok: false, detail: 'Unauthorized.' });
    const link = db.prepare('SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?').get(professional.id, patientId);
    if (!link) return res.status(403).json({ ok: false, detail: 'Patient not linked.' });
    try {
      const active = getActiveVirtualMeds(patientId);
      res.json(Array.isArray(active) ? active : []);
    } catch (e) {
      console.error('Failed to fetch virtual meds for professional:', e);
      res.status(500).json({ ok: false, detail: 'Failed to load' });
    }
  });

  app.get("/api/professional/patient/:patientId/mechanistic/:interactionId", async (req, res) => {
    const professional = getProfessionalFromRequest(req);
    const patientId = String(req.params.patientId || "").trim();
    const interactionId = String(req.params.interactionId || "").trim();
    if (!professional) {
      return res.status(401).json({ ok: false, detail: "Unauthorized." });
    }
    const link = db.prepare("SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?").get(professional.id, patientId);
    if (!link) {
      return res.status(403).json({ ok: false, detail: "Patient not linked." });
    }

    const row = db.prepare("SELECT * FROM interaction_history WHERE id = ? AND user_id = ?").get(interactionId, patientId) as any;
    if (!row) {
      return res.status(404).json({ ok: false, detail: "Interaction not found." });
    }

    try {
      const pyRes = await fetch("http://localhost:8000/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ drug: row.drug, food: row.food, language: "en" }),
      });
      const py = pyRes.ok ? await pyRes.json() as any : {};
      const cycleContext = getLatestCycleContext(patientId);
      const cycleAdjustment = buildCyclePkAdjustment(cycleContext, (py.graph_enzymes || py.graph_path || []) as string[], String(py.confidence || row.tier || "LOW"), null, String(row.drug || ""), String(row.food || ""));
      const activeVirtualMeds = getActiveVirtualMeds(patientId);
      const clinicalGate = Array.isArray(py?.physicochemical_warnings) && py.physicochemical_warnings.length > 0 ? "REVIEW" : "CONFIRMED";

      res.json({
        ok: true,
        interaction: row,
        patientId,
        rotate: {
          summary: String(py?.technical_view?.raw_mechanism || row.mechanism || ""),
          confidence: Number(py?.kge_score ?? py?.norm_kge ?? 0),
          enzymes: py?.kge_enzymes || [],
        },
        hkg: {
          path: py?.graph_path || py?.graph_enzymes || [],
          confidence: Number(py?.graph_score ?? py?.norm_graph ?? 0),
        },
        fusion: {
          lightgcn: py?.lgn_score ?? null,
          kge: py?.kge_score ?? null,
          hkg: py?.graph_score ?? null,
          clinical_gate: clinicalGate,
          fusion_score: py?.fusion_score ?? row.score ?? null,
        },
        cycle_modifier: cycleAdjustment,
        active_virtual_meds: activeVirtualMeds,
        technical_view: py?.technical_view || null,
      });
    } catch (error) {
      console.error("Professional mechanistic fetch failed", error);
      res.status(500).json({ ok: false, detail: "Failed to load mechanistic detail." });
    }
  });

  // Session cache for simulation results: key = "[patientId]:[inn]:[cyclePhase]:[virtualMedsHash]"
  const simulationCache = new Map<string, { result: any; timestamp: number }>();
  const SIMULATION_CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

  function getCacheKey(patientId: string, inn: string, cyclePhase: string | null, virtualMeds: string[]): string {
    const medsHash = virtualMeds.sort().join(',');
    return `${patientId}:${inn}:${cyclePhase || 'none'}:${medsHash}`;
  }

  function hashVirtualMeds(virtualMeds: string[]): string {
    return virtualMeds.sort().join(',');
  }

  // POST /api/professional/simulate - Therapeutic Alternatives Finder
  app.post("/api/professional/simulate", async (req, res) => {
    const professional = getProfessionalFromRequest(req);
    if (!professional) {
      return res.status(401).json({ status: "unauthorized", message: "Unauthorized." });
    }

    const patientId = String(req.body?.patientId || "").trim();
    const drugInput = String(req.body?.drug || "").trim();
    const cyclePhaseOverride = req.body?.cyclePhaseOverride as string | null | undefined;
    const virtualMedsOverride = req.body?.virtualMedsOverride as string[] | null | undefined;

    if (!patientId || !drugInput) {
      return res.status(400).json({ status: "error", message: "patientId and drug are required." });
    }

    // Verify patient is linked to this professional
    const link = db.prepare("SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?").get(professional.id, patientId);
    if (!link) {
      return res.status(403).json({ status: "error", message: "Patient not linked to this professional." });
    }

    // ─── A. Resolve the input drug ───────────────────────────────────────
    // Find drug in Algerian trade name index to get canonical INN
    let currentINN: string | null = null;
    let matchedTradeNames: string[] = [];

    // Try exact match in trade name index
    const tradeMatch = tradeNameIndex.find((row) => 
      normalizeLabText(row.brand_name) === normalizeLabText(drugInput) || 
      normalizeLabText(row.inn_raw) === normalizeLabText(drugInput)
    );

    if (tradeMatch) {
      currentINN = tradeMatch.inn_raw.toLowerCase();
      matchedTradeNames = [tradeMatch.brand_name];
    } else {
      // Fallback: use input as-is (lowercase)
      currentINN = drugInput.toLowerCase();
    }

    // Search DRUG_CLASS_ALTERNATIVES for class containing this INN
    let drugClassId: string | null = null;
    let drugClassInfo: DrugClassAlternative | null = null;
    for (const [classId, classInfo] of Object.entries(DRUG_CLASS_ALTERNATIVES)) {
      if (classInfo.members.includes(currentINN)) {
        drugClassId = classId;
        drugClassInfo = classInfo;
        // Add all Algerian trade names for this INN
        if (classInfo.algerian_trade_names[currentINN]) {
          matchedTradeNames = [...new Set([...matchedTradeNames, ...classInfo.algerian_trade_names[currentINN]])];
        }
        break;
      }
    }

    // If drug not found in any class, return drug_class_unknown
    if (!drugClassId || !drugClassInfo) {
      return res.status(200).json({
        status: "drug_class_unknown",
        message_en: "This medication is not in a class with documented therapeutic alternatives in HealthOpt.",
        message_fr: "Ce médicament n'appartient pas à une classe avec des alternatives thérapeutiques documentées dans HealthOpt.",
        alternatives: [],
      });
    }

    // ─── B. Get patient dietary pattern ──────────────────────────────────
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const thirtyDaysAgoStr = thirtyDaysAgo.toISOString();

    const dietaryRows = db.prepare(`
      SELECT food, COUNT(*) as frequency 
      FROM interaction_history 
      WHERE user_id = ? AND date >= ? 
      GROUP BY food 
      ORDER BY frequency DESC 
      LIMIT 15
    `).all(patientId, thirtyDaysAgoStr) as Array<{ food: string; frequency: number }>;

    const dietaryPattern = dietaryRows.map((row) => ({
      food: row.food,
      frequency_30d: Number(row.frequency),
    }));

    // Check if fewer than 3 unique foods
    if (dietaryPattern.length < 3) {
      return res.status(200).json({
        status: "insufficient_diet_data",
        message_en: "This patient has fewer than 3 foods logged in the last 30 days. Encourage them to log meals in the HealthOpt app before running this simulation.",
        message_fr: "Ce patient a enregistré moins de 3 aliments ces 30 derniers jours. Encouragez-le à enregistrer ses repas dans l'application HealthOpt avant de lancer cette simulation.",
        alternatives: [],
      });
    }

    // ─── C. Get patient physiological context ────────────────────────────
    // Cycle phase
    let cycleContext: { phase: string | null; source: "actual" | "override" | "none" };
    if (cyclePhaseOverride !== null && cyclePhaseOverride !== undefined) {
      cycleContext = { phase: cyclePhaseOverride, source: "override" };
    } else {
      const actualCycle = getLatestCycleContext(patientId);
      if (actualCycle?.active && actualCycle?.phase) {
        cycleContext = { phase: actualCycle.phase, source: "actual" };
      } else {
        cycleContext = { phase: null, source: "none" };
      }
    }

    // Virtual medications (biomarker deficiencies)
    let virtualMedsList: string[];
    if (virtualMedsOverride !== null && virtualMedsOverride !== undefined) {
      virtualMedsList = virtualMedsOverride;
    } else {
      const activeVirtuals = getActiveVirtualMeds(patientId);
      virtualMedsList = activeVirtuals.map((med) => med.drug_name);
    }

    // ─── Check cache ────────────────────────────────────────────────────
    const cacheKey = getCacheKey(patientId, currentINN, cycleContext.phase, virtualMedsList);
    const cached = simulationCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp) < SIMULATION_CACHE_TTL_MS) {
      return res.status(200).json(cached.result);
    }

    // ─── Helper: Score drug against dietary pattern ────────────────────
    async function scoreDrugAgainstDiet(
      inn: string,
      foods: Array<{ food: string; frequency_30d: number }>,
      cyclePhase: string | null,
      virtualMeds: string[]
    ): Promise<{
      inn: string;
      trade_names: string[];
      worst_tier: string;
      avg_score: number;
      high_count: number;
      med_count: number;
      low_count: number;
      high_foods: string[];
      critical_rules_fired: string[];
      per_food: any[];
      mechanism_flags: string[];
    }> {
      const perFood: any[] = [];
      const mechanismFlags: string[] = [];

      // Run predictions in parallel
      const predictions = await Promise.all(
        foods.map(async ({ food }) => {
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout per food

            const pyRes = await fetch("http://localhost:8000/predict", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                drug: inn,
                food,
                cycle_phase: cyclePhase,
                virtual_meds: virtualMeds,
                language: "en",
              }),
              signal: controller.signal,
            }).catch(() => null);

            clearTimeout(timeoutId);

            if (!pyRes?.ok) return null;
            const py = await pyRes.json() as any;

            const tier = String(py.confidence || "INSUFFICIENT").toUpperCase();
            const mechanismFlag = py.mechanism_flag || py.mechanism || "";

            return {
              food,
              tier,
              score: Number(py.fusion_score ?? 0),
              mechanism_flag: mechanismFlag,
              cycle_modifier: py.cycle_modifier || null,
              clinical_rule_fired: py.clinical_rule_fired || false,
            };
          } catch (e) {
            return null;
          }
        })
      );

      const validPredictions = predictions.filter((p): p is NonNullable<typeof p> => p !== null);

      for (const pred of validPredictions) {
        perFood.push(pred);
        if (pred.mechanism_flag) {
          mechanismFlags.push(pred.mechanism_flag);
        }
      }

      // Calculate aggregates
      const worstTierNum = perFood.reduce((acc, row) => Math.max(acc, tierToRank(row.tier)), 0);
      const avgScore = perFood.length > 0
        ? perFood.reduce((sum, row) => sum + row.score, 0) / perFood.length
        : 0;
      const highCount = perFood.filter((row) => tierToRank(row.tier) >= 3).length;
      const medCount = perFood.filter((row) => tierToRank(row.tier) === 2).length;
      const lowCount = perFood.filter((row) => tierToRank(row.tier) === 1).length;
      const highFoods = perFood
        .filter((row) => tierToRank(row.tier) >= 3)
        .map((row) => row.food);
      const criticalRules = perFood
        .filter((row) => row.clinical_rule_fired)
        .map((row) => row.mechanism_flag)
        .filter(Boolean);

      // Get trade names for this INN
      const tradeNames: string[] = [];
      for (const classInfo of Object.values(DRUG_CLASS_ALTERNATIVES)) {
        if (classInfo.algerian_trade_names[inn]) {
          tradeNames.push(...classInfo.algerian_trade_names[inn]);
        }
      }

      return {
        inn,
        trade_names: [...new Set(tradeNames)],
        worst_tier: rankToTier(worstTierNum),
        avg_score: avgScore,
        high_count: highCount,
        med_count: medCount,
        low_count: lowCount,
        high_foods: highFoods,
        critical_rules_fired: [...new Set(criticalRules)],
        per_food: perFood,
        mechanism_flags: [...new Set(mechanismFlags)],
      };
    }

    // ─── D. Score current drug ─────────────────────────────────────────
    const currentSummary = await scoreDrugAgainstDiet(
      currentINN,
      dietaryPattern,
      cycleContext.phase,
      virtualMedsList
    );

    // ─── E. Detect class-wide interaction ────────────────────────────────
    const highMedResults = currentSummary.per_food.filter(
      (row) => tierToRank(row.tier) >= 2
    );

    // Check if all HIGH/MEDIUM results share the same mechanism
    const uniqueMechanisms = [...new Set(highMedResults.map((r) => r.mechanism_flag).filter(Boolean))];
    const singleMechanism = uniqueMechanisms.length === 1 && highMedResults.length > 1;

    // Check if class has only 1 member
    const singleMemberClass = drugClassInfo.members.length === 1;

    const classWide = singleMechanism || singleMemberClass;

    // Generate dietary timing advice based on mechanism
    let dietaryTimingAdvice: string | null = null;
    let classWideNote: string | null = null;
    if (classWide) {
      classWideNote = drugClassInfo.therapeutic_note;
      const primaryMechanism = uniqueMechanisms[0] || "";

      if (primaryMechanism.includes("CHELATION") || currentINN.includes("floxacin")) {
        dietaryTimingAdvice = "Take medication 2 hours BEFORE or 6 hours AFTER meals containing dairy, eggs, iron supplements, or calcium-fortified foods.";
      } else if (primaryMechanism.includes("VITAMIN_K") || drugClassId === "anticoagulant_vka") {
        dietaryTimingAdvice = "Maintain CONSISTENT vitamin K intake daily — do not eliminate green vegetables, keep portions stable.";
      } else if (primaryMechanism.includes("POTASSIUM") || drugClassId === "ace_inhibitor") {
        dietaryTimingAdvice = "Limit high-potassium foods: avoid excess avocado, banana, dates, and dried fruits. Discuss dietary K+ targets with a dietitian.";
      } else {
        dietaryTimingAdvice = "Consult a clinical pharmacist for specific dietary timing guidance for this medication.";
      }
    }

    // If class-wide interaction detected, return early with advice
    if (classWide) {
      const result = {
        status: "ok",
        currentDrug: {
          inn: currentINN,
          trade_names: matchedTradeNames,
          class_label: drugClassInfo.class_label,
          dietary_summary: {
            worst_tier: currentSummary.worst_tier,
            avg_score: currentSummary.avg_score,
            high_count: currentSummary.high_count,
            med_count: currentSummary.med_count,
            low_count: currentSummary.low_count,
            high_foods: currentSummary.high_foods,
            critical_rules_fired: currentSummary.critical_rules_fired,
          },
        },
        dietaryPattern,
        cycleContext,
        virtualMedContext: virtualMedsList,
        class_wide: true,
        class_wide_note: classWideNote,
        dietary_timing_advice: dietaryTimingAdvice,
        qualified_alternatives: [],
        no_alternatives_reason: singleMemberClass ? "single_member_class" : "class_wide",
        advisory_warning: "This simulation identifies pharmacological interaction patterns only. Therapeutic substitution requires clinical assessment of efficacy, contraindications, renal function, patient history, and in some cases specialist approval. HealthOpt does not prescribe.",
        disclaimer: "For professional reference only. Not a substitution recommendation.",
      };
      simulationCache.set(cacheKey, { result, timestamp: Date.now() });
      return res.status(200).json(result);
    }

    // ─── F. Score all alternatives ─────────────────────────────────────
    // Build candidate list
    const candidates: Array<{ inn: string; class_id: string; cross_class: boolean; cross_class_note: string | null }> = [];

    // Same-class alternatives
    for (const member of drugClassInfo.members) {
      if (member !== currentINN) {
        candidates.push({
          inn: member,
          class_id: drugClassId,
          cross_class: false,
          cross_class_note: null,
        });
      }
    }

    // Cross-class alternatives (only if high_count >= 2)
    if (currentSummary.high_count >= 2 && drugClassInfo.cross_class_options.length > 0) {
      for (const crossOption of drugClassInfo.cross_class_options) {
        const targetClass = DRUG_CLASS_ALTERNATIVES[crossOption.target_class_id];
        if (targetClass) {
          for (const member of targetClass.members) {
            candidates.push({
              inn: member,
              class_id: crossOption.target_class_id,
              cross_class: true,
              cross_class_note: crossOption.cross_class_note,
            });
          }
        }
      }
    }

    // Score all candidates in parallel with timeout
    const candidateScores = await Promise.all(
      candidates.map(async (candidate) => {
        try {
          const score = await scoreDrugAgainstDiet(
            candidate.inn,
            dietaryPattern,
            cycleContext.phase,
            virtualMedsList
          );
          return { ...candidate, score, error: null };
        } catch (e) {
          return { ...candidate, score: null, error: e };
        }
      })
    );

    // ─── G. Filter: only genuinely safer alternatives ─────────────────
    const qualifiedAlternatives = candidateScores
      .filter((item): item is typeof item & { score: NonNullable<typeof item.score> } => {
        if (!item.score) return false;

        // Must pass all three conditions:
        // a) avg_score < current * 0.85 (at least 15% lower)
        const scoreImproved = item.score.avg_score < currentSummary.avg_score * 0.85;
        // b) high_count < current high_count
        const highCountImproved = item.score.high_count < currentSummary.high_count;
        // c) worst_tier not worse than current
        const tierNotWorse = tierToRank(item.score.worst_tier) <= tierToRank(currentSummary.worst_tier);

        return scoreImproved && highCountImproved && tierNotWorse;
      })
      .map((item) => {
        // Calculate biomarker conflicts
        const biomarkerConflicts = 0; // Simplified: would need additional queries

        // Calculate CYP fit score
        const candidateClass = DRUG_CLASS_ALTERNATIVES[item.class_id];
        let cypFitScore = 0.5; // neutral default

        if (cycleContext.phase && candidateClass?.cyp_primary?.length > 0) {
          // Get cycle phase modifiers from Model 3
          const cycleData = getLatestCycleContext(patientId);
          // Simplified: use phase-based estimation
          const phaseModifiers: Record<string, number> = {
            menstruation: 0.1,
            follicular: 0.05,
            ovulatory: 0.15,
            luteal: 0.2,
          };
          const modifier = phaseModifiers[cycleContext.phase.toLowerCase()] || 0.1;
          cypFitScore = 1 - modifier;
        }

        return {
          inn: item.inn,
          trade_names: item.score.trade_names,
          class_label: candidateClass?.class_label || item.class_id,
          cross_class: item.cross_class,
          cross_class_note: item.cross_class_note,
          dietary_summary: {
            worst_tier: item.score.worst_tier,
            avg_score: item.score.avg_score,
            high_count: item.score.high_count,
            med_count: item.score.med_count,
            low_count: item.score.low_count,
          },
          improvement: {
            avg_score_delta: item.score.avg_score - currentSummary.avg_score,
            high_count_delta: item.score.high_count - currentSummary.high_count,
            worst_tier_improved: tierToRank(item.score.worst_tier) < tierToRank(currentSummary.worst_tier),
          },
          biomarker_conflicts: biomarkerConflicts,
          cyp_fit_score: cypFitScore,
          therapeutic_note: candidateClass?.therapeutic_note || "",
        };
      });

    // ─── H. Rank qualified alternatives ─────────────────────────────────
    qualifiedAlternatives.sort((a, b) => {
      // 1. avg_score ASC
      if (a.dietary_summary.avg_score !== b.dietary_summary.avg_score) {
        return a.dietary_summary.avg_score - b.dietary_summary.avg_score;
      }
      // 2. biomarker_conflicts ASC
      if (a.biomarker_conflicts !== b.biomarker_conflicts) {
        return a.biomarker_conflicts - b.biomarker_conflicts;
      }
      // 3. cross_class ASC (same class preferred)
      if (a.cross_class !== b.cross_class) {
        return a.cross_class ? 1 : -1;
      }
      // 4. cyp_fit_score DESC
      return b.cyp_fit_score - a.cyp_fit_score;
    });

    // Assign ranks
    qualifiedAlternatives.forEach((alt, index) => {
      (alt as any).rank = index + 1;
    });

    // ─── I. Build and return response ──────────────────────────────────
    let noAlternativesReason: string | null = null;
    if (qualifiedAlternatives.length === 0) {
      noAlternativesReason = "no_safer_option";
    }

    const result = {
      status: "ok",
      currentDrug: {
        inn: currentINN,
        trade_names: matchedTradeNames,
        class_label: drugClassInfo.class_label,
        dietary_summary: {
          worst_tier: currentSummary.worst_tier,
          avg_score: currentSummary.avg_score,
          high_count: currentSummary.high_count,
          med_count: currentSummary.med_count,
          low_count: currentSummary.low_count,
          high_foods: currentSummary.high_foods,
          critical_rules_fired: currentSummary.critical_rules_fired,
        },
      },
      dietaryPattern,
      cycleContext,
      virtualMedContext: virtualMedsList,
      class_wide: false,
      class_wide_note: null,
      dietary_timing_advice: null,
      qualified_alternatives: qualifiedAlternatives,
      no_alternatives_reason: noAlternativesReason,
      advisory_warning: "This simulation identifies pharmacological interaction patterns only. Therapeutic substitution requires clinical assessment of efficacy, contraindications, renal function, patient history, and in some cases specialist approval. HealthOpt does not prescribe.",
      disclaimer: "For professional reference only. Not a substitution recommendation.",
    };

    // Cache the result
    simulationCache.set(cacheKey, { result, timestamp: Date.now() });

    res.status(200).json(result);
  });

  app.post("/api/professional/patient/:patientId/interactions/:interactionId/report", async (req, res) => {
    const professional = getProfessionalFromRequest(req);
    const patientId = String(req.params.patientId || "").trim();
    const interactionId = String(req.params.interactionId || "").trim();
    if (!professional) {
      return res.status(401).json({ ok: false, detail: "Unauthorized." });
    }
    const link = db.prepare("SELECT 1 FROM professional_patient_links WHERE professional_id = ? AND patient_user_id = ?").get(professional.id, patientId);
    if (!link) {
      return res.status(403).json({ ok: false, detail: "Patient not linked." });
    }

    const row = db.prepare("SELECT * FROM interaction_history WHERE id = ? AND user_id = ?").get(interactionId, patientId) as any;
    if (!row) {
      return res.status(404).json({ ok: false, detail: "Interaction not found." });
    }

    const blood = db.prepare("SELECT * FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(patientId) as any;
    const cycle = getLatestCycleContext(patientId);
    const activeVirtualMeds = getActiveVirtualMeds(patientId);
    const lines: string[] = [];
    lines.push("HealthOpt Clinical Decision Support Report");
    lines.push(`Generated: ${new Date().toISOString()}`);
    lines.push(`Professional: ${professional.name} (${professional.role})`);
    lines.push(`Patient: ${getPatientDisplayName(patientId)}`);
    lines.push(`Interaction: ${String(row.drug || "Unknown")} x ${String(row.food || "Unknown")}`);
    lines.push(`Tier: ${String(row.tier || "NA")} | Score: ${Number(row.score || 0).toFixed(3)}`);
    lines.push(`Mechanism: ${String(row.mechanism || "")}`);
    if (blood) {
      lines.push(`Blood test date: ${String(blood.date || "NA")}`);
      lines.push(`Ferritin: ${String(blood.ferritin ?? "NA")}`);
      lines.push(`Hemoglobin: ${String(blood.hemoglobin ?? "NA")}`);
      lines.push(`Vitamin D: ${String(blood.vitaminD ?? "NA")}`);
    }
    if (cycle?.active) {
      lines.push(`Cycle phase: ${String(cycle.phase || "NA")}`);
    }
    if (activeVirtualMeds.length > 0) {
      lines.push(`Active virtual medications: ${activeVirtualMeds.map((med) => med.public_label).join(", ")}`);
    }
    const pyRes = await fetch("http://localhost:8000/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drug: row.drug, food: row.food, language: "en" }),
    });
    if (pyRes.ok) {
      const py = await pyRes.json() as any;
      lines.push(`LightGCN: ${Number(py?.lgn_score ?? 0).toFixed(3)}`);
      lines.push(`KGE: ${Number(py?.kge_score ?? 0).toFixed(3)}`);
      lines.push(`HKG: ${Number(py?.graph_score ?? 0).toFixed(3)}`);
      lines.push(`Fusion: ${Number(py?.fusion_score ?? row.score ?? 0).toFixed(3)}`);
    }
    lines.push("");
    lines.push("For clinical decision support only. Not a substitute for professional judgment.");

    const pdfBuffer = buildSimplePdfFromLines(lines);
    const dateStamp = new Date().toISOString().slice(0, 10);
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename=clinical-report-${dateStamp}-${interactionId}.pdf`);
    res.send(pdfBuffer);
  });

  app.get("/api/backend-status", async (_req, res) => {
    try {
      const pyHealth = await fetch("http://localhost:8000/health");
      if (!pyHealth.ok) {
        return res.status(503).json({
          ready: false,
          loading: true,
          status: "loading",
          detail: `Backend returned ${pyHealth.status}`,
        });
      }
      const payload = await pyHealth.json() as any;
      return res.json({
        ready: Boolean(payload?.ready),
        loading: Boolean(payload?.loading),
        status: String(payload?.status || "unknown"),
        error: payload?.error || null,
      });
    } catch (err) {
      return res.status(503).json({
        ready: false,
        loading: true,
        status: "unreachable",
        detail: String((err as Error).message || err),
      });
    }
  });

  // Get Profile
  app.get("/api/profile", (req, res) => {
    const row = db.prepare("SELECT gender, age, daily_medications, plan FROM profile_by_user WHERE user_id = ?").get(req.userId);
    res.json(row || { gender: 'female', age: null, daily_medications: '', plan: 'free' });
  });

  // Update Profile
  app.post("/api/profile", (req, res) => {
    const { gender, age, daily_medications, plan } = req.body;
    const ageValue = age === null || age === undefined || age === '' ? null : Number(age);
    try {
      db.prepare(`
        INSERT INTO profile_by_user (user_id, gender, age, daily_medications, plan)
        VALUES (?, ?, ?, ?, COALESCE(?, 'free'))
        ON CONFLICT(user_id) DO UPDATE SET
          gender = excluded.gender,
          age = excluded.age,
          daily_medications = excluded.daily_medications,
          plan = COALESCE(excluded.plan, profile_by_user.plan)
      `).run(req.userId, gender, ageValue, daily_medications, plan ?? null);
      res.json({ status: "ok" });
    } catch (err) {
      console.error('Failed to save profile:', err);
      res.status(500).json({ status: 'error', detail: 'Failed to save profile' });
    }
  });

  app.get("/api/subscription", (req, res) => {
    const auth = getUserAuth(req.userId || "");
    const plan = getUserPlan(req.userId || "");
    res.json({ plan, isPremium: plan === "pro", authenticated: auth.authenticated, email: auth.email });
  });

  app.post("/api/subscription/plan", (req, res) => {
    const nextPlan = String(req.body?.plan || "free").toLowerCase();
    const allowed = new Set(["free", "pro"]);
    if (!allowed.has(nextPlan)) {
      return res.status(400).json({ detail: "Invalid plan. Use 'free' or 'pro'." });
    }

    const auth = getUserAuth(req.userId || "");
    if (auth.authenticated && auth.email) {
      db.prepare("UPDATE auth_accounts SET plan = ? WHERE email = ?").run(nextPlan, auth.email);
    }

    db.prepare(`
      INSERT INTO profile_by_user (user_id, gender, age, daily_medications, plan)
      VALUES (?, 'female', NULL, '', ?)
      ON CONFLICT(user_id) DO UPDATE SET plan = excluded.plan
    `).run(req.userId, nextPlan);

    res.json({
      status: "ok",
      plan: nextPlan,
      isPremium: nextPlan === "pro",
      authenticated: auth.authenticated,
    });
  });

  app.get("/api/usage", (req, res) => {
    const countRow = db.prepare(
      `SELECT COUNT(*) AS scans_today
       FROM scan_usage
       WHERE user_id = ? AND date(scanned_at, 'localtime') = ${todayKeySql}`
    ).get(req.userId) as any;
    const scansToday = Number(countRow?.scans_today || 0);
    res.json({ scansToday, freeDailyLimit: FREE_DAILY_SCAN_LIMIT });
  });

  // PDF Analysis using local text parsing first, Gemini only as fallback.
  app.post("/api/analyze-pdf", async (req, res) => {
    const plan = getUserPlan(req.userId || "");
    if (plan !== "pro") {
      return res.status(402).json({ detail: "PDF extraction is a Pro feature.", code: "PREMIUM_REQUIRED" });
    }

    const { pdfBase64 } = req.body;

    try {
      const pdfBuffer = Buffer.from(String(pdfBase64 || ""), "base64");
      const result = await extractBloodFieldsFromPdfBuffer(pdfBuffer);
      res.json(result);
    } catch (error) {
      console.error("PDF Analysis Error:", error);
      res.status(500).json({ error: "Failed to analyze PDF" });
    }
  });

  app.post("/api/analyze-blood-raw", async (req, res) => {
    const plan = getUserPlan(req.userId || "");
    if (plan !== "pro") {
      return res.status(402).json({ detail: "QR blood scan is a Pro feature.", code: "PREMIUM_REQUIRED" });
    }

    const rawText = String(req.body?.rawText || "").trim();
    if (!rawText) {
      return res.status(400).json({ detail: "Missing rawText payload." });
    }

    try {
      const result = extractBloodFieldsFromText(rawText);
      res.json(result);
    } catch (error) {
      console.error("Raw QR Analysis Error:", error);
      res.status(500).json({ error: "Failed to analyze raw blood payload" });
    }
  });

  app.post("/api/analyze-blood-url", async (req, res) => {
    const plan = getUserPlan(req.userId || "");
    if (plan !== "pro") {
      return res.status(402).json({ detail: "QR blood scan is a Pro feature.", code: "PREMIUM_REQUIRED" });
    }

    const url = String(req.body?.url || "").trim();
    if (!url || !/^https?:\/\//i.test(url)) {
      return res.status(400).json({ detail: "Missing or invalid URL." });
    }

    try {
      const pageRes = await fetch(url);
      const contentType = String(pageRes.headers.get("content-type") || "").toLowerCase();
      const pageBuffer = Buffer.from(await pageRes.arrayBuffer());

      let pdfBuffer = pageBuffer;
      if (!contentType.includes("application/pdf")) {
        const html = pageBuffer.toString("utf-8");
        const pdfMatch = html.match(/href=["']([^"']*\/result\/[^"']+)["']/i);
        if (!pdfMatch?.[1]) {
          return res.status(422).json({ detail: "QR URL did not expose a downloadable PDF report." });
        }

        const pdfUrl = new URL(pdfMatch[1], url).toString();
        const pdfRes = await fetch(pdfUrl);
        if (!pdfRes.ok) {
          return res.status(502).json({ detail: `Failed to fetch PDF report from QR URL (${pdfRes.status}).` });
        }
        pdfBuffer = Buffer.from(await pdfRes.arrayBuffer());
      }

      const pdfBase64 = pdfBuffer.toString("base64");
      const result = await extractBloodFieldsFromPdfBuffer(Buffer.from(pdfBase64, "base64"));
      res.json(result);
    } catch (error) {
      console.error("Blood URL Analysis Error:", error);
      res.status(500).json({ error: "Failed to analyze blood report URL" });
    }
  });

  // Get latest blood test
  app.get("/api/blood-tests/latest", (req, res) => {
    const row = db.prepare("SELECT * FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 1").get(req.userId);
    res.json(row || {});
  });

  app.get("/api/virtual-medications/active", (req, res) => {
    const active = getActiveVirtualMeds(req.userId || "");
    res.json(active);
  });

  // Save blood test
  app.post("/api/blood-tests", (req, res) => {
    const body = req.body || {};
    const pickNumber = (...keys: string[]) => {
      for (const key of keys) {
        const raw = body[key];
        if (raw === null || raw === undefined || raw === "") continue;
        const n = Number(raw);
        if (!Number.isNaN(n)) return n;
      }
      return null;
    };

    const ferritin = pickNumber("ferritin", "ferritine");
    const hemoglobin = pickNumber("hemoglobin", "hemoglobine");
    const vitaminD = pickNumber("vitaminD", "vitD");
    const calcium = pickNumber("calcium");
    const b12 = pickNumber("b12", "vitB12");
    const magnesium = pickNumber("magnesium");
    const zinc = pickNumber("zinc");
    const folate = pickNumber("folate", "folate_serique");
    const iode_urinaire = pickNumber("iode_urinaire");
    const albumine = pickNumber("albumine");
    const tsh = pickNumber("tsh");
    const glycemie_jejun = pickNumber("glycemie_jejun");
    const hba1c = pickNumber("hba1c");
    const triglycerides = pickNumber("triglycerides");
    const ldl = pickNumber("ldl");
    const ratio_albumine_creatinine = pickNumber("ratio_albumine_creatinine");

    const info = db.prepare(`
      INSERT INTO blood_tests (
        user_id, ferritin, hemoglobin, vitaminD, calcium, b12, magnesium, zinc, folate,
        iode_urinaire, albumine, tsh, glycemie_jejun, hba1c, triglycerides, ldl, ratio_albumine_creatinine
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      req.userId,
      ferritin,
      hemoglobin,
      vitaminD,
      calcium,
      b12,
      magnesium,
      zinc,
      folate,
      iode_urinaire,
      albumine,
      tsh,
      glycemie_jejun,
      hba1c,
      triglycerides,
      ldl,
      ratio_albumine_creatinine,
    );

    const snapshot = getLatestBloodSnapshot(req.userId || "");
    const baselineSignals = evaluateModel2Signals(snapshot);
    const mlResult = runModel2Inference(snapshot);
    const mergedSignals = mergeMlSignals(baselineSignals, mlResult);
    refreshVirtualMedications(req.userId || "", mergedSignals);

    // Auto-snooze referrals related to biomarkers since a new blood test was just saved
    try {
      const snoozeKeys = ['missing_biomarker', 'stale_biomarkers', 'stale_biomarkers_90_highrisk', 'stale_biomarkers_180'];
      const until = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString();
      for (const k of snoozeKeys) {
        db.prepare("INSERT INTO user_referral_dismissals (user_id, trigger_type, dismissed_at, snoozed_until) VALUES (?, ?, CURRENT_TIMESTAMP, ?)")
          .run(req.userId, k, until);
      }
    } catch (e) {
      console.error('Failed to auto-snooze referrals after blood save', e);
    }

    res.json({ id: info.lastInsertRowid });
  });

  app.post("/api/blood-tests/clear", (req, res) => {
    const info = db.prepare(`
      INSERT INTO blood_tests (
        user_id, ferritin, hemoglobin, vitaminD, calcium, b12, magnesium, zinc, folate,
        iode_urinaire, albumine, tsh, glycemie_jejun, hba1c, triglycerides, ldl, ratio_albumine_creatinine
      )
      VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    `).run(req.userId);

    // Hard clear active deficiency artifacts so UI and exports are immediately clean.
    const clearedVirtual = db.prepare("DELETE FROM virtual_medications WHERE user_id = ?").run(req.userId || "");
    refreshVirtualMedications(req.userId || "", []);

    res.json({
      status: "ok",
      id: info.lastInsertRowid,
      clearedVirtualCount: Number(clearedVirtual?.changes || 0),
    });
  });

  // Get cycle info
  app.get("/api/cycle", (req, res) => {
    const row = db.prepare("SELECT * FROM cycle_logs WHERE user_id = ? ORDER BY start_date DESC LIMIT 1").get(req.userId);
    res.json(row || {});
  });

  // Save cycle start
  app.post("/api/cycle", (req, res) => {
    const { start_date, duration, period_length } = req.body;
    const parsedDuration = Number(duration);
    const safeDuration = Number.isFinite(parsedDuration)
      ? Math.max(20, Math.min(40, Math.round(parsedDuration)))
      : 28;
    const parsedPeriodLength = Number(period_length);
    const safePeriodLength = Number.isFinite(parsedPeriodLength)
      ? Math.max(2, Math.min(10, Math.round(parsedPeriodLength)))
      : 5;
    db.prepare("INSERT INTO cycle_logs (user_id, start_date, duration, period_length) VALUES (?, ?, ?, ?)")
      .run(req.userId, start_date, safeDuration, safePeriodLength);
    res.json({ status: "ok" });
  });

  // Clear cycle history
  app.delete("/api/cycle", (req, res) => {
    db.prepare("DELETE FROM cycle_logs WHERE user_id = ?").run(req.userId);
    res.json({ status: "ok" });
  });

  // Get history
  app.get("/api/history", (req, res) => {
    const rows = db.prepare("SELECT * FROM interaction_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 25").all(req.userId);
    res.json(rows);
  });

  app.post("/api/history/:id/consumed", (req, res) => {
    const id = Number(req.params.id);
    const consumed = Boolean(req.body?.consumed);
    if (!Number.isFinite(id)) {
      return res.status(400).json({ detail: "Invalid history id" });
    }

    const found = db.prepare("SELECT id FROM interaction_history WHERE id = ? AND user_id = ?").get(id, req.userId);
    if (!found) {
      return res.status(404).json({ detail: "History item not found" });
    }

    db.prepare(
      `UPDATE interaction_history
       SET consumed = ?, consumed_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END
       WHERE id = ? AND user_id = ?`
    ).run(consumed ? 1 : 0, consumed ? 1 : 0, id, req.userId);

    res.json({ status: "ok", id, consumed });
  });

  app.post("/api/history/export", (req, res) => {
    const plan = getUserPlan(req.userId || "");
    if (plan !== "pro") {
      return res.status(402).json({
        detail: "Physician report export is a Pro feature.",
        code: "PREMIUM_REQUIRED",
      });
    }

    const includeBloodTrends = Boolean(req.body?.includeBloodTrends);

    const interactions = db.prepare(
      "SELECT * FROM interaction_history WHERE user_id = ? AND consumed = 1 ORDER BY COALESCE(consumed_at, timestamp) DESC LIMIT 300"
    ).all(req.userId) as any[];

    const bloodTrends = includeBloodTrends
      ? db.prepare("SELECT * FROM blood_tests WHERE user_id = ? ORDER BY date DESC LIMIT 20").all(req.userId)
      : [];

    const profile = db.prepare("SELECT gender, daily_medications, plan FROM profile_by_user WHERE user_id = ?").get(req.userId) as any;
    const lines: string[] = [];
    const stamp = new Date().toISOString();
    lines.push("HealthOpt Physician Report");
    lines.push(`Generated: ${stamp}`);
    lines.push(`Plan: ${String(profile?.plan || "free").toUpperCase()}`);
    lines.push(`Gender: ${String(profile?.gender || "unknown")}`);
    lines.push("");
    lines.push("Consumed interactions:");

    if (interactions.length === 0) {
      lines.push("No consumed interactions logged yet.");
    } else {
      interactions.forEach((row, index) => {
        const when = String(row?.consumed_at || row?.timestamp || "");
        const score = Number(row?.score || 0);
        lines.push(`${index + 1}. ${row?.drug || "Unknown drug"} x ${row?.food || "Unknown food"}`);
        lines.push(`   Tier: ${String(row?.tier || "NA")} | Score: ${score.toFixed(3)} | Logged: ${when || "NA"}`);
        const mechanism = String(row?.mechanism || "").trim();
        for (const wrapped of wrapPdfLine(mechanism, 86)) {
          lines.push(`   ${wrapped}`);
        }
        lines.push("");
      });
    }

    if (includeBloodTrends) {
      lines.push("Blood test trends (latest):");
      if (bloodTrends.length === 0) {
        lines.push("No blood tests available.");
      } else {
        const latest = bloodTrends[0] as any;
        lines.push(`Date: ${String(latest?.date || "NA")}`);
        const biomarkers: Array<[string, string]> = [
          ["Ferritin", String(latest?.ferritin ?? "NA")],
          ["Hemoglobin", String(latest?.hemoglobin ?? "NA")],
          ["Vitamin D", String(latest?.vitaminD ?? "NA")],
          ["B12", String(latest?.b12 ?? "NA")],
          ["Folate", String(latest?.folate ?? "NA")],
          ["TSH", String(latest?.tsh ?? "NA")],
          ["HbA1c", String(latest?.hba1c ?? "NA")],
          ["LDL", String(latest?.ldl ?? "NA")],
        ];
        biomarkers.forEach(([label, value]) => lines.push(`${label}: ${value}`));
      }
    }

    const pdfBuffer = buildSimplePdfFromLines(lines);
    const dateStamp = new Date().toISOString().slice(0, 10);
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename=physician-report-${dateStamp}.pdf`);
    res.send(pdfBuffer);
  });

  // Prediction Engine — calls DFinder Python API (api.py on port 8000)
  app.post("/api/predict", async (req, res) => {
    const { food, language } = req.body;
    const manualDrug = String(req.body?.manualDrug || req.body?.drug || "").trim();
    const hasFoodContextModifiers = /\b(without|no|sans|only)\b/i.test(String(food || ""));

    db.prepare("INSERT INTO scan_usage (user_id) VALUES (?)").run(req.userId);

    // Guard against cold-start requests while Python model is still warming up.
    try {
      const pyHealth = await fetch("http://localhost:8000/health");
      if (!pyHealth.ok) {
        return res.status(503).json({
          detail: "DFinder backend is warming up.",
          code: "BACKEND_WARMING_UP",
        });
      }
      const status = await pyHealth.json() as any;
      if (!status?.ready) {
        return res.status(503).json({
          detail: status?.status === "error"
            ? `DFinder backend failed to initialize: ${status?.error || "unknown error"}`
            : "DFinder backend is warming up.",
          code: status?.status === "error" ? "BACKEND_ERROR" : "BACKEND_WARMING_UP",
        });
      }
    } catch (_err) {
      return res.status(503).json({
        detail: "DFinder backend is not reachable.",
        code: "BACKEND_UNREACHABLE",
      });
    }

    // 1. Fetch context
    const profile = db.prepare("SELECT * FROM profile_by_user WHERE user_id = ?").get(req.userId) as any;
    const blood = getLatestBloodSnapshot(req.userId || "");
    const cycleContext = getLatestCycleContext(req.userId || "");
    const ageValue = profile?.age === null || profile?.age === undefined || profile?.age === '' ? null : Number(profile.age);

    const baselineSignals = evaluateModel2Signals(blood);
    const mlResult = runModel2Inference(blood);
    const model2Signals = mergeMlSignals(baselineSignals, mlResult);
    refreshVirtualMedications(req.userId || "", model2Signals);
    const activeVirtualMeds = getActiveVirtualMeds(req.userId || "");

    const dailyDrugs: string[] = profile?.daily_medications
      ? profile.daily_medications.split(',').map((s: string) => s.trim()).filter(Boolean)
      : [];

    const virtualDrugs: string[] = activeVirtualMeds.map((v) => v.drug_name);
    const virtualDrugMap = new Map(activeVirtualMeds.map((v) => [v.drug_name.toLowerCase(), v]));

    // Keep real and virtual medication contexts separate, even for the same drug name.
    type DrugTestContext = {
      drug: string;
      source: 'PROFILE' | 'MANUAL' | 'VIRTUAL';
      virtualMeta?: {
        drug_name: string;
        public_label: string;
        signal_key: string;
        signal_reason: string;
        severity: 'LOW' | 'MEDIUM' | 'HIGH';
      };
    };

    const contexts: DrugTestContext[] = [];
    for (const d of dailyDrugs) {
      contexts.push({ drug: d.trim(), source: 'PROFILE' });
    }
    if (manualDrug && manualDrug.trim()) {
      contexts.push({ drug: manualDrug.trim(), source: 'MANUAL' });
    }
    for (const vm of activeVirtualMeds) {
      contexts.push({ drug: vm.drug_name.trim(), source: 'VIRTUAL', virtualMeta: vm });
    }

    const seen = new Set<string>();
    const testsToRun: DrugTestContext[] = [];
    for (const c of contexts) {
      const norm = c.drug.trim().toLowerCase();
      if (!norm) continue;
      const key = `${c.source}:${norm}`;
      if (seen.has(key)) continue;
      seen.add(key);
      testsToRun.push(c);
    }

    const results: any[] = [];

    const scansTodayRow = db.prepare(
      `SELECT COUNT(*) AS scans_today
       FROM scan_usage
       WHERE user_id = ? AND date(scanned_at, 'localtime') = ${todayKeySql}`
    ).get(req.userId) as any;
    const scansToday = Number(scansTodayRow?.scans_today || 0);
    const plan = getUserPlan(req.userId || "");

    // 2. Call Python DFinder API for each context
    for (const testCtx of testsToRun) {
      const drug = testCtx.drug;
      try {
        const pyRes = await fetch('http://localhost:8000/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ drug, food, language })
        });
        if (!pyRes.ok) throw new Error(`DFinder API returned ${pyRes.status}`);
        const py = await pyRes.json() as any;

        // Format physicochemical warnings as readable strings
        const physWarnings: string[] = (py.physicochemical_warnings || []).map(
          (w: any) => `[${w.severity}] ${w.rule}: ${w.mechanism}`
        );

        // Deduplicated enzyme list from graph + KGE layers
        const graphPath: string[] = [
          ...(py.graph_enzymes || []),
          ...(py.kge_enzymes  || [])
        ].filter((v: string, i: number, a: string[]) => a.indexOf(v) === i).slice(0, 5);

        const virtualMeta = testCtx.source === 'VIRTUAL' ? testCtx.virtualMeta : undefined;
        const publicDrugLabel = virtualMeta ? `Nutrient: ${virtualMeta.public_label.replace(/\s*Support\s*$/i, "")}` : (py.drug_input || drug);

        const physWarningObjects: any[] = Array.isArray(py.physicochemical_warnings) ? py.physicochemical_warnings : [];
        const triggerCompounds = Array.from(new Set(
          physWarningObjects
            .map((w: any) => String(w?.trigger_compound || "").trim())
            .filter(Boolean)
        ));
        const triggerSignals = Array.from(new Set(
          physWarningObjects
            .map((w: any) => String(w?.food_signal || "").trim())
            .filter(Boolean)
        ));

        const maskedExplanation = virtualMeta
          ? maskDrugName(String(py.explanation || ""), virtualMeta.drug_name, virtualMeta.public_label)
          : py.explanation;

        const finalMechanism = virtualMeta
          ? toFoodNutrientNotice(String(py.food || food), virtualMeta.public_label, virtualMeta.signal_reason, maskedExplanation)
          : maskedExplanation;

        // Virtual meds should only produce a notice when DFinder indicates an interaction.
        const pyTier = String(py.confidence || '').toUpperCase();
        const isVirtualInteraction = !virtualMeta || (pyTier && pyTier !== 'INSUFFICIENT');
        const keepVirtualForContext = Boolean(virtualMeta) && hasFoodContextModifiers;
        if (!isVirtualInteraction) {
          if (!keepVirtualForContext) {
            continue;
          }
        }

        const noTriggerAfterContext = Boolean(virtualMeta) && !isVirtualInteraction && keepVirtualForContext;

        const virtualSimpleView = virtualMeta
          ? buildVirtualNutrientSimpleView(
              virtualMeta.public_label,
              String(py.food || food),
              virtualMeta.signal_reason,
              String(py.confidence || 'LOW'),
              { compounds: triggerCompounds, signals: triggerSignals },
              noTriggerAfterContext,
            )
          : undefined;

        if (!isVirtualInteraction && !keepVirtualForContext) {
          continue;
        }

        const cyclePkAdjustment = !virtualMeta
          ? buildCyclePkAdjustment(
              cycleContext,
              graphPath,
              String(py.confidence || 'LOW'),
              ageValue,
              publicDrugLabel,
              String(py.food || food),
            )
          : null;

        const hormonalWordingPolicy = py.hormonal_wording_policy || undefined;
        const cycleUserNote = buildCycleNoteForUser(cyclePkAdjustment, hormonalWordingPolicy);

        const effectiveTier = noTriggerAfterContext
          ? 'INFO'
          : (cyclePkAdjustment?.adjusted_tier || String(py.confidence || 'LOW'));
        const mechanismWithCycle = cycleUserNote
          ? `${String(finalMechanism || '').trim()} ${cycleUserNote}`.trim()
          : finalMechanism;

        const baseSimpleView = addTriggerDetailsToSimpleView(
          virtualSimpleView || py.simple_view || undefined,
          py,
          String(py.food || food),
        );
        const mergedSimpleView = cycleUserNote
          ? mergeCycleContextIntoSimpleView(baseSimpleView, cycleUserNote)
          : baseSimpleView;

        const hormonalContextNote = cycleContext.active
          ? `Cycle context: ${cycleContext.phase} phase detected${ageValue !== null ? `; age ${ageValue} years` : ''}. ${cycleUserNote || 'This may change interaction strength.'}`
          : (ageValue !== null ? `Age context: ${ageValue} years.` : undefined);

        results.push({
          drug        : publicDrugLabel,
          food        : py.food,
          tier        : effectiveTier,
          score       : py.fusion_score,
          graph_score : py.graph_score,
          graph_found : py.graph_found,
          kge_score   : py.kge_score,
          kge_found   : py.kge_found,
          lgn_score   : py.lgn_score,
          norm_graph  : py.norm_graph,
          norm_kge    : py.norm_kge,
          norm_lgn    : py.norm_lgn,
          mechanism   : mechanismWithCycle,
          flags       : py.flags || [],
          simple_view : mergedSimpleView,
          technical_view: py.technical_view || undefined,
          physicochemical_warnings: py.physicochemical_warnings || undefined,
          graph_path  : py.graph_path || py.graph_enzymes || undefined,
          kge_enzymes : py.kge_enzymes || undefined,
          fusion_score: py.fusion_score || undefined,
          drug_name   : publicDrugLabel,
          food_name   : py.food,
          physicochemicalWarnings: physWarnings.length > 0 ? physWarnings : undefined,
          graphPath   : graphPath.length > 0 ? graphPath : undefined,
          resolutionNote: py.resolution_note || undefined,
          llmCompounds: py.llm_compounds  || undefined,
          type        : virtualMeta ? 'NUTRIENT_FOOD' : 'DRUG_FOOD',
          medication_source: testCtx.source,
          mechanism_assembly: py.mechanism_assembly || undefined,
          hormonal_wording_policy: py.hormonal_wording_policy || undefined,
          cycle_pk_adjustment: cyclePkAdjustment,
          hormonal_context: cycleContext.active ? {
            age: ageValue,
            cycle_day: cycleContext.day,
            cycle_phase: cycleContext.phase,
          } : (ageValue !== null ? { age: ageValue } : undefined),
          cycle_context_note: hormonalContextNote,
        });
      } catch (err) {
        if (testCtx.source === 'VIRTUAL') {
          continue;
        }
        // Graceful fallback when Python backend is not running
        results.push({
          drug     : drug,
          food     : food,
          tier     : 'INSUFFICIENT',
          score    : 0,
          mechanism: 'DFinder backend unavailable. Start with: uvicorn api:app --port 8000',
          flags    : ['BACKEND_ERROR'],
          type     : 'DRUG_FOOD',
        });
      }
    }

    // ── REMOVED hardcoded if/else keyword matching (warfarin+grapefruit, etc.)
    // The Python DFinder pipeline now handles all drug-food logic via:
    //   Layer 0 — Physicochemical rules (chelation, VKA, MAOI, K-sparing, acid)
    //   Layer 1 — Graph Query over HKG (enzyme overlap)
    //   Layer 2 — Mechanistic KGE (RotatE, MRR=0.376)
    //   Layer 3 — LightGCN + DNN (AUC=0.9035, 5000 drugs × 1894 foods)
    // ─────────────────────────────────────────────────────────────────────────

    // 3. Nutrient context is now fully driven by DFinder virtual-med pipeline.

    // 4. Persist significant results to history
    results
      .filter(r => r.tier !== 'LOW' && r.tier !== 'INSUFFICIENT' && r.tier !== 'INFO')
      .forEach(r => {
        db.prepare(
          'INSERT INTO interaction_history (user_id, drug, food, tier, score, mechanism) VALUES (?, ?, ?, ?, ?, ?)'
        ).run(req.userId, r.drug, r.food, r.tier, r.score, r.mechanism);
      });

    res.json({
      results,
      hormonal_context: {
        age: ageValue,
        cycle_day: cycleContext.day,
        cycle_phase: cycleContext.phase,
        active: cycleContext.active,
      },
      model2: {
        integrated: true,
        mode: "hybrid-ml-threshold",
        mlRunnerOk: mlResult.runnerOk,
        mlRunnerError: mlResult.runnerError || null,
        mlPredictions: mlResult.predictions,
        activeSignals: model2Signals,
        activeVirtualMedicationCount: activeVirtualMeds.length,
      },
      usage: {
        scansToday,
        freeDailyLimit: FREE_DAILY_SCAN_LIMIT,
        plan,
      },
    });
  });


  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        hmr: { port: hmrPort },
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(process.cwd(), "dist")));
    app.get("*", (req, res) => {
      res.sendFile(path.join(process.cwd(), "dist", "index.html"));
    });
  }

  const listenWithFallback = (port: number) => {
    const server = app.listen(port, "0.0.0.0", () => {
      console.log(`HealthOpt Backend running on http://localhost:${port}`);
    });

    server.on("error", (err: NodeJS.ErrnoException) => {
      if (err.code === "EADDRINUSE") {
        const nextPort = port + 1;
        console.warn(`Port ${port} is in use, retrying on ${nextPort}...`);
        listenWithFallback(nextPort);
        return;
      }
      throw err;
    });
  };

  listenWithFallback(preferredPort);
}

startServer();

