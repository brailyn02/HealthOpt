/**
 * Pharmacist Dashboard backend routes.
 *
 * Designed for point-of-sale speed:
 *  - Curated knowledge base for the most-dispensed Algerian drugs (class, CYP profile,
 *    high/medium/safe foods, counseling scripts in FR/EN/AR).
 *  - SQLite caches for drug profiles, counseling scripts, and food checks.
 *  - Falls back to FastAPI DFinder /predict for unknown drug+food pairs and caches the
 *    result so subsequent counter visits are instant.
 *
 * All endpoints require the existing professional auth (Bearer token from
 * /api/professional/auth) with role === "pharmacist". Token verification is
 * delegated via a callback supplied by server.ts (verifyPharmacist).
 */

import type { Request, Response } from "express";
import type Database from "better-sqlite3";

export type TradeNameRow = {
  brand_name: string;
  inn_raw: string;
  inn_normalized: string;
  pipeline_drug: string;
  match_type: string;
};

export type ProfessionalContext = {
  id: string;
  role: string;
  name?: string;
  specialty?: string;
};

export type VerifyPharmacist = (req: Request) => ProfessionalContext | null;

type Lang = "fr" | "en" | "ar";

type FoodEntry = { name: string; reason?: string };

type DrugKnowledge = {
  key: string;                       // canonical lowercase id (e.g. "warfarin")
  inn: string;                       // display INN
  drug_class: { fr: string; en: string; ar: string };
  cyp_profile: {
    substrate?: string[];
    inhibitor?: string[];
    inducer?: string[];
    notes?: { fr: string; en: string; ar: string };
  };
  high_foods: FoodEntry[];
  medium_foods: FoodEntry[];
  safe_foods: FoodEntry[];
  contraindications?: Array<{
    food: string;
    mechanism: { fr: string; en: string; ar: string };
  }>;
  counseling: { fr: string[]; en: string[]; ar: string[] };
};

