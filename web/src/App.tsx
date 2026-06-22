import React from 'react';
import { Search, Pill, Apple, AlertCircle, Info, ChevronRight, Activity, Droplets, Calendar, TestTube, History, Plus, Save, Clock, SlidersHorizontal, Moon, Sun, X, KeyRound, Link2 } from 'lucide-react';
import ProfessionalDashboard from './ProfessionalDashboard';
import PharmacistDashboard from './PharmacistDashboard';
import NutritionistDashboard from './NutritionistDashboard';
import { motion, AnimatePresence } from 'motion/react';
import jsQR from 'jsqr';
import { ConfidenceTier, InteractionResult, PatientProfile } from './types';

type ProfessionalRole = 'doctor' | 'pharmacist' | 'nutritionist';

function ProfessionalRolePage() {
  const roles: Array<{ value: ProfessionalRole; label: string; blurb: string }> = [
    { value: 'doctor', label: 'Doctor', blurb: 'Clinical review, interactions, and patient linking.' },
    { value: 'pharmacist', label: 'Pharmacist', blurb: 'Medication safety, counseling, and alternatives.' },
    { value: 'nutritionist', label: 'Nutritionist', blurb: 'Dietary guidance and deficiency-focused follow-up.' },
  ];

  const chooseRole = (role: ProfessionalRole) => {
    if (role === 'pharmacist') {
      window.location.href = '/pharmacist-dashboard';
      return;
    }
    if (role === 'nutritionist') {
      window.location.href = '/nutritionist-dashboard';
      return;
    }
    window.location.href = `/doctor-dashboard?role=${encodeURIComponent(role)}`;
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_36%),linear-gradient(180deg,#f8fbff_0%,#eef4fb_100%)] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-10">
        <div className="grid w-full gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6 rounded-[2rem] border border-white/70 bg-white/85 p-8 shadow-[0_25px_70px_rgba(15,23,42,0.12)] backdrop-blur">
            <div className="inline-flex rounded-full bg-clinical-blue/10 px-4 py-2 text-sm font-semibold text-clinical-blue">
              Professional access
            </div>
            <div className="space-y-3">
              <h1 className="text-4xl font-black tracking-tight sm:text-5xl">Choose your workspace</h1>
              <p className="max-w-xl text-lg text-slate-600">
                Select the professional role you want to use. You’ll be taken to the PIN screen with that role already selected.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {roles.map((role) => (
                <button
                  key={role.value}
                  type="button"
                  onClick={() => chooseRole(role.value)}
                  className="group rounded-3xl border border-slate-200 bg-slate-50 p-5 text-left transition hover:-translate-y-1 hover:border-clinical-blue hover:bg-clinical-blue/5"
                >
                  <div className="text-lg font-black text-slate-900">{role.label}</div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{role.blurb}</p>
                  <div className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-clinical-blue">
                    Continue
                    <ChevronRight size={16} className="transition group-hover:translate-x-1" />
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-slate-950 p-8 text-white shadow-[0_25px_70px_rgba(15,23,42,0.28)]">
            <div className="space-y-3">
              <div className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/70">
                Clinical decision support
              </div>
              <h2 className="text-3xl font-black">Role-specific tools in one place</h2>
              <p className="text-white/75">
                Each role opens the same secure workspace with a tailored clinical focus, link-code access, and patient dashboards.
              </p>
            </div>
            <div className="mt-8 space-y-4 text-sm text-white/80">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Doctor: interaction review and patient risk matrix.</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Pharmacist: medication safety and therapeutic alternatives.</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Nutritionist: deficiency tracking and dietary support.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  // Check for professional route early, before any hooks
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/professional-login')) {
    return <ProfessionalDashboard initialRole="doctor" />;
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/pharmacist-dashboard')) {
    return <PharmacistDashboard />;
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/nutritionist-dashboard')) {
    return <NutritionistDashboard />;
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/doctor-dashboard')) {
    const role = new URLSearchParams(window.location.search).get('role');
    if (role === 'pharmacist') {
      window.location.replace('/pharmacist-dashboard');
      return null;
    }
    if (role === 'nutritionist') {
      window.location.replace('/nutritionist-dashboard');
      return null;
    }
    return <ProfessionalDashboard initialRole="doctor" />;
  }

  const [activeTab, setActiveTab] = React.useState<'analyze' | 'health' | 'history' | 'settings'>('analyze');
  const [manualDrug, setManualDrug] = React.useState('');
  const [food, setFood] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [analyzingPdf, setAnalyzingPdf] = React.useState(false);
  const [scanningQr, setScanningQr] = React.useState(false);
  const [results, setResults] = React.useState<any[]>([]);
  const [analysisNotice, setAnalysisNotice] = React.useState<{ type: 'error' | 'info'; text: string } | null>(null);
  const [expandedResults, setExpandedResults] = React.useState<Set<number>>(new Set());
  const [history, setHistory] = React.useState<any[]>([]);
  
  const [bloodData, setBloodData] = React.useState<any>({});
  const [bloodDraft, setBloodDraft] = React.useState<any>({});
  const [activeVirtualDeficiencies, setActiveVirtualDeficiencies] = React.useState<any[]>([]);
  const [cycleData, setCycleData] = React.useState<any>({});
  const [profile, setProfile] = React.useState<any>({ gender: 'female', age: '', daily_medications: '' });
  const [ageDraft, setAgeDraft] = React.useState<string>('');
  const [medicationsDraft, setMedicationsDraft] = React.useState('');
  const [savingMedications, setSavingMedications] = React.useState(false);
  const [medicationsSaveNotice, setMedicationsSaveNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [ageSaveNotice, setAgeSaveNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [bloodVaultNotice, setBloodVaultNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [referralActions, setReferralActions] = React.useState<any[]>([]);
  const [referralDismissUntil, setReferralDismissUntil] = React.useState<number | null>(null);
  const [referralDismissKey, setReferralDismissKey] = React.useState<string | null>(null);
  const [nearbyLabsOpen, setNearbyLabsOpen] = React.useState(false);
  const [nearbyLabs, setNearbyLabs] = React.useState<any[]>([]);
  const [showReferralWhyModal, setShowReferralWhyModal] = React.useState(false);
  const [backendStatus, setBackendStatus] = React.useState<any>({ ready: false, loading: true, status: 'loading' });
  const [subscription, setSubscription] = React.useState<{ plan: 'free' | 'pro'; isPremium: boolean }>({ plan: 'free', isPremium: false });
  const [authState, setAuthState] = React.useState<{ authenticated: boolean; email: string | null }>({ authenticated: false, email: null });
  const [usage, setUsage] = React.useState<{ scansToday: number; freeDailyLimit: number }>({ scansToday: 0, freeDailyLimit: 3 });
  const [showPremiumModal, setShowPremiumModal] = React.useState(false);
  const [showAuthModal, setShowAuthModal] = React.useState(false);
  const [authMode, setAuthMode] = React.useState<'signin' | 'signup'>('signin');
  const [authEmail, setAuthEmail] = React.useState('');
  const [authPassword, setAuthPassword] = React.useState('');
  const [authNotice, setAuthNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [authLoading, setAuthLoading] = React.useState(false);
  const [pendingProAfterAuth, setPendingProAfterAuth] = React.useState(false);
  const [premiumMessage, setPremiumMessage] = React.useState('');
  const [showExportModal, setShowExportModal] = React.useState(false);
  const [exportIncludeBloodTrends, setExportIncludeBloodTrends] = React.useState(true);
  const [savingHistoryId, setSavingHistoryId] = React.useState<number | null>(null);
  const [exportNotice, setExportNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [planNotice, setPlanNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showInstallGuide, setShowInstallGuide] = React.useState(false);
  const [shareCode, setShareCode] = React.useState('');
  const [shareCodeNotice, setShareCodeNotice] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [shareCodeLoading, setShareCodeLoading] = React.useState(false);
  const [cycleStartDate, setCycleStartDate] = React.useState(new Date().toISOString().split('T')[0]);
  const [cycleDurationDraft, setCycleDurationDraft] = React.useState<number>(28);
  const [periodLengthDraft, setPeriodLengthDraft] = React.useState<number>(5);
  const pdfInputRef = React.useRef<HTMLInputElement | null>(null);
  const qrInputRef = React.useRef<HTMLInputElement | null>(null);
  const [language, setLanguage] = React.useState<'en' | 'fr' | 'ar'>('en');
  const [darkMode, setDarkMode] = React.useState(false);

  React.useEffect(() => {
    fetchData();
  }, []);

  React.useEffect(() => {
    const savedLang = localStorage.getItem('healthopt.lang');
    const savedTheme = localStorage.getItem('healthopt.theme');
    if (savedLang === 'fr' || savedLang === 'ar' || savedLang === 'en') {
      setLanguage(savedLang);
    }
    if (savedTheme === 'dark') {
      setDarkMode(true);
    }
  }, []);

  React.useEffect(() => {
    localStorage.setItem('healthopt.lang', language);
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
  }, [language]);

  React.useEffect(() => {
    localStorage.setItem('healthopt.theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const translations: Record<'en' | 'fr' | 'ar', Record<string, string>> = {
    en: {
      'tab.analyze': 'Analyze',
      'tab.health': 'Health',
      'tab.history': 'History',
      'tab.settings': 'Settings',
      'status.live': 'Live Engine',
      'status.warming': 'Warming up engines',
      'header.join': 'Log In / Join Pro',
      'header.subscription': 'Subscription',
      'header.proActive': 'Pro Active',
      'header.mobileApp': 'Mobile App',
      'header.tagline': 'You are what you eat',
      'install.title': 'Install HealthOpt',
      'install.subtitle': 'Get the full mobile experience on your home screen.',
      'install.step1': 'Tap the Share button in your browser (bottom on iOS, top-right on Android).',
      'install.step2': 'Select "Add to Home Screen" from the menu.',
      'common.gotIt': 'Got it',
      'auth.create': 'Create account',
      'auth.signin': 'Sign in',
      'auth.signup': 'Sign up',
      'auth.subtitle': 'Sign in first, then choose your subscription plan.',
      'common.cancel': 'Cancel',
      'common.email': 'Email',
      'common.password': 'Password',
      'common.proBadge': 'Pro',
      'common.proSuffix': '(Pro)',
      'common.wait': 'Please wait...',
      'premium.title': 'Unlock HealthOpt Pro',
      'premium.freeBlurb': 'Free: analysis, manual tracking, limited daily scans',
      'premium.proBlurb': 'Pro: AI PDF extraction, verified physician report export, premium sync',
      'premium.signinRequired': 'Sign in is required before activating a paid plan.',
      'premium.upgradeDefault': 'Upgrade for AI sync, verified intake reports, and premium automation.',
      'premium.pdfExtractPrompt': 'Let our AI extract your biomarkers automatically. Upgrade to Pro.',
      'premium.cycleSyncPrompt': 'Cycle-aware interaction sync is a Pro feature. Upgrade to enable advanced women\'s health context.',
      'premium.keepFree': 'Keep Free',
      'premium.startPro': 'Start Pro',
      'premium.deactivatePro': 'Deactivate Pro',
      'analyze.smart': 'Smart Analysis',
      'analyze.context': 'Active Context',
      'analyze.currentCycle': 'Current Cycle Phase',
      'analyze.day': 'Day',
      'analyze.of28': 'of 28',
      'analyze.ofCycle': 'of {value}',
      'analyze.cypLine': 'CYP3A4 activity is {value}. Interaction tiers are adjusted automatically.',
      'analyze.cypIncreased': 'adjusted',
      'analyze.cypBaseline': 'at baseline',
      'analyze.profileSynced': 'PROFILE SYNCED',
      'analyze.unsavedMeds': 'UNSAVED MEDS',
      'analyze.ironDeficiency': 'Iron Deficiency',
      'analyze.vitdDeficiency': 'Vit D Deficiency',
      'analyze.zincDeficiency': 'Zinc Deficiency',
      'analyze.b12Deficiency': 'Vit B12 Deficiency',
      'analyze.folateDeficiency': 'Folate Deficiency',
      'analyze.calciumDeficiency': 'Calcium Deficiency',
      'analyze.magnesiumDeficiency': 'Magnesium Deficiency',
      'analyze.iodineDeficiency': 'Iodine Deficiency',
      'analyze.manualMedication': 'Manual medication to check: {name}',
      'analyze.noProfile': 'No profile data found. Update in Health tab.',
      'analyze.dailyScans': 'Daily Free Scans',
      'analyze.scansUsed': '{used} of {limit} used',
      'analyze.limitReached': "You reached today's free target. Continue exploring and upgrade for unlimited advanced sync/export tools.",
      'analyze.run': 'Run Smart Analysis',
      'analyze.inputFood': 'Food or Beverage',
      'analyze.inputFoodPh': 'e.g., Pizza, Grapefruit Juice, Coffee',
      'analyze.inputDrug': 'Additional Medication',
      'analyze.inputDrugOpt': '(Optional)',
      'analyze.inputDrugPh': 'e.g., Ibuprofen',
      'health.profile': 'User Profile',
      'health.gender': 'Gender',
      'health.age': 'Age',
      'health.ageHint': 'Used as profile context for interaction and pharmacokinetic adjustments.',
      'health.saveAge': 'Save Age',
      'health.female': 'Female',
      'health.male': 'Male',
      'health.dailyMeds': 'Daily Medications',
      'health.dailyMedsHint': 'These will be automatically checked during analysis.',
      'health.saveMeds': 'Save Medications',
      'health.saving': 'Saving...',
      'health.bloodVault': 'Blood Test Vault',
      'health.uploadHint': 'Upload PDF for AI-powered extraction',
      'health.uploadPdf': 'Upload PDF',
      'health.analyzing': 'Analyzing...',
      'health.updateProfile': 'Update Health Profile',
      'health.clearDeficiencies': 'Clear Deficiencies',
      'health.clearDeficienciesHint': 'Deficiency inputs cleared from vault context.',
      'health.cycleTracker': 'Cycle Tracker',
      'health.saveCycle': 'Save Cycle Start',
      'health.clearCycle': 'Clear Cycle Start',
      'health.lastLogged': 'Last logged: {value}',
      'health.never': 'Never',
      'history.title': 'Analysis History',
      'history.report': 'Generate Physician Report',
      'history.logConsumed': 'Log as consumed',
      'history.loggedConsumed': 'Logged as consumed',
      'history.none': 'No analysis history found',
      'settings.title': 'App Settings',
      'settings.subtitle': 'Customize display language and theme for your daily workflow.',
      'settings.language': 'Language',
      'settings.appearance': 'Appearance',
      'settings.darkEnabled': 'Dark mode enabled',
      'settings.lightEnabled': 'Light mode enabled',
      'settings.dark': 'Dark',
      'settings.light': 'Light',
      'settings.shareCode': 'Patient share code',
      'settings.shareCodeHint': 'Generate a 6-digit code for a professional to link your patient record.',
      'settings.generateShareCode': 'Generate share code',
      'notice.pdfSaved': 'PDF analyzed. Biomarkers updated.',
      'notice.shareCodeGenerated': 'Share code generated: {code}',
      'notice.shareCodeFailed': 'Failed to generate share code.',
      'notice.pdfFailed': 'Failed to analyze PDF.',
      'notice.bloodSaved': 'Blood test results saved to vault.',
      'notice.deficienciesCleared': 'Deficiency inputs cleared from vault context.',
      'notice.selectDate': 'Please choose a start date first.',
      'notice.proActivated': 'Pro activated.',
      'notice.freeSwitched': 'Switched to free plan.',
      'notice.signinFirst': 'Please sign in first.',
      'notice.failedPlan': 'Failed to update plan.',
      'notice.savedAge': 'Age saved.',
      'notice.failedAge': 'Failed to save age.',
      'notice.savedMeds': 'Daily medications saved.',
      'notice.deletedMed': 'Removed medication: {name}',
      'notice.failedMeds': 'Failed to save daily medications.',
      'notice.authCreated': 'Account created.',
      'notice.authSignedIn': 'Signed in successfully.',
      'notice.authFailed': 'Authentication failed.',
      'notice.predUnavailable': 'Prediction service is unavailable.',
      'notice.warmingSuffix': 'Warming up engines...',
      'notice.physicianAvailablePro': 'Physician report export is available on Pro.',
      'notice.physicianExportOk': 'Physician report exported successfully.',
      'notice.physicianExportFail': 'Failed to export physician report.',
      'notice.consumedLogged': 'Interaction logged as consumed.',
      'notice.consumedTheoretical': 'Interaction marked as theoretical.',
      'notice.consumedFailed': 'Failed to update consumed status.',
      'notice.exportFailed': 'Export failed',
      'results.noInteractionBadge': 'No Interaction Detected',
      'results.interactionBadge': 'Interaction Detected',
      'results.noInteractionTitle': 'No Interaction Detected',
      'results.context': 'CONTEXT',
      'results.manualMedicationNotice': 'This warning is based on the manual medication you entered.',
      'results.risk': 'RISK',
      'results.confidence': 'Confidence',
      'results.physCertaintyTitle': 'HIGH - Clinical Safety Gate Certainty',
      'results.physCertaintyBody': 'This interaction was detected by deterministic safety gate rules, not statistical probability. Confidence scores do not apply.',
      'results.medication': 'Medication',
      'results.food': 'Food',
      'results.whatHappening': 'What is happening?',
      'results.whyMatters': 'Why this matters for you:',
      'results.howFix': 'How to fix it:',
      'results.directExplanation': 'Direct Explanation',
      'results.whatToDo': 'What to do',
      'results.compoundsIdentified': 'Compounds Identified',
      'results.bioactiveCompounds': 'Bioactive Compounds:',
      'results.nutrients': 'Nutrients:',
      'results.fallbackDetected': 'Interaction detected.',
      'results.showTechnical': 'Show Technical AI Diagnostics',
      'results.hideTechnical': 'Hide Technical AI Diagnostics',
      'results.layerScores': 'Layer Scores',
      'results.layer0': 'Layer 0 (Clinical Safety Gate)',
      'results.layer1': 'Layer 1 (Graph)',
      'results.layer2': 'Layer 2 (KGE)',
      'results.layer3': 'Layer 3 (LightGCN)',
      'results.layer4': 'Layer 4 (Fusion)',
      'results.normalized': 'normalized',
      'results.raw': 'raw',
      'results.found': 'found',
      'results.notFound': 'not found',
      'results.warnings': 'warnings',
      'health.savedMeds': 'Saved Medications',
      'health.noSavedMeds': 'No saved daily medications yet.',
      'health.removeMed': 'Remove medication',
      'health.delete': 'Delete',
      'results.fusionScore': 'Fusion Score',
      'results.enzymePathways': 'Enzyme Pathways',
      'results.graph': 'Graph',
      'results.kge': 'KGE',
      'results.modelFlags': 'Model Flags',
      'results.detailedMechanism': 'Enzyme Mechanistic Path',
      'results.errorDisplay': 'Error displaying result',
      'results.emptyPrompt': 'Enter a food or beverage to analyze against your profile context',
      'health.medsPlaceholder': 'e.g., Sintrom, Metformin (comma separated)',
      'health.score': 'Health Score',
      'health.scoreSubtitle': 'Based on latest biomarkers and interactions.',
      'health.syncInteractions': 'Sync with interactions',
      'health.syncInteractionsHint': 'Cycle-aware interaction adjustments and premium context scoring',
      'health.enabled': 'Enabled',
      'health.periodStartDate': 'Period Start Date',
      'health.cycleDuration': 'Cycle Length (days)',
      'health.periodLength': 'Period Length (bleeding days)',
      'health.day': 'Day',
      'health.logStart': 'Log Start',
      'cycle.phase.menstrual': 'Menstrual',
      'cycle.phase.follicular': 'Follicular',
      'cycle.phase.ovulatory': 'Ovulatory',
      'cycle.phase.luteal': 'Luteal',
      'referral.bannerTitle': 'Lab test recommended',
      'referral.uploadResults': 'Upload results',
      'referral.findPartnerLab': 'Find partner lab',
      'referral.why': 'Why?',
      'referral.remind7d': 'Remind in 7d',
      'referral.dismiss': 'Dismiss',
      'referral.metricLastTest': 'Last test {days} days ago',
      'referral.metricFlags': '{count} recent flags',
      'referral.metricRecommended': 'Recommended: {tests}',
      'referral.whyTitle': 'Why this lab test recommendation?',
      'referral.urgencyRecommended': 'Recommended',
      'referral.urgencyUrgent': 'Urgent',
      'referral.reasonDefault': 'Recent health signals suggest updated blood tests would improve safety.',
      'referral.reasonStaleWithDays': 'Your last blood profile is {days} days old, which may no longer reflect your current status.',
      'referral.reasonStaleNoDays': 'Your blood profile appears outdated and should be refreshed.',
      'referral.reasonFreqWithCount': 'We detected {count} recent interaction-risk events, so updated labs are advised before continuing.',
      'referral.reasonFreqNoCount': 'We detected repeated interaction-risk patterns, so updated labs are advised.',
      'history.referralPattern': '📊 Pattern detected: {count} {drug} interactions this month. A lab check is recommended. [View Details]',
      'analyze.missingBiomarkerNotice': '⚠️ Analysis is running without {biomarker} data for {drug}. Add your lab results in Health tab for more precise scoring.',
      'referral.recommendedTests': 'Recommended tests',
      'referral.nextAction': 'Next action: review your Blood Test Vault or use a partner lab for a discounted panel.',
      'referral.close': 'Close',
      'referral.nearbyLabsTitle': 'Nearby partner labs',
      'referral.noNearbyLabs': 'No labs found nearby.',
      'referral.failedNearbyLabs': 'Failed to fetch nearby labs',
      'referral.unableNearbyLabs': 'Unable to find partner labs',
      'history.exportTitle': 'Physician Report Export',
      'history.exportPrompt': 'What would you like to include in your report?',
      'history.includeTheoretical': 'Include all searched interactions (theoretical)',
      'history.includeConsumedOnly': 'Include only verified consumed interactions (recommended)',
      'history.includeBlood': 'Include blood test trends',
      'health.cycleDisabledTitle': 'Cycle Tracker Disabled',
      'health.cycleDisabledBody': 'Cycle tracking is only available for female profiles.',
      'common.export': 'Export'
    },
    fr: {
      'tab.analyze': 'Analyser',
      'tab.health': 'Santé',
      'tab.history': 'Historique',
      'tab.settings': 'Paramètres',
      'status.live': 'Moteur actif',
      'status.warming': 'Mise en chauffe',
      'header.join': 'Connexion / Pro',
      'header.subscription': 'Abonnement',
      'header.proActive': 'Pro actif',
      'header.mobileApp': 'Application mobile',
      'header.tagline': 'Vous êtes ce que vous mangez',
      'install.title': 'Installer HealthOpt',
      'install.subtitle': 'Profitez de l\'expérience mobile complète sur votre écran d\'accueil.',
      'install.step1': 'Touchez le bouton Partager dans votre navigateur (bas iOS, haut droite Android).',
      'install.step2': 'Sélectionnez "Ajouter à l\'écran d\'accueil".',
      'common.gotIt': 'Compris',
      'auth.create': 'Créer un compte',
      'auth.signin': 'Se connecter',
      'auth.signup': 'S\'inscrire',
      'auth.subtitle': 'Connectez-vous, puis choisissez votre abonnement.',
      'common.cancel': 'Annuler',
      'common.email': 'E-mail',
      'common.password': 'Mot de passe',
      'common.proBadge': 'Pro',
      'common.proSuffix': '(Pro)',
      'common.wait': 'Veuillez patienter...',
      'premium.title': 'Débloquer HealthOpt Pro',
      'premium.freeBlurb': 'Gratuit : analyses, suivi manuel, scans quotidiens limités',
      'premium.proBlurb': 'Pro : extraction PDF IA, rapport médecin vérifié, synchronisation premium',
      'premium.signinRequired': 'La connexion est requise avant d\'activer un plan payant.',
      'premium.upgradeDefault': 'Passez à Pro pour la synchronisation IA, les rapports d\'ingestion vérifiés et l\'automatisation premium.',
      'premium.pdfExtractPrompt': 'Laissez notre IA extraire automatiquement vos biomarqueurs. Passez à Pro.',
      'premium.cycleSyncPrompt': 'La synchronisation des interactions selon le cycle est une fonctionnalité Pro. Passez à Pro pour un contexte santé avancé.',
      'premium.keepFree': 'Rester gratuit',
      'premium.startPro': 'Commencer Pro',
      'premium.deactivatePro': 'Désactiver Pro',
      'analyze.smart': 'Analyse intelligente',
      'analyze.context': 'Contexte actif',
      'analyze.currentCycle': 'Phase actuelle du cycle',
      'analyze.day': 'Jour',
      'analyze.of28': 'sur 28',
      'analyze.ofCycle': 'sur {value}',
      'analyze.cypLine': 'L\'activité CYP3A4 est {value}. Les niveaux d\'interaction sont ajustés automatiquement.',
      'analyze.cypIncreased': 'ajustée',
      'analyze.cypBaseline': 'au niveau de base',
      'analyze.profileSynced': 'PROFIL SYNCHRONISÉ',
      'analyze.unsavedMeds': 'MÉDICAMENTS NON ENREGISTRÉS',
      'analyze.ironDeficiency': 'Carence en fer',
      'analyze.vitdDeficiency': 'Carence en vitamine D',
      'analyze.zincDeficiency': 'Carence en zinc',
      'analyze.b12Deficiency': 'Carence en vitamine B12',
      'analyze.folateDeficiency': 'Carence en folates',
      'analyze.calciumDeficiency': 'Carence en calcium',
      'analyze.magnesiumDeficiency': 'Carence en magnesium',
      'analyze.iodineDeficiency': 'Carence en iode',
      'analyze.manualMedication': 'Médicament manuel à vérifier : {name}',
      'analyze.noProfile': 'Aucune donnée de profil. Mettez à jour l\'onglet Santé.',
      'analyze.dailyScans': 'Scans gratuits quotidiens',
      'analyze.scansUsed': '{used} sur {limit} utilisés',
      'analyze.limitReached': 'Votre quota gratuit du jour est atteint. Continuez et passez à Pro pour des outils de synchronisation/export avancés illimités.',
      'analyze.run': 'Lancer l\'analyse',
      'analyze.inputFood': 'Aliment ou boisson',
      'analyze.inputFoodPh': 'ex. : Pizza, jus de pamplemousse, café',
      'analyze.inputDrug': 'Médicament supplémentaire',
      'analyze.inputDrugOpt': '(Optionnel)',
      'analyze.inputDrugPh': 'ex. : Ibuprofène',
      'health.profile': 'Profil utilisateur',
      'health.gender': 'Genre',
      'health.age': 'Âge',
      'health.ageHint': 'Utilisé comme contexte de profil pour les ajustements pharmacocinétiques et d’interaction.',
      'health.female': 'Femme',
      'health.male': 'Homme',
      'health.dailyMeds': 'Médicaments quotidiens',
      'health.dailyMedsHint': 'Ils seront vérifiés automatiquement pendant l\'analyse.',
      'health.saveMeds': 'Enregistrer les médicaments',
      'health.saving': 'Enregistrement...',
      'health.bloodVault': 'Coffre des analyses sanguines',
      'health.uploadHint': 'Téléversez un PDF pour une extraction IA',
      'health.uploadPdf': 'Téléverser PDF',
      'health.analyzing': 'Analyse en cours...',
      'health.updateProfile': 'Mettre à jour le profil de santé',
      'health.clearDeficiencies': 'Effacer les carences',
      'health.clearDeficienciesHint': 'Les entrées de carence sont supprimées du contexte du coffre.',
      'health.cycleTracker': 'Suivi du cycle',
      'health.saveCycle': 'Enregistrer le début du cycle',
      'health.clearCycle': 'Effacer le début du cycle',
      'health.lastLogged': 'Dernier enregistrement : {value}',
      'health.never': 'Jamais',
      'notice.pdfSaved': 'PDF analysé. Biomarqueurs mis à jour.',
      'notice.shareCodeGenerated': 'Code de partage généré : {code}',
      'notice.shareCodeFailed': 'Échec de génération du code de partage.',
      'notice.pdfFailed': 'Échec de l\'analyse PDF.',
      'notice.bloodSaved': 'Résultats sanguins enregistrés.',
      'notice.deficienciesCleared': 'Les valeurs de carence ont été effacées du contexte.',
      'notice.selectDate': 'Veuillez d\'abord choisir une date de début.',
      'notice.proActivated': 'Pro activé.',
      'notice.freeSwitched': 'Passage au plan gratuit.',
      'notice.signinFirst': 'Veuillez vous connecter d\'abord.',
      'notice.failedPlan': 'Échec de la mise à jour du plan.',
      'notice.savedAge': 'Âge enregistré.',
      'notice.failedAge': 'Échec de l\'enregistrement de l\'âge.',
      'notice.savedMeds': 'Médicaments quotidiens enregistrés.',
      'notice.deletedMed': 'Médicament retiré : {name}',
      'notice.failedMeds': 'Échec de l\'enregistrement des médicaments.',
      'notice.authCreated': 'Compte créé.',
      'notice.authSignedIn': 'Connexion réussie.',
      'notice.authFailed': 'Échec de l\'authentification.',
      'notice.predUnavailable': 'Le service de prédiction est indisponible.',
      'notice.warmingSuffix': 'Mise en chauffe des moteurs...',
      'notice.physicianAvailablePro': 'L\'export de rapport médecin est disponible en Pro.',
      'notice.physicianExportOk': 'Rapport médecin exporté avec succès.',
      'notice.physicianExportFail': 'Échec de l\'export du rapport médecin.',
      'notice.consumedLogged': 'Interaction enregistrée comme consommée.',
      'notice.consumedTheoretical': 'Interaction marquée comme théorique.',
      'notice.consumedFailed': 'Échec de la mise à jour du statut consommé.',
      'notice.exportFailed': 'Échec de l\'export',
      'history.report': 'Générer un rapport médecin',
      'history.logConsumed': 'Marquer comme consommé',
      'history.loggedConsumed': 'Consommé enregistré',
      'history.none': 'Aucun historique d\'analyse',
      'history.exportTitle': 'Export du rapport médecin',
      'history.exportPrompt': 'Que souhaitez-vous inclure dans votre rapport ?',
      'history.includeTheoretical': 'Inclure toutes les interactions recherchées (théoriques)',
      'history.includeConsumedOnly': 'Inclure uniquement les interactions consommées vérifiées (recommandé)',
      'history.includeBlood': 'Inclure les tendances des analyses sanguines',
      'results.noInteractionBadge': 'Aucune interaction détectée',
      'results.interactionBadge': 'Interaction détectée',
      'results.noInteractionTitle': 'Aucune interaction détectée',
      'results.context': 'CONTEXTE',
      'results.manualMedicationNotice': 'Cet avertissement est basé sur le médicament saisi manuellement.',
      'results.risk': 'RISQUE',
      'results.confidence': 'Confiance',
      'results.physCertaintyTitle': 'ÉLEVÉ - Certitude du garde-fou clinique',
      'results.physCertaintyBody': 'Cette interaction a été détectée par des règles déterministes de sécurité, pas par une probabilité statistique. Les scores de confiance ne s\'appliquent pas.',
      'results.medication': 'Médicament',
      'results.food': 'Aliment',
      'results.whatHappening': 'Que se passe-t-il ?',
      'results.whyMatters': 'Pourquoi c\'est important pour vous :',
      'results.howFix': 'Comment corriger :',
      'results.directExplanation': 'Explication directe',
      'results.whatToDo': 'Que faire',
      'results.compoundsIdentified': 'Composés identifiés',
      'results.bioactiveCompounds': 'Composés bioactifs :',
      'results.nutrients': 'Nutriments :',
      'results.fallbackDetected': 'Interaction détectée.',
      'results.showTechnical': 'Afficher les diagnostics IA techniques',
      'results.hideTechnical': 'Masquer les diagnostics IA techniques',
      'results.layerScores': 'Scores des couches',
      'results.layer0': 'Couche 0 (Garde-fou clinique)',
      'results.layer1': 'Couche 1 (Graphe)',
      'results.layer2': 'Couche 2 (KGE)',
      'results.layer3': 'Couche 3 (LightGCN)',
      'results.layer4': 'Couche 4 (Fusion)',
      'results.normalized': 'normalisé',
      'results.raw': 'brut',
      'results.found': 'trouvé',
      'results.notFound': 'non trouvé',
      'results.warnings': 'alertes',
      'health.savedMeds': 'Médicaments enregistrés',
      'health.noSavedMeds': 'Aucun médicament quotidien enregistré.',
      'health.removeMed': 'Retirer le médicament',
      'health.delete': 'Supprimer',
      'results.fusionScore': 'Score de fusion',
      'results.enzymePathways': 'Voies enzymatiques',
      'results.graph': 'Graphe',
      'results.kge': 'KGE',
      'results.modelFlags': 'Indicateurs du modèle',
      'results.detailedMechanism': 'Voie mécanistique enzymatique',
      'results.errorDisplay': 'Erreur d\'affichage du résultat',
      'results.emptyPrompt': 'Entrez un aliment ou une boisson à analyser selon votre profil',
      'health.medsPlaceholder': 'ex. : Sintrom, Metformin (séparés par des virgules)',
      'health.score': 'Score de santé',
      'health.scoreSubtitle': 'Basé sur les derniers biomarqueurs et interactions.',
      'health.syncInteractions': 'Synchroniser avec les interactions',
      'health.syncInteractionsHint': 'Ajustements selon le cycle et score contextuel premium',
      'health.enabled': 'Activé',
      'health.periodStartDate': 'Date de début des règles',
      'health.cycleDuration': 'Durée du cycle (jours)',
      'health.periodLength': 'Durée des règles (jours de saignement)',
      'health.day': 'Jour',
      'health.logStart': 'Enregistrer le début',
      'health.cycleDisabledTitle': 'Suivi du cycle désactivé',
      'health.cycleDisabledBody': 'Le suivi du cycle est disponible uniquement pour les profils féminins.',
      'cycle.phase.menstrual': 'Menstruel',
      'cycle.phase.follicular': 'Folliculaire',
      'cycle.phase.ovulatory': 'Ovulatoire',
      'cycle.phase.luteal': 'Lutéal',
      'referral.bannerTitle': 'Bilan sanguin recommandé',
      'referral.uploadResults': 'Téléverser les résultats',
      'referral.findPartnerLab': 'Trouver un laboratoire partenaire',
      'referral.why': 'Pourquoi ? ',
      'referral.remind7d': 'Me rappeler dans 7 j',
      'referral.dismiss': 'Ignorer',
      'referral.metricLastTest': 'Dernier test il y a {days} jours',
      'referral.metricFlags': '{count} alertes récentes',
      'referral.metricRecommended': 'Recommandé : {tests}',
      'referral.whyTitle': 'Pourquoi cette recommandation de bilan ?',
      'referral.urgencyRecommended': 'Recommandé',
      'referral.urgencyUrgent': 'Urgent',
      'referral.reasonDefault': 'Des signaux de santé récents suggèrent de mettre à jour vos analyses sanguines.',
      'referral.reasonStaleWithDays': 'Votre dernier profil sanguin date de {days} jours et peut ne plus refléter votre état actuel.',
      'referral.reasonStaleNoDays': 'Votre profil sanguin semble obsolète et doit être actualisé.',
      'referral.reasonFreqWithCount': 'Nous avons détecté {count} événements récents de risque d\'interaction, donc un bilan mis à jour est conseillé.',
      'referral.reasonFreqNoCount': 'Nous avons détecté des schémas répétés de risque d\'interaction, donc un bilan est conseillé.',
      'history.referralPattern': '📊 Modèle détecté : {count} interactions avec {drug} ce mois. Un bilan est recommandé. [Voir les détails]',
      'analyze.missingBiomarkerNotice': '⚠️ L\'analyse s\'exécute sans les données de {biomarker} pour {drug}. Ajoutez vos résultats dans l\'onglet Santé pour un calcul plus précis.',
      'referral.recommendedTests': 'Tests recommandés',
      'referral.nextAction': 'Action suivante : consultez votre coffre des analyses ou utilisez un laboratoire partenaire avec réduction.',
      'referral.close': 'Fermer',
      'referral.nearbyLabsTitle': 'Laboratoires partenaires à proximité',
      'referral.noNearbyLabs': 'Aucun laboratoire trouvé à proximité.',
      'referral.failedNearbyLabs': 'Échec de récupération des laboratoires proches',
      'referral.unableNearbyLabs': 'Impossible de trouver des laboratoires partenaires',
      'history.title': 'Historique des analyses',
      'settings.title': 'Paramètres',
      'settings.subtitle': 'Personnalisez la langue et le thème de l\'application.',
      'settings.language': 'Langue',
      'settings.appearance': 'Apparence',
      'settings.darkEnabled': 'Mode sombre activé',
      'settings.lightEnabled': 'Mode clair activé',
      'settings.dark': 'Sombre',
      'settings.light': 'Clair',
      'settings.shareCode': 'Code de partage patient',
      'settings.shareCodeHint': 'Générez un code à 6 chiffres pour qu’un professionnel lie votre dossier.',
      'settings.generateShareCode': 'Générer le code',
      'common.export': 'Exporter'
    },
    ar: {
      'tab.analyze': 'تحليل',
      'tab.health': 'الصحة',
      'tab.history': 'السجل',
      'tab.settings': 'الإعدادات',
      'status.live': 'المحرك نشط',
      'status.warming': 'جاري التسخين',
      'header.join': 'تسجيل الدخول / برو',
      'header.subscription': 'الاشتراك',
      'header.proActive': 'برو مفعل',
      'header.mobileApp': 'تطبيق الجوال',
      'header.tagline': 'أنت ما تأكل',
      'install.title': 'ثبّت HealthOpt',
      'install.subtitle': 'احصل على تجربة الهاتف الكاملة على الشاشة الرئيسية.',
      'install.step1': 'اضغط زر المشاركة في المتصفح.',
      'install.step2': 'اختر "إضافة إلى الشاشة الرئيسية".',
      'common.gotIt': 'حسنًا',
      'auth.create': 'إنشاء حساب',
      'auth.signin': 'تسجيل الدخول',
      'auth.signup': 'إنشاء حساب',
      'auth.subtitle': 'سجّل الدخول أولًا ثم اختر خطة الاشتراك.',
      'common.cancel': 'إلغاء',
      'common.email': 'البريد الإلكتروني',
      'common.password': 'كلمة المرور',
      'common.proBadge': 'برو',
      'common.proSuffix': '(برو)',
      'common.wait': 'يرجى الانتظار...',
      'premium.title': 'افتح HealthOpt Pro',
      'premium.freeBlurb': 'مجاني: تحليل، تتبع يدوي، عدد محدود يوميًا',
      'premium.proBlurb': 'برو: استخراج PDF بالذكاء الاصطناعي، تقرير طبي موثق، مزامنة متقدمة',
      'premium.signinRequired': 'يجب تسجيل الدخول قبل تفعيل الخطة المدفوعة.',
      'premium.upgradeDefault': 'قم بالترقية إلى Pro لمزامنة الذكاء الاصطناعي وتقارير الاستهلاك الموثقة والأتمتة المتقدمة.',
      'premium.pdfExtractPrompt': 'دع الذكاء الاصطناعي يستخرج المؤشرات الحيوية تلقائيًا. قم بالترقية إلى Pro.',
      'premium.cycleSyncPrompt': 'مزامنة التفاعلات المعتمدة على الدورة ميزة Pro. قم بالترقية لتفعيل سياق صحة المرأة المتقدم.',
      'premium.keepFree': 'الاستمرار مجانًا',
      'premium.startPro': 'بدء برو',
      'premium.deactivatePro': 'إلغاء Pro',
      'analyze.smart': 'تحليل ذكي',
      'analyze.context': 'السياق الحالي',
      'analyze.currentCycle': 'المرحلة الحالية للدورة',
      'analyze.day': 'اليوم',
      'analyze.of28': 'من 28',
      'analyze.ofCycle': 'من {value}',
      'analyze.cypLine': 'نشاط CYP3A4 هو {value}. يتم ضبط مستويات التفاعل تلقائيًا.',
      'analyze.cypIncreased': 'معدّل',
      'analyze.cypBaseline': 'على المستوى الأساسي',
      'analyze.profileSynced': 'تمت مزامنة الملف',
      'analyze.unsavedMeds': 'أدوية غير محفوظة',
      'analyze.ironDeficiency': 'نقص الحديد',
      'analyze.vitdDeficiency': 'نقص فيتامين د',
      'analyze.zincDeficiency': 'نقص الزنك',
      'analyze.b12Deficiency': 'نقص فيتامين ب12',
      'analyze.folateDeficiency': 'نقص الفولات',
      'analyze.calciumDeficiency': 'نقص الكالسيوم',
      'analyze.magnesiumDeficiency': 'نقص المغنيسيوم',
      'analyze.iodineDeficiency': 'نقص اليود',
      'analyze.manualMedication': 'دواء مُدخل يدويًا للتحقق: {name}',
      'analyze.noProfile': 'لا توجد بيانات ملف شخصي. حدّث من تبويب الصحة.',
      'analyze.dailyScans': 'الفحوصات المجانية اليومية',
      'analyze.scansUsed': 'تم استخدام {used} من {limit}',
      'analyze.limitReached': 'لقد وصلت للحد المجاني اليوم. واصل الاستخدام وقم بالترقية لأدوات مزامنة/تصدير متقدمة غير محدودة.',
      'analyze.run': 'تشغيل التحليل الذكي',
      'analyze.inputFood': 'طعام أو مشروب',
      'analyze.inputFoodPh': 'مثال: بيتزا، عقير العنب، قهوة',
      'analyze.inputDrug': 'دواء إضافي',
      'analyze.inputDrugOpt': '(اختياري)',
      'analyze.inputDrugPh': 'مثال: إيبوبروفين',
      'health.profile': 'الملف الصحي',
      'health.gender': 'الجنس',
      'health.age': 'العمر',
      'health.ageHint': 'يُستخدم كسياق للملف من أجل تعديلات التفاعلات والحركية الدوائية.',
      'health.saveAge': 'حفظ العمر',
      'health.female': 'أنثى',
      'health.male': 'ذكر',
      'health.dailyMeds': 'الأدوية اليومية',
      'health.dailyMedsHint': 'سيتم التحقق منها تلقائيًا أثناء التحليل.',
      'health.saveMeds': 'حفظ الأدوية',
      'health.saving': 'جاري الحفظ...',
      'health.bloodVault': 'خزنة تحاليل الدم',
      'health.uploadHint': 'ارفع ملف PDF لاستخراج بالذكاء الاصطناعي',
      'health.uploadPdf': 'رفع PDF',
      'health.analyzing': 'جارٍ التحليل...',
      'health.updateProfile': 'تحديث الملف الصحي',
      'health.clearDeficiencies': 'مسح حالات النقص',
      'health.clearDeficienciesHint': 'تتم إزالة مدخلات النقص من سياق الخزنة.',
      'health.cycleTracker': 'متابعة الدورة',
      'health.saveCycle': 'حفظ بداية الدورة',
      'health.clearCycle': 'مسح بداية الدورة',
      'health.lastLogged': 'آخر تسجيل: {value}',
      'health.shareCodeGenerated': 'تم إنشاء رمز المشاركة: {code}',
      'notice.shareCodeFailed': 'فشل إنشاء رمز المشاركة.',
      'notice.never': 'أبدًا',
      'notice.pdfSaved': 'تم تحليل PDF وتحديث المؤشرات الحيوية.',
      'notice.pdfFailed': 'فشل تحليل PDF.',
      'notice.bloodSaved': 'تم حفظ نتائج الدم.',
      'notice.deficienciesCleared': 'تم مسح قيم النقص من سياق الخزنة.',
      'notice.selectDate': 'يرجى اختيار تاريخ البداية أولًا.',
      'notice.proActivated': 'تم تفعيل Pro.',
      'notice.freeSwitched': 'تم التحويل إلى الخطة المجانية.',
      'notice.signinFirst': 'يرجى تسجيل الدخول أولًا.',
      'notice.failedPlan': 'فشل تحديث الخطة.',
      'notice.savedAge': 'تم حفظ العمر.',
      'notice.failedAge': 'فشل حفظ العمر.',
      'notice.savedMeds': 'تم حفظ الأدوية اليومية.',
      'notice.deletedMed': 'تمت إزالة الدواء: {name}',
      'notice.failedMeds': 'فشل حفظ الأدوية اليومية.',
      'notice.authCreated': 'تم إنشاء الحساب.',
      'notice.authSignedIn': 'تم تسجيل الدخول بنجاح.',
      'notice.authFailed': 'فشل المصادقة.',
      'notice.predUnavailable': 'خدمة التنبؤ غير متاحة.',
      'notice.warmingSuffix': 'جاري تسخين المحركات...',
      'notice.physicianAvailablePro': 'تصدير التقرير الطبي متاح في Pro.',
      'notice.physicianExportOk': 'تم تصدير التقرير الطبي بنجاح.',
      'notice.physicianExportFail': 'فشل تصدير التقرير الطبي.',
      'notice.consumedLogged': 'تم تسجيل التفاعل كمستهلك.',
      'notice.consumedTheoretical': 'تم تعليم التفاعل كنظري.',
      'notice.consumedFailed': 'فشل تحديث حالة الاستهلاك.',
      'notice.exportFailed': 'فشل التصدير',
      'history.report': 'إنشاء تقرير للطبيب',
      'history.logConsumed': 'تسجيل كمستهلك',
      'history.loggedConsumed': 'تم تسجيل الاستهلاك',
      'history.none': 'لا يوجد سجل تحليلات',
      'history.exportTitle': 'تصدير التقرير الطبي',
      'history.exportPrompt': 'ماذا تريد أن يتضمن التقرير؟',
      'history.includeTheoretical': 'تضمين جميع التفاعلات التي تم البحث عنها (نظرية)',
      'history.includeConsumedOnly': 'تضمين التفاعلات المستهلكة الموثقة فقط (موصى به)',
      'history.includeBlood': 'تضمين اتجاهات تحاليل الدم',
      'results.noInteractionBadge': 'لم يتم اكتشاف تفاعل',
      'results.interactionBadge': 'تم اكتشاف تفاعل',
      'results.noInteractionTitle': 'لم يتم اكتشاف تفاعل',
      'results.context': 'سياق',
      'results.manualMedicationNotice': 'هذا التحذير مبني على الدواء الذي أدخلته يدويًا.',
      'results.risk': 'خطر',
      'results.confidence': 'الثقة',
      'results.physCertaintyTitle': 'مرتفع - يقين بوابة السلامة السريرية',
      'results.physCertaintyBody': 'تم اكتشاف هذا التفاعل بواسطة قواعد حتمية للسلامة، وليس بواسطة احتمال إحصائي. درجات الثقة لا تنطبق هنا.',
      'results.medication': 'الدواء',
      'results.food': 'الطعام',
      'results.whatHappening': 'ماذا يحدث؟',
      'results.whyMatters': 'لماذا هذا مهم لك:',
      'results.howFix': 'كيف تصلح ذلك:',
      'results.directExplanation': 'شرح مباشر',
      'results.whatToDo': 'ماذا تفعل',
      'results.compoundsIdentified': 'المركبات المكتشفة',
      'results.bioactiveCompounds': 'المركبات النشطة حيويًا:',
      'results.nutrients': 'العناصر الغذائية:',
      'results.fallbackDetected': 'تم اكتشاف تفاعل.',
      'results.showTechnical': 'إظهار تشخيصات الذكاء الاصطناعي التقنية',
      'results.hideTechnical': 'إخفاء تشخيصات الذكاء الاصطناعي التقنية',
      'results.layerScores': 'درجات الطبقات',
      'results.layer0': 'الطبقة 0 (بوابة السلامة السريرية)',
      'results.layer1': 'الطبقة 1 (الرسم البياني)',
      'results.layer2': 'الطبقة 2 (KGE)',
      'results.layer3': 'الطبقة 3 (LightGCN)',
      'results.layer4': 'الطبقة 4 (الدمج)',
      'results.normalized': 'مطبع',
      'results.raw': 'خام',
      'results.found': 'موجود',
      'results.notFound': 'غير موجود',
      'results.warnings': 'تحذيرات',
      'health.savedMeds': 'الأدوية المحفوظة',
      'health.noSavedMeds': 'لا توجد أدوية يومية محفوظة بعد.',
      'health.removeMed': 'إزالة الدواء',
      'health.delete': 'حذف',
      'results.fusionScore': 'درجة الدمج',
      'results.enzymePathways': 'مسارات الإنزيمات',
      'results.graph': 'الرسم البياني',
      'results.kge': 'KGE',
      'results.modelFlags': 'أعلام النموذج',
      'results.detailedMechanism': 'المسار الميكانيكي الإنزيمي',
      'results.errorDisplay': 'خطأ في عرض النتيجة',
      'results.emptyPrompt': 'أدخل طعامًا أو مشروبًا لتحليله مقابل سياق ملفك الشخصي',
      'health.medsPlaceholder': 'مثال: Sintrom, Metformin (مفصولة بفواصل)',
      'health.score': 'مؤشر الصحة',
      'health.scoreSubtitle': 'بناءً على أحدث المؤشرات الحيوية والتفاعلات.',
      'health.syncInteractions': 'المزامنة مع التفاعلات',
      'health.syncInteractionsHint': 'تعديلات تفاعلات مرتبطة بالدورة وتقييم سياقي متميز',
      'health.enabled': 'مفعّل',
      'health.periodStartDate': 'تاريخ بداية الدورة',
      'health.cycleDuration': 'طول الدورة (أيام)',
      'health.periodLength': 'مدة الحيض (أيام النزيف)',
      'health.day': 'اليوم',
      'health.logStart': 'سجل البداية',
      'health.cycleDisabledTitle': 'متابعة الدورة معطلة',
      'health.cycleDisabledBody': 'متابعة الدورة متاحة فقط لملفات الإناث.',
      'cycle.phase.menstrual': 'الحيض',
      'cycle.phase.follicular': 'الجريبية',
      'cycle.phase.ovulatory': 'الإباضة',
      'cycle.phase.luteal': 'الأصفرية',
      'referral.bannerTitle': 'يُنصح بإجراء تحليل مخبري',
      'referral.uploadResults': 'رفع النتائج',
      'referral.findPartnerLab': 'العثور على مختبر شريك',
      'referral.why': 'لماذا؟',
      'referral.remind7d': 'ذكرني بعد 7 أيام',
      'referral.dismiss': 'إخفاء',
      'referral.metricLastTest': 'آخر تحليل قبل {days} يومًا',
      'referral.metricFlags': '{count} إشارات خطورة حديثة',
      'referral.metricRecommended': 'الموصى به: {tests}',
      'referral.whyTitle': 'لماذا نوصي بهذا التحليل؟',
      'referral.urgencyRecommended': 'موصى به',
      'referral.urgencyUrgent': 'عاجل',
      'referral.reasonDefault': 'تشير المؤشرات الصحية الأخيرة إلى أن تحديث تحاليل الدم سيحسن الأمان.',
      'referral.reasonStaleWithDays': 'آخر ملف دم لديك عمره {days} يومًا وقد لا يعكس حالتك الحالية بدقة.',
      'referral.reasonStaleNoDays': 'يبدو أن ملف تحاليل الدم قديم ويجب تحديثه.',
      'referral.reasonFreqWithCount': 'رصدنا {count} أحداث حديثة لمخاطر التفاعل، لذلك يُنصح بتحديث التحاليل قبل المتابعة.',
      'referral.reasonFreqNoCount': 'رصدنا نمطًا متكررًا لمخاطر التفاعل، لذلك يُنصح بتحديث التحاليل.',
      'history.referralPattern': '📊 تم رصد نمط: {count} تداخلات مع {drug} هذا الشهر. يوصى بإجراء فحص مختبري. [عرض التفاصيل]',
      'analyze.missingBiomarkerNotice': '⚠️ التحليل يعمل بدون بيانات {biomarker} للدواء {drug}. أضف نتائج المختبر في تبويب الصحة للحصول على تقييم أدق.',
      'referral.recommendedTests': 'التحاليل الموصى بها',
      'referral.nextAction': 'الخطوة التالية: راجع خزنة التحاليل أو استخدم مختبرًا شريكًا للحصول على خصم.',
      'referral.close': 'إغلاق',
      'referral.nearbyLabsTitle': 'المختبرات الشريكة القريبة',
      'referral.noNearbyLabs': 'لم يتم العثور على مختبرات قريبة.',
      'referral.failedNearbyLabs': 'تعذر جلب المختبرات القريبة',
      'referral.unableNearbyLabs': 'تعذر العثور على مختبرات شريكة',
      'history.title': 'سجل التحليلات',
      'settings.title': 'إعدادات التطبيق',
      'settings.subtitle': 'خصص اللغة والمظهر لعملك اليومي.',
      'settings.language': 'اللغة',
      'settings.appearance': 'المظهر',
      'settings.darkEnabled': 'الوضع الداكن مفعل',
      'settings.lightEnabled': 'الوضع الفاتح مفعل',
      'settings.dark': 'داكن',
      'settings.light': 'فاتح',
      'settings.shareCode': 'رمز مشاركة المريض',
      'settings.shareCodeHint': 'أنشئ رمزًا من 6 أرقام ليربطه مختص بالملف الطبي.',
      'settings.generateShareCode': 'إنشاء رمز المشاركة',
      'common.export': 'تصدير'
    }
  };

  const tr = (key: string, vars?: Record<string, string | number>) => {
    const base = translations[language][key] || translations.en[key] || key;
    if (!vars) return base;
    return Object.entries(vars).reduce((txt, [k, v]) => txt.replaceAll(`{${k}}`, String(v)), base);
  };

  const deficiencyLabelBySignalKey: Record<string, string> = {
    label_ferritine: 'analyze.ironDeficiency',
    label_vitD: 'analyze.vitdDeficiency',
    label_vitd: 'analyze.vitdDeficiency',
    label_vitB12: 'analyze.b12Deficiency',
    label_zinc: 'analyze.zincDeficiency',
    label_b12: 'analyze.b12Deficiency',
    label_folate_serique: 'analyze.folateDeficiency',
    label_calcium: 'analyze.calciumDeficiency',
    label_magnesium: 'analyze.magnesiumDeficiency',
    label_iode_urinaire: 'analyze.iodineDeficiency',
  };

  const normalizeVirtualDeficiencies = (rows: any[]): any[] => {
    return (rows || [])
      .map((row: any) => ({
        signal_key: row.signal_key || row.key,
        public_label: row.public_label || row.publicLabel || '',
        severity: row.severity || 'LOW',
      }))
      .filter((row: any) => Boolean(row.signal_key || row.public_label));
  };

  const splitMedicationList = (value?: string): string[] =>
    String(value || '')
      .split(',')
      .map((m) => m.trim())
      .filter(Boolean);

  const normalizeBloodKey = (value: string) =>
    String(value || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

  const extractNumericValue = (value: unknown): number | null => {
    if (value === null || value === undefined || value === '') return null;
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;

    const text = String(value).replace(/\s+/g, '').replace(',', '.');
    const match = text.match(/[-+]?\d*\.?\d+/);
    if (!match) return null;

    const parsed = Number(match[0]);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const bloodKeyMatches = (candidate: string, alias: string) => {
    const a = normalizeBloodKey(candidate);
    const b = normalizeBloodKey(alias);
    return a === b || a.includes(b) || b.includes(a);
  };

  const collectBloodEntries = (raw: any): Record<string, any> => {
    const out: Record<string, any> = {};

    const mergeObject = (source: any) => {
      if (!source || typeof source !== 'object') return;
      for (const [key, value] of Object.entries(source)) {
        if (value === null || value === undefined || value === '') continue;

        const normalizedKey = normalizeBloodKey(key);
        if (['data', 'result', 'results', 'payload', 'fields', 'values', 'biomarkers', 'metrics'].includes(normalizedKey)) {
          if (typeof value === 'object') {
            mergeObject(value);
          } else if (typeof value === 'string') {
            const nested = collectBloodEntries(value);
            if (Object.keys(nested).length > 0) {
              Object.assign(out, nested);
            }
          }
          continue;
        }

        out[key] = value;
      }
    };

    if (typeof raw === 'string') {
      const text = raw.trim();
      if (!text) return out;

      try {
        return collectBloodEntries(JSON.parse(text));
      } catch {
        // Fall through to structured text parsing.
      }

      if ((text.includes('=') || text.includes('&')) && text.includes('?')) {
        try {
          const params = new URLSearchParams(text.slice(text.indexOf('?') + 1));
          params.forEach((value, key) => {
            out[key] = value;
          });
          if (Object.keys(out).length > 0) return out;
        } catch {
          // Fall through.
        }
      }

      for (const chunk of text.split(/[\r\n;|]+/g)) {
        const piece = chunk.trim();
        if (!piece) continue;
        const parts = piece.split(/[:=]/);
        if (parts.length < 2) continue;
        const key = parts.shift()?.trim();
        const value = parts.join(':').trim();
        if (key && value) out[key] = value;
      }

      return out;
    }

    if (Array.isArray(raw)) {
      for (const item of raw) {
        Object.assign(out, collectBloodEntries(item));
      }
      return out;
    }

    mergeObject(raw);
    return out;
  };

  const fetchData = async () => {
    try {
      const [bloodRes, cycleRes, historyRes, profileRes, backendRes, subscriptionRes, usageRes, authRes, virtualRes] = await Promise.all([
        fetch('/api/blood-tests/latest'),
        fetch('/api/cycle'),
        fetch('/api/history'),
        fetch('/api/profile'),
        fetch('/api/backend-status'),
        fetch('/api/subscription'),
        fetch('/api/usage'),
        fetch('/api/auth/status'),
        fetch('/api/virtual-medications/active')
      ]);
      setBloodData(await bloodRes.json());
      const nextCycleData = await cycleRes.json();
      setCycleData(nextCycleData);
      setHistory(await historyRes.json());
      const nextProfile = await profileRes.json();
      setProfile(nextProfile);
      setAgeDraft(nextProfile?.age ?? '');
      setMedicationsDraft(nextProfile?.daily_medications || '');
      if (backendRes.ok) {
        setBackendStatus(await backendRes.json());
      } else {
        setBackendStatus({ ready: false, loading: true, status: 'loading' });
      }
      if (subscriptionRes.ok) {
        const sub = await subscriptionRes.json();
        setSubscription({
          plan: sub?.plan === 'pro' ? 'pro' : 'free',
          isPremium: Boolean(sub?.isPremium),
        });
      }
      if (authRes.ok) {
        const authPayload = await authRes.json();
        setAuthState({
          authenticated: Boolean(authPayload?.authenticated),
          email: authPayload?.email || null,
        });
      }
      if (usageRes.ok) {
        const usagePayload = await usageRes.json();
        setUsage({
          scansToday: Number(usagePayload?.scansToday || 0),
          freeDailyLimit: Number(usagePayload?.freeDailyLimit || 3),
        });
      }
      if (virtualRes.ok) {
        const virtualPayload = await virtualRes.json();
        setActiveVirtualDeficiencies(normalizeVirtualDeficiencies(virtualPayload));
      }
      if (nextCycleData?.start_date) {
        setCycleStartDate(nextCycleData.start_date);
      }
      if (nextCycleData?.duration) {
        const parsedDuration = Number(nextCycleData.duration);
        if (Number.isFinite(parsedDuration) && parsedDuration > 0) {
          setCycleDurationDraft(Math.round(parsedDuration));
        }
      }
      if (nextCycleData?.period_length) {
        const parsedPeriodLength = Number(nextCycleData.period_length);
        if (Number.isFinite(parsedPeriodLength) && parsedPeriodLength > 0) {
          setPeriodLengthDraft(Math.round(parsedPeriodLength));
        }
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    }
    // After fetching core data, check referral triggers (try to include geolocation)
    try {
      checkReferrals();
    } catch (e) {
      // ignore
    }
  };

  const checkReferrals = async () => {
    try {
      const candidates = ['/api/referral_status', '/api/referral-status'];
      for (const endpoint of candidates) {
        const res = await fetch(endpoint);
        if (!res.ok) continue;
        const ctype = String(res.headers.get('content-type') || '').toLowerCase();
        if (!ctype.includes('application/json')) continue;
        const data = await res.json();
        if (Array.isArray(data?.actions)) {
          setReferralActions(data.actions);
          return;
        }
      }
    } catch (e) {
      console.error('Failed to check referrals', e);
    }
  };

  React.useEffect(() => {
    try {
      const v = localStorage.getItem('referralDismissUntil');
      if (v) setReferralDismissUntil(Number(v));
      const key = localStorage.getItem('referralDismissKey');
      if (key) setReferralDismissKey(key);
    } catch (e) {
      // ignore
    }
  }, []);

  const getReferralActionKey = (action: any) => String(action?.trigger_key || action?.trigger || '');

  const getVisibleReferralActions = () => {
    if (!Array.isArray(referralActions) || referralActions.length === 0) return [];
    if (!referralDismissUntil || Date.now() > referralDismissUntil) return referralActions;
    if (!referralDismissKey) return referralActions;
    return referralActions.filter((a: any) => getReferralActionKey(a) !== referralDismissKey);
  };

  const isReferralBannerVisible = () => {
    return getVisibleReferralActions().length > 0;
  };

  const handleFindLabFromBanner = async () => {
    try {
      let lat: number | undefined; let lon: number | undefined;
      if (navigator && navigator.geolocation) {
        const pos = await new Promise<GeolocationPosition | null>((resolve) => {
          const t = setTimeout(() => resolve(null), 4000);
          navigator.geolocation.getCurrentPosition(
            (p) => { clearTimeout(t); resolve(p); },
            () => { clearTimeout(t); resolve(null); },
            { maximumAge: 1000 * 60 * 60 }
          );
        });
        if (pos) { lat = pos.coords.latitude; lon = pos.coords.longitude; }
      }
      const q = lat && lon ? `?lat=${lat}&lon=${lon}` : '';
      const labsRes = await fetch(`/api/referrals/nearby${q}`);
      if (!labsRes.ok) { alert(tr('referral.failedNearbyLabs')); return; }
      const labs = await labsRes.json();
      setNearbyLabs(labs || []);
      setNearbyLabsOpen(true);
    } catch (e) {
      console.error(e);
      alert(tr('referral.unableNearbyLabs'));
    }
  };

  const handleRemindFromBanner = (days: number) => {
    const until = Date.now() + days * 24 * 60 * 60 * 1000;
    const actionKey = getReferralActionKey(getPrimaryReferralAction());
    try { localStorage.setItem('referralDismissUntil', String(until)); } catch (e) {}
    try { localStorage.setItem('referralDismissKey', actionKey); } catch (e) {}
    setReferralDismissUntil(until);
    setReferralDismissKey(actionKey);
  };

  const handleDismissFromBanner = () => {
    const until = Date.now() + 7 * 24 * 60 * 60 * 1000; // hide for 7 days
    const actionKey = getReferralActionKey(getPrimaryReferralAction());
    try { localStorage.setItem('referralDismissUntil', String(until)); } catch (e) {}
    try { localStorage.setItem('referralDismissKey', actionKey); } catch (e) {}
    setReferralDismissUntil(until);
    setReferralDismissKey(actionKey);
  };

  const getPrimaryReferralAction = () => {
    const visible = getVisibleReferralActions();
    return visible.length ? visible[0] : null;
  };

  const getReferralUrgencyLabel = () => {
    const action = getPrimaryReferralAction();
    if (!action) return tr('referral.urgencyRecommended');
    if (action.trigger === 'high_interaction_frequency') return tr('referral.urgencyUrgent');
    if (action.trigger === 'stale_biomarkers' && Number(action.ageDays || 0) >= 365) return tr('referral.urgencyUrgent');
    return tr('referral.urgencyRecommended');
  };

  const getReferralReasonText = () => {
    const action = getPrimaryReferralAction();
    if (!action) return tr('referral.reasonDefault');
    if (action.trigger === 'stale_biomarkers') {
      const ageDays = Number(action.ageDays || 0);
      return ageDays > 0
        ? tr('referral.reasonStaleWithDays', { days: ageDays })
        : tr('referral.reasonStaleNoDays');
    }
    if (action.trigger === 'high_interaction_frequency') {
      const count = Number(action.count || 0);
      return count > 0
        ? tr('referral.reasonFreqWithCount', { count })
        : tr('referral.reasonFreqNoCount');
    }
    return tr('referral.reasonDefault');
  };

  const handlePredict = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setAnalysisNotice(null);
    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ food, manualDrug, language })
      });
      if (!response.ok) {
        const errPayload = await response.json().catch(() => ({}));
        const detail = errPayload?.detail || tr('notice.predUnavailable');
        if (response.status === 503) {
          alert(detail + ' ' + tr('notice.warmingSuffix'));
          fetchData();
          return;
        }
        setResults([]);
        setAnalysisNotice({ type: 'error', text: detail });
        throw new Error(detail);
      }
      const data = await response.json();
      if (data?.usage) {
        setUsage({
          scansToday: Number(data.usage.scansToday || 0),
          freeDailyLimit: Number(data.usage.freeDailyLimit || 3),
        });
      }
      
      // Normalize response format (handle both snake_case and camelCase)
      let results = Array.isArray(data.results) ? data.results : [data];
      results = results.map((res: any) => ({
        ...res,
        // Handle both snake_case and camelCase
        physicochemical_warnings: res.physicochemical_warnings || res.physicochemicalWarnings || [],
        llm_compounds: res.llm_compounds || res.llmCompounds || null,
        graph_path: res.graph_path || [],
        kge_enzymes: res.kge_enzymes || [],
      }));

      if (!results.length) {
        setAnalysisNotice({
          type: 'info',
          text: 'No analysis could be produced. Add a medication in Additional Medication, or save medications/deficiencies in Health first.',
        });
      }
      
      setResults(results);
      if (Array.isArray(data?.model2?.activeSignals)) {
        setActiveVirtualDeficiencies(normalizeVirtualDeficiencies(data.model2.activeSignals));
      }
      fetchData();
    } catch (error) {
      console.error(error);
      if (!analysisNotice) {
        const msg = error instanceof Error ? error.message : 'Analysis failed. Please try again.';
        setAnalysisNotice({ type: 'error', text: msg });
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAnalyzingPdf(true);
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = (reader.result as string).split(',')[1];
      try {
        const res = await fetch('/api/analyze-pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pdfBase64: base64 })
        });
        const data = await res.json();
        const normalized = normalizeBloodPayload(data);
        if (Object.keys(normalized).length === 0) {
          setBloodVaultNotice({ type: 'error', text: 'No recognized blood fields were found in this PDF.' });
          return;
        }
        
        // Auto-fill and save
        await fetch('/api/blood-tests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(normalized)
        });
        setBloodData((prev: any) => ({ ...prev, ...normalized }));
        fetchData();
        setBloodVaultNotice({ type: 'success', text: tr('notice.pdfSaved') });
      } catch (err) {
        setBloodVaultNotice({ type: 'error', text: tr('notice.pdfFailed') });
      } finally {
        setAnalyzingPdf(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const normalizeBloodPayload = (raw: any) => {
    const src = collectBloodEntries(raw);
    const out: any = {};

    const assign = (targetKey: string, keys: string[]) => {
      for (const key of keys) {
        const v = Object.entries(src).find(([candidate]) => bloodKeyMatches(candidate, key))?.[1] ?? src[key];
        if (v === null || v === undefined || v === '') continue;
        const n = extractNumericValue(v);
        out[targetKey] = n === null ? v : n;
        return;
      }
    };

    assign('ferritin', ['ferritin', 'ferritine', 'ferritinemie', 'ferritinemie', 'serum ferritin']);
    assign('hemoglobin', ['hemoglobin', 'hemoglobine', 'hemoglobine', 'hgb']);
    assign('vitaminD', ['vitaminD', 'vit d', 'vit d3', 'vitd', 'vitamine d', '25 oh vitamin d', '25 hydroxy vitamin d', '25 hydroxyvitamine d']);
    assign('b12', ['b12', 'vitb12', 'vit b12', 'vitamine b12', 'vitamine b12 cobalamine']);
    assign('folate', ['folate', 'folate serique', 'folate serum', 'acide folique', 'vit b9', 'vitamin b9', 'folic acid']);
    assign('calcium', ['calcium', 'ca', 'calcemie']);
    assign('magnesium', ['magnesium', 'mg', 'magnesemie']);
    assign('zinc', ['zinc', 'zn']);
    assign('iode_urinaire', ['iode_urinaire', 'urinary iodine', 'iodine urine', 'iode urine']);
    assign('albumine', ['albumine', 'albumin']);
    assign('tsh', ['tsh', 'tsh 3eme generation', 'tsh 3e generation', 'tsh 3eme generation plus sensible que la tsh us', 'thyroid stimulating hormone']);
    assign('glycemie_jejun', ['glycemie_jejun', 'glycemie a jeun', 'fasting glucose', 'glucose a jeun']);
    assign('hba1c', ['hba1c', 'a1c', 'hba1c %', 'hemoglobine glycosylee']);
    assign('triglycerides', ['triglycerides', 'triglyceride']);
    assign('ldl', ['ldl', 'ldl cholesterol', 'cholesterol ldl']);
    assign('ratio_albumine_creatinine', ['ratio_albumine_creatinine', 'acr', 'albumin creatinine ratio']);

    return out;
  };

  const triggerQrUpload = () => {
    if (!subscription.isPremium) {
      requireLoginBeforePro(tr('premium.pdfExtractPrompt'));
      return;
    }
    qrInputRef.current?.click();
  };

  const handleQrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setScanningQr(true);
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const el = new Image();
        el.onload = () => resolve(el);
        el.onerror = reject;
        el.src = dataUrl;
      });

      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas context unavailable');

      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const qr = jsQR(imageData.data, imageData.width, imageData.height);

      if (!qr?.data) {
        setBloodVaultNotice({ type: 'error', text: 'No QR code detected in this image.' });
        return;
      }

      let normalized = normalizeBloodPayload(qr.data);
      if (Object.keys(normalized).length === 0) {
        const qrText = String(qr.data || '').trim();
        if (/^https?:\/\//i.test(qrText)) {
          const fallbackRes = await fetch('/api/analyze-blood-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: qrText })
          });

          if (!fallbackRes.ok) {
            const payload = await fallbackRes.json().catch(() => ({}));
            if (fallbackRes.status === 402) {
              requireLoginBeforePro(payload?.detail || tr('premium.pdfExtractPrompt'));
              return;
            }
            setBloodVaultNotice({ type: 'error', text: payload?.detail || 'QR detected, but no recognized blood test fields were found.' });
            return;
          }

          const fallbackData = await fallbackRes.json();
          normalized = normalizeBloodPayload(fallbackData);
        } else {
          const fallbackRes = await fetch('/api/analyze-blood-raw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rawText: qr.data })
          });

          if (!fallbackRes.ok) {
            const payload = await fallbackRes.json().catch(() => ({}));
            if (fallbackRes.status === 402) {
              requireLoginBeforePro(payload?.detail || tr('premium.pdfExtractPrompt'));
              return;
            }
            setBloodVaultNotice({ type: 'error', text: payload?.detail || 'QR detected, but no recognized blood test fields were found.' });
            return;
          }

          const fallbackData = await fallbackRes.json();
          normalized = normalizeBloodPayload(fallbackData);
        }
      }

      if (Object.keys(normalized).length === 0) {
        setBloodVaultNotice({ type: 'error', text: 'QR detected, but no recognized blood test fields were found.' });
        return;
      }

      await fetch('/api/blood-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(normalized)
      });

      setBloodData((prev: any) => ({ ...prev, ...normalized }));
      fetchData();
      setBloodVaultNotice({ type: 'success', text: 'Blood test QR decoded and saved to vault.' });
    } catch (err) {
      console.error(err);
      setBloodVaultNotice({ type: 'error', text: 'Failed to scan blood test QR.' });
    } finally {
      setScanningQr(false);
    }
  };

  const updateProfile = async (updates: any) => {
    const newProfile = { ...profile, ...updates };
    setProfile(newProfile);
    await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newProfile)
    });

    // Hide cycle state immediately when switching to male.
    if (newProfile.gender === 'male') {
      setCycleData({});
    }
  };

  const saveDailyMedications = async () => {
    setSavingMedications(true);
    setMedicationsSaveNotice(null);
    try {
      const newProfile = { ...profile, daily_medications: medicationsDraft };
      await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProfile)
      });
      setProfile(newProfile);
      await checkReferrals();
      setMedicationsSaveNotice({ type: 'success', text: tr('notice.savedMeds') });
    } catch (err) {
      console.error(err);
      setMedicationsSaveNotice({ type: 'error', text: tr('notice.failedMeds') });
    } finally {
      setSavingMedications(false);
    }
  };

  const removeSavedMedication = async (medicationName: string) => {
    const current = splitMedicationList(profile.daily_medications);
    const next = current.filter((m) => m.toLowerCase() !== medicationName.toLowerCase());
    const nextMedications = next.join(', ');

    setSavingMedications(true);
    setMedicationsSaveNotice(null);
    try {
      const newProfile = { ...profile, daily_medications: nextMedications };
      await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProfile)
      });
      setProfile(newProfile);
      setMedicationsDraft(nextMedications);
      await checkReferrals();
      setMedicationsSaveNotice({ type: 'success', text: tr('notice.deletedMed', { name: medicationName }) });
    } catch (err) {
      console.error(err);
      setMedicationsSaveNotice({ type: 'error', text: tr('notice.failedMeds') });
    } finally {
      setSavingMedications(false);
    }
  };

  const saveAge = async () => {
    setAgeSaveNotice(null);
    try {
      const newProfile = { ...profile, age: ageDraft === '' ? '' : Number(ageDraft) };
      await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProfile)
      });
      setProfile(newProfile);
      setAgeSaveNotice({ type: 'success', text: tr('notice.savedAge') });
    } catch (err) {
      console.error(err);
      setAgeSaveNotice({ type: 'error', text: tr('notice.failedAge') });
    }
  };

  const openPremiumPrompt = (message: string) => {
    setPremiumMessage(message);
    setShowPremiumModal(true);
  };

  const requireLoginBeforePro = (message: string) => {
    if (authState.authenticated) {
      openPremiumPrompt(message);
      return;
    }
    setShowPremiumModal(false);
    setAuthMode('signin');
    setPendingProAfterAuth(false);
    setAuthNotice({ type: 'error', text: tr('notice.signinFirst') });
    setShowAuthModal(true);
  };

  const setPlan = async (plan: 'free' | 'pro') => {
    try {
      const resp = await fetch('/api/subscription/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan })
      });
      if (!resp.ok) {
        if (resp.status === 401) {
          setShowPremiumModal(false);
          setShowAuthModal(true);
          setPendingProAfterAuth(plan === 'pro');
          setPlanNotice({ type: 'error', text: tr('notice.signinFirst') });
          return;
        }
        throw new Error('Failed to set plan');
      }
      setSubscription({ plan, isPremium: plan === 'pro' });
      setPlanNotice({ type: 'success', text: plan === 'pro' ? tr('notice.proActivated') : tr('notice.freeSwitched') });
      await fetchData();
      setShowPremiumModal(false);
    } catch (err) {
      console.error('Failed to update subscription plan', err);
      setPlanNotice({ type: 'error', text: tr('notice.failedPlan') });
    }
  };

  const submitAuth = async () => {
    setAuthLoading(true);
    setAuthNotice(null);
    try {
      const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/signin';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.detail || tr('notice.authFailed'));
      }

      setAuthState({ authenticated: true, email: payload?.email || authEmail });
      setAuthNotice({ type: 'success', text: authMode === 'signup' ? tr('notice.authCreated') : tr('notice.authSignedIn') });
      setShowAuthModal(false);
      if (pendingProAfterAuth) {
        setPendingProAfterAuth(false);
        await setPlan('pro');
      }
      await fetchData();
    } catch (err: any) {
      setAuthNotice({ type: 'error', text: err?.message || tr('notice.authFailed') });
    } finally {
      setAuthLoading(false);
    }
  };

  const beginProFlow = async () => {
    setShowPremiumModal(true);
    if (subscription.isPremium) return;
    await setPlan('pro');
  };

  const triggerPdfUpload = () => {
    if (!subscription.isPremium) {
      requireLoginBeforePro(tr('premium.pdfExtractPrompt'));
      return;
    }
    pdfInputRef.current?.click();
  };

  const openExportModal = () => {
    if (!subscription.isPremium) {
      requireLoginBeforePro(tr('notice.physicianAvailablePro'));
      return;
    }
    setShowExportModal(true);
  };

  const toggleConsumed = async (item: any) => {
    try {
      setSavingHistoryId(item.id);
      await fetch(`/api/history/${item.id}/consumed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consumed: !item.consumed })
      });
      setExportNotice({ type: 'success', text: !item.consumed ? tr('notice.consumedLogged') : tr('notice.consumedTheoretical') });
      await fetchData();
    } catch (err) {
      console.error('Failed to toggle consumed state', err);
      setExportNotice({ type: 'error', text: tr('notice.consumedFailed') });
    } finally {
      setSavingHistoryId(null);
    }
  };

  const exportDoctorReport = async () => {
    setExportNotice(null);
    try {
      const res = await fetch('/api/history/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          includeBloodTrends: exportIncludeBloodTrends,
        })
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        if (res.status === 402) {
          requireLoginBeforePro(payload?.detail || tr('notice.physicianAvailablePro'));
          return;
        }
        throw new Error(payload?.detail || tr('notice.exportFailed'));
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `physician-report-${stamp}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setShowExportModal(false);
      setExportNotice({ type: 'success', text: tr('notice.physicianExportOk') });
    } catch (err) {
      console.error(err);
      setExportNotice({ type: 'error', text: tr('notice.physicianExportFail') });
    }
  };

  const saveBloodTest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = normalizeBloodPayload(bloodDraft);
      const res = await fetch('/api/blood-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) {
        throw new Error('Failed to save blood test values');
      }
      await fetchData();
      setBloodDraft({});
      setBloodVaultNotice({ type: 'success', text: tr('notice.bloodSaved') });
      // Dismiss referral banners related to missing/stale biomarkers now that new blood data was saved
      try {
        const triggersToDismiss = ['missing_biomarker', 'stale_biomarkers_90_highrisk', 'stale_biomarkers_180', 'stale_biomarkers'];
        for (const trigger of triggersToDismiss) {
          try {
            await fetch('/api/referrals/dismiss', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ trigger_type: trigger, snooze_days: 365 })
            });
          } catch (e) {
            // ignore individual failures
          }
        }
        // Refresh referral checks to update UI
        try { await checkReferrals(); } catch (e) {}
      } catch (err) {
        // ignore
      }
    } catch (err) {
      console.error(err);
      setBloodVaultNotice({ type: 'error', text: tr('notice.exportFailed') });
    }
  };

  const clearDeficiencies = async () => {
    try {
      const res = await fetch('/api/blood-tests/clear', { method: 'POST' });
      if (!res.ok) {
        throw new Error('Failed to clear deficiencies');
      }
      setBloodData({});
      setBloodDraft({});
      setActiveVirtualDeficiencies([]);
      await fetchData();
      setBloodVaultNotice({ type: 'success', text: tr('notice.deficienciesCleared') });
    } catch (err) {
      console.error(err);
      setBloodVaultNotice({ type: 'error', text: tr('notice.exportFailed') });
    }
  };

  const logPeriod = async () => {
    if (!cycleStartDate) {
      alert(tr('notice.selectDate'));
      return;
    }

    await fetch('/api/cycle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_date: cycleStartDate,
        duration: Math.max(20, Math.min(40, Number(cycleDurationDraft) || 28)),
        period_length: Math.max(2, Math.min(10, Number(periodLengthDraft) || 5)),
      })
    });
    fetchData();
  };

  const clearCycleStart = async () => {
    await fetch('/api/cycle', { method: 'DELETE' });
    setCycleData({});
    setCycleDurationDraft(28);
    setPeriodLengthDraft(5);
  };

  const generateShareCode = async () => {
    setShareCodeLoading(true);
    setShareCodeNotice(null);
    try {
      const res = await fetch('/api/professional/share-code', { method: 'POST', credentials: 'include' });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.detail || tr('notice.shareCodeFailed'));
      }
      setShareCode(String(payload?.shareCode || ''));
      setShareCodeNotice({ type: 'success', text: tr('notice.shareCodeGenerated', { code: String(payload?.shareCode || '') }) });
    } catch (error: any) {
      setShareCodeNotice({ type: 'error', text: error?.message || tr('notice.shareCodeFailed') });
    } finally {
      setShareCodeLoading(false);
    }
  };

  // Flo-style Cycle Logic
  const getCyclePhase = () => {
    if (profile.gender !== 'female') return null;
    if (!cycleData.start_date) return null;
    if (!cycleData.duration || cycleData.duration <= 0) return null;

    const start = new Date(cycleData.start_date);
    const today = new Date();
    const diffDays = Math.floor((today.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) % cycleData.duration;
    
    if (diffDays <= 5) return { id: 'menstrual', labelKey: 'cycle.phase.menstrual', color: 'bg-rose-500', day: diffDays + 1 };
    if (diffDays <= 13) return { id: 'follicular', labelKey: 'cycle.phase.follicular', color: 'bg-emerald-500', day: diffDays + 1 };
    if (diffDays <= 15) return { id: 'ovulatory', labelKey: 'cycle.phase.ovulatory', color: 'bg-indigo-500', day: diffDays + 1 };
    return { id: 'luteal', labelKey: 'cycle.phase.luteal', color: 'bg-orange-500', day: diffDays + 1 };
  };

  const phase = getCyclePhase();

  return (
    <div className={`min-h-screen pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)] ${darkMode ? 'theme-dark bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      {/* Navigation Rail */}
      <nav className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-clinical-blue/90 backdrop-blur-xl px-8 py-4 rounded-full border border-white/10 shadow-2xl z-50 flex items-center gap-10 md:gap-12 touch-none">
        <button 
          onClick={() => setActiveTab('analyze')}
          className={`flex flex-col items-center gap-1 transition-all ${activeTab === 'analyze' ? 'text-white scale-110' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Activity size={20} />
          <span className="text-[10px] font-bold uppercase tracking-tighter">{tr('tab.analyze')}</span>
        </button>
        <button 
          onClick={() => setActiveTab('health')}
          className={`flex flex-col items-center gap-1 transition-all ${activeTab === 'health' ? 'text-white scale-110' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Droplets size={20} />
          <span className="text-[10px] font-bold uppercase tracking-tighter">{tr('tab.health')}</span>
        </button>
        <button 
          onClick={() => setActiveTab('history')}
          className={`flex flex-col items-center gap-1 transition-all ${activeTab === 'history' ? 'text-white scale-110' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <History size={20} />
          <span className="text-[10px] font-bold uppercase tracking-tighter">{tr('tab.history')}</span>
        </button>
        <button 
          onClick={() => setActiveTab('settings')}
          className={`flex flex-col items-center gap-1 transition-all ${activeTab === 'settings' ? 'text-white scale-110' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <SlidersHorizontal size={20} />
          <span className="text-[10px] font-bold uppercase tracking-tighter">{tr('tab.settings')}</span>
        </button>
      </nav>

      <header className="max-w-6xl mx-auto p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-white rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center overflow-hidden">
            <img 
              src="/logo.png" 
              alt="HealthOpt Logo" 
              className="w-full h-full object-contain"
              referrerPolicy="no-referrer"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
                (e.target as HTMLImageElement).parentElement!.innerHTML = '<div class="text-2xl font-black text-blue-600">HO</div>';
              }}
            />
          </div>
          <div>
            <h1 className={`text-4xl font-bold tracking-tight ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>HealthOpt</h1>
            <p className="text-slate-500 mt-1 font-medium italic">{tr('header.tagline')}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono bg-white px-4 py-2 rounded-full border border-slate-200 shadow-sm">
          <span className={`flex items-center gap-1 ${backendStatus.ready ? 'text-emerald-600' : 'text-amber-600'}`}>
            <div className={`w-2 h-2 rounded-full ${backendStatus.ready ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
            {backendStatus.ready ? tr('status.live') : tr('status.warming')}
          </span>
          <span className="text-slate-300">|</span>
          <button
            onClick={() => {
              setPremiumMessage(tr('auth.subtitle'));
              if (!authState.authenticated) {
                setShowAuthModal(true);
                return;
              }
              setShowPremiumModal(true);
            }}
            className="flex items-center gap-1.5 text-amber-600 hover:text-amber-700 font-bold transition-colors"
          >
            {authState.authenticated ? (subscription.isPremium ? tr('header.proActive') : tr('header.subscription')) : tr('header.join')}
          </button>
          <span className="text-slate-300">|</span>
          <button 
            onClick={() => setShowInstallGuide(true)}
            className="flex items-center gap-1.5 text-blue-600 hover:text-blue-700 font-bold transition-colors"
          >
            <Plus size={14} />
            {tr('header.mobileApp')}
          </button>
        </div>
      </header>

      {planNotice && (
        <div className={`max-w-6xl mx-auto px-6 md:px-8 -mt-2 mb-4 text-xs font-semibold ${planNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'}`}>
          {planNotice.text}
        </div>
      )}

      <AnimatePresence>
        {showInstallGuide && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-100 flex items-center justify-center p-6"
            onClick={() => setShowInstallGuide(false)}
          >
            <motion.div 
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="bg-white rounded-3xl p-8 max-w-sm w-full shadow-2xl"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex justify-center mb-6">
                <div className="w-20 h-20 bg-blue-50 rounded-2xl flex items-center justify-center">
                  <Activity size={40} className="text-blue-600" />
                </div>
              </div>
              <h3 className="text-2xl font-bold text-slate-900 text-center mb-2">{tr('install.title')}</h3>
              <p className="text-slate-500 text-center mb-8">{tr('install.subtitle')}</p>
              
              <div className="space-y-6">
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center shrink-0 font-bold text-slate-600">1</div>
                  <p className="text-slate-700 text-sm leading-relaxed">
                    {tr('install.step1')}
                  </p>
                </div>
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center shrink-0 font-bold text-slate-600">2</div>
                  <p className="text-slate-700 text-sm leading-relaxed">
                    {tr('install.step2')}
                  </p>
                </div>
              </div>

              <button 
                onClick={() => setShowInstallGuide(false)}
                className="w-full mt-10 bg-blue-600 text-white py-4 rounded-2xl font-bold shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all active:scale-95"
              >
                {tr('common.gotIt')}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showAuthModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-111 flex items-center justify-center p-6"
            onClick={() => setShowAuthModal(false)}
          >
            <motion.div
              initial={{ scale: 0.94, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.94, y: 16 }}
              className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-2xl font-black text-slate-900 mb-2">{authMode === 'signup' ? tr('auth.create') : tr('auth.signin')}</h3>
              <p className="text-slate-600 text-sm mb-6">{tr('auth.subtitle')}</p>

              <div className="flex bg-slate-100 rounded-xl p-1 mb-4">
                <button
                  type="button"
                  onClick={() => setAuthMode('signin')}
                  className={`flex-1 py-2 rounded-lg text-sm font-bold ${authMode === 'signin' ? 'bg-white text-clinical-blue' : 'text-slate-500'}`}
                >
                  {tr('auth.signin')}
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode('signup')}
                  className={`flex-1 py-2 rounded-lg text-sm font-bold ${authMode === 'signup' ? 'bg-white text-clinical-blue' : 'text-slate-500'}`}
                >
                  {tr('auth.signup')}
                </button>
              </div>

              <div className="space-y-3 mb-4">
                <input
                  type="email"
                  placeholder={tr('common.email')}
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-blue-500/20"
                />
                <input
                  type="password"
                  placeholder={tr('common.password')}
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>

              {authNotice && (
                <div className={`text-xs font-semibold mb-3 ${authNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {authNotice.text}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowAuthModal(false)}
                  className="flex-1 bg-slate-100 text-slate-700 font-bold py-3 rounded-xl"
                >
                  {tr('common.cancel')}
                </button>
                <button
                  type="button"
                  onClick={submitAuth}
                  disabled={authLoading || !authEmail || !authPassword}
                  className="flex-1 bg-clinical-blue text-white font-bold py-3 rounded-xl disabled:opacity-60"
                >
                  {authLoading ? tr('common.wait') : (authMode === 'signup' ? tr('auth.create') : tr('auth.signin'))}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showPremiumModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-110 flex items-center justify-center p-6"
            onClick={() => setShowPremiumModal(false)}
          >
            <motion.div
              initial={{ scale: 0.94, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.94, y: 16 }}
              className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-2xl font-black text-slate-900 mb-2">{tr('premium.title')}</h3>
              <p className="text-slate-600 text-sm mb-6">{premiumMessage || tr('premium.upgradeDefault')}</p>
              <div className="space-y-3 mb-6 text-sm text-slate-700">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">{tr('premium.freeBlurb')}</div>
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-100">{tr('premium.proBlurb')}</div>
              </div>
              {!authState.authenticated && (
                <div className="mb-4 text-xs font-semibold text-amber-700">{tr('premium.signinRequired')}</div>
              )}
              <div className="flex gap-3">
                {subscription.isPremium ? (
                  <button
                    onClick={() => setShowPremiumModal(false)}
                    className="flex-1 bg-slate-100 text-slate-700 font-bold py-3 rounded-xl"
                  >
                    {tr('common.cancel')}
                  </button>
                ) : (
                  <button
                    onClick={() => setPlan('free')}
                    className="flex-1 bg-slate-100 text-slate-700 font-bold py-3 rounded-xl"
                  >
                    {tr('premium.keepFree')}
                  </button>
                )}
                <button
                  onClick={subscription.isPremium ? () => setPlan('free') : beginProFlow}
                  className="flex-1 bg-clinical-blue text-white font-bold py-3 rounded-xl"
                >
                  {subscription.isPremium ? tr('premium.deactivatePro') : tr('premium.startPro')}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="max-w-6xl mx-auto p-6 md:p-8 pb-[calc(11rem+env(safe-area-inset-bottom))] md:pb-[calc(9rem+env(safe-area-inset-bottom))]">
        <AnimatePresence mode="wait">
          {activeTab === 'analyze' && (
            <motion.div 
              key="analyze"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              <div className="lg:col-span-5 space-y-6">
                {/* Flo-style Quick Status */}
                {profile.gender === 'female' && phase && (
                  <section className="glass-card p-6 bg-linear-to-br from-slate-900 to-slate-800 text-white border-none overflow-hidden relative">
                    <div className={`absolute -right-8 -top-8 w-32 h-32 rounded-full blur-3xl opacity-20 ${phase.color}`} />
                    <div className="relative z-10">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">{tr('analyze.currentCycle')}</h3>
                          <div className="text-2xl font-bold flex items-center gap-2">
                            {tr(phase.labelKey)}
                            <div className={`w-2 h-2 rounded-full ${phase.color}`} />
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-3xl font-bold">{tr('analyze.day')} {phase.day}</div>
                          <div className="text-[10px] text-slate-400 uppercase font-bold">
                            {tr('analyze.ofCycle', { value: cycleData.duration || 28 })}
                          </div>
                        </div>
                      </div>
                      <div className="mt-4 p-3 bg-white/5 rounded-xl border border-white/10 text-[11px] leading-relaxed text-slate-300">
                        <Info size={12} className="inline mr-1" />
                        {tr('analyze.cypLine', { value: phase.id === 'ovulatory' ? tr('analyze.cypIncreased') : tr('analyze.cypBaseline') })}
                      </div>
                    </div>
                  </section>
                )}

                  <section className="glass-card p-6">
                    <div className="flex items-center justify-between mb-6">
                      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <Activity size={16} />
                        {tr('analyze.smart')}
                      </h2>
                      <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-600 rounded-full text-[10px] font-bold">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        {medicationsDraft === (profile.daily_medications || '') ? tr('analyze.profileSynced') : tr('analyze.unsavedMeds')}
                      </div>
                    </div>

                    <div className="mb-6 p-4 bg-slate-50 rounded-2xl border border-slate-100">
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">{tr('analyze.context')}</h4>
                      <div className="flex flex-wrap gap-2">
                        {splitMedicationList(profile.daily_medications).map((m: string, i: number) => (
                          <span key={i} className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-700 flex items-center gap-1.5">
                            <Pill size={12} className="text-blue-500" />
                            {m}
                            <button
                              type="button"
                              onClick={() => removeSavedMedication(m)}
                              disabled={savingMedications}
                              className="ml-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-40"
                              title={tr('health.removeMed')}
                              aria-label={`${tr('health.removeMed')}: ${m}`}
                            >
                              <X size={12} />
                              <span className="text-[10px] font-bold">{tr('health.delete')}</span>
                            </button>
                          </span>
                        ))}
                        {activeVirtualDeficiencies.map((def: any, idx: number) => {
                          const signalKey = String(def.signal_key || '');
                          const labelKey = deficiencyLabelBySignalKey[signalKey];
                          const fallback = String(def.public_label || '').replace(/\s*Support\s*$/i, '').trim();
                          return (
                            <span key={`${signalKey || fallback}-${idx}`} className="px-3 py-1.5 bg-rose-50 border border-rose-100 rounded-lg text-xs font-medium text-rose-700 flex items-center gap-1.5">
                              <AlertCircle size={12} />
                              {labelKey ? tr(labelKey) : fallback}
                            </span>
                          );
                        })}
                        {!profile.daily_medications && !activeVirtualDeficiencies.length && (
                          <span className="text-xs text-slate-400 italic">{tr('analyze.noProfile')}</span>
                        )}
                      </div>
                    </div>

                    {!subscription.isPremium && (
                    <div className="mb-6 p-4 bg-white rounded-2xl border border-slate-200">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{tr('analyze.dailyScans')}</h4>
                        <span className="text-xs font-bold text-slate-600">
                          {tr('analyze.scansUsed', { used: usage.scansToday, limit: usage.freeDailyLimit })}
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full bg-linear-to-r from-blue-500 to-emerald-500 transition-all"
                          style={{ width: `${Math.min(100, (usage.scansToday / Math.max(usage.freeDailyLimit, 1)) * 100)}%` }}
                        />
                      </div>
                      {!subscription.isPremium && usage.scansToday >= usage.freeDailyLimit && (
                        <p className="text-[11px] text-amber-700 mt-2 font-semibold">
                          {tr('analyze.limitReached')}
                        </p>
                      )}
                    </div>
                    )}

                    <form onSubmit={handlePredict} className="space-y-6">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                          <Apple size={14} className="text-emerald-500" />
                          {tr('analyze.inputFood')}
                        </label>
                        <input
                          type="text"
                          value={food}
                          onChange={(e) => setFood(e.target.value)}
                          placeholder={tr('analyze.inputFoodPh')}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-emerald-500/20"
                          required
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                          <Plus size={14} className="text-slate-400" />
                          {tr('analyze.inputDrug')} <span className="text-[10px] text-slate-400 font-normal">{tr('analyze.inputDrugOpt')}</span>
                        </label>
                        <input
                          type="text"
                          value={manualDrug}
                          onChange={(e) => setManualDrug(e.target.value)}
                          placeholder={tr('analyze.inputDrugPh')}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-slate-500/10"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-clinical-blue text-white font-semibold py-4 rounded-xl hover:bg-slate-800 transition-all flex items-center justify-center gap-2"
                      >
                        {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : tr('analyze.run')}
                      </button>
                    </form>
                  </section>
                </div>

                <div className="lg:col-span-7">
                  {analysisNotice && (
                    <div className={`mb-4 rounded-2xl border px-4 py-3 text-sm font-medium ${analysisNotice.type === 'error' ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-blue-50 border-blue-200 text-blue-800'}`}>
                      {analysisNotice.text}
                    </div>
                  )}
                  {/* Missing biomarker notice in Analyze when relevant */}
                  {referralActions && referralActions.length > 0 && (() => {
                    const miss = referralActions.find(a => a.trigger === 'missing_biomarker');
                    if (miss) {
                      const biomarker = (Array.isArray(miss.missing) ? miss.missing[0] : (miss.missing || ''));
                      const drug = miss.drug || '';
                      return (
                        <div className="mb-4 rounded-2xl border px-4 py-3 text-sm font-medium bg-amber-50 border-amber-100 text-amber-900">
                          {tr('analyze.missingBiomarkerNotice', { biomarker: biomarker.toString(), drug: drug.toString() })}
                        </div>
                      );
                    }
                    return null;
                  })()}
                  <AnimatePresence mode="wait">
                    {results.length > 0 ? (
                      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-6">
                        {results.map((res, idx) => {
                          try {
                          // Safely access simple/technical views with fallbacks
                          const simpleView = res.simple_view || null;
                          const technicalView = res.technical_view || {
                            technical_flag: 'UNKNOWN',
                            raw_mechanism: res.mechanism || '',
                            fusion_score: res.score || res.fusion_score || 0,
                            layers: {
                              graph_enzymes: res.graph_enzymes || res.graph_path || [],
                              kge_enzymes: res.kge_enzymes || [],
                              lgn_score: res.lgn_score || 0,
                            },
                            flags: res.flags || [],
                            physicochemical_warnings: res.physicochemical_warnings || [],
                          };
                          const showTechnical = expandedResults.has(idx);
                          const friendlyNarrative = simpleView?.friendly_narrative && typeof simpleView.friendly_narrative === 'object'
                            ? simpleView.friendly_narrative
                            : null;
                          const hasFriendlyNarrative = Boolean(friendlyNarrative);
                          const toggleTechnical = () => {
                            const newExpanded = new Set(expandedResults);
                            if (newExpanded.has(idx)) {
                              newExpanded.delete(idx);
                            } else {
                              newExpanded.add(idx);
                            }
                            setExpandedResults(newExpanded);
                          };
                          
                          const tierColors = {
                            'HIGH': { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-500' },
                            'MEDIUM': { bg: 'bg-orange-50', border: 'border-orange-200', badge: 'bg-orange-500' },
                            'INFO': { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-500' },
                            'LOW': { bg: 'bg-yellow-50', border: 'border-yellow-200', badge: 'bg-yellow-500' },
                          };
                          
                          const colors = tierColors[res.tier || res.confidence] || { bg: 'bg-slate-50', border: 'border-slate-200', badge: 'bg-slate-400' };
                          const riskTier = String(res.tier || res.confidence || '').toUpperCase();
                          const isNoInteraction = riskTier === 'INSUFFICIENT' || riskTier === 'NONE' || riskTier === 'NO_INTERACTION';
                          const hasLayer0Physicochemical = Array.isArray(res.physicochemical_warnings) && res.physicochemical_warnings.length > 0;
                          
                          return (
                            <div key={idx} className={`p-6 rounded-3xl border-2 transition-all ${colors.bg} ${colors.border}`}>
                              {/* Header: Metaphor + Confidence Badge */}
                              <div className="flex justify-between items-start mb-6">
                                <div>
                                  <div className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-1">
                                    {isNoInteraction ? `✅ ${tr('results.noInteractionBadge')}` : `⚠️ ${tr('results.interactionBadge')}`}
                                  </div>
                                  <h3 className="text-3xl font-black text-slate-900">
                                    {isNoInteraction ? tr('results.noInteractionTitle') : (simpleView?.metaphor || res.drug + ' × ' + res.food)}
                                  </h3>
                                </div>
                                <div className="text-right">
                                  {hasLayer0Physicochemical ? (
                                    <div className="inline-block text-left p-3 rounded-xl border border-red-200 bg-red-50 text-red-900 max-w-65">
                                      <div className="text-[11px] font-bold uppercase tracking-widest">⚠️ {tr('results.physCertaintyTitle')}</div>
                                      <div className="text-[11px] mt-1 leading-relaxed">{tr('results.physCertaintyBody')}</div>
                                    </div>
                                  ) : (
                                    <>
                                      <span className={`inline-block text-[11px] font-bold uppercase tracking-widest px-3 py-1 rounded-full text-white ${colors.badge}`}>
                                        {res.tier || res.confidence} {res.type === 'NUTRIENT_FOOD' ? tr('results.context') : tr('results.risk')}
                                      </span>
                                      <div className="text-xs text-slate-500 mt-2">
                                        {tr('results.confidence')}: {(res.score || 0).toFixed(3)}
                                      </div>
                                    </>
                                  )}
                                </div>
                              </div>

                              {/* Drug & Food Names Section */}
                              <div className="mb-6 p-4 bg-white/80 rounded-2xl border border-white/60">
                                <div className="space-y-2">
                                  <div className="flex items-center gap-3">
                                    <Pill className="w-5 h-5 text-indigo-600" />
                                    <span className="text-sm font-bold text-slate-700">
                                      {(res.type === 'NUTRIENT_FOOD' ? tr('results.context') : tr('results.medication'))}: <span className="font-black text-slate-900">{res.drug_name || res.drug}</span>
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-3">
                                    <Apple className="w-5 h-5 text-green-600" />
                                    <span className="text-sm font-bold text-slate-700">
                                      {tr('results.food')}: <span className="font-black text-slate-900">{res.food_name || res.food}</span>
                                    </span>
                                  </div>
                                </div>
                              </div>

                              {res.medication_source === 'MANUAL' && (
                                <div className="mb-6 p-3 bg-indigo-50 rounded-2xl border border-indigo-100 text-xs text-indigo-800 font-semibold">
                                  {tr('results.manualMedicationNotice')}
                                </div>
                              )}

                              {/* LLM-Generated Friendly Narrative */}
                              {friendlyNarrative && (
                                <div className="mb-6 space-y-4 bg-linear-to-br from-blue-50 to-indigo-50 p-5 rounded-2xl border border-blue-100">
                                  {/* What is happening? */}
                                  {friendlyNarrative.what_is_happening && (
                                    <div>
                                      <h4 className="text-sm font-bold text-blue-900 mb-2">❓ {tr('results.whatHappening')}</h4>
                                      <p className="text-sm text-blue-800 leading-relaxed">
                                        {friendlyNarrative.what_is_happening}
                                      </p>
                                    </div>
                                  )}

                                  {/* Why it matters */}
                                  {friendlyNarrative.why_it_matters && (
                                    <div className="border-t border-blue-200 pt-3">
                                      <h4 className="text-sm font-bold text-blue-900 mb-2">💙 {tr('results.whyMatters')}</h4>
                                      <p className="text-sm text-blue-800 leading-relaxed">
                                        {friendlyNarrative.why_it_matters}
                                      </p>
                                    </div>
                                  )}

                                  {/* How to fix it */}
                                  {Array.isArray(friendlyNarrative.how_to_fix_it) && 
                                   friendlyNarrative.how_to_fix_it.length > 0 && (
                                    <div className="border-t border-green-200 pt-3 bg-green-50 p-3 rounded-xl">
                                      <h4 className="text-sm font-bold text-green-900 mb-2">✅ {tr('results.howFix')}</h4>
                                      <ul className="space-y-1">
                                        {friendlyNarrative.how_to_fix_it.map((tip, tipIdx) => (
                                          <li key={tipIdx} className="text-sm text-green-800">
                                            • {tip}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}

                                  {/* When to act */}
                                  {friendlyNarrative.when_to_act && (
                                    <div className="text-xs font-bold text-indigo-700 bg-indigo-100 px-3 py-2 rounded-lg">
                                      ⏰ {friendlyNarrative.when_to_act}
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Legacy simple explanation (shown only when no LLM narrative is available) */}
                              {simpleView && !hasFriendlyNarrative ? (
                                <div className="mb-6 space-y-4">
                                  {/* What it means */}
                                  <div className="p-4 bg-white/70 rounded-2xl border border-white/60">
                                    <div className="text-xs font-bold text-slate-500 uppercase mb-2">{tr('results.directExplanation')}</div>
                                    <p className="text-base font-medium text-slate-800 leading-relaxed">
                                      {simpleView.user_explanation || simpleView.explanation || res.mechanism?.substring(0, 200)}
                                    </p>
                                  </div>

                                  {/* What to do */}
                                  {simpleView.what_to_do && (
                                    <div className="p-4 bg-green-50 rounded-2xl border border-green-100">
                                      <div className="flex items-start gap-3">
                                        <div className="text-xl">🕒</div>
                                        <div>
                                          <div className="text-xs font-bold text-green-700 uppercase mb-1">{tr('results.whatToDo')}</div>
                                          <p className="text-sm text-green-800">
                                            {simpleView.what_to_do}
                                          </p>
                                        </div>
                                      </div>
                                    </div>
                                  )}

                                  {/* Identified Compounds */}
                                  {simpleView.compounds_identified && 
                                   (simpleView.compounds_identified.bioactive?.length > 0 || 
                                    simpleView.compounds_identified.nutritional?.length > 0) && (
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200">
                                      <div className="text-xs font-bold text-slate-600 uppercase mb-2">
                                        🔬 {tr('results.compoundsIdentified')}
                                      </div>
                                      <div className="space-y-2">
                                        {simpleView.compounds_identified.bioactive && simpleView.compounds_identified.bioactive.length > 0 && (
                                          <div>
                                            <div className="text-[11px] font-bold text-slate-500 mb-1">{tr('results.bioactiveCompounds')}</div>
                                            <div className="flex flex-wrap gap-2">
                                              {simpleView.compounds_identified.bioactive.map((comp, ci) => (
                                                <span key={ci} className="px-2.5 py-1 bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium">
                                                  {comp.name || comp}
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                        {simpleView.compounds_identified.nutritional && simpleView.compounds_identified.nutritional.length > 0 && (
                                          <div>
                                            <div className="text-[11px] font-bold text-slate-500 mb-1">{tr('results.nutrients')}</div>
                                            <div className="flex flex-wrap gap-2">
                                              {simpleView.compounds_identified.nutritional.map((comp, ci) => (
                                                <span key={ci} className="px-2.5 py-1 bg-amber-100 text-amber-700 rounded-lg text-xs font-medium">
                                                  {comp.name || comp}
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ) : !hasFriendlyNarrative ? (
                                /* Fallback: Traditional view if no simple_view */
                                <div className="mb-6 p-4 bg-white/60 rounded-2xl border border-white/40 text-sm text-slate-700 leading-relaxed">
                                  {res.mechanism || tr('results.fallbackDetected')}
                                </div>
                              ) : null}

                              {res.cycle_context_note && (
                                <div className="mb-6 p-4 bg-blue-50 rounded-2xl border border-blue-100 text-sm text-blue-900 leading-relaxed">
                                  <div className="text-[10px] font-bold uppercase tracking-widest text-blue-500 mb-2">{tr('results.context')}</div>
                                  {res.cycle_context_note}
                                </div>
                              )}

                              {/* Collapsible Technical Details */}
                              {technicalView && (
                                <div className="border-t border-white/40 pt-4">
                                  <button
                                    onClick={toggleTechnical}
                                    className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors"
                                  >
                                    <ChevronRight 
                                      size={16} 
                                      className={`transform transition-transform ${showTechnical ? 'rotate-90' : ''}`}
                                    />
                                    {showTechnical ? tr('results.hideTechnical') : tr('results.showTechnical')}
                                  </button>

                                  {showTechnical && (
                                    <motion.div
                                      initial={{ opacity: 0, height: 0 }}
                                      animate={{ opacity: 1, height: 'auto' }}
                                      exit={{ opacity: 0, height: 0 }}
                                      className="mt-4 pt-4 border-t border-white/40 space-y-3 text-xs"
                                    >
                                      {/* Layer Scores */}
                                      <div className="p-3 bg-white/50 rounded-lg">
                                        <div className="font-bold text-slate-700 mb-2">{tr('results.layerScores')}</div>
                                        <div className="space-y-1 text-slate-600">
                                          <div>
                                            <span className="font-medium">{tr('results.layer0')}</span>: {Array.isArray(technicalView.physicochemical_warnings) && technicalView.physicochemical_warnings.length > 0 ? tr('results.found') : tr('results.notFound')}
                                            {Array.isArray(technicalView.physicochemical_warnings) && (
                                              <span> ({technicalView.physicochemical_warnings.length} {tr('results.warnings')})</span>
                                            )}
                                          </div>
                                          {typeof res.norm_graph !== 'undefined' && (
                                            <div>
                                              <span className="font-medium">{tr('results.layer1')}</span>: {(res.norm_graph * 100).toFixed(1)}% ({tr('results.normalized')})
                                              {typeof res.graph_score !== 'undefined' && <span> | {Number(res.graph_score).toFixed(3)} ({tr('results.raw')})</span>}
                                              {typeof res.graph_found !== 'undefined' && <span> | {res.graph_found ? tr('results.found') : tr('results.notFound')}</span>}
                                            </div>
                                          )}
                                          {typeof res.norm_kge !== 'undefined' && (
                                            <div>
                                              <span className="font-medium">{tr('results.layer2')}</span>: {(res.norm_kge * 100).toFixed(1)}% ({tr('results.normalized')})
                                              {typeof res.kge_score !== 'undefined' && <span> | {Number(res.kge_score).toFixed(3)} ({tr('results.raw')})</span>}
                                              {typeof res.kge_found !== 'undefined' && <span> | {res.kge_found ? tr('results.found') : tr('results.notFound')}</span>}
                                            </div>
                                          )}
                                          {typeof res.norm_lgn !== 'undefined' && (
                                            <div>
                                              <span className="font-medium">{tr('results.layer3')}</span>: {(res.norm_lgn * 100).toFixed(1)}% ({tr('results.normalized')})
                                              {typeof res.lgn_score !== 'undefined' && <span> | {Number(res.lgn_score).toFixed(3)} ({tr('results.raw')})</span>}
                                            </div>
                                          )}
                                          <div className="mt-2 pt-2 border-t border-white/40 font-bold">
                                            {tr('results.layer4')}: {(res.fusion_score || res.score || 0).toFixed(4)}
                                          </div>
                                        </div>
                                      </div>

                                      {/* Enzymes Found */}
                                      {((Array.isArray(technicalView.layers?.graph_enzymes) && technicalView.layers.graph_enzymes.length > 0) || 
                                        (Array.isArray(technicalView.layers?.kge_enzymes) && technicalView.layers.kge_enzymes.length > 0)) && (
                                        <div className="p-3 bg-white/50 rounded-lg">
                                          <div className="font-bold text-slate-700 mb-2">{tr('results.enzymePathways')}</div>
                                          <div className="space-y-1 text-slate-600 text-xs">
                                            {Array.isArray(technicalView.layers?.graph_enzymes) && technicalView.layers.graph_enzymes.length > 0 && (
                                              <div>
                                                <span className="font-medium">{tr('results.graph')}:</span> {technicalView.layers.graph_enzymes.join(', ')}
                                              </div>
                                            )}
                                            {Array.isArray(technicalView.layers?.kge_enzymes) && technicalView.layers.kge_enzymes.length > 0 && (
                                              <div>
                                                <span className="font-medium">{tr('results.kge')}:</span> {technicalView.layers.kge_enzymes.join(', ')}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      )}

                                      {/* Flags */}
                                      {technicalView.flags && technicalView.flags.length > 0 && (
                                        <div className="p-3 bg-white/50 rounded-lg">
                                          <div className="font-bold text-slate-700 mb-2">{tr('results.modelFlags')}</div>
                                          <div className="flex flex-wrap gap-1">
                                            {technicalView.flags.map((flag, fi) => (
                                              <span key={fi} className="px-2 py-1 bg-slate-200 text-slate-700 rounded text-[10px] font-mono">
                                                {flag}
                                              </span>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      {/* Raw Mechanism */}
                                      {technicalView.raw_mechanism && (
                                        <div className="p-3 bg-white/50 rounded-lg">
                                          <div className="font-bold text-slate-700 mb-2">{tr('results.detailedMechanism')}</div>
                                          <p className="text-slate-600 leading-relaxed font-mono text-[10px]">
                                            {technicalView.raw_mechanism}
                                          </p>
                                        </div>
                                      )}
                                    </motion.div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                          } catch (e) {
                            console.error('Error rendering result:', e, res);
                            return (
                              <div key={idx} className="p-6 rounded-3xl border-2 bg-red-50 border-red-200">
                                <p className="text-red-700 font-bold">{tr('results.errorDisplay')}</p>
                                <p className="text-red-600 text-sm mt-2">{String(e)}</p>
                                <pre className="text-xs text-red-600 mt-2 bg-white p-2 rounded overflow-auto max-h-32">
                                  {JSON.stringify(res, null, 2)}
                                </pre>
                              </div>
                            );
                          }
                        })}
                      </motion.div>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-center p-12 border-2 border-dashed border-slate-200 rounded-3xl text-slate-400">
                        <Activity size={48} className="mb-4 opacity-20" />
                        <p className="max-w-50">{tr('results.emptyPrompt')}</p>
                      </div>
                    )}
                  </AnimatePresence>
                </div>
            </motion.div>
          )}

          {activeTab === 'health' && (
            <motion.div 
              key="health"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              {/* Profile & Medications */}
              <div className="lg:col-span-12">
                <section className="glass-card p-8 mb-8">
                  <div className="flex flex-col md:flex-row justify-between gap-8">
                    <div className="flex-1 space-y-6">
                      <h2 className={`text-2xl font-bold ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>{tr('health.profile')}</h2>
                      <div className="flex items-center gap-4">
                        <label className="text-sm font-bold text-slate-500 uppercase">{tr('health.gender')}</label>
                        <div className="flex bg-slate-100 p-1 rounded-xl">
                          <button 
                            type="button"
                            onClick={() => updateProfile({ gender: 'female' })}
                            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${profile.gender === 'female' ? 'bg-white text-clinical-blue shadow-sm' : 'text-slate-400'}`}
                          >
                            {tr('health.female')}
                          </button>
                          <button 
                            type="button"
                            onClick={() => updateProfile({ gender: 'male' })}
                            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${profile.gender === 'male' ? 'bg-white text-clinical-blue shadow-sm' : 'text-slate-400'}`}
                          >
                            {tr('health.male')}
                          </button>
                        </div>
                      </div>
                      <div className="space-y-2 max-w-sm">
                        <label className="text-sm font-bold text-slate-500 uppercase flex items-center gap-2">
                          <Calendar size={16} />
                          {tr('health.age')}
                        </label>
                        <input
                          type="number"
                          min="0"
                          max="120"
                          value={ageDraft}
                          onChange={(e) => setAgeDraft(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-4 outline-none focus:ring-2 focus:ring-blue-500/20"
                          placeholder="35"
                        />
                        <p className="text-[10px] text-slate-400 italic">{tr('health.ageHint')}</p>
                        <button
                          type="button"
                          onClick={saveAge}
                          disabled={ageDraft === String(profile.age ?? '')}
                          className="mt-2 inline-flex items-center gap-2 bg-clinical-blue text-white text-sm font-bold px-4 py-2 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 transition-all"
                        >
                          <Save size={14} />
                          {tr('health.saveAge')}
                        </button>
                        {ageSaveNotice && (
                          <div className={`mt-2 text-xs font-semibold ${ageSaveNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'}`}>
                            {ageSaveNotice.text}
                          </div>
                        )}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-bold text-slate-500 uppercase flex items-center gap-2">
                          <Pill size={16} />
                          {tr('health.dailyMeds')}
                        </label>
                        <input 
                          type="text"
                          placeholder={tr('health.medsPlaceholder')}
                          value={medicationsDraft}
                          onChange={(e) => setMedicationsDraft(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-4 outline-none focus:ring-2 focus:ring-blue-500/20"
                        />
                        <p className="text-[10px] text-slate-400 italic">{tr('health.dailyMedsHint')}</p>
                        <button
                          type="button"
                          onClick={saveDailyMedications}
                          disabled={savingMedications || medicationsDraft === (profile.daily_medications || '')}
                          className="mt-3 inline-flex items-center gap-2 bg-clinical-blue text-white text-sm font-bold px-4 py-2 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 transition-all"
                        >
                          <Save size={14} />
                          {savingMedications ? tr('health.saving') : tr('health.saveMeds')}
                        </button>
                        {medicationsSaveNotice && (
                          <div
                            className={`mt-2 text-xs font-semibold ${
                              medicationsSaveNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'
                            }`}
                          >
                            {medicationsSaveNotice.text}
                          </div>
                        )}
                        <div className="mt-4">
                          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">{tr('health.savedMeds')}</div>
                          <div className="flex flex-wrap gap-2">
                            {splitMedicationList(profile.daily_medications).length > 0 ? (
                              splitMedicationList(profile.daily_medications).map((m: string, i: number) => (
                                <span key={`${m}-${i}`} className="inline-flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700">
                                  <Pill size={12} className="text-blue-500" />
                                  {m}
                                  <button
                                    type="button"
                                    onClick={() => removeSavedMedication(m)}
                                    disabled={savingMedications}
                                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-40"
                                    title={tr('health.removeMed')}
                                    aria-label={`${tr('health.removeMed')}: ${m}`}
                                  >
                                    <X size={12} />
                                    <span className="text-[10px] font-bold">{tr('health.delete')}</span>
                                  </button>
                                </span>
                              ))
                            ) : (
                              <span className="text-xs text-slate-400 italic">{tr('health.noSavedMeds')}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="md:w-64 flex flex-col items-center justify-center p-6 bg-blue-50 rounded-2xl border border-blue-100 text-center">
                      <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center text-blue-500 mb-3">
                        <Activity size={32} />
                      </div>
                      <h4 className="font-bold text-blue-900">{tr('health.score')}</h4>
                      <p className="text-xs text-blue-700 mt-1">{tr('health.scoreSubtitle')}</p>
                    </div>
                  </div>
                </section>
              </div>

              {/* Blood Test Vault */}
              <div className="lg:col-span-7 space-y-6">
                {/* Referral Banner (compact) */}
                {isReferralBannerVisible() && (
                  <section className={`glass-card p-4 mb-4 border ${darkMode ? 'border-amber-700/50 bg-amber-900/25' : 'border-yellow-100 bg-yellow-50'} flex flex-col gap-3 sm:gap-4 lg:flex-row lg:items-center lg:justify-between`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold shrink-0 ${darkMode ? 'bg-amber-400/20 text-amber-200' : 'bg-amber-100 text-amber-700'}`}>⚕️</div>
                        <div className="min-w-0">
                          <div className={`text-sm font-bold ${darkMode ? 'text-amber-100' : 'text-amber-900'}`}>{tr('referral.bannerTitle')}</div>
                          <div className={`text-xs break-words ${darkMode ? 'text-slate-200' : 'text-slate-600'}`}>
                            {getPrimaryReferralAction()?.ageDays ? `${tr('referral.metricLastTest', { days: getPrimaryReferralAction().ageDays })} • ` : ''}
                            {getPrimaryReferralAction()?.count ? `${tr('referral.metricFlags', { count: getPrimaryReferralAction().count })} • ` : ''}
                            {getPrimaryReferralAction()?.recommended_tests ? tr('referral.metricRecommended', { tests: getPrimaryReferralAction().recommended_tests }) : ''}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="w-full lg:w-auto grid grid-cols-1 sm:grid-cols-2 lg:flex lg:flex-wrap items-stretch gap-2 lg:ml-4">
                      <button onClick={handleFindLabFromBanner} className={`px-3 py-2 rounded-xl text-sm font-bold ${darkMode ? 'bg-amber-300/25 text-amber-100 hover:bg-amber-300/35' : 'bg-amber-100 text-amber-800 hover:bg-amber-200'} transition-colors`}>{tr('referral.findPartnerLab')}</button>
                      <button onClick={() => setShowReferralWhyModal(true)} className={`px-3 py-2 rounded-xl text-sm font-bold border ${darkMode ? 'bg-slate-900/40 text-amber-100 border-amber-300/40 hover:bg-slate-900/70' : 'bg-white text-amber-800 border-amber-200 hover:bg-amber-50'} transition-colors`}>{tr('referral.why')}</button>
                      <button onClick={() => handleRemindFromBanner(7)} className={`px-3 py-2 rounded-xl text-xs font-semibold underline ${darkMode ? 'text-slate-200 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}>{tr('referral.remind7d')}</button>
                      <button onClick={handleDismissFromBanner} className={`px-3 py-2 rounded-xl text-xs font-semibold underline ${darkMode ? 'text-slate-200 hover:text-white' : 'text-slate-600 hover:text-slate-900'}`}>{tr('referral.dismiss')}</button>
                    </div>
                  </section>
                )}
                <section className="glass-card p-8">
                  <div className="flex justify-between items-center mb-8">
                    <div>
                      <h2 className={`text-2xl font-bold ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>{tr('health.bloodVault')}</h2>
                      <p className="text-slate-500 text-sm">{tr('health.uploadHint')}</p>
                    </div>
                    <div className="relative">
                      <input 
                        ref={pdfInputRef}
                        type="file" 
                        accept="application/pdf" 
                        onChange={handlePdfUpload}
                        className="hidden" 
                        id="pdf-upload"
                        disabled={analyzingPdf}
                      />
                      <input
                        ref={qrInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleQrUpload}
                        className="hidden"
                        disabled={scanningQr}
                      />
                      <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={triggerPdfUpload}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${analyzingPdf ? 'bg-slate-100 text-slate-400' : 'bg-blue-500 text-white hover:bg-blue-600 shadow-lg shadow-blue-200'}`}
                      >
                        {analyzingPdf ? (
                          <div className="w-4 h-4 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
                        ) : <Plus size={16} />}
                        {analyzingPdf ? tr('health.analyzing') : tr('health.uploadPdf')}
                        <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-white/20 border border-white/30">AI</span>
                        {!subscription.isPremium && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] bg-amber-200 text-amber-800">{tr('common.proBadge')}</span>
                        )}
                      </button>
                        <button
                          type="button"
                          onClick={triggerQrUpload}
                          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${scanningQr ? 'bg-slate-100 text-slate-400' : 'bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-200'}`}
                        >
                          {scanningQr ? (
                            <div className="w-4 h-4 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
                          ) : <TestTube size={16} />}
                          {scanningQr ? 'Scanning QR...' : 'Scan Blood QR'}
                        </button>
                      </div>
                    </div>
                  </div>

                  {bloodVaultNotice && (
                    <div
                      className={`mb-6 text-sm font-semibold px-4 py-3 rounded-xl border ${bloodVaultNotice.type === 'success' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-rose-700 bg-rose-50 border-rose-200'}`}
                    >
                      {bloodVaultNotice.text}
                    </div>
                  )}

                  <form onSubmit={saveBloodTest} className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {[
                      { id: 'ferritin', label: 'Ferritin (µg/L)', icon: 'Fe' },
                      { id: 'hemoglobin', label: 'Hemoglobin (g/dL)', icon: 'Hb' },
                      { id: 'vitaminD', label: 'Vitamin D (ng/mL)', icon: 'D' },
                      { id: 'b12', label: 'Vitamin B12 (pg/mL)', icon: 'B12' },
                      { id: 'folate', label: 'Folate Serique', icon: 'FOL' },
                      { id: 'calcium', label: 'Calcium (mg/dL)', icon: 'Ca' },
                      { id: 'iode_urinaire', label: 'Iode Urinaire', icon: 'I' },
                      { id: 'albumine', label: 'Albumine', icon: 'ALB' },
                      { id: 'tsh', label: 'TSH', icon: 'TSH' },
                      { id: 'glycemie_jejun', label: 'Glycemie Jejun', icon: 'GLU' },
                      { id: 'hba1c', label: 'HbA1c', icon: 'A1C' },
                      { id: 'triglycerides', label: 'Triglycerides', icon: 'TG' },
                      { id: 'ldl', label: 'LDL', icon: 'LDL' },
                      { id: 'ratio_albumine_creatinine', label: 'Ratio Albumine Creatinine', icon: 'ACR' },
                      { id: 'magnesium', label: 'Magnesium (mg/dL)', icon: 'Mg' },
                      { id: 'zinc', label: 'Zinc', icon: 'Zn' },
                    ].map(field => (
                      <div key={field.id} className="space-y-1.5">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">{field.label}</label>
                        <div className="relative">
                          <input 
                            name={field.id}
                            type="number" 
                            step="0.1"
                            value={bloodDraft[field.id] ?? ''}
                            onChange={(evt) => setBloodDraft((prev: any) => ({ ...prev, [field.id]: evt.target.value }))}
                            className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 pl-12 outline-none focus:ring-2 focus:ring-blue-500/20"
                          />
                          <span className="absolute left-4 top-3.5 text-[10px] font-bold text-blue-500/50">{field.icon}</span>
                        </div>
                      </div>
                    ))}
                    <div className="md:col-span-2 pt-4">
                      <button type="submit" className="w-full bg-clinical-blue text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 hover:bg-slate-800 transition-all mb-2">
                        <Save size={18} />
                        {tr('health.updateProfile')}
                      </button>
                      <button type="button" onClick={clearDeficiencies} className="w-full bg-white text-rose-600 border border-rose-200 font-bold py-3 rounded-xl hover:bg-rose-50 transition-all">
                        {tr('health.clearDeficiencies')}
                      </button>
                      <p className="mt-2 text-center text-xs text-rose-700/80">
                        {tr('health.clearDeficienciesHint')}
                      </p>
                    </div>
                  </form>
                </section>
              </div>

              {/* Flo-style Cycle Tracker */}
              <div className="lg:col-span-5 space-y-6">
                {profile.gender === 'female' ? (
                  <section className="glass-card p-8 bg-rose-50 border-rose-100">
                    <div className="flex justify-between items-center mb-6">
                      <h2 className="text-xl font-bold text-rose-900">{tr('health.cycleTracker')}</h2>
                      <Droplets className="text-rose-500" size={24} />
                    </div>

                    <div className="mb-4 p-3 rounded-xl border border-rose-200 bg-white/70 flex items-center justify-between">
                      <div>
                        <div className="text-xs font-bold text-rose-800 uppercase tracking-wider">{tr('health.syncInteractions')}</div>
                        <div className="text-[11px] text-rose-700">{tr('health.syncInteractionsHint')}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (!subscription.isPremium) {
                            requireLoginBeforePro(tr('premium.cycleSyncPrompt'));
                          }
                        }}
                        className={`px-3 py-1.5 rounded-full text-xs font-bold ${subscription.isPremium ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}
                      >
                        {subscription.isPremium ? tr('health.enabled') : tr('common.proBadge')}
                      </button>
                    </div>
                    
                    <div className="aspect-square rounded-full border-8 border-white bg-white shadow-xl flex flex-col items-center justify-center relative overflow-hidden">
                      <div className={`absolute inset-0 opacity-10 ${phase?.color || 'bg-slate-200'}`} />
                      <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">{tr('health.day')}</span>
                      <span className="text-6xl font-black text-slate-900">{phase?.day || '--'}</span>
                      <span className="text-rose-500 font-bold mt-2">{phase?.labelKey ? tr(phase.labelKey) : tr('health.logStart')}</span>
                    </div>

                    <div className="mt-8 space-y-4">
                      <div>
                        <label className="text-xs font-bold text-rose-500 uppercase tracking-wider mb-2 block">
                          {tr('health.periodStartDate')}
                        </label>
                        <input
                          type="date"
                          value={cycleStartDate}
                          onChange={(e) => setCycleStartDate(e.target.value)}
                          className="w-full bg-white border border-rose-200 rounded-xl p-3 outline-none focus:ring-2 focus:ring-rose-500/20"
                        />
                      </div>

                      <div>
                        <label className="text-xs font-bold text-rose-500 uppercase tracking-wider mb-2 block">
                          {tr('health.cycleDuration')}
                        </label>
                        <input
                          type="number"
                          min={20}
                          max={40}
                          value={cycleDurationDraft}
                          onChange={(e) => setCycleDurationDraft(Math.max(20, Math.min(40, Number(e.target.value) || 28)))}
                          className="w-full bg-white border border-rose-200 rounded-xl p-3 outline-none focus:ring-2 focus:ring-rose-500/20"
                        />
                      </div>

                      <div>
                        <label className="text-xs font-bold text-rose-500 uppercase tracking-wider mb-2 block">
                          {tr('health.periodLength')}
                        </label>
                        <input
                          type="number"
                          min={2}
                          max={10}
                          value={periodLengthDraft}
                          onChange={(e) => setPeriodLengthDraft(Math.max(2, Math.min(10, Number(e.target.value) || 5)))}
                          className="w-full bg-white border border-rose-200 rounded-xl p-3 outline-none focus:ring-2 focus:ring-rose-500/20"
                        />
                      </div>

                      <button 
                        onClick={logPeriod}
                        className="w-full bg-rose-500 text-white font-bold py-4 rounded-2xl shadow-lg shadow-rose-200 flex items-center justify-center gap-2 hover:bg-rose-600 transition-all"
                      >
                        <Plus size={18} />
                        {tr('health.saveCycle')}
                      </button>

                      <button
                        onClick={clearCycleStart}
                        className="w-full bg-white text-rose-600 border border-rose-200 font-bold py-3 rounded-2xl hover:bg-rose-50 transition-all"
                      >
                        {tr('health.clearCycle')}
                      </button>

                      <p className="text-center text-[10px] text-rose-400 font-medium uppercase tracking-widest">
                        {tr('health.lastLogged', { value: cycleData.start_date || tr('health.never') })}
                      </p>
                    </div>
                  </section>
                ) : (
                  <section className="glass-card p-8 bg-slate-100 border-slate-200 flex flex-col items-center justify-center text-center opacity-60">
                    <Calendar className="text-slate-400 mb-4" size={48} />
                    <h3 className="font-bold text-slate-600">{tr('health.cycleDisabledTitle')}</h3>
                    <p className="text-xs text-slate-500 mt-2">{tr('health.cycleDisabledBody')}</p>
                  </section>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'history' && (
            <motion.div 
              key="history"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-3xl mx-auto space-y-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className={`text-2xl font-bold ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>{tr('history.title')}</h2>
                <button
                  type="button"
                  onClick={openExportModal}
                  className="text-xs font-bold text-blue-500 hover:underline"
                >
                  {tr('history.report')} {subscription.isPremium ? '' : tr('common.proSuffix')}
                </button>
              </div>

              {exportNotice && (
                <div className={`text-xs font-semibold ${exportNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {exportNotice.text}
                </div>
              )}

              <div className="space-y-4">
                {/* Inline referral banner for frequent-drug patterns */}
                {referralActions && referralActions.length > 0 && (() => {
                  const freq = referralActions.find(a => a.trigger === 'high_interaction_frequency' || a.trigger === 'freq_high_tier' || a.trigger === 'freq_iron');
                  if (freq) {
                    const drugName = freq.drug || ''; const count = freq.count || freq.value || 0;
                    return (
                      <div className="p-4 rounded-xl bg-amber-50 border border-amber-100 text-amber-900 font-semibold">
                        {tr('history.referralPattern', { count, drug: drugName || 'medication' })}
                        <button onClick={() => setActiveTab('health')} className="ml-3 underline text-amber-800">View Details</button>
                      </div>
                    );
                  }
                  return null;
                })()}
                {history.map((item, i) => (
                  <div key={i} className="glass-card p-5 flex items-start gap-4 hover:border-slate-300 transition-all group">
                    <div className={`mt-1 p-2 rounded-lg ${item.tier === 'HIGH' ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'}`}>
                      <AlertCircle size={20} />
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-start">
                        <h4 className="font-bold text-slate-900">{item.drug} × {item.food}</h4>
                        <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                          <Clock size={10} />
                          {new Date(item.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-500 mt-1 line-clamp-2">{item.mechanism}</p>
                      <div className="mt-3 flex items-center gap-3">
                        <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded ${
                          item.tier === 'HIGH' ? 'bg-red-500 text-white' : 'bg-blue-500 text-white'
                        }`}>
                          {item.tier}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">Score: {item.score.toFixed(3)}</span>
                        <button
                          type="button"
                          onClick={() => toggleConsumed(item)}
                          disabled={savingHistoryId === item.id}
                          className={`text-[10px] font-bold px-2 py-1 rounded ${item.consumed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}
                        >
                          {savingHistoryId === item.id ? tr('health.saving') : (item.consumed ? tr('history.loggedConsumed') : tr('history.logConsumed'))}
                        </button>
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-slate-300 group-hover:translate-x-1 transition-transform" />
                  </div>
                ))}

                {history.length === 0 && (
                  <div className="text-center py-20 text-slate-400">
                    <History size={48} className="mx-auto mb-4 opacity-10" />
                    <p>{tr('history.none')}</p>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'settings' && (
            <motion.div
              key="settings"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-3xl mx-auto space-y-6"
            >
              <section className="glass-card p-8">
                <h2 className={`text-2xl font-bold mb-2 ${darkMode ? 'text-sky-200' : 'text-clinical-blue'}`}>{tr('settings.title')}</h2>
                <p className="text-slate-500 text-sm mb-8">{tr('settings.subtitle')}</p>

                <div className="space-y-8">
                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">{tr('settings.language')}</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {[
                        { value: 'en', label: 'English' },
                        { value: 'fr', label: 'Français' },
                        { value: 'ar', label: 'العربية' },
                      ].map((item) => (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => setLanguage(item.value as 'en' | 'fr' | 'ar')}
                          className={`px-4 py-3 rounded-xl border font-semibold transition-all ${language === item.value ? 'bg-clinical-blue text-white border-clinical-blue' : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300'}`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">{tr('settings.appearance')}</h3>
                    <button
                      type="button"
                      onClick={() => setDarkMode((prev) => !prev)}
                      className={`w-full flex items-center justify-between px-4 py-4 rounded-xl border transition-all ${darkMode ? 'bg-slate-900 text-slate-100 border-slate-700' : 'bg-white text-slate-800 border-slate-200'}`}
                    >
                      <span className="font-semibold">{darkMode ? tr('settings.darkEnabled') : tr('settings.lightEnabled')}</span>
                      <span className="inline-flex items-center gap-2 text-sm">
                        {darkMode ? <Moon size={16} /> : <Sun size={16} />}
                        {darkMode ? tr('settings.dark') : tr('settings.light')}
                      </span>
                    </button>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white/80 p-5 space-y-3">
                    <div>
                      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-2">
                        <KeyRound size={14} />
                        {tr('settings.shareCode')}
                      </h3>
                      <p className="text-sm text-slate-500">{tr('settings.shareCodeHint')}</p>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
                      <button
                        type="button"
                        onClick={generateShareCode}
                        disabled={shareCodeLoading}
                        className="inline-flex items-center justify-center gap-2 rounded-xl bg-clinical-blue px-4 py-3 text-white font-bold disabled:opacity-60"
                      >
                        <Link2 size={14} />
                        {shareCodeLoading ? tr('common.wait') : tr('settings.generateShareCode')}
                      </button>
                      {shareCode && (
                        <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-blue-900 font-mono tracking-[0.3em] text-lg">
                          {shareCode}
                        </div>
                      )}
                    </div>
                    {shareCodeNotice && (
                      <div className={`text-xs font-semibold ${shareCodeNotice.type === 'success' ? 'text-emerald-700' : 'text-rose-700'}`}>
                        {shareCodeNotice.text}
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {showReferralWhyModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-120 flex items-center justify-center p-6"
              onClick={() => setShowReferralWhyModal(false)}
            >
              <motion.div
                initial={{ scale: 0.95, y: 16 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 16 }}
                className={`rounded-3xl p-6 max-w-xl w-full shadow-2xl ${darkMode ? 'bg-slate-900 border border-slate-700' : 'bg-white'}`}
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className={`text-xl font-black mb-2 ${darkMode ? 'text-slate-100' : 'text-slate-900'}`}>{tr('referral.whyTitle')}</h3>
                <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 mb-4">
                  {getReferralUrgencyLabel()}
                </div>

                <p className={`text-sm leading-relaxed mb-4 ${darkMode ? 'text-slate-200' : 'text-slate-700'}`}>{getReferralReasonText()}</p>

                <div className={`rounded-xl p-3 mb-4 ${darkMode ? 'border border-slate-700 bg-slate-800/50' : 'border border-slate-200'}`}>
                  <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${darkMode ? 'text-slate-300' : 'text-slate-500'}`}>{tr('referral.recommendedTests')}</div>
                  <div className="flex flex-wrap gap-2">
                    {(String(getPrimaryReferralAction()?.recommended_tests || '')
                      .split(',')
                      .map((v: string) => v.trim())
                      .filter(Boolean)
                    ).map((test: string, idx: number) => (
                      <span key={`${test}-${idx}`} className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${darkMode ? 'bg-sky-900/40 text-sky-200 border-sky-700/60' : 'bg-blue-50 text-blue-700 border-blue-100'}`}>
                        {test}
                      </span>
                    ))}
                  </div>
                </div>

                <div className={`rounded-xl px-3 py-2 mb-5 text-xs font-medium ${darkMode ? 'border border-emerald-700/50 bg-emerald-900/30 text-emerald-200' : 'border border-emerald-100 bg-emerald-50 text-emerald-800'}`}>
                  {tr('referral.nextAction')}
                </div>

                <div className="flex gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => setShowReferralWhyModal(false)}
                    className={`px-4 py-2 rounded-xl text-sm font-bold ${darkMode ? 'bg-slate-800 text-slate-100 border border-slate-700' : 'bg-slate-100 text-slate-700'}`}
                  >
                    {tr('referral.close')}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
          {nearbyLabsOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-120 flex items-center justify-center p-6"
              onClick={() => setNearbyLabsOpen(false)}
            >
              <motion.div
                initial={{ scale: 0.95, y: 16 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 16 }}
                className="bg-white rounded-3xl p-6 max-w-lg w-full shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className={`text-xl font-black mb-4 ${darkMode ? 'text-slate-100' : 'text-slate-900'}`}>{tr('referral.nearbyLabsTitle')}</h3>
                <div className="space-y-3 max-h-64 overflow-auto">
                  {nearbyLabs.length === 0 ? (
                    <div className="text-sm text-slate-500">{tr('referral.noNearbyLabs')}</div>
                  ) : (
                    nearbyLabs.map((lab: any, li: number) => (
                      <div key={li} className="p-3 border rounded-lg flex justify-between items-center">
                        <div>
                          <div className="font-bold">{lab.name}</div>
                          <div className="text-xs text-slate-500">{lab.address || lab.city} • {lab.distance_km ? `${lab.distance_km.toFixed(1)} km` : ''}</div>
                        </div>
                        <div className="text-right">
                          {lab.discount_code && <div className="text-xs font-bold text-emerald-700">{lab.discount_code}</div>}
                          {lab.phone && <div className="text-xs text-slate-500">{lab.phone}</div>}
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-4 flex justify-end">
                  <button onClick={() => setNearbyLabsOpen(false)} className="px-4 py-2 rounded-xl bg-slate-100">{tr('referral.close')}</button>
                </div>
              </motion.div>
            </motion.div>
          )}
          {showExportModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-120 flex items-center justify-center p-6"
              onClick={() => setShowExportModal(false)}
            >
              <motion.div
                initial={{ scale: 0.95, y: 16 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 16 }}
                className="bg-white rounded-3xl p-8 max-w-lg w-full shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className={`text-xl font-black mb-4 ${darkMode ? 'text-slate-100' : 'text-slate-900'}`}>{tr('history.exportTitle')}</h3>
                <p className="text-sm text-slate-600 mb-4">{tr('history.exportPrompt')}</p>
                <div className="space-y-3 text-sm">
                  <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                    {tr('history.includeConsumedOnly')}
                  </p>
                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={exportIncludeBloodTrends}
                      onChange={(e) => setExportIncludeBloodTrends(e.target.checked)}
                    />
                    {tr('history.includeBlood')}
                  </label>
                </div>
                <div className="mt-6 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowExportModal(false)}
                    className="flex-1 bg-slate-100 text-slate-700 font-bold py-3 rounded-xl"
                  >
                    {tr('common.cancel')}
                  </button>
                  <button
                    type="button"
                    onClick={exportDoctorReport}
                    className="flex-1 bg-clinical-blue text-white font-bold py-3 rounded-xl"
                  >
                    {tr('common.export')} {subscription.isPremium ? '' : tr('common.proSuffix')}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

