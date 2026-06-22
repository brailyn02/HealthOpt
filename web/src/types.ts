export enum ConfidenceTier {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
  INSUFFICIENT = 'INSUFFICIENT'
}

export interface InteractionResult {
  drug: string;
  food: string;
  tier: ConfidenceTier;
  score: number;
  mechanism?: string;
  flags: string[];
  physicochemicalWarnings?: string[];
  graphPath?: string[];
  nutritionalContext?: {
    nutrient: string;
    severity: 'mild' | 'moderate' | 'severe';
  };
}

export interface PatientProfile {
  gender: 'male' | 'female';
  age?: number | null;
  cycleDay?: number;
  biomarkers: {
    ferritin?: number;
    hemoglobin?: number;
    vitaminD?: number;
    calcium?: number;
    b12?: number;
    magnesium?: number;
    zinc?: number;
    folate?: number;
  };
}