// ─── Curated Knowledge Base (top Algerian dispensed drugs) ───────────────────
// All foods use local North-African names. Counseling scripts are short,
// imperative, and read out loud-friendly. Add more entries here over time.
const KB: DrugKnowledge[] = [
  {
    key: "warfarin",
    inn: "Warfarin / Acenocoumarol",
    drug_class: {
      fr: "Anticoagulant — Antagoniste de la vitamine K",
      en: "Anticoagulant — Vitamin K Antagonist",
      ar: "مضاد تخثر — مضاد فيتامين ك",
    },
    cyp_profile: {
      substrate: ["CYP2C9", "CYP3A4", "CYP1A2"],
      inhibitor: [],
      inducer: [],
      notes: {
        fr: "Étroite marge thérapeutique. Surveiller l'INR.",
        en: "Narrow therapeutic index. Monitor INR.",
        ar: "هامش علاجي ضيق. يجب مراقبة الـ INR.",
      },
    },
    high_foods: [
      { name: "spinach (épinards / سبانخ)", reason: "high vitamin K" },
      { name: "parsley (persil / معدنوس)", reason: "high vitamin K" },
      { name: "mint tea (thé à la menthe / أتاي بالنعناع)", reason: "vitamin K, daily intake" },
      { name: "kale / chard (blette / سلق)", reason: "high vitamin K" },
      { name: "grapefruit (pamplemousse / بومبا)", reason: "CYP3A4 inhibition" },
      { name: "pomelo", reason: "CYP3A4 inhibition" },
      { name: "cranberry juice", reason: "potentiates anticoagulation" },
      { name: "green tea (high intake)", reason: "vitamin K" },
    ],
    medium_foods: [
      { name: "lettuce (laitue / خس)", reason: "moderate vitamin K" },
      { name: "broccoli", reason: "moderate vitamin K" },
      { name: "olive oil heavy meals", reason: "absorption variability" },
      { name: "garlic supplements", reason: "additive bleeding risk" },
      { name: "ginger in large amounts", reason: "additive bleeding risk" },
      { name: "iron supplements", reason: "absorption — separate by 2h" },
    ],
    safe_foods: [
      { name: "rice (riz / روز)" },
      { name: "couscous (semoule / كسكسي)" },
      { name: "chicken (poulet / دجاج)" },
      { name: "bread (khobz / خبز)" },
      { name: "dates (dattes / تمر)" },
      { name: "yogurt (yaourt / ياغورت)" },
      { name: "lamb / mutton" },
      { name: "fish (poisson / حوت)" },
    ],
    contraindications: [
      {
        food: "grapefruit / pomelo",
        mechanism: {
          fr: "Inhibition du CYP3A4 → augmentation des taux et risque hémorragique sévère.",
          en: "CYP3A4 inhibition raises drug levels and causes severe bleeding risk.",
          ar: "تثبيط CYP3A4 يرفع تركيز الدواء ويسبب خطر نزيف شديد.",
        },
      },
    ],
    counseling: {
      fr: [
        "Évitez de grandes portions d'épinards, persil ou thé à la menthe quotidien — ils diminuent l'effet du médicament.",
        "Gardez une consommation de légumes verts CONSTANTE — n'arrêtez pas, mais ne changez pas brutalement les quantités.",
        "Pamplemousse et bumba sont totalement interdits avec ce traitement.",
        "Si le patient prend du fer, séparer la prise de 2 heures.",
        "Toute fièvre, ecchymose ou saignement inhabituel → contrôle INR immédiat.",
      ],
      en: [
        "Avoid large portions of spinach, parsley, or daily mint tea — they reduce this medication's effect.",
        "Keep green vegetable intake CONSISTENT — don't eliminate, just keep portions stable day to day.",
        "Grapefruit and pomelo must be completely avoided with this medication.",
        "If the patient takes iron supplements, separate them by 2 hours.",
        "Any fever, bruising or unusual bleeding → check INR immediately.",
      ],
      ar: [
        "تجنب الكميات الكبيرة من السبانخ، المعدنوس أو الأتاي بالنعناع اليومي — تقلل من فعالية الدواء.",
        "حافظ على كمية ثابتة من الخضار الخضراء — لا توقفها لكن لا تغيّر الكمية فجأة.",
        "بومبا والپوميلو ممنوعان تمامًا مع هذا الدواء.",
        "إذا كان المريض يأخذ الحديد، افصل بين الأخذ بساعتين.",
        "أي حمى، كدمات أو نزيف غير عادي → افحص الـ INR فوراً.",
      ],
    },
  },
  {
    key: "atorvastatin",
    inn: "Atorvastatin",
    drug_class: {
      fr: "Hypolipémiant — Statine",
      en: "Lipid-lowering — Statin",
      ar: "خافض دهون — ستاتين",
    },
    cyp_profile: {
      substrate: ["CYP3A4"],
      inhibitor: [],
      inducer: [],
      notes: {
        fr: "Sensible aux inhibiteurs du CYP3A4 (jus de pamplemousse).",
        en: "Sensitive to CYP3A4 inhibitors (grapefruit juice).",
        ar: "حساس لمثبطات CYP3A4 (عصير البومبا).",
      },
    },
    high_foods: [
      { name: "grapefruit juice (jus de pamplemousse)", reason: "CYP3A4 inhibition → myopathy risk" },
      { name: "pomelo", reason: "CYP3A4 inhibition" },
      { name: "Seville orange", reason: "CYP3A4 inhibition" },
    ],
    medium_foods: [
      { name: "alcohol (excess)", reason: "liver enzyme rise" },
      { name: "high-fat fried meals", reason: "may affect tolerability" },
      { name: "red yeast rice", reason: "additive statin effect" },
    ],
    safe_foods: [
      { name: "oranges (orange table / تشينة)" },
      { name: "olive oil moderate" },
      { name: "fish (poisson / حوت)" },
      { name: "vegetables (légumes / خضرة)" },
      { name: "couscous" },
      { name: "yogurt" },
    ],
    contraindications: [
      {
        food: "grapefruit / pomelo",
        mechanism: {
          fr: "Inhibition intestinale du CYP3A4 → hausse des taux et risque de myopathie/rhabdomyolyse.",
          en: "Intestinal CYP3A4 inhibition raises levels and causes myopathy/rhabdomyolysis risk.",
          ar: "تثبيط CYP3A4 المعوي يرفع التركيز ويسبب خطر اعتلال عضلي.",
        },
      },
    ],
    counseling: {
      fr: [
        "Pas de jus de pamplemousse ni de pomelo pendant tout le traitement.",
        "Prendre le soir, de préférence avec un repas léger.",
        "Limiter l'alcool — risque hépatique additionnel.",
        "Toute douleur musculaire inhabituelle ou urines foncées → consulter immédiatement.",
        "Régime méditerranéen recommandé (poisson, huile d'olive, légumes).",
      ],
      en: [
        "No grapefruit or pomelo juice during the entire treatment.",
        "Take in the evening, preferably with a light meal.",
        "Limit alcohol — additional liver risk.",
        "Any unusual muscle pain or dark urine → consult immediately.",
        "Mediterranean diet is recommended (fish, olive oil, vegetables).",
      ],
      ar: [
        "ممنوع البومبا والپوميلو طوال فترة العلاج.",
        "تناوله في المساء مع وجبة خفيفة.",
        "قلل الكحول — خطر إضافي على الكبد.",
        "أي ألم عضلي غير عادي أو بول غامق → استشر فوراً.",
        "يُنصح بالنظام المتوسطي (سمك، زيت زيتون، خضار).",
      ],
    },
  },
  {
    key: "metformin",
    inn: "Metformin",
    drug_class: {
      fr: "Antidiabétique oral — Biguanide",
      en: "Oral antidiabetic — Biguanide",
      ar: "خافض سكر فموي — بيغوانيد",
    },
    cyp_profile: {
      notes: {
        fr: "Métabolisme non-CYP. Élimination rénale.",
        en: "Non-CYP metabolism. Renal elimination.",
        ar: "أيض غير CYP. إطراح كلوي.",
      },
    },
    high_foods: [
      { name: "alcohol (excess)", reason: "lactic acidosis risk" },
    ],
    medium_foods: [
      { name: "very high-sugar drinks", reason: "glycemic spikes" },
      { name: "energy drinks", reason: "glycemic disturbance" },
    ],
    safe_foods: [
      { name: "couscous (whole wheat)" },
      { name: "lentils (lentilles / عدس)" },
      { name: "chickpeas (pois chiches / حمص)" },
      { name: "vegetables" },
      { name: "bread (whole wheat)" },
      { name: "olive oil" },
      { name: "fish" },
      { name: "yogurt" },
    ],
    counseling: {
      fr: [
        "Toujours prendre à la fin du repas pour réduire les troubles digestifs.",
        "Pas d'alcool excessif — risque rare mais grave d'acidose lactique.",
        "Préférer les sucres lents (pain complet, semoule complète, lentilles).",
        "Boire suffisamment d'eau, surtout en été.",
        "En cas de jeûne (Ramadan), demander un ajustement avant de jeûner.",
      ],
      en: [
        "Always take at the end of a meal to reduce digestive upset.",
        "No excessive alcohol — rare but severe lactic acidosis risk.",
        "Prefer slow carbs (whole bread, whole semolina, lentils).",
        "Drink enough water, especially in summer.",
        "If fasting (Ramadan), request a dose adjustment beforehand.",
      ],
      ar: [
        "خذه دائمًا في نهاية الوجبة لتقليل الاضطرابات الهضمية.",
        "لا تفرط في الكحول — خطر نادر لكن خطير لحموضة اللاكتيك.",
        "فضّل السكريات البطيئة (خبز كامل، سميد كامل، عدس).",
        "اشرب ماء كافيًا خاصة في الصيف.",
        "في رمضان اطلب تعديل الجرعة قبل الصيام.",
      ],
    },
  },
  {
    key: "amoxicillin-clavulanate",
    inn: "Amoxicillin / Clavulanic acid",
    drug_class: {
      fr: "Antibiotique — Pénicilline + inhibiteur de bêta-lactamase",
      en: "Antibiotic — Penicillin + β-lactamase inhibitor",
      ar: "صاد حيوي — بنسلين + مثبط بيتا-لاكتاماز",
    },
    cyp_profile: {
      notes: {
        fr: "Pas d'interaction CYP majeure.",
        en: "No major CYP interactions.",
        ar: "لا توجد تفاعلات CYP رئيسية.",
      },
    },
    high_foods: [],
    medium_foods: [
      { name: "alcohol", reason: "hepatic burden, GI upset" },
      { name: "very high dairy with empty stomach", reason: "absorption variability" },
    ],
    safe_foods: [
      { name: "couscous" },
      { name: "rice" },
      { name: "chicken broth" },
      { name: "bread" },
      { name: "vegetables" },
      { name: "fruit" },
      { name: "yogurt with meal" },
      { name: "water" },
    ],
    counseling: {
      fr: [
        "Prendre au début du repas pour mieux tolérer.",
        "Compléter toute la durée du traitement, même si le patient se sent mieux.",
        "Pas d'alcool pendant le traitement.",
        "En cas d'éruption cutanée ou difficulté respiratoire → arrêter et consulter.",
        "Yaourt nature recommandé pour protéger la flore intestinale.",
      ],
      en: [
        "Take at the start of a meal to improve tolerance.",
        "Complete the full course even if the patient feels better.",
        "No alcohol during treatment.",
        "If rash or breathing difficulty → stop and seek care.",
        "Plain yogurt is recommended to protect gut flora.",
      ],
      ar: [
        "خذه في بداية الوجبة لتحسين التحمل.",
        "أكمل كامل مدة العلاج حتى لو شعر المريض بتحسن.",
        "لا تتناول الكحول خلال العلاج.",
        "في حال طفح جلدي أو صعوبة تنفس → أوقف الدواء واستشر.",
        "يُنصح بالياغورت الطبيعي لحماية الأمعاء.",
      ],
    },
  },
  {
    key: "paracetamol",
    inn: "Paracetamol (Acetaminophen)",
    drug_class: {
      fr: "Antalgique / Antipyrétique",
      en: "Analgesic / Antipyretic",
      ar: "مسكن / خافض حرارة",
    },
    cyp_profile: {
      substrate: ["CYP2E1"],
      notes: {
        fr: "Toxicité hépatique en cas de surdosage ou d'alcool chronique.",
        en: "Hepatotoxic on overdose or chronic alcohol use.",
        ar: "سمية كبدية عند الجرعة الزائدة أو إدمان الكحول.",
      },
    },
    high_foods: [],
    medium_foods: [
      { name: "alcohol (chronic / excess)", reason: "hepatotoxicity" },
    ],
    safe_foods: [
      { name: "water" },
      { name: "tea / coffee in moderation" },
      { name: "couscous, rice, bread" },
      { name: "fruits" },
      { name: "vegetables" },
      { name: "dairy" },
    ],
    counseling: {
      fr: [
        "Maximum 3 g par jour chez l'adulte sain — ne pas dépasser.",
        "Espacer chaque prise d'au moins 6 heures.",
        "Pas d'alcool excessif pendant le traitement.",
        "Vérifier que d'autres médicaments contre la grippe ne contiennent pas déjà du paracétamol.",
        "Si fièvre persistante > 3 jours → consulter.",
      ],
      en: [
        "Max 3 g per day in healthy adults — do not exceed.",
        "Space doses at least 6 hours apart.",
        "No excessive alcohol during treatment.",
        "Check other flu medications don't already contain paracetamol.",
        "If fever persists > 3 days → consult.",
      ],
      ar: [
        "الحد الأقصى 3 غ يوميًا للبالغ السليم — لا تتجاوز.",
        "افصل بين الجرعات 6 ساعات على الأقل.",
        "لا تفرط في الكحول خلال العلاج.",
        "تأكد أن أدوية الزكام الأخرى لا تحتوي على باراسيتامول.",
        "إذا استمرت الحمى أكثر من 3 أيام → استشر.",
      ],
    },
  },
  {
    key: "levothyroxine",
    inn: "Levothyroxine",
    drug_class: {
      fr: "Hormone thyroïdienne",
      en: "Thyroid hormone",
      ar: "هرمون درقي",
    },
    cyp_profile: {
      notes: {
        fr: "Absorption très sensible aux aliments et minéraux.",
        en: "Absorption highly sensitive to food and minerals.",
        ar: "الامتصاص حساس جدًا للطعام والمعادن.",
      },
    },
    high_foods: [
      { name: "couscous (phytic acid)", reason: "chelation, reduced absorption" },
      { name: "soy products", reason: "reduced absorption" },
      { name: "calcium-rich dairy at same time", reason: "chelation" },
      { name: "iron supplements", reason: "chelation" },
      { name: "coffee within 1 hour", reason: "reduced absorption ~30%" },
    ],
    medium_foods: [
      { name: "high-fiber breakfast at same time", reason: "absorption variability" },
      { name: "walnuts in large amounts", reason: "absorption" },
    ],
    safe_foods: [
      { name: "water (the ONLY thing to take it with)" },
      { name: "regular meals 1h later" },
      { name: "fruits later in day" },
      { name: "vegetables later in day" },
    ],
    counseling: {
      fr: [
        "À jeun, le matin, avec un grand verre d'eau uniquement.",
        "Attendre AU MOINS 30 à 60 minutes avant le café, le lait ou le petit-déjeuner.",
        "Séparer du fer, calcium, magnésium d'au moins 4 heures.",
        "Le couscous au petit-déjeuner doit être pris bien après le médicament.",
        "Ne pas changer de marque sans avis médical (bioéquivalence).",
      ],
      en: [
        "On an empty stomach in the morning, with a large glass of water only.",
        "Wait AT LEAST 30–60 minutes before coffee, milk, or breakfast.",
        "Separate from iron, calcium, magnesium by at least 4 hours.",
        "Breakfast couscous must be taken well after the medication.",
        "Do not switch brand without medical advice (bioequivalence).",
      ],
      ar: [
        "على معدة فارغة صباحًا، مع كوب ماء كبير فقط.",
        "انتظر 30 إلى 60 دقيقة على الأقل قبل القهوة أو الحليب أو الفطور.",
        "افصل عن الحديد والكالسيوم والمغنيسيوم بـ 4 ساعات على الأقل.",
        "كسكسي الفطور يؤخذ بعد الدواء بوقت كافٍ.",
        "لا تغيّر العلامة دون استشارة طبية.",
      ],
    },
  },
  {
    key: "ciprofloxacin",
    inn: "Ciprofloxacin",
    drug_class: {
      fr: "Antibiotique — Fluoroquinolone",
      en: "Antibiotic — Fluoroquinolone",
      ar: "صاد حيوي — كينولون",
    },
    cyp_profile: {
      inhibitor: ["CYP1A2"],
      notes: {
        fr: "Forte chélation par cations divalents.",
        en: "Strong chelation by divalent cations.",
        ar: "ارتباط قوي بالكاتيونات الثنائية.",
      },
    },
    high_foods: [
      { name: "dairy at same time (lait / حليب, yaourt)", reason: "calcium chelation" },
      { name: "calcium-fortified juice", reason: "chelation" },
      { name: "iron supplements", reason: "chelation" },
      { name: "antacids (Maalox)", reason: "chelation" },
      { name: "couscous mixed with milk", reason: "chelation" },
    ],
    medium_foods: [
      { name: "very strong coffee (CYP1A2 substrate buildup)", reason: "caffeine accumulation" },
      { name: "energy drinks", reason: "caffeine + cardiac" },
    ],
    safe_foods: [
      { name: "water" },
      { name: "bread" },
      { name: "chicken / fish" },
      { name: "vegetables" },
      { name: "fruits (separate from dairy)" },
      { name: "rice" },
    ],
    counseling: {
      fr: [
        "Pas de lait, yaourt ni Maalox 2 heures avant et 6 heures après.",
        "Bien s'hydrater pendant le traitement.",
        "Limiter le café et les boissons énergétiques (caféine retenue plus longtemps).",
        "Pas d'exposition solaire intense — risque de photosensibilité.",
        "Toute douleur tendineuse → arrêter et consulter.",
      ],
      en: [
        "No milk, yogurt or Maalox 2 hours before and 6 hours after.",
        "Stay well hydrated during treatment.",
        "Limit coffee and energy drinks (caffeine builds up).",
        "Avoid intense sun exposure — photosensitivity risk.",
        "Any tendon pain → stop and consult.",
      ],
      ar: [
        "ممنوع الحليب والياغورت والمالوكس قبل ساعتين وبعد 6 ساعات.",
        "اشرب ماء كافيًا خلال العلاج.",
        "قلل القهوة ومشروبات الطاقة (الكافيين يبقى أطول).",
        "تجنب التعرض الشديد للشمس — خطر حساسية ضوئية.",
        "أي ألم في الأوتار → أوقف الدواء واستشر.",
      ],
    },
  },
  {
    key: "omeprazole",
    inn: "Omeprazole",
    drug_class: {
      fr: "Inhibiteur de la pompe à protons (IPP)",
      en: "Proton pump inhibitor (PPI)",
      ar: "مثبط مضخة البروتون",
    },
    cyp_profile: {
      substrate: ["CYP2C19", "CYP3A4"],
      inhibitor: ["CYP2C19"],
      notes: {
        fr: "Réduit l'acidité gastrique → altère l'absorption d'autres médicaments.",
        en: "Reduces gastric acidity → alters absorption of other drugs.",
        ar: "يقلل حموضة المعدة → يغيّر امتصاص أدوية أخرى.",
      },
    },
    high_foods: [],
    medium_foods: [
      { name: "very acidic large meals", reason: "may reduce relief" },
      { name: "alcohol", reason: "GI irritation" },
      { name: "harissa (very spicy)", reason: "GI irritation" },
    ],
    safe_foods: [
      { name: "couscous" },
      { name: "rice" },
      { name: "bread" },
      { name: "vegetables" },
      { name: "lean chicken / fish" },
      { name: "yogurt" },
    ],
    counseling: {
      fr: [
        "Prendre 30 minutes avant le petit-déjeuner, avec un verre d'eau.",
        "Ne pas écraser ni croquer la gélule.",
        "Limiter les plats très épicés (harissa) et l'alcool.",
        "Si le patient prend du clopidogrel ou des antifongiques → demander avis.",
        "Ne pas prolonger sans suivi médical (> 8 semaines).",
      ],
      en: [
        "Take 30 minutes before breakfast with a glass of water.",
        "Do not crush or chew the capsule.",
        "Limit very spicy food (harissa) and alcohol.",
        "If patient takes clopidogrel or antifungals → ask for advice.",
        "Do not extend beyond 8 weeks without medical follow-up.",
      ],
      ar: [
        "خذه قبل الفطور بـ 30 دقيقة مع كوب ماء.",
        "لا تسحق أو تمضغ الكبسولة.",
        "قلل الطعام الحار جدًا (الهريسة) والكحول.",
        "إذا كان المريض يأخذ كلوبيدوغريل أو مضادات فطريات → اطلب استشارة.",
        "لا تطل العلاج فوق 8 أسابيع دون متابعة طبية.",
      ],
    },
  },
];

