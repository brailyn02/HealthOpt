import React from 'react';
import {
  AlertCircle,
  Calendar,
  ChevronRight,
  Clock,
  Download,
  FileText,
  KeyRound,
  Link2,
  Lock,
  Moon,
  Pill,
  Search,
  Shield,
  Sun,
  TestTube,
  TrendingUp,
  Users,
  Activity,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

type ProfessionalRole = 'doctor' | 'pharmacist' | 'nutritionist';

type ProfessionalDashboardProps = {
  initialRole?: ProfessionalRole;
};

type ProfessionalProfile = {
  id: string;
  role: ProfessionalRole;
  name: string;
  specialty: string;
};

type Locale = 'en' | 'fr' | 'ar';

type TimelineData = {
  ok: boolean;
  cycle?: { active: boolean; phase: string | null; day?: number | null } | null;
  cycle_bands: Array<{ start: string; end: string; phase: string; color: string }>;
  interactions: Array<{
    id: number;
    date: string;
    drug: string;
    food: string;
    score: number;
    tier: string;
    severity: number;
    mechanism_flag: string;
  }>;
  biomarker_series: Array<{
    date: string;
    label: string | null;
    value: number | null;
    ferritin?: number | null;
    hemoglobin?: number | null;
    vitaminD?: number | null;
    b12?: number | null;
    folate?: number | null;
  }>;
};

type MechanisticDetail = {
  ok: boolean;
  interaction?: any;
  rotate?: { summary: string; confidence: number; enzymes: string[] };
  hkg?: { path: string[]; confidence: number };
  fusion?: { lightgcn: number | null; kge: number | null; hkg: number | null; clinical_gate: string; fusion_score: number | null };
  cycle_modifier?: any;
  active_virtual_meds?: Array<{ public_label: string; drug_name: string; severity: string }>;
  technical_view?: any;
};

const translations: Record<Locale, Record<string, string>> = {
  en: {
    title: 'Professional Dashboard',
    subtitle: 'Clinical decision support for linked patients, interaction analysis, and therapeutic alternatives.',
    signInTitle: 'Professional PIN Access',
    signInSubtitle: 'Use your 6-digit PIN to enter your role-specific workspace.',
    role: 'Role',
    pin: 'PIN',
    signIn: 'Sign in',
    doctor: 'Doctor',
    pharmacist: 'Pharmacist',
    nutritionist: 'Nutritionist',
    riskMatrix: 'Patient Risk Matrix',
    timeline: 'Synchronized Timeline',
    mechanistic: 'Mechanistic Report Panel',
    simulator: 'Therapeutic Alternatives Finder',
    simulatorShort: 'Alternatives',
    currentMedication: 'Current medication',
    medicationToEvaluate: 'Medication to evaluate',
    cyclePhaseLabel: 'Cycle phase',
    activeDeficiencies: 'Active deficiency signals',
    findAlternatives: 'Find Safer Alternatives',
    scoringProgress: 'Scoring',
    noAlternativesFound: 'No safer alternative found',
    classWideInteraction: 'Class-wide interaction',
    dietaryTimingAdvice: 'Dietary timing recommendation',
    alternativeRank: 'Alternative',
    sameClass: 'Same class',
    differentClass: 'Different drug class',
    improvement: 'Improvement',
    biomarkerConflicts: 'Biomarker conflicts',
    cycleFit: 'Cycle phase compatibility',
    clinicalNote: 'Clinical note',
    insufficientDietData: 'Insufficient dietary history',
    linkPatient: 'Link Patient',
    shareCode: 'Share code',
    connect: 'Connect',
    connected: 'Connected patients',
    patientName: 'Patient Name',
    lastActive: 'Last Active',
    dominantTier: 'Dominant Tier',
    interactions30d: 'Total Interactions (30d)',
    lastBloodTest: 'Last Blood Test',
    cyclePhase: 'Cycle Phase',
    alertStatus: 'Alert Status',
    selectPatient: 'Select a patient to expand details.',
    generatedReport: 'Export as PDF',
    runSimulation: 'Find Alternatives',
    doNotAdjust: 'Do not adjust',
    insufficientEvidence: 'Insufficient evidence',
    disclaimer: 'For clinical decision support only. Not a substitute for professional judgment.',
    noPatients: 'No linked patients yet.',
    linkHelper: 'Ask the patient to generate a share code in Settings, then enter it here.',
    pinPlaceholder: '123456',
    sharePlaceholder: 'Enter 6-digit share code',
    drug: 'Current Medication',
    dose: 'Dose',
    unit: 'Unit',
    foods: 'Dietary pattern',
    phase: 'Cycle phase',
    deficiencies: 'Active deficiencies',
    safeFoods: 'Safe foods',
    riskTier: 'Risk tier',
    patientLinked: 'Patient linked successfully.',
    linkFailed: 'Unable to link patient.',
    authFailed: 'PIN authentication failed.',
  },
  fr: {
    title: 'Tableau de bord médecin',
    subtitle: 'Vue clinique pour les patients liés, les tendances et l’aide à la décision.',
    signInTitle: 'Accès professionnel par PIN',
    signInSubtitle: 'Utilisez votre PIN à 6 chiffres pour entrer dans l’espace de votre rôle.',
    role: 'Rôle',
    pin: 'PIN',
    signIn: 'Connexion',
    doctor: 'Médecin',
    pharmacist: 'Pharmacien',
    nutritionist: 'Nutritionniste',
    riskMatrix: 'Matrice de risque des patients',
    timeline: 'Chronologie synchronisée',
    mechanistic: 'Panneau du rapport mécanistique',
    simulator: 'Recherche d\'alternatives thérapeutiques',
    simulatorShort: 'Alternatives',
    currentMedication: 'Médicament actuel',
    medicationToEvaluate: 'Médicament à évaluer',
    cyclePhaseLabel: 'Phase du cycle',
    activeDeficiencies: 'Signaux de carence actifs',
    findAlternatives: 'Trouver des alternatives plus sûres',
    scoringProgress: 'Analyse en cours',
    noAlternativesFound: 'Aucune alternative plus sûre trouvée',
    classWideInteraction: 'Interaction de classe',
    dietaryTimingAdvice: 'Recommandation de timing alimentaire',
    alternativeRank: 'Alternative',
    sameClass: 'Même classe',
    differentClass: 'Classe différente',
    improvement: 'Amélioration',
    biomarkerConflicts: 'Conflits biomarqueurs',
    cycleFit: 'Compatibilité phase cycle',
    clinicalNote: 'Note clinique',
    insufficientDietData: 'Historique alimentaire insuffisant',
    linkPatient: 'Lier un patient',
    shareCode: 'Code de partage',
    connect: 'Associer',
    connected: 'Patients liés',
    patientName: 'Nom du patient',
    lastActive: 'Dernière activité',
    dominantTier: 'Niveau dominant',
    interactions30d: 'Interactions totales (30 j)',
    lastBloodTest: 'Dernière prise de sang',
    cyclePhase: 'Phase du cycle',
    alertStatus: 'État d’alerte',
    selectPatient: 'Sélectionnez un patient pour afficher le détail.',
    generatedReport: 'Exporter en PDF',
    runSimulation: 'Lancer la simulation',
    doNotAdjust: 'Ne pas ajuster',
    insufficientEvidence: 'Preuves insuffisantes',
    disclaimer: 'Pour l’aide à la décision clinique uniquement. Ne remplace pas le jugement professionnel.',
    noPatients: 'Aucun patient lié pour le moment.',
    linkHelper: 'Demandez au patient de générer un code de partage dans Paramètres, puis saisissez-le ici.',
    pinPlaceholder: '123456',
    sharePlaceholder: 'Saisissez un code à 6 chiffres',
    drug: 'Médicament',
    dose: 'Dose',
    unit: 'Unité',
    foods: 'Profil alimentaire',
    phase: 'Phase du cycle',
    deficiencies: 'Carences actives',
    safeFoods: 'Aliments sûrs',
    riskTier: 'Niveau de risque',
    patientLinked: 'Patient lié avec succès.',
    linkFailed: 'Impossible de lier le patient.',
    authFailed: 'Échec de l’authentification PIN.',
  },
  ar: {
    title: 'لوحة الطبيب',
    subtitle: 'عرض سريري للمرضى المرتبطين واتجاهات التفاعل ودعم القرار.',
    signInTitle: 'دخول مهني عبر PIN',
    signInSubtitle: 'استخدم رمز PIN المكوّن من 6 أرقام للدخول إلى مساحة الدور الخاص بك.',
    role: 'الدور',
    pin: 'PIN',
    signIn: 'تسجيل الدخول',
    doctor: 'طبيب',
    pharmacist: 'صيدلي',
    nutritionist: 'أخصائي تغذية',
    riskMatrix: 'مصفوفة مخاطر المرضى',
    timeline: 'الخط الزمني المتزامن',
    mechanistic: 'لوحة التقرير الآلي',
    simulator: 'محاكي تعديل الجرعة',
    linkPatient: 'ربط مريض',
    shareCode: 'رمز المشاركة',
    connect: 'ربط',
    connected: 'المرضى المرتبطون',
    patientName: 'اسم المريض',
    lastActive: 'آخر نشاط',
    dominantTier: 'الفئة الغالبة',
    interactions30d: 'إجمالي التفاعلات (30 يوم)',
    lastBloodTest: 'آخر تحليل دم',
    cyclePhase: 'مرحلة الدورة',
    alertStatus: 'حالة التنبيه',
    selectPatient: 'اختر مريضًا لعرض التفاصيل.',
    generatedReport: 'تصدير PDF',
    runSimulation: 'تشغيل المحاكاة',
    doNotAdjust: 'لا تعدّل',
    insufficientEvidence: 'الأدلة غير كافية',
    disclaimer: 'لأغراض دعم القرار السريري فقط. لا يغني عن الحكم المهني.',
    noPatients: 'لا يوجد مرضى مرتبطون بعد.',
    linkHelper: 'اطلب من المريض إنشاء رمز مشاركة من الإعدادات ثم أدخله هنا.',
    pinPlaceholder: '123456',
    sharePlaceholder: 'أدخل رمزًا من 6 أرقام',
    drug: 'الدواء',
    dose: 'الجرعة',
    unit: 'الوحدة',
    foods: 'النمط الغذائي',
    phase: 'مرحلة الدورة',
    deficiencies: 'نواقص فعالة',
    safeFoods: 'أطعمة آمنة',
    riskTier: 'فئة الخطورة',
    patientLinked: 'تم ربط المريض بنجاح.',
    linkFailed: 'تعذر ربط المريض.',
    authFailed: 'فشل التحقق من PIN.',
  },
};

function tierRank(tier: string) {
  const normalized = String(tier || '').toUpperCase();
  if (normalized === 'HIGH') return 3;
  if (normalized === 'MEDIUM') return 2;
  if (normalized === 'LOW') return 1;
  if (normalized === 'INFO') return 0;
  return -1;
}

function tierLabel(rank: number) {
  if (rank >= 3) return 'HIGH';
  if (rank === 2) return 'MEDIUM';
  if (rank === 1) return 'LOW';
  return 'INSUFFICIENT';
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString();
}

function safeNumber(value: any) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function colorForAlert(alertStatus: string) {
  if (alertStatus === 'RED') return 'border-rose-200 bg-rose-50 text-rose-800';
  if (alertStatus === 'YELLOW') return 'border-amber-200 bg-amber-50 text-amber-800';
  return 'border-emerald-200 bg-emerald-50 text-emerald-800';
}

function ProfessionalDashboard({ initialRole = 'doctor' }: ProfessionalDashboardProps) {
  const [locale, setLocale] = React.useState<Locale>('en');
  const [darkMode, setDarkMode] = React.useState(false);
  const [authRole, setAuthRole] = React.useState<ProfessionalRole>(initialRole);
  const [authPin, setAuthPin] = React.useState('');
  const [authNotice, setAuthNotice] = React.useState<string>('');
  const [authLoading, setAuthLoading] = React.useState(false);
  const [profile, setProfile] = React.useState<ProfessionalProfile | null>(null);
  const [token, setToken] = React.useState('');
  const [patients, setPatients] = React.useState<any[]>([]);
  const [selectedPatientId, setSelectedPatientId] = React.useState('');
  const [timeline, setTimeline] = React.useState<TimelineData | null>(null);
  const [patientVirtualMeds, setPatientVirtualMeds] = React.useState<any[]>([]);
  const [detailCache, setDetailCache] = React.useState<Record<string, MechanisticDetail>>({});
  const [expandedRows, setExpandedRows] = React.useState<Record<string, boolean>>({});
  const [shareCode, setShareCode] = React.useState('');
  const [patientAlias, setPatientAlias] = React.useState('');
  const [shareNotice, setShareNotice] = React.useState<string>('');
  const [simForm, setSimForm] = React.useState({
    drug: '',
    cyclePhaseOverride: null as string | null,
    virtualMedsOverride: null as string[] | null,
  });
  const [simResult, setSimResult] = React.useState<any>(null);
  const [simLoading, setSimLoading] = React.useState(false);
  const [simError, setSimError] = React.useState('');
  const [simShowResults, setSimShowResults] = React.useState(false);
  const [activeVirtualMedToggles, setActiveVirtualMedToggles] = React.useState<Record<string, boolean>>({});
  const [editingAliasId, setEditingAliasId] = React.useState<string | null>(null);
  const [aliasInput, setAliasInput] = React.useState('');
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  React.useEffect(() => {
    const savedLocale = localStorage.getItem('healthopt.lang');
    const savedTheme = localStorage.getItem('healthopt.theme');
    const savedToken = localStorage.getItem('healthopt.professional.token') || '';
    const savedProfile = localStorage.getItem('healthopt.professional.profile');
    if (savedLocale === 'fr' || savedLocale === 'ar' || savedLocale === 'en') {
      setLocale(savedLocale);
    }
    if (savedTheme === 'dark') {
      setDarkMode(true);
    }
    if (savedToken) {
      setToken(savedToken);
    }
    if (savedProfile) {
      try {
        const parsed = JSON.parse(savedProfile) as ProfessionalProfile;
        setProfile(parsed);
        // Redirect if not doctor role
        if (parsed.role === 'nutritionist') {
          window.location.href = '/nutritionist-dashboard';
          return;
        }
        if (parsed.role === 'pharmacist') {
          window.location.href = '/pharmacist-dashboard';
          return;
        }
      } catch {
        // ignore
      }
    }
  }, []);

  React.useEffect(() => {
    setAuthRole(initialRole);
  }, [initialRole]);

  React.useEffect(() => {
    localStorage.setItem('healthopt.lang', locale);
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
  }, [locale]);

  React.useEffect(() => {
    localStorage.setItem('healthopt.theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  React.useEffect(() => {
    if (token && profile) {
      console.log(`[DEBUG] useEffect: token=${token?.slice(0, 20)}..., profile.id=${profile.id}`);
      void loadPatients(token, profile.id).catch((error) => {
        console.error(`[ERROR] Failed to load patients:`, error);
      });
    } else {
      console.log(`[DEBUG] useEffect: skipping loadPatients because token=${!!token} profile=${!!profile}`);
    }
  }, [token, profile]);

  React.useEffect(() => {
    if (selectedPatientId && token && profile) {
      void loadPatientTimeline(selectedPatientId);
    }
  }, [selectedPatientId, token, profile]);

  const tr = React.useCallback((key: string) => translations[locale][key] || translations.en[key] || key, [locale]);

  const authHeaders = React.useCallback(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const loadPatients = async (authToken: string, professionalId: string) => {
    try {
      console.log(`[DEBUG] loadPatients called with authToken=${authToken?.slice(0, 20)}..., professionalId=${professionalId}`);
      const res = await fetch(`/api/professional/patients/${professionalId}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      console.log(`[DEBUG] fetch response status=${res.status}, ok=${res.ok}`);
      const payload = await res.json().catch(() => ({}));
      console.log(`[DEBUG] payload=`, payload);
      if (!res.ok) {
        const detail = payload?.detail || 'Unable to load patients';
        console.error(`[ERROR] loadPatients failed: ${detail}`);
        throw new Error(detail);
      }
      const patientList = Array.isArray(payload?.patients) ? payload.patients : [];
      console.log(`[DEBUG] Setting ${patientList.length} patients`);
      setPatients(patientList);
      if (!selectedPatientId && patientList.length > 0) {
        setSelectedPatientId(patientList[0].patient_id);
      }
    } catch (error) {
      console.error(`[ERROR] loadPatients exception:`, error);
      throw error;
    }
  };

  const loadPatientTimeline = async (patientId: string) => {
    if (!profile) return;
    const res = await fetch(`/api/professional/patient/${encodeURIComponent(patientId)}/timeline`, {
      headers: authHeaders(),
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) return;
    setTimeline(payload as TimelineData);
    const rows = Array.isArray(payload?.interactions) ? payload.interactions : [];
    if (rows.length > 0) {
      setSimForm((prev) => ({ ...prev, drug: prev.drug || String(rows[0].drug || '') }));
    }

    // Fetch professional view of patient's virtual medications / model2 signals
    try {
      const vmRes = await fetch(`/api/professional/patient/${encodeURIComponent(patientId)}/virtual-medications`, { headers: authHeaders() });
      if (vmRes.ok) {
        const vm = await vmRes.json().catch(() => ([]));
        const vmeds = Array.isArray(vm) ? vm : [];
        setPatientVirtualMeds(vmeds);
        // Initialize all virtual meds as active (toggled on)
        const toggles: Record<string, boolean> = {};
        vmeds.forEach((med: any) => {
          toggles[med.drug_name || med.public_label] = true;
        });
        setActiveVirtualMedToggles(toggles);
      } else {
        setPatientVirtualMeds([]);
        setActiveVirtualMedToggles({});
      }
    } catch (e) {
      setPatientVirtualMeds([]);
      setActiveVirtualMedToggles({});
    }
  };

  const submitAuth = async () => {
    setAuthLoading(true);
    setAuthNotice('');
    try {
      const res = await fetch('/api/professional/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: authRole, pin: authPin }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.detail || tr('authFailed'));
      }
      const nextProfile = payload?.professional as ProfessionalProfile;
      localStorage.setItem('healthopt.professional.token', String(payload?.token || ''));
      localStorage.setItem('healthopt.professional.profile', JSON.stringify(nextProfile));
      
      // Redirect to appropriate dashboard based on role
      if (nextProfile.role === 'nutritionist') {
        window.location.href = '/nutritionist-dashboard';
        return;
      }
      if (nextProfile.role === 'pharmacist') {
        window.location.href = '/pharmacist-dashboard';
        return;
      }
      
      setProfile(nextProfile);
      setToken(String(payload?.token || ''));
      setAuthNotice('');
      await loadPatients(String(payload?.token || ''), String(nextProfile.id));
    } catch (error: any) {
      setAuthNotice(error?.message || tr('authFailed'));
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setProfile(null);
    setToken('');
    setAuthPin('');
    localStorage.removeItem('healthopt.professional.token');
    localStorage.removeItem('healthopt.professional.profile');
    window.location.href = '/professional-login';
  };

  const linkPatient = async () => {
    setShareNotice('');
    try {
      const res = await fetch('/api/professional/link-patient', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ shareCode, patientAlias: patientAlias || undefined }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.detail || tr('linkFailed'));
      }
      setShareNotice(tr('patientLinked'));
      setShareCode('');
      setPatientAlias('');
      // Refresh linked patients and open the newly linked patient immediately
      if (profile) {
        await loadPatients(token, profile.id);
      }
      if (payload?.patientId) {
        setSelectedPatientId(String(payload.patientId));
        setExpandedRows({});
        setSimResult(null);
        await loadPatientTimeline(String(payload.patientId));
      }
    } catch (error: any) {
      setShareNotice(error?.message || tr('linkFailed'));
    }
  };

  const selectPatient = (patientId: string) => {
    setSelectedPatientId(patientId);
    setExpandedRows({});
    setSimResult(null);
  };

  const toggleRow = async (interactionId: number) => {
    const cacheKey = String(interactionId);
    setExpandedRows((prev) => ({ ...prev, [cacheKey]: !prev[cacheKey] }));
    if (detailCache[cacheKey] || !selectedPatientId) return;
    const res = await fetch(`/api/professional/patient/${encodeURIComponent(selectedPatientId)}/mechanistic/${interactionId}`, {
      headers: authHeaders(),
    });
    const payload = await res.json().catch(() => ({}));
    if (res.ok) {
      setDetailCache((prev) => ({ ...prev, [cacheKey]: payload as MechanisticDetail }));
    }
  };

  const exportReport = async (interactionId: number) => {
    if (!selectedPatientId) return;
    const res = await fetch(`/api/professional/patient/${encodeURIComponent(selectedPatientId)}/interactions/${interactionId}/report`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `clinical-report-${interactionId}.pdf`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const runSimulation = async () => {
    if (!selectedPatientId) {
      setSimError('Please select a patient first.');
      return;
    }
    setSimLoading(true);
    setSimError('');
    setSimResult(null);
    setSimShowResults(true);
    try {
      if (!simForm.drug.trim()) {
        setSimError('Please enter a medication name.');
        setSimLoading(false);
        return;
      }

      // Build active virtual meds list from toggles
      const activeVirtualMeds = Object.entries(activeVirtualMedToggles)
        .filter(([, active]) => active)
        .map(([name]) => name);

      const payload = {
        patientId: selectedPatientId,
        drug: simForm.drug,
        cyclePhaseOverride: simForm.cyclePhaseOverride,
        virtualMedsOverride: activeVirtualMeds.length > 0 ? activeVirtualMeds : null,
      };

      const res = await fetch('/api/professional/simulate', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      const payload_response = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail = payload_response?.message || 'Unable to run simulation. Please try again.';
        setSimError(detail);
        setSimLoading(false);
        return;
      }

      setSimResult(payload_response);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error. Please try again.';
      setSimError(message);
      console.error('[ERROR] Simulation failed:', error);
    } finally {
      setSimLoading(false);
    }
  };

  const startEditAlias = (patientId: string, currentName: string) => {
    setEditingAliasId(patientId);
    setAliasInput(currentName || '');
  };

  const saveAlias = async (patientId: string) => {
    if (!profile) return;
    try {
      const res = await fetch('/api/professional/link-patient/update', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ patientId, patientAlias: aliasInput }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload?.detail || 'Unable to update alias');
      setEditingAliasId(null);
      setAliasInput('');
      await loadPatients(token, profile.id);
    } catch (err) {
      console.error('[ERROR] saveAlias', err);
      alert((err as any)?.message || 'Failed to update name');
    }
  };

  const cancelEdit = () => {
    setEditingAliasId(null);
    setAliasInput('');
  };

  const deleteLink = async (patientId: string) => {
    if (!profile) return;
    const ok = window.confirm('Unlink this patient? This will remove access but not delete patient data.');
    if (!ok) return;
    try {
      const res = await fetch(`/api/professional/link-patient/${encodeURIComponent(patientId)}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload?.detail || 'Unable to unlink patient');
      await loadPatients(token, profile.id);
      if (selectedPatientId === patientId) {
        setSelectedPatientId(null);
        setTimeline(null);
      }
    } catch (err) {
      console.error('[ERROR] deleteLink', err);
      alert((err as any)?.message || 'Failed to unlink patient');
    }
  };

  const selectedPatient = patients.find((patient) => String(patient.patient_id) === String(selectedPatientId)) || null;
  const selectedInteractions = timeline?.interactions || [];
  // Only show mechanistic report entries that were logged as consumed by the patient
  const mechRows = selectedInteractions.filter((item) => Number(item.consumed || 0) === 1 && tierRank(item.tier) >= 1).slice(-10).reverse();
  const selectedMechanisticCard = selectedPatientId ? mechRows.map((item) => ({ ...item, cacheKey: String(item.id) })) : [];

  const chartData = React.useMemo(() => {
    if (!timeline) return { width: 1000, height: 280, minX: 0, maxX: 1, points: [], biomarker: [], bands: [] };
    const allDates = [
      ...timeline.interactions.map((item) => new Date(item.date).getTime()),
      ...timeline.biomarker_series.map((item) => new Date(item.date).getTime()),
      ...timeline.cycle_bands.map((item) => new Date(item.start).getTime()),
      ...timeline.cycle_bands.map((item) => new Date(item.end).getTime()),
    ].filter((value) => Number.isFinite(value));
    const minX = allDates.length ? Math.min(...allDates) : Date.now() - 90 * 24 * 60 * 60 * 1000;
    const maxX = allDates.length ? Math.max(...allDates) : Date.now();
    const scoreMax = 1;
    const biomarkerValues = timeline.biomarker_series.map((item) => safeNumber(item.value)).filter((value) => value > 0);
    const minBiomarker = biomarkerValues.length ? Math.min(...biomarkerValues) : 0;
    const maxBiomarker = biomarkerValues.length ? Math.max(...biomarkerValues) : 1;
    const scaleX = (value: number) => 60 + ((value - minX) / Math.max(1, maxX - minX)) * 890;
    const scaleScoreY = (value: number) => 220 - Math.max(0, Math.min(scoreMax, value)) * 180;
    const scaleBiomarkerY = (value: number) => {
      if (!Number.isFinite(value)) return 220;
      const normalized = (value - minBiomarker) / Math.max(1, maxBiomarker - minBiomarker);
      return 220 - normalized * 180;
    };
    return {
      width: 1000,
      height: 280,
      minX,
      maxX,
      points: timeline.interactions.map((item) => ({
        x: scaleX(new Date(item.date).getTime()),
        y: scaleScoreY(Number(item.score || 0)),
        tier: item.tier,
        label: `${item.drug} × ${item.food}`,
        flag: item.mechanism_flag,
        score: item.score,
      })),
      biomarker: timeline.biomarker_series.map((item) => ({
        x: scaleX(new Date(item.date).getTime()),
        y: scaleBiomarkerY(Number(item.value || 0)),
        value: item.value,
        label: item.label,
      })),
      bands: timeline.cycle_bands.map((band) => ({
        x: scaleX(new Date(band.start).getTime()),
        w: Math.max(12, scaleX(new Date(band.end).getTime()) - scaleX(new Date(band.start).getTime())),
        color: band.color,
        phase: band.phase,
      })),
    };
  }, [timeline]);

  if (!profile || !token) {
    return (
      <div className={`min-h-screen ${darkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'} text-[15px]`}>
        <div className="max-w-2xl mx-auto px-6 py-10">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className={`text-4xl font-black ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>{tr('title')}</h1>
              <p className="text-slate-500 mt-2">{tr('subtitle')}</p>
            </div>
            <button
              type="button"
              onClick={() => setDarkMode((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-2 border ${darkMode ? 'border-slate-700 bg-slate-900 text-slate-100' : 'border-slate-200 bg-white text-slate-700'}`}
            >
              {darkMode ? <Moon size={16} /> : <Sun size={16} />}
              {darkMode ? 'Dark' : 'Light'}
            </button>
          </div>
          <div className="glass-card p-8 space-y-5">
            <div>
              <h2 className="text-2xl font-black mb-1">{tr('signInTitle')}</h2>
              <p className="text-sm text-slate-500">{tr('signInSubtitle')}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {([
                ['doctor', tr('doctor')],
                ['pharmacist', tr('pharmacist')],
                ['nutritionist', tr('nutritionist')],
              ] as Array<[ProfessionalRole, string]>).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setAuthRole(value)}
                  className={`rounded-2xl px-4 py-3 font-bold border ${authRole === value ? 'bg-clinical-blue text-white border-clinical-blue' : 'bg-white border-slate-200 text-slate-700'}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              placeholder={tr('pinPlaceholder')}
              value={authPin}
              onChange={(event) => setAuthPin(event.target.value.replace(/\D/g, '').slice(0, 6))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            {authNotice && <div className="text-sm font-semibold text-rose-700">{authNotice}</div>}
            <button
              type="button"
              onClick={submitAuth}
              disabled={authLoading || authPin.length !== 6}
              className="w-full rounded-2xl bg-clinical-blue px-4 py-3 font-bold text-white disabled:opacity-60"
            >
              {authLoading ? 'Please wait...' : tr('signIn')}
            </button>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Lock size={14} />
              Demo PINs: 123456, 234567, 345678
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen text-[15px] ${darkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      <header className="max-w-7xl mx-auto px-6 lg:px-8 py-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-white flex items-center justify-center shadow-lg">
              <img src="/logo.png" alt="HealthOpt" className="w-10 h-10 object-contain" />
            </div>
            <div>
              <h1 className={`text-4xl font-black ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>
                {(() => {
                  const roleLabel = profile.role === 'doctor' ? tr('doctor') : profile.role === 'pharmacist' ? tr('pharmacist') : tr('nutritionist');
                  return `${roleLabel} Workspace`;
                })()}
              </h1>
              <p className="text-slate-500">{tr('subtitle')}</p>
            </div>
          </div>
          <div className="text-sm font-semibold text-slate-500 flex flex-wrap gap-3">
            <span>{profile.name}</span>
            <span>•</span>
            <span>{profile.specialty || tr(profile.role)}</span>
            <span>•</span>
            <span className="uppercase tracking-widest">{profile.role}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setDarkMode((prev) => !prev)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 border ${darkMode ? 'border-slate-700 bg-slate-900 text-slate-100' : 'border-slate-200 bg-white text-slate-700'}`}
          >
            {darkMode ? <Moon size={16} /> : <Sun size={16} />}
            {darkMode ? 'Dark' : 'Light'}
          </button>
          <button
            type="button"
            onClick={handleLogout}
            title="Sign out and return to role selection"
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 border ${darkMode ? 'border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-100'}`}
          >
            <KeyRound size={16} />
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 lg:px-8 pb-16 space-y-8">
        <section className="glass-card p-5 lg:p-6">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-4">
            <div>
              <h2 className="text-xl font-black mb-1">{tr('linkPatient')}</h2>
              <p className="text-sm text-slate-500">{tr('linkHelper')}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
              <div className="flex-1">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block\">Patient nickname (optional)</label>
                <input
                  type="text"
                  placeholder="e.g., Mrs. Sidi"
                  value={patientAlias}
                  onChange={(event) => setPatientAlias(event.target.value)}
                  className={`w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500/20 ${darkMode ? 'bg-slate-700 text-slate-100' : 'bg-white'}`}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block\">Share code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder={tr('sharePlaceholder')}
                  value={shareCode}
                  onChange={(event) => setShareCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  className={`w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500/20 ${darkMode ? 'bg-slate-700 text-slate-100' : 'bg-white'}`}
                />
              </div>
              <button
                type="button"
                onClick={linkPatient}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-clinical-blue px-4 py-3 font-bold text-white"
              >
                <Link2 size={16} />
                {tr('connect')}
              </button>
            </div>
          </div>
          {shareNotice && <div className="text-sm font-semibold text-emerald-700">{shareNotice}</div>}
        </section>

        <section className="glass-card p-5 lg:p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-black">{tr('riskMatrix')}</h2>
            <div className="text-xs font-semibold text-slate-500 inline-flex items-center gap-2"><Users size={14} />{tr('connected')} {patients.length}</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-separate border-spacing-y-2 min-w-[900px]">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-slate-500">
                  <th className="py-2 px-3">{tr('patientName')}</th>
                  <th className="py-2 px-3">{tr('lastActive')}</th>
                  <th className="py-2 px-3">{tr('dominantTier')}</th>
                  <th className="py-2 px-3">{tr('interactions30d')}</th>
                  <th className="py-2 px-3">{tr('lastBloodTest')}</th>
                  <th className="py-2 px-3">{tr('cyclePhase')}</th>
                  <th className="py-2 px-3">{tr('alertStatus')}</th>
                </tr>
              </thead>
              <tbody>
                {patients.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-500">{tr('noPatients')}</td>
                  </tr>
                ) : patients.map((patient) => (
                  <tr
                    key={patient.patient_id}
                    onClick={() => selectPatient(patient.patient_id)}
                    className={`cursor-pointer rounded-2xl border transition-all ${selectedPatientId === patient.patient_id ? 'ring-2 ring-blue-500/30' : ''}`}
                  >
                    <td className={`px-3 py-4 rounded-l-2xl border-y border-l ${colorForAlert(patient.alert_status)}`}>
                      {editingAliasId === patient.patient_id ? (
                        <div className="flex items-center gap-2">
                          <input
                            autoFocus
                            value={aliasInput}
                            onChange={(e) => setAliasInput(e.target.value)}
                            className="px-2 py-1 border rounded"
                            onClick={(e) => e.stopPropagation()}
                          />
                          <button onClick={(e) => { e.stopPropagation(); saveAlias(patient.patient_id); }} className="text-xs text-blue-600">Save</button>
                          <button onClick={(e) => { e.stopPropagation(); cancelEdit(); }} className="text-xs text-slate-500">Cancel</button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <div className="truncate">{patient.patient_name}</div>
                          <div className="flex items-center gap-2 ml-3">
                            <button onClick={(e) => { e.stopPropagation(); startEditAlias(patient.patient_id, patient.patient_name); }} className="text-xs text-slate-500">Edit</button>
                            <button onClick={(e) => { e.stopPropagation(); deleteLink(patient.patient_id); }} className="text-xs text-rose-600">Delete</button>
                          </div>
                        </div>
                      )}
                    </td>
                    <td className={`px-3 py-4 border-y ${colorForAlert(patient.alert_status)}`}>{formatDate(patient.last_active)}</td>
                    <td className={`px-3 py-4 border-y ${colorForAlert(patient.alert_status)}`}>{patient.dominant_tier}</td>
                    <td className={`px-3 py-4 border-y ${colorForAlert(patient.alert_status)}`}>{patient.total_interactions_30d}</td>
                    <td className={`px-3 py-4 border-y ${colorForAlert(patient.alert_status)}`}>{formatDate(patient.last_blood_test_date)}</td>
                    <td className={`px-3 py-4 border-y ${colorForAlert(patient.alert_status)}`}>{patient.cycle_phase || '—'}</td>
                    <td className={`px-3 py-4 rounded-r-2xl border-y border-r font-bold ${colorForAlert(patient.alert_status)}`}>{patient.alert_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          <div className="xl:col-span-8 space-y-8">
            <section className="glass-card p-5 lg:p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-black">{tr('timeline')}</h2>
                <div className="text-xs text-slate-500 flex items-center gap-2"><TrendingUp size={14} />90 days</div>
              </div>
              {!selectedPatient ? (
                <div className="py-16 text-center text-slate-500">{tr('selectPatient')}</div>
              ) : (
                <div className="overflow-x-auto">
                  <svg viewBox="0 0 1000 280" className="w-full min-w-[900px] h-[280px] rounded-3xl bg-white/60 border border-slate-200">
                    <rect x="0" y="0" width="1000" height="280" fill="transparent" />
                    {chartData.bands.map((band, index) => (
                      <rect key={`${band.phase}-${index}`} x={band.x} y={20} width={band.w} height={200} fill={band.color} />
                    ))}
                    <line x1="60" y1="40" x2="60" y2="220" stroke="currentColor" strokeOpacity="0.2" />
                    <line x1="60" y1="220" x2="950" y2="220" stroke="currentColor" strokeOpacity="0.2" />
                    {chartData.biomarker.length > 1 && (
                      <polyline
                        fill="none"
                        stroke="#0ea5e9"
                        strokeWidth="3"
                        points={chartData.biomarker.map((point) => `${point.x},${point.y}`).join(' ')}
                      />
                    )}
                    {chartData.points.map((point, index) => (
                      <g key={`${point.label}-${index}`}>
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={point.tier === 'HIGH' ? 7 : point.tier === 'MEDIUM' ? 6 : 5}
                          fill={point.tier === 'HIGH' ? '#ef4444' : point.tier === 'MEDIUM' ? '#f59e0b' : '#22c55e'}
                        >
                          <title>{`${point.label} | ${point.flag} | score ${Number(point.score || 0).toFixed(3)}`}</title>
                        </circle>
                      </g>
                    ))}
                    {chartData.biomarker.map((point, index) => (
                      <circle key={`bio-${index}`} cx={point.x} cy={point.y} r={4} fill="#0ea5e9">
                        <title>{`${point.label || 'biomarker'} | ${point.value ?? 'NA'}`}</title>
                      </circle>
                    ))}
                    <text x="60" y="18" className="fill-slate-500 text-[10px] font-bold">Interaction severity</text>
                    <text x="820" y="18" className="fill-slate-500 text-[10px] font-bold">Biomarker trend</text>
                  </svg>
                </div>
              )}
            </section>

            <section className="glass-card p-5 lg:p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-black">{tr('mechanistic')}</h2>
                <span className="text-xs font-semibold text-slate-500">{mechRows.length} rows</span>
              </div>
              {!selectedPatient ? (
                <div className="py-16 text-center text-slate-500">{tr('selectPatient')}</div>
              ) : (
                <div className="space-y-3">
                  {selectedMechanisticCard.length === 0 ? (
                    <div className="py-10 text-center text-slate-500">No HIGH/MEDIUM interactions in the last 90 days.</div>
                  ) : selectedMechanisticCard.map((row) => {
                    const detail = detailCache[row.cacheKey];
                    const open = Boolean(expandedRows[row.cacheKey]);
                    return (
                      <div key={row.cacheKey} className="rounded-2xl border border-slate-200 bg-white/70 overflow-hidden">
                        <button
                          type="button"
                          onClick={() => void toggleRow(row.id)}
                          className="w-full flex items-center justify-between gap-4 px-4 py-4 text-left"
                        >
                          <div>
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">{row.tier}</div>
                            <div className="font-bold text-slate-900">{row.drug} × {row.food}</div>
                            <div className="text-xs text-slate-500 flex items-center gap-2"><Clock size={12} />{formatDate(row.date)}</div>
                          </div>
                          <ChevronRight size={18} className={`transition-transform ${open ? 'rotate-90' : ''}`} />
                        </button>
                        <AnimatePresence>
                          {open && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="border-t border-slate-200 px-4 py-4 space-y-3 text-sm"
                            >
                              {!detail ? (
                                <div className="text-slate-500">Loading mechanistic detail...</div>
                              ) : (
                                <>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div className="rounded-2xl bg-slate-50 border border-slate-200 p-3">
                                      <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">RotatE / KGE</div>
                                      <div>{detail.rotate?.summary || '—'}</div>
                                      <div className="text-xs text-slate-500 mt-1">Confidence: {(safeNumber(detail.rotate?.confidence) * 100).toFixed(1)}%</div>
                                    </div>
                                    <div className="rounded-2xl bg-slate-50 border border-slate-200 p-3">
                                      <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">HKG path</div>
                                      <div>{Array.isArray(detail.hkg?.path) ? detail.hkg?.path.join(' → ') : '—'}</div>
                                      <div className="text-xs text-slate-500 mt-1">Fusion score: {(safeNumber(detail.fusion?.fusion_score)).toFixed(3)}</div>
                                    </div>
                                  </div>
                                  <div className="rounded-2xl bg-blue-50 border border-blue-100 p-3">
                                    <div className="text-xs font-bold uppercase tracking-wider text-blue-700 mb-1">Fusion breakdown</div>
                                    <div className="text-sm text-blue-900">
                                      LightGCN: {String(detail.fusion?.lightgcn ?? 'NA')} • KGE: {String(detail.fusion?.kge ?? 'NA')} • HKG: {String(detail.fusion?.hkg ?? 'NA')} • Clinical gate: {String(detail.fusion?.clinical_gate || 'NA')}
                                    </div>
                                  </div>
                                  {detail.cycle_modifier?.note && (
                                    <div className="rounded-2xl bg-amber-50 border border-amber-100 p-3 text-amber-900">
                                      {detail.cycle_modifier.note}
                                    </div>
                                  )}
                                  {Array.isArray(detail.active_virtual_meds) && detail.active_virtual_meds.length > 0 && (
                                    <div className="rounded-2xl bg-emerald-50 border border-emerald-100 p-3 text-emerald-900">
                                      Active virtual meds: {detail.active_virtual_meds.map((item) => item.public_label).join(', ')}
                                    </div>
                                  )}
                                  <div className="flex items-center justify-end gap-2 pt-2">
                                    <button
                                      type="button"
                                      onClick={() => void exportReport(row.id)}
                                      className="inline-flex items-center gap-2 rounded-xl bg-clinical-blue px-3 py-2 text-white font-bold"
                                    >
                                      <Download size={14} />
                                      {tr('generatedReport')}
                                    </button>
                                  </div>
                                </>
                              )}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          <div className="xl:col-span-4 space-y-8">
            {/* Therapeutic Alternatives Finder */}
            <section className={`rounded-2xl backdrop-blur p-5 lg:p-6 border ${darkMode ? 'bg-slate-800/40 border-slate-700 text-slate-100' : 'bg-white/50 border-slate-200 text-slate-900'}`}>
              <h2 className="text-xl font-black mb-4">{tr('simulator')}</h2>

              {!simShowResults ? (
                // INPUT SECTION
                <div className="space-y-4">
                  {/* Drug Input */}
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1 block">{tr('medicationToEvaluate')}</label>
                    <input
                      type="text"
                      value={simForm.drug}
                      onChange={(event) => setSimForm((prev) => ({ ...prev, drug: event.target.value }))}
                      placeholder="e.g., Sintrom, Tahor, Mopral"
                      className={`w-full rounded-2xl border border-slate-200 px-4 py-3 outline-none ${darkMode ? 'bg-slate-700 text-slate-100 border-slate-600' : 'bg-white'}`}
                    />
                  </div>

                  {/* Cycle Phase Selection */}
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">{tr('cyclePhaseLabel')}</label>
                    <div className="flex flex-wrap gap-2">
                      {['Menstruation', 'Follicular', 'Ovulatory', 'Luteal', 'N/A'].map((phase) => {
                        const isActual = timeline?.cycle?.phase?.toLowerCase() === phase.toLowerCase();
                        const isSelected = simForm.cyclePhaseOverride === phase || (simForm.cyclePhaseOverride === null && isActual);
                        return (
                          <button
                            key={phase}
                            type="button"
                            onClick={() => setSimForm((prev) => ({ ...prev, cyclePhaseOverride: phase === 'N/A' ? null : phase }))}
                            className={`px-3 py-1.5 rounded-full text-sm font-medium transition ${
                              isSelected
                                ? 'bg-clinical-blue text-white'
                                : darkMode
                                  ? 'bg-slate-700 text-slate-300 border border-slate-600'
                                  : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}
                          >
                            {phase}
                          </button>
                        );
                      })}
                    </div>
                    {timeline?.cycle?.phase && (
                      <div className="text-xs text-slate-500 mt-1">
                        Actual: {timeline.cycle.phase} {simForm.cyclePhaseOverride && simForm.cyclePhaseOverride !== timeline.cycle.phase && (
                          <span className="text-amber-600 font-medium">(Override active)</span>
                        )}
                      </div>
                    )}
                    {!timeline?.cycle?.phase && (
                      <div className="text-xs text-slate-500 mt-1">No cycle data for this patient</div>
                    )}
                  </div>

                  {/* Virtual Meds (Biomarker Deficiencies) */}
                  {patientVirtualMeds.length > 0 && (
                    <div>
                      <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">{tr('activeDeficiencies')}</label>
                      <div className="flex flex-wrap gap-2">
                        {patientVirtualMeds.map((med: any) => {
                          const key = med.drug_name || med.public_label;
                          const isActive = activeVirtualMedToggles[key] !== false;
                          return (
                            <button
                              key={key}
                              type="button"
                              onClick={() => setActiveVirtualMedToggles((prev) => ({ ...prev, [key]: !isActive }))}
                              title={`Detected via Model 2: ${med.signal_reason || med.signal_key}`}
                              className={`px-3 py-1.5 rounded-full text-sm font-medium transition ${
                                isActive
                                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                  : 'bg-slate-200 text-slate-500 line-through border border-slate-300'
                              }`}
                            >
                              {med.public_label || med.drug_name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Dietary Pattern Info */}
                  {timeline?.interactions && timeline.interactions.length > 0 && (
                    <div className={`p-3 rounded-xl border-l-4 ${darkMode ? 'bg-slate-700/50 border-slate-500' : 'bg-slate-50 border-slate-400'}`}>
                      <div className="text-sm text-slate-600">
                        Simulation scores against {timeline.interactions.slice(0, 15).length} foods logged by this patient in the last 30 days.
                      </div>
                    </div>
                  )}

                  {/* Run Button */}
                  <button
                    type="button"
                    onClick={() => void runSimulation()}
                    disabled={simLoading || !selectedPatientId}
                    className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-clinical-blue px-4 py-3 font-bold text-white disabled:opacity-50"
                  >
                    <Activity size={16} />
                    {simLoading ? `${tr('scoringProgress')}...` : tr('findAlternatives')}
                  </button>

                  {simError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-red-900 text-sm">
                      <div className="flex items-start gap-2">
                        <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                        <div>{simError}</div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                // RESULTS SECTION
                <div className="space-y-4">
                  {/* Back Button */}
                  <button
                    type="button"
                    onClick={() => { setSimShowResults(false); setSimResult(null); }}
                    className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
                  >
                    ← {locale === 'fr' ? 'Nouvelle simulation' : 'Run new simulation'}
                  </button>

                  {/* Loading State */}
                  {simLoading && (
                    <div className="p-8 text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-clinical-blue mx-auto mb-3"></div>
                      <div className="text-slate-500">
                        {tr('scoringProgress')} {simForm.drug}...
                      </div>
                    </div>
                  )}

                  {/* Status: drug_class_unknown */}
                  {!simLoading && simResult?.status === 'drug_class_unknown' && (
                    <div className={`rounded-2xl border-l-4 border-amber-500 p-4 ${darkMode ? 'bg-amber-900/20' : 'bg-amber-50'}`}>
                      <div className="font-bold text-amber-900 mb-1">{locale === 'fr' ? 'Médicament non répertorié' : 'Medication not in database'}</div>
                      <div className="text-sm text-amber-800">{simResult.message_fr || simResult.message_en}</div>
                    </div>
                  )}

                  {/* Status: insufficient_diet_data */}
                  {!simLoading && simResult?.status === 'insufficient_diet_data' && (
                    <div className={`rounded-2xl border-l-4 border-amber-500 p-4 ${darkMode ? 'bg-amber-900/20' : 'bg-amber-50'}`}>
                      <div className="font-bold text-amber-900 mb-1">{tr('insufficientDietData')}</div>
                      <div className="text-sm text-amber-800 mb-3">{simResult.message_fr || simResult.message_en}</div>
                      <div className={`p-3 rounded-lg text-sm ${darkMode ? 'bg-slate-700' : 'bg-white'} border border-slate-200`}>
                        <div className="text-xs text-slate-500 mb-1">WhatsApp message (copy):</div>
                        <div className="italic">
                          {selectedPatient?.patient_name?.split(' ')[0] || 'Patient'}, pour améliorer la précision de votre suivi HealthOpt, pensez à enregistrer vos repas quotidiens dans l'application. Chaque aliment enregistré aide à mieux évaluer vos interactions médicamenteuses.
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Status: class_wide interaction */}
                  {!simLoading && simResult?.class_wide && (
                    <>
                      <div className={`rounded-2xl border-l-4 border-blue-500 p-4 ${darkMode ? 'bg-blue-900/20' : 'bg-blue-50'}`}>
                        <div className="font-bold text-blue-900 mb-1">{tr('classWideInteraction')}</div>
                        <div className="text-sm text-blue-800">{simResult.class_wide_note}</div>
                      </div>
                      <div className={`rounded-2xl border-l-4 border-emerald-500 p-4 ${darkMode ? 'bg-emerald-900/20' : 'bg-emerald-50'}`}>
                        <div className="font-bold text-emerald-900 mb-1">{tr('dietaryTimingAdvice')}</div>
                        <div className="text-sm text-emerald-800">{simResult.dietary_timing_advice}</div>
                      </div>
                    </>
                  )}

                  {/* Status: no_safer_option */}
                  {!simLoading && simResult?.no_alternatives_reason === 'no_safer_option' && (
                    <div className={`rounded-2xl border-l-4 border-amber-500 p-4 ${darkMode ? 'bg-amber-900/20' : 'bg-amber-50'}`}>
                      <div className="font-bold text-amber-900 mb-2">{tr('noAlternativesFound')}</div>
                      <div className="text-sm text-amber-800 mb-3">
                        All medications in the {simResult.currentDrug?.class_label} class produce equal or greater interaction risk against this patient's current dietary pattern.
                      </div>
                      {simResult.currentDrug && (
                        <div className={`p-3 rounded-lg text-sm ${darkMode ? 'bg-slate-700' : 'bg-white'} border border-slate-200`}>
                          <div className="font-semibold">{simResult.currentDrug.inn} ({simResult.currentDrug.trade_names?.join(' / ')})</div>
                          <div className="text-slate-500 text-xs mt-1">
                            Avg: {simResult.currentDrug.dietary_summary?.avg_score?.toFixed(2)} | HIGH: {simResult.currentDrug.dietary_summary?.high_count} | MED: {simResult.currentDrug.dietary_summary?.med_count} | LOW: {simResult.currentDrug.dietary_summary?.low_count}
                          </div>
                          {simResult.currentDrug.dietary_summary?.high_foods?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {simResult.currentDrug.dietary_summary.high_foods.map((food: string) => (
                                <span key={food} className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 text-xs">{food}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Status: ok with alternatives */}
                  {!simLoading && simResult?.status === 'ok' && simResult.qualified_alternatives?.length > 0 && (
                    <>
                      {/* Current Drug Baseline */}
                      <div className={`rounded-2xl p-4 border-l-4 ${
                        simResult.currentDrug?.dietary_summary?.worst_tier === 'HIGH'
                          ? 'border-rose-500 bg-rose-50'
                          : simResult.currentDrug?.dietary_summary?.worst_tier === 'MEDIUM'
                            ? 'border-amber-500 bg-amber-50'
                            : 'border-emerald-500 bg-emerald-50'
                      }`}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">{tr('currentMedication')}</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                            simResult.currentDrug?.dietary_summary?.worst_tier === 'HIGH'
                              ? 'bg-rose-200 text-rose-800'
                              : simResult.currentDrug?.dietary_summary?.worst_tier === 'MEDIUM'
                                ? 'bg-amber-200 text-amber-800'
                                : 'bg-emerald-200 text-emerald-800'
                          }`}>
                            {simResult.currentDrug?.dietary_summary?.worst_tier}
                          </span>
                        </div>
                        <div className="font-bold text-lg">{simResult.currentDrug?.inn}</div>
                        <div className="text-sm text-slate-500">{simResult.currentDrug?.trade_names?.join(' / ')}</div>
                        <div className="flex flex-wrap gap-2 mt-3">
                          {simResult.currentDrug?.dietary_summary?.high_count > 0 && (
                            <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 text-xs">HIGH: {simResult.currentDrug.dietary_summary.high_count}</span>
                          )}
                          {simResult.currentDrug?.dietary_summary?.med_count > 0 && (
                            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-xs">MEDIUM: {simResult.currentDrug.dietary_summary.med_count}</span>
                          )}
                          {simResult.currentDrug?.dietary_summary?.low_count > 0 && (
                            <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-xs">LOW: {simResult.currentDrug.dietary_summary.low_count}</span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 mt-2">
                          Avg score: {simResult.currentDrug?.dietary_summary?.avg_score?.toFixed(2)}
                        </div>
                      </div>

                      {/* Alternatives */}
                      {simResult.qualified_alternatives.map((alt: any) => (
                        <div key={alt.inn} className={`rounded-2xl p-4 border ${darkMode ? 'bg-slate-700/50 border-slate-600' : 'bg-white border-slate-200'}`}>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                              {tr('alternativeRank')} #{alt.rank}
                            </span>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              alt.cross_class
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-emerald-100 text-emerald-800'
                            }`}>
                              {alt.cross_class ? tr('differentClass') : tr('sameClass')}
                            </span>
                          </div>
                          <div className="font-bold">{alt.inn}</div>
                          <div className="text-sm text-slate-500">Algerian names: {alt.trade_names?.join(' / ')}</div>

                          {/* Comparison */}
                          <div className={`mt-3 p-3 rounded-lg ${darkMode ? 'bg-slate-800' : 'bg-slate-50'}`}>
                            <div className="grid grid-cols-3 gap-2 text-center text-sm">
                              <div>
                                <div className="text-xs text-slate-500">{simResult.currentDrug?.inn}</div>
                                <div className="font-semibold">{simResult.currentDrug?.dietary_summary?.high_count}</div>
                              </div>
                              <div className="flex items-center justify-center">
                                <span className="text-slate-400">→</span>
                              </div>
                              <div>
                                <div className="text-xs text-slate-500">{alt.inn}</div>
                                <div className="font-semibold">{alt.dietary_summary?.high_count}</div>
                                {alt.improvement?.high_count_delta < 0 && (
                                  <span className="text-xs text-emerald-600">↓{Math.abs(alt.improvement.high_count_delta)}</span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* CYP Fit Score */}
                          {alt.cyp_fit_score > 0 && (
                            <div className="mt-3">
                              <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                                <span>{tr('cycleFit')}:</span>
                                <span className={
                                  alt.cyp_fit_score > 0.7 ? 'text-emerald-600' :
                                  alt.cyp_fit_score > 0.4 ? 'text-amber-600' : 'text-rose-600'
                                }>
                                  {alt.cyp_fit_score > 0.7 ? 'Good' : alt.cyp_fit_score > 0.4 ? 'Moderate' : 'Poor'}
                                </span>
                              </div>
                              <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    alt.cyp_fit_score > 0.7 ? 'bg-emerald-500' :
                                    alt.cyp_fit_score > 0.4 ? 'bg-amber-500' : 'bg-rose-500'
                                  }`}
                                  style={{ width: `${alt.cyp_fit_score * 100}%` }}
                                />
                              </div>
                            </div>
                          )}

                          {/* Cross-class warning */}
                          {alt.cross_class && alt.cross_class_note && (
                            <div className={`mt-3 p-2 rounded text-xs ${darkMode ? 'bg-amber-900/30 text-amber-200' : 'bg-amber-100 text-amber-800'}`}>
                              <strong>Cross-class:</strong> {alt.cross_class_note}
                            </div>
                          )}

                          {/* Therapeutic Note */}
                          <details className="mt-3">
                            <summary className="text-xs text-slate-500 cursor-pointer">{tr('clinicalNote')}</summary>
                            <div className="mt-2 text-sm text-slate-600">{alt.therapeutic_note}</div>
                          </details>
                        </div>
                      ))}
                    </>
                  )}

                  {/* Advisory & Disclaimer (always show when results present) */}
                  {!simLoading && simResult && (
                    <div className={`p-3 rounded-lg text-xs text-slate-500 ${darkMode ? 'bg-slate-700/50' : 'bg-slate-100'}`}>
                      <div className="mb-1">{simResult.advisory_warning}</div>
                      <div className="text-slate-400">{simResult.disclaimer}</div>
                    </div>
                  )}
                </div>
              )}
            </section>

            <section className="glass-card p-5 lg:p-6">
              <h2 className="text-xl font-black mb-3">{tr('connected')}</h2>
              <div className="space-y-2 text-sm">
                {selectedPatient ? (
                  <>
                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-3">
                      <div className="font-bold text-slate-900">{selectedPatient.patient_name}</div>
                      <div className="text-slate-500">{selectedPatient.dominant_tier} • {selectedPatient.alert_status}</div>
                    </div>
                    <div className={`rounded-2xl border border-slate-200 p-3 ${darkMode ? 'bg-slate-800 text-slate-200' : 'bg-white/80 text-slate-600'}`}>
                      <div className="font-bold mb-2">{tr('deficiencies')}</div>
                      <div className="text-xs space-y-2">
                        <div>
                          <span className="font-semibold">Daily medications:</span> {selectedPatient.daily_medications || '—'}
                        </div>
                        <div>
                          <span className="font-semibold">Active deficiencies:</span>
                          {patientVirtualMeds && patientVirtualMeds.length > 0 ? (
                            <ul className="list-disc ml-5 mt-1">
                              {patientVirtualMeds.map((v, i) => (
                                <li key={i} className="text-sm">{v.public_label || v.drug_name || JSON.stringify(v)}</li>
                              ))}
                            </ul>
                          ) : (
                            <span className="ml-2 text-slate-500">No active deficiencies detected</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="text-slate-500">{tr('noPatients')}</div>
                )}
              </div>
            </section>
          </div>
        </section>
      </main>

      <footer className="max-w-7xl mx-auto px-6 lg:px-8 pb-8 text-xs text-slate-500">
        {tr('disclaimer')}
      </footer>
    </div>
  );
}

export default ProfessionalDashboard;