// Map well-known Algerian trade names → KB key. The trade-name CSV will catch
// many more, but this dictionary lets the dashboard recognize the ones a
// pharmacist will speak out loud the most.
const TRADE_TO_KEY: Record<string, string> = {
  sintrom: "warfarin",
  coumadine: "warfarin",
  warfarine: "warfarin",
  tahor: "atorvastatin",
  atorvastatine: "atorvastatin",
  lipitor: "atorvastatin",
  glucophage: "metformin",
  metformine: "metformin",
  augmentin: "amoxicillin-clavulanate",
  ciblor: "amoxicillin-clavulanate",
  amoxicilline: "amoxicillin-clavulanate",
  doliprane: "paracetamol",
  efferalgan: "paracetamol",
  paracetamol: "paracetamol",
  perfalgan: "paracetamol",
  levothyrox: "levothyroxine",
  levothyroxine: "levothyroxine",
  euthyrox: "levothyroxine",
  ciproxine: "ciprofloxacin",
  ciprofloxacine: "ciprofloxacin",
  ciflox: "ciprofloxacin",
  mopral: "omeprazole",
  omeprazole: "omeprazole",
  inipomp: "omeprazole",
};

const TOP_KB_KEYS = KB.map((k) => k.key);

// ─── Schema ──────────────────────────────────────────────────────────────────

export function ensurePharmacistSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS pharmacist_drug_cache (
      drug_key TEXT PRIMARY KEY,
      payload TEXT NOT NULL,
      cached_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS pharmacist_script_cache (
      drug_key TEXT NOT NULL,
      lang TEXT NOT NULL,
      payload TEXT NOT NULL,
      cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (drug_key, lang)
    );
    CREATE TABLE IF NOT EXISTS pharmacist_food_cache (
      drug_key TEXT NOT NULL,
      food_key TEXT NOT NULL,
      tier TEXT,
      score REAL,
      mechanism TEXT,
      cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (drug_key, food_key)
    );
  `);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function normalize(s: string): string {
  return String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\u0600-\u06ff ]/g, "")
    .trim();
}

function findKbForTrade(
  trade: string,
  tradeNameIndex: TradeNameRow[],
): { kb: DrugKnowledge | null; trade_match?: TradeNameRow; resolved_inn?: string } {
  const norm = normalize(trade);
  if (!norm) return { kb: null };

  // 1) direct trade-key map
  if (TRADE_TO_KEY[norm]) {
    const k = TRADE_TO_KEY[norm];
    return { kb: KB.find((x) => x.key === k) || null, resolved_inn: k };
  }
  // 2) algerian_brand_map.csv
  const tradeMatch =
    tradeNameIndex.find((t) => normalize(t.brand_name) === norm) ||
    tradeNameIndex.find((t) => normalize(t.brand_name).startsWith(norm)) ||
    tradeNameIndex.find((t) => normalize(t.pipeline_drug) === norm);
  if (tradeMatch) {
    const innKey = normalize(tradeMatch.pipeline_drug);
    const kb = KB.find((x) => x.key === innKey || normalize(x.inn).includes(innKey));
    return { kb: kb || null, trade_match: tradeMatch, resolved_inn: tradeMatch.pipeline_drug };
  }
  // 3) try direct INN match against KB
  const direct = KB.find((x) => x.key === norm || normalize(x.inn).includes(norm));
  if (direct) return { kb: direct, resolved_inn: direct.inn };
  return { kb: null };
}

function buildDrugProfilePayload(opts: {
  trade?: string;
  trade_match?: TradeNameRow | null;
  kb: DrugKnowledge | null;
  resolved_inn?: string;
}) {
  const { trade, trade_match, kb, resolved_inn } = opts;
  if (kb) {
    return {
      ok: true,
      drug_key: kb.key,
      trade_name: trade_match?.brand_name || trade || kb.inn,
      inn: kb.inn,
      pipeline_drug: trade_match?.pipeline_drug || resolved_inn || kb.inn,
      drug_class: kb.drug_class,
      cyp_profile: kb.cyp_profile,
      counts: {
        high: kb.high_foods.length,
        medium: kb.medium_foods.length,
        safe: kb.safe_foods.length,
      },
      top_high: kb.high_foods.slice(0, 10),
      top_medium: kb.medium_foods.slice(0, 10),
      top_safe: kb.safe_foods.slice(0, 10),
      contraindications: kb.contraindications || [],
      has_detailed_profile: true,
    };
  }
  // No detailed KB — minimal profile from trade-name map
  return {
    ok: true,
    drug_key: normalize(resolved_inn || trade || ""),
    trade_name: trade_match?.brand_name || trade || "",
    inn: trade_match?.pipeline_drug || resolved_inn || "",
    pipeline_drug: trade_match?.pipeline_drug || resolved_inn || "",
    drug_class: { fr: "Non spécifié", en: "Unspecified", ar: "غير محدد" },
    cyp_profile: {
      notes: {
        fr: "Profil détaillé non disponible — vérifier la notice.",
        en: "Detailed profile not available — check the leaflet.",
        ar: "الملف التفصيلي غير متوفر — راجع النشرة.",
      },
    },
    counts: { high: 0, medium: 0, safe: 0 },
    top_high: [],
    top_medium: [],
    top_safe: [],
    contraindications: [],
    has_detailed_profile: false,
  };
}

function buildScripts(kb: DrugKnowledge | null, lang: Lang) {
  if (!kb) {
    const empty = {
      fr: ["Profil détaillé non disponible. Vérifier la notice et l'historique du patient."],
      en: ["Detailed profile not available. Check the leaflet and the patient's history."],
      ar: ["الملف التفصيلي غير متوفر. راجع النشرة وتاريخ المريض."],
    };
    return { ok: true, lang, scripts: empty[lang] || empty.fr, warnings: [] as any[] };
  }
  const warnings = (kb.contraindications || []).map((c) => ({
    food: c.food,
    mechanism: c.mechanism[lang] || c.mechanism.en,
    severity: "CLINICAL_RULE_CONFIRMED",
  }));
  return { ok: true, lang, scripts: kb.counseling[lang] || kb.counseling.en, warnings };
}

// ─── FastAPI fallback for unknown food/drug pairs ────────────────────────────

async function callDfinder(drug: string, food: string, language: Lang) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    const res = await fetch("http://localhost:8000/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drug, food, language: language === "ar" ? "fr" : language }),
      signal: controller.signal as any,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    return (await res.json()) as any;
  } catch {
    return null;
  }
}

// ─── Routes ──────────────────────────────────────────────────────────────────

export function registerPharmacistRoutes(opts: {
  app: any;
  db: Database.Database;
  tradeNameIndex: TradeNameRow[];
  verifyPharmacist: VerifyPharmacist;
}) {
  const { app, db, tradeNameIndex, verifyPharmacist } = opts;
  ensurePharmacistSchema(db);

  function requirePharmacist(req: Request, res: Response): ProfessionalContext | null {
    const ctx = verifyPharmacist(req);
    if (!ctx || (ctx.role || "").toLowerCase() !== "pharmacist") {
      res.status(401).json({ ok: false, detail: "Pharmacist authentication required." });
      return null;
    }
    return ctx;
  }

  function getCachedDrug(key: string): any | null {
    const row = db
      .prepare("SELECT payload FROM pharmacist_drug_cache WHERE drug_key = ?")
      .get(key) as any;
    if (!row?.payload) return null;
    try {
      return JSON.parse(row.payload);
    } catch {
      return null;
    }
  }
  function setCachedDrug(key: string, payload: any) {
    if (!key) return;
    db.prepare(
      `INSERT INTO pharmacist_drug_cache (drug_key, payload, cached_at)
       VALUES (?, ?, CURRENT_TIMESTAMP)
       ON CONFLICT(drug_key) DO UPDATE SET payload = excluded.payload, cached_at = CURRENT_TIMESTAMP`,
    ).run(key, JSON.stringify(payload));
  }
  function getCachedScript(key: string, lang: Lang): any | null {
    const row = db
      .prepare("SELECT payload FROM pharmacist_script_cache WHERE drug_key = ? AND lang = ?")
      .get(key, lang) as any;
    if (!row?.payload) return null;
    try {
      return JSON.parse(row.payload);
    } catch {
      return null;
    }
  }
  function setCachedScript(key: string, lang: Lang, payload: any) {
    if (!key) return;
    db.prepare(
      `INSERT INTO pharmacist_script_cache (drug_key, lang, payload, cached_at)
       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
       ON CONFLICT(drug_key, lang) DO UPDATE SET payload = excluded.payload, cached_at = CURRENT_TIMESTAMP`,
    ).run(key, lang, JSON.stringify(payload));
  }

  // 1) Drug profile -----------------------------------------------------------
  app.get("/api/pharmacist/drug-profile/:tradeName", (req: Request, res: Response) => {
    if (!requirePharmacist(req, res)) return;
    const trade = String(req.params.tradeName || "").trim();
    if (!trade) {
      return res.status(400).json({ ok: false, detail: "Missing tradeName." });
    }

    const { kb, trade_match, resolved_inn } = findKbForTrade(trade, tradeNameIndex);
    const cacheKey = (kb?.key || normalize(resolved_inn || trade)).slice(0, 64);

    const cached = getCachedDrug(cacheKey);
    if (cached) {
      return res.json({ ...cached, from_cache: true, trade_query: trade });
    }
    const payload = buildDrugProfilePayload({
      trade,
      trade_match: trade_match || null,
      kb,
      resolved_inn,
    });
    setCachedDrug(cacheKey, payload);
    res.json({ ...payload, from_cache: false, trade_query: trade });
  });

  // 2) Counseling script ------------------------------------------------------
  app.get("/api/pharmacist/counseling-script/:drugId", (req: Request, res: Response) => {
    if (!requirePharmacist(req, res)) return;
    const id = String(req.params.drugId || "").trim();
    const lang = (String(req.query.lang || "fr").toLowerCase() as Lang);
    const validLang: Lang = lang === "fr" || lang === "en" || lang === "ar" ? lang : "fr";
    if (!id) {
      return res.status(400).json({ ok: false, detail: "Missing drugId." });
    }
    const cacheKey = normalize(id);
    const cached = getCachedScript(cacheKey, validLang);
    if (cached) return res.json({ ...cached, from_cache: true });

    const kb = KB.find((k) => k.key === cacheKey || normalize(k.inn) === cacheKey)
      || findKbForTrade(id, tradeNameIndex).kb;
    const payload = buildScripts(kb, validLang);
    setCachedScript(cacheKey, validLang, payload);
    res.json({ ...payload, from_cache: false });
  });

  // 3) Safety slip HTML -------------------------------------------------------
  app.post("/api/pharmacist/safety-slip", (req: Request, res: Response) => {
    const ctx = requirePharmacist(req, res);
    if (!ctx) return;
    const drugId = String(req.body?.drugId || "").trim();
    const pharmacistName = String(req.body?.pharmacistName || ctx.name || "").trim() || "Pharmacist";
    const pharmacyName = String(req.body?.pharmacyName || "").trim() || "Pharmacy";
    const lang = (String(req.body?.lang || "fr").toLowerCase() as Lang);
    const validLang: Lang = lang === "fr" || lang === "en" || lang === "ar" ? lang : "fr";

    const { kb, trade_match } = findKbForTrade(drugId, tradeNameIndex);
    const tradeDisplay = trade_match?.brand_name || drugId;
    const innDisplay = kb?.inn || trade_match?.pipeline_drug || drugId;
    const avoid = (kb?.high_foods || []).slice(0, 3).map((f) => f.name);
    const safe = (kb?.safe_foods || []).slice(0, 3).map((f) => f.name);
    const consistent =
      validLang === "fr"
        ? "Garder la consommation de légumes verts CONSTANTE — pas zéro."
        : validLang === "ar"
        ? "حافظ على كمية الخضار الخضراء ثابتة — لا تجعلها صفر."
        : "Keep green vegetable intake CONSISTENT — not zero.";
    const headerTitle =
      validLang === "fr"
        ? "Carte Sécurité Alimentaire"
        : validLang === "ar"
        ? "بطاقة سلامة غذائية"
        : "Dietary Safety Card";
    const date = new Date().toISOString().slice(0, 10);
    const downloadUrl = `${req.protocol}://${req.get("host")}/`;
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(
      downloadUrl,
    )}`;

    const html = `<!doctype html>
<html lang="${validLang}" dir="${validLang === "ar" ? "rtl" : "ltr"}">
<head>
<meta charset="utf-8" />
<title>${headerTitle} — ${tradeDisplay}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 16px; color: #0f172a; background: #fff; }
  .slip { width: 320px; margin: 0 auto; border: 2px solid #0f172a; border-radius: 12px; padding: 14px; }
  .h { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px dashed #94a3b8; padding-bottom: 8px; margin-bottom: 10px; }
  .h .brand { font-weight: 800; letter-spacing: .5px; }
  .h .title { font-size: 12px; color: #475569; text-transform: uppercase; }
  .drug { font-size: 18px; font-weight: 800; }
  .inn { font-size: 13px; color: #475569; margin-bottom: 8px; }
  .row { font-size: 14px; line-height: 1.4; margin: 4px 0; }
  .avoid { color: #b91c1c; }
  .safe { color: #166534; }
  .rule { margin-top: 8px; padding: 8px; background: #f8fafc; border-left: 3px solid #0f172a; font-size: 13px; }
  .ft { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .ft .meta { font-size: 11px; color: #475569; }
  .ft img { width: 96px; height: 96px; }
  @media print {
    body { padding: 0; }
    .slip { border: 1px solid #0f172a; }
  }
</style>
</head>
<body>
  <div class="slip">
    <div class="h">
      <div class="brand">HealthOpt</div>
      <div class="title">${headerTitle}</div>
    </div>
    <div class="drug">${escapeHtml(tradeDisplay)}</div>
    <div class="inn">${escapeHtml(innDisplay)}</div>
    ${avoid.map((a) => `<div class="row avoid">🚫 ${escapeHtml(a)}</div>`).join("")}
    ${safe.map((a) => `<div class="row safe">✓ ${escapeHtml(a)}</div>`).join("")}
    <div class="rule">${escapeHtml(consistent)}</div>
    <div class="ft">
      <div class="meta">
        <div><strong>${escapeHtml(pharmacistName)}</strong></div>
        <div>${escapeHtml(pharmacyName)}</div>
        <div>${date}</div>
      </div>
      <img src="${qrUrl}" alt="QR" />
    </div>
  </div>
</body>
</html>`;

    const shareText =
      validLang === "fr"
        ? `Conseils HealthOpt pour ${tradeDisplay} (${innDisplay}). Téléchargez l'app: ${downloadUrl}`
        : validLang === "ar"
        ? `نصائح HealthOpt لـ ${tradeDisplay} (${innDisplay}). حمل التطبيق: ${downloadUrl}`
        : `HealthOpt advice for ${tradeDisplay} (${innDisplay}). Download the app: ${downloadUrl}`;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(shareText)}`;

    res.json({
      ok: true,
      html,
      whatsappUrl,
      downloadUrl,
      drug: { trade: tradeDisplay, inn: innDisplay },
      lang: validLang,
      generated_at: new Date().toISOString(),
    });
  });

  // 4) Real-time food check ---------------------------------------------------
  app.get("/api/pharmacist/food-check", async (req: Request, res: Response) => {
    if (!requirePharmacist(req, res)) return;
    const drug = String(req.query.drug || "").trim();
    const food = String(req.query.food || "").trim();
    if (!drug || !food) {
      return res.status(400).json({ ok: false, detail: "Missing drug or food." });
    }
    const { kb, trade_match, resolved_inn } = findKbForTrade(drug, tradeNameIndex);
    const drugKey = (kb?.key || normalize(resolved_inn || drug)).slice(0, 64);
    const foodKey = normalize(food).slice(0, 96);

    // 4a) cache
    const cached = db
      .prepare(
        "SELECT tier, score, mechanism FROM pharmacist_food_cache WHERE drug_key = ? AND food_key = ?",
      )
      .get(drugKey, foodKey) as any;
    if (cached) {
      return res.json({
        ok: true,
        drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb?.inn || resolved_inn || drug },
        food,
        tier: String(cached.tier || "INSUFFICIENT"),
        score: Number(cached.score || 0),
        mechanism: cached.mechanism || "",
        from_cache: true,
      });
    }

    // 4b) KB shortcut
    if (kb) {
      const inList = (rows: FoodEntry[]) =>
        rows.find((r) => normalize(r.name).includes(foodKey) || foodKey.includes(normalize(r.name)));
      const high = inList(kb.high_foods);
      if (high) {
        const payload = { tier: "HIGH", score: 0.85, mechanism: high.reason || "" };
        db.prepare(
          "INSERT OR REPLACE INTO pharmacist_food_cache (drug_key, food_key, tier, score, mechanism) VALUES (?, ?, ?, ?, ?)",
        ).run(drugKey, foodKey, payload.tier, payload.score, payload.mechanism);
        return res.json({
          ok: true,
          drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb.inn },
          food,
          ...payload,
          from_cache: false,
          source: "kb",
        });
      }
      const med = inList(kb.medium_foods);
      if (med) {
        const payload = { tier: "MEDIUM", score: 0.5, mechanism: med.reason || "" };
        db.prepare(
          "INSERT OR REPLACE INTO pharmacist_food_cache (drug_key, food_key, tier, score, mechanism) VALUES (?, ?, ?, ?, ?)",
        ).run(drugKey, foodKey, payload.tier, payload.score, payload.mechanism);
        return res.json({
          ok: true,
          drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb.inn },
          food,
          ...payload,
          from_cache: false,
          source: "kb",
        });
      }
      const safe = inList(kb.safe_foods);
      if (safe) {
        const payload = { tier: "LOW", score: 0.1, mechanism: "No significant interaction expected." };
        db.prepare(
          "INSERT OR REPLACE INTO pharmacist_food_cache (drug_key, food_key, tier, score, mechanism) VALUES (?, ?, ?, ?, ?)",
        ).run(drugKey, foodKey, payload.tier, payload.score, payload.mechanism);
        return res.json({
          ok: true,
          drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb.inn },
          food,
          ...payload,
          from_cache: false,
          source: "kb",
        });
      }
    }

    // 4c) DFinder fallback
    const drugForDfinder = kb?.inn?.split("/")[0]?.trim() || resolved_inn || drug;
    const py = await callDfinder(drugForDfinder, food, "fr");
    if (py) {
      const tier = String(py.confidence || "INSUFFICIENT").toUpperCase();
      const score = Number(py.fusion_score || py.score || 0);
      const mechanism = String(py.explanation || py.mechanism || "");
      db.prepare(
        "INSERT OR REPLACE INTO pharmacist_food_cache (drug_key, food_key, tier, score, mechanism) VALUES (?, ?, ?, ?, ?)",
      ).run(drugKey, foodKey, tier, score, mechanism);
      return res.json({
        ok: true,
        drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb?.inn || drugForDfinder },
        food,
        tier,
        score,
        mechanism,
        from_cache: false,
        source: "dfinder",
      });
    }

    // 4d) graceful default
    return res.json({
      ok: true,
      drug: { key: drugKey, trade: trade_match?.brand_name || drug, inn: kb?.inn || drugForDfinder },
      food,
      tier: "INSUFFICIENT",
      score: 0,
      mechanism: "Backend unavailable. No cached evidence for this pair.",
      from_cache: false,
      source: "none",
    });
  });

  // ─── Pre-cache top KB drugs at startup ─────────────────────────────────────
  for (const kb of KB) {
    const profile = buildDrugProfilePayload({
      kb,
      resolved_inn: kb.inn,
      trade_match: tradeNameIndex.find((t) => normalize(t.pipeline_drug) === kb.key) || null,
    });
    setCachedDrug(kb.key, profile);
    for (const lang of ["fr", "en", "ar"] as Lang[]) {
      setCachedScript(kb.key, lang, buildScripts(kb, lang));
    }
  }
  console.log(`Pharmacist KB pre-cached: ${TOP_KB_KEYS.length} drugs × 3 languages.`);
}

// ─── small html escape ───────────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
